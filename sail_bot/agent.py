# -*- coding: utf-8 -*-
# @file agent.py
# @brief Feishu Bot Agent - Main entry point (v3.0 refactored)
# @author sailing-innocent
# @date 2026-04-25
# @version 3.0
# ---------------------------------
"""Feishu Bot Agent - Main entry point.

v3.0: 使用 sail.opencode 基础设施层，精简 self-update，
移除对 async_task_manager / session_manager / opencode_client 的直接依赖。

协调组件:
- Message handling (via MessageHandler)
- Card action handling (via CardActionHandler)
- Plan execution (via PlanExecutor)
- Lifecycle management (via LifecycleManager)
- Process management (via sail.opencode.OpenCodeProcessManager)
- Self-update (via SelfUpdateOrchestrator, exit code 42)
"""

from pathlib import Path
from typing import Optional, Dict, Any
import json
import threading
import traceback
import logging
from datetime import datetime

import lark_oapi as lark

from sail_bot.self_update_orchestrator import SelfUpdateOrchestrator
from sail_bot.config import AgentConfig
from sail_bot.session_state import (
    ConfirmationManager,
    OperationTracker,
    SessionState,
    SessionStateStore,
)
from sail_bot.brain import BotBrain
from sail_bot.context import ConversationContext
from sail_bot.messaging import FeishuMessagingClient
from sail_bot.handlers import (
    HandlerContext,
    MessageHandler,
    CardActionHandler,
    PlanExecutor,
    LifecycleManager,
    WelcomeHandler,
)
from sail.opencode import OpenCodeProcessManager, check_health_sync

logger = logging.getLogger(__name__)


