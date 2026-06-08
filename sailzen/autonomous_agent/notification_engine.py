# -*- coding: utf-8 -*-
# @file notification_engine.py
# @brief Push notification abstraction (Lark, IM, log)
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""NotificationEngine — abstracts push channels for the autonomous agent.

Channels:
  - lark_im: Personal chat message
  - lark_group: Group chat message
  - log: Write to agent log (fallback)

Features:
  - Quiet hours: No non-urgent messages between 23:00-08:00
  - Deduplication: Same alert within 4h is suppressed
  - Priority filtering
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from sailzen.autonomous_agent.db import AgentDatabase

logger = logging.getLogger(__name__)


class NotificationEngine:
    """Notification delivery engine."""

    def __init__(self, config, db: Optional[AgentDatabase] = None):
        self.config = config
        self.db = db
        self._recent_alerts: Dict[str, datetime] = {}  # content_hash -> last_sent
        self._dedup_window_hours = 4

    # ── Public API ────────────────────────────────────────────────────

    async def send(self, title: str, content: str, channel: Optional[str] = None,
                   priority: str = "normal", context: Optional[dict] = None) -> bool:
        """Send a notification.

        Args:
            title: Notification title
            content: Notification body
            channel: Target channel (defaults to config.default_channel)
            priority: low | normal | high | urgent
            context: Additional context data

        Returns:
            True if sent successfully
        """
        channel = channel or self.config.default_channel

        # Quiet hours check
        if not self._should_send_during_quiet_hours(priority):
            logger.info("Notification suppressed due to quiet hours: %s", title)
            return False

        # Deduplication check
        content_hash = self._hash_content(title + content)
        if self._is_duplicate(content_hash):
            logger.info("Duplicate notification suppressed: %s", title)
            return False

        # Queue in DB if available
        if self.db:
            await self.db.create_reminder({
                "title": title,
                "content": content,
                "channel": channel,
                "priority": priority,
                "status": "pending",
                "context": json.dumps(context or {}),
            })

        # Deliver
        success = False
        if channel == "lark_im":
            success = await self._send_lark_im(title, content)
        elif channel == "lark_group":
            success = await self._send_lark_group(title, content)
        elif channel == "log":
            success = self._send_log(title, content)
        else:
            logger.warning("Unknown notification channel: %s", channel)

        if success:
            self._recent_alerts[content_hash] = datetime.now()
            if self.db:
                # Update reminder status (would need reminder_id tracking)
                pass

        return success

    async def flush_queue(self) -> int:
        """Flush pending notifications from DB queue."""
        if not self.db:
            return 0
        pending = await self.db.list_reminders(status="pending")
        sent = 0
        for reminder in pending:
            if not self._should_send_during_quiet_hours(reminder.get("priority", "normal")):
                continue
            success = False
            channel = reminder.get("channel", "log")
            title = reminder.get("title", "")
            content = reminder.get("content", "")
            if channel == "lark_im":
                success = await self._send_lark_im(title, content)
            elif channel == "lark_group":
                success = await self._send_lark_group(title, content)
            elif channel == "log":
                success = self._send_log(title, content)

            if success:
                await self.db.update_reminder(reminder["id"], {
                    "status": "sent",
                    "sent_at": datetime.now().isoformat(),
                })
                sent += 1
        return sent

    # ── Channel implementations ───────────────────────────────────────

    async def _send_lark_im(self, title: str, content: str) -> bool:
        """Send Lark IM message via lark-cli."""
        user_open_id = self.config.lark_user_open_id
        if not user_open_id:
            logger.warning("No LARK_USER_OPEN_ID configured, falling back to log")
            return self._send_log(title, content)

        full_content = f"**{title}**\n\n{content}"
        cmd = [
            "lark-cli", "im", "send-message",
            "--receive-id", user_open_id,
            "--content", full_content,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            if proc.returncode == 0:
                logger.info("Lark IM sent: %s", title)
                return True
            else:
                logger.error("Lark IM failed: %s", stderr.decode("utf-8", errors="replace"))
                return False
        except Exception as exc:
            logger.error("Lark IM error: %s", exc)
            return False

    async def _send_lark_group(self, title: str, content: str) -> bool:
        """Send Lark group message. (Placeholder — requires chat_id)"""
        logger.info("Lark group send not fully implemented, logging instead: %s", title)
        return self._send_log(f"[GROUP] {title}", content)

    def _send_log(self, title: str, content: str) -> bool:
        """Log notification as fallback."""
        logger.info("[NOTIFY] %s: %s", title, content)
        return True

    # ── Guards ────────────────────────────────────────────────────────

    def _should_send_during_quiet_hours(self, priority: str) -> bool:
        """Check if notification should be sent during quiet hours."""
        if priority == "urgent":
            return True
        now = datetime.now().hour
        start = self.config.quiet_hours_start
        end = self.config.quiet_hours_end
        if start <= end:
            in_quiet = start <= now < end
        else:
            in_quiet = now >= start or now < end
        return not in_quiet

    def _hash_content(self, content: str) -> str:
        import hashlib
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _is_duplicate(self, content_hash: str) -> bool:
        last_sent = self._recent_alerts.get(content_hash)
        if not last_sent:
            return False
        elapsed = (datetime.now() - last_sent).total_seconds()
        return elapsed < self._dedup_window_hours * 3600
