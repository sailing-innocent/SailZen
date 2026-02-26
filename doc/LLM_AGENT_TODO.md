# SailZen LLM/Agent 功能整合 - 阶段性迁移计划

> 基于 `LLM_AGENT_INTEGRATION_PLAN.md` 制定的可执行 TODO
> 创建日期: 2026-02-26

---

## 📋 阶段总览

| 阶段 | 名称 | 预计工期 | 风险等级 | 验收方式 |
|-----|------|---------|---------|---------|
| Phase 0 | 代码调研与冻结 | 1-2 天 | 🟢 低 | 调研报告 |
| Phase 1 | 统一数据模型设计 | 2-3 天 | 🟢 低 | 模型评审通过 |
| Phase 2 | 数据库迁移 | 2-3 天 | 🔴 高 | 数据完整性验证 |
| Phase 3 | LLM 网关封装 | 3-4 天 | 🟡 中 | LLM 调用测试通过 |
| Phase 4 | 统一调度器实现 | 3-4 天 | 🟡 中 | 调度功能测试 |
| Phase 5 | Agent 抽象与 NovelAnalysisAgent | 5-7 天 | 🟡 中 | 小说分析功能正常 |
| Phase 6 | GeneralAgent 实现 | 2-3 天 | 🟢 低 | Mock 替换完成 |
| Phase 7 | 旧 API 兼容层 | 2-3 天 | 🟡 中 | 旧接口回归测试 |
| Phase 8 | 前端统一 API 层 | 3-4 天 | 🟢 低 | API 调用正常 |
| Phase 9 | Agent 工作台页面 | 5-7 天 | 🟢 低 | 页面功能验收 |
| Phase 10 | 增强功能 | 按需 | 🟢 低 | 功能验收 |

---

## Phase 0: 代码调研与冻结

**目标**: 深入理解现有代码，冻结相关功能开发，准备迁移

### 任务清单

- [ ] **0.1 代码走查**: 阅读现有 Agent 系统和小说分析系统完整代码
  - `sail_server/router/agent.py` - 现有 Agent API
  - `sail_server/router/analysis.py` - 小说分析 API
  - `sail_server/model/agent.py` - Agent 数据模型
  - `sail_server/model/analysis.py` - 分析数据模型
  - `sail_server/utils/llm/` - LLM 相关工具
  - `packages/site/src/lib/api/agent.ts` - 前端 Agent API
  - `packages/site/src/lib/api/analysis.ts` - 前端分析 API

- [ ] **0.2 数据模型梳理**: 绘制现有实体关系图
  - AgentTask / AnalysisTask 字段对比
  - 外键关系梳理
  - 索引情况检查

- [ ] **0.3 接口清单整理**: 列出所有需要兼容的 API 端点
  - 现有 Agent 接口: 方法、路径、请求/响应格式
  - 现有 Analysis 接口: 方法、路径、请求/响应格式

- [ ] **0.4 功能冻结声明**: 在相关代码添加注释标记迁移边界

### 验收标准

- [ ] 产出《现有代码调研报告》文档
- [ ] 产出《数据模型对比表》
- [ ] 产出《API 接口清单》
- [ ] 团队评审通过，确认可以开始迁移

### 交付物

- `doc/migration/research_report.md`
- `doc/migration/data_model_comparison.md`
- `doc/migration/api_inventory.md`

---

## Phase 1: 统一数据模型设计

**目标**: 设计新的统一数据模型，确保能兼容现有所有功能

### 任务清单

