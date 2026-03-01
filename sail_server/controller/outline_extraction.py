# -*- coding: utf-8 -*-
# @file outline_extraction.py
# @brief Outline Extraction Controller with Enhanced Error Feedback and Persistence
# @author sailing-innocent
# @date 2025-02-28
# @version 2.1
# ---------------------------------

from __future__ import annotations
from litestar import Controller, post, get
from litestar.exceptions import NotFoundException, ClientException
from typing import Generator, List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import uuid
import asyncio
import logging
import json
import os

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from sail_server.application.dto.analysis import TextRangeSelection

from sail_server.service.outline_extractor import (
    OutlineExtractor,
    ServiceExtractionResult,
    ExtractionProgress,
    ExtractionErrorInfo,
    OutlineExtractionConfig,
    ExtractedOutlineNode,
    OutlineEvidence,
)
from sail_server.service.extraction_cache import (
    get_cache_manager, ExtractionPhase
)
from sqlalchemy.orm import Session
from sail_server.db import get_db_session


# ============================================================================
# Local Pydantic Models for API
# ============================================================================

class OutlineExtractionRequest(BaseModel):
    """大纲提取请求"""
    edition_id: int = Field(description="版本ID")
    range_selection: TextRangeSelection = Field(description="文本范围选择")
    config: OutlineExtractionConfig = Field(description="提取配置")
    work_title: str = Field(default="", description="作品标题")
    known_characters: Optional[List[str]] = Field(default=None, description="已知人物列表")


class OutlineExtractionResult(BaseModel):
    """大纲提取结果"""
    nodes: List[ExtractedOutlineNode] = Field(default_factory=list, description="提取的节点")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    turning_points: List[Dict[str, Any]] = Field(default_factory=list, description="转折点")


class OutlineExtractionResponse(BaseModel):
    """大纲提取响应"""
    success: bool = Field(description="是否成功")
    task_id: Optional[str] = Field(default=None, description="任务ID")
    result: Optional[OutlineExtractionResult] = Field(default=None, description="提取结果")
    message: str = Field(default="", description="消息")
    error: Optional[str] = Field(default=None, description="错误信息")


class OutlineExtractionTaskResponse(BaseModel):
    """大纲提取任务响应"""
    task_id: str = Field(description="任务ID")
    status: str = Field(description="状态")
    message: str = Field(description="消息")
    created_at: str = Field(description="创建时间")


class OutlineExtractionProgressResponse(BaseModel):
    """大纲提取进度响应"""
    task_id: str = Field(description="任务ID")
    current_step: str = Field(description="当前步骤")
    progress_percent: int = Field(description="进度百分比")
    message: str = Field(description="消息")
    chunk_index: Optional[int] = Field(default=None, description="当前块索引")
    total_chunks: Optional[int] = Field(default=None, description="总块数")
    batch_index: Optional[int] = Field(default=None, description="当前批次索引")
    total_batches: Optional[int] = Field(default=None, description="总批次数")
    is_retrying: bool = Field(default=False, description="是否重试中")
    retry_attempt: int = Field(default=0, description="重试次数")
    retry_delay: float = Field(default=0.0, description="重试延迟")
    rate_limit_info: Optional[Dict[str, Any]] = Field(default=None, description="速率限制信息")
    error_info: Optional[Dict[str, Any]] = Field(default=None, description="错误信息")


