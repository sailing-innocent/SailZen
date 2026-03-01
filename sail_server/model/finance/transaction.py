from sail_server.infrastructure.orm.finance import Account, Transaction
from sail_server.data.finance import AccountState, TransactionState
from sail_server.application.dto.finance import TransactionData
from sail_server.utils.finance_helpers import _acc, _acc_inv, _htime, _htime_inv

from sail_server.utils.money import Money
from datetime import datetime

import time
import logging

logger = logging.getLogger(__name__)


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
    return Transaction(
        from_acc_id=from_acc_id,
        to_acc_id=to_acc_id,
        budget_id=budget_id,
        prev_value="0.0",  # default
        value=create.value,
        description=create.description,
        tags=create.tags,
        state=init_state.value,
        htime=_htime(create.htime),
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
    q = db.query(Transaction).filter(Transaction.state != 0)
    
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
    q = _build_transaction_query(db, from_time, to_time, _tags, tag_op, _desc, min_value, max_value)
    
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


def delete_transaction_impl(db, transaction_id: int = None):
    if transaction_id is None:
        return None
    # db.query(Transaction).filter(Transaction.id == transaction_id).delete()
    # mark deprecate here
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    state = TransactionState(transaction.state)

    if state.is_from_acc_valid():
        state.unset_from_acc_valid()
    state.set_from_acc_deprecated()
    if state.is_to_acc_valid():
        state.unset_to_acc_valid()
    state.set_to_acc_deprecated()
    state.unset_from_acc_updated()
    state.unset_to_acc_updated()
    state.unset_from_acc_changed()
    state.unset_to_acc_changed()

    transaction.state = state.value
    db.commit()
    db.refresh(transaction)
    return read_from_trans(transaction)


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
    transaction.budget_id = transaction_update.budget_id if transaction_update.budget_id is not None else None
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
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        from_time: Start timestamp for filtering
        to_time: End timestamp for filtering
        _tags: List of tags to filter by
        tag_op: "and" or "or" operation for tag filtering
        _desc: Description filter (partial match)
        min_value: Minimum transaction value
        max_value: Maximum transaction value
        return_list: If True, include transaction data in response; if False, only return stats
    
    Returns:
        Dict with statistics and optional data field:
        {
            "total_count": int,
            "income_count": int,
            "expense_count": int,
            "income_total": str,
            "expense_total": str,
            "net_total": str,
            "data": List[TransactionData] (optional, only when return_list=True)
        }
    """
    q = db.query(Transaction).filter(Transaction.state != 0)
    
    # Apply tag filtering
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
    
    # Apply description filtering
    if _desc is not None:
        q = q.filter(Transaction.description.like(f"%{_desc}%"))
    
    # Apply time filtering
    if from_time is not None:
        q = q.filter(Transaction.htime >= _htime(from_time))
    if to_time is not None:
        q = q.filter(Transaction.htime <= _htime(to_time))
    
    # Apply value filtering
    if min_value is not None:
        q = q.filter(Transaction.value >= str(min_value))
    if max_value is not None:
        q = q.filter(Transaction.value <= str(max_value))
    
    q = q.order_by(Transaction.htime.desc())
    
    # Get all transactions for statistics calculation
    all_transactions = q.all()
    
    # Calculate statistics
    if all_transactions is None:
        stats = {
            "total_count": 0,
            "income_count": 0,
            "expense_count": 0,
            "income_total": "0.0",
            "expense_total": "0.0",
            "net_total": "0.0"
        }
    else:
        income_total = Money("0.0")
        expense_total = Money("0.0")
        income_count = 0
        expense_count = 0
        
        for transaction in all_transactions:
            from_acc_id = _acc_inv(transaction.from_acc_id)
            to_acc_id = _acc_inv(transaction.to_acc_id)
            value = Money(transaction.value)
            
            # Income: from_acc_id=-1, to_acc_id>0
            if from_acc_id == -1 and to_acc_id > 0:
                income_total += value
                income_count += 1
            # Expense: from_acc_id>0, to_acc_id=-1
            elif from_acc_id > 0 and to_acc_id == -1:
                expense_total += value
                expense_count += 1
        
        net_total = income_total - expense_total
        
        stats = {
            "total_count": len(all_transactions),
            "income_count": income_count,
            "expense_count": expense_count,
            "income_total": str(income_total),
            "expense_total": str(expense_total),
            "net_total": str(net_total)
        }
    
    # Add data field if return_list is True
    if return_list:
        # Apply pagination for data
        data_q = q
        if skip >= 0:
            data_q = data_q.offset(skip)
        if limit > 0:
            data_q = data_q.limit(limit)
        
        transactions = data_q.all()
        if transactions is None:
            stats["data"] = []
        else:
            stats["data"] = [read_from_trans(transaction) for transaction in transactions]
    
    return stats