# -*- coding: utf-8 -*-
# @file long_output_handler.py
# @brief Handler for long text output - supports file saving and pagination
# @author sailing-innocent
# @date 2026-04-07
# @version 1.0
# ---------------------------------
"""Long output handling strategies for Feishu Bot.

This module provides multiple strategies for handling output that exceeds
Feishu's card/message limits:

1. **Collapsible Card** - Use foldable sections for moderately long content (3K-8K chars)
2. **Multi-Card Pagination** - Split into multiple cards for long content (8K-30K chars)
3. **File Strategy** - Save to file and provide link for very long content (>30K chars)
"""

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

from sail_bot.paths import OUTPUT_DIR
from sail_bot.card_renderer import CardRenderer, LongContentSplitter, _text, _note, _divider


class LongOutputStrategy:
    """Strategy enum for long output handling."""
    PAGINATE = "paginate"      # Multiple cards (>8K chars)
    FILE = "file"              # Save to file (>30K chars)
    DIRECT = "direct"          # Direct output (<8K chars)


class LongOutputHandler:
    """Handle long text output with multiple strategies.
    
    Usage:
        handler = LongOutputHandler(messaging_client)
        strategy, cards_or_path = handler.process(
            title="任务结果",
            content=very_long_text,
            chat_id="oc_xxx",
        )
    """

    # Thresholds for choosing strategies
    COLLAPSE_THRESHOLD = 3000      # Use collapse above this
    PAGINATE_THRESHOLD = 8000      # Use pagination above this
    FILE_THRESHOLD = 30000         # Use file strategy above this

    def __init__(self, messaging_client: Optional[Any] = None):
        """Initialize handler.
        
        Args:
            messaging_client: FeishuMessagingClient for sending messages
        """
        self.messaging = messaging_client
        self._recent_files: List[Path] = []

    def determine_strategy(self, content: str) -> str:
        """Determine the best strategy for the content length."""
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
        chat_id: str,
        success: bool = True,
        context_path: str = "",
    ) -> Tuple[str, Any]:
        """Process long content and return appropriate output.
        
        Args:
            title: Title for the output
            content: The content to display
            chat_id: Target chat ID
            success: Whether the operation succeeded
            context_path: Optional workspace context path
        
        Returns:
            Tuple of (strategy, result) where result depends on strategy:
            - DIRECT/COLLAPSE: Single card dict
            - PAGINATE: List of card dicts
            - FILE: Path to saved file
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

        # COLLAPSE strategy removed - Feishu doesn't support 'collapse' component
        # Fall through to PAGINATE or DIRECT based on length

        elif strategy == LongOutputStrategy.PAGINATE:
            cards = LongContentSplitter.create_paginated_cards(
                title=title,
                content=content,
                success=success,
            )
            return strategy, cards

        elif strategy == LongOutputStrategy.FILE:
            file_path = self._save_to_file(title, content)
            card = self._create_file_card(title, file_path, len(content), success, context_path)
            return strategy, card

        return "direct", CardRenderer.result(title, content, success)

    def send(
        self,
        title: str,
        content: str,
        chat_id: str,
        message_id: Optional[str] = None,
        success: bool = True,
        context_path: str = "",
    ) -> List[str]:
        """Process and send long content to Feishu.
        
        Args:
            title: Title for the output
            content: The content to display
            chat_id: Target chat ID
            message_id: Optional message ID to reply to
            success: Whether the operation succeeded
            context_path: Optional workspace context path
        
        Returns:
            List of sent message IDs
        """
        if not self.messaging:
            print(f"[LongOutput] No messaging client, would send {len(content)} chars")
            return []

        strategy, result = self.process(title, content, chat_id, success, context_path)
        message_ids: List[str] = []

        if strategy == "paginate":
            # Send first card as reply, rest as new messages
            cards = result
            for i, card in enumerate(cards):
                if i == 0 and message_id:
                    mid = self.messaging.reply_card(message_id, card)
                else:
                    mid = self.messaging.send_card(chat_id, card)
                if mid:
                    message_ids.append(mid)
                # Small delay to preserve order
                if i < len(cards) - 1:
                    time.sleep(0.5)
        else:
            # Single card
            card = result
            if message_id:
                mid = self.messaging.reply_card(message_id, card)
            else:
                mid = self.messaging.send_card(chat_id, card)
            if mid:
                message_ids.append(mid)

        return message_ids

    def _save_to_file(self, title: str, content: str) -> Path:
        """Save content to file and return path.
        
        Args:
            title: Title for the file
            content: Content to save
        
        Returns:
            Path to saved file
        """
        # Generate filename from title and timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        title_hash = hashlib.md5(title.encode()).hexdigest()[:8]
        filename = f"{timestamp}_{title_hash}.md"
        file_path = OUTPUT_DIR / filename

        # Add header with metadata
        header = f"""# {title}

Generated: {datetime.now().isoformat()}
Length: {len(content)} characters

---

"""
        full_content = header + content

        # Write to file
        file_path.write_text(full_content, encoding="utf-8")
        
        # Track recent files
        self._recent_files.append(file_path)
        # Keep only last 100 files
        if len(self._recent_files) > 100:
            old_file = self._recent_files.pop(0)
            if old_file.exists():
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
        """Create a card showing file information.
        
        Args:
            title: Original title
            file_path: Path to saved file
            content_length: Length of original content
            success: Success status
            context_path: Optional context path
        
        Returns:
            Card dict
        """
        color = "green" if success else "red"
        icon = "✅" if success else "❌"

        elements: List[Dict[str, Any]] = [
            _text(f"{icon} **{title}**", bold=True),
            _divider(),
            _note(f"📄 内容长度：{content_length} 字符"),
            _note(f"💾 已保存到文件：{file_path.name}"),
            _divider(),
            _text("📂 文件位置："),
            _text(f"`{file_path}`"),
        ]

        if context_path:
            elements.append(_divider())
            elements.append(_note(f"💡 发送「状态 {Path(context_path).name}」查看详情"))

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{icon} {title} (文件)"},
                "template": color,
            },
            "elements": elements,
        }

    def get_recent_files(self, limit: int = 10) -> List[Path]:
        """Get list of recently saved output files."""
        return self._recent_files[-limit:]

    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """Clean up old output files.
        
        Args:
            max_age_hours: Delete files older than this
        
        Returns:
            Number of files deleted
        """
        cutoff = time.time() - (max_age_hours * 3600)
        deleted = 0

        for file_path in OUTPUT_DIR.glob("*.md"):
            try:
                if file_path.stat().st_mtime < cutoff:
                    file_path.unlink(missing_ok=True)
                    deleted += 1
            except Exception:
                pass

        return deleted


# Convenience function for quick usage
def handle_long_output(
    title: str,
    content: str,
    messaging_client: Optional[Any] = None,
    chat_id: Optional[str] = None,
    message_id: Optional[str] = None,
    success: bool = True,
    context_path: str = "",
) -> Any:
    """Convenience function to handle long output.
    
    This is a one-shot function that processes and optionally sends long content.
    
    Args:
        title: Title for the output
        content: The content to display
        messaging_client: FeishuMessagingClient for sending
        chat_id: Target chat ID (required if sending)
        message_id: Optional message ID to reply to
        success: Whether the operation succeeded
        context_path: Optional workspace context path
    
    Returns:
        Card dict, list of cards, or file path depending on strategy
    """
    handler = LongOutputHandler(messaging_client)
    
    if chat_id and messaging_client:
        return handler.send(title, content, chat_id, message_id, success, context_path)
    else:
        strategy, result = handler.process(title, content, chat_id or "", success, context_path)
        return result
