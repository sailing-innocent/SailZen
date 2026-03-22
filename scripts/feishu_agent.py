#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file feishu_agent.py
# @brief Generic Feishu Bot Agent - Universal OpenCode Controller
# @author sailing-innocent
# @date 2026-03-21
# @version 4.0
# ---------------------------------
"""Generic Feishu Bot Agent - Universal OpenCode Session Manager

This agent provides a universal interface to control OpenCode from Feishu.
It can start OpenCode sessions at ANY location on your computer and monitor
callback messages.

Features:
- No project binding - works with any directory
- Dynamic session creation at any path
- Session monitoring and management
- All configuration via config file (no env vars needed)

Configuration:
    ~/.config/feishu-agent/config.yaml

Usage:
    python scripts/feishu_agent.py

    # Or specify custom config
    python scripts/feishu_agent.py --config /path/to/config.yaml
"""

import os
import sys
import json
import yaml
import argparse
import subprocess
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict

# Feishu SDK
try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import *

    HAS_LARK = True
except ImportError:
    HAS_LARK = False
    print("❌ Error: lark-oapi not installed")
    print("   Install: pip install lark-oapi pyyaml")
    sys.exit(1)


@dataclass
class SessionInfo:
    """Information about an OpenCode session."""

    session_id: str
    path: str
    port: int
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    chat_id: Optional[str] = None
    status: str = "stopped"  # stopped, starting, running, error


@dataclass
class AgentConfig:
    """Agent configuration - all settings in one place."""

    # Feishu credentials
    app_id: str = ""
    app_secret: str = ""

    # Session settings
    base_port: int = 4096
    max_sessions: int = 10

    # Callback settings
    callback_timeout: int = 300  # seconds
    auto_restart: bool = False

    # Config file path (auto-populated)
    config_path: Optional[str] = None


