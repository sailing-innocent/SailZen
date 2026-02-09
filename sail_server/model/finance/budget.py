# -*- coding: utf-8 -*-
# @file budget.py
# @brief Budget model implementation - Unified budget system
# @author sailing-innocent
# @date 2026-02-01
# @version 2.0
# ---------------------------------
"""
通用预算系统

设计理念：
1. Budget 是一个容器，包含多个 BudgetItem
2. 所有业务场景（租房、房贷、工资等）都使用相同的数据结构
3. 通过不同的 items 配置来实现不同的业务逻辑
4. 不再提供硬编码的业务模板函数，改为通用接口
"""

from sail_server.data.finance import (
    Budget,
    BudgetData,
    BudgetItem,
    BudgetItemData,
    BudgetDirection,
    ItemType,
    ItemStatus,
    Transaction,
    TransactionData,
)
from sail_server.data.finance import _htime, _htime_inv
from sail_server.utils.money import Money
from datetime import datetime
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


# ============ Conversion Functions ============

def budget_item_to_data(item: BudgetItem) -> BudgetItemData:
    """Convert BudgetItem ORM to BudgetItemData"""
    # Calculate total amount
    if item.item_type == ItemType.FIXED:
        total = item.amount or "0.0"
    else:
        total = (Money(item.amount or "0.0") * (item.period_count or 1)).value_str
    
    return BudgetItemData(
        id=item.id,
        budget_id=item.budget_id,
        name=item.name or "",
        description=item.description or "",
        direction=item.direction or 0,
        item_type=item.item_type or 0,
        amount=item.amount or "0.0",
        period_count=item.period_count or 1,
        is_refundable=item.is_refundable or 0,
        refund_amount=item.refund_amount or "0.0",
        current_period=item.current_period or 0,
        status=item.status or 0,
        due_date=_htime_inv(item.due_date) if item.due_date else None,
        ctime=item.ctime,
        mtime=item.mtime,
        total_amount=total,
        remaining_periods=max(0, (item.period_count or 1) - (item.current_period or 0)),
    )


def budget_item_from_data(data: BudgetItemData) -> BudgetItem:
    """Convert BudgetItemData to BudgetItem ORM"""
    return BudgetItem(
        budget_id=data.budget_id,
        name=data.name,
        description=data.description,
        direction=data.direction,
        item_type=data.item_type,
        amount=data.amount,
        period_count=data.period_count,
        is_refundable=data.is_refundable,
        refund_amount=data.refund_amount,
        current_period=data.current_period,
        status=data.status,
        due_date=_htime(data.due_date) if data.due_date else None,
        ctime=datetime.now(),
        mtime=datetime.now(),
    )


def budget_to_data(budget: Budget, include_items: bool = True) -> BudgetData:
    """Convert Budget ORM to BudgetData"""
    items = []
    if include_items and budget.items:
        items = [budget_item_to_data(item) for item in budget.items]
    
    return BudgetData(
        id=budget.id,
        name=budget.name or "",
        description=budget.description or "",
        tags=budget.tags or "",
        start_date=_htime_inv(budget.start_date) if budget.start_date else None,
        end_date=_htime_inv(budget.end_date) if budget.end_date else None,
        total_amount=budget.total_amount or "0.0",
        direction=budget.direction or 0,
        htime=_htime_inv(budget.htime) if budget.htime else datetime.now().timestamp(),
        ctime=budget.ctime,
        mtime=budget.mtime,
        items=items,
    )


def budget_from_data(data: BudgetData) -> Budget:
    """Convert BudgetData to Budget ORM"""
    return Budget(
        name=data.name,
        description=data.description,
        tags=data.tags,
        start_date=_htime(data.start_date) if data.start_date else None,
        end_date=_htime(data.end_date) if data.end_date else None,
        total_amount=data.total_amount,
        direction=data.direction if hasattr(data, 'direction') else 0,
        htime=_htime(data.htime) if data.htime else datetime.now(),
        ctime=datetime.now(),
        mtime=datetime.now(),
    )


