"""Task Controller — /tasks 端点。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List

from litestar import get, post
from litestar.response import Response

from bot_server.deps import get_bus, get_db
from sail.dag.command_bus import Command, Source, Role
from sail.paths import path_under_data_dir


def _dash_cmd(name: str, **args) -> Command:
    return Command(name=name, args=args, source=Source.DASHBOARD,
                   actor="dashboard", role=Role.ADMIN)


def _safe_json_load(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _transcript_dirs() -> list[Path]:
    """返回 transcript 搜索目录，优先使用配置数据目录。"""
    dirs: list[Path] = []
    configured = os.environ.get("CUBECLAW_TRANSCRIPT_DIR", "")
    if configured:
        dirs.append(Path(configured))
    dirs.append(path_under_data_dir("transcripts"))

    unique: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        key = str(d.resolve()) if d.exists() else str(d)
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def _find_transcript_archive(task_id: str, sessions: list[dict]) -> tuple[dict[str, Any] | None, str | None, list[dict[str, Any]]]:
    """按 task_id / session_id 在 data/transcripts 中寻找归档文件。"""
    short = task_id[:8]
    session_ids = {str(s.get("id") or "") for s in sessions if s.get("id")}
    candidates: list[dict[str, Any]] = []

    for transcript_dir in _transcript_dirs():
        if not transcript_dir.exists():
            continue
        for path in transcript_dir.glob("*.json"):
            if short and short not in path.name and not any(sid[:12] in path.name for sid in session_ids if sid):
                continue
            data = _safe_json_load(path)
            if not data:
                continue
            archive_task_id = str(data.get("task_id") or "")
            archive_session_id = str(data.get("session_id") or "")
            exact_task = archive_task_id == task_id or archive_task_id.startswith(short)
            exact_session = archive_session_id in session_ids if archive_session_id else False
            if not exact_task and not exact_session:
                continue
            stat = path.stat()
            candidates.append({
                "path": str(path),
                "task_id": archive_task_id,
                "task_type": data.get("task_type"),
                "task_label": data.get("task_label"),
                "session_id": archive_session_id,
                "archived_at": data.get("archived_at"),
                "message_count": (data.get("summary") or {}).get("message_count"),
                "subagent_session_count": (data.get("summary") or {}).get("subagent_session_count"),
                "size_bytes": stat.st_size,
                "mtime": stat.st_mtime,
                "_archive": data,
            })

    candidates.sort(key=lambda c: (str(c.get("archived_at") or ""), float(c.get("mtime") or 0)), reverse=True)
    if not candidates:
        return None, None, []

    chosen = candidates[0]
    archive = chosen.pop("_archive", None)
    public_candidates = []
    for c in candidates:
        c = dict(c)
        c.pop("_archive", None)
        c.pop("mtime", None)
        public_candidates.append(c)
    return archive, str(chosen.get("path")), public_candidates


def _find_transcript_archive_by_session(session_id: str) -> tuple[dict[str, Any] | None, str | None, list[dict[str, Any]]]:
    if not session_id:
        return None, None, []
    return _find_transcript_archive("", [{"id": session_id}])


def _attach_transcripts_to_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for run in runs:
        item = dict(run)
        archive = None
        path = item.get("transcript_path")
        if path:
            archive = _safe_json_load(Path(str(path)))
        if not archive and item.get("session_id"):
            archive, path, candidates = _find_transcript_archive_by_session(str(item.get("session_id") or ""))
            item["transcript_candidates"] = candidates
        item["transcript_path"] = str(path) if path else None
        item["transcript_found"] = archive is not None
        item["transcript"] = archive
        enriched.append(item)
    return enriched


@get("/tasks")
async def list_tasks(sub_batch_id: str = "", status: str = "",
                     type: str = "") -> List[dict]:
    result = await get_bus().dispatch(
        _dash_cmd("list_tasks", sub_batch_id=sub_batch_id,
                  status=status, type=type))
    return result.data or []


@get("/tasks/{task_id:str}")
async def get_task(task_id: str) -> Response:
    result = await get_bus().dispatch(_dash_cmd("get_task", task_id=task_id))
    if result.success:
        return Response(result.data, text=f"Task {result.data['type']} [{result.data['status']}]")
    return Response({"error": result.error}, status_code=404)


@get("/tasks/{task_id:str}/detail")
async def get_task_detail(task_id: str) -> Response:
    """返回 Task 审阅详情：DB task、sessions、event logs、完整 transcript archive。"""
    db = get_db()
    task = await db.get_task(task_id)
    if not task:
        return Response({"error": "Task 不存在"}, status_code=404)

    sessions = await db.get_sessions(task_id)
    runs = await db.get_task_runs(task_id)
    task_runs = _attach_transcripts_to_runs(runs)
    events = await db.get_event_logs(entity_type="task", entity_id=task_id, limit=200)
    archive, transcript_path, candidates = _find_transcript_archive(task_id, sessions)

    return Response({
        "task": task,
        "runs": task_runs,
        "sessions": sessions,
        "events": events,
        "transcript_path": transcript_path,
        "transcript_found": archive is not None,
        "transcript_candidates": candidates,
        "transcript": archive,
    })


@post("/tasks/{task_id:str}/complete")
async def complete_task(task_id: str, data: dict) -> Response:
    result = await get_bus().dispatch(_dash_cmd(
        "complete_task", task_id=task_id, **data))
    return Response({"ok": result.success, "error": result.error})


@post("/tasks/{task_id:str}/retry")
async def retry_task(task_id: str) -> Response:
    result = await get_bus().dispatch(_dash_cmd("retry_task", task_id=task_id))
    return Response(result.data or {"ok": result.success})


@post("/tasks/{task_id:str}/resolve")
async def resolve_task(task_id: str) -> Response:
    result = await get_bus().dispatch(_dash_cmd("resolve_task", task_id=task_id))
    return Response({"ok": result.success})


@post("/tasks/{task_id:str}/skip")
async def skip_task(task_id: str) -> Response:
    result = await get_bus().dispatch(_dash_cmd("skip_task", task_id=task_id))
    return Response({"ok": result.success})
