# -*- coding: utf-8 -*-
# @file process_manager.py
# @brief opencode serve 进程生命周期管理
# @author sailing-innocent
# @date 2026-04-25
# @version 1.0
# ---------------------------------
"""sail.opencode.process_manager — opencode serve 进程生命周期管理。

每个工作区路径对应一个 opencode serve 进程和一个端口。

设计原则:
1. 唯一性：同一工作区路径只会映射到一个进程和一个端口
2. 持久化：进程状态写入 data/bot/state/sessions.json，重启后可恢复
3. 可观测：每个进程的 stdout/stderr 写入独立日志文件
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sail.opencode.client import check_health_sync

logger = logging.getLogger(__name__)

_DEFAULT_STATE_FILE = Path("data/bot/state/sessions.json")
_DEFAULT_LOG_DIR = Path("data/bot/opencode_logs")
_STARTUP_TIMEOUT_SEC = 20
_HEALTH_POLL_INTERVAL = 1


# ── 数据类 ────────────────────────────────────────────────────────


class ProcessStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class ManagedProcess:
    """追踪一个 agent serve 进程实例。"""

    path: str
    port: int
    pid: Optional[int] = None
    status: ProcessStatus = ProcessStatus.STOPPED
    session_id: Optional[str] = None
    started_at: Optional[str] = None
    last_error: Optional[str] = None
    chat_id: Optional[str] = None
    cli_tool: str = "opencode-cli"

    _process: Optional[subprocess.Popen] = field(default=None, repr=False)
    _stdout_log: Optional[Any] = field(default=None, repr=False)
    _stderr_log: Optional[Any] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "port": self.port,
            "pid": self.pid,
            "status": self.status.value,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "last_error": self.last_error,
            "chat_id": self.chat_id,
            "cli_tool": self.cli_tool,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManagedProcess":
        proc = cls(
            path=data.get("path", ""),
            port=data.get("port", 0),
            pid=data.get("pid"),
            session_id=data.get("session_id"),
            started_at=data.get("started_at"),
            last_error=data.get("last_error"),
            chat_id=data.get("chat_id"),
            cli_tool=data.get("cli_tool", "opencode-cli"),
        )
        try:
            proc.status = ProcessStatus(data.get("status", "stopped"))
        except ValueError:
            proc.status = ProcessStatus.STOPPED
        return proc

    @property
    def is_alive(self) -> bool:
        if not self.port:
            return False
        return _port_open(self.port)


# ── 主管理器 ──────────────────────────────────────────────────────


class OpenCodeProcessManager:
    """agent serve 进程生命周期管理器。"""

    def __init__(
        self,
        base_port: int = 4096,
        state_file: Optional[Path] = None,
        log_dir: Optional[Path] = None,
        startup_timeout: int = _STARTUP_TIMEOUT_SEC,
        projects: Optional[List[Dict[str, Any]]] = None,
        cli_tool: str = "opencode-cli",
    ) -> None:
        self.base_port = base_port
        self._cli_tool = cli_tool
        self._state_file = state_file or _DEFAULT_STATE_FILE
        self._log_dir = log_dir or _DEFAULT_LOG_DIR
        self._startup_timeout = startup_timeout
        self._projects: List[Dict[str, Any]] = projects or []
        self._processes: Dict[str, ManagedProcess] = {}
        self._load_state()

    # ── 公共 API（同步）───────────────────────────────────────────

    def ensure_running(
        self,
        path: str,
        chat_id: Optional[str] = None,
    ) -> Tuple[bool, ManagedProcess, str]:
        resolved = self._resolve_path(path)
        if resolved is None:
            dummy = ManagedProcess(path=path, port=0)
            dummy.status = ProcessStatus.ERROR
            dummy.last_error = f"路径不存在或无效: {path}"
            return False, dummy, dummy.last_error

        path = resolved
        proc = self._processes.get(path)
        if proc and proc.is_alive:
            proc.status = ProcessStatus.RUNNING
            return True, proc, f"已在端口 {proc.port} 运行"

        port = self._allocate_port()
        if proc is None:
            proc = ManagedProcess(path=path, port=port, chat_id=chat_id, cli_tool=self._cli_tool)
            self._processes[path] = proc
        else:
            proc.port = port
            proc.session_id = None
            proc.cli_tool = self._cli_tool

        return self._start_process(proc)

    def stop(self, path: str) -> Tuple[bool, str]:
        resolved = self._resolve_path(path, must_exist=False)
        path = resolved or path
        proc = self._processes.get(path)
        if not proc:
            return False, f"未找到 {path} 的进程"

        self._kill_process(proc)
        proc.status = ProcessStatus.STOPPED
        proc.pid = None
        proc.session_id = None
        self._save_state()
        logger.info("[ProcessManager] 已停止: %s", path)
        return True, "已停止"

    def stop_all(self) -> int:
        count = 0
        for path in list(self._processes.keys()):
            ok, _ = self.stop(path)
            if ok:
                count += 1
        return count

    def get_or_create_api_session(self, path: str) -> Optional[str]:
        resolved = self._resolve_path(path, must_exist=False)
        path = resolved or path
        proc = self._processes.get(path)
        if not proc or proc.status != ProcessStatus.RUNNING:
            return None
        if proc.session_id:
            return proc.session_id

        try:
            import httpx
            title = f"SailZen - {Path(path).name}"
            with httpx.Client(timeout=10.0) as c:
                resp = c.post(
                    f"http://127.0.0.1:{proc.port}/session",
                    json={"title": title},
                )
                resp.raise_for_status()
                from sail.opencode.client import Session
                sess = Session.from_dict(resp.json())
                proc.session_id = sess.id
                self._save_state()
                return sess.id
        except Exception as exc:
            logger.error("[ProcessManager] 创建 API session 失败: %s", exc)
            return None

    def list_processes(self) -> List[ManagedProcess]:
        return list(self._processes.values())

    def get_status_text(self) -> str:
        if not self._processes:
            return "当前无 agent 进程。"
        lines = [f"=== {self._cli_tool} 进程状态 ==="]
        for proc in self._processes.values():
            alive = proc.is_alive
            icon = (
                "🟢" if alive
                else {"stopped": "⚪", "starting": "🟡", "error": "🔴"}.get(
                    proc.status.value, "⚪"
                )
            )
            lines.append(
                f"{icon} {Path(proc.path).name}  port={proc.port}  pid={proc.pid or '-'}"
            )
            if proc.last_error:
                lines.append(f"   ⚠ {proc.last_error}")
        return "\n".join(lines)

    def find_by_slug(
        self, slug: str, projects: List[Dict[str, Any]]
    ) -> Optional[str]:
        for p in projects:
            if p.get("slug") == slug or p.get("label", "").lower() == slug.lower():
                return p.get("path", "")
        return None

    # ── 公共 API（异步）───────────────────────────────────────────

    async def ensure_running_async(
        self, path: str, chat_id: Optional[str] = None,
    ) -> Tuple[bool, ManagedProcess, str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.ensure_running, path, chat_id)

    async def stop_async(self, path: str) -> Tuple[bool, str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.stop, path)

    async def get_status_text_async(self) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_status_text)

    # ── 内部：进程控制 ────────────────────────────────────────────

    def _start_process(
        self, proc: ManagedProcess
    ) -> Tuple[bool, ManagedProcess, str]:
        path = Path(proc.path)
        if not path.exists():
            proc.status = ProcessStatus.ERROR
            proc.last_error = f"路径不存在: {proc.path}"
            return False, proc, proc.last_error

        self._log_dir.mkdir(parents=True, exist_ok=True)
        out_log_path = self._log_dir / f"agent_{proc.port}.out.log"
        err_log_path = self._log_dir / f"agent_{proc.port}.err.log"

        cmd = [
            proc.cli_tool, "serve",
            "--hostname", "127.0.0.1",
            "--port", str(proc.port),
        ]
        kwargs: Dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
            kwargs["shell"] = True

        logger.info("[ProcessManager] 启动: %s (cwd=%s)", " ".join(cmd), proc.path)

        try:
            stdout_fh = open(out_log_path, "w", encoding="utf-8")
            stderr_fh = open(err_log_path, "w", encoding="utf-8")
            process = subprocess.Popen(
                cmd, cwd=proc.path, stdout=stdout_fh, stderr=stderr_fh, **kwargs,
            )
            proc.pid = process.pid
            proc._process = process
            proc._stdout_log = stdout_fh
            proc._stderr_log = stderr_fh
            proc.status = ProcessStatus.STARTING
            proc.started_at = datetime.now().isoformat()
        except FileNotFoundError:
            proc.status = ProcessStatus.ERROR
            proc.last_error = f"{proc.cli_tool} 命令未找到。请确认已安装并在 PATH 中。"
            return False, proc, proc.last_error
        except Exception as exc:
            proc.status = ProcessStatus.ERROR
            proc.last_error = str(exc)
            return False, proc, proc.last_error

        for _ in range(self._startup_timeout):
            time.sleep(_HEALTH_POLL_INTERVAL)
            if check_health_sync(proc.port):
                proc.status = ProcessStatus.RUNNING
                self._save_state()
                msg = f"已启动 port={proc.port} PID={proc.pid}"
                logger.info("[ProcessManager] %s", msg)
                return True, proc, msg

        self._kill_process(proc)
        proc.status = ProcessStatus.ERROR
        proc.last_error = (
            f"{proc.cli_tool} serve 在 {self._startup_timeout}s 内未就绪 "
            f"(port={proc.port})。请检查日志: {err_log_path}"
        )
        return False, proc, proc.last_error

    def _kill_process(self, proc: ManagedProcess) -> None:
        if proc._process:
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/PID", str(proc._process.pid), "/T", "/F"],
                        check=False, capture_output=True,
                    )
                else:
                    proc._process.terminate()
                try:
                    proc._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc._process.kill()
                    proc._process.wait(timeout=2)
            except Exception as exc:
                logger.warning("[ProcessManager] 终止进程异常: %s", exc)
            proc._process = None

        for fh in (proc._stdout_log, proc._stderr_log):
            if fh:
                try:
                    fh.close()
                except Exception:
                    pass
        proc._stdout_log = proc._stderr_log = None

    # ── 内部：端口分配 ────────────────────────────────────────────

    def _allocate_port(self) -> int:
        used = {p.port for p in self._processes.values() if p.port}
        port = self.base_port
        while port in used or _port_open(port):
            port += 1
        return port

    # ── 内部：路径解析 ────────────────────────────────────────────

    def _resolve_path(self, path: str, must_exist: bool = True) -> Optional[str]:
        if not path:
            return None
        lower = path.strip().lower()
        for p in self._projects:
            if p.get("slug", "").lower() == lower or p.get("label", "").lower() == lower:
                raw = p.get("path", "")
                if raw:
                    return self._resolve_path(raw, must_exist=must_exist)
        try:
            resolved = str(Path(path).expanduser().resolve())
            if must_exist and not Path(resolved).exists():
                return None
            return resolved
        except Exception:
            return None

    # ── 内部：状态持久化 ──────────────────────────────────────────

    def _save_state(self) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            data = [p.to_dict() for p in self._processes.values()]
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error("[ProcessManager] 保存状态失败: %s", exc)

    def _load_state(self) -> None:
        if not self._state_file.exists():
            return
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            recovered = 0
            for item in data:
                path = item.get("path", "")
                port = item.get("port", 0)
                if not path or not port:
                    continue
                if _port_open(port):
                    try:
                        if check_health_sync(port):
                            proc = ManagedProcess.from_dict(item)
                            proc.status = ProcessStatus.RUNNING
                            self._processes[path] = proc
                            recovered += 1
                            continue
                    except Exception:
                        pass

            if recovered:
                logger.info("[ProcessManager] 恢复 %d 个进程", recovered)
            self._save_state()
        except Exception as exc:
            logger.error("[ProcessManager] 加载状态失败: %s", exc)
            self._processes.clear()


# ── 辅助函数 ──────────────────────────────────────────────────────


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def extract_path_from_text(text: str, projects: List[Dict[str, str]]) -> Optional[str]:
    """从文本中提取路径（支持项目快捷名和绝对路径）。"""
    import re
    text = text.strip()
    text_lower = text.lower()
    for p in projects:
        slug = p.get("slug", "")
        label = p.get("label", "")
        if slug and text_lower == slug.lower():
            return p.get("path", "")
        if label and text_lower == label.lower():
            return p.get("path", "")
    # 子串匹配：在文本中查找项目 slug/label（如 "启动 sz" 中的 sz）
    for p in projects:
        slug = p.get("slug", "")
        label = p.get("label", "")
        if slug and slug.lower() in text_lower:
            return p.get("path", "")
        if label and label.lower() in text_lower:
            return p.get("path", "")
    for pattern in [r"([~/][^\s]+)", r"([A-Z]:\\[^\s]+)", r"([A-Z]:/[^\s]+)"]:
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    return None
