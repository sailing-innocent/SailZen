# -*- coding: utf-8 -*-
# @file agent.py
# @brief Feishu Bot Agent - Main entry point
# @author sailing-innocent
# @date 2026-04-06
# @version 2.0
# ---------------------------------
"""Feishu Bot Agent - Main entry point.

This module provides a thin wrapper that coordinates:
- Message handling (via MessageHandler)
- Card action handling (via CardActionHandler)
- Plan execution (via PlanExecutor)
- Lifecycle management (via LifecycleManager)

All business logic has been extracted to handlers/ modules.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import json
import sys
import threading
import traceback
import logging
from datetime import datetime

import lark_oapi as lark
from sail_bot.bot_state_manager import (
    get_state_manager,
)
from sail_bot.self_update_orchestrator import (
    SelfUpdateOrchestrator,
    UpdateTriggerSource,
)

from sail_bot.config import AgentConfig
from sail_bot.session_state import (
    ConfirmationManager,
    OperationTracker,
    SessionHealthMonitor,
    SessionState,
    SessionStateStore,
)
from sail_bot.session_manager import OpenCodeSessionManager
from sail_bot.brain import BotBrain
from sail_bot.context import ConversationContext
from sail_bot.async_task_manager import task_manager

from sail_bot.messaging import FeishuMessagingClient
from sail_bot.handlers import (
    HandlerContext,
    MessageHandler,
    CardActionHandler,
    PlanExecutor,
    LifecycleManager,
    WelcomeHandler,
)


logger = logging.getLogger(__name__)


class FeishuBotAgent:
    """Feishu bot that bridges messages to OpenCode web sessions."""
    
    from sail_bot.paths import CONTEXTS_FILE
    
    CONTEXT_STATE_FILE = CONTEXTS_FILE
    
    def __init__(self, config: AgentConfig):
        self.config = config

        # Initialize state and session management
        self.state_store = SessionStateStore()
        self.state_store.load_from_disk()

        self.session_mgr = OpenCodeSessionManager(
            config.base_port, state_store=self.state_store
        )
        self.op_tracker = OperationTracker()
        self.confirm_mgr = ConfirmationManager()

        # Initialize messaging client
        self.messaging = FeishuMessagingClient()
        self.lark_client: Optional[lark.Client] = None

        # Initialize AI brain
        self.brain = BotBrain(
            config.projects,
            llm_provider=config.llm_provider,
            llm_api_key=config.llm_api_key,
        )

        # Initialize conversation contexts
        self._contexts: Dict[str, ConversationContext] = {}
        self._load_contexts()

        # Initialize health monitor
        self._health_monitor = SessionHealthMonitor(
            self.state_store,
            health_check_fn=self._health_check_fn,
            auto_restart=config.auto_restart,
        )
        self.state_store.register_hook(self._on_state_change)

        # Initialize self-update support
        self._self_update_enabled = True
        self._state_manager: Optional[Any] = None
        self._update_orchestrator: Optional[Any] = None
        self._ws_client: Optional[Any] = None
        self._init_self_update()

        # Create handler context
        self._handler_ctx = HandlerContext(
            messaging=self.messaging,
            session_mgr=self.session_mgr,
            state_store=self.state_store,
            op_tracker=self.op_tracker,
            confirm_mgr=self.confirm_mgr,
            brain=self.brain,
            config=self.config,
            self_update_enabled=self._self_update_enabled,
            agent=self,
        )

        # Initialize handlers
        self._message_handler = MessageHandler(self._handler_ctx)
        self._card_action_handler = CardActionHandler(self._handler_ctx)
        self._plan_executor = PlanExecutor(self._handler_ctx)
        self._lifecycle = LifecycleManager(self)
        self._welcome_handler = WelcomeHandler(self._handler_ctx)

        # Start async task manager
        task_manager.start()
        logger.info("Async task manager started")

    def _init_self_update(self) -> None:
        """Initialize self-update functionality."""
        if not self._self_update_enabled:
            return

        try:
            self._state_manager = get_state_manager()
            self._state_manager.initialize_session()

            # Check for handover from previous instance
            handover_data = SelfUpdateOrchestrator.check_for_handover()
            if handover_data:
                logger.info(
                    "Detected handover from PID %s", handover_data.get("old_pid")
                )
                self._state_manager.restore_from_backup(
                    Path(handover_data.get("backup_path"))
                    if handover_data.get("backup_path")
                    else None
                )

            logger.info(
                "Initialized (session: %s...)",
                self._state_manager.get_current_state().session_id[:16],
            )
        except Exception as exc:
            logger.error("Initialization failed: %s", exc, exc_info=True)
            self._self_update_enabled = False

    async def request_self_update(
        self,
        trigger_source: str = "manual",
        reason: str = "User requested update",
        initiated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request a self-update of the bot."""
        if not self._self_update_enabled or not self._state_manager:
            return {"success": False, "error": "Self-update not available"}

        try:
            if not self._update_orchestrator:
                self._update_orchestrator = SelfUpdateOrchestrator(
                    state_manager=self._state_manager,
                    feishu_client=self._ws_client,
                    workspace_root=Path(__file__).parent.parent,
                )

            source_map = {
                "manual": UpdateTriggerSource.MANUAL_COMMAND,
                "opencode": UpdateTriggerSource.OPENCODE_SESSION,
                "scheduled": UpdateTriggerSource.SCHEDULED,
            }
            source = source_map.get(trigger_source, UpdateTriggerSource.MANUAL_COMMAND)

            result = await self._update_orchestrator.initiate_self_update(
                trigger_source=source,
                reason=reason,
                initiated_by=initiated_by,
            )

            return {
                "success": result.success,
                "phase": result.phase.name
                if hasattr(result.phase, "name")
                else str(result.phase),
                "message": result.message,
                "backup_path": str(result.backup_path) if result.backup_path else None,
                "error": result.error,
            }
        except Exception as exc:
            return {"success": False, "error": f"Self-update failed: {exc}"}

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------

    def _get_context(self, chat_id: str) -> ConversationContext:
        """Get or create conversation context."""
        if chat_id not in self._contexts:
            self._contexts[chat_id] = ConversationContext(chat_id=chat_id)
        ctx = self._contexts[chat_id]
        if ctx.is_pending_expired():
            ctx.clear_pending()
        return ctx

    def _load_contexts(self) -> None:
        """Load conversation contexts from disk."""
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

                # Validate active_workspace
                if ctx.active_workspace:
                    session = self.session_mgr._sessions.get(ctx.active_workspace)
                    port = session.port if session else None
                    if not port:
                        entry = self.state_store.get(ctx.active_workspace)
                        port = entry.port if entry else None

                    if not port or not self.session_mgr._is_port_open(port):
                        logger.warning(
                            "Resetting context for %s: not connected", chat_id
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
        """Save conversation contexts to disk."""
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
        """Handle incoming Feishu message."""
        try:
            if not data or not data.event or not data.event.message:
                return

            message = data.event.message
            if message.message_type != "text":
                return

            content = json.loads(message.content or "{}")
            text = content.get("text", "").strip()
            chat_id = message.chat_id
            message_id = message.message_id

            if not text or not chat_id:
                return

            # Delegate to message handler
            from sail_bot.handlers.message_handler import MessageHandler

            handler = MessageHandler(self._handler_ctx)
            handler.handle(data)

        except Exception as exc:
            logger.error("Message handling error: %s", exc, exc_info=True)
            traceback.print_exc()

    def _handle_card_action(self, data) -> Any:
        """Handle card button click actions."""
        try:
            return self._card_action_handler.handle(data)
        except Exception as exc:
            logger.error("Card action error: %s", exc, exc_info=True)
            traceback.print_exc()
            return None

    def _handle_p2p_chat_entered(
        self, data: lark.im.v1.P2ImChatAccessEventBotP2pChatEnteredV1
    ) -> None:
        """Handle P2P chat entered event (user starts chat with bot)."""
        try:
            if not data or not data.event:
                return

            chat_id = data.event.chat_id
            if not chat_id:
                return

            logger.info("User entered P2P chat: %s", chat_id)

            # Send welcome card
            self._welcome_handler.handle(chat_id)

        except Exception as exc:
            logger.error("P2P chat entered handling error: %s", exc, exc_info=True)
            traceback.print_exc()

    def _health_check_fn(self, path: str, port: int) -> bool:
        """Health check function for sessions."""
        from sail_bot.opencode_client import OpenCodeSessionClient

        client = OpenCodeSessionClient(port=port)
        return client.is_healthy()

    def _on_state_change(
        self, path: str, prev: SessionState, next_state: SessionState, entry: Any
    ) -> None:
        """Handle session state changes."""
        if next_state == SessionState.ERROR:
            session = self.session_mgr._sessions.get(path)
            chat_id = (session.chat_id if session else None) or getattr(
                entry, "chat_id", None
            )
            if chat_id:
                from sail_bot.card_renderer import CardRenderer

                card = CardRenderer.session_status(
                    path=path,
                    state="error",
                    last_error=getattr(entry, "last_error", None) or "会话异常终止",
                    activities=entry.recent_activities()
                    if hasattr(entry, "recent_activities")
                    else [],
                )
                self.messaging.send_card(
                    chat_id, card, "session_status", {"path": path}
                )

    # ------------------------------------------------------------------
    # Messaging (delegated to messaging client)
    # ------------------------------------------------------------------

    def _send_to_chat(self, chat_id: str, text: str) -> bool:
        """Send a text message to a Feishu chat."""
        return self.messaging.send_text(chat_id, text)

    def _reply_to_message(self, message_id: str, text: str) -> bool:
        """Reply to a specific Feishu message."""
        return self.messaging.reply_text(message_id, text)

    def _send_card(
        self,
        chat_id: str,
        card: dict,
        card_type: str = "",
        context: Optional[dict] = None,
    ) -> Optional[str]:
        """Send an interactive card to a chat."""
        return self.messaging.send_card(chat_id, card, card_type, context)

    def _reply_card(
        self,
        message_id: str,
        card: dict,
        card_type: str = "",
        context: Optional[dict] = None,
    ) -> Optional[str]:
        """Reply with an interactive card."""
        return self.messaging.reply_card(message_id, card, card_type, context)

    def _update_card(self, message_id: str, card: dict) -> bool:
        """Update an existing card message."""
        return self.messaging.update_card(message_id, card)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Start the bot and return exit code.

        Returns:
            Exit code: 0 for normal exit, 42 for self-update restart
        """
        # Cleanup previous instances
        self._lifecycle.cleanup_previous_instances()

        print("Feishu OpenCode Bridge v7.0")
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

        self._ws_client = lark.ws.Client(
            self.config.app_id,
            self.config.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        self._health_monitor.start()

        logger.info("Connecting to Feishu (long connection)...")
        logger.info("Send '帮助' in Feishu to see available commands.")
        logger.info("(Ctrl+C to stop)")

        # Send startup notification
        self._lifecycle._notify_startup()

        exit_code = 0
        self._shutdown_event = threading.Event()

        # Start ws_client in a separate thread since it's blocking
        ws_thread = threading.Thread(target=self._ws_client.start)
        ws_thread.daemon = True
        ws_thread.start()

        try:
            # Wait for shutdown signal (from self-update or user interrupt)
            while not self._shutdown_event.is_set():
                if (
                    self._update_orchestrator
                    and self._update_orchestrator.should_exit()
                ):
                    logger.warning("Self-update requested, shutting down...")
                    break
                # Check every 100ms
                self._shutdown_event.wait(0.1)
        except KeyboardInterrupt:
            logger.info("Stopped by user")
            exit_code = 0
        except Exception as exc:
            logger.error("Fatal error: %s", exc, exc_info=True)
            traceback.print_exc()
            exit_code = 1
        finally:
            # Signal ws_client to stop
            if hasattr(self._ws_client, "stop"):
                self._ws_client.stop()

            self._lifecycle.on_shutdown()

            # Check if we should exit with special code for self-update
            if self._update_orchestrator and self._update_orchestrator.should_exit():
                exit_code = self._update_orchestrator.get_exit_code()
                logger.info("Exiting with code %s for self-update", exit_code)

        return exit_code
