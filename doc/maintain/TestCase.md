# SailZen 测试用例维护文档

## 概述

本文档记录了 SailZen 项目的测试用例结构、分类和维护指南。测试用例分为 Python 后端测试和 TypeScript 前端测试两部分。

本文档最新更新日期：2026-03-01

## 测试结构

```
tests/
├── conftest.py                      # 全局 pytest 配置和共享 fixtures
├── __init__.py
├── test_db_read.py                  # 数据库读取基础测试（保留）
│
├── unit/                            # 单元测试（函数功能测试）
│   ├── __init__.py
│   ├── test_utils_money.py          # Money 类单元测试 ✅ 新增
│   ├── test_utils_state.py          # StateBits 单元测试 ✅ 新增
│   └── test_utils_time.py           # time_utils 单元测试 ✅ 新增
│
├── orm/                             # 数据库定义测试
│   ├── __init__.py
│   └── test_orm_definitions.py      # ORM 模型定义测试 ✅ 新增
│
├── integration/                     # 集成测试（数据库连接）
│   ├── __init__.py
│   └── test_database_connection.py  # 数据库连接集成测试 ✅ 新增
│
├── workflow/                        # 标准流程测试
│   ├── __init__.py
│   └── test_finance_workflow.py     # 财务模块标准流程测试 ✅ 新增
│
├── llm_integration/                 # LLM 集成测试框架
│   ├── conftest.py                  # LLM 集成测试配置
│   ├── run_validation.py            # 验证运行器 CLI
│   ├── test_llm_connection.py       # LLM 连接测试
│   ├── test_prompt_templates.py     # Prompt 模板测试
│   ├── test_task_flow.py            # 任务流程测试
│   └── validators/                  # 验证器模块
│       ├── __init__.py
│       ├── base.py                  # 验证器基类
│       ├── connection.py            # 连接验证器
│       ├── prompt.py                # Prompt 验证器
│       └── task.py                  # 任务验证器
```

## 测试分类

### 1. 单元测试（Unit Tests）- 函数功能测试

| 测试文件 | 描述 | 状态 |
|---------|------|------|
| `tests/unit/test_utils_money.py` | Money 类功能测试（构造、运算、比较、转换） | ✅ 活跃 |
| `tests/unit/test_utils_state.py` | StateBits 功能测试（位操作、属性映射） | ✅ 活跃 |
| `tests/unit/test_utils_time.py` | time_utils 功能测试（季度、周、双周计算） | ✅ 活跃 |

#### 运行单元测试

```powershell
# 运行所有单元测试
uv run pytest tests/unit/ -v

# 运行特定单元测试
uv run pytest tests/unit/test_utils_money.py -v

# 运行特定测试类
uv run pytest tests/unit/test_utils_money.py::TestMoneyConstruction -v

# 运行特定测试方法
uv run pytest tests/unit/test_utils_money.py::TestMoneyConstruction::test_default_construction -v
```

### 2. 数据库定义测试（ORM Definition Tests）

| 测试文件 | 描述 | 状态 |
|---------|------|------|
| `tests/orm/test_orm_definitions.py` | ORM 模型定义测试（表名、列、关系、约束） | ✅ 活跃 |

#### 测试范围

- **ORM 基础类**: ORMBase、时间常量
- **财务模块**: Account、Transaction、Budget、BudgetItem
- **健康模块**: Weight
- **文本模块**: Work、Chapter
- **项目管理**: Project、Task
- **分析模块**: AnalysisTask、Character、OutlineNode、Setting
- **物资管理**: Residence、Container、Item、Inventory、Journey
- **历史模块**: History

#### 运行 ORM 定义测试

```powershell
# 运行所有 ORM 定义测试（不需要数据库连接）
uv run pytest tests/orm/ -v

# 运行特定模块的 ORM 测试
uv run pytest tests/orm/test_orm_definitions.py::TestFinanceORM -v
```

### 3. 集成测试（Integration Tests）- 数据库连接测试

| 测试文件 | 描述 | 状态 |
|---------|------|------|
| `tests/integration/test_database_connection.py` | 数据库连接和基本操作测试 | ✅ 活跃 |

#### 测试范围

- **连接测试**: 引擎创建、基本连接、多连接、连接池
- **操作测试**: 会话创建、SQL 执行、事务回滚
- **ORM 测试**: 表存在性、列定义、CRUD 操作
- **性能测试**: 查询性能、ORM 查询性能
- **编码测试**: Unicode 支持、编码设置
- **约束测试**: 主键约束、唯一性约束
- **恢复测试**: 错误后重连

#### 运行集成测试（需要本地 PostgreSQL）

```powershell
# 设置环境变量
$env:POSTGRE_URI="postgresql://postgres:password@localhost:5432/main"

# 运行所有集成测试
uv run pytest tests/integration/ -v

# 运行特定集成测试
uv run pytest tests/integration/test_database_connection.py::TestDatabaseConnection -v

# 跳过数据库测试
uv run pytest -m "not db"
```

