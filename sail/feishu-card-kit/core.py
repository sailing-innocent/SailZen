# -*- coding: utf-8 -*-
# @file core.py
# @brief Low-level building blocks for Feishu interactive cards
# @author sailing-innocent
# @date 2026-04-26
# @version 1.0
# ---------------------------------
"""Low-level building blocks for Feishu interactive cards.

This module provides the atomic components used to construct any Feishu card.
All functions return plain Python dicts that conform to Feishu's card JSON schema.

Zero external dependencies — only Python standard library.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CardColor(str, Enum):
    """Feishu card header template colors."""

    GREEN = "green"
    RED = "red"
    BLUE = "blue"
    YELLOW = "yellow"
    GREY = "grey"
    ORANGE = "orange"


class ButtonStyle(str, Enum):
    """Feishu button styles."""

    DEFAULT = "default"
    PRIMARY = "primary"
    DANGER = "danger"


# ---------------------------------------------------------------------------
# State mappings (commonly used)
# ---------------------------------------------------------------------------

_STATE_COLORS: Dict[str, CardColor] = {
    "idle": CardColor.GREY,
    "starting": CardColor.BLUE,
    "running": CardColor.GREEN,
    "stopping": CardColor.YELLOW,
    "error": CardColor.RED,
}

_STATE_ICONS: Dict[str, str] = {
    "idle": "⬜",
    "starting": "🔄",
    "running": "🟢",
    "stopping": "🟡",
    "error": "🔴",
}

_STATE_LABELS: Dict[str, str] = {
    "idle": "空闲",
    "starting": "启动中",
    "running": "运行中",
    "stopping": "停止中",
    "error": "出错",
}


# ---------------------------------------------------------------------------
# Atomic builders
# ---------------------------------------------------------------------------


def header(title: str, color: CardColor = CardColor.BLUE) -> Dict[str, Any]:
    """Create a card header.

    Args:
        title: Header text content
        color: Header color template

    Returns:
        Header dict conforming to Feishu card schema
    """
    return {
        "title": {"tag": "plain_text", "content": title},
        "template": color.value,
    }


def divider() -> Dict[str, Any]:
    """Create a horizontal divider element."""
    return {"tag": "hr"}


def text(content: str, bold: bool = False) -> Dict[str, Any]:
    """Create a text div element.

    Args:
        content: Text content (supports Lark Markdown syntax)
        bold: Whether to wrap content in bold markers
    """
    return {
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"**{content}**" if bold else content,
        },
    }


def note(content: str) -> Dict[str, Any]:
    """Create a note element (gray hint text).

    Args:
        content: Note text content
    """
    return {
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": content}],
    }


def section(title: str, content: str) -> Dict[str, Any]:
    """Create a section with title and content.

    Args:
        title: Section title (bold)
        content: Section body text (supports Lark Markdown)
    """
    return {
        "tag": "div",
        "elements": [
            {"tag": "plain_text", "content": f"**{title}**"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": content},
            },
        ],
    }


def button(
    label: str,
    action_type: str = "callback",
    value: Optional[Dict[str, Any]] = None,
    style: ButtonStyle | str = ButtonStyle.DEFAULT,
) -> Dict[str, Any]:
    """Create a button element.

    Args:
        label: Button display text
        action_type: "callback", "link", or "form_action"
        value: Payload dict (for callback) or {"url": "..."} (for link)
        style: Button visual style

    Returns:
        Button element dict
    """
    value = value or {}
    if action_type == "callback":
        behaviors = [{"type": "callback", "value": value}]
    elif action_type == "link":
        behaviors = [{"type": "open_url", "default_url": value.get("url", "")}]
    else:
        behaviors = [{"type": "callback", "value": value}]

    style_val = style.value if isinstance(style, ButtonStyle) else style

    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": label},
        "type": style_val,
        "behaviors": behaviors,
    }


def action_row(buttons: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create an action row containing buttons.

    Note: Mobile-optimized — never more than 2 buttons per row for
    adequate touch targets.

    Args:
        buttons: List of button element dicts
    """
    return {"tag": "action", "actions": buttons[:2]}


def field_row(pairs: List[tuple]) -> Dict[str, Any]:
    """Create a field row with label-value pairs.

    Args:
        pairs: List of (label, value) tuples
    """
    fields = [
        {
            "is_short": True,
            "text": {
                "tag": "lark_md",
                "content": f"**{str(label)}**\n{str(val)}",
            },
        }
        for label, val in pairs
    ]
    return {"tag": "div", "fields": fields}


# ---------------------------------------------------------------------------
# Card assembly
# ---------------------------------------------------------------------------


def card(
    elements: List[Dict[str, Any]],
    title: str = "",
    color: CardColor = CardColor.BLUE,
    wide_screen: bool = True,
) -> Dict[str, Any]:
    """Assemble a complete Feishu card from elements.

    Args:
        elements: List of card element dicts
        title: Optional header title
        color: Header color (only used if title is provided)
        wide_screen: Whether to enable wide screen mode

    Returns:
        Complete card dict ready to send to Feishu
    """
    result: Dict[str, Any] = {
        "config": {"wide_screen_mode": wide_screen},
        "elements": elements,
    }
    if title:
        result["header"] = header(title, color)
    return result


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def get_state_color(state: str) -> CardColor:
    """Get the color associated with a state string."""
    return _STATE_COLORS.get(state, CardColor.GREY)


def get_state_icon(state: str) -> str:
    """Get the icon associated with a state string."""
    return _STATE_ICONS.get(state, "⬜")


def get_state_label(state: str) -> str:
    """Get the human-readable label for a state string."""
    return _STATE_LABELS.get(state, state)
