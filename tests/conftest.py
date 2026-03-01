# -*- coding: utf-8 -*-
# @file conftest.py
# @brief Pytest 全局配置和共享 fixtures
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
Pytest 全局配置文件

提供以下 fixtures:
- db: 数据库会话 (需要本地 PostgreSQL 环境)
- db_session: 独立的数据库会话上下文管理器
- clean_db: 清理后的数据库会话 (每个测试后回滚)
"""

import os
import sys
import pytest
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 设置 PostgreSQL 客户端编码环境变量
os.environ["PGCLIENTENCODING"] = "UTF8"

# 导入 ORM Base 和所有模型
from sail_server.infrastructure.orm.orm_base import ORMBase
from sail_server.infrastructure.orm import (
    health, finance, life, project, history, text, necessity, analysis
)


# ============================================================================
# 配置
# ============================================================================

# 默认测试数据库 URI（本地 dev 环境）
DEFAULT_TEST_DB_URI = "postgresql://postgres:password@localhost:5432/main"

# SQLite 内存数据库（用于无数据库环境的快速测试）
SQLITE_MEMORY_URI = "sqlite:///:memory:"


def get_db_uri() -> str:
    """获取测试数据库 URI"""
    uri = os.environ.get("POSTGRE_URI", DEFAULT_TEST_DB_URI)
    # 转换为 psycopg3 格式
    if uri and uri.startswith("postgresql://"):
        uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
    return uri


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def engine():
    """创建数据库引擎 (session 级别)"""
    uri = get_db_uri()
    try:
        engine = create_engine(
            uri,
            pool_pre_ping=True,  # 自动检测连接是否有效
            pool_recycle=3600,   # 连接回收时间
        )
        # 测试连接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        yield engine
    except Exception as e:
        pytest.skip(f"数据库连接失败: {e}")
    finally:
        if 'engine' in locals():
            engine.dispose()


@pytest.fixture(scope="function")
def db(engine) -> Generator[Session, None, None]:
    """
    提供数据库会话 (function 级别，每个测试独立)
    
    使用示例:
        def test_something(db):
            result = db.query(Account).all()
            assert len(result) >= 0
    """
    connection = engine.connect()
    transaction = connection.begin()
    
    session_factory = sessionmaker(bind=connection)
    session = session_factory()
    
    yield session
    
    # 清理：回滚事务，关闭会话
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    """
    提供独立的数据库会话上下文管理器
    
    使用示例:
        def test_with_context(db_session):
            with db_session() as session:
                result = session.query(Account).all()
    """
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def clean_db(engine) -> Generator[Session, None, None]:
    """
    提供清理后的数据库会话，测试后回滚所有更改
    
    适用于需要保持数据库干净的测试
    """
    connection = engine.connect()
    transaction = connection.begin()
    
    session_factory = sessionmaker(bind=connection)
    session = session_factory()
    
    yield session
    
    # 回滚所有更改
    session.rollback()
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="module")
def module_db(engine) -> Generator[Session, None, None]:
    """
    模块级别的数据库会话，用于一组相关测试
    
    使用示例:
        @pytest.mark.usefixtures("module_db")
        class TestAccountOperations:
            def test_create(self, module_db):
                # 创建操作
                
            def test_read(self, module_db):
                # 读取操作（能看到 test_create 的数据）
    """
    connection = engine.connect()
    transaction = connection.begin()
    
    session_factory = sessionmaker(bind=connection)
    session = session_factory()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


# ============================================================================
# 辅助 Fixtures
# ============================================================================

@pytest.fixture
def sample_account_data():
    """提供示例账户数据"""
    return {
        "name": "测试账户",
        "description": "用于测试的账户",
        "balance": "1000.00",
        "state": 0,
    }


@pytest.fixture
def sample_transaction_data():
    """提供示例交易数据"""
    return {
        "from_acc_id": 1,
        "to_acc_id": 2,
        "value": "100.00",
        "description": "测试交易",
        "tags": "test",
        "state": 0,
    }


@pytest.fixture
def sample_budget_data():
    """提供示例预算数据"""
    return {
        "name": "测试预算",
        "description": "用于测试的预算",
        "total_amount": "5000.00",
        "direction": 0,
    }


# ============================================================================
# Pytest 钩子
# ============================================================================

def pytest_configure(config):
    """配置 pytest"""
    config.addinivalue_line(
        "markers", "db: mark test as requiring database connection"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "workflow: mark test as workflow test"
    )
    config.addinivalue_line(
        "markers", "orm: mark test as ORM definition test"
    )


def pytest_collection_modifyitems(config, items):
    """修改测试项，自动添加标记"""
    for item in items:
        # 根据路径自动添加标记
        if "test_utils_" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "test_orm_" in item.nodeid:
            item.add_marker(pytest.mark.orm)
        elif "test_database_" in item.nodeid:
            item.add_marker(pytest.mark.db)
        elif "test_workflow_" in item.nodeid:
            item.add_marker(pytest.mark.workflow)
            item.add_marker(pytest.mark.integration)
