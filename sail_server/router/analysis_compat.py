# -*- coding: utf-8 -*-
# @file analysis_compat.py
# @brief Analysis API Compatibility Layer
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# 分析 API 兼容层
# 保持旧 API 接口不变，内部转发到新实现

from typing import Generator, List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from litestar import Router, Controller, get, post, delete
from litestar.di import Provide
from litestar.exceptions import NotFoundException, ValidationException

from sail_server.db import get_db_dependency
from sail_server.data.analysis import (
    AnalysisTaskDataCompat as AnalysisTaskData,
    AnalysisResultDataCompat as AnalysisResultData,
)
from sail_server.data.unified_agent import (
    UnifiedAgentTask,
    UnifiedTaskData,
    TaskType,
    TaskSubType,
    TaskStatus,
)
from sail_server.model.unified_agent import UnifiedTaskDAO
from sail_server.model.unified_scheduler_ws import get_unified_scheduler_with_ws
from sail_server.agent import get_agent_registry
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# 类型映射
# ============================================================================

# 旧任务类型 -> 新 sub_type 映射
TASK_TYPE_MAPPING = {
    "outline_extraction": TaskSubType.OUTLINE_EXTRACTION,
    "character_detection": TaskSubType.CHARACTER_DETECTION,
    "setting_extraction": TaskSubType.SETTING_EXTRACTION,
    "relation_analysis": TaskSubType.RELATION_ANALYSIS,
    "plot_analysis": TaskSubType.PLOT_ANALYSIS,
}

# 旧状态 -> 新状态映射（双向兼容）
STATUS_MAPPING = {
    # 旧 -> 新
    "pending": TaskStatus.PENDING,
    "running": TaskStatus.RUNNING,
    "completed": TaskStatus.COMPLETED,
    "failed": TaskStatus.FAILED,
    "cancelled": TaskStatus.CANCELLED,
    
    # 新 -> 旧（反向映射）
    TaskStatus.PENDING: "pending",
    TaskStatus.SCHEDULED: "pending",
    TaskStatus.RUNNING: "running",
    TaskStatus.PAUSED: "pending",
    TaskStatus.COMPLETED: "completed",
    TaskStatus.FAILED: "failed",
    TaskStatus.CANCELLED: "cancelled",
}


# ============================================================================
# Request/Response Models (兼容旧格式)
# ============================================================================

@dataclass
class CreateAnalysisTaskRequest:
    """创建分析任务请求（旧格式）"""
    edition_id: int
    task_type: str  # outline_extraction, character_detection, etc.
    target_node_ids: Optional[List[int]] = None
    target_scope: str = "full"
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_prompt_template: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5


@dataclass
class AnalysisTaskResponse:
    """分析任务响应（旧格式）"""
    id: int
    edition_id: int
    task_type: str
    status: str
    target_scope: str
    target_node_ids: Optional[List[int]]
    parameters: Dict[str, Any]
    llm_provider: Optional[str]
    llm_model: Optional[str]
    llm_prompt_template: Optional[str]
    result_summary: Optional[Dict[str, Any]]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]


@dataclass
class AnalysisProgressResponse:
    """分析进度响应（旧格式）"""
    task_id: int
    status: str
    current_step: str
    total_chunks: int
    completed_chunks: int
    current_chunk_info: Optional[str]
    started_at: Optional[str]
    estimated_remaining_seconds: Optional[int]
    error: Optional[str]


# ============================================================================
# 转换函数
# ============================================================================

def convert_old_task_type_to_new(old_type: str) -> str:
    """将旧任务类型转换为新 sub_type"""
    return TASK_TYPE_MAPPING.get(old_type, old_type)

def convert_new_status_to_old(status: str) -> str:
    """将新状态转换为旧状态"""
    return STATUS_MAPPING.get(status, status)

def convert_unified_task_to_analysis_response(
    task: UnifiedAgentTask
) -> AnalysisTaskResponse:
    """将统一任务转换为旧分析任务响应"""
    # 反向查找旧任务类型
    old_task_type = task.sub_type or task.task_type
    for old, new in TASK_TYPE_MAPPING.items():
        if new == old_task_type:
            old_task_type = old
            break
    
    return AnalysisTaskResponse(
        id=task.id,
        edition_id=task.edition_id or 0,
        task_type=old_task_type,
        status=convert_new_status_to_old(task.status),
        target_scope=task.target_scope or "full",
        target_node_ids=task.target_node_ids,
        parameters=task.config or {},
        llm_provider=task.llm_provider,
        llm_model=task.llm_model,
        llm_prompt_template=task.prompt_template_id,
        result_summary=task.result_data,
        created_at=task.created_at.isoformat() if task.created_at else "",
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        error_message=task.error_message,
    )


# ============================================================================
# 兼容层 Controllers
# ============================================================================

