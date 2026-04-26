# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Feishu Card Kit — Zero-dependency toolkit for Feishu interactive cards
# @author sailing-innocent
# @date 2026-04-26
# @version 1.0.0
# ---------------------------------
"""Feishu Card Kit — A zero-dependency Python toolkit for building Feishu (Lark) interactive cards.

This package provides everything you need to create rich, mobile-optimized
interactive cards for Feishu bots, without any external dependencies.

Quick Start:
    from feishu_card_kit import CardRenderer, card_to_feishu_content

    # Create a result card
    card = CardRenderer.result(
        title="任务完成",
        content="代码已重构完成，共修改 3 个文件。",
        success=True,
    )

    # Serialize for Feishu API
    content = card_to_feishu_content(card)

Modules:
    core       — Atomic card building blocks (header, text, button, etc.)
    renderer   — Pre-built card templates (progress, result, error, etc.)
    tracker    — Card message tracking and serialization utilities
    handler    — Long content handling strategies

All modules use only Python standard library — no external dependencies.
"""

__version__ = "1.0.0"

from feishu_card_kit.core import (
    CardColor,
    ButtonStyle,
    header,
    divider,
    text,
    note,
    section,
    button,
    action_row,
    field_row,
    card,
    get_state_color,
    get_state_icon,
    get_state_label,
)

from feishu_card_kit.renderer import CardRenderer

from feishu_card_kit.tracker import (
    CardMessageTracker,
    card_to_feishu_content,
    text_fallback,
)

from feishu_card_kit.handler import (
    LongContentSplitter,
    LongOutputStrategy,
    LongOutputHandler,
    handle_long_output,
)

__all__ = [
    # Version
    "__version__",
    # Core builders
    "CardColor",
    "ButtonStyle",
    "header",
    "divider",
    "text",
    "note",
    "section",
    "button",
    "action_row",
    "field_row",
    "card",
    "get_state_color",
    "get_state_icon",
    "get_state_label",
    # Renderer
    "CardRenderer",
    # Tracker & utils
    "CardMessageTracker",
    "card_to_feishu_content",
    "text_fallback",
    # Handler
    "LongContentSplitter",
    "LongOutputStrategy",
    "LongOutputHandler",
    "handle_long_output",
]
