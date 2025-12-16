# -*- coding: utf-8 -*-
# @file history.py
# @brief History Events Router
# @author sailing-innocent
# @date 2025-10-12
# @version 1.0
# ---------------------------------

from litestar import Router
from litestar.di import Provide
from internal.controller.history import HistoryEventController
from internal.db import get_db_dependency


router = Router(
    path="/history",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        HistoryEventController,
    ],
)

