# -*- coding: utf-8 -*-
# @file outline_extraction_unified.py
# @brief Outline Extraction Controller with Unified Agent Integration
# @author sailing-innocent
# @date 2026-03-01
# @version 3.0
# ---------------------------------

"""
大纲提取控制器（Unified Agent 集成版本）

提供 API：
- 创建提取任务（使用 Unified Agent 系统）
- 获取任务进度（包含检查点信息）
- 恢复暂停/失败的任务
- 获取可恢复任务列表
- WebSocket 实时进度推送
"""

from __future__ import annotations
from litestar import Controller, post, get
from litestar.exceptions import NotFoundException, ClientException
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import logging

from pydantic import BaseModel, Field

from sail_server.application.dto.analysis import TextRangeSelection, OutlineExtractionConfig
from sail_server.service.outline_task_registry import (
    get_outline_task_registry,
    restore_tasks_on_startup,
)
from sail_server.service.persistent_checkpoint import get_persistent_checkpoint_manager
from sail_server.model.unified_agent import UnifiedTaskDAO
from sail_server.db import get_db_session

logger = logging.getLogger(__name__)

# ============================================================================
# V2 Support - 配置开关
# ============================================================================

# 设置为 True 启用 V2，False 使用 V1
USE_V2_EXTRACTOR = True

if USE_V2_EXTRACTOR:
    try:
        from sail_server.service.outline_extraction_v2 import (
            ExtractedOutlineNodeV2,
            MergedOutlineResult,
            NodePositionAnchor,
        )
        from sail_server.model.analysis.outline_v2 import OutlineBatchSaver
        logger.info("[OutlineExtractionUnified] V2 support loaded successfully")
    except ImportError as e:
        logger.warning(f"[OutlineExtractionUnified] Failed to load V2 support: {e}")
        USE_V2_EXTRACTOR = False


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateOutlineExtractionRequest(BaseModel):
    """创建大纲提取请求"""
    edition_id: int = Field(description="版本ID")
    range_selection: TextRangeSelection = Field(description="文本范围选择")
    config: OutlineExtractionConfig = Field(description="提取配置")
    work_title: str = Field(default="", description="作品标题")
    known_characters: Optional[List[str]] = Field(default=None, description="已知人物列表")


class OutlineExtractionTaskResponse(BaseModel):
    """大纲提取任务响应"""
    task_id: int = Field(description="任务ID")
    status: str = Field(description="状态")
    message: str = Field(description="消息")
    created_at: str = Field(description="创建时间")


class OutlineExtractionProgressResponse(BaseModel):
    """大纲提取进度响应"""
    task_id: int = Field(description="任务ID")
    status: str = Field(description="状态")
    progress: int = Field(description="进度百分比")
    current_phase: Optional[str] = Field(default=None, description="当前阶段")
    message: Optional[str] = Field(default=None, description="消息")
    checkpoint: Optional[Dict[str, Any]] = Field(default=None, description="检查点信息")


class CheckpointInfo(BaseModel):
    """检查点信息"""
    phase: str
    progress_percent: int
    total_batches: int
    completed_batches: List[int]
    failed_batches: List[int]
    current_batch: int
    total_nodes: int
    total_turning_points: int


class RecoverableTaskResponse(BaseModel):
    """可恢复任务响应"""
    task_id: str
    edition_id: Optional[int]
    status: str
    progress: int
    current_phase: Optional[str]
    checkpoint: Optional[CheckpointInfo]
    is_recoverable: bool
    recovery_suggestion: str
    created_at: Optional[str]


class ResumeTaskRequest(BaseModel):
    """恢复任务请求"""
    task_id: int = Field(description="任务ID")


class ResumeTaskResponse(BaseModel):
    """恢复任务响应"""
    success: bool
    task_id: int
    message: str
    resumed_from_batch: int = 0
    total_batches: int = 0


class DismissTaskResponse(BaseModel):
    """关闭任务响应"""
    success: bool
    task_id: int
    message: str


# ============================================================================
# Controller
# ============================================================================

