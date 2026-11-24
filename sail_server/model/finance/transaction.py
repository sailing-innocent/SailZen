from sailzen_orm.finance import Account, Transaction
from sail_server.application.dto.finance import (
    TransactionData,
    AccountState,
    TransactionState,
)
from sail_server.utils.finance_helpers import _acc, _acc_inv, _htime, _htime_inv

from sail_server.utils.money import Money
from bisect import bisect_left, bisect_right
from datetime import datetime
from decimal import Decimal
from typing import Any

import time
import logging

logger = logging.getLogger(__name__)

#: state bits 6/7 = from/to_acc_deprecated（见 TransactionState）
TRANSACTION_DEPRECATED_MASK = (1 << 6) | (1 << 7)


def _not_deprecated():
    """排除软删除（deprecated）交易的查询过滤条件。

    历史上 delete_transaction_impl 只做软删除标记，遗留数据仍带有
    deprecated 位，需要在这些查询中被排除。
    """
    return Transaction.state.op("&")(TRANSACTION_DEPRECATED_MASK) == 0


def clean_all_impl(db):
    db.query(Transaction).delete()
    db.commit()


def validate_account_exists(db, account_id: int) -> bool:
    return db.query(Account).filter(Account.id == account_id).first() is not None


def trans_from_create(create: TransactionData):
    init_state = TransactionState(0)
    from_acc_id = _acc(create.from_acc_id)
    to_acc_id = _acc(create.to_acc_id)
    budget_id = create.budget_id if create.budget_id is not None else None
    # Use current time if htime is None
    htime_val = create.htime if create.htime is not None else datetime.now().timestamp()
    return Transaction(
        from_acc_id=from_acc_id,
        to_acc_id=to_acc_id,
        budget_id=budget_id,
        prev_value="0.0",  # default
        value=create.value,
        description=create.description,
        tags=create.tags,
        state=init_state.value,
        htime=_htime(htime_val),
        ctime=datetime.now(),
        mtime=datetime.now(),
    )


def read_from_trans(trans: Transaction):
    tags = ""
    if trans.tags is not None:
        tags = trans.tags
    budget_id = None
    if trans.budget_id is not None:
        budget_id = trans.budget_id
    return TransactionData(
        id=trans.id,
        from_acc_id=_acc_inv(trans.from_acc_id),
        to_acc_id=_acc_inv(trans.to_acc_id),
        value=trans.value,
        prev_value=trans.prev_value,
        description=trans.description,
        tags=tags,
        budget_id=budget_id,
        state=trans.state,
        htime=_htime_inv(trans.htime),
        ctime=trans.ctime,
        mtime=trans.mtime,
    )


def validate_transaction_impl(db, transaction_id: int):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    state = TransactionState(transaction.state)
    from_acc_id = _acc_inv(transaction.from_acc_id)
    to_acc_id = _acc_inv(transaction.to_acc_id)

    if db.query(Account).filter(Account.id == from_acc_id).first() is not None:
        state.set_from_acc_valid()
    else:
        state.unset_from_acc_valid()
    if db.query(Account).filter(Account.id == to_acc_id).first() is not None:
        state.set_to_acc_valid()
    else:
        state.unset_to_acc_valid()

    transaction.state = state.value
    db.commit()


def validate_transactions_impl(db):
    transactions = db.query(Transaction).all()
    for transaction in transactions:
        state = TransactionState(transaction.state)
        # 已软删除（deprecated）的交易不再重新标记 valid，避免"复活"
        if state.is_from_acc_deprecated() or state.is_to_acc_deprecated():
            continue
        from_acc_id = _acc_inv(transaction.from_acc_id)
        to_acc_id = _acc_inv(transaction.to_acc_id)

        if db.query(Account).filter(Account.id == from_acc_id).first() is not None:
            state.set_from_acc_valid()
        else:
            state.unset_from_acc_valid()
        if db.query(Account).filter(Account.id == to_acc_id).first() is not None:
            state.set_to_acc_valid()
        else:
            state.unset_to_acc_valid()

        transaction.state = state.value
    db.commit()


def create_transaction_impl(db, transaction_create: TransactionData):
    transaction = trans_from_create(transaction_create)
    db.add(transaction)
    db.commit()
    # validate transaction
    validate_transaction_impl(db, transaction.id)
    db.refresh(transaction)
    return read_from_trans(transaction)


