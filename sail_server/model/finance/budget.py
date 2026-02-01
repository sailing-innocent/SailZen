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
    BudgetItem,
    BudgetItemData,
    BudgetType,
    PeriodType,
    BudgetItemStatus,
    Transaction,
    TransactionData,
)
from sail_server.data.finance import _htime, _htime_inv
from sail_server.utils.money import Money
from datetime import datetime
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def budget_from_create(create: BudgetData):
    return Budget(
        name=create.name,
        amount=create.amount,
        description=create.description,
        tags=create.tags,
        budget_type=create.budget_type,
        period_type=create.period_type,
        start_date=_htime(create.start_date) if create.start_date else None,
        end_date=_htime(create.end_date) if create.end_date else None,
        category=create.category,
        htime=_htime(create.htime),
        ctime=datetime.now(),
        mtime=datetime.now(),
    )


def read_from_budget(budget: Budget, include_items: bool = False):
    tags = ""
    if budget.tags is not None:
        tags = budget.tags
    
    items = []
    if include_items and budget.items:
        items = [read_from_budget_item(item) for item in budget.items]
    
    return BudgetData(
        id=budget.id,
        name=budget.name,
        amount=budget.amount,
        description=budget.description or "",
        tags=tags,
        budget_type=budget.budget_type or 0,
        period_type=budget.period_type or 0,
        start_date=_htime_inv(budget.start_date) if budget.start_date else None,
        end_date=_htime_inv(budget.end_date) if budget.end_date else None,
        category=budget.category or "",
        htime=_htime_inv(budget.htime),
        ctime=budget.ctime,
        mtime=budget.mtime,
        items=items,
    )


def read_from_budget_item(item: BudgetItem) -> BudgetItemData:
    return BudgetItemData(
        id=item.id,
        budget_id=item.budget_id,
        name=item.name,
        amount=item.amount or "0.0",
        description=item.description or "",
        is_refundable=item.is_refundable or 0,
        refund_amount=item.refund_amount or "0.0",
        status=item.status or 0,
        period_count=item.period_count or 1,
        current_period=item.current_period or 0,
        due_date=_htime_inv(item.due_date) if item.due_date else None,
        ctime=item.ctime,
        mtime=item.mtime,
    )


