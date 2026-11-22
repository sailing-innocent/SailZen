# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Router Package
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------

from .app_release import router as app_release_router
from .file_storage import router as file_storage_router
from .finance import router as finance_router
from .health import router as health_router
from .history import router as history_router
from .life import router as life_router
from .necessity import router as necessity_router
from .text import router as text_router

__all__ = [
    "analysis_router",
    "app_release_router",
    "file_storage_router",
    "finance_router",
    "health_router",
    "history_router",
    "life_router",
    "necessity_router",
    "text_router",
]
