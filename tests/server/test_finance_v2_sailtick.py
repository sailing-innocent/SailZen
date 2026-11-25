# -*- coding: utf-8 -*-
# @file test_finance_v2_sailtick.py
# @brief Finance 2.0 (SailTick 日常开销秘书) 后端核心单元测试：智能对账、明细拆分、分级自治清理与一键撤销、OCR 账单落库
# @author sailing-innocent
# @date 2026-11-25
# @version 1.0
# ---------------------------------

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sailzen_orm import ORMBase
from sailzen_orm.finance import Account, FinanceTag, Transaction
from sailzen_orm.health import DietLog
from sailzen_orm.tick import SailTickIntakeDraft
from sail_server.application.dto.finance import (
    AccountData,
    AccountReconcileRequest,
    TransactionData,
    TransactionLineItem,
    TransactionMetaUpdateRequest,
)
from sail_server.application.dto.tick import ImageIntakeCommitRequest, IntakeEntryDto
from sail_server.model.finance.account import (
    create_account_impl,
    list_balance_checkpoints_impl,
    reconcile_account_balance_impl,
    update_account_balance_impl,
)
from sail_server.model.finance.hygiene import (
    approve_hygiene_proposal_impl,
    create_hygiene_proposal_impl,
    dismiss_hygiene_proposal_impl,
    get_finance_overview_impl,
    list_hygiene_months_impl,
    list_hygiene_proposals_impl,
    revert_hygiene_proposal_impl,
    run_hygiene_scan_impl,
)
from sail_server.model.finance.tag import seed_default_tags_impl
from sail_server.model.finance.transaction import (
    create_transaction_impl,
    get_breakdown_stats_impl,
    get_transaction_stats_impl,
    update_transaction_meta_impl,
)
from sail_server.model.tick_intake import commit_image_intake_impl


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    ORMBase.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    seed_default_tags_impl(session)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _mk_account(db, name: str, balance: str = "1000.00") -> AccountData:
    return create_account_impl(
        db,
        AccountData(name=name, description="", balance=balance, state=0),
    )


def test_reconcile_micro_drift_and_revert(db_session):
    """小额余额漂移（<=30元）应自动无感平账，不污染消费统计，且支持一键撤销。"""
    acc = _mk_account(db_session, "微信", "500.00")
    now_ts = datetime.now().timestamp()

    # 正常消费 50 元
    create_transaction_impl(
        db_session,
        TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="50.00",
            description="午饭",
            tags="零食",
            htime=now_ts,
        ),
    )
    update_account_balance_impl(db_session, acc.id)

    # 真实余额为 438.50（差额 -11.50 <= 30）
    res = reconcile_account_balance_impl(
        db_session,
        AccountReconcileRequest(account_id=acc.id, actual_balance="438.50", note="月底核对"),
    )
    assert res["handling"] == "micro_adjusted"
    assert res["drift_amount"] == "-11.50"
    assert Decimal(res["account"].balance) == Decimal("438.50")
    assert res["proposal_id"] is not None

    # 统计中应只包含正常消费 50.00，不包含 11.50 的平账噪音
    stats = get_transaction_stats_impl(
        db_session,
        from_time=now_ts - 3600,
        to_time=now_ts + 3600,
    )
    assert stats["expense_total"].startswith("50.00")

    # 检查核对快照
    cps = list_balance_checkpoints_impl(db_session, account_id=acc.id)
    assert len(cps) == 1
    assert cps[0].handling == "micro_adjusted"

    # 一键撤销该小额平账，余额应准确回退到 450.00
    reverted = revert_hygiene_proposal_impl(db_session, res["proposal_id"])
    assert reverted is not None and reverted.status == "reverted"
    refreshed = db_session.query(Account).filter(Account.id == acc.id).first()
    assert Decimal(refreshed.balance) == Decimal("450.00")


def test_reconcile_large_drift_creates_review_proposal(db_session):
    """超过阈值的大额差额不应盲目抹平，应进入待排查清理队列，批准后再强制平账。"""
    acc = _mk_account(db_session, "支付宝余额宝", "2000.00")
    res = reconcile_account_balance_impl(
        db_session,
        AccountReconcileRequest(account_id=acc.id, actual_balance="1750.00", micro_threshold=30.0),
    )
    assert res["handling"] == "large_drift_pending"
    assert Decimal(res["account"].balance) == Decimal("2000.00")
    assert res["proposal_id"] is not None

    # 人工批准该提案 → 执行强制平账到 1750.00
    approved = approve_hygiene_proposal_impl(db_session, res["proposal_id"])
    assert approved is not None and approved.status == "applied"
    refreshed = db_session.query(Account).filter(Account.id == acc.id).first()
    assert Decimal(refreshed.balance) == Decimal("1750.00")


