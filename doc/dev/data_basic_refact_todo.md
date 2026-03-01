# SailZen 数据层系统性重构方案

> **文档状态**: Phase 1 完成，Phase 2 进行中  
> **创建日期**: 2026-03-01  
> **目标版本**: 0.3.0  
> **关联文档**: [AGENTS.md](../../AGENTS.md), [PRD](../../PRD.md)

---

## 1. 现状分析

### 1.1 当前架构概览

```
sail_server/data/           # 数据层（当前：DTO + ORM 混合）
├── analysis.py             # 60 dataclasses + 13 ORM 类（问题最严重）
├── finance.py              # 4 dataclasses + 4 ORM 类
├── health.py               # 8 dataclasses + 4 ORM 类
├── necessity.py            # 9 dataclasses + 9 ORM 类
├── project.py              # 2 dataclasses + 2 ORM 类
├── text.py                 # 8 dataclasses + 4 ORM 类
├── history.py              # 1 dataclass + 1 ORM 类
├── life.py                 # 1 dataclass + 1 ORM 类
├── unified_agent.py        # 5 dataclasses + 3 ORM 类
├── types.py                # 数据库类型定义
└── orm.py                  # ORMBase 定义
```

### 1.2 核心问题

| 问题类别 | 描述 | 影响文件 | 严重程度 |
|---------|------|---------|---------|
| **命名冲突** | `TextEvidence` 同时作为 dataclass 和 ORM 类 | `analysis.py` | 🔴 高 |
| **重复定义** | 同一 dataclass 在文件中定义两次 | `analysis.py` (6个类) | 🔴 高 |
| **文件过大** | `analysis.py` 1557+ 行，职责过多 | `analysis.py` | 🟡 中 |
| **类型混淆** | Pylance 无法区分 DTO 和 ORM | 多个文件 | 🟡 中 |
| **混合模式** | 部分模块清晰，部分混乱 | 不一致 | 🟡 中 |

### 1.3 重复定义详情（analysis.py）

以下 dataclass 在 `analysis.py` 中定义了两次：

| 类名 | 第一处位置 | 第二处位置 | 用途差异 |
|-----|-----------|-----------|---------|
| `AnalysisTaskData` | 第255行 | 第696行 | 兼容旧格式 / 新格式 |
| `AnalysisResultData` | 第289行 | 第741行 | 兼容旧格式 / 新格式 |
| `CharacterData` | 第372行 | 第781行 | 兼容旧格式 / 新格式 |
| `CharacterAliasData` | 第409行 | 第834行 | 兼容旧格式 / 新格式 |
| `CharacterAttributeData` | 第429行 | 第860行 | 兼容旧格式 / 新格式 |
| `CharacterRelationData` | 第481行 | 第892行 | 兼容旧格式 / 新格式 |

### 1.4 当前数据流

```
Router → Controller → Model/DAO → Data Layer
              ↓
         DataclassDTO (Litestar)
              ↓
    请求/响应序列化 (dataclass)
```

**优点**:
- Litestar 原生支持 dataclass
- DTOConfig 灵活控制字段
- 类型安全

**缺点**:
- dataclass 和 ORM 类同文件，职责不清
- 命名冲突导致类型检查错误
- 大型文件难以维护

---

## 2. 目标架构

### 2.1 分层架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  API Layer (Router/Controller)                              │
│  - Pydantic DTOs (请求/响应验证)                             │
│  - Litestar DTO 配置                                         │
├─────────────────────────────────────────────────────────────┤
│  Service Layer (可选)                                        │
│  - 复杂业务逻辑编排                                          │
│  - 事务管理                                                  │
├─────────────────────────────────────────────────────────────┤
│  Model/DAO Layer                                            │
│  - 数据访问对象 (DAO)                                        │
│  - ORM 操作封装                                              │
│  - DTO ↔ ORM 转换                                           │
├─────────────────────────────────────────────────────────────┤
│  Data Access Layer (Repository)                             │
│  - SQLAlchemy ORM 模型 (仅数据库操作)                         │
│  - 数据库迁移 (Alembic)                                      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构重构

