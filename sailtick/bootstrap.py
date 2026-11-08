# -*- coding: utf-8 -*-
# @file bootstrap.py
# @brief SailTick 初始化：goal=70kg、计划 v0.1、首批问卷票据（1-2 张）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""bootstrap — 首次启动引导。

保持最小假设（设计文档 §1.2 决议 5）：只预置 goal=70kg 与计划 v0.1，
其余 profile 全部走问卷。首批只开 1-2 张 minimum 必要票据。

用法:
    uv run python -m sailtick bootstrap
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml

from sailtick.config import SailTickConfig
from sailtick.db import TickDatabase
from sailtick.handoff import HandoffDoc, HandoffManager
from sailtick.inbox import TicketInbox
from sailtick.memory import AgentMemory

logger = logging.getLogger(__name__)

GOAL = "70kg"

PLAN_V01 = """# 减肥计划 v0.1（bootstrap 初版）

## 目标
长期：70kg。时间线不预设，依据体重数据滚动细化。

## 首周只做三件事
1. 每天早晨空腹称重（漏记不追）
2. 晚饭照常但留意吃了什么（可随手记，不强制）
3. 票据回复（AI 的问题尽量答，答不了就跳过）

## 暂不做
- 不计算热量、不限制任何食物
- 不安排运动计划（先确认你的运动条件）
- 不改变早餐午餐

## 理由
bootstrap 保持最小假设。任何干预都建立在"知道你的现状"之上，
而现状只能通过数据与你的回答获得。
"""

FIRST_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "current_weight",
        "title": "现在的体重是多少？",
        "body": (
            "我是 SailTick，你的私人减肥监督教练。\n\n"
            "首先建立基线：你现在的体重是多少？直接回复数字（kg）即可。\n\n"
            "为什么问这个：所有趋势分析和里程碑都以它为起点。"
        ),
        "fallback_assumption": "体重暂无基线，趋势分析推迟",
    },
    {
        "id": "wake_time",
        "title": "工作日几点起床、几点睡觉？",
        "body": (
            "第二个问题：工作日通常几点起床、几点睡觉？\n\n"
            "为什么问这个：我要安排提醒与称重时段，避开你休息的时间。"
        ),
        "fallback_assumption": "默认 07:30 起床 23:30 睡觉",
    },
]


async def bootstrap(config: SailTickConfig) -> Dict[str, Any]:
    """执行 bootstrap，返回初始化摘要。"""
    db = TickDatabase(config.db_path)
    await db.connect()
    memory = AgentMemory(db)
    handoffs = HandoffManager(db, config.handoffs_dir)

    # 1. goal（profile）
    await memory.set_profile("goal_weight", GOAL, confidence=1.0, source="asked")
    print(f"[bootstrap] profile goal_weight = {GOAL}")

    # 2. 计划 v0.1
    existing = await db.get_active_plan()
    if existing:
        print(f"[bootstrap] active plan already exists: {existing['version']} (skip)")
    else:
        await db.create_plan(
            version="v0.1", goal=GOAL, content=PLAN_V01, rationale="bootstrap 最小假设初版", active=True
        )
        print("[bootstrap] plan v0.1 created")

    # 3. 首批问卷票据（仅当 sail_server 可达且尚无 pending question 票据）
    inbox = TicketInbox(config.sail_server.api_base, config.sail_server.auth_token)
    created: List[int] = []
    try:
        if not await inbox.health():
            print("[bootstrap] sail_server unreachable — 跳过票据创建（启动 daemon 后补发）")
        else:
            pending = await inbox.pending_tickets()
            already = {t.get("title") for t in pending}
            for q in FIRST_QUESTIONS:
                if q["title"] in already:
                    continue
                ticket = await inbox.create_ticket(
                    tick_id="bootstrap",
                    ticket_type="question",
                    title=q["title"],
                    body=q["body"],
                    priority="normal",
                    expected_reply_hours=72,
                    fallback_assumption=q["fallback_assumption"],
                )
                created.append(ticket.get("id"))
                print(f"[bootstrap] ticket #{ticket.get('id')} created: {q['title']}")
    finally:
        await inbox.close()

    # 4. handoff 起点文档
    doc = HandoffDoc(
        tick_id="bootstrap",
        slot="bootstrap",
        tick_date=__import__("datetime").datetime.now().strftime("%Y-%m-%d"),
        prev_summary="bootstrap 完成：goal=70kg，计划 v0.1，首批问卷已发出",
        unfinished=[],
        plan_version="v0.1",
        plan_change="bootstrap 初版",
        pending_tickets=[],
        user_status="（尚无数据）",
        next_tick_suggestions=["读取问卷回复，补全 profile", "确认体重秤可及性"],
    )
    path = await handoffs.write(doc)
    await memory.save_episode("bootstrap", "bootstrap", {"handoff": path, "tickets": created})

    await db.close()
    summary = {"goal": GOAL, "plan": "v0.1", "tickets": created, "handoff": path}
    print(f"[bootstrap] done: {summary}")
    return summary


def load_question_bank(prompts_dir: str) -> List[Dict[str, Any]]:
    """读取问卷题库（供 PLAN 阶段切片使用）。"""
    path = Path(prompts_dir) / "coach" / "v1" / "question_bank.yaml"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []
