# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Analysis Data Models Re-export Module
# @author sailing-innocent
# @date 2025-02-28
# @version 3.0
# ---------------------------------

"""
分析模块数据模型聚合入口

此文件仅作为聚合入口，提供向后兼容的导入。
- 所有 ORM 模型位于 sail_server.infrastructure.orm.analysis
- 所有 Pydantic DTOs 位于 sail_server.application.dto.analysis
"""

# ============================================================================
# ORM Models (从 infrastructure 层导入)
# ============================================================================

from sail_server.infrastructure.orm.analysis import (
    # Outline
    Outline, OutlineNode, OutlineEvent,
    # Character
    Character, CharacterAlias, CharacterAttribute, CharacterArc, CharacterRelation,
    # Setting
    Setting, SettingAttribute, SettingRelation, CharacterSettingLink,
    # Evidence
    TextEvidence,
    # Task
    AnalysisTask, AnalysisResult,
)

# ============================================================================
# Pydantic DTOs (从 application 层导入)
# ============================================================================

from sail_server.application.dto.analysis import (
    # Enums
    RangeSelectionMode,
    AnalysisTaskType,
    AnalysisTaskStatus,
    
    # Text Range DTOs
    TextRangeSelection,
    TextRangePreview,
    
    # Analysis Task DTOs
    AnalysisTaskBase,
    AnalysisTaskCreateRequest,
    AnalysisTaskResponse,
    AnalysisTaskListResponse,
    
    # Character DTOs
    CharacterBase,
    CharacterCreateRequest,
    CharacterResponse,
    CharacterListResponse,
    
    # Outline DTOs
    OutlineBase,
    OutlineCreateRequest,
    OutlineResponse,
    OutlineListResponse,
    OutlineNodeBase,
    OutlineNodeCreateRequest,
    OutlineNodeResponse,
    
    # Evidence DTOs
    TextEvidenceBase,
    TextEvidenceCreateRequest,
    TextEvidenceResponse,
    TextEvidenceListResponse,
)

# ============================================================================
# Backward Compatibility Aliases
# ============================================================================

# 保留旧的 DTO 名称别名（用于向后兼容）
TextEvidenceDTO = TextEvidenceResponse

# ============================================================================
# __all__ 导出列表
# ============================================================================

__all__ = [
    # ORM Models
    "Outline", "OutlineNode", "OutlineEvent",
    "Character", "CharacterAlias", "CharacterAttribute", "CharacterArc", "CharacterRelation",
    "Setting", "SettingAttribute", "SettingRelation", "CharacterSettingLink",
    "TextEvidence",
    "AnalysisTask", "AnalysisResult",
    
    # Enums
    "RangeSelectionMode",
    "AnalysisTaskType",
    "AnalysisTaskStatus",
    
    # Pydantic DTOs
    "TextRangeSelection",
    "TextRangePreview",
    "AnalysisTaskBase",
    "AnalysisTaskCreateRequest",
    "AnalysisTaskResponse",
    "AnalysisTaskListResponse",
    "CharacterBase",
    "CharacterCreateRequest",
    "CharacterResponse",
    "CharacterListResponse",
    "OutlineBase",
    "OutlineCreateRequest",
    "OutlineResponse",
    "OutlineListResponse",
    "OutlineNodeBase",
    "OutlineNodeCreateRequest",
    "OutlineNodeResponse",
    "TextEvidenceBase",
    "TextEvidenceCreateRequest",
    "TextEvidenceResponse",
    "TextEvidenceListResponse",
    
    # Backward Compatibility Aliases
    "TextEvidenceDTO",
]