- [ ] **1.1 设计 UnifiedAgentTask 模型**: 创建 `sail_server/model/unified_agent.py`
  ```python
  class UnifiedAgentTask(Base):
      __tablename__ = 'unified_agent_tasks'
      
      id: Mapped[int] = mapped_column(primary_key=True)
      task_type: Mapped[str]  # 'novel_analysis' | 'code' | 'writing' | 'general'
      sub_type: Mapped[Optional[str]]
      
      # 目标范围 (小说分析用)
      target_edition_id: Mapped[Optional[int]]
      target_node_ids: Mapped[Optional[List[int]]]
      
      # LLM 配置
      llm_provider: Mapped[Optional[str]]
      llm_model: Mapped[Optional[str]]
      prompt_template_id: Mapped[Optional[str]]
      
      # 执行状态
      status: Mapped[str]  # pending | running | completed | failed | cancelled
      progress: Mapped[int]  # 0-100
      current_phase: Mapped[Optional[str]]
      error_message: Mapped[Optional[str]]
      
      # Token 成本追踪
      estimated_tokens: Mapped[Optional[int]]
      actual_tokens: Mapped[int] = mapped_column(default=0)
      estimated_cost: Mapped[Optional[float]]
      actual_cost: Mapped[float] = mapped_column(default=0.0)
      
      # 结果存储
      result_data: Mapped[Optional[dict]]  # JSON
      output_id: Mapped[Optional[int]]  # 关联 AgentOutput
      
      # 时间戳
      created_at: Mapped[datetime]
      started_at: Mapped[Optional[datetime]]
      completed_at: Mapped[Optional[datetime]]
      cancelled_at: Mapped[Optional[datetime]]
  ```

- [ ] **1.2 设计 UnifiedAgentStep 模型**: 任务执行步骤跟踪
  ```python
  class UnifiedAgentStep(Base):
      __tablename__ = 'unified_agent_steps'
      
      id: Mapped[int] = mapped_column(primary_key=True)
      task_id: Mapped[int] = mapped_column(ForeignKey('unified_agent_tasks.id'))
      step_type: Mapped[str]  # 'llm_call' | 'data_processing' | 'verification'
      step_name: Mapped[str]
      status: Mapped[str]
      
      # LLM 调用详情
      llm_provider: Mapped[Optional[str]]
      llm_model: Mapped[Optional[str]]
      prompt_tokens: Mapped[int] = mapped_column(default=0)
      completion_tokens: Mapped[int] = mapped_column(default=0)
      cost: Mapped[float] = mapped_column(default=0.0)
      
      # 时间戳
      started_at: Mapped[Optional[datetime]]
      completed_at: Mapped[Optional[datetime]]
  ```

- [ ] **1.3 设计数据访问层 (DAO)**: 创建 `sail_server/data/unified_agent.py`
  - `UnifiedAgentTaskDAO`: 任务 CRUD
  - `UnifiedAgentStepDAO`: 步骤 CRUD
  - 查询方法: 按状态、类型、时间范围查询

- [ ] **1.4 模型验证**: 确保新模型能覆盖现有功能
  - 验证 AgentTask 所有字段可映射
  - 验证 AnalysisTask 所有字段可映射
  - 验证外键关系完整性

### 验收标准

- [ ] 数据模型代码通过类型检查 (`pyright`/`mypy`)
- [ ] 模型能完整映射现有 AgentTask 和 AnalysisTask 的所有字段
- [ ] 编写单元测试，验证模型创建和查询
- [ ] 代码审查通过

### 交付物

- `sail_server/model/unified_agent.py`
- `sail_server/data/unified_agent.py`
- `tests/model/test_unified_agent.py`

---

## Phase 2: 数据库迁移（⚠️ 高风险）

**目标**: 安全迁移数据库，创建新表结构，保持数据完整性

### 前置条件

- Phase 1 完成且评审通过
- 数据库完整备份
- 开发环境可回滚

### 任务清单

