"""cube.codemaker.process_manager — codemaker serve 进程生命周期管理。

每个工作区路径对应一个 codemaker serve 进程和一个端口。

设计原则
--------
1. **唯一性**：同一工作区路径只会映射到一个进程和一个端口
2. **持久化**：进程状态写入 data/bot/state/sessions.json，重启后可恢复
3. **线程安全**：同步和异步操作均有锁保护
4. **可观测**：每个进程的 stdout/stderr 写入独立日志文件

工作区 → 进程 → 端口 映射关系
------------------------------
    /path/to/project-A  →  PID 12345  →  port 4096
    /path/to/project-B  →  PID 12346  →  port 4097

状态文件格式 (data/bot/state/sessions.json)
-----------------------------------------
    [
      {"path": "/abs/path", "port": 4096, "session_id": "abc..."},
      ...
    ]

集成示例
--------
::

    from cube.codemaker.process_manager import CodemakerProcessManager

    mgr = CodemakerProcessManager(base_port=4096, projects=[
        {"slug": "mycube", "path": "/abs/path/to/workspace"},
    ])

    # 同步 (脚本/启动时)
    ok, proc, msg = mgr.ensure_running("/path/to/workspace")

    # 异步 (FastAPI / asyncio)
    ok, proc, msg = await mgr.ensure_running_async("/path/to/workspace")
    if ok:
        print(f"Running on port {proc.port}")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cube.codemaker.client import check_health_sync
from cube.paths import path_under_data_dir

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────────

_DEFAULT_STATE_FILE = Path("bot/state/sessions.json")
_DEFAULT_LOG_DIR = Path("bot/codemaker_logs")
_STARTUP_TIMEOUT_SEC = 20   # 等待进程健康检查的最长秒数
_HEALTH_POLL_INTERVAL = 1   # 健康轮询间隔（秒）

# ── 进程级端口分配锁 ──────────────────────────────────────────────
# 跨所有 CodemakerProcessManager 实例的全局锁，确保并发启动多个 task 时不会竞争同一端口。
_PORT_ALLOC_LOCK = threading.Lock()


# ── 数据类 ────────────────────────────────────────────────────────


class ProcessStatus(str, Enum):
    """codemaker serve 进程状态。"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class ManagedProcess:
    """追踪一个 codemaker serve 进程实例。

    Attributes:
        path:           工作区绝对路径
        port:           监听端口
        pid:            操作系统进程 ID
        status:         当前状态
        session_id:     已创建的 codemaker API session ID（可选）
        started_at:     启动时间（ISO 格式）
        last_error:     最近一次错误信息
        chat_id:        POPO/IM 发送者标识（可选）
    """

    path: str
    port: int
    pid: Optional[int] = None
    status: ProcessStatus = ProcessStatus.STOPPED
    session_id: Optional[str] = None
    started_at: Optional[str] = None
    last_error: Optional[str] = None
    chat_id: Optional[str] = None

    # 内部进程句柄（不序列化）
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
        )
        try:
            proc.status = ProcessStatus(data.get("status", "stopped"))
        except ValueError:
            proc.status = ProcessStatus.STOPPED
        return proc

    @property
    def is_alive(self) -> bool:
        """通过轮询端口检查进程是否存活（不发 HTTP）。"""
        if not self.port:
            return False
        return _port_open(self.port)


# ── 主管理器 ──────────────────────────────────────────────────────