class OutlineExtractionUnifiedController(Controller):
    """大纲提取控制器（Unified Agent 集成）
    
    提供大纲提取相关的 API，集成 Unified Agent 系统：
    - 数据库持久化的任务状态
    - 检查点恢复机制
    - WebSocket 实时进度
    """
    path = "/outline-extraction-v2"
    
    @post("/")
    async def create_extraction_task(
        self,
        data: CreateOutlineExtractionRequest,
    ) -> OutlineExtractionTaskResponse:
        """创建大纲提取任务
        
        Request Body:
            - edition_id: 版本ID
            - range_selection: 文本范围选择
            - config: 提取配置
            - work_title: 作品标题（可选）
            - known_characters: 已知人物列表（可选）
        """
        with get_db_session() as db:
            try:
                registry = get_outline_task_registry(db)
                
                task_id = registry.create_task(
                    edition_id=data.edition_id,
                    range_selection=data.range_selection,
                    config=data.config,
                    work_title=data.work_title,
                    known_characters=data.known_characters,
                )
                
                # 异步执行提取任务
                asyncio.create_task(
                    self._run_extraction_task(task_id)
                )
                
                return OutlineExtractionTaskResponse(
                    task_id=task_id,
                    status="pending",
                    message="大纲提取任务已创建",
                    created_at=datetime.now().isoformat(),
                )
                
            except Exception as e:
                logger.error(f"[Controller] Failed to create task: {e}")
                raise ClientException(detail=f"创建任务失败: {str(e)}")
    
    async def _run_extraction_task(self, task_id: int):
        """后台执行提取任务"""
        with get_db_session() as db:
            registry = get_outline_task_registry(db)
            
            try:
                await registry.execute_task(task_id)
            except Exception as e:
                logger.error(f"[Controller] Task {task_id} execution failed: {e}")
    
    @get("/task/{task_id:int}")
    async def get_task_status(
        self,
        task_id: int,
    ) -> OutlineExtractionProgressResponse:
        """获取任务状态和进度"""
        with get_db_session() as db:
            registry = get_outline_task_registry(db)
            status = registry.get_task_status(task_id)
            
            if not status:
                raise NotFoundException(detail=f"Task {task_id} not found")
            
            return OutlineExtractionProgressResponse(
                task_id=task_id,
                status=status["status"],
                progress=status["progress"],
                current_phase=status.get("current_phase"),
                message=status.get("error_message"),
                checkpoint=status.get("checkpoint"),
            )
    
    @get("/tasks/edition/{edition_id:int}")
    async def get_edition_tasks(
        self,
        edition_id: int,
    ) -> List[RecoverableTaskResponse]:
        """获取指定版本的所有可恢复任务"""
        with get_db_session() as db:
            registry = get_outline_task_registry(db)
            tasks = registry.get_recoverable_tasks(edition_id)
            
            return [
                RecoverableTaskResponse(
                    task_id=task["task_id"],
                    edition_id=task.get("edition_id"),
                    status=task["status"],
                    progress=task["progress"],
                    current_phase=task.get("current_phase"),
                    checkpoint=CheckpointInfo(
                        phase=task["checkpoint"]["phase"],
                        progress_percent=task["checkpoint"]["progress_percent"],
                        total_batches=task["checkpoint"]["total_batches"],
                        completed_batches=task["checkpoint"]["completed_batches"],
                        failed_batches=task["checkpoint"]["failed_batches"],
                        current_batch=task["checkpoint"]["current_batch"],
                        total_nodes=task["checkpoint"]["total_nodes"],
                        total_turning_points=task["checkpoint"]["total_turning_points"],
                    ) if task.get("checkpoint") else None,
                    is_recoverable=task.get("is_recoverable", False),
                    recovery_suggestion=task.get("recovery_suggestion", ""),
                    created_at=task.get("created_at"),
                )
                for task in tasks
            ]
    
    @post("/task/{task_id:int}/resume")
    async def resume_task(
        self,
        task_id: int,
    ) -> ResumeTaskResponse:
        """恢复暂停或失败的任务"""
        with get_db_session() as db:
            registry = get_outline_task_registry(db)
            
            # 获取当前任务状态
            status = registry.get_task_status(task_id)
            if not status:
                raise NotFoundException(detail=f"Task {task_id} not found")
            
            if status["status"] not in ["paused", "failed"]:
                return ResumeTaskResponse(
                    success=False,
                    task_id=task_id,
                    message=f"任务状态为 {status['status']}，无法恢复",
                )
            
            # 异步恢复任务
            asyncio.create_task(
                self._run_extraction_task(task_id)
            )
            
            checkpoint = status.get("checkpoint", {})
            
            return ResumeTaskResponse(
                success=True,
                task_id=task_id,
                message="任务已恢复",
                resumed_from_batch=checkpoint.get("current_batch", 0),
                total_batches=checkpoint.get("total_batches", 0),
            )
    
    @post("/task/{task_id:int}/cancel")
    async def cancel_task(
        self,
        task_id: int,
    ) -> Dict[str, Any]:
        """取消运行中的任务"""
        with get_db_session() as db:
            task_dao = UnifiedTaskDAO(db)
            task = task_dao.get_by_id(task_id)
            
            if not task:
                raise NotFoundException(detail=f"Task {task_id} not found")
            
            if task.status != "running":
                return {
                    "success": False,
                    "task_id": task_id,
                    "message": f"任务状态为 {task.status}，无法取消",
                }
            
            # 标记为取消
            task_dao.mark_as_cancelled(task_id)
            
            return {
                "success": True,
                "task_id": task_id,
                "message": "任务已取消",
            }
    
    @post("/task/{task_id:int}/dismiss")
    async def dismiss_task(
        self,
        task_id: int,
    ) -> DismissTaskResponse:
        """关闭并清理任务"""
        with get_db_session() as db:
            registry = get_outline_task_registry(db)
            
            # 删除检查点
            checkpoint_manager = get_persistent_checkpoint_manager(db)
            checkpoint_manager.delete_checkpoint(str(task_id))
            
            # 删除任务（可选：根据需求决定是否保留历史记录）
            # task_dao.delete(task_id)
            
            return DismissTaskResponse(
                success=True,
                task_id=task_id,
                message="任务已关闭并清理",
            )
    
    @get("/task/{task_id:int}/result")
    async def get_task_result(
        self,
        task_id: int,
    ) -> Dict[str, Any]:
        """获取任务结果"""
        with get_db_session() as db:
            task_dao = UnifiedTaskDAO(db)
            task = task_dao.get_by_id(task_id)
            
            if not task:
                raise NotFoundException(detail=f"Task {task_id} not found")
            
            if task.status != "completed":
                return {
                    "success": False,
                    "task_id": task_id,
                    "message": f"任务状态为 {task.status}，尚未完成",
                }
            
            result_data = task.result_data or {}
            extraction_result = result_data.get("extraction_result", {})
            
            return {
                "success": True,
                "task_id": task_id,
                "result": extraction_result,
                "message": "大纲提取完成",
            }
    
    @post("/task/{task_id:int}/save")
    async def save_extraction_result(
        self,
        task_id: int,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """将提取结果保存到数据库
        
        Args:
            task_id: 任务ID
            data: 可选参数，包含要保存的节点ID列表（node_ids）
                  如果提供，只保存指定的节点；否则保存所有节点
        
        Returns:
            保存结果统计
        """
        with get_db_session() as db:
            task_dao = UnifiedTaskDAO(db)
            task = task_dao.get_by_id(task_id)
            
            if not task:
                raise NotFoundException(detail=f"Task {task_id} not found")
            
            if task.status != "completed":
                raise ClientException(detail=f"任务状态为 {task.status}，尚未完成，无法保存")
            
            # 获取任务结果
            result_data = task.result_data or {}
            extraction_result = result_data.get("extraction_result", {})
            
            if not extraction_result:
                raise ClientException(detail="任务没有提取结果")
            
            # 获取要保存的节点列表
            nodes = extraction_result.get("nodes", [])
            if not nodes:
                raise ClientException(detail="没有可保存的节点")
            
            # 如果指定了节点ID列表，只保存这些节点
            node_ids_to_save = data.get("node_ids") if data else None
            if node_ids_to_save:
                nodes = [n for n in nodes if n.get("id") in node_ids_to_save]
            
            # 获取任务配置
            config_data = task.config or {}
            extraction_config = config_data.get("extraction_config", {})
            
            if USE_V2_EXTRACTOR:
                # ===== V2 保存流程 =====
                logger.info(f"[SaveResult] Task {task_id}: Using V2 batch saver")
                
                # 重建 V2 结果对象
                v2_nodes = []
                for i, node_dict in enumerate(nodes):
                    # 构建位置锚点
                    position_anchor = None
                    if node_dict.get("position_anchor"):
                        pa = node_dict["position_anchor"]
                        position_anchor = NodePositionAnchor(
                            chapter_index=pa.get("chapter_index", 0),
                            in_chapter_order=pa.get("in_chapter_order", i),
                            char_offset=pa.get("char_offset"),
                            chapter_title=pa.get("chapter_title"),
                        )
                    else:
                        # 如果没有位置锚点，使用索引作为降级
                        position_anchor = NodePositionAnchor(
                            chapter_index=i,
                            in_chapter_order=0,
                        )
                    
                    v2_nodes.append(ExtractedOutlineNodeV2(
                        id=node_dict.get("id", f"node_{i}"),
                        node_type=node_dict.get("node_type", "scene"),
                        title=node_dict.get("title", ""),
                        summary=node_dict.get("summary", ""),
                        significance=node_dict.get("significance", "normal"),
                        parent_id=node_dict.get("parent_id"),
                        characters=node_dict.get("characters", []),
                        evidence_list=node_dict.get("evidence_list", []),
                        position_anchor=position_anchor,
                        depth=node_dict.get("depth", 0),
                        batch_index=node_dict.get("batch_index", 0),
                    ))
                
                # 构建 V2 结果
                v2_result = MergedOutlineResult(
                    nodes=v2_nodes,
                    turning_points=extraction_result.get("turning_points", []),
                    metadata=extraction_result.get("metadata", {}),
                )
                
                # 使用 V2 批量保存
                saver = OutlineBatchSaver(db)
                save_result = saver.save(
                    edition_id=task.edition_id,
                    result=v2_result,
                    outline_type=extraction_config.get("outline_type", "main"),
                    granularity=extraction_config.get("granularity", "scene"),
                )
                
            else:
                # ===== V1 保存流程（向后兼容）=====
                logger.info(f"[SaveResult] Task {task_id}: Using V1 extractor")
                
                from sail_server.service.outline_extractor import OutlineExtractor, ServiceExtractionResult, ExtractedTurningPoint
                from sail_server.application.dto.analysis import ExtractedOutlineNode, OutlineEvidence
                
                # 重建 ServiceExtractionResult
                extracted_nodes = []
                for node_dict in nodes:
                    evidence_list = []
                    for ev in node_dict.get("evidence_list", []):
                        evidence_list.append(OutlineEvidence(
                            text=ev.get("text", ""),
                            chapter_title=ev.get("chapter_title", ""),
                            start_fragment=ev.get("start_fragment", ""),
                            end_fragment=ev.get("end_fragment", ""),
                        ))
                    
                    extracted_nodes.append(ExtractedOutlineNode(
                        id=node_dict.get("id", ""),
                        node_type=node_dict.get("node_type", "scene"),
                        title=node_dict.get("title", ""),
                        summary=node_dict.get("summary", ""),
                        significance=node_dict.get("significance", "normal"),
                        sort_index=node_dict.get("sort_index", 0),
                        parent_id=node_dict.get("parent_id"),
                        characters=node_dict.get("characters", []),
                        evidence_list=evidence_list,
                    ))
                
                turning_points = []
                for tp_dict in extraction_result.get("turning_points", []):
                    turning_points.append(ExtractedTurningPoint(
                        node_id=tp_dict.get("node_id", ""),
                        turning_point_type=tp_dict.get("turning_point_type", ""),
                        description=tp_dict.get("description", ""),
                    ))
                
                result = ServiceExtractionResult(
                    nodes=extracted_nodes,
                    turning_points=turning_points,
                    metadata=extraction_result.get("metadata", {}),
                )
                
                # 创建配置对象
                from sail_server.application.dto.analysis import OutlineExtractionConfig as ExtractionConfig
                config = ExtractionConfig(
                    granularity=extraction_config.get("granularity", "scene"),
                    outline_type=extraction_config.get("outline_type", "main"),
                    extract_turning_points=extraction_config.get("extract_turning_points", True),
                    extract_characters=extraction_config.get("extract_characters", True),
                    max_nodes=extraction_config.get("max_nodes", 50),
                    temperature=extraction_config.get("temperature", 0.3),
                    llm_provider=extraction_config.get("llm_provider"),
                    llm_model=extraction_config.get("llm_model"),
                    prompt_template_id=extraction_config.get("prompt_template_id", "outline_extraction_v2"),
                )
                
                # 保存到数据库
                extractor = OutlineExtractor(db)
                save_result = extractor.save_to_database(
                    edition_id=task.edition_id,
                    result=result,
                    config=config,
                )
            
            logger.info(f"[SaveResult] Task {task_id}: saved {save_result['nodes_created']} nodes to outline {save_result['outline_id']}")
            
            return {
                "success": True,
                "task_id": task_id,
                "message": "大纲已保存到数据库",
                "outline_id": save_result["outline_id"],
                "nodes_created": save_result["nodes_created"],
                "events_created": save_result["events_created"],
            }


# ============================================================================
# Startup Recovery
# ============================================================================

async def restore_outline_tasks_on_startup():
    """服务器启动时恢复大纲提取任务"""
    with get_db_session() as db:
        await restore_tasks_on_startup(db)


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "OutlineExtractionUnifiedController",
    "restore_outline_tasks_on_startup",
]
