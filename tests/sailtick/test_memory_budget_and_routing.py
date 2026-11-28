# -*- coding: utf-8 -*-
# @file test_memory_budget_and_routing.py
# @brief SailTick Round 2 单元测试：记忆去重/硬预算/FTS5/压实/冷归档、JSON自愈、Slot模型路由、食物清洗与快脑分域
# @author sailing-innocent
# @date 2026-11-28
# @version 1.0
# ---------------------------------

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from sailtick.config import LLMConfig, LLMProviderConfig, SailTickConfig
from sailtick.context_budget import (
    PromptBudgeter,
    infer_ticket_domain,
    parse_json_with_repair,
)
from sailtick.db import TickDatabase
from sailtick.knowledge import HealthKnowledgeManager
from sailtick.llm import LLMGateway, LLMResponse
from sailtick.memory import AgentMemory
from sailtick.quick_agent import QuickCoachAgent


@pytest.mark.asyncio
async def test_memory_upsert_hard_budget_fts_and_compaction(tmp_path):
    db = TickDatabase(str(tmp_path / "sailtick.db"))
    await db.connect()
    try:
        mem = AgentMemory(db)

        # 1. 同 key 重复 save 必须幂等覆盖而非无限追加
        for i in range(5):
            await mem.save(
                "semantic",
                "diet_lunch_habit",
                {"detail": f"工作日午饭食堂观察第{i}次，偏好鸡胸肉配青菜与半碗米饭" * 8},
                domain="health",
                summary=f"工作日午餐偏食堂清淡高蛋白第{i}版",
            )
        rows = await mem.list("semantic", key_prefix="diet_lunch_habit")
        assert len(rows) == 1
        assert rows[0]["domain"] == "health"
        assert len(rows[0]["summary"]) <= 100

        # 2. 注入 30 条长语义记忆与 25 条 profile，验证 summary_for_prompt 严格守住字符预算
        for idx in range(25):
            await mem.set_profile(f"pref_{idx}", f"这是一个较长的用户偏好描述数值_{idx}_" + "x" * 60, 0.9, "asked")
        for idx in range(30):
            dom = ["health", "rhythm", "finance"][idx % 3]
            await mem.save(
                "semantic",
                f"pattern_{dom}_{idx}",
                {"raw": f"第{idx}条非常长的语义记忆原始观察正文" * 15},
                domain=dom,
                summary=f"{dom}域规律#{idx}：持续观察记录显示规律明确稳定且具有参考意义",
                salience=0.4 + (idx % 5) * 0.1,
            )

        summary = await mem.summary_for_prompt(
            slot="morning_checkin",
            profile_budget=900,
            semantic_budget=1200,
            procedural_budget=700,
        )
        assert summary["stats"]["profile_chars"] <= 900
        assert summary["stats"]["semantic_chars"] <= 1200
        assert summary["stats"]["procedural_chars"] <= 700
        assert summary["stats"]["total_chars"] <= 2800

        # 3. FTS5 毫秒快查命中中文记忆
        hits = await mem.search("食堂高蛋白", domain="health", limit=5)
        assert any(h["title"] == "diet_lunch_habit" for h in hits)

        # 4. 夜间压实：按每域上限归档多余低分记忆，保留原始数据
        comp = await mem.compact_memories(max_semantic_per_domain=5, max_procedural_per_domain=4)
        assert comp["archived"] > 0
        active_health = await mem.list("semantic", domain="health", status="active")
        assert len(active_health) <= 5
        archived_all = await mem.list("semantic", status="archived")
        assert len(archived_all) >= comp["archived"]

        # 5. 原始快照 gzip 落盘 + 旧事件冷归档
        snap = await mem.save_raw_snapshot(
            str(tmp_path / "snapshots"),
            tick_id="t1",
            slot="morning_checkin",
            tick_date="2026-11-28",
            kind="scan_7d",
            payload={"health_ok": True, "window_days": 7, "weight": [{"value": 73.5}]},
        )
        assert snap is not None
        with gzip.open(snap["file_path"], "rt", encoding="utf-8") as gz:
            restored = json.loads(gz.read())
        assert restored["weight"][0]["value"] == 73.5

        await mem.save_episode("t0", "scan", {"old": True})
        # 将刚写入的事件时间回拨 40 天以测试归档
        old_iso = (datetime.now() - timedelta(days=40)).isoformat()
        from sqlalchemy import text

        async with db.session() as s:
            await s.execute(text("UPDATE st_episodes SET created_at = :ts"), {"ts": old_iso})
            await s.commit()
        archived_ep = await mem.archive_old_episodes(str(tmp_path / "archives"), retention_days=30)
        assert archived_ep == 1
        assert await mem.list_episodes(limit=10) == []
    finally:
        await db.close()


