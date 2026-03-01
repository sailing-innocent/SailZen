# -*- coding: utf-8 -*-
# @file outline_task_registry.py
# @brief Outline Extraction Task Registry with Unified Agent Integration
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
大纲提取任务注册表

集成 Unified Agent 系统，提供：
- 数据库持久化的任务状态
- 异步任务执行管理
- WebSocket 事件推送
- 自动恢复机制
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session

from sail_server.model.unified_agent import UnifiedTaskDAO, UnifiedStepDAO, UnifiedEventDAO
from sail_server.application.dto.unified_agent import (
    UnifiedAgentTaskCreateRequest,
    TaskStatus,
)
from sail_server.service.persistent_checkpoint import (
    PersistentCheckpointManager, get_persistent_checkpoint_manager
)
from sail_server.service.outline_extractor import (
    OutlineExtractor, ServiceExtractionResult, ExtractionProgress
)
from sail_server.application.dto.analysis import TextRangeSelection, OutlineExtractionConfig
from sail_server.utils.llm.client import LLMClient, LLMConfig, LLMProvider
from sail_server.utils.llm.available_providers import (
    DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL, DEFAULT_LLM_CONFIG
)

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TaskRuntimeState:
    """任务运行时状态"""
    task_id: int
    db_task_id: int
    status: str
    progress: int = 0
    current_step: str = ""
    checkpoint: Optional[Dict[str, Any]] = None
    result: Optional[ServiceExtractionResult] = None
    error: Optional[str] = None
    cancelled: bool = False


# ============================================================================
# Outline Task Registry
# ============================================================================