class OpenCodeSessionManager:
    """Manages OpenCode sessions at arbitrary locations."""

    def __init__(self, base_port: int = 4096):
        self.base_port = base_port
        self.sessions: Dict[str, SessionInfo] = {}
        self.port_map: Dict[int, str] = {}  # port -> session_id
        self._load_sessions()

    def _generate_session_id(self, path: str) -> str:
        """Generate unique session ID from path."""
        path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
        return f"session_{path_hash}"

    def _find_free_port(self) -> int:
        """Find next available port."""
        port = self.base_port
        while port in self.port_map:
            port += 1
        return port

    def create_session(self, path: str, chat_id: Optional[str] = None) -> SessionInfo:
        """Create a new session for the given path."""
        path = str(Path(path).expanduser().resolve())

        # Check if session already exists
        session_id = self._generate_session_id(path)
        if session_id in self.sessions:
            return self.sessions[session_id]

        # Create new session
        port = self._find_free_port()
        session = SessionInfo(
            session_id=session_id, path=path, port=port, chat_id=chat_id
        )

        self.sessions[session_id] = session
        self.port_map[port] = session_id

        return session

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session by ID."""
        return self.sessions.get(session_id)

    def find_by_path(self, path: str) -> Optional[SessionInfo]:
        """Find session by path."""
        path = str(Path(path).expanduser().resolve())
        session_id = self._generate_session_id(path)
        return self.sessions.get(session_id)

    def is_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            return result != 0
        except:
            return False

    def is_session_running(self, session_id: str) -> bool:
        """Check if a session is running."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        return not self.is_port_available(session.port)

    def start_session(self, session_id: str) -> tuple[bool, str]:
        """Start OpenCode for a session."""
        session = self.sessions.get(session_id)
        if not session:
            return False, "❌ Session not found"

        # Check if already running
        if self.is_session_running(session_id):
            return True, f"✅ Session already running on port {session.port}"

        # Validate path
        path = Path(session.path)
        if not path.exists():
            return False, f"❌ Path does not exist: {session.path}"

        try:
            cmd = [
                "opencode",
                "web",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(session.port),
            ]

            print(f"🚀 Starting OpenCode session...")
            print(f"   Path: {session.path}")
            print(f"   Port: {session.port}")

            # Start process
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE

            process = subprocess.Popen(
                cmd,
                cwd=session.path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **kwargs,
            )

            session.pid = process.pid
            session.started_at = datetime.now()
            session.status = "starting"

            # Wait for startup
            import time

            time.sleep(3)

            if self.is_session_running(session_id):
                session.status = "running"
                self._save_sessions()
                return (
                    True,
                    f"✅ OpenCode started (PID: {process.pid}, Port: {session.port})",
                )
            else:
                session.status = "error"
                return False, f"❌ OpenCode failed to start"

        except Exception as e:
            session.status = "error"
            return False, f"❌ Error: {e}"

    def stop_session(self, session_id: str) -> tuple[bool, str]:
        """Stop OpenCode for a session."""
        session = self.sessions.get(session_id)
        if not session:
            return False, "❌ Session not found"

        if not self.is_session_running(session_id):
            session.status = "stopped"
            return True, "ℹ️ Session is not running"

        try:
            # Try to kill by PID if available
            if session.pid:
                import signal

                try:
                    os.kill(session.pid, signal.SIGTERM)
                    # Wait a bit
                    import time

                    time.sleep(2)

                    # Check if still running
                    if self.is_session_running(session_id):
                        os.kill(session.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

            session.pid = None
            session.status = "stopped"
            self._save_sessions()

            return True, f"✅ Session stopped"
        except Exception as e:
            return False, f"❌ Error stopping: {e}"

    def get_session_status(self, session_id: str) -> str:
        """Get human-readable status of a session."""
        session = self.sessions.get(session_id)
        if not session:
            return "❌ Session not found"

        running = self.is_session_running(session_id)
        status_icon = "🟢" if running else "⚪"
        status_text = "Running" if running else "Stopped"

        lines = [
            f"{status_icon} Session: {session.session_id}",
            f"   Status: {status_text}",
            f"   Path: {session.path}",
            f"   Port: {session.port}",
        ]

        if session.pid:
            lines.append(f"   PID: {session.pid}")
        if session.started_at and running:
            duration = datetime.now() - session.started_at
            lines.append(f"   Duration: {duration}")

        return "\n".join(lines)

    def list_sessions(self) -> List[SessionInfo]:
        """List all sessions."""
        return list(self.sessions.values())

    def get_running_sessions(self) -> List[SessionInfo]:
        """Get all running sessions."""
        return [
            s for s in self.sessions.values() if self.is_session_running(s.session_id)
        ]

    def _save_sessions(self) -> None:
        """Save sessions to state file."""
        try:
            state_file = Path.home() / ".config" / "feishu-agent" / "sessions.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)

            data = []
            for session in self.sessions.values():
                data.append(
                    {
                        "session_id": session.session_id,
                        "path": session.path,
                        "port": session.port,
                        "chat_id": session.chat_id,
                    }
                )

            with open(state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Warning: Failed to save sessions: {e}")

    def _load_sessions(self) -> None:
        """Load sessions from state file."""
        try:
            state_file = Path.home() / ".config" / "feishu-agent" / "sessions.json"
            if state_file.exists():
                with open(state_file, "r") as f:
                    data = json.load(f)

                for item in data:
                    session = SessionInfo(
                        session_id=item["session_id"],
                        path=item["path"],
                        port=item["port"],
                        chat_id=item.get("chat_id"),
                    )
                    self.sessions[session.session_id] = session
                    self.port_map[session.port] = session.session_id
        except Exception as e:
            print(f"⚠️ Warning: Failed to load sessions: {e}")


class FeishuBotAgent:
    """Generic Feishu Bot Agent."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.session_mgr = OpenCodeSessionManager(config.base_port)
        self.client: Optional[lark.ws.Client] = None
        self.edge_runtime = None

        try:
            from sail_server.edge_runtime import EdgeRuntime, load_edge_runtime_config

            runtime_config = load_edge_runtime_config(config.config_path)
            self.edge_runtime = EdgeRuntime(runtime_config)
        except Exception as e:
            print(f"⚠️ Edge runtime unavailable: {e}")

    def _send_message(self, chat_id: str, text: str) -> None:
        """Send text message to Feishu chat."""
        try:
            if not self.client:
                print("⚠️ Client not initialized")
                return

            content = json.dumps({"text": text}, ensure_ascii=False)

            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(content)
                    .build()
                )
                .build()
            )

            response: CreateMessageResponse = self.client.im.v1.message.create(request)

            if not response.success():
                print(f"⚠️ Failed to send message: {response.msg}")
            else:
                print(f"✅ Message sent successfully")

        except Exception as e:
            print(f"⚠️ Error sending message: {e}")
            import traceback

            traceback.print_exc()

    def _handle_message(self, data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        """Handle incoming message from Feishu."""
        try:
            # 详细调试输出
            print(f"\n📨 [{datetime.now().strftime('%H:%M:%S')}] Received event")

            # 安全检查数据结构
            if not data or not data.event:
                print("⚠️ Invalid data: missing event")
                return

            if not data.event.message:
                print("⚠️ Invalid data: missing message")
                return

            message = data.event.message

            # 检查消息类型
            if message.message_type != "text":
                print(f"ℹ️ Ignoring non-text message: {message.message_type}")
                return

            # 解析消息内容
            try:
                content_str = message.content or "{}"
                content = json.loads(content_str)
            except json.JSONDecodeError as e:
                print(f"⚠️ Failed to parse message content: {e}")
                print(f"   Raw content: {message.content}")
                return

            text = content.get("text", "").strip()
            chat_id = message.chat_id

            if not chat_id:
                print("⚠️ Missing chat_id")
                return

            print(f"📩 Message from chat {chat_id[:20]}...: {text[:60]}...")

            if self.edge_runtime:
                try:
                    sender_open_id = ""
                    if data.event.sender and data.event.sender.sender_id:
                        sender_open_id = data.event.sender.sender_id.open_id or ""
                    envelope = self.edge_runtime.normalize_text_message(
                        message_id=message.message_id
                        or f"local-{int(datetime.now().timestamp())}",
                        chat_id=chat_id,
                        sender_open_id=sender_open_id,
                        text=text,
                        chat_type=message.chat_type or "unknown",
                        mentions=[
                            item.model_dump() if hasattr(item, "model_dump") else {}
                            for item in (message.mentions or [])
                        ],
                    )
                    sync_result = self.edge_runtime.forward_message(envelope)
                    print(f"🔄 Edge sync result: {sync_result}")
                except Exception as e:
                    print(f"⚠️ Failed to sync inbound message to control plane: {e}")

            # 解析并执行命令
            response = self._parse_command(text, chat_id)
            if response:
                print(f"📤 Sending response: {response[:100]}...")
                self._send_message(chat_id, response)
            else:
                print("ℹ️ No response generated")

        except Exception as e:
            print(f"❌ Error handling message: {e}")
            import traceback

            traceback.print_exc()

    def _parse_command(self, text: str, chat_id: str) -> Optional[str]:
        """Parse command from message."""
        import re

        text = re.sub(r"@_user_\d+", "", text).strip()

        if not text:
            return None

        if text.startswith("/"):
            parts = text.split(maxsplit=2)
            cmd = parts[0].lower()
            arg1 = parts[1] if len(parts) > 1 else ""
            arg2 = parts[2] if len(parts) > 2 else ""

            handlers = {
                "/session": self._cmd_session,
                "/start": self._cmd_start,
                "/stop": self._cmd_stop,
                "/status": self._cmd_status,
                "/list": self._cmd_list,
                "/code": self._cmd_code,
                "/git": self._cmd_git,
                "/help": self._cmd_help,
            }

            handler = handlers.get(cmd)
            if handler:
                return handler(arg1, arg2, chat_id)
            else:
                return f"❓ Unknown: {cmd}\nTry /help"

        return self._handle_natural_language(text, chat_id)

    def _cmd_session(self, path: str, args: str, chat_id: str) -> str:
        """Create or get a session for a path."""
        if not path:
            return "Usage: /session <path>\nExample: /session ~/projects/myapp"

        session = self.session_mgr.create_session(path, chat_id)
        return (
            f"📁 Session created/retrieved\n"
            f"━━━━━━━━━━━━━━\n"
            f"ID: {session.session_id}\n"
            f"Path: {session.path}\n"
            f"Port: {session.port}\n\n"
            f"To start: /start {session.session_id}\n"
            f"Or: /start {path}"
        )

    def _cmd_start(self, identifier: str, args: str, chat_id: str) -> str:
        """Start OpenCode for a session."""
        if not identifier:
            # Show usage
            return (
                "Usage: /start <path_or_session_id>\nExample: /start ~/projects/myapp"
            )

        # Try to find session
        session = self.session_mgr.find_by_path(identifier)
        if not session:
            session = self.session_mgr.get_session(identifier)

        if not session:
            # Create new session
            session = self.session_mgr.create_session(identifier, chat_id)

        success, msg = self.session_mgr.start_session(session.session_id)
        return msg

    def _cmd_stop(self, identifier: str, args: str, chat_id: str) -> str:
        """Stop OpenCode."""
        if not identifier:
            # Stop all running
            running = self.session_mgr.get_running_sessions()
            if not running:
                return "ℹ️ No sessions running"

            results = []
            for session in running:
                success, msg = self.session_mgr.stop_session(session.session_id)
                results.append(msg)
            return "🛑 Stopped all:\n" + "\n".join(results)

        session = self.session_mgr.find_by_path(identifier)
        if not session:
            session = self.session_mgr.get_session(identifier)

        if not session:
            return f"❌ Session not found: {identifier}"

        success, msg = self.session_mgr.stop_session(session.session_id)
        return msg

    def _cmd_status(self, identifier: str, args: str, chat_id: str) -> str:
        """Get status."""
        if identifier:
            session = self.session_mgr.find_by_path(identifier)
            if not session:
                session = self.session_mgr.get_session(identifier)

            if not session:
                return f"❌ Session not found: {identifier}"

            return self.session_mgr.get_session_status(session.session_id)

        # Show all
        sessions = self.session_mgr.list_sessions()
        if not sessions:
            return "ℹ️ No sessions. Create one: /session ~/projects/myapp"

        lines = ["📊 All Sessions", "━━━━━━━━━━━━━━"]
        for session in sessions:
            running = self.session_mgr.is_session_running(session.session_id)
            icon = "🟢" if running else "⚪"
            lines.append(
                f"{icon} {session.session_id[:20]}... | {session.path[:40]}... | Port: {session.port}"
            )

        running_count = len(self.session_mgr.get_running_sessions())
        lines.append(
            f"━━━━━━━━━━━━━━\nTotal: {len(sessions)} | Running: {running_count}"
        )

        return "\n".join(lines)

    def _cmd_list(self, args: str, extra: str, chat_id: str) -> str:
        """List sessions."""
        return self._cmd_status("", "", chat_id)

    def _cmd_code(self, identifier: str, task: str, chat_id: str) -> str:
        """Request code generation."""
        if not identifier:
            return "Usage: /code <path> <task>\nExample: /code ~/projects/myapp implement login"

        # Get or create session
        session = self.session_mgr.find_by_path(identifier)
        if not session:
            session = self.session_mgr.get_session(identifier)

        if not session:
            session = self.session_mgr.create_session(identifier, chat_id)

        # Start if not running
        if not self.session_mgr.is_session_running(session.session_id):
            success, msg = self.session_mgr.start_session(session.session_id)
            if not success:
                return f"❌ Failed to start: {msg}"

        task_desc = task if task else "(no specific task)"

        return (
            f"📝 Code Generation\n"
            f"━━━━━━━━━━━━━━\n"
            f"Path: {session.path}\n"
            f"Port: {session.port}\n"
            f"Task: {task_desc}\n\n"
            f"OpenCode running at http://localhost:{session.port}\n"
            f"Open this URL and input your task."
        )

    def _cmd_git(self, args: str, extra: str, chat_id: str) -> str:
        """Execute git command."""
        if not args:
            return "Usage: /git <path> <command>\nCommands: status, pull, commit, push\nExample: /git ~/projects/myapp status"

        parts = args.split(maxsplit=1)
        path = parts[0]
        cmd = parts[1] if len(parts) > 1 else "status"
        message = extra if extra else ""

        # Resolve path
        try:
            full_path = Path(path).expanduser().resolve()
        except:
            return f"❌ Invalid path: {path}"

        if not full_path.exists():
            return f"❌ Path not found: {full_path}"

        try:
            if cmd == "status":
                result = subprocess.run(
                    ["git", "status"],
                    cwd=full_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return f"📊 Git status:\n```\n{result.stdout[:800]}\n```"

            elif cmd == "pull":
                result = subprocess.run(
                    ["git", "pull"],
                    cwd=full_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                status = "✅" if result.returncode == 0 else "❌"
                return f"{status} Pull:\n```\n{result.stdout or result.stderr}\n```"

            elif cmd == "commit":
                msg = message or "Update from Feishu"
                subprocess.run(["git", "add", "."], cwd=full_path, capture_output=True)
                result = subprocess.run(
                    ["git", "commit", "-m", msg],
                    cwd=full_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                status = "✅" if result.returncode == 0 else "⚠️"
                return f"{status} Commit:\n```\n{result.stdout or result.stderr}\n```"

            elif cmd == "push":
                result = subprocess.run(
                    ["git", "push"],
                    cwd=full_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                status = "✅" if result.returncode == 0 else "❌"
                return f"{status} Push:\n```\n{result.stdout or result.stderr}\n```"

            else:
                return f"❌ Unknown: {cmd}. Try: status, pull, commit, push"

        except Exception as e:
            return f"❌ Git error: {e}"

    def _cmd_help(self, args: str, extra: str, chat_id: str) -> str:
        """Show help."""
        return (
            "🤖 Feishu OpenCode Agent\n"
            "━━━━━━━━━━━━━━\n"
            "Session Management:\n"
            "  /session <path> - Create/get session for path\n"
            "  /start <path> - Start OpenCode at path\n"
            "  /stop [path] - Stop OpenCode\n"
            "  /status [path] - Show status\n"
            "  /list - List all sessions\n"
            "\n"
            "Code Generation:\n"
            "  /code <path> <task> - Start and request code\n"
            "\n"
            "Git Operations:\n"
            "  /git <path> status - Git status\n"
            "  /git <path> pull - Git pull\n"
            "  /git <path> commit [msg] - Git commit\n"
            "  /git <path> push - Git push\n"
            "\n"
            "Natural Language:\n"
            "  'start ~/projects/myapp'\n"
            "  'status' | 'list'"
        )

    def _handle_natural_language(self, text: str, chat_id: str) -> str:
        """Handle natural language."""
        text_lower = text.lower()

        if any(kw in text_lower for kw in ["start", "启动", "开启"]):
            # Try to extract path
            words = text.split()
            for word in words:
                if word.startswith("/") or word.startswith("~") or word.startswith("."):
                    return self._cmd_start(word, "", chat_id)
            return "Please specify a path: start ~/projects/myapp"

        elif any(kw in text_lower for kw in ["stop", "停止", "关闭"]):
            return self._cmd_stop("", "", chat_id)

        elif any(kw in text_lower for kw in ["status", "状态", "情况"]):
            return self._cmd_status("", "", chat_id)

        elif any(kw in text_lower for kw in ["list", "列表", "all"]):
            return self._cmd_list("", "", chat_id)

        elif any(kw in text_lower for kw in ["help", "帮助", "?"]):
            return self._cmd_help("", "", chat_id)

        else:
            return (
                f"🤖 Received: {text[:50]}...\n\n"
                f"Try:\n"
                f"• /start ~/projects/myapp\n"
                f"• /code ~/projects/myapp implement login\n"
                f"• /status\n"
                f"• /help"
            )

    def run(self) -> None:
        """Start the agent."""
        print("🚀 Feishu OpenCode Agent v4.0")
        print(f"   Config: {self.config.config_path}")
        print(f"   Sessions: {len(self.session_mgr.list_sessions())}")
        print()

        # Check credentials
        if not self.config.app_id or not self.config.app_secret:
            print("❌ Error: Feishu credentials not configured")
            print(f"   Edit config: {self.config.config_path}")
            print()
            print("Required settings:")
            print("  app_id: cli_xxxxxxxx")
            print("  app_secret: xxxxxxxxxx")
            return

        # Mask credentials for display
        app_id_display = (
            self.config.app_id[:10] + "..."
            if len(self.config.app_id) > 10
            else self.config.app_id
        )
        print(f"🔑 App ID: {app_id_display}")
        print(f"🔑 App Secret: {'*' * min(len(self.config.app_secret), 10)}...")
        print()

        try:
            if self.edge_runtime:
                self.edge_runtime.register_or_heartbeat()

            # Build event handler
            print("🔧 Building event handler...")

            # 添加一个通用的拦截器来捕获所有事件
            def debug_interceptor(data):
                print(f"\n🐛 [INTERCEPTOR] Raw event received!")
                print(f"   Type: {type(data)}")
                try:
                    print(f"   Data: {str(data)[:200]}...")
                except:
                    print(f"   Data: <cannot stringify>")

            event_handler = (
                lark.EventDispatcherHandler.builder("", "")
                .register_p2_im_message_receive_v1(self._handle_message)
                .register_p1_customized_event(
                    "im.message.receive_v1", debug_interceptor
                )  # 也注册v1事件
                .build()
            )
            print("✅ Event handler registered")

            # Create client
            print("🔧 Creating WebSocket client...")
            self.client = (
                lark.Client.builder()
                .app_id(self.config.app_id)
                .app_secret(self.config.app_secret)
                .log_level(lark.LogLevel.DEBUG)
                .build()
            )

            ws_client = lark.ws.Client(
                self.config.app_id,
                self.config.app_secret,
                event_handler=event_handler,
                log_level=lark.LogLevel.DEBUG,
            )
            print("✅ Client created")

            print()
            print(f"✅ Agent ready")
            print(f"   Sessions: {len(self.session_mgr.list_sessions())}")
            print("🔗 Connecting to Feishu...")
            print("   Waiting for messages...")
            print("   (Ctrl+C to stop)")
            print()
            print("💡 Tip: If you don't see messages after sending in Feishu,")
            print("   check that 'im.message.receive_v1' event is subscribed")
            print("   and the app is published with proper permissions.")
            print()

            ws_client.start()

        except KeyboardInterrupt:
            if self.edge_runtime:
                self.edge_runtime.close()
            print("\n👋 Stopped by user")
        except Exception as e:
            if self.edge_runtime:
                self.edge_runtime.close()
            print(f"\n❌ Fatal error: {e}")
            import traceback

            traceback.print_exc()


def get_default_config_path() -> str:
    """Get default config path."""
    if sys.platform == "win32":
        return str(Path.home() / "AppData" / "Roaming" / "feishu-agent" / "config.yaml")
    else:
        return str(Path.home() / ".config" / "feishu-agent" / "config.yaml")


def load_config(config_path: str) -> AgentConfig:
    """Load configuration from file."""
    config = AgentConfig(config_path=config_path)

    if not Path(config_path).exists():
        return config

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data:
            config.app_id = data.get("app_id", "")
            config.app_secret = data.get("app_secret", "")
            config.base_port = data.get("base_port", 4096)
            config.max_sessions = data.get("max_sessions", 10)
            config.callback_timeout = data.get("callback_timeout", 300)
            config.auto_restart = data.get("auto_restart", False)

    except Exception as e:
        print(f"⚠️ Warning: Failed to load config: {e}")

    return config


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

# Remote Control Plane
control_plane_url: "http://127.0.0.1:8000/api/v1/remote-dev/control-plane"
edge_node_key: "home-dev-host"
edge_secret: ""
host_name: ""
runtime_version: "0.1.0"
heartbeat_interval_seconds: 15
request_timeout_seconds: 15
offline_mode: false
queue_path: "data/control_plane/edge_queue.json"

# Optional project inventory
projects:
  - slug: "sailzen"
    path: "D:/ws/repos/SailZen"
    label: "SailZen"

# Session Settings
base_port: 4096        # Starting port for OpenCode sessions
max_sessions: 10       # Maximum concurrent sessions
callback_timeout: 300  # Session callback timeout (seconds)
auto_restart: false    # Auto-restart crashed sessions

# Example configuration:
# app_id: "cli_xxxxxxxx"
# app_secret: "xxxxxxxxxxxxxxxx"
"""

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(default_content)

    print(f"✅ Created default config: {config_path}")
    print("   Please edit and add your Feishu credentials.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Feishu OpenCode Agent - Universal Session Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration:
  Config file: ~/.config/feishu-agent/config.yaml
  
  Required fields:
    app_id: Your Feishu App ID
    app_secret: Your Feishu App Secret

Examples:
  # Start with default config
  python scripts/feishu_agent.py
  
  # Use custom config
  python scripts/feishu_agent.py --config /path/to/config.yaml
  
  # Create default config
  python scripts/feishu_agent.py --init
        """,
    )

    parser.add_argument(
        "--config", "-c", default=get_default_config_path(), help="Config file path"
    )
    parser.add_argument(
        "--init", action="store_true", help="Create default config file and exit"
    )

    args = parser.parse_args()

    # Init mode
    if args.init:
        create_default_config(args.config)
        return

    # Load config
    config = load_config(args.config)

    # Check if config exists
    if not Path(args.config).exists():
        print("❌ Config file not found")
        create_default_config(args.config)
        print(f"\nPlease edit: {args.config}")
        return

    # Run agent
    agent = FeishuBotAgent(config)
    agent.run()


if __name__ == "__main__":
    main()
