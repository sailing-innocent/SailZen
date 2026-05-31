"""DAG-aware Codemaker task runner.

This module keeps bot_server orchestration concerns in one place while using
``sail.opencode`` for the actual Codemaker session lifecycle and SSE handling.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from sail.opencode.session_dependencies import default_dependencies
from sail.opencode.session_models import TaskResult, TaskRunConfig
from sail.opencode.session_runner import run_task
from sail.paths import path_under_data_dir

from bot_server.models import SessionStatus, TaskRunStatus, make_session, make_task_run, now_iso

from .base import (
    DEFAULT_AGENT_NAME,
    DEFAULT_CODEMAKER_HOST,
    DEFAULT_CODEMAKER_PORT,
    DEFAULT_MAX_RECONNECTS,
    build_expected_session_result,
    default_session_result_path,
    load_session_result,
    normalize_session_result_path,
    recover_review_session_result_if_possible,
    session_result_meta_path,
    session_result_prompt_prefix,
    short_task_id,
    skill_error_result,
    validate_session_result,
    write_session_result_meta,
)
from .process_manager import ensure_codemaker_for_workdir
from .result_state import (
    build_retry_prompt_prefix,
    persist_recovered_session_result,
    wait_for_background_session_result,
)
from .transcripts import archive_session_transcript

logger = logging.getLogger(__name__)


@dataclass
class CodemakerTaskContext:
    task_label: str
    task: dict
    db: Any
    codemaker_config: Dict[str, Any]
    skill_name: str
    runner_name: str
    prompt: str
    working_dir: str
    success_key: str
    sse_timeout: float
    extra_result: Dict[str, Any] = field(default_factory=dict)

    session_result_path: str = ""
    expected_session_result: Dict[str, Any] = field(default_factory=dict)
    previous_runs: list[dict] = field(default_factory=list)
    current_attempt: int = 1
    retry_prompt_injected: bool = False

    host: str = DEFAULT_CODEMAKER_HOST
    port: int = DEFAULT_CODEMAKER_PORT
    process_key: str = ""
    process_manager: Any = None
    process_config: Dict[str, Any] = field(default_factory=dict)

    task_run: Optional[Dict[str, Any]] = None
    session_row: Optional[Dict[str, Any]] = None
    session_final_persisted: bool = False
    session_id: str = ""
    final_result: Optional[Dict[str, Any]] = None


async def run_prompt_via_codemaker(
    *,
    task_label: str,
    task: dict,
    db,
    codemaker_config: Dict[str, Any],
    skill_name: str,
    runner_name: str,
    prompt: str,
    working_dir: str,
    success_key: str,
    sse_timeout: float,
    extra_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run a DAG Codemaker task through the shared sail.opencode session runner."""
    ctx = CodemakerTaskContext(
        task_label=task_label,
        task=task,
        db=db,
        codemaker_config=codemaker_config,
        skill_name=skill_name,
        runner_name=runner_name,
        prompt=prompt,
        working_dir=working_dir,
        success_key=success_key,
        sse_timeout=sse_timeout,
        extra_result=extra_result or {},
    )
    await _prepare_prompt_contract(ctx)
    await _create_starting_records(ctx)

    try:
        await _ensure_process(ctx)
        result = await _run_shared_session(ctx)
        ctx.session_id = result.session_id
        ctx.final_result = await _build_final_result(ctx, result)
        await _persist_final_records(ctx)
        await _archive_transcript_if_possible(ctx)
        return ctx.final_result
    except CodemakerRunFailed as exc:
        return exc.result
    finally:
        await _finalize_incomplete_records(ctx)
        await _cleanup_process(ctx)


def _initial_result_path(ctx: CodemakerTaskContext) -> str:
    return normalize_session_result_path(
        str(
            ctx.extra_result.get("session_result_path")
            or ctx.codemaker_config.get("session_result_path")
            or default_session_result_path(ctx.working_dir, ctx.task)
        ),
        ctx.working_dir,
    )