def calculate_budget_total(items: List[BudgetItem]) -> Money:
    """
    Calculate total budget amount from items.
    Expense items are positive, income items are negative (for net calculation).
    Returns absolute sum for display purposes.
    """
    total = Money("0.0")
    for item in items:
        if item.item_type == ItemType.FIXED:
            item_total = Money(item.amount or "0.0")
        else:
            item_total = Money(item.amount or "0.0") * (item.period_count or 1)
        total += item_total
    return total


def calculate_budget_direction(items: List[BudgetItem]) -> int:
    """
    Calculate budget direction from items.
    Returns: 0 = EXPENSE (支出), 1 = INCOME (收入)
    Direction is determined by the majority of item amounts weighted by their totals.
    """
    expense_total = Money("0.0")
    income_total = Money("0.0")
    
    for item in items:
        if item.item_type == ItemType.FIXED:
            item_total = Money(item.amount or "0.0")
        else:
            item_total = Money(item.amount or "0.0") * (item.period_count or 1)
        
        if item.direction == BudgetDirection.INCOME:
            income_total += item_total
        else:
            expense_total += item_total
    
    # If income total is greater, it's an income budget
    return BudgetDirection.INCOME if income_total > expense_total else BudgetDirection.EXPENSE


# ============ Budget CRUD ============

def create_budget_impl(db, data: BudgetData) -> BudgetData:
    """
    Create a budget with items.
    
    This is the unified API for creating any type of budget.
    The caller provides the budget info and a list of items.
    """
    budget = budget_from_data(data)
    db.add(budget)
    db.flush()  # Get the budget ID
    
    # Create items if provided
    for item_data in data.items:
        item = budget_item_from_data(item_data)
        item.budget_id = budget.id
        db.add(item)
    
    db.flush()
    
    # Use provided total_amount if valid, otherwise recalculate from items
    if data.total_amount and data.total_amount != "0.0":
        budget.total_amount = data.total_amount
    else:
        budget.total_amount = calculate_budget_total(budget.items).value_str
    
    # Calculate direction from items
    budget.direction = calculate_budget_direction(budget.items)
    
    db.commit()
    db.refresh(budget)
    return budget_to_data(budget)


def read_budget_impl(db, budget_id: int, include_items: bool = True) -> Optional[BudgetData]:
    """Read a budget by ID"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        return None
    return budget_to_data(budget, include_items=include_items)


def read_budgets_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    from_time: float = None,
    to_time: float = None,
    _tags: List[str] = [],
    tag_op: str = "and",
    include_items: bool = False,
) -> List[BudgetData]:
    """Read budgets with optional filtering"""
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
    return [budget_to_data(budget, include_items=include_items) for budget in budgets]


def update_budget_impl(db, budget_id: int, data: BudgetData) -> Optional[BudgetData]:
    """Update a budget"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        return None

    budget.name = data.name
    budget.description = data.description
    budget.tags = data.tags
    budget.start_date = _htime(data.start_date) if data.start_date else None
    budget.end_date = _htime(data.end_date) if data.end_date else None
    budget.htime = _htime(data.htime) if data.htime else budget.htime
    budget.mtime = datetime.now()
    
    # Update total_amount if provided, otherwise recalculate from items
    if data.total_amount and data.total_amount != "0.0":
        budget.total_amount = data.total_amount
    else:
        budget.total_amount = calculate_budget_total(budget.items).value_str
    
    # Recalculate direction from items
    budget.direction = calculate_budget_direction(budget.items)

    db.commit()
    db.refresh(budget)
    return budget_to_data(budget)


def delete_budget_impl(db, budget_id: int) -> Optional[dict]:
    """Delete a budget and all its items"""
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


# ============ Budget Item CRUD ============

