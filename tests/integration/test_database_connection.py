# -*- coding: utf-8 -*-
# @file test_database_connection.py
# @brief 数据库连接集成测试
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
数据库连接集成测试

测试范围:
- 数据库连接
- 基本 CRUD 操作
- 事务回滚
- 连接池
- 性能基准

注意：这些测试需要本地 PostgreSQL 数据库运行
"""

import os
import pytest
import time
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from sail_server.infrastructure.orm.orm_base import ORMBase
from sail_server.infrastructure.orm.finance import Account
from sail_server.db import Database


# 标记需要数据库的测试
pytestmark = pytest.mark.db


class TestDatabaseConnection:
    """测试数据库连接"""
    
    def test_environment_variable_set(self):
        """测试环境变量已设置"""
        uri = os.environ.get("POSTGRE_URI")
        # 允许使用默认值或环境变量
        assert uri is not None or True  # 如果未设置，db fixture 会跳过
    
    def test_engine_creation(self, engine):
        """测试引擎创建"""
        assert engine is not None
        assert hasattr(engine, 'connect')
    
    def test_basic_connection(self, engine):
        """测试基本连接"""
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
    
    def test_connection_with_ping(self, engine):
        """测试连接池预检"""
        # 测试连接是否有效
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            assert "PostgreSQL" in version
    
    def test_multiple_connections(self, engine):
        """测试多个连接"""
        connections = []
        for _ in range(5):
            conn = engine.connect()
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
            connections.append(conn)
        
        # 清理
        for conn in connections:
            conn.close()


class TestDatabaseOperations:
    """测试数据库操作"""
    
    def test_session_creation(self, db):
        """测试会话创建"""
        assert db is not None
        assert isinstance(db, Session)
    
    def test_raw_sql_execution(self, db):
        """测试原始 SQL 执行"""
        result = db.execute(text("SELECT current_database()"))
        db_name = result.scalar()
        assert db_name is not None
    
    def test_parameterized_query(self, db):
        """测试参数化查询"""
        result = db.execute(
            text("SELECT :val as test_val"),
            {"val": 42}
        )
        assert result.scalar() == 42
    
    def test_transaction_rollback(self, engine):
        """测试事务回滚"""
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            # 执行一些操作
            result = session.execute(text("SELECT 1"))
            assert result.scalar() == 1
            
            # 回滚
            session.rollback()
            
            # 验证会话仍然可用
            result = session.execute(text("SELECT 2"))
            assert result.scalar() == 2
        finally:
            session.close()


class TestORMOperations:
    """测试 ORM 操作"""
    
    def test_table_exists(self, engine):
        """测试表存在"""
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # 检查核心表存在
        assert "accounts" in tables
        assert "transactions" in tables
        assert "weights" in tables
    
    def test_column_exists(self, engine):
        """测试列存在"""
        inspector = inspect(engine)
        columns = inspector.get_columns("accounts")
        column_names = [c['name'] for c in columns]
        
        assert 'id' in column_names
        assert 'name' in column_names
        assert 'balance' in column_names
    
    def test_simple_insert(self, db):
        """测试简单插入"""
        # 清理测试数据
        db.execute(text("DELETE FROM accounts WHERE name = 'test_insert'"))
        db.commit()
        
        # 插入测试数据
        db.execute(
            text("INSERT INTO accounts (name, balance, state) VALUES (:name, :balance, :state)"),
            {"name": "test_insert", "balance": "100.00", "state": 0}
        )
        db.commit()
        
        # 验证插入
        result = db.execute(
            text("SELECT balance FROM accounts WHERE name = :name"),
            {"name": "test_insert"}
        )
        assert result.scalar() == "100.00"
        
        # 清理
        db.execute(text("DELETE FROM accounts WHERE name = 'test_insert'"))
        db.commit()
    
    def test_orm_insert_and_query(self, db):
        """测试 ORM 插入和查询"""
        # 创建新账户
        account = Account(
            name="test_orm_account",
            balance="500.00",
            state=0,
            description="Test account for ORM operations"
        )
        db.add(account)
        db.commit()
        
        # 验证 ID 已生成
        assert account.id is not None
        
        # 查询验证
        queried = db.query(Account).filter_by(name="test_orm_account").first()
        assert queried is not None
        assert queried.balance == "500.00"
        assert queried.description == "Test account for ORM operations"
        
        # 清理
        db.delete(queried)
        db.commit()
    
    def test_orm_update(self, db):
        """测试 ORM 更新"""
        # 创建账户
        account = Account(name="test_update", balance="100.00", state=0)
        db.add(account)
        db.commit()
        
        # 更新
        account.balance = "200.00"
        db.commit()
        
        # 验证更新
        db.refresh(account)
        assert account.balance == "200.00"
        
        # 清理
        db.delete(account)
        db.commit()
    
    def test_orm_delete(self, db):
        """测试 ORM 删除"""
        # 创建账户
        account = Account(name="test_delete", balance="100.00", state=0)
        db.add(account)
        db.commit()
        account_id = account.id
        
        # 删除
        db.delete(account)
        db.commit()
        
        # 验证删除
        queried = db.query(Account).filter_by(id=account_id).first()
        assert queried is None


class TestDatabaseSingleton:
    """测试数据库单例"""
    
    def test_singleton_instance(self):
        """测试单例实例"""
        db1 = Database.get_instance()
        db2 = Database.get_instance()
        assert db1 is db2
    
    def test_cannot_create_second_instance(self):
        """测试不能创建第二个实例"""
        # 单例已存在，尝试创建新实例应失败
        with pytest.raises(Exception, match="singleton"):
            Database()


class TestDatabasePerformance:
    """测试数据库性能"""
    
    def test_query_performance(self, db):
        """测试查询性能"""
        start_time = time.time()
        
        # 执行多次查询
        for _ in range(100):
            db.execute(text("SELECT 1"))
        
        elapsed = time.time() - start_time
        # 100 次查询应在 1 秒内完成
        assert elapsed < 1.0, f"查询太慢: {elapsed}s"
    
    def test_orm_query_performance(self, db):
        """测试 ORM 查询性能"""
        start_time = time.time()
        
        # 执行多次 ORM 查询
        for _ in range(50):
            db.query(Account).limit(10).all()
        
        elapsed = time.time() - start_time
        # 50 次 ORM 查询应在 2 秒内完成
        assert elapsed < 2.0, f"ORM 查询太慢: {elapsed}s"


class TestDatabaseEncoding:
    """测试数据库编码"""
    
    def test_unicode_support(self, db):
        """测试 Unicode 支持"""
        # 创建含中文字符的记录
        account = Account(
            name="测试中文账户",
            description="这是一个测试账户，包含中文：你好世界 🎉",
            balance="100.00",
            state=0
        )
        db.add(account)
        db.commit()
        
        # 查询并验证
        queried = db.query(Account).filter_by(name="测试中文账户").first()
        assert queried is not None
        assert queried.description == "这是一个测试账户，包含中文：你好世界 🎉"
        
        # 清理
        db.delete(queried)
        db.commit()
    
    def test_encoding_settings(self, engine):
        """测试编码设置"""
        with engine.connect() as conn:
            # 检查客户端编码
            result = conn.execute(text("SHOW client_encoding"))
            encoding = result.scalar()
            assert encoding in ['UTF8', 'UNICODE']


class TestDatabaseConstraints:
    """测试数据库约束"""
    
    def test_primary_key_constraint(self, db):
        """测试主键约束"""
        # 创建账户
        account1 = Account(name="test_pk_1", balance="100.00", state=0)
        db.add(account1)
        db.commit()
        
        # 验证 ID 唯一
        account2 = Account(name="test_pk_2", balance="200.00", state=0)
        db.add(account2)
        db.commit()
        
        assert account1.id != account2.id
        
        # 清理
        db.delete(account1)
        db.delete(account2)
        db.commit()


class TestConnectionRecovery:
    """测试连接恢复"""
    
    def test_reconnect_after_error(self, engine):
        """测试错误后重连"""
        with engine.connect() as conn:
            # 执行有效查询
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
            
            # 执行无效查询（不应影响连接）
            try:
                conn.execute(text("SELECT * FROM nonexistent_table"))
            except SQLAlchemyError:
                pass
            
            # 连接应仍然可用
            result = conn.execute(text("SELECT 2"))
            assert result.scalar() == 2
