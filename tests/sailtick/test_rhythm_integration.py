# -*- coding: utf-8 -*-
# @file test_rhythm_integration.py
# @brief SailTick 接管 Rhythm 体系的完整单元与闭环集成测试
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""覆盖 SailTick Personal Agent（健康 + 节奏/项目统筹）的核心闭环：
1. RhythmAnalyticsEngine 夜间确定性分析（黄金时段、易跳过时段、过载预警、项目倒排风险）
2. NightlySelfMaintenance 编译统一 Health + Rhythm expert_brief 与 prompt 格式化
3. TickEngine WORK 阶段执行 rhythm_sync_timeline / rhythm_upsert_affair / rhythm_occupancy /
   rhythm_block_status / rhythm_transit_affair，以及综合睡前日报
4. QuickCoachAgent 快脑处理 /today、/projects、临时加会占位、新建项目及 LLM 自主重排（rhythm_updated=True）
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from sailtick.config import SailTickConfig
from sailtick.db import TickDatabase
from sailtick.handoff import HandoffManager
from sailtick.memory import AgentMemory
from sailtick.nightly import NightlySelfMaintenance
from sailtick.notify import NotificationEngine
from sailtick.quick_agent import QuickCoachAgent
from sailtick.rhythm_analytics import RhythmAnalyticsEngine
from sailtick.state import DependencyState
from sailtick.tick_engine import TickEngine


class _FakeInbox:
    def __init__(self) -> None:
        self.tickets: List[Dict[str, Any]] = []
        self.messages: List[Dict[str, Any]] = []
        self.reports: List[Dict[str, Any]] = []
        self.reminders: List[Dict[str, Any]] = []

    async def health(self) -> bool:
        return True

    async def pending_tickets(self) -> List[Dict[str, Any]]:
        return [t for t in self.tickets if t.get("status") == "pending"]

    async def sync_replies_since(self, since=None) -> List[Dict[str, Any]]:
        return []

    async def expire_overdue(self) -> int:
        return 0

    async def list_user_messages(self, **kwargs) -> List[Dict[str, Any]]:
        return []

    async def ingest_user_messages(self, ids, tick_id) -> int:
        return len(ids)

    async def create_user_message(self, **kwargs) -> Dict[str, Any]:
        msg = {"id": len(self.messages) + 1, **kwargs}
        self.messages.append(msg)
        return msg

    async def upsert_daily_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rep = {"id": len(self.reports) + 1, "pushed": True, **payload}
        self.reports.append(rep)
        return rep

    async def list_pending_reminders(self) -> List[Dict[str, Any]]:
        return list(self.reminders)

    async def create_reminder(self, **kwargs) -> Dict[str, Any]:
        rem = {"id": len(self.reminders) + 1, **kwargs}
        self.reminders.append(rem)
        return rem


