# SailZen LLM/Agent 功能整合计划

## 1. 当前开发状况

### 1.1 现有架构概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端 (packages/site)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  Agent 页面 (agent.tsx)          小说分析页面 (analysis.tsx)                   │
│  ├─ 任务提交/监控                  ├─ 任务管理 (task_panel.tsx)               │
│  ├─ 实时状态跟踪                   ├─ 人物管理 (character_panel.tsx)          │
│  └─ WebSocket 连接                ├─ 设定管理 (setting_panel.tsx)            │
│                                   └─ 大纲分析 (outline_panel.tsx)            │
├─────────────────────────────────────────────────────────────────────────────┤
│  Store: agentStore.ts (Zustand)        API: agent.ts / analysis.ts          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              后端 (sail_server)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Router Layer                                                                │
│  ├─ /api/v1/agent/* (agent.py)           - 通用 Agent API                    │
│  ├─ /api/v1/analysis/* (analysis.py)     - 小说分析 API                      │
│  └─ /api/v1/text/* (text.py)             - 文本管理 API                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Model/Controller Layer                                                      │
│  ├─ Agent 系统                    ├─ 小说分析系统                            │
│  │  ├─ scheduler.py (调度器)       │  ├─ task_scheduler.py                  │
│  │  ├─ runner.py (执行器)          │  ├─ outline.py                         │
│  │  └─ ...                         │  ├─ character.py                       │
│  └─ LLM Client                     │  └─ setting.py                         │
│     ├─ client.py (多提供商支持)    └─ analysis_llm.py (LLM分析控制)          │
│     └─ prompts.py (模板管理)                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  Data Layer (SQLAlchemy)                                                     │
│  ├─ agent.py: UserPrompt, AgentTask, AgentStep, AgentOutput...              │
│  ├─ analysis.py: Character, Setting, Outline, AnalysisTask...               │
│  └─ text.py: Work, Edition, DocumentNode...                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 当前功能对比

| 功能领域 | Agent 系统 | 小说分析系统 | 状态 |
|---------|-----------|-------------|------|
| **任务队列** | ✅ UserPrompt + 调度器 | ✅ AnalysisTask | 重复实现 |
| **LLM 调用** | ❌ Mock 实现 | ✅ LLMClient (多提供商) | 需要统一 |
| **进度追踪** | ✅ WebSocket 实时推送 | ✅ SSE + 轮询 | 两种机制 |
| **任务类型** | ✅ 通用 (code/analysis/writing) | ✅ 专用 (outline/character/setting) | 需要整合 |
| **Prompt 模板** | ❌ 内置字符串 | ✅ YAML 模板管理 | 需要统一 |
| **Token 控制** | ❌ 无 | ✅ 分块 + 预算 | 需要迁移 |
| **结果审核** | ❌ 无 | ✅ 审核流程 | 需要迁移 |
| **数据输出** | ✅ AgentOutput | ✅ AnalysisResult | 需要统一 |

### 1.3 技术债务

1. **Agent Runner 是 Mock 实现**，没有真正调用 LLM
2. **两个系统独立运行**，数据模型不互通
3. **进度通知机制不一致** (WebSocket vs SSE)
4. **前端页面分散**，缺乏统一入口
5. **Prompt 模板系统**只在小说分析中使用
6. **Token 成本控制**只在小说分析中实现

---

## 2. 整合目标

### 2.1 统一架构愿景

```
┌─────────────────────────────────────────────────────────────────┐
│                      统一 Agent 平台                             │
├─────────────────────────────────────────────────────────────────┤
│  前端                                                            │
│  ├─ Agent 工作台 (统一入口)                                      │
│  │  ├─ 快速任务 (通用 Agent)                                     │
│  │  ├─ 小说分析 (专用工作流)                                     │
│  │  └─ 任务监控中心                                              │
│  └─ 实时通知中心 (WebSocket)                                     │
├─────────────────────────────────────────────────────────────────┤
│  后端                                                            │
│  ├─ Unified Agent Engine                                        │
│  │  ├─ Task Scheduler (统一调度器)                              │
│  │  ├─ LLM Gateway (多提供商支持)                               │
│  │  ├─ Prompt Manager (模板系统)                                │
│  │  ├─ Token Budget (成本控制)                                  │
│  │  └─ Result Processor (结果处理)                              │
│  ├─ Domain Agents                                               │
│  │  ├─ NovelAnalysisAgent (小说分析)                            │
│  │  ├─ CodeAgent (代码助手)                                     │
│  │  └─ GeneralAgent (通用对话)                                  │
│  └─ Knowledge Store (知识库)                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心整合原则

1. **单一任务模型**: 统一使用 `AgentTask` 替代 `AnalysisTask`
2. **统一 LLM 网关**: 所有 LLM 调用通过 `LLMClient`
3. **共享模板系统**: 所有 Agent 使用 YAML 模板
4. **统一进度通知**: WebSocket 实时推送
5. **成本透明**: 所有任务显示 Token 消耗和成本估算

---

## 3. 详细开发计划

### Phase 1: 基础设施整合 (Week 1-2)

#### 3.1.1 统一数据模型

```python
# sail_server/data/unified_agent.py

@dataclass
class UnifiedAgentTask:
    """统一的任务模型"""
    id: int
    task_type: str  # 'novel_analysis' | 'code' | 'writing' | 'general'
    sub_type: str   # 如 'outline_extraction', 'character_detection'
    
    # 目标范围 (小说分析用)
    target_edition_id: Optional[int]
    target_node_ids: List[int]
    
    # LLM 配置
    llm_provider: str
    llm_model: str
    prompt_template_id: str
    
    # 执行状态
    status: TaskStatus
    progress: int  # 0-100
    current_phase: str
    
    # Token 成本追踪
    estimated_tokens: int
    actual_tokens: int
    estimated_cost: float
    actual_cost: float
    
    # 时间戳
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
```

**任务清单**:
- [ ] 创建 `unified_agent.py` 数据模型
- [ ] 编写数据库迁移脚本
- [ ] 创建数据访问层 (DAO)
- [ ] 编写向后兼容的适配器

#### 3.1.2 LLM 网关增强

```python
# sail_server/utils/llm/gateway.py

class LLMGateway:
    """统一 LLM 网关 - 支持多提供商、负载均衡、成本控制"""
    
    async def execute(
        self,
        prompt: RenderedPrompt,
        config: LLMExecutionConfig,
        budget: TokenBudget
    ) -> LLMExecutionResult:
        """
        执行 LLM 调用
        
        Features:
        - 自动选择提供商
        - Token 预算检查
        - 重试机制
        - 成本追踪
        """
        pass
```

**任务清单**:
- [ ] 封装 LLMGateway 类
- [ ] 实现 Provider 自动切换/降级
- [ ] 添加请求缓存机制
- [ ] 实现成本追踪中间件

#### 3.1.3 统一调度器

```python
# sail_server/model/unified_scheduler.py

class UnifiedAgentScheduler:
    """统一 Agent 调度器"""
    
    async def schedule_task(self, task: UnifiedAgentTask):
        # 1. 检查预算
        # 2. 选择 Agent 实现
        # 3. 提交到执行队列
        pass
    
    async def execute_task(self, task_id: int):
        # 1. 加载任务配置
        # 2. 获取 Agent 实例
        # 3. 执行并监控
        # 4. 更新状态和成本
        pass
```

**任务清单**:
- [ ] 实现 UnifiedAgentScheduler
- [ ] 集成现有调度器功能
- [ ] 添加任务优先级队列
- [ ] 实现资源限制控制

---

### Phase 2: Agent 实现层 (Week 3-4)

#### 3.2.1 BaseAgent 抽象类

```python
# sail_server/agent/base.py

class BaseAgent(ABC):
    """Agent 基类 - 所有具体 Agent 的抽象"""
    
    @property
    @abstractmethod
    def agent_type(self) -> str:
        pass
    
    @abstractmethod
    async def execute(
        self,
        task: UnifiedAgentTask,
        context: AgentContext,
        callback: ProgressCallback
    ) -> AgentExecutionResult:
        """执行 Agent 任务"""
        pass
    
    @abstractmethod
    def estimate_cost(
        self,
        task: UnifiedAgentTask
    ) -> CostEstimate:
        """预估任务成本"""
        pass
```

#### 3.2.2 NovelAnalysisAgent

```python
# sail_server/agent/novel_analysis.py

class NovelAnalysisAgent(BaseAgent):
    """
    小说分析 Agent
    
    整合现有功能:
    - 渐进式分析 (overview -> structure -> plot -> characters -> settings)
    - Token 预算控制
    - 分块处理
    - 结果审核流程
    """
    
    async def execute(self, task, context, callback):
        # 1. 加载章节数据
        # 2. 分块策略
        # 3. 渐进式分析
        # 4. 结果聚合
        pass
```

#### 3.2.3 GeneralAgent

```python
# sail_server/agent/general.py

class GeneralAgent(BaseAgent):
    """通用对话 Agent - 替代现有 Mock 实现"""
    
    async def execute(self, task, context, callback):
        # 简单的单轮/多轮对话
        pass
```

**任务清单**:
- [ ] 实现 BaseAgent 抽象类
- [ ] 重构 NovelAnalysisAgent
- [ ] 实现 GeneralAgent
- [ ] 创建 Agent 注册/发现机制

---

### Phase 3: 前端整合 (Week 5-6)

#### 3.3.1 统一 API 层

```typescript
// packages/site/src/lib/api/unifiedAgent.ts

export interface UnifiedTask {
  id: number;
  taskType: 'novel_analysis' | 'code' | 'writing' | 'general';
  subType: string;
  status: TaskStatus;
  progress: number;
  // ...
}

export class UnifiedAgentAPI {
  // 统一的任务提交
  async submitTask(request: CreateTaskRequest): Promise<UnifiedTask>;
  
  // 统一的进度查询
  async getTaskProgress(taskId: number): Promise<TaskProgress>;
  
  // WebSocket 实时通知
  connectRealtimeStream(onEvent: (event: AgentEvent) => void): WebSocket;
}
```

#### 3.3.2 Agent 工作台

```
页面: /agent-workbench

布局:
┌─────────────────────────────────────────────────────┐
│  Sidebar        │  Main Content                      │
│  ├─ 快速任务     │  ┌─────────────────────────────┐  │
│  ├─ 小说分析     │  │  任务创建 / 监控 / 结果       │  │
│  ├─ 任务历史     │  └─────────────────────────────┘  │
│  └─ 设置        │                                    │
└─────────────────────────────────────────────────────┘
```

**任务清单**:
- [ ] 创建统一 API 层
- [ ] 重构 Agent Store
- [ ] 设计 Agent 工作台页面
- [ ] 实现任务监控组件
- [ ] 统一进度显示组件

---

### Phase 4: 功能增强 (Week 7-8)

#### 3.4.1 Prompt 模板管理 UI

```
页面: /agent-workbench/templates

功能:
- 模板列表/搜索
- 模板编辑器 (YAML)
- 变量预览
- 测试执行
- 版本管理
```

#### 3.4.2 成本仪表盘

```
组件: CostDashboard

展示:
- 今日/本周/本月 Token 消耗
- 成本按 Provider 分布
- 任务类型成本占比
- 预算预警
```

#### 3.4.3 知识库集成

```python
# 允许 Agent 访问已分析的数据
class KnowledgeStore:
    def query_characters(self, edition_id: int, query: str) -> List[Character];
    def query_settings(self, edition_id: int, query: str) -> List[Setting];
    def get_plot_summary(self, edition_id: int, chapter_range: Tuple[int, int]) -> str;
```

**任务清单**:
- [ ] Prompt 模板管理 UI
- [ ] 成本仪表盘
- [ ] 知识库查询接口
- [ ] Agent 记忆机制

---

## 4. 数据库迁移计划

### 4.1 迁移脚本

```sql
-- migration: unify_agent_system.sql

-- 1. 创建统一任务表
CREATE TABLE unified_agent_tasks (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    sub_type VARCHAR(50),
    -- ... 其他字段
);

-- 2. 迁移现有 AnalysisTask 数据
INSERT INTO unified_agent_tasks (...)
SELECT ... FROM analysis_tasks;

-- 3. 迁移现有 AgentTask 数据
INSERT INTO unified_agent_tasks (...)
SELECT ... FROM agent_tasks;

-- 4. 创建视图保持向后兼容
CREATE VIEW analysis_tasks_v AS 
SELECT * FROM unified_agent_tasks WHERE task_type = 'novel_analysis';
```

---

## 5. API 兼容性策略

### 5.1 旧 API 保留

```python
# analysis.py 路由保持，但转发到新的实现

@router.post("/task/")
async def create_analysis_task(data: CreateTaskRequest):
    # 转换为统一任务格式
    unified_task = convert_to_unified(data)
    # 调用新调度器
    result = await unified_scheduler.submit(unified_task)
    # 返回兼容格式
    return convert_from_unified(result)
```

### 5.2 新 API 设计

```
POST   /api/v2/agent/tasks           # 创建任务
GET    /api/v2/agent/tasks/{id}      # 获取任务
GET    /api/v2/agent/tasks/{id}/progress  # 进度
POST   /api/v2/agent/tasks/{id}/cancel    # 取消
WS     /api/v2/agent/events          # 实时事件

GET    /api/v2/agent/templates       # 模板列表
GET    /api/v2/agent/templates/{id}  # 模板详情
POST   /api/v2/agent/templates/{id}/test  # 测试模板

GET    /api/v2/agent/cost/summary    # 成本摘要
GET    /api/v2/agent/cost/tasks      # 任务成本明细
```

---

## 6. 风险评估与缓解

| 风险 | 影响 | 缓解策略 |
|-----|-----|---------|
| 数据迁移失败 | 高 | 完整备份；灰度迁移；可回滚 |
| API 不兼容 | 中 | 保留旧 API；渐进式切换 |
| LLM 调用异常 | 高 | 多提供商降级；熔断机制 |
| Token 预算超支 | 中 | 硬限制；预警机制 |
| 前端重构复杂 | 中 | 组件复用；增量迭代 |

---

## 7. 验收标准

### 7.1 功能验收

- [ ] 小说分析功能完整可用
- [ ] 通用 Agent 可实际调用 LLM
- [ ] 任务进度实时显示
- [ ] Token 成本正确计算
- [ ] 数据完整迁移无丢失

### 7.2 性能验收

- [ ] 任务创建 < 500ms
- [ ] 进度查询 < 100ms
- [ ] WebSocket 延迟 < 100ms
- [ ] 支持 10+ 并发任务

### 7.3 代码验收

- [ ] 测试覆盖率 > 70%
- [ ] 旧 API 100% 兼容
- [ ] 文档完整
- [ ] 代码审查通过

---

## 8. 后续扩展建议

### 8.1 短期 (1-2 月)

1. **插件系统**: 允许第三方 Agent 注册
2. **批处理**: 批量提交任务
3. **定时任务**: 周期执行分析

### 8.2 中期 (3-6 月)

1. **Agent 协作**: 多 Agent 协同完成任务
2. **智能路由**: 根据任务类型自动选择最佳 Agent
3. **模型微调**: 支持自定义模型

### 8.3 长期 (6-12 月)

1. **多模态**: 支持图像/音频分析
2. **知识图谱**: 构建小说世界知识图谱
3. **智能推荐**: 基于分析结果推荐创作方向

---

**文档版本**: 1.0  
**创建日期**: 2026-02-25  
**作者**: AI Assistant  
**评审状态**: 待评审
