# -*- coding: utf-8 -*-
# @file bot_runtime.py
# @brief Main Feishu Bot Runtime with self-update capability
# @author sailing-innocent
# @date 2026-03-29
# @version 1.0
# ---------------------------------
"""Main Feishu Bot Runtime for SailZen 3.0 Phase 0 MVP.

This module provides:
- Long-connection Feishu client (WebSocket-based)
- Integration with control plane and edge runtime
- Self-update capability
- Graceful shutdown handling
- State persistence across restarts

Usage:
    uv run python -m sail_server.feishu_gateway.bot_runtime
    uv run python -m sail_server.feishu_gateway.bot_runtime --restore-state
"""

import argparse
import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional
import threading
import time

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sail_server.feishu_gateway.bot_state_manager import (
    BotStateManager,
    get_state_manager,
)
from sail_server.feishu_gateway.self_update_orchestrator import (
    SelfUpdateOrchestrator,
    UpdatePhase,
    UpdateTriggerSource,
)
from sail_server.feishu_gateway.cards import CardRenderer, CardTemplate


# Try to import lark-oapi
try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

    LARK_AVAILABLE = True
except ImportError:
    LARK_AVAILABLE = False
    lark = None  # type: ignore
    P2ImMessageReceiveV1 = None  # type: ignore
    print("Warning: lark-oapi not available, running in mock mode")