def create_item_impl(db, budget_id: int, data: BudgetItemData) -> BudgetItemData:
    """Create a budget item"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        raise ValueError(f"Budget {budget_id} not found")
    
    item = budget_item_from_data(data)
    item.budget_id = budget_id
    db.add(item)
    db.flush()
    
    # Update budget total
    budget.total_amount = calculate_budget_total(budget.items).value_str
    budget.mtime = datetime.now()
    
    db.commit()
    db.refresh(item)
    return budget_item_to_data(item)


def read_items_impl(db, budget_id: int) -> List[BudgetItemData]:
    """Read all items for a budget"""
    items = db.query(BudgetItem).filter(BudgetItem.budget_id == budget_id).order_by(BudgetItem.id).all()
    return [budget_item_to_data(item) for item in items]


def read_item_impl(db, item_id: int) -> Optional[BudgetItemData]:
    """Read a specific item"""
    item = db.query(BudgetItem).filter(BudgetItem.id == item_id).first()
    if item is None:
        return None
    return budget_item_to_data(item)


def update_item_impl(db, item_id: int, data: BudgetItemData) -> Optional[BudgetItemData]:
    """Update a budget item"""
    item = db.query(BudgetItem).filter(BudgetItem.id == item_id).first()
    if item is None:
        return None
    
    item.name = data.name
    item.description = data.description
    item.direction = data.direction
    item.item_type = data.item_type
    item.amount = data.amount
    item.period_count = data.period_count
    item.is_refundable = data.is_refundable
    item.refund_amount = data.refund_amount
    item.current_period = data.current_period
    item.status = data.status
    item.due_date = _htime(data.due_date) if data.due_date else None
    item.mtime = datetime.now()
    
    # Update budget total
    budget = item.budget
    if budget:
        budget.total_amount = calculate_budget_total(budget.items).value_str
        budget.mtime = datetime.now()
    
    db.commit()
    db.refresh(item)
    return budget_item_to_data(item)


def delete_item_impl(db, item_id: int) -> Optional[dict]:
    """Delete a budget item"""
    item = db.query(BudgetItem).filter(BudgetItem.id == item_id).first()
    if item is None:
        return None
    
    budget = item.budget
    db.delete(item)
    
    # Update budget total
    if budget:
        db.flush()
        budget.total_amount = calculate_budget_total(budget.items).value_str
        budget.mtime = datetime.now()
    
    db.commit()
    return {"id": item_id, "status": "success", "message": "Item deleted"}


# ============ Item Operations ============

def advance_period_impl(db, item_id: int) -> BudgetItemData:
    """Advance a periodic item to the next period"""
    item = db.query(BudgetItem).filter(BudgetItem.id == item_id).first()
    if item is None:
        raise ValueError(f"Item {item_id} not found")
    
    if item.current_period >= item.period_count:
        raise ValueError(f"Item {item_id} has completed all periods")
    
    item.current_period += 1
    if item.current_period >= item.period_count:
        item.status = ItemStatus.COMPLETED
    else:
        item.status = ItemStatus.IN_PROGRESS
    item.mtime = datetime.now()
    
    db.commit()
    db.refresh(item)
    return budget_item_to_data(item)


def record_refund_impl(db, item_id: int, refund_amount: str) -> BudgetItemData:
    """Record a refund for a refundable item"""
    item = db.query(BudgetItem).filter(BudgetItem.id == item_id).first()
    if item is None:
        raise ValueError(f"Item {item_id} not found")
    
    if not item.is_refundable:
        raise ValueError(f"Item {item_id} is not refundable")
    
    current_refund = Money(item.refund_amount or "0.0")
    new_refund = current_refund + Money(refund_amount)
    
    # Calculate item total
    if item.item_type == ItemType.FIXED:
        item_total = Money(item.amount or "0.0")
    else:
        item_total = Money(item.amount or "0.0") * item.period_count
    
    if new_refund > item_total:
        raise ValueError(f"Refund exceeds item total. Max: {item_total - current_refund}")
    
    item.refund_amount = str(new_refund)
    if new_refund >= item_total:
        item.status = ItemStatus.REFUNDED
    item.mtime = datetime.now()
    
    db.commit()
    db.refresh(item)
    return budget_item_to_data(item)


# ============ Budget Statistics ============

def get_budget_used_amount_impl(
    db, budget: Budget, from_time: float = None, to_time: float = None
) -> Dict[str, Money]:
    """
    Calculate used amounts for a budget.
    Returns dict with 'expense' and 'income' amounts from linked transactions.
    """
    expense_amount = Money("0.0")
    income_amount = Money("0.0")

    # Query transactions linked to this budget
    q = db.query(Transaction).filter(
        Transaction.state != 0,
        Transaction.budget_id == budget.id
    )
    
    if from_time is not None:
        q = q.filter(Transaction.htime >= _htime(from_time))
    if to_time is not None:
        q = q.filter(Transaction.htime <= _htime(to_time))
    
    transactions = q.all()
    
    for trans in transactions:
        from_acc_id = trans.from_acc_id if trans.from_acc_id is not None else -1
        to_acc_id = trans.to_acc_id if trans.to_acc_id is not None else -1
        
        # Expense: from account to external
        if from_acc_id > 0 and to_acc_id == -1:
            expense_amount += Money(trans.value)
        # Income: from external to account
        elif from_acc_id == -1 and to_acc_id > 0:
            income_amount += Money(trans.value)
    
    return {"expense": expense_amount, "income": income_amount}


def get_budget_stats_impl(
    db,
    from_time: float = None,
    to_time: float = None,
    _tags: List[str] = [],
    tag_op: str = "and",
    return_list: bool = False,
) -> Dict:
    """Get budget statistics"""
    budgets = read_budgets_impl(
        db,
        skip=0,
        limit=-1,
        from_time=from_time,
        to_time=to_time,
        _tags=_tags,
        tag_op=tag_op,
        include_items=True,
    )

    total_budget_amount = Money("0.0")
    total_used_amount = Money("0.0")

    budget_details = []

    for budget_data in budgets:
        budget = db.query(Budget).filter(Budget.id == budget_data.id).first()
        if budget is None:
            continue

        budget_amount = Money(budget_data.total_amount)
        used = get_budget_used_amount_impl(db, budget, from_time, to_time)
        
        # Calculate used amount (expense - income for net spending)
        used_amount = used["expense"]
        remaining_amount = budget_amount - used_amount

        total_budget_amount += budget_amount
        total_used_amount += used_amount

        # Count transactions
        q = db.query(Transaction).filter(
            Transaction.state != 0,
            Transaction.budget_id == budget.id
        )
        if from_time is not None:
            q = q.filter(Transaction.htime >= _htime(from_time))
        if to_time is not None:
            q = q.filter(Transaction.htime <= _htime(to_time))
        transaction_count = q.count()

        budget_details.append({
            "budget": budget_data,
            "used_amount": used_amount.value_str,
            "remaining_amount": remaining_amount.value_str,
            "transaction_count": transaction_count,
        })

    total_remaining = total_budget_amount - total_used_amount
    
    result = {
        "total_budget_count": len(budgets),
        "total_budget_amount": total_budget_amount.value_str,
        "total_used_amount": total_used_amount.value_str,
        "total_remaining_amount": total_remaining.value_str,
    }

    if return_list:
        result["budgets"] = budget_details

    return result


def get_budget_analysis_impl(db, budget_id: int) -> Optional[Dict]:
    """Get detailed analysis for a budget"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        return None

    budget_data = budget_to_data(budget, include_items=True)
    budget_amount = Money(budget_data.total_amount)
    used = get_budget_used_amount_impl(db, budget)
    
    # Calculate used amount (expense for spending tracking)
    used_amount = used["expense"]
    remaining_amount = budget_amount - used_amount
    
    usage_percentage = 0.0
    if budget_amount.value > 0:
        usage_percentage = float((used_amount.value / budget_amount.value) * 100)

    # Get transactions
    from sail_server.model.finance.transaction import read_from_trans
    
    q = db.query(Transaction).filter(
        Transaction.state != 0,
        Transaction.budget_id == budget.id
    ).order_by(Transaction.htime.desc())
    
    transactions = [read_from_trans(t) for t in q.all()]

    # Group by tag
    by_tag: Dict[str, Dict] = {}
    for trans in transactions:
        if trans.tags:
            for tag in trans.tags.split(","):
                tag = tag.strip()
                if tag:
                    if tag not in by_tag:
                        by_tag[tag] = {"amount": Money("0.0"), "count": 0}
                    
                    by_tag[tag]["amount"] += Money(trans.value)
                    by_tag[tag]["count"] += 1

    # Convert Money to string
    for tag in by_tag:
        by_tag[tag]["amount"] = by_tag[tag]["amount"].value_str

    return {
        "budget": budget_data,
        "used_amount": used_amount.value_str,
        "remaining_amount": remaining_amount.value_str,
        "usage_percentage": usage_percentage,
        "transactions": transactions,
        "by_tag": by_tag,
    }


