from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import os
import socket
import subprocess
import sys
import time


@dataclass
class ManagedSession:
    session_key: str
    workspace_slug: str
    local_path: str
    port: int
    pid: int | None = None
    status: str = "stopped"
    local_url: str | None = None
    last_error: str | None = None
    started_at: str | None = None


class LocalExecutionAgent:
    def __init__(self, base_port: int = 4096):
        self.base_port = base_port
        self.sessions: dict[str, ManagedSession] = {}
        self.allowed_commands = {
            "opencode_start",
            "opencode_stop",
            "opencode_restart",
            "workspace_status",
        }

    def inventory_from_projects(self, projects) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for project in projects:
            resolved = str(Path(project.path).expanduser().resolve())
            items.append(
                {
                    "slug": project.slug,
                    "name": project.label or project.slug,
                    "local_path": resolved,
                    "inventory_source": "edge-config",
                    "labels": {"label": project.label or project.slug},
                    "is_enabled": Path(resolved).exists(),
                }
            )
        return items

    def ensure_session(self, workspace_slug: str, local_path: str) -> ManagedSession:
        session_key = f"sess_{workspace_slug}"
        existing = self.sessions.get(session_key)
        if existing:
            return existing
        port = self._next_port()
        session = ManagedSession(
            session_key=session_key,
            workspace_slug=workspace_slug,
            local_path=str(Path(local_path).expanduser().resolve()),
            port=port,
            local_url=f"http://127.0.0.1:{port}",
        )
        self.sessions[session_key] = session
        return session

    def start_session(self, session_key: str) -> tuple[bool, ManagedSession]:
        session = self.sessions[session_key]
        if self.is_running(session):
            session.status = "running"
            return True, session

        cmd = [
            "opencode",
            "web",
            "--hostname",
            "127.0.0.1",
            "--port",
            str(session.port),
        ]
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE

        try:
            process = subprocess.Popen(
                cmd,
                cwd=session.local_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **kwargs,
            )
            session.pid = process.pid
            session.status = "starting"
            session.started_at = datetime.now(timezone.utc).isoformat()
            time.sleep(3)
            if self.is_running(session):
                session.status = "running"
                return True, session
            session.status = "error"
            session.last_error = "OpenCode failed to bind to port"
            return False, session
        except Exception as exc:
            session.status = "error"
            session.last_error = str(exc)
            return False, session

    def stop_session(self, session_key: str) -> tuple[bool, ManagedSession]:
        session = self.sessions[session_key]
        if not self.is_running(session):
            session.status = "stopped"
            session.pid = None
            return True, session

        try:
            if session.pid:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/PID", str(session.pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
                    )
                else:
                    os.kill(session.pid, 15)
            session.pid = None
            session.status = "stopped"
            return True, session
        except Exception as exc:
            session.status = "error"
            session.last_error = str(exc)
            return False, session

    def restart_session(self, session_key: str) -> tuple[bool, ManagedSession]:
        self.stop_session(session_key)
        return self.start_session(session_key)

    def collect_diagnostics(self, session_key: str) -> dict[str, Any]:
        session = self.sessions[session_key]
        diagnostics = {
            "local_path_exists": Path(session.local_path).exists(),
            "port": session.port,
            "port_open": self._is_port_open(session.port),
            "pid": session.pid,
            "status": session.status,
            "last_error": session.last_error,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        if Path(session.local_path).exists():
            diagnostics["workspace_entries"] = sorted(
                [entry.name for entry in Path(session.local_path).iterdir()][:20]
            )
        else:
            diagnostics["workspace_entries"] = []
        return diagnostics

    def observed_state_payload(self, session_key: str) -> dict[str, Any]:
        session = self.sessions[session_key]
        diagnostics = self.collect_diagnostics(session_key)
        observed_state = "running" if self.is_running(session) else "stopped"
        if session.status == "error":
            observed_state = "crashed"
        return {
            "session_key": session.session_key,
            "workspace_slug": session.workspace_slug,
            "desired_state": "running"
            if session.status in {"starting", "running"}
            else "stopped",
            "observed_state": observed_state,
            "health_status": "healthy" if observed_state == "running" else "idle",
            "local_url": session.local_url,
            "local_path": session.local_path,
            "last_error": session.last_error,
            "process_info": {"pid": session.pid, "port": session.port},
            "diagnostics": diagnostics,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "branch_name": None,
        }

    def safe_execute(
        self, command_name: str, session_key: str
    ) -> tuple[bool, dict[str, Any]]:
        if command_name not in self.allowed_commands:
            return False, {"error": f"Command not allowed: {command_name}"}
        if command_name == "workspace_status":
            return True, self.collect_diagnostics(session_key)
        if command_name == "opencode_start":
            ok, session = self.start_session(session_key)
            return ok, self.observed_state_payload(session.session_key)
        if command_name == "opencode_stop":
            ok, session = self.stop_session(session_key)
            return ok, self.observed_state_payload(session.session_key)
        ok, session = self.restart_session(session_key)
        return ok, self.observed_state_payload(session.session_key)

    def is_running(self, session: ManagedSession) -> bool:
        return self._is_port_open(session.port)

    def _next_port(self) -> int:
        port = self.base_port
        used_ports = {session.port for session in self.sessions.values()}
        while port in used_ports:
            port += 1
        return port

    def _is_port_open(self, port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(("127.0.0.1", port))
            return result == 0
        finally:
            sock.close()
