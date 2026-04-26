# -*- coding: utf-8 -*-
# @file text.py
# @brief Text Content Router
# @author sailing-innocent
# @date 2025-01-29
# @version 1.0
# ---------------------------------

from litestar import Router
from litestar.di import Provide
from sail_server.controller.text import (
    WorkController,
    EditionController,
    DocumentNodeController,
)
from sail_server.db import get_db_dependency


router = Router(
    path="/text",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        WorkController,
        EditionController,
        DocumentNodeController
    ],
)