### 4. 标准流程测试（Workflow Tests）

| 测试文件 | 描述 | 状态 |
|---------|------|------|
| `tests/workflow/test_finance_workflow.py` | 财务模块完整业务流程测试 | ✅ 活跃 |

#### 测试范围

- **账户生命周期**: 创建、读取、更新、删除、分页
- **交易流程**: 创建交易、更新余额
- **转账流程**: 多账户间转账
- **预算管理**: 创建预算、添加子项、进度追踪
- **余额修复**: fix_account_balance、recalc_account_balance
- **复杂场景**: 循环转账、零金额交易、大额交易

#### 运行流程测试（需要本地 PostgreSQL）

```powershell
# 设置环境变量
$env:POSTGRE_URI="postgresql://postgres:password@localhost:5432/main"

# 运行所有流程测试
uv run pytest tests/workflow/ -v

# 运行特定流程测试
uv run pytest tests/workflow/test_finance_workflow.py::TestAccountLifecycle -v

# 运行特定场景
uv run pytest tests/workflow/test_finance_workflow.py::TestComplexScenarios::test_circular_transfer -v
```

### 5. LLM 集成测试（LLM Integration Tests）

| 测试文件 | 描述 | 状态 |
|---------|------|------|
| `tests/llm_integration/test_llm_connection.py` | LLM 提供商连接测试 | ✅ 活跃 |
| `tests/llm_integration/test_prompt_templates.py` | Prompt 模板渲染测试 | ✅ 活跃 |
| `tests/llm_integration/test_task_flow.py` | 任务执行流程测试 | ✅ 活跃 |

## 全局配置

### conftest.py

全局配置文件位于 `tests/conftest.py`，提供以下 fixtures:

| Fixture | 作用域 | 描述 |
|---------|--------|------|
| `engine` | session | 数据库引擎 |
| `db` | function | 数据库会话（事务隔离） |
| `db_session` | function | 独立会话上下文管理器 |
| `clean_db` | function | 清理后的会话 |
| `module_db` | module | 模块级别会话 |
| `sample_account_data` | function | 示例账户数据 |
| `sample_transaction_data` | function | 示例交易数据 |
| `sample_budget_data` | function | 示例预算数据 |

### 测试标记

| 标记 | 描述 | 使用场景 |
|------|------|---------|
| `@pytest.mark.unit` | 单元测试 | 纯函数测试 |
| `@pytest.mark.orm` | ORM 定义测试 | 模型定义验证 |
| `@pytest.mark.db` | 数据库测试 | 需要数据库连接 |
| `@pytest.mark.integration` | 集成测试 | 多组件集成 |
| `@pytest.mark.workflow` | 流程测试 | 完整业务流程 |
| `@pytest.mark.asyncio` | 异步测试 | async 测试函数 |
| `@pytest.mark.current` | 当前开发标记 | 标记正在开发的测试 |

## 运行测试

### 基础命令

```powershell
# 运行所有测试
uv run pytest

# 运行特定目录测试
uv run pytest tests/unit/ -v
uv run pytest tests/orm/ -v
uv run pytest tests/integration/ -v
uv run pytest tests/workflow/ -v

# 运行特定测试文件
uv run pytest tests/unit/test_utils_money.py -v

# 运行特定测试类
uv run pytest tests/unit/test_utils_money.py::TestMoneyConstruction -v

# 运行特定测试方法
uv run pytest tests/unit/test_utils_money.py::TestMoneyConstruction::test_default_construction -v

# 跳过异步测试（不调用真实 LLM）
uv run pytest -m "not asyncio"

# 跳过数据库测试
uv run pytest -m "not db"

# 只运行单元测试
uv run pytest -m "unit"

# 只运行 ORM 定义测试
uv run pytest -m "orm"

# 只运行集成测试
uv run pytest -m "integration"

# 只运行流程测试
uv run pytest -m "workflow"

# 运行当前标记的测试
uv run pytest -m "current"
```

### 覆盖率测试

```powershell
# 安装 coverage 工具
uv add --dev pytest-cov

# 运行覆盖率测试
uv run pytest --cov=sail_server --cov-report=html

# 查看覆盖率报告
# 打开 htmlcov/index.html
```

### LLM 集成测试

```powershell
# 快速检查（不调用真实 LLM）
uv run python tests/llm_integration/run_validation.py quick

# 验证 LLM 连接（需要 API Key）
uv run python tests/llm_integration/run_validation.py connection --real-connection

# 验证 Prompt 模板
uv run python tests/llm_integration/run_validation.py prompt

# 验证任务流程
uv run python tests/llm_integration/run_validation.py task --minimal

# 运行所有验证
uv run python tests/llm_integration/run_validation.py all
```

## 环境变量配置

### 数据库连接

