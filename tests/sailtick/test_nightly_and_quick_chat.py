# -*- coding: utf-8 -*-
# @file test_nightly_and_quick_chat.py
# @brief 夜间深度自维护（长周期分析/数学建模/自主知识沉淀）与白天快反对话/QQ Bot/提醒闭环测试
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import pytest
from litestar.testing import AsyncTestClient

from sailtick.analytics import WeightModelingEngine
from sailtick.config import (
    LLMConfig,
    LLMProviderConfig,
    NightlyMaintenanceConfig,
    QQBotConfig,
    QuickChatConfig,
    SailServerConfig,
    SailTickConfig,
)
from sailtick.daemon import SailTickDaemon
from sailtick.knowledge import HealthKnowledgeManager, WebSearcher
from sailtick.llm import LLMResponse
from sailtick.quick_agent import QuickCoachAgent, extract_reminder_subject, parse_reminder_time
from sailtick.testing.clock import VirtualClock
from sailtick.testing.fake_server import SimulatedSailServer


class FakeWebSearcher(WebSearcher):
    """离线可控假搜索引擎。"""

    def __init__(self, canned: Optional[Dict[str, List[Dict[str, str]]]] = None):
        super().__init__(timeout=2.0, enabled=True)
        self.canned = canned or {}
        self.queries: List[str] = []

    async def search(self, query: str, max_results: int = 3) -> List[Dict[str, str]]:
        self.queries.append(query)
        for key, items in self.canned.items():
            if key in query:
                return items[:max_results]
        return [
            {
                "title": f"{query} 营养参考",
                "snippet": "常见每份约 360 千卡，蛋白质 14g，碳水 48g，脂肪 12g。",
                "url": "https://example.local/nutrition",
                "engine": "fake_search",
            }
        ]


class FakeFastLLM:
    """支持 chat 与 chat_fast 的可编程假 LLM。"""

    def __init__(self, responses: Optional[List[str]] = None):
        self.responses = list(responses or [])
        self.calls: List[Dict[str, Any]] = []
        self.tick_tokens = 0
        self.tick_usd = 0.0
        self.budget_exceeded = False
        self.config = LLMConfig(
            default="deepseek",
            fast_provider="deepseek",
            fast_model="deepseek-chat",
            providers={
                "deepseek": LLMProviderConfig(
                    api_key="fake-key", model="deepseek-reasoner"
                )
            },
        )

    def begin_tick(self) -> None:
        self.tick_tokens = 0
        self.tick_usd = 0.0

    async def chat(self, prompt: str, **kwargs) -> LLMResponse:
        self.calls.append({"mode": "chat", "prompt": prompt, "kwargs": kwargs})
        content = self.responses.pop(0) if self.responses else "{}"
        self.tick_tokens += 120
        return LLMResponse(content=content, usage={"total_tokens": 120}, model="deepseek-reasoner", provider="deepseek")

    async def chat_fast(self, prompt: str, **kwargs) -> LLMResponse:
        self.calls.append({"mode": "chat_fast", "prompt": prompt, "kwargs": kwargs})
        content = self.responses.pop(0) if self.responses else "{}"
        return LLMResponse(content=content, usage={"total_tokens": 90}, model="deepseek-chat", provider="deepseek")

    async def close(self) -> None:
        pass


