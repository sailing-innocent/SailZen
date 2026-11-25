# -*- coding: utf-8 -*-
# @file test_finance_integration.py
# @brief SailTick Finance 2.0 集成测试（FinanceAnalyticsEngine + Nightly + QuickCoachAgent + TickEngine）
# @author sailing-innocent
# @date 2026-11-25
# @version 1.0
# ---------------------------------

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest

from sailtick.config import SailTickConfig
from sailtick.db import TickDatabase
from sailtick.finance_analytics import FinanceAnalyticsEngine
from sailtick.memory import AgentMemory
from sailtick.nightly import NightlySelfMaintenance
from sailtick.quick_agent import QuickCoachAgent


class _FakeFinanceClient:
    def __init__(self, pending_count: int = 1, months: Optional[List[Dict[str, Any]]] = None):
        self.created_txs: List[Dict[str, Any]] = []
        self.reconciled: List[Dict[str, Any]] = []
        self.hygiene_scans: List[Dict[str, Any]] = []
        self.created_proposals: List[Dict[str, Any]] = []
        self.pending_count = pending_count
        self.months = months if months is not None else [
            {"month": "2026-11", "total": 10, "expenses": 8, "untagged_expenses": 0, "needs_work": False},
            {"month": "2026-10", "total": 38, "expenses": 30, "untagged_expenses": 12, "needs_work": True},
            {"month": "2026-09", "total": 90, "expenses": 80, "untagged_expenses": 20, "needs_work": True},
        ]
        self.untagged_items: List[Dict[str, Any]] = [
            {"id": 501, "from_acc_id": 5, "to_acc_id": -1, "value": "88.00", "description": "冲牙器替换头", "exclude_from_stats": False},
        ]

    async def health(self) -> bool:
        return True

    async def get_overview(self, month: Optional[str] = None) -> Dict[str, Any]:
        return {
            "month": "2026-11",
            "today_expense": "68.50",
            "today_count": 2,
            "mtd_expense": "2450.00",
            "mtd_income": "18000.00",
            "mtd_net": "15550.00",
            "mtd_snack_total": "420.00",
            "mtd_snack_from_split": "95.00",
            "mtd_snack_pct": 17.1,
            "overall_tag_coverage_pct": 92.5,
            "pending_hygiene_count": self.pending_count,
            "auto_applied_hygiene_count": 5,
            "mtd_by_tag": [
                {"tag": "日用消耗", "amount": "1200.00", "count": 15, "pct": 49.0},
                {"tag": "零食", "amount": "420.00", "count": 12, "pct": 17.1},
            ],
            "silent_accounts": [
                {"account_id": 6, "name": "微信", "days_silent": 6, "last_tx_date": "2026-11-19"}
            ],
            "account_health": [
                {"id": 5, "name": "支付宝余额宝", "balance": "2802.69", "days_since_last_tx": 1, "last_reconciled_at": "2026-11-20"},
                {"id": 6, "name": "微信", "balance": "349.81", "days_since_last_tx": 6, "last_reconciled_at": None},
            ],
        }

    async def get_hygiene_months(self) -> Dict[str, Any]:
        return {
            "months": self.months,
            "total_months": len(self.months),
            "months_need_work": sum(1 for m in self.months if m["needs_work"]),
            "legacy_fix_unclassified": 0,
        }

    async def list_untagged_window(self, **kwargs) -> List[Dict[str, Any]]:
        return list(self.untagged_items)

    async def list_tags(self) -> List[Dict[str, Any]]:
        return [{"name": "日用消耗"}, {"name": "零食"}, {"name": "交通"}]

    async def create_hygiene_proposal(self, **kwargs) -> Dict[str, Any]:
        self.created_proposals.append(kwargs)
        return {"created": True, "proposal": {"id": 100 + len(self.created_proposals), **kwargs}}

    async def create_transaction(self, **kwargs) -> Dict[str, Any]:
        tx = {"id": 900 + len(self.created_txs), "value": f"{kwargs['amount']:.2f}", "description": kwargs["description"]}
        self.created_txs.append(kwargs)
        return tx

    async def reconcile_account(self, **kwargs) -> Dict[str, Any]:
        self.reconciled.append(kwargs)
        return {"handling": "micro_adjusted", "drift_amount": "-8.50", "message": "已执行无感小额平账"}

    async def run_hygiene_scan(self, **kwargs) -> Dict[str, Any]:
        self.hygiene_scans.append(kwargs)
        is_bf = kwargs.get("created_by") == "sailtick_nightly_backfill"
        return {
            "auto_tagged_count": 10 if is_bf else 2,
            "legacy_fix_auto_classified": 0,
            "review_proposals_created": 1 if is_bf else 0,
        }


class _FakeRhythmClient:
    async def health(self) -> bool:
        return False


class _FakeInbox:
    async def health(self) -> bool:
        return False


