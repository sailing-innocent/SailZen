# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Analysis Router
# @author sailing-innocent
# @date 2025-02-28
# @version 1.0
# ---------------------------------

from litestar import Router
from litestar.di import Provide
from sail_server.controller.analysis import (
    TextRangeController,
    EvidenceController,
    AnalysisStatsController,
    TaskController,
    ProgressController,
    ResultController,
    LLMProviderController,
)
from sail_server.controller.outline_extraction import OutlineExtractionController
from sail_server.controller.outline import OutlineController
from sail_server.controller.character import CharacterController
from sail_server.controller.character_detection import CharacterDetectionController
from sail_server.controller.setting import SettingController
from sail_server.db import get_db_dependency


analysis_router = Router(
    path="/analysis",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        TextRangeController,
        EvidenceController,
        AnalysisStatsController,
        TaskController,
        ProgressController,
        ResultController,
        LLMProviderController,
        OutlineExtractionController,
        OutlineController,
        CharacterController,
        CharacterDetectionController,
        SettingController,
    ],
)
