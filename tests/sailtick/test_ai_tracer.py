# -*- coding: utf-8 -*-
# @file test_ai_tracer.py
# @brief SailTick AI Trace 收集器与 TickEngine 全链路追踪测试
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import pytest

from sailtick.config import (
    CanaryConfig,
    LLMConfig,
    LLMProviderConfig,
    SailServerConfig,
    SailTickConfig,
    TickConfig,
)
from sailtick.daemon import SailTickDaemon
from sailtick.llm import LLMResponse
from sailtick.tracer import sanitize_text


class TracingFakeInbox:
    def __init__(self):
        self.tickets: List[dict] = []
        self.reported_traces: List[dict] = []
        self._next_id = 1
        self.reachable = True

    async def health(self) -> bool:
        return self.reachable

    async def pending_tickets(self) -> List[dict]:
        return [t for t in self.tickets if t["status"] == "pending"]

    async def expire_overdue(self) -> int:
        return 0

    async def sync_replies_since(self, since=None) -> List[dict]:
        return []

    async def list_user_messages(self, status="unread", limit=50) -> List[dict]:
        return []

    async def create_ticket(self, **kwargs) -> Dict[str, Any]:
        t = {"id": self._next_id, "status": "pending", **kwargs}
        self._next_id += 1
        self.tickets.append(t)
        return t

    async def report_ai_trace(self, trace_payload: Dict[str, Any]) -> bool:
        self.reported_traces.append(trace_payload)
        return True

    async def close(self) -> None:
        pass


class TracingFakeScanner:
    async def scan(self, days: int = 7) -> Dict[str, Any]:
        return {"health_ok": True, "window_days": days, "weight": [{"value": 72.3}]}

    def describe(self, package: Dict[str, Any]) -> str:
        return "体重 72.3kg"

    async def close(self) -> None:
        pass


class TracingFakeLLM:
    def __init__(self, responses: Optional[List[Any]] = None):
        self.responses = list(responses or [])
        self.tick_tokens = 0
        self.tick_usd = 0.0
        self.cost_recorded_by_sink = False
        self.budget_exceeded = False
        self.config = LLMConfig(
            providers={"deepseek": LLMProviderConfig(api_key="sk-secret-key-1234567890", model="deepseek-chat")}
        )

    def begin_tick(self) -> None:
        self.tick_tokens = 0
        self.tick_usd = 0.0

    async def chat(self, prompt: str, **kwargs) -> LLMResponse:
        nxt = self.responses.pop(0) if self.responses else "{}"
        if isinstance(nxt, Exception):
            raise nxt
        self.tick_tokens += 350
        self.tick_usd += 0.0007
        return LLMResponse(
            content=nxt,
            usage={"prompt_tokens": 250, "completion_tokens": 100, "total_tokens": 350},
            model="deepseek-chat",
            provider="deepseek",
            latency_ms=42.5,
            finish_reason="stop",
            reasoning_content="step 1: check weight trend",
            cost_usd=0.0007,
        )

    async def close(self) -> None:
        pass


def _make_daemon(tmp_path, llm, inbox, canary_mode: str = "live") -> SailTickDaemon:
    cfg = SailTickConfig(
        data_dir=str(tmp_path / "data"),
        db_path=str(tmp_path / "db" / "sailtick.db"),
        log_dir=str(tmp_path / "logs"),
        api_port=19071,
        sail_server=SailServerConfig(api_base="http://127.0.0.1:9/api/v1"),
        tick=TickConfig(hours=[0, 6, 12, 18], work_budget_minutes=180),
        canary=CanaryConfig(mode=canary_mode),
        config_dir=os.getcwd(),
    )
    d = SailTickDaemon(cfg)
    d.llm = llm
    d.inbox = inbox
    d.scanner = TracingFakeScanner()
    d.notifier.inbox = inbox
    d.engine.llm = llm
    d.engine.inbox = inbox
    d.engine.scanner = d.scanner
    return d


def test_sanitize_text_redacts_secrets():
    raw = "Authorization: Bearer super_secret_token_99999 key=sk-abcdef1234567890 postgresql://user:pass123@host:5432/db"
    cleaned = sanitize_text(raw)
    assert "super_secret_token_99999" not in cleaned
    assert "sk-abcdef1234567890" not in cleaned
    assert "pass123" not in cleaned
    assert "Bearer ***" in cleaned
    assert "sk-***" in cleaned


