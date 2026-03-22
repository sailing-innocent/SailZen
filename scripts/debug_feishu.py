#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug script for Feishu Bot Agent
Run with: uv run python scripts/debug_feishu.py
"""

import os
import sys
import json
import yaml
from pathlib import Path


def get_config_path():
    """Get config file path."""
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Roaming" / "feishu-agent" / "config.yaml"
    else:
        return Path.home() / ".config" / "feishu-agent" / "config.yaml"


def main():
    print("=" * 60)
    print("🔍 Feishu Bot Agent Debug Tool")
    print("=" * 60)
    print()

    # 1. Check config
    print("1️⃣  Checking Configuration...")
    config_path = get_config_path()
    print(f"   Config path: {config_path}")

    if not config_path.exists():
        print("   ❌ Config file NOT FOUND")
        print(f"   Create it with: uv run python scripts/feishu_agent.py --init")
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        app_id = data.get("app_id", "").strip() if data else ""
        app_secret = data.get("app_secret", "").strip() if data else ""

        if not app_id or app_id == '""' or app_id == "''":
            print("   ❌ app_id is empty!")
            print("   Edit the config file and add your Feishu App ID")
            return

        if not app_secret or app_secret == '""' or app_secret == "''":
            print("   ❌ app_secret is empty!")
            print("   Edit the config file and add your Feishu App Secret")
            return

        print(f"   ✅ Config file exists")
        print(f"   ✅ app_id: {app_id[:20]}...")
        print(f"   ✅ app_secret: {'*' * min(len(app_secret), 10)}...")
    except Exception as e:
        print(f"   ❌ Error reading config: {e}")
        return

    print()
    print("2️⃣  Testing Connection...")

    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import *

        # Test message counter
        message_count = [0]

        def on_message(data):
            message_count[0] += 1
            print(f"\n   📨 Message #{message_count[0]} received!")

            try:
                if hasattr(data, "event") and hasattr(data.event, "message"):
                    msg = data.event.message
                    print(
                        f"   Chat ID: {msg.chat_id[:20] if msg.chat_id else 'None'}..."
                    )
                    print(f"   Message Type: {msg.message_type}")

                    if msg.message_type == "text" and msg.content:
                        content = json.loads(msg.content)
                        text = content.get("text", "")
                        print(f"   Text: {text[:50]}...")

                        # Send reply
                        reply_text = (
                            f"✅ Debug: Received your message!\nContent: {text[:100]}"
                        )

                        if msg.chat_id:
                            request = (
                                CreateMessageRequest.builder()
                                .receive_id_type("chat_id")
                                .request_body(
                                    CreateMessageRequestBody.builder()
                                    .receive_id(msg.chat_id)
                                    .msg_type("text")
                                    .content(json.dumps({"text": reply_text}))
                                    .build()
                                )
                                .build()
                            )

                            # Note: We can't easily send from here without the client
                            print(f"   Would reply: {reply_text[:50]}...")
                else:
                    print(f"   Data structure: {type(data)}")
                    print(f"   Data: {data}")
            except Exception as e:
                print(f"   ⚠️ Error processing message: {e}")

        # Create event handler
        print("   Creating event handler...")
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(on_message)
            .build()
        )

        # Create client
        print("   Creating WebSocket client...")
        client = lark.ws.Client(
            app_id,
            app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.DEBUG,
        )

        print("   ✅ Client created successfully")
        print()
        print("3️⃣  Starting connection...")
        print("   Waiting for messages from Feishu...")
        print("   Go to your Feishu group and @ the bot!")
        print("   Press Ctrl+C to stop")
        print()

        client.start()

    except ImportError:
        print("   ❌ lark-oapi not installed")
        print("   Run: uv add lark-oapi pyyaml")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
