# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Router Package
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------

from .analysis import analysis_router
from .finance import router as finance_router
from .health import router as health_router
from .history import router as history_router
from .necessity import router as necessity_router
from .project import router as project_router
from .text import router as text_router
from .unified_agent import unified_agent_router

__all__ = [
    "analysis_router",
    "finance_router",
    "health_router",
    "history_router",
    "necessity_router",
    "project_router",
    "text_router",
    "unified_agent_router",
]
