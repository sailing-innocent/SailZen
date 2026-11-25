# -*- coding: utf-8 -*-
# @file perf_loop.py
# @brief SailZen Telemetry-Driven Performance Analysis & Optimization Loop CLI
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""SailZen 遥测驱动的性能分析-优化-验收闭环工具。

子命令：
  1. collect           只读拉取生产/本地 Telemetry 全量快照并输出优先级诊断榜单
  2. bench-local       在本地调试库（.env.dev）上执行 SQL 计数 + 延迟基准，支持与基线对比
  3. audit-indexes     检查本地调试库（.env.dev）表行数、顺序扫描热点与索引覆盖/重复情况
  4. compare-snapshots 对比优化前后两份生产 Telemetry 快照（上线后回归验收）

用法示例:
    uv run python scripts/ops/perf_loop.py collect --env prod --hours 72
    uv run python scripts/ops/perf_loop.py bench-local --runs 5 --save data/perf_snapshots/baseline.json
    uv run python scripts/ops/perf_loop.py bench-local --runs 5 --baseline data/perf_snapshots/baseline.json
    uv run python scripts/ops/perf_loop.py audit-indexes
    uv run python scripts/ops/perf_loop.py compare-snapshots before.json after.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops.common import (
    assert_local_pg_target,
    configure_console_utf8,
    load_ops_config,
)

DEFAULT_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "perf_snapshots"

TELEMETRY_ENDPOINTS: List[Tuple[str, str]] = [
    ("api_profile", "/telemetry/profile/api?hours={hours}&include_self=true"),
    ("api_profile_noself", "/telemetry/profile/api?hours={hours}&include_self=false"),
    ("modules_profile", "/telemetry/profile/modules?days={days}"),
    ("runtime_profile", "/telemetry/profile/runtime"),
    ("ai_traces_stats", "/telemetry/ai-traces/stats?days={days}"),
    ("ai_traces_list", "/telemetry/ai-traces?days={days}&limit=50"),
    ("sailtick_live", "/telemetry/sailtick/live"),
]


def _is_binary_download(endpoint: str) -> bool:
    low = (endpoint or "").lower()
    return (
        "/app/release/download/" in low
        or (("/file_storage/" in low or "/file-storage/" in low) and "/download" in low)
    )


