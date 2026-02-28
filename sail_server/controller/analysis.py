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
    created_at: str
    message: str = "操作成功"


@dataclass
class AnalysisStatsResponse:
    """分析统计响应"""
    edition_id: int
    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    failed_tasks: int
    total_evidence: int
    character_count: int
    setting_count: int
    outline_node_count: int


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
    
    # 内存存储（临时实现，后续应使用数据库）
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
            - evidence_type: 证据类型
            - content: 证据内容
            - target_type: 目标类型（可选）
            - target_id: 目标ID（可选）
            - context: 上下文（可选）
        """
        db = next(router_dependency)
        
        # 验证节点存在
        from sail_server.data.text import DocumentNode
        node = db.query(DocumentNode).filter(DocumentNode.id == data.node_id).first()
        if not node:
            raise NotFoundException(detail=f"Node with ID {data.node_id} not found")
        
        # 创建证据
        evidence_id = str(uuid.uuid4())
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
            created_at=datetime.now(),
            meta_data=data.meta_data,
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
            created_at=evidence.created_at.isoformat(),
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
            created_at=evidence.created_at.isoformat(),
        )
    
    @get("/chapter/{node_id:int}")
    async def get_chapter_evidence(
        self,
        node_id: int,
        request: Request,
        evidence_type: Optional[str] = None,
    ) -> List[EvidenceResponse]:
        """获取指定章节的所有证据"""
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
                created_at=ev.created_at.isoformat(),
            )
            for ev in sorted(evidences, key=lambda x: x.created_at, reverse=True)
        ]
    
    @get("/target/{target_type:str}/{target_id:str}")
    async def get_target_evidence(
        self,
        target_type: str,
        target_id: str,
        request: Request,
    ) -> List[EvidenceResponse]:
        """获取指定目标的所有证据"""
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
                created_at=ev.created_at.isoformat(),
            )
            for ev in sorted(evidences, key=lambda x: x.created_at, reverse=True)
        ]
    
    @delete("/{evidence_id:str}")
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
            created_at=evidence.created_at.isoformat(),
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
        
        # TODO: 实现真实的统计逻辑
        # 这里返回模拟数据
        
        return AnalysisStatsResponse(
            edition_id=edition_id,
            total_tasks=0,
            completed_tasks=0,
            pending_tasks=0,
            failed_tasks=0,
            total_evidence=0,
            character_count=0,
            setting_count=0,
            outline_node_count=0,
        )
