# -*- coding: utf-8 -*-
# @file vault_sync.py
# @brief Vault synchronization worker
# @author sailing-innocent
# @date 2026-08-24
# @version 1.0
# ---------------------------------

import os
import subprocess
import logging
from pathlib import Path
from typing import List, Optional

from sail_server.agent.config import VaultConfig
from sail_server.infrastructure.orm.agent import AgentJob, JobType, JobStatus
from sail_server.db import get_db_session

logger = logging.getLogger(__name__)


class VaultSyncWorker:
    def __init__(self, vaults: List[VaultConfig]):
        self.vaults = vaults

    async def sync_all(self):
        for vault in self.vaults:
            try:
                await self._sync_one(vault)
            except Exception as e:
                logger.exception(f"[VaultSync] Failed to sync {vault.name}: {e}")

    async def _sync_one(self, vault: VaultConfig):
        local = Path(vault.local_path)
        if not local.exists():
            await self._clone(vault)
        else:
            await self._pull(vault)

    async def _clone(self, vault: VaultConfig):
        logger.info(f"[VaultSync] Cloning {vault.name} from {vault.url}")
        parent = Path(vault.local_path).parent
        parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "-b", vault.branch, vault.url, vault.local_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr}")
        await self._record_job(vault, "cloned")

    async def _pull(self, vault: VaultConfig):
        logger.info(f"[VaultSync] Pulling {vault.name}")
        result = subprocess.run(
            ["git", "fetch", "origin", vault.branch],
            cwd=vault.local_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git fetch failed: {result.stderr}")

        # Check if there are updates
        result_local = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=vault.local_path,
            capture_output=True,
            text=True,
        )
        result_remote = subprocess.run(
            ["git", "rev-parse", f"origin/{vault.branch}"],
            cwd=vault.local_path,
            capture_output=True,
            text=True,
        )

        local_sha = result_local.stdout.strip()
        remote_sha = result_remote.stdout.strip()

        if local_sha == remote_sha:
            logger.info(f"[VaultSync] {vault.name} is up-to-date")
            return

        # Attempt pull --rebase
        result = subprocess.run(
            ["git", "pull", "--rebase", "origin", vault.branch],
            cwd=vault.local_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Rebase conflict: abort and report
            subprocess.run(
                ["git", "rebase", "--abort"],
                cwd=vault.local_path,
                capture_output=True,
            )
            await self._record_job(vault, "conflict", error=result.stderr)
            logger.warning(f"[VaultSync] {vault.name} has merge conflict, aborted")
            return

        logger.info(f"[VaultSync] {vault.name} updated: {local_sha[:8]} -> {remote_sha[:8]}")
        await self._record_job(vault, "updated", result={"from": local_sha, "to": remote_sha})

    async def _record_job(self, vault: VaultConfig, action: str, result: dict = None, error: str = None):
        with get_db_session() as db:
            job = AgentJob(
                job_type=JobType.vault_sync.value,
                status=JobStatus.completed.value if not error else JobStatus.failed.value,
                params={"vault": vault.name, "action": action},
                result=result,
                error_message=error,
            )
            db.add(job)
            db.commit()