```
sail_server/
├── domain/                      # 领域层 (可选，复杂业务)
│   ├── __init__.py
│   └── analysis/               # 分析领域逻辑
│
├── application/                 # 应用层 (可选)
│   ├── __init__.py
│   └── dto/                    # Pydantic DTOs
│       ├── __init__.py
│       ├── analysis.py         # 分析模块 DTOs
│       ├── finance.py
│       └── ...
│
├── infrastructure/              # 基础设施层
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py       # 数据库连接管理
│   │   └── migrations/         # Alembic 迁移文件
│   └── orm/                    # ORM 模型 (原 data/)
│       ├── __init__.py
│       ├── base.py             # ORMBase
│       ├── analysis/           # 按模块拆分
│       │   ├── __init__.py
│       │   ├── outline.py      # Outline, OutlineNode...
│       │   ├── character.py    # Character, CharacterAlias...
│       │   ├── setting.py      # Setting, SettingAttribute...
│       │   ├── evidence.py     # TextEvidence
│       │   └── task.py         # AnalysisTask, AnalysisResult
│       ├── finance.py
│       ├── health.py
│       ├── necessity.py
│       ├── project.py
│       ├── text.py
│       ├── history.py
│       └── unified_agent.py
│
├── data/                        # 数据访问层 (DAO)
│   ├── __init__.py
│   ├── dao/                    # DAO 实现
│   │   ├── __init__.py
│   │   ├── base.py             # BaseDAO
│   │   ├── analysis.py         # AnalysisDAO
│   │   ├── finance.py
│   │   └── ...
│   └── dto/                    # 内部数据传输对象
│       ├── __init__.py
│       └── ...
│
└── model/                       # 业务逻辑层 (保留)
    └── ...
```

### 2.3 命名规范

| 层级 | 命名模式 | 示例 |
|-----|---------|------|
| ORM 模型 | 名词（单数） | `Character`, `Outline`, `TextEvidence` |
| Pydantic DTO (Request) | `*Request` | `CharacterCreateRequest`, `OutlineUpdateRequest` |
| Pydantic DTO (Response) | `*Response` | `CharacterResponse`, `OutlineListResponse` |
| DAO 类 | `*DAO` | `CharacterDAO`, `OutlineDAO` |
| Service 类 | `*Service` | `AnalysisService`, `CharacterService` |
| 内部 DTO | `*DTO` 或 `*Data` | `CharacterDTO` (内部使用) |

---

## 3. 重构任务清单

### Phase 1: 紧急修复 (v0.2.5) ✅ 已完成

**目标**: 解决命名冲突和重复定义，消除 Pylance 错误

**完成日期**: 2026-03-01

**修改摘要**:
- 修复了 `TextEvidence` 命名冲突（DTO 重命名为 `TextEvidenceDTO`，ORM 保留为 `TextEvidenceORM`）
- 合并了重复的 dataclass（`AnalysisTaskData`, `AnalysisResultData`, `CharacterData` 等）
- 添加了向后兼容的别名导出
- 所有 34 个 server 测试通过

**修改文件**:
- `sail_server/data/analysis.py` - 主要修改
- `sail_server/model/analysis/evidence.py` - 更新导入
- `sail_server/controller/analysis.py` - 更新导入
- `sail_server/router/analysis_compat.py` - 更新导入
- `tests/server/test_evidence_api.py` - 更新导入

**新的导入方式**:
```python
# 推荐：明确使用 DTO
from sail_server.data.analysis import TextEvidenceDTO

# 向后兼容：TextEvidence 现在是 DTO 的别名
from sail_server.data.analysis import TextEvidence  # 等同于 TextEvidenceDTO

# ORM 类
from sail_server.data.analysis import TextEvidenceORM
```

---

### Phase 2: ORM 模型拆分 (v0.2.6) ✅ 已完成

**目标**: 将 ORM 模型从 `data/` 层拆分出来

**完成日期**: 2026-03-01

