"""Workspace 管理服务。

WorkspaceManager 负责把 GlobalBatch 初始化过程中分散的 git clone / fetch /
worktree / 路径规划逻辑集中起来，形成稳定、可恢复、可观测的工作区标准结构。

标准目录结构：

    <batch_ws>/
      <repo_name>/        # bare-ish 主 clone，作为 worktree 管理根
      mcpe_main/          # main / github_branch 参考 worktree
      mcpe_prev_batch/    # 前序 GlobalBatch 参考 worktree
      mcpe_gb/            # 当前 GlobalBatch 初始化 / 主工作 worktree
      mcpe_gb_a/          # SubBatch _a worktree
      mcpe_gb_b/          # SubBatch _b worktree
      temp/               # skill 临时输出目录，位于 repo 外
      _logs/              # CubeClaw 初始化和调度日志

该模块不直接依赖数据库，方便在初始化、调度器、未来 TaskDispatcher 中复用。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

RunCommand = Callable[[List[str], str, str, int, bool], Awaitable[subprocess.CompletedProcess]]
RunCommandRc = Callable[[List[str], str, str, int, bool], Awaitable[int]]
RunCommandStdout = Callable[[List[str], str, str, int, bool], Awaitable[str]]


@dataclass(slots=True)
class WorkspaceLayout:
    """一次 GlobalBatch 的标准工作区路径。"""

    workspace_root: str
    batch_workspace_dir: str
    repo_dir: str
    mcpe_main_dir: str
    mcpe_prev_batch_dir: str
    mcpe_gb_dir: str
    temp_dir: str
    logs_dir: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class WorktreeHealth:
    """worktree 健康检查结果。"""

    path: str
    exists: bool
    is_git_worktree: bool
    branch: str = ""
    head: str = ""
    clean: bool = False
    bd_exists: bool = False
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WorkspaceManager:
    """集中管理 CubeClaw 的 git 工作区与 worktree。

    WorkspaceManager 本身只负责编排路径和 git 命令；命令执行、日志、超时策略由调用方注入。
    在 `gb_init.py` 中注入的是已有的 `_run_cmd` / `_run_cmd_stdout` / `_run_cmd_rc`，
    因此可以复用初始化阶段的流式日志和文件日志。
    """

    def __init__(
        self,
        run_cmd: RunCommand,
        run_cmd_stdout: RunCommandStdout,
        run_cmd_rc: RunCommandRc,
    ) -> None:
        self._run_cmd = run_cmd
        self._run_cmd_stdout = run_cmd_stdout
        self._run_cmd_rc = run_cmd_rc

    async def prepare_globalbatch_workspace(
        self,
        *,
        workspace_root: str,
        github_repo: str,
        github_branch: str,
        predecessor_branch: str,
        batch_workspace_name: str,
    ) -> WorkspaceLayout:
        """创建或刷新标准 GlobalBatch 工作区。

        该方法会：
        1. 创建 `<workspace_root>/<batch_workspace_name>`、`temp`、`_logs`；
        2. clone 或 fetch 主仓库；
        3. 创建 / 刷新 `mcpe_main` 指向 `origin/<github_branch>`；
        4. 创建 / 刷新 `mcpe_prev_batch` 指向 `origin/<predecessor_branch>`；
        5. 创建 / 刷新 `mcpe_gb` 指向 `origin/<predecessor_branch>`，供后续 start_globalbatch 使用。
        """
        workspace_root_path = Path(workspace_root).expanduser().resolve()
        batch_dir = workspace_root_path / batch_workspace_name
        temp_dir = batch_dir / "temp"
        logs_dir = batch_dir / "_logs"

        workspace_root_path.mkdir(parents=True, exist_ok=True)
        batch_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        repo_name = self._repo_name_from_url(github_repo)
        repo_dir = batch_dir / repo_name

        logger.info("[WorkspaceManager] 标准工作区: %s", batch_dir)
        logger.info("[WorkspaceManager] repo=%s branch=%s predecessor=%s", github_repo, github_branch, predecessor_branch)

        await self._ensure_repo(
            repo_dir=repo_dir,
            parent_dir=batch_dir,
            github_repo=github_repo,
            github_branch=github_branch,
            repo_name=repo_name,
        )

        await self._fetch_ref(repo_dir, github_branch, label="fetch-main")
        await self._fetch_ref(repo_dir, predecessor_branch, label="fetch-predecessor")
        await self._run_cmd(
            ["git", "worktree", "prune"],
            cwd=str(repo_dir),
            label="Workspace/worktree-prune",
            timeout=120,
            quiet=False,
        )

        mcpe_main_dir = batch_dir / "mcpe_main"
        mcpe_prev_batch_dir = batch_dir / "mcpe_prev_batch"
        mcpe_gb_dir = batch_dir / "mcpe_gb"

        await self.ensure_reference_worktree(
            repo_dir=repo_dir,
            path=mcpe_main_dir,
            ref=f"origin/{github_branch}",
            label="mcpe_main",
        )
        await self.ensure_reference_worktree(
            repo_dir=repo_dir,
            path=mcpe_prev_batch_dir,
            ref=f"origin/{predecessor_branch}",
            label="mcpe_prev_batch",
        )
        await self.ensure_reference_worktree(
            repo_dir=repo_dir,
            path=mcpe_gb_dir,
            ref=f"origin/{predecessor_branch}",
            label="mcpe_gb",
        )

        return WorkspaceLayout(
            workspace_root=str(workspace_root_path),
            batch_workspace_dir=str(batch_dir),
            repo_dir=str(repo_dir),
            mcpe_main_dir=str(mcpe_main_dir),
            mcpe_prev_batch_dir=str(mcpe_prev_batch_dir),
            mcpe_gb_dir=str(mcpe_gb_dir),
            temp_dir=str(temp_dir),
            logs_dir=str(logs_dir),
        )

    async def ensure_reference_worktree(
        self,
        *,
        repo_dir: Path,
        path: Path,
        ref: str,
        label: str,
    ) -> None:
        """创建一个可安全重建的参考 worktree。

        参考 worktree 不承载人工修改，因此采用 remove + add 的方式保证幂等、干净、可预测。
        """
        await self._remove_worktree_if_exists(repo_dir, path, label=label)
        await self._run_cmd(
            ["git", "worktree", "add", "--detach", str(path), ref],
            cwd=str(repo_dir),
            label=f"Workspace/worktree-add-{label}",
            timeout=3600,
            quiet=False,
        )
        await self._run_cmd(
            ["git", "reset", "--hard", ref],
            cwd=str(path),
            label=f"Workspace/reset-{label}",
            timeout=300,
            quiet=False,
        )
        await self._run_cmd_rc(
            ["git", "clean", "-fd"],
            cwd=str(path),
            label=f"Workspace/clean-{label}",
            timeout=300,
            quiet=False,
        )

    def plan_subbatch_worktree_paths(
        self,
        *,
        batch_workspace_dir: str,
        subbatch_count: int,
        prefix: str = "mcpe_gb",
    ) -> Dict[str, str]:
        """规划 SubBatch suffix 到 worktree path 的映射，不执行 git 操作。"""
        base = Path(batch_workspace_dir)
        return {
            chr(ord("a") + idx): str(base / f"{prefix}_{chr(ord('a') + idx)}")
            for idx in range(subbatch_count)
        }

    def plan_buildfix_worktree_path(
        self,
        *,
        subbatch_worktree_path: str,
    ) -> str:
        """规划 buildfix worktree path。

        约定与 buildfix skill 要求保持一致：目录名必须带 `_buildfix` 后缀。
        """
        return f"{subbatch_worktree_path}_buildfix"

    async def merge_buildfix_back(
        self,
        *,
        sub_batch: dict,
    ) -> Dict[str, Any]:
        """将 `<branch>_buildfix` 合并回对应 SubBatch 分支 worktree。"""
        worktree_path = sub_batch.get("worktree_path")
        if not worktree_path:
            raise ValueError(f"SubBatch {sub_batch.get('id', '')} missing worktree_path")
        target_branch = sub_batch["branch_name"]
        buildfix_branch = f"{target_branch}_buildfix"
        target_path = Path(worktree_path)

        await self._run_cmd(
            ["git", "checkout", target_branch],
            cwd=str(target_path),
            label="Workspace/mergeback-checkout-target",
            timeout=120,
            quiet=False,
        )
        merge_base_rc = await self._run_cmd_rc(
            ["git", "merge-base", "--is-ancestor", buildfix_branch, target_branch],
            cwd=str(target_path),
            label="Workspace/mergeback-already-merged",
            timeout=120,
            quiet=True,
        )
        already_merged = merge_base_rc == 0
        if already_merged:
            logger.info(
                "[WorkspaceManager] buildfix 已包含在目标分支，跳过 merge-back: %s <- %s",
                target_branch, buildfix_branch,
            )
        else:
            # 在 merge 之前创建备份分支，标记 pre-merge 状态，
            # 方便后续 SubBatch/Batch 定位正确的 merge-base。
            backup_branch = f"{target_branch}_pre_buildfix_backup"
            # 从 worktree 内执行 git branch 操作 — git worktree 会自动解析到主 repo。
            backup_exists = (await self._run_cmd_rc(
                ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{backup_branch}"],
                cwd=str(target_path),
                label="Workspace/mergeback-check-backup",
                timeout=30,
                quiet=True,
            )) == 0
            if backup_exists:
                await self._run_cmd(
                    ["git", "branch", "-f", backup_branch, target_branch],
                    cwd=str(target_path),
                    label="Workspace/mergeback-backup-update",
                    timeout=120,
                    quiet=False,
                )
            else:
                await self._run_cmd(
                    ["git", "branch", backup_branch, target_branch],
                    cwd=str(target_path),
                    label="Workspace/mergeback-backup-create",
                    timeout=120,
                    quiet=False,
                )
            logger.info(
                "[WorkspaceManager] pre-merge 备份: %s → %s",
                backup_branch, target_branch,
            )

            await self._run_cmd(
                ["git", "merge", buildfix_branch, "-m", f"Merge buildfix {buildfix_branch}"],
                cwd=str(target_path),
                label="Workspace/mergeback-buildfix",
                timeout=1800,
                quiet=False,
            )
        health = self.health_check_worktree(str(target_path)).to_dict()
        health.update({
            "target_branch": target_branch,
            "buildfix_branch": buildfix_branch,
            "merged_worktree_path": str(target_path),
            "already_merged": already_merged,
            "pre_merge_backup_branch": f"{target_branch}_pre_buildfix_backup",
        })
        return health

    async def ensure_buildfix_worktree(
        self,
        *,
        repo_dir: str,
        sub_batch: dict,
        source_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """为 Windows buildfix 创建或复用 `<subbatch>_buildfix` worktree。

        分支命名为 `<subbatch_branch>_buildfix`，base 默认取 SubBatch 当前分支。
        """
        worktree_path = sub_batch.get("worktree_path")
        if not worktree_path:
            raise ValueError(f"SubBatch {sub_batch.get('id', '')} missing worktree_path")

        branch_name = sub_batch["branch_name"]
        buildfix_branch = f"{branch_name}_buildfix"
        buildfix_path = Path(self.plan_buildfix_worktree_path(
            subbatch_worktree_path=worktree_path,
        ))
        base_ref = source_ref or branch_name
        label = f"buildfix-{sub_batch.get('id', '').split('_')[-1] or 'unknown'}"

        await self.ensure_branch_worktree(
            repo_dir=Path(repo_dir),
            path=buildfix_path,
            branch_name=buildfix_branch,
            base_ref=base_ref,
            label=label,
        )
        health = self.health_check_worktree(str(buildfix_path)).to_dict()
        health.update({
            "buildfix_branch": buildfix_branch,
            "buildfix_worktree_path": str(buildfix_path),
            "source_branch": branch_name,
        })
        return health

    async def materialize_subbatch_worktree(
        self,
        *,
        repo_dir: str,
        sub_batch: dict,
        source_worktree: Optional[str] = None,
        source_ref: str = "HEAD",
    ) -> Dict[str, Any]:
        """从当前 pick 主线物化一个 SubBatch 快照 worktree。

        正确的 GlobalBatch MVP 语义是：Branch Dance 始终在 `mcpe_gb` 中连续 pick，
        `bd/currentcommit.txt`、`bd/commits.txt` 以及 `../temp/agent_session.json` 都围绕这个
        主工作区推进。每个 SubBatch 的 `_a/_b/_c` 分支不是提前从前一个 SubBatch
        创建并相互 merge，而是在对应 pick chunk 完成后，从 `mcpe_gb` 当前 HEAD 拉出快照。
        """
        worktree_path = sub_batch.get("worktree_path")
        if not worktree_path:
            raise ValueError(f"SubBatch {sub_batch.get('id', '')} missing worktree_path")

        repo_path = Path(repo_dir)
        branch_name = sub_batch["branch_name"]
        path = Path(worktree_path)
        label = f"materialize-{sub_batch.get('id', '').split('_')[-1] or 'unknown'}"

        if source_worktree:
            source_sha = await self._run_cmd_stdout(
                ["git", "rev-parse", "HEAD"],
                cwd=str(source_worktree),
                label=f"Workspace/rev-parse-source-{label}",
                timeout=30,
                quiet=True,
            )
        else:
            source_sha = await self._run_cmd_stdout(
                ["git", "rev-parse", source_ref],
                cwd=str(repo_path),
                label=f"Workspace/rev-parse-source-{label}",
                timeout=30,
                quiet=True,
            )
        source_sha = source_sha.strip()
        if not source_sha:
            raise RuntimeError(f"无法解析 SubBatch 物化源: {source_worktree or source_ref}")

        await self._remove_worktree_if_exists(repo_path, path, label=label)

        branch_exists = await self._local_branch_exists(repo_path, branch_name)
        if branch_exists:
            # it is safe to overlap
            await self._run_cmd(
                ["git", "branch", "-f", branch_name, source_sha],
                cwd=str(repo_path),
                label=f"Workspace/branch-reset-{label}",
                timeout=120,
                quiet=False,
            )
        else:
            # not exits, new
            await self._run_cmd(
                ["git", "branch", branch_name, source_sha],
                cwd=str(repo_path),
                label=f"Workspace/branch-{label}",
                timeout=120,
                quiet=False,
            )

        await self._run_cmd(
            ["git", "worktree", "add", "--force", str(path), branch_name],
            cwd=str(repo_path),
            label=f"Workspace/worktree-add-{label}",
            timeout=3600,
            quiet=False,
        )

        health = self.health_check_worktree(str(path)).to_dict()
        health.update({
            "branch_name": branch_name,
            "source_ref": source_sha,
            "snapshot_worktree_path": str(path),
        })
        return health

    async def ensure_subbatch_worktrees(
        self,
        *,
        repo_dir: str,
        sub_batches: Iterable[dict],
    ) -> Dict[str, Dict[str, Any]]:
        """为 SubBatch 创建或复用 worktree，并返回健康检查结果。

        每个 SubBatch dict 需要包含：
        - `branch_name`
        - `subbatch_base_branch`
        - `worktree_path`

        若本地分支不存在，会从 `subbatch_base_branch` 创建；若已存在，则直接挂载该分支。
        """
        results: Dict[str, Dict[str, Any]] = {}
        repo_path = Path(repo_dir)

        for sb in sub_batches:
            sb_id = sb["id"]
            branch_name = sb["branch_name"]
            subbatch_base_branch = sb.get("subbatch_base_branch") or "HEAD"
            worktree_path = sb.get("worktree_path")
            if not worktree_path:
                raise ValueError(f"SubBatch {sb_id} missing worktree_path")

            path = Path(worktree_path)
            label = f"subbatch-{sb_id.split('_')[-1]}"
            await self.ensure_branch_worktree(
                repo_dir=repo_path,
                path=path,
                branch_name=branch_name,
                base_ref=subbatch_base_branch,
                label=label,
            )
            results[sb_id] = self.health_check_worktree(str(path)).to_dict()

        return results

    async def ensure_branch_worktree(
        self,
        *,
        repo_dir: Path,
        path: Path,
        branch_name: str,
        base_ref: str,
        label: str,
    ) -> None:
        """确保一个分支 worktree 存在。

        该方法尽量保留已经存在的分支；如果 worktree 路径存在但不是可用 git worktree，则先移除并重新 add。
        """
        base_ref_resolved = await self._resolve_ref(repo_dir, base_ref)
        branch_exists = await self._local_branch_exists(repo_dir, branch_name)

        health = self.health_check_worktree(str(path))
        if health.exists and health.is_git_worktree:
            current_branch = health.branch
            if current_branch == branch_name:
                logger.info(
                    "[WorkspaceManager] 复用 worktree: %s (branch=%s, base_ref=%s resolved=%s)",
                    path, branch_name, base_ref, base_ref_resolved,
                )
                await self._run_cmd(
                    ["git", "reset", "--hard", base_ref_resolved],
                    cwd=str(path),
                    label=f"Workspace/reset-{label}",
                    timeout=300,
                    quiet=False,
                )
                await self._run_cmd_rc(
                    ["git", "clean", "-fd"],
                    cwd=str(path),
                    label=f"Workspace/clean-{label}",
                    timeout=300,
                    quiet=False,
                )
                return
            logger.info(
                "[WorkspaceManager] worktree 分支不匹配，重建: %s current=%s expected=%s",
                path, current_branch, branch_name,
            )

        await self._remove_worktree_if_exists(repo_dir, path, label=label)

        if not branch_exists:
            await self._run_cmd(
                ["git", "branch", branch_name, base_ref_resolved],
                cwd=str(repo_dir),
                label=f"Workspace/branch-{label}",
                timeout=120,
                quiet=False,
            )

        await self._run_cmd(
            ["git", "worktree", "add", str(path), branch_name],
            cwd=str(repo_dir),
            label=f"Workspace/worktree-add-{label}",
            timeout=3600,
            quiet=False,
        )

    def health_check_worktree(self, path: str) -> WorktreeHealth:
        """同步健康检查：路径、git worktree、分支、HEAD、干净状态、bd/。"""
        p = Path(path)
        health = WorktreeHealth(path=str(p), exists=p.exists(), is_git_worktree=False)
        if not p.exists():
            return health
        if not p.is_dir():
            health.error = "path exists but is not a directory"
            return health

        try:
            git_dir = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(p),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
                check=False,
            )
            health.is_git_worktree = git_dir.returncode == 0
            if not health.is_git_worktree:
                health.error = git_dir.stderr.strip()
                return health

            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(p),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
                check=False,
            )
            health.branch = branch.stdout.strip()

            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(p),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
                check=False,
            )
            health.head = head.stdout.strip() if head.returncode == 0 else ""

            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(p),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )
            health.clean = status.returncode == 0 and not status.stdout.strip()
            health.bd_exists = (p / "bd").is_dir()
            return health
        except Exception as exc:
            health.error = str(exc)
            return health

    async def _ensure_repo(
        self,
        *,
        repo_dir: Path,
        parent_dir: Path,
        github_repo: str,
        github_branch: str,
        repo_name: str,
    ) -> None:
        if (repo_dir / ".git").exists():
            logger.info("[WorkspaceManager] clone 已存在，执行 fetch: %s", repo_dir)
            await self._run_cmd(
                ["git", "fetch", "--progress", "origin", github_branch],
                cwd=str(repo_dir),
                label="Workspace/fetch-repo",
                timeout=900,
                quiet=False,
            )
            await self._run_cmd_rc(
                ["git", "checkout", github_branch],
                cwd=str(repo_dir),
                label="Workspace/checkout-repo-branch",
                timeout=120,
                quiet=False,
            )
            await self._run_cmd_rc(
                ["git", "pull", "--ff-only", "origin", github_branch],
                cwd=str(repo_dir),
                label="Workspace/pull-repo",
                timeout=900,
                quiet=False,
            )
            return

        logger.info("[WorkspaceManager] clone %s -b %s -> %s", github_repo, github_branch, repo_dir)
        await self._run_cmd(
            ["git", "clone", "--progress", github_repo, "-b", github_branch, repo_name],
            cwd=str(parent_dir),
            label="Workspace/clone",
            timeout=3600,
            quiet=False,
        )

    async def _fetch_ref(self, repo_dir: Path, ref: str, *, label: str) -> None:
        await self._run_cmd(
            ["git", "fetch", "--progress", "origin", ref],
            cwd=str(repo_dir),
            label=f"Workspace/{label}",
            timeout=600,
            quiet=False,
        )

    async def _remove_worktree_if_exists(self, repo_dir: Path, path: Path, *, label: str) -> None:
        if path.exists():
            logger.info("[WorkspaceManager] 移除已有 worktree: %s", path)
            await self._run_cmd_rc(
                ["git", "worktree", "remove", "--force", str(path)],
                cwd=str(repo_dir),
                label=f"Workspace/worktree-remove-{label}",
                timeout=300,
                quiet=False,
            )
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        await self._run_cmd_rc(
            ["git", "worktree", "prune"],
            cwd=str(repo_dir),
            label=f"Workspace/worktree-prune-{label}",
            timeout=120,
            quiet=True,
        )

    async def _local_branch_exists(self, repo_dir: Path, branch_name: str) -> bool:
        rc = await self._run_cmd_rc(
            ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            cwd=str(repo_dir),
            label=f"Workspace/branch-exists-{self._safe_label(branch_name)}",
            timeout=30,
            quiet=True,
        )
        return rc == 0

    async def _resolve_ref(self, repo_dir: Path, ref: str) -> str:
        """把 branch / remote branch / raw sha 解析为 git 可接受的 ref。"""
        candidates = [ref]
        if not ref.startswith("origin/") and not self._looks_like_sha(ref):
            candidates.append(f"origin/{ref}")

        for candidate in candidates:
            rc = await self._run_cmd_rc(
                ["git", "rev-parse", "--verify", "--quiet", candidate],
                cwd=str(repo_dir),
                label=f"Workspace/resolve-{self._safe_label(candidate)}",
                timeout=30,
                quiet=True,
            )
            if rc == 0:
                return candidate
        raise RuntimeError(f"无法解析 git ref: {ref}")

    @staticmethod
    def _repo_name_from_url(github_repo: str) -> str:
        repo_name = github_repo.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        return repo_name or "repo"

    @staticmethod
    def _safe_label(value: str) -> str:
        return value.replace("/", "_").replace("\\", "_").replace(" ", "_")

    @staticmethod
    def _looks_like_sha(value: str) -> bool:
        if len(value) < 7 or len(value) > 40:
            return False
        return all(c in "0123456789abcdefABCDEF" for c in value)
