# -*- coding: utf-8 -*-
# @file message_handler.py
# @brief Message command handler
# @author sailing-innocent
# @date 2026-03-21
# @version 1.0
# ---------------------------------
"""Parse and handle user commands from Feishu messages.

This module provides both legacy text-based command handling and
new event-based handlers for the normalized event pipeline.
"""

import re
import os
import subprocess
from typing import Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from .events import TextEvent, CardActionEvent


class MessageHandler:
    """Parse and execute user commands from normalized Feishu events.

    Supports both legacy text-based commands and new event-driven
    interactions including card actions and voice-derived text.
    """

    def __init__(self):
        # TODO: Load from config/Redis
        self.configured_projects = {
            "default": os.environ.get("OPENCODE_DEFAULT_PROJECT", "D:/ws/repos/SailZen")
        }

    async def handle_text_event(self, event: "TextEvent") -> Optional[Dict[str, Any]]:
        """Handle normalized text message events.

        This is the primary entry point for text-based interactions,
        including both direct text and voice-derived text (flagged via
        event.is_voice_input for special normalization).

        Args:
            event: Normalized text event with cleaned text and metadata

        Returns:
            Response dict to send back to Feishu, or None if no response
        """
        text = event.text_normalized
        sender_id = event.sender.open_id

        # For MVP-2: Keep legacy command handling as fallback
        # In the future, this will route through the LLM intent router
        return await self.handle_command(
            text=text, sender_id=sender_id, chat_type=event.chat_type
        )

    async def handle_card_action_event(
        self, event: "CardActionEvent"
    ) -> Optional[Dict[str, Any]]:
        """Handle card action callback events.

        Card actions represent structured user interactions like
        button clicks, quick actions, and form submissions.

        Args:
            event: Normalized card action event with structured intent

        Returns:
            Response dict to send back to Feishu, or None if no response
        """
        intent = event.intent_type
        workspace = event.target_workspace
        session = event.target_session
        params = event.action_parameters

        # Map card actions to commands
        action_map = {
            "start_session": self._cmd_start_opencode,
            "stop_session": self._cmd_stop_opencode,
            "restart_session": self._cmd_restart_opencode,
            "get_status": self._cmd_status,
            "git_pull": self._cmd_git_pull,
            "git_commit": self._cmd_git_commit,
            "git_push": self._cmd_git_push,
            "git_status": self._cmd_git_status,
            "code_request": self._cmd_code,
        }

        if intent and (handler := action_map.get(intent)):
            # Convert params to args string for legacy compatibility
            args = params.get("args") or ""
            return await handler(args, event.sender.open_id)

        return {"type": "text", "content": f"未识别的操作: {intent or 'unknown'}"}

    # Legacy interface for backward compatibility
    async def handle_command(
        self, text: str, sender_id: str, chat_type: str
    ) -> Dict[str, Any]:
        """Parse and execute command from message text (legacy interface)."""
        # Remove @mentions
        text = re.sub(r"@_user_\d+", "", text).strip()

        # Parse command
        if text.startswith("/"):
            return await self._handle_structured_command(text, sender_id)
        else:
            return await self._handle_natural_language(text, sender_id)

    async def _handle_structured_command(
        self, text: str, sender_id: str
    ) -> Dict[str, Any]:
        """Handle structured /commands."""
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handlers = {
            "/start-opencode": self._cmd_start_opencode,
            "/stop-opencode": self._cmd_stop_opencode,
            "/restart-opencode": self._cmd_restart_opencode,
            "/status": self._cmd_status,
            "/code": self._cmd_code,
            "/git-pull": self._cmd_git_pull,
            "/git-commit": self._cmd_git_commit,
            "/git-push": self._cmd_git_push,
            "/git-status": self._cmd_git_status,
        }

        handler = handlers.get(command)
        if handler:
            return await handler(args, sender_id)
        else:
            return {"type": "text", "content": f"Unknown command: {command}"}

    async def _handle_natural_language(
        self, text: str, sender_id: str
    ) -> Dict[str, Any]:
        """Handle natural language commands (simplified for MVP)."""
        # Simple keyword matching for MVP
        text_lower = text.lower()

        if "启动" in text_lower or "start" in text_lower:
            return await self._cmd_start_opencode("", sender_id)
        elif "状态" in text_lower or "status" in text_lower:
            return await self._cmd_status("", sender_id)
        elif any(kw in text_lower for kw in ["提交", "commit"]):
            return await self._cmd_git_commit("", sender_id)
        else:
            return {
                "type": "text",
                "content": "收到消息，但我暂时只能理解特定的指令。\n可用指令：/start-opencode, /status, /git-commit",
            }

    async def _cmd_start_opencode(self, args: str, sender_id: str) -> Dict[str, Any]:
        """Start OpenCode in specified project."""
        project_path = args.strip() or self.configured_projects.get("default")

        if not project_path:
            return {"type": "text", "content": "错误：未配置项目路径"}

        # Validate path
        if not Path(project_path).exists():
            return {"type": "text", "content": f"错误：项目路径不存在: {project_path}"}

        # TODO: Trigger local agent to start OpenCode via desired_state
        # For MVP, we'll directly instruct user
        return {
            "type": "text",
            "content": f"📂 项目路径: {project_path}\n"
            f"🚀 请在本地运行以下命令启动OpenCode:\n"
            f"```\ncd {project_path} && opencode web --hostname 0.0.0.0\n```",
        }

    async def _cmd_stop_opencode(self, args: str, sender_id: str) -> Dict[str, Any]:
        """Stop OpenCode process."""
        return {
            "type": "text",
            "content": "⏹️ OpenCode停止功能需要本地Agent支持（开发中）",
        }

    async def _cmd_restart_opencode(self, args: str, sender_id: str) -> Dict[str, Any]:
        """Restart OpenCode process."""
        return {
            "type": "text",
            "content": "🔄 OpenCode重启功能需要本地Agent支持（开发中）",
        }

    async def _cmd_status(self, args: str, sender_id: str) -> Dict[str, Any]:
        """Get system status."""
        project = self.configured_projects.get("default", "未配置")
        return {
            "type": "text",
            "content": f"📊 系统状态\n"
            f"━━━━━━━━━━━━\n"
            f"🤖 Agent连接: 待实现\n"
            f"💻 OpenCode状态: 待实现\n"
            f"📁 当前项目: {project}\n"
            f"━━━━━━━━━━━━",
        }

    async def _cmd_code(self, args: str, sender_id: str) -> Dict[str, Any]:
        """Execute code generation via OpenCode."""
        if not args:
            return {
                "type": "text",
                "content": "用法: /code <描述>\n示例: /code 实现一个登录页面",
            }

        return {
            "type": "text",
            "content": f"📝 代码生成请求\n"
            f"━━━━━━━━━━━━\n"
            f"需求: {args}\n\n"
            f"请在OpenCode中执行以下操作:\n"
            f"1. 确保OpenCode已启动\n"
            f"2. 输入需求: {args}\n\n"
            f"（自动调用功能开发中）",
        }

    async def _cmd_git_pull(self, args: str, sender_id: str) -> Dict[str, Any]:
        """Execute git pull."""
        project_path = self.configured_projects.get("default")

        try:
            result = subprocess.run(
                ["git", "pull"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return {
                    "type": "text",
                    "content": f"✅ Git pull成功\n```\n{result.stdout}\n```",
                }
            else:
                return {
                    "type": "text",
                    "content": f"❌ Git pull失败\n```\n{result.stderr}\n```",
                }
        except Exception as e:
            return {"type": "text", "content": f"❌ 执行失败: {str(e)}"}

    async def _cmd_git_commit(self, args: str, sender_id: str) -> Dict[str, Any]:
        """Execute git commit."""
        project_path = self.configured_projects.get("default")
        message = args.strip() if args else "Update from Feishu Bot"

        try:
            # First add all changes
            subprocess.run(
                ["git", "add", "."], cwd=project_path, capture_output=True, timeout=10
            )

            # Then commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return {
                    "type": "text",
                    "content": f"✅ Git commit成功\n```\n{result.stdout}\n```",
                }
            else:
                return {
                    "type": "text",
                    "content": f"⚠️ {result.stderr}\n"
                    f"（如果没有变更需要提交，这是正常的）",
                }
        except Exception as e:
            return {"type": "text", "content": f"❌ 执行失败: {str(e)}"}

    async def _cmd_git_push(self, args: str, sender_id: str) -> Dict[str, Any]:
        """Execute git push."""
        project_path = self.configured_projects.get("default")

        try:
            result = subprocess.run(
                ["git", "push"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return {
                    "type": "text",
                    "content": f"✅ Git push成功\n```\n{result.stdout}\n```",
                }
            else:
                return {
                    "type": "text",
                    "content": f"❌ Git push失败\n```\n{result.stderr}\n```",
                }
        except Exception as e:
            return {"type": "text", "content": f"❌ 执行失败: {str(e)}"}

    async def _cmd_git_status(self, args: str, sender_id: str) -> Dict[str, Any]:
        """Execute git status."""
        project_path = self.configured_projects.get("default")

        try:
            result = subprocess.run(
                ["git", "status"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            return {"type": "text", "content": f"📊 Git状态\n```\n{result.stdout}\n```"}
        except Exception as e:
            return {"type": "text", "content": f"❌ 执行失败: {str(e)}"}
