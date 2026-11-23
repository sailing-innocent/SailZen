# -*- coding: utf-8 -*-
# @file qq_bot.py
# @brief QQ Bot 适配器（标准 OneBot v11 HTTP Webhook + 主动消息/提醒推送，兼容 NapCat/Lagrange/LLOneBot）
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""OneBotQQAdapter — SailTick 白天快速对话的 QQ Bot 接入层。

协议兼容：OneBot v11 标准（NapCatQQ / Lagrange.OneBot / LLOneBot / go-cqhttp 均可直接对接）：
- 入站：OneBot HTTP Post Webhook → `POST http://127.0.0.1:9070/onebot/webhook`
  * 可选 X-Signature HMAC-SHA1 验签（qq_bot.webhook_secret）；
  * 白名单校验（allowed_users / allowed_groups），保护个人健康隐私；
  * 私聊直回；群聊需 @机器人 或以 `/` 开头才触发；
- 出站：
  * Webhook 响应直接返回 `{"reply": "..."}`（支持 OneBot 快速操作），并在配置了 `onebot_api_base`
    时主动调用 `POST /send_private_msg` / `POST /send_group_msg`；
  * 配合 SailTickDaemon 定时轮询 `st_scheduled_nudges`，到期提醒自动通过 QQ 私聊发出（与 Android 提醒双保险）。
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import httpx

from sailtick.config import QQBotConfig
from sailtick.db import TickDatabase
from sailtick.quick_agent import QuickCoachAgent

logger = logging.getLogger(__name__)

_CQ_CODE_RE = re.compile(r"\[CQ:[^\]]+\]")


