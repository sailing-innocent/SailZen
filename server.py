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

from sail_server.utils.env import read_env

import argparse

from sail_server.exception_handlers import exception_handlers
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
        log_file_raw = os.environ.get("SERVER_LOG_FILE")
        # Validate and normalize log file path early
        if log_file_raw and log_file_raw.strip():
            try:
                self.log_file = os.path.abspath(os.path.expanduser(log_file_raw.strip()))
            except Exception as e:
                logger.warning(f"Invalid log file path '{log_file_raw}': {e}. Using console logging.")
                self.log_file = None
        else:
            self.log_file = None

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
        from sail_server.router.health import router as health_router
        from sail_server.router.finance import router as finance_router
        from sail_server.router.project import router as project_router
        from sail_server.router.history import router as history_router

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

        # Setup logging configuration
        # Note: We don't configure file handler through LoggingConfig to avoid
        # "Unable to configure handler 'file'" errors. Instead, we set it up manually.
        handlers = ["queue_listener"]
        formatters = {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }

        logging_config = LoggingConfig(
            root={"level": "INFO", "handlers": handlers},
            handlers={},
            formatters=formatters,
            log_exceptions="always",
        )

        # Setup file handler manually if log file is specified
        # Note: log_file path is already normalized in __init__
        if self.log_file and self.log_file.strip():
            try:
                # Ensure the log file directory exists
                log_dir = os.path.dirname(self.log_file)
                if log_dir:
                    # Create directory with proper error handling
                    try:
                        os.makedirs(log_dir, mode=0o755, exist_ok=True)
                        # Verify directory was created and is writable
                        if not os.path.exists(log_dir):
                            raise OSError(f"Directory creation failed: {log_dir}")
                        if not os.path.isdir(log_dir):
                            raise OSError(f"Path exists but is not a directory: {log_dir}")
                        if not os.access(log_dir, os.W_OK):
                            raise OSError(f"Directory is not writable: {log_dir}")
                    except OSError as e:
                        logger.error(f"Cannot create or access log directory {log_dir}: {e}. Falling back to console logging.")
                        self.log_file = None
                else:
                    # If no directory specified, use current directory
                    logger.warning(f"No directory specified for log file: {self.log_file}")

            except Exception as e:
                logger.error(f"Error setting up log file directory: {e}. Falling back to console logging.", exc_info=True)
                self.log_file = None

        if self.log_file and self.log_file.strip():
            def setup_file_handler():
                """Set up custom rotating file handler after Litestar configures logging."""
                import logging.handlers
                
                try:
                    # Ensure directory exists right before creating handler
                    log_dir = os.path.dirname(self.log_file)
                    if log_dir:
                        try:
                            os.makedirs(log_dir, exist_ok=True)
                            # Verify directory was created and is writable
                            if not os.path.exists(log_dir):
                                raise OSError(f"Failed to create log directory: {log_dir}")
                            if not os.access(log_dir, os.W_OK):
                                raise OSError(f"Log directory is not writable: {log_dir}")
                        except OSError as e:
                            logger.error(f"Cannot create or access log directory {log_dir}: {e}. Using console logging only.")
                            return
                    
                    root_logger = logging.getLogger()
                    
                    # Remove any existing file handlers to avoid duplicates
                    for handler in root_logger.handlers[:]:
                        if isinstance(handler, (logging.handlers.RotatingFileHandler, logging.FileHandler)):
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
                    logger.info(f"File logging configured: {self.log_file}")
                except Exception as e:
                    logger.error(f"Failed to configure file handler: {e}. Using console logging only.", exc_info=True)
                    # Don't raise - allow server to continue with console logging

            # Store the setup function to call after app initialization
            self._setup_file_handler = setup_file_handler

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
                logger.warning(f"Logging configuration error: {e}. Retrying with minimal logging config.")
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

        # Setup file handler after Litestar configures logging
        if self.log_file and hasattr(self, "_setup_file_handler"):
            try:
                self._setup_file_handler()
            except Exception as e:
                logger.error(f"Failed to setup file handler: {e}. Server will continue with console logging.")

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