def test_prompt_budgeter_and_json_repair():
    budgeter = PromptBudgeter()
    prompt, report = budgeter.build_plan_prompt(
        slot="morning_checkin",
        tick_date="2026-11-28",
        system_prompt="系统提示" * 800,
        slot_guidance="早间窗口",
        plan_text="计划" * 400,
        expert_brief_text="简报" * 600,
        memory_summary={"profile": "P" * 1500, "semantic": "S" * 3000, "procedural": "R" * 1200},
        prev_handoff_text="交接" * 300,
        weight_update_note="无更新",
        data_summary="数据" * 1500,
        replies_text="(无)",
        msgs_text="(无)",
        tickets_text="(无)",
        q_slice_text="(无)",
    )
    assert report["total_chars"] <= 12500
    assert "daily_report" not in report["allowed_action_kinds"]
    assert "finance_run_hygiene" not in report["allowed_action_kinds"]
    assert '"domain": "health|rhythm|finance|general"' in prompt

    # 尾逗号、缺少跨行逗号与截断 JSON 自愈
    broken1 = '```json\n{"summary": "ok", "tickets": [], "actions": [{"kind": "episode", "content": "hi",},]}\n```'
    obj1, repaired1, err1 = parse_json_with_repair(broken1)
    assert err1 is None and repaired1 is True and obj1["summary"] == "ok"

    broken2 = '{\n  "summary": "missing comma"\n  "tickets": []\n  "actions": []\n}'
    obj2, repaired2, err2 = parse_json_with_repair(broken2)
    assert err2 is None and repaired2 is True and obj2["summary"] == "missing comma"

    broken3 = '{"summary": "truncated", "tickets": [{"title": "hello"'
    obj3, repaired3, err3 = parse_json_with_repair(broken3)
    assert err3 is None and repaired3 is True and obj3["tickets"][0]["title"] == "hello"


def test_llm_slot_routing_and_food_cleaning():
    cfg = LLMConfig(
        default="deepseek",
        fast_provider="deepseek",
        fast_model="deepseek-chat",
        providers={"deepseek": LLMProviderConfig(api_key="test", model="deepseek-reasoner")},
        daily_soft_cap=40_000,
    )
    gw = LLMGateway(cfg)

    # 常规早间走 fast
    _, m1, r1 = gw.resolve_slot_route("morning_checkin", escalate=False, daily_tokens_so_far=5_000)
    assert m1 == "deepseek-chat" and r1 == "slot_fast"

    # 红线异常自动升档 default (reasoner)
    _, m2, r2 = gw.resolve_slot_route("morning_checkin", escalate=True, daily_tokens_so_far=5_000)
    assert m2 is None and r2 == "escalated_to_default"

    # 超过 daily_soft_cap 强制降档 fast
    _, m3, r3 = gw.resolve_slot_route("evening_review", escalate=True, daily_tokens_so_far=45_000)
    assert m3 == "deepseek-chat" and r3.startswith("daily_soft_cap_degraded")

    # 食物泛词与长句清洗（复现 11-28 生产垃圾词）
    for bad in ["主食", "蔬菜", "甜饮为主", "约贝纳颂蓝山咖啡含糖咖啡饮品", "一整条约的软质甜面包"]:
        assert HealthKnowledgeManager._clean_food_token(bad) == ""
    assert HealthKnowledgeManager._clean_food_token("烤冷面") == "烤冷面"
    assert HealthKnowledgeManager._clean_food_token("兰州牛肉面") == "兰州牛肉面"

    # 票据域推断
    assert infer_ticket_domain(topic="diet_lunch") == "health"
    assert infer_ticket_domain(topic="rhythm_key_projects") == "rhythm"
    assert infer_ticket_domain(title="微信余额差额确认") == "finance"


@pytest.mark.asyncio
async def test_quick_agent_domain_sessions_and_token_accounting(tmp_path):
    cfg = SailTickConfig(
        data_dir=str(tmp_path),
        db_path=str(tmp_path / "sailtick.db"),
    )
    db = TickDatabase(cfg.db_path)
    await db.connect()
    try:
        mem = AgentMemory(db)

        class FakeFastLLM:
            config = SimpleNamespace(providers={"deepseek": True})

            async def chat_fast(self, prompt, system=None, history=None, expect_json=True, max_tokens=900):
                return LLMResponse(
                    content=json.dumps(
                        {"reply": "收到，帮你记下下午 2 点会议。", "actions": []},
                        ensure_ascii=False,
                    ),
                    usage={"prompt_tokens": 320, "completion_tokens": 64, "total_tokens": 384},
                    model="deepseek-chat",
                    provider="deepseek",
                    cost_usd=0.0006,
                )

        class DummyClient:
            async def health(self):
                return False

        agent = QuickCoachAgent(
            config=cfg,
            db=db,
            memory=mem,
            inbox=DummyClient(),
            llm=FakeFastLLM(),
            rhythm=DummyClient(),
            finance=DummyClient(),
        )
        res_r = await agent.handle_message(
            "下午2点开会", channel="android", domain="rhythm", surface="android_plan"
        )
        assert res_r["domain"] == "rhythm"
        assert res_r["persona"] == "rhythm_planner"
        assert res_r["session_id"] == "owner:rhythm"

        # 验证 trace 正确记账非零 token（修复 quick_chat token=0 Bug）
        trace = await db.get_trace(res_r["trace_id"])
        assert trace is not None
        assert trace["prompt_tokens"] == 320
        assert trace["completion_tokens"] == 64
        assert trace["total_tokens"] == 384

        # 健康域会话严格隔离，不与 rhythm 会话串台
        res_h = await agent.handle_message(
            "美式咖啡多少大卡", channel="android", domain="health", surface="android_health"
        )
        assert res_h["session_id"] == "owner:health"
        r_hist = await db.list_quick_chat_history("owner:rhythm", limit=10)
        h_hist = await db.list_quick_chat_history("owner:health", limit=10)
        assert len(r_hist) == 2 and len(h_hist) == 2
        assert r_hist[0]["surface"] == "android_plan"
        assert h_hist[0]["surface"] == "android_health"
    finally:
        await db.close()