**修改摘要**:
- 创建了新的 ORM 目录结构 `sail_server/infrastructure/orm/`
- 迁移了所有模块的 ORM 类：
  - `analysis` - 大纲、人物、设定、证据
  - `health` - 体重、身体尺寸、运动、体重计划
  - `text` - 作品、版本、文档节点、导入任务
  - `project` - 项目、任务
  - `necessity` - 住所、容器、物品、库存、行程
  - `history` - 历史事件
  - `life` - 服务账户
  - `unified_agent` - 统一任务、步骤、事件
- 保持原文件中的 ORM 类定义（向后兼容）
- 所有测试通过

**新建文件**:
- `sail_server/infrastructure/orm/` - ORM 模型包
  - `analysis/` - 分析模块（outline, character, setting, evidence, task）
  - `health.py` - 健康模块
  - `text.py` - 文本模块
  - `project.py` - 项目模块
  - `necessity.py` - 物资模块
  - `history.py` - 历史模块
  - `life.py` - 生活服务模块
  - `unified_agent.py` - 统一 Agent 模块

**新的导入方式**:
```python
# 推荐：从新位置导入 ORM 模型
from sail_server.infrastructure.orm import (
    # analysis
    Outline, Character, Setting, TextEvidence,
    # health
    Weight, BodySize, Exercise, WeightPlan,
    # text
    Work, Edition, DocumentNode,
    # project
    Project, Mission,
    # necessity
    Item, Inventory, Journey,
    # ... 其他模型
)

# 向后兼容：仍然可以从原位置导入
from sail_server.data.analysis import Character, Setting
from sail_server.data.health import Weight, BodySize
# ... 其他原位置导入
```

**注意事项**:
- 原文件中的 ORM 类定义暂时保留，确保向后兼容
- 新的代码建议从 `infrastructure.orm` 导入
- 在 Phase 5 完成后，将移除原文件中的 ORM 类定义

---

### Phase 3: DTO Pydantic 化 (v0.2.7) ✅ 已完成

**目标**: 将 dataclass DTOs 迁移到 Pydantic

**完成日期**: 2026-03-01

**修改摘要**:
- 创建了 Pydantic DTO 目录 `sail_server/application/dto/`
- 为所有主要模块创建了 Pydantic DTOs
- 使用 Pydantic v2 的 `BaseModel` + `ConfigDict(from_attributes=True)`
- 所有测试通过

**新建文件**:
- `sail_server/application/__init__.py`
- `sail_server/application/dto/__init__.py`
- `sail_server/application/dto/finance.py` - Account, Transaction, Budget DTOs
- `sail_server/application/dto/health.py` - Weight, BodySize, Exercise, WeightPlan DTOs
- `sail_server/application/dto/text.py` - Work, Edition, DocumentNode, IngestJob DTOs
- `sail_server/application/dto/analysis.py` - Task, Character, Outline, Evidence DTOs

**Pydantic DTO 特点**:
- 使用 `BaseModel` 替代 `@dataclass`
- `ConfigDict(from_attributes=True)` 支持从 ORM 对象创建
- `Field()` 提供丰富的字段定义（描述、默认值、验证）
- 内置 JSON 序列化支持

**新的导入方式**:
```python
# 新的 Pydantic DTOs
from sail_server.application.dto.finance import (
    AccountCreateRequest, AccountResponse, AccountListResponse
)
from sail_server.application.dto.analysis import (
    CharacterCreateRequest, CharacterResponse
)

# 旧的 dataclass DTOs 仍然可用（向后兼容）
from sail_server.data.finance import AccountData
from sail_server.data.analysis import CharacterData
```

**注意事项**:
- Pydantic DTOs 目前与 dataclass DTOs 并存
- 在 Phase 4/5 中，controller 将逐步迁移到使用 Pydantic DTOs
- Pydantic DTOs 提供更好的 API 文档生成和请求验证

### Phase 4: DAO 层提取 (v0.2.8) ✅ 已完成

**目标**: 将数据访问逻辑从 Model 层提取到 DAO 层

**完成日期**: 2026-03-01

