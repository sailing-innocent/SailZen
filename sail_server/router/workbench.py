# -*- coding: utf-8 -*-
# @file workbench.py
# @brief SailZen Workbench Router (/api/v1/workbench)
# @author sailing-innocent
# @date 2026-11-27
# @version 1.0
# ---------------------------------

from litestar import Router
from litestar.di import Provide

from sail_server.controller.workbench import (
    WorkbenchController,
    WorkbenchReleaseController,
)
from sail_server.db import get_db_dependency

router = Router(
    path="/workbench",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[WorkbenchController, WorkbenchReleaseController],
)
