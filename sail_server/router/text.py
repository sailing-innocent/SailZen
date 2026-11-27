# -*- coding: utf-8 -*-
# @file text.py
# @brief Text & Content 2.0 Router
# @author sailing-innocent
# @date 2026-11-26
# @version 2.0
# ---------------------------------

from litestar import Router
from litestar.di import Provide

from sail_server.controller.content_v2 import (
    AssetController,
    ImportController,
    ProgressController,
    TopicController,
    VaultContentController,
)
from sail_server.controller.text import (
    DocumentNodeController,
    EditionController,
    NoteItemController,
    WorkController,
)
from sail_server.db import get_db_dependency


router = Router(
    path="/text",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        WorkController,
        EditionController,
        DocumentNodeController,
        NoteItemController,
        ImportController,
        ProgressController,
        TopicController,
        AssetController,
        VaultContentController,
    ],
)