def budget_item_from_create(create: BudgetItemData) -> BudgetItem:
    return BudgetItem(
        budget_id=create.budget_id,
        name=create.name,
        amount=create.amount,
        description=create.description,
        is_refundable=create.is_refundable,
        refund_amount=create.refund_amount,
        status=create.status,
        period_count=create.period_count,
        current_period=create.current_period,
        due_date=_htime(create.due_date) if create.due_date else None,
        ctime=datetime.now(),
        mtime=datetime.now(),
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
    budget.budget_type = budget_update.budget_type
    budget.period_type = budget_update.period_type
    budget.start_date = _htime(budget_update.start_date) if budget_update.start_date else None
    budget.end_date = _htime(budget_update.end_date) if budget_update.end_date else None
    budget.category = budget_update.category
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

    # Validate transaction type matches budget type
    from_acc_id = transaction.from_acc_id if transaction.from_acc_id is not None else -1
    to_acc_id = transaction.to_acc_id if transaction.to_acc_id is not None else -1
    
    budget_type = budget.budget_type or 0
    is_expense = from_acc_id > 0 and to_acc_id == -1  # 支出：从账户到外部
    is_income = from_acc_id == -1 and to_acc_id > 0   # 收入：从外部到账户
    
    if budget_type == 0 and not is_expense:  # 支出预算
        raise ValueError("Only expense transactions can be linked to expense budgets")
    if budget_type == 1 and not is_income:   # 收入预算
        raise ValueError("Only income transactions can be linked to income budgets")

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


# ============ Budget Item CRUD ============

def create_budget_item_impl(db, item_create: BudgetItemData) -> BudgetItemData:
    """Create a new budget item"""
    item = budget_item_from_create(item_create)
    db.add(item)
    db.commit()
    db.refresh(item)
    return read_from_budget_item(item)


def read_budget_items_impl(db, budget_id: int) -> List[BudgetItemData]:
    """Read all items for a budget"""
    items = db.query(BudgetItem).filter(BudgetItem.budget_id == budget_id).all()
    return [read_from_budget_item(item) for item in items]


def read_budget_item_impl(db, item_id: int) -> Optional[BudgetItemData]:
    """Read a specific budget item"""
    item = db.query(BudgetItem).filter(BudgetItem.id == item_id).first()
    if item is None:
        return None
    return read_from_budget_item(item)


def update_budget_item_impl(db, item_id: int, item_update: BudgetItemData) -> Optional[BudgetItemData]:
    """Update a budget item"""
    item = db.query(BudgetItem).filter(BudgetItem.id == item_id).first()
    if item is None:
        return None
    
    item.name = item_update.name
    item.amount = item_update.amount
    item.description = item_update.description
    item.is_refundable = item_update.is_refundable
    item.refund_amount = item_update.refund_amount
    item.status = item_update.status
    item.period_count = item_update.period_count
    item.current_period = item_update.current_period
    item.due_date = _htime(item_update.due_date) if item_update.due_date else None
    item.mtime = datetime.now()
    
    db.commit()
    db.refresh(item)
    return read_from_budget_item(item)


def delete_budget_item_impl(db, item_id: int) -> Optional[dict]:
    """Delete a budget item"""
    item = db.query(BudgetItem).filter(BudgetItem.id == item_id).first()
    if item is None:
        return None
    
    db.delete(item)
    db.commit()
    return {"id": item_id, "status": "success", "message": "Budget item deleted"}


def record_item_refund_impl(db, item_id: int, refund_amount: str) -> BudgetItemData:
    """Record a refund for a refundable budget item (e.g., deposit)"""
    item = db.query(BudgetItem).filter(BudgetItem.id == item_id).first()
    if item is None:
        raise ValueError(f"Budget item {item_id} not found")
    
    if not item.is_refundable:
        raise ValueError(f"Budget item {item_id} is not refundable")
    
    current_refund = Money(item.refund_amount or "0.0")
    new_refund = current_refund + Money(refund_amount)
    item_amount = Money(item.amount)
    
    if new_refund > item_amount:
        raise ValueError(f"Refund amount exceeds item amount. Max refundable: {item_amount - current_refund}")
    
    item.refund_amount = str(new_refund)
    if new_refund >= item_amount:
        item.status = BudgetItemStatus.REFUNDED
    item.mtime = datetime.now()
    
    db.commit()
    db.refresh(item)
    return read_from_budget_item(item)


def advance_item_period_impl(db, item_id: int) -> BudgetItemData:
    """Advance a periodic item to the next period (e.g., next month's rent)"""
    item = db.query(BudgetItem).filter(BudgetItem.id == item_id).first()
    if item is None:
        raise ValueError(f"Budget item {item_id} not found")
    
    if item.current_period >= item.period_count:
        raise ValueError(f"Budget item {item_id} has completed all periods")
    
    item.current_period += 1
    if item.current_period >= item.period_count:
        item.status = BudgetItemStatus.COMPLETED
    else:
        item.status = BudgetItemStatus.IN_PROGRESS
    item.mtime = datetime.now()
    
    db.commit()
    db.refresh(item)
    return read_from_budget_item(item)


# ============ Budget Templates ============

def create_rent_budget_impl(
    db,
    name: str,
    monthly_rent: str,
    deposit: str,
    start_date: float,
    end_date: float,
    description: str = "",
    tags: str = "",
) -> BudgetData:
    """Create a rent budget with monthly rent and deposit items"""
    # Calculate number of months
    start_dt = datetime.fromtimestamp(start_date)
    end_dt = datetime.fromtimestamp(end_date)
    months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month) + 1
    
    # Calculate total amount
    total_rent = Money(monthly_rent) * months
    total_deposit = Money(deposit)
    total_amount = total_rent + total_deposit
    
    # Create budget
    budget_data = BudgetData(
        name=name,
        amount=str(total_amount),
        description=description,
        tags=tags if tags else "rent,housing",
        budget_type=BudgetType.EXPENSE,
        period_type=PeriodType.MONTHLY,
        start_date=start_date,
        end_date=end_date,
        category="rent",
        htime=start_date,
    )
    
    budget = budget_from_create(budget_data)
    db.add(budget)
    db.flush()  # Get the budget ID
    
    # Create deposit item (refundable)
    deposit_item = BudgetItem(
        budget_id=budget.id,
        name="押金",
        amount=deposit,
        description="租房押金（合同结束可退还）",
        is_refundable=1,
        status=BudgetItemStatus.PENDING,
        period_count=1,
    )
    db.add(deposit_item)
    
    # Create monthly rent item
    rent_item = BudgetItem(
        budget_id=budget.id,
        name="月租金",
        amount=monthly_rent,
        description=f"每月租金，共{months}期",
        is_refundable=0,
        status=BudgetItemStatus.PENDING,
        period_count=months,
    )
    db.add(rent_item)
    
    db.commit()
    db.refresh(budget)
    return read_from_budget(budget, include_items=True)


