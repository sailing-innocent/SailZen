# -*- coding: utf-8 -*-
# @file test_tick_engine.py
# @brief TickEngine 状态机单元测试（mock 外部服务）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest
import pytest_asyncio

from sailtick.config import LLMConfig, LLMProviderConfig, SailTickConfig, SailServerConfig
from sailtick.daemon import SailTickDaemon
from sailtick.llm import LLMResponse


class FakeInbox:
    """模拟 sail_server 票据客户端。"""

    def __init__(self):
        self.tickets: List[dict] = []
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

    async def create_ticket(self, tick_id: str, ticket_type: str, title: str, body: str,
                            priority: str = "normal", expected_reply_hours=None,
                            fallback_assumption: str = "", channel: str = "web") -> Dict[str, Any]:
        t = {
            "id": self._next_id, "tick_id": tick_id, "type": ticket_type, "title": title,
            "status": "pending", "priority": priority, "fallback_assumption": fallback_assumption,
        }
        self._next_id += 1
        self.tickets.append(t)
        return t

    async def close(self) -> None:
        pass


class FakeScanner:
    def __init__(self):
        self.reachable = True

    async def health(self) -> bool:
        return self.reachable

    async def scan(self, days: int = 7) -> Dict[str, Any]:
        if not self.reachable:
            return {"health_ok": False}
        return {
            "health_ok": True,
            "window_days": days,
            "weight": [{"date": "2026-11-08", "value": 72.5}],
            "sleep": [{"date": "2026-11-08", "hours": 7}],
            "diet": None, "exercise": None, "mood": None,
            "finance_food": None, "rhythm_checkins": None, "notes": None,
        }

    def describe(self, package: Dict[str, Any]) -> str:
        return "体重 72.5kg，睡眠 7h" if package.get("health_ok") else "数据不可用"

    async def close(self) -> None:
        pass


class FakeLLM:
    """可编程 LLM：按队列返回响应。"""

    def __init__(self, responses: Optional[List[str]] = None):
        self.responses = list(responses or [])
        self.tick_tokens = 0
        self.budget_exceeded = False
        self.config = LLMConfig(
            providers={"fake": LLMProviderConfig(api_key="fake-key", model="fake")}
        )

    def begin_tick(self) -> None:
        self.tick_tokens = 0

    async def chat(self, prompt: str, **kwargs) -> LLMResponse:
        content = self.responses.pop(0) if self.responses else "{}"
        self.tick_tokens += 100
        return LLMResponse(content=content, usage={"total_tokens": 100}, model="fake", provider="fake")

    async def close(self) -> None:
        pass


def make_daemon(tmp_path, llm=None, inbox=None, scanner=None, tick_hours=None) -> SailTickDaemon:
    cfg = SailTickConfig(
        data_dir=str(tmp_path / "data"),
        db_path=str(tmp_path / "db" / "sailtick.db"),
        log_dir=str(tmp_path / "logs"),
        api_port=19070,
        sail_server=SailServerConfig(api_base="http://127.0.0.1:9/api/v1"),
        tick=__import__("sailtick.config", fromlist=["TickConfig"]).TickConfig(
            hours=tick_hours or [0, 6, 12, 18], work_budget_minutes=180
        ),
        config_dir=os.getcwd(),
    )
    d = SailTickDaemon(cfg)
    d.inbox = inbox or FakeInbox()
    d.scanner = scanner or FakeScanner()
    if llm is not None:
        d.engine.llm = llm
        # 重新接线 cost sink
        d.engine.llm._cost_sink = d._record_cost
    d.engine.inbox = d.inbox
    d.engine.scanner = d.scanner
    d.notifier.inbox = d.inbox  # notify 与 engine 共用 fake inbox
    d.engine.notifier = d.notifier
    return d


@pytest_asyncio.fixture()
async def daemon(tmp_path):
    d = make_daemon(tmp_path)
    await d.db.connect()
    yield d
    await d.db.close()


# ── 状态机 ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_tick_fallback_plan(tmp_path):
    """无 LLM 时走规则模板：完整跑完 SCAN→PLAN→WORK→HANDOFF。"""
    d = make_daemon(tmp_path)
    await d.db.connect()
    result = await d.engine.run_tick("morning_checkin")
    assert result["status"] == "completed"

    ticks = await d.db.list_ticks()
    assert ticks[0]["state"] == "completed"

    handoffs = await d.db.list_handoffs()
    assert len(handoffs) == 1
    assert os.path.exists(handoffs[0]["path"])

    # fallback 计划含 1 张体重问题票据
    assert len(d.inbox.tickets) == 1
    assert "体重" in d.inbox.tickets[0]["title"]
    await d.db.close()


