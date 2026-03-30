# -*- coding: utf-8 -*-
# @file conversation_bot_integration.py
# @brief Integration of ConversationManager with Feishu Bot
# @author sailing-innocent
# @date 2026-03-29
# @version 1.0
# ---------------------------------
"""Integration layer for conversation management in Feishu Bot.

Provides:
- Human-friendly conversation controls (start/pause/resume/end)
- Progressive message display (summary → details → full)
- Conversation history browsing with pagination
- Session state management
"""

import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from bot.conversation_manager import (
    ConversationManager,
    ConversationSession,
    ConversationStatus,
    get_conversation_manager,
)
from bot.message_formatter import MessageFormatter
from bot.opencode_client import OpenCodeWebClient


class ConversationBotIntegration:
    """Integrates conversation management with Feishu Bot."""

    def __init__(self, opencode_client: OpenCodeWebClient):
        """Initialize integration.

        Args:
            opencode_client: OpenCode web client for sending messages
        """
        self.opencode = opencode_client
        self.conv_mgr = get_conversation_manager()
        self.formatter = MessageFormatter()

    # =================================================================
    # Session Lifecycle Management
    # =================================================================

    def start_conversation(
        self,
        chat_id: str,
        workspace_path: str,
        task: str,
    ) -> Tuple[bool, str, Optional[str]]:
        """Start a new conversation session.

        Args:
            chat_id: Feishu chat ID
            workspace_path: Workspace path
            task: Initial task description

        Returns:
            Tuple of (success, message, session_id)
        """
        # Check for existing active session
        existing = self.conv_mgr.get_active_session(chat_id)
        if existing:
            return (
                False,
                f"当前已有活跃的对话: {existing.workspace_path}\n"
                f"任务: {existing.current_task}\n\n"
                "请先结束当前对话或回复「切换」开始新对话",
                None,
            )

        # Create new session
        session = self.conv_mgr.create_session(
            workspace_path=workspace_path,
            chat_id=chat_id,
            task=task,
        )

        # Add system message
        session.add_message(
            "system",
            f"对话已开始\n工作区: {workspace_path}\n任务: {task}",
        )

        return (
            True,
            f"✅ 对话已创建\n"
            f"会话ID: `{session.session_id[:16]}...`\n"
            f"工作区: {workspace_path}\n"
            f"任务: {task}\n\n"
            "现在开始你的任务描述，我会帮你处理。",
            session.session_id,
        )

    def send_message(
        self,
        session_id: str,
        user_message: str,
        callback=None,
    ) -> Tuple[str, bool, Dict[str, Any]]:
        """Send a message and handle the response with progressive display.

        Args:
            session_id: Conversation session ID
            user_message: User's message
            callback: Optional callback for streaming updates

        Returns:
            Tuple of (display_text, has_more, metadata)
        """
        session = self.conv_mgr.get_session(session_id)
        if not session:
            return "❌ 会话不存在", False, {}

        if session.status == ConversationStatus.PAUSED:
            return (
                "⏸️ 对话当前处于暂停状态\n回复「继续」恢复对话",
                False,
                {"status": "paused"},
            )

        if session.status not in (ConversationStatus.IDLE, ConversationStatus.ACTIVE):
            return (
                f"❌ 对话状态异常: {session.status.value}\n无法发送消息",
                False,
                {"status": session.status.value},
            )

        # Ensure session is active
        if session.status == ConversationStatus.IDLE:
            self.conv_mgr.start_session(session_id)

        # Add user message
        self.conv_mgr.add_user_message(session_id, user_message)

        # Send to OpenCode
        if not session.opencode_session_id:
            return (
                "⚠️ OpenCode 会话未就绪\n请等待服务启动完成...",
                False,
                {"status": "not_ready"},
            )

        # Send message and get response
        full_response = self.opencode.send_message(
            session.opencode_session_id,
            user_message,
        )

        # Add assistant message
        self.conv_mgr.add_assistant_message(
            session_id,
            full_response,
            metadata={"timestamp": time.time()},
        )

        # Format for progressive display
        formatted, has_more, total_pages = self.formatter.format_for_card(
            full_response,
            mode="auto",
            max_length=1500,
        )

        metadata = {
            "session_id": session_id,
            "has_more": has_more,
            "total_pages": total_pages,
            "message_length": len(full_response),
        }

        return formatted, has_more, metadata

    def pause_conversation(self, session_id: str) -> str:
        """Pause a conversation session."""
        if self.conv_mgr.pause_session(session_id):
            return "⏸️ 对话已暂停\n回复「继续」恢复对话"
        return "❌ 暂停失败，会话不存在"

    def resume_conversation(self, session_id: str) -> str:
        """Resume a paused conversation session."""
        session = self.conv_mgr.get_session(session_id)
        if not session:
            return "❌ 会话不存在"

        if session.status != ConversationStatus.PAUSED:
            return f"当前状态: {session.status.value}，无需恢复"

        self.conv_mgr.resume_session(session_id)

        # Get last few messages for context
        messages = session.get_messages(limit=3)
        context = ""
        if messages:
            last_assistant = [m for m in messages if m.role == "assistant"][-1:]
            if last_assistant:
                context = f"\n\n上次对话:\n{self.formatter.truncate_with_hint(last_assistant[0].content, 300)}"

        return (
            "▶️ 对话已恢复\n"
            f"会话: {session.workspace_path}\n"
            f"任务: {session.current_task}{context}\n\n"
            "请继续..."
        )

    def end_conversation(self, session_id: str, reason: str = "") -> str:
        """End a conversation session."""
        session = self.conv_mgr.get_session(session_id)
        if not session:
            return "❌ 会话不存在"

        # Generate summary
        stats = session.get_summary_stats()

        self.conv_mgr.end_session(session_id, completed=True)

        summary_lines = [
            "✅ 对话已结束",
            f"会话: {session.workspace_path}",
            f"任务: {session.current_task}",
            f"时长: {stats['duration_minutes']:.1f} 分钟",
            f"消息: {stats['user_messages']} 用户 / {stats['assistant_messages']} 助手",
        ]

        if reason:
            summary_lines.append(f"结束原因: {reason}")

        summary_lines.append("\n回复「历史」查看对话记录")

        return "\n".join(summary_lines)

    # =================================================================
    # Progressive Display
    # =================================================================

    def get_more_content(
        self,
        session_id: str,
        display_mode: str = "details",
        page: int = 1,
    ) -> Tuple[str, bool]:
        """Get more content for progressive display.

        Args:
            session_id: Session ID
            display_mode: "summary", "details", "full", or page number
            page: Page number for paginated view

        Returns:
            Tuple of (content, has_more)
        """
        session = self.conv_mgr.get_session(session_id)
        if not session:
            return "❌ 会话不存在", False

        last_message = session.get_last_message()
        if not last_message or last_message.role != "assistant":
            return "没有可查看的消息", False

        full_text = last_message.content

        if display_mode == "summary":
            # Return first stage (very brief)
            return (
                self.formatter.create_progressive_display(full_text, stage=1),
                True,
            )

        elif display_mode == "details":
            # Return key points
            return (
                self.formatter.create_progressive_display(full_text, stage=2),
                True,
            )

        elif display_mode == "full":
            # Return full text paginated
            pages = self.formatter.paginate(full_text)
            if page <= len(pages):
                content = pages[page - 1]
                has_more = page < len(pages)
                if has_more:
                    content += f"\n\n[第 {page}/{len(pages)} 页，回复「下一页」继续]"
                return content, has_more
            return "没有更多内容", False

        else:
            return "未知的显示模式", False

    # =================================================================
    # History and Browsing
    # =================================================================

    def get_conversation_history(
        self,
        chat_id: str,
        session_id: Optional[str] = None,
        page: int = 1,
        detail_level: str = "summary",
    ) -> str:
        """Get conversation history for display.

        Args:
            chat_id: Feishu chat ID
            session_id: Specific session ID (None for recent summary)
            page: Page number
            detail_level: "summary", "normal", or "full"

        Returns:
            Formatted history text
        """
        if not session_id:
            # Show recent sessions summary
            return self.conv_mgr.get_recent_summary(chat_id)

        session = self.conv_mgr.get_session(session_id)
        if not session:
            return "❌ 会话不存在"

        messages, total_pages = self.conv_mgr.get_session_history(
            session_id, page=page, page_size=5 if detail_level == "full" else 10
        )

        if not messages:
            return "该会话暂无消息记录"

        lines = [
            f"📜 对话记录",
            f"工作区: {session.workspace_path}",
            f"任务: {session.current_task}",
            f"状态: {session.status.value}",
            f"第 {page}/{total_pages} 页",
            "=" * 40,
        ]

        for msg in messages:
            time_str = time.strftime("%H:%M:%S", time.localtime(msg.timestamp))

            if msg.role == "user":
                lines.append(f"\n👤 [{time_str}]:")
            elif msg.role == "assistant":
                lines.append(f"\n🤖 [{time_str}]:")
            else:
                lines.append(f"\n⚙️ [{time_str}]:")

            content = msg.content
            if detail_level == "summary":
                content = self.formatter.truncate_with_hint(content, 300)
            elif detail_level == "normal":
                content = self.formatter.truncate_with_hint(content, 800)
            # "full" shows complete content

            lines.append(content)

        lines.append("\n" + "=" * 40)

        if total_pages > 1:
            lines.append(f"回复「历史 {page + 1}」查看下一页")

        if detail_level != "full":
            lines.append(f"回复「详情」查看完整内容")

        return "\n".join(lines)

    def list_sessions(self, chat_id: str) -> str:
        """List all sessions for a chat."""
        sessions = self.conv_mgr.list_sessions(chat_id=chat_id, limit=10)

        if not sessions:
            return "暂无对话记录\n\n发送「开始 工作区路径」创建新对话"

        lines = ["📋 对话列表"]

        for i, session in enumerate(sessions, 1):
            stats = session.get_summary_stats()
            status_icon = {
                ConversationStatus.ACTIVE: "🟢",
                ConversationStatus.PAUSED: "⏸️",
                ConversationStatus.COMPLETED: "✅",
                ConversationStatus.ERROR: "❌",
                ConversationStatus.IDLE: "⚪",
            }.get(session.status, "⚪")

            lines.append(
                f"\n{i}. {status_icon} `{session.session_id[:12]}...`\n"
                f"   工作区: {session.workspace_path}\n"
                f"   任务: {session.current_task[:40]}{'...' if len(session.current_task) > 40 else ''}\n"
                f"   消息: {stats['total_messages']} 条 | 时长: {stats['duration_minutes']:.1f} 分钟"
            )

        lines.append("\n" + "=" * 40)
        lines.append(
            "操作:\n"
            "• 「切换 编号」切换对话\n"
            "• 「历史 编号」查看记录\n"
            "• 「结束 编号」结束对话"
        )

        return "\n".join(lines)

    # =================================================================
    # Command Processing
    # =================================================================

    def process_command(
        self, text: str, chat_id: str
    ) -> Tuple[bool, str, Optional[str]]:
        """Process conversation management commands.

        Returns:
            Tuple of (handled, response, action)
        """
        text_lower = text.lower().strip()

        # Start new conversation
        if any(cmd in text_lower for cmd in ["开始", "start", "新建", "new"]):
            # Extract path and task
            parts = text.split(None, 2)
            if len(parts) < 2:
                return (
                    True,
                    "请指定工作区路径和任务\n"
                    "格式: 开始 [工作区路径] [任务描述]\n"
                    "示例: 开始 ~/projects/myapp 实现登录功能",
                    None,
                )

            workspace = parts[1]
            task = parts[2] if len(parts) > 2 else "未指定任务"

            success, msg, session_id = self.start_conversation(chat_id, workspace, task)
            return True, msg, "start_conversation" if success else None

        # Pause conversation
        if any(cmd in text_lower for cmd in ["暂停", "pause", "stop"]):
            session = self.conv_mgr.get_active_session(chat_id)
            if session:
                msg = self.pause_conversation(session.session_id)
                return True, msg, "pause_conversation"
            return True, "当前没有活跃的对话", None

        # Resume conversation
        if any(cmd in text_lower for cmd in ["继续", "resume", "恢复"]):
            session = self.conv_mgr.get_active_session(chat_id)
            if session:
                msg = self.resume_conversation(session.session_id)
                return True, msg, "resume_conversation"
            return True, "当前没有暂停的对话\n发送「列表」查看所有对话", None

        # End conversation
        if any(cmd in text_lower for cmd in ["结束", "end", "关闭", "close"]):
            session = self.conv_mgr.get_active_session(chat_id)
            if session:
                msg = self.end_conversation(session.session_id, reason="用户主动结束")
                return True, msg, "end_conversation"
            return True, "当前没有活跃的对话", None

        # List sessions
        if any(cmd in text_lower for cmd in ["列表", "list", "对话", "sessions"]):
            msg = self.list_sessions(chat_id)
            return True, msg, "list_sessions"

        # Show history
        if any(cmd in text_lower for cmd in ["历史", "history", "记录"]):
            # Check if specific session requested
            parts = text.split()
            session_id = parts[1] if len(parts) > 1 else None

            msg = self.get_conversation_history(chat_id, session_id)
            return True, msg, "show_history"

        # Get more content
        if any(cmd in text_lower for cmd in ["更多", "more", "详情", "详细", "完整"]):
            session = self.conv_mgr.get_active_session(chat_id)
            if session:
                display_mode = (
                    "full"
                    if any(cmd in text_lower for cmd in ["完整", "full"])
                    else "details"
                )
                content, has_more = self.get_more_content(
                    session.session_id,
                    display_mode=display_mode,
                )
                return True, content, "show_more"
            return True, "当前没有活跃的对话", None

        # Next page
        if any(cmd in text_lower for cmd in ["下一页", "next", "翻页"]):
            session = self.conv_mgr.get_active_session(chat_id)
            if session:
                content, has_more = self.get_more_content(
                    session.session_id,
                    display_mode="full",
                    page=2,  # TODO: Track current page per session
                )
                return True, content, "next_page"
            return True, "当前没有活跃的对话", None

        return False, "", None
