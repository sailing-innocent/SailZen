# -*- coding: utf-8 -*-
# @file outline_extraction.py
# @brief Outline Extraction Controller with Enhanced Error Feedback
# @author sailing-innocent
# @date 2025-02-28
# @version 2.0
# ---------------------------------

from __future__ import annotations
from litestar import Controller, post, get
from litestar.dto import DataclassDTO
from litestar.exceptions import NotFoundException, ClientException
from typing import Generator, List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

from sail_server.data.analysis import (
    OutlineExtractionRequest,
    OutlineExtractionConfig,
    OutlineExtractionResult,
    OutlineExtractionResponse,
    ExtractedOutlineNode,
    OutlineEvidence,
    TextRangeSelection,
)
from sail_server.service.outline_extractor import (
    OutlineExtractor,
    ServiceExtractionResult,
    ExtractionProgress,
    ExtractionErrorInfo,
)
from sail_server.service.extraction_cache import (
    get_cache_manager, ExtractionPhase
)
from sqlalchemy.orm import Session
from sail_server.db import get_db_session


# ============================================================================
# DTOs
# ============================================================================

class OutlineExtractionRequestDTO(DataclassDTO[OutlineExtractionRequest]):
    """大纲提取请求 DTO"""
    pass


class OutlineExtractionResponseDTO(DataclassDTO[OutlineExtractionResponse]):
    """大纲提取响应 DTO"""
    pass


# ============================================================================
# Response Models
# ============================================================================

@dataclass
class OutlineExtractionTaskResponse:
    """大纲提取任务响应"""
    task_id: str
    status: str
    message: str
    created_at: str


@dataclass
class OutlineExtractionProgressResponse:
    """大纲提取进度响应"""
    task_id: str
    current_step: str
    progress_percent: int
    message: str
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None
    batch_index: Optional[int] = None
    total_batches: Optional[int] = None
    
    # 新增：重试和错误信息
    is_retrying: bool = False
    retry_attempt: int = 0
    retry_delay: float = 0.0
    rate_limit_info: Optional[Dict[str, Any]] = None
    error_info: Optional[Dict[str, Any]] = None


@dataclass
class OutlineExtractionDetailedStatus:
    """大纲提取详细状态"""
    task_id: str
    status: str
    phase: str
    progress_percent: int
    current_step: str
    message: str
    
    # 批次信息
    total_batches: int
    completed_batches: List[int]
    failed_batches: List[int]
    current_batch: int
    
    # 结果统计
    total_nodes: int
    total_turning_points: int
    
    # 错误信息
    last_error: Optional[str] = None
    last_error_type: Optional[str] = None
    retry_count: int = 0
    
    # 恢复信息
    is_recovered: bool = False
    recovered_from: Optional[str] = None
    
    # 时间戳
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class OutlinePreviewResponse:
    """大纲预览响应"""
    preview_nodes: List[Dict[str, Any]]
    total_nodes: int
    estimated_tokens: int
    sample_evidence: List[str]


@dataclass
class ResumeTaskResponse:
    """恢复任务响应"""
    success: bool
    task_id: str
    message: str
    resumed_from_batch: int = 0
    total_batches: int = 0


@dataclass
class CheckpointListResponse:
    """检查点列表响应"""
    checkpoints: List[Dict[str, Any]]
    total: int


# ============================================================================
# Task Storage (In-Memory with Cache Integration)
# ============================================================================

# 任务存储（临时实现，后续应使用 Redis 或数据库）
_outline_extraction_tasks: Dict[str, Dict[str, Any]] = {}


