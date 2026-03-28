#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file feishu_agent.py
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
    uv run bot/feishu_agent.py -c bot/opencode.bot.yaml
    uv run bot/feishu_agent.py --init
"""

import asyncio
import os
import sys
import json
import re
import yaml
import time
import socket
import argparse
from pathlib import Path


def _load_dotenv():
    """Load environment variables from .env files."""
    env_files = [".env", ".env.local", ".env.dev", ".env.production"]
    for filename in env_files:
        env_path = Path(filename)
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip().strip("'\"")
                            # Only set if not already in environment
                            if key not in os.environ:
                                os.environ[key] = value
            except Exception:
                pass


_load_dotenv()
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

# Feishu SDK
try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest,
        CreateMessageRequestBody,
        PatchMessageRequest,
        PatchMessageRequestBody,
        ReplyMessageRequest,
        ReplyMessageRequestBody,
    )

    HAS_LARK = True
except ImportError:
    HAS_LARK = False
    print("Error: lark-oapi not installed")
    print("   Install: pip install lark-oapi pyyaml httpx")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("Error: httpx not installed")
    print("   Install: pip install httpx")
    sys.exit(1)

import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent))
from card_renderer import (
    CardColor,
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


# ---------------------------------------------------------------------------
# OpenCode Web API Client
# ---------------------------------------------------------------------------


class OpenCodeWebClient:
    """HTTP client for the OpenCode web/serve API.

    OpenCode exposes a local Hono-based server with these key endpoints:
      GET  /global/health              - health check
      POST /session                    - create new session
      GET  /session/:id                - get session details
      POST /session/:id/message        - send task (SSE stream response)

    This client handles session lifecycle and message streaming.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 4096, timeout: int = 120):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._base_url = f"http://{host}:{port}"

    @property
    def base_url(self) -> str:
        return self._base_url

    def is_healthy(self) -> bool:
        """Check if opencode server is up."""
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self._base_url}/global/health")
                return resp.status_code == 200
        except Exception:
            return False

    def create_session(self, title: Optional[str] = None) -> Optional[str]:
        """Create a new OpenCode session and return its ID.

        POST /session
        Body: { "title": "..." }
        Returns: Session object with "id" field
        """
        body: Dict[str, Any] = {}
        if title:
            body["title"] = title

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(f"{self._base_url}/session", json=body)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return data.get("id")
                print(
                    f"[OpenCode] create_session failed: {resp.status_code} {resp.text[:200]}"
                )
                return None
        except Exception as exc:
            print(f"[OpenCode] create_session error: {exc}")
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions on this server."""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"{self._base_url}/session")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as exc:
            print(f"[OpenCode] list_sessions error: {exc}")
        return []

    def send_message(
        self,
        session_id: str,
        text: str,
        collect_timeout: int = 300,
    ) -> str:
        """Send a task message to a session and return the assistant reply.

        POST /session/:id/message
        Body: { parts: [{ type: "text", text: "..." }] }
        Response: { info: Message, parts: Part[] }

        This call blocks until the model finishes. For long tasks set a larger
        collect_timeout (default 300s).

        Handles SSE stream edge cases: session.idle vs session.completed event names
        may vary across opencode versions. Uses robust event-name matching and
        timeout fallback.
        """
        url = f"{self._base_url}/session/{session_id}/message"
        body = {"parts": [{"type": "text", "text": text}]}

        # Initialize variables that need to be accessible in exception handlers
        import time

        start_time = time.time()
        collected_texts: List[str] = []
        session_completed = False

        try:
            with httpx.Client(timeout=collect_timeout) as client:
                resp = client.post(url, json=body)
                if resp.status_code not in (200, 201):
                    return f"OpenCode API error: HTTP {resp.status_code}: {resp.text[:300]}"

                # Check if response is SSE stream
                content_type = resp.headers.get("content-type", "")
                if (
                    "text/event-stream" in content_type
                    or resp.headers.get("transfer-encoding") == "chunked"
                ):
                    # Handle SSE stream
                    for line in resp.iter_lines():
                        if time.time() - start_time > collect_timeout:
                            break

                        line = line.strip()
                        if not line:
                            continue

                        # Parse SSE event
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix
                            try:
                                event_data = json.loads(data)
                            except json.JSONDecodeError:
                                continue

                            # Handle different event types with robust matching
                            event_type = event_data.get("type", "")

                            # Collect text from content events (various formats)
                            if event_type in ("content", "text", "chunk", "delta"):
                                content = (
                                    event_data.get("content", "")
                                    or event_data.get("text", "")
                                    or event_data.get("delta", "")
                                )
                                if content:
                                    collected_texts.append(content)

                            # Check for completion events (various names across versions)
                            elif event_type in (
                                "completed",
                                "done",
                                "finished",
                                "end",
                                "session.completed",
                            ):
                                session_completed = True
                                break

                            # Check for idle/stop events (alternative completion signals)
                            elif event_type in (
                                "idle",
                                "stopped",
                                "session.idle",
                                "halt",
                            ):
                                session_completed = True
                                break

                            # Check for error events
                            elif event_type in ("error", "failed"):
                                error_msg = event_data.get(
                                    "message", event_data.get("error", "Unknown error")
                                )
                                return f"OpenCode error: {error_msg}"

                    # Fallback: if we collected text but didn't get completion event,
                    # return what we have (with a note if incomplete)
                    reply = "".join(collected_texts).strip()
                    if reply and not session_completed:
                        return (
                            reply
                            + "\n\n[Response may be incomplete - timeout or stream interruption]"
                        )
                    return reply or "(OpenCode returned an empty response)"
                else:
                    # Handle regular JSON response
                    data = resp.json()
                    parts = data.get("parts", [])
                    text_parts = [
                        p.get("text", "")
                        for p in parts
                        if isinstance(p, dict)
                        and p.get("type") == "text"
                        and p.get("text")
                    ]
                    reply = "".join(text_parts).strip()
                    return reply or "(OpenCode returned an empty response)"

        except httpx.TimeoutException:
            # Return collected text even on timeout
            if collected_texts:
                reply = "".join(collected_texts).strip()
                return (
                    reply
                    + f"\n\n[Response truncated - timed out after {collect_timeout}s]"
                )
            return f"OpenCode timed out after {collect_timeout}s. The task may still be running."
        except Exception as exc:
            # Return collected text even on error
            if collected_texts:
                reply = "".join(collected_texts).strip()
                return reply + f"\n\n[Response may be incomplete - error: {exc}]"
            return f"OpenCode communication error: {exc}"


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------


@dataclass
class ManagedSession:
    """Tracks a running opencode web process and its API session."""

    path: str  # workspace directory
    port: int  # opencode server port
    pid: Optional[int] = None  # subprocess PID
    process_status: str = "stopped"  # stopped | starting | running | error
    opencode_session_id: Optional[str] = None  # OpenCode API session ID
    started_at: Optional[str] = None
    last_error: Optional[str] = None
    chat_id: Optional[str] = None  # Feishu chat this session was created from
    _process: Optional[Any] = None  # subprocess.Popen object for proper cleanup
    _stdout_log: Optional[Any] = None  # stdout file handle
    _stderr_log: Optional[Any] = None  # stderr file handle


@dataclass
class AgentConfig:
    """All agent settings."""

    app_id: str = ""
    app_secret: str = ""
    base_port: int = 4096
    max_sessions: int = 10
    callback_timeout: int = 300
    auto_restart: bool = False
    config_path: Optional[str] = None
    # Named project shortcuts
    projects: List[Dict[str, str]] = field(default_factory=list)
    # LLM settings for BotBrain (optional, fallback to env vars)
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None


class OpenCodeSessionManager:
    """Manages OpenCode web processes and their API sessions.

    For each workspace path, we maintain:
    - A running `opencode web --hostname 127.0.0.1 --port <N>` subprocess
    - An OpenCode API session created via POST /session
    - A client for communicating with that server

    Sessions persist across Feishu messages within the same process lifetime.
    State is saved to ~/.config/feishu-agent/sessions.json for restart recovery.
    """

    STATE_FILE = Path.home() / ".config" / "feishu-agent" / "sessions.json"

    def __init__(
        self, base_port: int = 4096, state_store: Optional["SessionStateStore"] = None
    ):
        self.base_port = base_port
        self._sessions: Dict[str, ManagedSession] = {}
        self._state_store = state_store
        self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_running(
        self, path: str, chat_id: Optional[str] = None
    ) -> Tuple[bool, ManagedSession, str]:
        """Ensure an opencode web process is running for `path`.

        Returns (success, session, message).
        If already running, returns immediately.
        If not running, starts a new process and waits for it to become healthy.
        """
        # 验证路径有效性
        try:
            path_obj = Path(path).expanduser().resolve()
            if not path_obj.exists():
                # 创建错误状态的 session
                error_session = ManagedSession(path=path, port=0, chat_id=chat_id)
                error_session.process_status = "error"
                error_session.last_error = f"路径不存在: {path}"
                return False, error_session, f"路径不存在: {path}"
            path = str(path_obj)
        except Exception as e:
            error_session = ManagedSession(path=path, port=0, chat_id=chat_id)
            error_session.process_status = "error"
            error_session.last_error = f"无效路径: {e}"
            return False, error_session, f"无效路径 '{path}': {e}"

        session = self._sessions.get(path)
        if session and self._is_port_open(session.port):
            session.process_status = "running"
            self._sync_state(path, "running", port=session.port, pid=session.pid)
            return True, session, f"Already running on port {session.port}"

        # Need to start or restart
        port = self._allocate_port()
        if session is None:
            session = ManagedSession(path=path, port=port, chat_id=chat_id)
            self._sessions[path] = session
        else:
            session.port = port
            session.opencode_session_id = None

        if self._state_store:
            entry = self._state_store.get_or_create(path, chat_id)
            self._state_store.transition(path, SessionState.STARTING, port=port)

        return self._start_process(session)

    def get_or_create_opencode_session(self, path: str) -> Optional[str]:
        """Get the OpenCode API session ID for a workspace, creating one if needed."""
        path = str(Path(path).expanduser().resolve())
        session = self._sessions.get(path)
        if not session or session.process_status != "running":
            return None

        if session.opencode_session_id:
            return session.opencode_session_id

        client = OpenCodeWebClient(port=session.port)
        title = f"Feishu session - {Path(path).name}"
        sess_id = client.create_session(title=title)
        if sess_id:
            session.opencode_session_id = sess_id
            self._save_state()
        return sess_id

    def send_task(self, path: str, task_text: str) -> str:
        """Send a coding task to the opencode session for `path`.

        Ensures process is running, creates API session if needed,
        then streams the response and returns the final reply text.
        """
        path = str(Path(path).expanduser().resolve())
        session = self._sessions.get(path)

        if not session or session.process_status != "running":
            return f"No running session for {path}. Use '启动 {path}' first."

        sess_id = self.get_or_create_opencode_session(path)
        if not sess_id:
            return "Failed to create OpenCode session. The server may not be ready yet."

        client = OpenCodeWebClient(port=session.port)
        print(f"[OpenCode] Sending task to session {sess_id} on port {session.port}")
        return client.send_message(sess_id, task_text)

    def stop_session(self, path: str) -> Tuple[bool, str]:
        """Stop the opencode process for a workspace."""
        path = str(Path(path).expanduser().resolve())
        session = self._sessions.get(path)
        if not session:
            return False, f"No session for {path}"

        self._sync_state(path, "stopping")

        # Kill the process
        if session.pid:
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/PID", str(session.pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
                    )
                else:
                    os.kill(session.pid, 15)

                # Wait for process to terminate
                if session._process:
                    try:
                        session._process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        # Force kill if graceful termination failed
                        try:
                            session._process.kill()
                            session._process.wait(timeout=2)
                        except Exception:
                            pass

                time.sleep(1)
            except Exception as exc:
                session.last_error = str(exc)

        # Close file handles to prevent resource leaks
        if session._stdout_log:
            try:
                session._stdout_log.close()
            except Exception:
                pass
            session._stdout_log = None

        if session._stderr_log:
            try:
                session._stderr_log.close()
            except Exception:
                pass
            session._stderr_log = None

        # Clean up process reference
        session._process = None
        session.pid = None
        session.process_status = "stopped"
        session.opencode_session_id = None
        self._save_state()
        self._sync_state(path, "stopped")
        print(f"[OpenCode] Stopped session for {path}")
        return True, "Stopped"

    def get_status(self, path: Optional[str] = None) -> str:
        """Return a human-readable status summary."""
        if path:
            path = str(Path(path).expanduser().resolve())
            session = self._sessions.get(path)
            if not session:
                return f"No session for {path}"
            return self._format_session(session)

        if not self._sessions:
            return "No sessions. Use '启动 <path>' to start one."

        lines = ["Session Status", "=" * 40]
        for s in self._sessions.values():
            lines.append(self._format_session(s))
        return "\n".join(lines)

    def list_sessions(self) -> List[ManagedSession]:
        return list(self._sessions.values())

    def find_by_slug(self, slug: str, projects: List[Dict[str, str]]) -> Optional[str]:
        """Resolve a project slug to a path from the config projects list."""
        for p in projects:
            if p.get("slug") == slug or p.get("label", "").lower() == slug.lower():
                return p.get("path", "")
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start_process(
        self, session: ManagedSession
    ) -> Tuple[bool, ManagedSession, str]:
        """Start an opencode web process for the session."""
        path = Path(session.path)
        if not path.exists():
            session.process_status = "error"
            session.last_error = f"Path does not exist: {session.path}"
            self._sync_state(session.path, "error", last_error=session.last_error)
            return False, session, session.last_error

        cmd = [
            "opencode",
            "web",
            "--hostname",
            "127.0.0.1",
            "--port",
            str(session.port),
        ]

        kwargs: Dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
            kwargs["shell"] = True

        print(f"[OpenCode] Starting: {' '.join(cmd)}")
        print(f"[OpenCode] Working dir: {session.path}")

        log_dir = Path.home() / ".config" / "feishu-agent" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_log = open(
            log_dir / f"opencode_{session.port}.out.log", "w", encoding="utf-8"
        )
        stderr_log = open(
            log_dir / f"opencode_{session.port}.err.log", "w", encoding="utf-8"
        )

        process = None
        try:
            process = subprocess.Popen(
                cmd,
                cwd=session.path,
                stdout=stdout_log,
                stderr=stderr_log,
                **kwargs,
            )
            session.pid = process.pid
            session._process = process
            session._stdout_log = stdout_log
            session._stderr_log = stderr_log
            session.process_status = "starting"
            session.started_at = datetime.now().isoformat()
        except FileNotFoundError:
            # Clean up file handles on error
            stdout_log.close()
            stderr_log.close()
            session.process_status = "error"
            session.last_error = (
                "opencode command not found. Is it installed and in PATH?"
            )
            self._sync_state(session.path, "error", last_error=session.last_error)
            return False, session, session.last_error
        except Exception as exc:
            # Clean up file handles on error
            stdout_log.close()
            stderr_log.close()
            session.process_status = "error"
            session.last_error = str(exc)
            self._sync_state(session.path, "error", last_error=session.last_error)
            return False, session, session.last_error

        client = OpenCodeWebClient(port=session.port)
        for attempt in range(15):
            time.sleep(1)
            if client.is_healthy():
                session.process_status = "running"
                self._save_state()
                self._sync_state(
                    session.path, "running", port=session.port, pid=session.pid
                )
                msg = f"Started on port {session.port} (PID {session.pid})"
                print(f"[OpenCode] {msg}")
                return True, session, msg

        # Health check failed - clean up the failed process
        if process:
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
                    )
                else:
                    os.kill(process.pid, 9)
            except Exception as exc:
                print(f"[OpenCode] Warning: Failed to kill failed process: {exc}")

        # Close file handles
        stdout_log.close()
        stderr_log.close()
        session._stdout_log = None
        session._stderr_log = None

        session.process_status = "error"
        session.last_error = (
            f"Server did not become healthy on port {session.port} after 15s"
        )
        self._sync_state(session.path, "error", last_error=session.last_error)
        return False, session, session.last_error

    def _sync_state(self, path: str, status: str, **kwargs: Any) -> None:
        if not self._state_store:
            return
        try:
            state_map = {
                "idle": SessionState.IDLE,
                "starting": SessionState.STARTING,
                "running": SessionState.RUNNING,
                "stopping": SessionState.STOPPING,
                "error": SessionState.ERROR,
                "stopped": SessionState.IDLE,
            }
            target = state_map.get(status, SessionState.IDLE)
            entry = self._state_store.get(path)
            if entry is None:
                return
            if entry.state != target:
                self._state_store.transition(path, target, **kwargs)
            elif kwargs:
                self._state_store.force_set(path, target, **kwargs)
        except Exception as exc:
            print(f"[SessionState] Sync error: {exc}")

    def _is_port_open(self, port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            return sock.connect_ex(("127.0.0.1", port)) == 0
        finally:
            sock.close()

    def _allocate_port(self) -> int:
        used = {s.port for s in self._sessions.values()}
        port = self.base_port
        while port in used or self._is_port_open(port):
            port += 1
        return port

    def _format_session(self, s: ManagedSession) -> str:
        running = self._is_port_open(s.port)
        icon = "running" if running else s.process_status
        lines = [
            f"[{icon}] {s.path}",
            f"  Port: {s.port}  PID: {s.pid}",
        ]
        if s.opencode_session_id:
            lines.append(f"  OpenCode session: {s.opencode_session_id}")
        if s.last_error:
            lines.append(f"  Last error: {s.last_error}")
        return "\n".join(lines)

    def _save_state(self) -> None:
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = []
            for s in self._sessions.values():
                data.append(
                    {
                        "path": s.path,
                        "port": s.port,
                        "opencode_session_id": s.opencode_session_id,
                        "chat_id": s.chat_id,
                    }
                )
            with open(self.STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            print(f"[State] Failed to save: {exc}")

    def _load_state(self) -> None:
        if not self.STATE_FILE.exists():
            return
        try:
            with open(self.STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                path = item.get("path", "")
                if not path:
                    continue
                s = ManagedSession(
                    path=path,
                    port=item.get("port", self.base_port),
                    opencode_session_id=item.get("opencode_session_id"),
                    chat_id=item.get("chat_id"),
                )
                # Check if process still running
                if self._is_port_open(s.port):
                    s.process_status = "running"
                self._sessions[path] = s
            if self._sessions:
                print(f"[State] Loaded {len(self._sessions)} session(s) from disk")
        except Exception as exc:
            print(f"[State] Failed to load: {exc}")


def _extract_path_from_text(text: str, projects: List[Dict[str, str]]) -> Optional[str]:
    patterns = [
        r"([~/][^\s]+)",
        r"([A-Z]:[/\\][^\s]+)",
        r"(\.[/\\][^\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1)
            try:
                return str(Path(candidate).expanduser().resolve())
            except Exception:
                continue

    for p in projects:
        slug = p.get("slug", "")
        label = p.get("label", "")
        if slug and slug in text:
            return p.get("path", "")
        if label and label.lower() in text.lower():
            return p.get("path", "")

    return None


def _resolve_path(raw: str, projects: List[Dict[str, str]]) -> Optional[str]:
    if not raw:
        return None
    for p in projects:
        if p.get("slug") == raw or p.get("label", "").lower() == raw.lower():
            return p.get("path", "")
    try:
        resolved = str(Path(raw).expanduser().resolve())
        return resolved
    except Exception:
        return raw or None


# ---------------------------------------------------------------------------
# Conversation context
# ---------------------------------------------------------------------------

_CONFIRM_WORDS = frozenset(
    [
        "确认",
        "确定",
        "是",
        "yes",
        "ok",
        "好",
        "好的",
        "执行",
        "继续",
        "confirm",
        "y",
    ]
)
_CANCEL_WORDS = frozenset(
    [
        "取消",
        "算了",
        "不",
        "no",
        "cancel",
        "停",
        "别",
        "n",
    ]
)

_HISTORY_WINDOW = 6


@dataclass
class TurnRecord:
    role: str
    text: str
    ts: datetime = field(default_factory=datetime.now)


@dataclass
class PendingConfirmation:
    action: str
    params: Dict[str, Any]
    summary: str
    expires_at: datetime


@dataclass
class ConversationContext:
    """Per-chat conversation state."""

    chat_id: str
    history: deque = field(default_factory=lambda: deque(maxlen=_HISTORY_WINDOW))
    mode: str = "idle"
    active_workspace: Optional[str] = None
    pending: Optional[PendingConfirmation] = None

    def push(self, role: str, text: str) -> None:
        self.history.append(TurnRecord(role=role, text=text))

    def history_text(self) -> str:
        lines = []
        for t in self.history:
            prefix = "User" if t.role == "user" else "Bot"
            lines.append(f"{prefix}: {t.text}")
        return "\n".join(lines)

    def is_pending_expired(self) -> bool:
        return self.pending is not None and datetime.now() > self.pending.expires_at

    def clear_pending(self) -> None:
        self.pending = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dict for persistence (excludes history and pending)."""
        return {
            "chat_id": self.chat_id,
            "mode": self.mode,
            "active_workspace": self.active_workspace,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """Deserialize context from dict."""
        ctx = cls(
            chat_id=data.get("chat_id", ""),
            mode=data.get("mode", "idle"),
            active_workspace=data.get("active_workspace"),
        )
        return ctx


# ---------------------------------------------------------------------------
# LLM-driven brain
# ---------------------------------------------------------------------------

_BRAIN_SYSTEM = """你是飞书机器人，帮用户控制OpenCode开发环境。理解自然语言（可能有错别字），返回JSON行动计划。

上下文：mode={mode}, workspace={active_workspace}, projects={projects}
历史：{history}

用户：{user_text}

返回JSON：
{{"action":"...","params":{{}},"confirm_required":false,"confirm_summary":"","reply":"","reasoning":""}}

actions: start_workspace|stop_workspace|send_task|import_text|show_status|show_help|chat|clarify
import_text: 用户想导入小说/文本到系统。params需要file_name(文件名)和可选的title(标题)、author(作者)。books目录下的txt文件可以导入。
规则：stop_workspace需确认；长消息或破坏性操作需确认；import_text不需确认
注意：推断用户意图，只返回JSON"""

_BRAIN_FALLBACK_ACTIONS = {
    "帮助": ("show_help", {}),
    "help": ("show_help", {}),
    "状态": ("show_status", {}),
    "status": ("show_status", {}),
    "导入小说": ("import_text", {}),
    "导入文本": ("import_text", {}),
    "import text": ("import_text", {}),
    "import novel": ("import_text", {}),
}


@dataclass
class ActionPlan:
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    confirm_required: bool = False
    confirm_summary: str = ""
    reply: str = ""


def _make_gateway(
    config_provider: Optional[str] = None, config_api_key: Optional[str] = None
):
    """Build a minimal LLMGateway from environment variables or config.

    Args:
        config_provider: Optional provider name from config file (e.g., "moonshot")
        config_api_key: Optional API key from config file
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from sail_server.utils.llm.gateway import LLMGateway
        from sail_server.utils.llm.providers import ProviderConfig
        from sail_server.utils.llm.available_providers import (
            DEFAULT_LLM_PROVIDER,
            DEFAULT_LLM_MODEL,
            DEFAULT_LLM_CONFIG,
        )

        provider_env_keys = {
            "moonshot": "MOONSHOT_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }

        # Default models for each provider
        default_models = {
            "moonshot": DEFAULT_LLM_MODEL
            if DEFAULT_LLM_PROVIDER == "moonshot"
            else "kimi-k2.5",
            "openai": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "google": os.environ.get("GOOGLE_MODEL", "gemini-2.0-flash"),
            "deepseek": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
            "anthropic": os.environ.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
        }

        gw = LLMGateway()
        registered = []

        # First, check if config file has explicit provider + api_key
        if config_provider and config_api_key:
            provider = config_provider.lower()
            if provider in provider_env_keys:
                model = default_models.get(provider, "")
                cfg = ProviderConfig(
                    provider_name=provider,
                    model=model,
                    api_key=config_api_key,
                    api_base=os.environ.get(f"{provider.upper()}_API_BASE"),
                )
                gw.register_provider(provider, cfg)
                registered.append(provider)
                print(f"[BotBrain] Registered provider from config: {provider}")

        # Then check environment variables for other providers
        for pname, env_key in provider_env_keys.items():
            if pname in registered:
                continue  # Skip if already registered from config
            key = os.environ.get(env_key, "")
            if key:
                cfg = ProviderConfig(
                    provider_name=pname,
                    model=default_models[pname],
                    api_key=key,
                    api_base=os.environ.get(f"{pname.upper()}_API_BASE"),
                )
                gw.register_provider(pname, cfg)
                registered.append(pname)

        if not registered:
            return None, None, None
        primary = (
            DEFAULT_LLM_PROVIDER
            if DEFAULT_LLM_PROVIDER in registered
            else registered[0]
        )
        model = default_models.get(primary, "")
        temp = float(DEFAULT_LLM_CONFIG.get("temperature", 0.7))
        return gw, primary, (model, temp)
    except Exception as exc:
        print(f"[BotBrain] Gateway init failed: {exc}")
        return None, None, None


class BotBrain:
    """LLM-driven intent recognizer for the Feishu bot.

    Converts raw user text + conversation context into a structured ActionPlan.
    Falls back to deterministic keyword matching when LLM is unavailable.
    """

    _CONFIRM_TTL = timedelta(minutes=5)

    def __init__(
        self,
        projects: List[Dict[str, str]],
        llm_provider: Optional[str] = None,
        llm_api_key: Optional[str] = None,
    ):
        self.projects = projects
        self._gw, self._provider, self._model_cfg = _make_gateway(
            llm_provider, llm_api_key
        )
        if self._gw:
            m, _ = self._model_cfg
            print(f"[BotBrain] LLM ready: {self._provider}/{m}")
        else:
            print("[BotBrain] No LLM API key found — falling back to keyword dispatch")

    def think(self, text: str, ctx: ConversationContext) -> ActionPlan:
        """Main entry: text + context → ActionPlan."""
        if self._gw:
            try:
                return asyncio.run(self._think_llm(text, ctx))
            except Exception as exc:
                print(f"[BotBrain] LLM call failed, using fallback: {exc}")
        return self._think_deterministic(text, ctx)

    def build_confirmation(
        self,
        action: str,
        params: Dict[str, Any],
        summary: str,
        ctx: ConversationContext,
    ) -> PendingConfirmation:
        return PendingConfirmation(
            action=action,
            params=params,
            summary=summary,
            expires_at=datetime.now() + self._CONFIRM_TTL,
        )

    def check_confirmation_reply(self, text: str) -> Optional[bool]:
        """Return True=confirmed, False=cancelled, None=unrelated."""
        t = text.strip().lower()
        if t in _CONFIRM_WORDS:
            return True
        if t in _CANCEL_WORDS:
            return False
        return None

    async def _think_llm(
        self,
        text: str,
        ctx: ConversationContext,
        chat_id: Optional[str] = None,
        max_retries: int = 2,
    ) -> ActionPlan:
        from sail_server.utils.llm.gateway import LLMExecutionConfig
        import time

        start_time = time.time()
        slugs = [p.get("slug", p.get("label", "")) for p in self.projects]
        prompt = _BRAIN_SYSTEM.format(
            mode=ctx.mode,
            active_workspace=ctx.active_workspace or "None",
            projects=", ".join(slugs) if slugs else "None",
            history=ctx.history_text() or "(无历史)",
            user_text=text,
        )

        # Log the prompt for debugging
        chat_prefix = f"[{chat_id}] " if chat_id else ""
        print(f"\n{'=' * 60}")
        print(f"{chat_prefix}[LLM] Prompt ({len(prompt)} chars):")
        print(f"{prompt[:500]}{'...' if len(prompt) > 500 else ''}")
        print(f"{'=' * 60}")

        model, temp = self._model_cfg
        config = LLMExecutionConfig(
            provider=self._provider,
            model=model,
            temperature=temp,
            max_tokens=512,
            enable_caching=False,
            timeout=30,  # 设置30秒超时，避免长时间等待
        )

        # 重试循环
        for attempt in range(max_retries + 1):
            try:
                result = await self._gw.execute(prompt, config)
                raw = result.content.strip()
                elapsed = time.time() - start_time

                # 检查空响应
                if not raw:
                    print(
                        f"{chat_prefix}[LLM] WARNING: Empty response (attempt {attempt + 1}/{max_retries + 1})"
                    )
                    if attempt < max_retries:
                        print(f"{chat_prefix}[LLM] Retrying in 1s...")
                        await asyncio.sleep(1)
                        continue
                    else:
                        raise Exception("LLM returned empty response after all retries")

                # Log the raw response
                print(
                    f"{chat_prefix}[LLM] Response ({elapsed:.2f}s, {len(raw)} chars, attempt {attempt + 1}):"
                )
                print(f"{raw[:800]}{'...' if len(raw) > 800 else ''}")

                # Clean up markdown code blocks
                raw_cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
                raw_cleaned = re.sub(r"\s*```$", "", raw_cleaned)

                data = self._parse_llm_json(raw_cleaned, chat_id=chat_id)

                action = data.get("action", "chat")
                print(f"{chat_prefix}[LLM] Parsed action: {action}")

                return ActionPlan(
                    action=action,
                    params=data.get("params", {}),
                    confirm_required=bool(data.get("confirm_required", False)),
                    confirm_summary=data.get("confirm_summary", ""),
                    reply=data.get("reply", ""),
                )

            except Exception as exc:
                elapsed = time.time() - start_time
                if attempt < max_retries:
                    print(
                        f"{chat_prefix}[LLM] Attempt {attempt + 1} failed after {elapsed:.2f}s: {exc}"
                    )
                    print(f"{chat_prefix}[LLM] Retrying...")
                    await asyncio.sleep(1)
                    continue
                else:
                    print(
                        f"{chat_prefix}[LLM] ERROR after {elapsed:.2f}s (all {max_retries + 1} attempts failed): {type(exc).__name__}: {exc}"
                    )
                    import traceback

                    traceback.print_exc()
                    raise

    async def think_with_feedback(
        self,
        text: str,
        ctx: ConversationContext,
        chat_id: str,
        message_id: str,
        agent: "FeishuBotAgent",
    ) -> Tuple[ActionPlan, Optional[str]]:
        """Think with UX feedback - returns (ActionPlan, thinking_card_message_id or None)."""
        # Send a thinking progress card
        thinking_card = CardRenderer.progress(
            "正在理解你的意图", "AI正在分析中，请稍候..."
        )
        thinking_mid = agent._reply_card(
            message_id, thinking_card, "thinking", {"user_text": text[:50]}
        )

        try:
            if self._gw:
                plan = await self._think_llm(text, ctx, chat_id=chat_id)
                return plan, thinking_mid
            else:
                # Fallback to deterministic without thinking card
                return self._think_deterministic(text, ctx), None
        except Exception as exc:
            # Update thinking card to show error
            if thinking_mid:
                error_card = CardRenderer.error(
                    "AI处理失败",
                    f"理解你的指令时出错：{str(exc)[:100]}\n已切换到备用模式。",
                    context_path=ctx.active_workspace or "unknown",
                )
                agent._update_card(thinking_mid, error_card)
            raise

    def _parse_llm_json(self, raw: str, chat_id: Optional[str] = None) -> dict:
        """Parse JSON from LLM response with robust error handling.

        LLMs often return malformed JSON with:
        - Single quotes instead of double quotes
        - Trailing commas
        - Missing quotes around property names
        - Python-style True/False/None instead of true/false/null
        """
        import ast

        chat_prefix = f"[{chat_id}] " if chat_id else ""

        # Try standard JSON parsing first
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"{chat_prefix}[LLM] JSON parse failed (attempt 1): {e}")

        # Fix common LLM JSON issues
        cleaned = raw

        # Replace Python-style booleans and None with JSON equivalents
        cleaned = re.sub(r"\bTrue\b", "true", cleaned)
        cleaned = re.sub(r"\bFalse\b", "false", cleaned)
        cleaned = re.sub(r"\bNone\b", "null", cleaned)

        # Try JSON parsing again after boolean fixes
        try:
            result = json.loads(cleaned)
            print(f"{chat_prefix}[LLM] JSON parsed after boolean fix")
            return result
        except json.JSONDecodeError as e:
            print(
                f"{chat_prefix}[LLM] JSON parse failed (attempt 2 after boolean fix): {e}"
            )

        # Try to use ast.literal_eval as a fallback for Python dict-like structures
        try:
            # This handles single quotes and other Python syntax
            result = ast.literal_eval(cleaned)
            if isinstance(result, dict):
                print(f"{chat_prefix}[LLM] Parsed with ast.literal_eval")
                return result
        except (ValueError, SyntaxError) as e:
            print(f"{chat_prefix}[LLM] ast.literal_eval failed: {e}")

        # Last resort: try to extract JSON-like structure with regex
        # Look for key-value pairs and reconstruct
        try:
            # Simple pattern to extract action and other fields
            pattern = r'["\']?action["\']?\s*[:=]\s*["\']([^"\']+)["\']'
            action_match = re.search(pattern, cleaned, re.IGNORECASE)
            if action_match:
                print(
                    f"{chat_prefix}[LLM] Extracted action via regex: {action_match.group(1)}"
                )
                return {"action": action_match.group(1)}
        except Exception as e:
            print(f"{chat_prefix}[LLM] Regex extraction failed: {e}")

        # If all parsing fails, return a default action
        print(f"{chat_prefix}[LLM] All parsing attempts failed. Raw: {raw[:300]}")
        return {"action": "chat", "reply": "抱歉，我处理请求时遇到了技术问题。"}

    def _think_deterministic(self, text: str, ctx: ConversationContext) -> ActionPlan:
        t = text.lower().strip()

        for kw, (action, params) in _BRAIN_FALLBACK_ACTIONS.items():
            if kw in t:
                return ActionPlan(action=action, params=params)

        # 快速工作区切换指令（无需等待LLM）
        switch_keywords = [
            "使用",
            "进入",
            "切换到",
            "切到",
            "use",
            "switch to",
            "enter",
        ]
        if any(k in t for k in switch_keywords):
            path = _extract_path_from_text(text, self.projects)
            if path:
                # 设置active_workspace
                ctx.mode = "coding"
                ctx.active_workspace = path
                return ActionPlan(
                    action="chat",
                    reply=f"已切换到工作区：{Path(path).name}\n现在可以直接发送指令给这个工作区。",
                )

        if any(k in t for k in ["start", "启动", "开启", "打开", "open"]):
            path = _extract_path_from_text(text, self.projects)
            return ActionPlan(action="start_workspace", params={"path": path})

        if any(k in t for k in ["导入", "import"]) and any(
            k in t for k in ["小说", "文本", "txt", "text", "novel", "书"]
        ):
            file_name = self._extract_file_name(text)
            return ActionPlan(action="import_text", params={"file_name": file_name})

        if any(k in t for k in ["stop", "停止", "关闭", "结束", "kill"]):
            path = _extract_path_from_text(text, self.projects)
            return ActionPlan(
                action="stop_workspace",
                params={"path": path},
                confirm_required=True,
                confirm_summary=f"停止 {'所有会话' if not path else path}",
            )

        if ctx.mode == "coding" and ctx.active_workspace:
            return ActionPlan(
                action="send_task", params={"task": text, "path": ctx.active_workspace}
            )

        if any(
            k in t
            for k in [
                "code",
                "写",
                "实现",
                "帮我",
                "task",
                "任务",
                "帮",
                "修",
                "fix",
                "add",
                "implement",
            ]
        ):
            path = _extract_path_from_text(text, self.projects)
            return ActionPlan(action="send_task", params={"task": text, "path": path})

        return ActionPlan(
            action="chat",
            reply=(
                "我理解你说的可能是一个开发任务，但我需要知道目标工作区。\n"
                "可以说：'启动 sailzen' 或 '使用 sailzen' 或 '进入 ~/projects/myapp'"
            ),
        )

    def _extract_file_name(self, text: str) -> Optional[str]:
        """Extract a .txt file name from user text."""
        match = re.search(r"[\w\u4e00-\u9fff\-\.]+\.txt", text)
        if match:
            return match.group()
        for quote_char in ["《", "》", '"', '"', '"', "'"]:
            text = text.replace(quote_char, '"')
        match = re.search(r'"([^"]+)"', text)
        if match:
            return match.group(1)
        return None


# ---------------------------------------------------------------------------
# Main Bot Agent
# ---------------------------------------------------------------------------


class FeishuBotAgent:
    """Feishu bot that bridges messages to OpenCode web sessions."""

    CONTEXT_STATE_FILE = Path.home() / ".config" / "feishu-agent" / "contexts.json"

    def __init__(self, config: AgentConfig):
        self.config = config
        self.state_store = SessionStateStore()
        self.state_store.load_from_disk()
        self.session_mgr = OpenCodeSessionManager(
            config.base_port, state_store=self.state_store
        )
        self.op_tracker = OperationTracker()
        self.confirm_mgr = ConfirmationManager()
        self.card_tracker = CardMessageTracker()
        self.lark_client: Optional[lark.Client] = None
        self.brain = BotBrain(
            config.projects,
            llm_provider=config.llm_provider,
            llm_api_key=config.llm_api_key,
        )
        self._contexts: Dict[str, ConversationContext] = {}
        self._load_contexts()
        self._health_monitor = SessionHealthMonitor(
            self.state_store,
            health_check_fn=self._health_check_fn,
            auto_restart=config.auto_restart,
        )
        self.state_store.register_hook(self._on_state_change)

    # ------------------------------------------------------------------
    # Feishu messaging
    # ------------------------------------------------------------------

    def _send_to_chat(self, chat_id: str, text: str) -> None:
        """Send a text message to a Feishu chat."""
        if not self.lark_client:
            print(f"[Feishu] (no client) Would send to {chat_id}: {text[:80]}")
            return
        try:
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
            resp = self.lark_client.im.v1.message.create(request)
            if not resp.success():
                print(f"[Feishu] Send failed: {resp.msg}")
        except Exception as exc:
            print(f"[Feishu] Send error: {exc}")

    def _reply_to_message(self, message_id: str, text: str) -> None:
        """Reply to a specific Feishu message (thread reply)."""
        if not self.lark_client:
            print(f"[Feishu] (no client) Would reply to {message_id}: {text[:80]}")
            return
        try:
            content = json.dumps({"text": text}, ensure_ascii=False)
            request = (
                ReplyMessageRequest.builder()
                .message_id(message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(content)
                    .msg_type("text")
                    .build()
                )
                .build()
            )
            resp = self.lark_client.im.v1.message.reply(request)
            if not resp.success():
                print(f"[Feishu] Reply failed: {resp.msg}")
        except Exception as exc:
            print(f"[Feishu] Reply error: {exc}")

    def _send_card(
        self,
        chat_id: str,
        card: dict,
        card_type: str = "",
        context: Optional[dict] = None,
    ) -> Optional[str]:
        """Send an interactive card to a chat. Returns message_id on success."""
        if not self.lark_client:
            print(
                f"[Feishu] (no client) Would send card to {chat_id}: {card.get('header', {}).get('title', {}).get('content', '')}"
            )
            return None
        try:
            content = card_to_feishu_content(card)
            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("interactive")
                    .content(content)
                    .build()
                )
                .build()
            )
            resp = self.lark_client.im.v1.message.create(request)
            if resp.success() and resp.data and resp.data.message_id:
                mid = resp.data.message_id
                if card_type:
                    self.card_tracker.register(mid, card_type, context or {})
                return mid
            else:
                print(f"[Feishu] Card send failed: {resp.msg}")
                self._send_to_chat(chat_id, text_fallback(card))
                return None
        except Exception as exc:
            print(f"[Feishu] Card send error: {exc}")
            try:
                self._send_to_chat(chat_id, text_fallback(card))
            except Exception:
                pass
            return None

    def _reply_card(
        self,
        message_id: str,
        card: dict,
        card_type: str = "",
        context: Optional[dict] = None,
    ) -> Optional[str]:
        """Reply with an interactive card to a specific message. Returns message_id on success."""
        if not self.lark_client:
            print(f"[Feishu] (no client) Would reply card to {message_id}")
            return None
        try:
            content = card_to_feishu_content(card)
            request = (
                ReplyMessageRequest.builder()
                .message_id(message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(content)
                    .msg_type("interactive")
                    .build()
                )
                .build()
            )
            resp = self.lark_client.im.v1.message.reply(request)
            if resp.success() and resp.data and resp.data.message_id:
                mid = resp.data.message_id
                if card_type:
                    self.card_tracker.register(mid, card_type, context or {})
                return mid
            else:
                print(f"[Feishu] Card reply failed: {resp.msg}")
                self._reply_to_message(message_id, text_fallback(card))
                return None
        except Exception as exc:
            print(f"[Feishu] Card reply error: {exc}")
            try:
                self._reply_to_message(message_id, text_fallback(card))
            except Exception:
                pass
            return None

    def _update_card(self, message_id: str, card: dict) -> bool:
        """Update an existing card message in-place (1.2.1)."""
        if not self.lark_client:
            print(f"[Feishu] (no client) Would update card {message_id}")
            return False
        try:
            content = card_to_feishu_content(card)
            request = (
                PatchMessageRequest.builder()
                .message_id(message_id)
                .request_body(
                    PatchMessageRequestBody.builder().content(content).build()
                )
                .build()
            )
            resp = self.lark_client.im.v1.message.patch(request)
            if not resp.success():
                print(f"[Feishu] Card update failed: {resp.msg}")
                return False
            return True
        except Exception as exc:
            print(f"[Feishu] Card update error: {exc}")
            return False

    def _health_check_fn(self, path: str, port: int) -> bool:
        client = OpenCodeWebClient(port=port)
        return client.is_healthy()

    def _on_state_change(
        self,
        path: str,
        prev: SessionState,
        next_state: SessionState,
        entry: Any,
    ) -> None:
        if next_state == SessionState.ERROR:
            session = self.session_mgr._sessions.get(path)
            chat_id = (session.chat_id if session else None) or getattr(
                entry, "chat_id", None
            )
            if chat_id:
                card = CardRenderer.session_status(
                    path=path,
                    state="error",
                    last_error=getattr(entry, "last_error", None) or "会话异常终止",
                    activities=entry.recent_activities()
                    if hasattr(entry, "recent_activities")
                    else [],
                )
                self._send_card(chat_id, card, "session_status", {"path": path})

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    def _handle_card_action(self, data) -> Any:
        """Handle card button click actions.

        Returns P2CardActionTriggerResponse to acknowledge the action.
        """
        try:
            if not data or not data.event or not data.event.action:
                return None

            action = data.event.action
            value = action.value if hasattr(action, "value") else {}

            # value could be a dict or string
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    value = {}

            action_type = value.get("action") if isinstance(value, dict) else None
            path = value.get("path") if isinstance(value, dict) else None

            # Get context info
            context = data.event.context if hasattr(data.event, "context") else None
            chat_id = context.open_chat_id if context else None
            message_id = context.open_message_id if context else None

            if not chat_id or not action_type:
                print(f"[CardAction] Missing chat_id or action_type")
                return None

            print(f"[CardAction] {action_type} for {path} in {chat_id}")

            # Execute the action in background thread
            ctx = self._get_context(chat_id)
            plan = ActionPlan(action=action_type, params={"path": path} if path else {})

            threading.Thread(
                target=self._execute_plan_with_card,
                args=(plan, chat_id, message_id, ctx),
                daemon=True,
            ).start()

            # Return success response to Feishu (required!)
            from lark_oapi.event.callback.model.p2_card_action_trigger import (
                P2CardActionTriggerResponse,
            )

            # 必须返回 P2CardActionTriggerResponse，传入 dict 结构
            resp = P2CardActionTriggerResponse(
                {
                    "toast": {
                        "type": "info",
                        "content": "处理中...",
                        "i18n": {"zh_cn": "处理中...", "en_us": "Processing..."},
                    }
                }
            )
            return resp

        except Exception as exc:
            print(f"[CardAction] Error: {exc}")
            import traceback

            traceback.print_exc()
            return None

    def _handle_message(self, data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        """Handle incoming Feishu message."""
        try:
            if not data or not data.event or not data.event.message:
                return

            message = data.event.message
            if message.message_type != "text":
                print(f"[Bot] Ignoring non-text message: {message.message_type}")
                return

            try:
                content = json.loads(message.content or "{}")
            except json.JSONDecodeError:
                return

            text = content.get("text", "").strip()
            chat_id = message.chat_id
            message_id = message.message_id

            if not text or not chat_id:
                return

            print(f"\n[Bot] Message from {chat_id}: {text[:80]}")

            # Handle in a background thread to avoid blocking the SDK
            threading.Thread(
                target=self._process_message,
                args=(text, chat_id, message_id),
                daemon=True,
            ).start()

        except Exception as exc:
            print(f"[Bot] handle_message error: {exc}")
            import traceback

            traceback.print_exc()

    def _get_context(self, chat_id: str) -> ConversationContext:
        if chat_id not in self._contexts:
            self._contexts[chat_id] = ConversationContext(chat_id=chat_id)
        ctx = self._contexts[chat_id]
        if ctx.is_pending_expired():
            ctx.clear_pending()
        return ctx

    def _process_message(self, text: str, chat_id: str, message_id: str) -> None:
        """Process a message (runs in background thread)."""
        text = re.sub(r"@\S+", "", text).strip()
        if not text:
            return

        ctx = self._get_context(chat_id)
        ctx.push("user", text)

        self._dispatch_message(text, chat_id, message_id, ctx)

    def _dispatch_message(
        self, text: str, chat_id: str, message_id: str, ctx: ConversationContext
    ) -> None:
        force_flag = "--force" in text or "强制" in text

        if ctx.pending:
            decision = self.brain.check_confirmation_reply(text)
            if decision is True:
                plan = ActionPlan(action=ctx.pending.action, params=ctx.pending.params)
                ctx.clear_pending()
                self._execute_plan_with_card(plan, chat_id, message_id, ctx)
                return
            elif decision is False:
                ctx.clear_pending()
                card = CardRenderer.result("已取消", "操作已取消。", success=False)
                self._reply_card(message_id, card)
                ctx.push("bot", "已取消")
                return
            else:
                ctx.clear_pending()
                self._reply_to_message(message_id, "确认已超时，请重新发起指令。")
                return

        pending_id = self._find_pending_id_from_text(text)
        if pending_id:
            pending = self.confirm_mgr.consume(pending_id)
            if pending:
                plan = ActionPlan(action=pending.action, params=pending.params)
                self._execute_plan_with_card(plan, chat_id, message_id, ctx)
                return

        # Use async think_with_feedback to show thinking indicator
        thinking_mid = None
        try:
            import asyncio

            plan, thinking_mid = asyncio.run(
                self.brain.think_with_feedback(text, ctx, chat_id, message_id, self)
            )
        except Exception as exc:
            # If think_with_feedback failed (including after error card update), fall back
            print(f"[{chat_id}] think_with_feedback failed: {exc}")
            plan = self.brain._think_deterministic(text, ctx)
            # If there was a thinking card, update it to show fallback
            if thinking_mid:
                fallback_card = CardRenderer.result(
                    "已切换到备用模式",
                    "AI处理遇到问题，正在使用备用模式响应。",
                    success=True,
                )
                self._update_card(thinking_mid, fallback_card)

        if plan.action in ("chat", "clarify"):
            reply = plan.reply or "我不太确定你的意思，能再描述一下吗？"
            ctx.push("bot", reply[:200])
            # Replace thinking card with reply, or send new message
            if thinking_mid:
                chat_card = CardRenderer.result("回复", reply, success=True)
                self._update_card(thinking_mid, chat_card)
            else:
                self._reply_to_message(message_id, reply)
            return

        task_text = plan.params.get("task", "")
        has_running = any(
            s.process_status == "running" for s in self.session_mgr.list_sessions()
        )
        risk = classify_risk(plan.action, task_text, has_running)

        if (
            risk == RiskLevel.CONFIRM_REQUIRED
            and not force_flag
            and not self.confirm_mgr.should_bypass(plan.action)
        ):
            pending = self.confirm_mgr.create(
                action=plan.action,
                params=plan.params,
                summary=plan.confirm_summary or plan.action,
                risk_level=risk,
                can_undo=(plan.action == "stop_workspace"),
            )
            ctx.pending = PendingConfirmation(
                action=plan.action,
                params=plan.params,
                summary=pending.summary,
                expires_at=datetime.now() + self.brain._CONFIRM_TTL,
            )
            card = CardRenderer.confirmation(
                action_summary=pending.summary,
                risk_level=risk.value,
                can_undo=pending.can_undo,
                pending_id=pending.pending_id,
            )
            # Replace thinking card with confirmation
            if thinking_mid:
                self._update_card(thinking_mid, card)
                self.card_tracker.register(
                    thinking_mid, "confirmation", {"pending_id": pending.pending_id}
                )
            else:
                self._reply_card(
                    message_id, card, "confirmation", {"pending_id": pending.pending_id}
                )
            ctx.push("bot", "需要确认: " + pending.summary)
            return

        if risk == RiskLevel.GUARDED and not force_flag:
            running_count = sum(
                1
                for s in self.session_mgr.list_sessions()
                if s.process_status == "running"
            )
            if running_count >= 3:
                card = CardRenderer.result(
                    "资源提示",
                    "当前已有 "
                    + str(running_count)
                    + " 个会话运行中，继续启动可能影响性能。\n回复「确认」继续，或「取消」放弃。",
                    success=False,
                )
                ctx.pending = PendingConfirmation(
                    action=plan.action,
                    params=plan.params,
                    summary="在资源紧张时启动新会话",
                    expires_at=datetime.now() + self.brain._CONFIRM_TTL,
                )
                if thinking_mid:
                    self._update_card(thinking_mid, card)
                else:
                    self._reply_card(message_id, card)
                return

        # Execute the plan - for non-confirmation actions, remove thinking card first
        # or let _execute_plan_with_card handle the UI
        if thinking_mid:
            # Delete the thinking card by sending a result card in its place for simple actions
            # For complex actions like start_workspace, the progress card will replace it
            if plan.action in ("show_help", "show_status"):
                # These don't need the thinking card anymore
                pass
            # Store thinking_mid so _execute_plan_with_card can use it if needed
            # For now, we'll let the action handlers send their own cards
        self._execute_plan_with_card(plan, chat_id, message_id, ctx, thinking_mid)

    def _find_pending_id_from_text(self, text: str) -> Optional[str]:
        import re as _re

        m = _re.search(r"pending_id[=:]\s*([a-f0-9]{12})", text)
        return m.group(1) if m else None

    def _execute_plan_with_card(
        self,
        plan: ActionPlan,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        thinking_mid: Optional[str] = None,
    ) -> None:
        action = plan.action
        params = plan.params

        if action == "show_help":
            self._reply_to_message(message_id, self._help())
            return

        if action == "show_status":
            sessions = self.session_mgr.list_sessions()
            session_dicts = [
                {
                    "path": s.path,
                    "state": s.process_status,
                    "port": s.port,
                }
                for s in sessions
            ]
            card = CardRenderer.all_sessions(session_dicts)
            self._reply_card(message_id, card, "all_sessions")
            ctx.push("bot", "状态已显示")
            return

        if action == "start_workspace":
            raw_path = params.get("path") or ""
            path = _resolve_path(raw_path, self.config.projects)
            if not path:
                projects = self.config.projects
                state_map: Dict[str, str] = {}
                for s in self.session_mgr.list_sessions():
                    state_map[s.path] = s.process_status
                card = CardRenderer.workspace_selection(
                    projects, session_states=state_map
                )
                self._reply_card(message_id, card, "workspace_selection")
                return

            self.state_store.get_or_create(path, chat_id)
            op_id = self.op_tracker.start(path, "启动 " + Path(path).name, timeout=30.0)
            progress_card = CardRenderer.progress(
                "正在启动 " + Path(path).name, "初始化 OpenCode 服务..."
            )
            prog_mid = self._reply_card(
                message_id, progress_card, "progress", {"op_id": op_id, "path": path}
            )

            def do_start() -> None:
                ok, session, msg = self.session_mgr.ensure_running(path, chat_id)
                self.op_tracker.finish(op_id)
                if ok:
                    ctx.mode = "coding"
                    ctx.active_workspace = session.path
                    self._save_contexts()
                    entry = self.state_store.get(path)
                    activities = entry.recent_activities() if entry else []
                    result_card = CardRenderer.session_status(
                        path=session.path,
                        state="running",
                        port=session.port,
                        pid=session.pid,
                        activities=activities,
                    )
                    if prog_mid:
                        self._update_card(prog_mid, result_card)
                    else:
                        self._send_card(
                            chat_id, result_card, "session_status", {"path": path}
                        )
                    ctx.push("bot", "OpenCode 已启动: " + session.path)
                else:
                    err_card = CardRenderer.error(
                        "启动失败",
                        msg,
                        context_path=path,
                        retry_action={"action": "start_workspace", "path": raw_path},
                    )
                    if prog_mid:
                        self._update_card(prog_mid, err_card)
                    else:
                        self._send_card(chat_id, err_card)

            threading.Thread(target=do_start, daemon=True).start()
            return

        if action == "stop_workspace":
            raw_path = params.get("path") or ""
            path = _resolve_path(raw_path, self.config.projects) if raw_path else None

            undo_deadline = time.time() + 30.0

            if path:
                ok, msg = self.session_mgr.stop_session(path)
                if ok:
                    ctx.mode = "idle"
                    ctx.active_workspace = None
                    self._save_contexts()
                result_card = CardRenderer.result(
                    "已停止" if ok else "停止失败",
                    Path(path).name + " 已停止。" if ok else msg,
                    success=ok,
                    can_undo=ok,
                    undo_deadline=undo_deadline if ok else None,
                    context_path=path,
                )
                self._reply_card(
                    message_id,
                    result_card,
                    "stop_result",
                    {"path": path, "undo_deadline": undo_deadline},
                )
                ctx.push("bot", "已停止: " + path)
            else:
                sessions = self.session_mgr.list_sessions()
                if not sessions:
                    self._reply_to_message(message_id, "没有正在运行的会话。")
                    return
                results = []
                for s in sessions:
                    ok, msg = self.session_mgr.stop_session(s.path)
                    results.append(Path(s.path).name + ": " + ("已停止" if ok else msg))
                ctx.mode = "idle"
                ctx.active_workspace = None
                self._save_contexts()
                result_card = CardRenderer.result(
                    "全部停止", "\n".join(results), success=True
                )
                self._reply_card(message_id, result_card)
                ctx.push("bot", "全部停止")
            return

        if action == "send_task":
            task_text = params.get("task", "")
            raw_path = params.get("path") or ""
            path = _resolve_path(raw_path, self.config.projects) if raw_path else None

            if not path:
                running = [
                    s
                    for s in self.session_mgr.list_sessions()
                    if s.process_status == "running"
                ]
                if not running:
                    card = CardRenderer.error(
                        "未找到会话",
                        "没有正在运行的 OpenCode 会话。\n请先启动一个，例如：启动 sailzen",
                    )
                    self._reply_card(message_id, card)
                    return
                if len(running) == 1:
                    path = running[0].path
                elif ctx.active_workspace:
                    path = ctx.active_workspace
                else:
                    names = [Path(s.path).name for s in running]
                    self._reply_to_message(
                        message_id,
                        "有多个会话运行中：" + ", ".join(names) + "\n请指定工作区",
                    )
                    return

            op_id = self.op_tracker.start(path, task_text[:60], timeout=300.0)
            progress_card = CardRenderer.progress(
                "处理中",
                task_text[:100] + ("..." if len(task_text) > 100 else ""),
            )
            prog_mid = self._reply_card(
                message_id, progress_card, "progress", {"op_id": op_id, "path": path}
            )

            def do_task() -> None:
                ok, session, start_msg = self.session_mgr.ensure_running(path, chat_id)
                if not ok:
                    self.op_tracker.finish(op_id)
                    err_card = CardRenderer.error(
                        "启动失败", start_msg, context_path=path
                    )
                    if prog_mid:
                        self._update_card(prog_mid, err_card)
                    return

                ctx.mode = "coding"
                ctx.active_workspace = session.path
                self._save_contexts()

                if not task_text:
                    self.op_tracker.finish(op_id)
                    card = CardRenderer.result(
                        "就绪",
                        "OpenCode 已就绪，请描述你的任务。",
                        success=True,
                        context_path=path,
                    )
                    if prog_mid:
                        self._update_card(prog_mid, card)
                    return

                reply = self.session_mgr.send_task(path, task_text)
                self.op_tracker.finish(op_id)

                if not reply:
                    reply = "（任务已完成，无文字输出）"
                result_card = CardRenderer.result(
                    "任务完成", reply, success=True, context_path=path
                )
                if prog_mid:
                    self._update_card(prog_mid, result_card)
                else:
                    self._send_card(chat_id, result_card)
                ctx.push("bot", "任务完成")

            threading.Thread(target=do_task, daemon=True).start()
            return

        if action == "import_text":
            file_name = params.get("file_name")
            books_path = self._resolve_books_path()

            if not books_path:
                card = CardRenderer.error(
                    "未配置 books 目录",
                    "请在 bot 配置文件的 projects 中添加 slug 为 'books' 的项目。",
                )
                self._reply_card(message_id, card)
                return

            books_dir = Path(books_path)
            if not books_dir.exists():
                card = CardRenderer.error(
                    "目录不存在", f"books 目录不存在: {books_path}"
                )
                self._reply_card(message_id, card)
                return

            txt_files = sorted(books_dir.glob("*.txt"))

            if not file_name and not txt_files:
                card = CardRenderer.result(
                    "无可导入文件",
                    f"books 目录下没有 .txt 文件: {books_path}",
                    success=False,
                )
                self._reply_card(message_id, card)
                return

            if not file_name:
                file_list = "\n".join(
                    f"  {i + 1}. {f.name} ({f.stat().st_size / 1024:.0f} KB)"
                    for i, f in enumerate(txt_files)
                )
                card = CardRenderer.result(
                    "可导入的小说文件",
                    f"books 目录下共 {len(txt_files)} 个 txt 文件：\n\n{file_list}"
                    + "\n\n请回复「导入 <文件名>」来导入指定文件。",
                    success=True,
                    context_path=books_path,
                )
                self._reply_card(message_id, card)
                ctx.push("bot", f"列出 {len(txt_files)} 个文件")
                return

            target_file = books_dir / file_name
            if not target_file.exists():
                candidates = [
                    f for f in txt_files if file_name.lower() in f.name.lower()
                ]
                if len(candidates) == 1:
                    target_file = candidates[0]
                    file_name = target_file.name
                elif candidates:
                    names = "\n".join(f"  - {f.name}" for f in candidates)
                    card = CardRenderer.result(
                        "找到多个匹配文件",
                        f"匹配「{file_name}」的文件：\n{names}\n\n请指定完整文件名。",
                        success=False,
                    )
                    self._reply_card(message_id, card)
                    return
                else:
                    card = CardRenderer.error(
                        "文件未找到",
                        f"在 books 目录下未找到「{file_name}」。",
                    )
                    self._reply_card(message_id, card)
                    return

            file_size_kb = target_file.stat().st_size / 1024
            op_id = self.op_tracker.start(
                books_path, f"导入 {file_name}", timeout=600.0
            )
            progress_card = CardRenderer.progress(
                f"正在导入 {file_name}",
                f"文件大小: {file_size_kb:.0f} KB\n正在启动 OpenCode 并加载文本导入 skill...",
            )
            prog_mid = self._reply_card(
                message_id,
                progress_card,
                "progress",
                {"op_id": op_id, "path": books_path},
            )

            def do_import() -> None:
                ok, session, start_msg = self.session_mgr.ensure_running(
                    books_path, chat_id
                )
                if not ok:
                    self.op_tracker.finish(op_id)
                    err_card = CardRenderer.error(
                        "启动失败", start_msg, context_path=books_path
                    )
                    if prog_mid:
                        self._update_card(prog_mid, err_card)
                    return

                ctx.mode = "coding"
                ctx.active_workspace = session.path
                self._save_contexts()

                import_task = (
                    f"使用 /sailzen-ai-text-import skill 导入小说文件。\n"
                    f"文件路径: {target_file}\n"
                    f"请按照 skill 的完整工作流程执行：\n"
                    f"1. 检测文件编码并读取\n"
                    f"2. 采样分析章节模式\n"
                    f"3. 生成临时导入脚本 _temp_import.py\n"
                    f"4. 运行脚本分析章节\n"
                    f"5. 展示分析报告等待我确认后上传到服务器"
                )

                reply = self.session_mgr.send_task(books_path, import_task)
                self.op_tracker.finish(op_id)

                if not reply:
                    reply = "导入任务已提交，请等待分析结果。"
                result_card = CardRenderer.result(
                    f"导入分析: {file_name}",
                    reply,
                    success=True,
                    context_path=books_path,
                )
                if prog_mid:
                    self._update_card(prog_mid, result_card)
                else:
                    self._send_card(chat_id, result_card)
                ctx.push("bot", f"导入分析完成: {file_name}")

            threading.Thread(target=do_import, daemon=True).start()
            return

        self._reply_to_message(message_id, "未知动作: " + action)

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _resolve_books_path(self) -> Optional[str]:
        for p in self.config.projects:
            if p.get("slug") == "books":
                return p.get("path", "")
        return None

    def _help(self) -> str:
        slugs = [p.get("slug", "") for p in self.config.projects]
        proj_line = f"  配置的项目: {', '.join(slugs)}\n" if slugs else ""
        llm_status = "LLM 已启用" if self.brain._gw else "LLM 未配置（关键词兜底模式）"
        sep = "=" * 32
        return (
            f"Feishu OpenCode Bridge v7.0\n{sep}\n"
            "直接用自然语言告诉我你想做什么：\n\n"
            "  启动工作区：\n"
            "    '打开 sailzen'\n"
            "    '启动 ~/projects/myapp'\n\n"
            "  发送编码任务：\n"
            "    '帮我实现用户登录'\n"
            "    'fix the bug in auth.py'\n"
            "    '在 sailzen 里加一个健康检查接口'\n\n"
            "  导入小说文本：\n"
            "    '导入小说'\n"
            "    '导入 xxx.txt'\n\n"
            "  管理会话：\n"
            "    '查看状态'\n"
            "    '停止所有会话'\n\n"
            f"{proj_line}"
            f"[{llm_status}]"
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _send_interim(self, chat_id: str, text: str) -> None:
        try:
            self._send_to_chat(chat_id, text)
        except Exception:
            pass

    def _load_contexts(self) -> None:
        """Load conversation contexts from disk."""
        if not self.CONTEXT_STATE_FILE.exists():
            return
        try:
            with open(self.CONTEXT_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                chat_id = item.get("chat_id", "")
                if not chat_id:
                    continue
                ctx = ConversationContext.from_dict(item)
                self._contexts[chat_id] = ctx
            if self._contexts:
                print(
                    f"[Context] Loaded {len(self._contexts)} conversation(s) from disk"
                )
        except Exception as exc:
            print(f"[Context] Failed to load contexts: {exc}")

    def _save_contexts(self) -> None:
        """Save conversation contexts to disk (mode + active_workspace only)."""
        try:
            self.CONTEXT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = []
            for chat_id, ctx in self._contexts.items():
                # Only save contexts with active workspace or non-idle mode
                if ctx.active_workspace or ctx.mode != "idle":
                    data.append(ctx.to_dict())
            with open(self.CONTEXT_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            print(f"[Context] Failed to save contexts: {exc}")

    def _cleanup_previous_instances(self) -> None:
        """启动前清理之前意外关闭时遗留的僵尸进程和文件句柄。"""
        print("\n[Cleanup] 检查之前遗留的进程和文件句柄...")

        import subprocess
        import os
        import signal

        # 1. 查找并终止 opencode 进程
        killed_count = 0
        try:
            if sys.platform == "win32":
                # Windows: 使用 tasklist 和 taskkill
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/V"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                )

                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    for line in lines[1:]:  # 跳过标题行
                        if "feishu_agent" in line.lower() or "opencode" in line.lower():
                            parts = line.strip('"').split('","')
                            if len(parts) >= 2:
                                pid = parts[1]
                                print(f"[Cleanup] 发现遗留进程 PID {pid}，正在终止...")
                                subprocess.run(
                                    ["taskkill", "/PID", pid, "/T", "/F"],
                                    check=False,
                                    capture_output=True,
                                )
                                killed_count += 1
            else:
                # Linux/Mac: 使用 ps 和 kill
                result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
                for line in result.stdout.split("\n"):
                    if "feishu_agent" in line.lower() or (
                        "python" in line.lower() and "opencode" in line.lower()
                    ):
                        parts = line.split()
                        if len(parts) >= 2:
                            pid = parts[1]
                            print(f"[Cleanup] 发现遗留进程 PID {pid}，正在终止...")
                            try:
                                os.kill(int(pid), signal.SIGTERM)
                                killed_count += 1
                            except Exception as e:
                                print(f"[Cleanup] 终止失败: {e}")
        except Exception as e:
            print(f"[Cleanup] 进程检查失败: {e}")

        # 2. 检查并关闭端口
        port_cleared = 0
        base_port = self.config.base_port
        for port in range(base_port, base_port + 20):  # 检查基础端口及后续端口
            if self.session_mgr._is_port_open(port):
                print(f"[Cleanup] 端口 {port} 被占用，尝试释放...")
                # 尝试找到并终止占用端口的进程
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
                                if len(parts) >= 5:
                                    pid = parts[-1]
                                    print(
                                        f"[Cleanup] 终止占用端口 {port} 的进程 PID {pid}"
                                    )
                                    subprocess.run(
                                        ["taskkill", "/PID", pid, "/F"],
                                        check=False,
                                        capture_output=True,
                                    )
                                    port_cleared += 1
                    else:
                        result = subprocess.run(
                            ["lsof", "-ti", f":{port}"], capture_output=True, text=True
                        )
                        if result.stdout:
                            pid = result.stdout.strip()
                            print(f"[Cleanup] 终止占用端口 {port} 的进程 PID {pid}")
                            os.kill(int(pid), signal.SIGKILL)
                            port_cleared += 1
                except Exception as e:
                    print(f"[Cleanup] 端口 {port} 释放失败: {e}")

        # 3. 清理日志文件句柄（关闭可能遗留的日志文件）
        log_dir = Path.home() / ".config" / "feishu-agent" / "logs"
        files_closed = 0
        if log_dir.exists():
            for log_file in log_dir.glob("*.log"):
                try:
                    # 尝试打开并立即关闭，确保文件句柄被释放
                    with open(log_file, "a"):
                        pass
                    files_closed += 1
                except Exception:
                    pass

        # 4. 清理状态文件中的无效会话
        invalid_sessions = 0
        for entry in list(self.state_store.all_entries()):
            if entry.state in (SessionState.RUNNING, SessionState.STARTING):
                port = entry.port
                if port and not self.session_mgr._is_port_open(port):
                    print(f"[Cleanup] 清理无效会话状态: {entry.path}")
                    self.state_store.force_set(
                        entry.path,
                        SessionState.ERROR,
                        last_error="Process terminated during cleanup",
                    )
                    invalid_sessions += 1

        # 5. 清理不在当前配置中的历史状态（防止污染新工作区）
        config_paths = set()
        for p in self.config.projects:
            if p.get("path"):
                try:
                    resolved = str(Path(p["path"]).expanduser().resolve())
                    config_paths.add(resolved)
                except Exception:
                    config_paths.add(p["path"])

        orphaned_entries = 0
        for entry in list(self.state_store.all_entries()):
            # 如果路径不在配置中，且目录不存在，则清理
            if entry.path not in config_paths:
                path_exists = False
                try:
                    path_exists = Path(entry.path).exists()
                except Exception:
                    pass

                if not path_exists:
                    print(f"[Cleanup] 清理孤立状态记录（路径不存在）: {entry.path}")
                    self.state_store.remove(entry.path)
                    orphaned_entries += 1

        # 报告清理结果
        total_cleaned = (
            killed_count + port_cleared + invalid_sessions + orphaned_entries
        )
        if total_cleaned > 0:
            print(
                f"[Cleanup] ✅ 清理完成: 终止了 {killed_count} 个进程, 释放了 {port_cleared} 个端口, "
                f"清理了 {invalid_sessions} 个无效会话, 移除了 {orphaned_entries} 个孤立记录"
            )
        else:
            print("[Cleanup] ✅ 未发现遗留的进程或资源")
        print()

    def on_bot_startup(self) -> None:
        """处理启动时的状态恢复，包含防御性检查。"""
        print("[Startup] 恢复会话状态...")

        # 验证配置中的项目路径是否有效
        valid_projects = []
        for p in self.config.projects:
            path = p.get("path", "")
            if not path:
                continue
            try:
                resolved = Path(path).expanduser().resolve()
                if resolved.exists():
                    valid_projects.append(str(resolved))
                else:
                    print(f"[Startup] 警告: 配置项目路径不存在: {path}")
            except Exception as e:
                print(f"[Startup] 警告: 无法解析路径 {path}: {e}")

        # 恢复会话状态
        recovered_count = 0
        error_count = 0

        for entry in self.state_store.all_entries():
            path = entry.path

            # 检查路径是否在有效配置中
            if path not in valid_projects:
                # 路径不在配置中，标记为错误（除非它存在）
                try:
                    if not Path(path).exists():
                        print(f"[Startup] 跳过不在配置中的路径: {path}")
                        self.state_store.force_set(
                            path,
                            SessionState.ERROR,
                            last_error="Path not in configuration",
                        )
                        error_count += 1
                        continue
                except Exception:
                    pass

            if entry.state in (SessionState.RUNNING, SessionState.STARTING):
                session = self.session_mgr._sessions.get(path)
                port = entry.port or (session.port if session else None)
                if port and self.session_mgr._is_port_open(port):
                    print(f"[Startup] Reconnected to {path} on port {port}")
                    if session:
                        session.process_status = "running"
                    recovered_count += 1
                else:
                    print(f"[Startup] Cannot recover {path}, marking error")
                    self.state_store.force_set(
                        path,
                        SessionState.ERROR,
                        last_error="Process not found on startup",
                    )
                    error_count += 1

        if recovered_count > 0 or error_count > 0:
            print(
                f"[Startup] 状态恢复完成: {recovered_count} 个成功, {error_count} 个失败"
            )

    def on_bot_shutdown(self) -> None:
        print("\n[Shutdown] Cleaning up resources...")
        self._health_monitor.stop()
        sessions = self.session_mgr.list_sessions()
        for s in sessions:
            if s.process_status in ("running", "starting"):
                print(f"[Shutdown] Stopping {s.path}")
                self.session_mgr.stop_session(s.path)
        # Also clean up any sessions in error state to release file handles
        for s in sessions:
            if s._stdout_log or s._stderr_log:
                print(f"[Shutdown] Cleaning up file handles for {s.path}")
                if s._stdout_log:
                    try:
                        s._stdout_log.close()
                    except Exception:
                        pass
                    s._stdout_log = None
                if s._stderr_log:
                    try:
                        s._stderr_log.close()
                    except Exception:
                        pass
                    s._stderr_log = None
        self.state_store.save_to_disk()
        print("[Shutdown] Cleanup complete")

    def run(self) -> None:
        """Start the bot."""
        # 首先清理之前可能遗留的僵尸进程
        self._cleanup_previous_instances()

        print("Feishu OpenCode Bridge v7.0")
        print(f"  Config: {self.config.config_path}")

        if not self.config.app_id or not self.config.app_secret:
            print("Error: Feishu credentials not configured")
            print(f"  Edit: {self.config.config_path}")
            return

        print(f"  App ID: {self.config.app_id[:10]}...")
        if self.config.projects:
            slugs = [p.get("slug", "") for p in self.config.projects]
            print(f"  Projects: {', '.join(slugs)}")

        self.on_bot_startup()

        self.lark_client = (
            lark.Client.builder()
            .app_id(self.config.app_id)
            .app_secret(self.config.app_secret)
            .build()
        )

        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_message)
            .register_p2_card_action_trigger(self._handle_card_action)
            .build()
        )

        ws_client = lark.ws.Client(
            self.config.app_id,
            self.config.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        self._health_monitor.start()

        print("Connecting to Feishu (long connection)...")
        print("Send '帮助' in Feishu to see available commands.")
        print("(Ctrl+C to stop)\n")

        try:
            ws_client.start()
        except KeyboardInterrupt:
            print("\nStopped by user")
        except Exception as exc:
            print(f"\nFatal error: {exc}")
            import traceback

            traceback.print_exc()
        finally:
            self.on_bot_shutdown()


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def get_default_config_path() -> str:
    if sys.platform == "win32":
        return str(Path.home() / "AppData" / "Roaming" / "feishu-agent" / "config.yaml")
    return str(Path.home() / ".config" / "feishu-agent" / "config.yaml")


def load_config(config_path: str) -> AgentConfig:
    config = AgentConfig(config_path=config_path)
    p = Path(config_path)
    if not p.exists():
        return config
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        config.app_id = data.get("app_id", "")
        config.app_secret = data.get("app_secret", "")
        config.base_port = data.get("base_port", 4096)
        config.max_sessions = data.get("max_sessions", 10)
        config.callback_timeout = data.get("callback_timeout", 300)
        config.auto_restart = data.get("auto_restart", False)
        raw_projects = data.get("projects", [])
        config.projects = [
            {
                "slug": p.get("slug", ""),
                "path": p.get("path", ""),
                "label": p.get("label", ""),
            }
            for p in raw_projects
            if p.get("path")
        ]
        # LLM settings (optional, fallback to environment variables)
        config.llm_provider = data.get("llm_provider") or None
        config.llm_api_key = data.get("llm_api_key") or None
    except Exception as exc:
        print(f"Warning: Failed to load config: {exc}")
    return config


def create_default_config(config_path: str) -> None:
    p = Path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    content = """\
# Feishu OpenCode Bridge Configuration
# Usage: uv run bot/feishu_agent.py -c bot/opencode.bot.yaml

# Feishu App Credentials (Required)
# Get from: https://open.feishu.cn/app
app_id: ""
app_secret: ""

# Optional: Named project shortcuts
# Use slug in Feishu: '启动 sailzen'
projects:
  - slug: "sailzen"
    path: "~/repos/SailZen"
    label: "SailZen"

# Session settings
base_port: 4096     # Starting port for opencode web instances
max_sessions: 10
callback_timeout: 300
auto_restart: false

# Optional: LLM settings for intent understanding
# If not set, falls back to environment variables (MOONSHOT_API_KEY, etc.)
# Supported providers: moonshot, openai, google, deepseek, anthropic
# llm_provider: "moonshot"
# llm_api_key: "your-api-key-here"
"""
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created config: {config_path}")
    print("Please edit and add your Feishu credentials.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Feishu OpenCode Bridge - Connect Feishu messages to OpenCode sessions"
    )
    parser.add_argument(
        "--config", "-c", default=get_default_config_path(), help="Config file path"
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
