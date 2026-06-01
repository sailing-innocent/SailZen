# -*- coding: utf-8 -*-
# @file __main__.py
# @brief 独立启动入口
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""SailZen DAG Client 独立启动入口。

Usage::

    # 使用默认 sail.yaml
    python -m sailzen.dag_client

    # 指定配置文件
    SAIL_CONFIG=/path/to/sail.yaml python -m sailzen.dag_client

    # 指定端口
    SAIL_DAG_API_PORT=9090 python -m sailzen.dag_client
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# 确保能找到 sail 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sailzen.dag_client.config import load_config
from sailzen.dag_client.app import create_app


def setup_logging(log_dir: str = "logs/dag", debug: bool = False) -> None:
    os.makedirs(log_dir, exist_ok=True)
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers = [logging.StreamHandler(sys.stdout)]

    # 文件日志
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "dag_client.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(fmt))
        handlers.append(file_handler)
    except Exception:
        pass

    logging.basicConfig(level=level, format=fmt, handlers=handlers)


def main() -> None:
    parser = argparse.ArgumentParser(description="SailZen DAG Client")
    parser.add_argument("--config", "-c", help="Path to sail.yaml")
    parser.add_argument("--port", "-p", type=int, help="API port override")
    parser.add_argument("--host", help="API host override")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    if args.config:
        os.environ["SAIL_CONFIG"] = args.config
    if args.port:
        os.environ["SAIL_DAG_API_PORT"] = str(args.port)
    if args.host:
        os.environ["SAIL_DAG_API_HOST"] = args.host
    if args.debug:
        os.environ["DAG_DEBUG"] = "1"

    cfg = load_config()
    setup_logging(cfg.log_dir, debug=args.debug)

    import uvicorn
    uvicorn.run(
        "sailzen.dag_client.app:app",
        host=cfg.api_host,
        port=cfg.api_port,
        reload=args.debug,
        log_level="debug" if args.debug else "info",
    )


if __name__ == "__main__":
    main()
