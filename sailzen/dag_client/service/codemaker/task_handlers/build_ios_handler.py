"""Build iOS task handler：batch-fixbuild-ios skill 前处理与 prompt 构造。

负责：
- 通过 WorkspaceManager 确保 buildfix worktree 存在
- 计算 buildfix_branch、buildfix_worktree_path
- 为 iOS buildfix 生成任务专属 build_state_dir / fix_state_path / fix_notes_path
- 构造 build_ios 约束 prompt（branch_name 必须是 buildfix 分支）
- 返回 (working_dir, prompt, extra_result)
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from .build_win_handler import build_task_state_paths, ensure_buildfix_worktree

HandlerResult = Tuple[str, str, Dict[str, Any]]


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
    """Build iOS 任务前处理。

    Returns:
        (working_dir, prompt, extra_result)
    """
    payload = task.get("payload") or {}
    sub_batch_id = task.get("sub_batch_id", "")
    subbatch_suffix = sub_batch_id.split("_")[-1] if sub_batch_id else "global"
    working_dir = sub_batch.get("worktree_path") or payload.get("worktree_path", "")

    paths = build_task_state_paths(temp_dir, task, prefix="build_ios")
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
        "\n\n## CubeClaw iOS buildfix state/output isolation (CRITICAL)\n"
        f"本任务是 SubBatch `_{subbatch_suffix}` 的 iOS buildfix，task_id=`{task.get('id', '')}`。\n"
        "所有 iOS buildfix 状态、轮次日志、修复记录都必须使用下面的任务专属路径；"
        "严禁读取或写入共享 `../temp/.build/fix_notes.md`、`../temp/.build/fix_state.json` 作为本任务状态。\n"
        f"- build_state_dir: `{paths['build_state_dir']}`\n"
        f"- build_temp_root / ios_build.sh --temp-root: `{paths['build_temp_root']}`\n"
        f"- build_rounds_dir: `{paths['build_rounds_dir']}`\n"
        f"- fix_notes_path: `{paths['fix_notes_path']}`\n"
        f"- fix_state_path: `{paths['fix_state_path']}`\n"
        "共享 `../temp/.build` 只允许在没有 orchestration 路径的手动场景作为 fallback；本 DAG 任务禁止读写共享 fix_state/fix_notes。\n"
        "轮次规则：每次 submodule/gen/ios_after_build/build 必须递增 round 序号，并把该轮原始日志/摘要归档到 "
        "`build_rounds_dir/round_<N>/`；`fix_state_path` 的 rounds 数组必须记录每轮 build_hash、result_json、summary_path、error_context、error_count、clusters、subagent 结果和 progress。\n"
        "编译命令仍必须使用 ios_build.sh，但 `--temp-root` 必须指向上述 `build_temp_root`，例如：\n"
        f"`bash ~/.agents/skills/batch-fixbuild-ios/scripts/ios_build.sh build/ios_ogl_arm64_netease/minecraftpe.xcodeproj --temp-root \"{paths['build_temp_root']}\"`\n"
        "最终 session_result.json 必须写入 `fix_state_path`、`fix_notes_path`、`build_state_dir`、最新轮次 `latest_build_summary` 和 `latest_build_result_json`。\n"
    )
    base_prompt = f"{path_contract}{base_prompt}"

    if extra_result.get("buildfix_branch"):
        buildfix_branch = extra_result["buildfix_branch"]
        buildfix_worktree = extra_result.get("buildfix_worktree_path", working_dir)
        source_branch = extra_result.get("source_branch", "")
        base_prompt = (
            f"本任务是 iOS buildfix，必须在 buildfix 分支 `{buildfix_branch}` "
            f"和 buildfix worktree `{buildfix_worktree}` 中完成。"
            f"最终 session_result.json 中 `branch_name` 必须是 buildfix 分支 `{buildfix_branch}`，"
            f"`buildfix_branch` 也必须是 `{buildfix_branch}`；"
            f"原始 SubBatch 分支 `{source_branch}` 只能作为 source_branch/merge-back 目标，"
            f"不要把它写成 branch_name。{base_prompt}"
        )

    return working_dir, base_prompt, extra_result
