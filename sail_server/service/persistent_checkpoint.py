# -*- coding: utf-8 -*-
# @file persistent_checkpoint.py
# @brief Persistent Checkpoint Manager with Database Integration
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
持久化检查点管理器

整合文件系统检查点和数据库存储，提供：
- 双写机制：文件系统存完整数据，数据库存元数据
- 自动恢复：服务器重启后可从数据库恢复检查点
- 原子更新：使用数据库事务保证一致性
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from enum import Enum

from sqlalchemy import text
from sqlalchemy.orm import Session

from sail_server.service.extraction_cache import (
    ExtractionCacheManager, ExtractionCheckpoint, ExtractionPhase, BatchCheckpoint
)
from sail_server.application.dto.analysis import ExtractedOutlineNode

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DatabaseCheckpoint:
    """数据库中的检查点记录"""
    id: int
    task_id: int
    phase: str
    progress_percent: int
    current_step: Optional[str]
    message: Optional[str]
    total_batches: int
    current_batch: int
    completed_batches: List[int]
    failed_batches: List[int]
    total_nodes: int
    total_turning_points: int
    last_error: Optional[str]
    last_error_type: Optional[str]
    retry_count: int
    checkpoint_file_path: Optional[str]
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Persistent Checkpoint Manager
# ============================================================================