def _build_daemon(
    tmp_path,
    clock: VirtualClock,
    server: SimulatedSailServer,
    llm: Any = None,
    qq_cfg: Optional[QQBotConfig] = None,
) -> SailTickDaemon:
    cfg = SailTickConfig(
        data_dir=str(tmp_path / "data"),
        db_path=str(tmp_path / "db" / "sailtick.db"),
        log_dir=str(tmp_path / "logs"),
        api_port=19071,
        sail_server=SailServerConfig(api_base="http://simulated-sail-server/api/v1"),
        nightly=NightlyMaintenanceConfig(
            enabled=True,
            deep_window_days=90,
            enable_web_search=False,
            max_foods_per_night=3,
            max_knowledge_per_night=1,
        ),
        quick_chat=QuickChatConfig(
            enabled=True,
            default_offwork_time="18:00",
            offwork_lead_minutes=20,
        ),
        qq_bot=qq_cfg or QQBotConfig(enabled=False),
        config_dir=os.getcwd(),
    )
    d = SailTickDaemon(cfg)
    d.inbox = server.create_inbox()
    d.scanner = server.create_scanner()
    if llm is not None:
        d.llm = llm
        d.engine.llm = llm
        d.knowledge.llm = llm
        d.nightly.llm = llm
        d.quick_agent.llm = llm
    d.engine.inbox = d.inbox
    d.engine.scanner = d.scanner
    d.engine._clock = clock
    d.notifier.inbox = d.inbox
    d.notifier._clock = clock
    d.nightly.scanner = d.scanner
    d.nightly._clock = clock
    d.nightly.modeling._clock = clock
    d.quick_agent.inbox = d.inbox
    d.quick_agent._clock = clock
    d.qq_bot._clock = clock
    return d


# ═══════════════════════════════════════════════════════════════════════
#  1. 数学建模与长周期深度数据分析
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_deep_collect_paginated_finance_and_modeling(tmp_path):
    """长周期 collect_deep 分页拉取 120+ 交易并完成 EWMA + 回归/动力学建模与 70kg ETA 预测。"""
    clock = VirtualClock(datetime(2026, 11, 23, 0, 5))
    server = SimulatedSailServer(clock=clock)

    # 构造 42 天带日常水重噪声的下降体重曲线（78.0 -> ~74.5kg）
    base_day = datetime(2026, 10, 12, 7, 30)
    noise = [0.2, -0.15, 0.3, -0.1, 0.05, 0.45, 0.35]  # 周六/周日偏高模拟周末小波动
    for i in range(42):
        dt = base_day + timedelta(days=i)
        w = 78.0 - 0.085 * i + noise[dt.weekday()]
        server.seed_weight(dt.strftime("%Y-%m-%d %H:%M"), round(w, 2))
        if i % 2 == 0:
            server.seed_signal("sleep", {"date": dt.strftime("%Y-%m-%d"), "hours": 6.4 if i % 4 == 0 else 7.5})
        if i % 4 == 0:
            server.seed_signal("exercise", {"date": dt.strftime("%Y-%m-%d"), "duration_minutes": 35})

    # 注入 125 条财务交易（跨 2 页），含零食、奶茶、外卖、聚餐与夜宵
    for idx in range(125):
        dt = base_day + timedelta(days=idx % 42, hours=(22 if idx % 15 == 0 else 13))
        if idx % 10 == 0:
            desc, tags, val = "周末同学火锅聚餐", "餐饮,聚餐", 168.0
        elif idx % 5 == 0:
            desc, tags, val = "瑞幸生椰拿铁+薯片", "零食,饮品", 29.0
        elif idx % 3 == 0:
            desc, tags, val = "美团外卖烤冷面", "外卖", 26.0
        else:
            desc, tags, val = "地铁通勤充值", "交通", 10.0
        server.seed_signal(
            "finance",
            {"htime": dt.timestamp(), "value": val, "tags": tags, "description": desc},
        )

    scanner = server.create_scanner()
    deep = await scanner.collect_deep(days=90)
    assert deep["health_ok"] is True
    assert deep["transactions_total"] == 125
    assert len(deep["finance_food"]) > 40
    assert any("social_dining" in tx["subtypes"] for tx in deep["finance_food"])
    assert any("snack_drink" in tx["subtypes"] for tx in deep["finance_food"])

    engine = WeightModelingEngine(clock=clock)
    res = engine.analyze(deep, target_weight_kg=70.0)
    assert res["sample_count"] == 42
    assert res["model_type"] in ("ewma_wls", "ewma_exp_adaptation")
    assert res["weekly_rate_kg"] is not None and res["weekly_rate_kg"] < -0.3
    assert res["eta_date"] is not None
    assert res["eta_optimistic_date"] <= res["eta_date"] <= res["eta_conservative_date"]
    assert res["confidence_score"] >= 60.0
    assert len(res["forecast_points"]) == 3
    assert len(res["daily_targets_14d"]) == 5
    assert "EWMA" in res["confidence_message"]
    assert res["metrics"]["finance_food"]["social_dining_count"] >= 10
    await scanner.close()