class OutlineExtractionDetailedStatus(BaseModel):
    """大纲提取详细状态"""
    task_id: str = Field(description="任务ID")
    status: str = Field(description="状态")
    phase: str = Field(description="阶段")
    progress_percent: int = Field(description="进度百分比")
    current_step: str = Field(description="当前步骤")
    message: str = Field(description="消息")
    total_batches: int = Field(description="总批次数")
    completed_batches: List[int] = Field(default_factory=list, description="已完成批次")
    failed_batches: List[int] = Field(default_factory=list, description="失败批次")
    current_batch: int = Field(description="当前批次")
    total_nodes: int = Field(description="总节点数")
    total_turning_points: int = Field(description="总转折点数")
    last_error: Optional[str] = Field(default=None, description="最后错误")
    last_error_type: Optional[str] = Field(default=None, description="最后错误类型")
    retry_count: int = Field(default=0, description="重试次数")
    is_recovered: bool = Field(default=False, description="是否已恢复")
    recovered_from: Optional[str] = Field(default=None, description="恢复来源")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    started_at: Optional[str] = Field(default=None, description="开始时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")


class OutlinePreviewResponse(BaseModel):
    """大纲预览响应"""
    preview_nodes: List[Dict[str, Any]] = Field(default_factory=list, description="预览节点")
    total_nodes: int = Field(description="总节点数")
    estimated_tokens: int = Field(description="预估token数")
    sample_evidence: List[str] = Field(default_factory=list, description="示例证据")


class ResumeTaskResponse(BaseModel):
    """恢复任务响应"""
    success: bool = Field(description="是否成功")
    task_id: str = Field(description="任务ID")
    message: str = Field(description="消息")
    resumed_from_batch: int = Field(default=0, description="恢复批次")
    total_batches: int = Field(default=0, description="总批次数")


class CheckpointListResponse(BaseModel):
    """检查点列表响应"""
    checkpoints: List[Dict[str, Any]] = Field(default_factory=list, description="检查点列表")
    total: int = Field(description="总数")


# ============================================================================
# Task Storage (In-Memory with Disk Persistence)
# ============================================================================

# 任务状态持久化目录
TASK_STATE_DIR = Path(os.getcwd()) / ".cache" / "task_states"
TASK_STATE_DIR.mkdir(parents=True, exist_ok=True)

# 内存中的任务存储
_outline_extraction_tasks: Dict[str, Dict[str, Any]] = {}


def _get_task_state_path(task_id: str) -> Path:
    """获取任务状态文件路径"""
    return TASK_STATE_DIR / f"{task_id}.json"


def _serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
    """序列化 datetime 为 ISO 格式字符串"""
    return dt.isoformat() if dt else None


def _deserialize_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """从 ISO 格式字符串反序列化 datetime"""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return None


def _save_task_state(task_id: str, task_data: Dict[str, Any]) -> bool:
    """将任务状态持久化到磁盘"""
    try:
        # 处理可能为 Pydantic 模型的字段
        range_selection = task_data.get("range_selection")
        if hasattr(range_selection, 'model_dump'):
            range_selection = range_selection.model_dump()
        
        config = task_data.get("config")
        if hasattr(config, 'model_dump'):
            config = config.model_dump()
        
        # 构建可序列化的状态数据
        state_data = {
            "id": task_data.get("id", task_id),
            "edition_id": task_data.get("edition_id"),
            "range_selection": range_selection,
            "config": config,
            "status": task_data.get("status", "unknown"),
            "phase": task_data.get("phase", ExtractionPhase.INITIALIZED.value),
            "progress": task_data.get("progress", 0),
            "current_step": task_data.get("current_step", ""),
            "progress_message": task_data.get("progress_message", ""),
            "error": task_data.get("error"),
            "error_info": task_data.get("error_info"),
            "is_retrying": task_data.get("is_retrying", False),
            "retry_attempt": task_data.get("retry_attempt", 0),
            "retry_delay": task_data.get("retry_delay", 0.0),
            "rate_limit_info": task_data.get("rate_limit_info"),
            "chunk_index": task_data.get("chunk_index"),
            "total_chunks": task_data.get("total_chunks"),
            "batch_index": task_data.get("batch_index"),
            "total_batches": task_data.get("total_batches"),
            "is_recovered": task_data.get("is_recovered", False),
            "recovered_from_checkpoint": task_data.get("recovered_from_checkpoint"),
            "created_at": _serialize_datetime(task_data.get("created_at")),
            "started_at": _serialize_datetime(task_data.get("started_at")),
            "completed_at": _serialize_datetime(task_data.get("completed_at")),
            "updated_at": datetime.now().isoformat(),
        }
        
        state_path = _get_task_state_path(task_id)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"[TaskState] Saved state for task {task_id}")
        return True
    except Exception as e:
        logger.error(f"[TaskState] Failed to save state for task {task_id}: {e}")
        return False