def _create_task(
    edition_id: int,
    range_selection: TextRangeSelection,
    config: OutlineExtractionConfig,
) -> str:
    """创建提取任务"""
    task_id = str(uuid.uuid4())
    _outline_extraction_tasks[task_id] = {
        "id": task_id,
        "edition_id": edition_id,
        "range_selection": range_selection,
        "config": config,
        "status": "pending",
        "phase": ExtractionPhase.INITIALIZED.value,
        "progress": 0,
        "current_step": "pending",
        "result": None,
        "error": None,
        "error_info": None,  # 新增：详细错误信息
        "created_at": datetime.now(),
        "started_at": None,
        "completed_at": None,
        "retry_count": 0,
        "rate_limit_info": None,
    }
    return task_id


def _update_task_progress(task_id: str, progress: ExtractionProgress):
    """更新任务进度"""
    if task_id in _outline_extraction_tasks:
        task = _outline_extraction_tasks[task_id]
        task["progress"] = progress.progress_percent
        task["current_step"] = progress.current_step
        task["progress_message"] = progress.message
        task["chunk_index"] = progress.chunk_index
        task["total_chunks"] = progress.total_chunks
        task["batch_index"] = progress.chunk_index  # 复用 chunk_index 作为 batch_index
        task["total_batches"] = progress.total_chunks
        
        # 新增：重试信息
        task["is_retrying"] = progress.is_retrying
        task["retry_attempt"] = progress.retry_attempt
        task["retry_delay"] = progress.retry_delay
        task["rate_limit_info"] = progress.rate_limit_info


def _update_task_error(task_id: str, error_info: ExtractionErrorInfo):
    """更新任务错误信息"""
    if task_id in _outline_extraction_tasks:
        task = _outline_extraction_tasks[task_id]
        task["error_info"] = {
            "type": error_info.error_type,
            "message": error_info.error_message,
            "is_retryable": error_info.is_retryable,
            "retry_count": error_info.retry_count,
            "rate_limit_info": error_info.rate_limit_info,
            "suggestion": error_info.suggestion,
        }
        task["retry_count"] = error_info.retry_count


def _complete_task(task_id: str, result: ServiceExtractionResult):
    """完成任务"""
    if task_id in _outline_extraction_tasks:
        task = _outline_extraction_tasks[task_id]
        task["status"] = "completed"
        task["phase"] = ExtractionPhase.COMPLETED.value
        task["progress"] = 100
        task["result"] = result
        task["completed_at"] = datetime.now()
        task["is_recovered"] = result.is_recovered
        task["recovered_from"] = result.recovered_from_checkpoint


def _fail_task(task_id: str, error: str, error_info: Optional[Dict] = None):
    """标记任务失败"""
    if task_id in _outline_extraction_tasks:
        task = _outline_extraction_tasks[task_id]
        task["status"] = "failed"
        task["phase"] = ExtractionPhase.FAILED.value
        task["error"] = error
        if error_info:
            task["error_info"] = error_info
        task["completed_at"] = datetime.now()


# ============================================================================
# Outline Extraction Controller
# ============================================================================

