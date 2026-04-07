# -*- coding: utf-8 -*-
# @file message_formatter.py
# @brief Message formatting and pagination for Feishu Bot
# @author sailing-innocent
# @date 2026-03-29
# @version 1.0
# ---------------------------------
"""Message formatting utilities for human-friendly conversation display.

Provides:
- Smart truncation with "see more" option
- Pagination for long messages
- Summary generation
- Code block detection and formatting
"""

import re
from typing import List, Tuple, Optional


class MessageFormatter:
    """Formats messages for display in Feishu with pagination support."""

    # Constants
    MAX_CARD_LENGTH = 8000  # Feishu card max content length (was 3000, increased to 8000)
    SUMMARY_LENGTH = 500  # Length for summary view
    PAGE_SIZE = 2000  # Characters per page

    @staticmethod
    def truncate_with_hint(
        text: str, max_length: int = 500, hint: str = "...\n\n[查看详情了解更多]"
    ) -> str:
        """Truncate text with a hint to see more.

        Args:
            text: Original text
            max_length: Maximum length before truncation
            hint: Hint text to append

        Returns:
            Truncated text with hint
        """
        if len(text) <= max_length:
            return text

        # Try to truncate at a natural boundary (paragraph or sentence)
        truncated = text[:max_length]

        # Look for paragraph break
        last_para = truncated.rfind("\n\n")
        if last_para > max_length * 0.7:
            truncated = truncated[:last_para]
        else:
            # Look for sentence end
            last_sentence = max(
                truncated.rfind(". "),
                truncated.rfind("。"),
                truncated.rfind("! "),
                truncated.rfind("！"),
            )
            if last_sentence > max_length * 0.7:
                truncated = truncated[: last_sentence + 1]

        return truncated + hint

    @staticmethod
    def paginate(text: str, page_size: int = 2000) -> List[str]:
        """Split text into pages.

        Args:
            text: Text to paginate
            page_size: Characters per page

        Returns:
            List of pages
        """
        if len(text) <= page_size:
            return [text]

        pages = []
        start = 0

        while start < len(text):
            end = start + page_size

            if end >= len(text):
                pages.append(text[start:])
                break

            # Try to find a good break point
            # 1. Look for paragraph
            chunk = text[start:end]
            last_para = chunk.rfind("\n\n")
            if last_para > page_size * 0.5:
                end = start + last_para + 2
            else:
                # 2. Look for sentence end
                last_sentence = max(
                    chunk.rfind(". "),
                    chunk.rfind("。"),
                    chunk.rfind("! "),
                    chunk.rfind("！"),
                    chunk.rfind("? "),
                    chunk.rfind("？"),
                )
                if last_sentence > page_size * 0.5:
                    end = start + last_sentence + 2
                else:
                    # 3. Look for newline
                    last_newline = chunk.rfind("\n")
                    if last_newline > page_size * 0.5:
                        end = start + last_newline + 1

            pages.append(text[start:end])
            start = end

        return pages

    @staticmethod
    def generate_summary(text: str, max_lines: int = 5) -> str:
        """Generate a brief summary of the text.

        Args:
            text: Original text
            max_lines: Maximum lines in summary

        Returns:
            Summary text
        """
        lines = text.split("\n")

        # Remove empty lines at start/end
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        if len(lines) <= max_lines:
            return text

        # Take first few lines
        summary_lines = lines[:max_lines]

        # Check if there's a code block that got cut
        code_block_open = (
            sum(1 for line in summary_lines if line.strip().startswith("```")) % 2 == 1
        )
        if code_block_open:
            # Close the code block
            summary_lines.append("```")
            summary_lines.append("")
            summary_lines.append("[代码块已截断，查看详情了解完整内容]")

        return "\n".join(summary_lines)

    @staticmethod
    def extract_key_points(text: str, max_points: int = 3) -> List[str]:
        """Extract key points from text.

        Args:
            text: Text to analyze
            max_points: Maximum number of points

        Returns:
            List of key points
        """
        points = []

        # Look for bullet points
        bullet_pattern = r"^[\s]*[-*•][\s]+(.+)$"
        matches = re.findall(bullet_pattern, text, re.MULTILINE)
        points.extend(matches[:max_points])

        # Look for numbered lists
        if len(points) < max_points:
            numbered_pattern = r"^[\s]*\d+[.\)][\s]+(.+)$"
            matches = re.findall(numbered_pattern, text, re.MULTILINE)
            points.extend(matches[: max_points - len(points)])

        # If still not enough, take first few non-empty lines
        if len(points) < max_points:
            lines = text.split("\n")
            for line in lines:
                line = line.strip()
                if line and len(line) > 20 and not line.startswith("```"):
                    points.append(line[:100])
                    if len(points) >= max_points:
                        break

        return points[:max_points]

    @staticmethod
    def format_for_card(
        text: str,
        mode: str = "auto",
        max_length: int = 2000,
    ) -> Tuple[str, bool, int]:
        """Format text for Feishu card display.

        Args:
            text: Original text
            mode: Display mode - "auto", "summary", "full", "paged"
            max_length: Maximum length for summary mode

        Returns:
            Tuple of (formatted_text, has_more, total_pages)
        """
        if mode == "full":
            pages = MessageFormatter.paginate(text)
            return text, len(pages) > 1, len(pages)

        elif mode == "paged":
            pages = MessageFormatter.paginate(text)
            if len(pages) == 1:
                return text, False, 1
            # Return first page with hint
            return (
                pages[0] + f"\n\n[共 {len(pages)} 页，回复「下一页」查看更多]",
                True,
                len(pages),
            )

        elif mode == "summary":
            summary = MessageFormatter.generate_summary(text)
            has_more = len(text) > len(summary)
            if has_more:
                summary += "\n\n[查看详情了解完整内容]"
            return summary, has_more, 1

        else:  # auto mode
            if len(text) <= max_length:
                return text, False, 1

            # Truncate with hint
            return (MessageFormatter.truncate_with_hint(text, max_length), True, 1)

    @staticmethod
    def format_conversation_history(
        messages: List,
        page: int = 1,
        page_size: int = 5,
        include_full_content: bool = False,
    ) -> str:
        """Format conversation history for display.

        Args:
            messages: List of Message objects
            page: Page number (1-indexed)
            page_size: Messages per page
            include_full_content: Whether to include full message content

        Returns:
            Formatted text
        """
        total = len(messages)
        total_pages = (total + page_size - 1) // page_size

        start = (page - 1) * page_size
        end = min(start + page_size, total)
        page_messages = messages[start:end]

        lines = [f"对话历史 (第 {page}/{total_pages} 页，共 {total} 条消息)"]
        lines.append("=" * 40)

        for msg in page_messages:
            time_str = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M:%S")

            if msg.role == "user":
                lines.append(f"\n👤 用户 [{time_str}]:")
            else:
                lines.append(f"\n🤖 助手 [{time_str}]:")

            content = msg.content
            if not include_full_content and len(content) > 500:
                content = content[:500] + "..."

            # Escape markdown for display
            content = content.replace("```", "\\`\\`\\`")
            lines.append(content)

        lines.append("\n" + "=" * 40)
        if total_pages > 1:
            lines.append(f"回复「历史 {page + 1}」查看下一页")
            lines.append(f"回复「详情」查看当前消息完整内容")

        return "\n".join(lines)

    @staticmethod
    def create_progressive_display(
        full_text: str,
        stage: int = 1,
    ) -> str:
        """Create progressive display stages for a long message.

        Stage 1: Very brief summary (1-2 sentences)
        Stage 2: Key points (3-5 bullet points)
        Stage 3: Full summary (first few paragraphs)
        Stage 4: Full text

        Args:
            full_text: Complete text
            stage: Display stage (1-4)

        Returns:
            Text appropriate for the stage
        """
        if stage >= 4:
            return full_text

        if stage == 1:
            # First sentence(s)
            sentences = re.split(r"(?<=[.!?。！？])\s+", full_text)
            if sentences:
                return sentences[0] + "\n\n[回复「更多」查看详细内容]"
            return full_text[:200] + "..."

        elif stage == 2:
            # Key points
            points = MessageFormatter.extract_key_points(full_text, max_points=5)
            if points:
                return (
                    "要点:\n"
                    + "\n".join(f"• {p[:150]}" for p in points)
                    + "\n\n[回复「详情」查看完整内容]"
                )
            return MessageFormatter.generate_summary(full_text, max_lines=5)

        else:  # stage == 3
            # Full summary
            summary = MessageFormatter.generate_summary(full_text, max_lines=10)
            return summary + "\n\n[回复「完整」查看全部内容]"


from datetime import datetime
