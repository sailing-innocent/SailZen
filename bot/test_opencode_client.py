#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test OpenCode client without Feishu Bot."""

import subprocess
import time
import sys
import os
import signal
import socket
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def is_port_open(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        return sock.connect_ex(("127.0.0.1", port)) == 0
    finally:
        sock.close()


def kill_process_on_port(port: int):
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["netstat", "-ano", "|", "findstr", f":{port}"],
                capture_output=True,
                text=True,
                shell=True,
            )
            if result.stdout:
                for line in result.stdout.split("\n"):
                    parts = line.strip().split()
                    if len(parts) >= 5 and f":{port}" in line:
                        pid = parts[-1]
                        print(f"Killing process {pid} on port {port}")
                        subprocess.run(
                            ["taskkill", "/PID", pid, "/F"],
                            capture_output=True,
                        )
        else:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
            )
            if result.stdout:
                pid = result.stdout.strip()
                print(f"Killing process {pid} on port {port}")
                os.kill(int(pid), signal.SIGKILL)
    except Exception as e:
        print(f"Warning: Could not kill process on port {port}: {e}")


def test_opencode_client():
    test_port = 9999
    test_workspace = Path(__file__).parent.parent / "sail_server"

    print("=" * 60)
    print("OpenCode Client Test")
    print("=" * 60)

    print("\n[1/6] Cleaning up existing servers...")
    if is_port_open(test_port):
        print(f"Port {test_port} is occupied, killing process...")
        kill_process_on_port(test_port)
        time.sleep(2)
    print("[OK] Cleanup done")

    print(f"\n[2/6] Starting opencode web server on port {test_port}...")
    print(f"Workspace: {test_workspace}")

    if not test_workspace.exists():
        print(f"[ERROR] Workspace does not exist: {test_workspace}")
        return False

    process = subprocess.Popen(
        f"opencode web --hostname 127.0.0.1 --port {test_port}",
        cwd=test_workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True,
    )

    print("Waiting for server to start (max 30s)...")
    max_wait = 30
    started = False
    for i in range(max_wait):
        if is_port_open(test_port):
            started = True
            print(f"[OK] Server started on port {test_port} after {i + 1}s")
            break
        time.sleep(1)
        print(f"  Waiting... ({i + 1}/{max_wait})")

    if not started:
        print("[ERROR] Server failed to start")
        process.terminate()
        return False

    try:
        print("\n[3/6] Importing client...")
        from opencode_client import OpenCodeSessionClient

        print("[OK] Client imported")

        client = OpenCodeSessionClient(port=test_port)
        print("[OK] Client initialized")

        print("\n[4/6] Testing health check...")
        if client.is_healthy():
            health = client.health_check()
            print("[OK] Server is healthy")
            print(f"  Version: {health.get('version', 'unknown')}")
        else:
            print("[ERROR] Server health check failed")
            return False

        print("\n[5/6] Testing session creation...")
        session = client.create_session(title="Test Session")
        if not session:
            print("[ERROR] Failed to create session")
            return False

        print(f"[OK] Session created: {session.id}")

        print("\n[6/6] Testing message sending...")

        print("\n  [6a] Testing sync message...")
        test_message = "Say 'Hello from test' and nothing else"
        print(f"  Sending: '{test_message}'")

        try:
            response = client.send_message(session.id, test_message, timeout=60.0)
            if response:
                print(f"  [OK] Received response:")
                print(f"    Content: {response.text_content[:100]}...")
            else:
                print("  [WARN] No response received")
        except Exception as e:
            print(f"  [ERROR] {e}")

        print("\n  [6b] Testing async send + poll...")
        test_message2 = "Count from 1 to 5"
        print(f"  Sending: '{test_message2}'")

        try:
            response2 = client.send_message_and_wait(
                session.id,
                test_message2,
                poll_interval=1.0,
                timeout=60.0,
            )

            if response2:
                print(f"  [OK] Received response:")
                print(f"    Content: {response2.text_content[:200]}...")
            else:
                print("  [WARN] No response received")
        except Exception as e:
            print(f"  [ERROR] {e}")

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)
        return True

    finally:
        print("\n[Cleanup] Stopping server...")
        process.terminate()
        try:
            process.wait(timeout=5)
            print("[OK] Server stopped gracefully")
        except:
            process.kill()
            print("[OK] Server killed")

        if is_port_open(test_port):
            kill_process_on_port(test_port)


if __name__ == "__main__":
    success = test_opencode_client()
    sys.exit(0 if success else 1)