async def _prepare_prompt_contract(ctx: CodemakerTaskContext) -> None:
    ctx.session_result_path = _initial_result_path(ctx)
    ctx.current_attempt = int(ctx.task.get("retry_count") or 0) + 1
    try:
        ctx.previous_runs = await ctx.db.get_task_runs(ctx.task.get("id", ""))
        ctx.current_attempt = await ctx.db.next_task_run_attempt(ctx.task.get("id", ""))
    except Exception as exc:
        logger.warning("[CodemkrSkill] %s: 获取 TaskRun 历史失败: %s", ctx.task_label, exc)

    retry_prefix = build_retry_prompt_prefix(
        task=ctx.task,
        previous_runs=ctx.previous_runs,
        current_attempt=ctx.current_attempt,
    )
    ctx.retry_prompt_injected = bool(retry_prefix)
    if retry_prefix:
        ctx.prompt = retry_prefix + ctx.prompt

    ctx.expected_session_result = build_expected_session_result(
        task=ctx.task,
        task_label=ctx.task_label,
        skill_name=ctx.skill_name,
        runner_name=ctx.runner_name,
        working_dir=ctx.working_dir,
        session_result_path=ctx.session_result_path,
        extra_result=ctx.extra_result,
    )
    meta_path = session_result_meta_path(ctx.session_result_path)
    if meta_path:
        ctx.expected_session_result["session_result_meta_path"] = meta_path
        try:
            write_session_result_meta(meta_path, ctx.expected_session_result)
        except Exception as exc:
            logger.warning("[CodemkrSkill] %s: 写入 session_result meta 失败: %s", ctx.task_label, exc)
    ctx.prompt = session_result_prompt_prefix(ctx.expected_session_result) + ctx.prompt

    ctx.host = ctx.codemaker_config.get("host", DEFAULT_CODEMAKER_HOST)
    ctx.port = int(ctx.codemaker_config.get("port", DEFAULT_CODEMAKER_PORT))
    ctx.process_key = ctx.working_dir

    logger.info(
        "[CodemkrSkill] %s: skill=%s worktree=%s codemaker=%s:%d attempt=%d previous_runs=%d",
        ctx.task_label,
        ctx.skill_name,
        ctx.working_dir or "<codemaker-default-cwd>",
        ctx.host,
        ctx.port,
        ctx.current_attempt,
        len(ctx.previous_runs),
    )


async def _create_starting_records(ctx: CodemakerTaskContext) -> None:
    run_key = f"codemaker-attempt:{ctx.task.get('id', '')}:{ctx.runner_name}:{time.time_ns()}"
    try:
        ctx.task_run = make_task_run(
            task_id=ctx.task["id"],
            attempt=ctx.current_attempt,
            runner=ctx.runner_name,
            agent_id=f"codemaker:{ctx.host}:{ctx.port}:starting",
            session_key=run_key,
            prompt=ctx.prompt,
            context=_base_context(ctx, phase="starting"),
        )
        await ctx.db.create_task_run(ctx.task_run)
    except Exception as exc:
        logger.warning("[CodemkrSkill] %s: DBTaskRun 启动审计记录持久化失败: %s", ctx.task_label, exc)
        ctx.task_run = None

    try:
        ctx.session_row = make_session(
            task_id=ctx.task["id"],
            agent_id=f"codemaker:{ctx.host}:{ctx.port}:starting",
            session_key=run_key,
            skill=ctx.skill_name,
            working_dir=ctx.working_dir,
            context={"prompt": ctx.prompt, **_base_context(ctx, phase="starting")},
        )
        ctx.session_row["status"] = SessionStatus.STARTING.value
        await ctx.db.upsert_session(ctx.session_row)
    except Exception as exc:
        logger.warning("[CodemkrSkill] %s: DBSession 启动审计记录持久化失败: %s", ctx.task_label, exc)
        ctx.session_row = None


