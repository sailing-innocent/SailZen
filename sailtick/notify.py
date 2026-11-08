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
from typing import Any, Dict, Optional

from sailtick.config import NotifyConfig
from sailtick.inbox import TicketInbox

logger = logging.getLogger(__name__)


class NotificationEngine:
    """通知引擎。"""

    def __init__(self, config: NotifyConfig, inbox: Optional[TicketInbox] = None):
        self.config = config
        self.inbox = inbox
        self._recent: Dict[str, datetime] = {}  # title -> last sent

    def in_quiet_hours(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now()
        start, end = self.config.quiet_hours.start, self.config.quiet_hours.end
        hour = now.hour
        if start <= end:  # 例如 01:00-06:00
            return start <= hour < end
        return hour >= start or hour < end  # 跨午夜，例如 23:00-08:00

    def _dedup_hit(self, title: str) -> bool:
        last = self._recent.get(title)
        if last and (datetime.now() - last).total_seconds() < self.config.dedup_window_seconds:
            return True
        self._recent[title] = datetime.now()
        return False

    async def emit(
        self,
        title: str,
        content: str,
        priority: str = "normal",
        ticket_type: str = "info",
        tick_id: str = "",
        channel: str = "web",
        expected_reply_hours: Optional[int] = None,
        fallback_assumption: str = "",
    ) -> Dict[str, Any]:
        """发出一条通知。返回处置结果。"""
        quiet = self.in_quiet_hours()
        would_push = priority in ("high", "urgent") and (not quiet or priority == "urgent")

        if self._dedup_hit(title):
            return {"action": "dedup_skipped", "title": title}

        result: Dict[str, Any] = {
            "action": "ticket",
            "title": title,
            "priority": priority,
            "quiet_hours": quiet,
            "push": would_push,
        }

        if self.inbox is None:
            result["action"] = "log"
            logger.info("[notify:log] %s: %s", title, content)
            return result

        try:
            ticket = await self.inbox.create_ticket(
                tick_id=tick_id,
                ticket_type=ticket_type,
                title=title,
                body=content,
                priority=priority,
                expected_reply_hours=expected_reply_hours,
                fallback_assumption=fallback_assumption,
                channel=channel,
            )
            result["ticket_id"] = ticket.get("id")
            if not would_push:
                result["push"] = False
        except Exception as exc:
            # 通知失败绝不阻塞 Tick
            logger.warning("notify ticket create failed, fallback to log: %s", exc)
            result["action"] = "log"
            result["error"] = str(exc)
        return result
