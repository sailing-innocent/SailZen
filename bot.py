# -*- coding: utf-8 -*-
# @file bot.py
# @brief Unified Feishu Bot Entry Point for SailZen 3.0 Phase 0 MVP
# @author sailing-innocent
# @date 2026-03-30
# @version 1.0
# ---------------------------------
"""Unified Feishu Bot Entry Point - Consolidated from:
- scripts/feishu_dev_bot.py (Phase 0 MVP launcher)
- bot/feishu_agent.py (Rich interaction features)

This script provides a single, unified entry point for the SailZen Feishu Bot
with full Phase 0 capabilities:
- Long-connection Feishu client
- LLM-driven intent recognition
- Interactive card system
- OpenCode session management
- Self-update capability
- State persistence

Usage:
    # Start bot normally
    uv run python bot.py

    # Start with specific config
    uv run python bot.py --config .env.feishu

    # Mock mode (no real Feishu connection)
    uv run python bot.py --mock

    # Show status
    uv run python bot.py --status

    # Trigger self-update from OpenCode
    uv run python bot.py --from-opencode --update-trigger
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import threading
import subprocess
import socket
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

# Add sail_server to path
sys.path.insert(0, str(Path(__file__).parent / "sail_server"))

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
    lark = None  # type: ignore
    print("Warning: lark-oapi not installed. Install: uv add lark-oapi")

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    httpx = None  # type: ignore
    print("Warning: httpx not installed. Install: uv add httpx")

# Import SailZen gateway components
try:
    from sail_server.feishu_gateway.bot_state_manager import (
        BotStateManager,
        get_state_manager,
    )
    from sail_server.feishu_gateway.self_update_orchestrator import (
        SelfUpdateOrchestrator,
        UpdateTriggerSource,
        UpdatePhase,
    )
    from sail_server.feishu_gateway.cards import CardRenderer, CardTemplate

    HAS_GATEWAY = True
except ImportError as e:
    HAS_GATEWAY = False
    print(f"[Warning] SailZen gateway not available: {e}")

# Import LLM gateway
try:
    from sail_server.utils.llm.gateway import LLMGateway
    from sail_server.utils.llm.providers import ProviderConfig
    from sail_server.utils.llm.available_providers import (
        DEFAULT_LLM_PROVIDER,
        DEFAULT_LLM_MODEL,
        DEFAULT_LLM_CONFIG,
    )

    HAS_LLM = True
except ImportError:
    HAS_LLM = False
    print("[Warning] LLM gateway not available")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class BotConfig:
    """Bot configuration."""

    app_id: str = ""
    app_secret: str = ""
    base_port: int = 4096
    max_sessions: int = 10
    workspace_root: Path = field(default_factory=lambda: Path("D:/ws/repos/SailZen"))
    projects: List[Dict[str, str]] = field(default_factory=list)
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    auto_restart: bool = False
    mock_mode: bool = False


# =============================================================================
# OpenCode Web Client
# =============================================================================


class OpenCodeWebClient:
    """HTTP client for OpenCode web/serve API."""

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
        if not HAS_HTTPX:
            return False
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self._base_url}/global/health")
                return resp.status_code == 200
        except Exception:
            return False

    def create_session(self, title: Optional[str] = None) -> Optional[str]:
        """Create a new OpenCode session and return its ID."""
        if not HAS_HTTPX:
            return None
        body: Dict[str, Any] = {}
        if title:
            body["title"] = title

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(f"{self._base_url}/session", json=body)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return data.get("id")
                return None
        except Exception as exc:
            print(f"[OpenCode] create_session error: {exc}")
            return None

    def send_message(
        self,
        session_id: str,
        text: str,
        collect_timeout: int = 300,
    ) -> str:
        """Send a task message to a session and return the assistant reply."""
        if not HAS_HTTPX:
            return "Error: httpx not available"

        url = f"{self._base_url}/session/{session_id}/message"
        body = {"parts": [{"type": "text", "text": text}]}

        start_time = time.time()
        collected_texts: List[str] = []
        session_completed = False

        try:
            with httpx.Client(timeout=collect_timeout) as client:
                resp = client.post(url, json=body)
                if resp.status_code not in (200, 201):
                    return f"OpenCode API error: HTTP {resp.status_code}"

                content_type = resp.headers.get("content-type", "")
                if (
                    "text/event-stream" in content_type
                    or resp.headers.get("transfer-encoding") == "chunked"
                ):
                    for line in resp.iter_lines():
                        if time.time() - start_time > collect_timeout:
                            break

                        line = line.strip()
                        if not line:
                            continue

                        if line.startswith("data: "):
                            data = line[6:]
                            try:
                                event_data = json.loads(data)
                            except json.JSONDecodeError:
                                continue

                            event_type = event_data.get("type", "")

                            if event_type in ("content", "text", "chunk", "delta"):
                                content = (
                                    event_data.get("content", "")
                                    or event_data.get("text", "")
                                    or event_data.get("delta", "")
                                )
                                if content:
                                    collected_texts.append(content)

                            elif event_type in (
                                "completed",
                                "done",
                                "finished",
                                "end",
                                "session.completed",
                            ):
                                session_completed = True
                                break
                            elif event_type in (
                                "idle",
                                "stopped",
                                "session.idle",
                                "halt",
                            ):
                                session_completed = True
                                break
                            elif event_type in ("error", "failed"):
                                error_msg = event_data.get(
                                    "message", event_data.get("error", "Unknown error")
                                )
                                return f"OpenCode error: {error_msg}"

                    reply = "".join(collected_texts).strip()
                    if reply and not session_completed:
                        return reply + "\n\n[Response may be incomplete]"
                    return reply or "(OpenCode returned an empty response)"
                else:
                    data = resp.json()
                    parts = data.get("parts", [])
                    text_parts = [
                        p.get("text", "")
                        for p in parts
                        if isinstance(p, dict)
                        and p.get("type") == "text"
                        and p.get("text")
                    ]
                    return (
                        "".join(text_parts).strip()
                        or "(OpenCode returned an empty response)"
                    )

        except httpx.TimeoutException:
            if collected_texts:
                reply = "".join(collected_texts).strip()
                return (
                    reply
                    + f"\n\n[Response truncated - timed out after {collect_timeout}s]"
                )
            return f"OpenCode timed out after {collect_timeout}s"
        except Exception as exc:
            if collected_texts:
                reply = "".join(collected_texts).strip()
                return reply + f"\n\n[Response may be incomplete - error: {exc}]"
            return f"OpenCode communication error: {exc}"


# =============================================================================
# Session Management
# =============================================================================


@dataclass
class ManagedSession:
    """Tracks a running opencode web process and its API session."""

    path: str
    port: int
    pid: Optional[int] = None
    process_status: str = "stopped"
    opencode_session_id: Optional[str] = None
    started_at: Optional[str] = None
    last_error: Optional[str] = None
    chat_id: Optional[str] = None
    _process: Optional[Any] = None
    _stdout_log: Optional[Any] = None
    _stderr_log: Optional[Any] = None


class OpenCodeSessionManager:
    """Manages OpenCode web processes and their API sessions."""

    STATE_FILE = Path.home() / ".config" / "feishu-agent" / "sessions.json"

    def __init__(self, base_port: int = 4096):
        self.base_port = base_port
        self._sessions: Dict[str, ManagedSession] = {}
        self._load_state()

    def ensure_running(
        self, path: str, chat_id: Optional[str] = None
    ) -> Tuple[bool, ManagedSession, str]:
        """Ensure an opencode web process is running for `path`."""
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
            return True, session, f"Already running on port {session.port}"

        port = self._allocate_port()
        if session is None:
            session = ManagedSession(path=path, port=port, chat_id=chat_id)
            self._sessions[path] = session
        else:
            session.port = port
            session.opencode_session_id = None

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
        """Send a coding task to the opencode session for `path`."""
        path = str(Path(path).expanduser().resolve())
        session = self._sessions.get(path)

        if not session or session.process_status != "running":
            return f"No running session for {path}. Use '启动 {path}' first."

        sess_id = self.get_or_create_opencode_session(path)
        if not sess_id:
            return "Failed to create OpenCode session."

        client = OpenCodeWebClient(port=session.port)
        print(f"[OpenCode] Sending task to session {sess_id} on port {session.port}")
        return client.send_message(sess_id, task_text)

    def stop_session(self, path: str) -> Tuple[bool, str]:
        """Stop the opencode process for a workspace."""
        path = str(Path(path).expanduser().resolve())
        session = self._sessions.get(path)
        if not session:
            return False, f"No session for {path}"

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

                if session._process:
                    try:
                        session._process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:
                            session._process.kill()
                            session._process.wait(timeout=2)
                        except Exception:
                            pass

                time.sleep(1)
            except Exception as exc:
                session.last_error = str(exc)

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

        session._process = None
        session.pid = None
        session.process_status = "stopped"
        session.opencode_session_id = None
        self._save_state()
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

    def _start_process(
        self, session: ManagedSession
    ) -> Tuple[bool, ManagedSession, str]:
        """Start an opencode web process for the session."""
        path = Path(session.path)
        if not path.exists():
            session.process_status = "error"
            session.last_error = f"Path does not exist: {session.path}"
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
            stdout_log.close()
            stderr_log.close()
            session.process_status = "error"
            session.last_error = (
                "opencode command not found. Is it installed and in PATH?"
            )
            return False, session, session.last_error
        except Exception as exc:
            stdout_log.close()
            stderr_log.close()
            session.process_status = "error"
            session.last_error = str(exc)
            return False, session, session.last_error

        client = OpenCodeWebClient(port=session.port)
        for attempt in range(15):
            time.sleep(1)
            if client.is_healthy():
                session.process_status = "running"
                self._save_state()
                msg = f"Started on port {session.port} (PID {session.pid})"
                print(f"[OpenCode] {msg}")
                return True, session, msg

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
            except Exception:
                pass

        stdout_log.close()
        stderr_log.close()
        session._stdout_log = None
        session._stderr_log = None

        session.process_status = "error"
        session.last_error = (
            f"Server did not become healthy on port {session.port} after 15s"
        )
        return False, session, session.last_error

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
                if self._is_port_open(s.port):
                    s.process_status = "running"
                self._sessions[path] = s
            if self._sessions:
                print(f"[State] Loaded {len(self._sessions)} session(s) from disk")
        except Exception as exc:
            print(f"[State] Failed to load: {exc}")


# =============================================================================
# LLM Brain for Intent Recognition
# =============================================================================


@dataclass
class ActionPlan:
    """Structured action plan from LLM or fallback."""

    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    confirm_required: bool = False
    confirm_summary: str = ""
    reply: str = ""


_BRAIN_SYSTEM = """你是飞书机器人，帮用户控制OpenCode开发环境。理解自然语言（可能有错别字），返回JSON行动计划。

