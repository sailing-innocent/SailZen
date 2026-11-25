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
from sailtick.rhythm_client import RhythmClient

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
        rhythm: Optional[RhythmClient] = None,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.config = config
        self.db = db
        self.memory = memory
        self.inbox = inbox
        self.llm = llm
        self._clock = clock
        self.rhythm = rhythm or RhythmClient(
            config.sail_server.api_base,
            config.sail_server.auth_token,
            clock=clock,
        )
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

        # 2. 装载专家简报 + 实时 Rhythm 日程/项目 + 食物热量 + 知识 + 短期对话上下文
        brief = await self.db.get_runtime_state("expert_brief")
        profile_dict = await self.memory.all_profile()
        matched_foods = await self.knowledge.lookup_foods_in_text(clean_text, limit=4)
        matched_knowledge = await self.knowledge.retrieve_knowledge(clean_text, limit=3)
        history = await self.db.list_quick_chat_history(
            sess_key, limit=max(2, self.config.quick_chat.history_turns)
        )
        rhythm_dash = await self._load_live_rhythm()

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
                    rhythm_dash=rhythm_dash,
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
                rhythm_dash=rhythm_dash,
            )
            reply_text = fb["reply"]
            raw_actions = fb["actions"]

        # 4. 执行轻量工具动作（Rhythm 排程/占用/项目/块状态 + 提醒 + 体重/饮食 + 慢脑同步）
        executed_actions: List[Dict[str, Any]] = []
        reminders_created: List[Dict[str, Any]] = []
        rhythm_updated = False
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
                if str(res.get("kind", "")).startswith("rhythm_") and res.get("ok"):
                    rhythm_updated = True

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
            "rhythm_updated": rhythm_updated,
            "expert_brief_date": (brief or {}).get("snapshot_date") if isinstance(brief, dict) else None,
            "foods_matched": [f["name"] for f in matched_foods],
            "source": plan_source,
            "session_id": sess_key,
            "latency_ms": latency_ms,
        }

    async def _load_live_rhythm(self) -> Optional[Dict[str, Any]]:
        try:
            if await self.rhythm.health():
                return await self.rhythm.get_dashboard(self._clock().date())
        except Exception as exc:
            logger.debug("QuickCoachAgent load live rhythm skipped: %s", exc)
        return None

    # ── 快捷指令（零 LLM 延迟） ───────────────────────────────────────

    async def _try_command(self, text: str) -> Optional[Dict[str, Any]]:
        low = text.lower().strip()
        if low in ("/help", "/帮助", "帮助"):
            return {
                "reply": (
                    "SailTick 快反助手（Personal Agent）在线！直接像聊天一样说就行：\n"
                    "• 日程突发变动：「下午2点到4点临时加会，帮我重排今天」「今天太累了晚上只留轻任务」\n"
                    "• 重要项目/待办：「新增项目：下月15号前上线新版本」「把评审文档标完成」\n"
                    "• 生活变动与提醒：「今天早下班怎么安排」「今晚聚餐」「下班前提醒我买洗衣液」\n"
                    "• 快捷命令：/today 今日日程 · /projects 重要项目 · /brief 专家简报 · /predict 体重预测 · /food 食物 · /remind 提醒"
                ),
                "actions": [],
                "reminders_created": [],
                "source": "command",
            }

        if low in ("/today", "/日程", "今日日程", "今日安排", "今天干嘛"):
            dash = await self._load_live_rhythm()
            if not dash:
                return {
                    "reply": "暂时连不上 Rhythm 日程服务，稍后再试。",
                    "actions": [],
                    "reminders_created": [],
                    "source": "command",
                }
            tl = dash.get("timeline") or {}
            blocks = tl.get("blocks") or []
            lines = [f"【今日日程 {dash.get('date', '')}】"]
            if tl.get("ai_rationale"):
                lines.append(f"💡 {tl['ai_rationale']}")
            if blocks:
                for b in blocks[:12]:
                    st = str(b.get("start_time") or "")[11:16]
                    ed = str(b.get("end_time") or "")[11:16]
                    title = b.get("affair_title") or (b.get("ref") or {}).get("label") or b.get("block_type")
                    status = b.get("status", "PLANNED")
                    mark = "✅" if status == "DONE" else ("⏭" if status == "SKIPPED" else ("📌" if b.get("pinned") else "•"))
                    lines.append(f"{mark} {st}-{ed} {title} (#{b.get('id')})")
            else:
                lines.append("今天还没有排好的时间块，跟我说一句你今天最想推进的事，我马上帮你排好。")
            return {
                "reply": "\n".join(lines),
                "actions": [],
                "reminders_created": [],
                "source": "command",
            }

        if low in ("/projects", "/项目", "项目进度", "重要项目"):
            try:
                projects = await self.rhythm.list_projects() if await self.rhythm.health() else []
            except Exception:
                projects = []
            if not projects:
                return {
                    "reply": "目前还没有登记的长期重要项目，直接跟我说「新建项目：xxx，目标下月底前完成」就行。",
                    "actions": [],
                    "reminders_created": [],
                    "source": "command",
                }
            lines = ["【重要项目倒排进度】"]
            for p in projects[:8]:
                dleft = p.get("days_left")
                ddl_part = f"目标 {p.get('target_date')} (剩{dleft}天)" if p.get("target_date") else "未设目标日"
                pct = int((p.get("completion_ratio") or 0) * 100)
                lines.append(f"• #{p.get('affair_id')} {p.get('title')} — {ddl_part} · 里程碑 {pct}% · 近14d投入 {p.get('recent_14d_hours', 0)}h")
            return {
                "reply": "\n".join(lines),
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

    @staticmethod
    def _format_live_rhythm_for_prompt(dash: Optional[Dict[str, Any]]) -> str:
        if not isinstance(dash, dict):
            return "(暂未获取到今日实时日程)"
        tl = dash.get("timeline") or {}
        lines: List[str] = [f"日期: {dash.get('date', '')}"]
        if tl.get("ai_rationale"):
            lines.append(f"当前排程说明: {tl['ai_rationale']}")
        blocks = tl.get("blocks") or []
        if blocks:
            lines.append("今日时间块:")
            for b in blocks[:12]:
                st = str(b.get("start_time") or "")[11:16]
                ed = str(b.get("end_time") or "")[11:16]
                title = b.get("affair_title") or (b.get("ref") or {}).get("label") or b.get("block_type")
                lines.append(
                    f"  - block#{b.get('id')} [{st}-{ed} {b.get('block_type')} {b.get('status')}{' pinned' if b.get('pinned') else ''}] {title}"
                    + (f" (affair#{b.get('affair_id')})" if b.get("affair_id") else "")
                )
        else:
            lines.append("今日时间块: (空)")
        projects = dash.get("projects") or []
        if projects:
            lines.append("活跃重要项目:")
            for p in projects[:6]:
                lines.append(
                    f"  - project#{p.get('affair_id')}「{p.get('title')}」 目标:{p.get('target_date') or '未定'}(剩{p.get('days_left')}天) 进度:{int((p.get('completion_ratio') or 0)*100)}%"
                )
        focus = dash.get("focus_affairs") or []
        if focus:
            lines.append("焦点待办:")
            for a in focus[:8]:
                lines.append(
                    f"  - affair#{a.get('id')}「{a.get('title')}」({a.get('est_minutes')}min, ddl:{str(a.get('urgency_ddl') or '')[:10] or '-'})"
                )
        return "\n".join(lines)

    async def _ask_fast_llm(
        self,
        clean_text: str,
        brief: Optional[Dict[str, Any]],
        profile_dict: Dict[str, Any],
        matched_foods: List[Dict[str, Any]],
        matched_knowledge: List[Dict[str, Any]],
        rhythm_dash: Optional[Dict[str, Any]],
        history: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        now = self._clock()
        today_str = now.strftime("%Y-%m-%d")
        offwork = self._resolve_offwork_time(profile_dict)
        brief_text = NightlySelfMaintenance.format_brief_for_prompt(brief)
        playbooks = (brief or {}).get("flexible_playbooks") if isinstance(brief, dict) else {}
        playbook_text = "\n".join(f"- {k}: {v}" for k, v in (playbooks or {}).items()) or "(默认温和策略)"
        rhythm_text = self._format_live_rhythm_for_prompt(rhythm_dash)

        food_text = "\n".join(
            f"- {f['name']}({f.get('serving_desc')}): 约{f.get('kcal_per_serving')}kcal "
            f"(P:{f.get('protein_g')}g C:{f.get('carbs_g')}g F:{f.get('fat_g')}g) | 建议: {f.get('lighter_swap')}"
            for f in matched_foods
        ) or "(无命中)"

        kn_text = "\n".join(
            f"- [{k.get('domain')}] {k.get('title')}: {k.get('summary')} 要点: {'; '.join((k.get('key_points') or [])[:3])}"
            for k in matched_knowledge
        ) or "(无)"

        system_prompt = f"""你是 SailTick Personal Agent 的「白天快速反应助手」（常驻 Web / QQ / 快捷对话端）。
你统一协助用户处理**日程与项目突发变动（Rhythm）**和**健康减重日常（饮食/运动/体重）**。
你有权直接调用 Rhythm API 帮用户更新今日/明日可视化时间线、钉入临时会议/请假、新建或更新重要项目/待办、标记完成或跳过——让用户用自然语言一句话就能搞定，绝不让用户去填复杂 PM 表单。

当前时间：{now.strftime('%Y-%m-%d %H:%M')}（星期{'一二三四五六日'[now.weekday()]}）
默认下班时间：{offwork}（若用户说「下班前提醒我...」，默认提前 {self.config.quick_chat.offwork_lead_minutes} 分钟触发）

【SailTick 夜间专家简报（健康 + 节奏）】
{brief_text}

【今日实时可视化日程与活跃项目】
{rhythm_text}

【专家应急预案】
{playbook_text}

【命中的食物热量库】
{food_text}

【命中的专业健康师知识】
{kn_text}

回复与行动原则：
1. 适合快速阅读：温和、口语化、有同理心、不苛责（3-6 行，必要时短要点）。
2. **日程突发变动（加会/请假/早下班/太累了/卡壳/想重排）**：立刻调用 `rhythm_occupancy`（如有新会议/请假）和/或 `rhythm_sync_timeline` 直接重排今日剩余可视化时间线（系统会自动保留已完成和刚性钉块，你只需给出当前时刻之后的新排程块和一句 `rationale`），并附带 `plan_adjust_signal` 同步给慢脑！
3. **新增项目或任务**：用户口述新目标/项目/任务时，用 `rhythm_upsert_affair` 直接落库（长期目标用 `venture` + `target_date`，一次性任务用 `task_oneoff`），不必追问一堆权重参数。
4. **反馈完成/跳过**：用户说某件事做完了或不想做了，用 `rhythm_block_status` 或 `rhythm_transit_affair` 直接更新。
5. **设提醒**：用户要求设提醒时，必须输出 `create_reminder` action，算出精确本地 ISO 时间 `YYYY-MM-DDTHH:MM:00`。
6. **食物热量/体重/饮食**：命中食物库直接答；未命中先估算并输出 `enqueue_food_research`；报体重/饮食直接落库。

严格只输出 JSON：
{{
  "reply": "直接发给用户的回复文本",
  "actions": [
    {{"kind": "rhythm_occupancy", "date": "{today_str}", "occupancy_type": "meeting|leave|travel|appointment", "start": "14:00", "end": "16:00", "label": "临时评审会"}},
    {{"kind": "rhythm_sync_timeline", "date": "{today_str}", "rationale": "一句温和排程说明", "blocks": [{{"title": "核心推进", "start": "16:15", "end": "17:30", "block_type": "focus", "affair_id": null, "note": ""}}]}},
    {{"kind": "rhythm_upsert_affair", "title": "项目或任务名", "kind_name": "venture|task_oneoff|habit|fixed_plan", "domain": "work|career|life", "target_date": "2026-12-15", "urgency_ddl": "2026-12-15T00:00:00", "est_minutes": 60, "description": ""}},
    {{"kind": "rhythm_block_status", "block_id": 12, "status": "DONE|SKIPPED|DOING"}},
    {{"kind": "rhythm_transit_affair", "affair_id": 5, "action": "finish|defer|pause|resume|graduate", "defer_to": "2026-11-26T09:00:00"}},
    {{"kind": "create_reminder", "title": "买洗衣液", "body": "下班顺路买洗衣液", "trigger_time": "{today_str}T17:40:00", "priority": "normal"}},
    {{"kind": "plan_adjust_signal", "scene": "unexpected_meeting|early_offwork|social_dining|low_energy|other", "summary": "一句话记录今日变动"}},
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
        rhythm_dash: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = self._clock()
        today_str = now.strftime("%Y-%m-%d")
        offwork = self._resolve_offwork_time(profile_dict)
        actions: List[Dict[str, Any]] = []

        # 0a. 临时会议/请假占用识别
        if any(k in clean_text for k in ("加会", "开会", "评审会", "请假", "出差")):
            m_rng = re.search(r"(\d{1,2})[:：]?(\d{2})?\s*[-到至~]\s*(\d{1,2})[:：]?(\d{2})?", clean_text)
            occ_type = "leave" if "请假" in clean_text else ("travel" if "出差" in clean_text else "meeting")
            occ_act: Dict[str, Any] = {
                "kind": "rhythm_occupancy",
                "date": today_str,
                "occupancy_type": occ_type,
                "label": clean_text[:28],
            }
            if m_rng:
                sh, sm = int(m_rng.group(1)), int(m_rng.group(2) or 0)
                eh, em = int(m_rng.group(3)), int(m_rng.group(4) or 0)
                if ("下午" in clean_text or "晚上" in clean_text) and 1 <= sh <= 11:
                    sh += 12
                if ("下午" in clean_text or "晚上" in clean_text) and 1 <= eh <= 11:
                    eh += 12
                if eh <= sh:
                    eh = min(23, sh + 1)
                occ_act["start"] = f"{sh:02d}:{sm:02d}"
                occ_act["end"] = f"{eh:02d}:{em:02d}"
            elif occ_type == "leave":
                occ_act["whole_day"] = True
            else:
                st = (now + timedelta(minutes=15)).replace(second=0, microsecond=0)
                ed = st + timedelta(hours=1)
                occ_act["start"] = st.strftime("%H:%M")
                occ_act["end"] = ed.strftime("%H:%M")
            actions.append(occ_act)
            actions.append(
                {
                    "kind": "plan_adjust_signal",
                    "scene": "unexpected_meeting",
                    "summary": f"用户临时占用/变动：{clean_text[:120]}",
                }
            )
            return {
                "reply": (
                    f"收到！已把这段「{occ_act['label']}」钉进今天的时间线占位"
                    + (f"（{occ_act.get('start')}-{occ_act.get('end')}）" if occ_act.get("start") else "（全天）")
                    + "，并通知 SailTick 慢脑同步顺延非核心事项，别给自己太大压力。"
                ),
                "actions": actions,
            }

        # 0b. 一句话新建项目或待办
        m_new = re.search(r"(?:新建|添加|加一个|帮我记)(?:重要)?(项目|任务|待办)[：:\s]*(.+)", clean_text)
        if m_new:
            is_proj = m_new.group(1) == "项目"
            title = m_new.group(2).strip(" ，。！？")[:100]
            actions.append(
                {
                    "kind": "rhythm_upsert_affair",
                    "title": title,
                    "kind_name": "venture" if is_proj else "task_oneoff",
                    "domain": "career" if is_proj else "work",
                    "est_minutes": 60 if is_proj else 30,
                }
            )
            return {
                "reply": f"已帮你记进 Rhythm {'重要项目' if is_proj else '待办'}：「{title}」。后续我会结合你的真实精力与空档自动帮你排进日程。",
                "actions": actions,
            }

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

        if kind == "rhythm_sync_timeline":
            target_date = str(act.get("date") or self._clock().strftime("%Y-%m-%d"))
            blocks_in = [b for b in (act.get("blocks") or []) if isinstance(b, dict)]
            try:
                if await self.rhythm.health():
                    res = await self.rhythm.sync_ai_timeline(
                        target_date=target_date,
                        blocks=blocks_in,
                        rationale=str(act.get("rationale") or ""),
                        preserve_done=bool(act.get("preserve_done", True)),
                        preserve_pinned=bool(act.get("preserve_pinned", True)),
                        source=f"sailtick:quick_chat:{channel}",
                    )
                    return {
                        "kind": "rhythm_sync_timeline",
                        "ok": True,
                        "date": target_date,
                        "plan_version": res.get("plan_version"),
                        "created_count": res.get("created_count", 0),
                    }
            except Exception as exc:
                logger.warning("QuickCoachAgent rhythm_sync_timeline failed: %s", exc)
            return {"kind": "rhythm_sync_timeline", "ok": False}

        if kind == "rhythm_occupancy":
            target_date = str(act.get("date") or self._clock().strftime("%Y-%m-%d"))
            try:
                if await self.rhythm.health():
                    res = await self.rhythm.create_occupancy(
                        target_date=target_date,
                        occupancy_type=str(act.get("occupancy_type") or "meeting"),
                        start=act.get("start"),
                        end=act.get("end"),
                        whole_day=bool(act.get("whole_day", False)),
                        label=str(act.get("label") or raw_text[:30]),
                        note=str(act.get("note") or ""),
                    )
                    return {"kind": "rhythm_occupancy", "ok": True, "id": res.get("id"), "label": res.get("label")}
            except Exception as exc:
                logger.warning("QuickCoachAgent rhythm_occupancy failed: %s", exc)
            return {"kind": "rhythm_occupancy", "ok": False}

        if kind == "rhythm_upsert_affair":
            try:
                if await self.rhythm.health():
                    aid = act.get("id") or act.get("affair_id")
                    if aid is not None:
                        updates = {
                            k: act[k]
                            for k in ("title", "description", "domain", "urgency_ddl", "est_minutes", "importance", "kind_meta")
                            if k in act and act[k] is not None
                        }
                        res = await self.rhythm.update_affair(int(aid), updates)
                        return {"kind": "rhythm_upsert_affair", "ok": True, "affair_id": res.get("id")}
                    k_name = str(act.get("kind_name") or "task_oneoff")
                    k_meta = dict(act.get("kind_meta") or {})
                    if k_name == "venture" and act.get("target_date") and not k_meta.get("target_date"):
                        k_meta["target_date"] = str(act["target_date"])[:10]
                    res = await self.rhythm.create_affair(
                        title=str(act.get("title") or raw_text[:80]),
                        kind=k_name,
                        domain=act.get("domain"),
                        description=str(act.get("description") or ""),
                        urgency_ddl=act.get("urgency_ddl"),
                        est_minutes=int(act.get("est_minutes") or 30),
                        importance=int(act.get("importance") or 3),
                        kind_meta=k_meta,
                    )
                    return {"kind": "rhythm_upsert_affair", "ok": True, "affair_id": res.get("id"), "title": res.get("title")}
            except Exception as exc:
                logger.warning("QuickCoachAgent rhythm_upsert_affair failed: %s", exc)
            return {"kind": "rhythm_upsert_affair", "ok": False}

        if kind == "rhythm_block_status":
            try:
                bid = int(act["block_id"])
                if await self.rhythm.health():
                    res = await self.rhythm.set_block_status(bid, str(act.get("status") or "DONE"))
                    return {"kind": "rhythm_block_status", "ok": True, "block_id": bid, "status": res.get("status")}
            except Exception as exc:
                logger.warning("QuickCoachAgent rhythm_block_status failed: %s", exc)
            return {"kind": "rhythm_block_status", "ok": False}

        if kind == "rhythm_transit_affair":
            try:
                aid = int(act["affair_id"])
                if await self.rhythm.health():
                    res = await self.rhythm.transit_affair(
                        aid,
                        str(act.get("action") or "finish"),
                        defer_to=act.get("defer_to"),
                        defer_end=act.get("defer_end"),
                    )
                    return {"kind": "rhythm_transit_affair", "ok": True, "affair_id": aid, "state": res.get("state")}
            except Exception as exc:
                logger.warning("QuickCoachAgent rhythm_transit_affair failed: %s", exc)
            return {"kind": "rhythm_transit_affair", "ok": False}

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
