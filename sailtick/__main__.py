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
    uv run python -m sailtick trigger midday_checkin   # 手动跑一次 Tick
    uv run python -m sailtick status           # 健康状态
    uv run python -m sailtick doctor           # 依赖体检
    uv run python -m sailtick bootstrap        # 初始化 goal/计划 v0.1/首批问卷
    uv run python -m sailtick canary status    # 查看当前灰度开关状态
    uv run python -m sailtick canary set shadow --reason "灰度预演"
    uv run python -m sailtick canary kill      # 一键总闸关停（off）
    uv run python -m sailtick canary resume    # 清除熔断并恢复到 canary
    uv run python -m sailtick monitor          # 监控健康与指标快照
    uv run python -m sailtick replay           # 运行 Layer 2 Mock LLM 轨迹测试
    uv run python -m sailtick sandbox          # 运行 Layer 3 真实 API 短周期沙盒
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


async def cmd_canary(args: argparse.Namespace) -> int:
    """一键灰度开关：优先热调运行中 daemon API，不可达时直接落库。"""
    import json

    import httpx

    from sailtick.canary import CanaryController
    from sailtick.db import TickDatabase

    cfg = load_config(args.config)
    base_url = f"http://{cfg.api_host}:{cfg.api_port}"
    action = args.canary_action

    # 先尝试通过运行中的 daemon 管理 API 热切
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            if action == "status":
                resp = await client.get(f"{base_url}/canary")
            elif action == "kill":
                resp = await client.post(
                    f"{base_url}/canary/kill",
                    json={"reason": args.reason or "cli kill-switch", "actor": "cli"},
                )
            elif action == "resume":
                resp = await client.post(
                    f"{base_url}/canary/resume",
                    json={
                        "mode": args.target_mode,
                        "reason": args.reason or "cli resume",
                        "actor": "cli",
                    },
                )
            else:
                payload = {
                    "mode": args.mode,
                    "reason": args.reason or "",
                    "actor": "cli",
                }
                if args.prefix is not None:
                    payload["ticket_title_prefix"] = args.prefix
                if args.max_tickets is not None:
                    payload["max_tickets_per_tick"] = args.max_tickets
                resp = await client.post(f"{base_url}/canary/switch", json=payload)
            resp.raise_for_status()
            print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
            return 0
    except Exception:
        pass

    # daemon 未运行时直接操作隔离 SQLite（下次启动自动加载）
    db = TickDatabase(cfg.db_path)
    await db.connect()
    try:
        ctrl = CanaryController(cfg.canary, db)
        await ctrl.load()
        if action == "status":
            res = ctrl.get_status()
        elif action == "kill":
            res = await ctrl.kill(reason=args.reason or "cli kill-switch", actor="cli")
        elif action == "resume":
            res = await ctrl.resume(
                target_mode=args.target_mode,
                reason=args.reason or "cli resume",
                actor="cli",
            )
        else:
            res = await ctrl.switch(
                args.mode,
                reason=args.reason or "",
                actor="cli",
                ticket_title_prefix=args.prefix,
                max_tickets_per_tick=args.max_tickets,
            )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    finally:
        await db.close()


async def cmd_monitor(config_path: Optional[str], as_json: bool = False) -> int:
    """输出监控健康快照（优先走运行中 daemon API，否则离线直读 DB）。"""
    import json

    import httpx

    from sailtick.canary import CanaryController, CanaryMonitor
    from sailtick.db import TickDatabase
    from sailtick.state import DependencyState

    cfg = load_config(config_path)
    base_url = f"http://{cfg.api_host}:{cfg.api_port}"
    snap = None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/monitor")
            resp.raise_for_status()
            snap = resp.json()
    except Exception:
        db = TickDatabase(cfg.db_path)
        await db.connect()
        try:
            ctrl = CanaryController(cfg.canary, db)
            await ctrl.load()
            mon = CanaryMonitor(
                db, ctrl, DependencyState(), daily_token_cap=cfg.llm.daily_token_cap
            )
            snap = await mon.snapshot()
        finally:
            await db.close()

    if as_json:
        print(json.dumps(snap, ensure_ascii=False, indent=2))
    else:
        print(CanaryMonitor.format_report(snap))
    return 0 if snap["overall_health"] != "critical" else 1


async def cmd_replay(scenario_name: str) -> int:
    """运行 Layer 2 Mock LLM 轨迹回放测试。"""
    from sailtick.testing.trajectory import BUILTIN_SCENARIOS, TrajectoryRunner

    runner = TrajectoryRunner()
    names = list(BUILTIN_SCENARIOS.keys()) if scenario_name == "all" else [scenario_name]
    failed = 0
    for name in names:
        if name not in BUILTIN_SCENARIOS:
            print(f"[ERROR] unknown scenario: {name} (available: {list(BUILTIN_SCENARIOS)})")
            return 2
        report = await runner.run(BUILTIN_SCENARIOS[name]())
        print(report.to_summary())
        if not report.passed:
            failed += 1
    return 0 if failed == 0 else 1