- [ ] **2.1 编写迁移脚本**: 创建 `sail_server/migration/unify_agent_system.sql`
  ```sql
  -- 迁移脚本结构
  -- 1. 开启事务
  BEGIN;
  
  -- 2. 创建统一任务表
  CREATE TABLE unified_agent_tasks (...);
  
  -- 3. 创建统一步骤表
  CREATE TABLE unified_agent_steps (...);
  
  -- 4. 创建索引
  CREATE INDEX idx_uat_status ON unified_agent_tasks(status);
  CREATE INDEX idx_uat_type ON unified_agent_tasks(task_type);
  CREATE INDEX idx_uat_created ON unified_agent_tasks(created_at);
  
  -- 5. 迁移 AnalysisTask 数据
  INSERT INTO unified_agent_tasks (...)
  SELECT ... FROM analysis_tasks;
  
  -- 6. 迁移 AgentTask 数据
  INSERT INTO unified_agent_tasks (...)
  SELECT ... FROM agent_tasks;
  
  -- 7. 创建兼容视图
  CREATE VIEW analysis_tasks_v AS 
  SELECT * FROM unified_agent_tasks WHERE task_type = 'novel_analysis';
  
  CREATE VIEW agent_tasks_v AS 
  SELECT * FROM unified_agent_tasks WHERE task_type IN ('code', 'writing', 'general');
  
  COMMIT;
  ```

- [ ] **2.2 数据验证脚本**: 创建 `sail_server/migration/verify_migration.py`
  - 对比源表和目标表的记录数
  - 抽样验证字段映射正确性
  - 验证外键关系

- [ ] **2.3 回滚脚本**: 创建 `sail_server/migration/rollback_unify_agent.sql`
  - 删除新表
  - 恢复旧表（如果需要）

- [ ] **2.4 测试环境迁移**: 先在测试数据库执行迁移
  - 使用测试数据验证迁移脚本
  - 运行验证脚本确认数据完整性
  - 运行应用功能测试

- [ ] **2.5 生产环境迁移**: 在维护窗口执行
  - 备份生产数据库
  - 执行迁移脚本
  - 运行验证脚本
  - 验证应用功能正常

### 风险控制

| 风险 | 预防措施 |
|-----|---------|
| 数据丢失 | 完整备份；迁移前导出关键表 |
| 迁移失败 | 脚本使用事务；失败自动回滚 |
| 应用中断 | 选择低峰期；准备快速回滚方案 |
| 数据不一致 | 验证脚本双重检查；抽样对比 |

### 验收标准

- [ ] 测试环境迁移成功，数据完整性验证 100% 通过
- [ ] 生产环境迁移成功，数据无丢失
- [ ] 所有外键关系和索引正常
- [ ] 回滚脚本已验证可用

### 交付物

- `sail_server/migration/unify_agent_system.sql`
- `sail_server/migration/verify_migration.py`
- `sail_server/migration/rollback_unify_agent.sql`
- 《迁移执行报告》

---

## Phase 3: LLM 网关封装

**目标**: 封装统一的 LLM 网关，支持多提供商、成本追踪

### 任务清单

- [ ] **3.1 创建 LLMGateway 类**: `sail_server/utils/llm/gateway.py`
  ```python
  @dataclass
  class LLMExecutionConfig:
      provider: str  # 'google' | 'openai' | 'moonshot'
      model: str
      temperature: float = 0.7
      max_tokens: Optional[int] = None
      timeout: int = 60
      retries: int = 3
  
  @dataclass
  class TokenBudget:
      max_tokens: int
      max_cost: float
      warning_threshold: float = 0.8
  
  @dataclass
  class LLMExecutionResult:
      content: str
      prompt_tokens: int
      completion_tokens: int
      total_tokens: int
      cost: float
      provider: str
      model: str
      latency_ms: int
  
  class LLMGateway:
      """统一 LLM 网关"""
      
      async def execute(
          self,
          prompt: str | list[dict],
          config: LLMExecutionConfig,
          budget: Optional[TokenBudget] = None
      ) -> LLMExecutionResult:
          """执行 LLM 调用"""
          
      async def execute_with_fallback(
          self,
          prompt: str | list[dict],
          configs: list[LLMExecutionConfig],
          budget: Optional[TokenBudget] = None
      ) -> LLMExecutionResult:
          """带降级的多提供商调用"""
  ```

