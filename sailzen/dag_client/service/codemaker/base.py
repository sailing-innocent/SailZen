"""公共常量、错误结果构建、session_result 生成/校验工具函数。

供所有 task handler 和 session_runner 共用的基础设施。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ── 默认配置 ────────────────────────────────────────────────────────

DEFAULT_CODEMAKER_HOST = "127.0.0.1"
DEFAULT_CODEMAKER_PORT = 4096
DEFAULT_SSE_TIMEOUT = 14400.0       # 4 小时, PICK 可能耗时较长
DEFAULT_MAX_RECONNECTS = 5
DEFAULT_AGENT_NAME = "Sisyphus - Ultraworker"     # oh-my-openagent 的默认 agent
SESSION_RESULT_FILENAME = "session_result.json"
SESSION_RESULTS_DIRNAME = "session_results"


# ── Skill 配置注册表 ───────────────────────────────────────────────

SKILL_SPECS: Dict[str, Dict[str, Any]] = {
    "pick": {
        "skill": "branch-dance",
        "runner": "codemaker_pick",
        "prompt": (
            "/branch-dance 帮我pick到{end_commit}（**inclusive，必须把这个 commit 自身也 pick 进 HEAD**）。"
            "完成判定只信 `gb pick run/status --end-commit {end_commit}` 输出的 `end_state.range_complete=true`，"
            "不要在 `current_commit == end_commit` 时就停止——那只表示边界 commit 还在队列里、尚未被 pick。"
        ),
        "timeout": DEFAULT_SSE_TIMEOUT,
        "success_key": "picked",
    },
    "rebase": {
        "skill": "batch-rebase",
        "runner": "codemaker_rebase",
        "prompt": "/batch-rebase 请将当前分支 rebase 到前序分支 `{previous_branch}`",
        "timeout": DEFAULT_SSE_TIMEOUT,
        "success_key": "rebase_ok",
    },
    "build_win": {
        "skill": "batch-fixbuild-windows",
        "runner": "codemaker_build_win",
        "prompt": "/batch-fixbuild-windows 帮我解决这个项目的编译问题",
        "timeout": DEFAULT_SSE_TIMEOUT,
        "success_key": "build_ok",
        "use_buildfix_worktree": True,
    },
    "build_ios": {
        "skill": "batch-fixbuild-ios",
        "runner": "codemaker_build_ios",
        "prompt": "/batch-fixbuild-ios 帮我解决这个项目的 iOS 编译问题",
        "timeout": DEFAULT_SSE_TIMEOUT,
        "success_key": "build_ok",
        "use_buildfix_worktree": True,
    },
    "review": {
        "skill": "batch-review",
        "runner": "codemaker_review_light",
        "prompt": "/batch-review 请执行轻量阶段 review，只输出本 SubBatch 阶段报告，不进入 Phase 2 深度审查，不做任何修复；报告文件请写入 ../temp/review_{subbatch_suffix}.md 和 ../temp/review_{subbatch_suffix}.json。",
        "timeout": DEFAULT_SSE_TIMEOUT,
        "success_key": "review_ok",
    },
    "final_review": {
        "skill": "batch-review",
        "runner": "codemaker_review_final",
        "prompt": (
            "/batch-review 请执行全量集中深度 review（full 模式），"
            "审查范围是本次 GlobalBatch **所有** SubBatch 合并后的最终工作分支（不是某个子批次分支）；"
            "只报告不修复；报告文件请写入 ../temp/final_review.md 和 ../temp/final_review.json。"
            "完成后请确保 session_result.json 已写入最终态（status: success/failed/blocked）。"
        ),
        "timeout": DEFAULT_SSE_TIMEOUT,
        "success_key": "final_review_ok",
    },
}


# ── 错误结果 ──────────────────────────────────────────────────────

def skill_error_result(
    error_msg: str,
    *,
    runner: str,
    session_id: str = "",
    working_dir: str = "",
) -> Dict[str, Any]:
    """通用 SkillRunner 错误结果。"""
    return {
        "success": False,
        "runner": runner,
        "session_id": session_id,
        "working_dir": working_dir,
        "text_response": "",
        "tool_calls": [],
        "error": error_msg,
    }


# ── session_result 路径工具 ───────────────────────────────────────


def short_task_id(task_or_id: Any, length: int = 8) -> str:
    """返回用于 prompt / session_result 的短 task_id。"""
    if isinstance(task_or_id, dict):
        task_id = str(task_or_id.get("id") or "")
    else:
        task_id = str(task_or_id or "")
    return task_id[:length] if task_id else ""


def normalize_session_result_path(path_value: str, working_dir: str = "") -> str:
    """将 orchestration 传入的 session_result 路径规范化为绝对路径。"""
    if not path_value:
        return ""
    path = Path(path_value)
    if path.is_absolute():
        return str(path)
    base = Path(working_dir) if working_dir else Path.cwd()
    return str((base / path).resolve())


def default_session_result_path(working_dir: str = "", task: Optional[dict] = None) -> str:
    """默认在 repo 外侧 ../temp/session_results/ 下按 task 生成独立结果文件。"""
    if not working_dir:
        return ""
    task = task or {}
    task_id = str(task.get("id") or "")
    task_type = str(task.get("type") or "task")
    sub_batch_id = str(task.get("sub_batch_id") or "")
    suffix = sub_batch_id.split("_")[-1] if sub_batch_id else "global"
    if task_id:
        safe_name = f"{task_type}_{suffix}_{task_id[:8]}.json"
    else:
        digest = hashlib.sha1(str(Path(working_dir).resolve()).encode("utf-8")).hexdigest()[:8]
        safe_name = f"{task_type}_{suffix}_{digest}.json"
    return str((Path(working_dir).resolve().parent / "temp" / SESSION_RESULTS_DIRNAME / safe_name).resolve())


def task_session_result_path(temp_dir: str, task: dict) -> str:
    task_id = str(task.get("id") or "")
    task_type = str(task.get("type") or "task")
    sub_batch_id = str(task.get("sub_batch_id") or "")
    suffix = sub_batch_id.split("_")[-1] if sub_batch_id else "global"
    safe_name = f"{task_type}_{suffix}_{task_id[:8] or 'unknown'}.json"
    return str((Path(temp_dir) / SESSION_RESULTS_DIRNAME / safe_name).resolve())


def session_result_meta_path(session_result_path: str) -> str:
    """根据 session_result 路径生成同目录下的任务元信息文件路径。"""
    if not session_result_path:
        return ""
    path = Path(session_result_path)
    return str(path.with_name(f"{path.stem}.meta.json"))


def write_session_result_meta(meta_path: str, expected: Dict[str, Any]) -> None:
    """把完整 expected 元信息写入 meta 文件，减少 prompt 内联内容。"""
    if not meta_path:
        return
    path = Path(meta_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(expected, f, ensure_ascii=False, indent=2)


# ── expected session_result 元信息 ────────────────────────────────

def build_expected_session_result(
    *,
    task: dict,
    task_label: str,
    skill_name: str,
    runner_name: str,
    working_dir: str,
    session_result_path: str,
    extra_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生成 prompt 注入和 DAG 校验共用的 expected 元信息。"""
    extra = extra_result or {}
    task_type = task.get("type", "")
    expected: Dict[str, Any] = {
        "schema_version": 1,
        "task_id": short_task_id(task),
        "full_task_id": task.get("id", ""),
        "task_type": task_type,
        "task_label": task_label,
        "skill": skill_name,
        "runner": runner_name,
        "working_dir": working_dir,
        "session_result_path": session_result_path,
        "sub_batch_id": task.get("sub_batch_id", ""),
        # `branch_name` is kept for non-pick tasks/backward compatibility.
        # For pick tasks, distinguish the main Branch Dance working branch from
        # the SubBatch snapshot branch to avoid switching mcpe_gb to _a/_b/_c.
        "branch_name": extra.get("branch_name", ""),
        "working_branch": extra.get("working_branch", ""),
        "snapshot_branch": extra.get("snapshot_branch", ""),
    }
    for key in (
        "start_commit",
        "end_commit",
        "commit_count",
        "branch_dance_state_dir",
        "buildfix_branch",
        "buildfix_worktree_path",
        "build_state_dir",
        "build_rounds_dir",
        "build_temp_root",
        "fix_notes_path",
        "fix_state_path",
        "review_mode",
        "review_output_json",
        "review_output_md",
        "previous_branch",
        "review_state_dir",
        "review_scan_input_json",
        "review_mechanical_scan_json",
        "review_progress_json",
        "review_findings_dir",
        "review_diffs_dir",
        "review_canonical_json",
        "review_canonical_md",
    ):
        if key in extra:
            expected[key] = extra[key]
    return expected


