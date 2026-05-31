"""Review / Final Review task handler：batch-review skill 前处理与 prompt 构造。

负责：
- 区分轻量（review）和全量（final_review）两种模式
- 为每个 review/final_review 任务分配互不共享的 checkpoint/state 目录
- 计算 review 报告输出路径（.md / .json）
- 格式化 prompt 中的 subbatch_suffix 占位符并注入审查范围
- 返回 (working_dir, prompt, extra_result)

final_review 注意事项：
- 任务虽然挂在最后一个 SubBatch（如 _d）下，但实际代表整批的全量 review
- branch_name 应使用 batch_config["working_branch"]，而不是最后一个 SubBatch 的分支
- commit_count 反映整批总提交数（来自 batch_config["commit_count"]）
- session_result_path 的 prompt 注入由 session_runner 统一处理（session_result_prompt_prefix），
  此 handler 无需也不应重复注入
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

logger = logging.getLogger(__name__)

HandlerResult = Tuple[str, str, Dict[str, Any]]


def _load_json_object(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Failed to read review resume file %s: %s", path, exc)
        return {}


def _normalise_commit_list(commits: Iterable[Any]) -> List[str]:
    """Return a clean list of commit SHAs/refs from DB or payload values."""
    result: List[str] = []
    for commit in commits or []:
        if isinstance(commit, str):
            value = commit.strip()
        elif isinstance(commit, dict):
            value = str(commit.get("sha") or commit.get("hash") or commit.get("commit") or "").strip()
        else:
            value = str(commit or "").strip()
        if value:
            result.append(value)
    return result


def _review_paths(temp_dir: str, *, task_type: str, suffix: str) -> Dict[str, str]:
    """Build task-scoped batch-review checkpoint and output paths.

    The batch-review skill has durable resume files.  If all review tasks share
    ../temp/_scan_input.json and ../temp/_mechanical_scan.json, review_b/c/d can
    incorrectly resume review_a and copy the same report.  Keep checkpoint state
    in a per-task directory, while preserving the orchestration-visible outputs
    at ../temp/review_<suffix>.* / ../temp/final_review.*.
    """
    if not temp_dir:
        return {}

    temp = Path(temp_dir)
    if task_type == "final_review":
        state_dir = temp / "final_review_state"
        output_md = temp / "final_review.md"
        output_json = temp / "final_review.json"
    else:
        state_dir = temp / f"review_{suffix}_state"
        output_md = temp / f"review_{suffix}.md"
        output_json = temp / f"review_{suffix}.json"

    return {
        "review_state_dir": str(state_dir),
        "review_scan_input_json": str(state_dir / "_scan_input.json"),
        "review_mechanical_scan_json": str(state_dir / "_mechanical_scan.json"),
        "review_progress_json": str(state_dir / "_review_progress.json"),
        "review_findings_dir": str(state_dir / "batch_review_findings"),
        "review_diffs_dir": str(state_dir / "batch_review_diffs"),
        "review_canonical_json": str(state_dir / "batch_review.json"),
        "review_canonical_md": str(state_dir / "batch_review_report.md"),
        "review_output_md": str(output_md),
        "review_output_json": str(output_json),
    }


def _build_commit_scope_prompt(*, task_type: str, suffix: str, commits: List[str], working_dir: str, paths: Dict[str, str]) -> str:
    if not commits:
        commit_block = "(commit list unavailable; determine from the explicit task range only if present)"
        first_commit = ""
        last_commit = ""
    else:
        commit_block = "\n".join(commits)
        first_commit = commits[0]
        last_commit = commits[-1]

    if task_type == "final_review":
        scope_text = (
            "本任务是 FINAL_REVIEW：审查范围是本次 GlobalBatch 的全部 commit，"
            "不得退化为最后一个 SubBatch，也不得复用任何 review_<suffix> 的 checkpoint。"
        )
    else:
        scope_text = (
            f"本任务是 SubBatch `_{suffix}` 的阶段 review：审查范围只能是下方 commit 列表，"
            "不得从其它 SubBatch 或 final_review 的 checkpoint 续跑。"
        )

    paths_json = json.dumps(paths, ensure_ascii=False, indent=2)
    return (
        "\n\n## CubeClaw review scope and checkpoint override (CRITICAL)\n"
        f"{scope_text}\n"
        f"- task_type: {task_type}\n"
        f"- subbatch_suffix: {suffix}\n"
        f"- repo_dir / working_dir: {working_dir}\n"
        f"- commit_count: {len(commits) if commits else 'unknown'}\n"
        f"- first_commit: {first_commit}\n"
        f"- last_commit: {last_commit}\n"
        "\n### Task-scoped paths\n"
        "必须使用下面这些路径作为本任务的唯一 checkpoint/output contract；"
        "不要读取或复用 ../temp 根目录下旧的 `_scan_input.json`、`_mechanical_scan.json`、"
        "`batch_review_findings/`、`batch_review.json` 或 `batch_review_report.md`，"
        "因为它们可能属于其它 SubBatch。\n"
        "```json\n"
        f"{paths_json}\n"
        "```\n"
        "\n### Exact commits to review\n"
        "Phase 0 必须把以下列表原样写入 review_scan_input_json 的 commits 字段；"
        "resume matching 除 review_mode 外，还必须校验 repo_dir、commit_count、first_commit、last_commit 均匹配，"
        "否则必须忽略旧 checkpoint 并重建本任务 state。\n"
        "```text\n"
        f"{commit_block}\n"
        "```\n"
    )


def _build_resume_hint(
    state_dir: str,
    *,
    task_type: str,
    review_mode: str,
    output_json: str = "",
) -> str:
    """Build a small progress summary for the batch-review prompt.

    The skill owns the real resume semantics, but the orchestration prompt should
    make the current on-disk checkpoint explicit so a fresh LLM session continues
    instead of restarting or asking questions.  The state directory is task-scoped
    so SubBatch reviews cannot accidentally share split/checkpoint files.
    """
    if not state_dir:
        return ""
    state = Path(state_dir)
    scan = _load_json_object(state / "_mechanical_scan.json")
    scan_input = _load_json_object(state / "_scan_input.json")
    final_json_path = Path(output_json) if output_json else state / "batch_review.json"

    total = scan.get("total_commits") or len(scan_input.get("commits") or []) or "unknown"
    high_signal = scan.get("high_signal_shas") or []
    if review_mode == "full" and scan_input.get("commits"):
        required = [c.get("sha") for c in scan_input.get("commits", []) if isinstance(c, dict) and c.get("sha")]
    else:
        required = [sha for sha in high_signal if sha]

    findings_dir = state / "batch_review_findings"
    done = []
    if findings_dir.exists():
        for finding in findings_dir.glob("*.json"):
            data = _load_json_object(finding)
            sha = str(data.get("sha") or finding.stem)
            if sha:
                done.append(sha)
    required_set = set(required)
    done_set = set(done)
    missing = sorted(required_set - done_set) if required_set else []

    return (
        "\n\n## CubeClaw resumable review checkpoint\n"
        "本任务必须幂等续跑，不得因为已有临时文件而重新开始或询问用户。\n"
        f"- task_type: {task_type}\n"
        f"- review_mode: {review_mode}\n"
        f"- state_dir: {state}\n"
        f"- mechanical_scan_exists: {bool(scan)}\n"
        f"- total_commits: {total}\n"
        f"- required_deep_review_count: {len(required_set) if required_set else 'unknown'}\n"
        f"- completed_findings_count: {len(done_set)}\n"
        f"- missing_findings_count: {len(missing) if required_set else 'unknown'}\n"
        f"- final_report_json_exists: {final_json_path.exists()}\n"
        "续跑规则：\n"
        "1. 只允许复用 state_dir 内的 _scan_input.json 和 _mechanical_scan.json；根 ../temp 或其它 review_*_state/final_review_state 内的文件一律视为其它任务。\n"
        "2. 如果 _scan_input.json 和 _mechanical_scan.json 已存在且与当前任务的 repo_dir/review_mode/commit 列表匹配，直接复用，禁止重复 Phase 1。\n"
        "3. Phase 2 只分发缺失或无效的 batch_review_findings/<sha>.json；已有合法 finding 必须跳过。\n"
        "4. 如果所有 required findings 均已存在，立即进入 Phase 3 聚合。\n"
        "5. Phase 3 必须同时写 state_dir 内 canonical batch_review.json/batch_review_report.md，并复制/输出到编排要求的 final_review.json/final_review.md 或 review_<suffix>.json/.md。\n"
        "6. 严禁以‘已启动后台 sub-agent，等待完成’作为最终回复；启动 sub-agent 后必须主动轮询/校验 findings 文件，直到缺失数为 0 或写 blocked 最终态。\n"
        "7. 无论成功、失败还是 blocked，最终必须覆盖 DAG session_result_path 为最终态。\n"
    )


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
    """Review / Final Review 任务前处理。

    Returns:
        (working_dir, prompt, extra_result)
    """
    task_type = task.get("type", "")
    sub_batch_id = task.get("sub_batch_id", "")
    suffix = sub_batch_id.split("_")[-1]
    payload = task.get("payload") or {}

    # final_review 使用主 pick worktree
    if task_type == "final_review" and main_pick_worktree:
        working_dir = main_pick_worktree
    else:
        working_dir = sub_batch.get("worktree_path") or payload.get("worktree_path", "")

    # final_review 代表整批全量 review，branch_name / commit_count / commits 应来自整批元数据，
    # 而不是最后一个 SubBatch（_d）的数据。
    if task_type == "final_review":
        branch_name = (
            batch_config.get("working_branch")
            or sub_batch.get("branch_name", "")
        )
        commits = _normalise_commit_list(batch_config.get("commits") or payload.get("commits") or [])
        if not commits:
            commits = _normalise_commit_list(sub_batch.get("commits", []))
        commit_count = (
            batch_config.get("commit_count")
            or len(commits)
            or len(sub_batch.get("commits", []))
        )
        review_mode = "full"
    else:
        branch_name = sub_batch.get("branch_name", "")
        commits = _normalise_commit_list(sub_batch.get("commits", []) or payload.get("commits") or [])
        commit_count = len(commits)
        review_mode = "sample"

    paths = _review_paths(temp_dir, task_type=task_type, suffix=suffix)

    extra_result: Dict[str, Any] = {
        "branch_name": branch_name,
        "commit_count": commit_count,
        "review_mode": review_mode,
        **paths,
    }
    if session_result_path:
        extra_result["session_result_path"] = session_result_path

    prompt = spec["prompt"].format(subbatch_suffix=suffix)
    prompt += _build_commit_scope_prompt(
        task_type=task_type,
        suffix=suffix,
        commits=commits,
        working_dir=working_dir,
        paths=paths,
    )
    prompt += _build_resume_hint(
        paths.get("review_state_dir", temp_dir),
        task_type=task_type,
        review_mode=review_mode,
        output_json=paths.get("review_output_json", ""),
    )

    return working_dir, prompt, extra_result
