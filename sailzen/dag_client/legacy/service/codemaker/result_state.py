"""session_result and retry helpers for Codemaker DAG runs."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from sail.opencode.client import OpencodeAsyncClient

from bot_server.models import TaskRunStatus

from .base import load_session_result, validate_session_result
from .process_manager import AUTOMATION_CONTINUE_PROMPT

logger = logging.getLogger(__name__)


def background_tasks_active(data: Dict[str, Any]) -> bool:
    """Return whether session_result declares unfinished background work."""
    background = data.get("background_tasks")
    if isinstance(background, dict):
        if background.get("active") is True:
            return True
        try:
            if int(background.get("pending_count") or 0) > 0:
                return True
        except (TypeError, ValueError):
            pass
    for key in ("background_tasks_active", "has_background_tasks", "pending_background_tasks"):
        value = data.get(key)
        if value is True:
            return True
        if isinstance(value, int) and value > 0:
            return True
    return False


async def load_session_result_if_exists(path_value: str) -> Dict[str, Any]:
    if not path_value or not Path(path_value).exists():
        return {}
    try:
        return load_session_result(path_value)
    except Exception:
        return {}


def build_retry_prompt_prefix(*, task: dict, previous_runs: list[dict], current_attempt: int) -> str:
    """Build retry context injected before skill prompt."""
    failed_runs = [
        run for run in previous_runs
        if str(run.get("status") or "") != TaskRunStatus.SUCCESS.value
    ]
    if current_attempt <= 1 and not failed_runs:
        return ""

    latest = previous_runs[-1] if previous_runs else {}
    latest_result = latest.get("result") or {}
    latest_error = (
        latest_result.get("error") if isinstance(latest_result, dict) else None
    ) or latest.get("error")
    latest_session_result = (
        latest_result.get("session_result") if isinstance(latest_result, dict) else None
    )
    latest_text = latest_result.get("text_response") if isinstance(latest_result, dict) else ""
    context = {
        "task_id": task.get("id"),
        "task_type": task.get("type"),
        "current_attempt": current_attempt,
        "previous_attempt_count": len(previous_runs),
        "latest_failed_run": {
            "run_id": latest.get("id"),
            "attempt": latest.get("attempt"),
            "status": latest.get("status"),
            "runner": latest.get("runner"),
            "session_id": latest.get("session_id"),
            "transcript_path": latest.get("transcript_path"),
            "error": latest_error,
            "session_result": latest_session_result,
            "text_response": latest_text,
        },
        "all_previous_runs": [
            {
                "run_id": run.get("id"),
                "attempt": run.get("attempt"),
                "status": run.get("status"),
                "runner": run.get("runner"),
                "session_id": run.get("session_id"),
                "transcript_path": run.get("transcript_path"),
                "error": run.get("error"),
            }
            for run in previous_runs
        ],
    }
    return (
        "\n【重试任务上下文 / Retry Context】\n"
        f"这是同一个 DAG Task 的第 {current_attempt} 次运行。前序运行因为异常/失败未完成或被手动重试。\n"
        "不要把本次当成全新任务直接开干。请先做环境体检：确认当前工作目录、git 状态、分支、未提交变更、锁文件、临时结果文件、上次遗留进程/后台任务。\n"
        "先阅读下面的上次运行结果，总结已经完成的有效工作，复用可保留产物；不要删除有效进度。\n"
        "如果上次错误由环境未准备、目录错误、服务未启动、依赖缺失、session_result 未写最终态、后台任务未完成造成，本次必须先修复/规避这些问题，再继续主任务。\n"
        "前序运行摘要 JSON：\n"
        f"```json\n{json.dumps(context, ensure_ascii=False, indent=2, default=str)[:12000]}\n```\n"
        "【重试要求结束】\n\n"
    )


async def wait_for_background_session_result(
    *,
    client_host: str,
    client_port: int,
    session_id: str,
    session_result_path: str,
    expected_session_result: Dict[str, Any],
    task_label: str,
    sse_timeout: float,
    already_waited: float,
) -> tuple[Dict[str, Any], bool, str]:
    """Wait for running session_result while declared background work exists."""
    deadline = time.time() + max(0.0, float(sse_timeout) - already_waited)
    poll_interval = 15.0
    reminder_interval = 120.0
    missing_file_grace = 30.0
    last_reminder = 0.0
    last_status = ""
    missing_since: Optional[float] = None
    last_running_fingerprint = ""

    async with OpencodeAsyncClient(host=client_host, port=client_port) as client:
        while time.time() < deadline:
            data = await load_session_result_if_exists(session_result_path)
            if not data:
                now = time.time()
                if missing_since is None:
                    missing_since = now
                elif now - missing_since >= missing_file_grace:
                    return {}, False, (
                        "foreground 已结束，但 session_result.json 在宽限期内仍不存在；"
                        "无法确认后台任务仍在运行"
                    )
                await asyncio.sleep(poll_interval)
                continue

            missing_since = None
            status = str(data.get("status", "")).lower()
            valid, reason = validate_session_result(data, expected_session_result)
            if valid:
                return data, True, "final session_result observed while waiting for running task"
            if status != "running":
                return data, False, reason

            background = data.get("background_tasks") or {}
            declared_active = background_tasks_active(data)
            running_fingerprint = json.dumps(
                {
                    "updated_at": data.get("updated_at"),
                    "summary": data.get("summary"),
                    "background_tasks": background,
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            progress_changed = bool(
                last_running_fingerprint
                and running_fingerprint != last_running_fingerprint
            )
            last_running_fingerprint = running_fingerprint
            progress = (
                f"status={status} active={declared_active} "
                f"progress_changed={progress_changed} "
                f"pending={background.get('pending_count', '?')} "
                f"desc={background.get('description', '') or background.get('phase', '')}"
            )
            if progress != last_status:
                logger.info(
                    "[CodemkrSkill] %s: session_result still running after foreground event: %s",
                    task_label,
                    progress,
                )
                last_status = progress

            now = time.time()
            if now - last_reminder >= reminder_interval:
                last_reminder = now
                try:
                    await client.send_prompt_async(session_id, AUTOMATION_CONTINUE_PROMPT)
                except Exception as exc:
                    logger.debug(
                        "[CodemkrSkill] %s: running-result keepalive prompt failed: %s",
                        task_label,
                        exc,
                    )

            await asyncio.sleep(poll_interval)

    data = await load_session_result_if_exists(session_result_path)
    return data, False, "等待 session_result.json 进入最终态超时"


def persist_recovered_session_result(path: str, data: Dict[str, Any]) -> tuple[bool, str]:
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with Path(path).open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        return True, ""
    except Exception as exc:
        return False, f"recovered session_result write failed: {exc}"