def _load_task_state(task_id: str) -> Optional[Dict[str, Any]]:
    """从磁盘加载任务状态"""
    try:
        state_path = _get_task_state_path(task_id)
        if not state_path.exists():
            return None
        
        with open(state_path, "r", encoding="utf-8") as f:
            state_data = json.load(f)
        
        # 转换时间戳为 datetime 对象
        state_data["created_at"] = _deserialize_datetime(state_data.get("created_at"))
        state_data["started_at"] = _deserialize_datetime(state_data.get("started_at"))
        state_data["completed_at"] = _deserialize_datetime(state_data.get("completed_at"))
        
        logger.debug(f"[TaskState] Loaded state for task {task_id}")
        return state_data
    except Exception as e:
        logger.error(f"[TaskState] Failed to load state for task {task_id}: {e}")
        return None


def _load_all_task_states() -> Dict[str, Dict[str, Any]]:
    """加载所有持久化的任务状态到内存"""
    tasks = {}
    try:
        for state_file in TASK_STATE_DIR.glob("*.json"):
            try:
                task_id = state_file.stem
                task_data = _load_task_state(task_id)
                if task_data:
                    tasks[task_id] = task_data
            except Exception as e:
                logger.warning(f"[TaskState] Failed to load state file {state_file}: {e}")
        
        logger.info(f"[TaskState] Loaded {len(tasks)} persisted task states")
    except Exception as e:
        logger.error(f"[TaskState] Failed to load task states: {e}")
    
    return tasks


def _delete_task_state(task_id: str) -> bool:
    """删除任务状态文件"""
    try:
        state_path = _get_task_state_path(task_id)
        if state_path.exists():
            state_path.unlink()
            logger.debug(f"[TaskState] Deleted state for task {task_id}")
        return True
    except Exception as e:
        logger.error(f"[TaskState] Failed to delete state for task {task_id}: {e}")
        return False


def _cleanup_old_task_states(max_age_hours: int = 48) -> int:
    """清理过期的任务状态文件"""
    cleaned = 0
    try:
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        for state_file in TASK_STATE_DIR.glob("*.json"):
            try:
                if state_file.stat().st_mtime < cutoff:
                    state_file.unlink()
                    cleaned += 1
            except Exception as e:
                logger.warning(f"[TaskState] Failed to cleanup {state_file}: {e}")
        
        if cleaned > 0:
            logger.info(f"[TaskState] Cleaned up {cleaned} old task states")
    except Exception as e:
        logger.error(f"[TaskState] Failed to cleanup old states: {e}")
    
    return cleaned


def _create_task(
    edition_id: int,
    range_selection: TextRangeSelection,
    config: OutlineExtractionConfig,
) -> str:
    """创建提取任务"""
    task_id = str(uuid.uuid4())
    task_data = {
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
        "error_info": None,
        "created_at": datetime.now(),
        "started_at": None,
        "completed_at": None,
        "retry_count": 0,
        "rate_limit_info": None,
    }
    _outline_extraction_tasks[task_id] = task_data
    _save_task_state(task_id, task_data)
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
        task["batch_index"] = progress.chunk_index
        task["total_batches"] = progress.total_chunks
        
        # 新增：重试信息
        task["is_retrying"] = progress.is_retrying
        task["retry_attempt"] = progress.retry_attempt
        task["retry_delay"] = progress.retry_delay
        task["rate_limit_info"] = progress.rate_limit_info
        
        # 持久化到磁盘
        _save_task_state(task_id, task)


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
        _save_task_state(task_id, task)


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
        task["recovered_from_checkpoint"] = result.recovered_from_checkpoint
        _save_task_state(task_id, task)


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
        _save_task_state(task_id, task)