class OutlineTaskRegistry:
    """大纲提取任务注册表
    
    管理大纲提取任务的生命周期：
    - 创建任务（数据库持久化）
    - 执行任务（异步）
    - 监控进度（WebSocket 推送）
    - 恢复任务（检查点恢复）
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.task_dao = UnifiedTaskDAO(db)
        self.step_dao = UnifiedStepDAO(db)
        self.event_dao = UnifiedEventDAO(db)
        self.checkpoint_manager = get_persistent_checkpoint_manager(db)
        
        # 运行时状态
        self._runtime_states: Dict[int, TaskRuntimeState] = {}
        self._event_callbacks: List[Callable[[int, str, Dict[str, Any]], None]] = []
    
    # --------------------------------------------------------------------------
    # Task Creation
    # --------------------------------------------------------------------------
    
    def create_task(
        self,
        edition_id: int,
        range_selection: TextRangeSelection,
        config: OutlineExtractionConfig,
        work_title: str = "",
        known_characters: Optional[List[str]] = None,
    ) -> int:
        """创建大纲提取任务"""
        # 1. 创建数据库记录
        create_request = UnifiedAgentTaskCreateRequest(
            task_type="novel_analysis",
            sub_type="outline_extraction",
            edition_id=edition_id,
            target_scope="full" if range_selection.mode == "full_edition" else "range",
            llm_provider=config.llm_provider or DEFAULT_LLM_PROVIDER,
            llm_model=config.llm_model or DEFAULT_LLM_MODEL,
            prompt_template_id=config.prompt_template_id,
            priority=5,
            config={
                "extraction_config": {
                    "granularity": config.granularity,
                    "outline_type": config.outline_type,
                    "extract_turning_points": config.extract_turning_points,
                    "extract_characters": config.extract_characters,
                    "max_nodes": config.max_nodes,
                    "temperature": config.temperature,
                },
                "range_selection": range_selection.model_dump(),
                "work_title": work_title,
                "known_characters": known_characters or [],
                "checkpoint_enabled": True,
                "checkpoint_interval_batches": 1,
            },
        )
        
        task = self.task_dao.create(create_request)
        
        # 2. 创建检查点
        self.checkpoint_manager.create_checkpoint(
            task_id=str(task.id),
            edition_id=edition_id,
            config=create_request.config["extraction_config"],
            range_selection=create_request.config["range_selection"],
            work_title=work_title,
            known_characters=known_characters,
            total_batches=0,  # 将在执行时确定
        )
        
        # 3. 记录事件
        self.event_dao.create(
            task_id=task.id,
            event_type="task_created",
            event_data={
                "edition_id": edition_id,
                "config": create_request.config["extraction_config"],
            },
        )
        
        logger.info(f"[TaskRegistry] Created outline extraction task {task.id}")
        return task.id
    
    # --------------------------------------------------------------------------
    # Task Execution
    # --------------------------------------------------------------------------
    
    async def execute_task(
        self,
        task_id: int,
        progress_callback: Optional[Callable[[int, Dict[str, Any]], None]] = None,
    ) -> ServiceExtractionResult:
        """执行大纲提取任务"""
        # 1. 获取任务信息
        task = self.task_dao.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # 2. 更新任务状态为运行中
        self.task_dao.mark_as_running(task_id)
        
        # 3. 创建运行时状态
        runtime_state = TaskRuntimeState(
            task_id=task_id,
            db_task_id=task_id,
            status="running",
        )
        self._runtime_states[task_id] = runtime_state
        
        # 4. 记录事件
        self.event_dao.create(
            task_id=task_id,
            event_type="task_started",
            event_data={"started_at": datetime.utcnow().isoformat()},
        )
        
        # 5. 解析配置
        config_data = task.config or {}
        extraction_config_data = config_data.get("extraction_config", {})
        range_selection_data = config_data.get("range_selection", {})
        work_title = config_data.get("work_title", "")
        known_characters = config_data.get("known_characters", [])
        
        logger.info(f"[TaskRegistry] Task {task_id}: config_data keys={list(config_data.keys())}")
        logger.info(f"[TaskRegistry] Task {task_id}: range_selection_data={range_selection_data}")
        
        # 6. 构建配置对象
        # 检查 provider 是否可用，如果不可用则回退到默认
        llm_provider = task.llm_provider or DEFAULT_LLM_PROVIDER
        logger.info(f"[TaskRegistry] Task {task_id}: task.llm_provider={task.llm_provider}, using llm_provider={llm_provider}")
        try:
            # 尝试创建 LLMConfig，如果失败则使用默认值
            from sail_server.utils.llm.client import LLMConfig, LLMProvider
            LLMConfig.from_env(LLMProvider(llm_provider))
        except (ValueError, KeyError) as e:
            logger.warning(f"[TaskRegistry] Provider {llm_provider} not available: {e}, using default {DEFAULT_LLM_PROVIDER}")
            llm_provider = DEFAULT_LLM_PROVIDER
        
        config = OutlineExtractionConfig(
            granularity=extraction_config_data.get("granularity", "scene"),
            outline_type=extraction_config_data.get("outline_type", "main"),
            extract_turning_points=extraction_config_data.get("extract_turning_points", True),
            extract_characters=extraction_config_data.get("extract_characters", True),
            max_nodes=extraction_config_data.get("max_nodes", 50),
            temperature=extraction_config_data.get("temperature", 0.3),
            llm_provider=llm_provider,
            llm_model=task.llm_model or DEFAULT_LLM_MODEL,
            prompt_template_id=task.prompt_template_id or "outline_extraction_v2",
        )
        logger.info(f"[TaskRegistry] Task {task_id}: Created OutlineExtractionConfig with llm_provider={config.llm_provider}, llm_model={config.llm_model}")
        
        range_selection = TextRangeSelection(**range_selection_data)
        
        # 7. 创建提取器
        extractor = OutlineExtractor(self.db)
        
        # 8. 定义进度回调
        async def on_progress(progress_info: Dict[str, Any]):
            # 更新运行时状态
            runtime_state.progress = progress_info.get("progress_percent", 0)
            runtime_state.current_step = progress_info.get("current_step", "")
            
            # 更新数据库进度
            self.task_dao.update_progress(
                task_id=task_id,
                progress=runtime_state.progress,
                current_phase=runtime_state.current_step,
            )
            
            # 推送事件
            self._emit_event(task_id, "task_progress", {
                "progress": runtime_state.progress,
                "current_phase": runtime_state.current_step,
                "batch_index": progress_info.get("batch_index"),
                "total_batches": progress_info.get("total_batches"),
            })
            
            # 调用外部回调
            if progress_callback:
                progress_callback(task_id, progress_info)
        
        try:
            # 9. 执行提取
            result = await extractor.extract(
                edition_id=task.edition_id,
                range_selection=range_selection,
                config=config,
                work_title=work_title,
                known_characters=known_characters,
                progress_callback=on_progress,
                task_id=str(task_id),
                resume_from_checkpoint=True,
            )
            
            # 10. 更新任务状态为完成
            result_data = {
                "extraction_result": {
                    "nodes": [self._node_to_dict(n) for n in result.nodes],
                    "turning_points": [
                        {
                            "node_id": tp.node_id,
                            "turning_point_type": tp.turning_point_type,
                            "description": tp.description,
                        }
                        for tp in result.turning_points
                    ],
                    "metadata": result.metadata,
                },
                "checkpoint": {
                    "phase": "completed",
                    "progress_percent": 100,
                    "total_nodes": len(result.nodes),
                    "total_turning_points": len(result.turning_points),
                },
            }
            
            self.task_dao.mark_as_completed(task_id, result_data)
            
            # 11. 记录完成事件
            self.event_dao.create(
                task_id=task_id,
                event_type="task_completed",
                event_data={
                    "completed_at": datetime.utcnow().isoformat(),
                    "total_nodes": len(result.nodes),
                    "total_turning_points": len(result.turning_points),
                },
            )
            
            runtime_state.result = result
            runtime_state.status = "completed"
            
            # 12. 推送完成事件
            self._emit_event(task_id, "task_completed", result_data)
            
            logger.info(f"[TaskRegistry] Task {task_id} completed successfully")
            return result
            
        except Exception as e:
            # 更新任务状态为失败
            error_message = str(e)
            self.task_dao.mark_as_failed(task_id, error_message)
            
            runtime_state.error = error_message
            runtime_state.status = "failed"
            
            # 记录失败事件
            self.event_dao.create(
                task_id=task_id,
                event_type="task_failed",
                event_data={
                    "error": error_message,
                    "failed_at": datetime.utcnow().isoformat(),
                },
            )
            
            # 推送失败事件
            self._emit_event(task_id, "task_failed", {"error": error_message})
            
            logger.error(f"[TaskRegistry] Task {task_id} failed: {error_message}")
            raise
        finally:
            # 清理运行时状态（但保留结果）
            if task_id in self._runtime_states:
                del self._runtime_states[task_id]
    
    # --------------------------------------------------------------------------
    # Task Recovery
    # --------------------------------------------------------------------------
    
    async def resume_task(
        self,
        task_id: int,
        progress_callback: Optional[Callable[[int, Dict[str, Any]], None]] = None,
    ) -> ServiceExtractionResult:
        """恢复暂停/失败的任务"""
        task = self.task_dao.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        if task.status not in ["paused", "failed"]:
            raise ValueError(f"Task {task_id} cannot be resumed (status: {task.status})")
        
        # 恢复任务
        return await self.execute_task(task_id, progress_callback)
    
    def get_recoverable_tasks(self, edition_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取可恢复的任务列表"""
        return self.checkpoint_manager.get_recoverable_tasks(edition_id)
    
    def get_task_status(self, task_id: int) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.task_dao.get_by_id(task_id)
        if not task:
            return None
        
        # 获取检查点信息
        checkpoint = None
        try:
            cp_result = self.checkpoint_manager.db.execute(
                "SELECT * FROM outline_extraction_checkpoints WHERE task_id = :task_id",
                {"task_id": task_id}
            ).first()
            
            if cp_result:
                checkpoint = {
                    "phase": cp_result.phase,
                    "progress_percent": cp_result.progress_percent,
                    "total_batches": cp_result.total_batches,
                    "completed_batches": cp_result.completed_batches,
                    "failed_batches": cp_result.failed_batches,
                    "current_batch": cp_result.current_batch,
                    "total_nodes": cp_result.total_nodes,
                    "total_turning_points": cp_result.total_turning_points,
                }
        except Exception as e:
            logger.error(f"[TaskRegistry] Failed to get checkpoint: {e}")
        
        return {
            "task_id": task.id,
            "status": task.status,
            "progress": task.progress,
            "current_phase": task.current_phase,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "checkpoint": checkpoint,
        }
    
    # --------------------------------------------------------------------------
    # Event Handling
    # --------------------------------------------------------------------------
    
    def register_event_callback(
        self,
        callback: Callable[[int, str, Dict[str, Any]], None]
    ):
        """注册事件回调"""
        self._event_callbacks.append(callback)
    
    def unregister_event_callback(
        self,
        callback: Callable[[int, str, Dict[str, Any]], None]
    ):
        """注销事件回调"""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)
    
    def _emit_event(self, task_id: int, event_type: str, data: Dict[str, Any]):
        """推送事件"""
        for callback in self._event_callbacks:
            try:
                callback(task_id, event_type, data)
            except Exception as e:
                logger.error(f"[TaskRegistry] Event callback error: {e}")
    
    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------
    
    def _node_to_dict(self, node) -> Dict[str, Any]:
        """转换节点为字典"""
        return {
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


# ============================================================================
# Global Registry
# ============================================================================

_task_registry: Optional[OutlineTaskRegistry] = None


def get_outline_task_registry(db: Session) -> OutlineTaskRegistry:
    """获取全局任务注册表"""
    return OutlineTaskRegistry(db)


async def restore_tasks_on_startup(db: Session):
    """服务器启动时恢复未完成的任务"""
    registry = get_outline_task_registry(db)
    
    # 获取所有运行中或暂停的任务
    running_tasks = registry.task_dao.list_tasks(
        status=TaskStatus.RUNNING,
        task_type="novel_analysis",
    )
    paused_tasks = registry.task_dao.list_tasks(
        status=TaskStatus.PAUSED,
        task_type="novel_analysis",
    )
    
    tasks_to_restore = running_tasks + paused_tasks
    
    for task in tasks_to_restore:
        if task.sub_type == "outline_extraction":
            logger.info(f"[Startup] Restoring task {task.id} (status: {task.status})")
            
            # 标记为暂停状态（等待用户恢复）
            registry.task_dao.update(
                task.id,
                status=TaskStatus.PAUSED,
                current_phase="paused_by_shutdown",
            )
            
            # 记录事件
            registry.event_dao.create(
                task_id=task.id,
                event_type="task_paused",
                event_data={
                    "reason": "server_shutdown",
                    "previous_status": task.status,
                },
            )
    
    logger.info(f"[Startup] Restored {len(tasks_to_restore)} tasks to paused state")