class PersistentCheckpointManager:
    """持久化检查点管理器
    
    管理大纲提取任务的检查点，支持：
    - 文件系统 + 数据库双写
    - 服务器重启后自动恢复
    - 原子更新操作
    """
    
    def __init__(self, db: Session, cache_dir: Optional[str] = None):
        self.db = db
        self.file_manager = ExtractionCacheManager(cache_dir)
        self._memory_cache: Dict[str, ExtractionCheckpoint] = {}
    
    # --------------------------------------------------------------------------
    # Core Operations
    # --------------------------------------------------------------------------
    
    def create_checkpoint(
        self,
        task_id: str,
        edition_id: int,
        config: Dict[str, Any],
        range_selection: Dict[str, Any],
        work_title: str = "",
        known_characters: Optional[List[str]] = None,
        total_batches: int = 0,
    ) -> ExtractionCheckpoint:
        """创建新的检查点（双写）"""
        # 1. 创建文件系统检查点
        checkpoint = self.file_manager.create_checkpoint(
            task_id=task_id,
            edition_id=edition_id,
            config=config,
            range_selection=range_selection,
            work_title=work_title,
            known_characters=known_characters,
            total_batches=total_batches,
        )
        
        # 2. 创建数据库记录
        self._create_db_checkpoint(
            task_id=int(task_id),
            phase=ExtractionPhase.INITIALIZED.value,
            total_batches=total_batches,
            checkpoint_file_path=str(self.file_manager._get_cache_path(task_id)),
        )
        
        self._memory_cache[task_id] = checkpoint
        logger.info(f"[PersistentCheckpoint] Created checkpoint for task {task_id}")
        return checkpoint
    
    def get_checkpoint(self, task_id: str) -> Optional[ExtractionCheckpoint]:
        """获取检查点（优先内存，然后文件系统）"""
        # 1. 检查内存缓存
        if task_id in self._memory_cache:
            return self._memory_cache[task_id]
        
        # 2. 从文件系统加载
        checkpoint = self.file_manager.get_checkpoint(task_id)
        if checkpoint:
            self._memory_cache[task_id] = checkpoint
            
            # 3. 同步更新数据库（如果数据库中没有）
            self._sync_to_db(task_id, checkpoint)
        
        return checkpoint
    
    def save_checkpoint(self, task_id: str) -> bool:
        """保存检查点（双写）"""
        # 1. 保存到文件系统
        file_success = self.file_manager.save_checkpoint(task_id)
        
        # 2. 同步到数据库
        checkpoint = self.file_manager.get_checkpoint(task_id)
        if checkpoint:
            db_success = self._sync_to_db(task_id, checkpoint)
            return file_success and db_success
        
        return file_success
    
    def update_checkpoint(
        self,
        task_id: str,
        updater: Callable[[ExtractionCheckpoint], None],
        auto_save: bool = True,
    ) -> bool:
        """更新检查点（双写）"""
        # 1. 更新文件系统检查点
        file_success = self.file_manager.update_checkpoint(task_id, updater, auto_save=False)
        
        if not file_success:
            return False
        
        # 2. 同步到数据库
        if auto_save:
            checkpoint = self.file_manager.get_checkpoint(task_id)
            if checkpoint:
                self._sync_to_db(task_id, checkpoint)
        
        return True
    
    def add_batch_result(
        self,
        task_id: str,
        batch_index: int,
        nodes: List[ExtractedOutlineNode],
        turning_points: List[Any],
        start_chapter: int,
        end_chapter: int,
    ) -> bool:
        """添加批次结果（双写）"""
        # 1. 更新文件系统
        file_success = self.file_manager.add_batch_result(
            task_id, batch_index, nodes, turning_points, start_chapter, end_chapter
        )
        
        if not file_success:
            return False
        
        # 2. 同步到数据库
        checkpoint = self.file_manager.get_checkpoint(task_id)
        if checkpoint:
            self._update_db_checkpoint_from_file(task_id, checkpoint)
        
        return True
    
    def delete_checkpoint(self, task_id: str) -> bool:
        """删除检查点（双删）"""
        # 1. 从内存移除
        if task_id in self._memory_cache:
            del self._memory_cache[task_id]
        
        # 2. 从文件系统删除
        file_success = self.file_manager.delete_checkpoint(task_id)
        
        # 3. 从数据库删除
        try:
            self.db.execute(
                text("DELETE FROM outline_extraction_checkpoints WHERE task_id = :task_id"),
                {"task_id": int(task_id)}
            )
            self.db.commit()
            db_success = True
        except Exception as e:
            logger.error(f"[PersistentCheckpoint] Failed to delete DB checkpoint: {e}")
            self.db.rollback()
            db_success = False
        
        return file_success and db_success
    
    # --------------------------------------------------------------------------
    # Database Operations
    # --------------------------------------------------------------------------
    
    def _create_db_checkpoint(
        self,
        task_id: int,
        phase: str,
        total_batches: int,
        checkpoint_file_path: str,
    ) -> bool:
        """创建数据库检查点记录"""
        try:
            self.db.execute(
                text("""
                    INSERT INTO outline_extraction_checkpoints (
                        task_id, phase, total_batches, checkpoint_file_path
                    ) VALUES (
                        :task_id, :phase, :total_batches, :file_path
                    )
                    ON CONFLICT (task_id) DO NOTHING
                """),
                {
                    "task_id": task_id,
                    "phase": phase,
                    "total_batches": total_batches,
                    "file_path": checkpoint_file_path,
                }
            )
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"[PersistentCheckpoint] Failed to create DB checkpoint: {e}")
            self.db.rollback()
            return False
    
    def _sync_to_db(self, task_id: str, checkpoint: ExtractionCheckpoint) -> bool:
        """同步文件系统检查点到数据库"""
        try:
            self.db.execute(
                text("""
                    INSERT INTO outline_extraction_checkpoints (
                        task_id, phase, progress_percent, current_step, message,
                        total_batches, current_batch, completed_batches, failed_batches,
                        total_nodes, total_turning_points, last_error, last_error_type,
                        retry_count, checkpoint_file_path
                    ) VALUES (
                        :task_id, :phase, :progress, :step, :message,
                        :total_batches, :current_batch, :completed_batches, :failed_batches,
                        :total_nodes, :total_turning_points, :last_error, :last_error_type,
                        :retry_count, :file_path
                    )
                    ON CONFLICT (task_id) DO UPDATE SET
                        phase = EXCLUDED.phase,
                        progress_percent = EXCLUDED.progress_percent,
                        current_step = EXCLUDED.current_step,
                        message = EXCLUDED.message,
                        total_batches = EXCLUDED.total_batches,
                        current_batch = EXCLUDED.current_batch,
                        completed_batches = EXCLUDED.completed_batches,
                        failed_batches = EXCLUDED.failed_batches,
                        total_nodes = EXCLUDED.total_nodes,
                        total_turning_points = EXCLUDED.total_turning_points,
                        last_error = EXCLUDED.last_error,
                        last_error_type = EXCLUDED.last_error_type,
                        retry_count = EXCLUDED.retry_count,
                        checkpoint_file_path = EXCLUDED.checkpoint_file_path,
                        updated_at = CURRENT_TIMESTAMP
                """),
                {
                    "task_id": int(task_id),
                    "phase": checkpoint.phase,
                    "progress": checkpoint.progress_percent,
                    "step": checkpoint.current_step,
                    "message": checkpoint.message,
                    "total_batches": checkpoint.total_batches,
                    "current_batch": checkpoint.current_batch,
                    "completed_batches": checkpoint.completed_batches,
                    "failed_batches": checkpoint.failed_batches,
                    "total_nodes": len(checkpoint.accumulated_nodes),
                    "total_turning_points": len(checkpoint.accumulated_turning_points),
                    "last_error": checkpoint.last_error,
                    "last_error_type": checkpoint.last_error_type,
                    "retry_count": checkpoint.retry_count,
                    "file_path": str(self.file_manager._get_cache_path(task_id)),
                }
            )
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"[PersistentCheckpoint] Failed to sync to DB: {e}")
            self.db.rollback()
            return False
    
    def _update_db_checkpoint_from_file(self, task_id: str, checkpoint: ExtractionCheckpoint) -> bool:
        """从文件系统检查点更新数据库"""
        return self._sync_to_db(task_id, checkpoint)
    
    # --------------------------------------------------------------------------
    # Recovery Operations
    # --------------------------------------------------------------------------
    
    def get_recoverable_tasks(
        self,
        edition_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取可恢复的任务列表"""
        query = """
            SELECT 
                uat.id as task_id,
                uat.edition_id,
                uat.status,
                uat.progress,
                uat.current_phase,
                uat.error_message,
                uat.created_at,
                uat.started_at,
                uat.completed_at,
                oec.phase as checkpoint_phase,
                oec.progress_percent as checkpoint_progress,
                oec.total_batches,
                oec.completed_batches,
                oec.failed_batches,
                oec.current_batch,
                oec.total_nodes,
                oec.total_turning_points,
                oec.checkpoint_file_path
            FROM unified_agent_tasks uat
            LEFT JOIN outline_extraction_checkpoints oec ON uat.id = oec.task_id
            WHERE uat.task_type = 'novel_analysis'
              AND uat.sub_type = 'outline_extraction'
              AND uat.status NOT IN ('cancelled', 'pending')
        """
        
        params = {}
        if edition_id is not None:
            query += " AND uat.edition_id = :edition_id"
            params["edition_id"] = edition_id
        
        query += " ORDER BY uat.updated_at DESC"
        
        try:
            result = self.db.execute(text(query), params)
            tasks = []
            for row in result:
                task = {
                    "task_id": str(row.task_id),
                    "edition_id": row.edition_id,
                    "status": row.status,
                    "progress": row.progress,
                    "current_phase": row.current_phase,
                    "error_message": row.error_message,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                    "checkpoint": {
                        "phase": row.checkpoint_phase,
                        "progress_percent": row.checkpoint_progress,
                        "total_batches": row.total_batches,
                        "completed_batches": row.completed_batches or [],
                        "failed_batches": row.failed_batches or [],
                        "current_batch": row.current_batch,
                        "total_nodes": row.total_nodes,
                        "total_turning_points": row.total_turning_points,
                        "checkpoint_file_path": row.checkpoint_file_path,
                    } if row.checkpoint_phase else None,
                }
                tasks.append(task)
            return tasks
        except Exception as e:
            logger.error(f"[PersistentCheckpoint] Failed to get recoverable tasks: {e}")
            return []
    
    def recover_from_checkpoint(self, task_id: str) -> Optional[ExtractionCheckpoint]:
        """从检查点恢复任务"""
        # 1. 尝试从文件系统恢复
        checkpoint = self.file_manager.get_checkpoint(task_id)
        
        if checkpoint:
            self._memory_cache[task_id] = checkpoint
            logger.info(f"[PersistentCheckpoint] Recovered task {task_id} from file")
            return checkpoint
        
        # 2. 尝试从数据库重建
        try:
            result = self.db.execute(
                text("""
                    SELECT * FROM outline_extraction_checkpoints
                    WHERE task_id = :task_id
                """),
                {"task_id": int(task_id)}
            ).first()
            
            if result and result.checkpoint_file_path:
                # 尝试从文件路径加载
                file_path = Path(result.checkpoint_file_path)
                if file_path.exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    checkpoint = ExtractionCheckpoint.from_dict(data)
                    self._memory_cache[task_id] = checkpoint
                    logger.info(f"[PersistentCheckpoint] Recovered task {task_id} from DB + file")
                    return checkpoint
        except Exception as e:
            logger.error(f"[PersistentCheckpoint] Failed to recover task {task_id}: {e}")
        
        return None
    
    # --------------------------------------------------------------------------
    # Cleanup Operations
    # --------------------------------------------------------------------------
    
    def cleanup_old_checkpoints(self, max_age_hours: int = 168) -> int:
        """清理过期的检查点"""
        try:
            # 调用数据库函数清理
            result = self.db.execute(
                text("SELECT * FROM cleanup_old_outline_checkpoints(:max_age)"),
                {"max_age": max_age_hours}
            ).first()
            
            self.db.commit()
            
            if result:
                deleted_count = result.deleted_count or 0
                deleted_ids = result.deleted_task_ids or []
                
                # 同时清理文件系统
                for task_id in deleted_ids:
                    self.file_manager.delete_checkpoint(str(task_id))
                    if str(task_id) in self._memory_cache:
                        del self._memory_cache[str(task_id)]
                
                logger.info(f"[PersistentCheckpoint] Cleaned up {deleted_count} old checkpoints")
                return deleted_count
            
            return 0
        except Exception as e:
            logger.error(f"[PersistentCheckpoint] Failed to cleanup old checkpoints: {e}")
            self.db.rollback()
            return 0


# ============================================================================
# Singleton Instance
# ============================================================================

_persistent_checkpoint_manager: Optional[PersistentCheckpointManager] = None


def get_persistent_checkpoint_manager(db: Session) -> PersistentCheckpointManager:
    """获取持久化检查点管理器实例"""
    return PersistentCheckpointManager(db)
