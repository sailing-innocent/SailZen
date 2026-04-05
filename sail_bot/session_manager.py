# -*- coding: utf-8 -*-
# @file session_manager.py
# @brief OpenCode 会话管理器
# @author sailing-innocent
# @date 2026-03-25
# @version 1.0
# ---------------------------------
"""Manages OpenCode serve processes and their API sessions.

Each workspace gets:
- A running `opencode serve --hostname 127.0.0.1 --port <N>` subprocess
- An OpenCode API session created via POST /session
- A client for communicating with that server

Sessions persist across Feishu messages within the same process lifetime.
State is saved to ~/.config/feishu-agent/sessions.json for restart recovery.
"""

import json
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .opencode_client import OpenCodeSessionClient
from .config import AgentConfig


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


class OpenCodeSessionManager:
    """Manages OpenCode web processes and their API sessions."""

    STATE_FILE = Path.home() / ".config" / "feishu-agent" / "sessions.json"

    def __init__(self, base_port: int = 4096, state_store: Optional[Any] = None):
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
        # Validate path
        try:
            path_obj = Path(path).expanduser().resolve()
            if not path_obj.exists():
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
            from session_state import SessionState

            self._state_store.get_or_create(path, chat_id)
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

        client = OpenCodeSessionClient(port=session.port)
        title = f"Feishu session - {Path(path).name}"
        opencode_session = client.create_session(title=title)
        if opencode_session:
            session.opencode_session_id = opencode_session.id
            self._save_state()
            return opencode_session.id
        return None

    def send_task_streaming(
        self,
        path: str,
        task_text: str,
        on_chunk=None,
    ):
        """Send a coding task and yield the complete response.

        This is a simple synchronous wrapper that yields the full response
        as a single chunk. OpenCode handles streaming internally.

        Args:
            path: Workspace path
            task_text: Task description
            on_chunk: Callback for progress (called once with full response)

        Yields:
            The complete response text
        """
        path = str(Path(path).expanduser().resolve())
        session = self._sessions.get(path)

        if not session or session.process_status != "running":
            yield f"No running session for {path}. Use '启动 {path}' first."
            return

        sess_id = self.get_or_create_opencode_session(path)
        if not sess_id:
            yield "Failed to create OpenCode session. The server may not be ready yet."
            return

        client = OpenCodeSessionClient(port=session.port)
        print(f"[OpenCode] Sending task to session {sess_id} on port {session.port}")
        print(f"[OpenCode] Task: {task_text[:100]}...")

        try:
            # Use synchronous API - it's reliable and handles long responses
            message = client.send_message(sess_id, task_text)

            if message and message.text_content:
                content = message.text_content
                print(f"[OpenCode] Response received: {len(content)} chars")

                # Call progress callback if provided
                if on_chunk:
                    on_chunk(content)

                # Yield the complete content
                yield content
            else:
                yield "(任务已完成，无文字输出)"

        except Exception as exc:
            print(f"[OpenCode] Error: {exc}")
            yield f"\n[Error: {exc}]"

    def send_task(self, path: str, task_text: str) -> str:
        """Send a coding task to the opencode session for `path`."""
        path = str(Path(path).expanduser().resolve())
        session = self._sessions.get(path)

        if not session or session.process_status != "running":
            return f"No running session for {path}. Use '启动 {path}' first."

        sess_id = self.get_or_create_opencode_session(path)
        if not sess_id:
            return "Failed to create OpenCode session. The server may not be ready yet."

        client = OpenCodeSessionClient(port=session.port)
        print(f"[OpenCode] Sending task to session {sess_id} on port {session.port}")
        msg = client.send_message(sess_id, task_text)
        return msg.text_content if msg else "(No response)"

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
            "serve",
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
            stdout_log.close()
            stderr_log.close()
            session.process_status = "error"
            session.last_error = (
                "opencode command not found. Is it installed and in PATH?"
            )
            self._sync_state(session.path, "error", last_error=session.last_error)
            return False, session, session.last_error
        except Exception as exc:
            stdout_log.close()
            stderr_log.close()
            session.process_status = "error"
            session.last_error = str(exc)
            self._sync_state(session.path, "error", last_error=session.last_error)
            return False, session, session.last_error

        client = OpenCodeSessionClient(port=session.port)
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
            from session_state import SessionState

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
        """Load session state from disk with validation.

        启动时清理无效状态，只保留健康的服务。
        """
        if not self.STATE_FILE.exists():
            return

        try:
            with open(self.STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            valid_sessions = []
            invalid_count = 0

            for item in data:
                path = item.get("path", "")
                if not path:
                    continue

                port = item.get("port", self.base_port)

                # 验证端口是否开放且健康
                if self._is_port_open(port):
                    # 端口开放，进一步验证是否是 opencode 服务
                    try:
                        client = OpenCodeSessionClient(port=port)
                        if client.is_healthy():
                            # 健康的服务，恢复状态
                            s = ManagedSession(
                                path=path,
                                port=port,
                                opencode_session_id=item.get("opencode_session_id"),
                                chat_id=item.get("chat_id"),
                            )
                            s.process_status = "running"
                            self._sessions[path] = s
                            valid_sessions.append(s)
                        else:
                            # 端口被占用但不是 opencode
                            invalid_count += 1
                            print(
                                f"[State] Port {port} is open but not healthy opencode, skipping: {path}"
                            )
                    except Exception as exc:
                        invalid_count += 1
                        print(
                            f"[State] Failed to verify port {port}: {exc}, skipping: {path}"
                        )
                else:
                    # 端口未开放，视为已停止
                    invalid_count += 1
                    print(f"[State] Port {port} is not open, skipping: {path}")

            if self._sessions:
                print(
                    f"[State] Loaded {len(self._sessions)} valid session(s) from disk"
                )
            if invalid_count > 0:
                print(f"[State] Skipped {invalid_count} invalid/stopped session(s)")

            # 保存清理后的状态
            self._save_state()

        except Exception as exc:
            print(f"[State] Failed to load: {exc}")
            # 出错时清空状态，重新开始
            self._sessions.clear()


# Path resolution utilities


def extract_path_from_text(text: str, projects: List[Dict[str, str]]) -> Optional[str]:
    """Extract path from text using patterns or project shortcuts."""
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


def resolve_path(raw: str, projects: List[Dict[str, str]]) -> Optional[str]:
    """Resolve a path string or project slug to actual path."""
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
