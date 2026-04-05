#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file bot.py
# @brief Feishu Bot Agent - Feishu <-> OpenCode Web Bridge
# @author sailing-innocent
# @date 2026-03-24
# @version 7.0
# ---------------------------------

"""Feishu Bot Agent - OpenCode Web Bridge with LLM-driven intent understanding.

Architecture (v6):
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

Configuration:
    bot/opencode.bot.yaml

Usage:
    uv run bot.py -c bot/opencode.bot.yaml
    uv run bot.py --init
"""

import argparse
from pathlib import Path
from sail.utils import read_env

read_env("prod")

from sail_bot.config import create_default_config, load_config
from sail_bot.agent import FeishuBotAgent

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Feishu OpenCode Bridge - Connect Feishu messages to OpenCode sessions"
    )
    parser.add_argument(
        "--config", "-c", default="code.bot.yaml", help="Config file path"
    )
    parser.add_argument(
        "--init", action="store_true", help="Create default config and exit"
    )
    args = parser.parse_args()

    if args.init:
        create_default_config(args.config)
        return

    if not Path(args.config).exists():
        print(f"Config not found: {args.config}")
        create_default_config(args.config)
        print(f"\nPlease edit: {args.config}")
        return

    config = load_config(args.config)
    agent = FeishuBotAgent(config)
    agent.run()


if __name__ == "__main__":
    main()
