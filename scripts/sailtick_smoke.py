# -*- coding: utf-8 -*-
# @file sailtick_smoke.py
# @brief SailTick 端到端冒烟测试
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick E2E 冒烟（设计文档 Phase 7 验收）。

流程:
  1. 起临时 SQLite 版 sail_server（独立端口与临时库）
  2. sailtick bootstrap（goal/计划 v0.1/首批问卷票据）
  3. 触发一个 Tick（midday_checkin）→ 断言票据/计划/handoff 生成
  4. 网页侧回复票据（REST）→ 再触发 Tick → 断言 SCAN 读到回复
  5. 清理进程与临时文件

用法:
    uv run python scripts/sailtick_smoke.py
    # 或指定已有 sail_server:
    uv run python scripts/sailtick_smoke.py --server-url http://127.0.0.1:1974
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SERVER_PORT = 19741
SAILTICK_API_PORT = 19071


def log(msg: str) -> None:
    print(f"[smoke] {msg}", flush=True)


def wait_http_ready(url: str, timeout: float = 30.0, proc: subprocess.Popen | None = None) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def http_json(url: str, method: str = "GET", payload: dict | None = None, token: str = "") -> dict | list:
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        import json

        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        import json

        return json.loads(resp.read().decode("utf-8"))


async def run_tick(config_path: str, slot: str) -> dict:
    """直接用 TickEngine 跑一次（不经 daemon，避免端口冲突）。"""
    from sailtick.config import load_config
    from sailtick.daemon import SailTickDaemon

    cfg = load_config(config_path)
    daemon = SailTickDaemon(cfg)
    await daemon.db.connect()
    daemon.scheduler.register_default_callback(daemon._on_tick_trigger)
    try:
        return await daemon.engine.run_tick(slot)
    finally:
        await daemon.llm.close()
        await daemon.inbox.close()
        await daemon.scanner.close()
        await daemon.db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="SailTick E2E smoke")
    parser.add_argument("--server-url", default=None, help="使用已有 sail_server（跳过自启）")
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="sailtick_smoke_"))
    server_proc: subprocess.Popen | None = None
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        status = "PASS" if cond else "FAIL"
        log(f"[{status}] {name} {detail}")
        if not cond:
            failures.append(name)

    try:
        # ── 1. 启动 sail_server（或复用） ────────────────────────────────
        if args.server_url:
            base = args.server_url.rstrip("/")
            api_base = f"{base}/api/v1"
            log(f"using existing server: {base}")
        else:
            base = f"http://127.0.0.1:{SERVER_PORT}"
            api_base = f"{base}/api/v1"
            env = os.environ.copy()
            env["DB_BACKEND"] = "sqlite"
            env["SQLITE_PATH"] = str(workdir / "sailzen_smoke.db")
            env["SERVER_PORT"] = str(SERVER_PORT)
            env["SERVER_HOST"] = "127.0.0.1"
            env["WEATHER_ENABLED"] = "false"
            env["REMINDER_ENABLED"] = "false"
            env.pop("POSTGRE_URI", None)
            log(f"starting sail_server on {base} (sqlite={workdir / 'sailzen_smoke.db'})")
            server_proc = subprocess.Popen(
                [sys.executable, "server.py"],
                cwd=REPO_ROOT, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            # 注意：根 /health 是静态站 302；健康端点在 /api/v1/health
            if not wait_http_ready(f"{api_base}/health", timeout=45, proc=server_proc):
                log("FATAL: sail_server failed to start")
                return 2
        log("sail_server ready")

        # ── 2. sailtick 配置 + bootstrap ─────────────────────────────
        sailtick_db = workdir / "sailtick" / "db" / "sailtick.db"
        config_path = workdir / "sailtick.yaml"
        config_path.write_text(
            f"""sailtick:
  db_path: {sailtick_db}
  data_dir: {workdir / 'sailtick'}
  log_dir: {workdir / 'logs'}
  api_port: {SAILTICK_API_PORT}
  sail_server:
    api_base: {api_base}
  llm:
    default: deepseek
""",
            encoding="utf-8",
        )

        from sailtick.bootstrap import bootstrap
        from sailtick.config import load_config

        cfg = load_config(str(config_path))
        summary = asyncio.run(bootstrap(cfg))
        check("bootstrap creates goal+plan", summary["plan"] == "v0.1")
        check("bootstrap creates first tickets", len(summary["tickets"]) >= 1,
              f"tickets={summary['tickets']}")
        check("bootstrap writes handoff", Path(summary["handoff"]).exists())

        tickets = http_json(f"{api_base}/tick/tickets?status=pending")
        check("server has pending tickets", len(tickets) >= 1, f"count={len(tickets)}")

        # ── 3. 触发 Tick → 断言产物 ───────────────────────────────────
        result = asyncio.run(run_tick(str(config_path), "midday_checkin"))
        check("tick completes", result["status"] == "completed")

        db_path = sailtick_db
        check("tick row persisted", db_path.exists())
        from sailtick.db import TickDatabase

        async def _check_artifacts():
            db = TickDatabase(str(db_path))
            await db.connect()
            ticks = await db.list_ticks()
            handoffs = await db.list_handoffs()
            plan = await db.get_active_plan()
            episodes = await db.list_episodes(limit=50)
            await db.close()
            return ticks, handoffs, plan, episodes

        ticks, handoffs, plan, episodes = asyncio.run(_check_artifacts())
        check("tick state=completed", any(t["state"] == "completed" for t in ticks))
        check("handoff doc generated", len(handoffs) >= 1)
        check("active plan v0.1", plan is not None and plan["version"] == "v0.1")
        check("episodes recorded", len(episodes) >= 3, f"episodes={len(episodes)}")
        if handoffs:
            check("handoff file exists", Path(handoffs[0]["path"]).exists())

        # ── 4. 回复票据 → 再触发 → SCAN 读到回复 ──────────────────────
        tid = tickets[0]["id"]
        http_json(f"{api_base}/tick/tickets/{tid}/reply", method="POST",
                  payload={"reply": "72.5（冒烟回复）"})
        result2 = asyncio.run(run_tick(str(config_path), "evening_review"))

        async def _check_reply_read():
            db = TickDatabase(str(db_path))
            await db.connect()
            eps = await db.list_episodes(limit=100)
            await db.close()
            # inbox 轮询在 daemon 里；engine 的 SCAN 把 new_replies 记进 scan episode
            scan_eps = [e for e in eps if e["kind"] == "scan"]
            return scan_eps

        scan_eps = asyncio.run(_check_reply_read())
        # 最后一次 scan episode 应显示 new_replies=1
        last_scan_new_replies = [
            (e["content"].get("new_replies") if isinstance(e["content"], dict) else None)
            for e in scan_eps
        ]
        check("second tick reads user reply", 1 in last_scan_new_replies,
              f"scan new_replies history={last_scan_new_replies}")

        tickets_after = http_json(f"{api_base}/tick/tickets?status=replied")
        check("ticket replied on server", any(t["id"] == tid for t in tickets_after))

        log(f"smoke finished: {len(failures)} failure(s)")
        return 1 if failures else 0
    finally:
        if server_proc is not None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_proc.kill()
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
