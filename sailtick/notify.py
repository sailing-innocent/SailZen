# -*- coding: utf-8 -*-
# @file notify.py
# @brief 通知引擎（安静时段 + 去重 + 票据/推送通道）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""NotificationEngine — 从旧 autonomous_agent/notification_engine.py 迁移。

通道:
  - ticket: 创建票据（走 sail_server REST；高优先票据由 sail_server 推送手机）
  - push:   请求立即推送（夜间无声任务不用）
  - log:    仅日志（默认兜底）

安静时段（默认 23:00–08:00）：非 urgent 不推送（仍可建票据，用户在网页看到）。
去重：同 title 在 dedup_window 内只发一次。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from sailtick.config import NotifyConfig
from sailtick.inbox import TicketInbox

logger = logging.getLogger(__name__)


class NotificationEngine:
    """通知引擎。"""

    def __init__(
        self,
        config: NotifyConfig,
        inbox: Optional[TicketInbox] = None,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.config = config
        self.inbox = inbox
        self._clock = clock
        self._recent: Dict[str, datetime] = {}  # title -> last sent

    def in_quiet_hours(self, now: Optional[datetime] = None) -> bool:
        now = now or self._clock()
        start, end = self.config.quiet_hours.start, self.config.quiet_hours.end
        hour = now.hour
        if start <= end:  # 例如 01:00-06:00
            return start <= hour < end
        return hour >= start or hour < end  # 跨午夜，例如 23:00-08:00

    def _dedup_hit(self, title: str) -> bool:
        now = self._clock()
        last = self._recent.get(title)
        if last and (now - last).total_seconds() < self.config.dedup_window_seconds:
            return True
        self._recent[title] = now
        return False

    async def emit(
        self,
        title: str,
        content: str,
        priority: str = "normal",
        ticket_type: str = "info",
        tick_id: str = "",
        channel: str = "mobile",
        expected_reply_hours: Optional[int] = None,
        fallback_assumption: str = "",
        suppress_push: bool = False,
        topic: str = "",
        meta: Optional[Dict[str, Any]] = None,
        force_push: bool = False,
        domain: str = "",
        persona: str = "",
        target_clients: Optional[list] = None,
        deep_link: str = "",
    ) -> Dict[str, Any]:
        """发出一条通知。返回处置结果。

        推送规则:
        - 安静时段（默认 23:00–08:00）：仅 urgent 推送；其他落库不推送（push="none"）。
        - 非安静时段且未 suppress_push：high/urgent 或显式 force_push / question 票据推送到 Android（push="force"）。
        """
        quiet = self.in_quiet_hours()
        effective_priority = priority
        if suppress_push and priority in ("high", "urgent"):
            effective_priority = "normal"
        wants_push = (
            effective_priority in ("high", "urgent")
            or force_push
            or ticket_type == "question"
        )
        would_push = (
            self.config.push_enabled
            and not suppress_push
            and wants_push
            and (not quiet or effective_priority == "urgent")
        )

        if self._dedup_hit(title):
            return {"action": "dedup_skipped", "title": title}

        result: Dict[str, Any] = {
            "action": "ticket",
            "title": title,
            "priority": effective_priority,
            "topic": topic,
            "quiet_hours": quiet,
            "push": would_push,
            "push_suppressed": suppress_push,
        }

        if self.inbox is None:
            result["action"] = "log"
            logger.info("[notify:log] %s: %s", title, content)
            return result

        try:
            import inspect

            create_kwargs: Dict[str, Any] = {
                "tick_id": tick_id,
                "ticket_type": ticket_type,
                "title": title,
                "body": content,
                "priority": effective_priority,
                "expected_reply_hours": expected_reply_hours,
                "fallback_assumption": fallback_assumption,
                "channel": channel,
            }
            sig = inspect.signature(self.inbox.create_ticket)
            accepts_var_kw = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            if accepts_var_kw or "push" in sig.parameters:
                create_kwargs["push"] = "force" if would_push else "none"
            if accepts_var_kw or "topic" in sig.parameters:
                create_kwargs["topic"] = topic
            if accepts_var_kw or "meta" in sig.parameters:
                create_kwargs["meta"] = meta or {}
            if domain and (accepts_var_kw or "domain" in sig.parameters):
                create_kwargs["domain"] = domain
            if persona and (accepts_var_kw or "persona" in sig.parameters):
                create_kwargs["persona"] = persona
            if target_clients is not None and (accepts_var_kw or "target_clients" in sig.parameters):
                create_kwargs["target_clients"] = target_clients
            if deep_link and (accepts_var_kw or "deep_link" in sig.parameters):
                create_kwargs["deep_link"] = deep_link

            ticket = await self.inbox.create_ticket(**create_kwargs)
            result["ticket_id"] = ticket.get("id")
            if not would_push:
                result["push"] = False
        except Exception as exc:
            # 通知失败绝不阻塞 Tick
            logger.warning("notify ticket create failed, fallback to log: %s", exc)
            result["action"] = "log"
            result["error"] = str(exc)
        return result