def _build_transaction_query(
    db,
    from_time: float = None,
    to_time: float = None,
    _tags: list = [],
    tag_op: str = "and",
    _desc: str = None,
    min_value: float = None,
    max_value: float = None,
):
    """Build the base query for transactions with filtering."""
    q = db.query(Transaction).filter(Transaction.state != 0, _not_deprecated())

    if len(_tags) > 0:
        condition = None
        for tag in _tags:
            if tag is not None and tag.strip() != "":
                if condition is None:
                    condition = Transaction.tags.like(f"%{tag}%")
                else:
                    if tag_op == "or":
                        condition = condition | Transaction.tags.like(f"%{tag}%")
                    else:
                        condition = condition & Transaction.tags.like(f"%{tag}%")
        if condition is not None:
            q = q.filter(condition)

    if _desc is not None:
        q = q.filter(Transaction.description.like(f"%{_desc}%"))
    if from_time is not None:
        q = q.filter(Transaction.htime >= _htime(from_time))
    if to_time is not None:
        q = q.filter(Transaction.htime <= _htime(to_time))
    if min_value is not None:
        q = q.filter(Transaction.value >= str(min_value))
    if max_value is not None:
        q = q.filter(Transaction.value <= str(max_value))

    return q


def read_transactions_impl(
    db,
    skip: int = -1,
    limit: int = -1,
    from_time: float = None,
    to_time: float = None,
    _tags: str = [],
    tag_op: str = "and",  # "and" or "or"
    _desc: str = None,
):
    q = _build_transaction_query(db, from_time, to_time, _tags, tag_op, _desc)
    q = q.order_by(Transaction.htime.desc())

    if skip >= 0:
        q = q.offset(skip)
    if limit > 0:
        q = q.limit(limit)

    transactions = q.all()
    if transactions is None:
        return []
    return [read_from_trans(transaction) for transaction in transactions]


def read_transactions_paginated_impl(
    db,
    page: int = 1,
    page_size: int = 20,
    from_time: float = None,
    to_time: float = None,
    _tags: list = [],
    tag_op: str = "and",
    _desc: str = None,
    min_value: float = None,
    max_value: float = None,
    sort_by: str = "htime",
    sort_order: str = "desc",
):
    """
    Get transactions with pagination support.

    Returns:
        Dict with pagination metadata and data:
        {
            "data": List[TransactionData],
            "total": int,
            "page": int,
            "page_size": int,
            "total_pages": int,
            "has_next": bool,
            "has_prev": bool
        }
    """
    from sqlalchemy import func

    # Build base query
    q = _build_transaction_query(
        db, from_time, to_time, _tags, tag_op, _desc, min_value, max_value
    )

    # Get total count (without pagination)
    total = q.count()

    # Apply sorting
    sort_column = getattr(Transaction, sort_by, Transaction.htime)
    if sort_order == "asc":
        q = q.order_by(sort_column.asc())
    else:
        q = q.order_by(sort_column.desc())

    # Apply pagination
    skip = (page - 1) * page_size
    q = q.offset(skip).limit(page_size)

    transactions = q.all()
    data = [read_from_trans(t) for t in transactions] if transactions else []

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def read_transaction_impl(db, transaction_id: int):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    return read_from_trans(transaction)


def label_transaction_impl(db, transaction_id: int, label: str, positive: bool = True):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    tags = transaction.tags
    if tags is None:
        tags = ""
    tags = tags.split(",")
    if positive:
        if label not in tags:
            tags.append(label)
    else:
        if label in tags:
            tags.remove(label)
    transaction.tags = ",".join(tags)

    db.commit()
    db.refresh(transaction)
    return


def _applied_side_value(state: TransactionState, side: str, transaction: Transaction):
    """返回交易某一侧（from/to）已实际计入账户余额的金额。

    与 update_account_balance_impl 的状态机语义保持一致：
    - updated 位置位     -> 余额持有当前 value
    - changed 位置位     -> 余额仍持有 prev_value（差额尚未入账）
    - 两者皆未置位       -> 尚未入账，返回 None
    """
    if side == "from":
        updated = state.is_from_acc_updated()
        changed = state.is_from_acc_changed()
    else:
        updated = state.is_to_acc_updated()
        changed = state.is_to_acc_changed()
    if updated:
        return transaction.value
    if changed:
        return transaction.prev_value
    return None