def analyze_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """对单份 Telemetry 快照执行结构化诊断，按优先级归类性能与稳定性信号。"""
    api_data = (snapshot.get("api_profile") or {}).get("data") or {}
    mod_data = (snapshot.get("modules_profile") or {}).get("data") or {}
    rt_data = (snapshot.get("runtime_profile") or {}).get("data") or {}
    ai_stats = (snapshot.get("ai_traces_stats") or {}).get("data") or {}

    top_slow = api_data.get("top_slow_endpoints") or []
    top_called = api_data.get("top_called_endpoints") or []
    by_mod = api_data.get("by_module") or []

    # 合并去重所有可见端点
    ep_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for ep in top_slow + top_called:
        key = (ep.get("method", "GET"), ep.get("endpoint", ""))
        ep_map[key] = ep
    all_eps = list(ep_map.values())

    # 1. 错误热点（4xx/5xx + 客户端 JS 错误）
    error_endpoints = sorted(
        [e for e in all_eps if (e.get("err_4xx", 0) + e.get("err_5xx", 0)) > 0],
        key=lambda e: (e.get("err_5xx", 0), e.get("error_rate", 0.0), e.get("err_4xx", 0)),
        reverse=True,
    )
    client_errors = mod_data.get("recent_client_errors") or []

    # 2. 业务慢接口（剥离二进制大文件下载，按综合影响力 avg_ms * log2(req+1) 排序）
    business_slow = []
    binary_downloads = []
    for e in all_eps:
        if _is_binary_download(e.get("endpoint", "")):
            binary_downloads.append(e)
            continue
        avg_ms = float(e.get("avg_ms") or 0.0)
        p95_ms = float(e.get("p95_ms") or 0.0)
        req_count = int(e.get("req_count") or 0)
        impact = round(avg_ms * math.log2(req_count + 1), 2)
        if p95_ms >= 20.0 or avg_ms >= 15.0:
            item = dict(e)
            item["impact_score"] = impact
            business_slow.append(item)
    business_slow.sort(key=lambda x: (x["impact_score"], x.get("p95_ms", 0.0)), reverse=True)

    # 3. 高流量负载端点（单次均值 >= 12KB 或总出流量 >= 500KB，不含二进制下载）
    heavy_payload = []
    for e in all_eps:
        if _is_binary_download(e.get("endpoint", "")):
            continue
        req_count = max(1, int(e.get("req_count") or 1))
        bytes_out = int(e.get("bytes_out") or 0)
        kb_per_req = round(bytes_out / req_count / 1024.0, 2)
        if kb_per_req >= 12.0 or bytes_out >= 500 * 1024:
            item = dict(e)
            item["kb_per_req"] = kb_per_req
            item["total_kb"] = round(bytes_out / 1024.0, 1)
            heavy_payload.append(item)
    heavy_payload.sort(key=lambda x: x["total_kb"], reverse=True)

    # 4. Telemetry 观测仪表自身体检
    instrument_warnings: List[str] = []
    global_p50 = float(api_data.get("p50_ms") or 0.0)
    if by_mod:
        top_mod_p50s = [
            float(m.get("p50_ms") or 0.0)
            for m in by_mod[:3]
            if not _is_binary_download(m.get("module", ""))
        ]
        if top_mod_p50s and global_p50 > max(top_mod_p50s) * 2.5 and global_p50 > 15.0:
            instrument_warnings.append(
                f"全局 P50 ({global_p50}ms) 远高于高频模块 P50 ({top_mod_p50s})，疑似存在离群请求或加权平均失真"
            )
    for e in all_eps:
        ep_path = e.get("endpoint", "")
        if ".apk" in ep_path.lower() or ".zip" in ep_path.lower():
            instrument_warnings.append(
                f"检测到未归一化的文件名路径桶: {ep_path}（建议在 normalize_api_path 中归一为 {{filename}}）"
            )

    return {
        "collected_at": snapshot.get("collected_at"),
        "env": snapshot.get("env"),
        "overview": {
            "total_requests": api_data.get("total_requests", 0),
            "error_rate": api_data.get("error_rate", 0.0),
            "total_4xx": api_data.get("total_4xx", 0),
            "total_5xx": api_data.get("total_5xx", 0),
            "avg_ms": api_data.get("avg_ms", 0.0),
            "p50_ms": api_data.get("p50_ms", 0.0),
            "p95_ms": api_data.get("p95_ms", 0.0),
            "p99_ms": api_data.get("p99_ms", 0.0),
            "max_ms": api_data.get("max_ms", 0.0),
            "memory_rss_mb": rt_data.get("memory_rss_mb", 0.0),
            "uptime_seconds": rt_data.get("uptime_seconds", 0.0),
            "ai_total_traces": ai_stats.get("total_traces", 0),
            "ai_success_rate": ai_stats.get("success_rate", 1.0),
            "ai_fallback_rate": ai_stats.get("fallback_rate", 0.0),
            "ai_avg_duration_ms": ai_stats.get("avg_duration_ms", 0.0),
            "ai_avg_llm_latency_ms": ai_stats.get("avg_llm_latency_ms", 0.0),
        },
        "error_endpoints": error_endpoints,
        "client_errors_count": len(client_errors),
        "client_errors_sample": client_errors[:5],
        "business_slow_endpoints": business_slow[:10],
        "binary_downloads": binary_downloads,
        "heavy_payload_endpoints": heavy_payload[:10],
        "instrument_warnings": instrument_warnings,
    }


