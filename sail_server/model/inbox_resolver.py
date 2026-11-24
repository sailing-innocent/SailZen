# -*- coding: utf-8 -*-
# @file inbox_resolver.py
# @brief Cross-Channel Domain Event -> UserInbox Auto-Reconciliation Engine
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""跨端/跨模块业务事件自动消解引擎（InboxResolver）。

核心场景（直接解决“教练问午餐如何处理，用户在 Web 健康页已回答或已记午餐，
Android 收件箱依然残留该消息”的架构痛点）：

当用户在任意终端完成业务域动作时：
- health.diet.logged       : 记录饮食 / 发餐饮消息 / 识图落库饮食
- health.weight.logged     : 记录体重 / 体脂秤识图
- health.sleep.logged      : 记录睡眠
- health.exercise.logged   : 记录运动
- health.medication.logged : 服药打卡
- rhythm.affair.done       : 完成事务

InboxResolver 自动匹配该用户当前活跃的 UserInboxItem（通过显式
action_schema.auto_resolve_signals 或语义话题规则），在同一事务中：
1. 将 UserInboxItem 标记为 answered/resolved 并递增 sync_seq；
2. 将关联的 SailTickTicket 标记为 replied 并写入摘要（供下轮 SCAN 吸收，不再重复发问）；
3. 将关联的 Reminder 标记为 RESOLVED；
4. 通过 UserSyncHub 向所有在线终端广播 inbox.item_resolved（Android 自动移出收件箱并撤回通知栏）。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from sail_server.model.inbox import (
    ACTIVE_STATUSES,
    STATUS_ANSWERED,
    STATUS_RESOLVED,
    _add_inbox_event,
    _broadcast_resolved,
    _close_linked_source_entities,
    next_sync_seq,
)
from sail_server.model.user import is_auto_resolve_enabled
from sailzen_orm.inbox import UserInboxItem

logger = logging.getLogger(__name__)

_MEAL_ALIASES = {
    "breakfast": ("breakfast", "早餐", "早饭"),
    "lunch": ("lunch", "午餐", "午饭", "中午", "canteen"),
    "dinner": ("dinner", "晚餐", "晚饭"),
    "snack": ("snack", "加餐", "零食"),
}

_MEAL_CN = {
    "breakfast": "早餐",
    "lunch": "午餐",
    "dinner": "晚餐",
    "snack": "加餐",
}