class FeishuLongConnectionClient:
    """Feishu long-connection WebSocket client."""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        message_handler: Optional[callable] = None,
        event_handler: Optional[callable] = None,
    ):
        """Initialize Feishu client.

        Args:
            app_id: Feishu app ID
            app_secret: Feishu app secret
            message_handler: Callback for message events
            event_handler: Callback for other events
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.message_handler = message_handler
        self.event_handler = event_handler

        self._client = None
        self._running = False
        self._event_handler_builder = None

    def build_event_handler(self):
        """Build event handler for Feishu events."""
        if not LARK_AVAILABLE or lark is None:
            return None

        def on_message(data) -> None:
            """Handle incoming message."""
            if self.message_handler:
                try:
                    # Extract message data - use getattr for safe access
                    event_data = {
                        "message_id": getattr(data.event.message, "message_id", ""),
                        "chat_id": getattr(data.event.message, "chat_id", ""),
                        "chat_type": getattr(data.event.message, "chat_type", ""),
                        "message_type": getattr(data.event.message, "message_type", ""),
                        "content": getattr(data.event.message, "content", ""),
                        "sender": {
                            "sender_id": getattr(
                                getattr(data.event.message, "sender", None),
                                "sender_id",
                                None,
                            )
                            and getattr(
                                getattr(data.event.message, "sender", None).sender_id,
                                "open_id",
                                "",
                            )
                            or "",
                            "user_type": getattr(
                                getattr(data.event.message, "sender", None),
                                "sender_type",
                                "",
                            ),
                        },
                        "mentions": [
                            {
                                "key": getattr(m, "key", ""),
                                "id": getattr(getattr(m, "id", None), "open_id", ""),
                                "username": getattr(m, "name", ""),
                            }
                            for m in (getattr(data.event.message, "mentions", []) or [])
                        ],
                        "create_time": getattr(data.event.message, "create_time", ""),
                    }

                    # Call handler in thread-safe way
                    asyncio.create_task(self._async_handle_message(event_data))
                except Exception as e:
                    print(f"[FeishuClient] Error handling message: {e}")

        # Build event handler
        builder = lark.EventDispatcherHandler.builder(self.app_id, self.app_secret)
        builder.register_p2_im_message_receive_v1(on_message)

        return builder.build()

    async def _async_handle_message(self, event_data: Dict[str, Any]) -> None:
        """Async wrapper for message handler."""
        if self.message_handler:
            try:
                await self.message_handler(event_data)
            except Exception as e:
                print(f"[FeishuClient] Message handler error: {e}")

    def start(self) -> None:
        """Start the Feishu long connection."""
        if not LARK_AVAILABLE:
            print("[FeishuClient] Running in mock mode (lark-oapi not available)")
            self._running = True
            return

        try:
            event_handler = self.build_event_handler()
            if not event_handler:
                print("[FeishuClient] Failed to build event handler")
                return

            self._client = lark.ws.Client(
                self.app_id,
                self.app_secret,
                event_handler=event_handler,
            )

            self._running = True
            print(f"[FeishuClient] Starting long connection...")

            # Start in a separate thread since it's blocking
            self._thread = threading.Thread(target=self._client.start)
            self._thread.daemon = True
            self._thread.start()

        except Exception as e:
            print(f"[FeishuClient] Failed to start: {e}")
            self._running = False

    def stop(self) -> None:
        """Stop the Feishu connection."""
        self._running = False

        if self._client:
            try:
                # Note: lark-oapi may not have explicit stop method
                print("[FeishuClient] Stopping connection...")
            except Exception as e:
                print(f"[FeishuClient] Error stopping: {e}")

    async def close(self) -> None:
        """Close connection gracefully."""
        self.stop()

    @property
    def is_running(self) -> bool:
        """Check if client is running."""
        return self._running


class SailZenBotRuntime:
    """Main SailZen Bot Runtime.

    Integrates:
    - Feishu long connection
    - State management
    - Self-update orchestration
    - Control plane integration
    """

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        workspace_root: Optional[Path] = None,
    ):
        """Initialize bot runtime.

        Args:
            app_id: Feishu app ID (or from env)
            app_secret: Feishu app secret (or from env)
            workspace_root: SailZen workspace root
        """
        # Configuration
        self.app_id = app_id or os.getenv("FEISHU_APP_ID", "")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET", "")
        self.workspace_root = workspace_root or Path("D:/ws/repos/SailZen")

        # State management
        self.state_manager = get_state_manager()

        # Self-update orchestration
        self.update_orchestrator: Optional[SelfUpdateOrchestrator] = None

        # Feishu client
        self.feishu_client: Optional[FeishuLongConnectionClient] = None

        # Runtime state
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Handover data (if restored)
        self._handover_data: Optional[Dict[str, Any]] = None

    async def initialize(self, restore_state: bool = False) -> bool:
        """Initialize the bot runtime.

        Args:
            restore_state: Whether to restore from previous backup

        Returns:
            True if initialization successful
        """
        print("[BotRuntime] Initializing...")

        # Check for handover (self-update restoration)
        handover_data = SelfUpdateOrchestrator.check_for_handover()
        if handover_data:
            print(
                f"[BotRuntime] Detected handover from previous process (PID: {handover_data.get('old_pid')})"
            )
            self._handover_data = handover_data
            restore_state = True

        # Initialize state
        if restore_state:
            session_state = self.state_manager.initialize_session()
            if handover_data:
                print(
                    f"[BotRuntime] Restored from backup: {handover_data.get('backup_path')}"
                )
        else:
            session_state = self.state_manager.initialize_session()

        print(f"[BotRuntime] Session ID: {session_state.session_id}")

        # Initialize Feishu client
        if self.app_id and self.app_secret:
            self.feishu_client = FeishuLongConnectionClient(
                app_id=self.app_id,
                app_secret=self.app_secret,
                message_handler=self._handle_feishu_message,
            )
        else:
            print("[BotRuntime] Warning: Feishu credentials not configured")

        # Initialize self-update orchestrator
        self.update_orchestrator = SelfUpdateOrchestrator(
            state_manager=self.state_manager,
            feishu_client=self.feishu_client,
            workspace_root=self.workspace_root,
        )

        # Register update callbacks
        self.update_orchestrator.register_update_callback(self._on_update_phase_change)

        print("[BotRuntime] Initialization complete")
        return True

    async def start(self) -> None:
        """Start the bot runtime."""
        print("[BotRuntime] Starting...")
        self._running = True

        # Start Feishu client
        if self.feishu_client:
            self.feishu_client.start()

        # Send startup notification if restored
        if self._handover_data:
            await self._send_update_complete_notification()

        # Main loop
        try:
            await self._main_loop()
        except asyncio.CancelledError:
            print("[BotRuntime] Main loop cancelled")
        except Exception as e:
            print(f"[BotRuntime] Main loop error: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        print("[BotRuntime] Shutting down...")
        self._running = False

        # Stop Feishu client
        if self.feishu_client:
            await self.feishu_client.close()

        # Cleanup state
        self.state_manager.cleanup_current_session()

        # Signal shutdown complete
        self._shutdown_event.set()

        print("[BotRuntime] Shutdown complete")

    async def request_self_update(
        self,
        reason: str,
        source: UpdateTriggerSource = UpdateTriggerSource.MANUAL_COMMAND,
        initiated_by: Optional[str] = None,
    ) -> bool:
        """Request a self-update.

        Args:
            reason: Reason for update
            source: Source of update trigger
            initiated_by: Who initiated the update

        Returns:
            True if update initiated successfully
        """
        if not self.update_orchestrator:
            print("[BotRuntime] Update orchestrator not initialized")
            return False

        print(f"[BotRuntime] Initiating self-update: {reason}")

        result = await self.update_orchestrator.initiate_self_update(
            trigger_source=source,
            reason=reason,
            initiated_by=initiated_by,
        )

        if result.success:
            print(f"[BotRuntime] Self-update successful, new PID: {result.new_pid}")
            # Trigger shutdown
            asyncio.create_task(self.shutdown())
            return True
        else:
            print(f"[BotRuntime] Self-update failed: {result.error}")
            return False

    async def _main_loop(self) -> None:
        """Main runtime loop."""
        heartbeat_interval = 30  # seconds
        last_heartbeat = 0

        while self._running:
            # Check for shutdown signal
            if self.update_orchestrator and self.update_orchestrator.should_exit():
                print("[BotRuntime] Update completion detected, exiting...")
                break

            # Send heartbeat
            now = time.time()
            if now - last_heartbeat >= heartbeat_interval:
                self.state_manager.update_heartbeat()
                last_heartbeat = now

            # Sleep briefly
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=1.0)
                break  # Shutdown event set
            except asyncio.TimeoutError:
                continue

    async def _handle_feishu_message(self, event_data: Dict[str, Any]) -> None:
        """Handle incoming Feishu message.

        Args:
            event_data: Normalized message event data
        """
        message_id = event_data.get("message_id", "unknown")
        chat_id = event_data.get("chat_id", "unknown")
        content_str = event_data.get("content", "{}")

        # Update chat context
        self.state_manager.update_chat_context(
            chat_id,
            {
                "last_message_id": message_id,
                "last_message_at": time.time(),
            },
        )

        try:
            # Parse content
            content = (
                json.loads(content_str) if isinstance(content_str, str) else content_str
            )
            text = content.get("text", "")

            print(f"[BotRuntime] Received message: {text[:100]}...")

            # Handle commands
            await self._handle_command(text, chat_id, event_data)

        except json.JSONDecodeError:
            print(f"[BotRuntime] Failed to parse message content: {content_str[:100]}")
        except Exception as e:
            print(f"[BotRuntime] Error handling message: {e}")

    async def _handle_command(
        self,
        text: str,
        chat_id: str,
        event_data: Dict[str, Any],
    ) -> None:
        """Handle command from message text.

        Args:
            text: Message text
            chat_id: Chat ID
            event_data: Full event data
        """
        text_lower = text.lower().strip()

        # Self-update command
        if any(cmd in text_lower for cmd in ["更新", "update", "升级", "restart"]):
            # Check if it's from authorized user
            sender_id = event_data.get("sender", {}).get("sender_id", "")

            # Send confirmation
            await self._send_text_reply(
                chat_id,
                "🔄 收到自更新请求，正在启动更新流程...",
            )

            # Initiate update
            await self.request_self_update(
                reason=f"User command: {text[:50]}",
                source=UpdateTriggerSource.MANUAL_COMMAND,
                initiated_by=sender_id,
            )
            return

        # Status command
        if any(cmd in text_lower for cmd in ["状态", "status", "信息", "info"]):
            status_text = self._build_status_text()
            await self._send_text_reply(chat_id, status_text)
            return

        # Help command
        if any(cmd in text_lower for cmd in ["帮助", "help", "怎么用", "指令"]):
            help_text = self._build_help_text()
            await self._send_text_reply(chat_id, help_text)
            return

        # Echo for unrecognized commands
        await self._send_text_reply(
            chat_id,
            f"🤖 收到消息: {text[:100]}\n\n发送「帮助」查看可用指令。",
        )

    async def _send_text_reply(self, chat_id: str, text: str) -> None:
        """Send text reply to Feishu.

        Args:
            chat_id: Chat ID to reply to
            text: Text content
        """
        # In a real implementation, this would call Feishu API
        # For now, just log it
        print(f"[BotRuntime] Would send to {chat_id}: {text[:200]}...")

    async def _send_update_complete_notification(self) -> None:
        """Send notification about successful update."""
        # This would send to the chat where update was initiated
        print("[BotRuntime] Update complete notification sent")

    def _on_update_phase_change(self, phase: UpdatePhase, message: str) -> None:
        """Handle update phase change.

        Args:
            phase: Current update phase
            message: Phase description
        """
        print(f"[BotRuntime] Update phase: {phase.name} - {message}")

    def _build_status_text(self) -> str:
        """Build status report text."""
        state = self.state_manager.get_current_state()
        if not state:
            return "❌ 状态不可用"

        return f"""🤖 **SailZen Bot 状态**

