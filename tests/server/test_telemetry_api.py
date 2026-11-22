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
    assert infer_client_source([(b"user-agent", b"okhttp/4.12.0")]) == "android"
    assert infer_client_source([(b"user-agent", b"python-httpx/0.27")]) == "sailtick"
    assert infer_client_source([(b"x-sailzen-client", b"web")]) == "web"


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
