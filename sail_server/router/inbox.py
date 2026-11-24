# -*- coding: utf-8 -*-
# @file inbox.py
# @brief Unified UserInbox Router (/api/v1/inbox)
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""统一用户收件箱路由（/api/v1/inbox）。"""

from litestar import Router
from litestar.di import Provide

from sail_server.controller.inbox import InboxController
from sail_server.db import get_db_dependency

router = Router(
    path="/inbox",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[InboxController],
)
