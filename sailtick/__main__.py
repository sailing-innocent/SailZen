# -*- coding: utf-8 -*-
# @file __main__.py
# @brief SailTick CLI: run / trigger / status / doctor / bootstrap
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 命令行入口。

用法:
    uv run python -m sailtick run              # 启动 daemon（前台）
    uv run python -m sailtick run --fg
    uv run python -m sailtick trigger midday_checkin   # 手动跑一次 Tick
    uv run python -m sailtick status           # 健康状态
    uv run python -m sailtick doctor           # 依赖体检
    uv run python -m sailtick bootstrap        # 初始化 goal/计划 v0.1/首批问卷
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Optional

from sailtick.config import load_config


def setup_logging(log_dir: str = "logs/sailtick", level: int = logging.INFO) -> None:
    import os

    from datetime import datetime

    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"sailtick_{datetime.now().strftime('%Y%m%d')}.log")
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


async def cmd_run(config_path: Optional[str]) -> None:
    from sailtick.daemon import SailTickDaemon

    daemon = SailTickDaemon(load_config(config_path))
    await daemon.start()


async def cmd_trigger(slot: str, config_path: Optional[str]) -> None:
    """前台手动跑一次 Tick（供测试与演练）。"""
    from sailtick.daemon import SailTickDaemon

    daemon = SailTickDaemon(load_config(config_path))
    await daemon.db.connect()
    try:
        # 临时接线（不启动 scheduler/api）
        daemon.scheduler.register_default_callback(daemon._on_tick_trigger)
        result = await daemon.engine.run_tick(slot)
        print(f"Tick result: {result}")
    finally:
        await daemon.llm.close()
        await daemon.inbox.close()
        await daemon.scanner.close()
        await daemon.db.close()


async def cmd_status(config_path: Optional[str]) -> None:
    import httpx

    cfg = load_config(config_path)
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"http://{cfg.api_host}:{cfg.api_port}/health")
            resp.raise_for_status()
            import json

            print(json.dumps(resp.json(), ensure_ascii=False, indent=2, default=str))
        except Exception as exc:
            print(f"Daemon not reachable at {cfg.api_host}:{cfg.api_port}: {exc}")
            print("Hint: start it with `uv run python -m sailtick run`")


async def cmd_doctor(config_path: Optional[str]) -> int:
    """依赖体检：配置 / DB / sail_server / LLM key。返回 0=全绿。"""
    cfg = load_config(config_path)
    problems = []

    print("== SailTick Doctor ==")
    print(f"config: {cfg.config_dir or '(cwd)'}/sailtick.yaml")
    print(f"db_path: {cfg.db_path}")
    print(f"api: {cfg.api_host}:{cfg.api_port}")

    # 1. DB 可连接
    from sailtick.db import TickDatabase

    db = TickDatabase(cfg.db_path)
    try:
        await db.connect()
        stats = await db.get_stats()
        await db.close()
        print(f"[ok] sqlite db connected ({stats.get('db_size_bytes', 0)} bytes)")
    except Exception as exc:
        problems.append(f"db connect failed: {exc}")
        print(f"[FAIL] db: {exc}")

    # 2. sail_server 可达
    from sailtick.inbox import TicketInbox

    inbox = TicketInbox(cfg.sail_server.api_base, cfg.sail_server.auth_token)
    try:
        ok = await inbox.health()
        if ok:
            tickets = await inbox.pending_tickets()
            print(f"[ok] sail_server reachable ({len(tickets)} pending tickets)")
        else:
            problems.append("sail_server not reachable")
            print("[FAIL] sail_server unreachable")
    except Exception as exc:
        problems.append(f"sail_server health failed: {exc}")
        print(f"[FAIL] sail_server: {exc}")
    finally:
        await inbox.close()

    # 3. LLM key
    if cfg.llm.providers:
        for name, p in cfg.llm.providers.items():
            has_key = bool(p.api_key)
            print(f"[{'ok' if has_key else 'warn'}] llm provider '{name}' key={'set' if has_key else 'MISSING'}")
            if not has_key:
                problems.append(f"llm provider {name} missing api key")
    else:
        print("[warn] no llm providers configured (PLAN will use fallback templates)")
        problems.append("no llm providers")

    # 4. 目录可写
    import os

    for d in (cfg.data_dir, cfg.log_dir, cfg.handoffs_dir):
        try:
            os.makedirs(d, exist_ok=True)
            print(f"[ok] dir {d}")
        except Exception as exc:
            problems.append(f"dir {d} not writable: {exc}")
            print(f"[FAIL] dir {d}: {exc}")

    print("== Doctor result ==")
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("all green")
    return 0


async def cmd_bootstrap(config_path: Optional[str]) -> None:
    """初始化：goal=70kg、计划 v0.1、首批问卷票据 1-2 张（设计文档 Phase 6）。"""

    from sailtick.bootstrap import bootstrap

    cfg = load_config(config_path)
    await bootstrap(cfg)


def main() -> None:
    parser = argparse.ArgumentParser(prog="sailtick", description="SailTick 私人减肥监督教练")
    parser.add_argument("--config", help="sailtick.yaml 路径", default=None)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="启动 daemon")
    p_trigger = sub.add_parser("trigger", help="手动跑一次 Tick")
    p_trigger.add_argument("slot", choices=["morning_checkin", "midday_checkin", "evening_review", "nightly_maintenance"])
    sub.add_parser("status", help="健康状态")
    sub.add_parser("doctor", help="依赖体检")
    sub.add_parser("bootstrap", help="初始化 goal/计划/首批问卷")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    setup_logging()
    command = args.command
    if command == "run":
        asyncio.run(cmd_run(args.config))
    elif command == "trigger":
        asyncio.run(cmd_trigger(args.slot, args.config))
    elif command == "status":
        asyncio.run(cmd_status(args.config))
    elif command == "doctor":
        sys.exit(asyncio.run(cmd_doctor(args.config)))
    elif command == "bootstrap":
        asyncio.run(cmd_bootstrap(args.config))


if __name__ == "__main__":
    main()
