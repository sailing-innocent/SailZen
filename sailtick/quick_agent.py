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
from sailtick.context_budget import persona_for_domain
from sailtick.db import TickDatabase
from sailtick.finance_client import FinanceClient
from sailtick.inbox import TicketInbox
from sailtick.knowledge import HealthKnowledgeManager
from sailtick.memory import AgentMemory
from sailtick.nightly import NightlySelfMaintenance
from sailtick.rhythm_client import RhythmClient
from sailtick.tracer import TickTraceRecorder

logger = logging.getLogger(__name__)

_CN_DIGIT_MAP = str.maketrans("零一二三四五六七八九０１２３４５６７８９", "01234567890123456789")
_TITLE_NOISE_RE = re.compile(r"[\s，。！？、,.;:：()（）\[\]【】\"'“”‘’/\-—_~`]+")
_REMINDER_PREFIX_RE = re.compile(r"^(?:提醒我?|到点提醒|记得|别忘了|不要忘了|下班(?:前|后|路上|回去的?路上)?)+")


def normalize_semantic_title(title: str) -> str:
    """将提醒/事务标题做语义归一化（去空白标点、统一全角与中文数字），用于幂等防重。"""
    s = (title or "").strip().lower().translate(_CN_DIGIT_MAP)
    s = _TITLE_NOISE_RE.sub("", s)
    return s


