# -*- coding: utf-8 -*-
# @file pems.py
# @brief Personal Energy Management System Router
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
个人精力管理系统(PEMS) 路由

注册 PEMS 控制器到 /api/v1/pems 路径下。
"""

from litestar import Router
from litestar.di import Provide

from sail_server.controller.pems import PEMSController
from sail_server.db import get_db_dependency


router = Router(
    path="/pems",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        PEMSController,
    ],
)
