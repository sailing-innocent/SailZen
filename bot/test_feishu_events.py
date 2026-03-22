#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test to verify Feishu event reception
Run with: uv run python scripts/test_feishu_events.py
"""

import sys
import json
from pathlib import Path


def get_config():
    """Load config."""
    if sys.platform == "win32":
        config_path = (
            Path.home() / "AppData" / "Roaming" / "feishu-agent" / "config.yaml"
        )
    else:
        config_path = Path.home() / ".config" / "feishu-agent" / "config.yaml"

    # Also check for custom config
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", default=str(config_path))
    args = parser.parse_args()
    config_path = Path(args.config)

    try:
        import yaml

        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return None


def main():
    print("=" * 60)
    print("🔍 Feishu Event Reception Test")
    print("=" * 60)
    print()

    # Load config
    config = get_config()
    if not config:
        return

    app_id = config.get("app_id", "")
    app_secret = config.get("app_secret", "")

    if not app_id or not app_secret:
        print("❌ app_id or app_secret not configured")
        return

    print(f"✅ Config loaded")
    print(f"   App ID: {app_id[:15]}...")
    print()

    # Test SDK
    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import *
    except ImportError:
        print("❌ lark-oapi not installed")
        print("   Run: uv add lark-oapi pyyaml")
        return

    print("✅ SDK imported")
    print()

    # Message counter
    msg_count = [0]

    def on_message_v2(data):
        """Handle v2.0 message event."""
        msg_count[0] += 1
        print(f"\n📨 [V2 EVENT #{msg_count[0]}] Message received!")

        try:
            if hasattr(data, "event") and data.event:
                event = data.event
                if hasattr(event, "message") and event.message:
                    msg = event.message
                    print(f"   Chat ID: {msg.chat_id}")
                    print(f"   Chat Type: {msg.chat_type}")
                    print(f"   Message Type: {msg.message_type}")

                    if msg.message_type == "text" and msg.content:
                        content = json.loads(msg.content)
                        text = content.get("text", "")
                        print(f"   Text: {text}")

                        # Auto-reply
                        reply = f"✅ Received: {text[:50]}"
                        if msg.chat_id:
                            req = (
                                CreateMessageRequest.builder()
                                .receive_id_type("chat_id")
                                .request_body(
                                    CreateMessageRequestBody.builder()
                                    .receive_id(msg.chat_id)
                                    .msg_type("text")
                                    .content(json.dumps({"text": reply}))
                                    .build()
                                )
                                .build()
                            )

                            # Send reply using a client
                            print(f"   Sending reply...")
                            # Note: We need a client to send, but let's just print for now
                else:
                    print(f"   No message in event")
            else:
                print(f"   No event in data")
                print(f"   Data type: {type(data)}")
                print(f"   Data: {data}")
        except Exception as e:
            print(f"   ⚠️ Error processing: {e}")

    def on_message_v1(data):
        """Handle v1.0 message event (fallback)."""
        msg_count[0] += 1
        print(f"\n📨 [V1 EVENT #{msg_count[0]}] Message received!")
        print(f"   Type: {type(data)}")
        try:
            print(f"   Data: {str(data)[:200]}")
        except:
            print(f"   Data: <cannot display>")

    # Build handler with BOTH v1 and v2
    print("🔧 Registering event handlers...")
    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message_v2)  # v2.0
        .register_p1_customized_event(
            "im.message.receive_v1", on_message_v1
        )  # v1.0 fallback
        .build()
    )
    print("✅ Handlers registered")
    print()

    # Create WS client
    print("🔧 Creating WebSocket client...")
    ws_client = lark.ws.Client(
        app_id,
        app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )
    print("✅ Client created")
    print()

    print("=" * 60)
    print("✅ Ready! Now:")
    print("   1. Go to Feishu")
    print("   2. Open a chat with your bot (single chat or group)")
    print("   3. Send any message")
    print("   4. You should see 'Message received!' above")
    print()
    print("   If you DON'T see messages, check:")
    print("   • Is 'im.message.receive_v1' event subscribed?")
    print("   • Is subscription mode 'long connection'?")
    print("   • Is the app published AND approved?")
    print("   • Is the bot added to the chat?")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()

    try:
        ws_client.start()
    except KeyboardInterrupt:
        print(f"\n\n👋 Stopped. Total messages received: {msg_count[0]}")


if __name__ == "__main__":
    main()
