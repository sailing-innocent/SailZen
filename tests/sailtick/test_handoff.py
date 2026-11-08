# -*- coding: utf-8 -*-
# @file test_handoff.py
# @brief handoff 文档读写往返测试
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------

from __future__ import annotations

import os

import pytest
import pytest_asyncio

from sailtick.db import TickDatabase
from sailtick.handoff import HandoffDoc, HandoffManager


@pytest_asyncio.fixture()
async def env(tmp_path):
    db = TickDatabase(str(tmp_path / "t.db"))
    await db.connect()
    mgr = HandoffManager(db, str(tmp_path / "handoffs"))
    yield db, mgr
    await db.close()


@pytest.mark.asyncio
async def test_write_read_roundtrip(env):
    db, mgr = env
    doc = HandoffDoc(
        tick_id="abc123",
        slot="morning_checkin",
        tick_date="2026-11-09",
        prev_summary="早间巡检完成，体重 72.5kg",
        unfinished=[{"task": "发票据: 午饭预告", "reason": "预算耗尽", "priority": "high"}],
        plan_version="v0.1",
        plan_change="无变化",
        pending_tickets=[
            {"id": 3, "type": "question", "title": "今天体重？",
             "expected_reply_by": "2026-11-10T06:00:00", "fallback_assumption": "维持上次"}
        ],
        user_status="睡眠 7h，情绪平稳",
        next_tick_suggestions=["晚间复盘今日摄入"],
    )
    path = await mgr.write(doc)
    assert os.path.exists(path)

    loaded = await mgr.read_latest()
    assert loaded is not None
    assert loaded.tick_id == "abc123"
    assert loaded.slot == "morning_checkin"
    assert loaded.prev_summary == "早间巡检完成，体重 72.5kg"
    assert loaded.plan_version == "v0.1"
    assert loaded.user_status == "睡眠 7h，情绪平稳"
    # 未完成事项与票据在 markdown 中保留（结构完整性）
    with open(path, encoding="utf-8") as f:
        md = f.read()
    assert "午饭预告" in md
    assert "今天体重？" in md
    assert "晚间复盘今日摄入" in md


@pytest.mark.asyncio
async def test_markdown_sections_parsed(env):
    db, mgr = env
    doc = HandoffDoc(
        tick_id="t1", slot="evening_review", tick_date="2026-11-09",
        prev_summary="晚间复盘",
        plan_version="v0.2",
    )
    md = doc.to_markdown()
    parsed = HandoffDoc.from_markdown(md)
    assert parsed.prev_summary == "晚间复盘"
    assert parsed.plan_version == "v0.2"


@pytest.mark.asyncio
async def test_read_for_specific_slot(env):
    db, mgr = env
    for slot in ("morning_checkin", "evening_review"):
        await mgr.write(HandoffDoc(tick_id=f"t-{slot}", slot=slot, tick_date="2026-11-09"))
    got = await mgr.read_for_tick("2026-11-09", "morning_checkin")
    assert got is not None and got.slot == "morning_checkin"
    assert (await mgr.read_for_tick("2026-11-09", "midday_checkin")) is None
