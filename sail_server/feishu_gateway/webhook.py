# -*- coding: utf-8 -*-
# @file webhook.py
# @brief Feishu webhook handler with normalized event processing
# @author sailing-innocent
# @date 2026-03-22
# @version 2.0
# ---------------------------------
"""Handle Feishu webhook events using normalized event types.

This module provides the webhook entry point that normalizes incoming
Feishu events and routes them through the interaction pipeline.
"""

import hashlib
import base64
import hmac
from typing import Dict, Any, Optional
from datetime import datetime
from litestar import Controller, Router, post
from litestar.response import Response

from .events import (
    normalize_feishu_event,
    FeishuEvent,
    TextEvent,
    VoiceEvent,
    MentionEvent,
    CardActionEvent,
    SystemEvent,
    EventType,
)
from .message_handler import MessageHandler


class FeishuWebhookHandler(Controller):
    """Handle Feishu bot webhook events with normalized event processing."""

    path = "/feishu"

    def __init__(self, owner: Router | None = None) -> None:
        super().__init__(owner=owner)
        self.message_handler = MessageHandler()
        # TODO: Load from environment variable
        self.encrypt_key = ""
        self.verification_token = ""

    @post("/webhook")
    async def handle_webhook(self, data: Dict[str, Any]) -> Response:
        """Handle incoming Feishu webhook events.

        All events are normalized into domain event types before processing.
        """
        try:
            # Normalize the raw Feishu event
            normalized_event = normalize_feishu_event(data)

            # Process the normalized event
            await self._handle_normalized_event(normalized_event)

            # Return success to acknowledge receipt
            return Response(content={"code": 0, "msg": "success"}, status_code=200)

        except Exception as e:
            # Log error but still return success to prevent Feishu retries
            # for unrecoverable errors
            print(f"Error handling webhook: {e}")
            import traceback

            traceback.print_exc()
            return Response(content={"code": 0, "msg": "processed"}, status_code=200)

    async def _handle_normalized_event(self, event: FeishuEvent) -> None:
        """Route normalized events to appropriate handlers.

        This is the central event routing logic that dispatches different
        event types to their respective handlers.
        """
        # Record processing time
        event.processed_at = datetime.now()

        if isinstance(event, TextEvent):
            await self._handle_text_event(event)
        elif isinstance(event, VoiceEvent):
            await self._handle_voice_event(event)
        elif isinstance(event, MentionEvent):
            await self._handle_mention_event(event)
        elif isinstance(event, CardActionEvent):
            await self._handle_card_action_event(event)
        elif isinstance(event, SystemEvent):
            await self._handle_system_event(event)
        else:
            print(f"[Feishu Gateway] Unknown event type: {type(event)}")

    async def _handle_text_event(self, event: TextEvent) -> None:
        """Handle normalized text message events.

        Text events include both direct messages and group messages
        (when the bot is mentioned). Voice-derived text is flagged
        for special normalization handling.
        """
        print(f"[Feishu Gateway] Text event from {event.sender.open_id}")
        print(f"  - Chat type: {event.chat_type}")
        print(f"  - Voice input: {event.is_voice_input}")
        print(f"  - Text: {event.text_normalized[:50]}...")

        # Pass to message handler with full event context
        result = await self.message_handler.handle_text_event(event)

        # Send response if provided
        if result:
            await self._send_response(
                event.raw_payload.get("message", {}).get("message_id"), result
            )

    async def _handle_voice_event(self, event: VoiceEvent) -> None:
        """Handle voice message events.

        Note: For MVP-2, voice processing assumes text is transcribed
        by the user's speech-to-text input method. Native voice support
        is a future enhancement.
        """
        print(f"[Feishu Gateway] Voice event from {event.sender.open_id}")
        print(f"  - Duration: {event.duration_ms}ms")
        print(f"  - Transcribed: {event.transcribed_text is not None}")

        # For MVP-2, treat voice with transcription as text
        if event.transcribed_text:
            # Convert to text event for processing
            text_event = TextEvent(
                event_id=event.event_id,
                event_type=EventType.TEXT,
                timestamp=event.timestamp,
                sender=event.sender,
                chat_type=event.chat_type,
                chat_id=event.chat_id,
                raw_payload=event.raw_payload,
                idempotency_key=event.idempotency_key,
                text=event.transcribed_text,
                text_normalized=event.transcribed_text,
                mentions=[],
                is_voice_input=True,  # Flag as voice-derived
            )
            await self._handle_text_event(text_event)
        else:
            # No transcription available
            await self._send_response(
                event.raw_payload.get("message", {}).get("message_id"),
                {
                    "type": "text",
                    "content": "🎤 收到语音消息，但暂不支持语音转文字。"
                    "请使用文字输入或手机的语音转文字功能。",
                },
            )

    async def _handle_mention_event(self, event: MentionEvent) -> None:
        """Handle bot mention events in group chats.

        Mentions are treated similarly to text events but with
        additional context about the mention.
        """
        print(f"[Feishu Gateway] Mention event from {event.sender.open_id}")
        print(f"  - Chat: {event.chat_id}")

        # Convert to text event for processing
        text_event = TextEvent(
            event_id=event.event_id,
            event_type=EventType.TEXT,
            timestamp=event.timestamp,
            sender=event.sender,
            chat_type=event.chat_type,
            chat_id=event.chat_id,
            raw_payload=event.raw_payload,
            idempotency_key=event.idempotency_key,
            text=event.text,
            text_normalized=event.text_without_mentions,
            mentions=[],  # Already processed
            is_voice_input=False,
        )
        await self._handle_text_event(text_event)

    async def _handle_card_action_event(self, event: CardActionEvent) -> None:
        """Handle card action callback events.

        Card actions represent structured user interactions like
        button clicks, form submissions, or quick actions.
        """
        print(f"[Feishu Gateway] Card action from {event.sender.open_id}")
        print(f"  - Action: {event.action_tag}")
        print(f"  - Intent: {event.intent_type}")
        print(f"  - Target: {event.target_workspace}/{event.target_session}")

        # Pass structured action to message handler
        result = await self.message_handler.handle_card_action_event(event)

        if result:
            await self._send_response(
                event.raw_payload.get("context", {}).get("open_message_id"), result
            )

    async def _handle_system_event(self, event: SystemEvent) -> None:
        """Handle system-level events.

        System events include bot added/removed from chats,
        configuration changes, etc.
        """
        print(f"[Feishu Gateway] System event: {event.system_event_type}")
        # TODO: Handle bot lifecycle events, admin notifications, etc.
        pass

    async def _send_response(
        self, message_id: Optional[str], result: Dict[str, Any]
    ) -> None:
        """Send response message to Feishu.

        TODO: Implement actual Feishu API integration
        """
        if not message_id:
            print(f"[Feishu Response] No message ID, cannot reply")
            return

        print(f"[Feishu Response] Message ID: {message_id}")
        print(f"[Feishu Response] Type: {result.get('type')}")
        content = result.get("content", "")
        if isinstance(content, str) and len(content) > 100:
            print(f"[Feishu Response] Content: {content[:100]}...")
        else:
            print(f"[Feishu Response] Content: {content}")

    def _verify_signature(
        self, signature: str, timestamp: str, nonce: str, body: str
    ) -> bool:
        """Verify Feishu webhook signature."""
        if not self.encrypt_key:
            return True  # Skip verification if no key set

        bytes_to_sign = f"{timestamp}{nonce}{self.encrypt_key}{body}".encode("utf-8")
        expected_signature = base64.b64encode(
            hmac.new(self.encrypt_key.encode(), bytes_to_sign, hashlib.sha256).digest()
        ).decode()

        return signature == expected_signature