上下文：mode={mode}, workspace={active_workspace}, projects={projects}
历史：{history}

用户：{user_text}

返回JSON：
{{"action":"...","params":{{}},"confirm_required":false,"confirm_summary":"","reply":"","reasoning":""}}

actions: start_workspace|stop_workspace|send_task|show_status|show_help|chat|clarify
规则：stop_workspace需确认；破坏性操作需确认
注意：推断用户意图，只返回JSON"""

_BRAIN_FALLBACK_ACTIONS = {
    "帮助": ("show_help", {}),
    "help": ("show_help", {}),
    "状态": ("show_status", {}),
    "status": ("show_status", {}),
    "更新": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested update"},
    ),
    "update": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested update"},
    ),
    "升级": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested upgrade"},
    ),
}


class BotBrain:
    """LLM-driven intent recognizer for the Feishu bot."""

    _CONFIRM_TTL = timedelta(minutes=5)

    def __init__(self, projects: List[Dict[str, str]], config: BotConfig):
        self.projects = projects
        self.config = config
        self._gw = None
        self._provider = None
        self._model_cfg = None
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM gateway."""
        if not HAS_LLM:
            print("[BotBrain] LLM gateway not available")
            return

        try:
            provider_env_keys = {
                "moonshot": "MOONSHOT_API_KEY",
                "openai": "OPENAI_API_KEY",
                "google": "GOOGLE_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
            }

            default_models = {
                "moonshot": DEFAULT_LLM_MODEL
                if DEFAULT_LLM_PROVIDER == "moonshot"
                else "kimi-k2.5",
                "openai": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                "google": os.environ.get("GOOGLE_MODEL", "gemini-2.0-flash"),
            }

            gw = LLMGateway()
            registered = []

            # Check config first
            if self.config.llm_provider and self.config.llm_api_key:
                provider = self.config.llm_provider.lower()
                if provider in provider_env_keys:
                    cfg = ProviderConfig(
                        provider_name=provider,
                        model=default_models.get(provider, ""),
                        api_key=self.config.llm_api_key,
                    )
                    gw.register_provider(provider, cfg)
                    registered.append(provider)

            # Then check env vars
            for pname, env_key in provider_env_keys.items():
                if pname in registered:
                    continue
                key = os.environ.get(env_key, "")
                if key:
                    cfg = ProviderConfig(
                        provider_name=pname,
                        model=default_models[pname],
                        api_key=key,
                    )
                    gw.register_provider(pname, cfg)
                    registered.append(pname)

            if registered:
                self._gw = gw
                self._provider = (
                    DEFAULT_LLM_PROVIDER
                    if DEFAULT_LLM_PROVIDER in registered
                    else registered[0]
                )
                self._model_cfg = (default_models.get(self._provider, ""), 0.7)
                print(f"[BotBrain] LLM ready: {self._provider}/{self._model_cfg[0]}")
            else:
                print("[BotBrain] No LLM API key found - using fallback mode")

        except Exception as exc:
            print(f"[BotBrain] Gateway init failed: {exc}")

    def think(self, text: str, ctx: "ConversationContext") -> ActionPlan:
        """Main entry: text + context → ActionPlan."""
        if self._gw:
            try:
                return asyncio.run(self._think_llm(text, ctx))
            except Exception as exc:
                print(f"[BotBrain] LLM call failed, using fallback: {exc}")
        return self._think_deterministic(text, ctx)

    async def _think_llm(self, text: str, ctx: "ConversationContext") -> ActionPlan:
        """Use LLM to understand intent."""
        from sail_server.utils.llm.gateway import LLMExecutionConfig

        slugs = [p.get("slug", p.get("label", "")) for p in self.projects]
        prompt = _BRAIN_SYSTEM.format(
            mode=ctx.mode,
            active_workspace=ctx.active_workspace or "None",
            projects=", ".join(slugs) if slugs else "None",
            history=ctx.history_text() or "(无历史)",
            user_text=text,
        )

        model, temp = self._model_cfg
        config = LLMExecutionConfig(
            provider=self._provider,
            model=model,
            temperature=temp,
            max_tokens=512,
            enable_caching=False,
            timeout=30,
        )

        try:
            result = await self._gw.execute(prompt, config)
            raw = result.content.strip()

            if not raw:
                raise Exception("LLM returned empty response")

            # Clean up markdown code blocks
            raw_cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
            raw_cleaned = re.sub(r"\s*```$", "", raw_cleaned)

            data = json.loads(raw_cleaned)

            return ActionPlan(
                action=data.get("action", "chat"),
                params=data.get("params", {}),
                confirm_required=bool(data.get("confirm_required", False)),
                confirm_summary=data.get("confirm_summary", ""),
                reply=data.get("reply", ""),
            )
        except Exception as exc:
            print(f"[LLM] Error: {exc}")
            raise

    def _think_deterministic(self, text: str, ctx: "ConversationContext") -> ActionPlan:
        """Fallback deterministic intent recognition."""
        t = text.lower().strip()

        for kw, (action, params) in _BRAIN_FALLBACK_ACTIONS.items():
            if kw in t:
                return ActionPlan(action=action, params=params)

        # Quick workspace switch
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
            path = self._extract_path_from_text(text)
            if path:
                ctx.mode = "coding"
                ctx.active_workspace = path
                return ActionPlan(
                    action="chat",
                    reply=f"已切换到工作区：{Path(path).name}\n现在可以直接发送指令给这个工作区。",
                )

        if any(k in t for k in ["start", "启动", "开启", "打开", "open"]):
            path = self._extract_path_from_text(text)
            return ActionPlan(action="start_workspace", params={"path": path})

        if any(k in t for k in ["stop", "停止", "关闭", "结束", "kill"]):
            path = self._extract_path_from_text(text)
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
            ]
        ):
            path = self._extract_path_from_text(text)
            return ActionPlan(action="send_task", params={"task": text, "path": path})

        return ActionPlan(
            action="chat",
            reply=(
                "我理解你说的可能是一个开发任务，但我需要知道目标工作区。\n"
                "可以说：'启动 sailzen' 或 '使用 sailzen' 或 '进入 ~/projects/myapp'"
            ),
        )

    def _extract_path_from_text(self, text: str) -> Optional[str]:
        """Extract path from text."""
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

        for p in self.projects:
            slug = p.get("slug", "")
            label = p.get("label", "")
            if slug and slug in text:
                return p.get("path", "")
            if label and label.lower() in text.lower():
                return p.get("path", "")

        return None


