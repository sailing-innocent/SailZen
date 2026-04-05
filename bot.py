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

import asyncio
import os
import sys
import json
import re
import yaml
import time
import argparse
from pathlib import Path
from sail.utils import read_env

read_env("prod")

import threading
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque


import httpx

from card_renderer import (
    CardMessageTracker,
    CardRenderer,
    card_to_feishu_content,
    text_fallback,
)
from session_state import (
    ActiveOperation,
    ConfirmationManager,
    OperationTracker,
    PendingAction,
    RiskLevel,
    SessionHealthMonitor,
    SessionState,
    SessionStateStore,
    classify_risk,
)
from session_manager import (
    ManagedSession,
    OpenCodeSessionManager,
    extract_path_from_text,
    resolve_path,
)

# 导入任务历史记录器

from task_logger import task_logger


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
