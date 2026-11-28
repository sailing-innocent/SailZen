# -*- coding: utf-8 -*-
# @file context_budget.py
# @brief SailTick Prompt 预算管理、按 Slot Schema 裁剪与 JSON 三段自愈
# @author sailing-innocent
# @date 2026-11-28
# @version 1.0
# ---------------------------------
"""PromptBudgeter — 严格控制单次 Tick Prompt 字符/Token 预算与按窗口裁剪 Action Schema。

核心职责：
1. 按 slot 仅注入本窗口真正需要的 Action JSON 模板（削减 ~55% Schema 字符）；
2. 对 system/slot、plan、expert_brief、memory、handoff、data_summary 实施分块硬预算截断；
3. 输出各区块字数明细（budget_report），写入 AI Trace 便于持续观测；
4. 提供确定性 JSON 提取与语法自愈工具（去围栏、去尾逗号、未闭合括号补全）。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
#  Action Schema 注册表与按 Slot 白名单
# ═══════════════════════════════════════════════════════════════════════


def build_action_schema_map(tick_date: str) -> Dict[str, str]:
    """返回所有慢脑 Action 的紧凑单行 JSON 示例模板。"""
    return {
        "profile_update": '{"kind": "profile_update", "key": "wake_time", "value": "07:30", "confidence": 0.9, "source": "asked"}',
        "memory": '{"kind": "memory", "memory_type": "semantic|procedural", "domain": "health|rhythm|finance|general", "key": "diet_pattern", "summary": "<=80字精简结论", "value": "完整说明"}',
        "diet_log": '{"kind": "diet_log", "meal_type": "lunch", "description": "食堂鸡胸肉+米饭半碗", "calories": 550}',
        "plan_update": f'{{"kind": "plan_update", "plan_version": "v1.1", "target_weight": "70.0", "phase_name": "稳态适应期", "phase_rationale": "原因", "focus_notes": "关注点", "tolerance_kg": 0.7, "ai_summary": "健康页一句话评语", "daily_targets": {{"{tick_date}": 74.5}}}}',
        "daily_report": f'{{"kind": "daily_report", "report_date": "{tick_date}", "title": "{tick_date} 今日生活总览", "summary": "1-2句总览摘要", "body_markdown": "完整日报 Markdown", "sections": {{"health": {{"summary": "...", "highlights": ["..."]}}, "rhythm": {{"summary": "...", "highlights": ["..."]}}, "finance": {{"summary": "...", "highlights": ["..."]}}, "chief": {{"summary": "...", "highlights": ["..."]}}}}, "weight_snapshot": {{}}, "diet_summary": {{}}, "plan_update": {{}}, "tomorrow_focus": ["建议1", "建议2"], "push": true}}',
        "rhythm_sync_timeline": f'{{"kind": "rhythm_sync_timeline", "date": "{tick_date}", "rationale": "排程说明", "blocks": [{{"title": "核心推进", "start": "10:00", "end": "11:30", "block_type": "focus|light|career|meal|habit|rest|micro_rest|sleep|commute|work_window|fixed|buffer|occupied", "affair_id": 12, "note": ""}}]}}',
        "rhythm_upsert_affair": '{"kind": "rhythm_upsert_affair", "id": null, "title": "项目/任务名", "kind_name": "venture|task_oneoff|habit|fixed_plan", "domain": "work|career|life", "urgency_ddl": "2026-12-15T00:00:00", "est_minutes": 60, "description": "", "milestones": ["里程碑1"]}',
        "rhythm_transit_affair": '{"kind": "rhythm_transit_affair", "affair_id": 12, "action": "finish|start|defer|pause|resume|graduate|cancel", "defer_to": "2026-11-29T09:00:00"}',
        "rhythm_milestone_done": '{"kind": "rhythm_milestone_done", "milestone_id": 34}',
        "rhythm_occupancy": f'{{"kind": "rhythm_occupancy", "date": "{tick_date}", "occupancy_type": "meeting|leave|travel|appointment", "start": "14:00", "end": "16:00", "label": "评审会"}}',
        "rhythm_block_status": '{"kind": "rhythm_block_status", "block_id": 56, "status": "DONE|SKIPPED|DOING"}',
        "rhythm_checkin": '{"kind": "rhythm_checkin", "affair_id": 7, "result": "done|kept|missed", "note": ""}',
        "finance_log_tx": '{"kind": "finance_log_tx", "amount": 35.5, "description": "午饭外卖", "direction": "expense", "tags": "零食", "account_hint": "微信", "items": []}',
        "finance_reconcile_account": '{"kind": "finance_reconcile_account", "account_hint": "支付宝余额宝", "actual_balance": 2950.3, "note": "余额核对"}',
        "finance_run_hygiene": '{"kind": "finance_run_hygiene", "days": 30, "auto_apply_safe": true}',
        "finance_batch_tag": '{"kind": "finance_batch_tag", "updates": [{"id": 123, "tags": "交通"}]}',
        "resolve_ticket": '{"kind": "resolve_ticket", "ticket_id": 1, "resolution": "已吸收至画像"}',
        "episode": '{"kind": "episode", "content": "要记入事件流的内容"}',
    }


SLOT_ACTION_ALLOWLIST: Dict[str, List[str]] = {
    "morning_checkin": [
        "profile_update",
        "memory",
        "diet_log",
        "plan_update",
        "rhythm_sync_timeline",
        "rhythm_upsert_affair",
        "rhythm_occupancy",
        "rhythm_checkin",
        "resolve_ticket",
    ],
    "midday_checkin": [
        "profile_update",
        "memory",
        "diet_log",
        "rhythm_sync_timeline",
        "rhythm_occupancy",
        "rhythm_block_status",
        "rhythm_transit_affair",
        "finance_log_tx",
        "resolve_ticket",
    ],
    "evening_review": [
        "profile_update",
        "memory",
        "diet_log",
        "plan_update",
        "rhythm_sync_timeline",
        "rhythm_upsert_affair",
        "rhythm_transit_affair",
        "rhythm_milestone_done",
        "rhythm_block_status",
        "rhythm_checkin",
        "finance_log_tx",
        "resolve_ticket",
    ],
    "pre_sleep_report": [
        "daily_report",
        "plan_update",
        "rhythm_sync_timeline",
        "profile_update",
        "memory",
        "resolve_ticket",
    ],
    "nightly_maintenance": [
        "plan_update",
        "rhythm_sync_timeline",
        "rhythm_upsert_affair",
        "profile_update",
        "memory",
        "finance_batch_tag",
        "resolve_ticket",
        "episode",
    ],
}

# 各 Slot 重点关注的业务域（用于筛选专家简报与记忆排序加权）
SLOT_PRIMARY_DOMAINS: Dict[str, List[str]] = {
    "morning_checkin": ["health", "rhythm"],
    "midday_checkin": ["rhythm", "health"],
    "evening_review": ["rhythm", "health", "finance"],
    "pre_sleep_report": ["health", "rhythm", "finance"],
    "nightly_maintenance": ["health", "rhythm", "finance"],
}

# 各区块字符硬上限（总目标 <= 12,000 字符）
DEFAULT_SECTION_CAPS: Dict[str, int] = {
    "system_slot": 2300,
    "plan": 600,
    "expert_brief": 1400,
    "memory_profile": 900,
    "memory_semantic": 1200,
    "memory_procedural": 700,
    "handoff": 400,
    "data_summary": 2100,
    "tickets_and_msgs": 1050,
}


def clip_text(text: str, max_chars: int, suffix: str = "…[已截断]") -> str:
    """按字符硬上限截断，尽量停在换行边界。"""
    s = (text or "").strip()
    if max_chars <= 0 or len(s) <= max_chars:
        return s
    cut = max(0, max_chars - len(suffix))
    candidate = s[:cut]
    nl = candidate.rfind("\n")
    if nl > int(cut * 0.65):
        candidate = candidate[:nl]
    return candidate.rstrip() + suffix


def infer_ticket_domain(
    *,
    explicit_domain: str = "",
    topic: str = "",
    title: str = "",
    body: str = "",
    ticket_type: str = "",
) -> str:
    """根据显式 domain、topic 或文案推断规范业务域：health | rhythm | finance | general。"""
    dom = (explicit_domain or "").strip().lower()
    if dom in ("health", "rhythm", "finance", "general"):
        return dom
    if dom in ("diet", "weight", "sleep", "exercise", "mood"):
        return "health"
    if dom in ("plan", "schedule", "project", "task", "work"):
        return "rhythm"
    if dom in ("money", "bill", "budget", "account"):
        return "finance"

    if ticket_type == "approval":
        comb = f"{topic} {title}".lower()
        if any(k in comb for k in ("账单", "财务", "平账", "finance", "tx", "tag")):
            return "finance"
        return "general"

    t_low = (topic or "").strip().lower()
    if t_low.startswith(("diet", "weight", "sleep", "exercise", "mood", "health", "canteen", "dinner", "breakfast", "lunch", "gym", "height")):
        return "health"
    if t_low.startswith(("rhythm", "project", "schedule", "focus", "wake", "spare", "meeting", "affair", "timeline", "task")):
        return "rhythm"
    if t_low.startswith(("finance", "bill", "budget", "money", "account", "reconcile", "hygiene", "spend", "snack_spend")):
        return "finance"

    combined = f"{topic} {title} {body[:120]}".lower()
    if any(k in combined for k in ("体重", "称重", "午饭", "晚饭", "早饭", "食堂", "饮食", "热量", "运动", "健身", "睡眠", "熬夜", "减脂", "蛋白", "聚餐")):
        return "health"
    if any(k in combined for k in ("账单", "消费", "余额", "平账", "支出", "预算", "记账", "打标", "微信余额", "支付宝")):
        return "finance"
    if any(k in combined for k in ("项目", "日程", "时间线", "里程碑", "待办", "排期", "开会", "专注", "工作时段", "下班", "起床", "作息", "ddl")):
        return "rhythm"
    return "general"


def persona_for_domain(domain: str) -> str:
    return {
        "health": "health_coach",
        "rhythm": "rhythm_planner",
        "finance": "finance_secretary",
    }.get((domain or "").lower(), "chief_steward")


def target_clients_for_domain(domain: str, ticket_type: str = "question") -> List[str]:
    dom = (domain or "general").lower()
    if ticket_type == "approval":
        return ["web", "vscode", "android"]
    if dom == "rhythm":
        return ["android", "web", "vscode"]
    if dom in ("health", "finance"):
        return ["android", "web"]
    return ["android", "web"]


# ═══════════════════════════════════════════════════════════════════════
#  Prompt 预算组装器
# ═══════════════════════════════════════════════════════════════════════


class PromptBudgeter:
    """按窗口裁剪与字符硬上限组装 PLAN Prompt。"""

    def __init__(self, section_caps: Optional[Dict[str, int]] = None):
        self.caps = {**DEFAULT_SECTION_CAPS, **(section_caps or {})}

    def build_plan_prompt(
        self,
        *,
        slot: str,
        tick_date: str,
        system_prompt: str,
        slot_guidance: str,
        plan_text: str,
        expert_brief_text: str,
        memory_summary: Dict[str, Any],
        prev_handoff_text: str,
        weight_update_note: str,
        data_summary: str,
        replies_text: str,
        msgs_text: str,
        tickets_text: str,
        q_slice_text: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """组装受硬预算保护的 Prompt，并返回 (prompt, budget_report)。"""
        sys_block = clip_text(f"{system_prompt.strip()}\n\n{slot_guidance.strip()}", self.caps["system_slot"])
        plan_block = clip_text(plan_text, self.caps["plan"])
        brief_block = clip_text(expert_brief_text, self.caps["expert_brief"])
        profile_block = clip_text(str(memory_summary.get("profile") or "(空)"), self.caps["memory_profile"])
        semantic_block = clip_text(str(memory_summary.get("semantic") or "(空)"), self.caps["memory_semantic"])
        procedural_block = clip_text(str(memory_summary.get("procedural") or "(空)"), self.caps["memory_procedural"])
        handoff_block = clip_text(prev_handoff_text, self.caps["handoff"])
        data_block = clip_text(f"{weight_update_note}\n{data_summary}", self.caps["data_summary"])

        # 票据/回复/消息合用预算，优先保留新回复与未读消息
        half = self.caps["tickets_and_msgs"] // 3
        replies_block = clip_text(replies_text, max(300, half + 150))
        msgs_block = clip_text(msgs_text, max(300, half + 150))
        tickets_block = clip_text(tickets_text, max(240, half))

        # 按 Slot 白名单裁剪 Action Schema
        all_schemas = build_action_schema_map(tick_date)
        allow_kinds = SLOT_ACTION_ALLOWLIST.get(slot) or list(all_schemas.keys())
        schema_lines = [f"    {all_schemas[k]}" for k in allow_kinds if k in all_schemas]
        actions_schema_str = ",\n".join(schema_lines)

        allow_tickets = slot not in ("nightly_maintenance", "pre_sleep_report")
        if allow_tickets:
            tickets_schema = (
                '  "tickets": [\n'
                '    {\n'
                '      "type": "question|task|info",\n'
                '      "domain": "health|rhythm|finance|general",\n'
                '      "topic": "话题唯一键，如 weight_checkin / diet_lunch / rhythm_key_projects",\n'
                '      "title": "简短标题（通知标题）",\n'
                '      "body": "正文（温和具体，含原因）",\n'
                '      "priority": "low|normal|high",\n'
                '      "expected_reply_hours": 36,\n'
                '      "fallback_assumption": "不回复时的默认假设",\n'
                '      "meta": {"quick_replies": ["快捷回复1", "快捷回复2"]}\n'
                '    }\n'
                '  ],'
            )
            q_section = f"\n# 本窗口渐进提问候选（最多选 0~1 个）\n{q_slice_text}\n"
        else:
            tickets_schema = '  "tickets": [],'
            q_section = ""

        task_block = f"""# 任务
