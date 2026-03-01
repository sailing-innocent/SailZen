# SailZen 产品需求文档 (PRD)

> **版本**: v2.0  
> **更新日期**: 2026-03-01  
> **状态**: 持续迭代中  
> **目标用户**: 个人用户、小说创作者、知识管理者

---

## 1. 产品概述

### 1.1 产品定位

SailZen 是面向个人用户的**全方位生活管理与AI辅助创作平台**，整合：
- **生活管理**: 财务追踪、健康监控、项目规划、物资管理
- **知识管理**: 层级化笔记系统、文本内容管理
- **AI辅助创作**: 小说分析、大纲提取、人物档案、设定管理

### 1.2 核心价值主张

| 价值维度 | 描述 |
|----------|------|
| **数据主权** | 本地优先部署，用户完全拥有数据 |
| **AI增强** | LLM辅助分析，人机协作 workflow |
| **一体化** | 生活、工作、创作场景全覆盖 |
| **可扩展** | 模块化架构，支持功能按需扩展 |

### 1.3 目标用户画像

```
┌─────────────────────────────────────────────────────────────────┐
│                        目标用户群体                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 知识工作者 (Knowledge Workers)                              │
│     • 需要管理大量文本、笔记、项目                              │
│     • 重视数据隐私和本地化                                      │
│     • 使用场景: 笔记管理、项目管理                              │
│                                                                 │
│  2. 小说创作者 (Novelists)                                      │
│     • 需要构建复杂的世界观和人物体系                            │
│     • 需要AI辅助分析和创作                                      │
│     • 使用场景: 大纲提取、人物档案、设定管理                    │
│                                                                 │
│  3. 个人管理者 (Personal Managers)                              │
│     • 需要系统化管理个人财务、健康、物资                        │
│     • 追求效率和数据可视化                                      │
│     • 使用场景: 记账、体重追踪、库存管理                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 系统架构

### 2.1 技术栈

| 组件 | 技术栈 | 说明 |
|------|--------|------|
| **sail_server** | Python 3.13 + Litestar + PostgreSQL | 后端API服务 |
| **site** | React 19 + TypeScript + Vite + Tailwind CSS 4 | Web前端 |
| **vscode_plugin** | TypeScript + VSCode API | VSCode笔记插件 |
| **AI引擎** | Google Gemini / OpenAI / Moonshot | LLM提供商 |

### 2.2 部署架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户设备                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Web Browser   │  │  VSCode Plugin  │  │   Mobile (TBD)  │ │
│  │   (site)        │  │  (vscode_plugin)│  │                 │ │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────┘ │
│           │                    │                               │
│           └────────────────────┘                               │
│                     │                                          │
│           ┌─────────▼─────────┐                                │
│           │   Local Server    │                                │
│           │  (sail_server)    │                                │
│           │  • Litestar API   │                                │
│           │  • PostgreSQL     │                                │
│           │  • AI Integration │                                │
│           └───────────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 功能模块详细需求

### 3.1 财务管理 (Finance Management)

#### 3.1.1 功能概述
全面个人财务管理，支持多账户、多币种、预算规划。

#### 3.1.2 核心功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **账户管理** | 多账户CRUD、余额追踪、资产统计 | P0 |
| **交易记录** | 收支记录、分类标签、批量导入 | P0 |
| **预算规划** | 预算模板、执行监控、超期预警 | P1 |
| **财务报表** | 收支分析、趋势图表、年度统计 | P1 |

#### 3.1.3 数据模型

```typescript
// 账户
interface Account {
  id: string
  name: string
  type: 'checking' | 'savings' | 'credit' | 'investment' | 'cash'
  currency: string
  initial_balance: number
  current_balance: number
  is_active: boolean
}

// 交易
interface Transaction {
  id: string
  account_id: string
  amount: number
  currency: string
  type: 'income' | 'expense' | 'transfer'
  category?: string
  tags: string[]
  description?: string
  transaction_date: string
}

