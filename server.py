# -*- coding: utf-8 -*-
# @file server.py
# @brief The Long Last Server Entry
# @author sailing-innocent
# @date 2025-04-27
# @version 1.0
# ---------------------------------

import asyncio
import os
import json
import hashlib
import time
from typing import Any
from datetime import datetime

from litestar import Litestar, Router, get, Request
from litestar.response import Redirect, Response
from litestar.openapi import OpenAPIConfig
from litestar.config.cors import CORSConfig
from litestar.logging import LoggingConfig

import argparse

from sail_server.exception_handlers import exception_handlers
from litestar.static_files import create_static_files_router
from litestar.plugins.pydantic import PydanticPlugin


class SailServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.app = None
        self.router = None

        self.api_endpoint = os.environ.get("API_ENDPOINT", "/api/v1")
        self.site_dist = os.environ.get("SITE_DIST", "site_dist")
        self.page_alias = [
            "/agent",
            "/energy",
            "/health",
            "/money",
            "/project",
            "/text",
            "/analysis",
            "/necessity",
            "/file-storage",
            "/dag-pipeline",
            "/rhythm",
        ]
        self.api_router = None
        self.debug = True
        self.log_file = None
        # 天气后台更新任务（on_startup 中按 WEATHER_ENABLED 启动）
        self._weather_task: "asyncio.Task | None" = None
        # 提醒调度任务（on_startup 中按 REMINDER_ENABLED 启动）
        self._reminder_task: "asyncio.Task | None" = None

    def init(self):
        # 日志已在 main() 中初始化，直接获取 logger
        from sail_server.utils.logging_config import get_logger

        logger = get_logger("sail_server")

        @get("/health")
        async def health_check(request: Request) -> dict[str, str]:
            return {"status": "ok"}

        # Suppress Chrome DevTools probe requests (returns 404 silently)
        @get(
            "/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False
        )
        async def devtools_json() -> Response:
            return Response(content=b"", status_code=404)

        # redirect all self.page_alias to root
        route_handlers = [devtools_json]
        for alias in self.page_alias:
            # Create a closure to capture the current alias value
            def create_redirect_function(path):
                @get(path)
                async def redirect_handler(request: Request) -> Redirect:
                    return Redirect(
                        path="/",
                        query_params={**request.query_params, "path": path.lstrip("/")},
                    )

                return redirect_handler

            # Add the handler with a unique function
            route_handlers.append(create_redirect_function(alias))

        self.base_router = Router(
            path="/",
            route_handlers=[
                *route_handlers,
                create_static_files_router(
                    directories=[self.site_dist],
                    path="/",
                    html_mode=True,
                    include_in_schema=False,
                ),
            ],
        )
        from sail_server.router.health import router as health_router
        from sail_server.router.finance import router as finance_router
        from sail_server.router.project import router as project_router
        from sail_server.router.history import router as history_router
        from sail_server.router.text import router as text_router
        from sail_server.router.necessity import router as necessity_router
        from sail_server.router.file_storage import router as file_storage_router
        from sail_server.router.life import router as life_router
        from sail_server.router.reminder import router as reminder_router
        from sail_server.router.rhythm import router as rhythm_router

        self.api_router = Router(
            path=self.api_endpoint,
            route_handlers=[
                health_check,
                health_router,
                finance_router,
                project_router,
                history_router,
                text_router,
                necessity_router,
                file_storage_router,
                life_router,
                reminder_router,
                rhythm_router,
            ],
        )

        # 使用 None 作为 logging_config，避免 Litestar 覆盖我们的日志配置
        # 我们的日志配置已在 main() 中通过 setup_logging() 设置
        logging_config = None

        cors_config = CORSConfig(allow_origins=["*"], allow_methods=["*"])

        # Configure OpenAPI documentation
        openapi_config = OpenAPIConfig(
            title="Sail Server API",
            version="1.0.0",
            summary="API documentation for Sail Server",
            path="/api_docs",
        )

        # 配置全局中间件
        from litestar.middleware.base import DefineMiddleware
        from sail_server.middleware.logging_middleware import logging_middleware_factory

        middleware = [DefineMiddleware(logging_middleware_factory)]

        try:
            self.app = Litestar(
                route_handlers=[self.base_router, self.api_router],
                debug=self.debug,
                logging_config=logging_config,
                cors_config=cors_config,
                exception_handlers=exception_handlers,
                on_startup=[self.on_startup],
                on_shutdown=[self.on_shutdown],
                openapi_config=openapi_config,
                middleware=middleware,
                plugins=[PydanticPlugin(prefer_alias=True)],
            )
        except Exception as e:
            # 如果初始化失败，记录错误并重新抛出
            logger.error(f"Failed to initialize Litestar app: {e}")
            raise

    async def on_startup(self):
        from sail_server.utils.logging_config import get_logger

        logger = get_logger("sail_server")
        logger.info("Server starting up...")

        # 初始化默认财务标签（幂等）
        try:
            from sail_server.model.finance.tag import seed_default_tags_impl
            from sail_server.db import Database

            db = Database.get_instance().get_db_session()
            try:
                created = seed_default_tags_impl(db)
                if created > 0:
                    logger.info(f"[Startup] Seeded {created} default finance tags")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"[Startup] Failed to seed finance tags: {e}")

        # 初始化时间系统（幂等）
        try:
            from sail_server.model.life import init_time_system_impl
            from sail_server.db import Database

            db = Database.get_instance().get_db_session()
            try:
                result = init_time_system_impl(db)
                logger.info(
                    f"[Startup] Time system initialized: "
                    f"{result['total_days']} days, {result['total_spans']} spans"
                )
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"[Startup] Failed to initialize time system: {e}")

        # 启动天气后台更新循环（失败仅告警，不影响服务启动）
        try:
            if os.environ.get("WEATHER_ENABLED", "true").lower() == "true":
                from sail_server.db import Database
                from sail_server.model.weather import weather_update_loop

                self._weather_task = asyncio.create_task(
                    weather_update_loop(Database.get_instance().get_db_session)
                )
                logger.info("[Startup] Weather update loop started")
        except Exception as e:
            logger.warning(f"[Startup] Failed to start weather update loop: {e}")

        # 启动提醒调度循环（失败仅告警，不影响服务启动）
        try:
            if os.environ.get("REMINDER_ENABLED", "true").lower() == "true":
                from sail_server.db import Database
                from sail_server.model.reminder_scheduler import reminder_scan_loop

                self._reminder_task = asyncio.create_task(
                    reminder_scan_loop(Database.get_instance().get_db_session)
                )
                logger.info("[Startup] Reminder scan loop started")
        except Exception as e:
            logger.warning(f"[Startup] Failed to start reminder scan loop: {e}")

    async def on_shutdown(self):
        from sail_server.utils.logging_config import get_logger

        logger = get_logger("sail_server")
        logger.info("Server shutting down...")

        # 取消天气后台更新任务
        if self._weather_task is not None:
            import contextlib

            self._weather_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._weather_task
            self._weather_task = None

        # 取消提醒调度任务
        if self._reminder_task is not None:
            import contextlib

            self._reminder_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reminder_task
            self._reminder_task = None

    def run(self):
        from sail_server.utils.logging_config import get_logger

        logger = get_logger("sail_server")
        logger.info(f"Server running on {self.host}:{self.port}")
        if not self.app:
            logger.error("App Not Initialized")
            return
        import uvicorn

        # 使用 uvicorn 运行服务器，保留 access_log 以便记录请求
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_config=None,  # 使用我们已配置的日志系统
            access_log=True,  # 启用访问日志
        )


def main():
    # 先初始化日志配置，再获取 logger
    from sail_server.utils.logging_config import setup_logging, get_logger

    setup_logging()
    logger = get_logger("sail_server")

    try:
        host = os.environ.get("SERVER_HOST", "0.0.0.0")
        port = int(os.environ.get("SERVER_PORT", 1974))
        logger.info(f"Starting server at {host}:{port}")
        server = SailServer(host, port)
        server.init()
        server.run()
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        raise
    finally:
        logger.info("Server stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sail Server")
    parser.add_argument("--dev", action="store_true", help="Run in development mode")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    args = parser.parse_args()

    from sail.utils import read_env

    if args.dev:
        read_env("dev")
    elif args.debug:
        read_env("debug")
    else:
        read_env("prod")

    main()
