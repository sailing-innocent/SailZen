# -*- coding: utf-8 -*-
# @file budget.py
# @brief Budget model implementation
# @author sailing-innocent
# @date 2026-01-12
# @version 1.0
# ---------------------------------

from sail_server.data.finance import (
    Budget,
    BudgetData,
    Transaction,
    TransactionData,
)
from sail_server.data.finance import _htime, _htime_inv
from sail_server.utils.money import Money
from datetime import datetime
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def budget_from_create(create: BudgetData):
    return Budget(
        name=create.name,
        amount=create.amount,
        description=create.description,
        tags=create.tags,
        htime=_htime(create.htime),
        ctime=datetime.now(),
        mtime=datetime.now(),
    )


def read_from_budget(budget: Budget):
    tags = ""
    if budget.tags is not None:
        tags = budget.tags
    return BudgetData(
        id=budget.id,
        name=budget.name,
        amount=budget.amount,
        description=budget.description,
        tags=tags,
        htime=_htime_inv(budget.htime),
        ctime=budget.ctime,
        mtime=budget.mtime,
    )


def create_budget_impl(db, budget_create: BudgetData):
    budget = budget_from_create(budget_create)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return read_from_budget(budget)


def read_budgets_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    from_time: float = None,
    to_time: float = None,
    _tags: List[str] = [],
    tag_op: str = "and",
):
    q = db.query(Budget)

    # Apply tag filtering
    if len(_tags) > 0:
        condition = None
        for tag in _tags:
            if tag is not None and tag.strip() != "":
                if condition is None:
                    condition = Budget.tags.like(f"%{tag}%")
                else:
                    if tag_op == "or":
                        condition = condition | Budget.tags.like(f"%{tag}%")
                    else:
                        condition = condition & Budget.tags.like(f"%{tag}%")
        if condition is not None:
            q = q.filter(condition)

    # Apply time filtering
    if from_time is not None:
        q = q.filter(Budget.htime >= _htime(from_time))
    if to_time is not None:
        q = q.filter(Budget.htime <= _htime(to_time))

    q = q.order_by(Budget.htime.desc())

    if skip >= 0:
        q = q.offset(skip)
    if limit > 0:
        q = q.limit(limit)

    budgets = q.all()
    if budgets is None:
        return []
    return [read_from_budget(budget) for budget in budgets]


def read_budget_impl(db, budget_id: int):
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        return None
    return read_from_budget(budget)


def update_budget_impl(db, budget_id: int, budget_update: BudgetData):
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        return None

    budget.name = budget_update.name
    budget.amount = budget_update.amount
    budget.description = budget_update.description
    budget.tags = budget_update.tags
    budget.htime = _htime(budget_update.htime)
    budget.mtime = datetime.now()

    db.commit()
    db.refresh(budget)
    return read_from_budget(budget)


def delete_budget_impl(db, budget_id: int):
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        return None

    db.delete(budget)
    db.commit()
    return {
        "id": budget_id,
        "status": "success",
        "message": f"Budget {budget_id} deleted successfully",
    }