class FeishuBotAgent:
    """Feishu bot that bridges messages to OpenCode web sessions."""

    from sail_bot.paths import CONTEXTS_FILE

    CONTEXT_STATE_FILE = CONTEXTS_FILE

    def __init__(self, config: AgentConfig):
        self.config = config

        # State management
        self.state_store = SessionStateStore()
        self.state_store.load_from_disk()

        # Process management (replaces old OpenCodeSessionManager)
        self.process_mgr = OpenCodeProcessManager(
            base_port=config.base_port,
            projects=config.projects,
            cli_tool=config.cli_tool,
        )

        self.op_tracker = OperationTracker()
        self.confirm_mgr = ConfirmationManager()

        # Messaging client
        self.messaging = FeishuMessagingClient(default_chat_id=config.default_chat_id)
        self.lark_client: Optional[lark.Client] = None

        # AI brain
        self.brain = BotBrain(
            config.projects,
            llm_provider=config.llm_provider,
            llm_api_key=config.llm_api_key,
        )

        # Conversation contexts
        self._contexts: Dict[str, ConversationContext] = {}
        self._load_contexts()

        # Self-update orchestrator (simplified)
        self._update_orchestrator = SelfUpdateOrchestrator()

        # Create handler context
        self._handler_ctx = HandlerContext(
            messaging=self.messaging,
            process_mgr=self.process_mgr,
            state_store=self.state_store,
            op_tracker=self.op_tracker,
            confirm_mgr=self.confirm_mgr,
            brain=self.brain,
            config=self.config,
            agent=self,
        )

        # Initialize handlers
        self._message_handler = MessageHandler(self._handler_ctx)
        self._card_action_handler = CardActionHandler(self._handler_ctx)
        self._plan_executor = PlanExecutor(self._handler_ctx)
        self._lifecycle = LifecycleManager(self)
        self._welcome_handler = WelcomeHandler(self._handler_ctx)

        logger.info("FeishuBotAgent initialized (v3.0)")

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------

    def _get_context(self, chat_id: str) -> ConversationContext:
        if chat_id not in self._contexts:
            self._contexts[chat_id] = ConversationContext(chat_id=chat_id)
        ctx = self._contexts[chat_id]
        if ctx.is_pending_expired():
            ctx.clear_pending()
        return ctx

    def _load_contexts(self) -> None:
        if not self.CONTEXT_STATE_FILE.exists():
            return
        try:
            with open(self.CONTEXT_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            reset_count = 0
            for item in data:
                chat_id = item.get("chat_id", "")
                if not chat_id:
                    continue
                ctx = ConversationContext.from_dict(item)

                # Validate active_workspace against running processes
                if ctx.active_workspace:
                    procs = {p.path: p for p in self.process_mgr.list_processes()}
                    proc = procs.get(ctx.active_workspace)
                    if not proc or not proc.is_alive:
                        logger.warning(
                            "Resetting context for %s: workspace not running", chat_id
                        )
                        ctx.mode = "idle"
                        ctx.active_workspace = None
                        reset_count += 1

                self._contexts[chat_id] = ctx

            if self._contexts:
                logger.info("Loaded %s conversation(s)", len(self._contexts))
            if reset_count > 0:
                logger.warning(
                    "Reset %s context(s) due to missing connection", reset_count
                )
        except Exception as exc:
            logger.error("Failed to load contexts: %s", exc, exc_info=True)

    def _save_contexts(self) -> None:
        try:
            self.CONTEXT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [
                ctx.to_dict()
                for chat_id, ctx in self._contexts.items()
                if ctx.active_workspace or ctx.mode != "idle"
            ]
            with open(self.CONTEXT_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error("Failed to save contexts: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_message(self, data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        try:
            if not data or not data.event or not data.event.message:
                return
            message = data.event.message
            if message.message_type != "text":
                return
            self._message_handler.handle(data)
        except Exception as exc:
            logger.error("Message handling error: %s", exc, exc_info=True)

    def _handle_card_action(self, data) -> Any:
        try:
            return self._card_action_handler.handle(data)
        except Exception as exc:
            logger.error("Card action error: %s", exc, exc_info=True)
            return None

    def _handle_p2p_chat_entered(
        self, data: lark.im.v1.P2ImChatAccessEventBotP2pChatEnteredV1
    ) -> None:
        try:
            if not data or not data.event:
                return
            chat_id = data.event.chat_id
            if chat_id:
                logger.info("User entered P2P chat: %s", chat_id)
                self._welcome_handler.handle(chat_id)
        except Exception as exc:
            logger.error("P2P chat entered error: %s", exc, exc_info=True)

    def _check_and_notify_update_completion(self) -> None:
        """检查是否有待完成的更新通知，并在 Bot 重启后发送完成消息。

        这是 self-update 流程的最后一步：当 watcher 执行 git pull 并重启 Bot 后，
        新进程会读取持久化的更新上下文，向用户发送更新已完成的消息。
        """
        try:
            pending = SelfUpdateOrchestrator.load_and_clear_pending_update()
            if not pending:
                return

            chat_id = pending.get("chat_id")
            reason = pending.get("reason", "")
            if not chat_id:
                logger.warning("[UpdateNotify] Pending update has no chat_id")
                return

            # Build completion message card
            from sail.feishu_card_kit.renderer import CardRenderer
            import platform
            from datetime import datetime

            hostname = platform.node() or "Unknown"
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            content = (
                f"🤖 Bot 已成功重启并恢复服务\n\n"
                f"📍 **主机**: {hostname}\n"
                f"🕐 **完成时间**: {now}\n"
            )
            if reason:
                content += f"📝 **更新原因**: {reason}\n"
            content += "\n✅ 更新流程全部完成"

            completion_card = CardRenderer.result(
                "🎉 更新完成",
                content,
                success=True,
            )
            self.messaging.send_card(chat_id, completion_card)
            logger.info(
                "[UpdateNotify] Update completion notification sent to %s", chat_id
            )

        except Exception as exc:
            logger.error(
                "[UpdateNotify] Failed to send update completion notification: %s",
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Start the bot and return exit code.

        Returns:
            0: normal exit
            42: self-update restart (watcher will git pull + restart)
        """
        self._lifecycle.cleanup_previous_instances()

        print(f"Feishu Agent Bridge v8.0 (tool={config.cli_tool})")
        logger.info("Config: %s", self.config.config_path)

        if not self.config.app_id or not self.config.app_secret:
            logger.error("Feishu credentials not configured")
            return 1

        logger.info("App ID: %s...", self.config.app_id[:10])
        if self.config.projects:
            slugs = [p.get("slug", "") for p in self.config.projects]
            logger.info("Projects: %s", ", ".join(slugs))

        # Startup
        self._lifecycle.on_startup()

        # Initialize Lark client
        self.lark_client = (
            lark.Client.builder()
            .app_id(self.config.app_id)
            .app_secret(self.config.app_secret)
            .build()
        )
        self.messaging.set_client(self.lark_client)

        # Setup event handlers
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_message)
            .register_p2_card_action_trigger(self._handle_card_action)
            .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(
                self._handle_p2p_chat_entered
            )
            .build()
        )

        ws_client = lark.ws.Client(
            self.config.app_id,
            self.config.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        logger.info("Connecting to Feishu (long connection)...")
        logger.info("Send '帮助' in Feishu to see available commands.")

        # Send startup notification
        self._lifecycle._notify_startup()

        # Check for pending update completion (from self-update restart)
        self._check_and_notify_update_completion()

        exit_code = 0
        shutdown_event = threading.Event()

        # Start ws_client in a separate thread (blocking call)
        ws_thread = threading.Thread(target=ws_client.start, daemon=True)
        ws_thread.start()

        try:
            while not shutdown_event.is_set():
                if self._update_orchestrator.should_exit():
                    logger.warning("Self-update requested, shutting down...")
                    break
                shutdown_event.wait(0.1)
        except KeyboardInterrupt:
            logger.info("Stopped by user")
        except Exception as exc:
            logger.error("Fatal error: %s", exc, exc_info=True)
            exit_code = 1
        finally:
            if hasattr(ws_client, "stop"):
                ws_client.stop()
            self._lifecycle.on_shutdown()

            if self._update_orchestrator.should_exit():
                exit_code = self._update_orchestrator.exit_code
                logger.info("Exiting with code %s for self-update", exit_code)

        return exit_code
