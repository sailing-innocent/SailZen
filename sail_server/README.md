# Sail Server

SailServer 是 SailZen 的后端服务，基于 Python + Litestar + PostgreSQL 构建，采用分层架构设计。

## 目录结构

```
sail_server/
├── router/                    # 路由层 (Presentation Layer)
│   ├── __init__.py           # 路由聚合导出
│   ├── analysis.py           # 文本分析路由
│   ├── finance.py            # 财务管理路由
│   ├── health.py             # 健康管理路由
│   ├── history.py            # 历史记录路由
│   ├── necessity.py          # 物资管理路由
│   ├── project.py            # 项目管理路由
│   ├── text.py               # 文本管理路由
│
├── controller/                # 控制器层 (Application Layer)
│   ├── analysis.py           # 文本分析控制器
│   ├── analysis_llm.py       # LLM 分析控制器
│   ├── character.py          # 角色分析控制器
│   ├── character_detection.py # 角色检测控制器
│   ├── finance.py            # 财务控制器
│   ├── health.py             # 健康控制器
│   ├── history.py            # 历史控制器
│   ├── necessity.py          # 物资控制器
│   ├── outline.py            # 大纲控制器
│   ├── outline_extraction.py # 大纲提取控制器
│   ├── project.py            # 项目控制器
│   ├── setting.py            # 设定控制器
│   ├── setting_extraction.py # 设定提取控制器
│   └── text.py               # 文本控制器
│
├── application/               # 应用层 (Application Layer)
│   ├── dto/                  # 数据传输对象
│   │   ├── __init__.py
│   │   ├── analysis.py       # 分析模块 DTOs
│   │   ├── finance.py        # 财务模块 DTOs
│   │   ├── health.py         # 健康模块 DTOs
│   │   ├── history.py        # 历史模块 DTOs
│   │   ├── life.py           # 生活模块 DTOs
│   │   ├── necessity.py      # 物资模块 DTOs
│   │   ├── project.py        # 项目模块 DTOs
│   │   ├── text.py           # 文本模块 DTOs
│   └── service/              # [预留] 应用服务层
│       └── __init__.py
│
├── model/                     # 领域模型层 (Domain Layer)
│   ├── analysis/             # 文本分析领域
│   │   ├── character.py      # 角色模型
│   │   ├── outline.py        # 大纲模型
│   │   ├── relation.py       # 关系模型
│   │   ├── setting.py        # 设定模型
│   │   ├── task_scheduler.py # 任务调度器
│   │   └── evidence.py       # 证据模型
│   ├── finance/              # 财务领域
│   │   ├── account.py        # 账户模型
│   │   ├── budget.py         # 预算模型
│   │   └── transaction.py    # 交易模型
│   ├── necessity/            # 物资领域
│   │   ├── category.py       # 分类模型
│   │   ├── container.py      # 容器模型
│   │   ├── inventory.py      # 库存模型
│   │   ├── item.py           # 物品模型
│   │   ├── journey.py        # 行程模型
│   │   └── residence.py      # 住所模型
│   ├── health.py             # 健康模型
│   ├── history.py            # 历史模型
│   ├── project.py            # 项目模型
│   ├── service.py            # 服务模型
│   ├── text.py               # 文本模型
│
├── agent/                     # Agent 层 (Domain Layer)
│   ├── __init__.py           # Agent 导出与自动注册
│   ├── base.py               # Agent 基类定义
│   ├── registry.py           # Agent 注册表
│   ├── general.py            # 通用 Agent
│   └── novel_analysis.py     # 小说分析 Agent
│
├── data/                      # 数据访问层 (Infrastructure Layer)
│   ├── __init__.py
│   ├── types.py              # 自定义数据类型 (JSONB 等)
│   └── dao/                  # 数据访问对象
│       ├── __init__.py
│       ├── base.py           # DAO 基类 (泛型 CRUD)
│       ├── analysis.py       # 分析模块 DAO
│       ├── finance.py        # 财务模块 DAO
│       ├── health.py         # 健康模块 DAO
│       ├── history.py        # 历史模块 DAO
│       ├── life.py           # 生活模块 DAO
│       ├── necessity.py      # 物资模块 DAO
│       ├── project.py        # 项目模块 DAO
│       ├── text.py           # 文本模块 DAO
│
├── infrastructure/            # 基础设施层 (Infrastructure Layer)
│   ├── __init__.py
│   ├── orm/                  # ORM 模型定义
│   │   ├── __init__.py
│   │   ├── orm_base.py       # ORM 基类
│   │   ├── analysis/         # 分析模块 ORM
│   │   ├── finance.py        # 财务模块 ORM
│   │   ├── health.py         # 健康模块 ORM
│   │   ├── history.py        # 历史模块 ORM
│   │   ├── life.py           # 生活模块 ORM
│   │   ├── necessity.py      # 物资模块 ORM
│   │   ├── project.py        # 项目模块 ORM
│   │   ├── text.py           # 文本模块 ORM
│   └── external/             # [预留] 外部服务集成
│       └── __init__.py
│
├── service/                   # 服务层 (Infrastructure Layer)
│   ├── character_detector.py # 角色检测服务
│   ├── character_profiler.py # 角色画像服务
│   ├── extraction_cache.py   # 提取缓存服务
│   ├── outline_extractor.py  # 大纲提取服务
│   ├── range_selector.py     # 范围选择服务
│   └── setting_extractor.py  # 设定提取服务
│
├── utils/                     # 工具层 (Infrastructure Layer)
│   ├── __init__.py
│   ├── db_utils.py           # 数据库工具
│   ├── env.py                # 环境变量管理
│   ├── finance_helpers.py    # 财务辅助函数
│   ├── image.py              # 图像处理
│   ├── jsonb.py              # JSONB 类型处理
│   ├── logging_config.py     # 日志配置
│   ├── money.py              # 货币处理
│   ├── sampler.py            # 采样工具
│   ├── state.py              # 状态管理
│   ├── time_utils.py         # 时间工具
│   ├── websocket_manager.py  # WebSocket 管理
│   ├── llm/                  # LLM 相关工具
│   │   ├── __init__.py
│   │   ├── available_providers.py  # 可用 Provider 配置
│   │   ├── client.py               # LLM 客户端
│   │   ├── gateway.py              # LLM 网关
│   │   ├── pricing.py              # 价格计算
│   │   ├── prompts.py              # 提示词模板
│   │   ├── retry_handler.py        # 重试处理
│   │   └── providers/              # Provider 实现
│   │       ├── __init__.py
│   │       ├── anthropic_provider.py
│   │       ├── base.py
│   │       ├── deepseek_provider.py
│   │       ├── google_provider.py
│   │       ├── moonshot_provider.py
│   │       └── openai_provider.py
│   └── stat/                 # 统计工具
│       ├── __init__.py
│       └── regression.py     # 回归分析
│
├── cli/                       # 命令行工具
│   ├── __init__.py
│   └── text_import.py        # 文本导入 CLI
│
├── db.py                      # 数据库连接管理
├── exception_handlers.py      # 异常处理器
└── sample_client.py          # 示例客户端
```