- [ ] **3.2 集成现有 LLMClient**: 复用 `analysis_llm.py` 的多提供商逻辑
  - 提取 Provider 抽象接口
  - 实现 Google/OpenAI/Moonshot Provider
  - 统一错误处理

- [ ] **3.3 实现成本追踪**: 
  - 各 Provider Token 价格配置
  - 实时成本计算
  - 预算检查（执行前/执行中）

- [ ] **3.4 实现请求缓存**: 
  - 相同 Prompt 缓存结果
  - 缓存过期策略
  - 缓存命中率统计

- [ ] **3.5 熔断机制**: 
  - Provider 故障检测
  - 自动切换备用 Provider
  - 故障恢复检测

### 验收标准

- [ ] 单元测试: 各 Provider 调用正常
- [ ] 集成测试: 降级机制正常工作
- [ ] 成本计算准确，与实际账单误差 < 1%
- [ ] 预算超支时能正确拦截
- [ ] 缓存命中率可监控

### 交付物

- `sail_server/utils/llm/gateway.py`
- `sail_server/utils/llm/providers/` (Provider 实现目录)
- `sail_server/utils/llm/pricing.py` (价格配置)
- `tests/utils/llm/test_gateway.py`

---

## Phase 4: 统一调度器实现

**目标**: 实现统一的任务调度器，支持优先级队列和资源控制

### 任务清单

- [ ] **4.1 创建 UnifiedAgentScheduler**: `sail_server/model/unified_scheduler.py`
  ```python
  class UnifiedAgentScheduler:
      """统一 Agent 调度器"""
      
      def __init__(self):
          self.task_queue: asyncio.PriorityQueue[TaskQueueItem]
          self.running_tasks: dict[int, asyncio.Task]
          self.max_concurrent: int = 5
      
      async def schedule_task(self, task_config: TaskConfig) -> UnifiedAgentTask:
          """调度新任务"""
          # 1. 检查预算
          # 2. 检查资源限制
          # 3. 创建任务记录
          # 4. 加入队列或直接执行
      
      async def execute_task(self, task_id: int):
          """执行任务"""
          # 1. 获取 Agent 实例
          # 2. 执行并监控
          # 3. 更新状态和成本
      
      async def cancel_task(self, task_id: int) -> bool:
          """取消任务"""
      
      async def get_task_progress(self, task_id: int) -> TaskProgress:
          """获取任务进度"""
  ```

- [ ] **4.2 实现优先级队列**:
  - 优先级策略: 用户类型 > 任务类型 > 提交时间
  - 插队机制: 高优先级任务可抢占
  - 队列持久化: 重启后恢复未执行任务

- [ ] **4.3 资源限制控制**:
  - 并发任务数限制
  - Token 消耗速率限制
  - 单用户任务数限制

- [ ] **4.4 进度通知机制**:
  - WebSocket 实时推送
  - 事件类型: start/progress/completed/failed/cancelled
  - 订阅/取消订阅

- [ ] **4.5 集成现有调度器功能**:
  - 复用 `scheduler.py` 的时间管理
  - 复用 `task_scheduler.py` 的任务状态管理

### 验收标准

- [ ] 任务能按优先级正确排序执行
- [ ] 并发任务数控制在限制内
- [ ] WebSocket 进度通知实时到达
- [ ] 任务取消能正确终止执行
- [ ] 调度器重启后能恢复未完成任务

### 交付物

- `sail_server/model/unified_scheduler.py`
- `sail_server/model/task_queue.py`
- `sail_server/utils/websocket_manager.py`
- `tests/model/test_unified_scheduler.py`

---

## Phase 5: Agent 抽象与 NovelAnalysisAgent

**目标**: 实现 BaseAgent 抽象，将现有小说分析功能迁移为 NovelAnalysisAgent

### 任务清单

