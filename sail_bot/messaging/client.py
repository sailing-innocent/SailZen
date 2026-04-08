# -*- coding: utf-8 -*-
# @file client.py
# @brief Feishu messaging client - encapsulates all message operations
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Feishu messaging client that encapsulates all message sending operations.

This module removes message sending logic from FeishuBotAgent and provides
clean, testable interfaces for all Feishu messaging operations.
"""

import json
import time
import threading
import logging
from typing import Optional, Dict, Any
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    PatchMessageRequest,
    PatchMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from sail_bot.card_renderer import (
    CardMessageTracker,
    card_to_feishu_content,
    text_fallback,
)


logger = logging.getLogger(__name__)


class _RateLimiter:
    def __init__(self, max_calls: int = 20, period: float = 1.0):
        self._max = max_calls
        self._period = period
        self._tokens = max_calls
        self._last_refill = time.time()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.time()
                elapsed = now - self._last_refill
                if elapsed >= self._period:
                    self._tokens = self._max
                    self._last_refill = now
                if self._tokens > 0:
                    self._tokens -= 1
                    return
            time.sleep(0.05)


_rate_limiter = _RateLimiter(max_calls=20, period=1.0)


class FeishuMessagingClient:
    """Client for all Feishu messaging operations.

    Responsibilities:
    - Send text messages to chats
    - Reply to messages
    - Send interactive cards
    - Update existing cards
    - Track card metadata
    """

    def __init__(self, lark_client: Optional[lark.Client] = None):
        self.lark_client = lark_client
        self.card_tracker = CardMessageTracker()

    def set_client(self, lark_client: lark.Client) -> None:
        """Set the Lark client (used after initialization)."""
        self.lark_client = lark_client

    def send_text(self, chat_id: str, text: str) -> bool:
        """Send a text message to a Feishu chat.

        Args:
            chat_id: The target chat ID
            text: Message text content

        Returns:
            True if successful, False otherwise
        """
        if not self.lark_client:
            logger.warning("(no client) Would send to %s", chat_id)
            return False

        _rate_limiter.acquire()

        try:
            content = json.dumps({"text": text}, ensure_ascii=False)
            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(content)
                    .build()
                )
                .build()
            )
            resp = self.lark_client.im.v1.message.create(request)
            if not resp.success():
                logger.error("Send failed: %s", resp.msg)
                return False
            return True
        except Exception as exc:
            logger.error("Send error: %s", exc, exc_info=True)
            return False

    def reply_text(self, message_id: str, text: str) -> bool:
        """Reply to a specific Feishu message (thread reply).

        Args:
            message_id: The message to reply to
            text: Reply text content

        Returns:
            True if successful, False otherwise
        """
        if not self.lark_client:
            logger.warning("(no client) Would reply to %s: %s", message_id, text[:80])
            return False

        _rate_limiter.acquire()

        try:
            content = json.dumps({"text": text}, ensure_ascii=False)
            request = (
                ReplyMessageRequest.builder()
                .message_id(message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(content)
                    .msg_type("text")
                    .build()
                )
                .build()
            )
            resp = self.lark_client.im.v1.message.reply(request)
            if not resp.success():
                logger.error("Reply failed: %s", resp.msg)
                return False
            return True
        except Exception as exc:
            logger.error("Reply error: %s", exc, exc_info=True)
            return False

    def send_card(
        self,
        chat_id: str,
        card: dict,
        card_type: str = "",
        context: Optional[dict] = None,
    ) -> Optional[str]:
        """Send an interactive card to a chat.

        Args:
            chat_id: The target chat ID
            card: Card content dictionary
            card_type: Type identifier for the card
            context: Additional context to track with the card

        Returns:
            Message ID if successful, None otherwise
        """
        if not self.lark_client:
            title = card.get("header", {}).get("title", {}).get("content", "")
            logger.warning("(no client) Would send card to %s: %s", chat_id, title)
            return None

        _rate_limiter.acquire()

        try:
            content = card_to_feishu_content(card)
            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("interactive")
                    .content(content)
                    .build()
                )
                .build()
            )
            resp = self.lark_client.im.v1.message.create(request)
            if resp.success() and resp.data and resp.data.message_id:
                mid = resp.data.message_id
                if card_type:
                    self.card_tracker.register(mid, card_type, context or {})
                return mid
            else:
                logger.error("Card send failed: %s", resp.msg)
                logger.warning("Falling back to text message for card send")
                self.send_text(chat_id, text_fallback(card))
                return None
        except Exception as exc:
            logger.error("Card send error: %s", exc, exc_info=True)
            logger.warning("Falling back to text message for card send")
            try:
                self.send_text(chat_id, text_fallback(card))
            except Exception:
                pass
            return None

    def reply_card(
        self,
        message_id: str,
        card: dict,
        card_type: str = "",
        context: Optional[dict] = None,
    ) -> Optional[str]:
        """Reply with an interactive card to a specific message.

        Args:
            message_id: The message to reply to
            card: Card content dictionary
            card_type: Type identifier for the card
            context: Additional context to track with the card

        Returns:
            Message ID if successful, None otherwise
        """
        if not self.lark_client:
            logger.warning("(no client) Would reply card to %s", message_id)
            return None

        _rate_limiter.acquire()

        try:
            content = card_to_feishu_content(card)
            request = (
                ReplyMessageRequest.builder()
                .message_id(message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(content)
                    .msg_type("interactive")
                    .build()
                )
                .build()
            )
            resp = self.lark_client.im.v1.message.reply(request)
            if resp.success() and resp.data and resp.data.message_id:
                mid = resp.data.message_id
                if card_type:
                    self.card_tracker.register(mid, card_type, context or {})
                return mid
            else:
                logger.error("Card reply failed: %s", resp.msg)
                logger.warning("Falling back to text reply for card")
                self.reply_text(message_id, text_fallback(card))
                return None
        except Exception as exc:
            logger.error("Card reply error: %s", exc, exc_info=True)
            logger.warning("Falling back to text reply for card")
            try:
                self.reply_text(message_id, text_fallback(card))
            except Exception:
                pass
            return None

    def update_card(self, message_id: str, card: dict) -> bool:
        """Update an existing card message in-place.

        Args:
            message_id: The message ID to update
            card: New card content

        Returns:
            True if successful, False otherwise
        """
        if not self.lark_client:
            logger.warning("(no client) Would update card %s", message_id)
            return False

        _rate_limiter.acquire()

        try:
            content = card_to_feishu_content(card)
            request = (
                PatchMessageRequest.builder()
                .message_id(message_id)
                .request_body(
                    PatchMessageRequestBody.builder().content(content).build()
                )
                .build()
            )
            resp = self.lark_client.im.v1.message.patch(request)
            if not resp.success():
                logger.error("Card update failed: %s", resp.msg)
                return False
            return True
        except Exception as exc:
            logger.error("Card update error: %s", exc, exc_info=True)
            return False

    def get_card_context(self, message_id: str) -> Optional[dict]:
        """Get the tracked context for a card message."""
        info = self.card_tracker.get(message_id)
        return info.get("context") if info else None