def _normalize_meal_type(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    for canonical, aliases in _MEAL_ALIASES.items():
        if s in aliases:
            return canonical
    return s


def _matches_explicit_signal(
    signal_rule: Dict[str, Any],
    domain: str,
    event: str,
    payload: Dict[str, Any],
) -> bool:
    if signal_rule.get("domain") != domain or signal_rule.get("event") != event:
        return False

    # 可选日期匹配
    rule_date = signal_rule.get("date")
    ev_date = payload.get("date") or date.today().isoformat()
    if rule_date and str(rule_date)[:10] != str(ev_date)[:10]:
        return False

    # 可选餐次匹配
    rule_meal = _normalize_meal_type(signal_rule.get("meal_type"))
    if rule_meal:
        ev_meal = _normalize_meal_type(payload.get("meal_type"))
        if ev_meal != rule_meal:
            return False

    # 可选事务 ID 匹配
    if signal_rule.get("affair_id") is not None:
        if str(payload.get("affair_id")) != str(signal_rule.get("affair_id")):
            return False

    return True


def _matches_heuristic(
    item: UserInboxItem,
    domain: str,
    event: str,
    payload: Dict[str, Any],
    now: datetime,
) -> bool:
    """对未声明 auto_resolve_signals 的存量/LLM 自由提问做精准语义兜底匹配。"""
    schema = item.action_schema if isinstance(item.action_schema, dict) else {}
    combined = f"{item.topic or ''} {item.title or ''} {item.body or ''}".lower()
    created = item.created_at or item.trigger_at or now
    is_recent = (now - created) <= timedelta(hours=20)

    if domain == "health" and event == "diet.logged" and is_recent:
        ev_meal = _normalize_meal_type(payload.get("meal_type"))
        if not ev_meal:
            return False
        schema_meal = _normalize_meal_type(schema.get("meal_type"))
        if schema_meal and schema_meal == ev_meal:
            return True
        aliases = _MEAL_ALIASES.get(ev_meal, (ev_meal,))
        has_meal_word = any(a in combined for a in aliases)
        has_diet_context = any(
            k in combined for k in ("餐", "饭", "饮食", "diet", "meal", "canteen", "吃", "零食")
        )
        return has_meal_word and has_diet_context

    if domain == "health" and event == "weight.logged" and is_recent:
        return (
            item.topic in ("weight_checkin", "rhythm.weight", "health.weight")
            or schema.get("collection_type") == "weight"
            or any(k in combined for k in ("称重", "记录体重", "体重打卡", "上秤"))
        )

    if domain == "health" and event == "sleep.logged" and is_recent:
        return (
            item.topic in ("sleep_checkin", "rhythm.sleep", "health.sleep")
            or schema.get("collection_type") == "sleep"
            or any(k in combined for k in ("睡眠记录", "昨晚睡", "几点睡"))
        )

    if domain == "health" and event == "exercise.logged" and is_recent:
        return (
            item.topic in ("exercise_checkin", "rhythm.exercise", "health.exercise")
            or schema.get("collection_type") == "exercise"
            or "运动打卡" in combined
        )

    if domain == "health" and event == "medication.logged" and is_recent:
        return (
            item.topic in ("medication_checkin", "rhythm.medication", "health.medication")
            or schema.get("collection_type") == "medication"
            or any(k in combined for k in ("服药", "吃药提醒"))
        )

    if domain == "rhythm" and event == "affair.done":
        affair_id = payload.get("affair_id")
        if affair_id is None:
            return False
        if item.ref_type == "rhythm_affair" and str(item.ref_id) == str(affair_id):
            return True
        if schema.get("affair_id") is not None and str(schema.get("affair_id")) == str(affair_id):
            return True

    return False


def _build_default_summary(
    domain: str, event: str, payload: Dict[str, Any], actor_client: str
) -> str:
    client_label = {
        "web": "Web 端",
        "android": "Android 端",
        "cli": "CLI",
        "sailtick": "SailTick",
        "qq_bot": "QQ 机器人",
    }.get(actor_client, actor_client or "其他端")

    custom = str(payload.get("summary") or "").strip()
    if domain == "health" and event == "diet.logged":
        meal = _MEAL_CN.get(_normalize_meal_type(payload.get("meal_type")), "饮食")
        return f"已在{client_label}记录{meal}" + (f"：{custom[:160]}" if custom else "")
    if domain == "health" and event == "weight.logged":
        val = payload.get("value")
        return f"已在{client_label}记录体重" + (f"：{val} kg" if val is not None else "")
    if domain == "health" and event == "sleep.logged":
        hrs = payload.get("hours")
        return f"已在{client_label}记录睡眠" + (f"：{hrs}h" if hrs is not None else "")
    if domain == "health" and event == "exercise.logged":
        return f"已在{client_label}记录运动" + (f"：{custom[:160]}" if custom else "")
    if domain == "health" and event == "medication.logged":
        return f"已在{client_label}完成服药打卡" + (f"：{custom[:120]}" if custom else "")
    if domain == "rhythm" and event == "affair.done":
        return f"已在{client_label}完成该事务" + (f"：{custom[:120]}" if custom else "")
    return f"已在{client_label}完成对应操作" + (f"：{custom[:160]}" if custom else "")


def reconcile_domain_signal(
    db: Session,
    *,
    domain: str,
    event: str,
    payload: Optional[Dict[str, Any]] = None,
    user_id: int = 1,
    actor_client: str = "web",
    device_id: str = "",
) -> List[int]:
    """根据业务域事件自动消解匹配的活跃收件箱条目，返回被消解的 inbox_item_id 列表。"""
    try:
        if not is_auto_resolve_enabled(db, user_id):
            return []

        ev_payload = dict(payload or {})
        ev_payload.setdefault("date", date.today().isoformat())
        now = datetime.now()

        active_items = (
            db.query(UserInboxItem)
            .filter(
                UserInboxItem.user_id == user_id,
                UserInboxItem.status.in_(sorted(ACTIVE_STATUSES)),
            )
            .all()
        )
        if not active_items:
            return []

        matched: List[UserInboxItem] = []
        for item in active_items:
            schema = item.action_schema if isinstance(item.action_schema, dict) else {}
            rules = schema.get("auto_resolve_signals")
            hit = False
            if isinstance(rules, list) and rules:
                for rule in rules:
                    if isinstance(rule, dict) and _matches_explicit_signal(
                        rule, domain, event, ev_payload
                    ):
                        hit = True
                        break
            if not hit and _matches_heuristic(item, domain, event, ev_payload, now):
                hit = True
            if hit:
                matched.append(item)

        if not matched:
            return []

        summary = _build_default_summary(domain, event, ev_payload, actor_client)
        res_source = f"auto:{actor_client}:{domain}.{event}"
        resolved_ids: List[int] = []

        for item in matched:
            is_question = item.item_kind == "question"
            item.status = STATUS_ANSWERED if is_question else STATUS_RESOLVED
            item.is_read = True
            item.read_at = item.read_at or now
            if is_question and not item.reply_text:
                item.reply_text = summary
            item.resolution_source = res_source
            item.resolution_summary = summary
            item.resolution_ref = ev_payload
            item.resolved_at = now
            item.sync_seq = next_sync_seq(db)
            item.updated_at = now

            _add_inbox_event(
                db,
                item,
                "auto_resolved",
                actor_client=actor_client,
                device_id=device_id,
                detail={
                    "domain": domain,
                    "event": event,
                    "summary": summary,
                    "payload": ev_payload,
                },
            )
            _close_linked_source_entities(
                db,
                item,
                action="reply" if is_question else "resolve",
                reply_text=summary if is_question else None,
                resolution_summary=summary,
            )
            resolved_ids.append(item.id)

        db.commit()
        for item in matched:
            db.refresh(item)
            _broadcast_resolved(item)

        logger.info(
            "[inbox_resolver] auto-resolved %d items for user=%s signal=%s.%s ids=%s",
            len(resolved_ids),
            user_id,
            domain,
            event,
            resolved_ids,
        )
        return resolved_ids
    except Exception as exc:
        logger.warning(
            "[inbox_resolver] reconcile_domain_signal(%s.%s) failed (non-fatal): %s",
            domain,
            event,
            exc,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return []
