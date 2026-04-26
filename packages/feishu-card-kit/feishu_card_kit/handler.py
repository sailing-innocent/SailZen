# -*- coding: utf-8 -*-
# @file handler.py
# @brief Long content handling strategies for Feishu cards
# @author sailing-innocent
# @date 2026-04-26
# @version 1.0
# ---------------------------------
"""Long content handling strategies for Feishu cards.

Provides multiple strategies for handling output that exceeds Feishu limits:
1. Direct — Single card (< 8K chars)
2. Paginate — Multiple cards (8K-30K chars)
3. File — Save to file (> 30K chars)

The output directory is configurable (no hardcoded paths).
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

from feishu_card_kit.renderer import CardRenderer


# ---------------------------------------------------------------------------
# Content splitting
# ---------------------------------------------------------------------------


class LongContentSplitter:
    """Utility for splitting long content into card-sized chunks."""

    # Feishu card content limit (conservative)
    CARD_CONTENT_LIMIT = 7500
    # Text message limit
    TEXT_MESSAGE_LIMIT = 20000

    @classmethod
    def split_for_cards(
        cls,
        content: str,
        max_chars_per_card: int = 7000,
        preserve_paragraphs: bool = True,
    ) -> List[str]:
        """Split long content into chunks suitable for card display.

        Args:
            content: Full content to split
            max_chars_per_card: Maximum characters per card chunk
            preserve_paragraphs: Try to split at paragraph boundaries

        Returns:
            List of content chunks
        """
        if len(content) <= max_chars_per_card:
            return [content]

        chunks = []
        remaining = content

        while remaining:
            if len(remaining) <= max_chars_per_card:
                chunks.append(remaining)
                break

            split_point = max_chars_per_card

            if preserve_paragraphs:
                search_start = max(0, max_chars_per_card - 500)
                search_end = min(len(remaining), max_chars_per_card + 500)
                search_text = remaining[search_start:search_end]

                para_break = search_text.rfind("\n\n")
                if para_break != -1:
                    split_point = search_start + para_break + 2
                else:
                    line_break = search_text.rfind("\n")
                    if line_break != -1:
                        split_point = search_start + line_break + 1
                    else:
                        for marker in [". ", "。", "! ", "！", "? ", "？"]:
                            idx = search_text.rfind(marker)
                            if idx != -1:
                                split_point = search_start + idx + len(marker)
                                break

            chunks.append(remaining[:split_point])
            remaining = remaining[split_point:].lstrip()

        return chunks

    @classmethod
    def create_paginated_cards(
        cls,
        title: str,
        content: str,
        success: bool = True,
    ) -> List[Dict[str, Any]]:
        """Create multiple paginated cards for very long content.

        Args:
            title: Base title for all cards
            content: Full content
            success: Success status

        Returns:
            List of card dicts
        """
        chunks = cls.split_for_cards(content)
        cards = []
        total = len(chunks)

        for i, chunk in enumerate(chunks, 1):
            card = CardRenderer.result_paginated(
                title=title,
                content=chunk,
                page=i,
                total_pages=total,
                success=success,
            )
            cards.append(card)

        return cards

    @classmethod
    def should_paginate(cls, content: str, threshold: int = 8000) -> bool:
        """Check if content should be split into multiple cards."""
        return len(content) > threshold


# ---------------------------------------------------------------------------
# Strategy enum
# ---------------------------------------------------------------------------


class LongOutputStrategy:
    """Strategy constants for long output handling."""

    PAGINATE = "paginate"
    FILE = "file"
    DIRECT = "direct"


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class LongOutputHandler:
    """Handle long text output with multiple strategies.

    Usage:
        handler = LongOutputHandler(output_dir="/tmp/bot_output")
        strategy, result = handler.process(
            title="任务结果",
            content=very_long_text,
        )
        # strategy = "direct" | "paginate" | "file"
        # result = card_dict | list[card_dict] | Path
    """

    PAGINATE_THRESHOLD = 8000
    FILE_THRESHOLD = 30000

    def __init__(
        self,
        output_dir: Optional[Path | str] = None,
        messaging_client: Optional[Any] = None,
    ):
        """Initialize handler.

        Args:
            output_dir: Directory for file strategy output. If None,
                       file strategy will return the path without saving.
            messaging_client: Optional messaging client for send() method.
                              Must have send_card(chat_id, card) and
                              reply_card(message_id, card) methods.
        """
        self.output_dir = Path(output_dir) if output_dir else None
        self.messaging = messaging_client
        self._recent_files: List[Path] = []

    def determine_strategy(self, content: str) -> str:
        """Determine the best strategy for content length."""
        length = len(content)
        if length > self.FILE_THRESHOLD:
            return LongOutputStrategy.FILE
        elif length > self.PAGINATE_THRESHOLD:
            return LongOutputStrategy.PAGINATE
        return LongOutputStrategy.DIRECT

    def process(
        self,
        title: str,
        content: str,
        success: bool = True,
        context_path: str = "",
    ) -> Tuple[str, Any]:
        """Process long content and return appropriate output.

        Args:
            title: Title for the output
            content: Content to display
            success: Whether operation succeeded
            context_path: Optional workspace context path

        Returns:
            Tuple of (strategy, result):
            - "direct": card dict
            - "paginate": list of card dicts
            - "file": Path to saved file (or dict with file info if no output_dir)
        """
        strategy = self.determine_strategy(content)

        if strategy == LongOutputStrategy.DIRECT:
            card = CardRenderer.result(
                title=title,
                content=content,
                success=success,
                context_path=context_path,
            )
            return strategy, card

        elif strategy == LongOutputStrategy.PAGINATE:
            cards = LongContentSplitter.create_paginated_cards(
                title=title,
                content=content,
                success=success,
            )
            return strategy, cards

        elif strategy == LongOutputStrategy.FILE:
            if self.output_dir:
                file_path = self._save_to_file(title, content)
                card = self._create_file_card(
                    title, file_path, len(content), success, context_path
                )
            else:
                # No output dir configured, return a card with content summary
                card = CardRenderer.result(
                    title=f"{title} (内容过长)",
                    content=f"内容共 {len(content)} 字符，已超出直接显示限制。"
                    f"\n\n前 500 字符预览：\n{content[:500]}...",
                    success=success,
                    context_path=context_path,
                )
            return strategy, card

        return LongOutputStrategy.DIRECT, CardRenderer.result(title, content, success)

    def send(
        self,
        title: str,
        content: str,
        chat_id: str,
        message_id: Optional[str] = None,
        success: bool = True,
        context_path: str = "",
    ) -> List[str]:
        """Process and send long content via messaging client.

        Args:
            title: Title
            content: Content
            chat_id: Target chat ID
            message_id: Optional message ID to reply to
            success: Success status
            context_path: Context path

        Returns:
            List of sent message IDs
        """
        if not self.messaging:
            print(f"[LongOutput] No messaging client, would send {len(content)} chars")
            return []

        strategy, result = self.process(title, content, success, context_path)
        message_ids: List[str] = []

        if strategy == "paginate":
            cards = result
            for i, card in enumerate(cards):
                if i == 0 and message_id:
                    mid = self._send_reply(message_id, card)
                else:
                    mid = self._send_new(chat_id, card)
                if mid:
                    message_ids.append(mid)
                if i < len(cards) - 1:
                    time.sleep(0.5)
        else:
            card = result
            if message_id:
                mid = self._send_reply(message_id, card)
            else:
                mid = self._send_new(chat_id, card)
            if mid:
                message_ids.append(mid)

        return message_ids

    # -- internal helpers --

    def _send_new(self, chat_id: str, card: Dict[str, Any]) -> Optional[str]:
        if hasattr(self.messaging, "send_card"):
            return self.messaging.send_card(chat_id, card)
        return None

    def _send_reply(self, message_id: str, card: Dict[str, Any]) -> Optional[str]:
        if hasattr(self.messaging, "reply_card"):
            return self.messaging.reply_card(message_id, card)
        return None

    def _save_to_file(self, title: str, content: str) -> Path:
        """Save content to file and return path."""
        if not self.output_dir:
            raise RuntimeError("output_dir not configured")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        title_hash = hashlib.md5(title.encode()).hexdigest()[:8]
        filename = f"{timestamp}_{title_hash}.md"
        file_path = self.output_dir / filename

        header = f"""# {title}

