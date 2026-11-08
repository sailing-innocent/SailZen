# -*- coding: utf-8 -*-
# @file tick.py
# @brief SailTick Ticket Router
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 票据路由（/api/v1/tick）。

设计文档: doc/design/agent-system/sailtick.md §6/§7
票据存于主库 sail_tick_tickets 表，SailTick daemon 经本路由访问。
"""

import logging

from litestar import Router
from litestar.di import Provide

from sail_server.controller.tick import TicketController
from sail_server.db import get_db_dependency

logger = logging.getLogger(__name__)

router = Router(
    path="/tick",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[TicketController],
)
