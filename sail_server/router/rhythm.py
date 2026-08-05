# -*- coding: utf-8 -*-
# @file rhythm.py
# @brief Rhythm Router (生活/工作节奏综合优先级调节工具)
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
节奏（Rhythm）路由

注册统一事务/时间线/模板/打卡/事业/精力/策略/计划/复盘控制器到
/api/v1/rhythm 路径下。
"""

from litestar import Router
from litestar.di import Provide

from sail_server.controller.rhythm import (
    AffairController,
    CheckinController,
    EnergyController,
    PlanController,
    PolicyController,
    ReviewController,
    TemplateController,
    TimelineController,
    VentureController,
)
from sail_server.db import get_db_dependency


router = Router(
    path="/rhythm",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        AffairController,
        TimelineController,
        TemplateController,
        CheckinController,
        VentureController,
        EnergyController,
        PolicyController,
        PlanController,
        ReviewController,
    ],
)