## 各层职责与约束

### 1. Router 层 (路由层)

**职责：**
- 定义 API 端点路径
- 配置依赖注入 (Provide)
- 绑定 HTTP 方法与 Controller

**约束：**
- ❌ 禁止包含业务逻辑
- ❌ 禁止直接操作数据库
- ✅ 仅负责路由配置和 Controller 聚合

**示例：**
```python
from litestar import Router
from litestar.di import Provide
from sail_server.controller.text import WorkController
from sail_server.db import get_db_dependency

router = Router(
    path="/text",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[WorkController, ...],
)
```

### 2. Controller 层 (控制器层)

**职责：**
- 处理 HTTP 请求/响应
- 参数校验与转换
- 调用 Model 层执行业务逻辑

**约束：**
- ❌ 禁止直接操作 ORM 模型
- ❌ 禁止直接执行 SQL
- ✅ 使用 DTO 进行数据交换
- ✅ 通过依赖注入获取数据库会话

**示例：**
```python
from litestar import Controller, get
from sqlalchemy.orm import Session

class WorkController(Controller):
    path = "/works"
    
    @get("/")
    async def list_works(
        self,
        router_dependency: Session,  # 依赖注入
        skip: int = 0,
        limit: int = 20
    ) -> WorkListResponse:
        # 调用 Model 层
        works = get_works_impl(router_dependency, skip, limit)
        return WorkListResponse(works=works, total=len(works))
```

### 3. Application/DTO 层 (数据传输对象)

**职责：**
- 定义请求/响应数据结构
- 数据验证与序列化

**约束：**
- ✅ 使用 Pydantic BaseModel
- ✅ 配置 `ConfigDict(from_attributes=True)` 支持 ORM 转换
- ❌ 禁止包含业务逻辑

**示例：**
```python
from pydantic import BaseModel, Field, ConfigDict

class WorkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(description="作品ID")
    title: str = Field(description="作品标题")
    created_at: datetime = Field(description="创建时间")
```

### 4. Model 层 (领域模型层)

**职责：**
- 实现核心业务逻辑
- 定义领域规则与计算
- 协调 DAO 完成数据持久化

**约束：**
- ✅ 接收数据库会话作为参数
- ✅ 返回 DTO 对象
- ❌ 禁止直接处理 HTTP 相关逻辑
- ❌ 禁止直接操作 ORM (通过 DAO)

**示例：**
```python
def create_work_impl(db: Session, work_data: WorkCreateRequest) -> WorkResponse:
    """创建作品"""
    work = Work(...)  # ORM 对象
    db.add(work)
    db.commit()
    db.refresh(work)
    return WorkResponse.model_validate(work)
```

### 5. Agent 层 (智能体层)

**职责：**
- 封装 LLM 任务执行逻辑
- 提供统一的 Agent 接口

