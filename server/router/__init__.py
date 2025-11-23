# -*- coding: utf-8 -*-
# @file __init__.py
# @brief API router package
# @author sailing-innocent
# @date 2025-04-21

from server.router.works import router as works_router
from server.router.nodes import router as nodes_router
from server.router.entities import router as entities_router
from server.router.relations import router as relations_router
from server.router.extract import router as extract_router
from server.router.sessions import router as sessions_router
from server.router.changesets import router as changesets_router
from server.router.reviews import router as reviews_router
from server.router.events import router as events_router
from server.router.collections import router as collections_router
from server.router.brainstorm import router as brainstorm_router

__all__ = [
    "works_router",
    "nodes_router",
    "entities_router",
    "relations_router",
    "extract_router",
    "sessions_router",
    "changesets_router",
    "reviews_router",
    "events_router",
    "collections_router",
    "brainstorm_router",
]
