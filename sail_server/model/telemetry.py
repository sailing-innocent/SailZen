# -*- coding: utf-8 -*-
# @file telemetry.py
# @brief Telemetry, AI Trace & System Profile 业务逻辑
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""SailZen AI Trace 与系统 Profile 核心业务逻辑。"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from sail_server.application.dto.telemetry import (
    AITraceDailyTrendPoint,
    AITraceDetailResponse,
    AITraceIngestRequest,
    AITraceSlotStats,
    AITraceSpanDTO,
    AITraceStatsResponse,
    AITraceSummaryResponse,
    ApiProfileResponse,
    ClientEventBatchRequest,
    EndpointApiMetric,
    ModuleApiMetric,
    ModuleProfileCard,
    ModulesProfileResponse,
    NotableEventItem,
    PageUsageItem,
    SystemRuntimeProfileResponse,
)
from sail_server.utils.telemetry_collector import (
    SLOW_REQUEST_THRESHOLD_MS,
    get_telemetry_collector,
)
from sailzen_orm.telemetry import (
    SysAITrace,
    SysAITraceSpan,
    SysApiMetricBucket,
    SysTelemetryEvent,
)

logger = logging.getLogger(__name__)

VALID_CLIENT_EVENT_CATEGORIES = {"page_view", "web_vital", "client_error", "system"}


def _to_naive_dt(val: Optional[datetime]) -> Optional[datetime]:
    if val is None:
        return None
    if val.tzinfo is not None:
        return val.astimezone().replace(tzinfo=None)
    return val


def _trace_to_summary(row: SysAITrace, span_count: int = 0) -> AITraceSummaryResponse:
    return AITraceSummaryResponse(
        id=row.id,
        trace_id=row.trace_id,
        service=row.service or "sailtick",
        tick_id=row.tick_id or "",
        slot=row.slot or "",
        tick_date=row.tick_date or "",
        trigger_source=row.trigger_source or "scheduler",
        mode=row.mode or "live",
        status=row.status or "completed",
        plan_source=row.plan_source or "none",
        started_at=row.started_at,
        ended_at=row.ended_at,
        duration_ms=round(float(row.duration_ms or 0.0), 2),
        llm_calls_count=int(row.llm_calls_count or 0),
        prompt_tokens=int(row.prompt_tokens or 0),
        completion_tokens=int(row.completion_tokens or 0),
        total_tokens=int(row.total_tokens or 0),
        cost_usd=round(float(row.cost_usd or 0.0), 6),
        tickets_created=int(row.tickets_created or 0),
        tickets_throttled=int(row.tickets_throttled or 0),
        actions_executed=int(row.actions_executed or 0),
        actions_failed=int(row.actions_failed or 0),
        summary=row.summary or "",
        error=row.error,
        meta=row.meta if isinstance(row.meta, dict) else {},
        span_count=span_count,
    )


