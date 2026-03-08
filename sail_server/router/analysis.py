# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Analysis Router
# @author sailing-innocent
# @date 2025-02-28
# @version 1.0
# ---------------------------------

import os
import logging

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
from sail_server.controller.outline_extraction_unified import (
    OutlineExtractionUnifiedController,
)
from sail_server.controller.outline import OutlineController
from sail_server.controller.character import CharacterController
from sail_server.controller.character_detection import CharacterDetectionController
from sail_server.controller.setting import SettingController
from sail_server.controller.setting_extraction import SettingExtractionController
from sail_server.db import get_db_dependency

logger = logging.getLogger(__name__)

# Feature flag for async outline extraction
USE_ASYNC_OUTLINE_EXTRACTION = (
    os.environ.get("USE_ASYNC_OUTLINE_EXTRACTION", "false").lower() == "true"
)

if USE_ASYNC_OUTLINE_EXTRACTION:
    try:
        from sail_server.controller.async_outline_extraction_controller import (
            AsyncOutlineExtractionController,
        )

        logger.info("[AnalysisRouter] Async outline extraction controller enabled")
    except ImportError as e:
        logger.warning(
            f"[AnalysisRouter] Failed to load async outline extraction controller: {e}"
        )
        USE_ASYNC_OUTLINE_EXTRACTION = False


# Build route handlers list
_route_handlers = [
    TextRangeController,
    EvidenceController,
    AnalysisStatsController,
    TaskController,
    ProgressController,
    ResultController,
    LLMProviderController,
    OutlineExtractionController,
    OutlineExtractionUnifiedController,
    OutlineController,
    CharacterController,
    CharacterDetectionController,
    SettingController,
    SettingExtractionController,
]

# Add async outline extraction controller if enabled
if USE_ASYNC_OUTLINE_EXTRACTION:
    _route_handlers.append(AsyncOutlineExtractionController)

analysis_router = Router(
    path="/analysis",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=_route_handlers,
)
