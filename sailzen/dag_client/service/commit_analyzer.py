"""Commit analyzer for pick node review page.

Reads:
- DB data (SubBatch, Batch with workspace_paths.config)
- Git worktrees (for git log/diff on source and target branches)
- File system (evidence directories, review findings JSON)

Outputs structured data consumed by the frontend PickReviewPage:
- Commit mappings (source→target, with status)
- Evidence snapshots (conflict evidence paths)
- Review findings (per-commit structured review)
- Diffs (source vs target)
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ── Data types (mirrors dashboard/src/lib/data/commit_map.ts) ──────────

CommitStatus = str  # 'picked' | 'conflict' | 'skipped' | 'pending' | 'duplicate' | 'revert_pair'


def _run_git(args: List[str], cwd: str, timeout: int = 30) -> str:
    """Run a read-only git command and return stdout text. Raise on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result.check_returncode()
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError(f"git not found on PATH; worktree={cwd}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"git command timed out after {timeout}s: {' '.join(args)}")
    except subprocess.CalledProcessError as e:
        # git may return non-zero for e.g. empty log range; return empty
        if "unknown revision" in (e.stderr or "") or "bad revision" in (e.stderr or ""):
            return ""
        raise RuntimeError(f"git command failed: {' '.join(args)}\n{e.stderr}")


def _git_log_commits(
    worktree_path: str,
    branch: str,
    start_commit: str,
    end_commit: str,
) -> List[Dict[str, str]]:
    """Get list of commits in range (start_commit exclusive, end_commit inclusive) on branch.

    Returns list of dicts with: hash, short_hash, message, author, timestamp.
    """
    if not branch or not end_commit:
        return []

    range_spec = f"{end_commit}"
    if start_commit:
        range_spec = f"{start_commit}..{end_commit}"

    # Try to get commits on the branch
    try:
        branch_ref = f"{branch}..{end_commit}" if start_commit else f"{branch}"
        if start_commit:
            # commits reachable from end_commit on branch, excluding those reachable from start_commit
            output = _run_git(
                [
                    "log",
                    "--format=%H%x00%h%x00%s%x00%an%x00%aI",
                    "--reverse",
                    f"{start_commit}..{end_commit}",
                    "--first-parent",
                    branch,
                ],
                worktree_path,
            )
        else:
            output = _run_git(
                [
                    "log",
                    "--format=%H%x00%h%x00%s%x00%an%x00%aI",
                    "--reverse",
                    f"^{start_commit}" if start_commit else "",
                    end_commit,
                    "--first-parent",
                    branch,
                ],
                worktree_path,
            )
    except RuntimeError:
        # Fallback: try without branch restriction
        output = _run_git(
            [
                "log",
                "--format=%H%x00%h%x00%s%x00%an%x00%aI",
                "--reverse",
                range_spec,
            ],
            worktree_path,
        )

    commits = []
    for line in output.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\0")
        if len(parts) >= 5:
            commits.append({
                "hash": parts[0],
                "short_hash": parts[1],
                "message": parts[2],
                "author": parts[3],
                "timestamp": parts[4],
                "files_changed": 0,  # populated lazily by caller
            })
    return commits


def _get_files_changed(worktree_path: str, sha: str) -> int:
    """Count files changed in a commit."""
    try:
        output = _run_git(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", sha],
            worktree_path,
        )
        return len([f for f in output.strip().split("\n") if f])
    except RuntimeError:
        return 0


def _cherry_pick_origin_sha(worktree_path: str, target_sha: str) -> Optional[str]:
    """Extract the original source SHA from a cherry-pick commit message.

    Git cherry-pick -x adds: (cherry picked from commit abc1234...)
    """
    try:
        msg = _run_git(["log", "-1", "--format=%B", target_sha], worktree_path)
        # Look for the cherry-picked-from line
        for line in msg.split("\n"):
            line = line.strip()
            if "(cherry picked from commit " in line:
                # Extract the SHA
                start = line.find("(cherry picked from commit ") + len("(cherry picked from commit ")
                end = line.find(")", start)
                if end > start:
                    return line[start:end]
        return None
    except RuntimeError:
        return None


# ── agent_session ↔ Frontend status mapping ──────────────────────────

# agent_session.json session_log entry status → frontend CommitStatus
AGENT_SESSION_STATUS_MAP: Dict[str, str] = {
    "CLEAN": "picked",
    "EMPTY": "picked",
    "CONFLICT_RESOLVED": "conflict",   # had conflicts → show as conflict so user can see evidence
    "CONFLICT": "conflict",
    "PREPICKED": "picked",
    "SKIPPED": "skipped",
    "REVERT_PAIR": "revert_pair",
    "LOCKED": "skipped",
    "MERGE": "picked",
}


def _read_agent_session_log(branch_dance_state_dir: str) -> Dict[str, Dict[str, Any]]:
    """Read agent_session.json session_log, return dict keyed by source SHA.

    This is the PRIMARY data source for commit pick status.
    _bd_pick_results.json may not exist (gb pick writes to agent_session.json directly).

    Each entry includes: sha, status, resolution, message, log_message, solve_session.
    """
    path = Path(branch_dance_state_dir) / "agent_session.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read agent_session.json: %s", e)
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    session_log = data.get("session_log")
    if not isinstance(session_log, list):
        return result

    for entry in session_log:
        if not isinstance(entry, dict):
            continue
        sha = entry.get("sha", "")
        if sha:
            result[sha] = entry
    return result


