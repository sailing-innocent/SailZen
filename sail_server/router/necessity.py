# -*- coding: utf-8 -*-
# @file necessity.py
# @brief Necessity Router
# @author sailing-innocent
# @date 2026-02-01
# @version 1.0
# ---------------------------------

from litestar import Router
from litestar.di import Provide
from sail_server.controller.necessity import (
    ResidenceController,
    ContainerController,
    CategoryController,
    ItemController,
    InventoryController,
    JourneyController,
)
from sail_server.db import get_db_dependency


router = Router(
    path="/necessity",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        ResidenceController,
        ContainerController,
        CategoryController,
        ItemController,
        InventoryController,
        JourneyController,
    ],
)
