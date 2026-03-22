#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file opencode_agent.py
# @brief Local agent for OpenCode remote control
# @author sailing-innocent
# @date 2026-03-21
# @version 1.0
# ---------------------------------
"""Local Agent for remote OpenCode control via Feishu Bot.

This agent runs on the local development machine and:
1. Connects to cloud gateway via WebSocket
2. Monitors desired_state from cloud
3. Manages OpenCode lifecycle (start/stop/restart)
4. Executes git commands and file operations
5. Reports actual state back to cloud

Usage:
    python scripts/opencode_agent.py --cloud ws://localhost:8080 --pin 123456
"""

import os
import sys
import json
import time
import asyncio
import subprocess
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Optional imports - gracefully degrade if not available
try:
    import websockets

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("Warning: websockets not installed, using HTTP polling mode")

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    print("Warning: httpx not installed, HTTP features disabled")


@dataclass
class AgentConfig:
    """Agent configuration."""

    cloud_url: str = "ws://localhost:8080"
    pin: str = ""
    project_path: str = "."
    opencode_port: int = 4096
    heartbeat_interval: int = 5
    check_interval: int = 5


@dataclass
class SystemState:
    """Current system state."""

    opencode_running: bool = False
    project_path: str = ""
    pid: Optional[int] = None
    last_check: str = ""


@dataclass
class DesiredState:
    """Desired state from cloud."""

    opencode_running: bool = False
    project_path: str = ""
    port: int = 4096
    updated_at: str = ""


class OpenCodeManager:
    """Manage OpenCode process lifecycle."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.current_project = config.project_path

    def check_health(self) -> bool:
        """Check if OpenCode is running and healthy."""
        if self.process is None:
            # Try to find existing process
            return self._check_existing_process()

        # Check if our managed process is still running
        if self.process.poll() is not None:
            self.process = None
            return False

        return True

    def _check_existing_process(self) -> bool:
        """Check if OpenCode is already running on configured port."""
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("127.0.0.1", self.config.opencode_port))
            sock.close()
            return result == 0
        except:
            return False

    def start(self, project_path: str) -> bool:
        """Start OpenCode in specified project."""
        if self.check_health():
            print(f"OpenCode already running on port {self.config.opencode_port}")
            return True

        if not Path(project_path).exists():
            print(f"Project path does not exist: {project_path}")
            return False

        try:
            # Start OpenCode in background
            cmd = [
                "opencode",
                "web",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(self.config.opencode_port),
            ]

            print(f"Starting OpenCode in {project_path}...")
            print(f"Command: {' '.join(cmd)}")

            self.process = subprocess.Popen(
                cmd,
                cwd=project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                if sys.platform == "win32"
                else 0,
            )

            self.current_project = project_path

            # Wait for OpenCode to be ready
            time.sleep(3)
            if self.check_health():
                print(f"✅ OpenCode started successfully (PID: {self.process.pid})")
                return True
            else:
                print("❌ OpenCode failed to start")
                return False

        except Exception as e:
            print(f"❌ Error starting OpenCode: {e}")
            return False

    def stop(self) -> bool:
        """Stop OpenCode process."""
        if self.process is None and not self._check_existing_process():
            print("OpenCode is not running")
            return True

        try:
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
                self.process = None

            print("✅ OpenCode stopped")
            return True

        except Exception as e:
            print(f"❌ Error stopping OpenCode: {e}")
            return False

    def restart(self, project_path: str) -> bool:
        """Restart OpenCode."""
        self.stop()
        time.sleep(1)
        return self.start(project_path)


class GitManager:
    """Execute git commands."""

    def __init__(self, project_path: str):
        self.project_path = project_path

    def _run_git(self, args: list) -> tuple[int, str, str]:
        """Run git command and return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, "", str(e)

    def status(self) -> str:
        """Get git status."""
        code, out, err = self._run_git(["status"])
        return out if code == 0 else err

    def pull(self) -> tuple[bool, str]:
        """Execute git pull."""
        code, out, err = self._run_git(["pull"])
        return code == 0, out if code == 0 else err

    def commit(self, message: str) -> tuple[bool, str]:
        """Execute git commit."""
        # First add all
        self._run_git(["add", "."])
        # Then commit
        code, out, err = self._run_git(["commit", "-m", message])
        return code == 0, out if code == 0 else err

    def push(self) -> tuple[bool, str]:
        """Execute git push."""
        code, out, err = self._run_git(["push"])
        return code == 0, out if code == 0 else err


class LocalAgent:
    """Main local agent."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.opencode_mgr = OpenCodeManager(config)
        self.git_mgr = GitManager(config.project_path)
        self.running = False
        self.desired_state = DesiredState()
        self.actual_state = SystemState()

    async def run(self):
        """Main agent loop."""
        print(f"🚀 OpenCode Local Agent starting...")
        print(f"   Cloud: {self.config.cloud_url}")
        print(f"   Project: {self.config.project_path}")
        print(f"   Port: {self.config.opencode_port}")

        self.running = True

        # For MVP, run in standalone mode without cloud connection
        # In production, this would connect to cloud WebSocket
        await self._standalone_mode()

    async def _standalone_mode(self):
        """Run in standalone mode (for testing)."""
        print("\nℹ️  Running in standalone mode (no cloud connection)")
        print("Available commands:")
        print("  start - Start OpenCode")
        print("  stop  - Stop OpenCode")
        print("  status - Show status")
        print("  commit - Git commit")
        print("  push - Git push")
        print("  quit - Exit\n")

        while self.running:
            try:
                cmd = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("Agent> ").strip().lower()
                )

                if cmd == "start":
                    self.opencode_mgr.start(self.config.project_path)
                elif cmd == "stop":
                    self.opencode_mgr.stop()
                elif cmd == "status":
                    running = self.opencode_mgr.check_health()
                    print(f"OpenCode running: {running}")
                    print(f"Git status:\n{self.git_mgr.status()[:500]}")
                elif cmd == "commit":
                    msg = input("Commit message: ").strip()
                    success, output = self.git_mgr.commit(msg or "Update from agent")
                    print(f"{'✅' if success else '❌'} {output}")
                elif cmd == "push":
                    success, output = self.git_mgr.push()
                    print(f"{'✅' if success else '❌'} {output}")
                elif cmd == "quit":
                    self.running = False
                else:
                    print(f"Unknown command: {cmd}")

            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"Error: {e}")

        print("\n👋 Agent shutting down...")
        self.opencode_mgr.stop()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="OpenCode Local Agent")
    parser.add_argument(
        "--cloud", default="ws://localhost:8080", help="Cloud WebSocket URL"
    )
    parser.add_argument(
        "--pin", default="123456", help="6-digit PIN for authentication"
    )
    parser.add_argument("--project", default=".", help="Project path")
    parser.add_argument("--port", type=int, default=4096, help="OpenCode port")

    args = parser.parse_args()

    config = AgentConfig(
        cloud_url=args.cloud,
        pin=args.pin,
        project_path=os.path.abspath(args.project),
        opencode_port=args.port,
    )

    agent = LocalAgent(config)

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
