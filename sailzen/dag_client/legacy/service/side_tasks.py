from typing import Dict
import logging 
import asyncio
import os
logger = logging.getLogger(__name__)

def _task_label(task: dict) -> str:
    return f"{task['type']}(_{task['sub_batch_id'].split('_')[-1]})"


def _make_subprocess_runners():
    async def _run_cmd_passthrough(cmd, cwd, label, timeout=3600, quiet=False):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(
                f"{label} failed rc={proc.returncode}: {stderr.decode(errors='ignore') or stdout.decode(errors='ignore')}"
            )
        return proc

    async def _run_cmd_rc_passthrough(cmd, cwd, label, timeout=3600, quiet=False):
        try:
            await _run_cmd_passthrough(cmd, cwd, label, timeout, quiet)
            return 0
        except Exception:
            return 1

    async def _run_cmd_stdout_passthrough(cmd, cwd, label, timeout=3600, quiet=False):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(f"{label} failed: {stderr.decode(errors='ignore')}")
        return stdout.decode(errors="ignore").strip()

    return _run_cmd_passthrough, _run_cmd_stdout_passthrough, _run_cmd_rc_passthrough

async def _merge_buildfix_back_after_success(
    task: dict,
    batch_id: str,
    db,
    result: Dict,
) -> None:
    """Windows buildfix 成功后自动 merge-back 到对应 SubBatch 分支。"""
    try:
        sub_batch = await db.get_sub_batch(task["sub_batch_id"])
        if not sub_batch:
            return
        from bot_server.service.workspace_manager import WorkspaceManager
        wm = WorkspaceManager(*_make_subprocess_runners())
        health = await wm.merge_buildfix_back(sub_batch=sub_batch)
        result["merge_back"] = health
        logger.info(
            "[TaskRunner] ✅ %s → buildfix 已 merge-back: %s <- %s",
            _task_label(task), health.get("target_branch"), health.get("buildfix_branch"),
        )
    except Exception as exc:
        logger.exception("[TaskRunner] %s: buildfix merge-back 失败: %s", _task_label(task), exc)
        raise