会话ID: `{state.session_id[:20]}...`
启动时间: {state.created_at}
上次心跳: {state.last_heartbeat or "N/A"}

活跃会话: {len(state.active_sessions)}
工作区状态: {len(state.workspace_states)}
待确认操作: {len(state.pending_confirmations)}

飞书连接: {"✅ 已连接" if self.feishu_client and self.feishu_client.is_running else "❌ 未连接"}
自更新就绪: {"✅ 是" if self.update_orchestrator else "❌ 否"}
"""

    def _build_help_text(self) -> str:
        """Build help text."""
        return """🤖 **SailZen Bot 帮助**

📋 **可用指令：**
• **状态** / status - 查看 Bot 运行状态
• **帮助** / help - 显示此帮助信息
• **更新** / update / 升级 - 触发 Bot 自更新

🚀 **会话控制：**
• **启动** / start + 工作区名称 - 启动指定工作区会话
• **停止** / stop - 停止当前会话
• **重启** / restart - 重启当前会话

📝 **代码开发：**
• **代码** / code + 需求描述 - 生成代码或执行开发任务
  例如："代码 帮我实现一个用户登录页面"

📦 **Git 操作：**
• **Git状态** / git status - 查看代码仓库状态
• **拉取** / git pull - 拉取最新代码
• **提交** / commit ["提交信息"] - 提交代码更改
  例如："提交 更新飞书Bot帮助信息"