// 预算
interface Budget {
  id: string
  name: string
  period: 'monthly' | 'yearly' | 'custom'
  amount: number
  categories: BudgetCategory[]
  consumed: number
  status: 'active' | 'paused' | 'completed'
}
```

---

### 3.2 项目管理 (Project Management)

#### 3.2.1 功能概述
项目与任务的全生命周期管理，支持状态机工作流。

#### 3.2.2 核心功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **项目管理** | CRUD、状态流转、进度追踪 | P0 |
| **任务管理** | 子任务、截止日期、优先级 | P0 |
| **看板视图** | 拖拽式状态管理、甘特图(TBD) | P1 |
| **提醒通知** | 到期提醒、逾期告警 | P1 |

#### 3.2.3 状态机定义

```
项目状态 (7状态):
  NOT_STARTED → IN_PROGRESS → [PAUSED] → COMPLETED
       │             │                      │
       └─────────────┴──────────────────────┘
                         │
                    CANCELLED

任务状态 (5状态):
  TODO → DOING → DONE
   │             │
   └─────────────┘
        │
   CANCELLED
```

---

### 3.3 健康管理 (Health Management)

#### 3.3.1 功能概述
个人健康数据追踪与分析，支持体重趋势和计划管理。

#### 3.3.2 核心功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **体重记录** | 体重录入、BMI计算、趋势图 | P0 |
| **目标管理** | 目标体重、达成预测 | P1 |
| **健身追踪** | 运动记录、消耗估算 (TBD) | P2 |
| **健康计划** | 饮食计划、运动计划 (TBD) | P2 |

#### 3.3.3 AI能力规划
- 体重趋势预测
- 健康建议生成
- 异常数据提醒

---

### 3.4 物资管理 (Necessity Management)

#### 3.4.1 功能概述
多住所物资定位与库存追踪，支持旅程携带物品管理。

#### 3.4.2 核心功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **住所管理** | 多住所CRUD | P0 |
| **容器管理** | 房间/柜子/箱子等容器层级 | P0 |
| **物品管理** | 物品CRUD、分类标签、位置追踪 | P0 |
| **库存预警** | 低库存提醒、过期提醒 | P1 |
| **旅程管理** | 行程规划、携带物品清单 | P1 |

---

### 3.5 文本管理 (Text Management)

#### 3.5.1 功能概述
长篇文本的结构化管理，支持作品、版本、章节层级。

#### 3.5.2 核心功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **作品管理** | 作品CRUD、元数据管理 | P0 |
| **版本管理** | 多版本支持、版本对比 | P0 |
| **章节管理** | 层级章节、排序索引 | P0 |
| **文本导入** | AI辅助分章、编码检测 | P1 |
| **内容搜索** | 全文搜索、标签过滤 | P1 |

---

### 3.6 AI文本分析系统 (Text Analysis) ⭐

#### 3.6.1 功能概述
基于LLM的智能文本分析系统，支持大纲提取、人物检测、设定提取等。

#### 3.6.2 核心分析功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **大纲提取** | 从文本提取情节结构、转折点 | P0 |
| **人物检测** | 识别人物、提取属性、追踪弧光 | P0 |
| **设定提取** | 提取世界观设定元素 | P0 |
| **关系分析** | 人物/设定间关系图谱 | P1 |
| **一致性检查** | 设定冲突检测、时间线验证 | P1 |
| **文本证据** | 分析结果关联原文证据 | P1 |

#### 3.6.3 AI Workflow 设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI 分析工作流 (4阶段)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: 范围选择 (Range Selection)                            │
│  ├─ 单章/连续章节/多选/全文/自定义范围                          │
│  ├─ Token预算预估                                               │
│  └─ 上下文构建 (Context Engineering)                            │
│                                                                 │
│  Phase 2: 任务配置 (Task Configuration)                         │
│  ├─ 分析类型选择 (大纲/人物/设定/关系)                          │
│  ├─ 粒度配置 (幕/弧/场景/节拍)                                  │
│  ├─ LLM提供商选择                                               │
│  └─ 提示词模板选择                                              │
│                                                                 │
│  Phase 3: AI 执行 (AI Execution)                                │
│  ├─ 文本分块 (Chunking)                                         │
│  ├─ 并行处理                                                    │
│  ├─ 进度追踪 (实时SSE推送)                                      │
│  ├─ 检查点机制 (断点续传)                                       │
│  └─ 结果合并                                                    │
│                                                                 │
│  Phase 4: 结果审核 (Result Review)                              │
│  ├─ 可视化展示                                                  │
│  ├─ 人工确认/修改                                               │
│  ├─ 证据关联                                                    │
│  └─ 保存到数据库                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.6.4 大纲提取详细需求

**输入**: 选定文本范围  
**输出**: 结构化大纲节点 + 转折点

```typescript
interface OutlineExtractionConfig {
  granularity: 'act' | 'arc' | 'scene' | 'beat'
  outline_type: 'main' | 'subplot' | 'character_arc' | 'theme'
  extract_turning_points: boolean
  extract_characters: boolean
  max_nodes: number
  temperature: number
  llm_provider?: string
  llm_model?: string
}