def titles_match_semantically(a: str, b: str, *, strip_reminder_prefix: bool = False) -> bool:
    """判断两个提醒或事务标题是否指向同一件事。"""
    na = normalize_semantic_title(a)
    nb = normalize_semantic_title(b)
    if strip_reminder_prefix:
        na = _REMINDER_PREFIX_RE.sub("", na) or na
        nb = _REMINDER_PREFIX_RE.sub("", nb) or nb
    if not na or not nb:
        return False
    if na == nb:
        return True
    if min(len(na), len(nb)) >= 4 and (na in nb or nb in na):
        return True
    # 2-gram Jaccard 相似度（兼容轻微措辞变化，如「顺路购买」vs「顺路买」）
    if min(len(na), len(nb)) >= 4:
        ga = {na[i : i + 2] for i in range(len(na) - 1)}
        gb = {nb[i : i + 2] for i in range(len(nb) - 1)}
        inter = len(ga & gb)
        union = len(ga | gb)
        if union > 0 and (inter / union) >= 0.72:
            return True
    return False


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
        elif not period and "下班" in s and 4 <= hh <= 11:
            # 如「今天预计正常7点下班，下班路上提醒我...」→ 推断为 19:00
            hh += 12
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            dt = datetime(target_date.year, target_date.month, target_date.day, hh, mm)
            if "下班" in s and ("下班前" in s or "下班回去" in s or "下班路上" in s):
                dt -= timedelta(minutes=offwork_lead_minutes)
            if day_offset == 0 and dt <= now:
                dt += timedelta(days=1)
            return dt.replace(second=0, microsecond=0), dt.strftime("%m-%d %H:%M")

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
        finance: Optional[FinanceClient] = None,
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
        self.finance = finance or FinanceClient(
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

    @staticmethod
    def _resolve_domain(domain: str = "", surface: str = "", channel: str = "") -> str:
        d = (domain or "").strip().lower()
        if d in ("health", "rhythm", "finance", "general"):
            return d
        hint = f"{surface} {channel}".lower()
        if any(k in hint for k in ("rhythm", "plan", "vscode", "workbench")):
            return "rhythm"
        if any(k in hint for k in ("finance", "money", "bill")):
            return "finance"
        if any(k in hint for k in ("health", "coach", "diet", "weight")):
            return "health"
        return "general"

    @staticmethod
    def _detect_routed_domain(actions: List[Dict[str, Any]], primary_domain: str) -> Optional[str]:
        """若用户在某域入口触发了跨域动作，返回实际落库域供前端展示柔和徽章提示。"""
        for act in actions:
            if not isinstance(act, dict) or not act.get("ok"):
                continue
            k = str(act.get("kind") or "")
            target = None
            if k.startswith("finance_"):
                target = "finance"
            elif k.startswith("rhythm_") or k in ("create_reminder", "update_reminder", "cancel_reminder"):
                target = "rhythm"
            elif k in ("log_diet", "log_weight", "enqueue_food_research"):
                target = "health"
            if target and primary_domain != "general" and target != primary_domain:
                return target
        return None

    async def handle_message(
        self,
        text: str,
        channel: str = "api",
        user_id: str = "owner",
        session_id: Optional[str] = None,
        target_type: str = "private",
        target_id: Optional[str] = None,
        domain: str = "",
        surface: str = "",
        context_hints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """处理一条用户即时消息，按 domain/persona 裁剪上下文与工具，返回快速回复与动作摘要。"""
        t0 = time.perf_counter()
        resolved_domain = self._resolve_domain(domain=domain, surface=surface, channel=channel)
        persona = persona_for_domain(resolved_domain)
        clean_text = (text or "").strip()
        if not clean_text:
            return {
                "reply": "发一句想问的事或提醒就行，比如「今天能早下班怎么安排」或「下班前提醒我买洗衣液」。",
                "actions": [],
                "reminders_created": [],
                "domain": resolved_domain,
                "persona": persona,
                "source": "empty",
                "latency_ms": 0.0,
            }

        await self.knowledge.ensure_seeded()
        # 跨端同域连续会话：默认 session_key = "{user_id}:{domain}"
        sess_key = session_id or f"{user_id or 'owner'}:{resolved_domain}"
        reply_target_id = str(target_id or user_id or self.config.qq_bot.primary_user_id or "")

        # 1. 优先处理零延迟斜杠快捷指令（/brief /predict /food /remind /help）
        cmd_res = await self._try_command(clean_text)
        if cmd_res is not None:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return {
                **cmd_res,
                "domain": resolved_domain,
                "persona": persona,
                "session_id": sess_key,
                "latency_ms": latency_ms,
            }

        # 2. 按域懒加载上下文（优先读 st_domain_briefs + FTS5，避免每次全量拉三域 API）
        now = self._clock()
        tracer = TickTraceRecorder(
            slot="quick_chat",
            tick_date=now.strftime("%Y-%m-%d"),
            mode="live",
            trigger_source=f"quick_chat:{surface or channel}",
            tick_id=f"qc-{now.strftime('%Y%m%d%H%M%S')}",
            clock=self._clock,
        )
        tracer.meta = {
            "session_id": sess_key,
            "channel": channel,
            "surface": surface,
            "domain": resolved_domain,
            "persona": persona,
            "user_id": str(user_id or "owner"),
        }

        wants_rhythm = resolved_domain in ("rhythm", "general") or any(
            k in clean_text for k in ("日程", "时间线", "加会", "开会", "项目", "待办", "任务", "排期", "下班", "提醒")
        )
        wants_finance = resolved_domain in ("finance", "general") or any(
            k in clean_text for k in ("元", "块", "花了", "余额", "账单", "记账", "支付宝", "微信", "开销", "消费", "盒马", "打标")
        )
        wants_health = resolved_domain in ("health", "general") or any(
            k in clean_text for k in ("热量", "大卡", "体重", "吃", "午饭", "晚饭", "早饭", "聚餐", "运动", "睡", "零食", "奶茶", "咖啡")
        )

        with tracer.span("context", "load_quick_context", input_summary=f"[{resolved_domain}] {clean_text[:180]}") as ctx_sp:
            brief = await self.db.get_runtime_state("expert_brief")
            domain_briefs = (
                await self.db.list_domain_briefs()
                if hasattr(self.db, "list_domain_briefs")
                else {}
            )
            profile_dict = await self.memory.all_profile()
            fts_memories = (
                await self.memory.search(clean_text, domain=resolved_domain, entity_types=["memory"], limit=3)
                if hasattr(self.memory, "search")
                else []
            )
            matched_foods = (
                await self.knowledge.lookup_foods_in_text(clean_text, limit=4)
                if wants_health
                else []
            )
            matched_knowledge = (
                await self.knowledge.retrieve_knowledge(clean_text, limit=3)
                if wants_health
                else []
            )
            history = await self.db.list_quick_chat_history(
                sess_key, limit=max(2, self.config.quick_chat.history_turns)
            )
            rhythm_dash = await self._load_live_rhythm() if wants_rhythm else None
            finance_overview = await self._load_live_finance() if wants_finance else None
            pending_reminders = (
                await self._load_pending_reminders()
                if (wants_rhythm or "提醒" in clean_text)
                else []
            )
            ctx_sp.set_output(
                f"domain={resolved_domain} history={len(history)} fts={len(fts_memories)} "
                f"rhythm={'ok' if rhythm_dash else 'skip'} finance={'ok' if finance_overview else 'skip'} foods={len(matched_foods)}"
            )

        # 3. 决策回复与动作（优先快模型，无 LLM 时自动规则兜底）
        plan_source = "rule_fallback"
        reply_text = ""
        raw_actions: List[Dict[str, Any]] = []
        p_tokens_used = 0
        c_tokens_used = 0

        llm_ready = bool(
            self.llm is not None
            and getattr(self.llm, "config", None)
            and self.llm.config.providers
        )
        if llm_ready:
            with tracer.span("llm", "fast_llm_chat", input_summary=f"[{resolved_domain}] {clean_text[:280]}") as llm_sp:
                try:
                    llm_out, llm_meta = await self._ask_fast_llm(
                        clean_text=clean_text,
                        brief=brief,
                        domain_briefs=domain_briefs,
                        fts_memories=fts_memories,
                        profile_dict=profile_dict,
                        matched_foods=matched_foods,
                        matched_knowledge=matched_knowledge,
                        rhythm_dash=rhythm_dash,
                        finance_overview=finance_overview,
                        pending_reminders=pending_reminders,
                        history=history,
                        domain=resolved_domain,
                        surface=surface,
                        context_hints=context_hints,
                    )
                    if llm_meta:
                        p_tokens_used = int(llm_meta.get("prompt_tokens", 0) or 0)
                        c_tokens_used = int(llm_meta.get("completion_tokens", 0) or 0)
                        t_tokens_used = int(llm_meta.get("total_tokens", 0) or (p_tokens_used + c_tokens_used))
                        tracer.add_llm_usage(
                            prompt_tokens=p_tokens_used,
                            completion_tokens=c_tokens_used,
                            total_tokens=t_tokens_used,
                            cost_usd=llm_meta.get("cost_usd", 0.0),
                        )
                        llm_sp.set_payload(llm_meta)
                    if llm_out and llm_out.get("reply"):
                        reply_text = str(llm_out["reply"]).strip()
                        raw_actions = list(llm_out.get("actions") or [])
                        plan_source = "fast_llm"
                        llm_sp.set_output(f"tokens={p_tokens_used}+{c_tokens_used} reply_len={len(reply_text)} raw_actions={len(raw_actions)}")
                    else:
                        llm_sp.mark_status("skipped", "empty or unparseable JSON reply")
                except Exception as exc:
                    logger.warning("QuickCoachAgent fast LLM failed, using rule fallback: %s", exc)
                    llm_sp.mark_status("error", f"{type(exc).__name__}: {exc}")

        if not reply_text:
            with tracer.span("plan", "rule_fallback", input_summary=clean_text[:200]) as fb_sp:
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
                fb_sp.set_output(f"actions={len(raw_actions)}")

        tracer.plan_source = plan_source

        # 4. 执行轻量工具动作（带强幂等防重闸门 + 逐动作 Trace 记录）
        executed_actions: List[Dict[str, Any]] = []
        reminders_created: List[Dict[str, Any]] = []
        rhythm_updated = False
        finance_updated = False
        for act in raw_actions:
            if not isinstance(act, dict):
                continue
            act_kind = str(act.get("kind") or "unknown").strip()
            with tracer.span("work", f"action:{act_kind}", input_summary=json.dumps(act, ensure_ascii=False)[:400]) as act_sp:
                res = await self._execute_action(
                    act=act,
                    raw_text=clean_text,
                    channel=channel,
                    target_type=target_type,
                    target_id=reply_target_id,
                    profile_dict=profile_dict,
                    rhythm_dash=rhythm_dash,
                    pending_reminders=pending_reminders,
                )
                if res:
                    executed_actions.append(res)
                    act_sp.set_payload({"request": act, "result": res})
                    if res.get("ok"):
                        tracer.actions_executed += 1
                        if res.get("deduplicated"):
                            act_sp.set_output(f"deduplicated ({res.get('action_taken', 'reused')})")
                        elif res.get("rescheduled"):
                            act_sp.set_output(f"rescheduled -> {res.get('trigger_time')}")
                        else:
                            act_sp.set_output("ok")
                    else:
                        tracer.actions_failed += 1
                        act_sp.mark_status("error", str(res.get("error") or "action failed"))
                    if res.get("kind") in ("create_reminder", "update_reminder") and res.get("ok"):
                        if not res.get("deduplicated"):
                            reminders_created.append(res)
                    if str(res.get("kind", "")).startswith("rhythm_") and res.get("ok") and not res.get("deduplicated"):
                        rhythm_updated = True
                    if str(res.get("kind", "")).startswith("finance_") and res.get("ok") and not res.get("deduplicated"):
                        finance_updated = True
                else:
                    act_sp.mark_status("skipped", "unsupported or disabled action")

        routed_domain = self._detect_routed_domain(executed_actions, resolved_domain)

        # 5. 保存原始对话历史（带 domain/surface/tokens，供跨端续聊与夜间提炼）+ 持久化 AI Trace
        await self.db.append_quick_chat(
            sess_key,
            "user",
            clean_text,
            channel=channel,
            user_id=str(user_id or ""),
            domain=resolved_domain,
            surface=surface,
        )
        await self.db.append_quick_chat(
            sess_key,
            "assistant",
            reply_text,
            channel=channel,
            user_id=str(user_id or ""),
            actions=executed_actions,
            domain=resolved_domain,
            surface=surface,
            prompt_tokens=p_tokens_used,
            completion_tokens=c_tokens_used,
        )

        trace_dict = tracer.finish(
            status="completed",
            summary=f"[{resolved_domain}/{surface or channel}] {clean_text[:72]} -> {len(executed_actions)} actions ({plan_source})",
        )
        await self._persist_trace(trace_dict)

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "reply": reply_text,
            "actions": executed_actions,
            "reminders_created": reminders_created,
            "rhythm_updated": rhythm_updated,
            "finance_updated": finance_updated,
            "domain": resolved_domain,
            "persona": persona,
            "routed_domain": routed_domain,
            "expert_brief_date": (brief or {}).get("snapshot_date") if isinstance(brief, dict) else None,
            "foods_matched": [f["name"] for f in matched_foods],
            "source": plan_source,
            "session_id": sess_key,
            "trace_id": tracer.trace_id,
            "latency_ms": latency_ms,
        }

    async def _persist_trace(self, trace_dict: Dict[str, Any]) -> None:
        try:
            if hasattr(self.db, "save_trace") and getattr(self.db, "_engine", None) is not None:
                await self.db.save_trace(trace_dict)
        except Exception as exc:
            logger.debug("QuickCoachAgent save_trace skipped: %s", exc)
        try:
            if hasattr(self.inbox, "report_ai_trace") and await self.inbox.health():
                await self.inbox.report_ai_trace(trace_dict)
        except Exception as exc:
            logger.debug("QuickCoachAgent report_ai_trace skipped: %s", exc)

    async def _load_live_rhythm(self) -> Optional[Dict[str, Any]]:
        try:
            if await self.rhythm.health():
                return await self.rhythm.get_dashboard(self._clock().date())
        except Exception as exc:
            logger.debug("QuickCoachAgent load live rhythm skipped: %s", exc)
        return None

    async def _load_live_finance(self) -> Optional[Dict[str, Any]]:
        try:
            if await self.finance.health():
                return await self.finance.get_overview()
        except Exception as exc:
            logger.debug("QuickCoachAgent load live finance skipped: %s", exc)
        return None

    async def _load_pending_reminders(self) -> List[Dict[str, Any]]:
        """汇总本地 pending nudges 与云端 pending reminders，供 Prompt 感知与幂等去重。"""
        merged: List[Dict[str, Any]] = []
        seen_server_ids: set[int] = set()
        try:
            nudges = await self.db.list_pending_nudges(limit=30)
            for n in nudges:
                sid = n.get("server_reminder_id")
                if sid is not None:
                    seen_server_ids.add(int(sid))
                merged.append(
                    {
                        "nudge_id": n.get("id"),
                        "server_reminder_id": sid,
                        "title": str(n.get("title") or ""),
                        "body": str(n.get("body") or ""),
                        "trigger_at": str(n.get("trigger_at") or ""),
                    }
                )
        except Exception as exc:
            logger.debug("QuickCoachAgent list_pending_nudges skipped: %s", exc)

        try:
            if hasattr(self.inbox, "list_pending_reminders") and await self.inbox.health():
                for r in await self.inbox.list_pending_reminders():
                    rid = r.get("id")
                    if rid is not None and int(rid) in seen_server_ids:
                        continue
                    merged.append(
                        {
                            "nudge_id": None,
                            "server_reminder_id": rid,
                            "title": str(r.get("title") or ""),
                            "body": str(r.get("body") or ""),
                            "trigger_at": str(r.get("trigger_time") or ""),
                        }
                    )
        except Exception as exc:
            logger.debug("QuickCoachAgent list_pending_reminders skipped: %s", exc)
        return merged

    @staticmethod
    def _format_pending_reminders_for_prompt(pending_reminders: List[Dict[str, Any]]) -> str:
        if not pending_reminders:
            return "(当前无待触发提醒)"
        lines: List[str] = []
        for item in pending_reminders[:15]:
            rid = item.get("server_reminder_id")
            nid = item.get("nudge_id")
            tag = f"reminder#{rid}" if rid is not None else f"nudge#{str(nid or '')[:8]}"
            trig = str(item.get("trigger_at") or "")[:16].replace("T", " ")
            lines.append(f"- {tag} [{trig}] {item.get('title') or ''}")
        return "\n".join(lines)

    @staticmethod
    def _format_history_for_llm(history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """将短期对话历史格式化为 LLM 消息，并在 assistant 轮次附带已执行动作回执以杜绝复读重放。"""
        out: List[Dict[str, str]] = []
        for h in history[-6:]:
            role = str(h.get("role") or "user")
            content = str(h.get("content") or "")
            if role == "assistant":
                acts = h.get("actions") or []
                receipts: List[str] = []
                for a in acts:
                    if not isinstance(a, dict) or not a.get("ok"):
                        continue
                    k = a.get("kind")
                    if k in ("create_reminder", "update_reminder"):
                        rid = a.get("server_reminder_id") or str(a.get("nudge_id") or "")[:8]
                        receipts.append(f"{k}#{rid}@{str(a.get('trigger_time') or '')[11:16]}({a.get('title') or ''})")
                    elif k == "cancel_reminder":
                        receipts.append(f"cancel_reminder({a.get('title') or a.get('server_reminder_id')})")
                    elif k == "rhythm_upsert_affair":
                        receipts.append(f"affair#{a.get('affair_id')}({a.get('title') or ''})")
                    elif k == "update_profile":
                        receipts.append(f"profile.{a.get('key')}={a.get('value')}")
                    elif k:
                        receipts.append(str(k))
                if receipts:
                    content = f"{content}\n[系统回执-该轮已执行，勿重复创建: {'; '.join(receipts)}]"
            out.append({"role": role, "content": content})
        return out

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
                    "• 日常记账与对账：「午饭外卖 32 微信」「支付宝余额对齐到 2950」「帮我扫描清理未打标账单」\n"
                    "• 快捷命令：/today 日程 · /projects 项目 · /money 账单概览 · /accounts 账户余额 · /brief 专家简报 · /predict 预测 · /food 热量 · /remind 提醒"
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

        if low in ("/money", "/账单", "/财务", "本月开销", "花钱情况"):
            ov = await self._load_live_finance()
            if not ov:
                return {
                    "reply": "暂时连不上 Finance 财务服务，稍后再试。",
                    "actions": [],
                    "reminders_created": [],
                    "source": "command",
                }
            lines = [
                f"【财务开销秘书 · {ov.get('month', '')}】",
                f"• 今日支出：¥{ov.get('today_expense', '0.00')}（{ov.get('today_count', 0)} 笔）",
                f"• 本月真实支出：¥{ov.get('mtd_expense', '0.00')} | 收入：¥{ov.get('mtd_income', '0.00')} | 净结余：¥{ov.get('mtd_net', '0.00')}",
                f"• 真实零食开销：¥{ov.get('mtd_snack_total', '0.00')}（占本月 {ov.get('mtd_snack_pct', 0)}%，含混合小票拆分 ¥{ov.get('mtd_snack_from_split', '0.00')}）",
                f"• 标签覆盖率：{ov.get('overall_tag_coverage_pct', 100)}% | 待审清理：{ov.get('pending_hygiene_count', 0)} 条 | AI 自动托管：{ov.get('auto_applied_hygiene_count', 0)} 条",
            ]
            top_tags = ov.get("mtd_by_tag") or []
            if top_tags:
                t_str = " · ".join(f"{t.get('tag')} ¥{t.get('amount')}" for t in top_tags[:4])
                lines.append(f"• 本月主要去向：{t_str}")
            silent = ov.get("silent_accounts") or []
            if silent:
                s_str = "、".join(f"{a.get('name')}({a.get('days_silent')}天未记)" for a in silent[:3])
                lines.append(f"• 提醒：{s_str}")
            bf = await self.db.get_runtime_state("finance_backfill_progress")
            if isinstance(bf, dict) and bf.get("status"):
                done_m = len(bf.get("completed_months") or [])
                tot_m = bf.get("total_months_detected") or done_m
                lines.append(
                    f"• 历史慢迭代：{bf.get('status')}（已理 {done_m}/{tot_m} 月，累计静默补标 {bf.get('cumulative_auto_tagged', 0)} 笔"
                    + (f"，下晚推进 {bf['cursor_month']}" if bf.get("cursor_month") else "")
                    + "）"
                )
            return {
                "reply": "\n".join(lines),
                "actions": [],
                "reminders_created": [],
                "source": "command",
            }

        if low in ("/accounts", "/余额", "/账户", "账户余额"):
            ov = await self._load_live_finance()
            accs = (ov or {}).get("account_health") or []
            if not accs:
                return {
                    "reply": "暂未读取到活跃账户余额信息。",
                    "actions": [],
                    "reminders_created": [],
                    "source": "command",
                }
            lines = ["【活跃账户余额与核对状态】"]
            for a in accs[:10]:
                rec = str(a.get("last_reconciled_at") or "")[:10] or "未核对"
                days_s = a.get("days_since_last_tx")
                act_part = f"{days_s}天前有流水" if days_s is not None else "暂无流水"
                lines.append(f"• {a.get('name')}：¥{a.get('balance')}（{act_part} · 上次核对 {rec}）")
            lines.append("直接说「把微信余额对齐到 xxx」即可无感平账核对。")
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

    @staticmethod
    def _format_live_finance_for_prompt(ov: Optional[Dict[str, Any]]) -> str:
        if not isinstance(ov, dict) or not ov:
            return "(暂未获取到实时财务总览)"
        lines = [
            f"月份: {ov.get('month')} | 今日支出: ¥{ov.get('today_expense')}({ov.get('today_count', 0)}笔) | 本月真实支出: ¥{ov.get('mtd_expense')} | 收入: ¥{ov.get('mtd_income')}",
            f"真实零食支出: ¥{ov.get('mtd_snack_total')} ({ov.get('mtd_snack_pct')}%, 含小票拆分¥{ov.get('mtd_snack_from_split')}) | 标签覆盖率: {ov.get('overall_tag_coverage_pct')}% | 待审清理: {ov.get('pending_hygiene_count')}条",
        ]
        accs = ov.get("account_health") or []
        if accs:
            acc_str = "；".join(f"#{a.get('id')}{a.get('name')}=¥{a.get('balance')}" for a in accs[:8])
            lines.append(f"活跃账户: {acc_str}")
        return "\n".join(lines)

    async def _ask_fast_llm(
        self,
        clean_text: str,
        brief: Optional[Dict[str, Any]],
        profile_dict: Dict[str, Any],
        matched_foods: List[Dict[str, Any]],
        matched_knowledge: List[Dict[str, Any]],
        rhythm_dash: Optional[Dict[str, Any]],
        finance_overview: Optional[Dict[str, Any]],
        pending_reminders: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
        *,
        domain: str = "general",
        surface: str = "",
        domain_briefs: Optional[Dict[str, dict]] = None,
        fts_memories: Optional[List[dict]] = None,
        context_hints: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        now = self._clock()
        today_str = now.strftime("%Y-%m-%d")
        offwork = self._resolve_offwork_time(profile_dict)

        # 按 domain 拼接极简分域热简报（大幅压降快脑输入 token）
        target_brief_domains = [domain] if domain in ("health", "rhythm", "finance") else ["health", "rhythm", "finance"]
        brief_text = NightlySelfMaintenance.format_domain_briefs_for_prompt(
            domain_briefs or {}, target_brief_domains
        )
        if not brief_text:
            brief_text = NightlySelfMaintenance.format_brief_for_prompt(brief)[:900]

        fts_text = "\n".join(
            f"- [{m.get('domain', 'general')}] {m.get('title', '')}: {m.get('summary', '')}"
            for m in (fts_memories or [])[:3]
        )

        persona_intro = {
            "health": "你是 SailTick 的「健康教练」（常驻健康页快脑）。专注体重趋势、饮食热量、聚餐控损、运动与睡眠恢复，温和不苛责。",
            "rhythm": "你是 SailTick 的「节奏规划师」（常驻规划页与 VSCode 工作台快脑）。专注今日/明日可视化时间线重排、临时会议占位、项目倒排与待办提醒，不主动谈无关饮食热量。",
            "finance": "你是 SailTick 的「财务秘书」（常驻记账页快脑）。专注一句话记账、混合小票拆分、账户余额无感核对、账单体检与零食预算洞察。",
        }.get(
            domain,
            "你是 SailTick Personal Agent 的「生活总管快脑」，统筹健康、节奏日程与日常开销，温和口语化且直接可执行。",
        )

        context_sections: List[str] = [
            f"{persona_intro}",
            f"当前时间：{now.strftime('%Y-%m-%d %H:%M')}（星期{'一二三四五六日'[now.weekday()]}） | 入口：{surface or domain} | 常规下班：{offwork}（若用户原话给出具体时刻须以原话为准）",
            f"【专家热简报】\n{brief_text}",
        ]
        if fts_text:
            context_sections.append(f"【命中长期记忆】\n{fts_text}")
        if context_hints:
            context_sections.append(f"【当前页面上下文】\n{json.dumps(context_hints, ensure_ascii=False)[:300]}")
        if pending_reminders:
            context_sections.append(
                f"【当前已生效的待触发提醒（严禁重复创建）】\n{self._format_pending_reminders_for_prompt(pending_reminders)}"
            )
        if rhythm_dash is not None:
            context_sections.append(f"【今日实时日程与活跃项目】\n{self._format_live_rhythm_for_prompt(rhythm_dash)}")
        if finance_overview is not None:
            context_sections.append(f"【实时财务开销与活跃账户】\n{self._format_live_finance_for_prompt(finance_overview)}")
        if matched_foods:
            food_text = "\n".join(
                f"- {f['name']}({f.get('serving_desc')}): 约{f.get('kcal_per_serving')}kcal "
                f"(P:{f.get('protein_g')}g C:{f.get('carbs_g')}g F:{f.get('fat_g')}g) | {f.get('lighter_swap')}"
                for f in matched_foods
            )
            context_sections.append(f"【命中食物热量库】\n{food_text}")
        if matched_knowledge:
            kn_text = "\n".join(
                f"- [{k.get('domain')}] {k.get('title')}: {k.get('summary')}"
                for k in matched_knowledge[:2]
            )
            context_sections.append(f"【命中专业知识】\n{kn_text}")

        # 按 domain 裁剪 Action Schema 子集（同时允许跨域动作，避免死板拒答）
        action_templates: Dict[str, str] = {
            "create_reminder": f'{{"kind": "create_reminder", "title": "买洗衣液", "body": "下班顺路买", "trigger_time": "{today_str}T18:40:00", "priority": "normal"}}',
            "update_reminder": f'{{"kind": "update_reminder", "server_reminder_id": 418, "match_title": "原提醒", "title": "新标题", "trigger_time": "{today_str}T18:40:00"}}',
            "cancel_reminder": '{"kind": "cancel_reminder", "server_reminder_id": 418, "match_title": "原提醒"}',
            "update_profile": '{"kind": "update_profile", "key": "offwork_time", "value": "19:00"}',
            "rhythm_occupancy": f'{{"kind": "rhythm_occupancy", "date": "{today_str}", "occupancy_type": "meeting|leave|travel|appointment", "start": "14:00", "end": "16:00", "label": "临时评审会"}}',
            "rhythm_sync_timeline": f'{{"kind": "rhythm_sync_timeline", "date": "{today_str}", "rationale": "排程说明", "blocks": [{{"title": "核心推进", "start": "16:15", "end": "17:30", "block_type": "focus|light|career|meal|habit|rest|micro_rest|sleep|commute|work_window|fixed|buffer|occupied", "affair_id": null, "note": ""}}]}}',
            "rhythm_upsert_affair": '{"kind": "rhythm_upsert_affair", "title": "项目或任务名", "kind_name": "venture|task_oneoff|habit|fixed_plan", "domain": "work|career|life", "target_date": "2026-12-15", "est_minutes": 60}',
            "rhythm_block_status": '{"kind": "rhythm_block_status", "block_id": 12, "status": "DONE|SKIPPED|DOING"}',
            "rhythm_transit_affair": '{"kind": "rhythm_transit_affair", "affair_id": 5, "action": "finish|defer|pause|resume|graduate"}',
            "finance_log_tx": '{"kind": "finance_log_tx", "amount": 128.0, "description": "盒马采购", "direction": "expense|income", "tags": "日用消耗,零食", "account_hint": "支付宝", "items": []}',
            "finance_reconcile_account": '{"kind": "finance_reconcile_account", "account_hint": "支付宝余额宝", "actual_balance": 2950.3, "force_adjust": false}',
            "finance_run_hygiene": '{"kind": "finance_run_hygiene", "days": 30, "auto_apply_safe": true}',
            "finance_batch_tag": '{"kind": "finance_batch_tag", "updates": [{"id": 123, "tags": "交通"}]}',
            "plan_adjust_signal": '{"kind": "plan_adjust_signal", "scene": "unexpected_meeting|early_offwork|social_dining|low_energy|other", "summary": "一句话变动"}',
            "log_diet": '{"kind": "log_diet", "meal_type": "breakfast|lunch|dinner|snack", "description": "饮食内容", "calories": 500}',
            "log_weight": '{"kind": "log_weight", "weight_kg": 73.6}',
            "enqueue_food_research": '{"kind": "enqueue_food_research", "foods": ["未知食物名"]}',
        }
        domain_action_keys = {
            "health": ["log_diet", "log_weight", "enqueue_food_research", "plan_adjust_signal", "update_profile", "create_reminder"],
            "rhythm": ["rhythm_occupancy", "rhythm_sync_timeline", "rhythm_upsert_affair", "rhythm_block_status", "rhythm_transit_affair", "create_reminder", "update_reminder", "cancel_reminder", "update_profile", "plan_adjust_signal"],
            "finance": ["finance_log_tx", "finance_reconcile_account", "finance_run_hygiene", "finance_batch_tag", "create_reminder", "update_profile"],
        }.get(domain, list(action_templates.keys()))
        # 若跨领域关键词触发了额外实时数据，动态补齐对应工具模板
        if finance_overview is not None and "finance_log_tx" not in domain_action_keys:
            domain_action_keys = [*domain_action_keys, "finance_log_tx", "finance_reconcile_account"]
        if rhythm_dash is not None and "rhythm_sync_timeline" not in domain_action_keys:
            domain_action_keys = [*domain_action_keys, "rhythm_occupancy", "rhythm_sync_timeline"]

        actions_block = ",\n    ".join(action_templates[k] for k in domain_action_keys if k in action_templates)
        rules_block = f"""回复与行动原则：
1. 温和、口语化、简洁易读（3-6 行）；严禁复读重放历史 `[系统回执-该轮已执行]` 动作，只针对本轮最新新增/修改/取消意图输出 `actions`；纯讨论/确认时输出 `"actions": []`。
2. 改已有提醒用 `update_reminder`，取消用 `cancel_reminder`，改作息用 `update_profile`。
3. 严格只输出 JSON：
{{
  "reply": "直接发给用户的回复文本",
  "actions": [
    {actions_block}
  ]
}}"""
        system_prompt = "\n\n".join([*context_sections, rules_block])

        hist_msgs = self._format_history_for_llm(history)
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
        raw_content = getattr(resp, "content", "") or ""
        parsed = HealthKnowledgeManager._parse_json_safe(raw_content)
        usage = getattr(resp, "usage", None) or {}
        p_tok = int(usage.get("prompt_tokens", 0) or getattr(resp, "prompt_tokens", 0) or 0)
        c_tok = int(usage.get("completion_tokens", 0) or getattr(resp, "completion_tokens", 0) or 0)
        t_tok = int(usage.get("total_tokens", 0) or getattr(resp, "total_tokens", 0) or (p_tok + c_tok))
        llm_meta: Dict[str, Any] = {
            "provider": getattr(resp, "provider", ""),
            "model": getattr(resp, "model", ""),
            "domain": domain,
            "prompt_chars": len(system_prompt),
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
            "total_tokens": t_tok,
            "cost_usd": float(getattr(resp, "cost_usd", 0.0) or 0.0),
            "history_turns": len(hist_msgs),
            "raw_response": raw_content[:4000],
        }
        return parsed, llm_meta

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

    @staticmethod
    def _find_matching_pending_reminder(
        pending_reminders: List[Dict[str, Any]],
        *,
        server_reminder_id: Optional[int] = None,
        nudge_id: Optional[str] = None,
        title: str = "",
        target_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """在活跃待触发提醒中按 ID 或语义标题匹配已有条目。"""
        if server_reminder_id is not None:
            for item in pending_reminders:
                if item.get("server_reminder_id") is not None and int(item["server_reminder_id"]) == int(server_reminder_id):
                    return item
        if nudge_id:
            for item in pending_reminders:
                if item.get("nudge_id") and str(item["nudge_id"]) == str(nudge_id):
                    return item
        if title:
            for item in pending_reminders:
                if target_date and str(item.get("trigger_at") or "")[:10] != target_date:
                    continue
                if titles_match_semantically(title, str(item.get("title") or ""), strip_reminder_prefix=True):
                    return item
        return None

    async def _reschedule_or_create_reminder(
        self,
        *,
        existing: Optional[Dict[str, Any]],
        title: str,
        body: str,
        priority: str,
        trig_dt: datetime,
        channel: str,
        target_type: str,
        target_id: str,
        pending_reminders: List[Dict[str, Any]],
        action_kind: str = "create_reminder",
    ) -> Dict[str, Any]:
        """创建或原地改期提醒（同日同主题自动幂等复用或替换，绝不产生多条重复提醒）。"""
        if existing is not None:
            old_iso = str(existing.get("trigger_at") or "")
            old_dt: Optional[datetime] = None
            try:
                old_dt = datetime.fromisoformat(old_iso.replace("Z", "+00:00"))
                if old_dt.tzinfo is not None:
                    old_dt = old_dt.astimezone().replace(tzinfo=None)
            except ValueError:
                old_dt = None

            # 1. 同主题且触发时间相差 <= 5 分钟：强幂等跳过（杜绝多轮复读重放）
            if old_dt is not None and abs((old_dt - trig_dt).total_seconds()) <= 300:
                return {
                    "kind": action_kind,
                    "ok": True,
                    "deduplicated": True,
                    "action_taken": "reused_existing",
                    "title": existing.get("title") or title,
                    "trigger_time": old_iso or trig_dt.isoformat(),
                    "server_reminder_id": existing.get("server_reminder_id"),
                    "server_synced": existing.get("server_reminder_id") is not None,
                    "nudge_id": existing.get("nudge_id"),
                }

            # 2. 同主题但时间改变：撤销旧云端提醒 → 新建新时间提醒 → 原地更新本地 Nudge
            old_sid = existing.get("server_reminder_id")
            server_ok = False
            new_sid: Optional[int] = None
            try:
                if await self.inbox.health():
                    if old_sid is not None and hasattr(self.inbox, "cancel_reminder"):
                        await self.inbox.cancel_reminder(int(old_sid))
                    rem = await self.inbox.create_reminder(
                        title=title,
                        trigger_time=trig_dt,
                        body=body,
                        priority=priority,
                        rem_type="agent.quick_reminder",
                        payload={"channel": channel, "from_quick_chat": True, "replaced_reminder_id": old_sid},
                    )
                    new_sid = rem.get("id")
                    server_ok = True
            except Exception as exc:
                logger.warning("QuickCoachAgent reschedule reminder on sail_server failed: %s", exc)

            old_nid = existing.get("nudge_id")
            if old_nid and hasattr(self.db, "update_scheduled_nudge"):
                nudge = await self.db.update_scheduled_nudge(
                    str(old_nid),
                    title=title,
                    body=body,
                    trigger_at=trig_dt.isoformat(),
                    server_reminder_id=new_sid if new_sid is not None else old_sid,
                )
                nudge_id = nudge["id"] if nudge else old_nid
            else:
                nudge_channel = "qq" if (channel == "qq" or self.config.qq_bot.enabled) else channel
                nudge = await self.db.create_scheduled_nudge(
                    title=title,
                    body=body,
                    trigger_at=trig_dt.isoformat(),
                    channel=nudge_channel,
                    target_id=target_id,
                    target_type=target_type,
                    server_reminder_id=new_sid,
                )
                nudge_id = nudge["id"]

            # 刷新内存视图，避免同一轮多条动作继续撞车
            existing["title"] = title
            existing["body"] = body
            existing["trigger_at"] = trig_dt.isoformat()
            existing["server_reminder_id"] = new_sid if new_sid is not None else old_sid
            existing["nudge_id"] = nudge_id

            return {
                "kind": action_kind,
                "ok": True,
                "rescheduled": True,
                "replaced_reminder_id": old_sid,
                "title": title,
                "trigger_time": trig_dt.isoformat(),
                "server_reminder_id": new_sid,
                "server_synced": server_ok,
                "nudge_id": nudge_id,
            }

        # 3. 全新提醒：正常双写并更新内存待触发列表
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
        pending_reminders.append(
            {
                "nudge_id": nudge["id"],
                "server_reminder_id": server_rem_id,
                "title": title,
                "body": body,
                "trigger_at": trig_dt.isoformat(),
            }
        )
        return {
            "kind": action_kind,
            "ok": True,
            "title": title,
            "trigger_time": trig_dt.isoformat(),
            "server_reminder_id": server_rem_id,
            "server_synced": server_ok,
            "nudge_id": nudge["id"],
        }

    async def _execute_action(
        self,
        act: Dict[str, Any],
        raw_text: str,
        channel: str,
        target_type: str,
        target_id: str,
        profile_dict: Dict[str, Any],
        rhythm_dash: Optional[Dict[str, Any]] = None,
        pending_reminders: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        kind = str(act.get("kind") or "").strip()
        if not kind:
            return None
        pending_list = pending_reminders if pending_reminders is not None else []

        if kind == "create_reminder" and self.config.quick_chat.allow_reminder_create:
            title = str(act.get("title") or extract_reminder_subject(raw_text)).strip()
            body = str(act.get("body") or f"提醒：{title}").strip()
            priority = str(act.get("priority") or "normal")
            trig_dt = self._parse_iso_or_fallback(
                act.get("trigger_time"), raw_text, profile_dict
            )
            existing = self._find_matching_pending_reminder(
                pending_list,
                title=title,
                target_date=trig_dt.strftime("%Y-%m-%d"),
            )
            return await self._reschedule_or_create_reminder(
                existing=existing,
                title=title,
                body=body,
                priority=priority,
                trig_dt=trig_dt,
                channel=channel,
                target_type=target_type,
                target_id=target_id,
                pending_reminders=pending_list,
                action_kind="create_reminder",
            )

        if kind == "update_reminder" and self.config.quick_chat.allow_reminder_create:
            sid_raw = act.get("server_reminder_id") or act.get("reminder_id")
            sid = int(sid_raw) if sid_raw is not None and str(sid_raw).isdigit() else None
            nid = str(act.get("nudge_id") or "").strip() or None
            match_title = str(act.get("match_title") or act.get("title") or "").strip()
            existing = self._find_matching_pending_reminder(
                pending_list,
                server_reminder_id=sid,
                nudge_id=nid,
                title=match_title,
            )
            title = str(act.get("title") or (existing or {}).get("title") or match_title or extract_reminder_subject(raw_text)).strip()
            body = str(act.get("body") or (existing or {}).get("body") or f"提醒：{title}").strip()
            priority = str(act.get("priority") or "normal")
            trig_dt = self._parse_iso_or_fallback(
                act.get("trigger_time"), raw_text, profile_dict
            )
            return await self._reschedule_or_create_reminder(
                existing=existing,
                title=title,
                body=body,
                priority=priority,
                trig_dt=trig_dt,
                channel=channel,
                target_type=target_type,
                target_id=target_id,
                pending_reminders=pending_list,
                action_kind="update_reminder",
            )

        if kind == "cancel_reminder" and self.config.quick_chat.allow_reminder_create:
            sid_raw = act.get("server_reminder_id") or act.get("reminder_id")
            sid = int(sid_raw) if sid_raw is not None and str(sid_raw).isdigit() else None
            nid = str(act.get("nudge_id") or "").strip() or None
            match_title = str(act.get("match_title") or act.get("title") or "").strip()
            existing = self._find_matching_pending_reminder(
                pending_list,
                server_reminder_id=sid,
                nudge_id=nid,
                title=match_title,
            )
            target_sid = sid if sid is not None else (existing or {}).get("server_reminder_id")
            target_nid = nid or (existing or {}).get("nudge_id")
            if target_sid is None and not target_nid:
                return {"kind": "cancel_reminder", "ok": False, "error": "no matching pending reminder"}
            server_canceled = False
            if target_sid is not None and hasattr(self.inbox, "cancel_reminder"):
                try:
                    if await self.inbox.health():
                        server_canceled = await self.inbox.cancel_reminder(int(target_sid))
                except Exception as exc:
                    logger.warning("QuickCoachAgent cancel_reminder failed: %s", exc)
            local_canceled = False
            if target_nid:
                local_canceled = await self.db.mark_nudge_status(str(target_nid), "canceled")
            elif target_sid is not None and hasattr(self.db, "cancel_nudges_by_server_reminder_id"):
                local_canceled = (await self.db.cancel_nudges_by_server_reminder_id(int(target_sid))) > 0
            if existing is not None and existing in pending_list:
                pending_list.remove(existing)
            return {
                "kind": "cancel_reminder",
                "ok": bool(server_canceled or local_canceled),
                "server_reminder_id": target_sid,
                "nudge_id": target_nid,
                "title": (existing or {}).get("title") or match_title,
            }

        if kind == "update_profile":
            key = str(act.get("key") or "").strip()[:64]
            val = act.get("value")
            if not key or val is None or (isinstance(val, str) and not val.strip()):
                return {"kind": "update_profile", "ok": False, "error": "empty key or value"}
            await self.memory.set_profile(
                key,
                val,
                confidence=0.95,
                source=f"quick_chat:{channel}",
            )
            profile_dict[key] = {"value": val, "confidence": 0.95, "source": f"quick_chat:{channel}"}
            return {"kind": "update_profile", "ok": True, "key": key, "value": val}

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
                    title_in = str(act.get("title") or raw_text[:80]).strip()
                    k_name = str(act.get("kind_name") or "task_oneoff")

                    # 未传 id 时，按语义标题在现有活跃事务/项目中判重，真正实现 Upsert 而非盲目 Insert
                    if aid is None and title_in:
                        existing_match = await self._find_existing_affair_by_title(
                            title_in, rhythm_dash=rhythm_dash
                        )
                        if existing_match is not None:
                            aid = existing_match.get("id") or existing_match.get("affair_id")
                            # 若关键信息无实质变化，幂等复用不重复写库
                            same_desc = not act.get("description") or str(act.get("description")) == str(existing_match.get("description") or "")
                            same_ddl = not act.get("urgency_ddl") or str(act.get("urgency_ddl")) == str(existing_match.get("urgency_ddl") or "")
                            if same_desc and same_ddl and not act.get("target_date"):
                                return {
                                    "kind": "rhythm_upsert_affair",
                                    "ok": True,
                                    "deduplicated": True,
                                    "action_taken": "reused_existing",
                                    "affair_id": int(aid),
                                    "title": existing_match.get("title") or title_in,
                                }

                    if aid is not None:
                        updates = {
                            k: act[k]
                            for k in ("title", "description", "domain", "urgency_ddl", "est_minutes", "importance", "kind_meta")
                            if k in act and act[k] is not None
                        }
                        if k_name == "venture" and act.get("target_date"):
                            km = dict(updates.get("kind_meta") or {})
                            km.setdefault("target_date", str(act["target_date"])[:10])
                            updates["kind_meta"] = km
                        res = await self.rhythm.update_affair(int(aid), updates)
                        return {
                            "kind": "rhythm_upsert_affair",
                            "ok": True,
                            "updated": True,
                            "affair_id": res.get("id"),
                            "title": res.get("title") or title_in,
                        }

                    k_meta = dict(act.get("kind_meta") or {})
                    if k_name == "venture" and act.get("target_date") and not k_meta.get("target_date"):
                        k_meta["target_date"] = str(act["target_date"])[:10]
                    res = await self.rhythm.create_affair(
                        title=title_in,
                        kind=k_name,
                        domain=act.get("domain"),
                        description=str(act.get("description") or ""),
                        urgency_ddl=act.get("urgency_ddl"),
                        est_minutes=int(act.get("est_minutes") or 30),
                        importance=int(act.get("importance") or 3),
                        kind_meta=k_meta,
                    )
                    # 同步放进当前轮 rhythm_dash 缓存，防同轮重复创建
                    if isinstance(rhythm_dash, dict):
                        rhythm_dash.setdefault("focus_affairs", []).append(res)
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

        if kind == "finance_log_tx":
            try:
                amt = float(act.get("amount") or act.get("value") or 0)
                if amt <= 0:
                    return {"kind": "finance_log_tx", "ok": False, "error": "invalid amount"}
                if await self.finance.health():
                    res = await self.finance.create_transaction(
                        amount=amt,
                        description=str(act.get("description") or raw_text[:60]),
                        direction=str(act.get("direction") or "expense"),
                        tags=str(act.get("tags") or ""),
                        account_id=act.get("account_id"),
                        account_hint=str(act.get("account_hint") or ""),
                        items=act.get("items") if isinstance(act.get("items"), list) else None,
                    )
                    return {
                        "kind": "finance_log_tx",
                        "ok": True,
                        "tx_id": res.get("id"),
                        "value": res.get("value"),
                        "description": res.get("description"),
                    }
            except Exception as exc:
                logger.warning("QuickCoachAgent finance_log_tx failed: %s", exc)
            return {"kind": "finance_log_tx", "ok": False}

        if kind == "finance_reconcile_account":
            try:
                bal = float(act.get("actual_balance"))
                if await self.finance.health():
                    res = await self.finance.reconcile_account(
                        actual_balance=bal,
                        account_id=act.get("account_id"),
                        account_hint=str(act.get("account_hint") or ""),
                        force_adjust=bool(act.get("force_adjust", False)),
                        note=str(act.get("note") or "快脑口头核对"),
                        source=f"quick_chat:{channel}",
                    )
                    return {
                        "kind": "finance_reconcile_account",
                        "ok": True,
                        "handling": res.get("handling"),
                        "drift_amount": res.get("drift_amount"),
                        "message": res.get("message"),
                    }
            except Exception as exc:
                logger.warning("QuickCoachAgent finance_reconcile_account failed: %s", exc)
            return {"kind": "finance_reconcile_account", "ok": False}

        if kind == "finance_run_hygiene":
            try:
                if await self.finance.health():
                    res = await self.finance.run_hygiene_scan(
                        days=act.get("days", 30),
                        auto_apply_safe=bool(act.get("auto_apply_safe", True)),
                        created_by=f"quick_chat:{channel}",
                    )
                    return {"kind": "finance_run_hygiene", "ok": True, **res}
            except Exception as exc:
                logger.warning("QuickCoachAgent finance_run_hygiene failed: %s", exc)
            return {"kind": "finance_run_hygiene", "ok": False}

        if kind == "finance_batch_tag":
            try:
                updates = [u for u in (act.get("updates") or []) if isinstance(u, dict)]
                if updates and await self.finance.health():
                    res = await self.finance.batch_tag(updates)
                    return {
                        "kind": "finance_batch_tag",
                        "ok": True,
                        "success_count": res.get("success_count", 0),
                    }
            except Exception as exc:
                logger.warning("QuickCoachAgent finance_batch_tag failed: %s", exc)
            return {"kind": "finance_batch_tag", "ok": False}

        return None

    async def _find_existing_affair_by_title(
        self, title: str, rhythm_dash: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """在活跃 Rhythm 事务/项目中按语义标题判重，防止多轮对话反复新建同名事务。"""
        terminal = {"DONE", "CANCELED", "ARCHIVED", "COMPLETED"}
        pool: List[Dict[str, Any]] = []
        if isinstance(rhythm_dash, dict):
            for key in ("focus_affairs", "inbox_affairs", "overdue_affairs", "projects"):
                for item in rhythm_dash.get(key) or []:
                    if isinstance(item, dict):
                        pool.append(item)
        # 兜底查全量活跃事务（覆盖未进 focus_affairs 的 base_rhythm/habit 等）
        try:
            if hasattr(self.rhythm, "list_affairs"):
                for item in await self.rhythm.list_affairs(limit=100):
                    if isinstance(item, dict):
                        pool.append(item)
        except Exception:
            pass
        for item in pool:
            st = str(item.get("state") or "").upper()
            if st in terminal:
                continue
            existing_title = str(item.get("title") or "")
            if titles_match_semantically(title, existing_title):
                return item
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
