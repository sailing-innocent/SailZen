# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Agent management API
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""Agent management HTTP API (optional, default port 9060)."""

from sailzen.autonomous_agent.api.routes import create_app

__all__ = ["create_app"]
