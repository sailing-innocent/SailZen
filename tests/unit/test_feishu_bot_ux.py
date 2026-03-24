# -*- coding: utf-8 -*-
# @file test_feishu_bot_ux.py
# @brief Unit tests for Feishu bot UX upgrade - card rendering, state machine, risk classification, confirmation flow
# @author sailing-innocent
# @date 2026-03-24
# @version 1.0
# ---------------------------------

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bot"))

from card_renderer import (
    CardColor,
    CardMessageTracker,
    CardRenderer,
    card_to_feishu_content,
    text_fallback,
)
from session_state import (
    ConfirmationManager,
    OperationTracker,
    RiskLevel,
    SessionState,
    SessionStateStore,
    classify_risk,
    is_valid_transition,
)


# ---------------------------------------------------------------------------
# 6.1.1 Card Rendering Tests
# ---------------------------------------------------------------------------


class TestCardRenderer:
    def test_workspace_selection_empty(self):
        card = CardRenderer.workspace_selection([])
        assert card["header"]["template"] == CardColor.BLUE.value
        assert any("暂无" in str(el) for el in card["elements"])

    def test_workspace_selection_with_projects(self):
        projects = [{"slug": "test", "label": "Test", "path": "/tmp/test"}]
        card = CardRenderer.workspace_selection(projects)
        elements_str = str(card["elements"])
        assert "test" in elements_str

    def test_workspace_selection_mobile_button_limit(self):
        projects = [{"slug": "a", "label": "A", "path": "/tmp/a"}]
        card = CardRenderer.workspace_selection(projects)
        for el in card["elements"]:
            if el.get("tag") == "action":
                assert len(el["actions"]) <= 2, "Mobile: max 2 buttons per action row"

    def test_session_status_running(self):
        card = CardRenderer.session_status(
            "/path/to/myapp", "running", port=4096, pid=12345
        )
        assert card["header"]["template"] == CardColor.GREEN.value
        elements_str = str(card["elements"])
        assert "myapp" in elements_str

    def test_session_status_error(self):
        card = CardRenderer.session_status(
            "/path/to/myapp", "error", last_error="Connection refused"
        )
        assert card["header"]["template"] == CardColor.RED.value
        assert "Connection refused" in str(card["elements"])

    def test_session_status_action_buttons_mobile_limit(self):
        card = CardRenderer.session_status("/path/to/myapp", "running")
        for el in card["elements"]:
            if el.get("tag") == "action":
                assert len(el["actions"]) <= 2

    def test_progress_indeterminate(self):
        card = CardRenderer.progress("启动中", "初始化...", spinner_tick=3)
        assert "⏳" in card["header"]["title"]["content"]
        elements_str = str(card["elements"])
        assert "处理中" in elements_str

    def test_progress_determinate(self):
        card = CardRenderer.progress("处理中", progress_pct=60)
        elements_str = str(card["elements"])
        assert "60%" in elements_str
        assert "█" in elements_str

    def test_confirmation_card_has_instructions(self):
        card = CardRenderer.confirmation(
            "停止会话 myapp", risk_level="confirm_required", pending_id="abc123"
        )
        # 卡片现在显示文字指令而不是按钮（本地运行不支持卡片按钮回调）
        elements_str = str(card["elements"])
        assert "确认" in elements_str
        assert "取消" in elements_str

    def test_confirmation_undo_note_30s(self):
        card = CardRenderer.confirmation("停止", can_undo=True, pending_id="x")
        elements_str = str(card["elements"])
        assert "30" in elements_str

    def test_result_success_green(self):
        card = CardRenderer.result("完成", "任务完成了", success=True)
        assert card["header"]["template"] == CardColor.GREEN.value

    def test_result_failure_red(self):
        card = CardRenderer.result("失败", "出错了", success=False)
        assert card["header"]["template"] == CardColor.RED.value

    def test_result_content_truncated_at_500(self):
        long_content = "x" * 1000
        card = CardRenderer.result("测试", long_content)
        elements_str = str(card["elements"])
        assert "截断" in elements_str

    def test_error_card(self):
        card = CardRenderer.error(
            "API错误", "Connection timeout", context_path="/tmp/proj"
        )
        assert card["header"]["template"] == CardColor.RED.value

    def test_all_sessions_card(self):
        sessions = [
            {"path": "/tmp/a", "state": "running", "port": 4096},
            {"path": "/tmp/b", "state": "idle", "port": None},
        ]
        card = CardRenderer.all_sessions(sessions)
        elements_str = str(card["elements"])
        assert "🟢" in elements_str
        assert "⬜" in elements_str

    def test_text_fallback_extracts_title_and_content(self):
        card = CardRenderer.result("任务完成", "这是一段内容", success=True)
        fallback = text_fallback(card)
        assert "任务完成" in fallback
        assert "这是一段内容" in fallback

    def test_card_to_feishu_content_is_valid_json(self):
        card = CardRenderer.progress("测试")
        content = card_to_feishu_content(card)
        import json

        parsed = json.loads(content)
        assert "header" in parsed

    def test_card_message_tracker(self):
        tracker = CardMessageTracker()
        tracker.register("msg_001", "progress", {"op_id": "abc", "path": "/tmp/x"})
        info = tracker.get("msg_001")
        assert info["card_type"] == "progress"
        found = tracker.find_by_context("progress", "path", "/tmp/x")
        assert found == "msg_001"
        tracker.remove("msg_001")
        assert tracker.get("msg_001") is None