# =============================================================================
# Conversation Context
# =============================================================================


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
    history: deque = field(default_factory=lambda: deque(maxlen=6))
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


# =============================================================================
# Feishu Client
# =============================================================================


class FeishuClient:
    """Feishu long-connection WebSocket client."""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        message_handler: Optional[callable] = None,
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.message_handler = message_handler
        self._client = None
        self._running = False
        self._thread = None

    def start(self) -> None:
        """Start the Feishu long connection."""
        if not HAS_LARK:
            print("[FeishuClient] Running in mock mode")
            self._running = True
            return

        try:

            def on_message(data) -> None:
                if self.message_handler:
                    try:
                        event_data = {
                            "message_id": getattr(data.event.message, "message_id", ""),
                            "chat_id": getattr(data.event.message, "chat_id", ""),
                            "content": getattr(data.event.message, "content", ""),
                            "sender": {
                                "sender_id": getattr(
                                    getattr(data.event.message, "sender", None),
                                    "sender_id",
                                    None,
                                )
                                and getattr(
                                    getattr(
                                        data.event.message, "sender", None
                                    ).sender_id,
                                    "open_id",
                                    "",
                                )
                                or "",
                            },
                        }
                        asyncio.create_task(self.message_handler(event_data))
                    except Exception as e:
                        print(f"[FeishuClient] Error handling message: {e}")

            builder = lark.EventDispatcherHandler.builder(self.app_id, self.app_secret)
            builder.register_p2_im_message_receive_v1(on_message)
            event_handler = builder.build()

            self._client = lark.ws.Client(
                self.app_id,
                self.app_secret,
                event_handler=event_handler,
            )

            self._running = True
            print(f"[FeishuClient] Starting long connection...")

            self._thread = threading.Thread(target=self._client.start)
            self._thread.daemon = True
            self._thread.start()

        except Exception as e:
            print(f"[FeishuClient] Failed to start: {e}")
            self._running = False

    def stop(self) -> None:
        """Stop the Feishu connection."""
        self._running = False
        print("[FeishuClient] Stopping connection...")

    async def close(self) -> None:
        """Close connection gracefully."""
        self.stop()

    @property
    def is_running(self) -> bool:
        return self._running