- [ ] **5.1 创建 BaseAgent 抽象类**: `sail_server/agent/base.py`
  ```python
  class BaseAgent(ABC):
      """Agent 基类"""
      
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
      
      @abstractmethod
      def estimate_cost(
          self,
          task: UnifiedAgentTask
      ) -> CostEstimate:
          """预估任务成本"""
      
      @abstractmethod
      def validate_task(self, task: UnifiedAgentTask) -> ValidationResult:
          """验证任务配置"""
  ```

- [ ] **5.2 创建 AgentContext**: 任务执行上下文
  ```python
  @dataclass
  class AgentContext:
      db_session: Session
      llm_gateway: LLMGateway
      knowledge_store: KnowledgeStore
      config: dict
  ```

- [ ] **5.3 实现 NovelAnalysisAgent**: `sail_server/agent/novel_analysis.py`
  - 整合 `outline.py` 的大纲分析
  - 整合 `character.py` 的人物分析
  - 整合 `setting.py` 的设定分析
  - 保留 Token 预算控制逻辑
  - 保留分块处理逻辑
  - 保留结果审核流程

- [ ] **5.4 创建 Agent 注册机制**:
  ```python
  class AgentRegistry:
      def register(self, agent_class: type[BaseAgent])
      def get_agent(self, task_type: str) -> BaseAgent
      def list_agents(self) -> list[AgentInfo]
  ```

- [ ] **5.5 重构现有分析流程**:
  - 将 `analysis_llm.py` 逻辑整合到 NovelAnalysisAgent
  - 保持现有 Prompt 模板兼容性
  - 保持结果数据格式不变

### 验收标准

- [ ] NovelAnalysisAgent 能完成完整的小说分析流程
- [ ] 分析结果与现有系统一致
- [ ] Token 预算控制正常工作
- [ ] 成本预估准确率 > 80%
- [ ] 结果审核流程正常工作

### 交付物

- `sail_server/agent/base.py`
- `sail_server/agent/novel_analysis.py`
- `sail_server/agent/registry.py`
- `tests/agent/test_novel_analysis.py`

---

## Phase 6: GeneralAgent 实现

**目标**: 实现通用 Agent，替换现有的 Mock 实现

### 任务清单

- [ ] **6.1 实现 GeneralAgent**: `sail_server/agent/general.py`
  ```python
  class GeneralAgent(BaseAgent):
      """通用对话 Agent"""
      
      agent_type = "general"
      
      async def execute(
          self,
          task: UnifiedAgentTask,
          context: AgentContext,
          callback: ProgressCallback
      ) -> AgentExecutionResult:
          # 1. 解析用户输入
          # 2. 构建对话上下文
          # 3. 调用 LLM Gateway
          # 4. 返回结果
      
      def estimate_cost(self, task: UnifiedAgentTask) -> CostEstimate:
          # 基于历史数据估算
  ```

- [ ] **6.2 支持多轮对话**:
  - 维护对话历史
  - 上下文窗口管理
  - 历史记录持久化

- [ ] **6.3 支持任务类型扩展**:
  - `code`: 代码辅助
  - `writing`: 写作辅助
  - `general`: 通用问答

- [ ] **6.4 替换 Mock 实现**:
  - 修改现有 Agent Runner
  - 删除 Mock 代码
  - 测试真实 LLM 调用

### 验收标准

- [ ] GeneralAgent 能实际调用 LLM
  - 测试 Google Provider
  - 测试 OpenAI Provider
  - 测试 Moonshot Provider
- [ ] 多轮对话上下文保持正确
- [ ] 成本预估合理
- [ ] 响应时间 < 10s (正常网络)

### 交付物

- `sail_server/agent/general.py`
- `sail_server/agent/code.py` (可选)
- `sail_server/agent/writing.py` (可选)
- `tests/agent/test_general.py`

---

## Phase 7: 旧 API 兼容层

**目标**: 保持旧 API 接口不变，内部转发到新实现

### 任务清单

