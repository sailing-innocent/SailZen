# -*- coding: utf-8 -*-
# @file guard.py
# @brief 自我开发硬护栏（防 AI 自改代码破坏仓库）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SelfDevGuard — 路径与操作白名单护栏。

所有自我开发任务的文件操作必须先过 guard.assert_allowed()。
违规即抛 GuardError，任务中止。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

from sailtick.config import SelfDevConfig

logger = logging.getLogger(__name__)


class GuardError(PermissionError):
    """护栏违规。"""


class SelfDevGuard:
    """硬护栏：分支 + 路径双重校验。"""

    def __init__(self, config: SelfDevConfig):
        self.config = config
        self.repo = Path(config.repo_dir).resolve() if config.repo_dir else None

    # ── 分支护栏 ──────────────────────────────────────────────────────

    def assert_branch_allowed(self, current_branch: str) -> None:
        """只允许在 self_dev.branch 上工作。"""
        if current_branch != self.config.branch:
            raise GuardError(
                f"current branch {current_branch!r} is not the dev branch "
                f"{self.config.branch!r}; self-dev refuses to run"
            )

    # ── 路径护栏 ──────────────────────────────────────────────────────

    def assert_path_allowed(self, path: str) -> Path:
        """校验单个路径是否在白名单目录内、且不在受保护路径上。"""
        if self.repo is None:
            raise GuardError("self_dev.repo_dir not configured")

        p = Path(path)
        if not p.is_absolute():
            p = (self.repo / p).resolve()
        else:
            p = p.resolve()

        # 必须在仓库内
        try:
            p.relative_to(self.repo)
        except ValueError:
            raise GuardError(f"path {p} is outside repo {self.repo}") from None

        rel = p.relative_to(self.repo)

        # 受保护路径（任何层级出现即拒绝）
        protected = tuple(self.config.protected_paths)
        parts = rel.parts
        for i in range(1, len(parts) + 1):
            prefix = os.path.join(*parts[:i]) if i > 1 else parts[0]
            if prefix in protected or parts[i - 1] in protected:
                raise GuardError(f"path {p} touches protected segment {parts[i-1]!r}")

        # 白名单目录（rel 须以任一白名单目录为前缀，目录边界匹配）
        rel_str = rel.as_posix()
        allowed = any(
            rel_str == w or rel_str.startswith(w.rstrip("/") + "/")
            for w in self.config.whitelist_dirs
        )
        if not allowed:
            raise GuardError(
                f"path {p} not in whitelist dirs {self.config.whitelist_dirs}"
            )
        return p

    def assert_paths_allowed(self, paths: List[str]) -> List[Path]:
        return [self.assert_path_allowed(p) for p in paths]