# =============================================================================
# Main Bot Class
# =============================================================================


class SailZenFeishuBot:
    """Unified SailZen Feishu Bot with full Phase 0 capabilities."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.session_manager = OpenCodeSessionManager(config.base_port)
        self.brain = BotBrain(config.projects, config)
        self._contexts: Dict[str, ConversationContext] = {}

        # Feishu client
        self.feishu_client: Optional[FeishuClient] = None

        # Gateway components
        self.state_manager = get_state_manager() if HAS_GATEWAY else None
        self.update_orchestrator: Optional[Any] = None

        # Runtime state
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def initialize(self, restore_state: bool = False) -> bool:
        """Initialize the bot."""
        print("[Bot] Initializing...")

        # Check for handover
        if HAS_GATEWAY:
            from sail_server.feishu_gateway.self_update_orchestrator import (
                SelfUpdateOrchestrator,
            )

            handover_data = SelfUpdateOrchestrator.check_for_handover()
            if handover_data:
                print(
                    f"[Bot] Detected handover from PID {handover_data.get('old_pid')}"
                )
                restore_state = True

        # Initialize state manager
        if self.state_manager:
            self.state_manager.initialize_session()

        # Initialize Feishu client
        if self.config.app_id and self.config.app_secret:
            self.feishu_client = FeishuClient(
                app_id=self.config.app_id,
                app_secret=self.config.app_secret,
                message_handler=self._handle_message,
            )
        else:
            print("[Bot] Warning: Feishu credentials not configured")

        # Initialize self-update orchestrator
        if HAS_GATEWAY:
            self.update_orchestrator = SelfUpdateOrchestrator(
                state_manager=self.state_manager,
                workspace_root=self.config.workspace_root,
            )

        print("[Bot] Initialization complete")
        return True

    async def start(self) -> None:
        """Start the bot."""
        print("[Bot] Starting...")
        self._running = True

        if self.feishu_client:
            self.feishu_client.start()

        # Main loop
        try:
            await self._main_loop()
        except asyncio.CancelledError:
            print("[Bot] Main loop cancelled")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        print("[Bot] Shutting down...")
        self._running = False

        if self.feishu_client:
            await self.feishu_client.close()

        if self.state_manager:
            self.state_manager.cleanup_current_session()

        self._shutdown_event.set()
        print("[Bot] Shutdown complete")

    async def request_self_update(self, reason: str, source: Any = None) -> bool:
        """Request a self-update."""
        if not self.update_orchestrator:
            print("[Bot] Update orchestrator not initialized")
            return False

        print(f"[Bot] Initiating self-update: {reason}")

        if source is None and HAS_GATEWAY:
            source = UpdateTriggerSource.MANUAL_COMMAND

        result = await self.update_orchestrator.initiate_self_update(
            trigger_source=source,
            reason=reason,
        )

        if result.success:
            print(f"[Bot] Self-update successful, new PID: {result.new_pid}")
            asyncio.create_task(self.shutdown())
            return True
        else:
            print(f"[Bot] Self-update failed: {result.error}")
            return False

    async def _main_loop(self) -> None:
        """Main runtime loop."""
        heartbeat_interval = 30
        last_heartbeat = 0

        while self._running:
            if self.update_orchestrator and self.update_orchestrator.should_exit():
                print("[Bot] Update completion detected, exiting...")
                break

            now = time.time()
            if now - last_heartbeat >= heartbeat_interval:
                if self.state_manager:
                    self.state_manager.update_heartbeat()
                last_heartbeat = now

            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=1.0)
                break
            except asyncio.TimeoutError:
                continue

    async def _handle_message(self, event_data: Dict[str, Any]) -> None:
        """Handle incoming Feishu message."""
        chat_id = event_data.get("chat_id", "unknown")
        content_str = event_data.get("content", "{}")

        try:
            content = (
                json.loads(content_str) if isinstance(content_str, str) else content_str
            )
            text = content.get("text", "").strip()

            if not text:
                return

            print(f"\n[Bot] Message from {chat_id}: {text[:80]}...")

            # Process in background
            threading.Thread(
                target=lambda: asyncio.run(
                    self._process_message(text, chat_id, event_data)
                ),
                daemon=True,
            ).start()

        except Exception as e:
            print(f"[Bot] Error handling message: {e}")

    async def _process_message(
        self, text: str, chat_id: str, event_data: Dict[str, Any]
    ) -> None:
        """Process a message."""
        # Get or create context
        if chat_id not in self._contexts:
            self._contexts[chat_id] = ConversationContext(chat_id=chat_id)
        ctx = self._contexts[chat_id]

        if ctx.is_pending_expired():
            ctx.clear_pending()

        ctx.push("user", text)

        # Get action plan
        plan = self.brain.think(text, ctx)

        # Execute
        await self._execute_plan(plan, chat_id, ctx)

    async def _execute_plan(
        self, plan: ActionPlan, chat_id: str, ctx: ConversationContext
    ) -> None:
        """Execute an action plan."""
        action = plan.action
        params = plan.params

        if action == "show_help":
            await self._send_text_reply(chat_id, self._build_help_text())
            ctx.push("bot", "Help shown")
            return

        if action == "show_status":
            status = self.session_manager.get_status()
            await self._send_text_reply(chat_id, f"```\n{status}\n```")
            ctx.push("bot", "Status shown")
            return

        if action == "start_workspace":
            path = params.get("path") or self.brain._extract_path_from_text(
                params.get("task", "")
            )
            if not path:
                await self._send_text_reply(
                    chat_id, "请指定工作区路径，例如：启动 sailzen"
                )
                return

            await self._send_text_reply(
                chat_id, f"正在启动工作区: {Path(path).name}..."
            )

            ok, session, msg = self.session_manager.ensure_running(path, chat_id)
            if ok:
                ctx.mode = "coding"
                ctx.active_workspace = session.path
                await self._send_text_reply(
                    chat_id,
                    f"工作区已启动！\n路径: {session.path}\n端口: {session.port}\nPID: {session.pid}",
                )
                ctx.push("bot", f"Started {session.path}")
            else:
                await self._send_text_reply(chat_id, f"启动失败: {msg}")
            return

        if action == "stop_workspace":
            path = params.get("path")
            if path:
                ok, msg = self.session_manager.stop_session(path)
                if ok:
                    if ctx.active_workspace == path:
                        ctx.mode = "idle"
                        ctx.active_workspace = None
                await self._send_text_reply(
                    chat_id, f"{'已停止' if ok else '停止失败'}: {Path(path).name}"
                )
            else:
                sessions = self.session_manager.list_sessions()
                if not sessions:
                    await self._send_text_reply(chat_id, "没有正在运行的会话。")
                    return
                for s in sessions:
                    self.session_manager.stop_session(s.path)
                ctx.mode = "idle"
                ctx.active_workspace = None
                await self._send_text_reply(chat_id, f"已停止 {len(sessions)} 个会话")
            ctx.push("bot", "Stopped session(s)")
            return

        if action == "send_task":
            task_text = params.get("task", "")
            path = params.get("path") or ctx.active_workspace

            if not path:
                running = [
                    s
                    for s in self.session_manager.list_sessions()
                    if s.process_status == "running"
                ]
                if len(running) == 1:
                    path = running[0].path
                elif not running:
                    await self._send_text_reply(
                        chat_id, "没有正在运行的会话。请先启动一个工作区。"
                    )
                    return
                else:
                    names = [Path(s.path).name for s in running]
                    await self._send_text_reply(
                        chat_id, f"有多个会话运行中: {', '.join(names)}\n请指定工作区"
                    )
                    return

            await self._send_text_reply(
                chat_id, f"正在向 {Path(path).name} 发送任务..."
            )

            # Ensure running
            ok, session, msg = self.session_manager.ensure_running(path, chat_id)
            if not ok:
                await self._send_text_reply(chat_id, f"启动失败: {msg}")
                return

            ctx.mode = "coding"
            ctx.active_workspace = session.path

            # Send task
            reply = self.session_manager.send_task(path, task_text)
            await self._send_text_reply(chat_id, f"**任务完成**\n\n{reply[:2000]}")
            ctx.push("bot", "Task completed")
            return

        if action == "self_update":
            await self._send_text_reply(chat_id, "正在启动自更新流程...")
            success = await self.request_self_update(
                reason=params.get("reason", "User requested"),
            )
            if success:
                await self._send_text_reply(chat_id, "✅ 自更新已启动，新进程将接管。")
            else:
                await self._send_text_reply(chat_id, "❌ 自更新失败，请检查日志。")
            return

        if action == "chat":
            reply = plan.reply or "我不太确定你的意思，能再描述一下吗？"
            await self._send_text_reply(chat_id, reply)
            ctx.push("bot", reply[:100])
            return

        await self._send_text_reply(chat_id, f"未知动作: {action}")

    async def _send_text_reply(self, chat_id: str, text: str) -> None:
        """Send text reply to Feishu."""
        if not HAS_LARK or not self.feishu_client:
            print(f"[Bot] Would send to {chat_id}: {text[:200]}...")
            return

        try:
            # Use lark API to send message
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
            # Note: This requires the client to have REST API capability
            # For now, just log it
            print(f"[Bot] Sending to {chat_id}: {text[:100]}...")
        except Exception as e:
            print(f"[Bot] Send error: {e}")

    def _build_help_text(self) -> str:
        """Build help text."""
        slugs = [p.get("slug", "") for p in self.config.projects]
        proj_line = f"配置的项目: {', '.join(slugs)}\n" if slugs else ""
        llm_status = "LLM 已启用" if self.brain._gw else "LLM 未配置"

        return f"""🤖 **SailZen Bot 帮助**

