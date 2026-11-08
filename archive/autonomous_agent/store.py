# -*- coding: utf-8 -*-
# @file store.py
# @brief Agent isolated file system storage
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""AgentStore — isolated file workspace for the autonomous agent.

Root: data/agent/ (configurable via AGENT_DATA_DIR)

  data/agent/
  ├── db/
  │   └── agent.db
  ├── runs/
  ├── memory/
  │   └── context_snapshots/
  ├── notifications/
  │   ├── queued/
  │   └── sent/
  ├── backups/
  └── config/
      └── agent.yaml
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentStore:
    """Agent isolated file system storage.

    All paths are based on config.data_dir, completely independent from sail_server.
    """

    def __init__(self, data_dir: str):
        self._data_dir = Path(data_dir).resolve()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        for sub in ("db", "runs", "memory/context_snapshots",
                    "notifications/queued", "notifications/sent",
                    "backups", "config"):
            (self._data_dir / sub).mkdir(parents=True, exist_ok=True)

    # ── Paths ─────────────────────────────────────────────────────────

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    @property
    def db_dir(self) -> Path:
        return self._data_dir / "db"

    def run_dir(self, run_id: str) -> Path:
        return self._data_dir / "runs" / run_id

    def run_artifacts_dir(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "artifacts"

    def run_logs_dir(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "logs"

    def memory_dir(self) -> Path:
        return self._data_dir / "memory"

    def context_snapshots_dir(self) -> Path:
        return self._data_dir / "memory" / "context_snapshots"

    def notifications_queued_dir(self) -> Path:
        return self._data_dir / "notifications" / "queued"

    def notifications_sent_dir(self) -> Path:
        return self._data_dir / "notifications" / "sent"

    def backup_dir(self) -> Path:
        return self._data_dir / "backups"

    def config_dir(self) -> Path:
        return self._data_dir / "config"

    # ── Run storage ───────────────────────────────────────────────────

    def init_run_storage(self, run_id: str) -> Path:
        """Initialize storage for a pipeline run."""
        rd = self.run_dir(run_id)
        rd.mkdir(parents=True, exist_ok=True)
        self.run_artifacts_dir(run_id).mkdir(exist_ok=True)
        self.run_logs_dir(run_id).mkdir(exist_ok=True)
        logger.info("Initialized agent run storage: %s", rd)
        return rd

    def save_run_config(self, run_id: str, config: Dict[str, Any]) -> Path:
        path = self.run_dir(run_id) / "config.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return path

    def write_run_log(self, run_id: str, filename: str, content: str) -> Path:
        ld = self.run_logs_dir(run_id)
        ld.mkdir(parents=True, exist_ok=True)
        path = ld / filename
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
            if not content.endswith("\n"):
                f.write("\n")
        return path

    def save_artifact(self, run_id: str, filename: str, content: str | bytes) -> Path:
        ad = self.run_artifacts_dir(run_id)
        ad.mkdir(parents=True, exist_ok=True)
        path = ad / filename
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(path, mode, encoding="utf-8" if mode == "w" else None) as f:
            f.write(content)
        return path

    def read_artifact(self, run_id: str, filename: str) -> Optional[str]:
        path = self.run_artifacts_dir(run_id) / filename
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    # ── Memory snapshots ──────────────────────────────────────────────

    def save_context_snapshot(self, snapshot_id: str, data: Dict[str, Any]) -> Path:
        sd = self.context_snapshots_dir()
        sd.mkdir(parents=True, exist_ok=True)
        path = sd / f"{snapshot_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def list_context_snapshots(self) -> List[Path]:
        sd = self.context_snapshots_dir()
        if not sd.exists():
            return []
        return sorted(sd.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    # ── Notifications queue ───────────────────────────────────────────

    def queue_notification(self, notification_id: str, data: Dict[str, Any]) -> Path:
        qd = self.notifications_queued_dir()
        qd.mkdir(parents=True, exist_ok=True)
        path = qd / f"{notification_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def archive_notification(self, notification_id: str) -> Optional[Path]:
        src = self.notifications_queued_dir() / f"{notification_id}.json"
        if not src.exists():
            return None
        dst_dir = self.notifications_sent_dir()
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{notification_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        shutil.move(str(src), str(dst))
        return dst

    def list_queued_notifications(self) -> List[Dict[str, Any]]:
        qd = self.notifications_queued_dir()
        if not qd.exists():
            return []
        result = []
        for p in sorted(qd.glob("*.json"), key=lambda x: x.stat().st_mtime):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    result.append(json.load(f))
            except Exception as exc:
                logger.warning("Failed to load queued notification %s: %s", p, exc)
        return result

    # ── Backup / Restore ──────────────────────────────────────────────

    def backup(self, label: Optional[str] = None) -> Path:
        """Backup agent data to tar.gz."""
        label = label or datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir() / f"agent_backup_{label}.tar.gz"
        with tarfile.open(str(backup_path), "w:gz") as tar:
            # Backup db, memory, config (exclude runs and notifications for size)
            for sub in ("db", "memory", "config"):
                sub_path = self._data_dir / sub
                if sub_path.exists():
                    tar.add(sub_path, arcname=sub_path.name)
        logger.info("Agent backup created: %s", backup_path)
        return backup_path

    def list_backups(self) -> List[Path]:
        bd = self.backup_dir()
        if not bd.exists():
            return []
        return sorted(bd.glob("agent_backup_*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)

    def cleanup_old_runs(self, days: int = 30) -> int:
        """Clean up run directories older than N days."""
        cutoff = datetime.now().timestamp() - days * 86400
        removed = 0
        runs_dir = self._data_dir / "runs"
        if not runs_dir.exists():
            return 0
        for rd in runs_dir.iterdir():
            if rd.is_dir() and rd.stat().st_mtime < cutoff:
                shutil.rmtree(rd)
                removed += 1
        logger.info("Cleaned up %d old agent runs (>%d days)", removed, days)
        return removed