def test_modeling_detects_plateau_and_suggests_question():
    """连续 18 天体重横盘时正确识别平台期并给出针对性心理/运动发问建议。"""
    clock = VirtualClock(datetime(2026, 11, 23, 0, 0))
    base = datetime(2026, 11, 4, 7, 30)
    weights = [
        {"date": (base + timedelta(days=i)).strftime("%Y-%m-%d"), "value": 74.0 + (0.12 if i % 2 == 0 else -0.10)}
        for i in range(19)
    ]
    deep = {"window_days": 90, "weight": weights, "finance_food": [], "sleep": [], "exercise": []}
    res = WeightModelingEngine(clock=clock).analyze(deep, target_weight_kg=70.0)
    assert res["plateau_detected"] is True
    assert any("平台期" in ins for ins in res["insights"])
    assert any(q["topic"] == "plateau_recovery_check" for q in res["suggested_questions"])


# ═══════════════════════════════════════════════════════════════════════
#  2. 自主食物热量库 & 健康师专业知识库
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_autonomous_food_research_and_knowledge_curation(tmp_path):
    """夜间自主发现未知食物（烤冷面），联网+LLM 查证入库并清空快脑待查队列，同时沉淀专业知识卡片。"""
    clock = VirtualClock(datetime(2026, 11, 23, 0, 10))
    server = SimulatedSailServer(clock=clock)
    llm = FakeFastLLM(
        responses=[
            # 1) 食物热量结构化校验响应
            json.dumps(
                {
                    "name": "烤冷面",
                    "aliases": ["东北烤冷面"],
                    "category": "snack",
                    "serving_desc": "1份加蛋(约280g)",
                    "kcal_per_100g": 195,
                    "kcal_per_serving": 545,
                    "protein_g": 16,
                    "carbs_g": 68,
                    "fat_g": 22,
                    "gi_level": "high",
                    "satiety_score": 3,
                    "lighter_swap": "少刷甜面酱和油、不加烤肠、加一个鸡蛋更稳",
                    "notes": "碳水与油脂偏高，适合偶尔解馋并与人分食",
                },
                ensure_ascii=False,
            ),
            # 2) 健康师专业知识卡片整理响应
            json.dumps(
                {
                    "title": "公司食堂与工作日外卖的低油高蛋白点餐指南",
                    "summary": "外食控热量的核心是控油汁与稳蛋白，而非挨饿。",
                    "key_points": [
                        "打菜优先清蒸/白灼/卤制瘦肉",
                        "汤汁不拌饭可立减 150+ kcal",
                        "餐前先吃蔬菜压低餐后血糖波动",
                    ],
                    "applicable_scenarios": ["食堂", "外卖", "午饭"],
                },
                ensure_ascii=False,
            ),
        ]
    )
    d = _build_daemon(tmp_path, clock, server, llm=llm)
    await d.db.connect()
    try:
        searcher = FakeWebSearcher()
        km = HealthKnowledgeManager(d.db, llm=llm, searcher=searcher)
        seeded = await km.ensure_seeded()
        assert seeded["foods_seeded"] >= 15
        assert seeded["knowledge_seeded"] >= 4

        # 内置库秒查
        hits = await km.lookup_foods_in_text("中午吃了牛肉面还喝了生椰拿铁")
        hit_names = {h["name"] for h in hits}
        assert "牛肉面" in hit_names and "生椰拿铁" in hit_names

        # 白天快脑把未知食物入队 → 夜间慢脑自动查证入库
        await km.enqueue_food_research(["烤冷面"])
        food_res = await km.run_nightly_food_research({}, max_foods=3)
        assert "烤冷面" in food_res["researched_names"]

        # 查证后即可秒查，且队列已清空
        new_hits = await km.lookup_foods_in_text("烤冷面多少热量")
        assert len(new_hits) == 1
        assert new_hits[0]["kcal_per_serving"] == 545.0
        assert (await d.db.get_runtime_state("pending_food_research")) == []

        # 专业知识卡片整理
        kn_res = await km.run_nightly_knowledge_curation(
            focus_domains=["diet", "psychology"],
            insights=["外卖频次较高"],
            max_items=1,
        )
        assert kn_res["curated_count"] == 1
        assert len(searcher.queries) >= 2
    finally:
        await d.db.close()


