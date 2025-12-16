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
from litestar.response import Redirect
from litestar.openapi import OpenAPIConfig

import logging
from litestar.config.cors import CORSConfig

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("sail_server")
from litestar.logging import LoggingConfig


from utils.env import read_env
import argparse

from internal.exception_handlers import exception_handlers
from litestar.static_files import create_static_files_router


class SailServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.app = None
        self.router = None
        self.api_endpoint = os.environ.get("API_ENDPOINT", "/api")
        self.site_dist = os.environ.get("SITE_DIST", "site_dist")
        self.page_alias = [
            "/health",
            "/money",
            "/project",
        ]
        self.api_router = None
        self.debug = os.environ.get("DEV_MODE", "false").lower() == "true"
        self.log_file = os.environ.get("SERVER_LOG_FILE")

    def _create_custom_rotating_handler(self):
        """Create a custom rotating file handler with timestamp-based backup naming."""
        import logging.handlers

        class TimestampRotatingFileHandler(logging.handlers.RotatingFileHandler):
            def doRollover(self):
                if self.stream:
                    self.stream.close()
                    self.stream = None

                # Generate timestamp for backup file
                save_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"{self.baseFilename}.bk.{save_time}"

                # Rename current log file to backup
                if os.path.exists(self.baseFilename):
                    os.rename(self.baseFilename, backup_name)

                # Open new log file
                if not self.delay:
                    self.stream = self._open()

        return TimestampRotatingFileHandler

    def init(self):
        @get("/health")
        async def health_check(request: Request) -> dict[str, str]:
            return {"status": "ok"}

        # redirect all self.page_alias to root
        route_handlers = []
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
        from internal.router.health import router as health_router
        from internal.router.finance import router as finance_router
        from internal.router.project import router as project_router
        from internal.router.history import router as history_router

        self.api_router = Router(
            path=self.api_endpoint,
            route_handlers=[
                health_check,
                self.base_router,
                health_router,
                finance_router,
                project_router,
                history_router,
            ],
        )

        # Setup logging configuration with file handler if log file is specified
        handlers = ["queue_listener"]
        formatters = {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }

        # Create custom handler instance if log file is specified
        handler_config = {}
        if self.log_file:
            # Remove console handlers and use only file handler
            handlers = ["file"]
            formatters["file"] = {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }

            # Configure the file handler in LoggingConfig
            handler_config = {
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": self.log_file,
                    "maxBytes": 512 * 1024,  # 512KB
                    "backupCount": 0,  # We'll override this behavior
                    "formatter": "file",
                    "level": "INFO",
                }
            }

        logging_config = LoggingConfig(
            root={"level": "INFO", "handlers": handlers},
            handlers=handler_config,
            formatters=formatters,
            log_exceptions="always",
        )

        # Override the rotating behavior after Litestar sets up logging
        if self.log_file:

            def setup_custom_rotation():
                # Find and replace the rotating file handler with our custom one
                root_logger = logging.getLogger()
                for handler in root_logger.handlers[:]:
                    if isinstance(handler, logging.handlers.RotatingFileHandler):
                        root_logger.removeHandler(handler)
                        handler.close()

                # Add our custom rotating handler
                custom_handler = self._create_custom_rotating_handler()(
                    filename=self.log_file,
                    maxBytes=512 * 1024,  # 512KB
                    backupCount=0,  # We handle backups manually
                )
                custom_handler.setLevel(logging.INFO)
                custom_handler.setFormatter(
                    logging.Formatter(
                        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                    )
                )
                root_logger.addHandler(custom_handler)

            # Store the setup function to call after app initialization
            self._setup_custom_rotation = setup_custom_rotation

        cors_config = CORSConfig(allow_origins=["*"], allow_methods=["*"])

        # Configure OpenAPI documentation
        openapi_config = OpenAPIConfig(
            title="Sail Server API",
            version="1.0.0",
            summary="API documentation for Sail Server",
            path="/api_docs",
        )

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

        # Setup custom rotation after Litestar configures logging
        if self.log_file and hasattr(self, "_setup_custom_rotation"):
            self._setup_custom_rotation()

    async def on_startup(self):
        logger.info("Server starting up...")
        # Initialize any resources or connections here
        await asyncio.sleep(0.1)

    async def on_shutdown(self):
        logger.info("Server shutting down...")
        # Clean up any resources or connections here
        await asyncio.sleep(0.1)

    def run(self):
        logger.info(f"Server running on {self.host}:{self.port}")
        import uvicorn

        # Configure uvicorn to use our logging setup
        uvicorn_config = {
            "host": self.host,
            "port": self.port,
            "log_level": "info",
            "access_log": False,
            "use_colors": False,  # Disable colors for file logging
        }

        # If we have a log file, disable uvicorn's default logging
        if self.log_file:
            uvicorn_config.update(
                {
                    "log_config": None,  # Disable uvicorn's logging config
                    "access_log": False,
                }
            )

        uvicorn.run(self.app, **uvicorn_config)


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
    args = parser.parse_args()
    if args.dev:
        read_env("dev")
    else:
        read_env("prod")
    main()