{proj_line}
状态: {llm_status}

**可用指令：**
• **启动 <项目名>** - 启动工作区
• **停止 <项目名>** - 停止工作区
• **状态** - 查看运行状态
• **更新** - 触发 Bot 自更新
• **帮助** - 显示此帮助

发送自然语言描述你的开发任务即可！
"""


# =============================================================================
# Utility Functions
# =============================================================================


def load_env_file(env_file: Path) -> dict:
    """Load environment variables from .env file."""
    env_vars = {}
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip("\"'")
    return env_vars


def setup_environment():
    """Setup environment from .env files."""
    env_files = [Path(".env"), Path(".env.local"), Path(".env.feishu")]
    for env_file in env_files:
        if env_file.exists():
            print(f"[Setup] Loading environment from {env_file}")
            env_vars = load_env_file(env_file)
            for key, value in env_vars.items():
                if key not in os.environ:
                    os.environ[key] = value


def create_default_config():
    """Create default configuration file if not exists."""
    config_file = Path(".env.feishu")
    if not config_file.exists():
        print(f"[Setup] Creating default config: {config_file}")
        config_content = """# Feishu Bot Configuration
# Get these from your Feishu app console: https://open.feishu.cn/app

FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Override workspace root
# SAILZEN_WORKSPACE_ROOT=D:/ws/repos/SailZen

