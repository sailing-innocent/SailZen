# -*- coding: utf-8 -*-
# @file types.py
# @brief Type definitions for async outline extraction
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""异步大纲提取的类型定义"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List
from datetime import datetime
import uuid


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待依赖完成
    READY = "ready"          # 依赖完成，等待执行
    RUNNING = "running"      # 正在执行
    COMPLETED = "completed"  # 成功完成
    FAILED = "failed"        # 执行失败
    CANCELLED = "cancelled"  # 已取消


class TaskLevel(Enum):
    """任务层级枚举"""
    CHUNK = 0      # 片段级别
    SEGMENT = 1    # 段落组级别
    CHAPTER = 2    # 章节级别


@dataclass
class OutlineNode:
    """大纲节点"""
    title: str
    content: str
    level: int  # 大纲层级（1, 2, 3...）
    start_pos: int  # 在原文中的起始位置
    end_pos: int    # 在原文中的结束位置
    children: List['OutlineNode'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """任务数据类
    
    表示任务图中的一个节点，包含任务的完整信息
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    level: TaskLevel = TaskLevel.CHUNK
    index: int = 0  # 在同级任务中的顺序索引
    text: str = ""  # 任务处理的文本内容
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务ID列表
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None  # 执行结果（通常是 OutlineNode 列表）
    error: Optional[str] = None   # 错误信息
    retry_count: int = 0          # 重试次数
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 执行上下文
    context: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """计算任务执行耗时（毫秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "level": self.level.value,
            "index": self.index,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class ExtractionConfig:
    """大纲提取配置"""
    # 切分参数
    chunk_size: int = 1500           # 每个 chunk 的 token 数
    chunk_overlap: int = 200         # chunk 之间的重叠 token 数
    chunks_per_segment: int = 5      # 每个 segment 包含的 chunk 数
    
    # 并发控制
    max_concurrent: int = 100        # 最大并发数
    rpm_limit: int = 400             # 每分钟请求数限制（留 20% 缓冲）
    tpm_limit: int = 2_400_000       # 每分钟 token 数限制（留 20% 缓冲）
    
    # 执行参数
    timeout_seconds: int = 30        # 单个任务超时时间
    max_retries: int = 3             # 最大重试次数
    retry_delay_base: float = 1.0    # 重试延迟基数（指数退避）
    
    # 功能开关
    enable_progress_tracking: bool = True
    enable_websocket: bool = False
    mode: str = "parallel"  # "parallel" 或 "sequential"


@dataclass
class ExtractionProgress:
    """提取进度信息"""
    task_id: str
    overall_progress: float  # 0-100
    level_progress: Dict[str, Dict[str, int]]  # 各级别进度
    estimated_time_remaining: Optional[int] = None  # 预估剩余时间（秒）
    current_status: str = "running"
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