def session_result_prompt_prefix(expected: Dict[str, Any]) -> str:
    """生成强约束 prompt，要求 skill 在退出前写 session_result.json。"""
    meta_path = str(expected.get("session_result_meta_path") or "")
    meta_hint = (
        f"完整任务元信息已写入：`{meta_path}`。如不确定 task_id、分支、commit 范围、状态目录等字段，请优先读取该 meta 文件；"
        if meta_path
        else ""
    )
    return (
        "本任务由 CubeClaw DAG 编排。为避免 LLM 提前结束导致误判，"
        "你在任何最终退出路径（成功、失败、blocked、跳过）都必须写入机器可读结果文件。"
        f"结果文件路径必须是：`{expected['session_result_path']}`。{meta_hint}\n"
        "写入必须使用 JSON，且至少包含以下字段：\n"
        "```json\n"
        "{\n"
        "  \"schema_version\": 1,\n"
        f"  \"task_id\": \"{expected.get('task_id', '')}\",\n"
        f"  \"task_type\": \"{expected.get('task_type', '')}\",\n"
        f"  \"skill\": \"{expected.get('skill', '')}\",\n"
        "  \"status\": \"running | success | failed | blocked | skipped\",\n"
        "  \"success\": false,\n"
        "  \"background_tasks\": {\n"
        "    \"active\": false,\n"
        "    \"pending_count\": 0,\n"
        "    \"description\": \"optional: active background sub-agent/tool work\"\n"
        "  },\n"
        "  \"finished_at\": \"<ISO8601, final states only>\",\n"
        "  \"summary\": \"<brief result>\"\n"
        "}\n"
        "```\n"
        "如果任务没有成功完成，`success` 必须为 false，`status` 必须为 `failed` 或 `blocked`，"
        "并写入 `error` 或 `blocked_reason`。\n"
        "如果你启动了后台 task/sub-agent/tool，或正在执行长时间 tool-call（例如编译、pick、rebase），但最终结果尚未产出，必须立即把结果 JSON 保持为 "
        "`status=running`、`success=false`，并写入 `background_tasks.active=true`（或至少持续更新 `updated_at`/`summary`）、`pending_count`、"
        "`description`、`updated_at` 等进度字段；后台/长工具全部完成并完成汇总后，才能覆盖为最终态。\n"
        "DAG 只以该 JSON 作为最终完成依据；仅仅回复文本、收到 session.idle 或 step-finish 都不算完成。"
        "如果结果 JSON 仍是 running，CubeClaw 会认为任务仍在执行，不会把任务判为完成。\n"
        "最终结果中的 task_id/task_type/skill/end_commit 等字段必须与 meta 文件一致；"
        "pick 任务必须区分 working_branch 与 snapshot_branch，pick 过程中绝不能 checkout/switch 到 snapshot_branch。\n"
        "请在开始时确保结果文件所在目录存在；在任务 running 状态可先写入 success=false/status=running，"
        "最终退出前必须覆盖为最终状态。\n\n"
    )


