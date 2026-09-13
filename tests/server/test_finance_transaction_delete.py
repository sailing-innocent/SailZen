# -*- coding: utf-8 -*-
# @file test_finance_transaction_delete.py
# @brief 财务交易删除链路测试（真正删除 + 余额回退 + deprecated 行排除）
# @author sailing-innocent
# @date 2026-XX-XX
# @version 1.0
# ---------------------------------

"""
覆盖 site 前端 Delete Transaction 链路对应的服务端行为：

- delete_transaction_impl 必须真正删除记录（历史实现只做软删除标记，
  导致记录刷新后重新出现、其他端仍可见）
- 删除时必须回退已实际计入账户余额的金额（updated/changed 状态机语义）
- 列表/统计查询必须排除历史遗留的 deprecated（软删除）行
"""

from datetime import datetime

import pytest

from sail_server.application.dto.finance import (
    AccountData,
    TransactionData,
    TransactionState,
)
from sail_server.infrastructure.orm.finance import Transaction
from sail_server.model.finance.account import (
    create_account_impl,
    read_account_impl,
    update_account_balance_impl,
)
from sail_server.model.finance.transaction import (
    clear_invalid_trnasaction_impl,
    create_transaction_impl,
    delete_transaction_impl,
    get_transaction_stats_impl,
    read_transactions_impl,
    read_untagged_transactions_impl,
    update_transaction_impl,
)

pytestmark = pytest.mark.server

HTIME = datetime(2026, 1, 1).timestamp()


def _make_account(db, name: str, balance: str = "0.0") -> AccountData:
    return create_account_impl(
        db, AccountData(name=name, description="", balance=balance, state=0)
    )


def _make_transaction(
    db, from_acc_id: int, to_acc_id: int, value: str, description: str = "test"
) -> TransactionData:
    return create_transaction_impl(
        db,
        TransactionData(
            from_acc_id=from_acc_id,
            to_acc_id=to_acc_id,
            value=value,
            description=description,
            tags="",
            htime=HTIME,
        ),
    )


# ----------------------------------------------------------------------------
# 删除行为
# ----------------------------------------------------------------------------


def test_delete_transaction_hard_deletes_row(db):
    acc_a = _make_account(db, "A", "100.0")
    acc_b = _make_account(db, "B", "0.0")
    trans = _make_transaction(db, acc_a.id, acc_b.id, "30.0")

    deleted = delete_transaction_impl(db, trans.id)

    assert deleted is not None
    assert deleted.id == trans.id
    # 记录必须真正从表中消失（历史 bug：仅设置 deprecated 位，行仍保留）
    assert db.query(Transaction).filter(Transaction.id == trans.id).first() is None


def test_delete_transaction_not_found_returns_none(db):
    assert delete_transaction_impl(db, 999999) is None
    assert delete_transaction_impl(db, None) is None


def test_delete_reverses_applied_balance(db):
    """交易已入账（updated 位）后删除：两侧余额都要回退。"""
    acc_a = _make_account(db, "A", "100.0")
    acc_b = _make_account(db, "B", "0.0")
    trans = _make_transaction(db, acc_a.id, acc_b.id, "30.0")

    # 先入账：A -= 30 -> 70, B += 30 -> 30
    update_account_balance_impl(db, acc_a.id)
    update_account_balance_impl(db, acc_b.id)
    assert read_account_impl(db, acc_a.id).balance == "70.0"
    assert read_account_impl(db, acc_b.id).balance == "30.0"

    delete_transaction_impl(db, trans.id)

    assert read_account_impl(db, acc_a.id).balance == "100.0"
    assert read_account_impl(db, acc_b.id).balance == "0.0"


def test_delete_never_applied_keeps_balance(db):
    """交易创建后从未入账就删除：余额不变。"""
    acc_a = _make_account(db, "A", "100.0")
    acc_b = _make_account(db, "B", "0.0")
    trans = _make_transaction(db, acc_a.id, acc_b.id, "30.0")

    delete_transaction_impl(db, trans.id)

    assert read_account_impl(db, acc_a.id).balance == "100.0"
    assert read_account_impl(db, acc_b.id).balance == "0.0"