async def _finalize_main_branch(
    task: dict,
    batch_id: str,
    db,
    result: dict,
) -> dict:
    """GlobalBatch finalization：备份主分支，再在 mcpe_gb 中将主分支重定向到最后一个 SubBatch snapshot。

    操作步骤：
      1. git branch backup/<working_branch_suffix> <working_branch>
         — 将当前主分支指针保存到 backup/ 命名空间
      2. 查找最后一个 SubBatch 的 snapshot 分支 (subbatch_worktree_health 中存储的 branch_name)
      3. 在 mcpe_gb worktree 执行 git checkout -B <working_branch> <snapshot_branch>
         — working_branch 当前被 mcpe_gb worktree 使用，不能在 repo_dir 中 git branch -f；
           checkout -B 会在持有该分支的 worktree 内安全地重置分支指针并强制刷新工作区。
      4. 将 bd/currentcommit.txt、bd/currentmilestone.txt 当前变动
         提交为 "Globalbatch mm/dd Finalization"，作为整个 batch 已结束、下一批可开始的标记。

    如果 payload 缺少 repo_dir（mock 模式 / workspace 未初始化），则跳过 git 操作并返回
    mock-style 结果，让 pipeline 继续正常完成。
    """
    payload = task.get("payload") or {}
    repo_dir = payload.get("repo_dir", "")
    mcpe_gb_dir = payload.get("mcpe_gb_dir", "")
    working_branch = payload.get("working_branch", "")
    backup_branch = payload.get("backup_branch", "")
    last_subbatch_id = payload.get("last_subbatch_id", "")

    label = _task_label(task)

    if not repo_dir or not mcpe_gb_dir or not working_branch or not backup_branch or not last_subbatch_id:
        logger.info(
            "[Finalization] %s: 缺少 repo_dir/mcpe_gb_dir/working_branch/backup_branch/last_subbatch_id，跳过 git 操作（mock 或未初始化 workspace）",
            label,
        )
        return {
            "finalized": False,
            "finalize_skipped": True,
            "finalize_skip_reason": "missing_payload_fields",
        }

    # ── 查找最后一个 SubBatch 的 snapshot 分支 ──────────────────
    batch = await db.get_batch(batch_id)
    if not batch:
        raise RuntimeError(f"[Finalization] batch {batch_id} 不存在")

    config = batch.get("config") or {}
    health_map = config.get("subbatch_worktree_health") or {}
    snapshot_health = health_map.get(last_subbatch_id)
    if not snapshot_health:
        raise RuntimeError(
            f"[Finalization] 找不到最后一个 SubBatch {last_subbatch_id} 的 snapshot 信息；"
            f"pick 阶段可能未成功物化 worktree。available keys: {list(health_map.keys())}"
        )

    snapshot_branch = snapshot_health.get("branch_name", "")
    if not snapshot_branch:
        raise RuntimeError(
            f"[Finalization] SubBatch {last_subbatch_id} 的 snapshot health 中缺少 branch_name: {snapshot_health}"
        )

    logger.info(
        "[Finalization] %s: working_branch=%s, backup_branch=%s, snapshot_branch=%s, repo_dir=%s, mcpe_gb_dir=%s",
        label, working_branch, backup_branch, snapshot_branch, repo_dir, mcpe_gb_dir,
    )

    _run_cmd, _run_cmd_stdout, _run_cmd_rc = _make_subprocess_runners()

    # ── Step 1: 备份主分支 ────────────────────────────────────────
    # git branch <backup_branch> <working_branch>
    # 若 backup 分支已存在则先删除（允许重跑）
    existing_backup_rc = await _run_cmd_rc(
        ["git", "branch", "--list", backup_branch],
        cwd=repo_dir,
        label=f"finalization/check-backup-{backup_branch}",
    )
    if existing_backup_rc == 0:
        # 检查是否真的存在（--list 输出非空）
        existing_backup_out = ""
        try:
            existing_backup_out = await _run_cmd_stdout(
                ["git", "branch", "--list", backup_branch],
                cwd=repo_dir,
                label=f"finalization/list-backup-{backup_branch}",
            )
        except Exception:
            pass
        if existing_backup_out.strip():
            logger.info(
                "[Finalization] %s: backup 分支 %s 已存在，先删除再重建",
                label, backup_branch,
            )
            await _run_cmd(
                ["git", "branch", "-D", backup_branch],
                cwd=repo_dir,
                label=f"finalization/delete-backup-{backup_branch}",
            )

    await _run_cmd(
        ["git", "branch", backup_branch, working_branch],
        cwd=repo_dir,
        label=f"finalization/backup-{working_branch}",
    )
    logger.info("[Finalization] %s: ✅ 主分支已备份 %s → %s", label, working_branch, backup_branch)

    # ── Step 2: 在持有主分支的 mcpe_gb worktree 中重置主分支到 snapshot 分支尖端 ──
    # working_branch 当前被 mcpe_gb worktree checkout，Git 禁止在 repo_dir 用
    # `git branch -f <working_branch> ...` 更新它。这里不需要重建 worktree，
    # 只需要在该 worktree 内 checkout -B；这会把 working_branch 重定向到
    # snapshot_branch，并用目标版本强制刷新工作区。
    await _run_cmd(
        ["git", "checkout", "-B", working_branch, snapshot_branch],
        cwd=mcpe_gb_dir,
        label=f"finalization/redirect-{working_branch}",
    )
    logger.info(
        "[Finalization] %s: ✅ 主分支已重定向 %s → %s",
        label, working_branch, snapshot_branch,
    )

    # ── Step 3: 提交 GlobalBatch 完成标记 ─────────────────────────────
    # checkout -B 到最后一个 SubBatch snapshot 后，mcpe_gb 工作区中 bd 状态文件
    # 保留了 batch 推进期间产生的变更。这里仅 stage 指定文件中的现有变动，避免把
    # 其他未跟踪/未预期文件卷入 finalization commit。
    finalization_files = payload.get("finalization_files") or [
        "bd/currentcommit.txt",
        "bd/currentmilestone.txt",
    ]
    commit_message = payload.get("finalization_commit_message") or "Globalbatch Finalization"
    existing_finalization_files = [
        path for path in finalization_files
        if os.path.exists(os.path.join(mcpe_gb_dir, path))
    ]
    missing_finalization_files = [
        path for path in finalization_files
        if path not in existing_finalization_files
    ]
    if missing_finalization_files:
        logger.warning(
            "[Finalization] %s: 完成标记文件不存在，跳过 stage: %s",
            label, ", ".join(missing_finalization_files),
        )

    finalization_commit_created = False
    finalization_commit_hash = ""
    staged_finalization_files = []
    if existing_finalization_files:
        await _run_cmd(
            ["git", "add", "--", *existing_finalization_files],
            cwd=mcpe_gb_dir,
            label="finalization/add-marker-files",
        )
        status_out = await _run_cmd_stdout(
            ["git", "diff", "--cached", "--name-only", "--", *existing_finalization_files],
            cwd=mcpe_gb_dir,
            label="finalization/status-marker-files",
        )
        staged_finalization_files = [
            line.strip() for line in status_out.splitlines()
            if line.strip()
        ]
        if staged_finalization_files:
            await _run_cmd(
                ["git", "commit", "-m", commit_message],
                cwd=mcpe_gb_dir,
                label="finalization/commit-marker-files",
            )
            finalization_commit_created = True
            finalization_commit_hash = await _run_cmd_stdout(
                ["git", "rev-parse", "HEAD"],
                cwd=mcpe_gb_dir,
                label="finalization/rev-parse-head",
            )
            logger.info(
                "[Finalization] %s: ✅ 完成标记已提交: %s (%s)",
                label, commit_message, finalization_commit_hash[:12],
            )
        else:
            logger.info(
                "[Finalization] %s: bd 状态文件没有变动，跳过完成标记提交: %s",
                label, ", ".join(existing_finalization_files),
            )
    else:
        logger.warning(
            "[Finalization] %s: 没有可提交的完成标记文件: %s",
            label, ", ".join(finalization_files),
        )

    return {
        "finalized": True,
        "backup_branch": backup_branch,
        "snapshot_branch": snapshot_branch,
        "working_branch": working_branch,
        "finalization_commit_message": commit_message,
        "finalization_commit_created": finalization_commit_created,
        "finalization_commit_hash": finalization_commit_hash,
        "finalization_files": existing_finalization_files,
        "finalization_missing_files": missing_finalization_files,
        "finalization_staged_files": staged_finalization_files,
        "summary": (
            f"✅ Finalized: backup={backup_branch}, "
            f"{working_branch} → {snapshot_branch}, "
            f"marker_commit={finalization_commit_hash[:12] if finalization_commit_created else 'skipped'}"
        ),
    }


