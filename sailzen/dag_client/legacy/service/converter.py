"""状态转换 & 数据格式转换工具。

提供:
  - task_status → DAG node_status 映射
  - batch_status → pipeline run_status 映射
  - batch_to_pipeline_run: Batch + Tasks → 前端 PipelineRun 格式
  - task_type → agent capability 映射
"""

from __future__ import annotations

from typing import Optional

from bot_server.deps import get_db


# ── Status Mapping ──────────────────────────────────────────────────


def task_status_to_node_status(ts: str) -> str:
    """Task 状态 → DAG 前端 node 状态。"""
    mapping = {
        "pending": "waiting",
        "queued": "pending",
        "assigned": "running",
        "running": "running",
        "success": "success",
        "failed": "failed",
        "blocked": "blocked",
        "cancelled": "skipped",
        "superseded": "skipped",
    }
    return mapping.get(ts, "waiting")


def batch_status_to_run_status(bs: str) -> str:
    """Batch 状态 → Pipeline run 前端状态。"""
    mapping = {
        "pending": "pending",
        "running": "running",
        "blocked": "blocked",
        "completed": "success",
        "failed": "failed",
        "awaiting_rebase": "running",
    }
    return mapping.get(bs, "pending")


def task_type_to_capability(task_type: str) -> Optional[str]:
    """Task 类型 → Agent capability 名称。"""
    mapping = {
        "init_workspace": "workspace",
        "pick": "pick", "rebase": "pick",
        "build_win": "build-win", "build_ios": "build-ios",
        "review": "review", "summary": "summary", "report": "report",
        "ensure_worktree": "workspace",
    }
    return mapping.get(task_type)


# ── Batch → PipelineRun ────────────────────────────────────────────


def _task_display_name(task: dict) -> str:
    """生成 Task 的显示名称，对 REPORT 做特殊处理。"""
    task_type = task["type"]
    sb_suffix = task["sub_batch_id"].split("_")[-1]

    if task_type == "init_workspace":
        return "Init Workspace"

    if task_type == "ensure_worktree":
        variant = (task.get("payload") or {}).get("variant", "main")
        suffix = "_buildfix" if variant == "buildfix" else ""
        return f"ensure_worktree{suffix} (_{sb_suffix})"

    if task_type == "report":
        # Batch 级 REPORT，不标注 SubBatch
        return "report (batch)"
    if task_type == "finalization":
        # Batch 级 FINALIZATION，不标注 SubBatch
        return "finalization (batch)"
    return f"{task_type} (_{sb_suffix})"


def _task_description(task: dict) -> str:
    """生成 Task 描述，对 SUMMARY 包含 commit 信息摘要。"""
    task_type = task["type"]
    sb_id = task["sub_batch_id"]
    payload = task.get("payload") or {}

    if task_type == "init_workspace":
        predecessor = payload.get("predecessor_branch", "")
        work_dir = payload.get("work_dir", "")
        mocked = bool((task.get("result") or {}).get("mock"))
        mode = "mock" if mocked else "real"
        return f"Init Workspace ({mode}): predecessor={predecessor}, work_dir={work_dir}"

    if task_type == "summary" and payload.get("commit_count"):
        count = payload["commit_count"]
        branch = payload.get("branch_name", "")
        subbatch_base = payload.get("subbatch_base_branch", "")
        batch_predecessor = payload.get("batch_predecessor_branch", "")
        first = payload.get("commits", [{}])[0].get("short", "?") if payload.get("commits") else "?"
        last = payload.get("commits", [{}])[-1].get("short", "?") if payload.get("commits") else "?"
        base_text = f", subbatch_base={subbatch_base}" if subbatch_base else ""
        predecessor_text = f", batch_predecessor={batch_predecessor}" if batch_predecessor else ""
        return f"Summary for {sb_id}: {count} commits ({first}..{last}), branch={branch}{base_text}{predecessor_text}"

    if task_type == "report":
        deps = task.get("dependencies", [])
        return f"Batch Report: depends on {len(deps)} reviews"

    if task_type == "finalization":
        payload = task.get("payload") or {}
        working_branch = payload.get("working_branch", "")
        backup_branch = payload.get("backup_branch", "")
        last_sb = payload.get("last_subbatch_branch", "")
        result = task.get("result") or {}
        if result.get("finalized"):
            snapshot = result.get("snapshot_branch", "")
            return (
                f"Finalization: {working_branch} backed up to {backup_branch}; "
                f"redirected → {snapshot}"
            )
        return (
            f"Finalization: backup {working_branch} → {backup_branch}; "
            f"redirect to snapshot of {last_sb}"
        )

    return f"Task {task_type} for {sb_id}"


async def batch_to_pipeline_run(batch: dict) -> dict:
    """将 Batch + Tasks 转换为前端 PipelineRun 格式。"""
    db = get_db()
    tasks = await db.get_tasks_by_batch(batch["id"])

    node_runs = []
    for i, t in enumerate(tasks):
        # --- Merge task.result fields into node payload ---
        # task.payload is set at DAG-build time (static config).
        # task.result contains extra_result from handlers (runtime info:
        # sub_batch_id, batch_id, branch_name, snapshot info, etc.)
        # These are needed by the frontend NodeDetailPanel for pick review links.
        result = t.get("result") or {}
        payload = {**((t.get("payload")) or {})}
        for key in (
            "sub_batch_id", "batch_id", "branch_name", "working_branch",
            "snapshot_branch", "start_commit", "end_commit", "commit_count",
            "branch_dance_state_dir", "session_result_path",
            "snapshot_worktree_path", "snapshot_source_ref",
        ):
            if key in result:
                payload.setdefault(key, result[key])

        node_runs.append({
            "id": i,
            "node_id": t["id"],
            "node_name": _task_display_name(t),
            "node_type": t["type"],
            "description": _task_description(t),
            "depends_on": t.get("dependencies", []),
            "status": task_status_to_node_status(t["status"]),
            "logs": [],
            "started_at": t.get("started_at"),
            "finished_at": t.get("completed_at"),
            "duration": None,
            "is_dynamic": False,
            "can_spawn": False,
            "payload": payload,
            "result": result,
            "error": t.get("error"),
        })

    pipeline_definition_id = batch.get("config", {}).get("pipeline_id") or batch["batch_type"]
    pipeline_name = batch.get("config", {}).get("pipeline_name") or f"{batch['batch_type']}batch"

    return {
        "id": batch["id"],
        # pipeline_id 表示 pipeline 定义，不应该拿来区分 run；真正唯一的是 id/run_id。
        # 为了前端调试和历史显示清晰，这里保留定义 id，同时在 params 中携带 run_id。
        "pipeline_id": pipeline_definition_id,
        "pipeline_name": f"{pipeline_name} ({batch['id']})",
        "params": batch.get("config", {}),
        "status": batch_status_to_run_status(batch["status"]),
        "created_at": batch["created_at"],
        "started_at": batch.get("started_at"),
        "finished_at": batch.get("completed_at"),
        "node_runs": node_runs,
    }
