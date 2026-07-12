# -*- coding: utf-8 -*-
# @file life.py
# @brief Life Time Management Router
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
生活时间管理路由

注册 Day 与 TimeSpan 控制器到 /api/v1/life 路径下。
"""

from litestar import Router
from litestar.di import Provide

from sail_server.controller.life import DayController, TimeSpanController
from sail_server.db import get_db_dependency


router = Router(
    path="/life",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        DayController,
        TimeSpanController,
    ],
)