# ═══════════════════════════════════════════════════════════════════════
#  3. 夜间自维护接入 TickEngine → 白天 Tick 继承专家简报
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_nightly_tick_generates_expert_brief_for_daytime_tick(tmp_path):
    """nightly_maintenance 自动完成建模与专家简报编译，次日 morning_checkin Prompt 自动携带专家简报。"""
    clock = VirtualClock(datetime(2026, 11, 23, 0, 0))
    server = SimulatedSailServer(clock=clock)
    base = datetime(2026, 11, 1, 7, 30)
    for i in range(22):
        server.seed_weight((base + timedelta(days=i)).strftime("%Y-%m-%d"), round(76.5 - 0.07 * i, 2))

    nightly_plan = json.dumps(
        {
            "summary": "夜间完成 90 天数学建模与简报刷新",
            "tickets": [],
            "actions": [{"kind": "episode", "content": "nightly modeling ok"}],
            "unfinished": [],
            "next_tick_suggestions": ["明早肯定用户稳步下降趋势"],
        },
        ensure_ascii=False,
    )
    morning_plan = json.dumps(
        {
            "summary": "早间巡检：结合夜间模型稳步推进",
            "tickets": [],
            "actions": [],
            "unfinished": [],
            "next_tick_suggestions": [],
        },
        ensure_ascii=False,
    )
    llm = FakeFastLLM(responses=[nightly_plan, morning_plan])
    d = _build_daemon(tmp_path, clock, server, llm=llm)
    await d.db.connect()
    try:
        r1 = await d.engine.run_tick("nightly_maintenance")
        assert r1["status"] == "completed"

        brief = await d.db.get_runtime_state("expert_brief")
        assert brief is not None
        assert brief["modeling"]["sample_count"] == 22
        assert brief["modeling"]["eta_date"] is not None

        snaps = await d.db.list_model_snapshots(limit=5)
        assert len(snaps) == 1

        # 次日 06:00 唤醒，检查 PLAN prompt 自动注入了夜间专家简报
        clock.advance(hours=6)
        r2 = await d.engine.run_tick("morning_checkin")
        assert r2["status"] == "completed"
        assert "夜间数学建模与深度洞察" in llm.calls[1]["prompt"]
        assert "EWMA" in llm.calls[1]["prompt"]
    finally:
        await d.db.close()


# ═══════════════════════════════════════════════════════════════════════
#  4. 白天快反对话 + 自然语言提醒解析 + 突发早下班/聚餐灵活调度
# ═══════════════════════════════════════════════════════════════════════


def test_parse_chinese_reminder_times():
    now = datetime(2026, 11, 23, 14, 15)
    dt1, _ = parse_reminder_time("下班前提醒我别忘了要买洗衣液和七号电池", now, "18:00", 20)
    assert dt1 == datetime(2026, 11, 23, 17, 40)
    assert extract_reminder_subject("下班前提醒我别忘了要买洗衣液和七号电池") == "买洗衣液和七号电池"

    dt2, _ = parse_reminder_time("30分钟后提醒我起身喝水", now)
    assert dt2 == datetime(2026, 11, 23, 14, 45)

    dt3, _ = parse_reminder_time("明早8点半提醒我空腹称体重", now)
    assert dt3 == datetime(2026, 11, 24, 8, 30)


