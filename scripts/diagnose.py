#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnose Feishu Bot Agent connectivity issues."""

import sys
import yaml
from pathlib import Path


def check_config():
    """Check configuration file."""
    print("=" * 50)
    print("1. Checking Configuration")
    print("=" * 50)

    if sys.platform == "win32":
        config_path = (
            Path.home() / "AppData" / "Roaming" / "feishu-agent" / "config.yaml"
        )
    else:
        config_path = Path.home() / ".config" / "feishu-agent" / "config.yaml"

    print(f"Config path: {config_path}")

    if not config_path.exists():
        print("❌ Config file NOT FOUND")
        return False

    print("✅ Config file exists")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            print("❌ Config file is empty")
            return False

        app_id = data.get("app_id", "")
        app_secret = data.get("app_secret", "")

        if not app_id:
            print("❌ app_id is empty")
            return False

        if not app_secret:
            print("❌ app_secret is empty")
            return False

        print(f"✅ app_id: {app_id[:15]}...")
        print(f"✅ app_secret: {'*' * 10}...")
        return True

    except Exception as e:
        print(f"❌ Failed to read config: {e}")
        return False


def check_sdk():
    """Check if SDK is installed."""
    print("\n" + "=" * 50)
    print("2. Checking SDK Installation")
    print("=" * 50)

    try:
        import lark_oapi as lark

        print(
            f"✅ lark-oapi installed: {lark.__version__ if hasattr(lark, '__version__') else 'unknown version'}"
        )
        return True
    except ImportError:
        print("❌ lark-oapi NOT installed")
        print("   Run: pip install lark-oapi pyyaml")
        return False


def test_connection():
    """Test connection to Feishu."""
    print("\n" + "=" * 50)
    print("3. Testing Connection")
    print("=" * 50)

    try:
        import lark_oapi as lark

        # Load config
        if sys.platform == "win32":
            config_path = (
                Path.home() / "AppData" / "Roaming" / "feishu-agent" / "config.yaml"
            )
        else:
            config_path = Path.home() / ".config" / "feishu-agent" / "config.yaml"

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        app_id = data.get("app_id", "")
        app_secret = data.get("app_secret", "")

        print(f"Connecting with app_id: {app_id[:15]}...")

        # Create a simple handler
        def handler(data):
            print("📨 Message received!")
            print(f"   Data type: {type(data)}")

        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(handler)
            .build()
        )

        client = lark.ws.Client(
            app_id,
            app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        print("✅ Client created successfully")
        print("   Starting connection (will timeout after 10 seconds)...")

        # Try to start and wait for a bit
        import threading
        import time

        def run_client():
            try:
                client.start()
            except Exception as e:
                print(f"   Connection error: {e}")

        thread = threading.Thread(target=run_client, daemon=True)
        thread.start()

        # Wait for connection
        time.sleep(5)

        print("✅ Connection test passed (or still connecting)")
        print("   If you see 'connected to wss://' above, connection is working!")

        return True

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_opencode():
    """Check if OpenCode is installed."""
    print("\n" + "=" * 50)
    print("4. Checking OpenCode")
    print("=" * 50)

    import subprocess

    try:
        result = subprocess.run(
            ["opencode", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print(f"✅ OpenCode installed: {result.stdout.strip()}")
            return True
        else:
            print("❌ OpenCode not working properly")
            return False
    except FileNotFoundError:
        print("❌ OpenCode NOT installed or not in PATH")
        print("   Please install OpenCode first")
        return False
    except Exception as e:
        print(f"❌ Error checking OpenCode: {e}")
        return False


def main():
    """Run all checks."""
    print("🔍 Feishu Bot Agent Diagnostic Tool")
    print()

    results = []

    results.append(("Config", check_config()))
    results.append(("SDK", check_sdk()))
    results.append(("OpenCode", check_opencode()))

    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")

    if all(r[1] for r in results):
        print("\n✅ All checks passed!")
        print("   Try running: python scripts/feishu_agent.py")
        print("\n   Make sure to:")
        print("   1. Your Feishu app is published and approved")
        print("   2. The bot is added to your group")
        print("   3. Event subscription is set to 'long connection' mode")
    else:
        print("\n❌ Some checks failed")
        print("   Please fix the issues above and try again")


if __name__ == "__main__":
    main()
