"""Batch & SubBatch Controller — /batches, /sub_batches 端点。"""

from __future__ import annotations

import logging
from typing import List

from litestar import get, post
from litestar.response import Response

from bot_server.deps import get_bus, get_db
from bot_server.service.commit_analyzer import (
    analyze_commit_mappings,
    collect_evidence_paths,
    collect_review_findings,
    collect_conflict_subagent_links,
    get_commit_diff,
    get_commit_pair_diff,
    read_evidence_file_content,
    read_conflict_decision,
    read_conflict_agent_trace,
    _read_agent_session_log,  # for solve_session linkage
)
from bot_server.controller.task import _find_transcript_archive_by_session
from cube.command_bus import Command, Source, Role

logger = logging.getLogger(__name__)


def _dash_cmd(name: str, **args) -> Command:
    return Command(name=name, args=args, source=Source.DASHBOARD,
                   actor="dashboard", role=Role.ADMIN)


# ── Batches ─────────────────────────────────────────────────────────


@get("/batches")
async def list_batches(workspace_id: str = "", status: str = "",
                       lifecycle: str = "") -> List[dict]:
    result = await get_bus().dispatch(
        _dash_cmd("list_batches", workspace_id=workspace_id,
                  status=status, lifecycle=lifecycle))
    return result.data or []


@post("/batches")
async def create_batch(data: dict) -> Response:
    result = await get_bus().dispatch(_dash_cmd("create_batch", **data))
    if result.success:
        return Response(result.data, status_code=201)
    return Response({"error": result.error}, status_code=400)


@get("/batches/{batch_id:str}")
async def get_batch_detail(batch_id: str) -> Response:
    result = await get_bus().dispatch(_dash_cmd("get_batch", batch_id=batch_id))
    if result.success:
        return Response(result.data)
    return Response({"error": result.error}, status_code=404)


@post("/batches/{batch_id:str}/schedule")
async def schedule_batch(batch_id: str) -> Response:
    result = await get_bus().dispatch(_dash_cmd("schedule_batch", batch_id=batch_id))
    if result.success:
        return Response(result.data)
    return Response({"error": result.error}, status_code=400)


# ── SubBatches ──────────────────────────────────────────────────────


@get("/sub_batches")
async def list_sub_batches(batch_id: str = "") -> List[dict]:
    result = await get_bus().dispatch(
        _dash_cmd("list_sub_batches", batch_id=batch_id))
    return result.data or []


@get("/sub_batches/{sb_id:str}")
async def get_sub_batch(sb_id: str) -> Response:
    result = await get_bus().dispatch(_dash_cmd("get_sub_batch", sb_id=sb_id))
    if result.success:
        return Response(result.data)
    return Response({"error": result.error}, status_code=404)


# ── SubBatch Review (Pick Commit Map) ───────────────────────────────


