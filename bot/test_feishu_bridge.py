#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script for Feishu-OpenCode Bridge MVP."""

import json
import httpx
import sys

BASE_URL = "http://localhost:1974/api/v1"


def test_webhook():
    """Test Feishu webhook endpoint."""
    print("Testing Feishu Webhook...")

    # Simulate Feishu message event
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": "test-event-001",
            "event_type": "im.message.receive_v1",
            "create_time": "1608725989000",
            "token": "test-token",
            "app_id": "cli_test",
        },
        "event": {
            "sender": {"sender_id": {"open_id": "ou_test_user"}, "sender_type": "user"},
            "message": {
                "message_id": "om_test_msg",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": "查看状态"}),
            },
        },
    }

    try:
        response = httpx.post(f"{BASE_URL}/feishu/webhook", json=payload, timeout=10.0)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_git_commands():
    """Test git command execution via message handler."""
    print("\nTesting Git Commands...")

    from pathlib import Path
    import subprocess

    # Test git status
    try:
        result = subprocess.run(
            ["git", "status"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=10,
        )
        print(f"Git status: {'✅' if result.returncode == 0 else '❌'}")
        if result.returncode == 0:
            print(result.stdout[:200])
    except Exception as e:
        print(f"❌ Git error: {e}")


def test_agent_standalone():
    """Test local agent in standalone mode."""
    print("\nTesting Local Agent...")

    import subprocess
    import time

    # Start agent in background
    try:
        agent = subprocess.Popen(
            [sys.executable, "bot/opencode_agent.py", "--project", "."],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Give it time to start
        time.sleep(2)

        # Send status command
        agent.stdin.write("status\n")
        agent.stdin.flush()

        # Read output
        time.sleep(1)

        # Terminate
        agent.stdin.write("quit\n")
        agent.stdin.flush()
        agent.wait(timeout=5)

        stdout, stderr = agent.communicate(timeout=5)
        print("Agent output:")
        print(stdout[-500:] if len(stdout) > 500 else stdout)

        return True
    except Exception as e:
        print(f"❌ Agent error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("Feishu-OpenCode Bridge MVP Test")
    print("=" * 50)

    results = []

    # Test 1: Webhook endpoint
    results.append(("Webhook", test_webhook()))

    # Test 2: Git commands
    test_git_commands()

    # Test 3: Local agent
    results.append(("Agent", test_agent_standalone()))

    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")

    print("\nNext steps:")
    print("1. Start server: uv run server.py --dev")
    print("2. Start agent: python bot/opencode_agent.py")
    print("3. Configure Feishu webhook to point to your server")
    print("4. Test in Feishu: @机器人 查看状态")
    print("\nNote: Use natural language (e.g., '查看状态') instead of /status")


if __name__ == "__main__":
    main()