你是 SailTick 的 PLAN 阶段，为「{slot}」（{tick_date}）生成本窗口计划。严格只输出合法 JSON：
{{
  "summary": "本 Tick 要点（1-2 句）",
{tickets_schema}
  "actions": [
{actions_schema_str}
  ],
  "unfinished": [{{"task": "未完成事项", "reason": "原因"}}],
  "next_tick_suggestions": ["给下个 Tick 的建议"]
}}
约束：
1. actions 仅输出本窗口真正需要的项；每张票据务必标注准确 `domain`（health/rhythm/finance/general）以便分端分 Tab 展示；
2. 写入 `memory` 动作时必须提供 `<=80` 字的 `summary` 和规范 `domain` 与稳定 `key`（同主题复用同一 key 避免堆积）；
3. 自主排程权：直接用 `rhythm_sync_timeline` 写出/更新今日或明日时间线（自动保留已完成与刚性钉块），少而精、留缓冲；
4. tickets 最多 1 张提问（总数最多 2 张）；睡前/夜间或已有待回提问时留空 `[]`；温和不苛责，压力与睡眠优先。"""

        prompt = f"""{sys_block}

# 当前计划
{plan_block}

# 夜间数学建模与深度洞察（分域精简）
{brief_block}

# 用户画像与记忆
[Profile]
{profile_block}
[Semantic]
{semantic_block}
[Procedural]
{procedural_block}