class AnalysisTaskCompatController(Controller):
    """分析任务兼容控制器"""
    path = "/task"
    
    @post("")
    async def create_task(
        self,
        router_dependency: Generator[Session, None, None],
        data: CreateAnalysisTaskRequest,
    ) -> AnalysisTaskResponse:
        """创建分析任务（兼容旧 API）"""
        db = next(router_dependency)
        
        # 转换为新格式
        sub_type = convert_old_task_type_to_new(data.task_type)
        
        # 创建统一任务
        task_data = UnifiedTaskData(
            task_type=TaskType.NOVEL_ANALYSIS,
            sub_type=sub_type,
            edition_id=data.edition_id,
            target_node_ids=data.target_node_ids,
            target_scope=data.target_scope,
            llm_provider=data.llm_provider,
            llm_model=data.llm_model,
            prompt_template_id=data.llm_prompt_template,
            priority=data.priority,
            config=data.parameters,
        )
        
        # 保存到数据库
        dao = UnifiedTaskDAO(db)
        orm = dao.create(task_data)
        task_data.id = orm.id
        
        # 调度任务
        scheduler = get_unified_scheduler_with_ws()
        if not scheduler.is_running():
            await scheduler.start()
        
        await scheduler.schedule_task(task_data)
        
        return convert_unified_task_to_analysis_response(orm)
    
    @get("")
    async def list_tasks(
        self,
        router_dependency: Generator[Session, None, None],
        edition_id: Optional[int] = None,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[AnalysisTaskResponse]:
        """获取分析任务列表（兼容旧 API）"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        # 转换状态
        new_status = None
        if status:
            new_status = STATUS_MAPPING.get(status)
        
        # 转换任务类型
        sub_type = None
        if task_type:
            sub_type = convert_old_task_type_to_new(task_type)
        
        # 查询统一任务
        tasks = dao.list_tasks(
            status=new_status,
            task_type=TaskType.NOVEL_ANALYSIS if task_type else None,
            sub_type=sub_type,
            edition_id=edition_id,
            skip=skip,
            limit=limit,
        )
        
        return [convert_unified_task_to_analysis_response(t) for t in tasks]
    
    @get("/{task_id:int}")
    async def get_task(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
    ) -> AnalysisTaskResponse:
        """获取分析任务详情（兼容旧 API）"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        task = dao.get_by_id(task_id)
        if not task:
            raise NotFoundException(f"Task {task_id} not found")
        
        return convert_unified_task_to_analysis_response(task)
    
    @post("/{task_id:int}/cancel")
    async def cancel_task(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
    ) -> Dict[str, Any]:
        """取消分析任务（兼容旧 API）"""
        scheduler = get_unified_scheduler_with_ws()
        
        success = await scheduler.cancel_task(task_id)
        if not success:
            raise ValidationException(f"Failed to cancel task {task_id}")
        
        return {"success": True, "message": f"Task {task_id} cancelled"}
    
    @delete("/{task_id:int}", status_code=200)
    async def delete_task(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
    ) -> Dict[str, Any]:
        """删除分析任务（兼容旧 API）"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        # 先取消
        scheduler = get_unified_scheduler_with_ws()
        await scheduler.cancel_task(task_id)
        
        # 删除
        success = dao.delete(task_id)
        if not success:
            raise NotFoundException(f"Task {task_id} not found")
        
        return {"success": True, "message": f"Task {task_id} deleted"}


class AnalysisProgressCompatController(Controller):
    """分析进度兼容控制器"""
    path = "/progress"
    
    @get("/{task_id:int}")
    async def get_progress(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
    ) -> AnalysisProgressResponse:
        """获取分析进度（兼容旧 API）"""
        scheduler = get_unified_scheduler_with_ws()
        
        progress = scheduler.get_task_progress(task_id)
        
        if not progress:
            # 从数据库获取
            db = next(router_dependency)
            dao = UnifiedTaskDAO(db)
            task = dao.get_by_id(task_id)
            
            if not task:
                raise NotFoundException(f"Task {task_id} not found")
            
            return AnalysisProgressResponse(
                task_id=task_id,
                status=convert_new_status_to_old(task.status),
                current_step="unknown",
                total_chunks=0,
                completed_chunks=0,
                current_chunk_info=None,
                started_at=task.started_at.isoformat() if task.started_at else None,
                estimated_remaining_seconds=None,
                error=task.error_message,
            )
        
        # 转换进度格式
        return AnalysisProgressResponse(
            task_id=progress.task_id,
            status=convert_new_status_to_old(progress.status),
            current_step=progress.current_phase or "unknown",
            total_chunks=progress.total_steps or 0,
            completed_chunks=progress.current_step or 0,
            current_chunk_info=None,
            started_at=progress.started_at.isoformat() if progress.started_at else None,
            estimated_remaining_seconds=progress.estimated_remaining_seconds,
            error=progress.error_message,
        )


class AnalysisResultCompatController(Controller):
    """分析结果兼容控制器"""
    path = "/result"
    
    @get("/{task_id:int}")
    async def get_results(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
        result_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """获取分析结果（兼容旧 API）"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        task = dao.get_by_id(task_id)
        if not task:
            raise NotFoundException(f"Task {task_id} not found")
        
        # 从 result_data 中提取结果
        result_data = task.result_data or {}
        raw_results = result_data.get("raw_results", [])
        
        # 过滤结果类型
        if result_type:
            raw_results = [r for r in raw_results if r.get("result_type") == result_type]
        
        # 分页
        total = len(raw_results)
        paginated = raw_results[skip:skip + limit]
        
        return {
            "success": True,
            "task_id": task_id,
            "total": total,
            "results": paginated,
        }
    
    @post("/{task_id:int}/verify")
    async def verify_result(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """审核分析结果（兼容旧 API）"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        task = dao.get_by_id(task_id)
        if not task:
            raise NotFoundException(f"Task {task_id} not found")
        
        # 更新审核状态
        review_status = data.get("status", "pending")
        dao.update_review_status(task_id, review_status)
        
        return {
            "success": True,
            "message": f"Result review status updated to {review_status}",
        }


# ============================================================================
# Router
# ============================================================================

analysis_compat_router = Router(
    path="/analysis-compat",
    route_handlers=[
        AnalysisTaskCompatController,
        AnalysisProgressCompatController,
        AnalysisResultCompatController,
    ],
    tags=["Analysis (Compatibility)"],
    dependencies={"router_dependency": Provide(get_db_dependency)},
)