def _reverse_transaction_balance_effect(db, transaction: Transaction) -> None:
    """删除交易前，回退其已实际计入相关账户余额的金额。"""
    state = TransactionState(transaction.state)
    to_acc_id = _acc_inv(transaction.to_acc_id)
    from_acc_id = _acc_inv(transaction.from_acc_id)

    # to 侧为入账（余额增加），回退时减去
    if to_acc_id != -1:
        applied = _applied_side_value(state, "to", transaction)
        if applied is not None:
            account = db.query(Account).filter(Account.id == to_acc_id).first()
            if account is not None:
                balance = Money(account.balance) - Money(applied)
                account.balance = balance.value_str
                account.mtime = datetime.now()

    # from 侧为出账（余额减少），回退时加回
    if from_acc_id != -1:
        applied = _applied_side_value(state, "from", transaction)
        if applied is not None:
            account = db.query(Account).filter(Account.id == from_acc_id).first()
            if account is not None:
                balance = Money(account.balance) + Money(applied)
                account.balance = balance.value_str
                account.mtime = datetime.now()


def delete_transaction_impl(db, transaction_id: int = None):
    if transaction_id is None:
        return None
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction is None:
        return None

    # 先回退已入账的余额影响，再真正删除记录。
    # 历史上这里只做软删除标记（deprecated 位），记录会一直留在表里，
    # 所有列表查询（仅过滤 state != 0）依旧返回它，导致"删除后刷新又出现"。
    deleted = read_from_trans(transaction)
    _reverse_transaction_balance_effect(db, transaction)
    db.delete(transaction)
    db.commit()
    return deleted


def clear_invalid_trnasaction_impl(db):
    # invalid and not deprecated
    db.query(Transaction).filter(Transaction.state == 0).delete()
    db.commit()


def update_transaction_impl(
    db, transaction_id: int, transaction_update: TransactionData
):
    logger.info("Get Transaction Update: %s", transaction_update)
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction is None:
        return None

    # update state to changed
    state = TransactionState(transaction.state)

    # update state valid
    from sail_server.model.finance.account import update_account_balance_impl

    if state.is_from_acc_valid():
        if not state.is_from_acc_updated():
            # IF NOT UPDATE, update manually
            update_account_balance_impl(db, _acc_inv(transaction.from_acc_id))
        else:
            # IF UPDATED, unset for later update
            state.unset_from_acc_updated()
        state.set_from_acc_changed()

    if state.is_to_acc_valid():
        if not state.is_to_acc_updated():
            # IF NOT UPDATE, update manually
            update_account_balance_impl(db, _acc_inv(transaction.to_acc_id))
        else:
            # IF UPDATED, unset for later update
            state.unset_to_acc_updated()
        state.set_to_acc_changed()

    # if -1 means third party, write NULL
    transaction.from_acc_id = _acc(transaction_update.from_acc_id)
    transaction.to_acc_id = _acc(transaction_update.to_acc_id)
    transaction.budget_id = (
        transaction_update.budget_id
        if transaction_update.budget_id is not None
        else None
    )
    transaction.prev_value = transaction.value
    transaction.value = transaction_update.value
    transaction.description = transaction_update.description
    transaction.tags = transaction_update.tags
    transaction.state = state.value
    transaction.htime = _htime(transaction_update.htime)
    transaction.mtime = datetime.now()
    db.commit()
    db.refresh(transaction)

    return read_from_trans(transaction)


# ============================================================================
# Agent-Friendly Tag Operations
# ============================================================================


