# -*- coding: utf-8 -*-
# @file test_perf_optimizations.py
# @brief 回归测试：Finance Batch Stats / Text Works N+1 消除 / Rhythm Review 批处理优化
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import event

from sail_server.model.finance.transaction import (
    get_transaction_stats_batch_impl,
    get_transaction_stats_impl,
)
from sail_server.model.rhythm import get_dashboard_impl
from sail_server.model.text import get_works_impl
from sailzen_orm.finance import Transaction
from sailzen_orm.text import DocumentNode, Edition, Work

pytestmark = pytest.mark.server


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


def test_finance_stats_batch_equivalence_and_single_sql(db):
    now = datetime(2026, 11, 15, 12, 0, 0)
    rows = [
        Transaction(
            from_acc_id=1,
            to_acc_id=-1,
            value="45.50 CNY",
            prev_value="0.0",
            description="午餐牛肉饭",
            tags="餐饮,日用消耗",
            state=3,
            htime=datetime(2026, 11, 10, 12, 0, 0),
            ctime=now,
            mtime=now,
        ),
        Transaction(
            from_acc_id=1,
            to_acc_id=-1,
            value="1200.00",
            prev_value="0.0",
            description="大宗电器采购",
            tags="大宗电器,大宗收支",
            state=3,
            htime=datetime(2026, 11, 12, 18, 0, 0),
            ctime=now,
            mtime=now,
        ),
        Transaction(
            from_acc_id=-1,
            to_acc_id=1,
            value="5000.00",
            prev_value="0.0",
            description="工资收入",
            tags="收入",
            state=3,
            htime=datetime(2026, 11, 1, 9, 0, 0),
            ctime=now,
            mtime=now,
        ),
        # 软删除（deprecated bit 6）应被排除
        Transaction(
            from_acc_id=1,
            to_acc_id=-1,
            value="999.00",
            prev_value="0.0",
            description="已删除测试",
            tags="餐饮",
            state=(1 << 6) | 3,
            htime=datetime(2026, 11, 11, 9, 0, 0),
            ctime=now,
            mtime=now,
        ),
    ]
    db.add_all(rows)
    db.commit()

    t_start = datetime(2026, 11, 1, 0, 0, 0).timestamp()
    t_mid = datetime(2026, 11, 11, 0, 0, 0).timestamp()
    t_end = datetime(2026, 11, 30, 23, 59, 59).timestamp()

    queries = [
        {"id": "q_all", "from_time": t_start, "to_time": t_end, "return_list": False},
        {"id": "q_food", "from_time": t_start, "to_time": t_end, "tags": "餐饮", "tag_op": "or", "return_list": False},
        {"id": "q_and", "from_time": t_start, "to_time": t_end, "tags": "大宗电器,大宗收支", "tag_op": "and", "return_list": False},
        {"id": "q_or", "from_time": t_start, "to_time": t_end, "tags": "餐饮,大宗电器", "tag_op": "or", "return_list": False},
        {"id": "q_subrange", "from_time": t_mid, "to_time": t_end, "return_list": False},
        {"id": "q_desc", "description": "牛肉", "return_list": False},
    ]

    with _SqlCounter(db.get_bind()) as counter:
        batch_res = get_transaction_stats_batch_impl(db, queries)

    # 6 条批处理统计查询合并为单次 SQL
    assert counter.count == 1

    # 与单条实现逐项比对 100% 一致
    for q, item in zip(queries, batch_res):
        tags_str = q.get("tags", "")
        tag_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
        expected = get_transaction_stats_impl(
            db=db,
            from_time=q.get("from_time"),
            to_time=q.get("to_time"),
            _tags=tag_list,
            tag_op=q.get("tag_op", "and"),
            _desc=q.get("description"),
            return_list=False,
        )
        assert item["id"] == q["id"]
        assert item["stats"] == expected


def test_get_works_eliminates_n_plus_1(db):
    for i in range(6):
        w = Work(slug=f"work-{i}", title=f"Work {i}")
        db.add(w)
        db.flush()
        ed = Edition(work_id=w.id, edition_name="v1", char_count=1000 * (i + 1))
        db.add(ed)
        db.flush()
        for c in range(i + 1):
            db.add(
                DocumentNode(
                    edition_id=ed.id,
                    node_type="chapter",
                    sort_index=c,
                    depth=1,
                    path=f"{i}.{c}",
                    title=f"Ch {c}",
                    raw_text="abc",
                )
            )
    db.commit()

    with _SqlCounter(db.get_bind()) as counter:
        works = get_works_impl(db, skip=0, limit=20)

    assert len(works) == 6
    # O(1) 常量批量查询，零 N+1：
    # 1(works) + 1(editions agg) + 1(chapters agg) + 1(progress) + 1(topic links) + 1(assets agg) = 6 SQL
    assert counter.count == 6
    by_slug = {w.slug: w for w in works}
    assert by_slug["work-0"].chapter_count == 1
    assert by_slug["work-5"].chapter_count == 6
    assert by_slug["work-5"].total_chars == 6000