def _base_context(ctx: CodemakerTaskContext, *, phase: str) -> Dict[str, Any]:
    return {
        "skill": ctx.skill_name,
        "runner": ctx.runner_name,
        "working_dir": ctx.working_dir,
        "host": ctx.host,
        "port": ctx.port,
        "phase": phase,
        "session_result_path": ctx.session_result_path,
        "expected_session_result": ctx.expected_session_result,
        "previous_runs": ctx.previous_runs,
        "retry_prompt_injected": ctx.retry_prompt_injected,
    }


async def _ensure_process(ctx: CodemakerTaskContext) -> None:
    config = await ensure_codemaker_for_workdir(
        working_dir=ctx.working_dir,
        codemaker_config={
            **ctx.codemaker_config,
            "task_id": ctx.task.get("id", ""),
            "task_id_short": short_task_id(ctx.task),
        },
    )
    ctx.process_config = config
    ctx.host = config.get("host", DEFAULT_CODEMAKER_HOST)
    ctx.port = int(config.get("port", DEFAULT_CODEMAKER_PORT))
    ctx.process_key = config.get("codemaker_process_key") or ctx.working_dir
    ctx.process_manager = config.get("_codemaker_process_manager")
    await _persist_process_ready(ctx)


async def _persist_process_ready(ctx: CodemakerTaskContext) -> None:
    context_patch = {
        "host": ctx.host,
        "port": ctx.port,
        "codemaker_pid": ctx.process_config.get("codemaker_pid"),
        "codemaker_process_key": ctx.process_key,
        "phase": "process_ready",
    }
    if ctx.session_row:
        try:
            ctx.session_row["agent_id"] = f"codemaker:{ctx.host}:{ctx.port}"
            ctx.session_row["status"] = SessionStatus.RUNNING.value
            ctx.session_row["last_activity_at"] = now_iso()
            ctx.session_row["context"] = {**(ctx.session_row.get("context") or {}), **context_patch}
            await ctx.db.upsert_session(ctx.session_row)
        except Exception as exc:
            logger.warning("[CodemkrSkill] %s: DBSession 进程就绪状态持久化失败: %s", ctx.task_label, exc)

    if ctx.task_run:
        try:
            ctx.task_run["agent_id"] = f"codemaker:{ctx.host}:{ctx.port}"
            ctx.task_run["status"] = TaskRunStatus.RUNNING.value
            ctx.task_run["last_activity_at"] = now_iso()
            ctx.task_run["context"] = {**(ctx.task_run.get("context") or {}), **context_patch}
            await ctx.db.update_task_run(
                ctx.task_run["id"],
                agent_id=ctx.task_run["agent_id"],
                status=ctx.task_run["status"],
                last_activity_at=ctx.task_run["last_activity_at"],
                context=ctx.task_run["context"],
            )
        except Exception as exc:
            logger.warning("[CodemkrSkill] %s: DBTaskRun 进程就绪状态持久化失败: %s", ctx.task_label, exc)


async def _run_shared_session(ctx: CodemakerTaskContext) -> TaskResult:
    config = TaskRunConfig(
        host=ctx.host,
        port=ctx.port,
        agent=ctx.process_config.get("agent", DEFAULT_AGENT_NAME),
        session_title=f"CubeClaw {ctx.skill_name} {ctx.task.get('id', '')[:8]} run#{ctx.current_attempt}",
        sse_timeout=ctx.sse_timeout,
        max_reconnects=DEFAULT_MAX_RECONNECTS,
        poll_fallback=False,
        finish_on_session_idle=True,
        finish_on_terminal_step=True,
        delayed_finish_heartbeat_sec=float(ctx.codemaker_config.get("delayed_finish_heartbeat_sec", 300.0)),
        delayed_finish_max_heartbeats=int(ctx.codemaker_config.get("delayed_finish_max_heartbeats", 3)),
        delayed_finish_heartbeat_prompt=ctx.codemaker_config.get(
            "delayed_finish_heartbeat_prompt",
            "后台任务可能已经完成但前台未继续接管。请检查后台/sub-agent/tool 结果，继续当前任务；如果任务完成，请写入最终 session_result.json。",
        ),
    )
    deps = default_dependencies()
    deps.can_finish_foreground = lambda: _foreground_finish_allowed(ctx)
    result = await run_task(
        prompt=ctx.prompt,
        config=config,
        label=ctx.task_label,
        dependencies=deps,
    )
    if result.session_id:
        await _persist_session_created(ctx, result.session_id)
    if not result.success:
        ctx.final_result = skill_error_result(
            result.error or "Codemaker task failed",
            session_id=result.session_id,
            runner=ctx.runner_name,
        )
        raise CodemakerRunFailed(ctx.final_result)
    return result


