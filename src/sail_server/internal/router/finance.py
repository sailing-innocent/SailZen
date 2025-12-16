# -*- coding: utf-8 -*-
# @file finance.py
# @brief Finance Router
# @author sailing-innocent
# @date 2025-05-22
# @version 1.0
# ---------------------------------

from litestar import Router
from litestar.di import Provide
from internal.controller.finance import AccountController, TransactionController
from internal.db import get_db_dependency


router = Router(
    path="/finance",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        AccountController,
        TransactionController,
    ],
)