class _FakeRhythmClient:
    def __init__(self) -> None:
        self.synced_timelines: List[Dict[str, Any]] = []
        self.affairs: List[Dict[str, Any]] = []
        self.milestones: List[Dict[str, Any]] = []
        self.occupancies: List[Dict[str, Any]] = []
        self.block_updates: List[Dict[str, Any]] = []
        self.transits: List[Dict[str, Any]] = []
        self.checkins: List[Dict[str, Any]] = []

    async def health(self) -> bool:
        return True

    async def get_dashboard(self, target_date=None) -> Dict[str, Any]:
        return {
            "date": "2026-11-24",
            "timeline": {
                "date": "2026-11-24",
                "day_id": 1,
                "plan_version": 2,
                "ai_rationale": "上午精力充沛先推进核心项目",
                "completed_minutes": 60,
                "planned_minutes": 180,
                "blocks": [
                    {
                        "id": 101,
                        "affair_id": 10,
                        "affair_title": "SailZen 重构核心接口",
                        "block_type": "focus",
                        "start_time": "2026-11-24T09:30:00",
                        "end_time": "2026-11-24T11:00:00",
                        "status": "DONE",
                        "pinned": False,
                        "ref": {"label": "SailZen 重构核心接口"},
                    },
                    {
                        "id": 102,
                        "affair_id": 11,
                        "affair_title": "下午测试验收",
                        "block_type": "focus",
                        "start_time": "2026-11-24T15:00:00",
                        "end_time": "2026-11-24T16:30:00",
                        "status": "PLANNED",
                        "pinned": False,
                        "ref": {"label": "下午测试验收"},
                    },
                ],
            },
            "projects": await self.list_projects(),
            "focus_affairs": [],
            "overdue_affairs": [],
            "occupancies": [],
        }

    async def list_projects(self) -> List[Dict[str, Any]]:
        return [
            {
                "affair_id": 10,
                "title": "SailZen 3.0 上线",
                "target_date": "2026-12-05",
                "days_left": 11,
                "completion_ratio": 0.5,
                "recent_14d_hours": 3.5,
                "milestones": [],
            }
        ]

    async def list_affairs(self, **kwargs) -> List[Dict[str, Any]]:
        return list(self.affairs)

    async def sync_ai_timeline(self, **kwargs) -> Dict[str, Any]:
        self.synced_timelines.append(kwargs)
        return {
            "date": str(kwargs.get("target_date")),
            "plan_version": len(self.synced_timelines) + 1,
            "created_count": len(kwargs.get("blocks") or []),
            "preserved_count": 1,
            "archived_count": 1,
        }

    async def create_affair(self, **kwargs) -> Dict[str, Any]:
        aid = len(self.affairs) + 20
        item = {"id": aid, **kwargs}
        self.affairs.append(item)
        return item

    async def update_affair(self, affair_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        return {"id": affair_id, **updates}

    async def add_milestone(self, venture_id: int, title: str, **kwargs) -> Dict[str, Any]:
        ms = {"id": len(self.milestones) + 200, "venture_id": venture_id, "title": title}
        self.milestones.append(ms)
        return ms

    async def transit_affair(self, affair_id: int, action: str, **kwargs) -> Dict[str, Any]:
        rec = {"affair_id": affair_id, "action": action, "state": "DONE", **kwargs}
        self.transits.append(rec)
        return rec

    async def create_occupancy(self, **kwargs) -> Dict[str, Any]:
        occ = {"id": len(self.occupancies) + 300, **kwargs}
        self.occupancies.append(occ)
        return occ

    async def set_block_status(self, block_id: int, status: str) -> Dict[str, Any]:
        rec = {"block_id": block_id, "status": status}
        self.block_updates.append(rec)
        return rec

    async def checkin(self, affair_id: int, **kwargs) -> Dict[str, Any]:
        rec = {"id": len(self.checkins) + 400, "affair_id": affair_id, **kwargs}
        self.checkins.append(rec)
        return rec


class _FakeScanner:
    async def health(self) -> bool:
        return True

    async def scan(self, days: int = 7) -> Dict[str, Any]:
        return {
            "health_ok": True,
            "window_days": days,
            "weight_monitor": {"latest_kg": 73.2, "delta_from_prev": -0.2, "avg_7d": 73.4, "recorded_today": True},
            "active_plan": {"target_weight": "70.0", "phase_name": "稳步期"},
            "diet": [],
            "user_messages": [],
            "rhythm": {
                "today_date": "2026-11-24",
                "completed_minutes": 90,
                "planned_minutes": 150,
                "today_blocks": [
                    {"id": 101, "title": "项目核心开发", "start": "09:30", "end": "11:00", "status": "DONE"}
                ],
                "projects": [
                    {"id": 10, "title": "SailZen 3.0", "target_date": "2026-12-05", "days_left": 11, "completion": 0.5}
                ],
            },
        }

    async def collect_deep(self, days: int = 90) -> Dict[str, Any]:
        return {
            "health_ok": True,
            "window_days": days,
            "weight": [{"date": "2026-11-20", "value": 74.0}, {"date": "2026-11-24", "value": 73.2}],
            "weight_monitor": {"latest_kg": 73.2},
            "active_plan": {"target_weight": "70.0"},
            "diet": [],
            "sleep": [],
            "exercise": [],
            "mood": [],
            "finance_food": [],
            "user_messages": [],
            "rhythm_history": {
                "days": [
                    {
                        "date": "2026-11-22",
                        "blocks": [
                            {"block_type": "focus", "start_time": "2026-11-22T09:30:00", "status": "DONE"},
                            {"block_type": "focus", "start_time": "2026-11-22T10:30:00", "status": "DONE"},
                            {"block_type": "career", "start_time": "2026-11-22T20:00:00", "status": "SKIPPED"},
                            {"block_type": "career", "start_time": "2026-11-22T21:00:00", "status": "SKIPPED"},
                        ],
                    }
                ]
            },
            "rhythm_projects": [
                {
                    "affair_id": 10,
                    "title": "关键产品发布",
                    "target_date": "2026-12-02",
                    "days_left": 8,
                    "completion_ratio": 0.3,
                    "recent_14d_hours": 0.2,
                    "milestones": [{"title": "完成验收", "state": "PLANNED"}],
                }
            ],
            "rhythm_affairs": [],
        }

    def describe(self, pkg: Dict[str, Any]) -> str:
        return "体重 73.2kg; 今日日程 1 块已完成; 活跃项目 SailZen 3.0"


class _ScriptedLLM:
    def __init__(self, json_reply: str) -> None:
        self.json_reply = json_reply
        self.tick_tokens = 120
        self.tick_usd = 0.001
        self.budget_exceeded = False
        self.config = type("Cfg", (), {"providers": {"mock": True}})()

    def begin_tick(self) -> None:
        pass

    async def chat(self, prompt: str, expect_json: bool = True, max_tokens: int = 1000):
        return type(
            "Resp",
            (),
            {
                "content": self.json_reply,
                "provider": "mock",
                "model": "mock-fast",
                "latency_ms": 12.0,
                "usage": {"prompt_tokens": 50, "completion_tokens": 70, "total_tokens": 120},
                "cost_usd": 0.001,
            },
        )()

    async def chat_fast(self, text: str, **kwargs):
        return await self.chat(text)


def test_rhythm_analytics_detects_golden_window_and_project_risk():
    engine = RhythmAnalyticsEngine(clock=lambda: datetime(2026, 11, 24, 0, 10))
    res = engine.analyze(
        {
            "rhythm_history": {
                "days": [
                    {
                        "date": "2026-11-23",
                        "blocks": [
                            {"block_type": "focus", "start_time": "2026-11-23T09:00:00", "status": "DONE"},
                            {"block_type": "focus", "start_time": "2026-11-23T10:30:00", "status": "DONE"},
                            {"block_type": "career", "start_time": "2026-11-23T19:30:00", "status": "SKIPPED"},
                            {"block_type": "career", "start_time": "2026-11-23T20:30:00", "status": "SKIPPED"},
                            {"block_type": "focus", "start_time": "2026-11-23T14:00:00", "status": "SKIPPED"},
                        ],
                    }
                ]
            },
            "rhythm_projects": [
                {
                    "affair_id": 10,
                    "title": "核心重构",
                    "target_date": "2026-12-01",
                    "days_left": 7,
                    "completion_ratio": 0.25,
                    "recent_14d_hours": 0.0,
                    "milestones": [{"title": "完成测试", "state": "PLANNED"}],
                }
            ],
            "rhythm_affairs": [],
        }
    )
    assert res["adherence_rate"] == 0.4
    assert res["overload_signal"] is True
    assert "上午(06-12)" in res["golden_windows"]
    assert "晚间(18-22)" in res["low_adherence_windows"]
    assert res["project_risks"][0]["risk"] == "at_risk"
    assert len(res["suggested_questions"]) == 1


@pytest.mark.asyncio
async def test_nightly_compiles_unified_health_and_rhythm_brief(tmp_path):
    cfg = SailTickConfig(db_path=str(tmp_path / "st.db"), data_dir=str(tmp_path))
    db = TickDatabase(cfg.db_path)
    await db.connect()
    try:
        mem = AgentMemory(db)
        nightly = NightlySelfMaintenance(
            config=cfg,
            db=db,
            memory=mem,
            scanner=_FakeScanner(),
            clock=lambda: datetime(2026, 11, 24, 0, 5),
        )
        res = await nightly.run_modeling_stage()
        brief = res["expert_brief"]
        assert "rhythm" in brief
        assert brief["rhythm"]["active_projects_count"] == 1
        assert brief["rhythm"]["project_risks"][0]["risk"] == "at_risk"
        assert "unexpected_meeting" in brief["flexible_playbooks"]

        prompt_str = NightlySelfMaintenance.format_brief_for_prompt(brief)
        assert "节奏执行画像" in prompt_str
        assert "关键产品发布" in prompt_str
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_tick_engine_executes_rhythm_work_actions_and_unified_report(tmp_path):
    cfg = SailTickConfig(db_path=str(tmp_path / "st.db"), data_dir=str(tmp_path))
    db = TickDatabase(cfg.db_path)
    await db.connect()
    try:
        mem = AgentMemory(db)
        inbox = _FakeInbox()
        rhythm = _FakeRhythmClient()
        llm = _ScriptedLLM(
            """{
              "summary": "已自主编排今日时间线并建好新项目",
              "tickets": [],
              "actions": [
                {
                  "kind": "rhythm_upsert_affair",
                  "title": "个人知识库升级",
                  "kind_name": "venture",
                  "target_date": "2026-12-30",
                  "milestones": ["设计方案", "落地验证"]
                },
                {
                  "kind": "rhythm_sync_timeline",
                  "date": "2026-11-24",
                  "rationale": "上午黄金时段推核心项目，下午留白缓冲。",
                  "blocks": [
                    {"title": "项目核心推进", "start": "09:30", "end": "11:00", "block_type": "focus"}
                  ]
                },
                {"kind": "rhythm_occupancy", "date": "2026-11-24", "occupancy_type": "meeting", "start": "14:00", "end": "15:00", "label": "同步会"},
                {"kind": "rhythm_block_status", "block_id": 101, "status": "DONE"},
                {"kind": "rhythm_transit_affair", "affair_id": 11, "action": "finish"}
              ],
              "unfinished": [],
              "next_tick_suggestions": []
            }"""
        )
        engine = TickEngine(
            config=cfg,
            db=db,
            memory=mem,
            llm=llm,
            inbox=inbox,
            scanner=_FakeScanner(),
            notifier=NotificationEngine(cfg.notify, inbox=inbox),
            handoffs=HandoffManager(db, str(tmp_path / "handoffs")),
            state=DependencyState(),
            rhythm=rhythm,
            clock=lambda: datetime(2026, 11, 24, 6, 5),
        )
        out = await engine.run_tick("morning_checkin")
        assert out["status"] == "completed"
        assert len(rhythm.affairs) == 1
        assert len(rhythm.milestones) == 2
        assert len(rhythm.synced_timelines) == 1
        assert len(rhythm.occupancies) == 1
        assert len(rhythm.block_updates) == 1
        assert len(rhythm.transits) == 1

        # 睡前综合日报兜底应包含节奏与项目进度
        rep_out = await engine.run_tick("pre_sleep_report", idempotency_suffix="r1")
        assert rep_out["status"] == "completed"
        assert len(inbox.reports) == 1
        assert "节奏" in inbox.reports[0]["body_markdown"]
        assert "SailZen 3.0" in inbox.reports[0]["body_markdown"]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_quick_agent_commands_and_live_rhythm_scheduling(tmp_path):
    cfg = SailTickConfig(db_path=str(tmp_path / "st.db"), data_dir=str(tmp_path))
    db = TickDatabase(cfg.db_path)
    await db.connect()
    try:
        mem = AgentMemory(db)
        inbox = _FakeInbox()
        rhythm = _FakeRhythmClient()

        # 1. 无 LLM 场景：/today、/projects、临时加会占位、一句话建项目
        qa = QuickCoachAgent(
            config=cfg,
            db=db,
            memory=mem,
            inbox=inbox,
            llm=None,
            rhythm=rhythm,
            clock=lambda: datetime(2026, 11, 24, 13, 0),
        )
        today_res = await qa.handle_message("/today")
        assert "SailZen 重构核心接口" in today_res["reply"]

        proj_res = await qa.handle_message("/projects")
        assert "SailZen 3.0 上线" in proj_res["reply"]

        meet_res = await qa.handle_message("下午2:00-4:00临时加会评审")
        assert meet_res["rhythm_updated"] is True
        assert len(rhythm.occupancies) == 1
        assert rhythm.occupancies[0]["start"] == "14:00"
        assert rhythm.occupancies[0]["end"] == "16:00"

        new_proj = await qa.handle_message("新建项目：个人博客2.0重构")
        assert new_proj["rhythm_updated"] is True
        assert len(rhythm.affairs) == 1
        assert rhythm.affairs[0]["kind"] == "venture"

        # 重复提交同名项目（含轻微空格变化）：幂等复用，不新建第二条事务
        dup_proj = await qa.handle_message("新建项目：个人博客 2.0 重构")
        assert len(rhythm.affairs) == 1
        assert dup_proj["actions"][0]["deduplicated"] is True
        assert dup_proj["rhythm_updated"] is False

        # 2. 有 Fast LLM 场景：直接调用 rhythm_sync_timeline 重排剩余日程
        qa_llm = QuickCoachAgent(
            config=cfg,
            db=db,
            memory=mem,
            inbox=inbox,
            llm=_ScriptedLLM(
                """{
                  "reply": "已帮你把今天下午调轻，会后只留 45 分钟核心验收。",
                  "actions": [
                    {
                      "kind": "rhythm_sync_timeline",
                      "date": "2026-11-24",
                      "rationale": "避开临时加会，减负留白",
                      "blocks": [
                        {"title": "轻量化验收", "start": "16:15", "end": "17:00", "block_type": "focus"}
                      ]
                    }
                  ]
                }"""
            ),
            rhythm=rhythm,
            clock=lambda: datetime(2026, 11, 24, 13, 30),
        )
        replan = await qa_llm.handle_message("下午好累帮我重排一下")
        assert replan["source"] == "fast_llm"
        assert replan["rhythm_updated"] is True
        assert len(rhythm.synced_timelines) == 1
    finally:
        await db.close()
