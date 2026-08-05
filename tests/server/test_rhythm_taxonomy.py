# -*- coding: utf-8 -*-
# @file test_rhythm_taxonomy.py
# @brief Rhythm 分类学测试（kind_meta schema 校验 / generic→habit 改判流 / AI hint 采纳）
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
分类学测试（设计文档 §4.0）

- kind_meta 按 kind 分发校验（非法类型拒绝；M1 宽松：缺字段补默认值）
- generic 捕获 → AI hint 写回 → confirm-hint 改判 habit → confirm → ACTIVE
- 驳回 hint 留痕
- buffer 禁止人工创建/改判
"""

import pytest
from sqlalchemy.orm import Session

from sail_server.application.dto.rhythm import (
    AffairCreateRequest,
    AffairKind,
    AffairState,
    AffairUpdateRequest,
    ConfirmHintRequest,
    validate_kind_meta,
)
from sail_server.model.rhythm import (
    RhythmBadRequestError,
    confirm_hint_impl,
    create_affair_impl,
    update_affair_impl,
)

pytestmark = pytest.mark.server


# ============================================================================
# kind_meta 校验器（纯函数）
# ============================================================================


class TestKindMetaValidation:
    def test_habit_meta_defaults(self):
        """M1 宽松校验：缺字段补默认值"""
        meta = validate_kind_meta(AffairKind.HABIT, {})
        assert meta["freq_per_week"] == 3
        assert meta["min_session_minutes"] == 30
        assert meta["streak"] == 0

    def test_habit_meta_invalid_type_rejected(self):
        """非法类型拒绝（controller 映射 400）"""
        with pytest.raises(ValueError):
            validate_kind_meta(AffairKind.HABIT, {"freq_per_week": "not_a_number"})

    def test_precept_meta(self):
        meta = validate_kind_meta(
            AffairKind.PRECEPT,
            {"rule_text": "23:30前入睡", "severity": "hard", "check_time": "23:00"},
        )
        assert meta["severity"] == "hard"
        assert meta["cycle"] == "daily"

    def test_venture_meta(self):
        meta = validate_kind_meta(
            AffairKind.VENTURE,
            {"target_date": "2027-04-01", "weekly_budget_hours": 8, "total_est_hours": 300},
        )
        assert meta["weekly_budget_hours"] == 8.0
        assert meta["spare_time_only"] is True

    def test_fixed_plan_meta(self):
        meta = validate_kind_meta(
            AffairKind.FIXED_PLAN,
            {"fixed_start": "2026-10-01T08:00:00", "fixed_end": "2026-10-05T20:00:00"},
        )
        assert meta["immovable"] is True

    def test_task_oneoff_meta_passthrough(self):
        """task_oneoff / generic / buffer 无额外约束"""
        assert validate_kind_meta(AffairKind.TASK_ONEOFF, {}) == {}
        assert validate_kind_meta(AffairKind.GENERIC, {"x": 1}) == {"x": 1}


# ============================================================================
# 捕获与改判流
# ============================================================================


class TestCaptureAndTriage:
    def test_capture_defaults_to_generic_inbox(self, db: Session):
        """快速捕获：仅标题，kind=generic 进 INBOX"""
        affair = create_affair_impl(db, AffairCreateRequest(title="给车做保养"))
        assert affair.kind == AffairKind.GENERIC
        assert affair.state == AffairState.INBOX
        assert affair.domain is None

    def test_create_with_kind_and_meta(self, db: Session):
        affair = create_affair_impl(
            db,
            AffairCreateRequest(
                title="每周运动3次",
                kind=AffairKind.HABIT,
                domain="life",
                kind_meta={"freq_per_week": 3, "min_session_minutes": 30},
            ),
        )
        assert affair.kind == AffairKind.HABIT
        assert affair.kind_meta["freq_per_week"] == 3

    def test_create_habit_invalid_meta_400(self, db: Session):
        """缺 freq_per_week 的 habit 走默认值；非法类型拒绝（ValueError → 400）"""
        with pytest.raises(ValueError):
            create_affair_impl(
                db,
                AffairCreateRequest(
                    title="bad habit",
                    kind=AffairKind.HABIT,
                    kind_meta={"freq_per_week": [1, 2]},
                ),
            )

    def test_buffer_create_forbidden(self, db: Session):
        with pytest.raises(RhythmBadRequestError):
            create_affair_impl(
                db, AffairCreateRequest(title="sys buffer", kind=AffairKind.BUFFER)
            )

    def test_generic_to_habit_via_put(self, db: Session):
        """PUT 改判 kind + kind_meta 校验"""
        affair = create_affair_impl(db, AffairCreateRequest(title="每天跑步"))
        updated = update_affair_impl(
            db,
            affair.id,
            AffairUpdateRequest(
                kind=AffairKind.HABIT,
                domain="life",
                kind_meta={"freq_per_week": 5},
            ),
        )
        assert updated is not None
        assert updated.kind == AffairKind.HABIT
        assert updated.kind_meta["freq_per_week"] == 5
        assert updated.kind_meta["min_session_minutes"] == 30  # 补默认

    def test_rejudge_to_buffer_forbidden(self, db: Session):
        affair = create_affair_impl(db, AffairCreateRequest(title="x"))
        with pytest.raises(RhythmBadRequestError):
            update_affair_impl(db, affair.id, AffairUpdateRequest(kind=AffairKind.BUFFER))


# ============================================================================
# AI hint 采纳/驳回
# ============================================================================


class TestAIHint:
    def _capture_with_hint(self, db: Session) -> int:
        affair = create_affair_impl(db, AffairCreateRequest(title="每周三次健身房"))
        hint = {
            "kind": "habit",
            "domain": "life",
            "kind_meta": {"freq_per_week": 3, "min_session_minutes": 45,
                          "preferred_slots": ["19:00-21:00"]},
            "importance": 4,
            "energy_cost": 20,
            "reason": "建设性/累计性目标 → habit",
            "confidence": 0.9,
        }
        updated = update_affair_impl(db, affair.id, AffairUpdateRequest(ai_hint=hint))
        assert updated is not None
        return affair.id

    def test_confirm_hint_accept(self, db: Session):
        """采纳：kind 改判 + kind_meta 草案 + 重要性/精力生效"""
        affair_id = self._capture_with_hint(db)
        confirmed = confirm_hint_impl(db, affair_id, ConfirmHintRequest(accept=True))
        assert confirmed.kind == AffairKind.HABIT
        assert confirmed.domain == "life"
        assert confirmed.kind_meta["freq_per_week"] == 3
        assert confirmed.kind_meta["min_session_minutes"] == 45
        assert confirmed.importance == 4
        assert confirmed.energy_cost == 20
        assert confirmed.ai_hint == {}

    def test_confirm_hint_accept_with_overrides(self, db: Session):
        affair_id = self._capture_with_hint(db)
        confirmed = confirm_hint_impl(
            db,
            affair_id,
            ConfirmHintRequest(accept=True, overrides={"importance": 5}),
        )
        assert confirmed.importance == 5
        assert confirmed.kind == AffairKind.HABIT

    def test_confirm_hint_reject(self, db: Session):
        affair_id = self._capture_with_hint(db)
        rejected = confirm_hint_impl(db, affair_id, ConfirmHintRequest(accept=False))
        assert rejected.kind == AffairKind.GENERIC  # 保持未分拣
        assert rejected.ai_hint == {}
        assert "rejected_hint" in rejected.ref  # 留痕

    def test_confirm_hint_no_hint_400(self, db: Session):
        affair = create_affair_impl(db, AffairCreateRequest(title="no hint"))
        with pytest.raises(RhythmBadRequestError):
            confirm_hint_impl(db, affair.id, ConfirmHintRequest(accept=True))