**修改摘要**:
- 创建了 DAO 基类 `BaseDAO`，提供通用 CRUD 操作
- 实现了所有模块的 DAO：
  - `analysis` - CharacterDAO, OutlineDAO, SettingDAO, TextEvidenceDAO 等
  - `finance` - AccountDAO, TransactionDAO, BudgetDAO, BudgetItemDAO
  - `health` - WeightDAO, BodySizeDAO, ExerciseDAO, WeightPlanDAO
  - `text` - WorkDAO, EditionDAO, DocumentNodeDAO, IngestJobDAO
  - `project` - ProjectDAO, MissionDAO
  - `necessity` - ItemDAO, InventoryDAO, JourneyDAO 等
  - `history` - HistoryEventDAO
  - `life` - ServiceAccountDAO
  - `unified_agent` - UnifiedAgentTaskDAO, UnifiedAgentStepDAO, UnifiedAgentEventDAO
- 所有测试通过

**新建文件**:
- `sail_server/data/dao/__init__.py`
- `sail_server/data/dao/base.py` - DAO 基类
- `sail_server/data/dao/analysis.py` - 分析 DAO
- `sail_server/data/dao/finance.py` - 财务 DAO
- `sail_server/data/dao/health.py` - 健康 DAO
- `sail_server/data/dao/text.py` - 文本 DAO
- `sail_server/data/dao/project.py` - 项目 DAO
- `sail_server/data/dao/necessity.py` - 物资 DAO
- `sail_server/data/dao/history.py` - 历史 DAO
- `sail_server/data/dao/life.py` - 生活服务 DAO
- `sail_server/data/dao/unified_agent.py` - 统一 Agent DAO

**DAO 基类功能**:
- `get_by_id()` - 通过 ID 获取
- `get_all()` - 分页获取所有
- `create()` / `create_many()` - 创建单条/批量
- `update()` - 更新
- `delete()` / `delete_many()` - 删除单条/批量
- `count()` - 统计
- `exists()` - 检查存在
- `filter_by()` - 条件查询

**具体 DAO 功能示例**:
- `CharacterDAO`: `get_by_edition()`, `get_with_relations()`, `search_by_name()`
- `OutlineDAO`: `get_by_edition()`, `get_with_nodes()`
- `TextEvidenceDAO`: `get_by_edition()`, `get_by_node()`, `get_by_target()`, `count_by_target_type()`
- `WorkDAO`: `get_by_slug()`, `search_by_title()`
- `ProjectDAO`: `get_active_projects()`, `get_by_state()`

**使用示例**:
```python
from sail_server.data.dao import CharacterDAO, TextEvidenceDAO

def get_character_with_evidence(db: Session, character_id: int):
    # 使用 DAO 获取数据
    char_dao = CharacterDAO(db)
    evidence_dao = TextEvidenceDAO(db)
    
    character = char_dao.get_by_id(character_id)
    evidences = evidence_dao.get_by_target("character", character_id)
    
    return character, evidences
```

**注意事项**:
- DAO 返回 ORM 对象，业务逻辑层负责转换为 DTO
- Model 层的 `*_impl` 函数可以逐步迁移到使用 DAO
- DAO 支持依赖注入，便于测试

### Phase 5: 清理和优化 (v0.3.0)

**目标**: 清理旧代码，完善文档

- [ ] **Task 5.1**: 删除旧的 `data/analysis.py`
  - 确保所有导入已迁移
  - 删除文件
  - **文件**: 删除

- [ ] **Task 5.2**: 统一导入路径
  - 创建清晰的公共 API
  - 更新 `__init__.py` 文件
  - **文件**: 多个

- [ ] **Task 5.3**: 更新文档
  - 更新 AGENTS.md 中的架构说明
  - 更新开发文档
  - **文件**: `AGENTS.md`, 其他文档

---

## 4. 技术选型决策

### 4.1 DTO 技术选型

| 方案 | 优点 | 缺点 | 决策 |
|-----|------|------|------|
| **保持 dataclass** | 改动小，Litestar 原生支持 | 验证能力弱，无自动生成 OpenAPI | ❌ 不采用 |
| **Pydantic v2** | 验证强，Litestar 支持，OpenAPI | 需要迁移工作 | ✅ **采用** |
| **msgspec** | 性能最好 | 生态小，Litestar 支持有限 | ❌ 不采用 |

### 4.2 ORM 技术选型

