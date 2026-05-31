# -*- coding: utf-8 -*-
# @file main.py
# @brief Entry point for the dummy opencode-compatible SSE server.
# @author sailing-innocent
# @date 2026-05-31
# @version 1.0
# ---------------------------------

from __future__ import annotations

import argparse
import asyncio
import logging
import os

from aiohttp import web

from sail.opencode_server.app import create_app
from sail.opencode_server.llm_backend import MockBackend, MoonshotBackend


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dummy OpenCode-compatible SSE server"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=4096, help="Bind port")
    parser.add_argument(
        "--backend",
        choices=["mock", "moonshot"],
        default="mock",
        help="LLM backend to use",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (for moonshot backend)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.backend == "moonshot":
        backend = MoonshotBackend(model=args.model)
    else:
        backend = MockBackend()

    app = create_app(backend=backend)
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
