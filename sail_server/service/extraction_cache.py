# -*- coding: utf-8 -*-
# @file extraction_cache.py
# @brief Extraction Result Cache with Checkpoint Support
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from enum import Enum

from sail_server.data.analysis import ExtractedOutlineNode

logger = logging.getLogger(__name__)


class ExtractionPhase(Enum):
    """提取阶段"""
    INITIALIZED = "initialized"           # 初始化
    CONTENT_FETCHED = "content_fetched"   # 内容获取完成
    BATCH_STARTED = "batch_started"       # 批次处理开始
    BATCH_COMPLETED = "batch_completed"   # 批次处理完成
    MERGING = "merging"                   # 合并中
    COMPLETED = "completed"               # 完成
    FAILED = "failed"                     # 失败
    PAUSED = "paused"                     # 暂停（等待重试）


@dataclass
class BatchCheckpoint:
    """批次检查点"""
    batch_index: int
    total_batches: int
    start_chapter: int
    end_chapter: int
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    turning_points: List[Dict[str, Any]] = field(default_factory=list)
    completed_at: Optional[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.completed_at is None:
            self.completed_at = datetime.now().isoformat()


@dataclass
class ExtractionCheckpoint:
    """提取检查点
    
    支持分阶段缓存，可以灵活存取和恢复：
    - 每个批次的处理结果独立存储
    - 支持增量保存
    - 支持失败恢复
    """
    # 任务标识
    task_id: str
    edition_id: int
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 当前状态
    phase: str = ExtractionPhase.INITIALIZED.value
    progress_percent: int = 0
    current_step: str = ""
    message: str = ""
    
    # 批次信息
    total_batches: int = 0
    current_batch: int = 0
    completed_batches: List[int] = field(default_factory=list)
    failed_batches: List[int] = field(default_factory=list)
    
    # 累积结果
    accumulated_nodes: List[Dict[str, Any]] = field(default_factory=list)
    accumulated_turning_points: List[Dict[str, Any]] = field(default_factory=list)
    
    # 批次检查点（详细数据）
    batch_checkpoints: Dict[str, BatchCheckpoint] = field(default_factory=dict)
    
    # 配置信息（用于恢复）
    config: Dict[str, Any] = field(default_factory=dict)
    range_selection: Dict[str, Any] = field(default_factory=dict)
    work_title: str = ""
    known_characters: List[str] = field(default_factory=list)
    
    # 错误信息
    last_error: Optional[str] = None
    last_error_type: Optional[str] = None
    retry_count: int = 0
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExtractionCheckpoint':
        """从字典创建"""
        # 处理 batch_checkpoints 中的嵌套 dataclass
        batch_checkpoints = {}
        for k, v in data.get("batch_checkpoints", {}).items():
            if isinstance(v, dict):
                batch_checkpoints[k] = BatchCheckpoint(**v)
            else:
                batch_checkpoints[k] = v
        
        data = data.copy()
        data["batch_checkpoints"] = batch_checkpoints
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def update_progress(self, percent: int, step: str, message: str = ""):
        """更新进度"""
        self.progress_percent = percent
        self.current_step = step
        if message:
            self.message = message
        self.updated_at = datetime.now().isoformat()
    
    def set_phase(self, phase: ExtractionPhase):
        """设置阶段"""
        self.phase = phase.value
        self.updated_at = datetime.now().isoformat()
    
    def add_batch_result(
        self,
        batch_index: int,
        nodes: List[ExtractedOutlineNode],
        turning_points: List[Any],
        start_chapter: int,
        end_chapter: int,
    ):
        """添加批次结果"""
        # 转换节点为可序列化格式
        node_dicts = []
        for node in nodes:
            node_dict = {
                "id": node.id,
                "node_type": node.node_type,
                "title": node.title,
                "summary": node.summary,
                "significance": node.significance,
                "sort_index": node.sort_index,
                "parent_id": node.parent_id,
                "characters": node.characters,
                "evidence_list": [
                    {
                        "text": e.text,
                        "chapter_title": e.chapter_title,
                        "start_fragment": e.start_fragment,
                        "end_fragment": e.end_fragment,
                    }
                    for e in (node.evidence_list or [])
                ],
            }
            node_dicts.append(node_dict)
            self.accumulated_nodes.append(node_dict)
        
        # 转换转折点
        tp_dicts = []
        for tp in turning_points:
            if hasattr(tp, '__dataclass_fields__'):
                tp_dict = {
                    "node_id": tp.node_id,
                    "turning_point_type": tp.turning_point_type,
                    "description": tp.description,
                }
            else:
                tp_dict = tp
            tp_dicts.append(tp_dict)
            self.accumulated_turning_points.append(tp_dict)
        
        # 创建批次检查点
        checkpoint = BatchCheckpoint(
            batch_index=batch_index,
            total_batches=self.total_batches,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            nodes=node_dicts,
            turning_points=tp_dicts,
        )
        
        self.batch_checkpoints[str(batch_index)] = checkpoint
        
        if batch_index not in self.completed_batches:
            self.completed_batches.append(batch_index)
        if batch_index in self.failed_batches:
            self.failed_batches.remove(batch_index)
        
        self.current_batch = batch_index + 1
        self.updated_at = datetime.now().isoformat()
    
    def mark_batch_failed(self, batch_index: int, error: str):
        """标记批次失败"""
        if batch_index not in self.failed_batches:
            self.failed_batches.append(batch_index)
        self.last_error = error
        self.updated_at = datetime.now().isoformat()
    
    def get_recoverable_nodes(self) -> List[Dict[str, Any]]:
        """获取可恢复的节点（来自已完成的批次）"""
        return self.accumulated_nodes.copy()
    
    def get_pending_batches(self) -> List[int]:
        """获取待处理的批次索引"""
        all_batches = set(range(self.total_batches))
        completed = set(self.completed_batches)
        return sorted(list(all_batches - completed))
    
    def is_batch_completed(self, batch_index: int) -> bool:
        """检查批次是否已完成"""
        return batch_index in self.completed_batches
    
    def get_batch_result(self, batch_index: int) -> Optional[BatchCheckpoint]:
        """获取批次结果"""
        return self.batch_checkpoints.get(str(batch_index))


class ExtractionCacheManager:
    """提取缓存管理器
    
    管理提取任务的检查点缓存，支持：
    - 自动保存检查点
    - 失败恢复
    - 增量保存
    - 清理过期缓存
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.getcwd(), ".cache", "extraction")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, ExtractionCheckpoint] = {}
    
    def _get_cache_path(self, task_id: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{task_id}.json"
    
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
        """创建新的检查点"""
        checkpoint = ExtractionCheckpoint(
            task_id=task_id,
            edition_id=edition_id,
            config=config,
            range_selection=range_selection,
            work_title=work_title,
            known_characters=known_characters or [],
            total_batches=total_batches,
        )
        self._memory_cache[task_id] = checkpoint
        self._save_checkpoint(checkpoint)
        logger.info(f"[CacheManager] Created checkpoint for task {task_id}")
        return checkpoint
    
    def get_checkpoint(self, task_id: str) -> Optional[ExtractionCheckpoint]:
        """获取检查点"""
        # 先检查内存缓存
        if task_id in self._memory_cache:
            return self._memory_cache[task_id]
        
        # 从磁盘加载
        cache_path = self._get_cache_path(task_id)
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                checkpoint = ExtractionCheckpoint.from_dict(data)
                self._memory_cache[task_id] = checkpoint
                logger.info(f"[CacheManager] Loaded checkpoint for task {task_id} from disk")
                return checkpoint
            except Exception as e:
                logger.error(f"[CacheManager] Failed to load checkpoint: {e}")
                return None
        
        return None
    
    def save_checkpoint(self, task_id: str) -> bool:
        """保存检查点"""
        if task_id not in self._memory_cache:
            logger.warning(f"[CacheManager] No checkpoint in memory for task {task_id}")
            return False
        
        return self._save_checkpoint(self._memory_cache[task_id])
    
    def _save_checkpoint(self, checkpoint: ExtractionCheckpoint) -> bool:
        """保存检查点到磁盘"""
        try:
            cache_path = self._get_cache_path(checkpoint.task_id)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug(f"[CacheManager] Saved checkpoint for task {checkpoint.task_id}")
            return True
        except Exception as e:
            logger.error(f"[CacheManager] Failed to save checkpoint: {e}")
            return False
    
    def update_checkpoint(
        self,
        task_id: str,
        updater: Callable[[ExtractionCheckpoint], None],
        auto_save: bool = True,
    ) -> bool:
        """更新检查点"""
        checkpoint = self.get_checkpoint(task_id)
        if checkpoint is None:
            logger.warning(f"[CacheManager] Checkpoint not found for task {task_id}")
            return False
        
        try:
            updater(checkpoint)
            checkpoint.updated_at = datetime.now().isoformat()
            
            if auto_save:
                return self._save_checkpoint(checkpoint)
            return True
        except Exception as e:
            logger.error(f"[CacheManager] Failed to update checkpoint: {e}")
            return False
    
    def add_batch_result(
        self,
        task_id: str,
        batch_index: int,
        nodes: List[ExtractedOutlineNode],
        turning_points: List[Any],
        start_chapter: int,
        end_chapter: int,
    ) -> bool:
        """添加批次结果"""
        def updater(cp: ExtractionCheckpoint):
            cp.add_batch_result(batch_index, nodes, turning_points, start_chapter, end_chapter)
        
        return self.update_checkpoint(task_id, updater, auto_save=True)
    
    def delete_checkpoint(self, task_id: str) -> bool:
        """删除检查点"""
        # 从内存移除
        if task_id in self._memory_cache:
            del self._memory_cache[task_id]
        
        # 从磁盘移除
        cache_path = self._get_cache_path(task_id)
        if cache_path.exists():
            try:
                cache_path.unlink()
                logger.info(f"[CacheManager] Deleted checkpoint for task {task_id}")
                return True
            except Exception as e:
                logger.error(f"[CacheManager] Failed to delete checkpoint: {e}")
                return False
        
        return True
    
    def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """清理过期的检查点"""
        cleaned = 0
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                if cache_file.stat().st_mtime < cutoff:
                    cache_file.unlink()
                    cleaned += 1
            except Exception as e:
                logger.warning(f"[CacheManager] Failed to cleanup {cache_file}: {e}")
        
        logger.info(f"[CacheManager] Cleaned up {cleaned} old checkpoints")
        return cleaned
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """列出所有检查点"""
        checkpoints = []
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                checkpoints.append({
                    "task_id": data.get("task_id"),
                    "phase": data.get("phase"),
                    "progress": data.get("progress_percent"),
                    "edition_id": data.get("edition_id"),
                    "updated_at": data.get("updated_at"),
                    "file": str(cache_file),
                })
            except Exception as e:
                logger.warning(f"[CacheManager] Failed to read {cache_file}: {e}")
        
        return sorted(checkpoints, key=lambda x: x.get("updated_at", ""), reverse=True)


# 全局缓存管理器
_cache_manager: Optional[ExtractionCacheManager] = None


def get_cache_manager() -> ExtractionCacheManager:
    """获取全局缓存管理器"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = ExtractionCacheManager()
    return _cache_manager


def set_cache_manager(manager: ExtractionCacheManager):
    """设置全局缓存管理器"""
    global _cache_manager
    _cache_manager = manager