class _FakeScanner:
    async def collect_deep(self, days: int = 90) -> Dict[str, Any]:
        now = datetime(2026, 11, 25, 0, 5)
        return {
            "health_ok": True,
            "weight": [],
            "diet": [],
            "sleep": [],
            "exercise": [],
            "mood": [],
            "finance_food": [],
            "rhythm_history": {},
            "rhythm_projects": [],
            "rhythm_affairs": [],
            "finance_accounts": [{"id": 5, "name": "支付宝余额宝", "balance": "2802.69", "meta": {}}],
            "finance_overview": await _FakeFinanceClient().get_overview(),
            "finance_transactions": [
                {
                    "id": 1,
                    "from_acc_id": 5,
                    "to_acc_id": -1,
                    "value": "128.00",
                    "description": "盒马采购",
                    "tags": "日用消耗,零食",
                    "exclude_from_stats": False,
                    "htime": (now - timedelta(days=2)).timestamp(),
                    "meta": {
                        "items": [
                            {"name": "薯片", "amount": "42.00", "tag": "零食", "is_snack": True},
                            {"name": "洗衣液", "amount": "86.00", "tag": "日用消耗", "is_snack": False},
                        ]
                    },
                },
                {
                    "id": 2,
                    "from_acc_id": 5,
                    "to_acc_id": -1,
                    "value": "500.00",
                    "description": "balance fix",
                    "tags": "",
                    "exclude_from_stats": True,
                    "htime": (now - timedelta(days=3)).timestamp(),
                    "meta": {},
                },
                {
                    "id": 3,
                    "from_acc_id": 5,
                    "to_acc_id": -1,
                    "value": "230.00",
                    "description": "12306高铁票",
                    "tags": "交通",
                    "exclude_from_stats": False,
                    "htime": (now - timedelta(days=4)).timestamp(),
                    "meta": {},
                },
            ],
        }


class _StubFastLLM:
    def __init__(self, json_reply: str):
        self.json_reply = json_reply
        self.config = type("Cfg", (), {"providers": {"deepseek": object()}})()

    async def chat_fast(self, *args, **kwargs):
        return type(
            "Resp",
            (),
            {
                "content": self.json_reply,
                "provider": "deepseek",
                "model": "deepseek-chat",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "cost_usd": 0.0001,
            },
        )()


def test_finance_analytics_engine_excludes_adjustments_and_counts_split_snacks():
    fixed_now = datetime(2026, 11, 25, 0, 5)
    engine = FinanceAnalyticsEngine(clock=lambda: fixed_now)
    deep_pkg = {
        "finance_accounts": [{"id": 5, "name": "支付宝", "meta": {}}],
        "finance_overview": {"overall_tag_coverage_pct": 88.0, "pending_hygiene_count": 2, "silent_accounts": []},
        "finance_transactions": [
            {
                "id": 1,
                "from_acc_id": 5,
                "to_acc_id": -1,
                "value": "128.00",
                "description": "盒马鲜生",
                "tags": "日用消耗,零食",
                "exclude_from_stats": False,
                "htime": datetime(2026, 11, 20, 19, 0).timestamp(),
                "meta": {
                    "items": [
                        {"name": "零食", "amount": "42.00", "tag": "零食", "is_snack": True},
                        {"name": "日用", "amount": "86.00", "tag": "日用消耗", "is_snack": False},
                    ]
                },
            },
            {
                "id": 2,
                "from_acc_id": 5,
                "to_acc_id": -1,
                "value": "999.00",
                "description": "小额无感平账",
                "tags": "",
                "exclude_from_stats": True,
                "htime": datetime(2026, 11, 21, 10, 0).timestamp(),
                "meta": {},
            },
        ],
    }
    res = engine.analyze(deep_pkg)
    assert res["mtd_expense"] == 128.0
    assert res["mtd_snack_total"] == 42.0
    assert res["mtd_snack_from_split"] == 42.0
    assert res["projected_eom_expense"] > 128.0
    assert any("零食" in s for s in res["insights"])


