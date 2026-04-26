# -*- coding: utf-8 -*-
# @file long_output_handler.py
# @brief Long text output handler — Compatibility shim for feishu_card_kit
# @author sailing-innocent
# @date 2026-04-26
# @version 2.0
# ---------------------------------
"""Long output handling — Compatibility shim.

This module re-exports from `feishu_card_kit.handler` with SailZen-specific
defaults (OUTPUT_DIR). All core implementation is in `feishu_card_kit`.

New code should use:
    from feishu_card_kit import LongOutputHandler

Existing code can continue using:
    from sail_bot.long_output_handler import LongOutputHandler
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from feishu_card_kit import (
    CardRenderer,
    LongContentSplitter,
    LongOutputStrategy,
    LongOutputHandler as _BaseLongOutputHandler,
    handle_long_output as _base_handle_long_output,
)
from feishu_card_kit.core import divider, note, text

from sail_bot.paths import OUTPUT_DIR


class LongOutputHandler(_BaseLongOutputHandler):
    """SailZen-specific LongOutputHandler with default OUTPUT_DIR."""

    def __init__(self, messaging_client: Optional[Any] = None):
        super().__init__(
            output_dir=OUTPUT_DIR,
            messaging_client=messaging_client,
        )


def handle_long_output(
    title: str,
    content: str,
    messaging_client: Optional[Any] = None,
    chat_id: Optional[str] = None,
    message_id: Optional[str] = None,
    success: bool = True,
    context_path: str = "",
) -> Any:
    """Convenience function with SailZen defaults."""
    handler = LongOutputHandler(messaging_client)

    if chat_id and messaging_client:
        return handler.send(title, content, chat_id, message_id, success, context_path)
    else:
        strategy, result = handler.process(title, content, success, context_path)
        return result

# Re-export other classes/functions
__all__ = [
    "LongContentSplitter",
    "LongOutputStrategy",
    "LongOutputHandler",
    "handle_long_output",
]
