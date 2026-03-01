# -*- coding: utf-8 -*-
# @file test_orm_definitions.py
# @brief ORM 模型定义测试
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
ORM 模型定义测试

测试范围:
- ORM 基础类
- 财务模块 ORM
- 健康模块 ORM
- 文本模块 ORM
- 项目管理 ORM
- 分析模块 ORM
- 物资管理 ORM
- 关系定义

注意：这些测试不需要数据库连接，只验证模型定义
"""

import pytest
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, Text
from sqlalchemy.orm import relationship, declared_attr

# 导入所有 ORM 模型
from sail_server.infrastructure.orm.orm_base import ORMBase, TIME_START, TIME_END
from sail_server.infrastructure.orm.finance import Account, Transaction, Budget, BudgetItem
from sail_server.infrastructure.orm.health import Weight
from sail_server.infrastructure.orm.text import Work, Edition, DocumentNode, IngestJob
from sail_server.infrastructure.orm.project import Project, Mission
from sail_server.infrastructure.orm.history import HistoryEvent
from sail_server.infrastructure.orm.necessity import (
    Residence, Container, Item, Inventory, Journey
)
from sail_server.infrastructure.orm.analysis import (
    Character, CharacterAlias, CharacterAttribute, CharacterArc, CharacterRelation,
    Outline, OutlineNode, OutlineEvent,
    Setting, SettingAttribute, SettingRelation, CharacterSettingLink,
    TextEvidence,
)


class TestORMBase:
    """测试 ORM 基础类"""
    
    def test_base_is_declarative(self):
        """测试 ORMBase 是 DeclarativeBase"""
        from sqlalchemy.orm import DeclarativeBase
        assert issubclass(ORMBase, DeclarativeBase)
    
    def test_time_constants(self):
        """测试时间常量"""
        assert TIME_START == 0
        assert TIME_END == 4102416000  # 2100-01-01
        assert isinstance(TIME_END, int)


class TestFinanceORM:
    """测试财务模块 ORM"""
    
    def test_account_table_name(self):
        """测试 Account 表名"""
        assert Account.__tablename__ == "accounts"
    
    def test_account_columns(self):
        """测试 Account 列定义"""
        assert hasattr(Account, 'id')
        assert hasattr(Account, 'name')
        assert hasattr(Account, 'description')
        assert hasattr(Account, 'balance')
        assert hasattr(Account, 'state')
        assert hasattr(Account, 'ctime')
        assert hasattr(Account, 'mtime')
    
    def test_account_relationships(self):
        """测试 Account 关系"""
        assert hasattr(Account, 'in_transactions')
        assert hasattr(Account, 'out_transactions')
    
    def test_transaction_table_name(self):
        """测试 Transaction 表名"""
        assert Transaction.__tablename__ == "transactions"
    
    def test_transaction_columns(self):
        """测试 Transaction 列定义"""
        assert hasattr(Transaction, 'id')
        assert hasattr(Transaction, 'from_acc_id')
        assert hasattr(Transaction, 'to_acc_id')
        assert hasattr(Transaction, 'value')
        assert hasattr(Transaction, 'description')
        assert hasattr(Transaction, 'tags')
        assert hasattr(Transaction, 'state')
        assert hasattr(Transaction, 'htime')
    
    def test_transaction_foreign_keys(self):
        """测试 Transaction 外键关系"""
        assert hasattr(Transaction, 'from_acc')
        assert hasattr(Transaction, 'to_acc')
        assert hasattr(Transaction, 'budget')
    
    def test_budget_table_name(self):
        """测试 Budget 表名"""
        assert Budget.__tablename__ == "budgets"
    
    def test_budget_columns(self):
        """测试 Budget 列定义"""
        assert hasattr(Budget, 'id')
        assert hasattr(Budget, 'name')
        assert hasattr(Budget, 'description')
        assert hasattr(Budget, 'tags')
        assert hasattr(Budget, 'start_date')
        assert hasattr(Budget, 'end_date')
        assert hasattr(Budget, 'total_amount')
        assert hasattr(Budget, 'direction')
    
    def test_budget_relationships(self):
        """测试 Budget 关系"""
        assert hasattr(Budget, 'transactions')
        assert hasattr(Budget, 'items')
    
    def test_budget_item_table_name(self):
        """测试 BudgetItem 表名"""
        assert BudgetItem.__tablename__ == "budget_items"
    
    def test_budget_item_columns(self):
        """测试 BudgetItem 列定义"""
        assert hasattr(BudgetItem, 'id')
        assert hasattr(BudgetItem, 'budget_id')
        assert hasattr(BudgetItem, 'name')
        assert hasattr(BudgetItem, 'direction')
        assert hasattr(BudgetItem, 'item_type')
        assert hasattr(BudgetItem, 'amount')
        assert hasattr(BudgetItem, 'period_count')
        assert hasattr(BudgetItem, 'is_refundable')


class TestHealthORM:
    """测试健康模块 ORM"""
    
    def test_weight_table_name(self):
        """测试 Weight 表名"""
        assert Weight.__tablename__ == "weights"
    
    def test_weight_columns_exist(self):
        """测试 Weight 列存在"""
        assert hasattr(Weight, 'id')


class TestTextORM:
    """测试文本模块 ORM"""
    
    def test_work_table_name(self):
        """测试 Work 表名"""
        assert Work.__tablename__ == "works"
    
    def test_work_columns(self):
        """测试 Work 列定义"""
        assert hasattr(Work, 'id')
        assert hasattr(Work, 'slug')
        assert hasattr(Work, 'title')
        assert hasattr(Work, 'author')
        assert hasattr(Work, 'status')
        assert hasattr(Work, 'created_at')
        assert hasattr(Work, 'updated_at')
    
    def test_work_relationships(self):
        """测试 Work 关系"""
        assert hasattr(Work, 'editions')
    
    def test_edition_table_name(self):
        """测试 Edition 表名"""
        assert Edition.__tablename__ == "editions"
    
    def test_edition_columns(self):
        """测试 Edition 列定义"""
        assert hasattr(Edition, 'id')
        assert hasattr(Edition, 'work_id')
        assert hasattr(Edition, 'edition_name')
        assert hasattr(Edition, 'language')
        assert hasattr(Edition, 'word_count')
        assert hasattr(Edition, 'char_count')
    
    def test_document_node_table_name(self):
        """测试 DocumentNode 表名"""
        assert DocumentNode.__tablename__ == "document_nodes"
    
    def test_document_node_columns(self):
        """测试 DocumentNode 列定义"""
        assert hasattr(DocumentNode, 'id')
        assert hasattr(DocumentNode, 'edition_id')
        assert hasattr(DocumentNode, 'parent_id')
        assert hasattr(DocumentNode, 'node_type')
        assert hasattr(DocumentNode, 'title')
        assert hasattr(DocumentNode, 'raw_text')
        assert hasattr(DocumentNode, 'word_count')
    
    def test_ingest_job_table_name(self):
        """测试 IngestJob 表名"""
        assert IngestJob.__tablename__ == "ingest_jobs"


class TestProjectORM:
    """测试项目管理 ORM"""
    
    def test_project_table_name(self):
        """测试 Project 表名"""
        assert Project.__tablename__ == "projects"
    
    def test_project_columns(self):
        """测试 Project 列定义"""
        assert hasattr(Project, 'id')
        assert hasattr(Project, 'name')
        assert hasattr(Project, 'description')
        assert hasattr(Project, 'state')
        assert hasattr(Project, 'start_time_qbw')
        assert hasattr(Project, 'end_time_qbw')
    
    def test_mission_table_name(self):
        """测试 Mission 表名"""
        assert Mission.__tablename__ == "missions"
    
    def test_mission_columns(self):
        """测试 Mission 列定义"""
        assert hasattr(Mission, 'id')
        assert hasattr(Mission, 'project_id')
        assert hasattr(Mission, 'name')
        assert hasattr(Mission, 'description')
        assert hasattr(Mission, 'state')


class TestHistoryORM:
    """测试历史模块 ORM"""
    
    def test_history_event_table_name(self):
        """测试 HistoryEvent 表名"""
        assert HistoryEvent.__tablename__ == "history_events"
    
    def test_history_event_columns(self):
        """测试 HistoryEvent 列定义"""
        assert hasattr(HistoryEvent, 'id')
        assert hasattr(HistoryEvent, 'title')
        assert hasattr(HistoryEvent, 'description')
        assert hasattr(HistoryEvent, 'tags')


class TestNecessityORM:
    """测试物资管理 ORM"""
    
    def test_residence_table_name(self):
        """测试 Residence 表名"""
        assert Residence.__tablename__ == "residences"
    
    def test_residence_columns(self):
        """测试 Residence 列定义"""
        assert hasattr(Residence, 'id')
        assert hasattr(Residence, 'name')
        assert hasattr(Residence, 'address')
    
    def test_container_table_name(self):
        """测试 Container 表名"""
        assert Container.__tablename__ == "containers"
    
    def test_container_columns_exist(self):
        """测试 Container 列存在"""
        assert hasattr(Container, 'id')
        assert hasattr(Container, 'residence_id')
    
    def test_item_table_name(self):
        """测试 Item 表名"""
        assert Item.__tablename__ == "items"
    
    def test_item_columns_exist(self):
        """测试 Item 列存在"""
        assert hasattr(Item, 'id')
        assert hasattr(Item, 'name')
    
    def test_inventory_table_name(self):
        """测试 Inventory 表名"""
        assert Inventory.__tablename__ == "inventories"
    
    def test_inventory_columns(self):
        """测试 Inventory 列定义"""
        assert hasattr(Inventory, 'id')
        assert hasattr(Inventory, 'container_id')
        assert hasattr(Inventory, 'item_id')
        assert hasattr(Inventory, 'quantity')
    
    def test_journey_table_name(self):
        """测试 Journey 表名"""
        assert Journey.__tablename__ == "journeys"
    
    def test_journey_columns_exist(self):
        """测试 Journey 列存在"""
        assert hasattr(Journey, 'id')


class TestAnalysisORM:
    """测试分析模块 ORM"""
    
    def test_character_table_name(self):
        """测试 Character 表名"""
        assert Character.__tablename__ == "characters"
    
    def test_character_columns(self):
        """测试 Character 列定义"""
        assert hasattr(Character, 'id')
        assert hasattr(Character, 'canonical_name')
        assert hasattr(Character, 'description')
    
    def test_character_alias_table_name(self):
        """测试 CharacterAlias 表名"""
        assert CharacterAlias.__tablename__ == "character_aliases"
    
    def test_outline_table_name(self):
        """测试 Outline 表名"""
        assert Outline.__tablename__ == "outlines"
    
    def test_outline_node_table_name(self):
        """测试 OutlineNode 表名"""
        assert OutlineNode.__tablename__ == "outline_nodes"
    
    def test_outline_node_columns(self):
        """测试 OutlineNode 列定义"""
        assert hasattr(OutlineNode, 'id')
        assert hasattr(OutlineNode, 'outline_id')
        assert hasattr(OutlineNode, 'parent_id')
        assert hasattr(OutlineNode, 'title')
    
    def test_setting_table_name(self):
        """测试 Setting 表名"""
        assert Setting.__tablename__ == "novel_settings"
    
    def test_setting_columns(self):
        """测试 Setting 列定义"""
        assert hasattr(Setting, 'id')
        assert hasattr(Setting, 'canonical_name')
        assert hasattr(Setting, 'description')
    
    def test_text_evidence_table_name(self):
        """测试 TextEvidence 表名"""
        assert TextEvidence.__tablename__ == "text_evidence"


class TestORMRelationships:
    """测试 ORM 关系定义"""
    
    def test_account_transaction_relationship(self):
        """测试账户与交易关系"""
        # 检查 relationship 存在
        assert Account.in_transactions.property is not None
        assert Account.out_transactions.property is not None
        
        # 检查 back_populates
        assert Transaction.from_acc.property.back_populates == "out_transactions"
        assert Transaction.to_acc.property.back_populates == "in_transactions"
    
    def test_budget_item_relationship(self):
        """测试预算与子项关系"""
        assert Budget.items.property is not None
        assert BudgetItem.budget.property is not None
        assert BudgetItem.budget.property.back_populates == "items"
    
    def test_work_edition_relationship(self):
        """测试作品与版本关系"""
        assert Work.editions.property is not None
        assert Edition.work.property is not None


class TestORMColumnTypes:
    """测试 ORM 列类型"""
    
    def test_account_id_type(self):
        """测试 Account ID 类型"""
        assert isinstance(Account.__table__.c.id.type, Integer)
    
    def test_account_name_type(self):
        """测试 Account name 类型"""
        assert isinstance(Account.__table__.c.name.type, String)
    
    def test_account_ctime_type(self):
        """测试 Account ctime 类型"""
        assert isinstance(Account.__table__.c.ctime.type, TIMESTAMP)
    
    def test_transaction_value_type(self):
        """测试 Transaction value 类型"""
        assert isinstance(Transaction.__table__.c.value.type, String)
    
    def test_transaction_foreign_key(self):
        """测试 Transaction 外键"""
        fk = Transaction.__table__.c.from_acc_id.foreign_keys
        assert len(fk) > 0


class TestORMMetadata:
    """测试 ORM 元数据"""
    
    def test_core_tables_registered(self):
        """测试核心表已注册"""
        tables = ORMBase.metadata.tables
        
        # 核心表
        assert "accounts" in tables
        assert "transactions" in tables
        assert "budgets" in tables
        assert "budget_items" in tables
        assert "weights" in tables
        assert "works" in tables


class TestORMInheritance:
    """测试 ORM 继承"""
    
    def test_core_models_inherit_base(self):
        """测试核心模型继承 ORMBase"""
        core_models = [
            Account, Transaction, Budget, BudgetItem,
            Weight, Work, Edition, DocumentNode,
            Project, Mission,
            HistoryEvent,
            Character, Outline, OutlineNode, Setting, TextEvidence,
        ]
        for model in core_models:
            assert issubclass(model, ORMBase), f"{model.__name__} 应继承 ORMBase"