@pytest.mark.asyncio
async def test_nightly_compiles_finance_into_expert_brief(tmp_path):
    cfg = SailTickConfig(db_path=str(tmp_path / "sailtick.db"), data_dir=str(tmp_path))
    db = TickDatabase(cfg.db_path)
    await db.connect()
    try:
        mem = AgentMemory(db)
        fin_client = _FakeFinanceClient()
        nightly = NightlySelfMaintenance(
            config=cfg,
            db=db,
            memory=mem,
            scanner=_FakeScanner(),
            finance_client=fin_client,
            clock=lambda: datetime(2026, 11, 25, 0, 5),
        )
        stage1 = await nightly.run_modeling_stage()
        # 1 次近期 14 天巡检 + 1 次按月历史回溯（跳过整洁的 2026-11，只推进 2026-10）
        assert len(fin_client.hygiene_scans) == 2
        brief = stage1["expert_brief"]
        assert "finance" in brief
        assert brief["finance"]["mtd_expense"] == 358.0
        assert brief["finance"]["mtd_snack_total"] == 42.0
        bf = brief["finance"]["backfill"]
        assert bf["status"] == "in_progress"
        assert bf["last_month_processed"] == "2026-10"
        assert bf["cursor_month"] == "2026-09"
        assert "2026-11" in bf["completed_months"] and "2026-10" in bf["completed_months"]
        prompt_text = NightlySelfMaintenance.format_brief_for_prompt(brief)
        assert "财务开销画像" in prompt_text
        assert "历史慢迭代" in prompt_text
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_nightly_backfill_multi_night_cursor_and_backpressure(tmp_path):
    """验证夜间慢迭代：第1晚推进2026-10→第2晚因待审水位满暂停→用户消化后第3晚推进2026-09并收尾，且阶段2慢脑长尾研判仅入待审。"""
    cfg = SailTickConfig(db_path=str(tmp_path / "sailtick.db"), data_dir=str(tmp_path))
    cfg.nightly.finance_backfill_pending_cap = 5
    cfg.nightly.finance_backfill_max_new_reviews_per_night = 3
    db = TickDatabase(cfg.db_path)
    await db.connect()
    try:
        mem = AgentMemory(db)
        fin_client = _FakeFinanceClient(pending_count=1)
        llm_stub = type(
            "Llm",
            (),
            {
                "chat": staticmethod(
                    lambda *a, **kw: _async_val(
                        type(
                            "R",
                            (),
                            {
                                "content": '{"suggestions":[{"id":501,"tags":"日用消耗","confidence":0.82,"reason":"口腔护理日用品"}]}'
                            },
                        )()
                    )
                )
            },
        )()

        class _ScannerWithClient(_FakeScanner):
            async def collect_deep(self, days: int = 90) -> Dict[str, Any]:
                pkg = await super().collect_deep(days=days)
                pkg["finance_overview"] = await fin_client.get_overview()
                return pkg

        nightly = NightlySelfMaintenance(
            config=cfg,
            db=db,
            memory=mem,
            scanner=_ScannerWithClient(),
            llm=llm_stub,
            finance_client=fin_client,
            clock=lambda: datetime(2026, 11, 25, 0, 5),
        )

        # 第 1 晚：推进 2026-10，并由阶段 2c 慢脑研判 1 条长尾进入待审
        s1 = await nightly.run_modeling_stage()
        assert s1["finance"]["backfill"]["last_month_processed"] == "2026-10"
        assert s1["finance"]["backfill"]["cursor_month"] == "2026-09"
        lt_res = await nightly._run_nightly_finance_llm_longtail(s1["deep_pkg"])
        assert lt_res["proposals_created"] == 1
        assert len(fin_client.created_proposals) == 1

        # 第 2 晚：待审队列达到水位上限 5 -> 自动暂停，绝不深挖 2026-09
        fin_client.pending_count = 5
        scans_before = len(fin_client.hygiene_scans)
        s2 = await nightly.run_modeling_stage()
        assert s2["finance"]["backfill"]["status"] == "paused_backpressure"
        assert len(fin_client.hygiene_scans) == scans_before + 1  # 只跑近期巡检（且预算为 0），不跑历史月

        # 第 3 晚：用户随手消化到 2 条 -> 恢复推进最后一个月 2026-09 并标记 completed
        fin_client.pending_count = 2
        s3 = await nightly.run_modeling_stage()
        assert s3["finance"]["backfill"]["last_month_processed"] == "2026-09"
        assert s3["finance"]["backfill"]["status"] == "completed"
        assert s3["finance"]["backfill"]["cursor_month"] is None
    finally:
        await db.close()


async def _async_val(v):
    return v


@pytest.mark.asyncio
async def test_quick_agent_finance_commands_and_actions(tmp_path):
    cfg = SailTickConfig(db_path=str(tmp_path / "sailtick.db"), data_dir=str(tmp_path))
    db = TickDatabase(cfg.db_path)
    await db.connect()
    try:
        mem = AgentMemory(db)
        fin_client = _FakeFinanceClient()
        llm = _StubFastLLM(
            '{"reply":"已帮你记入盒马采购 128 元（拆分零食 42 + 日用 86）","actions":['
            '{"kind":"finance_log_tx","amount":128,"description":"盒马采购","direction":"expense","tags":"日用消耗,零食","account_hint":"支付宝",'
            '"items":[{"name":"零食","amount":"42.00","tag":"零食","is_snack":true},{"name":"日用","amount":"86.00","tag":"日用消耗","is_snack":false}]}]}'
        )
        agent = QuickCoachAgent(
            config=cfg,
            db=db,
            memory=mem,
            inbox=_FakeInbox(),
            llm=llm,
            rhythm=_FakeRhythmClient(),
            finance=fin_client,
            clock=lambda: datetime(2026, 11, 25, 15, 0),
        )

        # 1. /money 零延迟指令
        r_money = await agent.handle_message("/money")
        assert "财务开销秘书" in r_money["reply"]
        assert "420.00" in r_money["reply"]

        # 2. /accounts 零延迟指令
        r_acc = await agent.handle_message("/accounts")
        assert "支付宝余额宝" in r_acc["reply"]

        # 3. 自然语言记账 + 拆分明细 -> finance_updated=True
        r_log = await agent.handle_message("盒马花了128，零食42日用86，支付宝")
        assert r_log["finance_updated"] is True
        assert len(fin_client.created_txs) == 1
        assert len(fin_client.created_txs[0]["items"]) == 2
    finally:
        await db.close()