_CONFLICT_TASK_TITLE_RE = re.compile(
    r"(?:Branch\s+Dance\s+conflict|Conflict(?:\s+(?:batch|resolve))?)[^:\n\"]*:\s*([0-9a-fA-F]{7,40})",
    re.IGNORECASE,
)


def _sha_matches(full_sha: str, short_sha: str) -> bool:
    """Return true when either SHA/prefix can identify the other."""
    if not full_sha or not short_sha:
        return False
    a = full_sha.lower()
    b = short_sha.lower()
    return a.startswith(b) or b.startswith(a)


def _extract_task_short_sha(value: Any) -> str:
    """Extract conflict commit short SHA from Branch Dance sub-agent title/description."""
    if not isinstance(value, str):
        return ""
    match = _CONFLICT_TASK_TITLE_RE.search(value)
    return match.group(1).lower() if match else ""


def _walk_transcript_tree(node: Dict[str, Any]):
    """Yield a transcript tree node and all descendants."""
    yield node
    for child in node.get("children") or []:
        if isinstance(child, dict):
            yield from _walk_transcript_tree(child)


def _read_transcript_archive(path: str) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read transcript archive %s: %s", path, e)
        return None


def collect_conflict_subagent_links(
    transcript_path: str,
    commits: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    """Link conflict commits to sub-agent sessions by task title convention.

    Branch Dance prompts spawn conflict sub-agents with titles/descriptions like
    ``Branch Dance conflict: <short_sha>``, ``Conflict batch 1/2: <short_sha>``,
    or legacy terse ``conflict: <short_sha>``. This parser uses that stable title
    bridge instead of relying on LLM-written ``--solve-session`` values in
    agent_session.json.
    """
    archive = _read_transcript_archive(transcript_path)
    if not archive:
        return {}

    root = archive.get("session_tree") if isinstance(archive.get("session_tree"), dict) else archive
    by_sha: Dict[str, List[Dict[str, Any]]] = {sha: [] for sha in commits}
    seen: Set[tuple[str, str]] = set()

    # Children carry the sub-agent session metadata/title after transcript archiving.
    for node in _walk_transcript_tree(root):
        session = node.get("session") if isinstance(node.get("session"), dict) else {}
        candidates = [
            session.get("title"),
            session.get("description"),
            node.get("title"),
            node.get("description"),
        ]
        short_sha = next((s for s in (_extract_task_short_sha(v) for v in candidates) if s), "")
        if not short_sha:
            continue
        session_id = str(node.get("session_id") or session.get("id") or "")
        if not session_id:
            continue
        commit_sha = next((sha for sha in commits if _sha_matches(sha, short_sha)), "")
        if not commit_sha:
            continue
        key = (commit_sha, session_id)
        if key in seen:
            continue
        seen.add(key)
        by_sha.setdefault(commit_sha, []).append({
            "session_id": session_id,
            "title": str(session.get("title") or node.get("title") or ""),
            "description": str(session.get("description") or node.get("description") or ""),
            "short_sha": short_sha,
            "depth": node.get("depth"),
        })

    # Fallback for older/incomplete archives: parse parent task tool calls.
    for node in _walk_transcript_tree(root):
        for msg in node.get("messages") or []:
            if not isinstance(msg, dict):
                continue
            for part in msg.get("parts") or []:
                if not isinstance(part, dict) or part.get("type") != "tool":
                    continue
                state = part.get("state") if isinstance(part.get("state"), dict) else {}
                metadata = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
                input_obj = state.get("input") if isinstance(state.get("input"), dict) else {}
                candidates = [
                    state.get("title"),
                    metadata.get("description"),
                    input_obj.get("description"),
                ]
                short_sha = next((s for s in (_extract_task_short_sha(v) for v in candidates) if s), "")
                if not short_sha:
                    continue
                session_id = str(metadata.get("sessionId") or metadata.get("taskId") or "")
                if not session_id:
                    continue
                commit_sha = next((sha for sha in commits if _sha_matches(sha, short_sha)), "")
                if not commit_sha:
                    continue
                key = (commit_sha, session_id)
                if key in seen:
                    continue
                seen.add(key)
                by_sha.setdefault(commit_sha, []).append({
                    "session_id": session_id,
                    "title": str(state.get("title") or input_obj.get("description") or ""),
                    "description": str(metadata.get("description") or input_obj.get("description") or ""),
                    "short_sha": short_sha,
                    "depth": metadata.get("spawnDepth"),
                })

    return {sha: links for sha, links in by_sha.items() if links}


def read_conflict_agent_trace(
    transcript_path: str,
    source_sha: str,
) -> Optional[Dict[str, Any]]:
    """Return combined sub-agent transcript tree for one conflict commit."""
    links = collect_conflict_subagent_links(transcript_path, [source_sha]).get(source_sha, [])
    if not links:
        return None
    archive = _read_transcript_archive(transcript_path)
    if not archive:
        return None
    root = archive.get("session_tree") if isinstance(archive.get("session_tree"), dict) else archive
    wanted = {str(link.get("session_id")) for link in links}
    nodes = [node for node in _walk_transcript_tree(root) if str(node.get("session_id") or "") in wanted]
    return {
        "source_sha": source_sha,
        "links": links,
        "sessions": nodes,
    }


def _read_pick_results(branch_dance_state_dir: str) -> Dict[str, Any]:
    """Read _bd_pick_results.json, return dict keyed by source commit SHA.

    Falls back to agent_session.json session_log if _bd_pick_results.json not found.
    """
    # Primary: _bd_pick_results.json
    path = Path(branch_dance_state_dir) / "_bd_pick_results.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read _bd_pick_results.json: %s", e)
        else:
            result: Dict[str, Any] = {}
            if isinstance(data, dict):
                commits = data.get("commits") or data
                if isinstance(commits, dict):
                    for sha, entry in commits.items():
                        if isinstance(entry, dict):
                            result[sha] = entry
                        else:
                            result[sha] = {"raw": entry}
                elif isinstance(commits, list):
                    for entry in commits:
                        if isinstance(entry, dict):
                            src = entry.get("source_commit") or entry.get("source_sha") or entry.get("sha") or ""
                            if src:
                                result[src] = entry
            elif isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict):
                        src = entry.get("source_commit") or entry.get("source_sha") or entry.get("sha") or ""
                        if src:
                            result[src] = entry
            if result:
                return result

    # Fallback: agent_session.json session_log
    agent_entries = _read_agent_session_log(branch_dance_state_dir)
    if agent_entries:
        return agent_entries

    return {}


