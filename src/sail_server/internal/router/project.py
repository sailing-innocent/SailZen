# -*- coding: utf-8 -*-
# @file life.py
# @brief Life Router
# @author sailing-innocent
# @date 2025-08-24
# @version 1.0
# ---------------------------------

from litestar import Router
from litestar.di import Provide
from internal.controller.project import ProjectController, MissionController
from internal.db import get_db_dependency


router = Router(
    path="/project",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        ProjectController,
        MissionController,
    ],
)