def _span_to_dto(sp: SysAITraceSpan) -> AITraceSpanDTO:
    return AITraceSpanDTO(
        span_id=sp.span_id,
        parent_span_id=sp.parent_span_id,
        seq=int(sp.seq or 0),
        stage=sp.stage,
        name=sp.name,
        status=sp.status or "ok",
        started_at=sp.started_at,
        ended_at=sp.ended_at,
        duration_ms=round(float(sp.duration_ms or 0.0), 2),
        input_summary=sp.input_summary or "",
        output_summary=sp.output_summary or "",
        payload=sp.payload if isinstance(sp.payload, dict) else {},
        error=sp.error,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. AI Trace 上报与查询
# ══════════════════════════════════════════════════════════════════════════════


def ingest_ai_trace_impl(db: Session, req: AITraceIngestRequest) -> AITraceSummaryResponse:
    """幂等写入一条 AI 全链路 Trace 及其所有 Spans。"""
    now = datetime.now()
    row = (
        db.query(SysAITrace).filter(SysAITrace.trace_id == req.trace_id).first()
    )
    if row is None:
        row = SysAITrace(trace_id=req.trace_id, created_at=now)
        db.add(row)

    row.service = req.service or "sailtick"
    row.tick_id = req.tick_id or ""
    row.slot = req.slot or ""
    row.tick_date = req.tick_date or now.strftime("%Y-%m-%d")
    row.trigger_source = req.trigger_source or "scheduler"
    row.mode = req.mode or "live"
    row.status = req.status or "completed"
    row.plan_source = req.plan_source or "none"
    row.started_at = _to_naive_dt(req.started_at) or now
    row.ended_at = _to_naive_dt(req.ended_at) or now
    row.duration_ms = round(float(req.duration_ms or 0.0), 2)
    row.llm_calls_count = int(req.llm_calls_count or 0)
    row.prompt_tokens = int(req.prompt_tokens or 0)
    row.completion_tokens = int(req.completion_tokens or 0)
    row.total_tokens = int(req.total_tokens or 0)
    row.cost_usd = float(req.cost_usd or 0.0)
    row.tickets_created = int(req.tickets_created or 0)
    row.tickets_throttled = int(req.tickets_throttled or 0)
    row.actions_executed = int(req.actions_executed or 0)
    row.actions_failed = int(req.actions_failed or 0)
    row.summary = (req.summary or "")[:4000]
    row.error = req.error[:4000] if req.error else None
    row.meta = req.meta if isinstance(req.meta, dict) else {}

    db.query(SysAITraceSpan).filter(
        SysAITraceSpan.trace_id == req.trace_id
    ).delete(synchronize_session=False)

    for idx, sp in enumerate(req.spans):
        db.add(
            SysAITraceSpan(
                trace_id=req.trace_id,
                span_id=sp.span_id,
                parent_span_id=sp.parent_span_id,
                seq=sp.seq if sp.seq is not None else idx,
                stage=sp.stage,
                name=sp.name[:128],
                status=sp.status or "ok",
                started_at=_to_naive_dt(sp.started_at) or row.started_at,
                ended_at=_to_naive_dt(sp.ended_at) or row.ended_at,
                duration_ms=round(float(sp.duration_ms or 0.0), 2),
                input_summary=(sp.input_summary or "")[:2000],
                output_summary=(sp.output_summary or "")[:2000],
                payload=sp.payload if isinstance(sp.payload, dict) else {},
                error=sp.error[:4000] if sp.error else None,
            )
        )

    db.commit()
    db.refresh(row)
    return _trace_to_summary(row, span_count=len(req.spans))


def list_ai_traces_impl(
    db: Session,
    service: Optional[str] = None,
    slot: Optional[str] = None,
    status: Optional[str] = None,
    plan_source: Optional[str] = None,
    days: int = 7,
    limit: int = 50,
) -> List[AITraceSummaryResponse]:
    q = db.query(SysAITrace)
    if service:
        q = q.filter(SysAITrace.service == service)
    if slot:
        q = q.filter(SysAITrace.slot == slot)
    if status:
        q = q.filter(SysAITrace.status == status)
    if plan_source:
        q = q.filter(SysAITrace.plan_source == plan_source)
    if days > 0:
        cutoff = datetime.now() - timedelta(days=days)
        q = q.filter(SysAITrace.started_at >= cutoff)

    rows = q.order_by(SysAITrace.started_at.desc(), SysAITrace.id.desc()).limit(min(limit, 200)).all()
    if not rows:
        return []

    trace_ids = [r.trace_id for r in rows]
    span_counts_rows = (
        db.query(SysAITraceSpan.trace_id, func.count(SysAITraceSpan.id))
        .filter(SysAITraceSpan.trace_id.in_(trace_ids))
        .group_by(SysAITraceSpan.trace_id)
        .all()
    )
    span_counts = {tid: int(cnt) for tid, cnt in span_counts_rows}
    return [_trace_to_summary(r, span_count=span_counts.get(r.trace_id, 0)) for r in rows]


def get_ai_trace_detail_impl(db: Session, trace_id: str) -> Optional[AITraceDetailResponse]:
    row = db.query(SysAITrace).filter(SysAITrace.trace_id == trace_id).first()
    if row is None:
        return None
    spans = (
        db.query(SysAITraceSpan)
        .filter(SysAITraceSpan.trace_id == trace_id)
        .order_by(SysAITraceSpan.seq.asc(), SysAITraceSpan.id.asc())
        .all()
    )
    summary = _trace_to_summary(row, span_count=len(spans))
    return AITraceDetailResponse(
        **summary.model_dump(),
        spans=[_span_to_dto(sp) for sp in spans],
    )


def get_ai_trace_stats_impl(
    db: Session,
    service: str = "sailtick",
    days: int = 7,
) -> AITraceStatsResponse:
    cutoff = datetime.now() - timedelta(days=max(1, days))
    q = db.query(SysAITrace).filter(SysAITrace.started_at >= cutoff)
    if service and service != "all":
        q = q.filter(SysAITrace.service == service)
    rows = q.order_by(SysAITrace.started_at.asc()).all()

    total = len(rows)
    completed = sum(1 for r in rows if r.status == "completed")
    failed = sum(1 for r in rows if r.status == "failed")
    paused = sum(1 for r in rows if r.status == "paused")
    skipped = sum(1 for r in rows if r.status == "skipped")
    executed = completed + failed
    success_rate = round(completed / executed, 4) if executed else 1.0

    llm_plans = sum(1 for r in rows if r.plan_source == "llm")
    fallback_plans = sum(1 for r in rows if (r.plan_source or "").startswith("fallback"))
    fallback_errors = sum(1 for r in rows if r.plan_source == "fallback_error")
    total_plans = llm_plans + fallback_plans
    fallback_rate = round(fallback_plans / total_plans, 4) if total_plans else 0.0

    durations = [float(r.duration_ms or 0.0) for r in rows if r.status in ("completed", "failed")]
    avg_dur = round(sum(durations) / len(durations), 2) if durations else 0.0

    # 统计 LLM 平均延迟（从 llm_call spans 计算）
    trace_ids = [r.trace_id for r in rows]
    avg_llm_ms = 0.0
    if trace_ids:
        llm_spans = (
            db.query(SysAITraceSpan.duration_ms)
            .filter(
                SysAITraceSpan.trace_id.in_(trace_ids),
                SysAITraceSpan.stage == "llm_call",
            )
            .all()
        )
        llm_durs = [float(x[0] or 0.0) for x in llm_spans]
        if llm_durs:
            avg_llm_ms = round(sum(llm_durs) / len(llm_durs), 2)

    slot_acc: Dict[str, Dict[str, Any]] = {}
    day_acc: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        sl = r.slot or "unknown"
        sa = slot_acc.setdefault(
            sl,
            {
                "slot": sl,
                "total": 0,
                "completed": 0,
                "failed": 0,
                "llm_plans": 0,
                "fallback_plans": 0,
                "dur_sum": 0.0,
                "dur_n": 0,
                "tokens": 0,
                "cost_usd": 0.0,
            },
        )
        sa["total"] += 1
        if r.status == "completed":
            sa["completed"] += 1
        elif r.status == "failed":
            sa["failed"] += 1
        if r.plan_source == "llm":
            sa["llm_plans"] += 1
        elif (r.plan_source or "").startswith("fallback"):
            sa["fallback_plans"] += 1
        if r.status in ("completed", "failed"):
            sa["dur_sum"] += float(r.duration_ms or 0.0)
            sa["dur_n"] += 1
        sa["tokens"] += int(r.total_tokens or 0)
        sa["cost_usd"] += float(r.cost_usd or 0.0)

        day_key = (r.tick_date or (r.started_at.strftime("%Y-%m-%d") if r.started_at else ""))[:10]
        if day_key:
            da = day_acc.setdefault(
                day_key,
                {
                    "date": day_key,
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "fallback": 0,
                    "tokens": 0,
                    "cost_usd": 0.0,
                },
            )
            da["total"] += 1
            if r.status == "completed":
                da["completed"] += 1
            elif r.status == "failed":
                da["failed"] += 1
            if (r.plan_source or "").startswith("fallback"):
                da["fallback"] += 1
            da["tokens"] += int(r.total_tokens or 0)
            da["cost_usd"] += float(r.cost_usd or 0.0)

    by_slot = [
        AITraceSlotStats(
            slot=v["slot"],
            total=v["total"],
            completed=v["completed"],
            failed=v["failed"],
            llm_plans=v["llm_plans"],
            fallback_plans=v["fallback_plans"],
            avg_duration_ms=round(v["dur_sum"] / v["dur_n"], 2) if v["dur_n"] else 0.0,
            total_tokens=v["tokens"],
            total_cost_usd=round(v["cost_usd"], 6),
        )
        for v in sorted(slot_acc.values(), key=lambda x: x["total"], reverse=True)
    ]

    daily_trend = [
        AITraceDailyTrendPoint(
            date=v["date"],
            total=v["total"],
            completed=v["completed"],
            failed=v["failed"],
            fallback=v["fallback"],
            tokens=v["tokens"],
            cost_usd=round(v["cost_usd"], 6),
        )
        for v in sorted(day_acc.values(), key=lambda x: x["date"])
    ]

    return AITraceStatsResponse(
        window_days=days,
        service=service,
        total_traces=total,
        completed_count=completed,
        failed_count=failed,
        paused_count=paused,
        skipped_count=skipped,
        success_rate=success_rate,
        llm_plan_count=llm_plans,
        fallback_plan_count=fallback_plans,
        fallback_error_count=fallback_errors,
        fallback_rate=fallback_rate,
        avg_duration_ms=avg_dur,
        avg_llm_latency_ms=avg_llm_ms,
        total_tokens=sum(int(r.total_tokens or 0) for r in rows),
        total_prompt_tokens=sum(int(r.prompt_tokens or 0) for r in rows),
        total_completion_tokens=sum(int(r.completion_tokens or 0) for r in rows),
        total_cost_usd=round(sum(float(r.cost_usd or 0.0) for r in rows), 6),
        total_tickets_created=sum(int(r.tickets_created or 0) for r in rows),
        total_tickets_throttled=sum(int(r.tickets_throttled or 0) for r in rows),
        total_actions_executed=sum(int(r.actions_executed or 0) for r in rows),
        total_actions_failed=sum(int(r.actions_failed or 0) for r in rows),
        by_slot=by_slot,
        daily_trend=daily_trend,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 2. 前端埋点事件批量落库
# ══════════════════════════════════════════════════════════════════════════════


def ingest_client_events_impl(db: Session, req: ClientEventBatchRequest) -> int:
    """批量写入前端页面访问/停留、Web Vitals 与 JS 异常事件。"""
    now = datetime.now()
    accepted = 0
    for item in req.events[:50]:
        cat = item.category if item.category in VALID_CLIENT_EVENT_CATEGORIES else "system"
        db.add(
            SysTelemetryEvent(
                category=cat,
                module=(item.module or "web")[:32],
                name=(item.name or "unknown")[:256],
                client_source=(item.client_source or "web")[:24],
                duration_ms=float(item.duration_ms) if item.duration_ms is not None else None,
                status_code=int(item.status_code) if item.status_code is not None else None,
                value=float(item.value) if item.value is not None else None,
                detail=item.detail if isinstance(item.detail, dict) else {},
                created_at=now,
            )
        )
        accepted += 1
    if accepted > 0:
        db.commit()
    return accepted


# ══════════════════════════════════════════════════════════════════════════════
# 3. API 性能与使用 Profile（DB 历史桶 + 内存实时增量合并）
# ══════════════════════════════════════════════════════════════════════════════


def _collect_merged_buckets(
    db: Session,
    window_hours: int,
    include_self: bool = False,
) -> List[Dict[str, Any]]:
    cutoff = datetime.now() - timedelta(hours=max(1, window_hours))
    rows = (
        db.query(SysApiMetricBucket)
        .filter(SysApiMetricBucket.bucket_hour >= cutoff)
        .all()
    )
    merged: Dict[Tuple[datetime, str, str, str, str], Dict[str, Any]] = {}

    def _absorb(b: Dict[str, Any]) -> None:
        if not include_self and b["module"] == "telemetry":
            return
        k = (b["bucket_hour"], b["module"], b["method"], b["endpoint"], b["client_source"])
        cur = merged.get(k)
        if cur is None:
            merged[k] = dict(b)
        else:
            prev_n = cur["req_count"]
            add_n = b["req_count"]
            tot_n = max(1, prev_n + add_n)
            cur["req_count"] = prev_n + add_n
            cur["err_4xx"] += b["err_4xx"]
            cur["err_5xx"] += b["err_5xx"]
            cur["total_ms"] = round(cur["total_ms"] + b["total_ms"], 2)
            cur["max_ms"] = round(max(cur["max_ms"], b["max_ms"]), 2)
            cur["p50_ms"] = round((cur["p50_ms"] * prev_n + b["p50_ms"] * add_n) / tot_n, 2)
            cur["p95_ms"] = round((cur["p95_ms"] * prev_n + b["p95_ms"] * add_n) / tot_n, 2)
            cur["p99_ms"] = round(max(cur["p99_ms"], b["p99_ms"]), 2)
            cur["bytes_out"] += b["bytes_out"]

    for r in rows:
        _absorb(
            {
                "bucket_hour": r.bucket_hour,
                "module": r.module,
                "method": r.method,
                "endpoint": r.endpoint,
                "client_source": r.client_source,
                "req_count": int(r.req_count or 0),
                "err_4xx": int(r.err_4xx or 0),
                "err_5xx": int(r.err_5xx or 0),
                "total_ms": float(r.total_ms or 0.0),
                "max_ms": float(r.max_ms or 0.0),
                "p50_ms": float(r.p50_ms or 0.0),
                "p95_ms": float(r.p95_ms or 0.0),
                "p99_ms": float(r.p99_ms or 0.0),
                "bytes_out": int(r.bytes_out or 0),
            }
        )

    for b in get_telemetry_collector().snapshot_unflushed_buckets():
        if b["bucket_hour"] >= cutoff:
            _absorb(b)

    return list(merged.values())


def _weighted_quantile(items: List[Dict[str, Any]], key: str, q: float) -> float:
    """按请求量加权计算分位数，避免单个离群大文件下载拉偏全局/模块 P50/P95。"""
    valid = [(float(x.get(key) or 0.0), int(x.get("req_count") or 0)) for x in items if int(x.get("req_count") or 0) > 0]
    if not valid:
        return 0.0
    valid.sort(key=lambda pair: pair[0])
    total = sum(w for _, w in valid)
    target = total * q
    cum = 0
    for val, weight in valid:
        cum += weight
        if cum >= target:
            return round(val, 2)
    return round(valid[-1][0], 2)


def get_api_profile_impl(
    db: Session,
    window_hours: int = 24,
    include_self: bool = False,
    include_notable: bool = True,
) -> ApiProfileResponse:
    buckets = _collect_merged_buckets(db, window_hours=window_hours, include_self=include_self)

    total_req = sum(b["req_count"] for b in buckets)
    total_4xx = sum(b["err_4xx"] for b in buckets)
    total_5xx = sum(b["err_5xx"] for b in buckets)
    total_ms = sum(b["total_ms"] for b in buckets)
    total_bytes = sum(b["bytes_out"] for b in buckets)
    max_ms = max((b["max_ms"] for b in buckets), default=0.0)

    by_mod_raw: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_ep_raw: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    by_client: Dict[str, int] = defaultdict(int)

    for b in buckets:
        by_mod_raw[b["module"]].append(b)
        by_ep_raw[(b["module"], b["method"], b["endpoint"])].append(b)
        by_client[b["client_source"]] += b["req_count"]

    by_module: List[ModuleApiMetric] = []
    for mod, items in by_mod_raw.items():
        n = sum(x["req_count"] for x in items)
        e4 = sum(x["err_4xx"] for x in items)
        e5 = sum(x["err_5xx"] for x in items)
        tms = sum(x["total_ms"] for x in items)
        by_module.append(
            ModuleApiMetric(
                module=mod,
                req_count=n,
                err_4xx=e4,
                err_5xx=e5,
                error_rate=round((e4 + e5) / n, 4) if n else 0.0,
                avg_ms=round(tms / n, 2) if n else 0.0,
                p50_ms=_weighted_quantile(items, "p50_ms", 0.50),
                p95_ms=_weighted_quantile(items, "p95_ms", 0.95),
                p99_ms=_weighted_quantile(items, "p99_ms", 0.99),
                max_ms=round(max((x["max_ms"] for x in items), default=0.0), 2),
                bytes_out=sum(x["bytes_out"] for x in items),
            )
        )
    by_module.sort(key=lambda m: m.req_count, reverse=True)

    endpoints: List[EndpointApiMetric] = []
    for (mod, method, ep), items in by_ep_raw.items():
        n = sum(x["req_count"] for x in items)
        e4 = sum(x["err_4xx"] for x in items)
        e5 = sum(x["err_5xx"] for x in items)
        tms = sum(x["total_ms"] for x in items)
        endpoints.append(
            EndpointApiMetric(
                module=mod,
                method=method,
                endpoint=ep,
                req_count=n,
                err_4xx=e4,
                err_5xx=e5,
                error_rate=round((e4 + e5) / n, 4) if n else 0.0,
                avg_ms=round(tms / n, 2) if n else 0.0,
                p95_ms=_weighted_quantile(items, "p95_ms", 0.95),
                max_ms=round(max((x["max_ms"] for x in items), default=0.0), 2),
                bytes_out=sum(x["bytes_out"] for x in items),
            )
        )

    top_slow = sorted(endpoints, key=lambda e: (e.p95_ms, e.max_ms), reverse=True)[:15]
    top_called = sorted(endpoints, key=lambda e: e.req_count, reverse=True)[:15]

    # 慢请求与 5xx 离散事件（DB + 内存实时合并）
    notable_items: List[NotableEventItem] = []
    if include_notable:
        cutoff = datetime.now() - timedelta(hours=max(1, window_hours))
        db_notable = (
            db.query(SysTelemetryEvent)
            .filter(
                SysTelemetryEvent.category.in_(["api_slow", "api_error"]),
                SysTelemetryEvent.created_at >= cutoff,
            )
            .order_by(SysTelemetryEvent.created_at.desc())
            .limit(60)
            .all()
        )
        notable_items = [
            NotableEventItem(
                id=r.id,
                category=r.category,
                module=r.module or "system",
                name=r.name,
                client_source=r.client_source or "other",
                duration_ms=r.duration_ms,
                status_code=r.status_code,
                value=r.value,
                detail=r.detail if isinstance(r.detail, dict) else {},
                created_at=r.created_at,
            )
            for r in db_notable
        ]
        seen_keys = {
            (it.category, it.name, it.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            for it in notable_items
        }
        for mem_evt in get_telemetry_collector().snapshot_recent_notable(limit=40):
            ts = mem_evt["created_at"]
            if ts < cutoff:
                continue
            k = (mem_evt["category"], mem_evt["name"], ts.strftime("%Y-%m-%d %H:%M:%S"))
            if k in seen_keys:
                continue
            seen_keys.add(k)
            notable_items.append(
                NotableEventItem(
                    id=None,
                    category=mem_evt["category"],
                    module=mem_evt["module"],
                    name=mem_evt["name"],
                    client_source=mem_evt["client_source"],
                    duration_ms=mem_evt.get("duration_ms"),
                    status_code=mem_evt.get("status_code"),
                    value=mem_evt.get("value"),
                    detail=mem_evt.get("detail") or {},
                    created_at=ts,
                )
            )
        notable_items.sort(key=lambda x: x.created_at, reverse=True)
    slow_count = sum(1 for x in notable_items if x.category == "api_slow")

    return ApiProfileResponse(
        window_hours=window_hours,
        total_requests=total_req,
        total_4xx=total_4xx,
        total_5xx=total_5xx,
        error_rate=round((total_4xx + total_5xx) / total_req, 4) if total_req else 0.0,
        avg_ms=round(total_ms / total_req, 2) if total_req else 0.0,
        p50_ms=_weighted_quantile(buckets, "p50_ms", 0.50),
        p95_ms=_weighted_quantile(buckets, "p95_ms", 0.95),
        p99_ms=_weighted_quantile(buckets, "p99_ms", 0.99),
        max_ms=round(max_ms, 2),
        total_bytes_out=total_bytes,
        slow_threshold_ms=SLOW_REQUEST_THRESHOLD_MS,
        slow_requests_count=slow_count,
        by_module=by_module,
        by_client=dict(by_client),
        top_slow_endpoints=top_slow,
        top_called_endpoints=top_called,
        recent_notable=notable_items[:50],
    )


# ══════════════════════════════════════════════════════════════════════════════
# 4. SailZen 各业务板块 Profile（数据规模 + 活跃度 + 健康度 + 前端访问统计）
# ══════════════════════════════════════════════════════════════════════════════


def _dir_stats(path: Path) -> Tuple[int, float]:
    """统计目录内文件数量与总体积（MB）。"""
    if not path.exists() or not path.is_dir():
        return 0, 0.0
    count = 0
    total_bytes = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                count += 1
                try:
                    total_bytes += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except OSError:
        pass
    return count, round(total_bytes / (1024 * 1024), 2)


def get_modules_profile_impl(db: Session, window_days: int = 7) -> ModulesProfileResponse:
    now = datetime.now()
    cutoff = now - timedelta(days=max(1, window_days))
    api_prof = get_api_profile_impl(
        db, window_hours=max(24, window_days * 24), include_notable=False
    )
    api_by_mod = {m.module: m for m in api_prof.by_module}

    def _attach_api(card: ModuleProfileCard, mod_key: str) -> ModuleProfileCard:
        am = api_by_mod.get(mod_key)
        if am:
            card.api_requests_window = am.req_count
            card.api_p95_ms = am.p95_ms
            card.api_error_rate = am.error_rate
            if am.error_rate >= 0.1 or am.p95_ms >= 800:
                card.status = "warning"
        return card

    cards: List[ModuleProfileCard] = []

    # 1. Finance 财务（单表条件聚合合并 3 次全表扫描为 1 次）
    try:
        from sailzen_orm.finance import Account, Budget, Transaction

        acc_total = db.query(func.count(Account.id)).scalar() or 0
        tx_agg = (
            db.query(
                func.count(Transaction.id),
                func.count(case((Transaction.htime >= cutoff, 1))),
                func.count(
                    case(((Transaction.tags.is_(None)) | (Transaction.tags == ""), 1))
                ),
            )
            .one()
        )
        tx_total, tx_recent, tx_untagged = (
            int(tx_agg[0] or 0),
            int(tx_agg[1] or 0),
            int(tx_agg[2] or 0),
        )
        budget_total = db.query(func.count(Budget.id)).scalar() or 0
        untagged_ratio = round(tx_untagged / tx_total, 4) if tx_total else 0.0
        cards.append(
            _attach_api(
                ModuleProfileCard(
                    key="finance",
                    label="财务 (Finance)",
                    status="warning" if untagged_ratio > 0.25 else ("healthy" if tx_total > 0 else "idle"),
                    summary=f"总交易 {tx_total} 笔 · 近{window_days}天新增 {tx_recent} 笔 · 未打标 {untagged_ratio*100:.1f}%",
                    metrics={
                        "accounts": int(acc_total),
                        "transactions_total": tx_total,
                        "transactions_window": tx_recent,
                        "budgets": int(budget_total),
                        "untagged_count": tx_untagged,
                        "untagged_ratio": untagged_ratio,
                    },
                ),
                "finance",
            )
        )
    except Exception as exc:
        logger.debug("[telemetry] finance profile skipped: %s", exc)

    # 2. Health 健康
    try:
        from sailzen_orm.health import BodyData, DietLog, Exercise, Mood, Sleep, Weight, WeightPlan

        bd_agg = (
            db.query(
                func.count(BodyData.id),
                func.count(case((BodyData.htime >= cutoff, 1))),
            )
            .one()
        )
        bd_total, bd_recent = int(bd_agg[0] or 0), int(bd_agg[1] or 0)
        w_recent = db.query(func.count(Weight.id)).filter(Weight.htime >= cutoff).scalar() or 0
        diet_recent = db.query(func.count(DietLog.id)).filter(DietLog.htime >= cutoff).scalar() or 0
        ex_recent = db.query(func.count(Exercise.id)).filter(Exercise.htime >= cutoff).scalar() or 0
        sleep_recent = db.query(func.count(Sleep.id)).filter(Sleep.htime >= cutoff).scalar() or 0
        mood_recent = db.query(func.count(Mood.id)).filter(Mood.htime >= cutoff).scalar() or 0
        plans_total = db.query(func.count(WeightPlan.id)).scalar() or 0
        total_recent_logs = bd_recent + diet_recent + ex_recent + sleep_recent + mood_recent
        cards.append(
            _attach_api(
                ModuleProfileCard(
                    key="health",
                    label="健康 (Health)",
                    status="healthy" if total_recent_logs > 0 else "idle",
                    summary=f"近{window_days}天：体重 {w_recent} · 饮食 {diet_recent} · 运动 {ex_recent} · 睡眠 {sleep_recent}",
                    metrics={
                        "body_data_total": bd_total,
                        "body_data_window": bd_recent,
                        "weight_window": int(w_recent),
                        "diet_window": int(diet_recent),
                        "exercise_window": int(ex_recent),
                        "sleep_window": int(sleep_recent),
                        "mood_window": int(mood_recent),
                        "weight_plans": int(plans_total),
                    },
                ),
                "health",
            )
        )
    except Exception as exc:
        logger.debug("[telemetry] health profile skipped: %s", exc)

    # 3. Rhythm 节奏（v2 极简 3 表：Affair / TimeBlock / DisciplineLog）
    try:
        from sailzen_orm.rhythm import (
            RhythmAffair,
            RhythmDisciplineLog,
            RhythmTimeBlock,
        )

        aff_agg = (
            db.query(
                func.count(RhythmAffair.id),
                func.count(
                    case(
                        (
                            RhythmAffair.state.in_(
                                ["ACTIVE", "DOING", "SCHEDULED", "PLANNED"]
                            ),
                            1,
                        )
                    )
                ),
                func.count(case((RhythmAffair.state == "INBOX", 1))),
            )
            .one()
        )
        aff_total, aff_active, aff_inbox = (
            int(aff_agg[0] or 0),
            int(aff_agg[1] or 0),
            int(aff_agg[2] or 0),
        )
        disc_recent = (
            db.query(func.count(RhythmDisciplineLog.id))
            .filter(RhythmDisciplineLog.log_date >= cutoff.date())
            .scalar()
            or 0
        )
        blocks_total = db.query(func.count(RhythmTimeBlock.id)).scalar() or 0
        cards.append(
            _attach_api(
                ModuleProfileCard(
                    key="rhythm",
                    label="节奏 (Rhythm)",
                    status="healthy" if (aff_active > 0 or blocks_total > 0 or disc_recent > 0) else "idle",
                    summary=f"活跃事务 {aff_active} · 时间块 {blocks_total} · 近{window_days}天打卡 {disc_recent}",
                    metrics={
                        "affairs_total": aff_total,
                        "affairs_active": aff_active,
                        "affairs_inbox": aff_inbox,
                        "discipline_logs_window": int(disc_recent),
                        "time_blocks_total": int(blocks_total),
                    },
                ),
                "rhythm",
            )
        )
    except Exception as exc:
        logger.debug("[telemetry] rhythm profile skipped: %s", exc)

    # 4. SailTick 教练（合并 SailTickTicket 4 次扫描为 1 次）
    try:
        from sailzen_orm.tick import SailTickDailyReport, SailTickMessage, SailTickTicket

        t_agg = (
            db.query(
                func.count(SailTickTicket.id),
                func.count(case((SailTickTicket.status == "pending", 1))),
                func.count(
                    case((SailTickTicket.status.in_(["replied", "resolved"]), 1))
                ),
                func.count(case((SailTickTicket.status == "expired", 1))),
            )
            .one()
        )
        t_total, t_pending, t_replied, t_expired = (
            int(t_agg[0] or 0),
            int(t_agg[1] or 0),
            int(t_agg[2] or 0),
            int(t_agg[3] or 0),
        )
        msg_unread = (
            db.query(func.count(SailTickMessage.id))
            .filter(SailTickMessage.status == "unread")
            .scalar()
            or 0
        )
        reports_total = db.query(func.count(SailTickDailyReport.id)).scalar() or 0
        trace_stats = get_ai_trace_stats_impl(db, service="sailtick", days=window_days)
        reply_rate = round(t_replied / t_total, 4) if t_total else 0.0
        status = "healthy"
        if trace_stats.failed_count > 0 or trace_stats.fallback_rate >= 0.5:
            status = "warning"
        elif t_total == 0 and trace_stats.total_traces == 0:
            status = "idle"
        cards.append(
            _attach_api(
                ModuleProfileCard(
                    key="tick",
                    label="SailTick 教练",
                    status=status,
                    summary=(
                        f"近{window_days}天 Trace {trace_stats.total_traces} 次 (成功率 {trace_stats.success_rate*100:.0f}%) · "
                        f"待回票据 {t_pending} · 日报 {reports_total}"
                    ),
                    metrics={
                        "tickets_total": t_total,
                        "tickets_pending": t_pending,
                        "tickets_expired": t_expired,
                        "ticket_reply_rate": reply_rate,
                        "messages_unread": int(msg_unread),
                        "daily_reports": int(reports_total),
                        "traces_window": trace_stats.total_traces,
                        "trace_success_rate": trace_stats.success_rate,
                        "llm_fallback_rate": trace_stats.fallback_rate,
                        "tokens_window": trace_stats.total_tokens,
                    },
                ),
                "tick",
            )
        )
    except Exception as exc:
        logger.debug("[telemetry] tick profile skipped: %s", exc)

    # 5. Reminder & Android WS（合并 Reminder 3 次扫描为 1 次）
    try:
        from sail_server.utils.reminder_ws import get_reminder_push_manager
        from sailzen_orm.reminder import Device, Reminder

        r_agg = (
            db.query(
                func.count(Reminder.id),
                func.count(
                    case(
                        (
                            Reminder.state.in_(["PENDING", "DELIVERED", "SNOOZED"]),
                            1,
                        )
                    )
                ),
                func.count(case((Reminder.state == "RESOLVED", 1))),
            )
            .one()
        )
        r_total, r_pending, r_resolved = (
            int(r_agg[0] or 0),
            int(r_agg[1] or 0),
            int(r_agg[2] or 0),
        )
        dev_total = db.query(func.count(Device.id)).scalar() or 0
        ws_online = get_reminder_push_manager().online_count()
        cards.append(
            _attach_api(
                ModuleProfileCard(
                    key="reminder",
                    label="提醒与推送 (Reminder)",
                    status="healthy" if (ws_online > 0 or r_total > 0) else "idle",
                    summary=f"在线 WS 设备 {ws_online} / 已注册 {dev_total} · 待处理提醒 {r_pending}",
                    metrics={
                        "online_ws_devices": int(ws_online),
                        "registered_devices": int(dev_total),
                        "reminders_total": r_total,
                        "reminders_active": r_pending,
                        "reminders_resolved": r_resolved,
                    },
                ),
                "reminder",
            )
        )
    except Exception as exc:
        logger.debug("[telemetry] reminder profile skipped: %s", exc)

    # 6. Text 文本与阅读（合并 Edition count + sum 为 1 次）
    try:
        from sailzen_orm.text import DocumentNode, Edition, NoteItem, Work

        works_cnt = db.query(func.count(Work.id)).scalar() or 0
        ed_agg = (
            db.query(
                func.count(Edition.id),
                func.coalesce(func.sum(Edition.char_count), 0),
            )
            .one()
        )
        editions_cnt, total_chars = int(ed_agg[0] or 0), int(ed_agg[1] or 0)
        nodes_cnt = db.query(func.count(DocumentNode.id)).scalar() or 0
        notes_cnt = db.query(func.count(NoteItem.id)).scalar() or 0
        cards.append(
            _attach_api(
                ModuleProfileCard(
                    key="text",
                    label="文本与阅读 (Text)",
                    status="healthy" if (works_cnt > 0 or notes_cnt > 0) else "idle",
                    summary=f"作品 {works_cnt} · 章节节点 {nodes_cnt} · 笔记索引 {notes_cnt}",
                    metrics={
                        "works": int(works_cnt),
                        "editions": editions_cnt,
                        "document_nodes": int(nodes_cnt),
                        "note_items": int(notes_cnt),
                        "total_chars": total_chars,
                    },
                ),
                "text",
            )
        )
    except Exception as exc:
        logger.debug("[telemetry] text profile skipped: %s", exc)

    # 7. Necessity 物资
    try:
        from sailzen_orm.necessity import Container, Item, Residence

        res_cnt = db.query(func.count(Residence.id)).scalar() or 0
        con_cnt = db.query(func.count(Container.id)).scalar() or 0
        item_cnt = db.query(func.count(Item.id)).scalar() or 0
        cards.append(
            _attach_api(
                ModuleProfileCard(
                    key="necessity",
                    label="物资 (Necessity)",
                    status="healthy" if item_cnt > 0 else "idle",
                    summary=f"住所 {res_cnt} · 容器 {con_cnt} · 物资 {item_cnt} 件",
                    metrics={
                        "residences": int(res_cnt),
                        "containers": int(con_cnt),
                        "items": int(item_cnt),
                    },
                ),
                "necessity",
            )
        )
    except Exception as exc:
        logger.debug("[telemetry] necessity profile skipped: %s", exc)

    # 8. File Storage & Blog
    try:
        from sail_server.config.paths import BLOG_STORAGE_DIR, FILE_STORAGE_DIR

        fs_count, fs_mb = _dir_stats(FILE_STORAGE_DIR)
        blog_count, blog_mb = _dir_stats(BLOG_STORAGE_DIR)
        cards.append(
            _attach_api(
                ModuleProfileCard(
                    key="file_storage",
                    label="文件与博客 (Storage/Blog)",
                    status="healthy" if (fs_count > 0 or blog_count > 0) else "idle",
                    summary=f"存储文件 {fs_count} ({fs_mb} MB) · 博客文件 {blog_count} ({blog_mb} MB)",
                    metrics={
                        "storage_files": fs_count,
                        "storage_mb": fs_mb,
                        "blog_files": blog_count,
                        "blog_mb": blog_mb,
                    },
                ),
                "file_storage",
            )
        )
    except Exception as exc:
        logger.debug("[telemetry] storage profile skipped: %s", exc)

    # 前端页面访问 & 停留时长统计
    pv_rows = (
        db.query(SysTelemetryEvent)
        .filter(
            SysTelemetryEvent.category == "page_view",
            SysTelemetryEvent.created_at >= cutoff,
        )
        .all()
    )
    page_acc: Dict[str, Dict[str, Any]] = {}
    for r in pv_rows:
        p = r.name or "/"
        acc = page_acc.setdefault(p, {"path": p, "views": 0, "dwell_ms": 0.0, "dwell_n": 0})
        acc["views"] += 1
        if r.duration_ms is not None and r.duration_ms > 0:
            acc["dwell_ms"] += float(r.duration_ms)
            acc["dwell_n"] += 1

    page_usage = [
        PageUsageItem(
            path=v["path"],
            views=v["views"],
            avg_dwell_sec=round((v["dwell_ms"] / v["dwell_n"]) / 1000.0, 1) if v["dwell_n"] else 0.0,
            total_dwell_sec=round(v["dwell_ms"] / 1000.0, 1),
        )
        for v in sorted(page_acc.values(), key=lambda x: x["views"], reverse=True)
    ]

    err_rows = (
        db.query(SysTelemetryEvent)
        .filter(
            SysTelemetryEvent.category == "client_error",
            SysTelemetryEvent.created_at >= cutoff,
        )
        .order_by(SysTelemetryEvent.created_at.desc())
        .limit(30)
        .all()
    )
    recent_client_errors = [
        NotableEventItem(
            id=r.id,
            category=r.category,
            module=r.module or "web",
            name=r.name,
            client_source=r.client_source or "web",
            duration_ms=r.duration_ms,
            status_code=r.status_code,
            value=r.value,
            detail=r.detail if isinstance(r.detail, dict) else {},
            created_at=r.created_at,
        )
        for r in err_rows
    ]

    return ModulesProfileResponse(
        generated_at=now,
        window_days=window_days,
        modules=cards,
        page_usage=page_usage,
        recent_client_errors=recent_client_errors,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 5. 系统运行时 Profile
# ══════════════════════════════════════════════════════════════════════════════


def _get_process_rss_mb() -> Optional[float]:
    """零依赖获取当前进程 RSS 内存（MB），兼容 Linux 与 Windows。"""
    try:
        # Linux /proc/self/status
        if os.path.exists("/proc/self/status"):
            with open("/proc/self/status", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        kb = int(line.split()[1])
                        return round(kb / 1024.0, 2)
    except Exception:
        pass
    try:
        import psutil  # type: ignore

        return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2)
    except Exception:
        pass
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux 返回 KB，macOS 返回 Bytes
        if sys.platform == "darwin":
            return round(usage / (1024 * 1024), 2)
        return round(usage / 1024.0, 2)
    except Exception:
        return None


def get_system_runtime_profile_impl(db: Session) -> SystemRuntimeProfileResponse:
    from sail_server.config.paths import SERVER_DATA_DIR
    from sail_server.utils.reminder_ws import get_reminder_push_manager

    collector = get_telemetry_collector()
    counters = collector.runtime_counters()

    backend = os.environ.get("DB_BACKEND", "postgres").lower().strip()
    try:
        bind = db.get_bind()
        if bind is not None:
            backend = bind.dialect.name
    except Exception:
        pass

    _files, data_mb = _dir_stats(SERVER_DATA_DIR)
    ws_devices = get_reminder_push_manager().online_device_ids()

    table_counts: Dict[str, int] = {}
    for tbl_name, model_cls in (
        ("sys_ai_traces", SysAITrace),
        ("sys_ai_trace_spans", SysAITraceSpan),
        ("sys_api_metric_buckets", SysApiMetricBucket),
        ("sys_telemetry_events", SysTelemetryEvent),
    ):
        try:
            table_counts[tbl_name] = int(db.query(func.count(model_cls.id)).scalar() or 0)
        except Exception:
            table_counts[tbl_name] = 0

    return SystemRuntimeProfileResponse(
        generated_at=datetime.now(),
        started_at=counters["started_at"],
        uptime_seconds=counters["uptime_seconds"],
        python_version=sys.version.split()[0],
        db_backend=backend,
        memory_rss_mb=_get_process_rss_mb(),
        data_dir=str(SERVER_DATA_DIR),
        data_dir_size_mb=data_mb,
        online_ws_devices=ws_devices,
        total_requests_since_boot=counters["total_requests_since_boot"],
        total_errors_since_boot=counters["total_errors_since_boot"],
        unflushed_buckets=counters["unflushed_buckets"],
        last_flush_at=counters["last_flush_at"],
        table_counts=table_counts,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 6. SailTick Daemon 实时代理（仅同机 localhost，不可达时优雅降级）
# ══════════════════════════════════════════════════════════════════════════════


def _sailtick_api_base() -> str:
    explicit = os.environ.get("SAILTICK_API_BASE", "").strip()
    if explicit:
        return explicit.rstrip("/")
    host = os.environ.get("SAILTICK_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("SAILTICK_API_PORT", "9070").strip() or "9070"
    return f"http://{host}:{port}"


async def fetch_sailtick_live_impl() -> Dict[str, Any]:
    base = _sailtick_api_base()
    is_local = "127.0.0.1" in base or "localhost" in base
    try:
        async with httpx.AsyncClient(timeout=3.0, trust_env=not is_local) as client:
            health_r, monitor_r, sched_r = await asyncio.gather(
                client.get(f"{base}/health"),
                client.get(f"{base}/monitor"),
                client.get(f"{base}/schedules"),
                return_exceptions=True,
            )
            if isinstance(health_r, Exception) or health_r.status_code >= 400:
                err_msg = str(health_r) if isinstance(health_r, Exception) else f"HTTP {health_r.status_code}"
                return {"reachable": False, "api_base": base, "error": err_msg}

            health_data = health_r.json()
            monitor_data = (
                monitor_r.json()
                if not isinstance(monitor_r, Exception) and monitor_r.status_code < 400
                else None
            )
            schedules_data = (
                sched_r.json()
                if not isinstance(sched_r, Exception) and sched_r.status_code < 400
                else []
            )
            return {
                "reachable": True,
                "api_base": base,
                "health": health_data,
                "monitor": monitor_data,
                "schedules": schedules_data,
            }
    except Exception as exc:
        return {"reachable": False, "api_base": base, "error": str(exc)}


async def trigger_sailtick_slot_impl(
    slot: str,
    idempotency_suffix: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base = _sailtick_api_base()
    is_local = "127.0.0.1" in base or "localhost" in base
    body = dict(params or {})
    body.setdefault("trigger_source", "debug_ui")
    if idempotency_suffix:
        body["idempotency_suffix"] = idempotency_suffix
    try:
        async with httpx.AsyncClient(timeout=5.0, trust_env=not is_local) as client:
            resp = await client.post(f"{base}/tick/{slot}", json=body)
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text}
            return {
                "reachable": True,
                "status_code": resp.status_code,
                "result": data,
            }
    except Exception as exc:
        return {"reachable": False, "api_base": base, "error": str(exc)}
