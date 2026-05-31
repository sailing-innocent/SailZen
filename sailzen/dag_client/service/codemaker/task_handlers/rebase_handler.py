"""Rebase task handler：batch-rebase skill 前处理与 prompt 构造。

负责：
- 检查是否需要跳过 rebase（首个 SubBatch）
- 查找前序 SubBatch，提取 previous_branch
- 构造 rebase 约束 prompt（防止误 checkout 其他分支）
- 返回 (working_dir, prompt, extra_result)，或直接返回跳过结果 dict
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# 返回类型：正常 → (working_dir, prompt, extra_result)；跳过 → 直接返回 result dict
HandlerResult = Tuple[str, str, Dict[str, Any]]


async def get_previous_subbatch(db, sub_batch: dict) -> Optional[dict]:
    """查找当前 SubBatch 的前序 SubBatch。"""
    batch_id = sub_batch.get("batch_id")
    index_num = sub_batch.get("index_num", 0)
    if not batch_id or index_num <= 0:
        return None
    sub_batches = await db.get_sub_batches(batch_id)
    for candidate in sub_batches:
        if candidate.get("index_num") == index_num - 1:
            return candidate
    return None


async def handle(
    *,
    task: dict,
    sub_batch: dict,
    batch_config: dict,
    spec: Dict[str, Any],
    temp_dir: str,
    session_result_path: str,
    db,
) -> Union[HandlerResult, Dict[str, Any]]:
    """Rebase 任务前处理。

    Returns:
        (working_dir, prompt, extra_result)，
        或跳过时直接返回 result dict（含 success=True, rebase_ok=True）。
    """
    sub_batch_id = task.get("sub_batch_id", "")
    subbatch_suffix = sub_batch_id.split("_")[-1]
    payload = task.get("payload") or {}
    working_dir = sub_batch.get("worktree_path") or payload.get("worktree_path", "")

    extra_result: Dict[str, Any] = {
        "branch_name": sub_batch.get("branch_name", ""),
        "commit_count": len(sub_batch.get("commits", [])),
    }
    if session_result_path:
        extra_result["session_result_path"] = session_result_path

    # ── 检查是否跳过 ──
    skip_result_base = {
        "success": True,
        "runner": spec["runner"],
        "rebase_ok": True,
        "skill": spec["skill"],
        "working_dir": working_dir,
        "text_response": "首个 SubBatch 无前序分支，跳过 rebase。",
        **extra_result,
    }
    if payload.get("skip_rebase"):
        return {
            **skip_result_base,
            "rebase_skipped": True,
            "reason": payload.get("reason", "first_subbatch"),
        }

    previous_sub_batch = await get_previous_subbatch(db, sub_batch)
    if not previous_sub_batch:
        return {
            **skip_result_base,
            "rebase_skipped": True,
            "reason": "no_previous_subbatch",
        }

    current_branch = sub_batch.get("branch_name", "")
    previous_branch = previous_sub_batch["branch_name"]
    extra_result["previous_branch"] = previous_branch
    extra_result["current_branch"] = current_branch

    # ── 传递 subbatch_base_branch 作为 merge-base 参考 ──
    subbatch_base_branch = sub_batch.get("subbatch_base_branch") or ""
    extra_result["subbatch_base_branch"] = subbatch_base_branch
    # 前序分支的 pre-buildfix 备份分支，可用作精确的 merge-base 参考点。
    pre_buildfix_backup = f"{previous_branch}_pre_buildfix_backup"
    extra_result["pre_buildfix_backup_branch"] = pre_buildfix_backup

    # 专属状态目录
    branch_dance_state_dir = str(Path(temp_dir) / f"batch_rebase_{subbatch_suffix}") if temp_dir else ""
    if branch_dance_state_dir:
        extra_result["branch_dance_state_dir"] = branch_dance_state_dir

    # 构造 batch-rebase prompt
    base_prompt = spec["prompt"].format(previous_branch=previous_branch)
    orchestration_fields = (
        f"task_id={task.get('id', '')!r}, "
        f"sub_batch_id={sub_batch_id!r}, "
        f"working_branch={current_branch!r}, "
        f"branch_name={current_branch!r}, "
        f"previous_branch={previous_branch!r}"
    )
    if subbatch_base_branch:
        orchestration_fields += f", subbatch_base_branch={subbatch_base_branch!r}"
        orchestration_fields += f", pre_buildfix_backup_branch={pre_buildfix_backup!r}"
    if branch_dance_state_dir:
        orchestration_fields += f", state_dir={branch_dance_state_dir!r}"
    if session_result_path:
        orchestration_fields += f", result_path={session_result_path!r}"

    prompt = (
        f"本次 Batch Rebase 任务由 CubeClaw DAG 编排。编排参数：{orchestration_fields}。\n"
        f"工作分支必须是 `{current_branch}`，目标 onto 分支为 `{previous_branch}`。\n"
        f"启动时请先 `git branch --show-current` 确认当前分支等于 `{current_branch}`；"
        f"若不等，请立即写最终态 `status: \"blocked\"`、`blocked_reason: \"wrong_working_branch\"` 后停止。\n"
        f"严禁 `git checkout {previous_branch}` 或切换到任何其他分支。\n"
        f"本次 rebase 必须使用 --onto 语义，将当前分支负责的 commit 范围精确 replay 到目标分支上：\n"
        f"1. 先用 `git merge-base HEAD {previous_branch}` 计算 merge-base；\n"
    )
    if subbatch_base_branch:
        prompt += (
            f"2. 若有 `{pre_buildfix_backup}` 分支，优先以其作为 merge-base 参考"
            f"（该分支记录了 {previous_branch} 在 buildfix merge-back 之前的精确状态）；\n"
            f"3. 使用 `git rebase --onto {previous_branch} <merge_base>` 执行 rebase；\n"
        )
    else:
        prompt += (
            f"2. 使用 `git rebase --onto {previous_branch} <merge_base>` 执行 rebase；\n"
        )
    prompt += (
        f"4. 严禁使用 `git rebase {previous_branch}`（隐式 merge-base 可能选错范围）。\n"
        f"最终 session_result.json 中 `skill` 必须是 `batch-rebase`，`task_type` 必须是 `rebase`，"
        f"`branch_name` 和 `working_branch` 必须是 `{current_branch}`，`previous_branch` 必须是 `{previous_branch}`，"
        f"并包含 `head_sha` 与 `rebase_state_path`。\n"
        f"{base_prompt}"
    )

    return working_dir, prompt, extra_result
