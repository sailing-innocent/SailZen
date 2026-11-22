# -*- coding: utf-8 -*-
# @file tracer.py
# @brief SailTick AI 全链路 Trace 记录器（唤醒 → SCAN → PLAN → LLM → 限流 → WORK → HANDOFF）
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""SailTick AI Trace 收集器。

每次 Tick 唤醒构建一个 TickTraceRecorder：
- 记录整次 Tick 的元数据（trace_id, tick_id, slot, trigger_source, mode, status, plan_source, tokens, cost, 产出统计）
- 通过 `with tracer.span(stage, name, ...) as sp:` 记录每个阶段与子步骤（含 LLM 请求/响应/思维链、限流理由、WORK 动作明细）
- 自动脱敏敏感凭据（Bearer Token / sk-*** 等）并截断超大文本，防止 DB 膨胀
- 最终输出标准化字典，既落盘本地隔离库（st_ai_traces / st_ai_trace_spans），也异步上报至 sail_server（/api/v1/telemetry/ai-traces）
"""

from __future__ import annotations

import re
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Generator, List, Optional

MAX_TEXT_CHARS = 65536

_SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
    re.compile(r"(sk-[A-Za-z0-9_\-]{8,})"),
    re.compile(r"(postgresql(?:\+psycopg)?://[^:\s]+:)([^@\s]+)(@)", re.IGNORECASE),
]


def sanitize_text(text: Any, max_chars: int = MAX_TEXT_CHARS) -> str:
    """将任意文本脱敏并安全截断。"""
    if text is None:
        return ""
    s = str(text)
    s = _SECRET_PATTERNS[0].sub(r"\1***", s)
    s = _SECRET_PATTERNS[1].sub("sk-***", s)
    s = _SECRET_PATTERNS[2].sub(r"\1***\3", s)
    if len(s) > max_chars:
        return s[:max_chars] + f"\n...[truncated {len(s) - max_chars} chars]"
    return s


def sanitize_payload(obj: Any, max_str: int = MAX_TEXT_CHARS) -> Any:
    """递归脱敏 JSON 载荷。"""
    if isinstance(obj, str):
        return sanitize_text(obj, max_chars=max_str)
    if isinstance(obj, dict):
        return {str(k): sanitize_payload(v, max_str=max_str) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_payload(v, max_str=max_str) for v in obj[:200]]
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    return sanitize_text(obj, max_chars=max_str)


@dataclass
class TraceSpanRecord:
    """单个阶段/步骤 Span 记录。"""

    span_id: str
    parent_span_id: Optional[str]
    seq: int
    stage: str
    name: str
    started_at: str
    _t0: float
    status: str = "ok"
    ended_at: Optional[str] = None
    duration_ms: float = 0.0
    input_summary: str = ""
    output_summary: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def set_input(self, summary: str) -> None:
        self.input_summary = sanitize_text(summary, max_chars=2000)

    def set_output(self, summary: str) -> None:
        self.output_summary = sanitize_text(summary, max_chars=2000)

    def set_payload(self, data: Dict[str, Any]) -> None:
        self.payload = sanitize_payload(data)

    def update_payload(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            self.payload[str(k)] = sanitize_payload(v)

    def mark_status(self, status: str, error: Optional[str] = None) -> None:
        self.status = status
        if error:
            self.error = sanitize_text(error, max_chars=4000)

    def finish(self, now_iso: str) -> None:
        if self.ended_at is None:
            self.ended_at = now_iso
            self.duration_ms = round((time.perf_counter() - self._t0) * 1000.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "seq": self.seq,
            "stage": self.stage,
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "payload": self.payload,
            "error": self.error,
        }


class TickTraceRecorder:
    """单次 Tick 唤醒的全链路 Trace 记录器。"""

    def __init__(
        self,
        slot: str,
        tick_date: str,
        mode: str = "live",
        trigger_source: str = "scheduler",
        service: str = "sailtick",
        tick_id: str = "",
        clock: Callable[[], datetime] = datetime.now,
    ):
        self._clock = clock
        self._t0 = time.perf_counter()
        self.trace_id: str = uuid.uuid4().hex
        self.service: str = service
        self.tick_id: str = tick_id
        self.slot: str = slot
        self.tick_date: str = tick_date
        self.trigger_source: str = trigger_source
        self.mode: str = mode
        self.status: str = "running"
        self.plan_source: str = "none"
        self.started_at: str = clock().isoformat()
        self.ended_at: Optional[str] = None
        self.duration_ms: float = 0.0

        self.llm_calls_count: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self.cost_usd: float = 0.0

        self.tickets_created: int = 0
        self.tickets_throttled: int = 0
        self.actions_executed: int = 0
        self.actions_failed: int = 0

        self.summary: str = ""
        self.error: Optional[str] = None
        self.meta: Dict[str, Any] = {}

        self._spans: List[TraceSpanRecord] = []
        self._span_stack: List[str] = []

    @property
    def current_span_id(self) -> Optional[str]:
        return self._span_stack[-1] if self._span_stack else None

    @contextmanager
    def span(
        self,
        stage: str,
        name: str,
        input_summary: str = "",
        parent_span_id: Optional[str] = None,
    ) -> Generator[TraceSpanRecord, None, None]:
        """开启一个计时 Span，自动嵌套父子关系并捕获异常。"""
        sp = TraceSpanRecord(
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=parent_span_id if parent_span_id is not None else self.current_span_id,
            seq=len(self._spans),
            stage=stage,
            name=name,
            started_at=self._clock().isoformat(),
            _t0=time.perf_counter(),
            input_summary=sanitize_text(input_summary, max_chars=2000),
        )
        self._spans.append(sp)
        self._span_stack.append(sp.span_id)
        try:
            yield sp
        except Exception as exc:
            sp.mark_status("error", f"{type(exc).__name__}: {exc}")
            raise
        finally:
            sp.finish(self._clock().isoformat())
            if self._span_stack and self._span_stack[-1] == sp.span_id:
                self._span_stack.pop()

    def record_instant_span(
        self,
        stage: str,
        name: str,
        status: str = "ok",
        input_summary: str = "",
        output_summary: str = "",
        payload: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
    ) -> TraceSpanRecord:
        """记录瞬时事件型 Span（如限流决策、熔断事件、跳过原因）。"""
        now_iso = self._clock().isoformat()
        sp = TraceSpanRecord(
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=self.current_span_id,
            seq=len(self._spans),
            stage=stage,
            name=name,
            status=status,
            started_at=now_iso,
            ended_at=now_iso,
            _t0=time.perf_counter(),
            duration_ms=round(float(duration_ms), 2),
            input_summary=sanitize_text(input_summary, max_chars=2000),
            output_summary=sanitize_text(output_summary, max_chars=2000),
            payload=sanitize_payload(payload or {}),
            error=sanitize_text(error, max_chars=4000) if error else None,
        )
        self._spans.append(sp)
        return sp

    def add_llm_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        self.llm_calls_count += 1
        self.prompt_tokens += int(prompt_tokens or 0)
        self.completion_tokens += int(completion_tokens or 0)
        tot = int(total_tokens or 0) or (int(prompt_tokens or 0) + int(completion_tokens or 0))
        self.total_tokens += tot
        self.cost_usd = round(self.cost_usd + float(cost_usd or 0.0), 8)

    def finish(
        self,
        status: str,
        summary: str = "",
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """结束整次 Trace 并返回标准序列化字典。"""
        self.status = status
        if summary:
            self.summary = sanitize_text(summary, max_chars=2000)
        if error:
            self.error = sanitize_text(error, max_chars=4000)
        now_iso = self._clock().isoformat()
        self.ended_at = now_iso
        self.duration_ms = round((time.perf_counter() - self._t0) * 1000.0, 2)
        for sp in self._spans:
            sp.finish(now_iso)
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "service": self.service,
            "tick_id": self.tick_id,
            "slot": self.slot,
            "tick_date": self.tick_date,
            "trigger_source": self.trigger_source,
            "mode": self.mode,
            "status": self.status,
            "plan_source": self.plan_source,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "llm_calls_count": self.llm_calls_count,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "tickets_created": self.tickets_created,
            "tickets_throttled": self.tickets_throttled,
            "actions_executed": self.actions_executed,
            "actions_failed": self.actions_failed,
            "summary": self.summary,
            "error": self.error,
            "meta": sanitize_payload(self.meta),
            "spans": [sp.to_dict() for sp in self._spans],
        }