# ============ Transaction Linking ============

def consume_budget_impl(
    db, budget_id: int, transaction_create: TransactionData
) -> TransactionData:
    """Create a transaction from budget (consume)"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        raise ValueError(f"Budget {budget_id} not found")

    # Create transaction with budget tags
    budget_tags = budget.tags if budget.tags else ""
    transaction_tags = transaction_create.tags if transaction_create.tags else ""

    # Merge tags
    all_tags = set()
    if budget_tags:
        all_tags.update([t.strip() for t in budget_tags.split(",") if t.strip()])
    if transaction_tags:
        all_tags.update([t.strip() for t in transaction_tags.split(",") if t.strip()])

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
        budget_id=budget_id,  # Link to budget
        htime=transaction_htime,
    )

    transaction = create_transaction_impl(db, transaction_data)

    # Update budget mtime
    budget.mtime = datetime.now()
    db.commit()

    return transaction


def link_transaction_impl(db, budget_id: int, transaction_id: int) -> TransactionData:
    """Link an existing transaction to a budget"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        raise ValueError(f"Budget {budget_id} not found")

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction is None:
        raise ValueError(f"Transaction {transaction_id} not found")

    if transaction.budget_id is not None and transaction.budget_id != budget_id:
        raise ValueError(f"Transaction is already linked to budget {transaction.budget_id}")

    transaction.budget_id = budget_id
    transaction.mtime = datetime.now()
    budget.mtime = datetime.now()
    
    db.commit()
    db.refresh(transaction)

    from sail_server.model.finance.transaction import read_from_trans
    return read_from_trans(transaction)


