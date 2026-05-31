"""DAG 构建与调度引擎。

TaskScheduler 负责:
  1. 将 Batch 拆分为 SubBatch
  2. 为每个 SubBatch 创建 Task DAG
  3. 拓扑排序 + 依赖驱动调度
  4. 任务完成回调 → 解锁后继
  5. Rebase 触发机制

DAG 拓扑（各节点依赖关系）:

  Batch 入口:
    INIT_WORKSPACE → PICK_a

  每个 SubBatch 内:
    PICK → SUMMARY → ENSURE_WORKTREE ─┬─→ REVIEW
                  │                    └─→ REBASE → ENSURE_WORKTREE_BUILDFIX → BUILD_WIN
                  └──────────────────────→ BUILD_IOS

  review 链路（串行跨 SubBatch 推进）:
    PICK_a → SUMMARY_a → ENSURE_WORKTREE_a → REVIEW_a
    PICK_b depends on PICK_a (pick 仍然串行)
    REVIEW_a 只影响 FINAL_REVIEW

  buildfix 链路:
    SUMMARY_a → ENSURE_WORKTREE_a → ENSURE_WORKTREE_a_BUILDFIX → BUILD_WIN_a
    BUILD_WIN_b depends on BUILD_WIN_a (上一轮 buildfix 没过, 下一轮必然失败)
    REBASE_b    depends on BUILD_WIN_a (需吸收上一轮 buildfix merge-back)

  跨 SubBatch 串行约束:
    PICK:      PICK_b      depends on PICK_a
    REBASE:    REBASE_b    depends on BUILD_WIN_a
    BUILD_WIN: BUILD_WIN_b depends on BUILD_WIN_a
    BUILD_IOS: BUILD_IOS_b depends on BUILD_IOS_a

  Batch 级别:
    FINAL_REVIEW depends on ALL REVIEW_*，REPORT depends on FINAL_REVIEW
    FINALIZATION depends on REPORT：将主分支 netease/globalbatch/mm/dd 备份到
      backup/globalbatch/mm/dd，再强制移动到最后一个 SubBatch 的 snapshot 分支尖端，
      并提交 bd/currentcommit.txt、bd/currentmilestone.txt
      作为 Globalbatch mm/dd Finalization 标记。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from bot_server.models import (
    BatchStatus, BatchType, SubBatchStatus, TaskStatus, TaskType,
    TaskTimeoutConfig, make_sub_batch, make_task, make_event_log,
    new_id, now_iso,
)

logger = logging.getLogger(__name__)


# ── Batch Strategy ────────────────────────────────────────────────


class BatchStrategy:
    """批次处理策略基类。"""

    def split_commits(self, commits: list, config: dict) -> List[list]:
        size = config.get("sub_batch_size", 50)
        return [commits[i:i + size] for i in range(0, len(commits), size)]

    def branch_name(self, batch_id: str, created_at: str, index: int) -> str:
        raise NotImplementedError


class GlobalBatchStrategy(BatchStrategy):
    def branch_name(self, batch_id: str, created_at: str, index: int) -> str:
        try:
            dt = datetime.fromisoformat(created_at)
            date_str = dt.strftime("%m/%d")
        except Exception:
            date_str = "00/00"
        suffix = chr(ord('a') + index)
        return f"netease/globalbatch/{date_str}_{suffix}"


class NeteaseBatchStrategy(BatchStrategy):
    def split_commits(self, commits: list, config: dict) -> List[list]:
        size = config.get("sub_batch_size", 30)
        return [commits[i:i + size] for i in range(0, len(commits), size)]

    def branch_name(self, batch_id: str, created_at: str, index: int) -> str:
        try:
            dt = datetime.fromisoformat(created_at)
            date_str = dt.strftime("%m/%d")
        except Exception:
            date_str = "00/00"
        suffix = chr(ord('a') + index)
        return f"netease/neteasebatch/{date_str}_{suffix}"


_STRATEGIES = {
    BatchType.GLOBAL.value: GlobalBatchStrategy(),
    BatchType.NETEASE.value: NeteaseBatchStrategy(),
}


# ── DAG Builder ────────────────────────────────────────────────────


def build_dag_for_batch(batch: dict, sub_batches: List[dict], init_task_id: Optional[str] = None) -> Tuple[List[dict], List[Tuple[str, str]]]:
    """为一个 Batch 的所有 SubBatch 构建 Task DAG。

    拓扑规则:
      - Batch 入口: INIT_WORKSPACE → PICK_a
      - 每个 SubBatch:
          PICK → SUMMARY → ENSURE_WORKTREE ──→ REVIEW
                        │                  └──→ REBASE → ENSURE_WORKTREE_BUILDFIX → BUILD_WIN
                        └──────────────────────→ BUILD_IOS
      - review 不再依赖 build_win，直接依赖 ensure_worktree
      - buildfix 链路: ensure_worktree → rebase → ensure_worktree_buildfix → build_win
      - 跨 SubBatch 串行:
          PICK_b      depends on PICK_a
          REBASE_b    depends on BUILD_WIN_a
          BUILD_WIN_b depends on BUILD_WIN_a  (上一轮没过就别浪费资源)
          BUILD_IOS_b depends on BUILD_IOS_a
      - Batch 级 FINAL_REVIEW: depends on ALL REVIEW_*，REPORT depends on FINAL_REVIEW
      - Batch 级 FINALIZATION: depends on REPORT，执行主分支备份 + 重定向 + 完成标记提交
      - SUMMARY payload 携带 commit 基本信息

    返回 (tasks, edges)，其中 edges = [(from_id, to_id), ...]
    """
    all_tasks: List[dict] = []
    edges: List[Tuple[str, str]] = []

    prev_pick_id: Optional[str] = None
    prev_build_win_id: Optional[str] = None
    prev_build_ios_id: Optional[str] = None
    all_review_ids: List[str] = []

    init_workspace: Optional[dict] = None
    if sub_batches:
        init_workspace = make_task(
            sub_batches[0]["id"],
            TaskType.INIT_WORKSPACE.value,
            sub_batches[0].get("rebase_generation", 0),
            priority=5,
            timeout_seconds=TaskTimeoutConfig.INIT_WORKSPACE,
            payload=_build_init_workspace_payload(batch),
        )
        if init_task_id:
            init_workspace["id"] = init_task_id
        all_tasks.append(init_workspace)

    for idx, sb in enumerate(sub_batches):
        gen = sb.get("rebase_generation", 0)
        sb_id = sb["id"]

        # ── 创建 Task ────────────────────────────────────────────
        pick = make_task(sb_id, TaskType.PICK.value, gen, priority=10,
                         timeout_seconds=TaskTimeoutConfig.PICK,
                         payload=_build_task_payload(TaskType.PICK.value, sb))
        summary = make_task(sb_id, TaskType.SUMMARY.value, gen, priority=20,
                            timeout_seconds=TaskTimeoutConfig.SUMMARY,
                            payload=_build_summary_payload(sb))
        ensure_wt = make_task(sb_id, TaskType.ENSURE_WORKTREE.value, gen, priority=22,
                              timeout_seconds=TaskTimeoutConfig.ENSURE_WORKTREE,
                              payload=_build_ensure_worktree_payload(sb, variant="main"))
        ensure_wt_buildfix = make_task(sb_id, TaskType.ENSURE_WORKTREE.value, gen, priority=23,
                                       timeout_seconds=TaskTimeoutConfig.ENSURE_WORKTREE,
                                       payload=_build_ensure_worktree_payload(sb, variant="buildfix"))
        rebase = make_task(sb_id, TaskType.REBASE.value, gen, priority=25,
                           timeout_seconds=TaskTimeoutConfig.REBASE,
                           payload=_build_task_payload(TaskType.REBASE.value, sb))
        build_w = make_task(sb_id, TaskType.BUILD_WIN.value, gen, priority=30,
                            timeout_seconds=TaskTimeoutConfig.BUILD_WIN,
                            payload=_build_task_payload(TaskType.BUILD_WIN.value, sb))
        build_i = make_task(sb_id, TaskType.BUILD_IOS.value, gen, priority=30,
                            timeout_seconds=TaskTimeoutConfig.BUILD_IOS,
                            payload=_build_task_payload(TaskType.BUILD_IOS.value, sb))
        review = make_task(sb_id, TaskType.REVIEW.value, gen, priority=40,
                           timeout_seconds=TaskTimeoutConfig.REVIEW,
                           payload=_build_task_payload(TaskType.REVIEW.value, sb))

        if idx == 0:
            rebase["payload"]["skip_rebase"] = True
            rebase["payload"]["reason"] = "first_subbatch"

        # ── Batch 入口依赖 ────────────────────────────────────
        # INIT_WORKSPACE 是 GlobalBatch 初始化流程的统一入口；跳过 init 等价于 mock 这个节点。
        if idx == 0 and init_workspace:
            pick["dependencies"].append(init_workspace["id"])
            edges.append((init_workspace["id"], pick["id"]))

        # ── 同 SubBatch 内依赖 ──────────────────────────────────
        # PICK → SUMMARY → ENSURE_WORKTREE
        summary["dependencies"] = [pick["id"]]
        edges.append((pick["id"], summary["id"]))

        ensure_wt["dependencies"] = [summary["id"]]
        edges.append((summary["id"], ensure_wt["id"]))

        # ENSURE_WORKTREE → REVIEW (review 不依赖 build，直接跟在 worktree 就绪后)
        review["dependencies"] = [ensure_wt["id"]]
        edges.append((ensure_wt["id"], review["id"]))

        # ENSURE_WORKTREE → REBASE
        rebase["dependencies"] = [ensure_wt["id"]]
        edges.append((ensure_wt["id"], rebase["id"]))

        # ENSURE_WORKTREE → REBASE → ENSURE_WORKTREE_BUILDFIX → BUILD_WIN
        # 必须先 rebase 完成后再物化 buildfix worktree，保证 _buildfix 分支 base 于
        # 最新 rebase 后的 subbatch 分支，否则 _buildfix 基于旧快照，上一轮错误仍会带入。
        ensure_wt_buildfix["dependencies"] = [rebase["id"]]
        edges.append((rebase["id"], ensure_wt_buildfix["id"]))

        build_w["dependencies"] = [ensure_wt_buildfix["id"]]
        edges.append((ensure_wt_buildfix["id"], build_w["id"]))

        # SUMMARY → BUILD_IOS (iOS 不依赖 worktree，保持原有逻辑)
        build_i["dependencies"] = [summary["id"]]
        edges.append((summary["id"], build_i["id"]))

        # ── 跨 SubBatch 串行约束 ────────────────────────────────
        # PICK 串行: PICK_b depends on PICK_a
        if prev_pick_id:
            pick["dependencies"].append(prev_pick_id)
            edges.append((prev_pick_id, pick["id"]))

        # REBASE 串行/串接: REBASE_b depends on BUILD_WIN_a。
        # 语义：_b 的 worktree 必须在上一轮 buildfix merge-back 成立后再 rebase，
        # 否则后续 subbatch 会基于"未吸收上一轮 buildfix"的快照继续验证，失去 rebase 节点的意义。
        if idx > 0 and prev_build_win_id:
            rebase["dependencies"].append(prev_build_win_id)
            edges.append((prev_build_win_id, rebase["id"]))

        # BUILD_WIN 串行: BUILD_WIN_b depends on BUILD_WIN_a
        if prev_build_win_id:
            build_w["dependencies"].append(prev_build_win_id)
            edges.append((prev_build_win_id, build_w["id"]))

        # BUILD_IOS 串行: BUILD_IOS_b depends on BUILD_IOS_a
        if prev_build_ios_id:
            build_i["dependencies"].append(prev_build_ios_id)
            edges.append((prev_build_ios_id, build_i["id"]))

        # 记录本轮 ID 供下一轮引用
        prev_pick_id = pick["id"]
        prev_build_win_id = build_w["id"]
        prev_build_ios_id = build_i["id"]
        all_review_ids.append(review["id"])

        all_tasks.extend([pick, summary, ensure_wt, ensure_wt_buildfix, rebase, build_w, build_i, review])

    # ── Batch 级 REPORT + FINALIZATION ──────────────────────────────
    # REPORT 依赖所有 SubBatch 的 REVIEW 通过，挂在最后一个 SubBatch 下
    # FINALIZATION 依赖 REPORT，执行主分支备份 + 重定向 + 完成标记提交
    if sub_batches and all_review_ids:
        last_sb_id = sub_batches[-1]["id"]
        last_gen = sub_batches[-1].get("rebase_generation", 0)
        final_review = make_task(last_sb_id, TaskType.FINAL_REVIEW.value, last_gen, priority=45,
                                 timeout_seconds=TaskTimeoutConfig.FINAL_REVIEW,
                                 payload=_build_task_payload(TaskType.FINAL_REVIEW.value, sub_batches[-1]))
        final_review["dependencies"] = list(all_review_ids)
        for rev_id in all_review_ids:
            edges.append((rev_id, final_review["id"]))
        all_tasks.append(final_review)

        report = make_task(last_sb_id, TaskType.REPORT.value, last_gen, priority=50,
                           timeout_seconds=TaskTimeoutConfig.REPORT,
                           payload=_build_task_payload(TaskType.REPORT.value, sub_batches[-1]))
        report["dependencies"] = [final_review["id"], prev_build_win_id]
        edges.append((final_review["id"], report["id"]))
        edges.append((prev_build_win_id, report["id"]))
        all_tasks.append(report)

        finalization = make_task(last_sb_id, TaskType.FINALIZATION.value, last_gen, priority=55,
                                 timeout_seconds=TaskTimeoutConfig.FINALIZATION,
                                 payload=_build_finalization_payload(batch, sub_batches[-1]))
        finalization["dependencies"] = [report["id"]]
        edges.append((report["id"], finalization["id"]))
        all_tasks.append(finalization)

    return all_tasks, edges


def _build_init_workspace_payload(batch: dict) -> dict:
    """为 GlobalBatch 入口节点构建 payload。"""
    config = batch.get("config") or {}
    return {
        "batch_id": batch["id"],
        "task_type": TaskType.INIT_WORKSPACE.value,
        "predecessor_branch": config.get("predecessor_branch") or batch.get("predecessor_branch", ""),
        "working_branch": config.get("working_branch", ""),
        "work_dir": config.get("work_dir", ""),
        "workspace_paths": config.get("workspace_paths") or {},
        "subbatch_worktree_paths": config.get("subbatch_worktree_paths") or {},
        "commit_count": len(batch.get("commits") or []),
    }



def _build_summary_payload(sub_batch: dict) -> dict:
    """为 SUMMARY task 构建 payload，包含 commit 基本信息。

    payload 结构:
      {
        "sub_batch_id": "globalbatch_0424_a",
        "branch_name": "netease/globalbatch/04/24_a",
        "subbatch_base_branch": "netease/globalbatch/MM/DD",
        "batch_predecessor_branch": "netease/globalbatch/MM/DD",
        "commit_count": 50,
        "commits": [
          {"hash": "abc123...", "short": "abc123"},
          ...
        ]
      }
    `subbatch_base_branch` 是当前 SubBatch 的直接前置分支；
    `batch_predecessor_branch` 是整个 GlobalBatch 的前序分支 / mcpe_prev_batch 来源。
    """
    commits_raw = sub_batch.get("commits", [])
    commit_entries = []
    for c in commits_raw:
        commit_entries.append({
            "hash": c,
            "short": c[:8] if len(c) >= 8 else c,
        })

    return {
        "sub_batch_id": sub_batch["id"],
        "branch_name": sub_batch.get("branch_name", ""),
        "subbatch_base_branch": sub_batch.get("subbatch_base_branch", ""),
        "batch_predecessor_branch": sub_batch.get("batch_predecessor_branch", ""),
        "worktree_path": sub_batch.get("worktree_path") or "",
        "commit_count": len(commits_raw),
        "commits": commit_entries,
    }


def get_ready_tasks(tasks: List[dict]) -> List[dict]:
    """获取依赖已全部 SUCCESS 的 PENDING 任务。"""
    completed_ids = {t["id"] for t in tasks if t["status"] == TaskStatus.SUCCESS.value}
    ready = []
    for t in tasks:
        if t["status"] != TaskStatus.PENDING.value:
            continue
        deps = t.get("dependencies", [])
        if all(d in completed_ids for d in deps):
            ready.append(t)
    return ready


def _build_ensure_worktree_payload(sub_batch: dict, variant: str = "main") -> dict:
    """为 ENSURE_WORKTREE task 构建 payload。

    variant:
      - "main"     : 确保主 subbatch worktree 已就绪
      - "buildfix" : 确保 buildfix worktree（<branch>_buildfix）已就绪
    """
    source_branch = sub_batch.get("branch_name", "")
    worktree_path = sub_batch.get("worktree_path") or ""
    is_buildfix = variant == "buildfix"
    branch_name = f"{source_branch}_buildfix" if is_buildfix and source_branch else source_branch
    buildfix_worktree_path = f"{worktree_path}_buildfix" if worktree_path else ""
    payload = {
        "sub_batch_id": sub_batch["id"],
        "branch_name": branch_name,
        "subbatch_base_branch": sub_batch.get("subbatch_base_branch", ""),
        "batch_predecessor_branch": sub_batch.get("batch_predecessor_branch", ""),
        "worktree_path": buildfix_worktree_path if is_buildfix else worktree_path,
        "commit_count": len(sub_batch.get("commits", [])),
        "task_type": TaskType.ENSURE_WORKTREE.value,
        "variant": variant,
    }
    if is_buildfix:
        payload.update({
            "source_branch": source_branch,
            "base_ref": source_branch,
            "buildfix_branch": branch_name,
            "buildfix_worktree_path": buildfix_worktree_path,
        })
    return payload


def _build_task_payload(task_type: str, sub_batch: dict) -> dict:
    """为 task 构建通用 payload，确保 Dashboard / Runner 能拿到真实 worktree 信息。"""
    payload = {
        "sub_batch_id": sub_batch["id"],
        "branch_name": sub_batch.get("branch_name", ""),
        "subbatch_base_branch": sub_batch.get("subbatch_base_branch", ""),
        "batch_predecessor_branch": sub_batch.get("batch_predecessor_branch", ""),
        "worktree_path": sub_batch.get("worktree_path") or "",
        "commit_count": len(sub_batch.get("commits", [])),
        "task_type": task_type,
    }
    if task_type == TaskType.INIT_WORKSPACE.value:
        payload.update({
            "batch_id": sub_batch.get("batch_id", ""),
        })
    if task_type == TaskType.PICK.value:
        commits = sub_batch.get("commits", [])
        if commits:
            payload.update({
                "start_commit": commits[0],
                "end_commit": commits[-1],
            })
    return payload


def _build_finalization_payload(batch: dict, last_sub_batch: dict) -> dict:
    """为 FINALIZATION task 构建 payload。

    payload 包含:
      - working_branch:       整个 GlobalBatch 的主分支 (netease/globalbatch/mm/dd)
      - backup_branch:        备份目标分支名 (backup/globalbatch/mm/dd)
      - last_snapshot_branch: 最后一个 SubBatch pick 完成后物化的 snapshot 分支
                              (在运行时由 pick side-effect 写入 batch config，
                               此处记录 last_sub_batch 的 branch_name 供 runner 查找)
      - last_subbatch_id:     最后一个 SubBatch 的 ID
      - repo_dir:             git bare repo 目录 (从 batch config workspace_paths 取)
      - mcpe_gb_dir:          mcpe_gb worktree 目录
      - finalization_commit_message:
                              Batch 完成标记提交信息，格式为 Globalbatch mm/dd Finalization
      - finalization_files:   需要纳入完成标记提交的 bd 状态文件列表
    """
    config = batch.get("config") or {}
    workspace_paths = config.get("workspace_paths") or {}
    working_branch = config.get("working_branch", "")

    # 构造备份分支名：netease/globalbatch/mm/dd → backup/globalbatch/mm/dd
    backup_branch = ""
    if working_branch.startswith("netease/"):
        backup_branch = "backup/" + working_branch[len("netease/"):]

    finalization_batch_name = ""
    globalbatch_prefix = "netease/globalbatch/"
    if working_branch.startswith(globalbatch_prefix):
        finalization_batch_name = working_branch[len(globalbatch_prefix):]
    else:
        finalization_batch_name = working_branch.rsplit("/", 1)[-1]
    finalization_commit_message = f"Globalbatch {finalization_batch_name} Finalization"

    return {
        "task_type": TaskType.FINALIZATION.value,
        "batch_id": batch["id"],
        "working_branch": working_branch,
        "backup_branch": backup_branch,
        "last_subbatch_id": last_sub_batch["id"],
        "last_subbatch_branch": last_sub_batch.get("branch_name", ""),
        "repo_dir": workspace_paths.get("repo_dir", ""),
        "mcpe_gb_dir": workspace_paths.get("mcpe_gb_dir", ""),
        "finalization_commit_message": finalization_commit_message,
        "finalization_files": [
            "bd/currentcommit.txt",
            "bd/currentmilestone.txt",
            "bd/ConflictRules/PrePicked.txt"
        ],
    }


# ── Scheduler ──────────────────────────────────────────────────────


class TaskScheduler:
    """Manager 调度器核心。"""

    def __init__(self, db):
        self.db = db
        self._paused = False

    async def schedule_batch(
        self,
        batch: dict,
        subbatch_overrides: Optional[List[dict]] = None,
        init_task_id: Optional[str] = None,
    ) -> List[dict]:
        """将 Batch 拆分为 SubBatch 并构建 DAG，返回所有 tasks。

        Args:
            batch: Batch dict。
            subbatch_overrides: 可选的 SubBatch 预规划信息。Real GlobalBatch 初始化会在
                WorkspaceManager 中提前规划 branch / subbatch_base_branch / worktree_path，调度器应复用
                这些真实路径，而不是再次按默认策略泛化生成。
            init_task_id: 可选的已有 init_workspace task ID。如果提供，DAG 会复用此 ID
                而不是创建新 task。用于两阶段初始化：Phase 0 先创建 init_workspace 入队，
                Phase 3 完成后用它来连接后续节点。
        """
        strategy = _STRATEGIES.get(batch["batch_type"], GlobalBatchStrategy())
        commits = batch.get("commits", [])
        config = batch.get("config", {})

        if not commits:
            raise ValueError("Batch has no commits")

        # 1. 切分 SubBatch
        commit_groups = strategy.split_commits(commits, config)
        sub_batches = []
        overrides = subbatch_overrides or []
        for idx, group in enumerate(commit_groups):
            override = overrides[idx] if idx < len(overrides) else {}
            subbatch_base = override.get("subbatch_base_branch") or (sub_batches[-1]["branch_name"] if sub_batches else batch["predecessor_branch"])
            sb = make_sub_batch(
                batch_id=batch["id"],
                index=idx,
                branch_name=override.get("branch_name") or strategy.branch_name(batch["id"], batch["created_at"], idx),
                subbatch_base_branch=subbatch_base,
                commits=override.get("commits") or group,
            )
            if override.get("id"):
                sb["id"] = override["id"]
            # 非持久字段，供 task payload / Dashboard 展示使用。
            sb["batch_predecessor_branch"] = config.get("predecessor_branch") or batch.get("predecessor_branch", "")
            if override.get("worktree_path"):
                sb["worktree_path"] = override["worktree_path"]
            sub_batches.append(sb)

        # 2. 持久化 SubBatch
        for idx, sb in enumerate(sub_batches):
            await self.db.upsert_sub_batch(sb)

        # 3. 构建 DAG
        all_tasks, edges = build_dag_for_batch(batch, sub_batches, init_task_id=init_task_id)

        # 4. 持久化 Task — 已存在的 task 保留其状态（如 init_workspace 已在 Two-Phase Init 中入队）
        for t in all_tasks:
            existing = await self.db.get_task(t["id"])
            if existing and existing.get("status") not in (
                TaskStatus.PENDING.value,
            ) and t["type"] == TaskType.INIT_WORKSPACE.value:
                # 复用已入队/运行中的 init_workspace，不覆盖其状态
                logger.info(
                    "schedule_batch: 复用已有 %s task %s (status=%s)",
                    t["type"], t["id"][:8], existing.get("status"),
                )
                t["status"] = existing["status"]
                t["queued_at"] = existing.get("queued_at")
                t["started_at"] = existing.get("started_at")
            await self.db.upsert_task(t)

        # 5. 更新 Batch 状态
        await self.db.update_batch_status(
            batch["id"], BatchStatus.RUNNING.value, started_at=now_iso())

        # 6. 将就绪 Task 入队
        ready = get_ready_tasks(all_tasks)
        for t in ready:
            t["status"] = TaskStatus.QUEUED.value
            t["queued_at"] = now_iso()
            await self.db.upsert_task(t)

        # 7. 事件日志
        await self.db.log_event(make_event_log(
            "batch.scheduled", "batch", batch["id"],
            new_state={"sub_batches": len(sub_batches), "tasks": len(all_tasks)},
        ))

        logger.info(
            "Batch %s scheduled: %d sub-batches, %d tasks, %d ready",
            batch["id"], len(sub_batches), len(all_tasks), len(ready),
        )
        return all_tasks

    async def on_task_completed(self, task_id: str, success: bool,
                                result: dict | None = None,
                                error: dict | None = None) -> None:
        """任务完成回调。"""
        task = await self.db.get_task(task_id)
        if not task:
            logger.error("Task not found: %s", task_id)
            return

        old_status = task["status"]

        if success:
            task = {
                **task,
                "status": TaskStatus.SUCCESS.value,
                "result": result,
                "completed_at": now_iso(),
            }
            # 任务完成是状态机的关键边沿，使用定向 UPDATE，避免把 runner 早先持有的
            # detached/stale task dict 通过 merge/upsert 写回时覆盖已完成状态。
            updated = await self.db.update_task_status(
                task_id,
                TaskStatus.SUCCESS.value,
                expected_statuses=[TaskStatus.RUNNING.value, TaskStatus.ASSIGNED.value],
                result=result,
                completed_at=task["completed_at"],
            )
            if not updated:
                latest = await self.db.get_task(task_id)
                latest_status = (latest or {}).get("status")
                if latest_status == TaskStatus.SUCCESS.value:
                    task = latest or task
                    logger.info(
                        "Task %s (%s) already success; continue completion side effects",
                        task_id[:8], task.get("type"),
                    )
                else:
                    logger.warning(
                        "Skip completing task %s (%s): expected running/assigned, actual=%s",
                        task_id[:8], task.get("type"), latest_status,
                    )
                    return

            # 解锁后继
            await self._unlock_dependents(task)

            # 检查 SubBatch / Batch 是否全部完成
            await self._check_completion(task)

        else:
            task["completed_at"] = now_iso()
            if task["retry_count"] < task["max_retries"]:
                task["retry_count"] += 1
                task["status"] = TaskStatus.QUEUED.value
                task["queued_at"] = now_iso()
                logger.info(
                    "Retrying task %s (%s): attempt %d/%d",
                    task_id[:8], task.get("type"), task["retry_count"], task["max_retries"],
                )
                # 重试是主动把任务从 RUNNING 降回 QUEUED 的合法操作，
                # 需要 force=True 绕过 rank 防回退检查（rank: queued < running）。
                updated = await self.db.update_task_status(
                    task_id,
                    TaskStatus.QUEUED.value,
                    expected_statuses=[TaskStatus.RUNNING.value, TaskStatus.ASSIGNED.value],
                    force=True,
                    error=error,
                    retry_count=task["retry_count"],
                    queued_at=task["queued_at"],
                    started_at=None,
                    completed_at=None,
                )
            else:
                task["status"] = TaskStatus.BLOCKED.value
                updated = await self.db.update_task_status(
                    task_id,
                    TaskStatus.BLOCKED.value,
                    expected_statuses=[TaskStatus.RUNNING.value, TaskStatus.ASSIGNED.value],
                    error=error,
                    completed_at=task["completed_at"],
                )
            if not updated:
                latest = await self.db.get_task(task_id)
                logger.warning(
                    "Skip failing task %s (%s): expected running/assigned, actual=%s",
                    task_id[:8], task.get("type"), (latest or {}).get("status"),
                )
                return

            if task["status"] == TaskStatus.BLOCKED.value:
                logger.warning(
                    "Task %s (%s) BLOCKED; batch status will be decided by DAG reachability",
                    task_id[:8], task.get("type"),
                )

        # 事件日志
        await self.db.log_event(make_event_log(
            "task.completed", "task", task_id,
            old_state={"status": old_status},
            new_state={"status": task["status"], "success": success},
        ))

        # 释放 Agent
        if task.get("agent_id"):
            from bot_server.models import AgentStatus
            await self.db.update_agent_status(
                task["agent_id"], AgentStatus.ONLINE.value, current_task_id=None)

    async def _unlock_dependents(self, completed_task: dict) -> None:
        """解锁依赖于 completed_task 的后继任务。"""
        sb = await self.db.get_sub_batch(completed_task["sub_batch_id"])
        if not sb:
            return

        batch_tasks = await self.db.get_tasks_by_batch(sb["batch_id"])
        completed_ids = {t["id"] for t in batch_tasks if t["status"] == TaskStatus.SUCCESS.value}
        completed_ids.add(completed_task["id"])  # 包含刚完成的

        for t in batch_tasks:
            if t["status"] != TaskStatus.PENDING.value:
                continue
            deps = t.get("dependencies", [])
            if deps and all(d in completed_ids for d in deps):
                queued_at = now_iso()
                queued = await self.db.update_task_status(
                    t["id"],
                    TaskStatus.QUEUED.value,
                    expected_statuses=[TaskStatus.PENDING.value],
                    queued_at=queued_at,
                )
                if queued:
                    logger.info("Unlocked task %s (%s)", t["id"][:8], t["type"])
                else:
                    latest = await self.db.get_task(t["id"])
                    logger.info(
                        "Skip unlock task %s (%s): expected pending, actual=%s",
                        t["id"][:8], t["type"], (latest or {}).get("status"),
                    )

    async def _check_completion(self, task: dict) -> None:
        """检查 SubBatch 和 Batch 是否已完成。"""
        # SubBatch 完成检查
        sb_tasks = await self.db.get_tasks(sub_batch_id=task["sub_batch_id"])
        all_done = all(t["status"] in (TaskStatus.SUCCESS.value, TaskStatus.CANCELLED.value,
                                        TaskStatus.SUPERSEDED.value)
                       for t in sb_tasks)
        if all_done:
            await self.db.update_sub_batch_status(
                task["sub_batch_id"], SubBatchStatus.COMPLETED.value)

        # Batch 完成检查必须基于全 Batch 的 task 终态，而不能只看 SubBatch 状态。
        # resume-from-node 会把目标节点后续重置为 PENDING；如果目标所在 SubBatch
        # 之前已经是 COMPLETED，完成目标节点后可能先 unlock 后继、再误判所有 SubBatch
        # 仍为 COMPLETED，导致 Batch 提前 COMPLETED，把刚解锁的 QUEUED 后继挡在终态外。
        sb = await self.db.get_sub_batch(task["sub_batch_id"])
        if not sb:
            return
        batch_tasks = await self.db.get_tasks_by_batch(sb["batch_id"])
        incomplete = [
            t for t in batch_tasks
            if t["status"] not in (
                TaskStatus.SUCCESS.value,
                TaskStatus.CANCELLED.value,
                TaskStatus.SUPERSEDED.value,
            )
        ]
        if incomplete:
            logger.debug(
                "Batch %s not complete: %d unfinished tasks, examples=%s",
                sb["batch_id"],
                len(incomplete),
                [(t["id"][:8], t.get("type"), t.get("status")) for t in incomplete[:5]],
            )
            return

        all_sbs = await self.db.get_sub_batches(sb["batch_id"])
        if all(s["status"] == SubBatchStatus.COMPLETED.value for s in all_sbs):
            await self.db.update_batch_status(
                sb["batch_id"], BatchStatus.COMPLETED.value, completed_at=now_iso())
            logger.info("Batch %s COMPLETED", sb["batch_id"])

    async def get_queued_tasks(self, limit: int = 10) -> List[dict]:
        """获取等待分配的任务。"""
        return await self.db.get_tasks(status=TaskStatus.QUEUED.value)

    async def assign_task(self, task_id: str, agent_id: str) -> bool:
        """分配任务到 Agent。"""
        task = await self.db.get_task(task_id)
        agent = await self.db.get_agent(agent_id)
        if not task or not agent:
            return False

        from bot_server.models import AgentStatus
        updated = await self.db.update_task_status(
            task_id,
            TaskStatus.ASSIGNED.value,
            expected_statuses=[TaskStatus.QUEUED.value],
            agent_id=agent_id,
            started_at=now_iso(),
        )
        if not updated:
            return False

        await self.db.update_agent_status(
            agent_id, AgentStatus.BUSY.value, current_task_id=task_id)

        await self.db.log_event(make_event_log(
            "task.assigned", "task", task_id,
            new_state={"agent_id": agent_id},
        ))
        return True

    def pause(self) -> None:
        self._paused = True
        logger.warning("Scheduler PAUSED")

    def resume(self) -> None:
        self._paused = False
        logger.info("Scheduler RESUMED")

    @property
    def is_paused(self) -> bool:
        return self._paused