interface ExtractedOutlineNode {
  id: string
  node_type: 'act' | 'arc' | 'scene' | 'beat'
  title: string
  summary: string
  significance: 'critical' | 'major' | 'normal' | 'minor'
  sort_index: number
  parent_id?: string
  characters?: string[]
  evidence_list: TextEvidence[]
}
```

**异常处理**:
- 超长文本自动分块处理
- API限流自动重试(指数退避)
- 检查点机制支持断点续传
- 失败批次单独重试

#### 3.6.5 人物检测详细需求

**检测阶段**:
1. **初筛**: 识别人名实体，记录出现位置
2. **分类**: 判断角色重要性 (主角/配角/龙套)
3. **画像**: 提取属性 (外貌/性格/背景)
4. **关系**: 分析人物间关系
5. **弧光**: 追踪人物变化轨迹

```typescript
interface CharacterDetectionConfig {
  detect_aliases: boolean
  detect_attributes: boolean
  detect_relations: boolean
  min_confidence: number
  max_characters: number
}

interface DetectedCharacter {
  canonical_name: string
  aliases: { alias: string; alias_type: string }[]
  role_type: 'protagonist' | 'antagonist' | 'deuteragonist' | 'supporting' | 'minor'
  description: string
  attributes: { category: string; key: string; value: string; confidence: number }[]
  relations: { target_name: string; relation_type: string; description?: string }[]
}
```

#### 3.6.6 任务调度系统

**任务生命周期**:
```
PENDING → QUEUED → RUNNING → COMPLETED
   │         │         │
   └─────────┴─────────┴──► FAILED/CANCELLED
