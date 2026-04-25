# -*- coding: utf-8 -*-
# @file outline_extractor_v3.py
# @brief Outline Extractor V3 - Service Entry Point with Unified Agent Integration
# @author sailing-innocent
# @date 2026-04-17
# @version 1.0
# ---------------------------------

"""
大纲提取服务 V3 入口

集成 Unified Agent 任务系统，提供：
- V3 引擎的任务封装
- 进度追踪和事件推送
- 结果持久化
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime

from sqlalchemy.orm import Session

from sail_server.model.unified_agent import (
    UnifiedTaskDAO,
    UnifiedStepDAO,
    UnifiedEventDAO,
)
from sail_server.service.outline_extraction_v3 import (
    OutlineExtractionEngineV3,
    StrategySelector,
)
from sail_server.service.persistent_checkpoint import get_persistent_checkpoint_manager
from sail_server.application.dto.analysis import (
    TextRangeSelection,
    OutlineExtractionConfig,
)
from sail_server.service.outline_extraction_v2 import MergedOutlineResult

logger = logging.getLogger(__name__)


# ============================================================================
# V3 Task Registry
# ============================================================================

class OutlineTaskRegistryV3:
    """大纲提取 V3 任务注册表
    
    复用 Unified Agent 任务系统，提供 V3 特有的任务管理。
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.task_dao = UnifiedTaskDAO(db)
        self.step_dao = UnifiedStepDAO(db)
        self.event_dao = UnifiedEventDAO(db)
        self.checkpoint_manager = get_persistent_checkpoint_manager(db)
    
    def create_task(
        self,
        edition_id: int,
        range_selection: TextRangeSelection,
        config: OutlineExtractionConfig,
        work_title: str = "",
        known_characters: Optional[List[str]] = None,
        strategy_override: Optional[str] = None,
    ) -> int:
        """创建 V3 大纲提取任务"""
        from sail_server.application.dto.unified_agent import UnifiedAgentTaskCreateRequest
        from sail.llm.available_providers import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL
        
        # 自动检测策略
        # 先粗略估计章节数（从 range_selection）
        # 实际章节数在执行时确定，这里用配置中的预估
        estimated_chapters = self._estimate_chapter_count(range_selection)
        strategy_config = StrategySelector.select(estimated_chapters, strategy_override)
        
        create_request = UnifiedAgentTaskCreateRequest(
            task_type="novel_analysis",
            sub_type="outline_extraction_v3",
            edition_id=edition_id,
            target_scope="full" if range_selection.mode.value == "full_edition" else "range",
            llm_provider=config.llm_provider or DEFAULT_LLM_PROVIDER,
            llm_model=config.llm_model or DEFAULT_LLM_MODEL,
            prompt_template_id=config.prompt_template_id or "outline_extraction_v3",
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
                "strategy_override": strategy_override,
                "auto_selected_strategy": strategy_config.strategy.value,
                "enable_refinement": strategy_config.enable_refinement,
            },
        )
        
        task = self.task_dao.create(create_request)
        
        # 创建检查点
        self.checkpoint_manager.create_checkpoint(
            task_id=str(task.id),
            edition_id=edition_id,
            config=create_request.config["extraction_config"],
            range_selection=create_request.config["range_selection"],
            work_title=work_title,
            known_characters=known_characters,
            total_batches=0,
        )
        
        # 记录事件
        self.event_dao.create(
            task_id=task.id,
            event_type="task_created",
            event_data={
                "edition_id": edition_id,
                "strategy": strategy_config.strategy.value,
                "estimated_chapters": estimated_chapters,
            },
        )
        
        logger.info(f"[TaskRegistryV3] Created V3 task {task.id} with strategy {strategy_config.strategy.value}")
        return task.id
    
    async def execute_task(
        self,
        task_id: int,
        progress_callback: Optional[Callable[[int, Dict[str, Any]], None]] = None,
    ) -> MergedOutlineResult:
        """执行 V3 大纲提取任务"""
        task = self.task_dao.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # 更新状态
        self.task_dao.mark_as_running(task_id)
        self.event_dao.create(
            task_id=task_id,
            event_type="task_started",
            event_data={"started_at": datetime.utcnow().isoformat()},
        )
        
        # 解析配置
        config_data = task.config or {}
        extraction_config_data = config_data.get("extraction_config", {})
        range_selection_data = config_data.get("range_selection", {})
        work_title = config_data.get("work_title", "")
        known_characters = config_data.get("known_characters", [])
        strategy_override = config_data.get("strategy_override")
        
        from sail_server.application.dto.analysis import OutlineExtractionConfig
        
        config = OutlineExtractionConfig(
            granularity=extraction_config_data.get("granularity", "scene"),
            outline_type=extraction_config_data.get("outline_type", "main"),
            extract_turning_points=extraction_config_data.get("extract_turning_points", True),
            extract_characters=extraction_config_data.get("extract_characters", True),
            max_nodes=extraction_config_data.get("max_nodes", 50),
            temperature=extraction_config_data.get("temperature", 0.3),
            llm_provider=task.llm_provider,
            llm_model=task.llm_model,
            prompt_template_id=task.prompt_template_id or "outline_extraction_v3",
        )
        
        range_selection = TextRangeSelection(**range_selection_data)
        
        # 创建 V3 引擎
        engine = OutlineExtractionEngineV3(self.db)
        
        # 记录步骤
        step_id = self._record_step(
            task_id=task_id,
            step_number=1,
            step_type="data_processing",
            title="初始化提取引擎",
            content=f"策略: {config_data.get('auto_selected_strategy', 'auto')}",
        )
        
        # 定义进度回调
        async def on_progress(progress_info: Dict[str, Any]):
            progress = progress_info.get("progress_percent", 0)
            current_phase = progress_info.get("current_step", "")
            message = progress_info.get("message", "")
            
            self.task_dao.update_progress(
                task_id=task_id,
                progress=progress,
                current_phase=current_phase,
            )
            
            self.event_dao.create(
                task_id=task_id,
                event_type="progress_update",
                event_data=progress_info,
            )
            
            if progress_callback:
                progress_callback(task_id, progress_info)
        
        try:
            # 执行提取
            result = await engine.extract(
                edition_id=task.edition_id,
                range_selection=range_selection,
                config=config,
                work_title=work_title,
                known_characters=known_characters,
                progress_callback=on_progress,
                strategy_override=strategy_override,
            )
            
            # 构建结果数据
            result_data = {
                "extraction_result": {
                    "nodes": [self._node_to_dict(n) for n in result.nodes],
                    "turning_points": result.turning_points,
                    "conflicts": result.conflicts,
                    "metadata": result.metadata,
                },
                "strategy": config_data.get("auto_selected_strategy"),
                "checkpoint": {
                    "phase": "completed",
                    "progress_percent": 100,
                    "total_nodes": len(result.nodes),
                    "total_turning_points": len(result.turning_points),
                },
            }
            
            self.task_dao.mark_as_completed(task_id, result_data)
            
            self.event_dao.create(
                task_id=task_id,
                event_type="task_completed",
                event_data={
                    "completed_at": datetime.utcnow().isoformat(),
                    "total_nodes": len(result.nodes),
                    "total_turning_points": len(result.turning_points),
                    "strategy": config_data.get("auto_selected_strategy"),
                },
            )
            
            logger.info(f"[TaskRegistryV3] Task {task_id} completed: {len(result.nodes)} nodes")
            return result
            
        except Exception as e:
            error_message = str(e)
            self.task_dao.mark_as_failed(task_id, error_message)
            
            self.event_dao.create(
                task_id=task_id,
                event_type="task_failed",
                event_data={
                    "error": error_message,
                    "failed_at": datetime.utcnow().isoformat(),
                },
            )
            
            logger.error(f"[TaskRegistryV3] Task {task_id} failed: {error_message}")
            raise
    
    def _estimate_chapter_count(self, range_selection: TextRangeSelection) -> int:
        """估算章节数"""
        if range_selection.mode.value == "full_edition":
            # 查询数据库获取实际章节数
            from sail_server.infrastructure.orm.text import DocumentNode
            count = self.db.query(DocumentNode).filter(
                DocumentNode.edition_id == range_selection.edition_id,
                DocumentNode.node_type == "chapter",
            ).count()
            return count or 50  # 默认值
        
        if range_selection.mode.value == "chapter_range":
            start = range_selection.start_index or 0
            end = range_selection.end_index or start
            return end - start + 1
        
        if range_selection.mode.value == "multi_chapter":
            return len(range_selection.chapter_indices)
        
        return 50  # 默认估计
    
    def _record_step(
        self,
        task_id: int,
        step_number: int,
        step_type: str,
        title: str,
        content: str = "",
    ) -> int:
        """记录步骤"""
        from sail_server.application.dto.unified_agent import UnifiedAgentStepCreateRequest
        
        step_request = UnifiedAgentStepCreateRequest(
            task_id=task_id,
            step_number=step_number,
            step_type=step_type,
            title=title,
            content=content,
        )
        
        step = self.step_dao.create(step_request)
        return step.id
    
    def _node_to_dict(self, node) -> Dict[str, Any]:
        """转换节点为字典"""
        anchor = node.get_effective_anchor()
        return {
            "id": node.id,
            "node_type": node.node_type,
            "title": node.title,
            "summary": node.summary,
            "significance": node.significance,
            "parent_id": node.parent_id,
            "depth": node.depth,
            "characters": node.characters,
            "evidence_list": node.evidence_list,
            "position_anchor": {
                "chapter_index": anchor.chapter_index,
                "in_chapter_order": anchor.in_chapter_order,
                "char_offset": anchor.char_offset,
                "chapter_title": anchor.chapter_title,
            },
            "batch_index": node.batch_index,
        }


# ============================================================================
# Global Registry Factory
# ============================================================================

_registry_v3_cache: Dict[int, OutlineTaskRegistryV3] = {}


def get_outline_task_registry_v3(db: Session) -> OutlineTaskRegistryV3:
    """获取 V3 任务注册表"""
    return OutlineTaskRegistryV3(db)


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "OutlineTaskRegistryV3",
    "get_outline_task_registry_v3",
]
