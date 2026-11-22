# -*- coding: utf-8 -*-
# @file health_check.py
# @brief Read-only HTTP & SailTick health check for dev and prod SailZen servers
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""SailZen 服务只读健康体检脚本。

检查项：
1. 核心存活接口 /api/v1/health 返回 {"status": "ok"}
2. 核心业务只读 GET 路由（Finance / Health / Rhythm / Reminder / Tick / Life / Necessity / Text）均返回 200
3. （可选）Web 前端首页 / 返回 HTML（prod 默认校验）
4. （可选 --with-sailtick）校验 SailTick 管理 API (:9070/health) 状态

用法:
    uv run python scripts/ops/health_check.py --env dev
    uv run python scripts/ops/health_check.py --env prod --with-sailtick
    uv run python scripts/ops/health_check.py --url http://127.0.0.1:4399
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops.common import (
    OpsConfig,
    configure_console_utf8,
    load_ops_config,
    run_ssh_command,
)

# 全部只读、零副作用的核心业务探针（相对 API_ENDPOINT，如 /api/v1）
CORE_READONLY_ENDPOINTS: List[Tuple[str, str]] = [
    ("Core Health", "/health"),
    ("Health/Weight", "/health/weight"),
    ("Health/BodyMetrics", "/health/body-data/metrics"),
    ("Finance/Account", "/finance/account"),
    ("Rhythm/Affair", "/rhythm/affair"),
    ("Rhythm/EnergyProfile", "/rhythm/energy/profile"),
    ("Reminder/Pending", "/reminder/pending"),
    ("Tick/Tickets", "/tick/tickets"),
    ("Life/Weather", "/life/weather"),
    ("Necessity/Residence", "/necessity/residence"),
    ("Text/Work", "/text/work"),
]


@dataclass
class CheckResult:
    name: str
    target: str
    ok: bool
    status_code: Optional[int]
    latency_ms: float
    detail: str


def _probe_http(
    client: httpx.Client, name: str, url: str, expect_json_status_ok: bool = False
) -> CheckResult:
    t0 = time.monotonic()
    try:
        resp = client.get(url)
        latency = (time.monotonic() - t0) * 1000.0
    except Exception as exc:
        latency = (time.monotonic() - t0) * 1000.0
        return CheckResult(name, url, False, None, latency, f"请求异常: {exc}")

    if resp.status_code != 200:
        snippet = resp.text.strip().replace("\n", " ")[:120]
        return CheckResult(name, url, False, resp.status_code, latency, f"HTTP {resp.status_code}: {snippet}")

    if expect_json_status_ok:
        try:
            payload = resp.json()
        except Exception as exc:
            return CheckResult(name, url, False, resp.status_code, latency, f"JSON 解析失败: {exc}")
        if payload.get("status") != "ok":
            return CheckResult(name, url, False, resp.status_code, latency, f"预期 status=ok，实际: {payload}")
        return CheckResult(name, url, True, resp.status_code, latency, "status=ok")

    return CheckResult(name, url, True, resp.status_code, latency, f"200 ({len(resp.content)}B)")


def _check_sailtick(cfg: OpsConfig, env_name: str) -> CheckResult:
    """检查 SailTick 管理 API (:9070/health)。prod 通过 SSH 在本机查询，dev 直接请求本地。"""
    t0 = time.monotonic()
    url = f"{cfg.remote_sailtick_url}/health"
    try:
        if env_name == "prod":
            proc = run_ssh_command(cfg, f"curl -fsS --max-time 8 {shlex.quote(url)}", timeout=15)
            payload = json.loads(proc.stdout)
        else:
            resp = httpx.get(url, timeout=8.0)
            resp.raise_for_status()
            payload = resp.json()
        latency = (time.monotonic() - t0) * 1000.0
        status = payload.get("status", "unknown")
        ok = status in {"running", "ok"}
        detail = f"status={status}, schedules={len(payload.get('schedules', []))}"
        return CheckResult("SailTick Daemon", url, ok, 200 if ok else None, latency, detail)
    except Exception as exc:
        latency = (time.monotonic() - t0) * 1000.0
        return CheckResult("SailTick Daemon", url, False, None, latency, str(exc).splitlines()[0])


