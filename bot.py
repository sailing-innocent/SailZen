#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file bot.py
# @brief Feishu Bot Agent - Feishu <-> OpenCode Web Bridge
# @author sailing-innocent
# @date 2026-04-06
# @version 7.1
# ---------------------------------
"""Feishu Bot Agent - OpenCode Web Bridge with LLM-driven intent understanding.

Architecture (v7):
  Feishu Message
      ↓ (lark long-connection SDK)
  FeishuBotAgent._handle_message()
      ↓
  BotBrain.think(text, context)     ← LLM intent recognition + confirmation logic
      ↓
  ActionPlan (action, params, needs_confirm)
      ↓ (if needs_confirm: return confirmation prompt, await next message)
  Execute action → OpenCodeSessionManager / status / help
      ↓
  FeishuBotAgent._reply_to_message()   ← lark SDK REST reply

Self-Update:
  When running under bot_watcher.py, bot exits with code 42 to signal restart.
  The watcher then performs git pull and restarts the bot.

Configuration:
    bot/opencode.bot.yaml

Usage:
    # Run directly (no self-update support)
    uv run bot.py -c bot/opencode.bot.yaml

    # Run with watcher (supports self-update)
    uv run bot_watcher.py -c bot/opencode.bot.yaml
"""

import argparse
import sys
from pathlib import Path
from sail.utils import read_env

read_env("prod")

from sail_bot.config import create_default_config, load_config
from sail_bot.agent import FeishuBotAgent

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Main entry point.

    Returns:
        Exit code: 0 for normal exit, 42 for self-update restart
    """
    parser = argparse.ArgumentParser(
        description="Feishu OpenCode Bridge - Connect Feishu messages to OpenCode sessions"
    )
    parser.add_argument(
        "--config", "-c", default="code.bot.yaml", help="Config file path"
    )
    parser.add_argument(
        "--init", action="store_true", help="Create default config and exit"
    )
    parser.add_argument(
        "--restore-state",
        action="store_true",
        help="Restore state from backup (internal use)",
    )
    args = parser.parse_args()

    if args.init:
        create_default_config(args.config)
        return 0

    if not Path(args.config).exists():
        print(f"Config not found: {args.config}")
        create_default_config(args.config)
        print(f"\nPlease edit: {args.config}")
        return 1

    config = load_config(args.config)
    agent = FeishuBotAgent(config)
    exit_code = agent.run()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
