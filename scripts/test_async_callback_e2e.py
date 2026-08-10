# -*- coding: utf-8 -*-
# @file test_async_callback_e2e.py
# @brief async_callback kind 端到端冒烟测试（SQLite）
# ---------------------------------
import os

os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_PATH"] = "data/test_async_e2e.db"

from datetime import datetime, date

from sail_server.db import Database, g_db_func
from sail_server.application.dto.rhythm import (
    AffairCreateRequest,
    AffairAction,
    AffairDomain,
    AffairKind,
    AffairState,
    AffairStateRequest,
    PlanDayRequest,
)
from sail_server.model.rhythm import (
    create_affair_impl,
    transit_affair_state_impl,
    get_affair_impl,
)
from sail_server.model.rhythm_planner import plan_day_impl

# 重置库（drop+create，避免文件锁）
db_obj = Database.get_instance()
db_obj.drop_all()
db_obj.create_all()

db = next(g_db_func())

print("=== 1. 捕获 async_callback 事务（INBOX）===")
resp = create_affair_impl(db, AffairCreateRequest(
    title="让 AI 起草营销文案",
    kind=AffairKind.ASYNC_CALLBACK,
    kind_meta={
        "phases": [
            {"name": "kickoff", "est_minutes": 30, "energy_cost": 25},
            {"name": "delegated", "est_minutes": 0, "energy_cost": 0},
            {"name": "review", "est_minutes": 20, "energy_cost": 15},
        ],
        "max_rounds": 3,
        "work_hours_only": True,
        "delegate_to": "ai",
        "est_wait_hours": 2.0,
    },
    importance=4,
    domain=AffairDomain.WORK,
))
aid = resp.id
print(f"  id={aid} state={resp.state} kind={resp.kind} domain={resp.domain}")
assert resp.state == AffairState.INBOX

print("=== 2. CONFIRM → ACTIVE(=KICKOFF) ===")
resp = transit_affair_state_impl(db, aid, AffairStateRequest(action=AffairAction.CONFIRM))
print(f"  state={resp.state} phase={resp.kind_meta['current_phase']} energy={resp.energy_cost} est={resp.est_minutes}")
assert resp.state == AffairState.ACTIVE
assert resp.kind_meta["current_phase"] == "kickoff"
assert resp.energy_cost == 25

print("=== 3. plan_day: KICKOFF 阶段排 async_kickoff 块 ===")
d = date(2026, 8, 5)  # 当天，HANDOFF 后 next_review_at 也落在此日
pres = plan_day_impl(db, PlanDayRequest(date=d))
kickoff_blocks = [b for b in pres.blocks if b.block_type == "async_kickoff"]
print(f"  blocks={len(pres.blocks)} kickoff_blocks={len(kickoff_blocks)}")
for b in kickoff_blocks:
    print(f"    {b.start_time:%H:%M}-{b.end_time:%H:%M} phase={b.ref.get('phase')} round={b.ref.get('round')}")
assert len(kickoff_blocks) >= 1, "KICKOFF 阶段应排块"

print("=== 4. HANDOFF → DELEGATED，计算 next_review_at ===")
resp = transit_affair_state_impl(db, aid, AffairStateRequest(
    action=AffairAction.HANDOFF, est_wait_hours=2.0))
print(f"  state={resp.state} phase={resp.kind_meta['current_phase']} next_review={resp.kind_meta.get('next_review_at')}")
assert resp.state == AffairState.DELEGATED
assert resp.kind_meta["current_phase"] == "delegated"
assert resp.kind_meta["next_review_at"] is not None
assert resp.energy_cost == 0  # DELEGATED 不占精力

print("=== 5. plan_day: DELEGATED 阶段画 informational async_wait 提醒块 ===")
pres = plan_day_impl(db, PlanDayRequest(date=d))
wait_blocks = [b for b in pres.blocks if b.block_type == "async_wait"]
print(f"  wait_blocks={len(wait_blocks)}")
for b in wait_blocks:
    print(f"    {b.start_time:%H:%M}-{b.end_time:%H:%M} info={b.ref.get('informational')} phase={b.ref.get('phase')}")
