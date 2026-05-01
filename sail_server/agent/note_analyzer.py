# -*- coding: utf-8 -*-
# @file note_analyzer.py
# @brief Note analysis worker for task generation
# @author sailing-innocent
# @date 2026-08-24
# @version 1.0
# ---------------------------------

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from sail_server.agent.config import AnalysisConfig, VaultConfig
from sail_server.infrastructure.orm.agent import AgentJob, JobType, JobStatus
from sail_server.db import get_db_session

logger = logging.getLogger(__name__)

# Simple fallback parser when engine server is not available
# In production, use DendronEngineClient from dendron_kb skill


class NoteAnalyzerWorker:
    def __init__(self, config: AnalysisConfig, vaults: List[VaultConfig]):
        self.config = config
        self.vaults = vaults

    async def scan_and_create_tasks(self):
        if not self.config.enabled:
            return
        for vault in self.vaults:
            try:
                await self._scan_vault(vault)
            except Exception as e:
                logger.exception(f"[Analyzer] Failed to scan {vault.name}: {e}")

    async def _scan_vault(self, vault: VaultConfig):
        logger.info(f"[Analyzer] Scanning vault: {vault.name}")
        vault_path = Path(vault.local_path)
        if not vault_path.exists():
            logger.warning(f"[Analyzer] Vault path not found: {vault_path}")
            return

        notes = self._collect_notes(vault_path)
        jobs = []

        if self.config.orphan_detection:
            jobs.extend(self._find_orphans(notes, vault))
        if self.config.daily_gap_detection:
            jobs.extend(self._find_missing_dailies(notes, vault))
        if self.config.todo_extraction:
            jobs.extend(self._find_todos(notes, vault))
        if self.config.broken_link_detection:
            jobs.extend(self._find_broken_links(notes, vault))

        if jobs:
            await self._insert_jobs(jobs)
            logger.info(f"[Analyzer] Created {len(jobs)} jobs for {vault.name}")

    def _collect_notes(self, vault_path: Path) -> List[Dict[str, Any]]:
        notes = []
        for md_file in vault_path.rglob("*.md"):
            rel = md_file.relative_to(vault_path)
            content = md_file.read_text(encoding="utf-8")
            frontmatter, body = self._parse_frontmatter(content)
            notes.append({
                "fname": str(rel.with_suffix("")).replace(os.sep, "."),
                "path": str(rel),
                "title": frontmatter.get("title", md_file.stem),
                "body": body,
                "links": self._extract_wiki_links(body),
                "has_backlinks": False,  # Will be computed
            })
        # Compute backlinks
        link_targets = set()
        for n in notes:
            for link in n["links"]:
                link_targets.add(link)
        for n in notes:
            if n["fname"] in link_targets:
                n["has_backlinks"] = True
        return notes

    def _parse_frontmatter(self, content: str) -> tuple:
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    import yaml
                    return yaml.safe_load(parts[1]) or {}, parts[2]
                except Exception:
                    pass
        return {}, content

    def _extract_wiki_links(self, body: str) -> List[str]:
        # [[link]] or [[link|alias]]
        pattern = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"
        return list(set(re.findall(pattern, body)))

    def _find_orphans(self, notes: List[Dict], vault: VaultConfig) -> List[Dict]:
        orphans = []
        for n in notes:
            if not n["has_backlinks"] and not n["fname"].endswith(".root"):
                orphans.append({
                    "job_type": JobType.note_analysis.value,
                    "status": JobStatus.pending_review.value,
                    "params": {
                        "rule": "orphan_detection",
                        "vault": vault.name,
                        "note_fname": n["fname"],
                        "note_path": n["path"],
                    },
                    "auto_approved": False,
                })
        return orphans

    def _find_missing_dailies(self, notes: List[Dict], vault: VaultConfig) -> List[Dict]:
        # Find daily journal gaps in last 7 days
        daily_pattern = re.compile(r"daily\.journal\.(\d{4}\.\d{2}\.\d{2})")
        existing = set()
        for n in notes:
            m = daily_pattern.match(n["fname"])
            if m:
                existing.add(m.group(1))

        jobs = []
        today = datetime.now()
        for i in range(1, 8):
            day = today - timedelta(days=i)
            key = day.strftime("%Y.%m.%d")
            if key not in existing:
                jobs.append({
                    "job_type": JobType.daily_fill.value,
                    "status": JobStatus.pending.value,
                    "params": {
                        "rule": "daily_gap_detection",
                        "vault": vault.name,
                        "date": key,
                    },
                    "auto_approved": True,
                })
        return jobs

    def _find_todos(self, notes: List[Dict], vault: VaultConfig) -> List[Dict]:
        jobs = []
        todo_pattern = re.compile(r"- \[ \] (.+)")
        for n in notes:
            for match in todo_pattern.finditer(n["body"]):
                jobs.append({
                    "job_type": JobType.task_exec.value,
                    "status": JobStatus.pending_review.value,
                    "params": {
                        "rule": "todo_extraction",
                        "vault": vault.name,
                        "note_fname": n["fname"],
                        "todo_text": match.group(1).strip(),
                    },
                    "auto_approved": False,
                })
        return jobs

    def _find_broken_links(self, notes: List[Dict], vault: VaultConfig) -> List[Dict]:
        jobs = []
        all_fnames = {n["fname"] for n in notes}
        for n in notes:
            for link in n["links"]:
                if link not in all_fnames:
                    jobs.append({
                        "job_type": JobType.stub_create.value,
                        "status": JobStatus.pending.value,
                        "params": {
                            "rule": "broken_link_detection",
                            "vault": vault.name,
                            "source_note": n["fname"],
                            "missing_link": link,
                        },
                        "auto_approved": True,
                    })
        return jobs

    async def _insert_jobs(self, jobs: List[Dict]):
        with get_db_session() as db:
            for j in jobs:
                # Deduplicate: skip if same params already pending
                existing = (
                    db.query(AgentJob)
                    .filter(
                        AgentJob.job_type == j["job_type"],
                        AgentJob.status.in_([JobStatus.pending.value, JobStatus.pending_review.value]),
                        AgentJob.params == j["params"],
                    )
                    .first()
                )
                if existing:
                    continue
                job = AgentJob(**j)
                db.add(job)
            db.commit()
