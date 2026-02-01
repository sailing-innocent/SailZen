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
    ],
    tags=["Analysis"],
)