# 上 Tick 摘要
{handoff_block}

# 用户状态数据
{data_block}

# 新收到的用户票据回复（请吸收并 resolve_ticket）
{replies_block}

# 用户主动发来的消息（请吸收并整合）
{msgs_block}

# 当前未回复票据
{tickets_block}
{q_section}
{task_block}"""

        report = {
            "slot": slot,
            "total_chars": len(prompt),
            "estimated_tokens": int(len(prompt) * 0.55),
            "sections": {
                "system_slot": len(sys_block),
                "plan": len(plan_block),
                "expert_brief": len(brief_block),
                "memory_profile": len(profile_block),
                "memory_semantic": len(semantic_block),
                "memory_procedural": len(procedural_block),
                "handoff": len(handoff_block),
                "data_summary": len(data_block),
                "tickets_and_msgs": len(replies_block) + len(msgs_block) + len(tickets_block),
                "task_schema": len(task_block),
            },
            "allowed_action_kinds": allow_kinds,
            "memory_stats": memory_summary.get("stats") if isinstance(memory_summary, dict) else {},
        }
        return prompt, report


# ═══════════════════════════════════════════════════════════════════════
#  JSON 提取与确定性语法自愈
# ═══════════════════════════════════════════════════════════════════════


def extract_json_candidate(raw: str) -> str:
    """剥离 markdown 代码围栏并截取最外层 JSON 对象。"""
    s = (raw or "").strip()
    if not s:
        return ""
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if fence:
        s = fence.group(1).strip()
    start = s.find("{")
    if start == -1:
        return s
    end = s.rfind("}")
    if end != -1 and end > start:
        return s[start : end + 1]
    return s[start:]


def _strip_trailing_commas(s: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", s)


def _escape_raw_newlines_in_strings(s: str) -> str:
    """将 JSON 字符串字面量内部的裸换行替换为 \\n，修复常见 LLM 输出失误。"""
    out: List[str] = []
    in_str = False
    escaped = False
    for ch in s:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\":
            out.append(ch)
            escaped = True
            continue
        if ch == '"':
            in_str = not in_str
            out.append(ch)
            continue
        if in_str and ch == "\n":
            out.append("\\n")
            continue
        if in_str and ch == "\r":
            continue
        out.append(ch)
    return "".join(out)


def _close_truncated_json(s: str) -> str:
    """为被 max_tokens 截断的 JSON 补齐未闭合的引号与括号。"""
    stack: List[str] = []
    in_str = False
    escaped = False
    for ch in s:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in ("}", "]") and stack and stack[-1] == ch:
            stack.pop()
    repaired = s.rstrip()
    if in_str:
        repaired += '"'
    repaired = re.sub(r",\s*$", "", repaired)
    if stack:
        repaired += "".join(reversed(stack))
    return _strip_trailing_commas(repaired)


def _insert_missing_commas(s: str) -> str:
    """修复对象/数组元素之间漏掉的逗号（如 `"a": 1\n"b": 2` 或 `}\n{`）。"""
    # `}\s*{` 或 `]\s*[` 或 `}\s*"` 或 `"\s*"`（跨行）
    s = re.sub(r'(\}|\]|true|false|null|\d)\s*\n(\s*["{\[])', r"\1,\n\2", s)
    s = re.sub(r'("\s*)\n(\s*"[^"]+"\s*:)', r"\1,\n\2", s)
    return s


def parse_json_with_repair(raw: str) -> Tuple[Optional[Dict[str, Any]], bool, Optional[str]]:
    """尝试解析 JSON，并在失败时执行轻量确定性自愈。

    Returns:
        (parsed_dict_or_none, was_repaired, error_message_if_failed)
    """
    cand = extract_json_candidate(raw)
    if not cand:
        return None, False, "empty json content"

    try:
        parsed = json.loads(cand)
        if isinstance(parsed, dict):
            return parsed, False, None
        return None, False, f"expected JSON object, got {type(parsed).__name__}"
    except json.JSONDecodeError as first_err:
        err_msg = str(first_err)

    # 可选优先使用第三方 json_repair（若环境已安装）
    try:
        import json_repair  # type: ignore

        repaired_obj = json_repair.loads(cand)
        if isinstance(repaired_obj, dict):
            return repaired_obj, True, None
    except Exception:
        pass

    # 内置确定性修复流水线
    attempts = [
        _strip_trailing_commas(cand),
        _strip_trailing_commas(_escape_raw_newlines_in_strings(cand)),
        _strip_trailing_commas(_insert_missing_commas(_escape_raw_newlines_in_strings(cand))),
        _close_truncated_json(_insert_missing_commas(_escape_raw_newlines_in_strings(cand))),
    ]
    for fixed in attempts:
        try:
            parsed = json.loads(fixed)
            if isinstance(parsed, dict):
                return parsed, True, None
        except json.JSONDecodeError as exc:
            err_msg = str(exc)

    return None, False, err_msg
