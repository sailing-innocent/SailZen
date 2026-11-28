# -*- coding: utf-8 -*-
# @file telemetry.py
# @brief Telemetry, AI Trace & System Profile Pydantic DTOs
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""Telemetry & AI Trace REST DTO 定义。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── AI Trace DTOs ────────────────────────────────────────────────────────────


class AITraceSpanDTO(BaseModel):
    span_id: str
    parent_span_id: Optional[str] = None
    seq: int = 0
    stage: str
    name: str
    status: str = "ok"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_ms: float = 0.0
    input_summary: str = ""
    output_summary: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class AITraceIngestRequest(BaseModel):
    trace_id: str
    service: str = "sailtick"
    tick_id: str = ""
    slot: str = ""
    tick_date: str = ""
    trigger_source: str = "scheduler"
    mode: str = "live"
    status: str = "completed"
    plan_source: str = "none"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_ms: float = 0.0
    llm_calls_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    tickets_created: int = 0
    tickets_throttled: int = 0
    actions_executed: int = 0
    actions_failed: int = 0
    summary: str = ""
    error: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    spans: List[AITraceSpanDTO] = Field(default_factory=list)


class AITraceSummaryResponse(BaseModel):
    id: int
    trace_id: str
    service: str
    tick_id: str
    slot: str
    tick_date: str
    trigger_source: str
    mode: str
    status: str
    plan_source: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_ms: float
    llm_calls_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    tickets_created: int
    tickets_throttled: int
    actions_executed: int
    actions_failed: int
    summary: str
    error: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    span_count: int = 0


class AITraceDetailResponse(AITraceSummaryResponse):
    spans: List[AITraceSpanDTO] = Field(default_factory=list)


class AITraceSlotStats(BaseModel):
    slot: str
    total: int
    completed: int
    failed: int
    llm_plans: int
    fallback_plans: int
    avg_duration_ms: float
    total_tokens: int
    total_cost_usd: float


class AITraceDailyTrendPoint(BaseModel):
    date: str
    total: int
    completed: int
    failed: int
    fallback: int
    tokens: int
    cost_usd: float


class AITraceStatsResponse(BaseModel):
    window_days: int
    service: str
    total_traces: int
    completed_count: int
    failed_count: int
    paused_count: int
    skipped_count: int
    success_rate: float
    llm_plan_count: int
    fallback_plan_count: int
    fallback_error_count: int
    fallback_rate: float
    avg_duration_ms: float
    avg_llm_latency_ms: float
    total_tokens: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_usd: float
    total_tickets_created: int
    total_tickets_throttled: int
    total_actions_executed: int
    total_actions_failed: int
    by_slot: List[AITraceSlotStats] = Field(default_factory=list)
    daily_trend: List[AITraceDailyTrendPoint] = Field(default_factory=list)


# ── Client Telemetry Events DTOs ─────────────────────────────────────────────


class ClientEventItem(BaseModel):
    category: str  # page_view | web_vital | client_error | system
    module: str = "web"
    name: str
    client_source: str = "web"
    duration_ms: Optional[float] = None
    status_code: Optional[int] = None
    value: Optional[float] = None
    detail: Dict[str, Any] = Field(default_factory=dict)


class ClientEventBatchRequest(BaseModel):
    events: List[ClientEventItem] = Field(default_factory=list)


# ── API Performance Profile DTOs ─────────────────────────────────────────────


class ModuleApiMetric(BaseModel):
    module: str
    req_count: int
    err_4xx: int
    err_5xx: int
    error_rate: float
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    bytes_out: int


class EndpointApiMetric(BaseModel):
    module: str
    method: str
    endpoint: str
    req_count: int
    err_4xx: int
    err_5xx: int
    error_rate: float
    avg_ms: float
    p95_ms: float
    max_ms: float
    bytes_out: int


class NotableEventItem(BaseModel):
    id: Optional[int] = None
    category: str
    module: str
    name: str
    client_source: str
    duration_ms: Optional[float] = None
    status_code: Optional[int] = None
    value: Optional[float] = None
    detail: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ApiProfileResponse(BaseModel):
    window_hours: int
    total_requests: int
    total_4xx: int
    total_5xx: int
    error_rate: float
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    total_bytes_out: int
    slow_threshold_ms: float
    slow_requests_count: int
    by_module: List[ModuleApiMetric] = Field(default_factory=list)
    by_client: Dict[str, int] = Field(default_factory=dict)
    top_slow_endpoints: List[EndpointApiMetric] = Field(default_factory=list)
    top_called_endpoints: List[EndpointApiMetric] = Field(default_factory=list)
    top_error_endpoints: List[EndpointApiMetric] = Field(default_factory=list)
    recent_notable: List[NotableEventItem] = Field(default_factory=list)


# ── Module Business & Usage Profile DTOs ─────────────────────────────────────


class ModuleProfileCard(BaseModel):
    key: str
    label: str
    status: str = "healthy"  # healthy | warning | idle
    summary: str = ""
    metrics: Dict[str, Any] = Field(default_factory=dict)
    api_requests_window: int = 0
    api_p95_ms: float = 0.0
    api_error_rate: float = 0.0


class PageUsageItem(BaseModel):
    path: str
    views: int
    avg_dwell_sec: float
    total_dwell_sec: float


class ModulesProfileResponse(BaseModel):
    generated_at: datetime
    window_days: int
    modules: List[ModuleProfileCard] = Field(default_factory=list)
    page_usage: List[PageUsageItem] = Field(default_factory=list)
    recent_client_errors: List[NotableEventItem] = Field(default_factory=list)


class SystemRuntimeProfileResponse(BaseModel):
    generated_at: datetime
    started_at: str
    uptime_seconds: float
    python_version: str
    db_backend: str
    memory_rss_mb: Optional[float] = None
    data_dir: str
    data_dir_size_mb: float
    online_ws_devices: List[str] = Field(default_factory=list)
    total_requests_since_boot: int
    total_errors_since_boot: int
    unflushed_buckets: int
    last_flush_at: Optional[str] = None
    table_counts: Dict[str, int] = Field(default_factory=dict)


class SailTickTriggerRequest(BaseModel):
    slot: str
    idempotency_suffix: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