**约束：**
- ✅ 继承 `BaseAgent`
- ✅ 实现 `execute`, `estimate_cost`, `validate_task` 方法
- ✅ 使用 `AgentContext` 获取依赖

**示例：**
```python
from sail_server.agent import BaseAgent, AgentContext

class MyAgent(BaseAgent):
    @property
    def agent_type(self) -> str:
        return "my_agent"
    
    async def execute(self, task, context: AgentContext, callback=None):
        # 使用 context.llm_gateway 调用 LLM
        # 使用 context.db_session 访问数据库
        pass
```

### 6. Data Access 层 (数据访问层)

**职责：**
- 封装数据库访问逻辑
- 提供通用的 CRUD 接口

**约束：**
- ✅ 继承 `BaseDAO[T]`
- ✅ 使用泛型指定 ORM 类型
- ✅ 封装复杂查询逻辑
- ❌ 禁止包含业务逻辑

**示例：**
```python
from sail_server.data.dao.base import BaseDAO
from sail_server.infrastructure.orm.text import Work

class WorkDAO(BaseDAO[Work]):
    def __init__(self, db: Session):
        super().__init__(db, Work)
    
    def find_by_slug(self, slug: str) -> Optional[Work]:
        return self.db.query(Work).filter(Work.slug == slug).first()
```

### 7. Infrastructure/ORM 层 (基础设施层)

**职责：**
- 定义数据库表结构
- 配置 ORM 关系映射

**约束：**
- ✅ 继承 `ORMBase`
- ✅ 仅包含字段定义和关系配置
- ❌ 禁止包含业务逻辑
- ❌ 禁止包含数据验证逻辑

**示例：**
```python
from sail_server.infrastructure.orm.orm_base import ORMBase

class Work(ORMBase):
    __tablename__ = "works"
    
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    # ... 字段定义
```

### 8. Service 层 (服务层)

**职责：**
- 提供领域无关的通用服务
- 封装复杂算法或外部调用

**约束：**
- ✅ 纯函数或状态less 类
- ✅ 不依赖数据库会话
- ✅ 可独立测试

## 数据流向

```
HTTP Request
    ↓
Router (路径匹配)
    ↓
Controller (参数校验)
    ↓
DTO (数据转换)
    ↓
Model (业务逻辑)
    ↓
DAO (数据访问)
    ↓
ORM (SQL 生成)
    ↓
PostgreSQL
    ↓
ORM (结果映射)
    ↓
DAO (对象返回)
    ↓
Model (DTO 封装)
    ↓
Controller (响应构建)
    ↓
Router (序列化)
    ↓
HTTP Response
```

## 模块状态

| 模块 | 状态 | 说明 |
|------|------|------|
| text (文本管理) | ✅ 完整 | Work/Edition/DocumentNode CRUD, 文本导入 |
| finance (财务管理) | ✅ 完整 | 账户、交易、预算管理 |
| necessity (物资管理) | ✅ 完整 | 物品、库存、住所、行程 |
| project (项目管理) | ✅ 完整 | 任务板、任务管理 |
| health (健康管理) | 🔶 部分 | 体重追踪基础功能 |
| history (历史记录) | ✅ 完整 | 时间线事件追踪 |

## 扩展指南

### 添加新模块

1. **定义 ORM 模型** (`infrastructure/orm/<module>.py`)
2. **定义 DTO** (`application/dto/<module>.py`)
3. **实现 DAO** (`data/dao/<module>.py`)
4. **实现 Model** (`model/<module>.py`)
5. **实现 Controller** (`controller/<module>.py`)
6. **配置 Router** (`router/<module>.py`)
7. **注册路由** (`server.py`)

### 添加新 Agent

1. **继承 BaseAgent** (`agent/<new_agent>.py`)
2. **实现抽象方法** (`execute`, `estimate_cost`, `validate_task`)
3. **自动注册** (通过 `agent/__init__.py` 的 `auto_register_agents`)

### 代码规范

- **文件头**：所有 Python 文件必须包含标准文件头
```python
# -*- coding: utf-8 -*-
# @file filename.py
# @brief 简要描述
# @author sailing-innocent
# @date YYYY-MM-DD
# @version 1.0
# ---------------------------------
```

- **类型提示**：鼓励使用类型提示
- **日志**：使用 `sail_server.utils.logging_config.get_logger`
- **LLM**：使用 `sail.llm.available_providers` 中的默认配置

## 依赖关系

```
Router → Controller → Model → DAO → ORM
  ↓         ↓          ↓      ↓
Provide   DTO        Agent   Database
```

## 环境配置

- `POSTGRE_URI`: 数据库连接字符串
- `LOG_MODE`: 日志模式 (prod/dev/debug)
- `API_ENDPOINT`: API 前缀 (默认 /api/v1)
- `SITE_DIST`: 前端静态文件目录

## 运行方式

```bash
# 开发模式
uv run server.py --dev

# 生产模式
uv run server.py

# 调试模式
uv run server.py --debug
```
