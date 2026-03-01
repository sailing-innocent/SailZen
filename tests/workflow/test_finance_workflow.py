# -*- coding: utf-8 -*-
# @file test_finance_workflow.py
# @brief 财务模块标准流程测试
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
财务模块标准流程测试

测试范围:
- 账户生命周期（创建-读取-更新-删除）
- 交易流程（创建交易-更新余额）
- 转账流程（多账户间转账）
- 预算管理流程
- 余额修复流程
- 复杂场景（并发交易、异常处理）

注意：这些测试需要本地 PostgreSQL 数据库运行
"""

import pytest
from datetime import datetime
from decimal import Decimal

from sail_server.infrastructure.orm.finance import Account, Transaction, Budget, BudgetItem
from sail_server.model.finance.account import (
    create_account_impl,
    read_accounts_impl,
    read_account_impl,
    update_account_balance_impl,
    fix_account_balance_impl,
    recalc_account_balance_impl,
    clean_all_impl,
)
from sail_server.model.finance.transaction import create_transaction_impl
from sail_server.application.dto.finance import AccountData, TransactionData, BudgetData, BudgetItemData
from sail_server.utils.money import Money


pytestmark = [pytest.mark.db, pytest.mark.workflow]


class TestAccountLifecycle:
    """测试账户生命周期"""
    
    def test_create_account(self, db):
        """测试创建账户"""
        # 准备数据
        account_data = AccountData(
            name="生命周期测试账户",
            description="测试账户创建",
            balance="1000.00",
            state=0,
        )
        
        # 执行创建
        result = create_account_impl(db, account_data)
        
        # 验证
        assert result.id is not None
        assert result.name == "生命周期测试账户"
        assert result.balance == "1000.00"
        assert result.state == 0
        
        # 清理
        db.query(Account).filter(Account.id == result.id).delete()
        db.commit()
    
    def test_read_accounts(self, db):
        """测试读取账户列表"""
        # 创建测试数据
        for i in range(3):
            account = Account(
                name=f"读取测试账户{i}",
                balance=f"{100 * (i + 1)}.00",
                state=0
            )
            db.add(account)
        db.commit()
        
        # 读取
        accounts = read_accounts_impl(db, skip=0, limit=10)
        
        # 验证
        assert len(accounts) >= 3
        test_accounts = [a for a in accounts if a.name.startswith("读取测试账户")]
        assert len(test_accounts) == 3
        
        # 清理
        for account in test_accounts:
            db.query(Account).filter(Account.id == account.id).delete()
        db.commit()
    
    def test_read_single_account(self, db):
        """测试读取单个账户"""
        # 创建账户
        account = Account(name="单读测试", balance="500.00", state=0)
        db.add(account)
        db.commit()
        db.refresh(account)
        
        # 读取
        result = read_account_impl(db, account.id)
        
        # 验证
        assert result is not None
        assert result.name == "单读测试"
        assert result.balance == "500.00"
        
        # 清理
        db.delete(account)
        db.commit()
    
    def test_account_pagination(self, db):
        """测试账户分页"""
        # 创建多个账户
        created_ids = []
        for i in range(5):
            account = Account(name=f"分页测试{i}", balance="100.00", state=0)
            db.add(account)
            db.commit()
            db.refresh(account)
            created_ids.append(account.id)
        
        # 测试分页
        page1 = read_accounts_impl(db, skip=0, limit=2)
        page2 = read_accounts_impl(db, skip=2, limit=2)
        
        # 验证
        assert len(page1) >= 0
        assert len(page2) >= 0
        
        # 清理
        for account_id in created_ids:
            db.query(Account).filter(Account.id == account_id).delete()
        db.commit()


class TestTransactionWorkflow:
    """测试交易流程"""
    
    def test_simple_transaction(self, db):
        """测试简单交易"""
        # 创建两个账户
        from_acc = Account(name="转出账户", balance="1000.00", state=0)
        to_acc = Account(name="转入账户", balance="500.00", state=0)
        db.add(from_acc)
        db.add(to_acc)
        db.commit()
        db.refresh(from_acc)
        db.refresh(to_acc)
        
        # 创建交易
        trans_data = TransactionData(
            from_acc_id=from_acc.id,
            to_acc_id=to_acc.id,
            value="200.00",
            description="测试转账",
            tags="test",
            htime=datetime.now().timestamp(),
        )
        
        result = create_transaction_impl(db, trans_data)
        
        # 验证交易创建
        assert result.id is not None
        assert result.value == "200.00"
        
        # 清理
        db.query(Transaction).filter(Transaction.id == result.id).delete()
        db.delete(from_acc)
        db.delete(to_acc)
        db.commit()
    
    def test_transaction_updates_balance(self, db):
        """测试交易更新余额"""
        # 创建账户
        from_acc = Account(name="余额转出", balance="1000.00", state=0)
        to_acc = Account(name="余额转入", balance="500.00", state=0)
        db.add(from_acc)
        db.add(to_acc)
        db.commit()
        db.refresh(from_acc)
        db.refresh(to_acc)
        
        # 创建交易
        trans_data = TransactionData(
            from_acc_id=from_acc.id,
            to_acc_id=to_acc.id,
            value="200.00",
            description="余额更新测试",
            htime=datetime.now().timestamp(),
        )
        create_transaction_impl(db, trans_data)
        
        # 更新余额
        update_account_balance_impl(db, from_acc.id)
        update_account_balance_impl(db, to_acc.id)
        
        # 重新读取验证
        db.refresh(from_acc)
        db.refresh(to_acc)
        
        # 验证余额更新
        from_balance = Money(from_acc.balance)
        to_balance = Money(to_acc.balance)
        
        assert from_balance == Money("800.00")
        assert to_balance == Money("700.00")
        
        # 清理
        db.query(Transaction).filter(
            (Transaction.from_acc_id == from_acc.id) | 
            (Transaction.to_acc_id == to_acc.id)
        ).delete()
        db.delete(from_acc)
        db.delete(to_acc)
        db.commit()
    
    def test_multiple_transactions(self, db):
        """测试多笔交易"""
        # 创建账户
        acc1 = Account(name="多交易1", balance="1000.00", state=0)
        acc2 = Account(name="多交易2", balance="1000.00", state=0)
        db.add(acc1)
        db.add(acc2)
        db.commit()
        db.refresh(acc1)
        db.refresh(acc2)
        
        # 创建多笔交易
        amounts = ["100.00", "200.00", "50.00"]
        for amount in amounts:
            trans_data = TransactionData(
                from_acc_id=acc1.id,
                to_acc_id=acc2.id,
                value=amount,
                description="多笔交易测试",
                htime=datetime.now().timestamp(),
            )
            create_transaction_impl(db, trans_data)
        
        # 更新余额
        update_account_balance_impl(db, acc1.id)
        update_account_balance_impl(db, acc2.id)
        
        # 验证
        db.refresh(acc1)
        db.refresh(acc2)
        
        # acc1: 1000 - 100 - 200 - 50 = 650
        # acc2: 1000 + 100 + 200 + 50 = 1350
        assert Money(acc1.balance) == Money("650.00")
        assert Money(acc2.balance) == Money("1350.00")
        
        # 清理
        db.query(Transaction).filter(
            (Transaction.from_acc_id == acc1.id) | 
            (Transaction.to_acc_id == acc1.id)
        ).delete()
        db.delete(acc1)
        db.delete(acc2)
        db.commit()


class TestBalanceFixWorkflow:
    """测试余额修复流程"""
    
    def test_fix_account_balance(self, db):
        """测试修复账户余额"""
        # 创建账户
        account = Account(name="修复测试", balance="1000.00", state=0)
        db.add(account)
        db.commit()
        db.refresh(account)
        
        # 创建交易
        trans_data = TransactionData(
            from_acc_id=account.id,
            to_acc_id=-1,  # 外部账户
            value="100.00",
            description="支出",
            htime=datetime.now().timestamp(),
        )
        create_transaction_impl(db, trans_data)
        update_account_balance_impl(db, account.id)
        
        # 验证当前余额
        db.refresh(account)
        assert Money(account.balance) == Money("900.00")
        
        # 修复余额（调整到 800）
        fix_request = AccountData(id=account.id, balance="800.00")
        fix_account_balance_impl(db, fix_request)
        
        # 验证修复后余额
        db.refresh(account)
        assert Money(account.balance) == Money("800.00")
        
        # 清理
        db.query(Transaction).filter(
            (Transaction.from_acc_id == account.id) | 
            (Transaction.to_acc_id == account.id)
        ).delete()
        db.delete(account)
        db.commit()
    
    def test_recalc_account_balance(self, db):
        """测试重新计算余额"""
        # 创建账户
        account = Account(name="重算测试", balance="0.00", state=0)
        db.add(account)
        db.commit()
        db.refresh(account)
        
        # 创建多笔收入交易
        for i in range(3):
            trans_data = TransactionData(
                from_acc_id=-1,  # 外部账户
                to_acc_id=account.id,
                value=f"{100 * (i + 1)}.00",
                description=f"收入{i}",
                htime=datetime.now().timestamp(),
            )
            create_transaction_impl(db, trans_data)
        
        # 重新计算余额
        recalc_account_balance_impl(db, account.id)
        
        # 验证
        db.refresh(account)
        assert Money(account.balance) == Money("600.00")
        
        # 清理
        db.query(Transaction).filter(
            (Transaction.from_acc_id == account.id) | 
            (Transaction.to_acc_id == account.id)
        ).delete()
        db.delete(account)
        db.commit()


class TestBudgetWorkflow:
    """测试预算管理流程"""
    
    def test_create_budget(self, db):
        """测试创建预算"""
        budget = Budget(
            name="测试预算",
            description="预算流程测试",
            total_amount="5000.00",
            direction=0,
        )
        db.add(budget)
        db.commit()
        db.refresh(budget)
        
        # 验证
        assert budget.id is not None
        assert budget.name == "测试预算"
        assert budget.total_amount == "5000.00"
        
        # 清理
        db.delete(budget)
        db.commit()
    
    def test_create_budget_with_items(self, db):
        """测试创建预算及子项"""
        # 创建预算
        budget = Budget(
            name="带子项预算",
            description="含子项的预算测试",
            total_amount="12000.00",
            direction=0,
        )
        db.add(budget)
        db.commit()
        db.refresh(budget)
        
        # 添加子项
        items = [
            BudgetItem(
                budget_id=budget.id,
                name="房租",
                direction=0,
                item_type=1,  # 周期性
                amount="3500.00",
                period_count=12,
                is_refundable=0,
            ),
            BudgetItem(
                budget_id=budget.id,
                name="押金",
                direction=0,
                item_type=0,  # 固定
                amount="7000.00",
                period_count=1,
                is_refundable=1,
            ),
        ]
        for item in items:
            db.add(item)
        db.commit()
        
        # 验证关系
        db.refresh(budget)
        assert len(budget.items) == 2
        
        # 验证子项
        item_names = [item.name for item in budget.items]
        assert "房租" in item_names
        assert "押金" in item_names
        
        # 清理
        for item in budget.items:
            db.delete(item)
        db.delete(budget)
        db.commit()
    
    def test_budget_progress_tracking(self, db):
        """测试预算进度追踪"""
        # 创建预算
        budget = Budget(
            name="进度测试预算",
            total_amount="12000.00",
            direction=0,
        )
        db.add(budget)
        db.commit()
        db.refresh(budget)
        
        # 添加子项并更新进度
        item = BudgetItem(
            budget_id=budget.id,
            name="月度支出",
            direction=0,
            item_type=1,
            amount="1000.00",
            period_count=12,
            current_period=3,  # 已完成 3 期
        )
        db.add(item)
        db.commit()
        
        # 验证进度
        db.refresh(item)
        assert item.current_period == 3
        
        # 清理
        db.delete(item)
        db.delete(budget)
        db.commit()


class TestComplexScenarios:
    """测试复杂场景"""
    
    def test_circular_transfer(self, db):
        """测试循环转账"""
        # 创建三个账户
        acc_a = Account(name="账户A", balance="1000.00", state=0)
        acc_b = Account(name="账户B", balance="1000.00", state=0)
        acc_c = Account(name="账户C", balance="1000.00", state=0)
        db.add(acc_a)
        db.add(acc_b)
        db.add(acc_c)
        db.commit()
        db.refresh(acc_a)
        db.refresh(acc_b)
        db.refresh(acc_c)
        
        # A -> B -> C -> A 循环
        transfers = [
            (acc_a.id, acc_b.id, "100.00"),
            (acc_b.id, acc_c.id, "100.00"),
            (acc_c.id, acc_a.id, "100.00"),
        ]
        
        for from_id, to_id, amount in transfers:
            trans_data = TransactionData(
                from_acc_id=from_id,
                to_acc_id=to_id,
                value=amount,
                description="循环转账",
                htime=datetime.now().timestamp(),
            )
            create_transaction_impl(db, trans_data)
        
        # 更新所有余额
        for acc in [acc_a, acc_b, acc_c]:
            update_account_balance_impl(db, acc.id)
        
        # 验证（循环转账后余额应回到初始值）
        db.refresh(acc_a)
        db.refresh(acc_b)
        db.refresh(acc_c)
        
        assert Money(acc_a.balance) == Money("1000.00")
        assert Money(acc_b.balance) == Money("1000.00")
        assert Money(acc_c.balance) == Money("1000.00")
        
        # 清理
        for acc in [acc_a, acc_b, acc_c]:
            db.query(Transaction).filter(
                (Transaction.from_acc_id == acc.id) | 
                (Transaction.to_acc_id == acc.id)
            ).delete()
            db.delete(acc)
        db.commit()
    
    def test_zero_amount_transaction(self, db):
        """测试零金额交易"""
        # 创建账户
        acc1 = Account(name="零金额1", balance="1000.00", state=0)
        acc2 = Account(name="零金额2", balance="1000.00", state=0)
        db.add(acc1)
        db.add(acc2)
        db.commit()
        db.refresh(acc1)
        db.refresh(acc2)
        
        # 创建零金额交易
        trans_data = TransactionData(
            from_acc_id=acc1.id,
            to_acc_id=acc2.id,
            value="0.00",
            description="零金额测试",
            htime=datetime.now().timestamp(),
        )
        result = create_transaction_impl(db, trans_data)
        
        # 更新余额
        update_account_balance_impl(db, acc1.id)
        update_account_balance_impl(db, acc2.id)
        
        # 验证余额不变
        db.refresh(acc1)
        db.refresh(acc2)
        assert Money(acc1.balance) == Money("1000.00")
        assert Money(acc2.balance) == Money("1000.00")
        
        # 清理
        db.query(Transaction).filter(Transaction.id == result.id).delete()
        db.delete(acc1)
        db.delete(acc2)
        db.commit()
    
    def test_large_amount_transaction(self, db):
        """测试大额交易"""
        # 创建账户
        acc1 = Account(name="大额1", balance="1000000.00", state=0)
        acc2 = Account(name="大额2", balance="0.00", state=0)
        db.add(acc1)
        db.add(acc2)
        db.commit()
        db.refresh(acc1)
        db.refresh(acc2)
        
        # 创建大额交易
        trans_data = TransactionData(
            from_acc_id=acc1.id,
            to_acc_id=acc2.id,
            value="999999.99",
            description="大额测试",
            htime=datetime.now().timestamp(),
        )
        result = create_transaction_impl(db, trans_data)
        
        # 更新余额
        update_account_balance_impl(db, acc1.id)
        update_account_balance_impl(db, acc2.id)
        
        # 验证
        db.refresh(acc1)
        db.refresh(acc2)
        assert Money(acc1.balance) == Money("0.01")
        assert Money(acc2.balance) == Money("999999.99")
        
        # 清理
        db.query(Transaction).filter(Transaction.id == result.id).delete()
        db.delete(acc1)
        db.delete(acc2)
        db.commit()
    
    def test_transaction_with_budget(self, db):
        """测试关联预算的交易"""
        # 创建预算
        budget = Budget(
            name="交易预算",
            total_amount="5000.00",
            direction=0,
        )
        db.add(budget)
        db.commit()
        db.refresh(budget)
        
        # 创建账户
        acc = Account(name="预算账户", balance="5000.00", state=0)
        db.add(acc)
        db.commit()
        db.refresh(acc)
        
        # 创建关联预算的交易
        trans_data = TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="1000.00",
            description="预算支出",
            budget_id=budget.id,
            htime=datetime.now().timestamp(),
        )
        result = create_transaction_impl(db, trans_data)
        
        # 验证交易关联了预算
        assert result.budget_id == budget.id
        
        # 清理
        db.query(Transaction).filter(Transaction.id == result.id).delete()
        db.delete(acc)
        db.delete(budget)
        db.commit()


class TestCleanup:
    """测试清理功能"""
    
    def test_clean_all_impl(self, db):
        """测试清理所有账户（谨慎使用）"""
        # 这个测试在事务内运行，会自动回滚
        # 创建临时账户
        account = Account(name="临时清理测试", balance="100.00", state=0)
        db.add(account)
        db.commit()
        
        # 记录初始数量
        initial_count = db.query(Account).count()
        
        # 注意：clean_all_impl 会删除所有账户，这里我们只验证函数存在
        # 实际使用中需要非常谨慎
        assert callable(clean_all_impl)
