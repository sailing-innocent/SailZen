# -*- coding: utf-8 -*-
# @file quick_agent.py
# @brief SailTick 白天快反对话代理（查询专家简报 + 灵活调计划 + 食物秒查 + 一句话设提醒）
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""QuickCoachAgent — 白天快速反应助手（System 1 快脑）。

设计定位：
- 不跑重型 Tick 状态机、不直连全量长周期库；
- 秒级读取 SailTick 专家最新结论（expert_brief）+ 食物热量库 + 健康师知识卡片；
- 面向 QQ Bot / CLI / 快捷 API 提供 1-3 秒低延迟回复（优先走 deepseek-chat 等非推理快模型）；
- 支持高频白天场景：
  1. 突发早下班 → 结合画像与今日精力，给出可执行的运动+晚餐安排；
  2. 突发同学聚餐/应酬 → 给出控损策略与次日回稳方案，并异步通知慢脑微调动态计划；
  3. 食物热量秒查 → 命中本地知识库秒答，未命中则快速估算并入队待夜间慢脑深度核查；
  4. 一句话定时提醒 → 如「下班前提醒我别忘了买洗衣液和七号电池」，解析时间写入 sail_server Reminder
     （Android 到点弹窗）+ 本地 Nudge 队列（QQ Bot 到点私聊双推）；
  5. 顺手记录体重/饮食。
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from sailtick.config import SailTickConfig
from sailtick.db import TickDatabase
from sailtick.inbox import TicketInbox
from sailtick.knowledge import HealthKnowledgeManager
from sailtick.memory import AgentMemory
from sailtick.nightly import NightlySelfMaintenance

logger = logging.getLogger(__name__)


def parse_reminder_time(
    text: str,
    now: datetime,
    default_offwork_time: str = "18:00",
    offwork_lead_minutes: int = 20,
) -> Tuple[datetime, str]:
    """从中文自然语言中解析提醒触发时间，返回 (trigger_dt, human_label)。"""
    s = (text or "").strip()

    # 1. 相对分钟/小时：「30分钟后」「半小时后」「2小时后」
    m_half = re.search(r"半(?:个)?小时后", s)
    if m_half:
        dt = now + timedelta(minutes=30)
        return dt.replace(second=0, microsecond=0), dt.strftime("%m-%d %H:%M")

    m_min = re.search(r"(\d{1,3})\s*(?:分钟|分)后", s)
    if m_min:
        dt = now + timedelta(minutes=int(m_min.group(1)))
        return dt.replace(second=0, microsecond=0), dt.strftime("%m-%d %H:%M")

    m_hr = re.search(r"(\d{1,2})\s*(?:个)?小时后", s)
    if m_hr:
        dt = now + timedelta(hours=int(m_hr.group(1)))
        return dt.replace(second=0, microsecond=0), dt.strftime("%m-%d %H:%M")

    # 2. 日期偏移前缀
    day_offset = 0
    if "后天" in s:
        day_offset = 2
    elif "明天" in s or "明早" in s or "明晚" in s:
        day_offset = 1
    target_date = (now + timedelta(days=day_offset)).date()

    # 3. 显式时刻：「17:30」「18：00」「下午5点半」「晚上8点15」「明早8点」
    m_colon = re.search(r"(?<!\d)(\d{1,2})[:：](\d{2})(?!\d)", s)
    if m_colon:
        hh, mm = int(m_colon.group(1)), int(m_colon.group(2))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            dt = datetime(target_date.year, target_date.month, target_date.day, hh, mm)
            if day_offset == 0 and dt <= now:
                dt += timedelta(days=1)
            return dt, dt.strftime("%m-%d %H:%M")

    m_cn = re.search(r"(早上|上午|中午|下午|傍晚|晚上|明早|明晚)?\s*(\d{1,2})\s*点\s*(半|\d{1,2})?", s)
    if m_cn:
        period = m_cn.group(1) or ""
        hh = int(m_cn.group(2))
        mm_raw = m_cn.group(3)
        mm = 30 if mm_raw == "半" else (int(mm_raw) if mm_raw and mm_raw.isdigit() else 0)
        if period in ("下午", "傍晚", "晚上", "明晚") and 1 <= hh <= 11:
            hh += 12
        elif period == "中午" and 1 <= hh <= 3:
            hh += 12
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            dt = datetime(target_date.year, target_date.month, target_date.day, hh, mm)
            if day_offset == 0 and dt <= now:
                dt += timedelta(days=1)
            return dt, dt.strftime("%m-%d %H:%M")

    # 4. 语义锚点：「下班前」「下班时」「午休前」「睡前」「明早」
    if "下班" in s:
        try:
            oh, om = [int(x) for x in default_offwork_time.strip().split(":", 1)]
        except Exception:
            oh, om = 18, 0
        base = datetime(target_date.year, target_date.month, target_date.day, oh, om)
        lead = offwork_lead_minutes if "前" in s else 0
        dt = base - timedelta(minutes=lead)
        if day_offset == 0 and dt <= now:
            # 若已经过了下班前时间，仍在今天下班时间前则取 10 分钟后，否则明天
            if now < base:
                dt = now + timedelta(minutes=10)
            else:
                dt = dt + timedelta(days=1)
        return dt.replace(second=0, microsecond=0), dt.strftime("%m-%d %H:%M")

    if "睡前" in s:
        dt = datetime(target_date.year, target_date.month, target_date.day, 22, 0)
        if day_offset == 0 and dt <= now:
            dt += timedelta(days=1)
        return dt, dt.strftime("%m-%d %H:%M")

    if "午饭" in s or "中午" in s:
        dt = datetime(target_date.year, target_date.month, target_date.day, 11, 45)
        if day_offset == 0 and dt <= now:
            dt += timedelta(days=1)
        return dt, dt.strftime("%m-%d %H:%M")

    if "明早" in s or "明天" in s:
        dt = datetime(target_date.year, target_date.month, target_date.day, 8, 30)
        return dt, dt.strftime("%m-%d %H:%M")

    # 默认兜底：30 分钟后
    dt = (now + timedelta(minutes=30)).replace(second=0, microsecond=0)
    return dt, dt.strftime("%m-%d %H:%M")


