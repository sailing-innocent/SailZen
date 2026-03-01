# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Analysis Controller
# @author sailing-innocent
# @date 2025-02-28
# @version 1.0
# ---------------------------------

from __future__ import annotations
from litestar.dto import DataclassDTO
from litestar.dto.config import DTOConfig
from litestar import Controller, post, get, delete, Request
from litestar.exceptions import NotFoundException, ClientException

from sail_server.data.analysis import (
    TextRangeSelection,
    TextRangePreview,
    TextRangeContent,
    RangeSelectionMode,
    EvidenceCreateRequest,
    EvidenceUpdateRequest,
    EvidenceListResponse,
    TextEvidence,
)
from sail_server.service.range_selector import TextRangeParser, create_range_selection

from sqlalchemy.orm import Session
from typing import Generator, List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid


# ============================================================================
# DTOs
# ============================================================================

class TextRangeSelectionDTO(DataclassDTO[TextRangeSelection]):
    """文本范围选择 DTO"""
    pass


class TextRangePreviewDTO(DataclassDTO[TextRangePreview]):
    """文本范围预览 DTO"""
    pass


class TextRangeContentDTO(DataclassDTO[TextRangeContent]):
    """文本范围内容 DTO"""
    pass


# ============================================================================
# Response Models
# ============================================================================

@dataclass
class EvidenceResponse:
    """证据响应"""
    id: str
    edition_id: int
    node_id: int
    evidence_type: str
    content: str
    selected_text: str
    start_offset: int
    end_offset: int
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    context: Optional[str] = None
    created_at: str = ""
    updated_at: Optional[str] = None
    message: str = "操作成功"


@dataclass
class AnalysisStatsResponse:
    """分析统计响应"""
    edition_id: int
    tasks: Dict[str, int]  # pending, running, completed, failed, cancelled
    evidence: Dict[str, int]  # character, setting, outline_node, relation
    last_updated: Optional[str] = None


# ============================================================================
# Range Controller
# ============================================================================

