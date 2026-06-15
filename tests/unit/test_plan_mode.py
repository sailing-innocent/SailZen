"""Tests for plan mode components."""

import pytest

from sail_bot.context import ConversationContext, PlanModeState
from sail_bot.planner.plan_parser import PlanParser
from sail_bot.planner.plan_doc_store import PlanDocStore
from sail.feishu_card_kit.renderer import CardRenderer


class TestPlanModeState:
    """Test PlanModeState serialization."""

    def test_to_dict_round_trip(self):
        state = PlanModeState(
            status="review",
            requirement="重构健康管理模块",
            doc_token="doxcnXXX",
            doc_url="https://example.com/docx/doxcnXXX",
            plan_title="健康管理重构",
            plan_revision=2,
        )
        data = state.to_dict()
        restored = PlanModeState.from_dict(data)
        assert restored.status == "review"
        assert restored.requirement == "重构健康管理模块"
        assert restored.doc_token == "doxcnXXX"
        assert restored.doc_url == "https://example.com/docx/doxcnXXX"
        assert restored.plan_title == "健康管理重构"
        assert restored.plan_revision == 2


class TestConversationContextSerialization:
    """Test conversation context serialization with plan state."""

    def test_context_with_plan_state(self):
        ctx = ConversationContext(chat_id="oc_test")
        ctx.mode = "planning"
        ctx.plan_state = PlanModeState(
            status="review",
            requirement="测试需求",
            doc_token="doxcnYYY",
            plan_title="测试计划",
        )
        data = ctx.to_dict()
        restored = ConversationContext.from_dict(data)
        assert restored.mode == "planning"
        assert restored.plan_state is not None
        assert restored.plan_state.requirement == "测试需求"
        assert restored.plan_state.doc_token == "doxcnYYY"


class TestPlanParser:
    """Test plan parser."""

    def test_parse_markdown_plan(self):
        content = """# 健康管理重构

## 目标
完成健康管理模块重构。

## 背景
当前模块耦合严重。

## 执行步骤
1. 迁移数据库表
2. 编写 API
3. 添加测试

## 风险与回退方案
- 数据丢失风险：先备份

## 预计耗时
3 天
"""
        plan = PlanParser.parse(content)
        assert plan.title == "健康管理重构"
        assert "迁移数据库表" in plan.goal or any("迁移" in s.title for s in plan.steps)
        assert len(plan.steps) == 3
        assert plan.steps[0].step_id == "step-1"
        assert "迁移数据库表" in plan.steps[0].title
        assert len(plan.risks) >= 1

    def test_preview_steps(self):
        content = "# Plan\n1. Step A\n2. Step B\n3. Step C\n"
        previews = PlanParser.preview_steps(content, max_steps=2)
        assert len(previews) == 2
        assert "Step A" in previews[0]

    def test_parse_xml_title(self):
        content = "<title>XML Title</title><h1>需求</h1><p>内容</p>"
        plan = PlanParser.parse(content)
        assert plan.title == "XML Title"


class TestPlanDocStoreLocalFallback:
    """Test PlanDocStore local fallback behavior."""

    def test_create_local_fallback(self, tmp_path):
        store = PlanDocStore(fallback_to_local=True)
        # Force local fallback by using invalid token behavior path
        token, url = store._create_local_fallback(
            title="Test Plan", initial_content="hello", chat_id="oc_123"
        )
        assert token.endswith(".md")
        assert url.endswith(".md")
        path = tmp_path / "test_plan.md"
        from pathlib import Path
        real_path = Path(token)
        assert real_path.exists()

    def test_update_local_fallback(self, tmp_path):
        store = PlanDocStore(fallback_to_local=True)
        path = tmp_path / "plan.md"
        path.write_text("# Plan\nold", encoding="utf-8")
        ok = store._update_local_fallback(path, "str_replace", "new", "old")
        assert ok
        assert "new" in path.read_text(encoding="utf-8")


class TestPlanCards:
    """Test plan mode card rendering."""

    def test_plan_review_card(self):
        card = CardRenderer.plan_review(
            title="Test Plan",
            requirement="Do something",
            doc_url="https://example.com/docx/abc",
            preview_steps=["1. Step 1", "2. Step 2"],
        )
        assert "计划审阅" in card["header"]["title"]["content"]
        elements = str(card["elements"])
        assert "Test Plan" in elements
        assert "Step 1" in elements
        assert "docx/abc" in elements

    def test_plan_revising_card(self):
        card = CardRenderer.plan_revising("https://example.com/docx/abc")
        assert "修订中" in card["header"]["title"]["content"]

    def test_plan_executing_card(self):
        card = CardRenderer.plan_executing(
            plan_title="Test Plan",
            current_step="Running step",
            completed_steps=["Step 1"],
            total_steps=3,
            elapsed=10,
        )
        assert "计划执行中" in card["header"]["title"]["content"]
        elements = str(card["elements"])
        assert "33%" in elements

    def test_plan_cancelled_card(self):
        card = CardRenderer.plan_cancelled()
        assert "计划已取消" in card["header"]["title"]["content"]


class TestBotBrainPlanMode:
    """Test BotBrain deterministic plan mode recognition."""

    def test_enter_plan_mode_keyword(self):
        from sail_bot.brain import BotBrain
        brain = BotBrain(projects=[])
        ctx = ConversationContext(chat_id="oc_test")
        plan = brain._think_deterministic("帮我规划一下健康管理重构", ctx)
        assert plan.action == "enter_plan_mode"

    def test_plan_mode_approve(self):
        from sail_bot.brain import BotBrain
        brain = BotBrain(projects=[])
        ctx = ConversationContext(chat_id="oc_test")
        ctx.mode = "planning"
        ctx.plan_state = PlanModeState(status="review")
        plan = brain._think_deterministic("批准", ctx)
        assert plan.action == "approve_plan"

    def test_plan_mode_cancel(self):
        from sail_bot.brain import BotBrain
        brain = BotBrain(projects=[])
        ctx = ConversationContext(chat_id="oc_test")
        ctx.mode = "planning"
        ctx.plan_state = PlanModeState(status="review")
        plan = brain._think_deterministic("取消", ctx)
        assert plan.action == "cancel_plan"

    def test_plan_mode_feedback(self):
        from sail_bot.brain import BotBrain
        brain = BotBrain(projects=[])
        ctx = ConversationContext(chat_id="oc_test")
        ctx.mode = "planning"
        ctx.plan_state = PlanModeState(status="review")
        plan = brain._think_deterministic("第一步改成先迁移数据库", ctx)
        assert plan.action == "revise_plan"
        assert "先迁移数据库" in plan.params.get("feedback", "")
