# -*- coding: utf-8 -*-
# @file health.py
# @brief Health Router
# @author sailing-innocent
# @date 2025-05-22
# @version 1.0
# ---------------------------------

from litestar import Router
from litestar.di import Provide
from sail_server.controller.health import WeightController, ExerciseController
from sail_server.db import get_db_dependency


router = Router(
    path="/health",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        WeightController,
        ExerciseController,
    ],
)
