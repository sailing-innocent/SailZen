# -*- coding: utf-8 -*-
# @file store.py
# @brief 独立文件系统存储抽象
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""SailZen DAG Client 独立文件系统存储层。

提供与 sail_server 完全隔离的文件操作，支持：
  - 运行时数据目录管理
  - 执行产物存储
  - 日志归档
  - 备份/恢复接口
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


class DAGStore:
    """DAG Client 独立文件系统存储。

    所有路径都基于 config.data_dir，与 sail_server 无关。
    """

    def __init__(self, data_dir: str):
        self._data_dir = Path(data_dir).resolve()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """确保必要目录存在。"""
        for sub in ("runs", "artifacts", "logs", "backups", "configs"):
            (self._data_dir / sub).mkdir(parents=True, exist_ok=True)

    # ── 路径解析 ──────────────────────────────────────────────────────

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    def run_dir(self, run_id: str) -> Path:
        return self._data_dir / "runs" / run_id

    def artifacts_dir(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "artifacts"

    def logs_dir(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "logs"

    def config_dir(self) -> Path:
        return self._data_dir / "configs"

    def backup_dir(self) -> Path:
        return self._data_dir / "backups"

    # ── 运行数据 ──────────────────────────────────────────────────────

    def init_run_storage(self, run_id: str) -> Path:
        """为一次 DAG 运行初始化存储目录。"""
        rd = self.run_dir(run_id)
        rd.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir(run_id).mkdir(exist_ok=True)
        self.logs_dir(run_id).mkdir(exist_ok=True)
        logger.info("Initialized run storage: %s", rd)
        return rd

    def save_run_config(self, run_id: str, config: Dict[str, Any]) -> Path:
        """保存运行时的配置快照。"""
        path = self.run_dir(run_id) / "config.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return path

    def load_run_config(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = self.run_dir(run_id) / "config.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_log(self, run_id: str, filename: str, content: str) -> Path:
        """写入运行日志。"""
        ld = self.logs_dir(run_id)
        ld.mkdir(parents=True, exist_ok=True)
        path = ld / filename
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
            if not content.endswith("\n"):
                f.write("\n")
        return path

    def save_artifact(self, run_id: str, filename: str, content: str | bytes) -> Path:
        """保存执行产物。"""
        ad = self.artifacts_dir(run_id)
        ad.mkdir(parents=True, exist_ok=True)
        path = ad / filename
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(path, mode, encoding="utf-8" if mode == "w" else None) as f:
            f.write(content)
        return path

    def list_artifacts(self, run_id: str) -> List[str]:
        ad = self.artifacts_dir(run_id)
        if not ad.exists():
            return []
        return [p.name for p in ad.iterdir()]

    def read_artifact(self, run_id: str, filename: str) -> Optional[str]:
        path = self.artifacts_dir(run_id) / filename
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    # ── 备份 / 恢复 ───────────────────────────────────────────────────

    def backup(self, label: Optional[str] = None) -> Path:
        """备份整个 data_dir 到 tar.gz。"""
        label = label or datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir() / f"dag_backup_{label}.tar.gz"
        with tarfile.open(str(backup_path), "w:gz") as tar:
            tar.add(self._data_dir, arcname=self._data_dir.name)
        logger.info("Backup created: %s", backup_path)
        return backup_path

    def list_backups(self) -> List[Path]:
        bd = self.backup_dir()
        if not bd.exists():
            return []
        return sorted(bd.glob("dag_backup_*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)

    def restore(self, backup_path: str, *, wipe: bool = False) -> None:
        """从 tar.gz 恢复 dataDir。

        Args:
            backup_path: 备份文件路径。
            wipe: 是否先清空现有 data_dir。
        """
        bp = Path(backup_path)
        if not bp.exists():
            raise FileNotFoundError(f"Backup not found: {bp}")

        # 如果 wipe=True 且备份文件在 data_dir 内，先复制到安全位置
        safe_bp = bp
        if wipe and self._data_dir in bp.parents or bp.parent == self._data_dir or bp.parent == self.backup_dir():
            import tempfile
            safe = Path(tempfile.gettempdir()) / bp.name
            shutil.copy2(str(bp), str(safe))
            safe_bp = safe

        if wipe:
            if self._data_dir.exists():
                shutil.rmtree(self._data_dir)
            self._data_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(str(safe_bp), "r:gz") as tar:
            tar.extractall(path=self._data_dir.parent)
        logger.info("Restored from %s", bp)

    def export_run(self, run_id: str, output_path: Optional[str] = None) -> Path:
        """导出单次运行的所有数据为 tar.gz。"""
        rd = self.run_dir(run_id)
        if not rd.exists():
            raise FileNotFoundError(f"Run not found: {run_id}")
        out = Path(output_path or self.backup_dir() / f"run_{run_id}.tar.gz")
        with tarfile.open(str(out), "w:gz") as tar:
            tar.add(rd, arcname=rd.name)
        return out

    # ── 清理 ──────────────────────────────────────────────────────────

    def cleanup_run(self, run_id: str) -> None:
        rd = self.run_dir(run_id)
        if rd.exists():
            shutil.rmtree(rd)
            logger.info("Cleaned up run storage: %s", run_id)

    def cleanup_old_runs(self, days: int = 30) -> int:
        """清理超过 N 天的运行数据。"""
        cutoff = datetime.now().timestamp() - days * 86400
        removed = 0
        runs_dir = self._data_dir / "runs"
        if not runs_dir.exists():
            return 0
        for rd in runs_dir.iterdir():
            if rd.is_dir() and rd.stat().st_mtime < cutoff:
                shutil.rmtree(rd)
                removed += 1
        logger.info("Cleaned up %d old runs (>%d days)", removed, days)
        return removed
