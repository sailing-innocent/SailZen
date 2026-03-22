#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file echo_bot.py
# @brief Feishu Echo Bot - Configuration-based example
# @author sailing-innocent
# @date 2026-03-21
# @version 2.0
# ---------------------------------
"""Feishu Echo Bot Example with Configuration File

This is a simple echo bot that demonstrates the configuration-based approach.
It reads all settings from a config file instead of environment variables.

Usage:
    1. Create config file: python echo_bot.py --init
    2. Edit config: ~/.config/feishu-agent/config.yaml
    3. Run: python echo_bot.py

Configuration file format:
    app_id: "cli_xxxxxxxx"
    app_secret: "xxxxxxxxxxxxxxxx"
"""

import os
import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import Optional

# Feishu SDK
try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import *
except ImportError:
    print("❌ Error: lark-oapi not installed")
    print("   Install: pip install lark-oapi pyyaml")
    sys.exit(1)


def get_default_config_path() -> str:
    """Get default config path."""
    if sys.platform == "win32":
        return str(Path.home() / "AppData" / "Roaming" / "feishu-agent" / "config.yaml")
    else:
        return str(Path.home() / ".config" / "feishu-agent" / "config.yaml")


def load_config(config_path: str) -> tuple[str, str]:
    """Load Feishu credentials from config file."""
    if not Path(config_path).exists():
        return "", ""

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data:
            return data.get("app_id", ""), data.get("app_secret", "")
    except Exception as e:
        print(f"⚠️ Warning: Failed to load config: {e}")

    return "", ""


def create_default_config(config_path: str) -> None:
    """Create default config file."""
    config_dir = Path(config_path).parent
    config_dir.mkdir(parents=True, exist_ok=True)

    default_content = """# Feishu Agent Configuration
# Save as: ~/.config/feishu-agent/config.yaml

# Feishu App Credentials (Required)
# Get from: https://open.feishu.cn/app
app_id: ""
app_secret: ""
"""

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(default_content)

    print(f"✅ Created default config: {config_path}")
    print("   Please edit and add your Feishu credentials.")


def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    """Handle received message - echo back."""
    # Parse message content
    if data.event.message.message_type == "text":
        received_text = json.loads(data.event.message.content)["text"]
    else:
        received_text = "[Non-text message]"

    # Prepare response
    response_text = (
        f"🤖 Echo Bot received:\n"
        f"━━━━━━━━━━━━━━\n"
        f"{received_text}\n"
        f"━━━━━━━━━━━━━━\n"
        f"This is an echo response from Feishu Bot"
    )

    content = json.dumps({"text": response_text})

    # Send response based on chat type
    if data.event.message.chat_type == "p2p":
        # Private chat - send message
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(data.event.message.chat_id)
                .msg_type("text")
                .content(content)
                .build()
            )
            .build()
        )
        response = client.im.v1.message.create(request)

        if not response.success():
            print(f"⚠️ Failed to send message: {response.msg}")
    else:
        # Group chat - reply to message
        request = (
            ReplyMessageRequest.builder()
            .message_id(data.event.message.message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type("text")
                .build()
            )
            .build()
        )
        response = client.im.v1.message.reply(request)

        if not response.success():
            print(f"⚠️ Failed to reply: {response.msg}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Feishu Echo Bot - Configuration-based example"
    )
    parser.add_argument(
        "--config", "-c", default=get_default_config_path(), help="Config file path"
    )
    parser.add_argument(
        "--init", action="store_true", help="Create default config file"
    )

    args = parser.parse_args()

    # Init mode
    if args.init:
        create_default_config(args.config)
        return

    # Check config exists
    if not Path(args.config).exists():
        print("❌ Config file not found")
        create_default_config(args.config)
        print(f"\nPlease edit: {args.config}")
        return

    # Load credentials
    app_id, app_secret = load_config(args.config)

    if not app_id or not app_secret:
        print("❌ Feishu credentials not configured")
        print(f"Please edit: {args.config}")
        print("\nRequired:")
        print("  app_id: cli_xxxxxxxx")
        print("  app_secret: xxxxxxxxxx")
        return

    print("🚀 Feishu Echo Bot")
    print(f"   Config: {args.config}")
    print("   Starting...")
    print()

    # Create event handler
    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
        .build()
    )

    # Create clients
    global client
    client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    ws_client = lark.ws.Client(
        app_id,
        app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )

    print("✅ Ready - Listening for messages")
    print("   (Ctrl+C to stop)")
    print()

    try:
        ws_client.start()
    except KeyboardInterrupt:
        print("\n👋 Stopped")


if __name__ == "__main__":
    main()
