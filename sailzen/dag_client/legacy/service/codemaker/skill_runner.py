"""Skill Runner：按 task type 依赖注入对应 task handler，统一调用 entry。

公共入口：
    run_skill_via_codemaker(task, db, codemaker_config)

分发逻辑：
    task.type  →  SKILL_SPECS[task_type]  →  task_handlers.*  →  entry.run_prompt_via_codemaker
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base import SKILL_SPECS, skill_error_result, task_session_result_path, DEFAULT_SSE_TIMEOUT
from .entry import run_prompt_via_codemaker
from .task_handlers import handle_pick, handle_rebase, handle_build_win, handle_build_ios, handle_review

logger = logging.getLogger(__name__)


async def run_skill_via_codemaker(
    task: dict,
    db,
    codemaker_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """按 task type 调用对应 CodeMaker skill。

    当前支持的 task type：
    - pick         → branch-dance
    - rebase       → batch-rebase
    - build_win    → batch-fixbuild-windows
    - build_ios    → batch-fixbuild-ios
    - review       → batch-review (轻量阶段)
    - final_review → batch-review (全量集中)

    Args:
        task:             Task dict，必须包含 sub_batch_id 和 type
        db:               DatabaseCompat 实例
        codemaker_config: Codemaker 连接配置（host/port/sse_timeout 等）

    Returns:
        result dict，包含 success、runner、success_key 等字段
    """
    task_type = task.get("type", "")
    spec = SKILL_SPECS.get(task_type)
    if not spec:
        return skill_error_result(
            f"Unsupported Codemaker task type: {task_type}",
            runner="codemaker_skill",
        )

    config = codemaker_config or {}
    sub_batch_id = task.get("sub_batch_id", "")
    task_label = f"{task_type}(_{sub_batch_id.split('_')[-1]})"

    # ── 加载 SubBatch 与 Batch 公共数据 ──────────────────────────────
    sub_batch = await db.get_sub_batch(sub_batch_id)
    if not sub_batch:
        return skill_error_result(
            f"SubBatch not found: {sub_batch_id}",
            runner=spec["runner"],
        )

    batch = await db.get_batch(sub_batch["batch_id"])
    batch_config = (batch or {}).get("config") or {}
    workspace_paths = batch_config.get("workspace_paths", {})
    main_pick_worktree = workspace_paths.get("mcpe_gb_dir", "")
    temp_dir = workspace_paths.get("temp_dir", "")

    # ── 计算 session_result_path ──────────────────────────────────────
    session_result_path = ""
    if temp_dir:
        session_result_path = task_session_result_path(temp_dir, task)

    # ── 依赖注入：按 task_type 调用对应 handler ───────────────────────
    if task_type == "pick":
        commits = sub_batch.get("commits", [])
        if not commits:
            return skill_error_result(
                f"SubBatch {sub_batch_id} has no commits",
                runner=spec["runner"],
            )
        working_dir, prompt, extra_result = handle_pick(
            task=task,
            sub_batch=sub_batch,
            batch_config=batch_config,
            spec=spec,
            temp_dir=temp_dir,
            main_pick_worktree=main_pick_worktree,
            session_result_path=session_result_path,
        )

    elif task_type == "rebase":
        handler_result = await handle_rebase(
            task=task,
            sub_batch=sub_batch,
            batch_config=batch_config,
            spec=spec,
            temp_dir=temp_dir,
            session_result_path=session_result_path,
            db=db,
        )
        # handle_rebase 可能直接返回跳过结果 dict
        if isinstance(handler_result, dict):
            return handler_result
        working_dir, prompt, extra_result = handler_result

    elif task_type == "build_win":
        working_dir, prompt, extra_result = await handle_build_win(
            task=task,
            sub_batch=sub_batch,
            batch_config=batch_config,
            spec=spec,
            workspace_paths=workspace_paths,
            temp_dir=temp_dir,
            session_result_path=session_result_path,
        )

    elif task_type == "build_ios":
        working_dir, prompt, extra_result = await handle_build_ios(
            task=task,
            sub_batch=sub_batch,
            batch_config=batch_config,
            spec=spec,
            workspace_paths=workspace_paths,
            temp_dir=temp_dir,
            session_result_path=session_result_path,
        )

    elif task_type in ("review", "final_review"):
        # Review tasks need the exact commit scope in their prompt/state matching.
        # Lightweight review uses the current SubBatch commits; final_review uses
        # the full Batch commits so it cannot accidentally review only the last
        # SubBatch or resume another SubBatch's checkpoint.
        if batch:
            batch_config = dict(batch_config)
            batch_config.setdefault("commits", batch.get("commits") or [])
        if task_type == "final_review" and batch:
            batch_config.setdefault("commit_count", len(batch.get("commits") or []))
        working_dir, prompt, extra_result = handle_review(
            task=task,
            sub_batch=sub_batch,
            batch_config=batch_config,
            spec=spec,
            temp_dir=temp_dir,
            main_pick_worktree=main_pick_worktree,
            session_result_path=session_result_path,
        )

    else:
        return skill_error_result(
            f"No handler registered for task type: {task_type}",
            runner=spec["runner"],
        )

    # ── 追加通用 prompt 前缀（workdir 和 DAG 结果文件提示） ─────────────
    if working_dir:
        prompt = (
            f"请在工作目录 `{working_dir}` 中执行本任务。"
            f"如果当前 shell 不在该目录，请先切换到该目录；"
            f"确认后执行：{prompt}"
        )
    if session_result_path:
        prompt = (
            f"DAG 结果文件：`{session_result_path}`；"
            f"请确保其父目录存在，并在最终退出前写入最终态 JSON。{prompt}"
        )

    # ── 统一调用 DAG-aware Codemaker entry ───────────────────────────
    return await run_prompt_via_codemaker(
        task_label=task_label,
        task=task,
        db=db,
        codemaker_config=config,
        skill_name=spec["skill"],
        runner_name=spec["runner"],
        prompt=prompt,
        working_dir=working_dir,
        success_key=spec["success_key"],
        sse_timeout=float(config.get("sse_timeout", spec.get("timeout", DEFAULT_SSE_TIMEOUT))),
        extra_result=extra_result,
    )
