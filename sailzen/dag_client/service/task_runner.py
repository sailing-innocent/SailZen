"""Task Runner / Dispatcher — productive DAG execution loop.

DAG progression, real task execution, and development simulation separated:

- ``productive_task_runner`` drives queued tasks toward injected executors.
- Built-in lightweight nodes (summary/report) are completed by the manager.
- CodeMaker-backed nodes are delegated to the generic SkillRunner.
- Unsupported real nodes (currently iOS remote buildfix) are blocked instead of
  being silently mocked.

"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Optional, Protocol

from bot_server.models import BatchStatus, TaskStatus, now_iso
from bot_server.service.codemaker import run_skill_via_codemaker
from bot_server.service.converter import batch_to_pipeline_run
from bot_server.service.mock_runner import (
    _mock_result_for_task,
)
from bot_server.service.side_tasks import (
    _materialize_subbatch_after_pick,
    _merge_buildfix_back_after_success,
    _finalize_main_branch,
)

logger = logging.getLogger(__name__)

CODEMAKER_TASK_TYPES = {"pick", "rebase", "build_win", "review", "final_review"}
MANAGER_TASK_TYPES = {"init_workspace", "summary", "ensure_worktree", "report", "finalization"}
UNSUPPORTED_REAL_TASK_TYPES = {"build_ios"}
OPTIONAL_UNSUPPORTED_REAL_TASK_TYPES = {"build_ios"}

TaskExecutor = Callable[..., Awaitable[dict]]


class SchedulerLike(Protocol):
    is_paused: bool

    async def on_task_completed(
        self,
        task_id: str,
        success: bool,
        result: Optional[dict] = None,
        error: Optional[dict] = None,
    ) -> None: ...


class DatabaseLike(Protocol):
    async def get_batch(self, batch_id: str) -> Optional[dict]: ...

    async def get_tasks_by_batch(self, batch_id: str) -> list[dict]: ...

    async def update_batch_status(self, batch_id: str, status: str, **kwargs) -> None: ...

    async def update_task_status(self, task_id: str, status: str, **kwargs) -> bool: ...

    async def claim_queued_task(self, task_id: str, **kwargs) -> bool: ...


class EventBusLike(Protocol):
    async def emit(self, event: dict) -> None: ...


@dataclass(slots=True)
class TaskRunnerDependencies:
    """External collaborators required by the productive task runner.

    Keep the runner itself focused on DAG polling/state transitions.  Integrations
    such as EventBus publishing and concrete task executors are injected here so
    future TaskDispatcher/remote-agent work can replace them independently.
    """

    db: DatabaseLike
    scheduler: SchedulerLike
    event_bus: Optional[EventBusLike] = None
    codemaker_executor: TaskExecutor = run_skill_via_codemaker
    mock_result_factory: Callable[[dict], dict] = _mock_result_for_task
    materialize_subbatch_after_pick: Callable[[dict, str, DatabaseLike, dict], Awaitable[None]] = _materialize_subbatch_after_pick
    merge_buildfix_back_after_success: Callable[[dict, str, DatabaseLike, dict], Awaitable[None]] = _merge_buildfix_back_after_success
    manager_result_factory: Optional[Callable[[dict, Optional[dict], Optional[list]], dict]] = None
    claim_task: Optional[Callable[[str, DatabaseLike], Awaitable[bool]]] = None

    def __post_init__(self) -> None:
        if self.manager_result_factory is None:
            self.manager_result_factory = _manager_result_for_task
        if self.claim_task is None:
            self.claim_task = _claim_queued_task

    async def emit_task_event(self, event_type: str, batch_id: str, task: dict, data: dict) -> None:
        await _emit_task_event(self.event_bus, event_type, batch_id, task, data)

    async def emit_pipeline_progress(self, batch_id: str) -> None:
        await _emit_pipeline_progress(self.event_bus, self.db, batch_id)


@dataclass(slots=True)
class TaskRunnerConfig:
    """Runtime configuration for a productive runner instance."""

    codemaker_config: Optional[Dict] = None
    mock_task_types: set[str] = field(default_factory=set)
    poll_interval: float = 2.0


def normalize_mock_task_types(value: object) -> set[str]:
    """Normalize per-run task mock configuration.

    Accepted forms from Dashboard/API:
    - ["build_ios", "review"]
    - "build_ios,review"
    - {"build_ios": true, "review": false}
    """
    if not value:
        return set()
    if isinstance(value, str):
        return {item.strip() for item in value.split(",") if item.strip()}
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    if isinstance(value, dict):
        return {str(key).strip() for key, enabled in value.items() if enabled and str(key).strip()}
    return set()


def _task_label(task: dict) -> str:
    return f"{task['type']}(_{task['sub_batch_id'].split('_')[-1]})"


def _blocked_dependency_closure(tasks: list[dict]) -> set[str]:
    """Return tasks that can never run because one of their DAG ancestors is blocked.

    The task type does not matter here: reachability is derived purely from DAG
    edges.  A blocked node only blocks its downstream closure; unrelated branches
    remain runnable until no queued/running/reachable-pending work exists.
    """
    by_id = {t["id"]: t for t in tasks}
    blocked_ids = {t["id"] for t in tasks if t.get("status") == TaskStatus.BLOCKED.value}
    unreachable = set(blocked_ids)
    changed = True
    while changed:
        changed = False
        for task in tasks:
            task_id = task["id"]
            if task_id in unreachable:
                continue
            deps = task.get("dependencies") or []
            if any(dep in unreachable for dep in deps):
                unreachable.add(task_id)
                changed = True
    return unreachable


def _has_reachable_pending_work(tasks: list[dict]) -> bool:
    """Whether any pending task may still become runnable.

    Pending nodes whose dependency chain already contains a BLOCKED node are dead;
    all other pending nodes are still part of a live DAG frontier, even if they are
    waiting for running/queued ancestors to finish.
    """
    unreachable = _blocked_dependency_closure(tasks)
    return any(
        task.get("status") == TaskStatus.PENDING.value and task["id"] not in unreachable
        for task in tasks
    )


def _manager_result_for_task(task: dict, batch: Optional[dict] = None, tasks: Optional[list] = None) -> dict:
    """Generate real manager-owned results for lightweight nodes."""
    task_type = task.get("type", "")
    payload = task.get("payload") or {}
    result = {"mock": False, "runner": "task_runner", "task_type": task_type}

    if task_type == "init_workspace":
        workspace_paths = payload.get("workspace_paths") or {}
        result.update({
            "summary": "GlobalBatch workspace initialized.",
            "batch_id": payload.get("batch_id") or task.get("batch_id") or (batch or {}).get("id", ""),
            "predecessor_branch": payload.get("predecessor_branch", ""),
            "working_branch": payload.get("working_branch", ""),
            "work_dir": payload.get("work_dir", ""),
            "workspace_paths": workspace_paths,
            "commit_count": payload.get("commit_count", 0),
        })
    elif task_type == "summary":
        commit_count = payload.get("commit_count", 0)
        branch = payload.get("branch_name", "")
        commits = payload.get("commits", [])
        first_short = commits[0]["short"] if commits else "?"
        last_short = commits[-1]["short"] if commits else "?"
        result.update({
            "summary": f"{commit_count} commits on {branch} ({first_short}..{last_short})",
            "commit_count": commit_count,
            "branch_name": branch,
            "commits": commits,
        })
    elif task_type == "ensure_worktree":
        variant = payload.get("variant", "main")
        branch = payload.get("branch_name", "")
        worktree_path = payload.get("worktree_path", "")
        if variant == "buildfix":
            buildfix_branch = payload.get("buildfix_branch") or (f"{branch}_buildfix" if branch and not branch.endswith("_buildfix") else branch)
            source_branch = payload.get("source_branch") or (branch[:-len("_buildfix")] if branch.endswith("_buildfix") else branch)
            result.update({
                "summary": f"Ensured buildfix worktree for {buildfix_branch}",
                "variant": variant,
                "branch_name": buildfix_branch,
                "source_branch": source_branch,
                "base_ref": payload.get("base_ref") or source_branch,
                "buildfix_branch": buildfix_branch,
                "buildfix_worktree_path": worktree_path,
                "worktree_path": worktree_path,
            })
        else:
            result.update({
                "summary": f"Ensured main worktree for {branch}",
                "variant": variant,
                "branch_name": branch,
                "worktree_path": worktree_path,
            })
    elif task_type == "report":
        all_tasks = tasks or []
        completed_tasks = [t for t in all_tasks if t.get("id") != task.get("id")]
        successful = len([t for t in completed_tasks if t.get("status") == TaskStatus.SUCCESS.value])
        blocked = len([t for t in completed_tasks if t.get("status") == TaskStatus.BLOCKED.value])
        result.update({
            "report": "GlobalBatch manager summary generated.",
            "batch_id": task.get("batch_id") or (batch or {}).get("id", ""),
            "task_total": len(completed_tasks) + 1,
            "task_success": successful + 1,
            "task_blocked": blocked,
        })
    elif task_type == "finalization":
        working_branch = payload.get("working_branch", "")
        backup_branch = payload.get("backup_branch", "")
        last_subbatch_id = payload.get("last_subbatch_id", "")
        last_subbatch_branch = payload.get("last_subbatch_branch", "")
        result.update({
            "summary": (
                f"Finalization: backup {working_branch} → {backup_branch}; "
                f"redirect {working_branch} → snapshot of {last_subbatch_branch}"
            ),
            "working_branch": working_branch,
            "backup_branch": backup_branch,
            "last_subbatch_id": last_subbatch_id,
            "last_subbatch_branch": last_subbatch_branch,
        })

    return result


async def _emit_task_event(event_bus, event_type: str, batch_id: str, task: dict, data: dict) -> None:
    if not event_bus:
        return
    await event_bus.emit({
        "type": event_type,
        "entity_type": "task",
        "entity_id": task["id"],
        "run_id": batch_id,
        "data": data,
    })


async def _emit_pipeline_progress(event_bus, db, batch_id: str) -> None:
    if not event_bus:
        return
    batch = await db.get_batch(batch_id)
    if not batch:
        return
    run = await batch_to_pipeline_run(batch)

    # 只在 PipelineRun snapshot 真实发生变化时 emit，避免轮询点反复推送同一份大对象
    # 进而灌爆 SSE 通道、event_logs 表与 POPO 通知。状态变化（task running/completed/blocked、
    # batch terminal）必然会改变 status/started_at/finished_at/node_runs[*] 中的某一项，
    # 因此基于 snapshot 内容的 fingerprint 是状态变化最准确的判定。
    fingerprint = _pipeline_run_fingerprint(run)
    last_seen = getattr(event_bus, "_pipeline_progress_fingerprints", None)
    if last_seen is None:
        last_seen = {}
        try:
            setattr(event_bus, "_pipeline_progress_fingerprints", last_seen)
        except Exception:
            last_seen = None  # event_bus 不允许挂属性时，退化为始终 emit
    if last_seen is not None and last_seen.get(batch_id) == fingerprint:
        # 同一份 snapshot 已经发过了，跳过
        terminal_emit_only = batch["status"] in (
            BatchStatus.COMPLETED.value,
            BatchStatus.FAILED.value,
            BatchStatus.BLOCKED.value,
        )
        if not terminal_emit_only:
            return
    if last_seen is not None:
        last_seen[batch_id] = fingerprint
        # 已结束的 batch 不再保留指纹缓存，避免内存泄漏
        if batch["status"] in (
            BatchStatus.COMPLETED.value,
            BatchStatus.FAILED.value,
            BatchStatus.BLOCKED.value,
        ):
            last_seen.pop(batch_id, None)

    await event_bus.emit({
        "type": "pipeline_run.progress",
        "entity_type": "batch",
        "entity_id": batch_id,
        "run_id": batch_id,
        "data": run,
    })
    if batch["status"] == BatchStatus.COMPLETED.value:
        await event_bus.emit({
            "type": "pipeline_run.completed",
            "entity_type": "batch",
            "entity_id": batch_id,
            "run_id": batch_id,
            "data": {"pipeline_name": run.get("pipeline_name", batch_id), "batch_id": batch_id},
        })
    elif batch["status"] in (BatchStatus.FAILED.value, BatchStatus.BLOCKED.value):
        await event_bus.emit({
            "type": "pipeline_run.failed",
            "entity_type": "batch",
            "entity_id": batch_id,
            "run_id": batch_id,
            "data": {"pipeline_name": run.get("pipeline_name", batch_id), "batch_id": batch_id},
        })


def _pipeline_run_fingerprint(run: dict) -> str:
    """计算 PipelineRun 的内容指纹，仅取会随状态变化而变化的字段。"""
    relevant = {
        "status": run.get("status"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "nodes": [
            {
                "id": node.get("node_id"),
                "status": node.get("status"),
                "started_at": node.get("started_at"),
                "finished_at": node.get("finished_at"),
            }
            for node in run.get("node_runs", [])
        ],
    }
    payload = json.dumps(relevant, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


async def _run_codemaker_task(
    task: dict,
    batch_id: str,
    deps: TaskRunnerDependencies,
    codemaker_config: Dict,
) -> dict:
    task_type = task.get("type", "")
    result = await deps.codemaker_executor(task=task, db=deps.db, codemaker_config=codemaker_config)
    if result.get("success"):
        if task_type == "pick":
            await deps.emit_task_event("task.progress", batch_id, task, {
                "task_type": task_type,
                "task_label": _task_label(task),
                "runner": result.get("runner", "codemaker_skill"),
                "stage": "materialize_subbatch_start",
                "message": "pick 已完成，开始物化 SubBatch 快照 worktree",
                "working_dir": result.get("working_dir", ""),
            })
            timeout = float(codemaker_config.get("materialize_timeout", 1800))
            await asyncio.wait_for(
                deps.materialize_subbatch_after_pick(task, batch_id, deps.db, result),
                timeout=timeout,
            )
            await deps.emit_task_event("task.progress", batch_id, task, {
                "task_type": task_type,
                "task_label": _task_label(task),
                "runner": result.get("runner", "codemaker_skill"),
                "stage": "materialize_subbatch_done",
                "message": "SubBatch 快照 worktree 物化完成",
                "snapshot_branch": result.get("snapshot_branch", ""),
                "snapshot_worktree_path": result.get("snapshot_worktree_path", ""),
                "snapshot_source_ref": result.get("snapshot_source_ref", ""),
            })
        elif task_type == "build_win":
            await deps.emit_task_event("task.progress", batch_id, task, {
                "task_type": task_type,
                "task_label": _task_label(task),
                "runner": result.get("runner", "codemaker_skill"),
                "stage": "merge_buildfix_back_start",
                "message": "Windows buildfix 已完成，开始 merge-back",
            })
            await deps.merge_buildfix_back_after_success(task, batch_id, deps.db, result)
            await deps.emit_task_event("task.progress", batch_id, task, {
                "task_type": task_type,
                "task_label": _task_label(task),
                "runner": result.get("runner", "codemaker_skill"),
                "stage": "merge_buildfix_back_done",
                "message": "Windows buildfix merge-back 完成",
            })
    return result


async def _claim_queued_task(task_id: str, db: DatabaseLike) -> bool:
    claim = getattr(db, "claim_queued_task", None)
    if callable(claim):
        return await claim(task_id, started_at=now_iso())

    task = None
    get_task = getattr(db, "get_task", None)
    if callable(get_task):
        task = await get_task(task_id)
    if task and task.get("status") != TaskStatus.QUEUED.value:
        return False
    return await db.update_task_status(
        task_id,
        TaskStatus.RUNNING.value,
        expected_statuses=[TaskStatus.QUEUED.value],
        started_at=now_iso(),
    )


async def _emit_current_pipeline_progress(deps: TaskRunnerDependencies, batch_id: str) -> None:
    """Emit a PipelineRun snapshot immediately after a DB state transition.

    Productive tasks run in background asyncio tasks while the outer polling loop emits
    periodic progress snapshots.  Relying only on the poller leaves a short but visible
    stale window after fast completions: POPO has already received task.completed, but
    Dashboard may still be rendering the previous RUNNING snapshot until the next tick.
    Emitting here makes task completion/unlock transitions observable immediately.
    """
    try:
        await deps.emit_pipeline_progress(batch_id)
    except Exception:
        logger.exception("[TaskRunner] pipeline progress emit failed: batch=%s", batch_id[:16])


async def _run_single_productive_task(
    task: dict,
    batch_id: str,
    deps: TaskRunnerDependencies,
    config: TaskRunnerConfig,
) -> None:
    label = _task_label(task)
    task_type = task.get("type", "")

    claimed = await deps.claim_task(task["id"], deps.db)
    if not claimed:
        logger.info("[TaskRunner] ⏭ %s 已被其他 runner 抢占或状态变化，跳过", label)
        return
    task = {**task, "status": TaskStatus.RUNNING.value, "started_at": now_iso()}
    logger.info("[TaskRunner] ▶ %s → RUNNING", label)
    await deps.emit_task_event("task.running", batch_id, task, {
        "task_type": task_type,
        "task_label": label,
        "runner": "task_runner",
        "mocked_by_config": task_type in config.mock_task_types,
    })
    await _emit_current_pipeline_progress(deps, batch_id)

    task_run: Optional[dict] = None
    if task_type not in CODEMAKER_TASK_TYPES:
        try:
            attempt = await deps.db.next_task_run_attempt(task["id"])
            task_run = await deps.db.create_task_run({
                "id": __import__("uuid").uuid4().hex,
                "task_id": task["id"],
                "attempt": attempt,
                "status": "running",
                "runner": "task_runner",
                "agent_id": "task_runner",
                "session_id": None,
                "session_key": None,
                "prompt": None,
                "context": {"task_type": task_type, "task_label": label, "mocked_by_config": task_type in config.mock_task_types},
                "result": None,
                "error": None,
                "transcript_path": None,
                "started_at": now_iso(),
                "completed_at": None,
                "last_activity_at": now_iso(),
            })
        except Exception:
            logger.exception("[TaskRunner] %s: TaskRun 创建失败", label)

    try:
        if task_type in config.mock_task_types:
            await asyncio.sleep(0.1)
            result = deps.mock_result_factory(task)
            if task_type == "init_workspace":
                batch = await deps.db.get_batch(batch_id)
                result.update(deps.manager_result_factory(task, batch=batch, tasks=None))
                # Mock 模式下仍需创建剩余 DAG（Phase 3），只是跳过 git 操作。
                # 此处调用 execute_init 的 mock 路径：设置 mock=True 以生成模拟 commits。
                from bot_server.service.gb_init import execute_init
                batch_config = batch.get("config") or {}
                init_config = {**batch_config, "mock": True, "mock_init_workspace": True}
                init_result = await execute_init(
                    db=deps.db,
                    scheduler=deps.scheduler,
                    batch=batch,
                    task=task,
                    config=init_config,
                )
                if "error" not in init_result:
                    result.update(init_result)
                    result.update({
                        "summary": (
                            f"GlobalBatch initialized (mock): {init_result.get('total_commits', 0)} commits, "
                            f"{init_result.get('subbatch_count', 0)} subbatches, "
                            f"{init_result.get('tasks_created', 0)} tasks"
                        ),
                        "runner": "task_runner_node_mock_init",
                    })
                batch = await deps.db.get_batch(batch_id)
            result.update({
                "mock": True,
                "runner": "task_runner_node_mock",
                "mock_reason": "enabled_by_pipeline_node_mock_config",
            })
            await deps.scheduler.on_task_completed(task["id"], success=True, result=result)
            if task_run:
                await deps.db.complete_task_run(task_run["id"], success=True, result=result)
            task = {**task, "status": TaskStatus.SUCCESS.value, "result": result, "completed_at": now_iso()}
            await deps.emit_task_event("task.completed", batch_id, task, {
                "task_type": task_type,
                "task_label": label,
                "runner": "task_runner_node_mock",
                "mocked": True,
            })
            await _emit_current_pipeline_progress(deps, batch_id)
            logger.info("[TaskRunner] ✅ %s → SUCCESS (node mock)", label)
            return

        if task_type in MANAGER_TASK_TYPES:
            batch = await deps.db.get_batch(batch_id)
            tasks = await deps.db.get_tasks_by_batch(batch_id)
            result = deps.manager_result_factory(task, batch=batch, tasks=tasks)

            if task_type == "init_workspace":
                # init_workspace 是真正的异步工作节点（Two-Phase Init 的 Phase 1/2/3）。
                # 调用 execute_init 执行 git clone/fetch/worktree/start_globalbatch，
                # 然后在数据库中创建剩余 SubBatch DAG 节点。
                from bot_server.service.gb_init import execute_init

                batch_config = batch.get("config") or {}
                init_result = await execute_init(
                    db=deps.db,
                    scheduler=deps.scheduler,
                    batch=batch,
                    task=task,
                    config=batch_config,
                )
                if "error" in init_result:
                    raise RuntimeError(init_result["error"])
                result.update(init_result)
                result.update({
                    "summary": (
                        f"GlobalBatch initialized: {init_result.get('total_commits', 0)} commits, "
                        f"{init_result.get('subbatch_count', 0)} subbatches, "
                        f"{init_result.get('tasks_created', 0)} tasks"
                    ),
                    "runner": "task_runner_init_workspace",
                })
                # 刷新 batch/tasks 引用（execute_init 创建了新 task）
                batch = await deps.db.get_batch(batch_id)
                tasks = await deps.db.get_tasks_by_batch(batch_id)

            if task_type == "ensure_worktree":
                payload = task.get("payload") or {}
                variant = payload.get("variant", "main")
                worktree_path = payload.get("worktree_path", "")
                branch_name = payload.get("branch_name", "")
                logger.info(
                    "[TaskRunner] %s: variant=%s branch=%s worktree_path=%s",
                    label, variant, branch_name, worktree_path,
                )
                await deps.emit_task_event("task.progress", batch_id, task, {
                    "task_type": task_type,
                    "task_label": label,
                    "runner": "task_runner",
                    "stage": "ensure_worktree_checking",
                    "message": f"检查 worktree 状态: {worktree_path or '(未指定)'}",
                    "variant": variant,
                    "branch_name": branch_name,
                    "worktree_path": worktree_path,
                })

            # finalization 节点需要额外执行异步 git 操作（backup + checkout -B）
            if task_type == "finalization":
                payload = task.get("payload") or {}
                repo_dir = payload.get("repo_dir", "")
                mcpe_gb_dir = payload.get("mcpe_gb_dir", "")
                working_branch = payload.get("working_branch", "")
                backup_branch = payload.get("backup_branch", "")
                last_subbatch_id = payload.get("last_subbatch_id", "")
                if repo_dir and mcpe_gb_dir and working_branch and backup_branch and last_subbatch_id:
                    await deps.emit_task_event("task.progress", batch_id, task, {
                        "task_type": task_type,
                        "task_label": label,
                        "runner": "task_runner",
                        "stage": "finalize_branch_start",
                        "message": f"开始备份主分支 {working_branch} → {backup_branch}，再重定向到最后 SubBatch snapshot",
                    })
                    finalize_result = await _finalize_main_branch(task, batch_id, deps.db, result)
                    result.update(finalize_result)
                else:
                    logger.warning(
                        "[TaskRunner] %s: finalization payload 缺少 repo_dir/mcpe_gb_dir/working_branch/backup_branch/last_subbatch_id，跳过 git 操作",
                        label,
                    )
                    result.update({
                        "finalize_skipped": True,
                        "finalize_skip_reason": "missing_payload_fields",
                    })

            await deps.scheduler.on_task_completed(task["id"], success=True, result=result)
            if task_run:
                await deps.db.complete_task_run(task_run["id"], success=True, result=result)
            task = {**task, "status": TaskStatus.SUCCESS.value, "result": result, "completed_at": now_iso()}
            # emit task event, 
            await deps.emit_task_event("task.completed", batch_id, task, {
                "task_type": task_type,
                "task_label": label,
                "runner": result.get("runner", "task_runner"),
                "summary": result.get("summary") or result.get("report", ""),
            })
            await _emit_current_pipeline_progress(deps, batch_id)
            logger.info("[TaskRunner] ✅ %s → SUCCESS (manager)", label)
            return

        if task_type in CODEMAKER_TASK_TYPES:
            if not config.codemaker_config:
                raise RuntimeError(
                    f"Task {task_type} requires CodeMaker config in productive mode; "
                    "refusing to fall back to mock execution."
                )
            logger.info("[TaskRunner] 🔌 %s → CodeMaker SkillRunner", label)
            result = await _run_codemaker_task(task, batch_id, deps, config.codemaker_config)
            if result.get("success"):
                await deps.scheduler.on_task_completed(task["id"], success=True, result=result)
                task = {**task, "status": TaskStatus.SUCCESS.value, "result": result, "completed_at": now_iso()}
                await deps.emit_task_event("task.completed", batch_id, task, {
                    "task_type": task_type,
                    "task_label": label,
                    "runner": result.get("runner", "codemaker_skill"),
                    "session_id": result.get("session_id", ""),
                    "working_dir": result.get("working_dir", ""),
                })
                await _emit_current_pipeline_progress(deps, batch_id)
                logger.info("[TaskRunner] ✅ %s → SUCCESS (codemaker)", label)
            else:
                await deps.scheduler.on_task_completed(task["id"], success=False, error={
                    "runner": result.get("runner", "codemaker_skill"),
                    "error": result.get("error", "Unknown error"),
                    "session_id": result.get("session_id", ""),
                    "working_dir": result.get("working_dir", ""),
                })
                task = {**task, "status": TaskStatus.BLOCKED.value, "error": result, "completed_at": now_iso()}
                logger.warning("[TaskRunner] ❌ %s → FAILED (codemaker): %s", label, result.get("error", ""))
                await deps.emit_task_event("task.blocked", batch_id, task, {
                    "task_type": task_type,
                    "task_label": label,
                    "runner": result.get("runner", "codemaker_skill"),
                    "error": result.get("error", ""),
                    "working_dir": result.get("working_dir", ""),
                })
                await _emit_current_pipeline_progress(deps, batch_id)
            return

        if task_type in UNSUPPORTED_REAL_TASK_TYPES:
            if task_type in OPTIONAL_UNSUPPORTED_REAL_TASK_TYPES:
                result = {
                    "success": True,
                    "skipped": True,
                    "runner": "task_runner_optional_skip",
                    "task_type": task_type,
                    "reason": "productive_executor_not_registered",
                    "summary": f"Optional node {task_type} skipped: no productive executor registered.",
                }
                await deps.scheduler.on_task_completed(task["id"], success=True, result=result)
                if task_run:
                    await deps.db.complete_task_run(task_run["id"], success=True, result=result)
                task = {**task, "status": TaskStatus.SUCCESS.value, "result": result, "completed_at": now_iso()}
                logger.info("[TaskRunner] ⏭ %s → SUCCESS (optional unsupported node skipped)", label)
                await deps.emit_task_event("task.completed", batch_id, task, {
                    "task_type": task_type,
                    "task_label": label,
                    "runner": result["runner"],
                    "skipped": True,
                    "reason": result["reason"],
                })
                await _emit_current_pipeline_progress(deps, batch_id)
                return
            raise RuntimeError(
                f"Task {task_type} is present in DAG, but no productive executor is registered yet. "
                "Remote iOS Agent / workspace sync / result callback is still required."
            )

        raise RuntimeError(f"No productive executor registered for task type: {task_type}")

    except Exception as exc:
        logger.exception("[TaskRunner] %s → BLOCKED: %s", label, exc)
        error_result = {
            "runner": "task_runner",
            "error": str(exc),
        }
        await deps.scheduler.on_task_completed(task["id"], success=False, error=error_result)
        if task_run:
            try:
                await deps.db.complete_task_run(task_run["id"], success=False, error=error_result)
            except Exception:
                logger.exception("[TaskRunner] %s: TaskRun 失败状态持久化失败", label)
        task = {**task, "status": TaskStatus.BLOCKED.value, "error": error_result, "completed_at": now_iso()}
        await deps.emit_task_event("task.blocked", batch_id, task, {
            "task_type": task_type,
            "task_label": label,
            "runner": "task_runner",
            "error": str(exc),
        })
        await _emit_current_pipeline_progress(deps, batch_id)


async def productive_task_runner(
    batch_id: str,
    deps: TaskRunnerDependencies,
    config: Optional[TaskRunnerConfig] = None,
) -> None:
    """Run queued DAG tasks using injected dependencies."""
    runner_config = config or TaskRunnerConfig()
    node_mock_types = set(runner_config.mock_task_types)
    logger.info(
        "[TaskRunner] 启动: batch=%s, codemaker=%s, node_mocks=%s",
        batch_id[:16], "yes" if runner_config.codemaker_config else "no", ",".join(sorted(node_mock_types)) or "none",
    )

    running_tasks: set[asyncio.Task] = set()

    def _on_task_done(done_task: asyncio.Task) -> None:
        running_tasks.discard(done_task)
        try:
            done_task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("[TaskRunner] 后台任务泄漏异常")

    try:
        tick = 0
        while True:
            tick += 1
            if deps.scheduler.is_paused:
                await asyncio.sleep(runner_config.poll_interval)
                continue

            await asyncio.sleep(runner_config.poll_interval)
            batch = await deps.db.get_batch(batch_id)
            if not batch:
                logger.warning("[TaskRunner] batch 不存在: %s", batch_id)
                break
            if batch["status"] in (BatchStatus.COMPLETED.value, BatchStatus.FAILED.value, BatchStatus.BLOCKED.value):
                if running_tasks:
                    logger.info(
                        "[TaskRunner] Batch %s 已结束但仍有 %d 个后台任务，等待其自然收尾",
                        batch_id[:16], len(running_tasks),
                    )
                else:
                    logger.info("[TaskRunner] Batch %s 已结束: %s", batch_id[:16], batch["status"])
                    break

            tasks = await deps.db.get_tasks_by_batch(batch_id)
            running_ids = {
                getattr(task, "_cubeclaw_task_id", "")
                for task in running_tasks
            }
            queued = [
                t for t in tasks
                if t["status"] == TaskStatus.QUEUED.value and t["id"] not in running_ids
            ]
            if queued:
                labels = [_task_label(t) for t in queued]
                logger.info("[TaskRunner] Tick %d: 启动 %d 个任务 [%s]", tick, len(queued), ", ".join(labels))
                for queued_task in queued:
                    task_future = asyncio.create_task(
                        _run_single_productive_task(queued_task, batch_id, deps, runner_config)
                    )
                    setattr(task_future, "_cubeclaw_task_id", queued_task["id"])
                    task_future.add_done_callback(_on_task_done)
                    running_tasks.add(task_future)

            # Re-read after launching queued tasks: short manager/mock nodes may have
            # already completed and unlocked successors before this tick reaches the
            # idle/block checks below.  Using the pre-launch snapshot here can
            # incorrectly conclude "no queued/running work" or emit stale RUNNING
            # PipelineRun data.
            tasks = await deps.db.get_tasks_by_batch(batch_id)
            running_ids = {
                getattr(task, "_cubeclaw_task_id", "")
                for task in running_tasks
            }
            queued = [
                t for t in tasks
                if t["status"] == TaskStatus.QUEUED.value and t["id"] not in running_ids
            ]

            pending = [t for t in tasks if t["status"] == TaskStatus.PENDING.value]
            running_db = [
                t for t in tasks
                if t["status"] in (TaskStatus.ASSIGNED.value, TaskStatus.RUNNING.value)
                and t["id"] not in running_ids
            ]
            blocked = [t for t in tasks if t["status"] == TaskStatus.BLOCKED.value]
            if not queued:
                reachable_pending = _has_reachable_pending_work(tasks)
                if blocked and not reachable_pending and not running_db and not running_tasks:
                    await deps.db.update_batch_status(batch_id, BatchStatus.BLOCKED.value)
                    logger.warning(
                        "[TaskRunner] Batch %s BLOCKED: no queued/running/reachable pending work remains; blocked=%d pending=%d",
                        batch_id[:16], len(blocked), len(pending),
                    )
                    await deps.emit_pipeline_progress(batch_id)
                    break
                if blocked and reachable_pending:
                    logger.info(
                        "[TaskRunner] Batch %s has %d blocked task(s), but reachable pending DAG work remains; continue",
                        batch_id[:16], len(blocked),
                    )
                if not pending and not running_db and not running_tasks:
                    logger.info("[TaskRunner] Batch %s 无可执行任务，结束 runner", batch_id[:16])
                    break

            # 注意: 这里故意不再做 "每 tick 都 emit pipeline_run.progress" 兜底。
            # 真实状态变化（task RUNNING/SUCCESS/BLOCKED、batch 终态）已在 _run_single_productive_task
            # 与上面的 BLOCKED 分支显式 emit 过；定时无脑 emit 会让 EventBus 把同一份完整
            # PipelineRun snapshot（含全部 node_runs）反复写入 event_logs，把审计日志刷爆。
            # SSE 通道由 controller 层的 15s heartbeat 保活，前端不会断流。

    except asyncio.CancelledError:
        logger.info("[TaskRunner] 被取消: batch=%s", batch_id[:16])
        for task in list(running_tasks):
            task.cancel()
        if running_tasks:
            await asyncio.gather(*running_tasks, return_exceptions=True)
    except Exception:
        logger.exception("[TaskRunner] 异常: batch=%s", batch_id[:16])

    logger.info("[TaskRunner] 结束: batch=%s", batch_id[:16])
