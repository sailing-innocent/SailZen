# -*- coding: utf-8 -*-
# @file blog.py
# @brief Blog Router
# @author sailing-innocent
# @date 2026-05-05
# @version 1.0
# ---------------------------------

from litestar import Router

from sail_server.controller.blog import BlogController

router = Router(
    path="/blog",
    route_handlers=[BlogController],
)