@pytest.mark.asyncio
async def test_tick_engine_records_full_ai_trace_and_spans(tmp_path):
    plan_json = json.dumps(
        {
            "summary": "早间巡检完成，询问晨起体重并更新画像",
            "tickets": [
                {
                    "type": "question",
                    "topic": "morning_weight",
                    "title": "今早体重多少？",
                    "body": "方便记录一下",
                    "priority": "normal",
                },
                {
                    "type": "question",
                    "topic": "second_q",
                    "title": "第二个问题应被限流",
                    "body": "将被 max_questions_per_tick 拦截",
                    "priority": "normal",
                },
            ],
            "actions": [
                {"kind": "profile_update", "key": "wake_time", "value": "07:30", "confidence": 0.9},
                {"kind": "episode", "content": "测试记录"},
            ],
            "unfinished": [],
            "next_tick_suggestions": ["午间关注饮食"],
        },
        ensure_ascii=False,
    )
    inbox = TracingFakeInbox()
    llm = TracingFakeLLM([plan_json])
    d = _make_daemon(tmp_path, llm, inbox, canary_mode="live")
    d.config.notify.max_questions_per_tick = 1
    await d.db.connect()
    try:
        res = await d.engine.run_tick("morning_checkin", tick_date="2026-11-23")
        assert res["status"] == "completed"
        trace_id = res["trace_id"]
        assert trace_id

        # 1. 本地隔离库可完整查回 Trace 与 Spans
        local_trace = await d.db.get_trace(trace_id)
        assert local_trace is not None
        assert local_trace["status"] == "completed"
        assert local_trace["plan_source"] == "llm"
        assert local_trace["llm_calls_count"] == 1
        assert local_trace["prompt_tokens"] == 250
        assert local_trace["completion_tokens"] == 100
        assert local_trace["total_tokens"] == 350
        assert local_trace["tickets_created"] == 1
        assert local_trace["tickets_throttled"] == 1
        assert local_trace["actions_executed"] == 2
        assert local_trace["actions_failed"] == 0

        stages = [sp["stage"] for sp in local_trace["spans"]]
        for expected in ("wake", "scan", "plan", "llm_call", "throttle", "work", "ticket_emit", "work_action", "handoff"):
            assert expected in stages, f"missing stage {expected} in {stages}"

        llm_span = next(sp for sp in local_trace["spans"] if sp["stage"] == "llm_call")
        assert llm_span["payload"]["model"] == "deepseek-chat"
        assert llm_span["payload"]["parse_ok"] is True
        assert "今早体重多少" in llm_span["payload"]["response_text"]
        assert llm_span["payload"]["reasoning_content"] == "step 1: check weight trend"
        assert llm_span["payload"]["prompt_chars"] > 100

        throttle_span = next(sp for sp in local_trace["spans"] if sp["stage"] == "throttle")
        assert throttle_span["status"] == "degraded"
        assert len(throttle_span["payload"]["dropped"]) == 1

        # 2. 已异步上报至 sail_server
        assert len(inbox.reported_traces) == 1
        assert inbox.reported_traces[0]["trace_id"] == trace_id
    finally:
        await d.db.close()


@pytest.mark.asyncio
async def test_tick_engine_traces_llm_error_and_canary_paused(tmp_path):
    inbox = TracingFakeInbox()
    llm = TracingFakeLLM([RuntimeError("LLM gateway timeout 504")])
    d = _make_daemon(tmp_path, llm, inbox, canary_mode="live")
    await d.db.connect()
    try:
        res = await d.engine.run_tick("midday_checkin", tick_date="2026-11-23")
        assert res["plan_source"] == "fallback_error"
        tr = await d.db.get_trace(res["trace_id"])
        assert tr is not None
        assert tr["plan_source"] == "fallback_error"
        assert "timeout 504" in (tr["error"] or "")
        llm_span = next(sp for sp in tr["spans"] if sp["stage"] == "llm_call")
        assert llm_span["status"] == "error"
        assert llm_span["payload"]["parse_ok"] is False

        # Canary off 态也记录 paused trace
        await d.canary.kill(reason="maintenance")
        paused_res = await d.engine.run_tick("evening_review", tick_date="2026-11-23")
        assert paused_res["status"] == "paused"
        paused_tr = await d.db.get_trace(paused_res["trace_id"])
        assert paused_tr is not None
        assert paused_tr["status"] == "paused"
        assert any(sp["stage"] == "canary" for sp in paused_tr["spans"])
    finally:
        await d.db.close()
