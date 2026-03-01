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
from sail_server.utils.env import read_env
from litestar import Litestar, Router, get, Request
from litestar.response import Redirect, Response
from litestar.openapi import OpenAPIConfig

# 导入新的日志体系
from sail_server.utils.logging_config import setup_logging, get_logger
logger = get_logger("sail_server")

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
        ]
        self.api_router = None
        # 调试模式由 LOG_MODE 环境变量控制
        self.debug = os.environ.get("LOG_MODE", "prod") in ("dev", "debug")
        # 新的日志体系自动处理日志文件，不需要手动设置
        self.log_file = None

    def init(self):
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
        from sail_server.router.analysis_compat import analysis_compat_router
        from sail_server.router.agent_compat import agent_compat_router
        
        # 自动注册 Agent
        from sail_server.agent import auto_register_agents
        auto_register_agents()
        
        # 修复数据库序列
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

        self.api_router = Router(
            path=self.api_endpoint,
            route_handlers=[
                health_check,
                self.base_router,
                health_router,
                finance_router,
                project_router,
                history_router,
                text_router,
                necessity_router,
                analysis_router,
                unified_agent_router,
                # 兼容层路由
                analysis_compat_router,
                agent_compat_router,
            ],
        )

        # Setup logging configuration
        handlers = ["queue_listener"]
        formatters = {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }

        # 使用最小化的 Litestar 日志配置（因为我们已经通过 logging_config 设置了）
        logging_config = LoggingConfig(
            root={"level": "INFO", "handlers": []},
            handlers={},
            formatters={},
            log_exceptions="always",
        )

        cors_config = CORSConfig(allow_origins=["*"], allow_methods=["*"])

        # Configure OpenAPI documentation
        openapi_config = OpenAPIConfig(
            title="Sail Server API",
            version="1.0.0",
            summary="API documentation for Sail Server",
            path="/api_docs",
        )

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
            )
        except Exception as e:
            # If logging config fails, try without it
            if "handler" in str(e).lower() or "logging" in str(e).lower():
                logger.warning(
                    f"Logging configuration error: {e}. Retrying with minimal logging config."
                )
                # Create a minimal logging config without any custom handlers
                minimal_logging_config = LoggingConfig(
                    root={"level": "INFO", "handlers": ["queue_listener"]},
                    handlers={},
                    formatters={},
                    log_exceptions="always",
                )
                self.app = Litestar(
                    route_handlers=[self.base_router, self.api_router],
                    debug=self.debug,
                    logging_config=minimal_logging_config,
                    cors_config=cors_config,
                    exception_handlers=exception_handlers,
                    on_startup=[self.on_startup],
                    on_shutdown=[self.on_shutdown],
                    openapi_config=openapi_config,
                )
            else:
                raise

    async def on_startup(self):
        logger.info("Server starting up...")

    async def on_shutdown(self):
        logger.info("Server shutting down...")

    def run(self):
        logger.info(f"Server running on {self.host}:{self.port}")
        if not self.app:
            logger.error("App Not Initialized")
            return
        import uvicorn

        # 使用新的日志体系，禁用 uvicorn 的默认日志
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_config=None,  # 使用我们的日志配置
            access_log=False,
        )


def main():
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

    
    if args.dev:
        from sail_server.utils.env import read_env
        read_env("dev")
    elif args.debug:
        read_env("debug")
    else:
        read_env("prod")

    setup_logging()      
    main()
