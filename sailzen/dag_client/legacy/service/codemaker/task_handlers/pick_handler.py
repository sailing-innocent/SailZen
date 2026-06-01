"""Pick task handler：branch-dance skill 前处理与 prompt 构造。

负责：
- 从 sub_batch 提取 commits（start/end）
- 计算 working_branch、snapshot_branch、branch_dance_state_dir
- 构造 pick 任务专属 prompt 前缀（防止切错分支等约束）
- 返回 (working_dir, prompt, extra_result)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

# 返回类型：(working_dir, prompt, extra_result)
HandlerResult = Tuple[str, str, Dict[str, Any]]


def handle(
    *,
    task: dict,
    sub_batch: dict,
    batch_config: dict,
    spec: Dict[str, Any],
    temp_dir: str,
    main_pick_worktree: str,
    session_result_path: str,
) -> HandlerResult:
    """Pick 任务前处理。

    Returns:
        (working_dir, prompt, extra_result)
    """
    commits = sub_batch.get("commits", [])
    sub_batch_id = task.get("sub_batch_id", "")
    subbatch_suffix = sub_batch_id.split("_")[-1]
    working_dir = main_pick_worktree or sub_batch.get("worktree_path") or (task.get("payload") or {}).get("worktree_path", "")

    extra_result: Dict[str, Any] = {
        "sub_batch_id": sub_batch_id,
        "batch_id": sub_batch.get("batch_id", ""),
        "branch_name": sub_batch.get("branch_name", ""),
        "commit_count": len(commits),
        "start_commit": commits[0],
        "end_commit": commits[-1],
        "snapshot_branch": sub_batch.get("branch_name", ""),
        "working_branch": batch_config.get("working_branch", ""),
    }
    if session_result_path:
        extra_result["session_result_path"] = session_result_path

    # branch_dance 专属状态目录
    if temp_dir:
        branch_dance_state_dir = str(Path(temp_dir) / f"branch_dance_{subbatch_suffix}")
        extra_result["branch_dance_state_dir"] = branch_dance_state_dir

    base_prompt = spec["prompt"].format(end_commit=commits[-1])

    # 注入状态目录约束
    if temp_dir:
        branch_dance_state_dir = extra_result["branch_dance_state_dir"]
        base_prompt = (
            f"本次 Branch Dance 的 agent 状态文件必须使用 SubBatch 专属状态目录 `{branch_dance_state_dir}`，"
            f"严禁读取或写入共享根目录 `{temp_dir}` 下的 agent_session.json、agent_review.md、_bd_pick_results.json。"
            f"请确保专属目录存在，并将 agent_session.json、agent_review.md、_bd_pick_results.json、_bd_temp_msg.txt "
            f"等文件全部写入该专属目录；不要在各个 SubBatch worktree 下创建独立 temp 状态。"
            f"冲突审阅视图会通过 sub-agent task description/title 中的规范格式 "
            f"`Branch Dance conflict<batch-suffix>: <short_hash>`（兼容 `Conflict batch N/M: <short_hash>`，"
            f"旧 transcript 中的 `conflict: <short_hash>` 也会被容忍）"
            f"把 LLM 冲突决策和对应 commit/evidence 关联起来；"
            f"不要再依赖 `gb pick resume --solve-session` 或手写 solve_session 记录。"
            f"DAG session_result.json 必须由你直接写入 `{session_result_path}`；"
            f"gb pick 不接收也不会写 DAG 结果参数。"
            f"{base_prompt}"
        )

    # 注入分支约束
    working_branch = extra_result.get("working_branch", "")
    snapshot_branch = extra_result.get("snapshot_branch", "")
    prompt = (
        f"当前任务是 SubBatch `_{subbatch_suffix}`，范围为 `{commits[0]}` 到 `{commits[-1]}`（**inclusive，包含首尾**）；"
        f"目标 end commit 必须按字面值使用 `{commits[-1]}`，且**必须被 cherry-pick 到 HEAD**之后才算完成。"
        f"⚠️ Inclusive 语义提醒：`bd/currentcommit.txt` / `gb pick status` 中的 `current_commit` 是**下一个待 pick 的 SHA**；"
        f"当它等于 `{commits[-1]}` 时表示**末尾 commit 还未被 pick**（end_commit_pending），"
        f"此时绝不能宣告完成，必须再跑一次 `gb pick run --end-commit {commits[-1]}` 把它 pick 进去。"
        f"完成判定**只**以 gb 输出的 `end_state.range_complete == true` 为准（gb 会同时校验指针越过 + Branch Dance trailer 在 HEAD 历史中）；"
        f"禁止用 `current_commit == end_commit`、SHA 前缀近似、commits.txt 行号比较等任何其他办法判断完成。"
        f"在写最终 session_result.json 之前，请先执行一次 `gb pick status --end-commit {commits[-1]} --format json` 校验 `end_state.range_complete=true`。"
        f"本任务必须在主线 working_branch `{working_branch}` 上连续 pick；"
        f"SubBatch snapshot_branch `{snapshot_branch}` 只是 DAG 在 pick 成功后物化快照使用的分支名，"
        f"pick 过程中严禁执行 `git checkout {snapshot_branch}`、`git switch {snapshot_branch}`，"
        f"也严禁把当前工作目录切换到任何 `_a/_b/_c/_d` 快照分支。"
        f"最终 session_result.json 中 `branch_name` 和 `working_branch` 必须是 `{working_branch}`，"
        f"`snapshot_branch` 必须是 `{snapshot_branch}`。{base_prompt}"
    )

    return working_dir, prompt, extra_result