class TextRangeController(Controller):
    """文本范围控制器"""
    path = "/range"
    
    @post("/preview", dto=TextRangeSelectionDTO, return_dto=TextRangePreviewDTO)
    async def preview_range(
        self,
        data: TextRangeSelection,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> TextRangePreview:
        """预览文本范围
        
        返回选定范围的统计信息，包括章节数、字数、预估 token 数等。
        
        Request Body:
            - edition_id: 版本ID
            - mode: 选择模式 (single_chapter, chapter_range, multi_chapter, full_edition, current_to_end, custom_range)
            - chapter_index: 单章选择的章节索引
            - start_index: 范围选择的起始索引
            - end_index: 范围选择的结束索引
            - chapter_indices: 多章选择的索引列表
            - node_ids: 自定义范围的节点ID列表
        """
        db = next(router_dependency)
        parser = TextRangeParser(db)
        
        result = parser.preview(data)
        request.logger.info(
            f"Preview range for edition {data.edition_id}, mode {data.mode}, "
            f"chapters: {result.chapter_count}, tokens: {result.estimated_tokens}"
        )
        return result
    
    @post("/content", dto=TextRangeSelectionDTO, return_dto=TextRangeContentDTO)
    async def get_range_content(
        self,
        data: TextRangeSelection,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> TextRangeContent:
        """获取文本范围内容
        
        返回选定范围的完整文本内容。
        
        Request Body:
            同 preview_range
        """
        db = next(router_dependency)
        parser = TextRangeParser(db)
        
        result = parser.get_content(data)
        request.logger.info(
            f"Get content for edition {data.edition_id}, mode {data.mode}, "
            f"chapters: {result.chapter_count}, chars: {result.total_chars}"
        )
        return result
    
    @get("/modes")
    async def get_selection_modes(
        self,
        request: Request,
    ) -> List[Dict[str, Any]]:
        """获取所有支持的选择模式"""
        modes = [
            {
                "value": RangeSelectionMode.SINGLE_CHAPTER,
                "label": "单章选择",
                "description": "选择单个章节进行分析",
                "params": ["chapter_index"],
            },
            {
                "value": RangeSelectionMode.CHAPTER_RANGE,
                "label": "连续章节",
                "description": "选择一个连续的章节范围",
                "params": ["start_index", "end_index"],
            },
            {
                "value": RangeSelectionMode.MULTI_CHAPTER,
                "label": "多章选择",
                "description": "选择多个不连续的章节",
                "params": ["chapter_indices"],
            },
            {
                "value": RangeSelectionMode.FULL_EDITION,
                "label": "整部作品",
                "description": "选择整部作品的所有章节",
                "params": [],
            },
            {
                "value": RangeSelectionMode.CURRENT_TO_END,
                "label": "到结尾",
                "description": "从指定章节到作品结尾",
                "params": ["start_index"],
            },
            {
                "value": RangeSelectionMode.CUSTOM_RANGE,
                "label": "自定义范围",
                "description": "通过节点ID自定义选择范围",
                "params": ["node_ids"],
            },
        ]
        return modes


# ============================================================================
# Evidence Controller
# ============================================================================

class EvidenceController(Controller):
    """证据控制器"""
    path = "/evidence"
    
    _evidence_store: Dict[str, TextEvidence] = {}
    
    @post("/")
    async def create_evidence(
        self,
        data: EvidenceCreateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> EvidenceResponse:
        """创建证据
        
        Request Body:
            - edition_id: 版本ID
            - node_id: 节点ID
            - start_offset: 起始偏移
            - end_offset: 结束偏移
            - selected_text: 选中的文本
            - evidence_type: 证据类型 (character, setting, outline, relation, etc.)
            - content: 证据内容
            - target_type: 目标类型（可选）
            - target_id: 目标ID（可选）
            - context: 上下文（可选）
            - meta_data: 元数据（可选）
        """
        db = next(router_dependency)
        
        # 验证节点存在
        from sail_server.data.text import DocumentNode
        node = db.query(DocumentNode).filter(DocumentNode.id == data.node_id).first()
        if not node:
            raise NotFoundException(detail=f"Node with ID {data.node_id} not found")
        
        # 创建证据
        evidence_id = str(uuid.uuid4())
        now = datetime.now()
        evidence = TextEvidence(
            id=evidence_id,
            edition_id=data.edition_id,
            node_id=data.node_id,
            start_offset=data.start_offset,
            end_offset=data.end_offset,
            selected_text=data.selected_text,
            evidence_type=data.evidence_type,
            target_type=data.target_type,
            target_id=data.target_id,
            content=data.content,
            context=data.context,
            created_at=now,
            updated_at=None,
            meta_data=data.meta_data or {},
        )
        
        # 存储证据
        self._evidence_store[evidence_id] = evidence
        
        request.logger.info(f"Created evidence {evidence_id} for node {data.node_id}")
        
        return EvidenceResponse(
            id=evidence_id,
            edition_id=evidence.edition_id,
            node_id=evidence.node_id,
            evidence_type=evidence.evidence_type,
            content=evidence.content,
            selected_text=evidence.selected_text,
            start_offset=evidence.start_offset,
            end_offset=evidence.end_offset,
            target_type=evidence.target_type,
            target_id=evidence.target_id,
            context=evidence.context,
            created_at=evidence.created_at.isoformat(),
            updated_at=None,
            message="证据创建成功"
        )
    
    @get("/{evidence_id:str}")
    async def get_evidence(
        self,
        evidence_id: str,
        request: Request,
    ) -> EvidenceResponse:
        """获取单个证据"""
        evidence = self._evidence_store.get(evidence_id)
        
        if not evidence:
            raise NotFoundException(detail=f"Evidence with ID {evidence_id} not found")
        
        return EvidenceResponse(
            id=evidence.id,
            edition_id=evidence.edition_id,
            node_id=evidence.node_id,
            evidence_type=evidence.evidence_type,
            content=evidence.content,
            selected_text=evidence.selected_text,
            start_offset=evidence.start_offset,
            end_offset=evidence.end_offset,
            target_type=evidence.target_type,
            target_id=evidence.target_id,
            context=evidence.context,
            created_at=evidence.created_at.isoformat() if evidence.created_at else "",
            updated_at=evidence.updated_at.isoformat() if evidence.updated_at else None,
        )
    
    @post("/{evidence_id:str}")
    async def update_evidence(
        self,
        evidence_id: str,
        data: EvidenceUpdateRequest,
        request: Request,
    ) -> EvidenceResponse:
        """更新证据
        
        Request Body:
            - content: 证据内容（可选）
            - evidence_type: 证据类型（可选）
            - target_type: 目标类型（可选）
            - target_id: 目标ID（可选）
            - context: 上下文（可选）
            - meta_data: 元数据（可选）
        """
        evidence = self._evidence_store.get(evidence_id)
        if not evidence:
            raise NotFoundException(detail=f"Evidence with ID {evidence_id} not found")
        
        # 更新字段
        if data.content is not None:
            evidence.content = data.content
        if data.evidence_type is not None:
            evidence.evidence_type = data.evidence_type
        if data.target_type is not None:
            evidence.target_type = data.target_type
        if data.target_id is not None:
            evidence.target_id = data.target_id
        if data.context is not None:
            evidence.context = data.context
        if data.meta_data is not None:
            evidence.meta_data = data.meta_data
        
        evidence.updated_at = datetime.now()
        
        request.logger.info(f"Updated evidence {evidence_id}")
        
        return EvidenceResponse(
            id=evidence.id,
            edition_id=evidence.edition_id,
            node_id=evidence.node_id,
            evidence_type=evidence.evidence_type,
            content=evidence.content,
            selected_text=evidence.selected_text,
            start_offset=evidence.start_offset,
            end_offset=evidence.end_offset,
            target_type=evidence.target_type,
            target_id=evidence.target_id,
            context=evidence.context,
            created_at=evidence.created_at.isoformat() if evidence.created_at else "",
            updated_at=evidence.updated_at.isoformat() if evidence.updated_at else None,
            message="证据更新成功"
        )
    
    @get("/chapter/{node_id:int}")
    async def get_chapter_evidence(
        self,
        node_id: int,
        request: Request,
        evidence_type: Optional[str] = None,
    ) -> List[EvidenceResponse]:
        """获取指定章节的所有证据
        
        Args:
            node_id: 节点ID（章节ID）
            evidence_type: 证据类型过滤（可选）
        """
        evidences = [
            ev for ev in self._evidence_store.values()
            if ev.node_id == node_id
            and (evidence_type is None or ev.evidence_type == evidence_type)
        ]
        
        return [
            EvidenceResponse(
                id=ev.id,
                edition_id=ev.edition_id,
                node_id=ev.node_id,
                evidence_type=ev.evidence_type,
                content=ev.content,
                selected_text=ev.selected_text,
                start_offset=ev.start_offset,
                end_offset=ev.end_offset,
                target_type=ev.target_type,
                target_id=ev.target_id,
                context=ev.context,
                created_at=ev.created_at.isoformat() if ev.created_at else "",
                updated_at=ev.updated_at.isoformat() if ev.updated_at else None,
            )
            for ev in sorted(evidences, key=lambda x: (x.start_offset, x.created_at or datetime.min))
        ]
    
    @get("/target/{target_type:str}/{target_id:str}")
    async def get_target_evidence(
        self,
        target_type: str,
        target_id: str,
        request: Request,
    ) -> List[EvidenceResponse]:
        """获取指定目标的所有证据
        
        Args:
            target_type: 目标类型 (character, setting, outline_node, etc.)
            target_id: 目标ID
        """
        evidences = [
            ev for ev in self._evidence_store.values()
            if ev.target_type == target_type and ev.target_id == target_id
        ]
        
        return [
            EvidenceResponse(
                id=ev.id,
                edition_id=ev.edition_id,
                node_id=ev.node_id,
                evidence_type=ev.evidence_type,
                content=ev.content,
                selected_text=ev.selected_text,
                start_offset=ev.start_offset,
                end_offset=ev.end_offset,
                target_type=ev.target_type,
                target_id=ev.target_id,
                context=ev.context,
                created_at=ev.created_at.isoformat() if ev.created_at else "",
                updated_at=ev.updated_at.isoformat() if ev.updated_at else None,
            )
            for ev in sorted(evidences, key=lambda x: x.created_at or datetime.min, reverse=True)
        ]
    
    @delete("/{evidence_id:str}", status_code=200)
    async def delete_evidence(
        self,
        evidence_id: str,
        request: Request,
    ) -> EvidenceResponse:
        """删除证据"""
        evidence = self._evidence_store.pop(evidence_id, None)
        if not evidence:
            raise NotFoundException(detail=f"Evidence with ID {evidence_id} not found")
        
        request.logger.info(f"Deleted evidence {evidence_id}")
        
        return EvidenceResponse(
            id=evidence.id,
            edition_id=evidence.edition_id,
            node_id=evidence.node_id,
            evidence_type=evidence.evidence_type,
            content=evidence.content,
            selected_text=evidence.selected_text,
            start_offset=evidence.start_offset,
            end_offset=evidence.end_offset,
            target_type=evidence.target_type,
            target_id=evidence.target_id,
            context=evidence.context,
            created_at=evidence.created_at.isoformat() if evidence.created_at else "",
            updated_at=evidence.updated_at.isoformat() if evidence.updated_at else None,
            message="证据删除成功"
        )


# ============================================================================
# Stats Controller
# ============================================================================

class AnalysisStatsController(Controller):
    """分析统计控制器"""
    path = "/stats"
    
    @get("/{edition_id:int}")
    async def get_stats(
        self,
        edition_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> AnalysisStatsResponse:
        """获取版本的统计分析数据"""
        db = next(router_dependency)
        
        # 验证版本存在
        from sail_server.data.text import Edition
        edition = db.query(Edition).filter(Edition.id == edition_id).first()
        if not edition:
            raise NotFoundException(detail=f"Edition with ID {edition_id} not found")
        
        # 从证据存储中统计（使用类变量直接访问）
        all_evidence = list(EvidenceController._evidence_store.values())
        edition_evidence = [ev for ev in all_evidence if ev.edition_id == edition_id]
        
        # 统计证据类型
        evidence_stats = {
            "character": len([ev for ev in edition_evidence if ev.evidence_type == "character"]),
            "setting": len([ev for ev in edition_evidence if ev.evidence_type == "setting"]),
            "outline_node": len([ev for ev in edition_evidence if ev.evidence_type == "outline"]),
            "relation": len([ev for ev in edition_evidence if ev.evidence_type == "relation"]),
        }
        
        # TODO: 从任务存储中统计（当任务系统实现后）
        task_stats = {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        
        return AnalysisStatsResponse(
            edition_id=edition_id,
            tasks=task_stats,
            evidence=evidence_stats,
            last_updated=datetime.now().isoformat(),
        )


# ============================================================================
# Task Controller (Stub)
# ============================================================================

class TaskController(Controller):
    """任务控制器（桩实现）"""
    path = "/task"
    
    # 内存存储（临时实现）
    _tasks: Dict[int, Dict] = {}
    _task_counter: int = 0
    
    @post("/")
    async def create_task(
        self,
        data: Dict[str, Any],
        request: Request,
    ) -> Dict[str, Any]:
        """创建分析任务"""
        TaskController._task_counter += 1
        task_id = TaskController._task_counter
        
        task = {
            "id": task_id,
            "edition_id": data.get("edition_id"),
            "task_type": data.get("task_type"),
            "status": "pending",
            "target_scope": data.get("target_scope", "full"),
            "target_node_ids": data.get("target_node_ids", []),
            "parameters": data.get("parameters", {}),
            "created_at": datetime.now().isoformat(),
            "result_count": 0,
        }
        TaskController._tasks[task_id] = task
        request.logger.info(f"Created task {task_id}")
        return task
    
    @get("/")
    async def list_tasks(
        self,
        edition_id: Optional[int] = None,
        status: Optional[str] = None,
        request: Request = None,
    ) -> List[Dict[str, Any]]:
        """获取任务列表"""
        tasks = list(TaskController._tasks.values())
        
        if edition_id:
            tasks = [t for t in tasks if t.get("edition_id") == edition_id]
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        
        return tasks
    
    @get("/{task_id:int}")
    async def get_task(
        self,
        task_id: int,
        request: Request,
    ) -> Dict[str, Any]:
        """获取任务详情"""
        task = TaskController._tasks.get(task_id)
        if not task:
            raise NotFoundException(detail=f"Task with ID {task_id} not found")
        return task
    
    @post("/{task_id:int}/cancel")
    async def cancel_task(
        self,
        task_id: int,
        request: Request,
    ) -> Dict[str, Any]:
        """取消任务"""
        task = TaskController._tasks.get(task_id)
        if not task:
            raise NotFoundException(detail=f"Task with ID {task_id} not found")
        
        task["status"] = "cancelled"
        return {"success": True, "message": f"Task {task_id} cancelled"}
    
    @delete("/{task_id:int}", status_code=200)
    async def delete_task(
        self,
        task_id: int,
        request: Request,
    ) -> Dict[str, Any]:
        """删除任务"""
        if task_id not in TaskController._tasks:
            raise NotFoundException(detail=f"Task with ID {task_id} not found")
        
        del TaskController._tasks[task_id]
        return {"success": True, "message": f"Task {task_id} deleted"}
    
    @post("/{task_id:int}/plan")
    async def create_task_plan(
        self,
        task_id: int,
        data: Dict[str, Any],
        request: Request,
    ) -> Dict[str, Any]:
        """创建任务执行计划"""
        task = TaskController._tasks.get(task_id)
        if not task:
            raise NotFoundException(detail=f"Task with ID {task_id} not found")
        
        # 模拟执行计划
        plan = {
            "chunks": [
                {"index": 0, "node_ids": [1, 2, 3], "estimated_tokens": 1500},
                {"index": 1, "node_ids": [4, 5, 6], "estimated_tokens": 2000},
            ],
            "total_estimated_tokens": 3500,
            "estimated_cost_usd": 0.05,
            "prompt_template_id": "default_analysis",
        }
        return {"success": True, "plan": plan}
    
    @post("/{task_id:int}/execute")
    async def execute_task(
        self,
        task_id: int,
        data: Dict[str, Any],
        request: Request,
    ) -> Dict[str, Any]:
        """执行任务"""
        task = TaskController._tasks.get(task_id)
        if not task:
            raise NotFoundException(detail=f"Task with ID {task_id} not found")
        
        task["status"] = "running"
        return {"success": True}
    
    @post("/{task_id:int}/apply")
    async def apply_results(
        self,
        task_id: int,
        request: Request,
    ) -> Dict[str, Any]:
        """应用任务结果"""
        task = TaskController._tasks.get(task_id)
        if not task:
            raise NotFoundException(detail=f"Task with ID {task_id} not found")
        
        return {"applied": 5, "failed": 0}


# ============================================================================
# Progress Controller
# ============================================================================

class ProgressController(Controller):
    """进度控制器"""
    path = "/progress"
    
    @get("/{task_id:int}")
    async def get_progress(
        self,
        task_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> Dict[str, Any]:
        """获取任务进度"""
        from sail_server.model.unified_scheduler_ws import get_unified_scheduler_with_ws
        from sail_server.model.unified_agent import UnifiedTaskDAO
        
        scheduler = get_unified_scheduler_with_ws()
        progress = scheduler.get_task_progress(task_id)
        
        if not progress:
            # 从数据库获取任务状态
            db = next(router_dependency)
            dao = UnifiedTaskDAO(db)
            task = dao.get_by_id(task_id)
            
            if not task:
                raise NotFoundException(detail=f"Task with ID {task_id} not found")
            
            # 转换状态
            status_map = {
                "pending": "pending",
                "scheduled": "pending",
                "running": "running",
                "paused": "pending",
                "completed": "completed",
                "failed": "failed",
                "cancelled": "cancelled",
            }
            
            return {
                "success": True,
                "progress": {
                    "task_id": str(task_id),
                    "status": status_map.get(task.status, "unknown"),
                    "current_step": "unknown",
                    "total_chunks": 0,
                    "completed_chunks": 0,
                    "current_chunk_info": None,
                }
            }
        
        # 转换进度格式
        status_map = {
            "pending": "pending",
            "scheduled": "pending",
            "running": "running",
            "paused": "pending",
            "completed": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
        }
        
        return {
            "success": True,
            "progress": {
                "task_id": str(progress.task_id),
                "status": status_map.get(progress.status, "unknown"),
                "current_step": progress.current_phase or "unknown",
                "total_chunks": progress.total_steps or 0,
                "completed_chunks": progress.current_step or 0,
                "current_chunk_info": None,
            }
        }


# ============================================================================
# Result Controller (Stub)
# ============================================================================

class ResultController(Controller):
    """结果控制器（桩实现）"""
    path = "/result"
    
    @get("/{task_id:int}")
    async def get_results(
        self,
        task_id: int,
        request: Request,
    ) -> List[Dict[str, Any]]:
        """获取任务结果"""
        # 模拟结果数据
        return [
            {
                "id": 1,
                "task_id": str(task_id),
                "result_type": "character",
                "result_data": {"name": "主角", "role": "protagonist"},
                "confidence": 0.95,
                "review_status": "pending",
            },
            {
                "id": 2,
                "task_id": str(task_id),
                "result_type": "setting",
                "result_data": {"name": "主城", "type": "location"},
                "confidence": 0.88,
                "review_status": "approved",
            },
        ]
    
    @post("/{result_id:int}/verify")
    async def verify_result(
        self,
        result_id: int,
        data: Dict[str, Any],
        request: Request,
    ) -> Dict[str, Any]:
        """审核结果"""
        status = data.get("status", "pending")
        return {"success": True, "message": f"Result {result_id} status updated to {status}"}


# ============================================================================
# LLM Provider Controller
# ============================================================================

class LLMProviderController(Controller):
    """LLM 提供商控制器 - 返回系统支持的 LLM Provider 列表"""
    path = "/llm-providers"
    
    @get("/")
    async def get_providers(
        self,
        request: Request,
    ) -> Dict[str, Any]:
        """获取 LLM 提供商列表
        
        返回系统中所有可用的 LLM Provider 及其配置信息，
        供前端选择使用。
        
        Returns:
            {
                "success": true,
                "providers": [
                    {
                        "id": "moonshot",
                        "name": "Moonshot (Kimi)",
                        "display_name": "Moonshot (Kimi)",
                        "description": "Moonshot Kimi 系列模型，支持长文本",
                        "models": ["kimi-k2.5", "kimi-k2", "kimi-k1.5"],
                        "default_model": "kimi-k2.5",
                        "requires_api_key": true
                    },
                    ...
                ],
                "default_provider": "moonshot",
                "fallback_chain": ["deepseek", "openai", "anthropic", "google"],
                "task_fallback_chains": {...}
            }
        """
        from sail_server.utils.llm.available_providers import (
            AVAILABLE_PROVIDERS,
            DEFAULT_PROVIDER_PRIORITY,
            FALLBACK_PROVIDER_CHAIN,
            TASK_FALLBACK_CHAINS,
        )
        
        # 构建 Provider 列表
        providers = []
        for name, info in AVAILABLE_PROVIDERS.items():
            providers.append({
                "id": name,
                "name": info.display_name,
                "display_name": info.display_name,
                "description": info.description,
                "models": info.available_models,
                "default_model": info.default_model,
                "requires_api_key": info.requires_api_key,
            })
        
        return {
            "success": True,
            "providers": providers,
            "default_provider": DEFAULT_PROVIDER_PRIORITY[0] if DEFAULT_PROVIDER_PRIORITY else None,
            "default_priority": DEFAULT_PROVIDER_PRIORITY,
            "fallback_chain": FALLBACK_PROVIDER_CHAIN,
            "task_fallback_chains": TASK_FALLBACK_CHAINS,
        }