def create_mortgage_budget_impl(
    db,
    name: str,
    down_payment: str,
    monthly_payment: str,
    monthly_interest: str,
    loan_months: int,
    start_date: float,
    description: str = "",
    tags: str = "",
) -> BudgetData:
    """Create a mortgage budget with down payment and monthly payments"""
    from dateutil.relativedelta import relativedelta
    
    # Calculate total amounts
    total_monthly = Money(monthly_payment) * loan_months
    total_interest = Money(monthly_interest) * loan_months
    total_amount = Money(down_payment) + total_monthly
    
    # Calculate end date
    start_dt = datetime.fromtimestamp(start_date)
    end_dt = start_dt + relativedelta(months=loan_months)
    
    # Create budget
    budget_data = BudgetData(
        name=name,
        amount=str(total_amount),
        description=description,
        tags=tags if tags else "mortgage,housing",
        budget_type=BudgetType.EXPENSE,
        period_type=PeriodType.MONTHLY,
        start_date=start_date,
        end_date=end_dt.timestamp(),
        category="mortgage",
        htime=start_date,
    )
    
    budget = budget_from_create(budget_data)
    db.add(budget)
    db.flush()
    
    # Create down payment item
    down_item = BudgetItem(
        budget_id=budget.id,
        name="首付款",
        amount=down_payment,
        description="购房首付款",
        is_refundable=0,
        status=BudgetItemStatus.PENDING,
        period_count=1,
    )
    db.add(down_item)
    
    # Create monthly payment item
    payment_item = BudgetItem(
        budget_id=budget.id,
        name="月供",
        amount=monthly_payment,
        description=f"每月还款，共{loan_months}期",
        is_refundable=0,
        status=BudgetItemStatus.PENDING,
        period_count=loan_months,
    )
    db.add(payment_item)
    
    # Create interest tracking item
    interest_item = BudgetItem(
        budget_id=budget.id,
        name="利息支出",
        amount=str(total_interest),
        description=f"贷款利息，月均{monthly_interest}",
        is_refundable=0,
        status=BudgetItemStatus.PENDING,
        period_count=loan_months,
    )
    db.add(interest_item)
    
    db.commit()
    db.refresh(budget)
    return read_from_budget(budget, include_items=True)


def create_salary_budget_impl(
    db,
    name: str,
    monthly_salary: str,
    year: int,
    annual_bonus: str = "0.0",
    description: str = "",
    tags: str = "",
) -> BudgetData:
    """Create a salary/income budget for a year"""
    # Calculate total expected income
    total_salary = Money(monthly_salary) * 12
    total_bonus = Money(annual_bonus)
    total_amount = total_salary + total_bonus
    
    # Set date range for the year
    start_dt = datetime(year, 1, 1)
    end_dt = datetime(year, 12, 31)
    
    # Create budget
    budget_data = BudgetData(
        name=name,
        amount=str(total_amount),
        description=description,
        tags=tags if tags else "salary,income",
        budget_type=BudgetType.INCOME,  # Income budget
        period_type=PeriodType.YEARLY,
        start_date=start_dt.timestamp(),
        end_date=end_dt.timestamp(),
        category="salary",
        htime=start_dt.timestamp(),
    )
    
    budget = budget_from_create(budget_data)
    db.add(budget)
    db.flush()
    
    # Create monthly salary item
    salary_item = BudgetItem(
        budget_id=budget.id,
        name="月薪",
        amount=monthly_salary,
        description=f"{year}年月薪，共12期",
        is_refundable=0,
        status=BudgetItemStatus.PENDING,
        period_count=12,
    )
    db.add(salary_item)
    
    # Create annual bonus item if applicable
    if Money(annual_bonus).value > 0:
        bonus_item = BudgetItem(
            budget_id=budget.id,
            name="年终奖",
            amount=annual_bonus,
            description=f"{year}年年终奖",
            is_refundable=0,
            status=BudgetItemStatus.PENDING,
            period_count=1,
        )
        db.add(bonus_item)
    
    db.commit()
    db.refresh(budget)
    return read_from_budget(budget, include_items=True)


def get_budget_with_items_impl(db, budget_id: int) -> Optional[BudgetData]:
    """Get budget with all its items"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        return None
    return read_from_budget(budget, include_items=True)