def _parse_pick_entry_status(entry: dict) -> str:
    """Determine normalized status from a pick result entry.

    Handles both _bd_pick_results.json format and agent_session.json session_log format.
    """
    status = (entry.get("status") or "").upper()

    # agent_session.json format (priority — these are uppercase)
    if status in AGENT_SESSION_STATUS_MAP:
        return AGENT_SESSION_STATUS_MAP[status]

    # _bd_pick_results.json / legacy format (lowercase)
    status_lower = status.lower()
    if status_lower in ("picked", "success", "clean"):
        return "picked"
    if status_lower in ("conflict", "unresolved"):
        return "conflict"
    if status_lower in ("skipped", "skip"):
        return "skipped"
    if status_lower in ("pending",):
        return "pending"
    if status_lower in ("duplicate", "dupe"):
        return "duplicate"
    if status_lower in ("revert_pair", "revert"):
        return "revert_pair"
    if entry.get("resolved"):
        return "picked"
    return "pending"


# ── Public API ─────────────────────────────────────────────────────────


def analyze_commit_mappings(
    repo_path: str,
    batch_branch: str,
    source_branch: str,
    start_commit: str,
    end_commit: str,
    branch_dance_state_dir: str = "",
) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Analyze commit mappings between source and target branches."""
    import time

    # --- Read pick results for status data ---
    pick_results = _read_pick_results(branch_dance_state_dir) if branch_dance_state_dir else {}
    logger.info("[analyze] pick_results from %s: %d entries",
                branch_dance_state_dir or "N/A", len(pick_results))

    # Build commit list from agent session data
    # Falls back to git log when pick_results is empty
    source_commits: list[Dict[str, Any]] = []

    if pick_results:
        for sha, entry in pick_results.items():
            source_commits.append({
                "hash": sha,
                "short_hash": sha[:12],
                "message": entry.get("message", ""),
                "author": "",
                "timestamp": "",
                "files_changed": 0,
            })
        logger.info("[analyze] built %d commits from agent_session", len(source_commits))
    else:
        t0 = time.monotonic()
        source_commits = _git_log_commits(repo_path, source_branch, start_commit, end_commit)
        logger.info("[analyze] step1 done: %d source commits (%.1fs)", len(source_commits), time.monotonic() - t0)
        if not source_commits:
            source_commits = _git_log_commits(repo_path, "", start_commit, end_commit)

    # --- Read commits.txt TODO list ---
    # commits.txt: authoritative TODO — what this subbatch SHOULD pick.
    # Format: <sha>|NONE  or  <sha>|<revert_target_sha>
    # Derive temp_dir from branch_dance_state_dir: .../temp/branch_dance_c -> .../temp
    _temp_dir = str(Path(branch_dance_state_dir).parent) if branch_dance_state_dir else ""
    todo = _read_commits_todo(_temp_dir, start_commit, end_commit)
    logger.info("[analyze] commits.txt TODO: %d entries", len(todo))

    # Build target SHA lookup from the same pick_results
    target_by_origin: Dict[str, dict] = {}

    if not pick_results:
        t0 = time.monotonic()
        logger.info("[analyze] step2 _git_log target: %s..%s on %s", start_commit[:12], end_commit[:12], batch_branch)
        target_commits_raw: List[Dict[str, str]] = []
        try:
            target_commits_raw = _git_log_commits(repo_path, batch_branch, start_commit, end_commit)
        except RuntimeError as e:
            logger.warning("[analyze] step2 failed: %s", e)
        logger.info("[analyze] step2 done: %d target commits (%.1fs)", len(target_commits_raw), time.monotonic() - t0)

        t0 = time.monotonic()
        logger.info("[analyze] step3 cherry-pick origin for %d targets", len(target_commits_raw))
        for idx, tc in enumerate(target_commits_raw):
            if idx > 0 and idx % 20 == 0:
                logger.info("[analyze] step3 progress: %d/%d (%.1fs)", idx, len(target_commits_raw), time.monotonic() - t0)
            origin = _cherry_pick_origin_sha(repo_path, tc["hash"])
            entry = {
                "hash": tc["hash"],
                "short_hash": tc["short_hash"],
                "message": tc["message"],
                "author": tc["author"],
                "timestamp": tc["timestamp"],
                "files_changed": _get_files_changed(repo_path, tc["hash"]),
                "cherry_pick_origin": origin,
            }
            if origin:
                target_by_origin[origin] = entry
        logger.info("[analyze] step3 done: %d mapped (%.1fs)", len(target_by_origin), time.monotonic() - t0)

    # --- Read commits.txt TODO list ---
    # commits.txt: authoritative TODO — what this subbatch SHOULD pick.
    # Format: <sha>|NONE  or  <sha>|<revert_target_sha>
    # Derive temp_dir from branch_dance_state_dir: .../temp/branch_dance_c -> .../temp
    _temp_dir = str(Path(branch_dance_state_dir).parent) if branch_dance_state_dir else ""
    todo = _read_commits_todo(_temp_dir, start_commit, end_commit)
    logger.info("[analyze] commits.txt TODO: %d entries for range %s..%s",
                len(todo), start_commit[:12], end_commit[:12])

    if not todo:
        logger.warning("[analyze] commits.txt has no matching range, falling back to session-only")

    # Build mappings
    mappings: List[Dict[str, Any]] = []
    stats: Dict[str, int] = {
        "picked": 0, "conflict": 0, "skipped": 0, "pending": 0,
        "duplicate": 0, "revert_pair": 0,
    }

    # Source commits index for fast lookup
    source_by_sha = {sc["hash"]: sc for sc in source_commits}

    # Driver: commits.txt TODO list ensures we show ALL planned commits
    # (including those the LLM missed), not just what agent_session reported.
    for sha, pair_type in todo.items():
        sc = source_by_sha.get(sha, {
            "hash": sha,
            "short_hash": sha[:12],
            "message": "",
            "author": "",
            "timestamp": "",
            "files_changed": 0,
        })

        if pair_type != "NONE":
            tc = {"hash": pair_type, "short_hash": pair_type[:12], "message": "", "author": "", "timestamp": ""}
            status = "revert_pair"
        else:
            tc = target_by_origin.get(sha)
            pick_entry = pick_results.get(sha, {})
            if pick_entry:
                status = _parse_pick_entry_status(pick_entry)
            elif tc:
                status = "picked"
            else:
                status = "pending"

        conflict_files: List[str] = []
        pick_entry = pick_results.get(sha, {})
        if pick_entry:
            cf = pick_entry.get("conflict_files") or pick_entry.get("conflicts") or []
            if isinstance(cf, list):
                conflict_files = [str(f) for f in cf]

        mapping = {
            "source_commit": sc,
            "target_commit": tc or None,
            "status": status,
            "conflict_files": conflict_files,
            "origin": {
                "label": source_branch,
                "original_hash": sha,
            },
        }
        mappings.append(mapping)
        stats[status] = stats.get(status, 0) + 1

    return mappings, stats


def _read_commits_todo(temp_dir: str, start_commit: str, end_commit: str) -> Dict[str, str]:
    """Read commits.txt and extract the TODO commit range for this subbatch.

    Format: <sha>|NONE  or  <sha>|<revert_target_sha>

    Returns dict of sha -> pair_type (string: "NONE" or revert_target_sha).
    """
    path = Path(temp_dir) / "commits.txt"
    if not path.is_file():
        logger.warning("[commits.txt] not found at %s", path)
        return {}

    try:
        lines = path.read_text(encoding="utf-8").split("\n")
    except OSError as e:
        logger.warning("[commits.txt] read error: %s", e)
        return {}

    result: Dict[str, str] = {}
    in_range = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("|", 1)
        sha = parts[0].strip()
        pair_type = parts[1].strip() if len(parts) > 1 else "NONE"

        if sha == start_commit:
            in_range = True
        if in_range:
            result[sha] = pair_type
        if sha == end_commit:
            break

    logger.info("[commits.txt] parsed %d TODO commits for %s..%s", len(result), start_commit[:12], end_commit[:12])
    return result


def collect_evidence_paths(
    branch_dance_state_dir: str,
    commits: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Collect evidence directory snapshots for conflict commits.

    Args:
        branch_dance_state_dir: Path like .../temp/branch_dance_a/.
        commits: List of source commit SHAs to check.

    Returns:
        Dict of sha → EvidenceSnapshot (null for non-conflict).
    """
    evidence_dir = Path(branch_dance_state_dir) / "evidence"
    result: Dict[str, Dict[str, Any]] = {}

    for sha in commits:
        short_sha = sha[:12] if len(sha) >= 12 else sha
        # Try both full SHA and short SHA directory names
        ev_dir = None
        for candidate in (sha, short_sha):
            candidate_path = evidence_dir / candidate
            if candidate_path.is_dir():
                ev_dir = candidate_path
                break

        if not ev_dir:
            result[sha] = {
                "path": "",
                "conflict_files": [],
                "has_prev": False,
                "has_incoming": False,
                "has_local": False,
                "has_on_conflict": False,
                "has_resolved": False,
            }
            continue

        # Read conflict files list
        # NOTE: conflict_files.txt is often "# All conflicts resolved" after gb pick resume.
        # Fall back to enumerating on_conflict/ directory for actual conflict files.
        conflict_files: List[str] = []
        cf_file = ev_dir / "conflict_files.txt"
        if cf_file.is_file():
            try:
                raw_lines = [
                    line.strip() for line in cf_file.read_text(encoding="utf-8").split("\n")
                    if line.strip()
                ]
                # Filter out comment lines like "# All conflicts resolved"
                conflict_files = [l for l in raw_lines if not l.startswith("#")]
            except OSError:
                pass

        # If conflict_files.txt is empty or had only comments, discover from on_conflict/
        if not conflict_files:
            on_conflict_dir = ev_dir / "on_conflict"
            if on_conflict_dir.is_dir():
                discovered: List[str] = []
                for f in on_conflict_dir.rglob("*"):
                    if f.is_file():
                        rel = str(f.relative_to(on_conflict_dir)).replace("\\", "/")
                        discovered.append(rel)
                conflict_files = sorted(discovered)

        result[sha] = {
            "path": str(ev_dir),
            "conflict_files": conflict_files,
            "has_prev": (ev_dir / "prev").is_dir(),
            "has_incoming": (ev_dir / "incoming").is_dir(),
            "has_local": (ev_dir / "local").is_dir(),
            "has_on_conflict": (ev_dir / "on_conflict").is_dir(),
            "has_resolved": (ev_dir / "resolved").is_dir() and (ev_dir / "resolved_files.txt").is_file(),
        }

    return result


