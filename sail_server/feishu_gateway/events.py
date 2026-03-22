# -*- coding: utf-8 -*-
# @file events.py
# @brief Normalized Feishu event types for unified handling
# @author sailing-innocent
# @date 2026-03-22
# @version 1.0
# ---------------------------------
"""Normalized event types for Feishu interaction pipeline.

This module defines standardized event envelopes that abstract away
Feishu-specific message formats into a clean domain model for the
remote control system.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum, auto
from datetime import datetime
import re


class EventType(Enum):
    """Types of normalized Feishu events."""

    TEXT = auto()
    VOICE = auto()
    MENTION = auto()
    CARD_ACTION = auto()
    SYSTEM = auto()


class IntentCategory(Enum):
    """Categories of user intent derived from events."""

    SESSION_CONTROL = auto()  # start, stop, restart, recover
    CODE_REQUEST = auto()  # code generation, refactoring
    MONITORING = auto()  # status, logs, health
    RECOVERY = auto()  # retry, resume, rollback
    NAVIGATION = auto()  # list, select, help
    UNKNOWN = auto()


@dataclass
class SenderInfo:
    """Information about the message sender."""

    open_id: str
    name: Optional[str] = None
    email: Optional[str] = None

    @classmethod
    def from_feishu(cls, sender_data: Dict[str, Any]) -> "SenderInfo":
        """Extract sender info from Feishu event data."""
        return cls(
            open_id=sender_data.get("sender_id", {}).get("open_id", ""),
            name=sender_data.get("name", ""),
            email=sender_data.get("email", None),
        )


@dataclass
class MentionInfo:
    """Information about a mention in a message."""

    user_id: str
    name: str
    offset: int = 0
    length: int = 0


@dataclass
class NormalizedEvent:
    """Base class for all normalized Feishu events.

    This provides a consistent interface regardless of the underlying
    Feishu message format (text, voice, card actions, etc.)
    """

    event_id: str
    event_type: EventType
    timestamp: datetime
    sender: SenderInfo
    chat_type: str  # "p2p" or "group"
    chat_id: str
    raw_payload: Dict[str, Any] = field(repr=False)

    # Normalization metadata
    idempotency_key: Optional[str] = None
    processed_at: Optional[datetime] = None


@dataclass
class TextEvent(NormalizedEvent):
    """Normalized text message event."""

    text: str = ""
    text_normalized: str = ""  # Cleaned text (mentions removed, etc.)
    mentions: List[MentionInfo] = field(default_factory=list)
    is_voice_input: bool = False  # Flag for speech-to-text derived text

    @property
    def has_mentions(self) -> bool:
        return len(self.mentions) > 0

    @property
    def is_slash_command(self) -> bool:
        return self.text_normalized.strip().startswith("/")


@dataclass
class VoiceEvent(NormalizedEvent):
    """Normalized voice message event.

    Note: For MVP-2, we assume voice is transcribed by the user's
    speech-to-text input method and arrives as text. This type
    exists for future native voice support.
    """

    voice_file_key: Optional[str] = None
    duration_ms: int = 0
    # If transcribed by Feishu
    transcribed_text: Optional[str] = None


@dataclass
class MentionEvent(NormalizedEvent):
    """Specific event type for bot mentions in group chats."""

    text: str = ""
    text_without_mentions: str = ""
    mention_positions: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_direct_mention(self) -> bool:
        """Check if the bot is the only/primary mention."""
        return len(self.mention_positions) > 0


@dataclass
class CardActionEvent(NormalizedEvent):
    """Normalized card interaction callback event."""

    action_value: Dict[str, Any] = field(default_factory=dict)
    action_tag: str = ""
    card_id: Optional[str] = None
    original_message_id: Optional[str] = None

    # Structured action intent extracted from card
    intent_type: Optional[str] = None
    target_workspace: Optional[str] = None
    target_session: Optional[str] = None
    action_parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemEvent(NormalizedEvent):
    """System-level events (bot added/removed, etc.)."""

    system_event_type: str = ""
    system_data: Dict[str, Any] = field(default_factory=dict)


# Union type for all event types
FeishuEvent = TextEvent | VoiceEvent | MentionEvent | CardActionEvent | SystemEvent


def normalize_feishu_event(raw_event: Dict[str, Any]) -> FeishuEvent:
    """Normalize a raw Feishu webhook event into a domain event.

    This is the main entry point for converting Feishu-specific
    message formats into normalized events.

    Args:
        raw_event: The raw event data from Feishu webhook

    Returns:
        A normalized event of the appropriate type
    """
    header = raw_event.get("header", {})
    event_type = header.get("event_type")
    event_data = raw_event.get("event", {})

    # Extract common fields
    event_id = header.get("event_id", "")
    timestamp = datetime.fromtimestamp(int(header.get("create_time", 0)) / 1000)
    sender = SenderInfo.from_feishu(event_data.get("sender", {}))
    chat_type = event_data.get("message", {}).get("chat_type", "p2p")
    chat_id = event_data.get("message", {}).get("chat_id", "")

    # Generate idempotency key from event_id
    idempotency_key = f"feishu:{event_id}"

    # Route to specific normalizer based on event type
    if event_type == "im.message.receive_v1":
        return _normalize_message_event(
            event_data, event_id, timestamp, sender, chat_type, chat_id, raw_event
        )
    elif event_type == "card.action.trigger":
        return _normalize_card_action(
            event_data, event_id, timestamp, sender, chat_type, chat_id, raw_event
        )
    elif event_type and event_type.startswith("im.chat"):
        return _normalize_system_event(
            event_data,
            event_id,
            timestamp,
            sender,
            chat_type,
            chat_id,
            raw_event,
            event_type,
        )
    else:
        # Unknown event type, create generic system event
        return SystemEvent(
            event_id=event_id,
            event_type=EventType.SYSTEM,
            timestamp=timestamp,
            sender=sender,
            chat_type=chat_type,
            chat_id=chat_id,
            raw_payload=raw_event,
            idempotency_key=idempotency_key,
            system_event_type=event_type or "unknown",
            system_data=event_data,
        )


def _normalize_message_event(
    event_data: Dict[str, Any],
    event_id: str,
    timestamp: datetime,
    sender: SenderInfo,
    chat_type: str,
    chat_id: str,
    raw_event: Dict[str, Any],
) -> FeishuEvent:
    """Normalize an incoming message event."""
    import json
    import re

    message = event_data.get("message", {})
    msg_type = message.get("msg_type", "text")
    mentions_raw = message.get("mentions", [])
    content = json.loads(message.get("content", "{}"))

    idempotency_key = f"feishu:{event_id}"

    # Extract mentions
    mentions = []
    for m in mentions_raw:
        mentions.append(
            MentionInfo(
                user_id=m.get("id", {}).get("open_id", ""),
                name=m.get("name", ""),
                offset=m.get("offset", 0),
                length=m.get("length", 0),
            )
        )

    # Handle text messages (includes speech-to-text derived text)
    if msg_type == "text":
        text = content.get("text", "")

        # Remove @mentions from text
        text_normalized = re.sub(r"@_user_\d+", "", text).strip()
        text_normalized = re.sub(r"\s+", " ", text_normalized).strip()

        # Detect if this might be voice input (long text with certain patterns)
        is_voice = _detect_voice_input(text_normalized)

        # Check if this is primarily a mention event
        if chat_type == "group" and mentions:
            return MentionEvent(
                event_id=event_id,
                event_type=EventType.MENTION,
                timestamp=timestamp,
                sender=sender,
                chat_type=chat_type,
                chat_id=chat_id,
                raw_payload=raw_event,
                idempotency_key=idempotency_key,
                text=text,
                text_without_mentions=text_normalized,
                mention_positions=[
                    {"user_id": m.user_id, "name": m.name} for m in mentions
                ],
            )

        return TextEvent(
            event_id=event_id,
            event_type=EventType.TEXT,
            timestamp=timestamp,
            sender=sender,
            chat_type=chat_type,
            chat_id=chat_id,
            raw_payload=raw_event,
            idempotency_key=idempotency_key,
            text=text,
            text_normalized=text_normalized,
            mentions=mentions,
            is_voice_input=is_voice,
        )

    # Handle audio/voice messages (native Feishu voice)
    elif msg_type in ["audio", "voice"]:
        return VoiceEvent(
            event_id=event_id,
            event_type=EventType.VOICE,
            timestamp=timestamp,
            sender=sender,
            chat_type=chat_type,
            chat_id=chat_id,
            raw_payload=raw_event,
            idempotency_key=idempotency_key,
            voice_file_key=content.get("file_key"),
            duration_ms=content.get("duration", 0),
            transcribed_text=content.get("text"),  # If Feishu transcribed it
        )

    # Default to text for unknown types
    else:
        return TextEvent(
            event_id=event_id,
            event_type=EventType.TEXT,
            timestamp=timestamp,
            sender=sender,
            chat_type=chat_type,
            chat_id=chat_id,
            raw_payload=raw_event,
            idempotency_key=idempotency_key,
            text=str(content),
            text_normalized=str(content),
            mentions=mentions,
            is_voice_input=False,
        )


def _normalize_card_action(
    event_data: Dict[str, Any],
    event_id: str,
    timestamp: datetime,
    sender: SenderInfo,
    chat_type: str,
    chat_id: str,
    raw_event: Dict[str, Any],
) -> CardActionEvent:
    """Normalize a card action callback event."""
    action = event_data.get("action", {})
    card = event_data.get("card", {})
    context = event_data.get("context", {})

    action_value = action.get("value", {})

    return CardActionEvent(
        event_id=event_id,
        event_type=EventType.CARD_ACTION,
        timestamp=timestamp,
        sender=sender,
        chat_type=chat_type,
        chat_id=chat_id,
        raw_payload=raw_event,
        idempotency_key=f"feishu:{event_id}",
        action_value=action_value,
        action_tag=action.get("tag", ""),
        card_id=card.get("id"),
        original_message_id=context.get("open_message_id"),
        intent_type=action_value.get("intent"),
        target_workspace=action_value.get("workspace"),
        target_session=action_value.get("session"),
        action_parameters=action_value.get("params", {}),
    )


def _normalize_system_event(
    event_data: Dict[str, Any],
    event_id: str,
    timestamp: datetime,
    sender: SenderInfo,
    chat_type: str,
    chat_id: str,
    raw_event: Dict[str, Any],
    system_type: str,
) -> SystemEvent:
    """Normalize system-level events."""
    return SystemEvent(
        event_id=event_id,
        event_type=EventType.SYSTEM,
        timestamp=timestamp,
        sender=sender,
        chat_type=chat_type,
        chat_id=chat_id,
        raw_payload=raw_event,
        idempotency_key=f"feishu:{event_id}",
        system_event_type=system_type,
        system_data=event_data,
    )


def _detect_voice_input(text: str) -> bool:
    """Detect if text likely came from speech-to-text input.

    Heuristics include:
    - Long text (>100 chars)
    - Filler words and patterns
    - Repeated phrases
    - Imperfect punctuation
    """
    if len(text) < 50:
        return False

    # Common speech-to-text patterns
    speech_patterns = [
        r"[，。]+[，。]+",  # Repeated punctuation
        r"(那个|这个|然后|就是|嗯|啊)\s*",  # Filler words
        r"\b(\w+)\s+\1\b",  # Repeated words
    ]

    for pattern in speech_patterns:
        if re.search(pattern, text):
            return True

    # Long text is more likely voice input
    if len(text) > 150:
        return True

    return False