@get("/sub_batches/{sb_id:str}/review")
async def get_sub_batch_review(sb_id: str) -> Response:
    """返回 SubBatch 的完整 pick review 数据包。

    Endpoint 对应前端 CommitReviewPage，包含:
      - commit 映射表 (source→target)
      - conflict evidence 路径
      - review findings
      - temp 目录路径
    """
    logger.info("[review] Request for sb_id=%s", sb_id)

    db = get_db()
    sb = await db.get_sub_batch(sb_id)
    if not sb:
        logger.warning("[review] SubBatch not found: %s", sb_id)
        return Response({"error": "SubBatch 不存在"}, status_code=404)

    logger.info("[review] SubBatch found: batch_id=%s commits=%d", sb.get("batch_id", ""), len(sb.get("commits") or []))

    batch = await db.get_batch(sb["batch_id"])
    if not batch:
        logger.warning("[review] Batch not found: %s", sb["batch_id"])
        return Response({"error": "Batch 不存在"}, status_code=404)

    config = batch.get("config") or {}
    workspace_paths = config.get("workspace_paths") or {}
    temp_dir = workspace_paths.get("temp_dir", "")
    repo_dir = workspace_paths.get("repo_dir") or workspace_paths.get("mcpe_gb_dir", "")
    logger.info("[review] temp_dir=%s repo_dir=%s", temp_dir, repo_dir)

    worktree_path = sb.get("worktree_path") or repo_dir
    if not worktree_path:
        return Response({"error": "worktree_path 和 repo_dir 均不可用"}, status_code=503)

    commits: List[str] = sb.get("commits") or []
    if not commits:
        return Response({"error": "SubBatch 无 commits"}, status_code=503)

    start_commit = commits[0]
    end_commit = commits[-1]
    branch_name = sb.get("branch_name", "")
    source_branch = batch.get("predecessor_branch", "main")

    # Calculate subbatch suffix
    subbatch_suffix = sb_id.split("_")[-1]
    branch_dance_state_dir = ""
    if temp_dir:
        from pathlib import Path
        branch_dance_state_dir = str(Path(temp_dir) / f"branch_dance_{subbatch_suffix}")

    # --- Analyze commit mappings ---
    logger.info("[review] analyze_commit_mappings start: repo=%s source=%s start=%s end=%s",
                worktree_path, source_branch, start_commit[:12], end_commit[:12])
    try:
        mappings, stats = analyze_commit_mappings(
            repo_path=worktree_path,
            batch_branch=branch_name,
            source_branch=source_branch,
            start_commit=start_commit,
            end_commit=end_commit,
            branch_dance_state_dir=branch_dance_state_dir,
        )
        logger.info("[review] analyze_commit_mappings done: mappings=%d stats=%s", len(mappings), stats)
    except Exception as e:
        logger.exception("[review] analyze_commit_mappings FAILED: %s", e)
        return Response({"error": str(e)}, status_code=500)

    # --- Collect evidence paths for all commits ---
    all_source_shas = [m["source_commit"]["hash"] for m in mappings]
    evidence_map = {}
    if branch_dance_state_dir:
        evidence_map = collect_evidence_paths(branch_dance_state_dir, all_source_shas)

    # --- Read agent_session.json for legacy solve_session linkage ---
    session_log_map = {}
    if branch_dance_state_dir:
        session_log_map = _read_agent_session_log(branch_dance_state_dir)
        logger.info("[review] session_log_map: %d entries", len(session_log_map))

    # --- Link conflict commits to LLM sub-agent decisions by task title convention ---
    transcript_path = ""
    conflict_agent_map = {}
    try:
        tasks = await db.get_tasks(sub_batch_id=sb_id, task_type="pick")
        pick_task = tasks[0] if tasks else None
        if pick_task:
            runs = await db.get_task_runs(pick_task["id"])
            for run in sorted(runs, key=lambda r: str(r.get("created_at") or ""), reverse=True):
                candidate = str(run.get("transcript_path") or "")
                if candidate:
                    transcript_path = candidate
                    break
        if transcript_path:
            conflict_agent_map = collect_conflict_subagent_links(transcript_path, all_source_shas)
            logger.info("[review] conflict_agent_map: %d commits from %s", len(conflict_agent_map), transcript_path)
    except Exception as e:
        logger.warning("[review] conflict sub-agent linkage failed: %s", e)

    # --- Collect review findings ---
    findings_map = {}
    if temp_dir:
        findings_map = collect_review_findings(temp_dir, subbatch_suffix, all_source_shas)

    # --- Enrich mappings with evidence and review findings ---
    for m in mappings:
        sha = m["source_commit"]["hash"]
        ev = evidence_map.get(sha)
        if ev and ev.get("path"):
            m["evidence"] = ev
            # If mapping has no conflict_files (agent_session doesn't store them),
            # copy from evidence discovery (on_conflict/ directory enumeration)
            if not m.get("conflict_files") and ev.get("conflict_files"):
                m["conflict_files"] = ev["conflict_files"]
        else:
            m["evidence"] = None

        f = findings_map.get(sha)
        m["review_findings"] = f if f else None

        # Prefer deterministic title-based linkage over legacy LLM-authored solve_session.
        links = conflict_agent_map.get(sha) or []
        sl = session_log_map.get(sha, {})
        m["conflict_agents"] = links
        if links:
            m["solve_session_id"] = links[0].get("session_id")
        elif sl.get("solve_session"):
            m["solve_session_id"] = sl["solve_session"]
        m["pick_status"] = sl.get("status")  # CLEAN / CONFLICT_RESOLVED / etc.

    # Build temp_paths
    evidence_dir = ""
    review_state_dir = ""
    if temp_dir:
        from pathlib import Path
        evidence_dir = str(Path(temp_dir) / f"branch_dance_{subbatch_suffix}" / "evidence")
        review_state_dir = str(Path(temp_dir) / f"review_{subbatch_suffix}_state")

    return Response({
        "sub_batch_id": sb_id,
        "batch_id": sb["batch_id"],
        "branch_name": branch_name,
        "source_branch": source_branch,
        "start_commit": start_commit,
        "end_commit": end_commit,
        "total": len(mappings),
        "stats": stats,
        "temp_paths": {
            "branch_dance_state_dir": branch_dance_state_dir,
            "evidence_dir": evidence_dir,
            "review_state_dir": review_state_dir,
            "transcript_path": transcript_path,
        },
        "mappings": mappings,
    })