def extract_reminder_subject(text: str) -> str:
    """从「下班前提醒我别忘了买洗衣液和七号电池」提取干净提醒事项标题。"""
    s = (text or "").strip()
    m = re.search(r"提醒(?:我|一下)?(?:别忘了|不要忘了|记得|要)?(.+)", s)
    subj = m.group(1) if m else s
    subj = re.sub(r"^(?:别忘了|不要忘了|千万别忘|记得|要|去|一下|帮我)", "", subj).strip(" ，。！？!?,.")
    return subj[:60] if subj else s[:60]


class QuickCoachAgent:
    """SailTick 白天快速对话与生活提醒助手。"""

    def __init__(
        self,
        config: SailTickConfig,
        db: TickDatabase,
        memory: AgentMemory,
        inbox: TicketInbox,
        llm: Any = None,
        knowledge: Optional[HealthKnowledgeManager] = None,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.config = config
        self.db = db
        self.memory = memory
        self.inbox = inbox
        self.llm = llm
        self._clock = clock
        self.knowledge = knowledge or HealthKnowledgeManager(
            db=db,
            llm=llm,
            enable_web_search=config.nightly.enable_web_search,
            web_search_timeout=config.nightly.web_search_timeout,
        )

    async def handle_message(
        self,
        text: str,
        channel: str = "api",
        user_id: str = "owner",
        session_id: Optional[str] = None,
        target_type: str = "private",
        target_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """处理一条用户即时消息，返回快速回复与已执行动作摘要。"""
        t0 = time.perf_counter()
        clean_text = (text or "").strip()
        if not clean_text:
            return {
                "reply": "发一句想问的事或提醒就行，比如「今天能早下班怎么安排」或「下班前提醒我买洗衣液」。",
                "actions": [],
                "reminders_created": [],
                "source": "empty",
                "latency_ms": 0.0,
            }

        await self.knowledge.ensure_seeded()
        sess_key = session_id or f"{channel}:{user_id or 'owner'}"
        reply_target_id = str(target_id or user_id or self.config.qq_bot.primary_user_id or "")

        # 1. 优先处理零延迟斜杠快捷指令（/brief /predict /food /remind /help）
        cmd_res = await self._try_command(clean_text)
        if cmd_res is not None:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return {
                **cmd_res,
                "session_id": sess_key,
                "latency_ms": latency_ms,
            }

        # 2. 装载专家简报 + 匹配食物热量 + 相关健康知识 + 短期对话上下文
        brief = await self.db.get_runtime_state("expert_brief")
        profile_dict = await self.memory.all_profile()
        matched_foods = await self.knowledge.lookup_foods_in_text(clean_text, limit=4)
        matched_knowledge = await self.knowledge.retrieve_knowledge(clean_text, limit=3)
        history = await self.db.list_quick_chat_history(
            sess_key, limit=max(2, self.config.quick_chat.history_turns)
        )

        # 3. 决策回复与动作（优先快模型，无 LLM 时自动规则兜底）
        plan_source = "rule_fallback"
        reply_text = ""
        raw_actions: List[Dict[str, Any]] = []

        llm_ready = bool(
            self.llm is not None
            and getattr(self.llm, "config", None)
            and self.llm.config.providers
        )
        if llm_ready:
            try:
                llm_out = await self._ask_fast_llm(
                    clean_text=clean_text,
                    brief=brief,
                    profile_dict=profile_dict,
                    matched_foods=matched_foods,
                    matched_knowledge=matched_knowledge,
                    history=history,
                )
                if llm_out and llm_out.get("reply"):
                    reply_text = str(llm_out["reply"]).strip()
                    raw_actions = list(llm_out.get("actions") or [])
                    plan_source = "fast_llm"
            except Exception as exc:
                logger.warning("QuickCoachAgent fast LLM failed, using rule fallback: %s", exc)

        if not reply_text:
            fb = self._rule_fallback(
                clean_text=clean_text,
                brief=brief,
                profile_dict=profile_dict,
                matched_foods=matched_foods,
                matched_knowledge=matched_knowledge,
            )
            reply_text = fb["reply"]
            raw_actions = fb["actions"]

        # 4. 执行轻量工具动作（创建提醒 / 同步计划微调给慢脑 / 记体重 / 记饮食 / 入队待查食物）
        executed_actions: List[Dict[str, Any]] = []
        reminders_created: List[Dict[str, Any]] = []
        for act in raw_actions:
            if not isinstance(act, dict):
                continue
            res = await self._execute_action(
                act=act,
                raw_text=clean_text,
                channel=channel,
                target_type=target_type,
                target_id=reply_target_id,
                profile_dict=profile_dict,
            )
            if res:
                executed_actions.append(res)
                if res.get("kind") == "create_reminder" and res.get("ok"):
                    reminders_created.append(res)

        # 5. 保存短期对话历史（供下轮追问）
        await self.db.append_quick_chat(
            sess_key, "user", clean_text, channel=channel, user_id=str(user_id or "")
        )
        await self.db.append_quick_chat(
            sess_key,
            "assistant",
            reply_text,
            channel=channel,
            user_id=str(user_id or ""),
            actions=executed_actions,
        )

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "reply": reply_text,
            "actions": executed_actions,
            "reminders_created": reminders_created,
            "expert_brief_date": (brief or {}).get("snapshot_date") if isinstance(brief, dict) else None,
            "foods_matched": [f["name"] for f in matched_foods],
            "source": plan_source,
            "session_id": sess_key,
            "latency_ms": latency_ms,
        }

    # ── 快捷指令（零 LLM 延迟） ───────────────────────────────────────

    async def _try_command(self, text: str) -> Optional[Dict[str, Any]]:
        low = text.lower().strip()
        if low in ("/help", "/帮助", "帮助"):
            return {
                "reply": (
                    "SailTick 快反助手在线！你可以直接像聊天一样说：\n"
                    "• 临时变动：「今天能早下班，下班后怎么安排？」「今晚同学聚餐计划怎么调？」\n"
                    "• 顺手设提醒：「下班前提醒我别忘了买洗衣液和七号电池」「30分钟后提醒我喝水」\n"
                    "• 查热量/记数据：「牛肉面多少大卡」「今早体重 73.6」\n"
                    "• 快捷命令：/brief 专家简报 · /predict 体重预测 · /food 食物名 · /remind 待办提醒"
                ),
                "actions": [],
                "reminders_created": [],
                "source": "command",
            }

        if low in ("/brief", "/简报", "专家简报"):
            brief = await self.db.get_runtime_state("expert_brief")
            if not brief:
                return {
                    "reply": "SailTick 专家尚未完成首次夜间深度建模，你可以稍等今晚 00:00 自动分析，或手动触发一次夜间分析。",
                    "actions": [],
                    "reminders_created": [],
                    "source": "command",
                }
            return {
                "reply": "【SailTick 专家简报】\n" + NightlySelfMaintenance.format_brief_for_prompt(brief),
                "actions": [],
                "reminders_created": [],
                "source": "command",
            }

        if low in ("/predict", "/预测", "体重预测"):
            brief = await self.db.get_runtime_state("expert_brief")
            mod = (brief or {}).get("modeling") if isinstance(brief, dict) else None
            if not mod or not mod.get("sample_count"):
                return {
                    "reply": "目前还没有足够的体重建模样本，连续记录几天晨起体重后，夜间建模会自动算出精准预测区间。",
                    "actions": [],
                    "reminders_created": [],
                    "source": "command",
                }
            pts = mod.get("forecast_points") or []
            pts_lines = [
                f"• +{p['days']}天({p['date']}): 约 {p['predicted_kg']}kg（区间 {p['low_kg']}~{p['high_kg']}kg）"
                for p in pts
            ]
            msg = (
                f"【数学模型预测】({mod.get('model_type')}, 信心 {mod.get('confidence_score')}/100)\n"
                f"{mod.get('confidence_message', '')}\n"
                + ("\n".join(pts_lines) if pts_lines else "")
            )
            return {
                "reply": msg.strip(),
                "actions": [],
                "reminders_created": [],
                "source": "command",
            }

        if low.startswith("/food ") or low.startswith("/热量 "):
            q = text.split(None, 1)[1].strip()
            hits = await self.knowledge.lookup_foods_in_text(q, limit=3)
            if hits:
                lines = ["【食物热量速查】"]
                for f in hits:
                    lines.append(
                        f"• {f['name']}（{f.get('serving_desc', '1份')}）：约 {f.get('kcal_per_serving') or f.get('kcal_per_100g')} kcal"
                        f"（蛋白 {f.get('protein_g') or '-'}g / 碳水 {f.get('carbs_g') or '-'}g / 脂肪 {f.get('fat_g') or '-'}g，GI:{f.get('gi_level')}）"
                    )
                    if f.get("lighter_swap"):
                        lines.append(f"  轻负担吃法：{f['lighter_swap']}")
                return {
                    "reply": "\n".join(lines),
                    "actions": [],
                    "reminders_created": [],
                    "source": "command",
                }
            await self.knowledge.enqueue_food_research([q])
            return {
                "reply": f"本地营养库暂未收录「{q}」，已加入 SailTick 今晚自主查证队列，明天就能秒查精准数据啦。",
                "actions": [{"kind": "enqueue_food_research", "foods": [q], "ok": True}],
                "reminders_created": [],
                "source": "command",
            }

        if low in ("/remind", "/提醒", "待办提醒", "今日提醒"):
            nudges = await self.db.list_pending_nudges(limit=10)
            server_rems: List[Dict[str, Any]] = []
            try:
                if await self.inbox.health():
                    server_rems = await self.inbox.list_pending_reminders()
            except Exception:
                pass
            lines: List[str] = []
            seen_titles = set()
            for n in nudges:
                t_str = str(n.get("trigger_at") or "")[5:16].replace("T", " ")
                lines.append(f"• [{t_str}] {n.get('title')}")
                seen_titles.add(n.get("title"))
            for r in server_rems[:8]:
                title = r.get("title") or ""
                if title in seen_titles:
                    continue
                t_str = str(r.get("trigger_time") or "")[5:16].replace("T", " ")
                lines.append(f"• [{t_str}] {title}")
            reply = "【待触发提醒】\n" + "\n".join(lines) if lines else "当前没有待触发的提醒，直接跟我说「下班前提醒我买xxx」就能建一条。"
            return {
                "reply": reply,
                "actions": [],
                "reminders_created": [],
                "source": "command",
            }

        return None

    # ── 快速 LLM 推理 ─────────────────────────────────────────────────

    async def _ask_fast_llm(
        self,
        clean_text: str,
        brief: Optional[Dict[str, Any]],
        profile_dict: Dict[str, Any],
        matched_foods: List[Dict[str, Any]],
        matched_knowledge: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        now = self._clock()
        offwork = self._resolve_offwork_time(profile_dict)
        brief_text = NightlySelfMaintenance.format_brief_for_prompt(brief)
        playbooks = (brief or {}).get("flexible_playbooks") if isinstance(brief, dict) else {}
        playbook_text = "\n".join(f"- {k}: {v}" for k, v in (playbooks or {}).items()) or "(默认温和健康教练策略)"

        food_text = "\n".join(
            f"- {f['name']}({f.get('serving_desc')}): 约{f.get('kcal_per_serving')}kcal "
            f"(P:{f.get('protein_g')}g C:{f.get('carbs_g')}g F:{f.get('fat_g')}g) | 建议: {f.get('lighter_swap')}"
            for f in matched_foods
        ) or "(无命中)"

        kn_text = "\n".join(
            f"- [{k.get('domain')}] {k.get('title')}: {k.get('summary')} 要点: {'; '.join((k.get('key_points') or [])[:3])}"
            for k in matched_knowledge
        ) or "(无)"

        system_prompt = f"""你是 SailTick 的「白天快速反应助手」（常驻 QQ / 快捷对话端）。
你的核心职责是：快速查询并转达 SailTick 夜间专家的建模结论与专业策略，灵活回应用户白天的临时变动（早下班安排、突发同学聚餐、热量询问、情绪安抚），并帮用户顺手设置定时提醒或记录体重/饮食。

当前时间：{now.strftime('%Y-%m-%d %H:%M')}（星期{'一二三四五六日'[now.weekday()]}）
默认下班时间：{offwork}（若用户说「下班前提醒我...」，默认提前 {self.config.quick_chat.offwork_lead_minutes} 分钟触发）

【SailTick 专家最新简报】
{brief_text}

【专家应急预案】
{playbook_text}

【命中的食物热量库】
{food_text}

【命中的专业健康师知识】
{kn_text}

回复风格要求：
1. 适合手机/QQ 快速阅读：温和、口语化、有同理心、不苛责、不长篇大论（一般 3-6 行，必要时用短要点）。
2. 如果用户询问早下班安排，给出 2 个按精力分档的轻量可执行方案（运动+晚餐衔接）。
3. 如果用户临时要同学聚餐/应酬，先肯定开心赴约，再给 2-3 条零压力控损技巧和次日回稳提示，并附带 `plan_adjust_signal` action 通知慢脑在晚间同步微调计划。
4. 如果用户要求设提醒（如买洗衣液、七号电池、喝水、拿快递等生活杂事也完全支持！），必须输出 `create_reminder` action，算出精确的本地 ISO 时间 `YYYY-MM-DDTHH:MM:00`，并在回复中明确告知设好的提醒时间和内容。
5. 如果用户问了食物热量但【命中的食物热量库】为空，先给合理估算，同时附带 `enqueue_food_research` 让夜间慢脑今晚深入查证。

严格只输出 JSON：
{{
  "reply": "直接发给用户的回复文本",
  "actions": [
    {{"kind": "create_reminder", "title": "买洗衣液和七号电池", "body": "下班顺路买洗衣液和七号电池", "trigger_time": "2026-11-23T17:40:00", "priority": "normal"}},
    {{"kind": "plan_adjust_signal", "scene": "social_dining|early_offwork|stress|other", "summary": "一句话记录今日计划微调"}},
    {{"kind": "log_diet", "meal_type": "breakfast|lunch|dinner|snack", "description": "饮食内容", "calories": 500}},
    {{"kind": "log_weight", "weight_kg": 73.6}},
    {{"kind": "enqueue_food_research", "foods": ["未知食物名"]}}
  ]
}}
不需要动作时 actions 输出 []。"""

        hist_msgs = [{"role": h["role"], "content": h["content"]} for h in history[-6:]]
        if hasattr(self.llm, "chat_fast"):
            resp = await self.llm.chat_fast(
                clean_text,
                system=system_prompt,
                history=hist_msgs,
                expect_json=True,
                max_tokens=900,
            )
        else:
            resp = await self.llm.chat(
                f"{system_prompt}\n\n用户消息：{clean_text}",
                expect_json=True,
                max_tokens=900,
            )
        parsed = HealthKnowledgeManager._parse_json_safe(getattr(resp, "content", ""))
        return parsed

    # ── 无 LLM 确定性规则兜底 ─────────────────────────────────────────

    def _rule_fallback(
        self,
        clean_text: str,
        brief: Optional[Dict[str, Any]],
        profile_dict: Dict[str, Any],
        matched_foods: List[Dict[str, Any]],
        matched_knowledge: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        now = self._clock()
        offwork = self._resolve_offwork_time(profile_dict)
        actions: List[Dict[str, Any]] = []

        # 1. 定时提醒识别
        if "提醒" in clean_text:
            trig_dt, label = parse_reminder_time(
                clean_text,
                now=now,
                default_offwork_time=offwork,
                offwork_lead_minutes=self.config.quick_chat.offwork_lead_minutes,
            )
            subject = extract_reminder_subject(clean_text)
            actions.append(
                {
                    "kind": "create_reminder",
                    "title": subject,
                    "body": f"到点提醒：{subject}",
                    "trigger_time": trig_dt.isoformat(),
                    "priority": "normal",
                }
            )
            return {
                "reply": f"好嘞，已经记下了！我会在 {label} 准时提醒你：{subject}。",
                "actions": actions,
            }

        # 2. 体重快速记录
        m_w = re.search(r"体重[^\d]{0,4}(\d{2,3}(?:\.\d{1,2})?)", clean_text)
        if m_w:
            wval = float(m_w.group(1))
            if 35.0 <= wval <= 200.0:
                actions.append({"kind": "log_weight", "weight_kg": wval})
                ewma = ((brief or {}).get("goal") or {}).get("ewma_weight_kg")
                hint = f"（当前平滑均值约 {ewma}kg，单日小波动都很正常）" if ewma else ""
                return {
                    "reply": f"已帮你记下体重 {wval:.1f}kg {hint}，今晚睡前日报会自动更新趋势曲线。",
                    "actions": actions,
                }

        # 3. 突发聚餐/应酬
        if any(k in clean_text for k in ("聚餐", "应酬", "请客", "火锅", "烧烤", "同学聚")):
            pb = ((brief or {}).get("flexible_playbooks") or {}).get("social_dining") or (
                "开心去聚餐就好！遵循「先喝水→先吃蔬菜→再吃瘦肉鱼虾→最后少量主食」，饮品选无糖茶，"
                "明天如果因为高盐涨了 0.5-1kg 多半是水分，多喝水清淡吃两天就回来，不用节食。"
            )
            actions.append(
                {
                    "kind": "plan_adjust_signal",
                    "scene": "social_dining",
                    "summary": f"用户白天反馈突发聚餐：{clean_text[:120]}",
                }
            )
            return {
                "reply": f"完全可以灵活调整计划，聚餐开心最重要！SailTick 专家给的控损方案：\n{pb}\n（我已同步通知主教练，今晚日报和后续计划会自动帮你留出缓冲。）",
                "actions": actions,
            }

        # 4. 提前/早下班安排
        if any(k in clean_text for k in ("早下班", "早点下班", "提前下班", "下班后", "下班安排")):
            pb = ((brief or {}).get("flexible_playbooks") or {}).get("early_offwork") or (
                "精力还不错的话：15分钟居家/健身房抗阻 + 30分钟快走或慢跑；\n"
                "如果有点累：户外快走 25-30 分钟听点喜欢的播客，回家做 10 分钟拉伸。\n"
                "晚餐保证一份优质蛋白（鸡胸/瘦牛肉/鱼虾/鸡蛋）+ 青菜 + 半碗主食就很完美。"
            )
            actions.append(
                {
                    "kind": "plan_adjust_signal",
                    "scene": "early_offwork",
                    "summary": f"用户今天可提前下班，已给下班后运动与晚餐建议：{clean_text[:120]}",
                }
            )
            return {
                "reply": f"难得能早点下班，太棒了！按 SailTick 专家的建议，可以按今天精力二选一：\n{pb}",
                "actions": actions,
            }

        # 5. 食物热量查询
        if matched_foods and any(k in clean_text for k in ("热量", "大卡", "千卡", "能吃", "胖", "吃了")):
            f = matched_foods[0]
            return {
                "reply": (
                    f"「{f['name']}」（{f.get('serving_desc', '1份')}）大约 {f.get('kcal_per_serving') or f.get('kcal_per_100g')} kcal"
                    f"（蛋白 {f.get('protein_g') or '-'}g / 碳水 {f.get('carbs_g') or '-'}g / 脂肪 {f.get('fat_g') or '-'}g）。\n"
                    f"轻负担建议：{f.get('lighter_swap') or '搭配蔬菜和优质蛋白更稳血糖。'}"
                ),
                "actions": [],
            }

        # 6. 命中健康师知识卡片或播报专家结论
        if matched_knowledge:
            kn = matched_knowledge[0]
            pts = "\n".join(f"• {p}" for p in (kn.get("key_points") or [])[:3])
            return {
                "reply": f"参考 SailTick 专家的建议（{kn['title']}）：\n{kn['summary']}\n{pts}",
                "actions": [],
            }

        conf_msg = ((brief or {}).get("modeling") or {}).get("confidence_message")
        if conf_msg:
            return {
                "reply": f"收到！转达一下 SailTick 专家最新结论：{conf_msg}\n需要我帮你调整今晚安排或设个提醒直接说就行。",
                "actions": [],
            }

        return {
            "reply": "收到啦！我可以随时帮你转达 SailTick 专家的体重趋势与饮食运动建议，也能帮你设定时提醒（比如「下班前提醒我买洗衣液」）。",
            "actions": [],
        }

    # ── 工具动作执行 ──────────────────────────────────────────────────

    async def _execute_action(
        self,
        act: Dict[str, Any],
        raw_text: str,
        channel: str,
        target_type: str,
        target_id: str,
        profile_dict: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        kind = str(act.get("kind") or "").strip()
        if not kind:
            return None

        if kind == "create_reminder" and self.config.quick_chat.allow_reminder_create:
            title = str(act.get("title") or extract_reminder_subject(raw_text)).strip()
            body = str(act.get("body") or f"提醒：{title}").strip()
            priority = str(act.get("priority") or "normal")
            trig_dt = self._parse_iso_or_fallback(
                act.get("trigger_time"), raw_text, profile_dict
            )
            server_rem_id: Optional[int] = None
            server_ok = False
            try:
                if await self.inbox.health():
                    rem = await self.inbox.create_reminder(
                        title=title,
                        trigger_time=trig_dt,
                        body=body,
                        priority=priority,
                        rem_type="agent.quick_reminder",
                        payload={"channel": channel, "from_quick_chat": True},
                    )
                    server_rem_id = rem.get("id")
                    server_ok = True
            except Exception as exc:
                logger.warning("QuickCoachAgent create_reminder on sail_server failed: %s", exc)

            # 同步写入本地 Nudge 队列（若来自 QQ 或启用了 QQ Bot，到点同时发 QQ 私聊提醒）
            nudge_channel = "qq" if (channel == "qq" or self.config.qq_bot.enabled) else channel
            nudge = await self.db.create_scheduled_nudge(
                title=title,
                body=body,
                trigger_at=trig_dt.isoformat(),
                channel=nudge_channel,
                target_id=target_id,
                target_type=target_type,
                server_reminder_id=server_rem_id,
            )
            return {
                "kind": "create_reminder",
                "ok": True,
                "title": title,
                "trigger_time": trig_dt.isoformat(),
                "server_reminder_id": server_rem_id,
                "server_synced": server_ok,
                "nudge_id": nudge["id"],
            }

        if kind == "plan_adjust_signal" and self.config.quick_chat.allow_plan_adjust_signal:
            summary = str(act.get("summary") or raw_text).strip()
            scene = str(act.get("scene") or "other")
            await self.memory.save_episode(
                None,
                "quick_plan_adjustment",
                {"scene": scene, "summary": summary, "channel": channel},
            )
            msg_id = None
            try:
                if await self.inbox.health():
                    res = await self.inbox.create_user_message(
                        content=f"[快反日程变动:{scene}] {summary}",
                        category="daily_info",
                        meta={"scene": scene, "from_quick_chat": True, "raw_text": raw_text[:200]},
                        source_channel=channel,
                        auto_log_diet=False,
                    )
                    msg_id = res.get("id")
            except Exception as exc:
                logger.warning("QuickCoachAgent sync plan_adjust_signal failed: %s", exc)
            return {
                "kind": "plan_adjust_signal",
                "ok": True,
                "scene": scene,
                "message_id": msg_id,
            }

        if kind == "log_diet":
            desc = str(act.get("description") or raw_text).strip()
            payload: Dict[str, Any] = {
                "meal_type": str(act.get("meal_type") or "snack"),
                "description": desc,
            }
            if act.get("calories") is not None:
                try:
                    payload["calories"] = float(act["calories"])
                except (ValueError, TypeError):
                    pass
            try:
                if await self.inbox.health():
                    res = await self.inbox.create_diet_log(payload)
                    return {"kind": "log_diet", "ok": True, "id": res.get("id")}
            except Exception as exc:
                logger.warning("QuickCoachAgent log_diet failed: %s", exc)
            return {"kind": "log_diet", "ok": False}

        if kind == "log_weight":
            try:
                w = float(act.get("weight_kg"))
            except (ValueError, TypeError):
                return {"kind": "log_weight", "ok": False}
            try:
                if await self.inbox.health():
                    res = await self.inbox.create_weight_log(w, note=f"via {channel} quick chat")
                    return {"kind": "log_weight", "ok": True, "weight_kg": w, "id": res.get("id")}
            except Exception as exc:
                logger.warning("QuickCoachAgent log_weight failed: %s", exc)
            return {"kind": "log_weight", "ok": False}

        if kind == "enqueue_food_research":
            foods = [str(f) for f in (act.get("foods") or []) if str(f).strip()]
            q = await self.knowledge.enqueue_food_research(foods)
            return {"kind": "enqueue_food_research", "ok": True, "queued": foods, "queue_size": len(q)}

        return None

    def _resolve_offwork_time(self, profile_dict: Dict[str, Any]) -> str:
        for k in ("offwork_time", "work_end_time"):
            entry = profile_dict.get(k)
            if isinstance(entry, dict) and entry.get("value"):
                return str(entry["value"])
        return self.config.quick_chat.default_offwork_time

    def _parse_iso_or_fallback(
        self, raw_iso: Any, raw_text: str, profile_dict: Dict[str, Any]
    ) -> datetime:
        if isinstance(raw_iso, str) and raw_iso.strip():
            try:
                dt = datetime.fromisoformat(raw_iso.strip().replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    dt = dt.astimezone().replace(tzinfo=None)
                return dt
            except ValueError:
                pass
        dt, _ = parse_reminder_time(
            raw_text,
            now=self._clock(),
            default_offwork_time=self._resolve_offwork_time(profile_dict),
            offwork_lead_minutes=self.config.quick_chat.offwork_lead_minutes,
        )
        return dt