def get_budget_used_amount_impl(
    db, budget: Budget, from_time: float = None, to_time: float = None
) -> Money:
    """
    Calculate the used amount for a budget.
    Priority: 1. Directly linked transactions (budget_id), 2. Transactions matched by tags.
    Only counts expense transactions (from_acc_id > 0, to_acc_id = -1).
    """
    used_amount = Money("0.0")

    # First, count directly linked transactions
    q_linked = db.query(Transaction).filter(
        Transaction.state != 0,
        Transaction.budget_id == budget.id
    )
    
    # Filter by time range for linked transactions
    if from_time is not None:
        q_linked = q_linked.filter(Transaction.htime >= _htime(from_time))
    if to_time is not None:
        q_linked = q_linked.filter(Transaction.htime <= _htime(to_time))
    
    linked_transactions = q_linked.all()
    
    # Calculate used amount from directly linked transactions
    for transaction in linked_transactions:
        from_acc_id = (
            transaction.from_acc_id if transaction.from_acc_id is not None else -1
        )
        to_acc_id = transaction.to_acc_id if transaction.to_acc_id is not None else -1

        # Only count expense transactions (from_acc_id > 0, to_acc_id = -1)
        if from_acc_id > 0 and to_acc_id == -1:
            used_amount += Money(transaction.value)

    # Then, count transactions matched by tags (excluding already linked ones)
    budget_tags = []
    if budget.tags:
        budget_tags = [tag.strip() for tag in budget.tags.split(",") if tag.strip()]

    if len(budget_tags) == 0:
        return used_amount

    # Build query for tag-matched transactions (excluding already linked)
    q = db.query(Transaction).filter(
        Transaction.state != 0,
        Transaction.budget_id.is_(None)  # Exclude already linked transactions
    )

    # Filter by tags (OR operation - transaction matches if it has any budget tag)
    if len(budget_tags) > 0:
        tag_condition = None
        for tag in budget_tags:
            if tag_condition is None:
                tag_condition = Transaction.tags.like(f"%{tag}%")
            else:
                tag_condition = tag_condition | Transaction.tags.like(f"%{tag}%")
        if tag_condition is not None:
            q = q.filter(tag_condition)

    # Filter by time range
    budget_htime = budget.htime
    if from_time is not None:
        q = q.filter(Transaction.htime >= _htime(from_time))
    else:
        q = q.filter(Transaction.htime >= budget_htime)

    if to_time is not None:
        q = q.filter(Transaction.htime <= _htime(to_time))

    # Get matching transactions
    transactions = q.all()

    # Calculate used amount (only expense transactions)
    for transaction in transactions:
        from_acc_id = (
            transaction.from_acc_id if transaction.from_acc_id is not None else -1
        )
        to_acc_id = transaction.to_acc_id if transaction.to_acc_id is not None else -1

        # Only count expense transactions (from_acc_id > 0, to_acc_id = -1)
        if from_acc_id > 0 and to_acc_id == -1:
            used_amount += Money(transaction.value)

    return used_amount


def get_budget_stats_impl(
    db,
    from_time: float = None,
    to_time: float = None,
    _tags: List[str] = [],
    tag_op: str = "and",
    return_list: bool = False,
) -> Dict:
    """
    Get budget statistics.
    """
    budgets = read_budgets_impl(
        db,
        skip=0,
        limit=-1,
        from_time=from_time,
        to_time=to_time,
        _tags=_tags,
        tag_op=tag_op,
    )

    total_budget_amount = Money("0.0")
    total_used_amount = Money("0.0")

    budget_details = []

    for budget_data in budgets:
        budget = db.query(Budget).filter(Budget.id == budget_data.id).first()
        if budget is None:
            continue

        budget_amount = Money(budget_data.amount)
        used_amount = get_budget_used_amount_impl(db, budget, from_time, to_time)
        remaining_amount = budget_amount - used_amount

        total_budget_amount += budget_amount
        total_used_amount += used_amount

        # Count transactions
        budget_tags = []
        if budget.tags:
            budget_tags = [tag.strip() for tag in budget.tags.split(",") if tag.strip()]

        # Count transactions: directly linked + tag-matched
        transaction_count = 0
        
        # Count directly linked transactions
        q_linked = db.query(Transaction).filter(
            Transaction.state != 0,
            Transaction.budget_id == budget.id
        )
        if from_time is not None:
            q_linked = q_linked.filter(Transaction.htime >= _htime(from_time))
        if to_time is not None:
            q_linked = q_linked.filter(Transaction.htime <= _htime(to_time))
        transaction_count += q_linked.count()
        
        # Count tag-matched transactions (excluding already linked)
        if len(budget_tags) > 0:
            q = db.query(Transaction).filter(
                Transaction.state != 0,
                Transaction.budget_id.is_(None)  # Exclude already linked
            )
            tag_condition = None
            for tag in budget_tags:
                if tag_condition is None:
                    tag_condition = Transaction.tags.like(f"%{tag}%")
                else:
                    tag_condition = tag_condition | Transaction.tags.like(f"%{tag}%")
            if tag_condition is not None:
                q = q.filter(tag_condition)

            budget_htime = budget.htime
            if from_time is not None:
                q = q.filter(Transaction.htime >= _htime(from_time))
            else:
                q = q.filter(Transaction.htime >= budget_htime)

            if to_time is not None:
                q = q.filter(Transaction.htime <= _htime(to_time))

            transaction_count += q.count()

        budget_details.append(
            {
                "budget": budget_data,
                "used_amount": str(used_amount),
                "remaining_amount": str(remaining_amount),
                "transaction_count": transaction_count,
            }
        )

    total_remaining_amount = total_budget_amount - total_used_amount

    result = {
        "total_budget_count": len(budgets),
        "total_budget_amount": str(total_budget_amount),
        "total_used_amount": str(total_used_amount),
        "total_remaining_amount": str(total_remaining_amount),
    }

    if return_list:
        result["budgets"] = budget_details

    return result