@get("/sub_batches/{sb_id:str}/commits/{sha:str}/diff")
async def get_commit_diff_by_sha(sb_id: str, sha: str) -> Response:
    """返回指定 commit 的 source vs target diff。

    Query params:
      sha: source commit SHA (完整或缩写)
    """
    db = get_db()
    sb = await db.get_sub_batch(sb_id)
    if not sb:
        return Response({"error": "SubBatch 不存在"}, status_code=404)

    batch = await db.get_batch(sb["batch_id"])
    if not batch:
        return Response({"error": "Batch 不存在"}, status_code=404)

    config = batch.get("config") or {}
    workspace_paths = config.get("workspace_paths") or {}
    repo_dir = workspace_paths.get("repo_dir") or workspace_paths.get("mcpe_gb_dir", "")
    worktree_path = sb.get("worktree_path") or repo_dir

    if not worktree_path:
        return Response({"error": "worktree_path 不可用"}, status_code=503)

    # Get source diff
    source_diff = get_commit_diff(worktree_path, sha)

    # Find the cherry-picked target commit
    # We need to search the batch branch for a commit with cherry-pick origin = sha
    target_diff = []
    conflict_decision = None
    review_findings = None

    branch_name = sb.get("branch_name", "")
    if branch_name:
        try:
            # Search for cherry-picked commit
            import subprocess
            result = subprocess.run(
                ["git", "log", "--format=%H", "--grep", f"(cherry picked from commit {sha}", branch_name],
                cwd=worktree_path, capture_output=True, text=True, timeout=15,
            )
            target_shas = [h for h in result.stdout.strip().split("\n") if h]
            if target_shas:
                target_sha = target_shas[0]
                target_diff = get_commit_diff(worktree_path, target_sha)
        except Exception:
            pass

    # Read conflict decision
    subbatch_suffix = sb_id.split("_")[-1]
    if workspace_paths.get("temp_dir"):
        from pathlib import Path
        bd_state_dir = str(Path(workspace_paths["temp_dir"]) / f"branch_dance_{subbatch_suffix}")
        conflict_decision = read_conflict_decision(bd_state_dir, sha)

        # Read review findings
        findings_map = collect_review_findings(
            workspace_paths["temp_dir"], subbatch_suffix, [sha],
        )
        review_findings = findings_map.get(sha)

    return Response({
        "commit_sha": sha,
        "source_diff": source_diff,
        "target_diff": target_diff,
        "conflict_decision": conflict_decision,
        "review_findings": review_findings,
    })