def test_delete_pending_change_reverses_prev_value(db):
    """交易已入账后又被修改（changed 位，差额未入账），删除时按 prev_value 回退。"""
    acc_a = _make_account(db, "A", "100.0")
    acc_b = _make_account(db, "B", "0.0")
    trans = _make_transaction(db, acc_a.id, acc_b.id, "30.0")
    update_account_balance_impl(db, acc_a.id)
    update_account_balance_impl(db, acc_b.id)

    # 修改交易 30 -> 50，差额尚未入账（changed 位）
    update_transaction_impl(
        db,
        trans.id,
        TransactionData(
            from_acc_id=acc_a.id,
            to_acc_id=acc_b.id,
            value="50.0",
            description="test",
            tags="",
            htime=HTIME,
        ),
    )

    delete_transaction_impl(db, trans.id)

    # 余额中只入账过 30.0，删除后应完全回退
    assert read_account_impl(db, acc_a.id).balance == "100.0"
    assert read_account_impl(db, acc_b.id).balance == "0.0"


def test_delete_income_transaction_reverses_to_account(db):
    """外部 -> 账户 的收入交易删除后，to 账户余额回退。"""
    acc = _make_account(db, "A", "100.0")
    trans = _make_transaction(db, -1, acc.id, "55.5")

    update_account_balance_impl(db, acc.id)
    assert read_account_impl(db, acc.id).balance == "155.5"

    delete_transaction_impl(db, trans.id)
    assert read_account_impl(db, acc.id).balance == "100.0"


# ----------------------------------------------------------------------------
# 历史软删除（deprecated）数据的查询排除
# ----------------------------------------------------------------------------


def _insert_legacy_soft_deleted(db, from_acc_id, to_acc_id, value: str) -> int:
    """模拟历史 delete_transaction_impl 遗留的 deprecated 行。

    与旧实现一致：仅对有效账户侧设置 deprecated 位。
    """
    state = TransactionState(0)
    if from_acc_id is not None:
        state.set_from_acc_deprecated()
    if to_acc_id is not None:
        state.set_to_acc_deprecated()
    trans = Transaction(
        from_acc_id=from_acc_id,
        to_acc_id=to_acc_id,
        value=value,
        prev_value="0.0",
        description="legacy-deleted",
        tags="legacy",
        state=state.value,
        htime=datetime.fromtimestamp(HTIME),
        ctime=datetime.now(),
        mtime=datetime.now(),
    )
    db.add(trans)
    db.commit()
    return trans.id


def test_read_transactions_excludes_legacy_deprecated_rows(db):
    acc_a = _make_account(db, "A", "100.0")
    acc_b = _make_account(db, "B", "0.0")
    live = _make_transaction(db, acc_a.id, acc_b.id, "30.0")
    legacy_id = _insert_legacy_soft_deleted(db, acc_a.id, acc_b.id, "99.0")

    ids = [t.id for t in read_transactions_impl(db)]
    assert live.id in ids
    assert legacy_id not in ids


def test_stats_exclude_legacy_deprecated_rows(db):
    acc_a = _make_account(db, "A", "100.0")
    _insert_legacy_soft_deleted(db, acc_a.id, None, "99.0")

    stats = get_transaction_stats_impl(db)
    assert stats["total_count"] == 0
    assert stats["income_count"] == 0
    assert stats["expense_count"] == 0


def test_untagged_exclude_legacy_deprecated_rows(db):
    acc_a = _make_account(db, "A", "100.0")
    _insert_legacy_soft_deleted(db, acc_a.id, None, "99.0")

    result = read_untagged_transactions_impl(db)
    assert result["total"] == 0
    assert result["data"] == []


def test_update_balance_finalizes_legacy_deprecated_once(db):
    """余额更新遇到历史 deprecated 行：回退一次后状态位清零，不再重复影响。"""
    acc = _make_account(db, "A", "100.0")
    # 该交易为支出 40 且曾入账（余额 100 是已扣除 40 后的值），
    # 删除回退后余额应加回 40 -> 140
    legacy_id = _insert_legacy_soft_deleted(db, acc.id, None, "40.0")
    row = db.query(Transaction).filter(Transaction.id == legacy_id).first()
    state = TransactionState(row.state)
    state.set_from_acc_updated()  # 历史数据：余额中已入账
    row.state = state.value
    db.commit()

    update_account_balance_impl(db, acc.id)
    assert read_account_impl(db, acc.id).balance == "140.0"
    assert db.query(Transaction).filter(Transaction.id == legacy_id).first().state == 0

    # 再次更新不应重复回退
    update_account_balance_impl(db, acc.id)
    assert read_account_impl(db, acc.id).balance == "140.0"


def test_clear_invalid_removes_finalized_legacy_rows(db):
    acc = _make_account(db, "A", "100.0")
    legacy_id = _insert_legacy_soft_deleted(db, acc.id, None, "40.0")

    update_account_balance_impl(db, acc.id)
    clear_invalid_trnasaction_impl(db)

    assert db.query(Transaction).filter(Transaction.id == legacy_id).first() is None