```powershell
# 设置 PostgreSQL 连接
$env:POSTGRE_URI="postgresql://postgres:password@localhost:5432/main"

# 验证连接
uv run pytest tests/integration/test_database_connection.py::TestDatabaseConnection::test_basic_connection -v
```

### LLM API Keys

```powershell
# 设置 API Keys（如需测试真实 LLM 连接）
$env:OPENAI_API_KEY="your-key"
$env:GOOGLE_API_KEY="your-key"
$env:ANTHROPIC_API_KEY="your-key"
$env:MOONSHOT_API_KEY="your-key"
```

## 维护指南

### 添加新测试

1. **确定测试类型**
   - 纯函数测试 → `tests/unit/`
   - ORM 定义测试 → `tests/orm/`
   - 数据库连接测试 → `tests/integration/`
   - 业务流程测试 → `tests/workflow/`

2. **使用标准文件头格式**

```python
# -*- coding: utf-8 -*-
# @file test_xxx.py
# @brief 测试描述
# @author sailing-innocent
# @date YYYY-MM-DD
# @version 1.0
# ---------------------------------
```

3. **使用 pytest 最佳实践**
   - 使用 fixtures 管理依赖
   - 使用参数化测试减少重复代码
   - 使用适当的标记分类测试
   - 每个测试方法只测试一个功能点

### 示例：添加新的单元测试

```python
# tests/unit/test_utils_new.py

# -*- coding: utf-8 -*-
# @file test_utils_new.py
# @brief 新工具函数测试
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

import pytest
from sail_server.utils.new_module import new_function


class TestNewFunction:
    """测试新功能"""
    
    def test_basic_case(self):
        """测试基本场景"""
        result = new_function("input")
        assert result == "expected"
    
    @pytest.mark.parametrize("input,expected", [
        ("a", "result_a"),
        ("b", "result_b"),
    ])
    def test_multiple_cases(self, input, expected):
        """测试多场景"""
        assert new_function(input) == expected
```

### 示例：添加新的集成测试

```python
# tests/integration/test_new_feature.py

# -*- coding: utf-8 -*-
# @file test_new_feature.py
# @brief 新功能集成测试
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

import pytest
from sail_server.model.new_feature import create_impl

pytestmark = pytest.mark.db  # 标记需要数据库


class TestNewFeature:
    """测试新功能"""
    
    def test_create(self, db):
        """测试创建"""
        result = create_impl(db, data)
        assert result.id is not None
```

## 常见问题

### 1. 数据库连接失败

```powershell
# 检查环境变量
echo $env:POSTGRE_URI

# 设置正确的连接字符串
$env:POSTGRE_URI="postgresql://postgres:password@localhost:5432/main"

# 检查 PostgreSQL 服务是否运行
# Windows: 服务管理器检查 postgresql-x64-XX
# 或使用 pgAdmin 测试连接
```

### 2. 跳过数据库测试

```powershell
# 运行不需要数据库的测试
uv run pytest -m "not db" -v

# 只运行单元测试和 ORM 定义测试
uv run pytest tests/unit/ tests/orm/ -v
```

### 3. 编码问题（Windows）

```powershell
# 修复终端编码
chcp 65001

# 设置 PostgreSQL 编码
$env:PGCLIENTENCODING="UTF8"
```

### 4. 测试数据清理

```python
# 使用 fixture 的事务隔离（推荐）
def test_example(db):
    # 在 db fixture 中，每个测试后自动回滚
    pass

# 或手动清理
def test_with_cleanup(db):
    try:
        # 测试代码
        pass
    finally:
        # 清理代码
        db.rollback()
```

## 测试覆盖率目标

| 模块 | 目标覆盖率 | 当前状态 |
|------|-----------|---------|
| `sail_server.utils.money` | 90% | 🟢 已实现 |
| `sail_server.utils.state` | 85% | 🟢 已实现 |
| `sail_server.utils.time_utils` | 80% | 🟢 已实现 |
| `sail_server.infrastructure.orm` | 75% | 🟢 已实现 |
| `sail_server.model.finance` | 70% | 🟡 进行中 |
| `sail_server.data.dao` | 70% | 🔴 待添加 |
| `sail.llm` | 60% | 🟡 进行中 |

## 更新记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-02-27 | 1.0 | 初始版本，整理 LLM 网关重构后的测试结构 |
| 2026-02-27 | 1.1 | 标记过时测试文件，创建新的 Unified Agent 系统测试 |
| 2026-03-01 | 2.0 | 重构测试结构，添加四个层次的测试（函数功能、数据库定义、数据库连接、标准流程） |
| 2026-03-01 | 2.1 | 新增 Money/StateBits/time_utils 单元测试 |
| 2026-03-01 | 2.2 | 新增 ORM 定义测试 |
| 2026-03-01 | 2.3 | 新增数据库连接集成测试 |
| 2026-03-01 | 2.4 | 新增财务模块标准流程测试 |
