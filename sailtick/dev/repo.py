# -*- coding: utf-8 -*-
# @file repo.py
# @brief 开发仓库分支管理（创建/校验 agent/sailtick-dev）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""DevRepo — 服务器仓库分支操作封装。

只用 git plumbing（subprocess），不依赖第三方库。
所有写操作前先确认/创建 dev 分支；禁止任何 push。
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from sailtick.config import SelfDevConfig
from sailtick.dev.guard import GuardError, SelfDevGuard

logger = logging.getLogger(__name__)


class DevRepo:
    """开发仓库封装。"""

    def __init__(self, config: SelfDevConfig):
        self.config = config
        self.guard = SelfDevGuard(config)
        self.repo = Path(config.repo_dir) if config.repo_dir else None

    def _git(self, *args: str, check: bool = True) -> str:
        """执行 git 命令，返回 stdout。"""
        if self.repo is None:
            raise GuardError("self_dev.repo_dir not configured")
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if check and result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    # ── 分支 ──────────────────────────────────────────────────────────

    def current_branch(self) -> str:
        return self._git("branch", "--show-current")

    def ensure_dev_branch(self) -> str:
        """确保 dev 分支存在（基于当前 HEAD）；返回分支名。"""
        branch = self.config.branch
        exists = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            cwd=self.repo, capture_output=True,
        ).returncode == 0
        if exists:
            logger.info("dev branch %s exists", branch)
        else:
            self._git("branch", branch)
            logger.info("created dev branch %s", branch)
        return branch

    def checkout_dev(self) -> None:
        """切到 dev 分支（若已在则 no-op）。"""
        branch = self.ensure_dev_branch()
        if self.current_branch() != branch:
            self._git("checkout", branch)
            logger.info("checked out %s", branch)

    def status_porcelain(self) -> List[str]:
        out = self._git("status", "--porcelain")
        return [line for line in out.splitlines() if line.strip()]

    def diff_stat(self, base: str = "main") -> str:
        """相对 base 的改动统计。"""
        return self._git("diff", "--stat", f"{base}...HEAD", check=False)

    def head_commit(self) -> str:
        return self._git("rev-parse", "--short", "HEAD")

    # ── 提交（护栏内） ────────────────────────────────────────────────

    def commit_all(self, message: str, files: Optional[List[str]] = None) -> str:
        """在白名单校验后提交指定文件（或全部白名单内改动）。

        Returns: commit hash
        """
        # 分支护栏：必须在 dev 分支
        branch = self.current_branch()
        self.guard.assert_branch_allowed(branch)

        if files:
            allowed = self.guard.assert_paths_allowed(files)
            for p in allowed:
                self._git("add", str(p.relative_to(self.repo)))
        else:
            # 全量提交也必须逐文件过白名单
            changed = self.status_porcelain()
            whitelist_changes = []
            for line in changed:
                rel = line[3:].strip().strip('"')
                try:
                    self.guard.assert_path_allowed(rel)
                    whitelist_changes.append(rel)
                except GuardError:
                    logger.warning("guard skipped non-whitelist change: %s", rel)
            if not whitelist_changes:
                raise GuardError("no whitelisted changes to commit")
            for rel in whitelist_changes:
                self._git("add", rel)

        self._git("commit", "-m", message)
        commit = self.head_commit()
        logger.info("committed %s on %s", commit, branch)
        return commit

    def never_push(self) -> None:
        """铁律声明：本模块不提供 push。调用即违规。"""
        raise GuardError("push is forbidden by project rule (铁律: 禁止 push 源代码)")