# 初始化时加载所有持久化的任务状态
_outline_extraction_tasks = _load_all_task_states()


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
    
    @post("/")
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
            from dataclasses import replace
            preview_config = replace(data.config, max_nodes=10)
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
    
    @get("/tasks/edition/{edition_id:int}")
    async def get_edition_tasks(
        self,
        edition_id: int,
    ) -> List[Dict[str, Any]]:
        """获取指定版本的所有大纲提取任务
        
        Args:
            edition_id: 版本ID
            
        Returns:
            该版本的任务列表，按创建时间倒序排列
        """
        tasks = []
        for task_id, task_data in _outline_extraction_tasks.items():
            if task_data.get("edition_id") == edition_id:
                # 从检查点获取额外信息
                cache_manager = get_cache_manager()
                checkpoint = cache_manager.get_checkpoint(task_id)
                
                # 构建任务摘要
                task_summary = {
                    "task_id": task_id,
                    "edition_id": task_data.get("edition_id"),
                    "status": task_data.get("status", "unknown"),
                    "phase": task_data.get("phase", "unknown"),
                    "progress": task_data.get("progress", 0),
                    "current_step": task_data.get("current_step", ""),
                    "config": task_data.get("config"),
                    "error": task_data.get("error"),
                    "is_recovered": task_data.get("is_recovered", False),
                    "created_at": _serialize_datetime(task_data.get("created_at")),
                    "started_at": _serialize_datetime(task_data.get("started_at")),
                    "completed_at": _serialize_datetime(task_data.get("completed_at")),
                }
                
                # 添加检查点信息（如果有）
                if checkpoint:
                    task_summary["checkpoint_progress"] = checkpoint.progress_percent
                    task_summary["total_nodes"] = len(checkpoint.accumulated_nodes)
                    task_summary["total_turning_points"] = len(checkpoint.accumulated_turning_points)
                    task_summary["total_batches"] = checkpoint.total_batches
                    task_summary["completed_batches"] = len(checkpoint.completed_batches)
                
                tasks.append(task_summary)
        
        # 按创建时间倒序排列
        tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return tasks
    
    @get("/task/{task_id:str}/recover")
    async def recover_task_view(
        self,
        task_id: str,
    ) -> OutlineExtractionResponse:
        """恢复任务查看（支持从检查点重建结果）
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务结果或进度信息
        """
        # 1. 尝试从内存获取
        if task_id in _outline_extraction_tasks:
            task = _outline_extraction_tasks[task_id]
            
            # 如果任务已完成，返回结果
            if task["status"] == "completed" and task.get("result"):
                result_data = task["result"]
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
                
                turning_points = [
                    {
                        "node_id": tp.node_id,
                        "turning_point_type": tp.turning_point_type,
                        "description": tp.description,
                    }
                    for tp in result_data.turning_points
                ]
                
                return OutlineExtractionResponse(
                    success=True,
                    task_id=task_id,
                    result=OutlineExtractionResult(
                        nodes=nodes,
                        metadata=result_data.metadata,
                        turning_points=turning_points,
                    ),
                    message="任务结果已从内存恢复",
                )
            
            # 任务还在运行中，返回进度
            if task["status"] in ["pending", "running"]:
                return OutlineExtractionResponse(
                    success=True,
                    task_id=task_id,
                    message=f"任务正在进行中，当前进度: {task.get('progress', 0)}%",
                )
        
        # 2. 从检查点获取结果（即使内存中没有）
        cache_manager = get_cache_manager()
        checkpoint = cache_manager.get_checkpoint(task_id)
        
        if checkpoint:
            # 检查点存在，尝试重建结果
            if checkpoint.phase == ExtractionPhase.COMPLETED.value or len(checkpoint.accumulated_nodes) > 0:
                # 从检查点重建节点
                nodes = [
                    ExtractedOutlineNode(
                        id=node_dict.get("id", str(uuid.uuid4())),
                        node_type=node_dict.get("node_type", "scene"),
                        title=node_dict.get("title", ""),
                        summary=node_dict.get("summary", ""),
                        significance=node_dict.get("significance", "normal"),
                        sort_index=node_dict.get("sort_index", 0),
                        parent_id=node_dict.get("parent_id"),
                        characters=node_dict.get("characters", []),
                        evidence_list=[
                            OutlineEvidence(
                                text=e.get("text", ""),
                                chapter_title=e.get("chapter_title", ""),
                                start_fragment=e.get("start_fragment", ""),
                                end_fragment=e.get("end_fragment", ""),
                            )
                            for e in node_dict.get("evidence_list", [])
                        ],
                    )
                    for node_dict in checkpoint.accumulated_nodes
                ]
                
                turning_points = checkpoint.accumulated_turning_points
                
                return OutlineExtractionResponse(
                    success=True,
                    task_id=task_id,
                    result=OutlineExtractionResult(
                        nodes=nodes,
                        metadata={
                            "recovered_from_checkpoint": True,
                            "checkpoint_phase": checkpoint.phase,
                            "total_batches": checkpoint.total_batches,
                            "completed_batches": len(checkpoint.completed_batches),
                        },
                        turning_points=turning_points,
                    ),
                    message=f"任务结果已从检查点恢复（{len(checkpoint.completed_batches)}/{checkpoint.total_batches} 批次）",
                )
            else:
                # 检查点存在但未完成
                return OutlineExtractionResponse(
                    success=True,
                    task_id=task_id,
                    message=f"任务处理中，已完成 {len(checkpoint.completed_batches)}/{checkpoint.total_batches} 批次",
                )
        
        # 3. 尝试从磁盘加载任务状态
        task_state = _load_task_state(task_id)
        if task_state:
            status = task_state.get("status", "unknown")
            progress = task_state.get("progress", 0)
            
            if status == "completed":
                return OutlineExtractionResponse(
                    success=False,
                    task_id=task_id,
                    error="任务状态显示已完成，但未找到结果数据",
                    message="任务结果不可用，请重新创建任务",
                )
            else:
                return OutlineExtractionResponse(
                    success=True,
                    task_id=task_id,
                    message=f"任务状态: {status}, 进度: {progress}%",
                )
        
        # 任务不存在
        raise NotFoundException(detail=f"Task {task_id} not found")
    
    @post("/task/{task_id:str}/dismiss")
    async def dismiss_task(
        self,
        task_id: str,
    ) -> Dict[str, Any]:
        """关闭并清理任务
        
        用户查看完任务结果后，可以调用此接口清理任务状态和检查点
        
        Args:
            task_id: 任务ID
            
        Returns:
            清理结果
        """
        # 从内存中移除
        if task_id in _outline_extraction_tasks:
            del _outline_extraction_tasks[task_id]
        
        # 删除持久化状态
        _delete_task_state(task_id)
        
        # 删除检查点
        cache_manager = get_cache_manager()
        cache_manager.delete_checkpoint(task_id)
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "任务已关闭并清理",
        }
    
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
        """清理过期的检查点和任务状态"""
        cache_manager = get_cache_manager()
        checkpoints_cleaned = cache_manager.cleanup_old_checkpoints(max_age_hours)
        states_cleaned = _cleanup_old_task_states(max_age_hours)
        
        return {
            "success": True,
            "checkpoints_cleaned": checkpoints_cleaned,
            "task_states_cleaned": states_cleaned,
            "max_age_hours": max_age_hours,
        }


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "OutlineExtractionController",
    "OutlineExtractionRequest",
    "OutlineExtractionResponse",
]
