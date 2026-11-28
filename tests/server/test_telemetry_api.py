# -*- coding: utf-8 -*-
# @file test_telemetry_api.py
# @brief SailZen Telemetry, AI Trace & System Profile 单元测试
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------

from __future__ import annotations

from datetime import datetime

import pytest

from sail_server.application.dto.telemetry import (
    AITraceIngestRequest,
    AITraceSpanDTO,
    ClientEventBatchRequest,
    ClientEventItem,
)
from sail_server.model.telemetry import (
    get_ai_trace_detail_impl,
    get_ai_trace_stats_impl,
    get_api_profile_impl,
    get_modules_profile_impl,
    get_system_runtime_profile_impl,
    ingest_ai_trace_impl,
    ingest_client_events_impl,
    list_ai_traces_impl,
)
from sail_server.utils.telemetry_collector import (
    get_telemetry_collector,
    infer_client_source,
    normalize_api_path,
)

pytestmark = pytest.mark.server


def test_normalize_api_path_and_client_inference():
    assert normalize_api_path("/api/v1/tick/tickets/42/reply") == (
        "tick",
        "/api/v1/tick/tickets/{id}/reply",
    )
    assert normalize_api_path("/api/v1/tick/reports/2026-11-23") == (
        "tick",
        "/api/v1/tick/reports/{date}",
    )
    assert normalize_api_path("/api/v1/file-storage/list") == (
        "file_storage",
        "/api/v1/file-storage/list",
    )
    assert normalize_api_path(
        "/api/v1/app/release/download/SailZen-0.2.0-vc4-release-11232256.apk"
    ) == (
        "app_release",
        "/api/v1/app/release/download/{filename}",
    )
    assert normalize_api_path(
        "/api/v1/workbench/release/download/sailzen-workbench-0.3.2.vsix"
    ) == (
        "workbench",
        "/api/v1/workbench/release/download/{filename}",
    )
    assert infer_client_source([(b"user-agent", b"okhttp/4.12.0")]) == "android"
    assert infer_client_source([(b"user-agent", b"python-httpx/0.27")]) == "sailtick"
    assert infer_client_source([(b"x-sailzen-client", b"web")]) == "web"
    assert infer_client_source([(b"x-sailzen-client", b"vscode")]) == "vscode"


def test_ai_trace_ingest_query_detail_and_stats(db):
    now = datetime.now()
    req1 = AITraceIngestRequest(
        trace_id="trace_abc_001",
        service="sailtick",
        tick_id="tick_001",
        slot="morning_checkin",
        tick_date=now.strftime("%Y-%m-%d"),
        trigger_source="scheduler",
        mode="live",
        status="completed",
        plan_source="llm",
        started_at=now,
        ended_at=now,
        duration_ms=1450.5,
        llm_calls_count=1,
        prompt_tokens=1200,
        completion_tokens=300,
        total_tokens=1500,
        cost_usd=0.0025,
        tickets_created=1,
        tickets_throttled=0,
        actions_executed=2,
        actions_failed=0,
        summary="早间巡检完成",
        spans=[
            AITraceSpanDTO(
                span_id="sp_1",
                seq=0,
                stage="wake",
                name="WAKE",
                status="ok",
                duration_ms=12.0,
            ),
            AITraceSpanDTO(
                span_id="sp_2",
                parent_span_id="sp_1",
                seq=1,
                stage="llm_call",
                name="LLM 规划",
                status="ok",
                duration_ms=1200.0,
                payload={"model": "deepseek-chat", "prompt_text": "hello", "response_text": "{}"},
            ),
        ],
    )
    saved = ingest_ai_trace_impl(db, req1)
    assert saved.trace_id == "trace_abc_001"
    assert saved.span_count == 2

    # 幂等覆盖更新
    req1.summary = "早间巡检完成(更新)"
    ingest_ai_trace_impl(db, req1)

    req2 = AITraceIngestRequest(
        trace_id="trace_abc_002",
        service="sailtick",
        tick_id="tick_002",
        slot="midday_checkin",
        tick_date=now.strftime("%Y-%m-%d"),
        mode="shadow",
        status="completed",
        plan_source="fallback_error",
        started_at=now,
        ended_at=now,
        duration_ms=210.0,
        error="LLM timeout",
        spans=[],
    )
    ingest_ai_trace_impl(db, req2)

    listed = list_ai_traces_impl(db, service="sailtick", days=7, limit=20)
    assert len(listed) == 2

    detail = get_ai_trace_detail_impl(db, "trace_abc_001")
    assert detail is not None
    assert detail.summary == "早间巡检完成(更新)"
    assert len(detail.spans) == 2
    assert detail.spans[1].stage == "llm_call"

    stats = get_ai_trace_stats_impl(db, service="sailtick", days=7)
    assert stats.total_traces == 2
    assert stats.completed_count == 2
    assert stats.llm_plan_count == 1
    assert stats.fallback_error_count == 1
    assert stats.fallback_rate == 0.5
    assert stats.avg_llm_latency_ms == 1200.0
    assert stats.total_tokens == 1500
    assert len(stats.by_slot) == 2