Generated: {datetime.now().isoformat()}
Length: {len(content)} characters

---

"""
        file_path.write_text(header + content, encoding="utf-8")

        self._recent_files.append(file_path)
        if len(self._recent_files) > 100:
            old_file = self._recent_files.pop(0)
            old_file.unlink(missing_ok=True)

        return file_path

    def _create_file_card(
        self,
        title: str,
        file_path: Path,
        content_length: int,
        success: bool,
        context_path: str = "",
    ) -> Dict[str, Any]:
        """Create a card showing file information."""
        color = "green" if success else "red"
        icon = "✅" if success else "❌"

        from feishu_card_kit.core import divider, note, text

        elements: List[Dict[str, Any]] = [
            text(f"{icon} **{title}**", bold=True),
            divider(),
            note(f"📄 内容长度：{content_length} 字符"),
            note(f"💾 已保存到文件：{file_path.name}"),
            divider(),
            text("📂 文件位置："),
            text(f"`{file_path}`"),
        ]

        if context_path:
            elements.append(divider())
            elements.append(note(f"💡 发送「状态 {Path(context_path).name}」查看详情"))

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{icon} {title} (文件)"},
                "template": color,
            },
            "elements": elements,
        }

    def get_recent_files(self, limit: int = 10) -> List[Path]:
        """Get recently saved output files."""
        return self._recent_files[-limit:]

    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """Clean up old output files."""
        if not self.output_dir:
            return 0

        cutoff = time.time() - (max_age_hours * 3600)
        deleted = 0

        for file_path in self.output_dir.glob("*.md"):
            try:
                if file_path.stat().st_mtime < cutoff:
                    file_path.unlink(missing_ok=True)
                    deleted += 1
            except Exception:
                pass

        return deleted


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def handle_long_output(
    title: str,
    content: str,
    output_dir: Optional[Path | str] = None,
    messaging_client: Optional[Any] = None,
    chat_id: Optional[str] = None,
    message_id: Optional[str] = None,
    success: bool = True,
    context_path: str = "",
) -> Any:
    """One-shot convenience function for long output handling.

    Args:
        title: Output title
        content: Content to display
        output_dir: Optional directory for file strategy
        messaging_client: Optional client with send_card/reply_card
        chat_id: Target chat ID (required if sending)
        message_id: Optional message ID to reply to
        success: Success status
        context_path: Context path

    Returns:
        Card dict, list of cards, or file path depending on strategy
    """
    handler = LongOutputHandler(
        output_dir=output_dir, messaging_client=messaging_client
    )

    if chat_id and messaging_client:
        return handler.send(title, content, chat_id, message_id, success, context_path)
    else:
        strategy, result = handler.process(title, content, success, context_path)
        return result
