# -*- coding: utf-8 -*-
# @file logging_middleware.py
# @brief Request/Response Logging Middleware
# @author sailing-innocent
# @date 2026-03-02
# @version 1.0
# ---------------------------------

import time
from typing import Any

from litestar.types import ASGIApp, Scope, Receive, Send

from sail_server.utils.logging_config import get_logger

logger = get_logger("api")


def logging_middleware_factory(app: ASGIApp) -> ASGIApp:
    """创建日志中间件的工厂函数"""

    async def logging_middleware(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "UNKNOWN")

        start_time = time.time()
        response_status = 200

        async def wrapped_send(message: Any) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message.get("status", 200)
            await send(message)

        try:
            await app(scope, receive, wrapped_send)
        except Exception as e:
            logger.error(f"Request failed: {method} {path} - {e}")
            raise
        finally:
            duration = (time.time() - start_time) * 1000
            logger.info(f"{method} {path} - {response_status} - {duration:.2f}ms")

    return logging_middleware
