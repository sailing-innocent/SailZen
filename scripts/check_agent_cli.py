#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file check_agent_cli.py
# @brief CLI tool compatibility checker for opencode-compatible agent runtimes
# @author sailing-innocent
# @date 2026-04-25
# @version 1.0
# ---------------------------------
"""检查命令行工具是否兼容 opencode serve API。

Usage::

    uv run scripts/check_agent_cli.py --tool opencode-cli
    uv run scripts/check_agent_cli.py --tool kimix --port 8192
"""

import argparse
import sys

from sail.opencode.compatibility import check_cli_compatibility


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check if a CLI tool is compatible with opencode serve API"
    )
    parser.add_argument(
        "--tool",
        default="opencode-cli",
        help="CLI tool name to check (default: opencode-cli)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port for temporary test server (0 = auto-assign)",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=15.0,
        help="Max seconds to wait for server startup",
    )
    parser.add_argument(
        "--api-timeout",
        type=float,
        default=5.0,
        help="Timeout for API test requests",
    )
    args = parser.parse_args()

    print(f"Checking compatibility for: {args.tool}")
    print("-" * 50)

    report = check_cli_compatibility(
        cli_tool=args.tool,
        port=args.port,
        startup_timeout=args.startup_timeout,
        api_timeout=args.api_timeout,
    )

    print(report.to_text())
    return 0 if report.is_compatible else 1


if __name__ == "__main__":
    sys.exit(main())