def test_breakdown_stats_honors_multi_item_split(db_session):
    """一次超市混合采购拆分为日用+零食后，统计应精准计入各自品类并穿透统计真实零食支出。"""
    acc = _mk_account(db_session, "支付宝", "1000.00")
    now_ts = datetime.now().timestamp()

    tx = create_transaction_impl(
        db_session,
        TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="128.50",
            description="盒马鲜生采购",
            tags="日用消耗",
            htime=now_ts,
        ),
    )
    updated = update_transaction_meta_impl(
        db_session,
        tx.id,
        TransactionMetaUpdateRequest(
            items=[
                TransactionLineItem(name="薯片+可乐", amount="42.00", tag="零食", is_snack=True),
                TransactionLineItem(name="洗衣液+抽纸", amount="86.50", tag="日用消耗", is_snack=False),
            ]
        ),
    )
    assert updated is not None
    assert "零食" in updated.tags and "日用消耗" in updated.tags

    bd = get_breakdown_stats_impl(db_session, from_time=now_ts - 3600, to_time=now_ts + 3600)
    assert bd["total_expense"] == "128.50"
    assert bd["snack_total"] == "42.00"
    assert bd["snack_from_split"] == "42.00"
    assert bd["split_tx_count"] == 1
    by_tag = {r["tag"]: r["amount"] for r in bd["by_tag"]}
    assert by_tag["零食"] == "42.00"
    assert by_tag["日用消耗"] == "86.50"


def test_hygiene_graded_autonomy_scan_and_revert(db_session):
    """分级自治扫描：历史 balance fix 自动隔离、高置信度精确匹配自动打标（可撤销），混合商超/疑似重复/差旅入待审队列。"""
    acc = _mk_account(db_session, "微信", "5000.00")
    now = datetime.now()

    # 1. 历史已打标样本（建立精确共识：瑞幸咖啡 -> 零食）
    for i in range(3):
        create_transaction_impl(
            db_session,
            TransactionData(
                from_acc_id=acc.id,
                to_acc_id=-1,
                value="18.00",
                description="瑞幸咖啡",
                tags="零食",
                htime=(now - timedelta(days=20 + i)).timestamp(),
            ),
        )

    # 2. 历史遗留 1970 balance fix
    legacy_fix = create_transaction_impl(
        db_session,
        TransactionData(
            from_acc_id=-1,
            to_acc_id=acc.id,
            value="12.34",
            description="balance fix",
            tags="",
            htime=1.0,
        ),
    )

    # 3. 待自动补标：瑞幸咖啡（高置信度精确匹配）
    untagged_coffee = create_transaction_impl(
        db_session,
        TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="19.90",
            description="瑞幸咖啡 ",
            tags="",
            htime=(now - timedelta(days=2)).timestamp(),
        ),
    )

    # 4. 混合商超采购（应进入待审 mixed_split_hint，而非盲目单标）
    create_transaction_impl(
        db_session,
        TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="156.00",
            description="盒马鲜生",
            tags="",
            htime=(now - timedelta(days=1)).timestamp(),
        ),
    )

    # 5. 疑似重复交易（同金额 3 分钟内两笔）
    create_transaction_impl(
        db_session,
        TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="35.00",
            description="晚饭",
            tags="零食",
            htime=(now - timedelta(hours=3)).timestamp(),
        ),
    )
    create_transaction_impl(
        db_session,
        TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="35.00",
            description="晚饭",
            tags="零食",
            htime=(now - timedelta(hours=3) + timedelta(minutes=2)).timestamp(),
        ),
    )

    # 6. 近 30 天高铁账单（应生成 travel_rhythm_link 待审建议）
    create_transaction_impl(
        db_session,
        TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="233.00",
            description="12306高铁订票",
            tags="交通",
            htime=(now - timedelta(days=3)).timestamp(),
        ),
    )

    scan_res = run_hygiene_scan_impl(db_session, days=90, auto_apply_safe=True)
    assert scan_res["legacy_fix_auto_classified"] == 1
    assert scan_res["auto_tagged_count"] >= 1
    assert scan_res["mixed_split_hints"] >= 1
    assert scan_res["duplicates_detected"] >= 1
    assert scan_res["travel_links_detected"] >= 1

    # 验证 legacy fix 已被隔离，且瑞幸咖啡已被自动打标
    db_fix = db_session.query(Transaction).filter(Transaction.id == legacy_fix.id).first()
    assert db_fix.exclude_from_stats is True
    assert db_fix.entry_kind == "balance_adjust"

    db_coffee = db_session.query(Transaction).filter(Transaction.id == untagged_coffee.id).first()
    assert db_coffee.tags == "零食"

    # 测试一键撤销自动打标
    auto_props = list_hygiene_proposals_impl(db_session, status="applied", autonomy_level="auto_applied")
    tag_prop = next(p for p in auto_props if p.proposal_type == "auto_tag")
    revert_hygiene_proposal_impl(db_session, tag_prop.id)
    db_session.refresh(db_coffee)
    assert db_coffee.tags == ""

    # 测试 overview 正常返回
    ov = get_finance_overview_impl(db_session)
    assert ov["excluded_adjustments_count"] >= 1
    assert ov["pending_hygiene_count"] >= 3