@pytest.mark.asyncio
async def test_tick_llm_plan_and_ticket_throttle(tmp_path):
    """LLM 计划被采用；票据节流每 Tick 最多 2 张。"""
    plan = {
        "summary": "午间巡检",
        "tickets": [
            {"type": "question", "title": f"问题{i}", "body": "b", "priority": "normal",
             "expected_reply_hours": 48, "fallback_assumption": "f"}
            for i in range(4)  # LLM 试图发 4 张
        ],
        "actions": [{"kind": "episode", "content": "note"}],
        "unfinished": [], "next_tick_suggestions": ["s"],
    }
    llm = FakeLLM(responses=[json.dumps(plan, ensure_ascii=False)])
    d = make_daemon(tmp_path, llm=llm)
    await d.db.connect()
    result = await d.engine.run_tick("midday_checkin")
    assert result["status"] == "completed"
    assert result["plan"]["summary"] == "午间巡检"
    assert len(d.inbox.tickets) == 2  # 截断到 2 张
    await d.db.close()


@pytest.mark.asyncio
async def test_llm_invalid_json_falls_back(tmp_path):
    """LLM 返回非法 JSON → 规则模板兜底。"""
    llm = FakeLLM(responses=["not json at all {{{"])
    d = make_daemon(tmp_path, llm=llm)
    await d.db.connect()
    result = await d.engine.run_tick("evening_review")
    assert result["status"] == "completed"
    assert len(d.inbox.tickets) == 0  # evening_review fallback 无票据
    await d.db.close()


@pytest.mark.asyncio
async def test_duplicate_tick_skipped(tmp_path):
    """幂等键防重：同 slot 同一天不重复跑。"""
    d = make_daemon(tmp_path)
    await d.db.connect()
    r1 = await d.engine.run_tick("morning_checkin")
    assert r1["status"] == "completed"

    # 模拟另一个并发实例试图跑同一天的同一 slot
    d2 = make_daemon(tmp_path)
    await d2.db.connect()
    d2.engine._current_tick = None
    tick = await d2.db.create_tick("morning_checkin", datetime.now().strftime("%Y-%m-%d"))
    assert tick["state"] == "completed"  # 已完成的 tick 直接返回
    await d2.db.close()
    await d.db.close()


@pytest.mark.asyncio
async def test_tick_failed_marks_state(tmp_path):
    """WORK 阶段异常 → tick 标记 failed 并抛出。"""
    d = make_daemon(tmp_path)
    await d.db.connect()

    class ExplodingInbox(FakeInbox):
        async def create_ticket(self, **kwargs):
            raise RuntimeError("boom")

    d.engine.notifier.inbox = ExplodingInbox()  # notify 内部会吞掉 → 改用直接异常路径

    # 让 _work 抛异常验证失败路径
    async def bad_work(context, tick, deadline):
        raise RuntimeError("work exploded")

    d.engine._work = bad_work
    with pytest.raises(RuntimeError):
        await d.engine.run_tick("midday_checkin")
    ticks = await d.db.list_ticks()
    assert ticks[0]["state"] == "failed"
    assert "work exploded" in ticks[0]["error"]
    await d.db.close()


@pytest.mark.asyncio
async def test_interrupt_running_ticks(tmp_path):
    """daemon 重启时残留 running tick → interrupted。"""
    d = make_daemon(tmp_path)
    await d.db.connect()
    t = await d.db.create_tick("nightly_maintenance", "2026-11-08")
    await d.db.update_tick(t["id"], state="running")
    n = await d.engine.interrupt_running_ticks()
    assert n == 1
    got = await d.db.get_tick(t["id"])
    assert got["state"] == "interrupted"
    await d.db.close()


@pytest.mark.asyncio
async def test_work_budget_records_unfinished(tmp_path):
    """WORK 超预算时剩余任务记入未完成事项。"""
    d = make_daemon(tmp_path)
    await d.db.connect()

    plan = {
        "summary": "s",
        "tickets": [
            {"type": "question", "title": f"q{i}", "body": "b"}
            for i in range(10)
        ],
        "actions": [], "unfinished": [], "next_tick_suggestions": [],
    }
    llm = FakeLLM(responses=[json.dumps(plan, ensure_ascii=False)])
    d.engine.llm = llm

    # 把截止时间拨到过去，模拟预算耗尽
    from datetime import datetime as dt

    original_work = d.engine._work

    async def fake_work(context, tick, deadline):
        await original_work(context, tick, dt.now() - timedelta(minutes=1))

    d.engine._work = fake_work
    result = await d.engine.run_tick("midday_checkin")
    # 所有（被 PLAN 节流后的）票据都没来得及发，全部记入未完成
    assert len(d.inbox.tickets) == 0
    assert len(result["plan"]["unfinished"]) == 2  # PLAN 节流上限
    await d.db.close()
