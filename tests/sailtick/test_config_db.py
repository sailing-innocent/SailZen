# -*- coding: utf-8 -*-
# @file test_config_db.py
# @brief sailtick config / db 单元测试
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------

from __future__ import annotations

import os

import pytest
import pytest_asyncio
import yaml

from sailtick.config import load_config
from sailtick.db import TickDatabase


# ── config ──────────────────────────────────────────────────────────────────


def test_load_config_defaults(tmp_path, monkeypatch):
    """无配置文件时使用默认值，路径解析正常。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SAILTICK_CONFIG", raising=False)
    cfg = load_config("nonexistent.yaml")
    assert cfg.api_port == 9070
    assert cfg.tick.hours == [0, 6, 12, 18]
    assert os.path.isabs(cfg.db_path)


def test_load_config_from_yaml(tmp_path, monkeypatch):
    """yaml 配置 + 环境变量覆盖。"""
    config_file = tmp_path / "sailtick.yaml"
    config_file.write_text(
        yaml.safe_dump(
            {
                "sailtick": {
                    "api_port": 9123,
                    "tick": {"hours": [6, 18], "work_budget_minutes": 90},
                    "llm": {"default": "deepseek", "providers": {"deepseek": {"model": "deepseek-chat"}}},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SAILTICK_API_PORT", "9999")
    cfg = load_config(str(config_file))
    assert cfg.api_port == 9999  # env override wins
    assert cfg.tick.hours == [6, 18]
    assert cfg.tick.work_budget_minutes == 90
    assert cfg.llm.default == "deepseek"
    # 相对路径基于配置文件目录解析
    assert cfg.db_path.startswith(str(tmp_path))


def test_config_env_token_resolution(tmp_path, monkeypatch):
    r"""\${VAR} 形式引用环境变量。"""
    monkeypatch.setenv("MY_TICK_TOKEN", "secret-123")
    config_file = tmp_path / "sailtick.yaml"
    config_file.write_text(
        yaml.safe_dump(
            {"sailtick": {"sail_server": {"auth_token": "${MY_TICK_TOKEN}"}}}
        ),
        encoding="utf-8",
    )
    cfg = load_config(str(config_file))
    assert cfg.sail_server.auth_token == "secret-123"


# ── db ──────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture()
async def db(tmp_path):
    d = TickDatabase(str(tmp_path / "test.db"))
    await d.connect()
    yield d
    await d.close()


@pytest.mark.asyncio
async def test_tick_idempotency(db):
    """同 (slot, date) 幂等：重复创建返回同一实例。"""
    t1 = await db.create_tick("morning_checkin", "2026-11-09")
    t2 = await db.create_tick("morning_checkin", "2026-11-09")
    assert t1["id"] == t2["id"]
    t3 = await db.create_tick("evening_review", "2026-11-09")
    assert t3["id"] != t1["id"]


@pytest.mark.asyncio
async def test_tick_update_and_cost(db):
    t = await db.create_tick("morning_checkin", "2026-11-09")
    await db.update_tick(t["id"], plan={"summary": "x"})
    await db.add_tick_cost(t["id"], 100, 0.001)
    await db.add_tick_cost(t["id"], 50, 0.0005)
    got = await db.get_tick(t["id"])
    assert got["plan"]["summary"] == "x"
    assert got["cost_tokens"] == 150
    assert abs(got["cost_usd"] - 0.0015) < 1e-9


@pytest.mark.asyncio
async def test_handoff_and_plan(db, tmp_path):
    h = await db.create_handoff("tick1", str(tmp_path / "h.md"), "summary text")
    assert h["tick_id"] == "tick1"
    latest = await db.get_latest_handoff()
    assert latest["summary"] == "summary text"

    await db.create_plan("v0.1", "70kg", "content", "rationale", active=True)
    await db.create_plan("v0.2", "70kg", "content2", "rationale2", active=True)
    active = await db.get_active_plan()
    assert active["version"] == "v0.2"  # 后建 active 抢占
    assert len(await db.list_plans()) == 2


@pytest.mark.asyncio
async def test_memory_and_profile(db):
    await db.create_memory("semantic", "k1", {"a": 1}, ttl_seconds=3600)
    m = await db.get_memory("semantic", "k1")
    assert m["value"] == {"a": 1}

    await db.set_profile("goal_weight", "70kg", 1.0, "asked")
    p = await db.get_profile("goal_weight")
    assert p["value"] == "70kg"
    assert p["source"] == "asked"


@pytest.mark.asyncio
async def test_episodes_and_run_log(db):
    await db.create_episode("t1", "scan", {"ok": True})
    await db.create_episode("t1", "plan", {"src": "llm"})
    eps = await db.list_episodes(tick_id="t1")
    assert len(eps) == 2

    log = await db.create_run_log({"pipeline_id": "morning_checkin", "status": "started"})
    await db.update_run_log(log["id"], {"status": "completed"})
    stats = await db.get_stats()
    assert stats["st_run_log"] == 1
    assert stats["st_episodes"] == 2


@pytest.mark.asyncio
async def test_schedules(db):
    await db.create_schedule({"id": "tick_06", "name": "Tick morning", "slot": "morning_checkin"})
    await db.update_schedule("tick_06", {"last_run_status": "success"})
    schedules = await db.list_schedules()
    assert schedules[0]["slot"] == "morning_checkin"
    assert schedules[0]["last_run_status"] == "success"
    assert await db.delete_schedule("tick_06") is True
    assert await db.delete_schedule("tick_06") is False