def test_api_profile_collector_and_modules_profile(db, rhythm_engine):
    collector = get_telemetry_collector()
    collector.reset_for_tests()

    # 模拟多次 API 请求（含慢请求和 500）
    collector.record_request(
        method="GET",
        path="/api/v1/health/body-data",
        status_code=200,
        duration_ms=45.0,
        bytes_out=2048,
        headers=[(b"x-sailzen-client", b"web")],
    )
    collector.record_request(
        method="POST",
        path="/api/v1/finance/transaction",
        status_code=200,
        duration_ms=420.0,
        bytes_out=512,
        headers=[(b"user-agent", b"okhttp/4.12")],
    )
    collector.record_request(
        method="GET",
        path="/api/v1/rhythm/affair/99",
        status_code=500,
        duration_ms=80.0,
        bytes_out=128,
        headers=[(b"x-sailzen-client", b"web")],
        error_detail="RuntimeError: boom",
    )

    # 不刷盘也能实时看到（内存合并）
    live_prof = get_api_profile_impl(db, window_hours=24)
    assert live_prof.total_requests == 3
    assert live_prof.total_5xx == 1
    assert live_prof.slow_requests_count == 1
    assert live_prof.by_client["web"] == 2
    assert live_prof.by_client["android"] == 1

    # 刷盘后再查，数量不重复
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=rhythm_engine)
    flushed = collector.flush_to_db(SessionLocal)
    assert flushed >= 3

    persisted_prof = get_api_profile_impl(db, window_hours=24)
    assert persisted_prof.total_requests == 3
    assert persisted_prof.total_5xx == 1
    assert len(persisted_prof.recent_notable) == 2

    # 前端埋点事件批量写入
    accepted = ingest_client_events_impl(
        db,
        ClientEventBatchRequest(
            events=[
                ClientEventItem(
                    category="page_view", module="health", name="/health", duration_ms=12500
                ),
                ClientEventItem(
                    category="page_view", module="tick", name="/tick", duration_ms=8000
                ),
                ClientEventItem(
                    category="client_error",
                    module="web",
                    name="TypeError: test err",
                    detail={"path": "/health"},
                ),
            ]
        ),
    )
    assert accepted == 3

    mod_prof = get_modules_profile_impl(db, window_days=7)
    mod_keys = {m.key for m in mod_prof.modules}
    for expected_key in ("finance", "health", "rhythm", "tick", "reminder", "text", "necessity"):
        assert expected_key in mod_keys
    assert len(mod_prof.page_usage) == 2
    assert len(mod_prof.recent_client_errors) == 1

    rt_prof = get_system_runtime_profile_impl(db)
    assert rt_prof.db_backend == "sqlite"
    assert rt_prof.table_counts["sys_telemetry_events"] >= 3
    collector.reset_for_tests()


