# -*- coding: utf-8 -*-
# @file dag_pipeline.py
# @brief DAG Pipeline Router
# @author sailing-innocent
# @date 2026-04-13
# @version 1.0
# ---------------------------------

from litestar import Router
from litestar.di import Provide
from sail_server.controller.dag_pipeline import (
    PipelineDefController,
    PipelineRunController,
    PipelineSSEController,
)
from sail_server.db import get_db_dependency

router = Router(
    path="/pipeline",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        PipelineDefController,
        PipelineRunController,
        PipelineSSEController,
    ],
)