# ── session_result 读取与校验 ─────────────────────────────────────

def load_session_result(path_value: str) -> Dict[str, Any]:
    if not path_value:
        raise FileNotFoundError("session_result_path is empty")
    path = Path(path_value)
    if not path.exists():
        raise FileNotFoundError(f"session_result.json 不存在: {path_value}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("session_result.json 顶层必须是 JSON object")
    return data


# ── 每种 task type 的专属字段校验器 ──────────────────────────────
#
# 签名：(data, expected) -> (ok: bool, reason: str)
# 只负责校验该 task type 独有的字段约束；通用字段（schema_version、
# task_id、status 等）由 validate_session_result 的公共阶段处理。
#
# 新增 task type 时，只需在此处添加一个函数并注册到 RESULT_VALIDATORS。

ResultValidator = Callable[[Dict[str, Any], Dict[str, Any]], Tuple[bool, str]]


def _validate_pick(data: Dict[str, Any], expected: Dict[str, Any]) -> Tuple[bool, str]:
    for key in ("working_branch", "snapshot_branch"):
        expected_value = expected.get(key)
        if expected_value and str(data.get(key, "")) != str(expected_value):
            return False, f"{key} 不匹配: expected={expected_value!r}, actual={data.get(key)!r}"
    working_branch = expected.get("working_branch")
    actual_branch = data.get("branch_name")
    if working_branch and actual_branch and str(actual_branch) != str(working_branch):
        return False, (
            f"pick branch_name 必须等于 working_branch: "
            f"expected={working_branch!r}, actual={actual_branch!r}"
        )

    # Inclusive end-commit safety net: if the agent reports success but its own
    # next_commit_sha still equals end_commit, the boundary commit has NOT been
    # picked yet (off-by-one trap). Mark the result invalid so the upper layer
    # can re-dispatch instead of materializing an incomplete snapshot branch.
    status = str(data.get("status", "")).lower()
    success = bool(data.get("success"))
    expected_end = expected.get("end_commit")
    next_sha = str(data.get("next_commit_sha", "")).strip()
    if (
        status == "success"
        and success
        and expected_end
        and next_sha
        and next_sha == str(expected_end)
    ):
        return False, (
            "pick 报告 status=success 但 next_commit_sha 仍等于 end_commit；"
            "这表示末尾 commit 还未被 pick（inclusive 语义）。"
            f"end_commit={expected_end!r}, next_commit_sha={next_sha!r}"
        )
    return True, "ok"


def _validate_build_win(data: Dict[str, Any], expected: Dict[str, Any]) -> Tuple[bool, str]:
    expected_buildfix_branch = expected.get("buildfix_branch")
    actual_branch = data.get("branch_name")
    if expected_buildfix_branch:
        if str(data.get("buildfix_branch", "")) != str(expected_buildfix_branch):
            return False, (
                f"buildfix_branch 不匹配: "
                f"expected={expected_buildfix_branch!r}, actual={data.get('buildfix_branch')!r}"
            )
        if actual_branch and str(actual_branch) != str(expected_buildfix_branch):
            return False, (
                f"build_win branch_name 必须等于 buildfix_branch: "
                f"expected={expected_buildfix_branch!r}, actual={actual_branch!r}"
            )
    return True, "ok"


def _validate_rebase(data: Dict[str, Any], expected: Dict[str, Any]) -> Tuple[bool, str]:
    actual_skill = str(data.get("skill", ""))
    if actual_skill and actual_skill != "batch-rebase":
        return False, f"rebase skill 不匹配: expected='batch-rebase', actual={actual_skill!r}"
    expected_working = expected.get("working_branch") or expected.get("branch_name")
    actual_branch = data.get("working_branch") or data.get("branch_name")
    if expected_working and actual_branch and str(actual_branch) != str(expected_working):
        return False, (
            f"rebase working_branch 不匹配: "
            f"expected={expected_working!r}, actual={actual_branch!r}"
        )
    expected_prev = expected.get("previous_branch")
    actual_prev = data.get("previous_branch")
    if expected_prev and actual_prev and str(actual_prev) != str(expected_prev):
        return False, (
            f"rebase previous_branch 不匹配: "
            f"expected={expected_prev!r}, actual={actual_prev!r}"
        )
    return True, "ok"


def _validate_branch_name(data: Dict[str, Any], expected: Dict[str, Any]) -> Tuple[bool, str]:
    """通用 fallback：只校验 branch_name 一致性（review / final_review / 其他）。"""
    expected_value = expected.get("branch_name")
    actual_branch = data.get("branch_name")
    if expected_value and actual_branch and str(actual_branch) != str(expected_value):
        return False, f"branch_name 不匹配: expected={expected_value!r}, actual={actual_branch!r}"
    return True, "ok"


# 注册表：task_type → 专属校验器
# 未注册的 task type 自动落到 _validate_branch_name（通用 fallback）。
RESULT_VALIDATORS: Dict[str, ResultValidator] = {
    "pick": _validate_pick,
    "build_win": _validate_build_win,
    "build_ios": _validate_build_win,
    "rebase": _validate_rebase,
    "review": _validate_branch_name,
    "final_review": _validate_branch_name,
}


def recover_review_session_result_if_possible(
    data: Dict[str, Any],
    expected: Dict[str, Any],
) -> Tuple[Dict[str, Any], bool, str]:
    """Recover review/final_review success when the agent left session_result running.

    batch-review writes heavyweight report files separately from the orchestration
    result.  In long final_review runs the LLM may finish after producing the report
    but forget to flip session_result.json from running to success.  When the expected
    report JSON exists and is structurally complete, synthesize the final
    session_result so DAG orchestration can trust a machine-readable result instead
    of text replies.
    """
    task_type = str(expected.get("task_type", ""))
    if task_type not in ("review", "final_review"):
        return data, False, "not a review task"
    if str(data.get("status", "")).lower() != "running":
        return data, False, "session_result status is not running"

    output_json = expected.get("review_output_json")
    if not output_json:
        return data, False, "review_output_json is not configured"
    output_path = Path(str(output_json))
    if not output_path.exists():
        return data, False, f"review output json not found: {output_path}"

    try:
        with output_path.open("r", encoding="utf-8-sig") as f:
            review_data = json.load(f)
    except Exception as exc:
        return data, False, f"review output json cannot be loaded: {exc}"
    if not isinstance(review_data, dict):
        return data, False, "review output json top-level is not an object"

    overall_verdict = str(review_data.get("overall_verdict") or review_data.get("verdict") or "").upper()
    if not overall_verdict:
        return data, False, "review output json missing overall_verdict"
    if "stats" not in review_data and "commits" not in review_data:
        return data, False, "review output json missing stats/commits summary"

    recovered = dict(data)
    recovered.update({
        "schema_version": expected.get("schema_version", 1),
        "task_id": expected.get("task_id", ""),
        "task_type": task_type,
        "skill": expected.get("skill", "batch-review"),
        "status": "success",
        "success": True,
        "review_ok": overall_verdict in ("APPROVE", "CONDITIONAL", "PASS", "PASS_WITH_WARNINGS"),
        "branch_name": recovered.get("branch_name") or expected.get("branch_name", ""),
        "working_dir": recovered.get("working_dir") or expected.get("working_dir", ""),
        "review_mode": recovered.get("review_mode") or expected.get("review_mode", ""),
        "overall_verdict": overall_verdict,
        "json_path": str(output_path),
        "report_path": str(expected.get("review_output_md") or recovered.get("report_path") or ""),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "summary": recovered.get("summary") or "Batch review completed; session_result recovered from report json",
        "recovered_from_report_json": True,
    })
    return recovered, True, "recovered from review output json"

def validate_session_result(data: Dict[str, Any], expected: Dict[str, Any]) -> Tuple[bool, str]:
    """校验 skill 写出的最终结果，避免只凭 LLM/SSE 结束误判成功。

    公共阶段：schema_version / task_id / task_type / skill / status / end_commit
    专属阶段：按 task_type 查表，调用对应的 ResultValidator
    """
    # ── 公共校验 ──────────────────────────────────────────────────
    if int(data.get("schema_version", 0) or 0) != int(expected.get("schema_version", 1)):
        return False, "schema_version 不匹配"
    for key in ("task_id", "task_type", "skill"):
        if str(data.get(key, "")) != str(expected.get(key, "")):
            return False, f"{key} 不匹配: expected={expected.get(key)!r}, actual={data.get(key)!r}"

    status = str(data.get("status", "")).lower()
    if status in ("running", ""):
        return False, f"session_result 状态不是最终态: {status or '<empty>'}"
    if status not in ("success", "failed", "blocked", "skipped"):
        return False, f"未知 session_result status: {status}"

    expected_end_commit = expected.get("end_commit")
    if expected_end_commit and str(data.get("end_commit", "")) != str(expected_end_commit):
        return False, f"end_commit 不匹配: expected={expected_end_commit!r}, actual={data.get('end_commit')!r}"

    # ── 专属校验（依赖注入） ──────────────────────────────────────
    task_type = str(expected.get("task_type", ""))
    validator = RESULT_VALIDATORS.get(task_type, _validate_branch_name)
    ok, reason = validator(data, expected)
    if not ok:
        return False, reason

    # ── success / status 一致性 ────────────────────────────────────
    success = bool(data.get("success"))
    if status in ("failed", "blocked") and success:
        return False, f"status={status} 时 success 不能为 true"
    if status == "success" and not success:
        return False, "status=success 但 success=false"
    return True, "ok"