def test_ocr_receipt_commit_splits_and_links_health(db_session):
    """小票 OCR 草稿确认落库时：创建 1 笔带 items 拆分的交易 + 自动向健康表写入零食 DietLog。"""
    _mk_account(db_session, "支付宝余额宝", "1000.00")

    draft = SailTickIntakeDraft(
        status="pending_confirm",
        source_channel="web",
        media_key="2026-11/sample_receipt.jpg",
        scene="receipt",
        summary="盒马小票 ¥128.50（日用品+零食）",
        coach_advice="已自动拆出零食 ¥42，注意减脂期控制",
        entries=[
            {
                "selected": True,
                "kind": "transaction",
                "title": "盒马采购 ¥128.50",
                "confidence": 0.94,
                "data": {
                    "direction": "expense",
                    "amount": 128.5,
                    "description": "盒马鲜生",
                    "tags": "日用消耗,零食",
                    "account_hint": "支付宝",
                    "htime": "2026-11-25 18:20",
                    "sync_to_health": True,
                    "items": [
                        {"name": "薯片", "amount": "42.00", "tag": "零食", "is_snack": True},
                        {"name": "洗衣液", "amount": "86.50", "tag": "日用消耗", "is_snack": False},
                    ],
                },
            }
        ],
    )
    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)

    commit_res = commit_image_intake_impl(
        db_session,
        draft.id,
        ImageIntakeCommitRequest(
            entries=[IntakeEntryDto.model_validate(draft.entries[0])],
            summary=draft.summary,
        ),
    )

    ref_kinds = {r.kind for r in commit_res.committed_refs}
    assert "transaction" in ref_kinds
    assert "diet" in ref_kinds

    tx = db_session.query(Transaction).first()
    assert tx is not None
    assert tx.value == "128.50"
    assert len(tx.meta.get("items", [])) == 2
    assert len(tx.meta.get("links", {}).get("diet_ids", [])) == 1

    diet = db_session.query(DietLog).first()
    assert diet is not None
    assert "薯片" in diet.description


def test_hygiene_months_window_scan_and_budget_cap(db_session):
    """按月统计未打标分布 + 精确月份窗口扫描 + 待审条数上限限流 + 幂等创建提案。"""
    acc = _mk_account(db_session, "微信", "5000.00")

    # 2026-09：2 笔商超混合采购（均未打标）
    for day in (5, 12):
        create_transaction_impl(
            db_session,
            TransactionData(
                from_acc_id=acc.id,
                to_acc_id=-1,
                value="98.00",
                description="盒马鲜生",
                tags="",
                htime=datetime(2026, 9, day, 18, 0).timestamp(),
            ),
        )
    # 2026-10：1 笔已打标交易（整洁月）
    create_transaction_impl(
        db_session,
        TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="25.00",
            description="地铁",
            tags="交通",
            htime=datetime(2026, 10, 8, 9, 0).timestamp(),
        ),
    )

    months = list_hygiene_months_impl(db_session)
    assert months["total_months"] == 2
    assert months["months"][0]["month"] == "2026-10"
    assert months["months"][0]["needs_work"] is False
    assert months["months"][1]["month"] == "2026-09"
    assert months["months"][1]["needs_work"] is True
    assert months["months"][1]["untagged_expenses"] == 2

    # 仅扫描 2026-09 且限制 max_review_proposals=1
    res = run_hygiene_scan_impl(
        db_session,
        days=None,
        from_time=datetime(2026, 9, 1, 0, 0).timestamp(),
        to_time=datetime(2026, 9, 30, 23, 59).timestamp(),
        auto_apply_safe=True,
        max_review_proposals=1,
        include_legacy_fix=False,
    )
    assert res["scanned_transactions"] == 2
    assert res["review_proposals_created"] == 1

    # 慢脑创建待审提案：幂等去重 & 严格 needs_review
    p1, c1 = create_hygiene_proposal_impl(
        db_session,
        proposal_type="auto_tag",
        target_tx_ids=[1],
        title="慢脑建议 #1",
        reason="语义推断",
        confidence=0.8,
        after_payload={"tags": "日用消耗"},
    )
    assert c1 is True and p1 is not None and p1.autonomy_level == "needs_review"
    p2, c2 = create_hygiene_proposal_impl(
        db_session,
        proposal_type="auto_tag",
        target_tx_ids=[1],
        title="重复建议 #1",
        after_payload={"tags": "日用消耗"},
    )
    assert c2 is False and p2 is None
