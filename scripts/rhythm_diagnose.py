# -*- coding: utf-8 -*-
# @file rhythm_diagnose.py
# @brief Rhythm 模块逐端点诊断脚本（对运行中的 sail_server 逐步探测）
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""Rhythm 模块诊断脚本。

对运行中的 sail_server 顺序请求核心端点，逐步打印 ``状态码 / 耗时 / 摘要``，
用于 I-01 类故障（空库启动后首访 500 / 子模块拖垮 dashboard）的现场定位。

探测步骤（均为只读 GET）：
  1. /dashboard                聚合入口（含 degraded 降级字段）
  2. /timeline/day             日时间线
  3. /review/day               日评分
  4. /review/week              周评分
  5. /checkin/today            今日打卡
  6. /energy/profile           精力画像
  7. /plan/conflicts           侵占报告
  8. /affair/?state=INBOX      INBOX 列表
  9. /affair/?urgency_ddl_after/before  今日截止列表
 10. /affair/?urgency_ddl_before=now    逾期列表

用法：
  uv run python scripts/rhythm_diagnose.py                # 默认 http://127.0.0.1:8000
  uv run python scripts/rhythm_diagnose.py --url http://127.0.0.1:18974
  SAILZEN_API_TOKEN=xxx uv run python scripts/rhythm_diagnose.py

退出码：全部 2xx → 0；任一失败 → 1。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

BASE_DEFAULT = os.environ.get("SAIL_SERVER_URL", "http://127.0.0.1:8000")
TOKEN = os.environ.get("SAILZEN_API_TOKEN", "")


def _headers() -> dict:
    h = {"Accept": "application/json"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def _get(url: str, timeout: float = 15.0):
    """返回 (status, elapsed_ms, parsed_json_or_None)。"""
    started = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        status = e.code
    except Exception as e:
        return -1, int((time.perf_counter() - started) * 1000), {"error": str(e)}
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    try:
        parsed = json.loads(body)
    except Exception:
        parsed = {"raw": body[:200]}
    return status, elapsed_ms, parsed


def _summarize(step: str, data) -> str:
    """为每个端点提取一行关键摘要。"""
    if not isinstance(data, dict):
        return ""
    try:
        if step == "dashboard":
            parts = [f"degraded={data.get('degraded') or '[]'}"]
            timeline = data.get("timeline") or {}
            if timeline:
                parts.append(f"blocks={len(timeline.get('blocks') or [])}")
            for key in ("inbox_summary", "overdue_summary", "today_due_summary"):
                parts.append(f"{key.split('_')[0]}={len(data.get(key) or [])}")
            profile = data.get("energy_profile") or {}
            parts.append(f"profile.is_default={profile.get('is_default')}")
            return ", ".join(parts)
        if step == "timeline":
            return f"plan_version={data.get('plan_version')}, blocks={len(data.get('blocks') or [])}"
        if step in ("review_day", "review_week"):
            return f"scope={data.get('scope')}, score={data.get('rhythm_score')}"
        if step == "checkin":
            return (
                f"precepts={len(data.get('precepts') or [])}, "
                f"habits={len(data.get('habits') or [])}"
            )
        if step == "profile":
            return f"name={data.get('name')}, is_default={data.get('is_default')}"
        if step == "conflicts":
            return f"encroachments={len(data.get('encroachments') or [])}"
        if step.startswith("affair"):
            items = (
                data
                if isinstance(data, list)
                else (data.get("affairs") or data.get("items") or [])
            )
            return f"count={len(items)}"
    except Exception:
        pass
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Rhythm 模块逐端点诊断")
    parser.add_argument("--url", default=BASE_DEFAULT, help="sail_server 基础地址")
    parser.add_argument("--date", default=date.today().isoformat(), help="探测日期")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    d = args.date
    today = date.today()
    day_start = datetime.combine(today, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    steps = [
        ("dashboard", f"{base}/api/v1/rhythm/dashboard?date={d}"),
        ("timeline", f"{base}/api/v1/rhythm/timeline/day?date={d}"),
        ("review_day", f"{base}/api/v1/rhythm/review/day?date={d}"),
        ("review_week", f"{base}/api/v1/rhythm/review/week?span={d}"),
        ("checkin", f"{base}/api/v1/rhythm/checkin/today?date={d}"),
        ("profile", f"{base}/api/v1/rhythm/energy/profile"),
        ("conflicts", f"{base}/api/v1/rhythm/plan/conflicts?date={d}"),
        ("affair_inbox", f"{base}/api/v1/rhythm/affair/?state=INBOX&limit=5"),
        (
            "affair_today_due",
            f"{base}/api/v1/rhythm/affair/?urgency_ddl_after={day_start.isoformat()}"
            f"&urgency_ddl_before={day_end.isoformat()}&limit=5",
        ),
        (
            "affair_overdue",
            f"{base}/api/v1/rhythm/affair/?urgency_ddl_before={datetime.now().isoformat()}"
            f"&limit=5",
        ),
    ]

    print(f"[diagnose] target={base} date={d}")
    if TOKEN:
        print("[diagnose] Authorization: Bearer <token>")

    failures = 0
    total_ms = 0
    results = []
    for name, url in steps:
        status, elapsed_ms, data = _get(url)
        total_ms += elapsed_ms
        ok = 200 <= status < 300
        if not ok:
            failures += 1
        results.append((name, status, elapsed_ms, data))
        mark = "OK " if ok else "FAIL"
        detail = _summarize(name, data)
        line = f"[{mark}] {name:<16} {status:>4} {elapsed_ms:>6}ms"
        if detail:
            line += f"  {detail}"
        if not ok and isinstance(data, dict) and data.get("error"):
            line += f"  error={data['error']}"
        print(line)

    print("-" * 72)
    print(
        f"[diagnose] {len(steps) - failures}/{len(steps)} 通过, "
        f"累计耗时 {total_ms}ms"
    )
    if failures:
        print("[diagnose] 存在失败端点，请结合上方状态码与服务端日志定位")
        return 1
    print("[diagnose] all green ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