# ---------------------------------------------------------------------------
# 6.1.2 State Machine Transition Tests
# ---------------------------------------------------------------------------


class TestSessionStateMachine:
    def test_valid_transitions(self):
        assert is_valid_transition(SessionState.IDLE, SessionState.STARTING)
        assert is_valid_transition(SessionState.STARTING, SessionState.RUNNING)
        assert is_valid_transition(SessionState.RUNNING, SessionState.STOPPING)
        assert is_valid_transition(SessionState.STOPPING, SessionState.IDLE)
        assert is_valid_transition(SessionState.ERROR, SessionState.STARTING)

    def test_invalid_transitions(self):
        assert not is_valid_transition(SessionState.IDLE, SessionState.RUNNING)
        assert not is_valid_transition(SessionState.RUNNING, SessionState.IDLE)
        assert not is_valid_transition(SessionState.STOPPING, SessionState.RUNNING)

    def test_state_store_transition_updates_entry(self):
        store = SessionStateStore()
        store.get_or_create("/tmp/testproject", chat_id="chat_001")
        result = store.transition("/tmp/testproject", SessionState.STARTING)
        assert result is True
        entry = store.get("/tmp/testproject")
        assert entry.state == SessionState.STARTING

    def test_state_store_invalid_transition_rejected(self):
        store = SessionStateStore()
        store.get_or_create("/tmp/testproject2")
        result = store.transition("/tmp/testproject2", SessionState.RUNNING)
        assert result is False
        entry = store.get("/tmp/testproject2")
        assert entry.state == SessionState.IDLE

    def test_state_change_hook_called(self):
        store = SessionStateStore()
        store.get_or_create("/tmp/hooktest")
        hook_calls = []
        store.register_hook(
            lambda path, prev, nxt, entry: hook_calls.append((path, prev, nxt))
        )
        store.transition("/tmp/hooktest", SessionState.STARTING)
        assert len(hook_calls) == 1
        assert hook_calls[0][1] == SessionState.IDLE
        assert hook_calls[0][2] == SessionState.STARTING

    def test_activity_log_records_transitions(self):
        store = SessionStateStore()
        store.get_or_create("/tmp/acttest")
        store.transition("/tmp/acttest", SessionState.STARTING)
        entry = store.get("/tmp/acttest")
        activities = entry.recent_activities()
        assert len(activities) >= 1
        assert "idle" in activities[0] or "starting" in activities[0]

    def test_full_lifecycle_transitions(self):
        store = SessionStateStore()
        path = "/tmp/fullcycle"
        store.get_or_create(path)
        assert store.transition(path, SessionState.STARTING)
        assert store.transition(path, SessionState.RUNNING)
        assert store.transition(path, SessionState.STOPPING)
        assert store.transition(path, SessionState.IDLE)
        entry = store.get(path)
        assert entry.state == SessionState.IDLE