class CodemakerProcessManager:
    """codemaker serve 进程生命周期管理器。

    每个工作区路径对应一个独立的 codemaker 进程。
    管理器负责启动、检测、停止进程，并持久化状态到磁盘。

    同步用法::

        mgr = CodemakerProcessManager(base_port=4096)
        ok, proc, msg = mgr.ensure_running("/path/to/workspace")
        if ok:
            # 使用 proc.port 连接 codemaker
            sess_id = mgr.get_or_create_api_session(proc.path)

    异步用法::

        mgr = CodemakerProcessManager(base_port=4096)
        ok, proc, msg = await mgr.ensure_running_async("/path/to/workspace")

    与旧 CodemakerSessionManager 的区别
    ------------------------------------
    - 状态字段统一为 ProcessStatus 枚举（不再是字符串）
    - 异步方法不阻塞事件循环（使用 run_in_executor）
    - 更完善的错误诊断信息
    - 支持健康检查超时配置
    """

    def __init__(
        self,
        base_port: int = 4096,
        state_file: Optional[Path] = None,
        log_dir: Optional[Path] = None,
        startup_timeout: int = _STARTUP_TIMEOUT_SEC,
        projects: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.base_port = base_port
        self._state_file = self._resolve_data_path(state_file or _DEFAULT_STATE_FILE)
        self._log_dir = self._resolve_data_path(log_dir or _DEFAULT_LOG_DIR)
        self._startup_timeout = startup_timeout
        # projects: [{"slug": "foo", "path": "/abs/path", "label": "..."}]
        self._projects: List[Dict[str, Any]] = projects or []
        self._processes: Dict[str, ManagedProcess] = {}
        self._load_state()

    @staticmethod
    def _resolve_data_path(path: str | os.PathLike[str] | Path) -> Path:
        raw = Path(path).expanduser()
        if raw.is_absolute():
            return raw.resolve()
        parts = raw.parts
        if parts and parts[0].lower() == "data":
            raw = Path(*parts[1:]) if len(parts) > 1 else Path()
        return path_under_data_dir(raw)

    # ── 公共 API（同步）───────────────────────────────────────────

    def ensure_running(
        self,
        path: str,
        chat_id: Optional[str] = None,
    ) -> Tuple[bool, ManagedProcess, str]:
        """确保指定路径有运行中的 codemaker 进程。

        如果进程已在运行则直接返回，否则启动新进程并等待健康检查。

        Returns:
            (success, managed_process, message)
        """
        resolved = self._resolve_path(path)
        if resolved is None:
            dummy = ManagedProcess(path=path, port=0)
            dummy.status = ProcessStatus.ERROR
            dummy.last_error = f"路径不存在或无效: {path}"
            return False, dummy, dummy.last_error

        path = resolved
        proc_key = path
        proc = self._processes.get(proc_key)
        if proc and proc.is_alive:
            proc.status = ProcessStatus.RUNNING
            return True, proc, f"已在端口 {proc.port} 运行"

        # 分配端口并启动
        port = self._allocate_port()
        if proc is None:
            proc = ManagedProcess(path=path, port=port, chat_id=chat_id)
            self._processes[proc_key] = proc
        else:
            proc.port = port
            proc.session_id = None

        return self._start_process(proc)

    def ensure_running_unique(
        self,
        path: str,
        key: str,
        chat_id: Optional[str] = None,
    ) -> Tuple[bool, ManagedProcess, str]:
        """启动一个以 key 区分的独立 codemaker 进程，cwd 仍使用真实 path。

        与 ensure_running(path) 不同，这个方法不按工作区路径复用进程；调用方可用
        task_id/session_id 等构造 key，实现同一工作目录下多个任务的端口隔离。
        """
        resolved = self._resolve_path(path)
        if resolved is None:
            dummy = ManagedProcess(path=path, port=0)
            dummy.status = ProcessStatus.ERROR
            dummy.last_error = f"路径不存在或无效: {path}"
            return False, dummy, dummy.last_error

        proc_key = key or resolved
        proc = self._processes.get(proc_key)
        if proc and proc.is_alive:
            proc.status = ProcessStatus.RUNNING
            return True, proc, f"已在端口 {proc.port} 运行"

        port = self._allocate_port()
        if proc is None:
            proc = ManagedProcess(path=resolved, port=port, chat_id=chat_id)
            self._processes[proc_key] = proc
        else:
            proc.path = resolved
            proc.port = port
            proc.session_id = None

        return self._start_process(proc)

    def stop(self, path: str) -> Tuple[bool, str]:
        """停止工作区或唯一 key 对应的 codemaker 进程。"""
        resolved = self._resolve_path(path, must_exist=False)
        proc_key = path
        proc = self._processes.get(proc_key)
        if proc is None and resolved:
            proc_key = resolved
            proc = self._processes.get(proc_key)
        if not proc:
            return False, f"未找到 {path} 的进程"

        self._kill_process(proc)
        proc.status = ProcessStatus.STOPPED
        proc.pid = None
        proc.session_id = None
        self._save_state()
        logger.info("[ProcessManager] 已停止: %s", proc_key)
        return True, "已停止"

    def stop_all(self) -> int:
        """停止所有托管进程，返回停止数量。"""
        count = 0
        for path in list(self._processes.keys()):
            ok, _ = self.stop(path)
            if ok:
                count += 1
        return count

    def get_or_create_api_session(self, path: str) -> Optional[str]:
        """获取或创建 codemaker API session，返回 session_id。"""
        resolved = self._resolve_path(path, must_exist=False)
        path = resolved or path
        proc = self._processes.get(path)
        if not proc or proc.status != ProcessStatus.RUNNING:
            return None
        if proc.session_id:
            return proc.session_id

        try:
            import httpx
            title = f"CubeClaw - {Path(path).name}"
            with httpx.Client(timeout=10.0) as c:
                resp = c.post(
                    f"http://127.0.0.1:{proc.port}/session",
                    json={"title": title},
                )
                resp.raise_for_status()
                from cube.codemaker.client import Session
                sess = Session.from_dict(resp.json())
                proc.session_id = sess.id
                self._save_state()
                return sess.id
        except Exception as exc:
            logger.error("[ProcessManager] 创建 API session 失败: %s", exc)
            return None

    def list_processes(self) -> List[ManagedProcess]:
        """列出所有托管进程。"""
        return list(self._processes.values())

    def get_status_text(self) -> str:
        """返回所有进程状态的可读摘要。"""
        if not self._processes:
            return "当前无 codemaker 进程。"
        lines = ["=== CodeMaker 进程状态 ==="]
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
        """从项目配置中通过 slug/label 解析路径。"""
        for p in projects:
            if p.get("slug") == slug or p.get("label", "").lower() == slug.lower():
                return p.get("path", "")
        return None

    # ── 公共 API（异步）───────────────────────────────────────────

    async def ensure_running_async(
        self,
        path: str,
        chat_id: Optional[str] = None,
    ) -> Tuple[bool, ManagedProcess, str]:
        """异步版 ensure_running，不阻塞事件循环。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.ensure_running, path, chat_id
        )

    async def ensure_running_unique_async(
        self,
        path: str,
        key: str,
        chat_id: Optional[str] = None,
    ) -> Tuple[bool, ManagedProcess, str]:
        """异步版 ensure_running_unique。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.ensure_running_unique, path, key, chat_id
        )

    async def stop_async(self, path: str) -> Tuple[bool, str]:
        """异步版 stop。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.stop, path)

    async def get_status_text_async(self) -> str:
        """异步版 get_status_text（含端口存活检测）。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_status_text)

    def register_commands(self, bus: Any) -> None:
        """将 codemaker 进程管理命令注册到 CommandBus。

        注册以下命令:
          cm_start   — 启动指定工作区的 codemaker 进程
          cm_stop    — 停止指定工作区的 codemaker 进程
          cm_status  — 查看所有进程状态
          cm_list    — 列出所有进程（JSON 结构）

        Args:
            bus: cube.command_bus.CommandBus 实例
        """
        from cube.command_bus import Command, CommandResult

        mgr = self  # 闭包捕获

        async def handle_cm_start(cmd: Command) -> CommandResult:
            target = cmd.args.get("target", "")
            path = mgr._resolve_path(target, must_exist=False)
            if not path:
                # 如果解析失败，直接用 target 当路径尝试
                path = target
            if not path:
                return CommandResult.fail("请指定工作区路径或项目名")
            ok, proc, msg = await mgr.ensure_running_async(path)
            if ok:
                return CommandResult.ok(
                    data=proc.to_dict(),
                    text=f"✅ {Path(path).name}: {msg}",
                )
            return CommandResult.fail(msg)

        async def handle_cm_stop(cmd: Command) -> CommandResult:
            target = cmd.args.get("target", "")
            path = mgr._resolve_path(target, must_exist=False) or target
            if not path:
                return CommandResult.fail("请指定工作区路径或项目名")
            ok, msg = await mgr.stop_async(path)
            if ok:
                return CommandResult.ok(text=f"✅ {Path(path).name} 已停止")
            return CommandResult.fail(msg)

        async def handle_cm_status(cmd: Command) -> CommandResult:
            text = await mgr.get_status_text_async()
            procs = [p.to_dict() for p in mgr.list_processes()]
            return CommandResult.ok(data=procs, text=text)

        async def handle_cm_list(cmd: Command) -> CommandResult:
            procs = [p.to_dict() for p in mgr.list_processes()]
            return CommandResult.ok(
                data=procs, text=f"共 {len(procs)} 个 codemaker 进程"
            )

        bus.register("cm_start", handle_cm_start)
        bus.register("cm_stop", handle_cm_stop)
        bus.register("cm_status", handle_cm_status)
        bus.register("cm_list", handle_cm_list)

    def _start_process(
        self, proc: ManagedProcess
    ) -> Tuple[bool, ManagedProcess, str]:
        """启动 codemaker serve 进程并等待健康检查。"""
        path = Path(proc.path)
        if not path.exists():
            proc.status = ProcessStatus.ERROR
            proc.last_error = f"路径不存在: {proc.path}"
            return False, proc, proc.last_error

        self._log_dir.mkdir(parents=True, exist_ok=True)
        out_log_path = self._log_dir / f"codemaker_{proc.port}.out.log"
        err_log_path = self._log_dir / f"codemaker_{proc.port}.err.log"

        cmd = [
            "codemaker", "serve",
            "--hostname", "127.0.0.1",
            "--port", str(proc.port),
        ]
        kwargs: Dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
            kwargs["shell"] = True

        logger.info(
            "[ProcessManager] 启动: %s (cwd=%s)", " ".join(cmd), proc.path
        )

        try:
            stdout_fh = open(out_log_path, "w", encoding="utf-8")
            stderr_fh = open(err_log_path, "w", encoding="utf-8")
            process = subprocess.Popen(
                cmd,
                cwd=proc.path,
                stdout=stdout_fh,
                stderr=stderr_fh,
                **kwargs,
            )
            proc.pid = process.pid
            proc._process = process
            proc._stdout_log = stdout_fh
            proc._stderr_log = stderr_fh
            proc.status = ProcessStatus.STARTING
            proc.started_at = datetime.now().isoformat()
        except FileNotFoundError:
            proc.status = ProcessStatus.ERROR
            proc.last_error = "codemaker 命令未找到。请确认 codemaker 可执行文件在 PATH 中。"
            return False, proc, proc.last_error
        except Exception as exc:
            proc.status = ProcessStatus.ERROR
            proc.last_error = str(exc)
            return False, proc, proc.last_error

        # ── 健康检查轮询 ──────────────────────────────────────────
        logger.info(
            "[ProcessManager] 等待 codemaker 就绪: port=%d pid=%s timeout=%ds",
            proc.port, proc.pid, self._startup_timeout,
        )
        _t_start = time.time()
        _t_last_log = _t_start
        for _ in range(self._startup_timeout):
            time.sleep(_HEALTH_POLL_INTERVAL)
            elapsed_s = time.time() - _t_start
            if check_health_sync(proc.port):
                proc.status = ProcessStatus.RUNNING
                self._save_state()
                msg = f"已启动 port={proc.port} PID={proc.pid}"
                logger.info("[ProcessManager] %s (耗时 %.1fs)", msg, elapsed_s)
                return True, proc, msg
            # 每 5 秒（挂钟时间）打一次进度日志，避免长时间启动静默
            now = time.time()
            if now - _t_last_log >= 5.0:
                logger.info(
                    "[ProcessManager] 仍在等待 codemaker 就绪: port=%d elapsed=%.0fs/timeout=%ds",
                    proc.port, elapsed_s, self._startup_timeout,
                )
                _t_last_log = now

        # 超时：清理
        self._kill_process(proc)
        proc.status = ProcessStatus.ERROR
        proc.last_error = (
            f"codemaker serve 在 {self._startup_timeout}s 内未就绪 "
            f"(port={proc.port})。请检查日志: {err_log_path}"
        )
        return False, proc, proc.last_error

    def _kill_process(self, proc: ManagedProcess) -> None:
        """终止进程，关闭日志文件句柄。

        优先使用 subprocess.Popen 句柄终止；若句柄已丢失（如从磁盘恢复的状态），
        则通过 pid 使用 taskkill(Windows) / os.kill(Unix) 强制终止。
        """
        if proc._process:
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/PID", str(proc._process.pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
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
        elif proc.pid:
            # _process 句柄已丢失（如从 sessions.json 恢复），通过 pid 强杀
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
                    )
                else:
                    os.kill(proc.pid, signal.SIGTERM)
                logger.info("[ProcessManager] 通过 pid 强制终止: PID %d", proc.pid)
            except (ProcessLookupError, PermissionError, OSError) as exc:
                logger.warning("[ProcessManager] 通过 pid 终止失败 (PID %d): %s", proc.pid, exc)
            proc.pid = None

        for fh in (proc._stdout_log, proc._stderr_log):
            if fh:
                try:
                    fh.close()
                except Exception:
                    pass
        proc._stdout_log = proc._stderr_log = None

    # ── 内部：端口分配 ────────────────────────────────────────────

    def _allocate_port(self) -> int:
        """分配一个未被占用的端口（从 base_port 递增查找）。

        使用进程级全局锁（_PORT_ALLOC_LOCK）防止多个 CodemakerProcessManager 实例
        在并发启动时竞争同一端口。锁内用 socket.bind 做原子性占用探测，避免
        "检查-分配"之间的 TOCTOU 竞态。
        """
        with _PORT_ALLOC_LOCK:
            used = {p.port for p in self._processes.values() if p.port}
            port = self.base_port
            while True:
                if port in used or _port_open(port):
                    port += 1
                    continue
                # 用 SO_REUSEADDR=0 尝试 bind，确保端口真的可用且无其他进程抢占
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
                        probe.bind(("127.0.0.1", port))
                    # bind 成功代表端口可用，立刻返回（close 后端口释放，由 codemaker 占用）
                    break
                except OSError:
                    port += 1
                    continue
            return port

    # ── 内部：路径解析 ────────────────────────────────────────────

    def _resolve_path(self, path: str, must_exist: bool = True) -> Optional[str]:
        """将 path / slug / label 解析为绝对路径。

        优先尝试 self._projects 中的 slug/label 匹配，
        再按文件系统路径解析。
        """
        if not path:
            return None
        # 1. 尝试 slug / label
        lower = path.strip().lower()
        for p in self._projects:
            if p.get("slug", "").lower() == lower or p.get("label", "").lower() == lower:
                raw = p.get("path", "")
                if raw:
                    return self._resolve_path(raw, must_exist=must_exist)
        # 2. 文件系统路径
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
        """启动时从磁盘恢复状态，跳过端口已关闭的条目。"""
        if not self._state_file.exists():
            return
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            recovered = 0
            skipped = 0
            for item in data:
                path = item.get("path", "")
                port = item.get("port", 0)
                if not path or not port:
                    skipped += 1
                    continue
                if _port_open(port):
                    # 尝试健康检查
                    try:
                        if check_health_sync(port):
                            proc = ManagedProcess.from_dict(item)
                            proc.status = ProcessStatus.RUNNING
                            self._processes[path] = proc
                            recovered += 1
                            continue
                    except Exception:
                        pass
                skipped += 1

            if recovered:
                logger.info("[ProcessManager] 恢复 %d 个进程", recovered)
            if skipped:
                logger.info("[ProcessManager] 跳过 %d 个失效进程", skipped)
            self._save_state()  # 清理失效条目
        except Exception as exc:
            logger.error("[ProcessManager] 加载状态失败: %s", exc)
            self._processes.clear()


# ── 辅助函数 ──────────────────────────────────────────────────────


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    """检查指定端口是否可达。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def resolve_workspace_path(
    slug_or_path: str,
    projects: List[Dict[str, Any]],
) -> Optional[str]:
    """从项目配置或路径字符串解析工作区绝对路径。

    查找优先级:
      1. projects 列表中的 slug 精确匹配
      2. projects 列表中的 label 大小写无关匹配
      3. 直接路径（expanduser + resolve）

    Args:
        slug_or_path: 项目 slug、label 或路径字符串
        projects:     来自 bot.yaml 的项目配置列表

    Returns:
        绝对路径字符串，或 None（未找到）
    """
    if not slug_or_path:
        return None

    for p in projects:
        if p.get("slug") == slug_or_path:
            return p.get("path")
        if p.get("label", "").lower() == slug_or_path.lower():
            return p.get("path")

    try:
        resolved = str(Path(slug_or_path).expanduser().resolve())
        return resolved
    except Exception:
        return None
