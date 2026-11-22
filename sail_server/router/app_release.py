# -*- coding: utf-8 -*-
# @file app_release.py
# @brief Android App Release Router (/api/v1/app)
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------

from litestar import Router

from sail_server.controller.app_release import AppReleaseController

router = Router(
    path="/app",
    route_handlers=[AppReleaseController],
)