def read_untagged_transactions_impl(
    db,
    page: int = 1,
    page_size: int = 50,
    from_time: float = None,
    to_time: float = None,
):
    """
    获取未打标签的交易列表（tags 为空或 null）。

    Agent 用此接口发现需要打标签的交易。

    Returns:
        Dict with pagination metadata and untagged transactions.
    """
    from sqlalchemy import or_

    q = db.query(Transaction).filter(Transaction.state != 0, _not_deprecated())

    # 筛选未打标签: tags 为 NULL、空字符串、或只包含逗号
    q = q.filter(
        or_(
            Transaction.tags.is_(None),
            Transaction.tags == "",
            Transaction.tags == ",",
        )
    )

    if from_time is not None:
        q = q.filter(Transaction.htime >= _htime(from_time))
    if to_time is not None:
        q = q.filter(Transaction.htime <= _htime(to_time))

    total = q.count()
    q = q.order_by(Transaction.htime.desc())

    skip = (page - 1) * page_size
    q = q.offset(skip).limit(page_size)

    transactions = q.all()
    data = [read_from_trans(t) for t in transactions] if transactions else []

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def get_tag_patterns_impl(
    db,
    limit: int = 200,
    from_time: float = None,
    to_time: float = None,
    min_occurrences: int = 1,
):
    """
    从已打标签的交易中提取 description → tags 的模式映射。

    Agent 用此接口学习已有的标签模式，作为 few-shot 参考。

    Returns:
        Dict containing:
        - patterns: list of {description, tags, count, example_ids}
        - total_tagged: 已标签交易总数
        - total_untagged: 未标签交易总数
        - tag_vocabulary: 所有出现过的 tag 列表
    """
    from sqlalchemy import or_, func as sa_func
    from collections import defaultdict

    # Base query: valid transactions with non-empty tags
    q = db.query(Transaction).filter(Transaction.state != 0, _not_deprecated())
    q = q.filter(
        Transaction.tags.isnot(None),
        Transaction.tags != "",
        Transaction.tags != ",",
    )

    if from_time is not None:
        q = q.filter(Transaction.htime >= _htime(from_time))
    if to_time is not None:
        q = q.filter(Transaction.htime <= _htime(to_time))

    tagged_transactions = q.all()

    # Aggregate patterns: group by (description, tags)
    pattern_map = defaultdict(lambda: {"count": 0, "example_ids": []})
    tag_vocabulary = set()

    for t in tagged_transactions:
        desc = (t.description or "").strip()
        tags = (t.tags or "").strip()
        if not desc or not tags:
            continue

        key = (desc, tags)
        pattern_map[key]["count"] += 1
        if len(pattern_map[key]["example_ids"]) < 3:
            pattern_map[key]["example_ids"].append(t.id)

        # Collect tag vocabulary
        for tag in tags.split(","):
            tag = tag.strip()
            if tag:
                tag_vocabulary.add(tag)

    # Convert to list and filter by min_occurrences
    patterns = []
    for (desc, tags), info in pattern_map.items():
        if info["count"] >= min_occurrences:
            patterns.append(
                {
                    "description": desc,
                    "tags": tags,
                    "count": info["count"],
                    "example_ids": info["example_ids"],
                }
            )

    # Sort by count descending, take top N
    patterns.sort(key=lambda x: x["count"], reverse=True)
    patterns = patterns[:limit]

    # Count untagged
    untagged_q = db.query(Transaction).filter(Transaction.state != 0, _not_deprecated())
    untagged_q = untagged_q.filter(
        or_(
            Transaction.tags.is_(None),
            Transaction.tags == "",
            Transaction.tags == ",",
        )
    )
    total_untagged = untagged_q.count()

    return {
        "patterns": patterns,
        "total_tagged": len(tagged_transactions),
        "total_untagged": total_untagged,
        "tag_vocabulary": sorted(tag_vocabulary),
        "pattern_count": len(patterns),
    }


def batch_tag_transactions_impl(
    db,
    updates: list[dict],
):
    """
    批量为交易设置标签。

    Args:
        db: 数据库会话
        updates: list of {"id": int, "tags": str}
            每个 item 指定交易 ID 和要设置的标签字符串

    Returns:
        Dict containing:
        - success: list of updated transaction IDs
        - failed: list of {id, error}
        - total, success_count, failed_count
    """
    success = []
    failed = []

    for item in updates:
        tid = item.get("id")
        tags = item.get("tags", "")

        if tid is None:
            failed.append({"id": None, "error": "Missing transaction id"})
            continue

        try:
            transaction = db.query(Transaction).filter(Transaction.id == tid).first()
            if transaction is None:
                failed.append({"id": tid, "error": "Transaction not found"})
                continue

            transaction.tags = tags
            transaction.mtime = datetime.now()
            success.append(tid)
        except Exception as e:
            failed.append({"id": tid, "error": str(e)})

    if success:
        db.commit()

    return {
        "success": success,
        "failed": failed,
        "total": len(updates),
        "success_count": len(success),
        "failed_count": len(failed),
    }


def _parse_money_decimal(raw_val: Any) -> Decimal:
    """将交易金额字符串解析为 Decimal（与 Money.__init__ 语义完全一致）。"""
    if isinstance(raw_val, Decimal):
        return raw_val
    if isinstance(raw_val, str):
        s = raw_val.strip()
        if " " in s:
            parts = s.split()
            if len(parts) == 2 and parts[1] in Money._supported_currency:
                s = parts[0]
        return Decimal(s)
    return Decimal(str(raw_val))


