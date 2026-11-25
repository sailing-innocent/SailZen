# -*- coding: utf-8 -*-
# @file rhythm.py
# @brief Rhythm v2 Router (极简项目/事务 + AI 可视化时间线 + 占用 + 轻量打卡)
# @author sailing-innocent
# @date 2026-11-24
# @version 2.0
# ---------------------------------

"""
节奏（Rhythm v2）路由

注册精简后的 6 个核心控制器到 /api/v1/rhythm：
Dashboard / Affair / Venture / Timeline / Occupancy / Checkin
"""

from litestar import Router
from litestar.di import Provide

from sail_server.controller.rhythm import (
    AffairController,
    CheckinController,
    DashboardController,
    OccupancyController,
    TimelineController,
    VentureController,
)
from sail_server.db import get_db_dependency


router = Router(
    path="/rhythm",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        DashboardController,
        AffairController,
        VentureController,
        TimelineController,
        OccupancyController,
        CheckinController,
    ],
)