def print_triage_report(report: Dict[str, Any]) -> None:
    ov = report["overview"]
    print("\n================ SailZen Telemetry Triage Report ================")
    print(
        f"Env: {report['env']} | Collected: {report['collected_at']} | "
        f"Reqs: {ov['total_requests']} | 4xx/5xx: {ov['total_4xx']}/{ov['total_5xx']} ({ov['error_rate']*100:.2f}%)"
    )
    print(
        f"Latency: avg={ov['avg_ms']}ms  p50={ov['p50_ms']}ms  p95={ov['p95_ms']}ms  "
        f"p99={ov['p99_ms']}ms  max={ov['max_ms']}ms"
    )
    print(
        f"Runtime: RSS={ov['memory_rss_mb']}MB | Uptime={ov['uptime_seconds']}s | "
        f"AI Traces={ov['ai_total_traces']} (ok={ov['ai_success_rate']*100:.0f}%, "
        f"avg={ov['ai_avg_duration_ms']}ms, llm={ov['ai_avg_llm_latency_ms']}ms)"
    )

    if report["instrument_warnings"]:
        print("\n[P0] Telemetry Instrument Warnings:")
        for w in report["instrument_warnings"]:
            print(f"  - {w}")

    if report["error_endpoints"] or report["client_errors_count"] > 0:
        print("\n[P1] Error Hotspots (API 4xx/5xx & Frontend Client Errors):")
        for e in report["error_endpoints"]:
            print(
                f"  - {e['method']} {e['endpoint']}  reqs={e['req_count']} "
                f"4xx={e['err_4xx']} 5xx={e['err_5xx']} rate={e['error_rate']*100:.1f}%"
            )
        if report["client_errors_count"]:
            print(f"  - Frontend client_error count={report['client_errors_count']}:")
            seen = set()
            for ce in report["client_errors_sample"]:
                msg = ce.get("name", "")
                if msg not in seen:
                    seen.add(msg)
                    print(f"      * [{(ce.get('detail') or {}).get('path', '?')}] {msg[:110]}")

    print("\n[P2] Top Business Slow Endpoints (ranked by impact = avg_ms * log2(reqs+1)):")
    if not report["business_slow_endpoints"]:
        print("  (none >= 15ms avg / 20ms p95)")
    else:
        print(f"  {'Method':<6} {'Endpoint':<44} {'Reqs':>5} {'Avg(ms)':>8} {'P95(ms)':>8} {'Max(ms)':>8} {'Impact':>8}")
        for e in report["business_slow_endpoints"]:
            print(
                f"  {e['method']:<6} {e['endpoint']:<44} {e['req_count']:>5} "
                f"{e['avg_ms']:>8.1f} {e['p95_ms']:>8.1f} {e['max_ms']:>8.1f} {e['impact_score']:>8.1f}"
            )

    if report["heavy_payload_endpoints"]:
        print("\n[P3] Heavy Payload Endpoints:")
        for e in report["heavy_payload_endpoints"]:
            print(
                f"  - {e['method']} {e['endpoint']:<42} reqs={e['req_count']:<4} "
                f"avg={e['kb_per_req']:>6.1f} KB/req  total={e['total_kb']:>7.1f} KB"
            )
    print("=================================================================\n")