def _is_safe_like_literal(s: str) -> bool:
    return ("%" not in s) and ("_" not in s)


def get_transaction_stats_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    from_time: float = None,
    to_time: float = None,
    _tags: str = [],
    tag_op: str = "and",
    _desc: str = None,
    min_value: float = None,
    max_value: float = None,
    return_list: bool = False,
):
    """
    Get transaction statistics with filtering options.
    """
    q = _build_transaction_query(
        db=db,
        from_time=from_time,
        to_time=to_time,
        _tags=_tags,
        tag_op=tag_op,
        _desc=_desc,
        min_value=min_value,
        max_value=max_value,
    )

    # 仅需统计时使用轻量列投影 + Decimal 聚合，避免加载整行 ORM 实例与反复构造 Money 对象
    rows = q.with_entities(
        Transaction.from_acc_id,
        Transaction.to_acc_id,
        Transaction.value,
    ).all()

    income_total = Decimal("0.0")
    expense_total = Decimal("0.0")
    income_count = 0
    expense_count = 0

    for raw_from, raw_to, raw_val in rows:
        from_acc_id = _acc_inv(raw_from)
        to_acc_id = _acc_inv(raw_to)
        if from_acc_id == -1 and to_acc_id > 0:
            income_total += _parse_money_decimal(raw_val)
            income_count += 1
        elif from_acc_id > 0 and to_acc_id == -1:
            expense_total += _parse_money_decimal(raw_val)
            expense_count += 1

    net_total = income_total - expense_total
    stats = {
        "total_count": len(rows),
        "income_count": income_count,
        "expense_count": expense_count,
        "income_total": f"{income_total} CNY",
        "expense_total": f"{expense_total} CNY",
        "net_total": f"{net_total} CNY",
    }

    # Add data field if return_list is True
    if return_list:
        data_q = q.order_by(Transaction.htime.desc())
        if skip >= 0:
            data_q = data_q.offset(skip)
        if limit > 0:
            data_q = data_q.limit(limit)

        transactions = data_q.all()
        if transactions is None:
            stats["data"] = []
        else:
            stats["data"] = [
                read_from_trans(transaction) for transaction in transactions
            ]

    return stats


