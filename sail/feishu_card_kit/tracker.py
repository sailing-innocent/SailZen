# -*- coding: utf-8 -*-
# @file tracker.py
# @brief Card message tracking and serialization utilities
# @author sailing-innocent
# @date 2026-04-26
# @version 1.0
# ---------------------------------
"""Card message tracking and serialization utilities.

Provides:
- CardMessageTracker: Track sent card metadata for later updates
- card_to_feishu_content: Serialize card dict to Feishu API format
- text_fallback: Extract plain text from card for fallback messaging
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class CardMessageTracker:
    """Track metadata for sent card messages.

    Useful when you need to update a previously sent card or
    look up cards by their context.
    """

    def __init__(self) -> None:
        self._map: Dict[str, Dict[str, Any]] = {}

    def register(
        self, message_id: str, card_type: str, context: Dict[str, Any]
    ) -> None:
        """Register a sent card message.

        Args:
            message_id: The Feishu message ID
            card_type: Type identifier (e.g. "progress", "result")
            context: Arbitrary context dict (e.g. {"op_id": "xxx", "path": "..."})
        """
        self._map[message_id] = {"card_type": card_type, "context": context}

    def get(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get tracked info for a message ID."""
        return self._map.get(message_id)

    def remove(self, message_id: str) -> None:
        """Remove a message from tracking."""
        self._map.pop(message_id, None)

    def find_by_context(self, card_type: str, key: str, value: Any) -> Optional[str]:
        """Find a message ID by card type and context key-value.

        Args:
            card_type: Card type to match
            key: Context dict key to match
            value: Context dict value to match

        Returns:
            Message ID if found, None otherwise
        """
        for mid, info in self._map.items():
            if (
                info.get("card_type") == card_type
                and info.get("context", {}).get(key) == value
            ):
                return mid
        return None

    def list_by_type(self, card_type: str) -> List[str]:
        """List all message IDs of a given card type."""
        return [
            mid for mid, info in self._map.items() if info.get("card_type") == card_type
        ]

    def clear(self) -> None:
        """Clear all tracked messages."""
        self._map.clear()

    def __len__(self) -> int:
        return len(self._map)


def card_to_feishu_content(card: Dict[str, Any]) -> str:
    """Serialize a card dict to JSON string for Feishu API.

    Args:
        card: Card dict from CardRenderer or custom builder

    Returns:
        JSON string ready to pass to Feishu message API
    """
    return json.dumps(card, ensure_ascii=False)


def text_fallback(card: Dict[str, Any]) -> str:
    """Extract plain-text fallback from a card dict.

    When interactive card API fails, use this to send a text
    message containing the same information.

    Args:
        card: Card dict

    Returns:
        Plain text representation of the card content
    """
    lines: List[str] = []
    header = card.get("header", {})
    title_obj = header.get("title", {})
    title = title_obj.get("content", "") if isinstance(title_obj, dict) else ""
    if title:
        lines.append(title)
        lines.append("=" * min(len(title), 40))

    for el in card.get("elements", []):
        tag = el.get("tag", "")
        if tag == "div":
            text_obj = el.get("text", {})
            if isinstance(text_obj, dict):
                content = text_obj.get("content", "").replace("**", "")
                if content:
                    lines.append(content)
            for f in el.get("fields", []):
                field_text = f.get("text", {})
                if isinstance(field_text, dict):
                    c = field_text.get("content", "").replace("**", "")
                    if c:
                        lines.append(c)
        elif tag == "note":
            for ne in el.get("elements", []):
                c = ne.get("content", "")
                if c:
                    lines.append(f"[{c}]")
        elif tag == "hr":
            lines.append("-" * 20)

    return "\n".join(lines)