- [ ] **7.1 创建 API 适配器**: `sail_server/router/analysis_compat.py`
  ```python
  @router.post("/task/")
  async def create_analysis_task(data: CreateTaskRequest):
      # 1. 转换请求格式
      unified_request = convert_analysis_to_unified(data)
      # 2. 调用新调度器
      result = await unified_scheduler.schedule_task(unified_request)
      # 3. 转换响应格式
      return convert_unified_to_analysis(result)
  ```

- [ ] **7.2 保留所有旧端点**:
  - `/api/v1/analysis/task/*`
  - `/api/v1/analysis/progress/*`
  - `/api/v1/analysis/result/*`
  - `/api/v1/analysis/verify/*`
  - `/api/v1/agent/*` (现有 Agent API)

- [ ] **7.3 请求/响应格式兼容**:
  - 字段名映射
  - 枚举值映射
  - 错误码兼容

- [ ] **7.4 回归测试**:
  - 运行现有前端功能测试
  - 验证所有旧接口返回正确
  - 验证错误处理兼容

### 验收标准

- [ ] 现有前端页面无需修改即可正常工作
- [ ] 所有旧 API 单元测试通过
- [ ] 集成测试: 旧接口调用新实现，结果正确

### 交付物

- `sail_server/router/analysis_compat.py`
- `sail_server/router/agent_compat.py`
- `tests/router/test_analysis_compat.py`
- 《API 兼容性报告》

---

## Phase 8: 前端统一 API 层

**目标**: 前端创建统一的 API 层，对接新的统一后端 API

### 任务清单

- [ ] **8.1 创建 UnifiedAgentAPI**: `packages/site/src/lib/api/unifiedAgent.ts`
  ```typescript
  export interface UnifiedTask {
    id: number;
    taskType: 'novel_analysis' | 'code' | 'writing' | 'general';
    subType: string;
    status: TaskStatus;
    progress: number;
    currentPhase?: string;
    estimatedTokens?: number;
    actualTokens: number;
    estimatedCost?: number;
    actualCost: number;
    createdAt: string;
    startedAt?: string;
    completedAt?: string;
  }
  
  export class UnifiedAgentAPI {
    async submitTask(request: CreateTaskRequest): Promise<UnifiedTask>;
    async getTask(taskId: number): Promise<UnifiedTask>;
    async getTaskProgress(taskId: number): Promise<TaskProgress>;
    async cancelTask(taskId: number): Promise<boolean>;
    async listTasks(filter: TaskFilter): Promise<UnifiedTask[]>;
    
    // WebSocket
    connectRealtimeStream(
      onEvent: (event: AgentEvent) => void
    ): WebSocket;
  }
  ```

- [ ] **8.2 创建新的 Agent Store**: `packages/site/src/lib/store/unifiedAgentStore.ts`
  - 使用 Zustand
  - 管理任务列表
  - 管理 WebSocket 连接
  - 统一状态更新

- [ ] **8.3 封装现有 API 调用**:
  - 保持现有页面代码不变
  - 在 API 层内部切换调用
  - 添加 feature flag 控制

- [ ] **8.4 类型定义更新**:
  - 更新 TypeScript 类型定义
  - 保持向后兼容的类型别名

### 验收标准

- [ ] 新 API 层 TypeScript 类型检查通过
- [ ] 新 Store 单元测试通过
- [ ] 与后端 API 集成测试通过
- [ ] WebSocket 实时通知正常工作

### 交付物

- `packages/site/src/lib/api/unifiedAgent.ts`
- `packages/site/src/lib/store/unifiedAgentStore.ts`
- `packages/site/src/lib/types/agent.ts` (更新)
- `packages/site/src/__tests__/api/unifiedAgent.test.ts`

---

## Phase 9: Agent 工作台页面

**目标**: 创建统一的 Agent 工作台页面

### 任务清单

- [ ] **9.1 设计页面布局**:
  ```
  /agent-workbench
  
  Layout:
  ┌─────────────────────────────────────────────────────┐
  │  Sidebar        │  Main Content                      │
  │  ├─ 快速任务     │  ┌─────────────────────────────┐  │
  │  ├─ 小说分析     │  │  任务创建 / 监控 / 结果       │  │
  │  ├─ 任务历史     │  └─────────────────────────────┘  │
  │  └─ 设置        │                                    │
  └─────────────────────────────────────────────────────┘
  ```