def get_transaction_stats_batch_impl(db, queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """批量计算交易统计：合并单次轻量 SQL 查询 + htime 二分切片聚合，消除 N 次全表扫描。"""
    if not queries:
        return []

    bind = db.get_bind()
    is_sqlite = bool(bind is not None and bind.dialect.name == "sqlite")

    def _norm_text(s: str) -> str:
        return s.lower() if is_sqlite else s

    def _can_fast_path(q: dict[str, Any]) -> bool:
        if q.get("return_list", False):
            return False
        if q.get("min_value") is not None or q.get("max_value") is not None:
            return False
        tags_str = q.get("tags", "")
        if tags_str and not _is_safe_like_literal(str(tags_str)):
            return False
        desc = q.get("description")
        if desc is not None and not _is_safe_like_literal(str(desc)):
            return False
        return True

    fast_indices: list[int] = [i for i, q in enumerate(queries) if _can_fast_path(q)]

    # 预先构建全局时间边界（仅当所有 fast-path 查询均给出对应边界时下推 SQL 过滤）
    timed_rows: list[tuple[datetime, int, Decimal, str, str]] = []
    timed_keys: list[datetime] = []
    null_time_rows: list[tuple[int, Decimal, str, str]] = []

    if fast_indices:
        all_have_from = all(queries[i].get("from_time") is not None for i in fast_indices)
        all_have_to = all(queries[i].get("to_time") is not None for i in fast_indices)

        base_q = db.query(
            Transaction.from_acc_id,
            Transaction.to_acc_id,
            Transaction.value,
            Transaction.tags,
            Transaction.description,
            Transaction.htime,
        ).filter(Transaction.state != 0, _not_deprecated())

        if all_have_from:
            min_from = min(float(queries[i]["from_time"]) for i in fast_indices)
            base_q = base_q.filter(Transaction.htime >= _htime(min_from))
        if all_have_to:
            max_to = max(float(queries[i]["to_time"]) for i in fast_indices)
            base_q = base_q.filter(Transaction.htime <= _htime(max_to))

        raw_rows = base_q.all()
        for raw_from, raw_to, raw_val, raw_tags, raw_desc, htime_val in raw_rows:
            from_acc_id = _acc_inv(raw_from)
            to_acc_id = _acc_inv(raw_to)
            if from_acc_id == -1 and to_acc_id > 0:
                kind = 1  # income
                val = _parse_money_decimal(raw_val)
            elif from_acc_id > 0 and to_acc_id == -1:
                kind = -1  # expense
                val = _parse_money_decimal(raw_val)
            else:
                kind = 0  # transfer / other
                val = Decimal("0.0")

            tags_norm = _norm_text(raw_tags) if raw_tags is not None else ""
            desc_norm = _norm_text(raw_desc) if raw_desc is not None else ""
            if htime_val is None:
                null_time_rows.append((kind, val, tags_norm, desc_norm))
            else:
                timed_rows.append((htime_val, kind, val, tags_norm, desc_norm))

        timed_rows.sort(key=lambda r: r[0])
        timed_keys = [r[0] for r in timed_rows]

    fast_set = set(fast_indices)
    results: list[dict[str, Any]] = []

    for idx, query in enumerate(queries):
        query_id = query.get("id", "")
        try:
            tags_str = query.get("tags", "")
            tag_list = (
                [tag.strip() for tag in str(tags_str).split(",") if tag.strip()]
                if tags_str and str(tags_str).strip()
                else []
            )

            if idx not in fast_set:
                stats = get_transaction_stats_impl(
                    db=db,
                    skip=query.get("skip", 0),
                    limit=query.get("limit", -1),
                    from_time=query.get("from_time"),
                    to_time=query.get("to_time"),
                    _tags=tag_list,
                    tag_op=query.get("tag_op", "and"),
                    _desc=query.get("description"),
                    min_value=query.get("min_value"),
                    max_value=query.get("max_value"),
                    return_list=query.get("return_list", False),
                )
                results.append({"id": query_id, "stats": stats})
                continue

            from_ts = query.get("from_time")
            to_ts = query.get("to_time")
            lo = bisect_left(timed_keys, _htime(from_ts)) if from_ts is not None else 0
            hi = (
                bisect_right(timed_keys, _htime(to_ts))
                if to_ts is not None
                else len(timed_rows)
            )

            norm_tags = [_norm_text(t) for t in tag_list]
            use_or = query.get("tag_op", "and") == "or"
            desc = query.get("description")
            norm_desc = _norm_text(str(desc)) if desc is not None else None

            total_count = 0
            income_count = 0
            expense_count = 0
            income_total = Decimal("0.0")
            expense_total = Decimal("0.0")

            # 遍历命中时间区间的记录
            for i in range(lo, hi):
                _, kind, val, row_tags, row_desc = timed_rows[i]
                if norm_tags:
                    if not row_tags:
                        continue
                    if use_or:
                        if not any(t in row_tags for t in norm_tags):
                            continue
                    else:
                        if not all(t in row_tags for t in norm_tags):
                            continue
                if norm_desc is not None and norm_desc not in row_desc:
                    continue

                total_count += 1
                if kind == 1:
                    income_total += val
                    income_count += 1
                elif kind == -1:
                    expense_total += val
                    expense_count += 1

            # 仅在未指定时间范围时纳入 htime 为 NULL 的行（与 SQL 语义一致）
            if from_ts is None and to_ts is None and null_time_rows:
                for kind, val, row_tags, row_desc in null_time_rows:
                    if norm_tags:
                        if not row_tags:
                            continue
                        if use_or:
                            if not any(t in row_tags for t in norm_tags):
                                continue
                        else:
                            if not all(t in row_tags for t in norm_tags):
                                continue
                    if norm_desc is not None and norm_desc not in row_desc:
                        continue
                    total_count += 1
                    if kind == 1:
                        income_total += val
                        income_count += 1
                    elif kind == -1:
                        expense_total += val
                        expense_count += 1

            net_total = income_total - expense_total
            results.append(
                {
                    "id": query_id,
                    "stats": {
                        "total_count": total_count,
                        "income_count": income_count,
                        "expense_count": expense_count,
                        "income_total": f"{income_total} CNY",
                        "expense_total": f"{expense_total} CNY",
                        "net_total": f"{net_total} CNY",
                    },
                }
            )
        except Exception as e:
            logger.error(f"Error getting stats for query {query_id}: {e}")
            results.append({"id": query_id, "stats": None, "error": str(e)})

    return results