def get_budget_analysis_impl(db, budget_id: int) -> Dict:
    """
    Get detailed analysis for a specific budget.
    """
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        return None

    budget_data = read_from_budget(budget)
    budget_amount = Money(budget_data.amount)
    used_amount = get_budget_used_amount_impl(db, budget)
    remaining_amount = budget_amount - used_amount

    usage_percentage = 0.0
    if budget_amount.value > 0:
        usage_percentage = float((used_amount.value / budget_amount.value) * 100)

    # Get matching transactions
    budget_tags = []
    if budget.tags:
        budget_tags = [tag.strip() for tag in budget.tags.split(",") if tag.strip()]

    transactions = []
    by_tag: Dict[str, Dict] = {}

    # Get directly linked transactions
    q_linked = db.query(Transaction).filter(
        Transaction.state != 0,
        Transaction.budget_id == budget.id
    )
    q_linked = q_linked.order_by(Transaction.htime.desc())
    linked_transactions = q_linked.all()

    # Get tag-matched transactions (excluding already linked)
    if len(budget_tags) > 0:
        q = db.query(Transaction).filter(
            Transaction.state != 0,
            Transaction.budget_id.is_(None)  # Exclude already linked
        )
        tag_condition = None
        for tag in budget_tags:
            if tag_condition is None:
                tag_condition = Transaction.tags.like(f"%{tag}%")
            else:
                tag_condition = tag_condition | Transaction.tags.like(f"%{tag}%")
        if tag_condition is not None:
            q = q.filter(tag_condition)

        q = q.filter(Transaction.htime >= budget.htime)
        q = q.order_by(Transaction.htime.desc())

        tag_matched_transactions = q.all()
    else:
        tag_matched_transactions = []

    # Combine both lists
    matching_transactions = list(linked_transactions) + list(tag_matched_transactions)

    from sail_server.model.finance.transaction import read_from_trans

    for transaction in matching_transactions:
        from_acc_id = (
            transaction.from_acc_id if transaction.from_acc_id is not None else -1
        )
        to_acc_id = (
            transaction.to_acc_id if transaction.to_acc_id is not None else -1
        )

        # Only include expense transactions
        if from_acc_id > 0 and to_acc_id == -1:
            trans_data = read_from_trans(transaction)
            transactions.append(trans_data)

            # Group by tag
            trans_tags = []
            if trans_data.tags:
                trans_tags = [
                    tag.strip() for tag in trans_data.tags.split(",") if tag.strip()
                ]

            for tag in trans_tags:
                if tag not in by_tag:
                    by_tag[tag] = {"amount": Money("0.0"), "count": 0}
                by_tag[tag]["amount"] += Money(trans_data.value)
                by_tag[tag]["count"] += 1

    # Convert Money to string in by_tag
    for tag in by_tag:
        by_tag[tag]["amount"] = str(by_tag[tag]["amount"])

    return {
        "budget": budget_data,
        "used_amount": str(used_amount),
        "remaining_amount": str(remaining_amount),
        "usage_percentage": usage_percentage,
        "transactions": transactions,
        "by_tag": by_tag,
    }


def consume_budget_impl(
    db, budget_id: int, transaction_create: TransactionData
) -> TransactionData:
    """
    Consume budget by creating a transaction.
    Validates that the consume amount doesn't exceed remaining budget.
    """
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        raise ValueError(f"Budget {budget_id} not found")

    budget_amount = Money(budget.amount)
    used_amount = get_budget_used_amount_impl(db, budget)
    remaining_amount = budget_amount - used_amount
    consume_amount = Money(transaction_create.value)

    if consume_amount > remaining_amount:
        raise ValueError(
            f"Consume amount {consume_amount} exceeds remaining budget {remaining_amount}"
        )

    # Create transaction with budget tags
    budget_tags = budget.tags if budget.tags else ""
    transaction_tags = transaction_create.tags if transaction_create.tags else ""

    # Merge tags (avoid duplicates)
    all_tags = set()
    if budget_tags:
        all_tags.update([tag.strip() for tag in budget_tags.split(",") if tag.strip()])
    if transaction_tags:
        all_tags.update(
            [tag.strip() for tag in transaction_tags.split(",") if tag.strip()]
        )

    merged_tags = ",".join(sorted(all_tags))

    # Add budget info to description
    budget_desc = f"[预算: {budget.name}]"
    if transaction_create.description:
        transaction_desc = f"{budget_desc} {transaction_create.description}"
    else:
        transaction_desc = budget_desc

    # Use budget htime if not specified
    transaction_htime = transaction_create.htime
    if transaction_htime is None or transaction_htime <= 0:
        transaction_htime = _htime_inv(budget.htime)

    # Create transaction
    from sail_server.model.finance.transaction import create_transaction_impl

    transaction_data = TransactionData(
        from_acc_id=transaction_create.from_acc_id,
        to_acc_id=transaction_create.to_acc_id,
        value=transaction_create.value,
        description=transaction_desc,
        tags=merged_tags,
        htime=transaction_htime,
    )

    transaction = create_transaction_impl(db, transaction_data)

    # Update budget mtime
    budget.mtime = datetime.now()
    db.commit()

    return transaction


def link_transaction_to_budget_impl(
    db, budget_id: int, transaction_id: int
) -> TransactionData:
    """
    Link an existing transaction to a budget.
    """
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        raise ValueError(f"Budget {budget_id} not found")

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction is None:
        raise ValueError(f"Transaction {transaction_id} not found")

    # Check if transaction is already linked to another budget
    if transaction.budget_id is not None and transaction.budget_id != budget_id:
        raise ValueError(
            f"Transaction {transaction_id} is already linked to budget {transaction.budget_id}"
        )

    # Validate transaction is an expense transaction
    from_acc_id = transaction.from_acc_id if transaction.from_acc_id is not None else -1
    to_acc_id = transaction.to_acc_id if transaction.to_acc_id is not None else -1
    if not (from_acc_id > 0 and to_acc_id == -1):
        raise ValueError("Only expense transactions can be linked to budgets")

    # Check if linking this transaction would exceed budget
    budget_amount = Money(budget.amount)
    used_amount = get_budget_used_amount_impl(db, budget)
    
    # If transaction is not already linked, add its value to used amount
    if transaction.budget_id is None:
        transaction_value = Money(transaction.value)
        if used_amount + transaction_value > budget_amount:
            raise ValueError(
                f"Linking transaction {transaction_id} would exceed budget. "
                f"Remaining: {budget_amount - used_amount}, Transaction: {transaction_value}"
            )

    # Link transaction to budget
    transaction.budget_id = budget_id
    transaction.mtime = datetime.now()
    
    # Update budget mtime
    budget.mtime = datetime.now()
    
    db.commit()
    db.refresh(transaction)

    from sail_server.model.finance.transaction import read_from_trans
    return read_from_trans(transaction)


def unlink_transaction_from_budget_impl(db, transaction_id: int) -> TransactionData:
    """
    Unlink a transaction from its budget.
    """
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction is None:
        raise ValueError(f"Transaction {transaction_id} not found")

    if transaction.budget_id is None:
        raise ValueError(f"Transaction {transaction_id} is not linked to any budget")

    budget_id = transaction.budget_id
    transaction.budget_id = None
    transaction.mtime = datetime.now()

    # Update budget mtime
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is not None:
        budget.mtime = datetime.now()

    db.commit()
    db.refresh(transaction)

    from sail_server.model.finance.transaction import read_from_trans
    return read_from_trans(transaction)