assert len(wait_blocks) >= 1
assert wait_blocks[0].ref.get("informational") is True
# work_hours_only 事务的 next_review_at 应落在工作窗
nxt = datetime.fromisoformat(resp.kind_meta["next_review_at"])
print(f"  next_review_at={nxt} weekday={nxt.weekday()} hour={nxt.hour}")
assert nxt.weekday() < 5, "work_hours_only 应顺延到工作日"
assert 9 <= nxt.hour < 12 or 14 <= nxt.hour < 18, "work_hours_only 应落在工作窗"

print("=== 6. RETURN_REVIEW → REVIEWING ===")
resp = transit_affair_state_impl(db, aid, AffairStateRequest(action=AffairAction.RETURN_REVIEW))
print(f"  state={resp.state} phase={resp.kind_meta['current_phase']} energy={resp.energy_cost} est={resp.est_minutes}")
assert resp.state == AffairState.REVIEWING
assert resp.kind_meta["current_phase"] == "review"
assert resp.energy_cost == 15

print("=== 7. REQUEST_REVISION → 回 DELEGATED，round=2 ===")
resp = transit_affair_state_impl(db, aid, AffairStateRequest(
    action=AffairAction.REQUEST_REVISION, revision_note="文案太正式"))
print(f"  state={resp.state} round={resp.kind_meta['round']} phase={resp.kind_meta['current_phase']}")
print(f"  revision_history={resp.kind_meta.get('revision_history')}")
assert resp.state == AffairState.DELEGATED
assert resp.kind_meta["round"] == 2
assert len(resp.kind_meta["revision_history"]) == 1

print("=== 8. 跑 round 2 全流程到 APPROVE ===")
# REQUEST_REVISION 已把状态置 DELEGATED（round=2），直接 RETURN_REVIEW → APPROVE
transit_affair_state_impl(db, aid, AffairStateRequest(action=AffairAction.RETURN_REVIEW))
resp = transit_affair_state_impl(db, aid, AffairStateRequest(action=AffairAction.APPROVE))
print(f"  state={resp.state} phase={resp.kind_meta['current_phase']}")
assert resp.state == AffairState.COMPLETED

print("=== 9. REQUEST_REVISION 超 max_rounds 应被拒 ===")
# max_rounds=2：round1 revise→round2(达 max)，再 revise→round3 应拒
resp2 = create_affair_impl(db, AffairCreateRequest(
    title="边界测试", kind=AffairKind.ASYNC_CALLBACK,
    kind_meta={"max_rounds": 2, "work_hours_only": False, "est_wait_hours": 1.0},
    domain=AffairDomain.WORK,
))
transit_affair_state_impl(db, resp2.id, AffairStateRequest(action=AffairAction.CONFIRM))
transit_affair_state_impl(db, resp2.id, AffairStateRequest(action=AffairAction.HANDOFF, est_wait_hours=1.0))
transit_affair_state_impl(db, resp2.id, AffairStateRequest(action=AffairAction.RETURN_REVIEW))
# round 1 → 2 (达 max，仍允许进入 round 2)
transit_affair_state_impl(db, resp2.id, AffairStateRequest(action=AffairAction.REQUEST_REVISION, revision_note="r1"))
print(f"  round after first revision: {get_affair_impl(db, resp2.id).kind_meta['round']}")
# round 2：DELEGATED → RETURN_REVIEW → REVIEWING → 再 revise 触发 round3，超 max 应拒
transit_affair_state_impl(db, resp2.id, AffairStateRequest(action=AffairAction.RETURN_REVIEW))
try:
    transit_affair_state_impl(db, resp2.id, AffairStateRequest(action=AffairAction.REQUEST_REVISION, revision_note="r2"))
    print("  ERROR: 应被拒绝但未拒绝")
    assert False, "应抛 max_rounds 异常"
except Exception as e:
    print(f"  正确拒绝: {type(e).__name__}: {e}")

print("\n=== ALL TESTS PASSED ===")