@pytest.mark.asyncio
async def test_quick_chat_reminder_and_flexible_daytime_scenarios(tmp_path):
    """覆盖：下班前买洗衣液提醒、突发早下班安排、突发同学聚餐调计划、食物速查、快捷指令。"""
    clock = VirtualClock(datetime(2026, 11, 23, 14, 20))
    server = SimulatedSailServer(clock=clock)
    base = datetime(2026, 11, 1, 7, 30)
    for i in range(20):
        server.seed_weight((base + timedelta(days=i)).strftime("%Y-%m-%d"), round(76.0 - 0.08 * i, 2))

    # 无 LLM（规则兜底模式）也能丝滑跑通所有核心场景
    d = _build_daemon(tmp_path, clock, server, llm=None)
    d.llm.config.providers.clear()
    await d.db.connect()
    try:
        # 先跑一次夜间确定性建模产出专家简报
        await d.nightly.run(allow_llm_research=False)

        # 1) 下班前提醒买洗衣液和七号电池
        res_rem = await d.quick_agent.handle_message(
            "下班前提醒我别忘了要买洗衣液和七号电池", channel="qq", user_id="10001"
        )
        assert "17:40" in res_rem["reply"]
        assert "洗衣液" in res_rem["reply"]
        assert len(res_rem["reminders_created"]) == 1
        # 验证同步落库到了 sail_server Reminder（Android 到点弹窗）与本地 Nudge（QQ 双推）
        assert len(server.reminders) == 1
        assert "买洗衣液和七号电池" in server.reminders[0]["title"]
        nudges = await d.db.list_pending_nudges()
        assert len(nudges) == 1

        # 2) 突然同学聚餐 → 给出控损策略并同步给慢脑
        res_party = await d.quick_agent.handle_message(
            "突然同学聚餐，今晚能不能调整计划？", channel="qq", user_id="10001"
        )
        assert "聚餐" in res_party["reply"]
        assert any(a["kind"] == "plan_adjust_signal" for a in res_party["actions"])
        assert any("social_dining" in m["content"] for m in server.messages)

        # 3) 今天能早点下班 → 给出运动+晚餐建议
        res_early = await d.quick_agent.handle_message(
            "今天能早点下班，下班后有没有推荐的安排？", channel="qq", user_id="10001"
        )
        assert "下班" in res_early["reply"] or "运动" in res_early["reply"]

        # 4) 快捷指令 /brief /predict /food /remind
        r_brief = await d.quick_agent.handle_message("/brief", channel="qq", user_id="10001")
        assert "SailTick 专家简报" in r_brief["reply"]
        r_pred = await d.quick_agent.handle_message("/predict", channel="qq", user_id="10001")
        assert "数学模型预测" in r_pred["reply"]
        r_food = await d.quick_agent.handle_message("/food 牛肉面", channel="qq", user_id="10001")
        assert "620" in r_food["reply"]
        r_unknown = await d.quick_agent.handle_message("/food 螺蛳粉", channel="qq", user_id="10001")
        assert "螺蛳粉" in r_unknown["reply"]
        assert "螺蛳粉" in (await d.db.get_runtime_state("pending_food_research"))
        r_rem_list = await d.quick_agent.handle_message("/remind", channel="qq", user_id="10001")
        assert "买洗衣液和七号电池" in r_rem_list["reply"]
    finally:
        await d.db.close()