async def cmd_sandbox(args: argparse.Namespace) -> int:
    """运行 Layer 3 真实 LLM API 短周期沙盒测试。"""
    from sailtick.testing.sandbox import LiveSandboxRunner, SandboxConfig

    sb_cfg = SandboxConfig(
        provider=args.provider,
        model=args.model or "",
        base_url=args.base_url or "",
        scenario=args.scenario,
        wake_interval_seconds=args.interval,
        max_ticks=args.ticks,
        per_tick_token_cap=args.token_cap,
        workdir=args.workdir,
        keep_artifacts=bool(args.workdir or args.keep),
    )
    runner = LiveSandboxRunner(sb_cfg)
    report = await runner.run()
    print(report.to_markdown())
    if report.status == "passed":
        return 0
    if report.status == "api_blocked":
        print(f"[sandbox] API blocked/unavailable (skipped): {report.error}")
        return 0 if args.allow_skip else 2
    return 1


def main() -> None:
    common_cfg = argparse.ArgumentParser(add_help=False)
    common_cfg.add_argument("--config", help="sailtick.yaml 路径", default=argparse.SUPPRESS)

    parser = argparse.ArgumentParser(
        prog="sailtick", description="SailTick 私人减肥监督教练", parents=[common_cfg]
    )
    parser.set_defaults(config=None)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="启动 daemon", parents=[common_cfg])
    p_trigger = sub.add_parser("trigger", help="手动跑一次 Tick", parents=[common_cfg])
    p_trigger.add_argument(
        "slot",
        choices=[
            "morning_checkin",
            "midday_checkin",
            "evening_review",
            "pre_sleep_report",
            "nightly_maintenance",
        ],
    )
    sub.add_parser("status", help="健康状态", parents=[common_cfg])
    sub.add_parser("doctor", help="依赖体检", parents=[common_cfg])
    sub.add_parser("bootstrap", help="初始化 goal/计划/首批问卷", parents=[common_cfg])

    # Layer 4: 一键灰度开关
    p_canary = sub.add_parser("canary", help="一键灰度开关与熔断控制", parents=[common_cfg])
    canary_sub = p_canary.add_subparsers(dest="canary_action", required=True)
    canary_sub.add_parser("status", help="查看当前模式与策略", parents=[common_cfg])
    p_cset = canary_sub.add_parser("set", help="切换模式 (off|shadow|canary|live)", parents=[common_cfg])
    p_cset.add_argument("mode", choices=["off", "shadow", "canary", "live"])
    p_cset.add_argument("--reason", default="")
    p_cset.add_argument("--prefix", default=None, help="灰度票据标题前缀")
    p_cset.add_argument("--max-tickets", type=int, default=None, help="单 Tick 最大票据数")
    p_ckill = canary_sub.add_parser("kill", help="紧急总闸关停（切换至 off）", parents=[common_cfg])
    p_ckill.add_argument("--reason", default="emergency kill-switch")
    p_cresume = canary_sub.add_parser("resume", help="解除熔断并恢复", parents=[common_cfg])
    p_cresume.add_argument("--to", dest="target_mode", choices=["shadow", "canary", "live"], default="canary")
    p_cresume.add_argument("--reason", default="manual resume")

    # Layer 4: 监控快照
    p_mon = sub.add_parser("monitor", help="输出运行监控与告警快照", parents=[common_cfg])
    p_mon.add_argument("--json", dest="as_json", action="store_true", help="JSON 格式输出")

    # Layer 2: Mock LLM 轨迹回放
    p_rep = sub.add_parser("replay", help="运行 Mock LLM 轨迹回放测试（Layer 2）")
    p_rep.add_argument("--scenario", default="all", help="场景名或 all")

    # Layer 3: 真实 API 短周期沙盒
    p_sb = sub.add_parser("sandbox", help="运行真实 API 短周期可控沙盒测试（Layer 3）")
    p_sb.add_argument("--provider", default="kimi", help="LLM provider（默认 kimi）")
    p_sb.add_argument("--model", default="", help="覆盖模型名")
    p_sb.add_argument("--base-url", default="", help="覆盖 API base_url")
    p_sb.add_argument("--scenario", default="quick_ping", choices=["quick_ping", "stress_override", "canary_shadow_live"])
    p_sb.add_argument("--interval", type=float, default=2.0, help="Tick 唤醒间隔（秒）")
    p_sb.add_argument("--ticks", type=int, default=2, help="最多执行 Tick 次数")
    p_sb.add_argument("--token-cap", type=int, default=20000, help="单 Tick token 上限")
    p_sb.add_argument("--workdir", default=None, help="保留产物与报告的目录")
    p_sb.add_argument("--keep", action="store_true", help="保留临时目录报告")
    p_sb.add_argument("--allow-skip", action="store_true", help="API 阻塞时返回 0（CI 友好）")

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
    elif command == "canary":
        sys.exit(asyncio.run(cmd_canary(args)))
    elif command == "monitor":
        sys.exit(asyncio.run(cmd_monitor(args.config, as_json=args.as_json)))
    elif command == "replay":
        sys.exit(asyncio.run(cmd_replay(args.scenario)))
    elif command == "sandbox":
        sys.exit(asyncio.run(cmd_sandbox(args)))


if __name__ == "__main__":
    main()
