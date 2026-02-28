# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Analysis Data Models and DTOs
# @author sailing-innocent
# @date 2025-02-28
# @version 1.0
# ---------------------------------

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================================================
# Text Range Selection Types
# ============================================================================

class RangeSelectionMode(str, Enum):
    """文本范围选择模式"""
    SINGLE_CHAPTER = "single_chapter"      # 单章选择
    CHAPTER_RANGE = "chapter_range"        # 连续章节范围
    MULTI_CHAPTER = "multi_chapter"        # 多章选择（不连续）
    FULL_EDITION = "full_edition"          # 整部作品
    CURRENT_TO_END = "current_to_end"      # 从当前到结尾
    CUSTOM_RANGE = "custom_range"          # 自定义范围


@dataclass
class TextRangeSelection:
    """文本范围选择数据类
    
    支持多种选择模式：
    - single_chapter: 单个章节，使用 chapter_index 指定
    - chapter_range: 连续章节范围，使用 start_index 和 end_index 指定
    - multi_chapter: 多章选择，使用 chapter_indices 指定
    - full_edition: 整部作品，无需额外参数
    - current_to_end: 从当前章节到结尾，使用 start_index 指定
    - custom_range: 自定义范围，使用 node_ids 指定具体节点
    """
    edition_id: int
    mode: RangeSelectionMode
    
    # 单章选择
    chapter_index: Optional[int] = None
    
    # 连续章节范围
    start_index: Optional[int] = None
    end_index: Optional[int] = None
    
    # 多章选择（不连续）
    chapter_indices: List[int] = field(default_factory=list)
    
    # 自定义范围（节点ID列表）
    node_ids: List[int] = field(default_factory=list)
    
    # 元数据
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TextRangePreview:
    """文本范围预览结果"""
    edition_id: int
    mode: RangeSelectionMode
    
    # 统计信息
    chapter_count: int
    total_chars: int
    total_words: int
    estimated_tokens: int
    
    # 选中的章节信息
    selected_chapters: List[Dict[str, Any]] = field(default_factory=list)
    
    # 预览内容（前N个字符）
    preview_text: Optional[str] = None
    
    # 警告信息
    warnings: List[str] = field(default_factory=list)
    
    # 元数据
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TextRangeContent:
    """文本范围内容结果"""
    edition_id: int
    mode: RangeSelectionMode
    
    # 完整文本内容
    full_text: str
    
    # 统计信息
    chapter_count: int
    total_chars: int
    total_words: int
    estimated_tokens: int
    
    # 章节内容列表
    chapters: List[Dict[str, Any]] = field(default_factory=list)
    
    # 元数据
    meta_data: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Analysis Task Types
# ============================================================================

class AnalysisTaskType(str, Enum):
    """分析任务类型"""
    OUTLINE_EXTRACTION = "outline_extraction"      # 大纲提取
    CHARACTER_DETECTION = "character_detection"    # 人物检测
    SETTING_EXTRACTION = "setting_extraction"      # 设定提取
    RELATION_ANALYSIS = "relation_analysis"        # 关系分析
    CONSISTENCY_CHECK = "consistency_check"        # 一致性检查
    CUSTOM_ANALYSIS = "custom_analysis"            # 自定义分析


class AnalysisTaskStatus(str, Enum):
    """分析任务状态"""
    PENDING = "pending"           # 待处理
    RUNNING = "running"           # 运行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消


@dataclass
class AnalysisTaskRequest:
    """分析任务请求"""
    edition_id: int
    task_type: AnalysisTaskType
    range_selection: TextRangeSelection
    
    # 任务配置
    config: Dict[str, Any] = field(default_factory=dict)
    
    # 优先级
    priority: int = 0
    
    # 元数据
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisTask:
    """分析任务"""
    id: str
    edition_id: int
    task_type: AnalysisTaskType
    status: AnalysisTaskStatus
    
    # 范围选择
    range_selection: TextRangeSelection
    
    # 任务配置
    config: Dict[str, Any] = field(default_factory=dict)
    
    # 进度信息
    progress: int = 0  # 0-100
    current_step: Optional[str] = None
    
    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 结果
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    # 元数据
    meta_data: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Evidence Types
# ============================================================================

@dataclass
class TextEvidence:
    """文本证据"""
    id: str
    edition_id: int
    
    # 证据位置
    node_id: int
    start_offset: int
    end_offset: int
    selected_text: str
    
    # 证据类型和目标
    evidence_type: str  # character, setting, outline, etc.
    
    # 证据内容
    content: str
    context: Optional[str] = None  # 上下文
    
    # 目标关联
    target_type: Optional[str] = None  # character, setting, etc.
    target_id: Optional[str] = None
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceCreateRequest:
    """创建证据请求"""
    edition_id: int
    node_id: int
    start_offset: int
    end_offset: int
    selected_text: str
    evidence_type: str
    content: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    context: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceUpdateRequest:
    """更新证据请求"""
    content: Optional[str] = None
    evidence_type: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    context: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None


@dataclass
class EvidenceListResponse:
    """证据列表响应"""
    evidences: List[TextEvidence]
    total: int
    node_id: Optional[int] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None


# ============================================================================
# Compatibility Types (for analysis_compat.py)
# ============================================================================

@dataclass
class AnalysisTaskData:
    """分析任务数据（兼容旧格式）"""
    id: str
    edition_id: int
    task_type: AnalysisTaskType
    status: AnalysisTaskStatus
    range_selection: TextRangeSelection
    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    progress: int = 0
    current_step: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """分析结果（兼容旧格式）"""
    id: int
    task_id: str
    result_type: str
    result_data: Dict[str, Any]
    confidence: Optional[float] = None
    review_status: str = "pending"  # pending, approved, rejected
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResultData:
    """分析结果数据（兼容旧格式）"""
    result_type: str
    content: Dict[str, Any]
    confidence: Optional[float] = None
    evidence_ids: List[str] = field(default_factory=list)
    meta_data: Dict[str, Any] = field(default_factory=dict)
