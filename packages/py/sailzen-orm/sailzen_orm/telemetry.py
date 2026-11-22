# -*- coding: utf-8 -*-
# @file telemetry.py
# @brief Telemetry, AI Trace & System Profile ORM Models
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""SailZen 线上埋点、AI 全链路 Trace 与系统 Profile ORM 模型。

表结构：
- sys_ai_traces          AI 执行主链路记录（SailTick / 未来其他 Agent 共用）
- sys_ai_trace_spans     AI 执行阶段与 LLM/工具调用 Span 明细
- sys_api_metric_buckets HTTP API 小时级聚合性能指标（QPS / 错误 / P50 / P95 / P99）
- sys_telemetry_events   离散可观测事件（慢请求、5xx、前端页面访问与停留、JS 异常等）

时间戳统一 naive TIMESTAMP（服务器本地时间，与 SailZen 其他模块一致）。
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    func,
)

from sailzen_orm.orm_base import ORMBase
from sailzen_orm.types import JSONB


class SysAITrace(ORMBase):
    """AI 执行全链路 Trace（每次 SailTick 唤醒或 Agent 任务一条）。"""

    __tablename__ = "sys_ai_traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String(64), unique=True, nullable=False, index=True)
    # 来源服务：sailtick | sail_server | dag | cli
    service = Column(String(32), default="sailtick", nullable=False, index=True)
    # 关联业务实例（如 SailTick 的 st_ticks.id）
    tick_id = Column(String(64), default="", index=True)
    slot = Column(String(64), default="", index=True)
    tick_date = Column(String(16), default="", index=True)
    # 触发源：scheduler | manual | catch_up | api | test
    trigger_source = Column(String(32), default="scheduler")
    # 运行模式：off | shadow | canary | live
    mode = Column(String(16), default="live")
    # 终态：running | completed | failed | skipped | paused | interrupted
    status = Column(String(24), default="running", index=True)
    # 规划来源：llm | fallback | fallback_error | none
    plan_source = Column(String(32), default="none", index=True)
    started_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp(), index=True
    )
    ended_at = Column(TIMESTAMP, nullable=True)
    duration_ms = Column(Float, default=0.0)
    # LLM 消耗统计
    llm_calls_count = Column(Integer, default=0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    # 产物与执行统计
    tickets_created = Column(Integer, default=0)
    tickets_throttled = Column(Integer, default=0)
    actions_executed = Column(Integer, default=0)
    actions_failed = Column(Integer, default=0)
    # 摘要与错误
    summary = Column(Text, default="")
    error = Column(Text, nullable=True)
    # 扩展上下文（handoff_path, canary_downgraded, plan_summary, deps 等）
    meta = Column(JSONB, default=dict)
    created_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp()
    )

    __table_args__ = (
        Index("ix_sys_ai_traces_svc_started", "service", "started_at"),
        Index("ix_sys_ai_traces_status_started", "status", "started_at"),
    )


class SysAITraceSpan(ORMBase):
    """AI Trace 子阶段与调用 Span（WAKE / SCAN / PLAN / LLM / THROTTLE / WORK / HANDOFF）。"""

    __tablename__ = "sys_ai_trace_spans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String(64), nullable=False, index=True)
    span_id = Column(String(64), nullable=False)
    parent_span_id = Column(String(64), nullable=True)
    seq = Column(Integer, default=0)
    # wake | scan | plan | llm_call | throttle | work | ticket_emit | work_action | handoff | canary
    stage = Column(String(32), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    # ok | error | degraded | skipped
    status = Column(String(24), default="ok")
    started_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp()
    )
    ended_at = Column(TIMESTAMP, nullable=True)
    duration_ms = Column(Float, default=0.0)
    input_summary = Column(Text, default="")
    output_summary = Column(Text, default="")
    # 结构化载荷（例如 llm_call 的 prompt_text/response_text/reasoning/tokens/model 等）
    payload = Column(JSONB, default=dict)
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_sys_ai_trace_spans_trace_seq", "trace_id", "seq"),
    )


class SysApiMetricBucket(ORMBase):
    """HTTP API 小时级聚合性能与使用指标。"""

    __tablename__ = "sys_api_metric_buckets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bucket_hour = Column(TIMESTAMP, nullable=False, index=True)
    module = Column(String(32), nullable=False, index=True)
    method = Column(String(12), nullable=False)
    endpoint = Column(String(256), nullable=False)
    # web | android | sailtick | cli | other
    client_source = Column(String(24), default="other", nullable=False)
    req_count = Column(Integer, default=0)
    err_4xx = Column(Integer, default=0)
    err_5xx = Column(Integer, default=0)
    total_ms = Column(Float, default=0.0)
    max_ms = Column(Float, default=0.0)
    p50_ms = Column(Float, default=0.0)
    p95_ms = Column(Float, default=0.0)
    p99_ms = Column(Float, default=0.0)
    bytes_out = Column(Integer, default=0)
    updated_at = Column(
        TIMESTAMP,
        default=datetime.now,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        UniqueConstraint(
            "bucket_hour",
            "module",
            "method",
            "endpoint",
            "client_source",
            name="uq_sys_api_metric_bucket_key",
        ),
        Index("ix_sys_api_metric_buckets_mod_hour", "module", "bucket_hour"),
    )


class SysTelemetryEvent(ORMBase):
    """离散可观测与埋点事件（慢请求、5xx、前端页面访问与停留、前端异常等）。"""

    __tablename__ = "sys_telemetry_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # api_slow | api_error | page_view | web_vital | client_error | system
    category = Column(String(32), nullable=False, index=True)
    module = Column(String(32), default="system", index=True)
    name = Column(String(256), nullable=False)
    client_source = Column(String(24), default="web")
    duration_ms = Column(Float, nullable=True)
    status_code = Column(Integer, nullable=True)
    value = Column(Float, nullable=True)
    detail = Column(JSONB, default=dict)
    created_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp(), index=True
    )

    __table_args__ = (
        Index("ix_sys_telemetry_events_cat_created", "category", "created_at"),
    )
