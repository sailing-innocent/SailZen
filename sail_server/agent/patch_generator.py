# -*- coding: utf-8 -*-
# @file patch_generator.py
# @brief Automatic patch generation worker
# @author sailing-innocent
# @date 2026-08-24
# @version 1.0
# ---------------------------------

import os
import re
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from sail_server.agent.config import PatchConfig
from sail_server.infrastructure.orm.agent import AgentJob, JobType, JobStatus
from sail_server.db import get_db_session

logger = logging.getLogger(__name__)


class PatchGeneratorWorker:
    def __init__(self, config: PatchConfig):
        self.config = config
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    async def generate_all(self):
        if not self.config.enabled:
            return
        # Find git repos under current project
        # In practice, this may iterate over multiple vaults or the main repo
        repo_root = self._find_repo_root()
        if repo_root:
            await self._generate_for_repo(repo_root)

    async def _generate_for_repo(self, repo_root: str):
        branch = await self._get_current_branch(repo_root)
        ahead = await self._commits_ahead(repo_root, branch)
        if not ahead:
            logger.info("[PatchGen] No commits ahead of origin")
            return

        topic = await self._infer_topic(repo_root, ahead)
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}-sailzen-{topic}.patch"
        filepath = Path(self.config.output_dir) / filename

        if filepath.exists():
            logger.info(f"[PatchGen] Patch already exists: {filepath}")
            return

        logger.info(f"[PatchGen] Generating patch: {filename} ({len(ahead)} commits)")
        result = subprocess.run(
            ["git", "format-patch", f"origin/{branch}", "--stdout"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git format-patch failed: {result.stderr}")

        filepath.write_text(result.stdout, encoding="utf-8")

        # Verify
        check = subprocess.run(
            ["git", "apply", "--check", str(filepath)],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )

        status = JobStatus.completed.value if check.returncode == 0 else JobStatus.failed.value
        with get_db_session() as db:
            job = AgentJob(
                job_type=JobType.patch_gen.value,
                status=status,
                params={"branch": branch, "commits": ahead, "filepath": str(filepath)},
                result={"topic": topic, "verified": check.returncode == 0},
                error_message=check.stderr if check.returncode != 0 else None,
            )
            db.add(job)
            db.commit()

        logger.info(f"[PatchGen] Patch saved: {filepath}")

    async def _infer_topic(self, repo_root: str, commits: List[str]) -> str:
        if not self.config.auto_generate_topic or not commits:
            return "mixed"
        # Simple heuristic: collect subjects and pick most common keyword
        subjects = []
        for commit in commits:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%s", commit],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                subjects.append(result.stdout.strip().lower())

        # Try to extract a meaningful topic
        keywords = ["feat", "fix", "docs", "refactor", "test", "agent", "cli", "patch"]
        for kw in keywords:
            if any(kw in s for s in subjects):
                return kw
        return "mixed"

    async def _get_current_branch(self, repo_root: str) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError("Failed to get current branch")
        return result.stdout.strip()

    async def _commits_ahead(self, repo_root: str, branch: str) -> List[str]:
        result = subprocess.run(
            ["git", "log", f"origin/{branch}..HEAD", "--pretty=format:%H"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.strip().split("\n") if line]

    def _find_repo_root(self) -> Optional[str]:
        # Start from cwd and walk up
        cwd = Path.cwd()
        for p in [cwd, *cwd.parents]:
            if (p / ".git").exists():
                return str(p)
        return None