def _read_mechanical_scan(review_state_dir: str) -> Dict[str, Dict[str, Any]]:
    """Read _mechanical_scan.json per_commit data.

    This is the fallback when batch_review_findings/{sha}.json files don't exist
    (e.g., in 'sample' review mode where only Phase 1 mechanical scan ran).
    """
    path = Path(review_state_dir) / "_mechanical_scan.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read _mechanical_scan.json: %s", e)
        return {}
    per_commit = data.get("per_commit")
    if isinstance(per_commit, dict):
        return per_commit
    return {}


def _mechanical_to_review_findings(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Convert _mechanical_scan per_commit entry to ReviewFindings format.

    Preserves compatibility with the existing frontend interface (mirror_sync_ok, etc.)
    while passing through the real mechanical scan fields.
    """
    return {
        # Compat fields (derived from mechanical scan)
        "mirror_sync_ok": not entry.get("file_migration", False),
        "netease_macro_ok": not entry.get("macro_deletion_candidate", False),
        "intrusion_check_ok": not entry.get("problem_file_touched", False),
        # Mechanical scan fields (passthrough)
        "conflict_marker_found": entry.get("conflict_marker_found", False),
        "has_conflict_log": entry.get("has_conflict_log", False),
        "macro_deletion_candidate": entry.get("macro_deletion_candidate", False),
        "macro_add": entry.get("macro_add", 0),
        "macro_del": entry.get("macro_del", 0),
        "whitespace_heavy": entry.get("whitespace_heavy", False),
        "whitespace_delta": entry.get("whitespace_delta", 0),
        "file_migration": entry.get("file_migration", False),
        "renamed_deleted_files": entry.get("renamed_deleted_files", []),
        "is_fix_commit": entry.get("is_fix_commit", False),
        "large_commit": entry.get("large_commit", False),
        "files_count": entry.get("files_count", 0),
        "problem_file_touched": entry.get("problem_file_touched", False),
        "high_signal": entry.get("high_signal", False),
        "high_signal_reasons": entry.get("high_signal_reasons", []),
        "subject": entry.get("subject", ""),
    }


def collect_review_findings(
    temp_dir: str,
    subbatch_suffix: str,
    commits: List[str],
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Read per-commit review findings.

    Priority:
      1. batch_review_findings/{sha}.json (deep review, Phase 2)
      2. _mechanical_scan.json → per_commit (mechanical scan, Phase 1, sample mode)

    Args:
        temp_dir: Root temp directory (from workspace_paths.temp_dir).
        subbatch_suffix: SubBatch suffix like "a", "b", etc.
        commits: List of source commit SHAs.

    Returns:
        Dict of sha → ReviewFindings (or None if no findings).
    """
    review_state_dir = Path(temp_dir) / f"review_{subbatch_suffix}_state"
    findings_dir = review_state_dir / "batch_review_findings"

    # Phase 2 fallback: _mechanical_scan.json
    mechanical_scan = _read_mechanical_scan(str(review_state_dir))

    result: Dict[str, Optional[Dict[str, Any]]] = {}

    for sha in commits:
        short_sha = sha[:12] if len(sha) >= 12 else sha
        findings = None

        # 1. Try individual batch_review_findings/{sha}.json
        for candidate in (sha, short_sha):
            path = findings_dir / f"{candidate}.json"
            if path.is_file():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    findings = {
                        "mirror_sync_ok": data.get("mirror_sync_ok", False),
                        "netease_macro_ok": data.get("netease_macro_ok", False),
                        "intrusion_check_ok": data.get("intrusion_check_ok", False),
                        "intrusion_detail": data.get("intrusion_detail", ""),
                        "reviewer": data.get("reviewer") or data.get("reviewed_by", ""),
                        "reviewed_at": data.get("reviewed_at") or data.get("timestamp", ""),
                    }
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("Failed to read review findings %s: %s", path, e)
                break

        # 2. Fallback: _mechanical_scan.json per_commit
        if findings is None and mechanical_scan:
            for candidate in (sha, short_sha):
                if candidate in mechanical_scan:
                    findings = _mechanical_to_review_findings(mechanical_scan[candidate])
                    break

        result[sha] = findings

    return result


def get_commit_diff(worktree_path: str, sha: str) -> List[Dict[str, Any]]:
    """Get the diff of a single commit as structured hunks.

    Returns list of DiffFile objects.
    """
    try:
        output = _run_git(
            ["show", "--format=", "--unified=3", sha],
            worktree_path,
            timeout=60,
        )
    except RuntimeError:
        return []

    return _parse_diff_output(output)


def get_commit_pair_diff(
    worktree_path: str,
    source_sha: str,
    target_sha: str,
) -> Dict[str, Any]:
    """Get both source diff and target diff for a commit pair.

    Returns {"commit_sha": ..., "source_diff": [...], "target_diff": [...]}
    """
    source_diff = get_commit_diff(worktree_path, source_sha) if source_sha else []
    target_diff = get_commit_diff(worktree_path, target_sha) if target_sha else []
    return {
        "commit_sha": source_sha,
        "source_diff": source_diff,
        "target_diff": target_diff,
    }


def _parse_diff_output(output: str) -> List[Dict[str, Any]]:
    """Parse unified diff output into structured DiffFile list."""
    files: List[Dict[str, Any]] = []
    current_file: Optional[Dict[str, Any]] = None
    current_hunk: Optional[Dict[str, Any]] = None

    for line in output.split("\n"):
        if line.startswith("diff --git "):
            if current_file:
                if current_hunk:
                    current_file["hunks"].append(current_hunk)
                    current_hunk = None
                if current_file.get("hunks"):
                    files.append(current_file)
            current_file = {"old_path": "", "new_path": "", "hunks": [], "additions": 0, "deletions": 0}
            continue

        if not current_file:
            continue

        if line.startswith("--- "):
            current_file["old_path"] = line[4:]
            continue
        if line.startswith("+++ "):
            current_file["new_path"] = line[4:]
            continue

        if line.startswith("@@ "):
            if current_hunk:
                current_file["hunks"].append(current_hunk)
            current_hunk = {"header": line, "lines": []}
            continue

        if current_hunk is not None:
            if line.startswith("+") and not line.startswith("+++"):
                current_hunk["lines"].append({"type": "addition", "content": line})
                current_file["additions"] += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_hunk["lines"].append({"type": "deletion", "content": line})
                current_file["deletions"] += 1
            elif line.startswith(" ") or line == "":
                current_hunk["lines"].append({"type": "context", "content": line})
            # Skip other lines (like \ No newline at end of file)

    if current_file:
        if current_hunk:
            current_file["hunks"].append(current_hunk)
        if current_file.get("hunks"):
            files.append(current_file)

    return files


def read_evidence_file_content(
    evidence_dir: str,
    conflict_files: List[str],
) -> List[Dict[str, str]]:
    """Read all evidence files for a single conflict commit.

    Returns list of EvidenceFileContent objects with filepath, source, content.
    """
    sources = ["prev", "incoming", "local", "on_conflict", "resolved"]
    result: List[Dict[str, str]] = []

    ev_path = Path(evidence_dir)
    if not ev_path.is_dir():
        return result

    for source in sources:
        src_dir = ev_path / source
        if not src_dir.is_dir():
            continue
        for cf in conflict_files:
            # The file might have a subdirectory structure within the evidence dir
            file_path = src_dir / cf
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    result.append({
                        "filepath": cf,
                        "source": source,
                        "content": content,
                    })
                except OSError as e:
                    logger.warning("Failed to read evidence file %s: %s", file_path, e)

    return result


def read_conflict_decision(
    branch_dance_state_dir: str,
    source_sha: str,
) -> Optional[Dict[str, Any]]:
    """Read conflict decision from _bd_pick_results.json for a specific commit."""
    pick_results = _read_pick_results(branch_dance_state_dir)
    entry = pick_results.get(source_sha, {})
    if not entry:
        return None

    return {
        "status": entry.get("status", "unknown"),
        "resolved_by": entry.get("resolved_by") or entry.get("resolver", "llm"),
        "decision_summary": entry.get("decision_summary") or entry.get("summary", ""),
        "timestamp": entry.get("timestamp") or entry.get("resolved_at", ""),
    }