def cmd_collect(args: argparse.Namespace) -> int:
    cfg = load_ops_config(args.ops_env)
    base = (args.url or cfg.get_server_url(args.env)).rstrip("/")
    prefix = cfg.get_api_endpoint(args.env)
    token = cfg.get_api_token(args.env)

    headers = {"Accept": "application/json", "X-SailZen-Client": "cli"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    snapshot: Dict[str, Any] = {
        "env": args.env,
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "hours": args.hours,
        "days": args.days,
    }
    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        for key, tmpl in TELEMETRY_ENDPOINTS:
            rel = tmpl.format(hours=args.hours, days=args.days)
            resp = client.get(f"{base}{prefix}{rel}")
            try:
                body = resp.json() if resp.status_code == 200 else resp.text[:400]
            except Exception:
                body = resp.text[:400]
            snapshot[key] = {
                "status": resp.status_code,
                "elapsed_ms": round(resp.elapsed.total_seconds() * 1000.0, 1),
                "data": body,
            }

    out_path = Path(args.out) if args.out else (
        DEFAULT_SNAPSHOT_DIR / f"telemetry_{args.env}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    report = analyze_snapshot(snapshot)
    print_triage_report(report)
    print(f"[Saved] {out_path}")
    return 0


def _make_finance_batch_queries() -> List[Dict[str, Any]]:
    regular_tags = ["餐饮", "零食", "日用消耗", "交通", "娱乐", "医疗", "服饰", "学习"]
    major_tags = ["大宗收支", "大宗电器"]
    queries: List[Dict[str, Any]] = []
    periods = []
    for m in range(6, 12):
        start = datetime(2026, m, 1).timestamp()
        end = datetime(2026, m + 1, 1).timestamp() - 1
        periods.append((f"2026-{m:02d}", start, end))
    for key, s, e in periods:
        for tag in regular_tags:
            queries.append({"id": f"reg-{key}-{tag}", "tags": tag, "tag_op": "or", "return_list": False, "from_time": s, "to_time": e})
        queries.append({"id": f"tot-{key}", "return_list": False, "from_time": s, "to_time": e})
        for tag in major_tags:
            queries.append({"id": f"maj-{key}-{tag}", "tags": tag, "tag_op": "or", "return_list": False, "from_time": s, "to_time": e})
        queries.append({"id": f"day-{key}", "tags": "日用消耗", "tag_op": "or", "return_list": False, "from_time": s, "to_time": e})
    overall_s, overall_e = periods[0][1], periods[-1][2]
    for tag in regular_tags + major_tags:
        queries.append({"id": f"ov-{tag}", "tags": tag, "tag_op": "or", "return_list": False, "from_time": overall_s, "to_time": overall_e})
    return queries


def cmd_bench_local(args: argparse.Namespace) -> int:
    cfg = load_ops_config(args.ops_env)
    assert_local_pg_target(cfg.get_dev_pg())

    from sail.utils import read_env

    read_env("dev")

    from sqlalchemy import event
    from sail_server.db import get_db_session
    from sail_server.model.finance.transaction import (
        get_transaction_stats_batch_impl,
        read_transactions_impl,
    )
    from sail_server.model.rhythm import get_dashboard_impl
    from sail_server.model.telemetry import get_api_profile_impl, get_modules_profile_impl
    from sail_server.model.text import get_works_impl

    class _SqlCounter:
        def __init__(self, bind) -> None:
            self.bind = bind
            self.count = 0

        def _on_exec(self, conn, cursor, statement, parameters, context, executemany):
            self.count += 1

        def __enter__(self):
            self.count = 0
            event.listen(self.bind, "before_cursor_execute", self._on_exec)
            return self

        def __exit__(self, exc_type, exc, tb):
            event.remove(self.bind, "before_cursor_execute", self._on_exec)

    target_day = date.fromisoformat(args.date) if args.date else date.today()
    batch_queries = _make_finance_batch_queries()
    cases: List[Tuple[str, Callable[[Any], Any]]] = [
        ("POST /finance/transaction/stats/batch (82q)", lambda db: get_transaction_stats_batch_impl(db, batch_queries)),
        ("GET /telemetry/profile/modules", lambda db: get_modules_profile_impl(db, window_days=7)),
        ("GET /text/work (limit=20)", lambda db: get_works_impl(db, skip=0, limit=20)),
        ("GET /finance/transaction (all)", lambda db: read_transactions_impl(db, skip=0, limit=-1)),
        ("GET /rhythm/dashboard", lambda db: get_dashboard_impl(db, target_day)),
        ("GET /telemetry/profile/api (72h)", lambda db: get_api_profile_impl(db, window_hours=72)),
    ]

    results: List[Dict[str, Any]] = []
    for name, fn in cases:
        with get_db_session() as db:
            fn(db)  # warmup
        latencies: List[float] = []
        sql_count = 0
        for i in range(max(1, args.runs)):
            with get_db_session() as db:
                if i == 0:
                    with _SqlCounter(db.get_bind()) as sc:
                        t0 = time.perf_counter()
                        fn(db)
                        dt = (time.perf_counter() - t0) * 1000.0
                    sql_count = sc.count
                else:
                    t0 = time.perf_counter()
                    fn(db)
                    dt = (time.perf_counter() - t0) * 1000.0
                latencies.append(round(dt, 2))
        s = sorted(latencies)
        results.append(
            {
                "name": name,
                "sql_count": sql_count,
                "avg_ms": round(sum(latencies) / len(latencies), 2),
                "p50_ms": s[len(s) // 2],
                "max_ms": s[-1],
            }
        )

    baseline_map: Dict[str, Dict[str, Any]] = {}
    if args.baseline:
        raw = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        items = raw.get("results", raw) if isinstance(raw, dict) else raw
        baseline_map = {r["name"]: r for r in items}

    if baseline_map:
        print(f"\n{'Endpoint':<44} {'SQL (B->A)':>12} {'Avg ms (B->A)':>20} {'Speedup':>9}")
        print("-" * 92)
        for r in results:
            b = baseline_map.get(r["name"], {})
            b_sql = b.get("sql_count", 0)
            b_avg = float(b.get("avg_ms") or 0.0)
            sp = f"{b_avg / r['avg_ms']:.2f}x" if b_avg > 0 and r["avg_ms"] > 0 else "-"
            print(f"{r['name']:<44} {b_sql:>4} -> {r['sql_count']:<4}  {b_avg:>7.2f} -> {r['avg_ms']:<7.2f}  {sp:>9}")
    else:
        print(f"\n{'Endpoint':<44} {'SQL#':>6} {'Avg(ms)':>9} {'P50(ms)':>9} {'Max(ms)':>9}")
        print("-" * 82)
        for r in results:
            print(f"{r['name']:<44} {r['sql_count']:>6} {r['avg_ms']:>9.2f} {r['p50_ms']:>9.2f} {r['max_ms']:>9.2f}")

    if args.save:
        dest = Path(args.save)
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "runs": args.runs,
            "date": target_day.isoformat(),
            "results": results,
        }
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[Saved] {dest}")
    return 0


def cmd_audit_indexes(args: argparse.Namespace) -> int:
    cfg = load_ops_config(args.ops_env)
    assert_local_pg_target(cfg.get_dev_pg())

    from sail.utils import read_env

    read_env("dev")

    from sqlalchemy import text
    from sail_server.db import get_db_session

    with get_db_session() as db:
        tables = db.execute(
            text(
                """
                SELECT relname, n_live_tup, seq_scan, idx_scan
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY n_live_tup DESC, seq_scan DESC
                LIMIT 20
                """
            )
        ).fetchall()
        indexes = db.execute(
            text(
                """
                SELECT tablename, indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname
                """
            )
        ).fetchall()

    idx_by_table: Dict[str, List[Tuple[str, str]]] = {}
    for tbl, name, idxdef in indexes:
        idx_by_table.setdefault(tbl, []).append((name, idxdef))

    print(f"\n{'Table':<28} {'Rows':>8} {'SeqScan':>8} {'IdxScan':>8} {'Idx#':>5}")
    print("-" * 64)
    for relname, live, seq_s, idx_s in tables:
        cnt = len(idx_by_table.get(relname, []))
        flag = "  <-- CHECK" if (live >= 500 and cnt <= 1) else ""
        print(f"{relname:<28} {live:>8} {seq_s:>8} {idx_s:>8} {cnt:>5}{flag}")

    # 检测同表同列重复索引
    dup_found = False
    for tbl, items in idx_by_table.items():
        by_cols: Dict[str, List[str]] = {}
        for name, idxdef in items:
            pos = idxdef.find("USING ")
            sig = idxdef[pos:] if pos >= 0 else idxdef
            by_cols.setdefault(sig, []).append(name)
        for sig, names in by_cols.items():
            if len(names) > 1:
                if not dup_found:
                    print("\n[Info] Duplicate index definitions detected (optional cleanup):")
                    dup_found = True
                print(f"  - {tbl}: {', '.join(names)} -> {sig}")
    return 0


def compare_snapshots(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """对比优化前后两份生产 Telemetry 快照的关键端点指标。"""
    b_api = (before.get("api_profile") or {}).get("data") or {}
    a_api = (after.get("api_profile") or {}).get("data") or {}

    def _index_eps(api_dict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for ep in (api_dict.get("top_slow_endpoints") or []) + (api_dict.get("top_called_endpoints") or []):
            out[f"{ep.get('method')} {ep.get('endpoint')}"] = ep
        return out

    b_eps = _index_eps(b_api)
    a_eps = _index_eps(a_api)
    common = sorted(set(b_eps) & set(a_eps))
    diffs = []
    for k in common:
        be, ae = b_eps[k], a_eps[k]
        b_avg = float(be.get("avg_ms") or 0.0)
        a_avg = float(ae.get("avg_ms") or 0.0)
        b_p95 = float(be.get("p95_ms") or 0.0)
        a_p95 = float(ae.get("p95_ms") or 0.0)
        delta_pct = round(((a_avg - b_avg) / b_avg) * 100.0, 1) if b_avg > 0 else 0.0
        diffs.append(
            {
                "endpoint": k,
                "before_avg_ms": b_avg,
                "after_avg_ms": a_avg,
                "before_p95_ms": b_p95,
                "after_p95_ms": a_p95,
                "avg_delta_pct": delta_pct,
                "before_err_rate": be.get("error_rate", 0.0),
                "after_err_rate": ae.get("error_rate", 0.0),
            }
        )
    diffs.sort(key=lambda x: x["avg_delta_pct"])
    return {
        "before_collected_at": before.get("collected_at"),
        "after_collected_at": after.get("collected_at"),
        "global_before": {
            "p50_ms": b_api.get("p50_ms", 0.0),
            "p95_ms": b_api.get("p95_ms", 0.0),
            "error_rate": b_api.get("error_rate", 0.0),
        },
        "global_after": {
            "p50_ms": a_api.get("p50_ms", 0.0),
            "p95_ms": a_api.get("p95_ms", 0.0),
            "error_rate": a_api.get("error_rate", 0.0),
        },
        "endpoint_diffs": diffs,
    }


def cmd_compare_snapshots(args: argparse.Namespace) -> int:
    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))
    diff = compare_snapshots(before, after)

    gb, ga = diff["global_before"], diff["global_after"]
    print("\n================ Snapshot Before vs After ================")
    print(f"Before: {diff['before_collected_at']} | After: {diff['after_collected_at']}")
    print(
        f"Global P50: {gb['p50_ms']}ms -> {ga['p50_ms']}ms | "
        f"P95: {gb['p95_ms']}ms -> {ga['p95_ms']}ms | "
        f"ErrRate: {gb['error_rate']*100:.2f}% -> {ga['error_rate']*100:.2f}%"
    )
    print(f"\n{'Endpoint':<48} {'Avg (B->A)':>18} {'P95 (B->A)':>18} {'Delta':>8}")
    print("-" * 96)
    for d in diff["endpoint_diffs"]:
        print(
            f"{d['endpoint']:<48} "
            f"{d['before_avg_ms']:>7.1f}->{d['after_avg_ms']:<7.1f}  "
            f"{d['before_p95_ms']:>7.1f}->{d['after_p95_ms']:<7.1f}  "
            f"{d['avg_delta_pct']:>+7.1f}%"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SailZen Telemetry-Driven Performance Analysis & Optimization Loop CLI"
    )
    parser.add_argument("--ops-env", default=None, help="运维配置文件路径（默认 .env.ops）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_col = sub.add_parser("collect", help="拉取只读 Telemetry 快照并输出诊断榜单")
    p_col.add_argument("--env", choices=("dev", "prod"), default="prod")
    p_col.add_argument("--url", default=None, help="覆盖服务基础 URL")
    p_col.add_argument("--hours", type=int, default=72, help="API 统计窗口（小时）")
    p_col.add_argument("--days", type=int, default=7, help="模块与 AI Trace 窗口（天）")
    p_col.add_argument("--out", default=None, help="快照保存路径（默认 data/perf_snapshots/...）")
    p_col.set_defaults(func=cmd_collect)

    p_bench = sub.add_parser("bench-local", help="在本地调试库执行 SQL 计数与延迟基准")
    p_bench.add_argument("--runs", type=int, default=5, help="每个用例测量轮次")
    p_bench.add_argument("--date", default=None, help="Rhythm 基准目标日期 YYYY-MM-DD")
    p_bench.add_argument("--baseline", default=None, help="基线 JSON 文件（输出 Before->After 对比）")
    p_bench.add_argument("--save", default=None, help="保存当前基准到 JSON 文件")
    p_bench.set_defaults(func=cmd_bench_local)

    p_idx = sub.add_parser("audit-indexes", help="审计本地调试库表行数、顺序扫描与索引覆盖")
    p_idx.set_defaults(func=cmd_audit_indexes)

    p_cmp = sub.add_parser("compare-snapshots", help="对比优化前后两份 Telemetry 快照")
    p_cmp.add_argument("before", help="优化前快照 JSON")
    p_cmp.add_argument("after", help="优化后快照 JSON")
    p_cmp.set_defaults(func=cmd_compare_snapshots)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_console_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
