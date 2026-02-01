# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Novel Analysis Router
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------

from litestar import Router
from sail_server.controller.analysis import (
    CharacterController,
    RelationController,
    SettingController,
    SettingRelationController,
    CharacterSettingLinkController,
    OutlineController,
    EvidenceController,
    AnalysisTaskController,
)
from sail_server.controller.analysis_llm import (
    TaskExecutionController,
    PromptTemplateController,
    PromptExportController,
    LLMConfigController,
)

analysis_router = Router(
    path="/analysis",
    route_handlers=[
        CharacterController,
        RelationController,
        SettingController,
        SettingRelationController,
        CharacterSettingLinkController,
        OutlineController,
        EvidenceController,
        AnalysisTaskController,
        # LLM 辅助分析
        TaskExecutionController,
        PromptTemplateController,
        PromptExportController,
        LLMConfigController,
    ],
    tags=["Analysis"],
)
