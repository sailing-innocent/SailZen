# -*- coding: utf-8 -*-
# @file feishu.py
# @brief Feishu integration router
# @author sailing-innocent
# @date 2026-03-21
# @version 1.0
# ---------------------------------
"""Feishu Bot integration routes."""

from litestar import Router
from sail_server.feishu_gateway import FeishuWebhookHandler


def create_feishu_router() -> Router:
    """Create Feishu integration router."""
    return Router(
        path="/feishu",
        route_handlers=[FeishuWebhookHandler],
        tags=["Feishu Integration"],
    )
