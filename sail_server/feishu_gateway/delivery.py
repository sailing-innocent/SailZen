# -*- coding: utf-8 -*-
# @file delivery.py
# @brief Feishu outbound delivery adapters
# @author sailing-innocent
# @date 2026-03-22
# @version 1.0
# ---------------------------------
"""Outbound delivery adapters for Feishu API interactions.

This module provides adapters for sending messages back to Feishu,
including text replies, card creation, card updates, and confirmation
flows with retry and deduplication support.
"""

import json
import time
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
import hashlib


class DeliveryStatus(Enum):
    """Status of a delivery attempt."""

    PENDING = auto()
    DELIVERED = auto()
    FAILED = auto()
    RETRYING = auto()
    EXPIRED = auto()


@dataclass
class DeliveryRecord:
    """Record of a delivery attempt for deduplication and retry tracking."""

    message_id: str
    delivery_id: str
    content_hash: str
    status: DeliveryStatus
    created_at: datetime
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    error_message: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if delivery record has expired (24 hours)."""
        return datetime.now() - self.created_at > timedelta(hours=24)


class FeishuDeliveryAdapter:
    """Adapter for delivering messages to Feishu.

    Provides:
    - Text message delivery
    - Interactive card creation and updates
    - Confirmation flow support
    - Automatic retry with exponential backoff
    - Deduplication to prevent duplicate messages
    """

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        max_retries: int = 3,
        retry_delay_base: float = 1.0,
        enable_deduplication: bool = True,
    ):
        """Initialize the delivery adapter.

        Args:
            app_id: Feishu app ID (optional, can be loaded from env)
            app_secret: Feishu app secret (optional, can be loaded from env)
            max_retries: Maximum number of delivery retries
            retry_delay_base: Base delay for exponential backoff
            enable_deduplication: Whether to deduplicate messages
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self.enable_deduplication = enable_deduplication

        # In-memory delivery tracking (should be Redis in production)
        self._delivery_records: Dict[str, DeliveryRecord] = {}
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def _generate_delivery_id(self, message_id: str, content: Dict[str, Any]) -> str:
        """Generate a unique delivery ID for deduplication."""
        content_str = json.dumps(content, sort_keys=True)
        content_hash = hashlib.md5(content_str.encode()).hexdigest()[:16]
        return f"{message_id}:{content_hash}"

    def _check_duplicate(self, delivery_id: str) -> bool:
        """Check if message has already been delivered (idempotency check)."""
        if not self.enable_deduplication:
            return False

        record = self._delivery_records.get(delivery_id)
        if not record:
            return False

        # Check if expired
        if record.is_expired:
            del self._delivery_records[delivery_id]
            return False

        # Already delivered or in progress
        return record.status in [DeliveryStatus.DELIVERED, DeliveryStatus.PENDING]

    async def _get_access_token(self) -> Optional[str]:
        """Get or refresh Feishu access token.

        TODO: Implement actual Feishu API call
        """
        if (
            self._access_token
            and self._token_expires_at
            and datetime.now() < self._token_expires_at
        ):
            return self._access_token

        # TODO: Call Feishu auth API to get token
        # For MVP-2, return None (adapter will work in mock mode)
        return None

    async def _make_api_call(
        self, endpoint: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make an API call to Feishu.

        TODO: Implement actual HTTP calls to Feishu API
        For MVP-2, this logs the call and returns mock success.
        """
        token = await self._get_access_token()

        print(f"[Feishu API] {endpoint}")
        print(
            f"[Feishu API] Payload: {json.dumps(payload, ensure_ascii=False, indent=2)[:200]}"
        )

        # Mock successful response for MVP-2
        return {"code": 0, "msg": "ok", "data": {}}

    async def send_text_reply(
        self,
        receive_id: str,
        text: str,
        reply_to_message_id: Optional[str] = None,
        receive_id_type: str = "open_id",
    ) -> Dict[str, Any]:
        """Send a text reply message.

        Args:
            receive_id: User or chat ID to send to
            text: Text content
            reply_to_message_id: Optional message ID to reply to
            receive_id_type: Type of ID (open_id, chat_id, etc.)

        Returns:
            Response from Feishu API
        """
        delivery_id = self._generate_delivery_id(
            reply_to_message_id or receive_id, {"type": "text", "content": text}
        )

        if self._check_duplicate(delivery_id):
            print(f"[Feishu Delivery] Duplicate suppressed: {delivery_id}")
            return {"code": 0, "msg": "duplicate suppressed"}

        content = json.dumps({"text": text})

        payload: Dict[str, Any] = {
            "receive_id": receive_id,
            "content": content,
            "msg_type": "text",
        }

        if reply_to_message_id:
            payload["reply_in_thread"] = True
            # For reply, we might need a different endpoint

        return await self._deliver_with_retry(
            delivery_id=delivery_id,
            endpoint="/open-apis/im/v1/messages",
            payload=payload,
        )

    async def send_card(
        self,
        receive_id: str,
        card_data: Dict[str, Any],
        receive_id_type: str = "open_id",
    ) -> Dict[str, Any]:
        """Send an interactive card message.

        Args:
            receive_id: User or chat ID to send to
            card_data: Card JSON data
            receive_id_type: Type of ID

        Returns:
            Response with message_id for future updates
        """
        delivery_id = self._generate_delivery_id(
            receive_id, {"type": "card", "card": card_data}
        )

        if self._check_duplicate(delivery_id):
            print(f"[Feishu Delivery] Duplicate suppressed: {delivery_id}")
            return {"code": 0, "msg": "duplicate suppressed"}

        content = json.dumps(card_data)

        payload = {
            "receive_id": receive_id,
            "content": content,
            "msg_type": "interactive",
        }

        return await self._deliver_with_retry(
            delivery_id=delivery_id,
            endpoint="/open-apis/im/v1/messages",
            payload=payload,
        )

    async def update_card(
        self, message_id: str, card_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing interactive card.

        Args:
            message_id: ID of the message to update
            card_data: New card JSON data

        Returns:
            Response from Feishu API
        """
        delivery_id = f"update:{message_id}"

        payload = {"content": json.dumps(card_data)}

        return await self._deliver_with_retry(
            delivery_id=delivery_id,
            endpoint=f"/open-apis/im/v1/messages/{message_id}",
            payload=payload,
        )

    async def send_confirmation_card(
        self,
        receive_id: str,
        title: str,
        description: str,
        action_payload: Dict[str, Any],
        timeout_seconds: int = 300,
        receive_id_type: str = "open_id",
    ) -> Dict[str, Any]:
        """Send a confirmation card requiring user action.

        Args:
            receive_id: User to send to
            title: Confirmation title
            description: Description of what needs confirmation
            action_payload: Data to include in callback when confirmed
            timeout_seconds: Timeout for confirmation
            receive_id_type: Type of ID

        Returns:
            Response with message_id
        """
        card_data = self._build_confirmation_card(
            title=title,
            description=description,
            action_payload=action_payload,
            timeout_seconds=timeout_seconds,
        )

        return await self.send_card(
            receive_id=receive_id, card_data=card_data, receive_id_type=receive_id_type
        )

    def _build_confirmation_card(
        self,
        title: str,
        description: str,
        action_payload: Dict[str, Any],
        timeout_seconds: int,
    ) -> Dict[str, Any]:
        """Build a confirmation card structure."""
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"⚠️ {title}"},
                "template": "red",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": description}},
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✅ 确认执行"},
                            "type": "primary",
                            "value": {**action_payload, "confirm_action": "confirm"},
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 取消"},
                            "type": "default",
                            "value": {**action_payload, "confirm_action": "cancel"},
                        },
                    ],
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"⏰ 此确认将在 {timeout_seconds // 60} 分钟后过期",
                        }
                    ],
                },
            ],
        }

    async def _deliver_with_retry(
        self, delivery_id: str, endpoint: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deliver a message with automatic retry.

        Implements exponential backoff for transient failures.
        """
        # Create or get delivery record
        if delivery_id not in self._delivery_records:
            self._delivery_records[delivery_id] = DeliveryRecord(
                message_id=payload.get("receive_id", "unknown"),
                delivery_id=delivery_id,
                content_hash=hashlib.md5(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest()[:16],
                status=DeliveryStatus.PENDING,
                created_at=datetime.now(),
            )

        record = self._delivery_records[delivery_id]

        for attempt in range(self.max_retries):
            try:
                record.attempts += 1
                record.last_attempt = datetime.now()
                record.status = (
                    DeliveryStatus.RETRYING if attempt > 0 else DeliveryStatus.PENDING
                )

                response = await self._make_api_call(endpoint, payload)

                if response.get("code") == 0:
                    record.status = DeliveryStatus.DELIVERED
                    return response
                else:
                    # API returned error
                    record.error_message = response.get("msg", "Unknown error")

                    # Check if we should retry
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay_base * (2**attempt)
                        print(
                            f"[Feishu Delivery] Attempt {attempt + 1} failed, retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        record.status = DeliveryStatus.FAILED
                        return response

            except Exception as e:
                record.error_message = str(e)

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay_base * (2**attempt)
                    print(f"[Feishu Delivery] Exception on attempt {attempt + 1}: {e}")
                    await asyncio.sleep(delay)
                else:
                    record.status = DeliveryStatus.FAILED
                    return {
                        "code": -1,
                        "msg": f"Delivery failed after {self.max_retries} attempts: {e}",
                    }

        return {"code": -1, "msg": "Max retries exceeded"}

    async def cleanup_expired_records(self) -> int:
        """Clean up expired delivery records.

        Returns:
            Number of records removed
        """
        expired_ids = [
            delivery_id
            for delivery_id, record in self._delivery_records.items()
            if record.is_expired
        ]

        for delivery_id in expired_ids:
            del self._delivery_records[delivery_id]

        return len(expired_ids)

    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get statistics about delivery attempts."""
        stats = {
            "total": len(self._delivery_records),
            "pending": 0,
            "delivered": 0,
            "failed": 0,
            "retrying": 0,
        }

        for record in self._delivery_records.values():
            status_name = record.status.name.lower()
            if status_name in stats:
                stats[status_name] += 1

        return stats


# Global adapter instance (singleton pattern)
_delivery_adapter: Optional[FeishuDeliveryAdapter] = None


def get_delivery_adapter() -> FeishuDeliveryAdapter:
    """Get or create the global delivery adapter instance."""
    global _delivery_adapter
    if _delivery_adapter is None:
        _delivery_adapter = FeishuDeliveryAdapter()
    return _delivery_adapter


def configure_delivery_adapter(
    app_id: Optional[str] = None, app_secret: Optional[str] = None, **kwargs
) -> FeishuDeliveryAdapter:
    """Configure the global delivery adapter."""
    global _delivery_adapter
    _delivery_adapter = FeishuDeliveryAdapter(
        app_id=app_id, app_secret=app_secret, **kwargs
    )
    return _delivery_adapter