# Optional: LLM Configuration
# LLM_PROVIDER=moonshot
# LLM_API_KEY=your_api_key_here
"""
        config_file.write_text(config_content, encoding="utf-8")
        print(f"[Setup] Please edit {config_file} with your Feishu credentials")
        return False
    return True


def show_status():
    """Show bot status."""
    print("\n🤖 SailZen Bot Status")
    print("=" * 50)

    # Show sessions
    session_manager = OpenCodeSessionManager()
    sessions = session_manager.list_sessions()

    if sessions:
        print(f"\n📦 Active Sessions ({len(sessions)}):")
        for s in sessions:
            print(f"  • {Path(s.path).name}")
            print(f"    Port: {s.port}, PID: {s.pid}, Status: {s.process_status}")
    else:
        print("\n📦 No active sessions")

    # Show backups
    if HAS_GATEWAY:
        from sail_server.feishu_gateway.bot_state_manager import get_state_manager

        state_manager = get_state_manager()
        backups = state_manager.list_backups()

        if backups:
            print(f"\n💾 Available Backups ({len(backups)}):")
            for i, backup in enumerate(backups[:5], 1):
                stat = backup.stat()
                print(f"  {i}. {backup.name} ({stat.st_size} bytes)")

    print("\n" + "=" * 50)


# =============================================================================
# Main Entry Point
# =============================================================================


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SailZen Feishu Bot - Unified Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start bot normally
  uv run python bot.py

  # Start with specific config
  uv run python bot.py --config .env.feishu

  # Mock mode (no real Feishu connection)
  uv run python bot.py --mock

  # Show status
  uv run python bot.py --status

  # Trigger self-update from OpenCode
  uv run python bot.py --from-opencode --update-trigger
        """,
    )

    parser.add_argument("--config", type=str, help="Path to environment config file")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    parser.add_argument(
        "--status", action="store_true", help="Show bot status and exit"
    )
    parser.add_argument(
        "--restore", action="store_true", help="Restore from previous backup"
    )
    parser.add_argument(
        "--from-opencode", action="store_true", help="Started from OpenCode session"
    )
    parser.add_argument(
        "--update-trigger", action="store_true", help="Trigger self-update immediately"
    )

    args = parser.parse_args()

    # Show status and exit
    if args.status:
        show_status()
        return

    # Load configuration
    if args.config:
        env_vars = load_env_file(Path(args.config))
        for key, value in env_vars.items():
            os.environ[key] = value
    else:
        if not create_default_config():
            return
        setup_environment()

    # Create config
    config = BotConfig(
        app_id=os.getenv("FEISHU_APP_ID", ""),
        app_secret=os.getenv("FEISHU_APP_SECRET", ""),
        workspace_root=Path(os.getenv("SAILZEN_WORKSPACE_ROOT", "D:/ws/repos/SailZen")),
        llm_provider=os.getenv("LLM_PROVIDER"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        mock_mode=args.mock,
    )

    # Mock mode
    if args.mock:
        print("[Main] Running in MOCK mode")
        config.app_id = "mock_app_id"
        config.app_secret = "mock_app_secret"
    elif not config.app_id or not config.app_secret or "xxxx" in config.app_id:
        print("❌ Feishu credentials not configured!")
        print("   Please edit .env.feishu with your app credentials")
        print("   Get them from: https://open.feishu.cn/app")
        sys.exit(1)

    # Print banner
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║         SailZen Feishu Bot - Phase 0 MVP                     ║
╠══════════════════════════════════════════════════════════════╣
║  Workspace: {str(config.workspace_root)[:48]:<48} ║
║  Mock Mode: {str(config.mock_mode):<48} ║
║  LLM: {str(config.llm_provider or "Not configured"):<52} ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Create and initialize bot
    bot = SailZenFeishuBot(config)
    initialized = await bot.initialize(restore_state=args.restore)
    if not initialized:
        print("❌ Failed to initialize bot")
        sys.exit(1)

    # Trigger self-update if requested
    if args.update_trigger and args.from_opencode:
        print("[Main] Triggering self-update from OpenCode...")
        success = await bot.request_self_update(
            reason="Triggered from OpenCode session",
        )
        if success:
            print("✅ Self-update initiated")
        else:
            print("❌ Self-update failed")
        return

    # Run bot
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\n[Main] Interrupted by user")
    finally:
        print("[Main] Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