```

**执行模式**:
| 模式 | 描述 | 适用场景 |
|------|------|----------|
| `sync` | 同步执行 | 快速分析、小文本 |
| `async` | 异步执行 | 大规模分析 |
| `prompt_only` | 仅生成Prompt | 外部工具处理 |

**进度追踪**:
- SSE(Server-Sent Events) 实时推送
- 检查点持久化支持断线重连
- 批量处理进度百分比

---

### 3.7 笔记知识管理 (Knowledge Management)

#### 3.7.1 功能概述
基于Dendron的层级化笔记系统，支持多Vault工作区。

#### 3.7.2 核心功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **层级笔记** | 点号分隔层级 (e.g., project.idea.note) | P0 |
| **Wiki链接** | [[内部链接]] 支持 | P0 |
| **多Vault** | 多工作区管理 | P1 |
| **Zotero集成** | 文献引用集成 | P2 |

---

### 3.8 历史事件追踪 (History Timeline)

#### 3.8.1 功能概述
时间线事件管理，支持个人历史记录和作品时间线。

#### 3.8.2 核心功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **事件CRUD** | 时间点/时间段事件 | P1 |
| **分类标签** | 事件分类、颜色标记 | P1 |
| **时间线视图** | 可视化时间线展示 | P2 |

---

## 4. AI能力矩阵

### 4.1 LLM集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      LLM 提供商抽象层                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Google    │  │   OpenAI    │  │  Moonshot   │             │
│  │   Gemini    │  │   GPT-4o    │  │  Kimi-K2.5  │             │
│  │             │  │             │  │             │             │
│  │ • 长上下文  │  │ • 能力强    │  │ • 中文优    │             │
│  │ • 速度快    │  │ • 生态丰富  │  │ • 长文本    │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          │                                       │
│         ┌────────────────▼────────────────┐                      │
│         │      Unified LLM Client          │                      │
│         │  • 统一接口                      │                      │
│         │  • 自动降级                      │                      │
│         │  • 错误重试                      │                      │
│         │  • Token管理                     │                      │
│         └─────────────────────────────────┘                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 AI应用场景

| 模块 | AI应用场景 | 状态 |
|------|------------|------|
| **文本分析** | 大纲提取、人物检测、设定提取 | ✅ 已实现 |
| **文本导入** | 智能分章、章节识别 | ✅ 已实现 |
| **财务分析** | 消费分类、异常检测、预算建议 | 📋 规划中 |
| **健康分析** | 趋势预测、健康建议 | 📋 规划中 |
| **项目规划** | 任务拆解、时间估算 | 📋 规划中 |
| **笔记助手** | 自动标签、内容摘要 | 📋 规划中 |

### 4.3 Prompt工程规范

```typescript
// Prompt模板结构
interface PromptTemplate {
  id: string
  name: string
  description: string
  task_type: string
  version: string
  
  // 模板内容
  system_prompt: string
  user_prompt_template: string
  
  // 变量定义
  variables: {
    name: string
    type: 'string' | 'number' | 'array' | 'object'
    required: boolean
    description: string
  }[]
  
  // 输出格式
  output_schema: JSONSchema
  
  // 模型配置
  model_config: {
    preferred_provider: string
    preferred_model: string
    temperature: number
    max_tokens: number
  }
}
```

---

## 5. 用户界面设计

### 5.1 整体布局

```
┌─────────────────────────────────────────────────────────────────┐
│  SailZen                                    [🔍] [🔔] [👤]       │  Header
├──────────┬──────────────────────────────────────────────────────┤
│          │                                                      │
│  📊 仪表盘 │         Main Content Area                          │
│  💰 财务   │                                                      │
│  📋 项目   │         • 功能模块页面                              │
│  🏥 健康   │         • 数据表格/图表                             │
│  📚 文本   │         • 分析工作台                                │
│  🔍 分析   │                                                      │
│  📦 物资   │                                                      │
│  📝 笔记   │                                                      │
│          │                                                      │
│  ────────│                                                      │
│  ⚙️ 设置   │                                                      │
│          │                                                      │
└──────────┴──────────────────────────────────────────────────────┘
   Sidebar
```

### 5.2 响应式设计

| 断点 | 布局调整 |
|------|----------|
| Desktop (≥1280px) | 完整侧边栏 + 多列内容 |
| Tablet (768-1279px) | 可折叠侧边栏 |
| Mobile (<768px) | 底部导航栏 |

---

## 6. 数据模型总览

### 6.1 核心实体关系

```
┌─────────────────────────────────────────────────────────────────┐
│                      核心实体关系图                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User                                                           │
│   │                                                             │
│   ├──► Work (作品)                                              │
│   │      ├──► Edition (版本)                                    │
│   │      │      ├──► DocumentNode (章节)                        │
│   │      │      ├──► Character (人物)                           │
│   │      │      ├──► Setting (设定)                             │
│   │      │      ├──► Outline (大纲)                             │
│   │      │      └──► AnalysisTask (分析任务)                    │
│   │      │                                                        │
│   │      └──► CharacterRelation (人物关系)                      │
│   │                                                                │
│   ├──► Account (财务账户)                                       │
│   │      └──► Transaction (交易记录)                            │
│   │                                                                │
│   ├──► Project (项目)                                           │
│   │      └──► Mission (任务)                                    │
│   │                                                                │
│   ├──► WeightRecord (体重记录)                                  │
│   │                                                                │
│   ├──► Residence (住所)                                         │
│   │      ├──► Container (容器)                                  │
│   │      └──► Item (物品)                                       │
│   │                                                                │
│   └──► HistoryEvent (历史事件)                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 通用字段规范