@pytest.mark.asyncio
async def test_quick_chat_with_fast_llm_routes_to_fast_model(tmp_path):
    """配置 LLM 时快反代理走 chat_fast 低延迟接口并正确执行返回的提醒/调计划动作。"""
    clock = VirtualClock(datetime(2026, 11, 23, 15, 0))
    server = SimulatedSailServer(clock=clock)
    llm = FakeFastLLM(
        responses=[
            json.dumps(
                {
                    "reply": "太好了！今天 16:30 早下班的话，建议先去快走 35 分钟顺路买好洗衣液和七号电池，我也在 16:20 设了个提醒。",
                    "actions": [
                        {
                            "kind": "create_reminder",
                            "title": "买洗衣液和七号电池",
                            "body": "下班顺路买洗衣液和七号电池",
                            "trigger_time": "2026-11-23T16:20:00",
                        },
                        {
                            "kind": "plan_adjust_signal",
                            "scene": "early_offwork",
                            "summary": "今天 16:30 早下班，安排快走 35 分钟",
                        },
                    ],
                },
                ensure_ascii=False,
            )
        ]
    )
    d = _build_daemon(tmp_path, clock, server, llm=llm)
    await d.db.connect()
    try:
        res = await d.quick_agent.handle_message(
            "今天16:30能早下班，帮我安排一下，顺便下班前提醒买洗衣液和七号电池",
            channel="qq",
            user_id="10001",
        )
        assert res["source"] == "fast_llm"
        assert len(llm.calls) == 1 and llm.calls[0]["mode"] == "chat_fast"
        assert len(res["reminders_created"]) == 1
        assert len(server.reminders) == 1
        assert len(server.messages) == 1
    finally:
        await d.db.close()


# ═══════════════════════════════════════════════════════════════════════
#  5. QQ Bot (OneBot v11) Webhook + 验签 + 白名单 + 到点双推 + Daemon 路由
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_onebot_qq_webhook_security_and_due_nudge_push(tmp_path):
    """验证 OneBot v11 签名校验、QQ 白名单、Webhook 快速回复与到期提醒主动推送。"""
    clock = VirtualClock(datetime(2026, 11, 23, 15, 0))
    server = SimulatedSailServer(clock=clock)
    sent_qq_payloads: List[Dict[str, Any]] = []

    def onebot_handler(request: httpx.Request) -> httpx.Response:
        sent_qq_payloads.append(
            {"path": request.url.path, "body": json.loads(request.content.decode("utf-8"))}
        )
        return httpx.Response(200, json={"status": "ok", "retcode": 0})

    qq_cfg = QQBotConfig(
        enabled=True,
        onebot_api_base="http://mock-onebot:3000",
        webhook_secret="my-secret-key",
        allowed_users=["888888"],
        primary_user_id="888888",
    )
    d = _build_daemon(tmp_path, clock, server, llm=None, qq_cfg=qq_cfg)
    d.llm.config.providers.clear()
    d.qq_bot._client = httpx.AsyncClient(
        transport=httpx.MockTransport(onebot_handler),
        base_url="http://mock-onebot:3000",
    )
    await d.db.connect()
    try:
        from sailtick.api.routes import create_app

        app = create_app(d)
        async with AsyncTestClient(app=app) as client:
            # 1) 非法签名被拒 401
            bad_resp = await client.post(
                "/onebot/webhook",
                content=b'{"post_type":"message"}',
                headers={"X-Signature": "sha1=deadbeef"},
            )
            assert bad_resp.status_code == 401

            # 2) 陌生人 QQ 被白名单忽略
            stranger_body = json.dumps(
                {
                    "post_type": "message",
                    "message_type": "private",
                    "user_id": 999999,
                    "raw_message": "你好",
                }
            ).encode("utf-8")
            sig_stranger = "sha1=" + hmac.new(b"my-secret-key", stranger_body, hashlib.sha1).hexdigest()
            r_stranger = await client.post(
                "/onebot/webhook",
                content=stranger_body,
                headers={"X-Signature": sig_stranger},
            )
            assert r_stranger.status_code == 201
            assert r_stranger.json()["status"] == "ignored"

            # 3) 主人 QQ 发提醒消息 → 建提醒并通过 OneBot send_private_msg 主动回复
            owner_body = json.dumps(
                {
                    "post_type": "message",
                    "message_type": "private",
                    "user_id": 888888,
                    "raw_message": "下班前提醒我别忘了买洗衣液和七号电池",
                },
                ensure_ascii=False,
            ).encode("utf-8")
            sig_owner = "sha1=" + hmac.new(b"my-secret-key", owner_body, hashlib.sha1).hexdigest()
            r_owner = await client.post(
                "/onebot/webhook",
                content=owner_body,
                headers={"X-Signature": sig_owner},
            )
            assert r_owner.status_code == 201
            assert r_owner.json()["status"] == "ok"
            assert r_owner.json()["pushed"] is True
            assert len(sent_qq_payloads) == 1
            assert sent_qq_payloads[0]["path"] == "/send_private_msg"
            assert sent_qq_payloads[0]["body"]["user_id"] == 888888

            # 4) 推进虚拟时钟到 17:41 → 触发到期 QQ 提醒推送
            clock.advance(hours=2, minutes=41)
            dispatched = await d.qq_bot.dispatch_due_nudges()
            assert dispatched == 1
            assert len(sent_qq_payloads) == 2
            assert "洗衣液" in sent_qq_payloads[1]["body"]["message"]
            assert await d.db.list_pending_nudges() == []

            # 5) 管理 API 查食物库 & 专家简报 & 快速对话
            r_foods = await client.get("/knowledge/foods?q=牛肉面")
            assert r_foods.status_code == 200
            assert len(r_foods.json()) >= 1

            r_qchat = await client.post(
                "/chat/quick", json={"text": "/help", "channel": "api"}
            )
            assert r_qchat.status_code == 201
            assert "SailTick 快反助手" in r_qchat.json()["reply"]
    finally:
        await d.qq_bot.close()
        await d.db.close()