class OneBotQQAdapter:
    """OneBot v11 QQ Bot 适配器。"""

    def __init__(
        self,
        config: QQBotConfig,
        db: TickDatabase,
        quick_agent: QuickCoachAgent,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.config = config
        self.db = db
        self.quick_agent = quick_agent
        self._clock = clock
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.config.access_token:
                headers["Authorization"] = f"Bearer {self.config.access_token}"
            api_base = self.config.onebot_api_base or ""
            is_local = "127.0.0.1" in api_base or "localhost" in api_base
            self._client = httpx.AsyncClient(
                timeout=10.0, headers=headers, trust_env=not is_local
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """校验 OneBot X-Signature (sha1=...)，未配置 webhook_secret 时放行。"""
        secret = (self.config.webhook_secret or "").strip()
        if not secret:
            return True
        if not signature_header:
            return False
        expected = "sha1=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha1).hexdigest()
        return hmac.compare_digest(expected, signature_header.strip())

    @staticmethod
    def extract_text(event: Dict[str, Any]) -> str:
        """从 OneBot v11 事件提取纯文本（兼容 string raw_message 与 array message segments）。"""
        msg = event.get("message")
        if isinstance(msg, list):
            parts = []
            for seg in msg:
                if isinstance(seg, dict) and seg.get("type") == "text":
                    parts.append(str((seg.get("data") or {}).get("text") or ""))
            joined = "".join(parts).strip()
            if joined:
                return joined
        raw = str(event.get("raw_message") or event.get("message") or "")
        return _CQ_CODE_RE.sub("", raw).strip()

    @staticmethod
    def is_bot_mentioned(event: Dict[str, Any]) -> bool:
        self_id = str(event.get("self_id") or "")
        if not self_id:
            return False
        msg = event.get("message")
        if isinstance(msg, list):
            for seg in msg:
                if (
                    isinstance(seg, dict)
                    and seg.get("type") == "at"
                    and str((seg.get("data") or {}).get("qq") or "") == self_id
                ):
                    return True
        raw = str(event.get("raw_message") or "")
        return f"[CQ:at,qq={self_id}" in raw

    async def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """处理 OneBot v11 Webhook JSON 事件。"""
        if not isinstance(event, dict):
            return {"status": "ignored", "reason": "invalid_event"}

        post_type = str(event.get("post_type") or "")
        if post_type != "message":
            return {"status": "ignored", "reason": f"post_type={post_type}"}

        msg_type = str(event.get("message_type") or "private")
        user_id = str(event.get("user_id") or "")
        group_id = str(event.get("group_id") or "")

        # 权限白名单校验
        if self.config.allowed_users and user_id not in set(self.config.allowed_users):
            logger.debug("OneBot message ignored: user %s not in allowed_users", user_id)
            return {"status": "ignored", "reason": "user_not_allowed"}

        if msg_type == "group":
            if self.config.allowed_groups and group_id not in set(self.config.allowed_groups):
                return {"status": "ignored", "reason": "group_not_allowed"}
            clean_preview = self.extract_text(event)
            if not self.is_bot_mentioned(event) and not clean_preview.startswith("/"):
                return {"status": "ignored", "reason": "group_not_mentioned"}

        text = self.extract_text(event)
        if not text:
            return {"status": "ignored", "reason": "empty_text"}

        target_id = group_id if msg_type == "group" else user_id
        session_id = f"qq:{msg_type}:{target_id}"
        res = await self.quick_agent.handle_message(
            text=text,
            channel="qq",
            user_id=user_id,
            session_id=session_id,
            target_type=msg_type,
            target_id=target_id,
        )
        reply_text = str(res.get("reply") or "").strip()

        # 若配置了 OneBot HTTP API，主动推送回复；同时也返回 quick-operation {"reply": ...}
        pushed = False
        if reply_text and self.config.onebot_api_base:
            if msg_type == "group" and group_id:
                pushed = await self.send_group_message(group_id, reply_text)
            elif user_id:
                pushed = await self.send_private_message(user_id, reply_text)

        out: Dict[str, Any] = {
            "status": "ok",
            "pushed": pushed,
            "actions": res.get("actions", []),
            "latency_ms": res.get("latency_ms", 0.0),
        }
        # 未主动发 HTTP API 时，使用 OneBot webhook quick-operation 直接回复（避免双发）
        if reply_text and not pushed:
            out["reply"] = reply_text
            if msg_type == "group":
                out["at_sender"] = True
        return out

    async def send_private_message(self, user_id: str, text: str) -> bool:
        if not self.config.onebot_api_base or not user_id or not text:
            return False
        try:
            uid: Any = int(user_id) if user_id.isdigit() else user_id
            client = self._get_client()
            resp = await client.post(
                f"{self.config.onebot_api_base.rstrip('/')}/send_private_msg",
                json={"user_id": uid, "message": text},
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.warning("OneBot send_private_msg failed (user=%s): %s", user_id, exc)
            return False

    async def send_group_message(self, group_id: str, text: str) -> bool:
        if not self.config.onebot_api_base or not group_id or not text:
            return False
        try:
            gid: Any = int(group_id) if group_id.isdigit() else group_id
            client = self._get_client()
            resp = await client.post(
                f"{self.config.onebot_api_base.rstrip('/')}/send_group_msg",
                json={"group_id": gid, "message": text},
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.warning("OneBot send_group_msg failed (group=%s): %s", group_id, exc)
            return False

    async def dispatch_due_nudges(self) -> int:
        """检查本地到期的定时提醒，若配置了 OneBot API 则同步经 QQ 发出提醒。"""
        due = await self.db.list_due_nudges(now_iso=self._clock().isoformat())
        if not due:
            return 0
        sent_count = 0
        for item in due:
            if item.get("channel") != "qq":
                # 非 QQ 通道提醒已由 sail_server Reminder 负责投递 Android，标记 sent 避免堆积
                await self.db.mark_nudge_status(item["id"], "sent")
                continue
            if not self.config.enabled or not self.config.onebot_api_base:
                # 未开启 QQ Bot 时不强行失败，若已同步至 sail_server 则直接归档
                if item.get("server_reminder_id"):
                    await self.db.mark_nudge_status(item["id"], "sent")
                continue

            target = str(item.get("target_id") or self.config.primary_user_id or "")
            if not target and self.config.allowed_users:
                target = str(self.config.allowed_users[0])
            msg = f"⏰ 【SailTick 提醒】{item['title']}"
            if item.get("body") and item["body"] != item["title"]:
                msg += f"\n{item['body']}"
            ok = False
            if target:
                if item.get("target_type") == "group":
                    ok = await self.send_group_message(target, msg)
                else:
                    ok = await self.send_private_message(target, msg)
            await self.db.mark_nudge_status(item["id"], "sent" if ok else "failed")
            if ok:
                sent_count += 1
        return sent_count