async def _materialize_subbatch_after_pick(
    task: dict,
    batch_id: str,
    db,
    result: Dict,
) -> None:
    """pick 成功后，从 mcpe_gb 当前 HEAD 拉出当前 SubBatch 快照 worktree。
    """
    logger.info("[TaskRunner] %s: 开始物化 SubBatch 快照", _task_label(task))
    try:
        sub_batch = await db.get_sub_batch(task["sub_batch_id"])
        batch = await db.get_batch(batch_id)
        if not sub_batch or not batch:
            return
        config = batch.get("config") or {}
        workspace_paths = config.get("workspace_paths") or {}
        repo_dir = workspace_paths.get("repo_dir")
        mcpe_gb_dir = workspace_paths.get("mcpe_gb_dir")
        if not repo_dir or not mcpe_gb_dir:
            logger.warning(
                "[TaskRunner] %s: 缺少 repo_dir/mcpe_gb_dir，无法物化 SubBatch worktree",
                _task_label(task),
            )
            return

        from bot_server.service.workspace_manager import WorkspaceManager

        async def _run_cmd_passthrough(cmd, cwd, label, timeout=3600, quiet=False):
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"{label} failed rc={proc.returncode}: {stderr.decode(errors='ignore') or stdout.decode(errors='ignore')}"
                )
            return proc

        async def _run_cmd_rc_passthrough(cmd, cwd, label, timeout=3600, quiet=False):
            try:
                await _run_cmd_passthrough(cmd, cwd, label, timeout, quiet)
                return 0
            except Exception:
                return 1

        async def _run_cmd_stdout_passthrough(cmd, cwd, label, timeout=3600, quiet=False):
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            if proc.returncode != 0:
                raise RuntimeError(f"{label} failed: {stderr.decode(errors='ignore')}")
            return stdout.decode(errors="ignore").strip()

        wm = WorkspaceManager(
            _run_cmd_passthrough,
            _run_cmd_stdout_passthrough,
            _run_cmd_rc_passthrough,
        )
        # create snapshot for this subbatch
        health = await wm.materialize_subbatch_worktree(
            repo_dir=repo_dir,
            sub_batch=sub_batch,
            source_worktree=mcpe_gb_dir,
        )
        config.setdefault("subbatch_worktree_health", {})[sub_batch["id"]] = health
        batch["config"] = config
        await db.upsert_batch(batch)
        result["snapshot_branch"] = health.get("branch_name")
        result["snapshot_worktree_path"] = health.get("snapshot_worktree_path")
        result["snapshot_source_ref"] = health.get("source_ref")
        logger.info(
            "[TaskRunner] ✅ %s → 已物化 SubBatch 快照: %s @ %s",
            _task_label(task), health.get("snapshot_worktree_path"), health.get("source_ref", "")[:12],
        )
    except Exception as exc:
        logger.exception(
            "[TaskRunner] %s: pick 已成功但物化 SubBatch 快照失败: %s",
            _task_label(task), exc,
        )
        raise


