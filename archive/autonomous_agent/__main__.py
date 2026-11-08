# -*- coding: utf-8 -*-
# @file __main__.py
# @brief CLI entry point for autonomous agent
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""CLI entry point: python -m sailzen.autonomous_agent

Usage:
    # Start daemon (foreground)
    uv run python -m sailzen.autonomous_agent --fg

    # Start daemon with custom config
    uv run python -m sailzen.autonomous_agent --config agent.yaml

    # Trigger a pipeline manually
    uv run python -m sailzen.autonomous_agent trigger daily_standup

    # Show help
    uv run python -m sailzen.autonomous_agent --help
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Optional

from sailzen.autonomous_agent.config import load_agent_config
from sailzen.autonomous_agent.daemon import AgentDaemon


def setup_logging(log_dir: str = "logs/agent") -> None:
    """Setup agent logging."""
    import os
    from datetime import datetime

    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"agent_{datetime.now().strftime('%Y%m%d')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


async def start_daemon(config_path: Optional[str] = None, foreground: bool = True) -> None:
    """Start the agent daemon."""
    config = load_agent_config(config_path)
    setup_logging(config.log_dir)

    daemon = AgentDaemon(config)

    try:
        await daemon.start()
    except KeyboardInterrupt:
        await daemon.stop()
    except Exception as exc:
        logging.getLogger(__name__).exception("Daemon crashed: %s", exc)
        await daemon.stop()
        sys.exit(1)


async def trigger_pipeline(pipeline_id: str, config_path: Optional[str] = None) -> None:
    """Manually trigger a pipeline."""
    config = load_agent_config(config_path)
    setup_logging(config.log_dir)

    daemon = AgentDaemon(config)
    await daemon.db.connect()
    await daemon.scheduler.start()

    try:
        await daemon.scheduler.trigger_now(pipeline_id)
        # Give it a moment to execute
        await asyncio.sleep(2)
    finally:
        await daemon.scheduler.stop()
        await daemon.db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SailZen Autonomous Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", "-c", help="Path to agent.yaml config file")
    parser.add_argument("--fg", action="store_true", help="Run in foreground (default)")
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")

    subparsers = parser.add_subparsers(dest="command")

    trigger_parser = subparsers.add_parser("trigger", help="Manually trigger a pipeline")
    trigger_parser.add_argument("pipeline_id", help="Pipeline ID to trigger")

    args = parser.parse_args()

    if args.command == "trigger":
        asyncio.run(trigger_pipeline(args.pipeline_id, args.config))
    else:
        asyncio.run(start_daemon(args.config, foreground=args.fg))


if __name__ == "__main__":
    main()