def _foreground_finish_allowed(ctx: CodemakerTaskContext) -> bool:
    data = _load_session_result_silent(ctx.session_result_path)
    if not data:
        return True
    status = str(data.get("status", "")).lower()
    if status != "running":
        return True
    background = data.get("background_tasks") or {}
    try:
        pending = int(background.get("pending_count") or 0)
    except (TypeError, ValueError):
        pending = 0
    active = bool(background.get("active")) or pending > 0
    if active:
        logger.info(
            "[CodemkrSkill] %s: foreground terminate ignored; background still active pending=%s desc=%s",
            ctx.task_label,
            pending,
            background.get("description", "") or background.get("phase", ""),
        )
    return not active


async def _persist_session_created(ctx: CodemakerTaskContext, session_id: str) -> None:
    ctx.session_id = session_id
    context_patch = {
        "host": ctx.host,
        "port": ctx.port,
        "codemaker_pid": ctx.process_config.get("codemaker_pid"),
        "codemaker_process_key": ctx.process_key,
        "session_result_path": ctx.session_result_path,
        "expected_session_result": ctx.expected_session_result,
        "phase": "session_created",
    }
    if ctx.task_run:
        try:
            ctx.task_run.update({
                "agent_id": f"codemaker:{ctx.host}:{ctx.port}",
                "session_id": session_id,
                "session_key": session_id,
                "status": TaskRunStatus.RUNNING.value,
                "last_activity_at": now_iso(),
                "context": {**(ctx.task_run.get("context") or {}), **context_patch},
            })
            await ctx.db.update_task_run(
                ctx.task_run["id"],
                agent_id=ctx.task_run["agent_id"],
                session_id=ctx.task_run["session_id"],
                session_key=ctx.task_run["session_key"],
                status=ctx.task_run["status"],
                context=ctx.task_run["context"],
                last_activity_at=ctx.task_run["last_activity_at"],
            )
        except Exception as exc:
            logger.warning("[CodemkrSkill] %s: DBTaskRun session 状态持久化失败: %s", ctx.task_label, exc)

    if ctx.session_row:
        try:
            ctx.session_row.update({
                "agent_id": f"codemaker:{ctx.host}:{ctx.port}",
                "session_key": session_id,
                "skill": ctx.skill_name,
                "working_dir": ctx.working_dir,
                "status": SessionStatus.RUNNING.value,
                "last_activity_at": now_iso(),
                "context": {
                    **(ctx.session_row.get("context") or {}),
                    "prompt": ctx.prompt,
                    **context_patch,
                },
            })
            await ctx.db.upsert_session(ctx.session_row)
        except Exception as exc:
            logger.warning("[CodemkrSkill] %s: DBSession 持久化失败: %s", ctx.task_label, exc)