# ---------------------------------------------------------------------------
# 6.1.3 Risk Level Classification Tests
# ---------------------------------------------------------------------------


class TestRiskClassification:
    def test_show_status_is_safe(self):
        assert classify_risk("show_status") == RiskLevel.SAFE

    def test_show_help_is_safe(self):
        assert classify_risk("show_help") == RiskLevel.SAFE

    def test_stop_workspace_is_confirm_required(self):
        assert classify_risk("stop_workspace") == RiskLevel.CONFIRM_REQUIRED

    def test_start_workspace_is_guarded(self):
        assert classify_risk("start_workspace") == RiskLevel.GUARDED

    def test_start_workspace_safe_when_already_running(self):
        assert (
            classify_risk("start_workspace", has_running_session=True) == RiskLevel.SAFE
        )

    def test_send_task_with_destructive_keyword_is_confirm(self):
        assert (
            classify_risk("send_task", task_text="删除所有用户数据")
            == RiskLevel.CONFIRM_REQUIRED
        )

    def test_send_task_long_text_is_guarded(self):
        long_task = "x" * 201
        assert classify_risk("send_task", task_text=long_task) == RiskLevel.GUARDED

    def test_send_task_short_safe_is_safe(self):
        assert classify_risk("send_task", task_text="fix the typo") == RiskLevel.SAFE

    def test_unknown_action_defaults_to_safe(self):
        assert classify_risk("unknown_action") == RiskLevel.SAFE


# ---------------------------------------------------------------------------
# 6.1.4 Confirmation Flow Timeout Tests
# ---------------------------------------------------------------------------


class TestConfirmationFlow:
    def test_create_and_consume_confirmation(self):
        mgr = ConfirmationManager()
        pending = mgr.create("stop_workspace", {"path": "/tmp/x"}, "停止 x")
        consumed = mgr.consume(pending.pending_id)
        assert consumed is not None
        assert consumed.action == "stop_workspace"

    def test_consume_nonexistent_returns_none(self):
        mgr = ConfirmationManager()
        result = mgr.consume("nonexistent_id")
        assert result is None

    def test_expired_confirmation_not_consumed(self):
        mgr = ConfirmationManager()
        pending = mgr.create("stop_workspace", {}, "停止", timeout_seconds=0.001)
        time.sleep(0.01)
        result = mgr.consume(pending.pending_id)
        assert result is None

    def test_cancel_removes_pending(self):
        mgr = ConfirmationManager()
        pending = mgr.create("stop_workspace", {}, "停止")
        cancelled = mgr.cancel(pending.pending_id)
        assert cancelled is True
        result = mgr.consume(pending.pending_id)
        assert result is None

    def test_cleanup_expired(self):
        mgr = ConfirmationManager()
        p1 = mgr.create("stop_workspace", {}, "停止", timeout_seconds=0.001)
        p2 = mgr.create("start_workspace", {}, "启动")
        time.sleep(0.01)
        expired = mgr.cleanup_expired()
        assert p1.pending_id in expired
        assert p2.pending_id not in expired

    def test_bypass_after_threshold(self):
        mgr = ConfirmationManager()
        for _ in range(3):
            p = mgr.create("stop_workspace", {}, "停止")
            mgr.consume(p.pending_id)
        assert mgr.should_bypass("stop_workspace") is True

    def test_force_flag_bypasses(self):
        mgr = ConfirmationManager()
        assert mgr.should_bypass("stop_workspace", force=True) is True

    def test_operation_tracker_busy_detection(self):
        tracker = OperationTracker()
        op_id = tracker.start("/tmp/p", "some task")
        assert tracker.is_busy("/tmp/p") is not None
        tracker.finish(op_id)
        assert tracker.is_busy("/tmp/p") is None

    def test_operation_tracker_elapsed(self):
        tracker = OperationTracker()
        op_id = tracker.start("/tmp/q", "task")
        time.sleep(0.05)
        elapsed = tracker.elapsed(op_id)
        assert elapsed >= 0.04
        tracker.finish(op_id)
