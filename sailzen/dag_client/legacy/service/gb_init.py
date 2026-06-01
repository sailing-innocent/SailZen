"""GlobalBatch 初始化服务 — 环境准备 + 任务分配。

Mock 模式: 生成模拟 commit 列表, 跳过 git 操作
Real 模式: 执行实际的 git clone / fetch / worktree + start_globalbatch.py

两阶段架构:
  Phase 0 (create_init_batch):  立即创建 Batch + init_workspace 节点 → 前端可立刻看到 Pipeline
  Phase 1/2/3 (execute_init):   task runner 执行 init_workspace 节点时，真实执行 git 操作并创建剩余 DAG

用法:
    from bot_server.service.gb_init import create_init_batch, execute_init

    # Phase 0 — Pipeline handler 立即调用
    batch, init_task = await create_init_batch(
        db=db, scheduler=scheduler, workspace_id="...",
        config={"predecessor_branch": "...", "subbatch_size": 50, ...},
    )

    # Phase 1/2/3 — task runner 执行 init_workspace 节点时调用
    result = await execute_init(db=db, scheduler=scheduler, batch=batch, task=init_task, config=config)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from bot_server.models import (
    BatchStatus, TaskStatus, TaskType, TaskTimeoutConfig, make_batch, make_sub_batch,
    make_task, make_event_log, new_id, now_iso,
)
from bot_server.scheduler import get_ready_tasks
from bot_server.service.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


# ── 进度回调类型 ────────────────────────────────────────────────────
# progress_cb(phase, step, message) — 用于 SSE/日志 实时推送初始化进度

ProgressCallback = Optional[Callable[[str, str, str], Any]]


# ── Mock commit 生成 ──────────────────────────────────────────────


def _generate_mock_commits(count: int) -> List[str]:
    """生成可读的模拟 commit hash 列表。

    格式: mock001, mock002, ..., mock200
    这样在 POPO 报告和 Dashboard 中可以一眼看出:
      - SubBatch _a 分到了 mock001..mock050
      - SubBatch _b 分到了 mock051..mock100
      - ...
    """
    return [f"mock{i + 1:03d}" for i in range(count)]


# ── Shell 命令执行 ────────────────────────────────────────────────


# ── 初始化日志目录 (模块级, 每次 init 设置一次) ────────────────────

_init_log_dir: Optional[str] = None


def _set_init_log_dir(workspace_root: str) -> str:
    """创建并设置本次初始化的日志目录。

    目录结构:
        {workspace_root}/_logs/{YYYYMMDD_HHmmss}/
            Phase1_clone.stdout.log
            Phase1_clone.stderr.log
            Phase1_fetch-predecessor.stdout.log
            ...
    """
    global _init_log_dir
    now = datetime.now()
    log_dir = os.path.join(
        workspace_root, "_logs", now.strftime("%Y%m%d_%H%M%S"),
    )
    os.makedirs(log_dir, exist_ok=True)
    _init_log_dir = log_dir
    logger.info("[GB Init] 命令日志目录: %s", log_dir)
    return log_dir


def _get_log_path(label: str, stream: str) -> Optional[str]:
    """获取日志文件路径。label 中的 / 替换为 _。"""
    if not _init_log_dir:
        return None
    safe_label = label.replace("/", "_").replace("\\", "_").replace(" ", "_")
    return os.path.join(_init_log_dir, f"{safe_label}.{stream}.log")


async def _stream_pipe(
    pipe: asyncio.StreamReader,
    label: str,
    stream_name: str,
    log_file: Optional[str],
    collected: List[bytes],
) -> None:
    """实时读取 pipe 并输出到 logger + 文件。

    git 的进度信息 (clone/fetch) 通过 stderr + \\r 输出,
    不会触发 readline(), 所以使用 read(chunk) 作为后备:
      - 先尝试带超时的 readline()
      - 超时后 fallback 到 read(4096) 读取 partial 数据
    """
    fh = None
    if log_file:
        try:
            fh = open(log_file, "wb")
        except Exception as e:
            logger.warning("[GB Init][%s] 无法打开日志文件 %s: %s", label, log_file, e)

    _last_log_text = ""  # 用于去重 git progress bar 的重复行

    try:
        while True:
            # 尝试 readline, 3 秒超时后用 read(chunk) 兜底
            try:
                data = await asyncio.wait_for(pipe.readline(), timeout=3.0)
            except asyncio.TimeoutError:
                # git progress 用 \r, readline 读不到 \n → 读 chunk
                try:
                    data = await asyncio.wait_for(pipe.read(4096), timeout=3.0)
                except asyncio.TimeoutError:
                    continue  # 什么都没读到, 继续等
            if not data:
                break

            collected.append(data)

            # 解码并按 \r 或 \n 分行, 只取最后一段有意义的文本
            text = data.decode("utf-8", errors="replace")
            # git progress: "Receiving objects:  42% (1234/2929)\r..."
            fragments = text.replace("\r", "\n").split("\n")
            for frag in fragments:
                frag = frag.strip()
                if not frag or frag == _last_log_text:
                    continue
                _last_log_text = frag
                display = frag[:300] + ("..." if len(frag) > 300 else "")
                logger.info("[GB Init][%s][%s] %s", label, stream_name, display)

            if fh:
                fh.write(data)
                fh.flush()
    finally:
        if fh:
            fh.close()


async def _heartbeat(label: str, proc: asyncio.subprocess.Process, interval: float = 15.0) -> None:
    """每隔 interval 秒输出一条心跳日志, 直到进程结束。"""
    elapsed = 0.0
    while proc.returncode is None:
        await asyncio.sleep(interval)
        elapsed += interval
        if proc.returncode is None:
            logger.info(
                "[GB Init][%s] ⏳ 仍在运行... (已经过 %.0fs, PID=%d)",
                label, elapsed, proc.pid,
            )


async def _run_cmd(
    cmd: List[str],
    cwd: str,
    label: str = "",
    timeout: int = 600,
    quiet: bool = False,
) -> subprocess.CompletedProcess:
    """异步执行 shell 命令 — 实时流式输出 + 文件日志 + 心跳。

    特性:
      - stdout/stderr 逐行实时输出到 Python logger
      - 同时写入 {_init_log_dir}/{label}.{stdout|stderr}.log 文件
      - 每 15 秒打印心跳日志, 表明进程仍在运行
      - 超时后 kill 进程并抛出 RuntimeError

    Args:
        cmd: 命令列表, 如 ["git", "clone", ...]
        cwd: 工作目录
        label: 日志标识
        timeout: 超时秒数
        quiet: 静默模式 — 跳过日志头/尾、流式输出、心跳;
               适用于批量执行的瞬时命令 (如 git show --quiet),
               失败时仍会打印错误信息

    Returns:
        CompletedProcess

    Raises:
        RuntimeError: 命令执行失败 (returncode != 0) 或超时
    """
    cmd_str = " ".join(cmd)

    if quiet:
        # ── 静默模式: 直接 communicate, 不流式输出, 不心跳 ──
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            err_msg = f"[{label}] 命令超时 ({timeout}s): {cmd_str}"
            logger.error("[GB Init][%s] ❌ %s", label, err_msg)
            raise RuntimeError(err_msg)

        if proc.returncode != 0:
            stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
            last_lines = stderr_text.split("\n")[-10:]
            summary = "\n".join(last_lines)
            err_msg = (
                f"[{label}] 命令失败 (rc={proc.returncode}): {cmd_str}\n"
                f"  stderr 尾部:\n{summary}"
            )
            logger.error("[GB Init][%s] ❌ %s", label, err_msg)
            raise RuntimeError(err_msg)

        return subprocess.CompletedProcess(cmd, proc.returncode, stdout_bytes, stderr_bytes)

    # ── 正常模式: 流式输出 + 心跳 + 文件日志 ──
    stdout_log = _get_log_path(label, "stdout")
    stderr_log = _get_log_path(label, "stderr")

    logger.info("[GB Init][%s] ──────────────────────────────────", label)
    logger.info("[GB Init][%s] 执行命令: %s", label, cmd_str)
    logger.info("[GB Init][%s] 工作目录: %s", label, cwd)
    if stdout_log:
        logger.info("[GB Init][%s] 日志文件: %s", label, stdout_log)
    logger.info("[GB Init][%s] 超时: %ds", label, timeout)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    logger.info("[GB Init][%s] 进程已启动 (PID=%d)", label, proc.pid)

    stdout_lines: List[bytes] = []
    stderr_lines: List[bytes] = []

    # 并发: 流式读取 stdout + stderr + 心跳 + 等待进程
    heartbeat_task = asyncio.create_task(_heartbeat(label, proc))
    stdout_task = asyncio.create_task(
        _stream_pipe(proc.stdout, label, "stdout", stdout_log, stdout_lines)
    )
    stderr_task = asyncio.create_task(
        _stream_pipe(proc.stderr, label, "stderr", stderr_log, stderr_lines)
    )

    try:
        await asyncio.wait_for(
            asyncio.gather(stdout_task, stderr_task, proc.wait()),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        heartbeat_task.cancel()
        err_msg = (
            f"[{label}] 命令超时 ({timeout}s): {cmd_str}\n"
            f"  日志文件: {stderr_log or 'N/A'}"
        )
        logger.error("[GB Init][%s] ❌ %s", label, err_msg)
        raise RuntimeError(err_msg)
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    stdout_bytes = b"".join(stdout_lines)
    stderr_bytes = b"".join(stderr_lines)
    stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        # 失败时输出最后 20 行 stderr 作为摘要
        last_lines = stderr_text.split("\n")[-20:]
        summary = "\n".join(last_lines)
        err_msg = (
            f"[{label}] 命令失败 (rc={proc.returncode}): {cmd_str}\n"
            f"  stderr 尾部:\n{summary}\n"
            f"  完整日志: {stderr_log or 'N/A'}"
        )
        logger.error("[GB Init][%s] ❌ %s", label, err_msg)
        raise RuntimeError(err_msg)

    logger.info("[GB Init][%s] ✅ 命令成功 (rc=0, PID=%d)", label, proc.pid)
    logger.info("[GB Init][%s] ──────────────────────────────────", label)
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout_bytes, stderr_bytes)


# ── 磁盘空间检查 ─────────────────────────────────────────────────


def _check_disk_space(path: str, required_gb: float = 20.0) -> bool:
    """检查指定路径的可用磁盘空间是否满足要求。"""
    try:
        stat = shutil.disk_usage(path)
        free_gb = stat.free / (1024 ** 3)
        logger.info(
            "[GB Init] 磁盘空间检查: %s — %.1f GB 可用 (需要 %.1f GB)",
            path, free_gb, required_gb,
        )
        return free_gb >= required_gb
    except Exception as e:
        logger.warning("[GB Init] 无法检查磁盘空间: %s — %s", path, e)
        return True  # 无法检查时不阻塞


# ── commits.txt 解析 ──────────────────────────────────────────────


def parse_commits_file(commits_path: str) -> List[str]:
    """解析 bd/commits.txt, 返回 commit hash 列表 (不含 revert 信息)。"""
    commits: List[str] = []
    with open(commits_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line == "END":
                break
            commit_hash = line.split("|")[0].strip()
            if commit_hash:
                commits.append(commit_hash)
    return commits


def read_current_commit(current_commit_path: str) -> str:
    """读取 bd/currentCommit.txt, 返回当前 commit hash。"""
    with open(current_commit_path, "r", encoding="utf-8") as f:
        return f.readline().strip()


# ── SubBatch 规划 ────────────────────────────────────────────────


def plan_subbatches(
    all_commits: List[str],
    current_commit: Optional[str] = None,
    subbatch_size: int = 50,
    subbatch_count: int = 4,
) -> List[Dict[str, Any]]:
    """从 commit 列表中规划 SubBatch 分配。

    Args:
        all_commits: 全部 commit hash 列表 (有序)
        current_commit: 起始 commit (从此处开始分配), None 则从头开始
        subbatch_size: 每个 SubBatch 的 commit 数
        subbatch_count: 一次分配的 SubBatch 数量 (_a, _b, _c, _d)

    Returns:
        list of {"suffix", "commits", "start_commit", "end_commit"}
    """
    if not all_commits:
        return []

    # 找到 current_commit 的位置
    start_idx = 0
    if current_commit:
        try:
            start_idx = all_commits.index(current_commit)
        except ValueError:
            logger.warning(
                "current_commit %s not found in commits list, starting from index 0",
                current_commit[:16] if current_commit else "None",
            )
            start_idx = 0

    subbatches: List[Dict[str, Any]] = []
    for i in range(subbatch_count):
        begin = start_idx + i * subbatch_size
        end = min(begin + subbatch_size, len(all_commits))
        if begin >= len(all_commits):
            break
        chunk = all_commits[begin:end]
        subbatches.append({
            "suffix": chr(ord("a") + i),
            "commits": chunk,
            "start_commit": chunk[0],
            "end_commit": chunk[-1],
            "count": len(chunk),
        })

    return subbatches


# ── Phase 1: 环境准备 (Real Mode) ────────────────────────────────


async def _phase1_prepare_environment(
    workspace_root: str,
    github_repo: str,
    github_branch: str,
    predecessor_branch: str,
) -> Dict[str, str]:
    """Phase 1: 创建标准 GlobalBatch 工作目录与 git worktree。

    返回:
        {
            "work_dir": str,              # 日期目录 (如 .../20260424_mcpe/)
            "clone_dir": str,             # clone 目录 (如 .../20260424_mcpe/Minecraftpe/)
            "main_worktree_dir": str,     # mcpe_main 参考 worktree
            "prev_worktree_dir": str,     # mcpe_prev_batch 参考 worktree
            "worktree_dir": str,          # mcpe_gb worktree
            "temp_dir": str,              # repo 外 temp 目录
            "logs_dir": str,              # 初始化/调度日志目录
        }
    """
    now = datetime.now()
    date_dir_name = f"{now.strftime('%Y%m%d')}_mcpe"

    logger.info("[GB Init][Phase1] ── 标准工作区准备 ──")
    logger.info("[GB Init][Phase1] workspace_root: %s", workspace_root)
    logger.info("[GB Init][Phase1] batch_workspace: %s", date_dir_name)

    # 所有命令日志仍放在 workspace_root/_logs 下，保持旧 Dashboard / 调试路径兼容。
    os.makedirs(workspace_root, exist_ok=True)
    _set_init_log_dir(workspace_root)

    if not _check_disk_space(workspace_root):
        raise RuntimeError(
            f"磁盘空间不足: {workspace_root} 需要至少 20GB 可用空间"
        )

    manager = WorkspaceManager(
        run_cmd=_run_cmd,
        run_cmd_stdout=_run_cmd_stdout,
        run_cmd_rc=_run_cmd_rc,
    )
    layout = await manager.prepare_globalbatch_workspace(
        workspace_root=workspace_root,
        github_repo=github_repo,
        github_branch=github_branch,
        predecessor_branch=predecessor_branch,
        batch_workspace_name=date_dir_name,
    )

    logger.info("[GB Init][Phase1] ✅ 标准工作区就绪: %s", layout.batch_workspace_dir)
    logger.info("[GB Init][Phase1]   mcpe_main:       %s", layout.mcpe_main_dir)
    logger.info("[GB Init][Phase1]   mcpe_prev_batch: %s", layout.mcpe_prev_batch_dir)
    logger.info("[GB Init][Phase1]   mcpe_gb:         %s", layout.mcpe_gb_dir)
    logger.info("[GB Init][Phase1]   temp:            %s", layout.temp_dir)

    return {
        "work_dir": layout.batch_workspace_dir,
        "clone_dir": layout.repo_dir,
        "main_worktree_dir": layout.mcpe_main_dir,
        "prev_worktree_dir": layout.mcpe_prev_batch_dir,
        "worktree_dir": layout.mcpe_gb_dir,
        "temp_dir": layout.temp_dir,
        "logs_dir": layout.logs_dir,
    }


async def _mock_init_workspace(
    workspace_root: str,
    github_repo: str,
    github_branch: str,
    predecessor_branch: str,
    subbatch_size: int,
    subbatch_count: int,
) -> Dict[str, Any]:
    """复用一个已存在的 GlobalBatch workspace，跳过 git/start_globalbatch。

    该函数用于 Real 模式下“跳过 Init Workspace”节点：DAG 仍然创建 Init Workspace
    入口节点，但初始化产物必须来自已有真实 workspace 的 ``bd/commits.txt`` 与
    ``bd/currentcommit.txt``，不能再生成 ``mock001`` 这类占位 commit。这样后续
    ``/branch-dance 帮我pick到...`` 才能按真实 SubBatch 边界下发。
    """
    now = datetime.now()
    date_dir_name = f"{now.strftime('%Y%m%d')}_mcpe"
    date_str = now.strftime("%m/%d")
    batch_workspace_dir = os.path.join(workspace_root, date_dir_name) if workspace_root else ""
    env_info = {
        "work_dir": batch_workspace_dir,
        "clone_dir": os.path.join(batch_workspace_dir, "Minecraftpe") if batch_workspace_dir else "",
        "main_worktree_dir": os.path.join(batch_workspace_dir, "mcpe_main") if batch_workspace_dir else "",
        "prev_worktree_dir": os.path.join(batch_workspace_dir, "mcpe_prev_batch") if batch_workspace_dir else "",
        "worktree_dir": os.path.join(batch_workspace_dir, "mcpe_gb") if batch_workspace_dir else "",
        "temp_dir": os.path.join(batch_workspace_dir, "temp") if batch_workspace_dir else "",
        "logs_dir": os.path.join(workspace_root, "_logs", datetime.now().strftime("%Y%m%d_%H%M%S")) if workspace_root else "",
    }

    if not workspace_root:
        raise ValueError("Real 模式跳过 Init Workspace 时仍需要配置 workspace_root")

    worktree_dir = env_info["worktree_dir"]
    bd_dir = os.path.join(worktree_dir, "bd")
    commits_file = os.path.join(bd_dir, "commits.txt")
    current_commit_file = os.path.join(bd_dir, "currentcommit.txt")
    if not os.path.isfile(current_commit_file):
        current_commit_file = os.path.join(bd_dir, "currentCommit.txt")

    missing = [
        path for path in (worktree_dir, bd_dir, commits_file, current_commit_file)
        if not os.path.exists(path)
    ]
    if missing:
        raise RuntimeError(
            "Real 模式跳过 Init Workspace 需要复用已有真实 GlobalBatch workspace，"
            "但未找到必要文件/目录；不会生成 mock commit。缺失: "
            + ", ".join(missing)
        )

    all_commits = parse_commits_file(commits_file)
    current_commit = read_current_commit(current_commit_file)
    if not all_commits:
        raise RuntimeError(f"跳过 Init Workspace 失败: commits.txt 为空或解析失败: {commits_file}")
    if not current_commit:
        raise RuntimeError(f"跳过 Init Workspace 失败: currentcommit.txt 为空: {current_commit_file}")

    working_branch = f"netease/globalbatch/{date_str}"
    branch_state_file = os.path.join(bd_dir, "branchState.txt")
    if os.path.isfile(branch_state_file):
        try:
            with open(branch_state_file, "r", encoding="utf-8") as f:
                branch_state_lines = [line.strip() for line in f.readlines()]
            if len(branch_state_lines) >= 3 and branch_state_lines[2]:
                working_branch = branch_state_lines[2]
        except Exception as exc:
            logger.warning("[GB Init][Real] 读取 branchState.txt 失败，使用默认 working_branch: %s", exc)

    os.makedirs(env_info["temp_dir"], exist_ok=True)
    os.makedirs(env_info["logs_dir"], exist_ok=True)
    logger.info(
        "[GB Init][Real] 复用已有 workspace: commits=%d, currentCommit=%s, worktree=%s",
        len(all_commits), current_commit[:16], worktree_dir,
    )

    return {
        "env_info": env_info,
        "working_branch": working_branch,
        "all_commits": all_commits,
        "current_commit": current_commit,
        "work_dir": env_info["worktree_dir"],
        "mocked": True,
        "reason": "init_workspace_node_mocked_reuse_existing_workspace",
        "github_repo": github_repo,
        "github_branch": github_branch,
        "predecessor_branch": predecessor_branch,
        "commits_file": commits_file,
        "current_commit_file": current_commit_file,
    }


# ── Phase 2: 执行 start_globalbatch (内联, 流式日志) ─────────────


async def _run_cmd_stdout(
    cmd: List[str],
    cwd: str,
    label: str = "",
    timeout: int = 300,
    quiet: bool = False,
) -> str:
    """执行命令并返回 stdout 文本。

    Args:
        quiet: 静默模式, 不输出流式日志 (适用于批量瞬时命令)
    """
    result = await _run_cmd(cmd, cwd=cwd, label=label, timeout=timeout, quiet=quiet)
    return result.stdout.decode("utf-8", errors="replace").strip()


async def _run_cmd_rc(
    cmd: List[str],
    cwd: str,
    label: str = "",
    timeout: int = 120,
    quiet: bool = False,
) -> int:
    """执行命令并返回 returncode, 失败时不抛异常。

    注意: 一些 git 探测命令会用 returncode 表达布尔结果，例如
    `git show-ref --verify --quiet ...` 在 ref 不存在时返回 1。对于
    quiet=True 的调用，这类非 0 退出码是调用方要消费的正常结果，
    不能先经过 `_run_cmd()` 记录为 ERROR 后再转成 rc。
    """
    cmd_str = " ".join(cmd)

    if quiet:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.warning(
                "[GB Init][%s] 命令超时 (非致命, rc=124, %ss): %s",
                label, timeout, cmd_str,
            )
            return 124
        return int(proc.returncode or 0)

    try:
        result = await _run_cmd(cmd, cwd=cwd, label=label, timeout=timeout, quiet=quiet)
        return result.returncode
    except RuntimeError as e:
        logger.warning("[GB Init][%s] 命令失败 (非致命): %s", label, e)
        return 1


async def _is_branch_defined_async(branch: str, cwd: str) -> bool:
    """检查远程分支是否存在 (async 版本)。"""
    result = await _run_cmd_stdout(
        ["git", "ls-remote", "--heads", "origin", branch],
        cwd=cwd,
        label=f"Phase2/ls-remote-{branch.replace('/', '_')}",
        timeout=60,
    )
    return bool(result)


def _parse_milestone_branch(branch: str) -> Optional[tuple[int, int]]:
    """解析 milestone 分支名，支持 r/<major>_u<update>，如 r/26_u2。"""
    match = re.fullmatch(r"r/(\d+)_u(\d+)", branch.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


async def _find_latest_remote_milestone(current_milestone: str, cwd: str) -> str:
    """从 origin 远程分支中找出不小于 current_milestone 的最新 milestone。"""
    current_key = _parse_milestone_branch(current_milestone)
    if current_key is None:
        logger.warning(
            "[GB Init][Phase2] 无法解析 next_milestone '%s'，跳过自动更新 milestone",
            current_milestone,
        )
        return current_milestone

    refs_raw = await _run_cmd_stdout(
        ["git", "ls-remote", "--heads", "origin", "r/*_u*"],
        cwd=cwd,
        label="Phase2/ls-remote-milestones",
        timeout=120,
        quiet=True,
    )

    latest_milestone = current_milestone
    latest_key = current_key
    for line in refs_raw.splitlines():
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        prefix = "refs/heads/"
        if not ref.startswith(prefix):
            continue
        branch = ref[len(prefix):]
        key = _parse_milestone_branch(branch)
        if key is not None and key > latest_key:
            latest_milestone = branch
            latest_key = key

    return latest_milestone


async def _update_next_milestone_from_origin(
    milestone_file: str,
    previous_milestone: str,
    next_milestone: str,
    cwd: str,
) -> str:
    """当 origin 已有更新的 milestone 分支时，更新 currentmilestone.txt 第二行。"""
    latest_milestone = await _find_latest_remote_milestone(next_milestone, cwd)
    if latest_milestone == next_milestone:
        logger.info(
            "[GB Init][Phase2] next_milestone 已是最新: %s",
            next_milestone,
        )
        return next_milestone

    logger.info(
        "[GB Init][Phase2] 发现 origin 上存在更新的 milestone: %s -> %s，更新 currentmilestone.txt",
        next_milestone, latest_milestone,
    )
    with open(milestone_file, "w", encoding="utf-8") as f:
        f.write(f"{previous_milestone}\n{latest_milestone}\n")
    return latest_milestone


async def _phase2_start_globalbatch(
    worktree_dir: str,
    temp_dir: str = "",
) -> Dict[str, Any]:
    """Phase 2: 执行 start_globalbatch 逻辑 (Bedrock mode)。

    每一步 git 命令都通过
    _run_cmd 执行, 享受:
      - 实时流式 stdout/stderr 日志输出
      - 每 15 秒心跳防止看似卡死
      - 超时自动 kill + 错误报告
      - 所有输出写入日志文件

    返回:
        {
            "returncode": int,
            "working_branch": str,
            "commits_file": str,
            "current_commit_file": str,
        }
    """
    logger.info("[GB Init][Phase2] ── 执行 start_globalbatch ──")
    logger.info("[GB Init][Phase2] worktree_dir: %s", worktree_dir)

    path = os.path.abspath(worktree_dir)
    bd_dir = os.path.join(path, "bd")
    if not os.path.isdir(bd_dir):
        raise RuntimeError(
            f"bd/ 目录不存在: {bd_dir}. "
            f"请确认 worktree 目录 {path} 包含 bd/ 文件夹"
        )

    # ── Step 1: 读取 milestone 信息 ──────────────────────────────────
    milestone_file = os.path.join(bd_dir, "currentmilestone.txt")
    if not os.path.isfile(milestone_file):
        raise RuntimeError(f"currentmilestone.txt 未找到: {milestone_file}")

    with open(milestone_file, "r", encoding="utf-8") as f:
        previous_milestone = f.readline().strip()
        next_milestone = f.readline().strip()

    logger.info("[GB Init][Phase2] previous_milestone: %s", previous_milestone)
    logger.info("[GB Init][Phase2] next_milestone: %s", next_milestone)

    next_milestone = await _update_next_milestone_from_origin(
        milestone_file=milestone_file,
        previous_milestone=previous_milestone,
        next_milestone=next_milestone,
        cwd=path,
    )

    # ── Step 2: Bedrock mode 常量 ────────────────────────────────────
    is_netease = "false"
    mergebase_branch = next_milestone
    global_branch = "main"

    # ── Step 3: 验证远程分支存在 ─────────────────────────────────────
    logger.info("[GB Init][Phase2] 检查远程分支...")
    if not await _is_branch_defined_async(global_branch, path):
        raise RuntimeError(
            f"Global branch '{global_branch}' not found on remote."
        )
    if not await _is_branch_defined_async(mergebase_branch, path):
        raise RuntimeError(
            f"Mergebase branch '{mergebase_branch}' not found on remote."
        )

    netease_branch = "netease/" + global_branch
    pointer_branch = "netease/bd_pointer/" + global_branch
    now = datetime.now()
    working_branch = "netease/globalbatch/" + now.strftime("%m/%d")

    logger.info("[GB Init][Phase2] global_branch:  %s", global_branch)
    logger.info("[GB Init][Phase2] pointer_branch: %s", pointer_branch)
    logger.info("[GB Init][Phase2] working_branch: %s", working_branch)
    logger.info("[GB Init][Phase2] netease_branch: %s", netease_branch)

    # ── Step 4: 生成 milestone-range commit 列表 ────────────────────
    logger.info("[GB Init][Phase2] 生成 milestone-range commit 列表...")

    initial_mergebase = await _run_cmd_stdout(
        ["git", "merge-base", f"origin/{previous_milestone}", f"origin/{global_branch}"],
        cwd=path,
        label="Phase2/merge-base-initial",
        timeout=120,
    )
    logger.info("[GB Init][Phase2] initial_mergebase: %s", initial_mergebase[:16])

    final_mergebase = await _run_cmd_stdout(
        ["git", "merge-base", f"origin/{next_milestone}", f"origin/{global_branch}"],
        cwd=path,
        label="Phase2/merge-base-final",
        timeout=120,
    )
    logger.info("[GB Init][Phase2] final_mergebase: %s", final_mergebase[:16])

    commit_list_raw = await _run_cmd_stdout(
        ["git", "rev-list", "--reverse", "--first-parent",
         f"{initial_mergebase}..{final_mergebase}"],
        cwd=path,
        label="Phase2/rev-list",
        timeout=300,
        quiet=True, # 大概有2000多个commits，打出来太污染日志
    )

    raw_commits = [c.strip() for c in commit_list_raw.split("\n") if c.strip()]
    logger.info("[GB Init][Phase2] rev-list 共 %d 个 commit", len(raw_commits))

    # 检测 revert commit。
    # 次性读取整个 range 的 subject/body，再在 Python 中解析 `This reverts commit ...`。
    logger.info("[GB Init][Phase2] 检测 revert commit (共 %d 个待检查, bulk 模式)...", len(raw_commits))
    reverts: Dict[str, str] = {}
    if raw_commits:
        revert_log_text = await _run_cmd_stdout(
            [
                "git", "log", "--reverse", "--format=%H%x00%B%x00END_COMMIT%x00",
                f"{initial_mergebase}..{final_mergebase}",
            ],
            cwd=path,
            label="Phase2/log-reverts-bulk",
            timeout=300,
            quiet=True,
        )
        current_commit = ""
        current_body: List[str] = []
        parts = revert_log_text.split("\x00")
        idx = 0
        while idx < len(parts):
            token = parts[idx]
            if token == "END_COMMIT":
                for line in "\n".join(current_body).split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("This reverts commit "):
                        commit_reverts = stripped[len("This reverts commit "):].split(".")[0].strip()
                        if len(commit_reverts) >= 40:
                            reverts[commit_reverts[:40]] = current_commit
                current_commit = ""
                current_body = []
                idx += 1
                continue
            if not current_commit:
                current_commit = token.strip()
            else:
                current_body.append(token)
            idx += 1

    logger.info("[GB Init][Phase2] 检测到 %d 个 revert", len(reverts))

    # 构建最终 commit 列表并写入文件
    final_commit_list = ""
    for commit in raw_commits:
        if len(commit) > 1:
            if commit in reverts:
                final_commit_list += f"{commit}|{reverts[commit]}\n"
            else:
                final_commit_list += f"{commit}|NONE\n"

    commits_file = os.path.join(bd_dir, "commits.txt")
    with open(commits_file, "w", encoding="utf-8") as f:
        f.write(final_commit_list)
        f.write("END")
    logger.info("[GB Init][Phase2] ✅ commits.txt 已写入: %s", commits_file)

    # ── Step 4b: 处理 commits_for_merge_commits.txt ──────────────────
    merge_commits_file = os.path.join(bd_dir, "commits_for_merge_commits.txt")
    if os.path.exists(merge_commits_file):
        current_commit_file_tmp = os.path.join(bd_dir, "currentcommit.txt")
        if os.path.isfile(current_commit_file_tmp):
            with open(current_commit_file_tmp, "r", encoding="utf-8") as f:
                current_commit_val = f.readline().strip()

            combine_commit = "83123fe574ec5ad75371dbc639c284bfa6c6d40b"
            test_commit = await _run_cmd_stdout(
                ["git", "merge-base", current_commit_val, combine_commit],
                cwd=path,
                label="Phase2/merge-base-combine",
                timeout=60,
            )

            if test_commit == combine_commit:
                os.remove(merge_commits_file)
                logger.info("[GB Init][Phase2] 已删除 merge_commits_file (combine 已合入)")
            else:
                shutil.copy(merge_commits_file, commits_file)
                logger.info("[GB Init][Phase2] 使用 merge_commits_file 覆盖 commits.txt")

    # ── Step 5: 设置 pointer branch ──────────────────────────────────
    logger.info("[GB Init][Phase2] 设置 pointer branch...")
    POINTER_WORKTREE = "bd_pointer"

    if await _is_branch_defined_async(pointer_branch, path):
        rc = await _run_cmd_rc(
            ["git", "fetch", "origin", pointer_branch],
            cwd=path,
            label="Phase2/fetch-pointer",
            timeout=120,
        )
        if rc != 0:
            logger.warning(
                "[GB Init][Phase2] 无法连接 pointer branch '%s'", pointer_branch
            )
    else:
        # _create_branch_as_clone_in_worktree 内联
        worktree_path = os.path.normpath(os.path.join(path, "..", POINTER_WORKTREE))
        logger.info(
            "[GB Init][Phase2] 创建 pointer worktree: %s, branch: %s",
            worktree_path, pointer_branch,
        )
        await _run_cmd_rc(
            ["git", "worktree", "add", worktree_path],
            cwd=path,
            label="Phase2/worktree-pointer",
            timeout=120,
        )
        await _run_cmd_rc(
            ["git", "branch", "-D", pointer_branch],
            cwd=worktree_path,
            label="Phase2/branch-D-pointer",
            timeout=30,
        )
        # branch 为空, 跳过 checkout source
        await _run_cmd_rc(
            ["git", "checkout", "-b", pointer_branch],
            cwd=worktree_path,
            label="Phase2/checkout-b-pointer",
            timeout=30,
        )

    # ── Step 6: 设置 working branch ──────────────────────────────────
    logger.info("[GB Init][Phase2] 设置 working branch: %s", working_branch)
    if await _is_branch_defined_async(working_branch, path):
        # 检查是否存在远端的同名branch TODO: 应该删除
        raise RuntimeError(
            f"远端存在同名branch '{working_branch}' 请先清理"
        )
    else:
        local_branch_exists = await _run_cmd_rc(
            ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{working_branch}"],
            cwd=path,
            label="Phase2/local-branch-exists-working",
            timeout=30,
            quiet=True,
        ) == 0
        if local_branch_exists:
            logger.warning(
                "[GB Init][Phase2] working branch 远端不存在但本地已存在，直接 checkout: %s",
                working_branch,
            )
            await _run_cmd(
                ["git", "checkout", working_branch],
                cwd=path,
                label="Phase2/checkout-local-working",
                timeout=60,
            )
        else:
            # 都不是，新建workspace
            await _run_cmd(
                ["git", "checkout", "-b", working_branch],
                cwd=path,
                label="Phase2/checkout-b-working",
                timeout=60,
            )

    # ── Step 7: 写入 branchState.txt ─────────────────────────────────
    branch_state_file = os.path.join(bd_dir, "branchState.txt")
    with open(branch_state_file, "w", encoding="utf-8") as f:
        f.write(
            f"{global_branch}\n"
            f"{pointer_branch}\n"
            f"{working_branch}\n"
            f"{netease_branch}\n"
            f"{is_netease}"
        )
    logger.info("[GB Init][Phase2] ✅ branchState.txt 已写入: %s", branch_state_file)

    # ── 验证产出文件 ─────────────────────────────────────────────────
    current_commit_file = os.path.join(bd_dir, "currentCommit.txt")
    if not os.path.isfile(current_commit_file):
        current_commit_file = os.path.join(bd_dir, "currentcommit.txt")
    if not os.path.isfile(current_commit_file):
        raise RuntimeError(
            f"currentCommit.txt 不存在: {bd_dir}. "
            f"start_globalbatch 可能未正确执行"
        )
    if not os.path.isfile(commits_file):
        raise RuntimeError(
            f"commits.txt 不存在: {commits_file}. "
            f"start_globalbatch 可能未正确执行"
        )

    # 存档 commits.txt 到 workspace temp 目录
    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        backup_path = os.path.join(temp_dir, "commits.txt")
        shutil.copy(commits_file, backup_path)
        logger.info("[GB Init][Phase2] ✅ commits.txt 已存档到: %s", backup_path)

    logger.info("[GB Init][Phase2] ── start_globalbatch 完成 ──")
    return {
        "returncode": 0,
        "working_branch": working_branch,
        "commits_file": commits_file,
        "current_commit_file": current_commit_file,
    }


# ── 核心初始化函数 ────────────────────────────────────────────────


async def init_globalbatch(
    db,
    scheduler,
    workspace_id: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """执行 GlobalBatch 初始化流程。

    Args:
        db: DatabaseCompat 实例
        scheduler: TaskScheduler 实例
        workspace_id: Workspace ID
        config: 初始化配置, 包含:
            - predecessor_branch: str, 上一轮分支 (Real 模式必填；Mock 模式默认 mock/predecessor)
            - subbatch_size: int (默认 50)
            - subbatch_count: int (默认 4)
            - mock: bool (默认 True, 测试模式)
            - workspace_root: str (非 Mock 时需要)
            - github_repo: str (非 Mock 时需要)
            - github_branch: str (非 Mock 时需要)

    Returns:
        {"batch_id": str, "subbatches": [...], "total_commits": int, ...}
    """
    mock = config.get("mock", True)
    mock_init_workspace = bool(config.get("mock_init_workspace"))
    predecessor_branch = str(config.get("predecessor_branch") or "").strip()
    if not predecessor_branch:
        if mock:
            predecessor_branch = "mock/predecessor"
        else:
            raise ValueError(
                "Real 模式需要显式配置 predecessor_branch "
                "(Dashboard 参数或 bot.yaml → globalbatch → predecessor_branch)"
            )
    unsupported_branch_keys = [
        key for key in ("base_branch",)
        if key in config
    ]
    if unsupported_branch_keys:
        raise ValueError(
            "init_globalbatch 只接受 predecessor_branch 作为 Batch 前序分支；"
            f"不接受参数: {', '.join(unsupported_branch_keys)}"
        )
    subbatch_size = int(config.get("subbatch_size", 10))
    subbatch_count = int(config.get("subbatch_count", 4))

    now = datetime.now()
    date_str = now.strftime("%m/%d")
    date_id = now.strftime("%m%d")

    logger.info(
        "[GB Init] ═══════════════════════════════════════════════════",
    )
    logger.info(
        "[GB Init] 开始初始化 GlobalBatch: predecessor=%s, size=%d, count=%d, mock=%s, mock_init_workspace=%s",
        predecessor_branch, subbatch_size, subbatch_count, mock, mock_init_workspace,
    )

    # ── Phase 1 & 2: 环境准备 + start_globalbatch ────────────────
    if mock:
        # Mock 模式: 生成模拟数据
        total_commits = subbatch_size * subbatch_count
        all_commits = _generate_mock_commits(total_commits)
        current_commit = all_commits[0]
        working_branch = f"netease/globalbatch/{date_str}"
        work_dir = f"mock://globalbatch_ai/{now.strftime('%Y%m%d')}_mcpe/mcpe_gb"

        logger.info(
            "[GB Init][Mock] 生成 %d 个模拟 commit, 工作分支: %s",
            total_commits, working_branch,
        )
    else:
        # ── Real 模式 ────────────────────────────────────────────
        workspace_root = config.get("workspace_root", "")
        github_repo = config.get("github_repo", "https://github.com/Mojang/Minecraftpe/")
        github_branch = config.get("github_branch", "main")

        if not workspace_root:
            raise ValueError(
                "Real 模式需要配置 workspace_root (在 bot.yaml → globalbatch → workspace_root)"
            )

        logger.info("[GB Init][Real] workspace_root: %s", workspace_root)
        logger.info("[GB Init][Real] github_repo: %s", github_repo)
        logger.info("[GB Init][Real] github_branch: %s", github_branch)
        logger.info("[GB Init][Real] predecessor_branch: %s", predecessor_branch)

        if mock_init_workspace:
            logger.info("[GB Init][Real] Init Workspace 节点配置为 mock，复用已有 workspace，跳过 git/start_globalbatch")
            mock_init_result = await _mock_init_workspace(
                workspace_root=workspace_root,
                github_repo=github_repo,
                github_branch=github_branch,
                predecessor_branch=predecessor_branch,
                subbatch_size=subbatch_size,
                subbatch_count=subbatch_count,
            )
            env_info = mock_init_result["env_info"]
            work_dir = mock_init_result["work_dir"]
            working_branch = mock_init_result["working_branch"]
            all_commits = mock_init_result["all_commits"]
            current_commit = mock_init_result["current_commit"]
        else:
            # Phase 1: 环境准备
            logger.info("[GB Init][Real] ── Phase 1: 环境准备 ──")
            env_info = await _phase1_prepare_environment(
                workspace_root=workspace_root,
                github_repo=github_repo,
                github_branch=github_branch,
                predecessor_branch=predecessor_branch,
            )

            work_dir = env_info["worktree_dir"]

            # Phase 2: 执行 start_globalbatch
            logger.info("[GB Init][Real] ── Phase 2: 执行 start_globalbatch ──")
            sg_result = await _phase2_start_globalbatch(
                worktree_dir=work_dir,
                temp_dir=env_info.get("temp_dir", ""),
            )

            working_branch = sg_result["working_branch"]
            commits_file = sg_result["commits_file"]
            current_commit_file = sg_result["current_commit_file"]

            # Phase 3 (前置): 解析产出文件
            logger.info("[GB Init][Real] ── Phase 3: 解析 commits.txt ──")
            all_commits = parse_commits_file(commits_file)
            current_commit = read_current_commit(current_commit_file)

            logger.info(
                "[GB Init][Real] 读取到 %d 个 commit, currentCommit=%s",
                len(all_commits),
                current_commit[:16] if current_commit else "None",
            )

            if not all_commits:
                raise RuntimeError(
                    f"commits.txt 为空或解析失败: {commits_file}"
                )

    # ── Phase 3: 任务分配 ────────────────────────────────────────
    logger.info("[GB Init] ── Phase 3: 任务分配 ──")
    subbatch_plan = plan_subbatches(
        all_commits=all_commits,
        current_commit=current_commit,
        subbatch_size=subbatch_size,
        subbatch_count=subbatch_count,
    )

    if not subbatch_plan:
        return {"error": "No subbatches planned (empty commit list?)"}

    # 汇总 commit 列表 (用于 Batch 记录)
    batch_commits: List[str] = []
    for sb in subbatch_plan:
        batch_commits.extend(sb["commits"])

    logger.info(
        "[GB Init] SubBatch 分配: %s",
        ", ".join(
            f"_{sb['suffix']}({sb['count']} commits: {sb['start_commit'][:8]}..{sb['end_commit'][:8]})"
            for sb in subbatch_plan
        ),
    )

    # 创建 Batch
    date_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    batch_id = f"globalbatch_{date_id}"
    workspace_paths: Dict[str, str] = {}
    if not mock:
        workspace_paths = {
            "batch_workspace_dir": env_info.get("work_dir", ""),
            "repo_dir": env_info.get("clone_dir", ""),
            "mcpe_main_dir": env_info.get("main_worktree_dir", ""),
            "mcpe_prev_batch_dir": env_info.get("prev_worktree_dir", ""),
            "mcpe_gb_dir": env_info.get("worktree_dir", ""),
            "temp_dir": env_info.get("temp_dir", ""),
            "logs_dir": env_info.get("logs_dir", ""),
        }

    subbatch_worktree_paths: Dict[str, str] = {}
    if not mock and workspace_paths.get("batch_workspace_dir"):
        wm = WorkspaceManager(_run_cmd, _run_cmd_stdout, _run_cmd_rc)
        subbatch_worktree_paths = wm.plan_subbatch_worktree_paths(
            batch_workspace_dir=workspace_paths["batch_workspace_dir"],
            subbatch_count=len(subbatch_plan),
        )

    batch = make_batch(
        workspace_id=workspace_id,
        batch_type="global",
        commits=batch_commits,
        predecessor_branch=predecessor_branch,
        config={
            "pipeline_id": "globalbatch_init",
            "pipeline_name": "GlobalBatch Init",
            "sub_batch_size": subbatch_size,
            "subbatch_count": subbatch_count,
            "predecessor_branch": predecessor_branch,
            "subbatch_base_branch_semantics": "per-subbatch previous branch; do not use as mcpe_prev_batch source",
            "working_branch": working_branch,
            "work_dir": work_dir if work_dir else "",
            "workspace_paths": workspace_paths,
            "subbatch_worktree_paths": subbatch_worktree_paths,
            "mock": mock,
            "mock_init_workspace": mock_init_workspace,
            "mock_task_types": list(config.get("mock_task_types") or []),
        },
        batch_id=batch_id,
    )
    await db.upsert_batch(batch)
    logger.info("[GB Init] ✅ Batch 已创建: %s", batch_id)

    # 调度: 创建 SubBatch + Task DAG
    subbatch_overrides: List[Dict[str, Any]] = []
    for idx, sb in enumerate(subbatch_plan):
        branch_name = f"netease/globalbatch/{date_str}_{sb['suffix']}"
        subbatch_base_branch = predecessor_branch if idx == 0 else f"netease/globalbatch/{date_str}_{subbatch_plan[idx - 1]['suffix']}"
        worktree_path = subbatch_worktree_paths.get(sb["suffix"])
        subbatch_overrides.append({
            "branch_name": branch_name,
            # SubBatch 级 subbatch_base_branch 仅表示该 SubBatch pick/rebase 的直接前置分支；
            # 整个 Batch 的前序 GlobalBatch 始终是 predecessor_branch。
            "subbatch_base_branch": subbatch_base_branch,
            "commits": sb["commits"],
            "worktree_path": worktree_path,
        })

    tasks = await scheduler.schedule_batch(batch, subbatch_overrides=subbatch_overrides)

    if not mock and subbatch_overrides:
        # SubBatch worktree 不在初始化阶段提前创建。
        # Branch Dance 必须始终在 mcpe_gb 内连续推进，以保证 bd/currentcommit.txt、bd/commits.txt
        # 和 ../temp/agent_session.json 是同一套共享状态。每个 SubBatch 的 _a/_b/_c 快照
        # 会在对应 pick task 成功后从 mcpe_gb 当前 HEAD 物化出来。
        batch["config"]["subbatch_worktree_health"] = {}
        await db.upsert_batch(batch)
        logger.info(
            "[GB Init][Real] SubBatch worktree 将在 pick 完成后从 mcpe_gb 物化: %d",
            len(subbatch_overrides),
        )

    logger.info(
        "[GB Init] ═══════════════════════════════════════════════════",
    )
    logger.info(
        "[GB Init] ✅ 初始化完成: batch=%s, subbatches=%d, tasks=%d, commits=%d",
        batch_id, len(subbatch_plan), len(tasks), len(batch_commits),
    )
    logger.info(
        "[GB Init] ═══════════════════════════════════════════════════",
    )

    # 构建返回结果
    subbatch_summary = []
    for sb in subbatch_plan:
        subbatch_summary.append({
            "suffix": sb["suffix"],
            "branch": f"netease/globalbatch/{date_str}_{sb['suffix']}",
            "worktree_path": subbatch_worktree_paths.get(sb["suffix"], ""),
            "commit_count": sb["count"],
            "start_commit": sb["start_commit"][:12],
            "end_commit": sb["end_commit"][:12],
        })

    return {
        "batch_id": batch_id,
        "working_branch": working_branch,
        "predecessor_branch": predecessor_branch,
        "total_commits": len(batch_commits),
        "subbatch_count": len(subbatch_plan),
        "subbatch_size": subbatch_size,
        "subbatches": subbatch_summary,
        "tasks_created": len(tasks),
        "mock": mock,
        "mock_init_workspace": mock_init_workspace,
        "work_dir": work_dir if not mock else "",
        "workspace_paths": workspace_paths,
    }


# ── 两阶段初始化 (Phase 0 + Phase 1/2/3) ────────────────────────


async def create_init_batch(
    db,
    scheduler,
    workspace_id: str,
    config: Dict[str, Any],
) -> tuple[dict, dict]:
    """Phase 0: 立即创建 Batch 和 init_workspace 节点，不做任何 git 操作。

    前端可以立即看到 Pipeline DAG（仅含 init_workspace 一个节点）。

    Args:
        db: DatabaseCompat 实例
        scheduler: TaskScheduler 实例
        workspace_id: Workspace ID
        config: 初始化配置 (与 init_globalbatch 相同)

    Returns:
        (batch, init_workspace_task) — batch 已持久化，init_workspace_task 已入队为 QUEUED。
    """
    mock = config.get("mock", True)
    mock_init_workspace = bool(config.get("mock_init_workspace"))
    predecessor_branch = str(config.get("predecessor_branch") or "").strip()
    if not predecessor_branch:
        if mock:
            predecessor_branch = "mock/predecessor"
        else:
            raise ValueError(
                "Real 模式需要显式配置 predecessor_branch "
                "(Dashboard 参数或 bot.yaml → globalbatch → predecessor_branch)"
            )
    subbatch_size = int(config.get("subbatch_size", 10))
    subbatch_count = int(config.get("subbatch_count", 4))

    now = datetime.now()
    date_id = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]
    batch_id = f"globalbatch_{date_id}"

    logger.info(
        "[GB Init][Phase0] 创建 Batch: %s, predecessor=%s, size=%d, count=%d, mock=%s, mock_init=%s",
        batch_id, predecessor_branch, subbatch_size, subbatch_count, mock, mock_init_workspace,
    )

    # 创建最小 Batch — 此时还没有 real commits，用空列表占位
    batch = make_batch(
        workspace_id=workspace_id,
        batch_type="global",
        commits=[],
        predecessor_branch=predecessor_branch,
        config={
            "pipeline_id": "globalbatch_init",
            "pipeline_name": "GlobalBatch Init",
            "sub_batch_size": subbatch_size,
            "subbatch_count": subbatch_count,
            "predecessor_branch": predecessor_branch,
            "mock": mock,
            "mock_init_workspace": mock_init_workspace,
            "mock_task_types": list(config.get("mock_task_types") or []),
            "_phase": "init_workspace_pending",
            "_config_raw": config,  # 暂存原始 config，供 execute_init 使用
        },
        batch_id=batch_id,
    )
    await db.upsert_batch(batch)

    # 创建一个虚拟 SubBatch 用于承载 init_workspace 任务。
    # 使用负数 index_num 避免与 schedule_batch 创建的真实 SubBatch 冲突
    # （sub_batches 表有 UNIQUE(batch_id, index_num) 约束）。
    placeholder_sb_id = new_id()
    placeholder_sb = make_sub_batch(
        batch_id=batch_id,
        index=-1,
        branch_name="",
        subbatch_base_branch=predecessor_branch,
        commits=[],
    )
    placeholder_sb["id"] = placeholder_sb_id
    placeholder_sb["index_num"] = -1
    placeholder_sb["batch_predecessor_branch"] = predecessor_branch
    await db.upsert_sub_batch(placeholder_sb)

    # 创建唯一入口任务: init_workspace
    init_workspace = make_task(
        placeholder_sb_id,
        TaskType.INIT_WORKSPACE.value,
        0,
        priority=5,
        timeout_seconds=TaskTimeoutConfig.INIT_WORKSPACE,
        payload={
            "batch_id": batch_id,
            "task_type": TaskType.INIT_WORKSPACE.value,
            "predecessor_branch": predecessor_branch,
        },
    )
    all_tasks = [init_workspace]

    # 持久化 + 入队
    for t in all_tasks:
        await db.upsert_task(t)

    await db.update_batch_status(batch_id, BatchStatus.RUNNING.value, started_at=now_iso())

    ready = get_ready_tasks(all_tasks)
    for t in ready:
        t["status"] = TaskStatus.QUEUED.value
        t["queued_at"] = now_iso()
        await db.upsert_task(t)

    # 刷新 batch 引用以反映 DB 中的最新数据
    batch = await db.get_batch(batch_id)

    logger.info(
        "[GB Init][Phase0] ✅ Batch %s 就绪: init_workspace=%s (status=%s, queued=%d)",
        batch_id, init_workspace["id"][:8], init_workspace.get("status", "?"), len(ready),
    )
    return batch, init_workspace


async def execute_init(
    db,
    scheduler,
    batch: dict,
    task: dict,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Phase 1/2/3: 在 task runner 中执行 init_workspace 节点的真正工作。

    执行 git clone/fetch/worktree/start_globalbatch → 解析 commits →
    规划 SubBatch → 创建剩余 DAG 任务。

    调用方 (task runner) 需要在 invoke 后:
      - 调用 scheduler.on_task_completed(task_id, success=True, result=result)
      - 或者 success=False 时 block 节点

    Returns:
        {"batch_id": str, "subbatches": [...], "total_commits": int, "tasks_created": int, ...}
        或 {"error": str}
    """
    batch_id = batch["id"]
    batch_config = batch.get("config") or {}
    mock = batch_config.get("mock", True)
    mock_init_workspace = bool(batch_config.get("mock_init_workspace"))
    predecessor_branch = str(batch_config.get("predecessor_branch") or "").strip()
    subbatch_size = int(batch_config.get("sub_batch_size", 10))
    subbatch_count = int(batch_config.get("subbatch_count", 4))

    # 从 _config_raw 补充可能缺失的字段
    raw_config = batch_config.get("_config_raw", config)
    if not mock:
        config.setdefault("workspace_root", raw_config.get("workspace_root", ""))
        config.setdefault("github_repo", raw_config.get("github_repo", "https://github.com/Mojang/Minecraftpe/"))
        config.setdefault("github_branch", raw_config.get("github_branch", "main"))

    now = datetime.now()
    date_str = now.strftime("%m/%d")

    logger.info(
        "[GB Init][Phase1-3] ── 执行 init_workspace 真实工作: batch=%s, mock=%s, mock_init=%s",
        batch_id, mock, mock_init_workspace,
    )

    # ── Phase 1 & 2: 环境准备 + start_globalbatch ────────────────
    if mock:
        total_commits = subbatch_size * subbatch_count
        all_commits = _generate_mock_commits(total_commits)
        current_commit = all_commits[0]
        working_branch = f"netease/globalbatch/{date_str}"
        work_dir = f"mock://globalbatch_ai/{now.strftime('%Y%m%d')}_mcpe/mcpe_gb"
        env_info = {}
        logger.info(
            "[GB Init][Mock] 生成 %d 个模拟 commit, 工作分支: %s",
            total_commits, working_branch,
        )
    else:
        workspace_root = config.get("workspace_root", "")
        github_repo = config.get("github_repo", "https://github.com/Mojang/Minecraftpe/")
        github_branch = config.get("github_branch", "main")

        if not workspace_root:
            raise ValueError(
                "Real 模式需要配置 workspace_root (在 bot.yaml → globalbatch → workspace_root)"
            )

        if mock_init_workspace:
            logger.info("[GB Init][Real] Init Workspace mocked，复用已有 workspace")
            mock_init_result = await _mock_init_workspace(
                workspace_root=workspace_root,
                github_repo=github_repo,
                github_branch=github_branch,
                predecessor_branch=predecessor_branch,
                subbatch_size=subbatch_size,
                subbatch_count=subbatch_count,
            )
            env_info = mock_init_result["env_info"]
            work_dir = mock_init_result["work_dir"]
            working_branch = mock_init_result["working_branch"]
            all_commits = mock_init_result["all_commits"]
            current_commit = mock_init_result["current_commit"]
        else:
            logger.info("[GB Init][Real] ── Phase 1: 环境准备 ──")
            env_info = await _phase1_prepare_environment(
                workspace_root=workspace_root,
                github_repo=github_repo,
                github_branch=github_branch,
                predecessor_branch=predecessor_branch,
            )
            work_dir = env_info["worktree_dir"]

            logger.info("[GB Init][Real] ── Phase 2: 执行 start_globalbatch ──")
            sg_result = await _phase2_start_globalbatch(
                worktree_dir=work_dir,
                temp_dir=env_info.get("temp_dir", ""),
            )
            working_branch = sg_result["working_branch"]
            commits_file = sg_result["commits_file"]
            current_commit_file = sg_result["current_commit_file"]

            logger.info("[GB Init][Real] ── 解析 commits.txt ──")
            all_commits = parse_commits_file(commits_file)
            current_commit = read_current_commit(current_commit_file)

            if not all_commits:
                raise RuntimeError(f"commits.txt 为空或解析失败: {commits_file}")

    # ── Phase 3: 任务分配 ────────────────────────────────────────
    logger.info("[GB Init] ── Phase 3: SubBatch 规划 ──")
    subbatch_plan = plan_subbatches(
        all_commits=all_commits,
        current_commit=current_commit,
        subbatch_size=subbatch_size,
        subbatch_count=subbatch_count,
    )

    if not subbatch_plan:
        return {"error": "No subbatches planned (empty commit list?)"}

    batch_commits: List[str] = []
    for sb in subbatch_plan:
        batch_commits.extend(sb["commits"])

    logger.info(
        "[GB Init] SubBatch 分配: %s",
        ", ".join(
            f"_{sb['suffix']}({sb['count']} commits: {sb['start_commit'][:8]}..{sb['end_commit'][:8]})"
            for sb in subbatch_plan
        ),
    )

    # 更新 Batch config（替换空 commits 为真实 commits，更新路径信息）
    workspace_paths: Dict[str, str] = {}
    if not mock:
        workspace_paths = {
            "batch_workspace_dir": env_info.get("work_dir", ""),
            "repo_dir": env_info.get("clone_dir", ""),
            "mcpe_main_dir": env_info.get("main_worktree_dir", ""),
            "mcpe_prev_batch_dir": env_info.get("prev_worktree_dir", ""),
            "mcpe_gb_dir": env_info.get("worktree_dir", ""),
            "temp_dir": env_info.get("temp_dir", ""),
            "logs_dir": env_info.get("logs_dir", ""),
        }

    subbatch_worktree_paths: Dict[str, str] = {}
    if not mock and workspace_paths.get("batch_workspace_dir"):
        wm = WorkspaceManager(_run_cmd, _run_cmd_stdout, _run_cmd_rc)
        subbatch_worktree_paths = wm.plan_subbatch_worktree_paths(
            batch_workspace_dir=workspace_paths["batch_workspace_dir"],
            subbatch_count=len(subbatch_plan),
        )

    updated_config = {
        **{k: v for k, v in batch_config.items() if k not in ("_config_raw", "_phase")},
        "working_branch": working_branch,
        "work_dir": work_dir or "",
        "workspace_paths": workspace_paths,
        "subbatch_worktree_paths": subbatch_worktree_paths,
        "subbatch_base_branch_semantics": "per-subbatch previous branch; do not use as mcpe_prev_batch source",
    }
    batch["commits"] = batch_commits
    batch["config"] = updated_config
    await db.upsert_batch(batch)

    # 更新 Batch config → 创建真正的 SubBatch + DAG。
    # 复用已有 init_workspace task ID 以便 DAG 中 pick_a 正确依赖它。
    subbatch_overrides: List[Dict[str, Any]] = []
    for idx, sb in enumerate(subbatch_plan):
        branch_name = f"netease/globalbatch/{date_str}_{sb['suffix']}"
        subbatch_base_branch = predecessor_branch if idx == 0 else f"netease/globalbatch/{date_str}_{subbatch_plan[idx - 1]['suffix']}"
        worktree_path = subbatch_worktree_paths.get(sb["suffix"])
        subbatch_overrides.append({
            "branch_name": branch_name,
            "subbatch_base_branch": subbatch_base_branch,
            "commits": sb["commits"],
            "worktree_path": worktree_path,
        })

    tasks = await scheduler.schedule_batch(
        batch, subbatch_overrides=subbatch_overrides, init_task_id=task["id"],
    )

    if not mock and subbatch_overrides:
        batch["config"]["subbatch_worktree_health"] = {}
        await db.upsert_batch(batch)

    logger.info("[GB Init] ✅ init_workspace 完成: tasks=%d, commits=%d", len(tasks), len(batch_commits))

    # 构建返回结果
    subbatch_summary = []
    for sb in subbatch_plan:
        subbatch_summary.append({
            "suffix": sb["suffix"],
            "branch": f"netease/globalbatch/{date_str}_{sb['suffix']}",
            "worktree_path": subbatch_worktree_paths.get(sb["suffix"], ""),
            "commit_count": sb["count"],
            "start_commit": sb["start_commit"][:12],
            "end_commit": sb["end_commit"][:12],
        })

    return {
        "batch_id": batch_id,
        "working_branch": working_branch,
        "predecessor_branch": predecessor_branch,
        "total_commits": len(batch_commits),
        "subbatch_count": len(subbatch_plan),
        "subbatch_size": subbatch_size,
        "subbatches": subbatch_summary,
        "tasks_created": len(tasks),
        "mock": mock,
        "mock_init_workspace": mock_init_workspace,
        "work_dir": work_dir if not mock else "",
        "workspace_paths": workspace_paths,
    }

