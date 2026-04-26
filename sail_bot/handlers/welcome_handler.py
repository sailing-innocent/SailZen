# -*- coding: utf-8 -*-
# @file welcome_handler.py
# @brief Welcome handler for new P2P chat users
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Welcome handler for bot_p2p_chat_entered_v1 events.

This module handles the welcome flow when a user enters a P2P chat with the bot.
"""

from typing import Any, Dict
from pathlib import Path

from sail_bot.handlers.base import BaseHandler, HandlerContext
from sail.feishu_card_kit.renderer import CardRenderer


class WelcomeHandler(BaseHandler):
    """Handler for welcome messages when users enter P2P chat."""

    def handle(self, chat_id: str) -> None:
        """Send welcome card to the new chat.

        Args:
            chat_id: The chat ID of the P2P conversation
        """
        try:
            print(f"[WelcomeHandler] Sending welcome card to {chat_id}")

            # Collect session states from process manager
            session_states: Dict[str, str] = {}
            proc_map = {p.path: p for p in self.ctx.process_mgr.list_processes()}
            for proj in self.ctx.config.projects:
                path = proj.get("path", "")
                if path:
                    try:
                        resolved_path = str(Path(path).expanduser().resolve())
                    except Exception:
                        resolved_path = path

                    proc = proc_map.get(resolved_path)
                    if proc:
                        session_states[path] = proc.status.value
                    else:
                        session_states[path] = "idle"

            # Generate welcome card
            welcome_card = CardRenderer.welcome(
                projects=self.ctx.config.projects,
                session_states=session_states,
                has_llm=self.ctx.brain._gw is not None,
                has_self_update=True,
            )

            # Send welcome card
            self.ctx.messaging.send_card(chat_id, welcome_card)
            print(f"[WelcomeHandler] Welcome card sent to {chat_id}")

        except Exception as exc:
            print(f"[WelcomeHandler] Error sending welcome card: {exc}")
            import traceback
            traceback.print_exc()