# ═══════════════════════════════════════════════════════════════════════
#  6. 快脑多轮防复读、提醒改期/取消闭环、画像持久化与 AI Trace 落盘回归
# ═══════════════════════════════════════════════════════════════════════


def test_parse_explicit_offwork_hour_in_sentence():
    """用户明确说「7点下班，下班回去的路上提醒...」时，必须推算为 18:40 而非次日 07:00。"""
    now = datetime(2026, 11, 25, 11, 51)
    dt, _ = parse_reminder_time(
        "今天预计能够正常7点下班，记得提醒我要在下班回去的路上购买7号电池和洗衣液",
        now=now,
        default_offwork_time="18:00",
        offwork_lead_minutes=20,
    )
    assert dt == datetime(2026, 11, 25, 18, 40)


@pytest.mark.asyncio
async def test_quick_chat_idempotent_dedup_reschedule_cancel_profile_and_trace(tmp_path):
    """复现并根治「买7号电池和洗衣液」3轮产生3条提醒 + 重复事务 + 缺失 Trace 的线上问题。"""
    clock = VirtualClock(datetime(2026, 11, 25, 11, 51))
    server = SimulatedSailServer(clock=clock)

    # 模拟快模型依次输出：
    # Turn 1: 建 17:40 提醒
    # Turn 2: 纠正作息 19:00（update_profile + 同主题改期到 18:40，即使仍输出 create_reminder 也应自动改期替换而非双建！）
    # Turn 3: 纯聊天总结却误重放带空格标题的 create_reminder@18:40 → 执行层强幂等跳过！
    # Turn 4: 显式 cancel_reminder → 云端与本地 Nudge 双向取消！
    llm = FakeFastLLM(
        responses=[
            json.dumps(
                {
                    "reply": "收到，17:40 提醒你买7号电池和洗衣液。",
                    "actions": [
                        {
                            "kind": "create_reminder",
                            "title": "下班路上买7号电池和洗衣液",
                            "body": "下班回家路上顺路购买",
                            "trigger_time": "2026-11-25T17:40:00",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "reply": "记下你 19:00 下班啦，提醒已顺延到 18:40。",
                    "actions": [
                        {"kind": "update_profile", "key": "offwork_time", "value": "19:00"},
                        {
                            "kind": "create_reminder",
                            "title": "下班路上买7号电池和洗衣液",
                            "body": "下班回去的路上顺路购买",
                            "trigger_time": "2026-11-25T18:40:00",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "reply": "明白，前期先慢慢磨合；今天 18:40 的买电池洗衣液提醒照旧。",
                    "actions": [
                        {
                            "kind": "create_reminder",
                            "title": "下班路上买 7 号电池和洗衣液",
                            "body": "重复复读测试",
                            "trigger_time": "2026-11-25T18:40:00",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "reply": "好的，已经帮你取消买7号电池和洗衣液的提醒了。",
                    "actions": [
                        {"kind": "cancel_reminder", "match_title": "买7号电池和洗衣液"},
                    ],
                },
                ensure_ascii=False,
            ),
        ]
    )

    d = _build_daemon(tmp_path, clock, server, llm=llm)
    await d.db.connect()
    try:
        # Turn 1: 首次创建 17:40
        r1 = await d.quick_agent.handle_message("下班提醒我买7号电池和洗衣液", channel="android", user_id="owner")
        assert r1["trace_id"]
        assert len([r for r in server.reminders if r["state"] != "CANCELED"]) == 1
        assert len(await d.db.list_pending_nudges()) == 1

        # Turn 2: 纠正作息 19:00 + 改期到 18:40 → 旧 17:40 被自动取消，只剩 1 条 18:40！
        clock.advance(minutes=2)
        r2 = await d.quick_agent.handle_message("我们正常下班是19:00", channel="android", user_id="owner")
        assert any(a.get("kind") == "update_profile" and a.get("ok") for a in r2["actions"])
        assert any(a.get("rescheduled") is True for a in r2["actions"])
        # 验证 profile 已持久化
        prof = await d.memory.all_profile()
        assert prof["offwork_time"]["value"] == "19:00"
        # 验证云端仅剩 1 条活跃提醒（旧的已 CANCELED），本地也仅 1 条 pending nudge
        active_rems = [r for r in server.reminders if r["state"] != "CANCELED"]
        assert len(active_rems) == 1
        assert active_rems[0]["trigger_time"] == "2026-11-25T18:40:00"
        nudges_t2 = await d.db.list_pending_nudges()
        assert len(nudges_t2) == 1
        assert nudges_t2[0]["trigger_at"] == "2026-11-25T18:40:00"

        # 验证 Turn 2 传给 LLM 的历史中携带了 Turn 1 的系统回执 + 当前待触发提醒列表
        assert "系统回执-该轮已执行" in str(llm.calls[1])
        assert "当前已生效的待触发提醒" in str(llm.calls[1])

        # Turn 3: 即使 LLM 误重放带空格标题的 18:40 提醒，执行层强幂等跳过，不新增任何提醒！
        clock.advance(minutes=10)
        r3 = await d.quick_agent.handle_message("前期多磨合，不必过快规划", channel="android", user_id="owner")
        assert r3["actions"][0]["deduplicated"] is True
        assert r3["reminders_created"] == []
        assert len([r for r in server.reminders if r["state"] != "CANCELED"]) == 1
        assert len(await d.db.list_pending_nudges()) == 1

        # Turn 4: 取消提醒 → 云端与本地双清
        clock.advance(minutes=5)
        r4 = await d.quick_agent.handle_message("电池已经买好了，取消提醒吧", channel="android", user_id="owner")
        assert r4["actions"][0]["kind"] == "cancel_reminder"
        assert r4["actions"][0]["ok"] is True
        assert len([r for r in server.reminders if r["state"] != "CANCELED"]) == 0
        assert len(await d.db.list_pending_nudges()) == 0

        # 验证 4 轮快脑对话全部写入 st_ai_traces（可观测性闭环）
        traces = await d.db.list_traces(limit=10)
        qc_traces = [t for t in traces if t["slot"] == "quick_chat"]
        assert len(qc_traces) == 4
        detail = await d.db.get_trace(r3["trace_id"])
        assert detail is not None
        assert any(sp["name"] == "action:create_reminder" and "deduplicated" in sp["output_summary"] for sp in detail["spans"])
    finally:
        await d.db.close()
