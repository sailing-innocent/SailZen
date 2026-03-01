# -*- coding: utf-8 -*-
# @file finance.py
# @brief Finance DAO
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
财务模块 DAO

从 sail_server/model/finance/ 迁移数据访问逻辑
"""

from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.finance import Account, Transaction, Budget, BudgetItem
from sail_server.data.dao.base import BaseDAO


class AccountDAO(BaseDAO[Account]):
    """账户 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, Account)
    
    def get_by_name(self, name: str) -> Optional[Account]:
        """通过名称获取账户"""
        return self.db.query(Account).filter(Account.name == name).first()
    
    def get_active_accounts(self) -> List[Account]:
        """获取所有活跃账户"""
        return self.db.query(Account).filter(Account.state == 0).all()
    
    def get_archived_accounts(self) -> List[Account]:
        """获取所有归档账户"""
        return self.db.query(Account).filter(Account.state == 1).all()


class TransactionDAO(BaseDAO[Transaction]):
    """交易 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, Transaction)
    
    def get_by_account(self, account_id: int) -> List[Transaction]:
        """获取账户的所有交易"""
        return self.db.query(Transaction).filter(
            (Transaction.from_acc_id == account_id) | 
            (Transaction.to_acc_id == account_id)
        ).order_by(Transaction.htime.desc()).all()
    
    def get_by_budget(self, budget_id: int) -> List[Transaction]:
        """获取预算的所有交易"""
        return self.db.query(Transaction).filter(
            Transaction.budget_id == budget_id
        ).order_by(Transaction.htime.desc()).all()
    
    def get_income_by_account(self, account_id: int) -> List[Transaction]:
        """获取账户的收入交易"""
        return self.db.query(Transaction).filter(
            Transaction.to_acc_id == account_id
        ).order_by(Transaction.htime.desc()).all()
    
    def get_expense_by_account(self, account_id: int) -> List[Transaction]:
        """获取账户的支出交易"""
        return self.db.query(Transaction).filter(
            Transaction.from_acc_id == account_id
        ).order_by(Transaction.htime.desc()).all()


class BudgetDAO(BaseDAO[Budget]):
    """预算 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, Budget)
    
    def get_with_items(self, budget_id: int) -> Optional[Budget]:
        """获取预算及其子项"""
        budget = self.get_by_id(budget_id)
        if budget:
            # 触发加载子项
            _ = budget.items
        return budget
    
    def get_active_budgets(self) -> List[Budget]:
        """获取所有活跃预算"""
        return self.db.query(Budget).filter(Budget.status == 0).all()


class BudgetItemDAO(BaseDAO[BudgetItem]):
    """预算子项 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, BudgetItem)
    
    def get_by_budget(self, budget_id: int) -> List[BudgetItem]:
        """获取预算的所有子项"""
        return self.db.query(BudgetItem).filter(
            BudgetItem.budget_id == budget_id
        ).order_by(BudgetItem.id).all()