class OutlineExtractionController(Controller):
    """大纲提取控制器
    
    提供大纲提取相关的 API：
    - 创建提取任务
    - 获取任务进度
    - 获取提取结果
    - 预览提取效果
    - 恢复失败任务
    - 查询详细状态
    """
    path = "/outline-extraction"
    
    @post("/", dto=OutlineExtractionRequestDTO)
    async def create_extraction_task(
        self,
        data: OutlineExtractionRequest,
    ) -> OutlineExtractionTaskResponse:
        """创建大纲提取任务
        
        Request Body:
            - edition_id: 版本ID
            - range_selection: 文本范围选择
            - config: 提取配置
                - granularity: 粒度 (act|arc|scene|beat)
                - outline_type: 大纲类型 (main|subplot|character_arc|theme)
                - extract_turning_points: 是否提取转折点
                - extract_characters: 是否关联人物
            - work_title: 作品标题（可选）
            - known_characters: 已知人物列表（可选）
        """
        task_id = _create_task(
            edition_id=data.edition_id,
            range_selection=data.range_selection,
            config=data.config,
        )
        
        # 异步执行提取任务
        asyncio.create_task(
            self._run_extraction_task(
                task_id=task_id,
                edition_id=data.edition_id,
                range_selection=data.range_selection,
                config=data.config,
                work_title=data.work_title,
                known_characters=data.known_characters,
            )
        )
        
        return OutlineExtractionTaskResponse(
            task_id=task_id,
            status="pending",
            message="大纲提取任务已创建",
            created_at=datetime.now().isoformat(),
        )
    
    async def _run_extraction_task(
        self,
        task_id: str,
        edition_id: int,
        range_selection: TextRangeSelection,
        config: OutlineExtractionConfig,
        work_title: str,
        known_characters: Optional[List[str]],
    ):
        """运行提取任务（后台）"""
        logger.info(f"[Task {task_id}] Starting extraction task for edition {edition_id}")
        
        # 更新任务状态为运行中
        if task_id in _outline_extraction_tasks:
            _outline_extraction_tasks[task_id]["status"] = "running"
            _outline_extraction_tasks[task_id]["phase"] = ExtractionPhase.CONTENT_FETCHED.value
            _outline_extraction_tasks[task_id]["started_at"] = datetime.now()
            _outline_extraction_tasks[task_id]["current_step"] = "initializing"
            logger.info(f"[Task {task_id}] Status updated to 'running'")
        
        # 定义进度回调函数
        async def progress_callback(progress_info: Dict[str, Any]):
            """更新任务进度"""
            if task_id in _outline_extraction_tasks:
                task = _outline_extraction_tasks[task_id]
                task["progress"] = progress_info.get("progress_percent", 0)
                task["current_step"] = progress_info.get("current_step", "processing")
                task["progress_message"] = progress_info.get("message", "")
                task["batch_index"] = progress_info.get("batch_index")
                task["total_batches"] = progress_info.get("total_batches")
                
                # 新增：重试信息
                task["is_retrying"] = progress_info.get("is_retrying", False)
                task["retry_attempt"] = progress_info.get("retry_attempt", 0)
                task["retry_delay"] = progress_info.get("retry_delay", 0.0)
                task["rate_limit_info"] = progress_info.get("rate_limit_info")
                
                logger.info(f"[Task {task_id}] Progress: {task['progress']}%, {task['progress_message']}")
        
        with get_db_session() as db:
            try:
                # 创建提取器
                logger.info(f"[Task {task_id}] Creating OutlineExtractor")
                extractor = OutlineExtractor(db)
                
                # 执行提取（带进度回调和任务ID）
                logger.info(f"[Task {task_id}] Starting extraction with config: granularity={config.granularity}, outline_type={config.outline_type}")
                result = await extractor.extract(
                    edition_id=edition_id,
                    range_selection=range_selection,
                    config=config,
                    work_title=work_title,
                    known_characters=known_characters,
                    progress_callback=progress_callback,
                    task_id=task_id,
                    resume_from_checkpoint=True,
                )
                
                # 完成任务
                logger.info(f"[Task {task_id}] Extraction completed successfully, nodes: {len(result.nodes)}, turning_points: {len(result.turning_points)}")
                _complete_task(task_id, result)
                logger.info(f"[Task {task_id}] Task marked as completed")
                
            except ClientException as e:
                # 处理客户端异常（包含详细错误信息）
                logger.error(f"[Task {task_id}] Extraction failed with client exception: {e}")
                error_detail = e.detail if hasattr(e, 'detail') else str(e)
                
                if isinstance(error_detail, dict) and "error_info" in error_detail:
                    _fail_task(task_id, error_detail.get("message", str(e)), error_detail.get("error_info"))
                else:
                    _fail_task(task_id, str(e))
                    
            except Exception as e:
                logger.error(f"[Task {task_id}] Extraction failed: {str(e)}", exc_info=True)
                _fail_task(task_id, str(e))
    
    @get("/task/{task_id:str}")
    async def get_task_status(
        self,
        task_id: str,
    ) -> OutlineExtractionProgressResponse:
        """获取任务状态和进度"""
        if task_id not in _outline_extraction_tasks:
            raise NotFoundException(detail=f"Task {task_id} not found")
        
        task = _outline_extraction_tasks[task_id]
        
        return OutlineExtractionProgressResponse(
            task_id=task_id,
            current_step=task.get("current_step", "unknown"),
            progress_percent=task.get("progress", 0),
            message=task.get("progress_message", ""),
            chunk_index=task.get("chunk_index"),
            total_chunks=task.get("total_chunks"),
            batch_index=task.get("batch_index"),
            total_batches=task.get("total_batches"),
            is_retrying=task.get("is_retrying", False),
            retry_attempt=task.get("retry_attempt", 0),
            retry_delay=task.get("retry_delay", 0.0),
            rate_limit_info=task.get("rate_limit_info"),
            error_info=task.get("error_info"),
        )
    
    @get("/task/{task_id:str}/detailed")
    async def get_task_detailed_status(
        self,
        task_id: str,
    ) -> OutlineExtractionDetailedStatus:
        """获取任务详细状态（包含检查点信息）"""
        if task_id not in _outline_extraction_tasks:
            raise NotFoundException(detail=f"Task {task_id} not found")
        
        task = _outline_extraction_tasks[task_id]
        
        # 从缓存管理器获取检查点信息
        cache_manager = get_cache_manager()
        checkpoint = cache_manager.get_checkpoint(task_id)
        
        if checkpoint:
            # 使用检查点的详细信息
            return OutlineExtractionDetailedStatus(
                task_id=task_id,
                status=task.get("status", "unknown"),
                phase=checkpoint.phase,
                progress_percent=checkpoint.progress_percent,
                current_step=checkpoint.current_step,
                message=checkpoint.message,
                total_batches=checkpoint.total_batches,
                completed_batches=checkpoint.completed_batches,
                failed_batches=checkpoint.failed_batches,
                current_batch=checkpoint.current_batch,
                total_nodes=len(checkpoint.accumulated_nodes),
                total_turning_points=len(checkpoint.accumulated_turning_points),
                last_error=checkpoint.last_error,
                last_error_type=checkpoint.last_error_type,
                retry_count=checkpoint.retry_count,
                is_recovered=task.get("is_recovered", False),
                recovered_from=task.get("recovered_from"),
                created_at=checkpoint.created_at,
                started_at=task.get("started_at").isoformat() if task.get("started_at") else None,
                completed_at=task.get("completed_at").isoformat() if task.get("completed_at") else None,
                updated_at=checkpoint.updated_at,
            )
        else:
            # 使用任务存储的基本信息
            result = task.get("result")
            return OutlineExtractionDetailedStatus(
                task_id=task_id,
                status=task.get("status", "unknown"),
                phase=task.get("phase", "unknown"),
                progress_percent=task.get("progress", 0),
                current_step=task.get("current_step", ""),
                message=task.get("progress_message", ""),
                total_batches=task.get("total_batches", 0),
                completed_batches=[],
                failed_batches=[],
                current_batch=task.get("batch_index", 0) or 0,
                total_nodes=len(result.nodes) if result else 0,
                total_turning_points=len(result.turning_points) if result else 0,
                last_error=task.get("error"),
                last_error_type=task.get("error_info", {}).get("type") if task.get("error_info") else None,
                retry_count=task.get("retry_count", 0),
                is_recovered=task.get("is_recovered", False),
                recovered_from=task.get("recovered_from"),
                created_at=task.get("created_at").isoformat() if task.get("created_at") else None,
                started_at=task.get("started_at").isoformat() if task.get("started_at") else None,
                completed_at=task.get("completed_at").isoformat() if task.get("completed_at") else None,
                updated_at=None,
            )
    
    @get("/task/{task_id:str}/result")
    async def get_task_result(
        self,
        task_id: str,
    ) -> OutlineExtractionResponse:
        """获取任务结果"""
        if task_id not in _outline_extraction_tasks:
            raise NotFoundException(detail=f"Task {task_id} not found")
        
        task = _outline_extraction_tasks[task_id]
        
        if task["status"] == "pending" or task["status"] == "running":
            return OutlineExtractionResponse(
                success=False,
                task_id=task_id,
                message="任务仍在进行中",
            )
        
        if task["status"] == "failed":
            error_info = task.get("error_info", {})
            return OutlineExtractionResponse(
                success=False,
                task_id=task_id,
                error=task.get("error", "Unknown error"),
                message="任务执行失败",
            )
        
        # 转换结果
        result_data = task["result"]
        if result_data:
            nodes = [
                ExtractedOutlineNode(
                    id=node.id,
                    node_type=node.node_type,
                    title=node.title,
                    summary=node.summary,
                    significance=node.significance,
                    sort_index=node.sort_index,
                    parent_id=node.parent_id,
                    characters=node.characters,
                    evidence_list=[
                        OutlineEvidence(
                            text=e.text,
                            chapter_title=e.chapter_title,
                            start_fragment=e.start_fragment,
                            end_fragment=e.end_fragment,
                        )
                        for e in (node.evidence_list or [])
                    ],
                )
                for node in result_data.nodes
            ]
            
            # 转换转折点格式
            turning_points = [
                {
                    "node_id": tp.node_id,
                    "turning_point_type": tp.turning_point_type,
                    "description": tp.description,
                }
                for tp in result_data.turning_points
            ]
            
            result = OutlineExtractionResult(
                nodes=nodes,
                metadata=result_data.metadata,
                turning_points=turning_points,
            )
        else:
            result = None
        
        return OutlineExtractionResponse(
            success=True,
            task_id=task_id,
            result=result,
            message="大纲提取完成",
        )
    
    @post("/task/{task_id:str}/save")
    async def save_extraction_result(
        self,
        task_id: str,
        router_dependency: Generator[Session, None, None] = None,
    ) -> Dict[str, Any]:
        """将提取结果保存到数据库"""
        if task_id not in _outline_extraction_tasks:
            raise NotFoundException(detail=f"Task {task_id} not found")
        
        task = _outline_extraction_tasks[task_id]
        
        if task["status"] != "completed":
            raise ClientException(detail="Task is not completed yet")
        
        db = next(router_dependency)
        
        try:
            # 创建提取器并保存
            extractor = OutlineExtractor(db)
            save_result = extractor.save_to_database(
                edition_id=task["edition_id"],
                result=task["result"],
                config=task["config"],
            )
            
            return {
                "success": True,
                "message": "大纲已保存到数据库",
                "outline_id": save_result["outline_id"],
                "nodes_created": save_result["nodes_created"],
                "events_created": save_result["events_created"],
            }
            
        except Exception as e:
            raise ClientException(detail=f"Failed to save: {str(e)}")
    
    @post("/task/{task_id:str}/resume")
    async def resume_task(
        self,
        task_id: str,
    ) -> ResumeTaskResponse:
        """恢复失败或暂停的任务"""
        if task_id not in _outline_extraction_tasks:
            raise NotFoundException(detail=f"Task {task_id} not found")
        
        task = _outline_extraction_tasks[task_id]
        
        # 检查是否可以恢复
        if task["status"] not in ["failed", "paused"]:
            return ResumeTaskResponse(
                success=False,
                task_id=task_id,
                message=f"任务状态为 {task['status']}，无法恢复",
            )
        
        # 检查检查点
        cache_manager = get_cache_manager()
        checkpoint = cache_manager.get_checkpoint(task_id)
        
        if not checkpoint:
            return ResumeTaskResponse(
                success=False,
                task_id=task_id,
                message="未找到检查点，无法恢复任务",
            )
        
        # 获取待处理的批次
        pending_batches = checkpoint.get_pending_batches()
        
        if not pending_batches:
            # 所有批次都已完成
            return ResumeTaskResponse(
                success=False,
                task_id=task_id,
                message="所有批次都已完成，无需恢复",
            )
        
        # 更新任务状态
        task["status"] = "running"
        task["phase"] = ExtractionPhase.BATCH_STARTED.value
        task["error"] = None
        task["error_info"] = None
        
        # 重新启动任务
        asyncio.create_task(
            self._run_extraction_task(
                task_id=task_id,
                edition_id=task["edition_id"],
                range_selection=task["range_selection"],
                config=task["config"],
                work_title=checkpoint.work_title,
                known_characters=checkpoint.known_characters,
            )
        )
        
        return ResumeTaskResponse(
            success=True,
            task_id=task_id,
            message=f"任务已恢复，将继续处理剩余的 {len(pending_batches)} 个批次",
            resumed_from_batch=min(pending_batches),
            total_batches=checkpoint.total_batches,
        )
    
    @post("/preview")
    async def preview_extraction(
        self,
        data: OutlineExtractionRequest,
        router_dependency: Generator[Session, None, None] = None,
    ) -> OutlinePreviewResponse:
        """预览大纲提取效果（同步，限制节点数）
        
        用于在执行完整提取前预览效果，只返回前 10 个节点。
        """
        db = next(router_dependency)
        
        try:
            # 创建提取器
            extractor = OutlineExtractor(db)
            
            # 执行提取（预览模式限制节点数）
            preview_config = OutlineExtractionConfig(
                granularity=data.config.granularity,
                outline_type=data.config.outline_type,
                max_nodes=10,  # 预览模式限制节点数
            )
            result = await extractor.extract(
                edition_id=data.edition_id,
                range_selection=data.range_selection,
                config=preview_config,
                work_title=data.work_title,
                known_characters=data.known_characters,
                resume_from_checkpoint=False,  # 预览模式不启用缓存
            )
            
            # 构建预览响应
            preview_nodes = [
                {
                    "id": node.id,
                    "node_type": node.node_type,
                    "title": node.title,
                    "summary": node.summary[:100] + "..." if len(node.summary) > 100 else node.summary,
                    "significance": node.significance,
                    "parent_id": node.parent_id,
                }
                for node in result.nodes[:10]
            ]
            
            sample_evidence = [
                evidence.text[:100] + "..."
                for node in result.nodes[:5]
                for evidence in (node.evidence_list or [])
                if evidence.text
            ]
            
            return OutlinePreviewResponse(
                preview_nodes=preview_nodes,
                total_nodes=len(result.nodes),
                estimated_tokens=result.metadata.get("estimated_tokens", 0),
                sample_evidence=sample_evidence,
            )
            
        except ClientException as e:
            # 预览模式也返回详细错误
            error_detail = e.detail if hasattr(e, 'detail') else str(e)
            if isinstance(error_detail, dict) and "error_info" in error_detail:
                raise ClientException(detail=error_detail)
            raise
        except Exception as e:
            raise ClientException(detail=f"Preview failed: {str(e)}")
    
    @get("/checkpoints")
    async def list_checkpoints(
        self,
    ) -> CheckpointListResponse:
        """列出所有可用的检查点"""
        cache_manager = get_cache_manager()
        checkpoints = cache_manager.list_checkpoints()
        
        return CheckpointListResponse(
            checkpoints=checkpoints,
            total=len(checkpoints),
        )
    
    @post("/checkpoints/cleanup")
    async def cleanup_checkpoints(
        self,
        max_age_hours: int = 24,
    ) -> Dict[str, Any]:
        """清理过期的检查点"""
        cache_manager = get_cache_manager()
        cleaned = cache_manager.cleanup_old_checkpoints(max_age_hours)
        
        return {
            "success": True,
            "cleaned_count": cleaned,
            "max_age_hours": max_age_hours,
        }


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "OutlineExtractionController",
    "OutlineExtractionRequestDTO",
    "OutlineExtractionResponseDTO",
]