def run_health_check(
    cfg: OpsConfig,
    *,
    env_name: str = "dev",
    base_url: Optional[str] = None,
    check_web_root: Optional[bool] = None,
    with_sailtick: bool = False,
    retries: int = 1,
    retry_delay: float = 2.0,
    timeout: float = 10.0,
) -> Tuple[bool, List[CheckResult]]:
    """执行完整体检；支持重启后等待重试。"""
    resolved_url = (base_url or cfg.get_server_url(env_name)).rstrip("/")
    api_prefix = cfg.get_api_endpoint(env_name)
    token = cfg.get_api_token(env_name)
    should_check_web = (env_name == "prod") if check_web_root is None else check_web_root

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_results: List[CheckResult] = []
    attempts = max(1, retries)

    for attempt in range(1, attempts + 1):
        results: List[CheckResult] = []
        with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
            if should_check_web:
                web_res = _probe_http(client, "Web Root (site_dist)", f"{resolved_url}/")
                results.append(web_res)

            for name, rel_path in CORE_READONLY_ENDPOINTS:
                full_url = f"{resolved_url}{api_prefix}{rel_path}"
                res = _probe_http(
                    client,
                    name,
                    full_url,
                    expect_json_status_ok=(rel_path == "/health"),
                )
                results.append(res)

        if with_sailtick:
            results.append(_check_sailtick(cfg, env_name))

        last_results = results
        if all(r.ok for r in results):
            return True, results

        if attempt < attempts:
            print(f"[HealthCheck] 第 {attempt}/{attempts} 次体检未全通过，{retry_delay:.1f}s 后重试...")
            time.sleep(retry_delay)

    return False, last_results


def print_report(results: List[CheckResult], title: str) -> None:
    print(f"\n=== {title} ===\n")
    for r in results:
        tag = "[OK]  " if r.ok else "[FAIL]"
        code = str(r.status_code) if r.status_code is not None else "-"
        print(f"{tag} {r.name:<22} code={code:<4} {r.latency_ms:6.1f}ms  {r.detail}")
    passed = sum(1 for r in results if r.ok)
    print(f"\nResult: {passed}/{len(results)} passed.")


def main() -> int:
    configure_console_utf8()
    parser = argparse.ArgumentParser(description="SailZen 服务只读健康体检")
    parser.add_argument("--ops-env", default=None, help="指定运维配置文件路径（默认 .env.ops）")
    parser.add_argument("--env", choices=("dev", "prod"), default="dev", help="目标环境（默认 dev）")
    parser.add_argument("--url", default=None, help="覆盖服务基础 URL（如 http://127.0.0.1:4399）")
    parser.add_argument("--check-web", action="store_true", help="强制检查根路径 / 静态首页")
    parser.add_argument("--skip-web", action="store_true", help="跳过根路径 / 静态首页检查")
    parser.add_argument("--with-sailtick", action="store_true", help="同时检查 SailTick 管理 API (:9070/health)")
    parser.add_argument("--retries", type=int, default=1, help="失败重试次数（部署重启后建议设 5）")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="重试间隔秒数")
    args = parser.parse_args()

    check_web: Optional[bool] = None
    if args.check_web:
        check_web = True
    elif args.skip_web:
        check_web = False

    cfg = load_ops_config(args.ops_env)
    try:
        ok, results = run_health_check(
            cfg,
            env_name=args.env,
            base_url=args.url,
            check_web_root=check_web,
            with_sailtick=args.with_sailtick,
            retries=args.retries,
            retry_delay=args.retry_delay,
        )
        print_report(results, f"SailZen Health Check ({args.env})")
        return 0 if ok else 1
    except Exception as exc:
        print(f"\n[FAIL] 健康体检异常: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