所有实体应包含以下字段：
```typescript
interface BaseEntity {
  id: string | number        // 唯一标识
  created_at: string         // ISO 8601 时间戳
  updated_at?: string        // 更新时间
  created_by?: string        // 创建者 (多用户支持预留)
  is_deleted?: boolean       // 软删除标记
  meta_data?: Record<string, unknown>  // 扩展元数据
}
```

---

## 7. 非功能性需求

### 7.1 性能需求

| 指标 | 目标值 | 说明 |
|------|--------|------|
| API响应时间 | < 200ms (P95) | 常规CRUD操作 |
| 页面首屏加载 | < 3s | 3G网络环境下 |
| AI分析进度更新 | < 5s 间隔 | SSE推送频率 |
| 并发任务数 | ≥ 5 | 同时运行的AI任务 |

### 7.2 安全需求

- **认证**: JWT Token认证
- **授权**: 基于角色的访问控制 (RBAC预留)
- **数据加密**: 敏感字段加密存储
- **输入验证**: 全量输入参数校验
- **SQL注入防护**: 使用ORM参数化查询

### 7.3 可用性需求

- **可用性**: 99.9% (本地部署无网络依赖)
- **数据备份**: 支持导出/导入
- **错误恢复**: 任务断点续传
- **离线支持**: 部分功能支持离线使用 (TBD)

---

## 8. 路线图 (Roadmap)

### Phase 1: 核心稳固 (当前 - 2026 Q1)
- [x] 财务管理完整实现
- [x] 项目任务核心功能
- [x] 文本管理与分析
- [x] 物资管理基础
- [x] AI大纲提取/人物检测/设定提取
- [ ] 健康管理完善
- [ ] Agent系统统一

### Phase 2: 体验优化 (2026 Q2)
- [ ] 项目管理高级功能（里程碑、日程）
- [ ] 智能日程规划
- [ ] 模块间数据联动
- [ ] 移动端适配
- [ ] 性能优化

### Phase 3: AI增强 (2026 Q3)
- [ ] 智能分析与建议
- [ ] 自然语言交互
- [ ] 个人数据预测模型
- [ ] AI辅助创作 (续写、润色)

### Phase 4: 生态扩展 (2026 Q4)
- [ ] 插件系统
- [ ] 第三方集成
- [ ] 社区模板市场
- [ ] 协作功能 (TBD)

---

## 9. 附录

### 9.1 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 作品 | Work | 一本小说或书籍 |
| 版本 | Edition | 作品的特定版本或译本 |
| 文档节点 | DocumentNode | 章节、卷等文本单元 |
| 大纲节点 | OutlineNode | 情节结构的节点 |
| 设定 | Setting | 世界观设定元素 |
| 人物弧光 | Character Arc | 人物的成长变化轨迹 |
| 文本证据 | Text Evidence | 分析结果的原文依据 |
| 检查点 | Checkpoint | 任务断点续传保存点 |
| Context工程 | Context Engineering | LLM输入上下文构建 |

### 9.2 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 开发指南 | `./dev/README.md` | 环境搭建与开发规范 |
| 测试指南 | `./TESTING.md` | 测试框架与用例 |
| 设计文档 | `./design/` | 各模块详细设计 |
| 架构设计 | `./design/overview.md` | 系统架构总览 |
| 文本分析设计 | `./design/text-analysis-system.md` | AI分析详细设计 |
| 已知问题 | `./KNOWN_ISSUES.md` | 问题追踪 |
| 重构计划 | `./refact_todo.md` | 代码重构计划 |

### 9.3 需求变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| v1.0 | 2026-02 | 初始版本 | AI Agent |
| v2.0 | 2026-03 | 整合AI能力需求、完善模块需求 | AI Agent |

---

*本文档持续更新中，最新版本请以 Git 仓库为准。*
