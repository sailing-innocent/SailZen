"""Build Win task handler：batch-fixbuild-windows skill 前处理与 prompt 构造。

负责：
- 通过 WorkspaceManager 确保 buildfix worktree 存在
- 计算 buildfix_branch、buildfix_worktree_path
- 构造 build_win 约束 prompt（branch_name 必须是 buildfix 分支）
- 返回 (working_dir, prompt, extra_result)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

HandlerResult = Tuple[str, str, Dict[str, Any]]


def _make_subprocess_runners():
    async def _run_cmd_passthrough(cmd, cwd, label, timeout=3600, quiet=False):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(
                f"{label} failed rc={proc.returncode}: {stderr.decode(errors='ignore') or stdout.decode(errors='ignore')}"
            )
        return proc

    async def _run_cmd_rc_passthrough(cmd, cwd, label, timeout=3600, quiet=False):
        try:
            await _run_cmd_passthrough(cmd, cwd, label, timeout, quiet)
            return 0
        except Exception:
            return 1

    async def _run_cmd_stdout_passthrough(cmd, cwd, label, timeout=3600, quiet=False):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(f"{label} failed: {stderr.decode(errors='ignore')}")
        return stdout.decode(errors="ignore").strip()

    return _run_cmd_passthrough, _run_cmd_stdout_passthrough, _run_cmd_rc_passthrough


def build_task_state_paths(temp_dir: str, task: dict, *, prefix: str) -> Dict[str, str]:
    """Return task-scoped buildfix state/output paths."""
    sub_batch_id = task.get("sub_batch_id", "")
    subbatch_suffix = sub_batch_id.split("_")[-1] if sub_batch_id else "global"
    task_id = str(task.get("id") or "")
    task_suffix = task_id[:8] or "unknown"
    build_root = Path(temp_dir) / ".build" if temp_dir else Path("../temp/.build")
    build_state_dir = build_root / f"{prefix}_{subbatch_suffix}_{task_suffix}"
    return {
        "build_state_dir": str(build_state_dir),
        "build_rounds_dir": str(build_state_dir / "rounds"),
        "build_temp_root": str(build_state_dir),
        "fix_notes_path": str(build_state_dir / "fix_notes.md"),
        "fix_state_path": str(build_state_dir / "fix_state.json"),
    }


async def ensure_buildfix_worktree(
    *,
    workspace_paths: Dict[str, str],
    sub_batch: dict,
    working_dir: str,
) -> Dict[str, Any]:
    """Ensure buildfix worktree when repo_dir is available."""
    repo_dir = workspace_paths.get("repo_dir", "")
    if not (repo_dir and working_dir):
        return {}

    from bot_server.service.workspace_manager import WorkspaceManager
    wm = WorkspaceManager(*_make_subprocess_runners())
    return await wm.ensure_buildfix_worktree(
        repo_dir=repo_dir,
        sub_batch=sub_batch,
    )


async def handle(
    *,
    task: dict,
    sub_batch: dict,
    batch_config: dict,
    spec: Dict[str, Any],
    workspace_paths: Dict[str, str],
    temp_dir: str,
    session_result_path: str,
) -> HandlerResult:
    """Build Win 任务前处理。

    Returns:
        (working_dir, prompt, extra_result)
    """
    payload = task.get("payload") or {}
    sub_batch_id = task.get("sub_batch_id", "")
    subbatch_suffix = sub_batch_id.split("_")[-1] if sub_batch_id else "global"
    task_id = str(task.get("id") or "")
    task_suffix = task_id[:8] or "unknown"
    working_dir = sub_batch.get("worktree_path") or payload.get("worktree_path", "")

    paths = build_task_state_paths(temp_dir, task, prefix="build_win")

    extra_result: Dict[str, Any] = {
        "branch_name": sub_batch.get("branch_name", ""),
        "commit_count": len(sub_batch.get("commits", [])),
        **paths,
    }
    if session_result_path:
        extra_result["session_result_path"] = session_result_path

    buildfix = await ensure_buildfix_worktree(
        workspace_paths=workspace_paths,
        sub_batch=sub_batch,
        working_dir=working_dir,
    )
    if buildfix:
        working_dir = buildfix["buildfix_worktree_path"]
        extra_result.update({
            "buildfix_branch": buildfix["buildfix_branch"],
            "branch_name": buildfix["buildfix_branch"],
            "source_branch": sub_batch.get("branch_name", ""),
            "buildfix_worktree_path": buildfix["buildfix_worktree_path"],
            "worktree_health": buildfix,
        })

    base_prompt = spec["prompt"]
    path_contract = (
        "\n\n## CubeClaw buildfix state/output isolation (CRITICAL)\n"
        f"本任务是 SubBatch `_{subbatch_suffix}` 的 Windows buildfix，task_id=`{task.get('id', '')}`。\n"
        "所有 buildfix 状态、轮次日志、修复记录都必须使用下面的任务专属路径；"
        "严禁读取或写入共享 `../temp/.build/fix_notes.md`、`../temp/.build/fix_state.json` 作为本任务状态。\n"
        f"- build_state_dir: `{paths['build_state_dir']}`\n"
        f"- build_temp_root / auto_build_win.ps1 -TempRoot: `{paths['build_temp_root']}`\n"
        f"- build_rounds_dir: `{paths['build_rounds_dir']}`\n"
        f"- fix_notes_path: `{paths['fix_notes_path']}`\n"
        f"- fix_state_path: `{paths['fix_state_path']}`\n"
        "共享 `../temp/.build` 只允许在没有 orchestration 路径的手动场景作为 fallback；本 DAG 任务禁止读写共享 fix_state/fix_notes。\n"
        "轮次规则：每次 gen/submodule/build 必须递增 round 序号，并把该轮原始日志/摘要归档到 "
        "`build_rounds_dir/round_<N>/`；`fix_state_path` 的 rounds 数组必须记录每轮 build_hash、summary_path、error_count、clusters、subagent 结果和 progress。\n"
        "编译命令仍必须使用 auto_build_win.ps1，但 `-TempRoot` 必须指向上述 `build_temp_root`，例如：\n"
        f"`powershell -ExecutionPolicy Bypass -File ~/.agents/skills/batch-fixbuild-windows/scripts/auto_build_win.ps1 -BuildDir \"./build/win32_ogl_x64_netease\" -Config \"Release\" -TempRoot \"{paths['build_temp_root']}\"`\n"
        "最终 session_result.json 必须写入 `fix_state_path`、`fix_notes_path`、`build_state_dir` 和最新轮次 `latest_build_summary`。\n"
    )
    base_prompt = f"{path_contract}{base_prompt}"
    if extra_result.get("buildfix_branch"):
        buildfix_branch = extra_result["buildfix_branch"]
        buildfix_worktree = extra_result.get("buildfix_worktree_path", working_dir)
        source_branch = extra_result.get("source_branch", "")
        base_prompt = (
            f"本任务是 Windows buildfix，必须在 buildfix 分支 `{buildfix_branch}` "
            f"和 buildfix worktree `{buildfix_worktree}` 中完成。"
            f"最终 session_result.json 中 `branch_name` 必须是 buildfix 分支 `{buildfix_branch}`，"
            f"`buildfix_branch` 也必须是 `{buildfix_branch}`；"
            f"原始 SubBatch 分支 `{source_branch}` 只能作为 source_branch/merge-back 目标，"
            f"不要把它写成 branch_name。{base_prompt}"
        )

    return working_dir, base_prompt, extra_result