async def _build_final_result(ctx: CodemakerTaskContext, task_result: TaskResult) -> Dict[str, Any]:
    session_result_data = await _load_and_validate_session_result(ctx, task_result)
    session_result_valid, session_result_error = validate_session_result(
        session_result_data,
        ctx.expected_session_result,
    )
    if not session_result_valid:
        recovered_data, recovered, recovered_reason = recover_review_session_result_if_possible(
            session_result_data,
            ctx.expected_session_result,
        )
        if recovered:
            session_result_data = recovered_data
            session_result_valid, session_result_error = validate_session_result(
                session_result_data,
                ctx.expected_session_result,
            )
            if session_result_valid:
                ok, write_error = persist_recovered_session_result(
                    ctx.session_result_path,
                    session_result_data,
                )
                if ok:
                    logger.info("[CodemkrSkill] %s: session_result recovered: %s", ctx.task_label, recovered_reason)
                else:
                    session_result_valid = False
                    session_result_error = write_error

    skill_success = bool(
        session_result_valid
        and session_result_data.get("success")
        and str(session_result_data.get("status", "")).lower() in ("success", "skipped")
    )
    final = {
        "success": skill_success,
        "runner": ctx.runner_name,
        ctx.success_key: skill_success,
        "skill": ctx.skill_name,
        "working_dir": ctx.working_dir,
        "session_id": task_result.session_id,
        "finish_reason": task_result.finish_reason,
        "text_response": task_result.text[:2000],
        "tool_calls": task_result.tool_calls[-20:],
        "tool_count": len(task_result.tool_calls),
        "sse_finished": task_result.success,
        "session_result_path": ctx.session_result_path,
        "session_result_valid": session_result_valid,
        "session_result": session_result_data,
        **ctx.extra_result,
    }
    _attach_result_error(final, session_result_data, session_result_valid, session_result_error, ctx.success_key)
    logger.info(
        "[CodemkrSkill] %s: 任务结束 success=%s finish_reason=%s session_result_valid=%s error=%s",
        ctx.task_label,
        skill_success,
        task_result.finish_reason,
        session_result_valid,
        final.get("error", ""),
    )
    return final


async def _load_and_validate_session_result(
    ctx: CodemakerTaskContext,
    task_result: TaskResult,
) -> Dict[str, Any]:
    data = _load_session_result_silent(ctx.session_result_path)
    if data and str(data.get("status", "")).lower() == "running":
        logger.info(
            "[CodemkrSkill] %s: run_task returned with running session_result (%s); wait for final state",
            ctx.task_label,
            task_result.finish_reason,
        )
        waited_data, waited_valid, waited_reason = await wait_for_background_session_result(
            client_host=ctx.host,
            client_port=ctx.port,
            session_id=task_result.session_id,
            session_result_path=ctx.session_result_path,
            expected_session_result=ctx.expected_session_result,
            task_label=ctx.task_label,
            sse_timeout=ctx.sse_timeout,
            already_waited=task_result.elapsed_sec,
        )
        if waited_data:
            data = waited_data
        if waited_valid:
            logger.info("[CodemkrSkill] %s: background session_result completed", ctx.task_label)
        else:
            logger.warning("[CodemkrSkill] %s: background wait ended before final result: %s", ctx.task_label, waited_reason)
    if data:
        return data
    try:
        return load_session_result(ctx.session_result_path)
    except Exception as exc:
        logger.warning("[CodemkrSkill] %s: session_result.json 加载失败: %s", ctx.task_label, exc)
        return {}


def _load_session_result_silent(path: str) -> Dict[str, Any]:
    try:
        return load_session_result(path)
    except Exception:
        return {}


def _attach_result_error(
    final: Dict[str, Any],
    data: Dict[str, Any],
    valid: bool,
    validation_error: str,
    success_key: str,
) -> None:
    if not valid and str(data.get("status", "")).lower() == "running":
        background = data.get("background_tasks") or {}
        active = bool(background.get("active")) or int(background.get("pending_count") or 0) > 0
        final["error"] = (
            "任务仍在运行，session_result.json 尚未进入最终态: "
            f"active={active} pending={background.get('pending_count', '?')} "
            f"description={background.get('description', '') or background.get('phase', '')}"
        )
        final["background_tasks_active"] = active
        final["session_result_still_running"] = True
    elif not valid:
        final["success"] = False
        final[success_key] = False
        final["error"] = f"session_result.json 校验失败: {validation_error}"
    elif not final["success"]:
        final["error"] = (
            data.get("error")
            or data.get("blocked_reason")
            or f"skill reported status={data.get('status')} success={data.get('success')}"
        )


