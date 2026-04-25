# -*- coding: utf-8 -*-
# @file outline_extraction_v3.py
# @brief Outline Extraction V3 Controller
# @author sailing-innocent
# @date 2026-04-17
# @version 1.0
# ---------------------------------

"""
大纲提取 V3 控制器

提供 API：
- 创建 V3 提取任务（动态策略选择 + 迭代精炼）
- 获取任务进度
- 恢复暂停/失败的任务
- 获取可恢复任务列表
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
from sail_server.service.outline_extractor_v3 import get_outline_task_registry_v3
from sail_server.service.persistent_checkpoint import get_persistent_checkpoint_manager
from sail_server.model.unified_agent import UnifiedTaskDAO
from sail_server.db import get_db_session

logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateOutlineExtractionV3Request(BaseModel):
    """创建 V3 大纲提取请求"""
    edition_id: int = Field(description="版本ID")
    range_selection: TextRangeSelection = Field(description="文本范围选择")
    config: OutlineExtractionConfig = Field(description="提取配置")
    work_title: str = Field(default="", description="作品标题")
    known_characters: Optional[List[str]] = Field(default=None, description="已知人物列表")
    strategy_override: Optional[str] = Field(default=None, description="策略覆盖（direct/standard/hierarchical/progressive）")


class OutlineExtractionV3TaskResponse(BaseModel):
    """V3 任务响应"""
    task_id: int = Field(description="任务ID")
    status: str = Field(description="状态")
    strategy: str = Field(description="自动选择的策略")
    message: str = Field(description="消息")
    created_at: str = Field(description="创建时间")


class OutlineExtractionV3ProgressResponse(BaseModel):
    """V3 进度响应"""
    task_id: int = Field(description="任务ID")
    status: str = Field(description="状态")
    progress: int = Field(description="进度百分比")
    current_phase: Optional[str] = Field(default=None, description="当前阶段")
    strategy: Optional[str] = Field(default=None, description="使用的策略")
    message: Optional[str] = Field(default=None, description="消息")
    checkpoint: Optional[Dict[str, Any]] = Field(default=None, description="检查点信息")
    refinement_info: Optional[Dict[str, Any]] = Field(default=None, description="精炼信息")


class StrategyInfoResponse(BaseModel):
    """策略信息响应"""
    chapter_count: int = Field(description="章节数")
    recommended_strategy: str = Field(description="推荐策略")
    strategy_description: str = Field(description="策略说明")
    enable_refinement: bool = Field(description="是否启用精炼")
    estimated_time_minutes: int = Field(description="预估耗时（分钟）")
    estimated_cost_cny: float = Field(description="预估成本（元）")


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

class OutlineExtractionV3Controller(Controller):
    """大纲提取 V3 控制器
    
    提供基于动态策略选择和迭代精炼的大纲提取 API。
    """
    path = "/outline-extraction-v3"
    
    @post("/")
    async def create_extraction_task(
        self,
        data: CreateOutlineExtractionV3Request,
    ) -> OutlineExtractionV3TaskResponse:
        """创建 V3 大纲提取任务
        
        系统会根据章节数自动选择最优策略：
        - ≤30 章: direct（单次调用）
        - 31-150 章: standard（V2 标准批次并行）
        - 151-500 章: hierarchical（标准 + 全局精炼）
        - >500 章: progressive（递进模式）
        
        Request Body:
            - edition_id: 版本ID
            - range_selection: 文本范围选择
            - config: 提取配置
            - work_title: 作品标题（可选）
            - known_characters: 已知人物列表（可选）
            - strategy_override: 手动指定策略（可选，覆盖自动选择）
        """
        with get_db_session() as db:
            try:
                registry = get_outline_task_registry_v3(db)
                
                task_id = registry.create_task(
                    edition_id=data.edition_id,
                    range_selection=data.range_selection,
                    config=data.config,
                    work_title=data.work_title,
                    known_characters=data.known_characters,
                    strategy_override=data.strategy_override,
                )
                
                # 获取自动选择的策略
                task = registry.task_dao.get_by_id(task_id)
                config_data = task.config or {}
                strategy = config_data.get("auto_selected_strategy", "unknown")
                
                # 异步执行提取任务
                asyncio.create_task(
                    self._run_extraction_task(task_id)
                )
                
                return OutlineExtractionV3TaskResponse(
                    task_id=task_id,
                    status="pending",
                    strategy=strategy,
                    message=f"V3 大纲提取任务已创建（策略: {strategy}）",
                    created_at=datetime.now().isoformat(),
                )
                
            except Exception as e:
                logger.error(f"[V3 Controller] Failed to create task: {e}")
                raise ClientException(detail=f"创建任务失败: {str(e)}")
    
    async def _run_extraction_task(self, task_id: int):
        """后台执行提取任务"""
        with get_db_session() as db:
            registry = get_outline_task_registry_v3(db)
            
            try:
                await registry.execute_task(task_id)
            except Exception as e:
                logger.error(f"[V3 Controller] Task {task_id} execution failed: {e}")
    
    @get("/strategy-preview")
    async def preview_strategy(
        self,
        edition_id: int,
        chapter_count: Optional[int] = None,
    ) -> StrategyInfoResponse:
        """预览推荐策略
        
        根据章节数预览系统会选择的策略和预估成本。
        
        Query Parameters:
            - edition_id: 版本ID
            - chapter_count: 章节数（可选，不提供则查询数据库）
        """
        with get_db_session() as db:
            if chapter_count is None:
                from sail_server.infrastructure.orm.text import DocumentNode
                chapter_count = db.query(DocumentNode).filter(
                    DocumentNode.edition_id == edition_id,
                    DocumentNode.node_type == "chapter",
                ).count()
            
            from sail_server.service.outline_extraction_v3 import StrategySelector
            
            strategy_config = StrategySelector.select(chapter_count)
            
            # 计算预估耗时和成本
            if strategy_config.strategy.value == "direct":
                estimated_time = 1
                estimated_cost = 2.0
            elif strategy_config.strategy.value == "standard":
                batches = (chapter_count // strategy_config.max_chapters_per_batch) + 1
                estimated_time = max(2, batches // strategy_config.concurrency + 1)
                estimated_cost = batches * 2.0
            elif strategy_config.strategy.value == "hierarchical":
                batches = (chapter_count // strategy_config.max_chapters_per_batch) + 1
                estimated_time = max(3, batches // strategy_config.concurrency + 2)
                estimated_cost = batches * 2.0 + 5.0  # 额外精炼成本
            else:  # progressive
                stages = (chapter_count // (strategy_config.progressive_stage_size or 200)) + 1
                estimated_time = stages * 5
                estimated_cost = stages * 15.0
            
            descriptions = {
                "direct": "直通模式：单次 LLM 调用，适合短篇作品",
                "standard": "标准模式：批次并行提取 + 位置锚点合并，适合中篇作品",
                "hierarchical": "分层模式：标准模式 + 全局精炼，适合长篇作品",
                "progressive": "递进模式：分阶段分析 + 活跃实体追踪，适合超长篇作品",
            }
            
            return StrategyInfoResponse(
                chapter_count=chapter_count,
                recommended_strategy=strategy_config.strategy.value,
                strategy_description=descriptions.get(strategy_config.strategy.value, ""),
                enable_refinement=strategy_config.enable_refinement,
                estimated_time_minutes=estimated_time,
                estimated_cost_cny=estimated_cost,
            )
    
    @get("/task/{task_id:int}")
    async def get_task_status(
        self,
        task_id: int,
    ) -> OutlineExtractionV3ProgressResponse:
        """获取任务状态和进度"""
        with get_db_session() as db:
            registry = get_outline_task_registry_v3(db)
            task = registry.task_dao.get_by_id(task_id)
            
            if not task:
                raise NotFoundException(detail=f"Task {task_id} not found")
            
            # 获取策略信息
            config_data = task.config or {}
            strategy = config_data.get("auto_selected_strategy")
            
            # 获取精炼信息（如果已完成）
            refinement_info = None
            if task.status == "completed" and task.result_data:
                extraction_result = task.result_data.get("extraction_result", {})
                metadata = extraction_result.get("metadata", {})
                refinement_info = metadata.get("refinement")
            
            return OutlineExtractionV3ProgressResponse(
                task_id=task_id,
                status=task.status,
                progress=task.progress,
                current_phase=task.current_phase,
                strategy=strategy,
                message=task.error_message,
                checkpoint=task.result_data.get("checkpoint") if task.result_data else None,
                refinement_info=refinement_info,
            )
    
    @get("/tasks/edition/{edition_id:int}")
    async def get_edition_tasks(
        self,
        edition_id: int,
    ) -> List[Dict[str, Any]]:
        """获取指定版本的 V3 任务列表"""
        with get_db_session() as db:
            registry = get_outline_task_registry_v3(db)
            checkpoint_manager = get_persistent_checkpoint_manager(db)
            tasks = checkpoint_manager.get_recoverable_tasks(edition_id)
            
            # 过滤 V3 任务
            v3_tasks = [
                task for task in tasks
                if task.get("sub_type") == "outline_extraction_v3"
            ]
            
            return v3_tasks
    
    @post("/task/{task_id:int}/resume")
    async def resume_task(
        self,
        task_id: int,
    ) -> ResumeTaskResponse:
        """恢复暂停或失败的任务"""
        with get_db_session() as db:
            registry = get_outline_task_registry_v3(db)
            task = registry.task_dao.get_by_id(task_id)
            
            if not task:
                raise NotFoundException(detail=f"Task {task_id} not found")
            
            if task.status not in ["paused", "failed"]:
                return ResumeTaskResponse(
                    success=False,
                    task_id=task_id,
                    message=f"任务状态为 {task.status}，无法恢复",
                )
            
            # 异步恢复任务
            asyncio.create_task(
                self._run_extraction_task(task_id)
            )
            
            checkpoint = task.result_data.get("checkpoint", {}) if task.result_data else {}
            
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
            checkpoint_manager = get_persistent_checkpoint_manager(db)
            checkpoint_manager.delete_checkpoint(str(task_id))
            
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
                "strategy": result_data.get("strategy"),
                "message": "V3 大纲提取完成",
            }
    
    @post("/task/{task_id:int}/save")
    async def save_extraction_result(
        self,
        task_id: int,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """将 V3 提取结果保存到数据库
        
        复用 V2 的 OutlineBatchSaver 进行保存。
        """
        with get_db_session() as db:
            task_dao = UnifiedTaskDAO(db)
            task = task_dao.get_by_id(task_id)
            
            if not task:
                raise NotFoundException(detail=f"Task {task_id} not found")
            
            if task.status != "completed":
                raise ClientException(detail=f"任务状态为 {task.status}，尚未完成，无法保存")
            
            result_data = task.result_data or {}
            extraction_result = result_data.get("extraction_result", {})
            
            if not extraction_result:
                raise ClientException(detail="任务没有提取结果")
            
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
            
            # 复用 V2 的保存逻辑
            from sail_server.service.outline_extraction_v2 import (
                NodePositionAnchor,
                ExtractedOutlineNodeV2,
                MergedOutlineResult,
            )
            from sail_server.model.analysis.outline_v2 import OutlineBatchSaver
            
            v2_nodes = []
            for i, node_dict in enumerate(nodes):
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
            
            v2_result = MergedOutlineResult(
                nodes=v2_nodes,
                turning_points=extraction_result.get("turning_points", []),
                conflicts=extraction_result.get("conflicts", []),
                metadata=extraction_result.get("metadata", {}),
            )
            
            saver = OutlineBatchSaver(db)
            save_result = saver.save(
                edition_id=task.edition_id,
                result=v2_result,
                outline_type=extraction_config.get("outline_type", "main"),
                granularity=extraction_config.get("granularity", "scene"),
            )
            
            logger.info(f"[V3 Controller] Task {task_id}: saved {save_result['nodes_created']} nodes")
            
            return {
                "success": True,
                "task_id": task_id,
                "message": "V3 大纲已保存到数据库",
                "outline_id": save_result["outline_id"],
                "nodes_created": save_result["nodes_created"],
                "events_created": save_result.get("events_created", 0),
            }
    
    @post("/task/{task_id:int}/link-entities")
    async def link_entities(
        self,
        task_id: int,
    ) -> Dict[str, Any]:
        """将提取结果中的实体链接到 Character 表
        
        自动将提取结果中发现的实体与现有 Character 表进行关联，
        支持精确匹配、别名匹配和新建。
        """
        with get_db_session() as db:
            task_dao = UnifiedTaskDAO(db)
            task = task_dao.get_by_id(task_id)
            
            if not task:
                raise NotFoundException(detail=f"Task {task_id} not found")
            
            result_data = task.result_data or {}
            extraction_result = result_data.get("extraction_result", {})
            nodes = extraction_result.get("nodes", [])
            
            # 收集所有角色名称
            candidate_names = set()
            for node in nodes:
                for char in node.get("characters", []):
                    candidate_names.add(char.strip())
            
            if not candidate_names:
                return {
                    "success": True,
                    "task_id": task_id,
                    "message": "未检测到角色实体",
                    "stats": {},
                }
            
            # 执行实体链接
            from sail_server.service.entity_linker import EntityLinker
            
            linker = EntityLinker(db)
            link_results = linker.link_entities(
                edition_id=task.edition_id,
                candidate_names=list(candidate_names),
            )
            
            # 应用链接结果
            stats = linker.apply_links(task.edition_id, link_results)
            
            return {
                "success": True,
                "task_id": task_id,
                "message": f"实体链接完成：{stats['matched']} 匹配, {stats['new_created']} 新建, {stats['uncertain']} 待审核",
                "stats": stats,
                "links": [
                    {
                        "name": r.candidate_name,
                        "action": r.action.value,
                        "character_id": r.character_id,
                        "confidence": r.confidence,
                    }
                    for r in link_results
                ],
            }


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "OutlineExtractionV3Controller",
]