def test_rhythm_v2_dashboard_query_budget(db):
    target = date(2026, 11, 22)
    d1 = get_dashboard_impl(db, target)
    assert d1.degraded == []

    # 极简 Rhythm v2 聚合查询轻量无 N+1 放大
    with _SqlCounter(db.get_bind()) as counter:
        d2 = get_dashboard_impl(db, target)

    assert d2.degraded == []
    assert counter.count <= 10


def test_perf_loop_analyze_and_compare_snapshots():
    from scripts.ops.perf_loop import analyze_snapshot, compare_snapshots

    snap_before = {
        "env": "prod",
        "collected_at": "2026-11-24T00:00:00",
        "api_profile": {
            "data": {
                "total_requests": 1000,
                "total_4xx": 4,
                "total_5xx": 0,
                "error_rate": 0.004,
                "avg_ms": 30.0,
                "p50_ms": 26.0,
                "p95_ms": 28.0,
                "p99_ms": 25000.0,
                "max_ms": 25000.0,
                "by_module": [
                    {"module": "health", "p50_ms": 3.2},
                    {"module": "tick", "p50_ms": 4.6},
                ],
                "top_slow_endpoints": [
                    {
                        "method": "GET",
                        "endpoint": "/api/v1/app/release/download/SailZen-0.2.0.apk",
                        "req_count": 1,
                        "err_4xx": 0,
                        "err_5xx": 0,
                        "error_rate": 0.0,
                        "avg_ms": 25000.0,
                        "p95_ms": 25000.0,
                        "max_ms": 25000.0,
                        "bytes_out": 13_000_000,
                    },
                    {
                        "method": "POST",
                        "endpoint": "/api/v1/finance/transaction/stats/batch",
                        "req_count": 2,
                        "err_4xx": 0,
                        "err_5xx": 0,
                        "error_rate": 0.0,
                        "avg_ms": 248.0,
                        "p95_ms": 248.0,
                        "max_ms": 289.0,
                        "bytes_out": 50000,
                    },
                    {
                        "method": "POST",
                        "endpoint": "/api/v1/rhythm/affair/{id}/state",
                        "req_count": 10,
                        "err_4xx": 4,
                        "err_5xx": 0,
                        "error_rate": 0.4,
                        "avg_ms": 10.0,
                        "p95_ms": 15.0,
                        "max_ms": 19.0,
                        "bytes_out": 3000,
                    },
                ],
                "top_called_endpoints": [],
            }
        },
        "modules_profile": {"data": {"recent_client_errors": [{"name": "409 err", "detail": {"path": "/main"}}]}},
        "runtime_profile": {"data": {"memory_rss_mb": 170.0, "uptime_seconds": 500.0}},
        "ai_traces_stats": {"data": {"total_traces": 6, "success_rate": 1.0}},
    }

    report = analyze_snapshot(snap_before)
    assert len(report["instrument_warnings"]) == 2
    assert len(report["error_endpoints"]) == 1
    assert report["business_slow_endpoints"][0]["endpoint"] == "/api/v1/finance/transaction/stats/batch"
    assert len(report["binary_downloads"]) == 1

    snap_after = {
        "env": "prod",
        "collected_at": "2026-11-24T12:00:00",
        "api_profile": {
            "data": {
                "p50_ms": 4.5,
                "p95_ms": 18.0,
                "error_rate": 0.0,
                "top_slow_endpoints": [
                    {
                        "method": "POST",
                        "endpoint": "/api/v1/finance/transaction/stats/batch",
                        "req_count": 5,
                        "avg_ms": 12.0,
                        "p95_ms": 15.0,
                        "error_rate": 0.0,
                    }
                ],
                "top_called_endpoints": [],
            }
        },
    }
    diff = compare_snapshots(snap_before, snap_after)
    assert diff["global_after"]["p50_ms"] == 4.5
    assert diff["endpoint_diffs"][0]["avg_delta_pct"] < -90.0