async def _persist_final_records(ctx: CodemakerTaskContext) -> None:
    if ctx.task_run:
        try:
            await ctx.db.complete_task_run(
                ctx.task_run["id"],
                success=bool(ctx.final_result.get("success")),
                result=ctx.final_result,
                error=ctx.final_result.get("error"),
            )
        except Exception as exc:
            logger.warning("[CodemkrSkill] %s: DBTaskRun 完成状态持久化失败: %s", ctx.task_label, exc)

    if ctx.session_row:
        try:
            ctx.session_row["status"] = SessionStatus.COMPLETED.value if ctx.final_result.get("success") else SessionStatus.FAILED.value
            ctx.session_row["result"] = ctx.final_result
            ctx.session_row["completed_at"] = now_iso()
            ctx.session_row["last_activity_at"] = now_iso()
            await ctx.db.upsert_session(ctx.session_row)
            ctx.session_final_persisted = True
        except Exception as exc:
            logger.warning("[CodemkrSkill] %s: DBSession 完成状态持久化失败: %s", ctx.task_label, exc)


async def _archive_transcript_if_possible(ctx: CodemakerTaskContext) -> None:
    if not ctx.session_id or not ctx.final_result:
        return
    from sail.opencode.client import OpencodeAsyncClient

    transcript_dir = str(path_under_data_dir(ctx.process_config.get("transcript_dir", "transcripts")))
    try:
        async with OpencodeAsyncClient(
            host=ctx.host,
            port=ctx.port,
            timeout=float(ctx.process_config.get("http_timeout", 120.0)),
        ) as client:
            transcript_path = await archive_session_transcript(
                client,
                ctx.session_id,
                ctx.task_label,
                task_id=ctx.task.get("id", ""),
                task_type=ctx.task.get("type", ""),
                transcript_dir=transcript_dir,
            )
    except Exception as exc:
        logger.warning("[CodemkrSkill] %s: transcript 归档失败: %s", ctx.task_label, exc)
        return
    if not transcript_path:
        return
    ctx.final_result["transcript_path"] = transcript_path
    if ctx.task_run:
        try:
            await ctx.db.update_task_run(
                ctx.task_run["id"],
                transcript_path=transcript_path,
                result=ctx.final_result,
            )
        except Exception as exc:
            logger.warning("[CodemkrSkill] %s: DBTaskRun transcript 路径持久化失败: %s", ctx.task_label, exc)


async def _finalize_incomplete_records(ctx: CodemakerTaskContext) -> None:
    if isinstance(ctx.final_result, dict) and ctx.final_result.get("success") is False:
        await _persist_final_records(ctx)
    if ctx.session_row and ctx.final_result and not ctx.session_final_persisted:
        try:
            ctx.session_row["status"] = SessionStatus.COMPLETED.value if ctx.final_result.get("success") else SessionStatus.FAILED.value
            ctx.session_row["result"] = ctx.final_result
            ctx.session_row["completed_at"] = now_iso()
            ctx.session_row["last_activity_at"] = now_iso()
            context = ctx.session_row.get("context") or {}
            ctx.session_row["context"] = {**context, "phase": "failed_before_normal_completion"}
            await ctx.db.upsert_session(ctx.session_row)
            ctx.session_final_persisted = True
        except Exception as exc:
            logger.warning("[CodemkrSkill] %s: DBSession 异常退出状态持久化失败: %s", ctx.task_label, exc)


async def _cleanup_process(ctx: CodemakerTaskContext) -> None:
    if not ctx.process_manager or not ctx.process_key:
        return
    try:
        ok, msg = await ctx.process_manager.stop_async(ctx.process_key)
        logger.info(
            "[CodemkrSkill] %s: Codemaker process cleanup key=%s ok=%s msg=%s",
            ctx.task_label,
            ctx.process_key,
            ok,
            msg,
        )
    except Exception as exc:
        logger.warning("[CodemkrSkill] %s: Codemaker process cleanup failed: %s", ctx.task_label, exc)


class CodemakerRunFailed(Exception):
    def __init__(self, result: Dict[str, Any]) -> None:
        super().__init__(result.get("error") or "Codemaker run failed")
        self.result = result