@get("/sub_batches/{sb_id:str}/commits/{sha:str}/evidence")
async def get_commit_evidence_by_sha(sb_id: str, sha: str) -> Response:
    """返回指定冲突 commit 的 evidence 文件内容。

    读取 evidence/{sha}/ 下的 prev/, incoming/, local/, on_conflict/, resolved/ 文件。
    """
    db = get_db()
    sb = await db.get_sub_batch(sb_id)
    if not sb:
        return Response({"error": "SubBatch 不存在"}, status_code=404)

    batch = await db.get_batch(sb["batch_id"])
    if not batch:
        return Response({"error": "Batch 不存在"}, status_code=404)

    config = batch.get("config") or {}
    workspace_paths = config.get("workspace_paths") or {}
    temp_dir = workspace_paths.get("temp_dir", "")
    if not temp_dir:
        return Response({"error": "temp_dir 未配置"}, status_code=503)

    subbatch_suffix = sb_id.split("_")[-1]
    from pathlib import Path
    branch_dance_state_dir = str(Path(temp_dir) / f"branch_dance_{subbatch_suffix}")

    # Find evidence dir for this sha
    evidence_map = collect_evidence_paths(branch_dance_state_dir, [sha])
    ev = evidence_map.get(sha, {})
    evidence_dir = ev.get("path", "")
    conflict_files = ev.get("conflict_files", [])

    if not evidence_dir or not conflict_files:
        return Response({
            "commit_sha": sha,
            "files": [],
        })

    files = read_evidence_file_content(evidence_dir, conflict_files)
    return Response({
        "commit_sha": sha,
        "files": files,
    })


@get("/sub_batches/{sb_id:str}/commits/{sha:str}/agent_trace")
async def get_commit_agent_trace_by_sha(sb_id: str, sha: str) -> Response:
    """Return LLM sub-agent conflict decisions linked by conflict task title."""
    db = get_db()
    sb = await db.get_sub_batch(sb_id)
    if not sb:
        return Response({"error": "SubBatch 不存在"}, status_code=404)

    transcript_path = ""
    try:
        tasks = await db.get_tasks(sub_batch_id=sb_id, task_type="pick")
        pick_task = tasks[0] if tasks else None
        if pick_task:
            runs = await db.get_task_runs(pick_task["id"])
            for run in sorted(runs, key=lambda r: str(r.get("created_at") or ""), reverse=True):
                candidate = str(run.get("transcript_path") or "")
                if candidate:
                    transcript_path = candidate
                    break
    except Exception as e:
        logger.warning("[agent_trace] transcript lookup failed: %s", e)

    if not transcript_path:
        return Response({"error": "pick transcript not found"}, status_code=404)

    trace = read_conflict_agent_trace(transcript_path, sha)
    if not trace:
        return Response({"error": "conflict agent trace not found"}, status_code=404)

    return Response({
        "commit_sha": sha,
        "transcript_path": transcript_path,
        **trace,
    })


@get("/sub_batches/{sb_id:str}/transcript/{session_id:str}")
async def get_session_transcript(sb_id: str, session_id: str) -> Response:
    """Resolve a sub-agent session ID into its transcript archive.

    Used by the Commit Review page to show AI solve trace inline.
    Returns the transcript tree for the session (or 404 if not found).
    """
    logger.info("[transcript] Looking up session_id=%s", session_id)
    archive, path, _candidates = _find_transcript_archive_by_session(session_id)
    if not archive:
        logger.warning("[transcript] No transcript found for session_id=%s", session_id)
        return Response({"error": "Transcript not found for session"}, status_code=404)

    # If the archive has a session_tree, use it; otherwise look for the root
    tree = archive.get("session_tree")
    if not tree:
        # Old format: messages at top-level
        tree = {
            "session_id": archive.get("session_id", session_id),
            "depth": 0,
            "messages": archive.get("messages", []),
            "children": archive.get("children", []),
        }

    return Response({
        "session_id": session_id,
        "transcript_path": path,
        "archived_at": archive.get("archived_at"),
        "summary": archive.get("summary", {}),
        "session_tree": tree,
    })