def unlink_transaction_impl(db, transaction_id: int) -> TransactionData:
    """Unlink a transaction from its budget"""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction is None:
        raise ValueError(f"Transaction {transaction_id} not found")

    if transaction.budget_id is None:
        raise ValueError(f"Transaction is not linked to any budget")

    budget_id = transaction.budget_id
    transaction.budget_id = None
    transaction.mtime = datetime.now()

    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is not None:
        budget.mtime = datetime.now()

    db.commit()
    db.refresh(transaction)

    from sail_server.model.finance.transaction import read_from_trans
    return read_from_trans(transaction)


# ============ Legacy Compatibility ============
# Keep old function names for backward compatibility

def read_from_budget(budget: Budget, include_items: bool = False) -> BudgetData:
    """Legacy: Use budget_to_data instead"""
    return budget_to_data(budget, include_items)


def budget_from_create(data: BudgetData) -> Budget:
    """Legacy: Use budget_from_data instead"""
    return budget_from_data(data)


def read_from_budget_item(item: BudgetItem) -> BudgetItemData:
    """Legacy: Use budget_item_to_data instead"""
    return budget_item_to_data(item)


def budget_item_from_create(data: BudgetItemData) -> BudgetItem:
    """Legacy: Use budget_item_from_data instead"""
    return budget_item_from_data(data)


# Legacy function mappings
create_budget_item_impl = create_item_impl
read_budget_items_impl = read_items_impl
read_budget_item_impl = read_item_impl
update_budget_item_impl = update_item_impl
delete_budget_item_impl = delete_item_impl
advance_item_period_impl = advance_period_impl
record_item_refund_impl = record_refund_impl
link_transaction_to_budget_impl = link_transaction_impl
unlink_transaction_from_budget_impl = unlink_transaction_impl
get_budget_with_items_impl = read_budget_impl