def test_weighted_quantile_resists_binary_download_outlier(db):
    """单个大文件下载（25s）不应污染全局 P50/P95，也不应误报 api_slow 告警。"""
    collector = get_telemetry_collector()
    collector.reset_for_tests()

    for _ in range(100):
        collector.record_request(
            method="GET",
            path="/api/v1/health/dashboard",
            status_code=200,
            duration_ms=5.0,
            bytes_out=512,
            headers=[(b"x-sailzen-client", b"web")],
        )
    collector.record_request(
        method="GET",
        path="/api/v1/app/release/download/SailZen-0.2.0-vc4.apk",
        status_code=200,
        duration_ms=25000.0,
        bytes_out=13_000_000,
        headers=[(b"user-agent", b"okhttp/4.12")],
    )
    collector.record_request(
        method="GET",
        path="/api/v1/app/release/latest.apk",
        status_code=200,
        duration_ms=26000.0,
        bytes_out=13_000_000,
        headers=[(b"user-agent", b"okhttp/4.12")],
    )
    collector.record_request(
        method="GET",
        path="/api/v1/workbench/release/download/sailzen-workbench-0.3.2.vsix",
        status_code=200,
        duration_ms=1200.0,
        bytes_out=250_000,
        headers=[(b"x-sailzen-client", b"vscode")],
    )

    prof = get_api_profile_impl(db, window_hours=24)
    assert prof.total_requests == 103
    assert prof.p50_ms == 5.0
    assert prof.p95_ms == 5.0
    assert prof.max_ms == 26000.0
    # 二进制下载不触发常规 api_slow 误报
    assert prof.slow_requests_count == 0
    collector.reset_for_tests()


def test_top_error_endpoints_surfaces_hidden_4xx(db):
    """低频且极快但 100% 返回 400 的端点必须出现在 top_error_endpoints 中。"""
    collector = get_telemetry_collector()
    collector.reset_for_tests()

    # 制造 20 个更高频、更慢的 200 端点，试图把错误端点挤出 top_slow / top_called
    for i in range(20):
        for _ in range(5):
            collector.record_request(
                method="GET",
                path=f"/api/v1/health/metric-{i}",
                status_code=200,
                duration_ms=30.0 + i,
                bytes_out=256,
                headers=[(b"x-sailzen-client", b"web")],
            )

    # 低频且极快（3ms）但 100% 失败的 ai-sync 端点
    for _ in range(3):
        collector.record_request(
            method="POST",
            path="/api/v1/rhythm/timeline/ai-sync",
            status_code=400,
            duration_ms=3.0,
            bytes_out=120,
            headers=[(b"x-sailzen-client", b"sailtick")],
        )

    prof = get_api_profile_impl(db, window_hours=24)
    err_eps = [e.endpoint for e in prof.top_error_endpoints]
    assert "/api/v1/rhythm/timeline/ai-sync" in err_eps
    top_err = prof.top_error_endpoints[0]
    assert top_err.err_4xx == 3
    assert top_err.error_rate == 1.0
    collector.reset_for_tests()


def test_ai_timeline_block_type_alias_coercion():
    """LLM 输出 routine/exercise/未知 block_type 时应容错映射，不再触发 400 Bad Request。"""
    from sail_server.application.dto.rhythm import AITimelineBlockInput, BlockType

    b_routine = AITimelineBlockInput(title="午饭", start="12:00", end="13:00", block_type="routine")
    assert b_routine.block_type == BlockType.HABIT

    b_dining = AITimelineBlockInput(title="晚饭", start="18:30", end="19:15", block_type="Dining")
    assert b_dining.block_type == BlockType.MEAL

    b_unknown = AITimelineBlockInput(title="杂项", start="20:00", end="20:30", block_type="non_existent_kind")
    assert b_unknown.block_type == BlockType.LIGHT

    b_exact = AITimelineBlockInput(title="推进", start="10:00", end="11:30", block_type="focus")
    assert b_exact.block_type == BlockType.FOCUS
