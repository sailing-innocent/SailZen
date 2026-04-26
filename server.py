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
            "/health",
            "/money",
            "/project",
            "/text",
            "/analysis",
            "/necessity",
            "/file-storage",
            "/dag-pipeline",
        ]
        self.api_router = None
        self.debug = True
        self.log_file = None

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
        from sail_server.router.analysis import analysis_router
        from sail_server.router.unified_agent import unified_agent_router
        from sail_server.router.file_storage import router as file_storage_router
        from sail_server.router.dag_pipeline import router as dag_pipeline_router
        from sail_server.controller.outline_extraction_unified import (
            OutlineExtractionUnifiedController,
        )

        # 自动注册 Agent
        from sail_server.agent import auto_register_agents

        auto_register_agents()

        # 修复数据库序列（仅 PostgreSQL）
        from sail_server.db import Database

        if Database.get_instance().backend != "sqlite":
            try:
                from sail_server.db import get_db_session
                from sail_server.utils.db_utils import fix_all_sequences

                with get_db_session() as db:
                    fix_results = fix_all_sequences(db)
                    for table, success in fix_results.items():
                        if not success:
                            logger.warning(f"Failed to fix sequence for {table}")
            except Exception as e:
                logger.warning(f"Failed to fix sequences: {e}")
        else:
            logger.info("SQLite backend detected, skipping sequence fix")

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
                analysis_router,
                unified_agent_router,
                file_storage_router,
                OutlineExtractionUnifiedController,
                dag_pipeline_router,
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

        # 执行大纲提取任务恢复
        try:
            from sail_server.service.startup_recovery import perform_startup_recovery

            result = perform_startup_recovery()
            if result["recovered_count"] > 0:
                logger.info(
                    f"[Startup] Recovered {result['recovered_count']} outline extraction tasks "
                    f"to paused state"
                )
        except Exception as e:
            logger.warning(f"[Startup] Failed to recover outline extraction tasks: {e}")

    async def on_shutdown(self):
        from sail_server.utils.logging_config import get_logger

        logger = get_logger("sail_server")
        logger.info("Server shutting down...")

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
