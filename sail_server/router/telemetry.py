# -*- coding: utf-8 -*-
# @file telemetry.py
# @brief Telemetry, AI Trace & System Profile Router (/api/v1/telemetry)
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""SailZen 埋点、AI 全链路 Trace 与系统 Profile 路由。"""

from litestar import Router
from litestar.di import Provide

from sail_server.controller.telemetry import TelemetryController
from sail_server.db import get_db_dependency

router = Router(
    path="/telemetry",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[TelemetryController],
)