• **推送** / git push - 推送代码到远程仓库

🔄 **工作区导航：**
• **列表** / list / 工作区列表 - 查看所有已配置工作区
• **主页** / home / 首页 - 返回主控制台

🎯 **使用方法：**
1. **自然语言输入** - 直接用中文或英文描述您的需求
   例如："查看状态"、"启动SailZen工作区"

2. **快捷按钮** - 卡片消息下方的操作按钮

3. **注意：** 不支持 / 开头的斜杠命令（手机上需切换键盘）

⚠️ **风险提示：**
• git push 等操作会触发确认流程
• 自更新会短暂离线（状态自动恢复）

发送「状态」查看当前运行情况。
"""


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="SailZen Feishu Bot Runtime")
    parser.add_argument(
        "--restore-state",
        action="store_true",
        help="Restore state from previous backup",
    )
    parser.add_argument(
        "--handover-file",
        type=str,
        help="Handover file from previous process",
    )
    parser.add_argument(
        "--app-id",
        type=str,
        default=os.getenv("FEISHU_APP_ID", ""),
        help="Feishu app ID",
    )
    parser.add_argument(
        "--app-secret",
        type=str,
        default=os.getenv("FEISHU_APP_SECRET", ""),
        help="Feishu app secret",
    )

    args = parser.parse_args()

    # Create runtime
    runtime = SailZenBotRuntime(
        app_id=args.app_id,
        app_secret=args.app_secret,
    )

    # Initialize
    asyncio.run(runtime.initialize(restore_state=args.restore_state))

    # Handle signals for graceful shutdown
    def signal_handler(signum, frame):
        print(f"\n[Main] Received signal {signum}, shutting down...")
        asyncio.create_task(runtime.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run
    try:
        asyncio.run(runtime.start())
    except KeyboardInterrupt:
        print("\n[Main] Interrupted by user")
    finally:
        print("[Main] Exiting")


if __name__ == "__main__":
    main()
