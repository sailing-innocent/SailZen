# -*- coding: utf-8 -*-
# @file webhook.py
# @brief Feishu webhook handler
# @author sailing-innocent
# @date 2026-03-21
# @version 1.0
# ---------------------------------
"""Handle Feishu webhook events."""

import json
import hashlib
import base64
import hmac
import time
from typing import Dict, Any, Optional
from litestar import Controller, post
from litestar.response import Response
from .message_handler import MessageHandler


class FeishuWebhookHandler(Controller):
    """Handle Feishu bot webhook events."""

    path = "/feishu"

    def __init__(self) -> None:
        self.message_handler = MessageHandler()
        # TODO: Load from environment variable
        self.encrypt_key = ""
        self.verification_token = ""

    @post("/webhook")
    async def handle_webhook(self, data: Dict[str, Any]) -> Response:
        """Handle incoming Feishu webhook events."""
        try:
            # Extract event data
            event_type = data.get("header", {}).get("event_type")

            if event_type == "im.message.receive_v1":
                # Handle message event
                await self._handle_message(data.get("event", {}))

            # Return success to acknowledge receipt
            return Response(content={"code": 0, "msg": "success"}, status_code=200)

        except Exception as e:
            print(f"Error handling webhook: {e}")
            return Response(content={"code": -1, "msg": str(e)}, status_code=500)

    async def _handle_message(self, event: Dict[str, Any]) -> None:
        """Process message received event."""
        message = event.get("message", {})
        sender = event.get("sender", {})

        # Extract message info
        content = json.loads(message.get("content", "{}"))
        text = content.get("text", "")
        chat_type = message.get("chat_type")
        mentions = message.get("mentions", [])

        # Get sender info
        sender_id = sender.get("sender_id", {}).get("open_id")

        # For group chats, only respond if bot is mentioned
        if chat_type == "group" and not mentions:
            return

        # Parse and execute command
        result = await self.message_handler.handle_command(
            text=text, sender_id=sender_id, chat_type=chat_type
        )

        # Send response back to Feishu
        await self._send_response(message.get("message_id"), result)

    async def _send_response(self, message_id: str, result: Dict[str, Any]) -> None:
        """Send response message to Feishu."""
        # TODO: Implement actual Feishu API call
        print(f"[Feishu Response] Message ID: {message_id}")
        print(f"[Feishu Response] Content: {result}")

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