- [ ] **9.2 实现 Sidebar 导航**: `app/agent-workbench/components/Sidebar.tsx`
  - 快速任务入口
  - 小说分析入口
  - 任务历史入口
  - 设置入口

- [ ] **9.3 实现快速任务组件**: `app/agent-workbench/components/QuickTask.tsx`
  - 任务类型选择
  - Prompt 输入
  - 模型选择
  - 提交按钮
  - 实时结果展示

- [ ] **9.4 实现任务监控中心**: `app/agent-workbench/components/TaskMonitor.tsx`
  - 任务列表
  - 进度显示
  - 状态筛选
  - 取消/重试操作

- [ ] **9.5 实现成本显示组件**: `app/agent-workbench/components/CostDisplay.tsx`
  - 当前任务成本
  - 今日/本周累计
  - 预算进度条

- [ ] **9.6 集成现有小说分析页面**:
  - 嵌入现有分析组件
  - 统一导航入口

### 验收标准

- [ ] 页面能正常访问 `/agent-workbench`
- [ ] 快速任务能提交并显示结果
- [ ] 任务监控中心实时更新
- [ ] 成本显示准确
- [ ] 移动端适配良好

### 交付物

- `packages/site/src/app/agent-workbench/page.tsx`
- `packages/site/src/app/agent-workbench/components/*.tsx`
- `packages/site/src/app/agent-workbench/hooks/*.ts`

---

## Phase 10: 增强功能

**目标**: 实现增强功能，提升用户体验

### 任务清单（按需选择）

- [ ] **10.1 Prompt 模板管理 UI**
  - 页面: `/agent-workbench/templates`
  - 模板列表/搜索
  - YAML 编辑器
  - 变量预览
  - 测试执行

- [ ] **10.2 成本仪表盘**
  - 今日/本周/本月 Token 消耗
  - 成本按 Provider 分布
  - 任务类型成本占比
  - 预算预警

- [ ] **10.3 知识库集成**
  - 查询已分析的人物
  - 查询已分析的设定
  - 获取情节摘要

- [ ] **10.4 Agent 记忆机制**
  - 跨任务记忆
  - 用户偏好学习
  - 上下文保持

### 验收标准

- [ ] 各增强功能按需求验收

---

## 📊 进度跟踪

### 当前阶段

<!-- 更新此处的阶段状态 -->
- [x] Phase 0: 代码调研与冻结 ✅
- [x] Phase 1: 统一数据模型设计 ✅
- [ ] Phase 2: 数据库迁移 🔄
- [ ] Phase 3: LLM 网关封装
- [ ] Phase 4: 统一调度器实现
- [ ] Phase 5: Agent 抽象与 NovelAnalysisAgent
- [ ] Phase 6: GeneralAgent 实现
- [ ] Phase 7: 旧 API 兼容层
- [ ] Phase 8: 前端统一 API 层
- [ ] Phase 9: Agent 工作台页面
- [ ] Phase 10: 增强功能

### 里程碑

| 里程碑 | 完成阶段 | 日期 | 状态 |
|-------|---------|------|------|
| 后端架构完成 | Phase 7 | - | ⏳ |
| 前端对接完成 | Phase 9 | - | ⏳ |
| 功能完整可用 | Phase 10 | - | ⏳ |

---

## 🔄 变更记录

| 日期 | 版本 | 变更内容 | 作者 |
|-----|------|---------|------|
| 2026-02-26 | 1.0 | 初始版本 | AI Assistant |
| 2026-02-26 | 1.1 | Phase 0 完成，产出调研报告、数据模型对比、API清单 | AI Assistant |
| 2026-02-26 | 1.2 | Phase 1 完成，产出统一数据模型代码、DAO、单元测试 | AI Assistant |