| 方案 | 优点 | 缺点 | 决策 |
|-----|------|------|------|
| **保持 SQLAlchemy 2.0** | 成熟，团队熟悉 | 需要手动维护 DTO | ✅ **采用** |
| **SQLModel** | Pydantic + SQLAlchemy 结合 | 较新，需要大面积重构 | ❌ 不采用 |
| **Pydantic + async ORM** | 现代化 | 学习成本，迁移工作大 | ❌ 不采用 |

### 4.3 目录结构决策

采用 **渐进式重构**，不一次性改变太多：

```
# 当前结构（保持）
sail_server/
├── data/              # 逐步迁移后删除
├── model/             # 保留，专注业务逻辑
├── controller/        # 保留
└── router/            # 保留

# 新增结构
sail_server/
├── application/       # 新增：Pydantic DTOs
├── infrastructure/    # 新增：ORM 模型
└── domain/            # 可选：复杂领域逻辑
```

---

## 5. 风险与缓解

| 风险 | 影响 | 可能性 | 缓解措施 |
|-----|------|--------|---------|
| 重构引入 Bug | 高 | 中 | 1. 每个 Phase 后全面测试<br>2. 保持向后兼容<br>3. 小步提交 |
| 性能下降 | 中 | 低 | 1. Pydantic v2 性能已优化<br>2. 基准测试对比<br>3. 必要时优化 |
| 开发进度延迟 | 中 | 中 | 1. 分 Phase 实施<br>2. 优先修复紧急问题<br>3. 可跳过非关键任务 |
| 团队适应成本 | 低 | 低 | 1. 完善文档<br>2. Code Review 指导<br>3. 保持命名一致 |

---

## 6. 测试策略

### 6.1 每个 Phase 的测试要求

- **单元测试**: 所有 DTO/DAO/Model 类
- **集成测试**: API 端到端测试
- **数据库测试**: 迁移脚本测试
- **性能测试**: 关键 API 响应时间对比

### 6.2 测试文件位置

```
tests/
├── unit/
│   ├── infrastructure/     # ORM 模型测试
│   ├── application/        # DTO 测试
│   └── data/               # DAO 测试
├── integration/
│   └── api/                # API 集成测试
└── migration/              # 数据库迁移测试
```

---

## 7. 实施时间线

```
Week 1-2:  Phase 1 (紧急修复)
Week 3-4:  Phase 2 (ORM 拆分)
Week 5-6:  Phase 3 (DTO Pydantic 化)
Week 7-8:  Phase 4 (DAO 层提取)
Week 9-10: Phase 5 (清理优化)
```

---

## 8. 参考资源

- [Pydantic v2 文档](https://docs.pydantic.dev/)
- [SQLAlchemy 2.0 文档](https://docs.sqlalchemy.org/)
- [Litestar DTO 文档](https://docs.litestar.dev/2/usage/dto.html)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [DDD 分层架构](https://ddd-practitioners.com/layered-architecture)

---

## 9. 附录

### 9.1 当前命名冲突完整列表

```python
# sail_server/data/analysis.py

# 冲突 1: TextEvidence
@dataclass
class TextEvidence: ...       # 第186行 (DTO)

class TextEvidence(ORMBase): ...  # 第1503行 (ORM)

# 冲突 2-7: 重复定义的 dataclass
# AnalysisTaskData, AnalysisResultData, CharacterData,
# CharacterAliasData, CharacterAttributeData, CharacterRelationData
```

### 9.2 建议的导入路径映射

| 当前导入 | 新导入 (Phase 2 后) | 新导入 (Phase 3 后) |
|---------|-------------------|-------------------|
| `from sail_server.data.analysis import TextEvidence` | `from sail_server.infrastructure.orm.analysis.evidence import TextEvidence` | `from sail_server.application.dto.analysis.evidence import TextEvidenceResponse` |
| `from sail_server.data.finance import Account` | `from sail_server.infrastructure.orm.finance import Account` | (不变) |
| `from sail_server.data.finance import AccountData` | `from sail_server.data.finance import AccountData` | `from sail_server.application.dto.finance import AccountResponse` |

---

**文档维护**: 此文档应在每个 Phase 完成后更新，记录实际进展和遇到的问题。
