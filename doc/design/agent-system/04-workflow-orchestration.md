# 工作流编排与状态管理设计

## 目录

1. [工作流模型](#工作流模型)
2. [状态机设计](#状态机设计)
3. [断点续传机制](#断点续传机制)
4. [事件驱动架构](#事件驱动架构)

---

## 工作流模型

### DAG工作流定义

```yaml
# workflow-schema.yaml
workflow:
  # 基本信息
  id: "feature-development-v1"
  name: "新功能开发工作流"
  description: "从需求到上线的完整开发流程"
  version: "1.0.0"
  
  # 触发条件
  triggers:
    - type: "manual"              # 手动触发
    - type: "webhook"             # Webhook触发
      endpoint: "/webhook/feature"
    - type: "schedule"            # 定时触发
      cron: "0 2 * * *"
  
  # 输入参数定义
  inputs:
    - name: "requirement"
      type: "string"
      required: true
      description: "功能需求描述"
    
    - name: "project_id"
      type: "string"
      required: true
      description: "项目ID"
    
    - name: "priority"
      type: "integer"
      default: 5
      description: "优先级 (1-10)"
  
  # 上下文变量
  context:
    workspace_id: "{{generate_uuid()}}"
    start_time: "{{now()}}"
    user: "{{session.user}}"
  
  # 步骤定义
  steps:
    # ========== Step 1: 需求分析 ==========
    - id: "analyze"
      name: "需求分析"
      agent: "analyze_agent"
      action: "analyze_requirement"
      
      input:
        requirement: "{{inputs.requirement}}"
        project_context: "{{load_project_context(inputs.project_id)}}"
      
      output:
        analysis_report: "report"
        suggested_files: "files"
        estimated_effort: "effort"
      
      config:
        timeout: 300
        retry: 3
        checkpoint: true
      
      on_success:
        next: "design"
      
      on_failure:
        action: "notify"
        message: "需求分析失败: {{error}}"
        next: "failed"
    
    # ========== Step 2: 方案设计 ==========
    - id: "design"
      name: "技术方案设计"
      agent: "design_agent"
      action: "create_design_doc"
      
      depends_on: ["analyze"]
      
      input:
        analysis: "{{steps.analyze.output.analysis_report}}"
        target_files: "{{steps.analyze.output.suggested_files}}"
      
      output:
        design_document: "doc"
        implementation_plan: "plan"
      
      config:
        timeout: 600
        confirmation_required: true  # 需要人工确认
      
      on_complete:
        - condition: "{{outputs.implementation_plan.complexity}} == 'high'"
          action: "notify"
          message: "⚠️ 复杂度较高，建议人工Review设计文档"
    
    # ========== Step 3: 代码实现 (并行) ==========
    - id: "implement"
      name: "代码实现"
      type: "parallel"  # 并行步骤
      
      depends_on: ["design"]
      
      branches:
        - id: "impl_core"
          name: "核心功能"
          agent: "code_agent"
          action: "generate_core"
          input:
            design: "{{steps.design.output.design_document}}"
            scope: "core"
        
        - id: "impl_tests"
          name: "测试代码"
          agent: "test_agent"
          action: "generate_tests"
          input:
            design: "{{steps.design.output.design_document}}"
            target_coverage: 80
      
      aggregator: "merge_implementation"
      
      output:
        code_changes: "changes"
        test_files: "tests"
    
    # ========== Step 4: 代码审查 ==========
    - id: "review"
      name: "代码审查"
      agent: "review_agent"
      action: "comprehensive_review"
      
      depends_on: ["implement"]
      
      input:
        changes: "{{steps.implement.output.code_changes}}"
        tests: "{{steps.implement.output.test_files}}"
        standards: "{{project.standards}}"
      
      output:
        review_report: "report"
        overall_score: "score"
      
      # 条件分支
      on_complete:
        - condition: "{{outputs.overall_score}} >= 85"
          next: "test"
          message: "✅ 代码审查通过"
        
        - condition: "{{outputs.overall_score}} < 60"
          next: "implement"  # 打回重改
          action: "restart"
          message: "❌ 代码质量不合格，需要重新实现"
        
        - default:
          next: "fix"
          message: "⚠️ 有一些问题需要修复"
    
    # ========== Step 5: 自动修复 ==========
    - id: "fix"
      name: "自动修复"
      agent: "code_agent"
      action: "apply_fixes"
      
      input:
        code: "{{steps.implement.output.code_changes}}"
        review_comments: "{{steps.review.output.review_report.issues}}"
      
      output:
        fixed_code: "code"
      
      next: "review"  # 重新审查
    
    # ========== Step 6: 测试执行 ==========
    - id: "test"
      name: "测试执行"
      agent: "test_agent"
      action: "run_full_test_suite"
      
      depends_on: ["review"]
      
      input:
        test_files: "{{steps.implement.output.test_files}}"
        coverage_threshold: 80
      
      output:
        test_results: "results"
        coverage_report: "coverage"
      
      on_complete:
        - condition: "{{outputs.test_results.pass_rate}} < 100"
          next: "debug"
        
        - condition: "{{outputs.coverage_report.line_coverage}} < 80"
          next: "implement"
          action: "restart"
          message: "覆盖率不足，需要补充测试"
    
    # ========== Step 7: 调试修复 ==========
    - id: "debug"
      name: "调试修复"
      agent: "debug_agent"
      action: "fix_failures"
      
      input:
        test_results: "{{steps.test.output.test_results}}"
        code: "{{steps.implement.output.code_changes}}"
      
      output:
        fixes: "fixes"
      
      next: "test"  # 重新测试
      max_iterations: 3
    
    # ========== Step 8: 构建 ==========
    - id: "build"
      name: "构建打包"
      agent: "build_agent"
      action: "build_package"
      
      depends_on: ["test"]
      
      input:
        project_path: "{{project.path}}"
        target: "production"
      
      output:
        artifacts: "artifacts"
        build_log: "log"
    
    # ========== Step 9: 部署 ==========
    - id: "deploy"
      name: "部署上线"
      agent: "deploy_agent"
      action: "deploy_to_production"
      
      depends_on: ["build"]
      
      input:
        artifacts: "{{steps.build.output.artifacts}}"
        environment: "production"
        strategy: "canary"
      
      config:
        confirmation_required: true
        rollback_on_failure: true
      
      output:
        deployment_id: "deployment_id"
        endpoint: "url"
    
    # ========== Step 10: 验证 ==========
    - id: "verify"
      name: "上线验证"
      agent: "monitor_agent"
      action: "verify_deployment"
      
      depends_on: ["deploy"]
      
      input:
        endpoint: "{{steps.deploy.output.endpoint}}"
        health_checks: ["/health", "/api/status"]
        duration_minutes: 10
      
      output:
        verification_result: "result"
    
    # ========== 结束状态 ==========
    - id: "completed"
      name: "完成"
      type: "terminal"
      action: "cleanup"
      message: "🎉 功能开发完成并成功上线！"
    
    - id: "failed"
      name: "失败"
      type: "terminal"
      action: "cleanup"
      message: "❌ 工作流执行失败"
```

---

## 状态机设计

### 工作流状态机

```
                            ┌────────────────────────────────────────────────────────────┐
                            │                                                            │
                            │    ┌──────────────────────────────────────────────────┐    │
                            │    │                                                  │    │
                            ▼    │                                                  ▼    │
┌──────────┐           ┌──────────┐           ┌──────────┐           ┌──────────┐    │    │
│  CREATED │──────────▶│ PENDING  │──────────▶│ RUNNING  │──────────▶│COMPLETED │────┘    │
└──────────┘           └──────────┘           └────┬─────┘           └──────────┘         │
     │                    │    │                   │                                    │
     │                    │    │                   │                                    │
     │                    │    └───────────────────┼────────────────────────────────────┘
     │                    │                        │
     │                    │    ┌──────────┐        │
     │                    └───▶│  PAUSED  │◀───────┘
     │                       │ └──────────┘        │
     │                       │      │              │
     │                       └──────┼──────────────┘
     │                              │
     │                              ▼
     │                         ┌──────────┐
     └────────────────────────▶│  FAILED  │
                               └────┬─────┘
                                    │
                                    ▼
                              ┌──────────┐
                              │ RETRYING │
                              └──────────┘
```

**状态定义：**

| 状态 | 描述 | 可转换到 |
|------|------|----------|
| `CREATED` | 工作流已创建 | PENDING, CANCELLED |
| `PENDING` | 等待资源/调度 | RUNNING, CANCELLED |
| `RUNNING` | 执行中 | PAUSED, COMPLETED, FAILED, CANCELLED |
| `PAUSED` | 暂停执行 | RUNNING, CANCELLED |
| `COMPLETED` | 成功完成 | - (终态) |
| `FAILED` | 执行失败 | RETRYING, CANCELLED |
| `RETRYING` | 重试中 | RUNNING, FAILED |
| `CANCELLED` | 已取消 | - (终态) |

---

### 步骤状态机

```
┌──────────┐           ┌──────────┐           ┌──────────┐           ┌──────────┐
│  PENDING │──────────▶│SCHEDULED │──────────▶│ RUNNING  │──────────▶│COMPLETED │
└──────────┘           └──────────┘           └────┬─────┘           └──────────┘
     │                    │                        │
     │                    │                        │
     │                    │    ┌──────────┐        │
     │                    └───▶│  WAITING │◀───────┘
     │                       │ │(人工确认)│        │
     │                       │ └────┬─────┘        │
     │                       │      │              │
     │                       └──────┼──────────────┘
     │                              │
     │                              ▼
     │                         ┌──────────┐
     └────────────────────────▶│  FAILED  │
                               └──────────┘
```

---

### 状态管理实现

```python
class WorkflowStateMachine:
    """工作流状态机"""
    
    # 状态转换规则
    TRANSITIONS = {
        WorkflowStatus.CREATED: [
            WorkflowStatus.PENDING,
            WorkflowStatus.CANCELLED
        ],
        WorkflowStatus.PENDING: [
            WorkflowStatus.RUNNING,
            WorkflowStatus.CANCELLED
        ],
        WorkflowStatus.RUNNING: [
            WorkflowStatus.PAUSED,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED
        ],
        WorkflowStatus.PAUSED: [
            WorkflowStatus.RUNNING,
            WorkflowStatus.CANCELLED
        ],
        WorkflowStatus.FAILED: [
            WorkflowStatus.RETRYING,
            WorkflowStatus.CANCELLED
        ],
        WorkflowStatus.RETRYING: [
            WorkflowStatus.RUNNING,
            WorkflowStatus.FAILED
        ],
    }
    
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.current_status = WorkflowStatus.CREATED
        self.history = []
    
    async def transition(self, new_status: WorkflowStatus, reason: str = None):
        """状态转换"""
        if new_status not in self.TRANSITIONS.get(self.current_status, []):
            raise InvalidStateTransition(
                f"Cannot transition from {self.current_status} to {new_status}"
            )
        
        old_status = self.current_status
        self.current_status = new_status
        
        # 记录状态变更
        self.history.append({
            "from": old_status,
            "to": new_status,
            "timestamp": datetime.utcnow(),
            "reason": reason
        })
        
        # 持久化状态
        await self._persist_state()
        
        # 触发状态变更事件
        await self._emit_state_changed_event(old_status, new_status)
    
    async def _persist_state(self):
        """持久化状态到数据库"""
        async with db.session() as session:
            await session.execute(
                update(Workflow)
                .where(Workflow.id == self.workflow_id)
                .values(
                    status=self.current_status,
                    status_history=self.history,
                    updated_at=datetime.utcnow()
                )
            )
            await session.commit()
```

---

## 断点续传机制

### 检查点策略

```python
@dataclass
class Checkpoint:
    """检查点数据"""
    id: str
    workflow_id: str
    step_id: str
    timestamp: datetime
    
    # 完整状态快照
    workflow_state: Dict[str, Any]
    step_states: Dict[str, StepState]
    context_variables: Dict[str, Any]
    
    # 元数据
    memory_usage_mb: float
    disk_usage_mb: float
    execution_time_seconds: float
    
    # 恢复信息
    recoverable: bool
    recovery_instructions: Optional[str]


class CheckpointManager:
    """检查点管理器"""
    
    def __init__(self):
        self.persistence = DatabaseCheckpointPersistence()
        self.retention_policy = CheckpointRetentionPolicy()
    
    async def create_checkpoint(
        self,
        workflow: Workflow,
        step: Optional[Step] = None,
        trigger: CheckpointTrigger = CheckpointTrigger.MANUAL
    ) -> Checkpoint:
        """创建检查点"""
        
        checkpoint = Checkpoint(
            id=generate_uuid(),
            workflow_id=workflow.id,
            step_id=step.id if step else None,
            timestamp=datetime.utcnow(),
            workflow_state=workflow.serialize_state(),
            step_states={
                s.id: s.serialize_state() 
                for s in workflow.steps
            },
            context_variables=deepcopy(workflow.context.variables),
            memory_usage_mb=get_memory_usage(),
            disk_usage_mb=get_disk_usage(),
            execution_time_seconds=workflow.get_execution_time(),
            recoverable=True,
            recovery_instructions=None
        )
        
        # 保存到数据库
        await self.persistence.save(checkpoint)
        
        # 更新工作流检查点引用
        workflow.latest_checkpoint_id = checkpoint.id
        
        logger.info(f"Checkpoint created: {checkpoint.id} for workflow {workflow.id}")
        
        return checkpoint
    
    async def restore_from_checkpoint(
        self,
        checkpoint_id: str,
        resume_from_step: Optional[str] = None
    ) -> Workflow:
        """从检查点恢复工作流"""
        
        # 加载检查点
        checkpoint = await self.persistence.load(checkpoint_id)
        
        if not checkpoint.recoverable:
            raise NonRecoverableCheckpoint(
                f"Checkpoint {checkpoint_id} is not recoverable"
            )
        
        # 反序列化工作流状态
        workflow = Workflow.deserialize_state(checkpoint.workflow_state)
        
        # 恢复步骤状态
        for step_id, step_state in checkpoint.step_states.items():
            step = workflow.get_step(step_id)
            if step:
                step.deserialize_state(step_state)
        
        # 恢复上下文变量
        workflow.context.variables = deepcopy(checkpoint.context_variables)
        
        # 设置恢复点
        if resume_from_step:
            workflow.current_step_id = resume_from_step
        elif checkpoint.step_id:
            workflow.current_step_id = checkpoint.step_id
        
        # 更新状态为RUNNING
        await workflow.state_machine.transition(WorkflowStatus.RUNNING)
        
        logger.info(f"Workflow {workflow.id} restored from checkpoint {checkpoint_id}")
        
        return workflow
    
    async def list_checkpoints(
        self,
        workflow_id: str,
        limit: int = 10
    ) -> List[Checkpoint]:
        """列出工作流的所有检查点"""
        return await self.persistence.list_by_workflow(workflow_id, limit)
```

### 自动检查点触发条件

| 触发条件 | 检查点类型 | 保留策略 |
|----------|-----------|----------|
| 步骤开始前 | PRE_STEP | 最近5个 |
| 步骤完成后 | POST_STEP | 最近5个 |
| 异常中断时 | EMERGENCY | 永久保留 |
| 定时保存 | PERIODIC | 最近24小时 |
| 手动保存 | MANUAL | 永久保留 |
| 长时间运行 | PROGRESS | 最近10个 |

### 检查点恢复流程

```
用户请求恢复
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ 1. 加载检查点                                           │
│    - 从数据库读取检查点数据                               │
│    - 验证检查点完整性                                     │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ 2. 状态恢复                                             │
│    - 反序列化工作流状态                                   │
│    - 恢复所有步骤状态                                     │
│    - 恢复上下文变量                                       │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ 3. 环境恢复                                             │
│    - 重建工作区                                           │
│    - 恢复文件状态                                         │
│    - 重新连接外部服务                                     │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ 4. 验证恢复                                             │
│    - 检查Agent可用性                                      │
│    - 验证资源访问                                         │
│    - 确认依赖服务                                         │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ 5. 恢复执行                                             │
│    - 更新状态为RUNNING                                   │
│    - 通知用户恢复成功                                     │
│    - 继续执行工作流                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 事件驱动架构

### 事件类型定义

```python
class WorkflowEventType(Enum):
    """工作流事件类型"""
    
    # 生命周期事件
    WORKFLOW_CREATED = "workflow.created"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_CANCELLED = "workflow.cancelled"
    
    # 状态变更事件
    WORKFLOW_STATUS_CHANGED = "workflow.status_changed"
    STEP_STATUS_CHANGED = "step.status_changed"
    
    # 执行事件
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    STEP_RETRYING = "step.retrying"
    
    # 检查点事件
    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_RESTORED = "checkpoint.restored"
    
    # Agent事件
    AGENT_ASSIGNED = "agent.assigned"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    
    # 用户交互事件
    CONFIRMATION_REQUIRED = "confirmation.required"
    CONFIRMATION_RECEIVED = "confirmation.received"
    INPUT_REQUIRED = "input.required"
    INPUT_RECEIVED = "input.received"


@dataclass
class WorkflowEvent:
    """工作流事件"""
    event_id: str
    event_type: WorkflowEventType
    timestamp: datetime
    workflow_id: str
    step_id: Optional[str]
    
    # 事件数据
    payload: Dict[str, Any]
    
    # 上下文
    session_id: str
    user_id: str
    
    # 元数据
    source: str  # 事件来源
    correlation_id: str  # 关联ID
```

### 事件总线

```python
class EventBus:
    """事件总线 - 基于Redis Streams"""
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.subscribers: Dict[WorkflowEventType, List[Callable]] = {}
    
    async def publish(self, event: WorkflowEvent):
        """发布事件"""
        # 序列化事件
        event_data = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "workflow_id": event.workflow_id,
            "step_id": event.step_id,
            "payload": json.dumps(event.payload),
            "session_id": event.session_id,
            "user_id": event.user_id,
            "source": event.source,
            "correlation_id": event.correlation_id
        }
        
        # 写入Redis Stream
        await self.redis.xadd(
            f"workflow:events:{event.workflow_id}",
            event_data
        )
        
        # 广播到所有订阅者
        await self._broadcast(event)
    
    async def subscribe(
        self,
        event_type: WorkflowEventType,
        handler: Callable[[WorkflowEvent], Awaitable[None]]
    ):
        """订阅事件"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    async def _broadcast(self, event: WorkflowEvent):
        """广播事件到订阅者"""
        handlers = self.subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler failed: {e}")
```

### 事件处理器

```python
class WorkflowEventHandler:
    """工作流事件处理器"""
    
    def __init__(
        self,
        event_bus: EventBus,
        notification_service: NotificationService,
        checkpoint_manager: CheckpointManager
    ):
        self.event_bus = event_bus
        self.notification = notification_service
        self.checkpoint = checkpoint_manager
    
    async def register_handlers(self):
        """注册事件处理器"""
        await self.event_bus.subscribe(
            WorkflowEventType.WORKFLOW_STARTED,
            self._on_workflow_started
        )
        await self.event_bus.subscribe(
            WorkflowEventType.STEP_COMPLETED,
            self._on_step_completed
        )
        await self.event_bus.subscribe(
            WorkflowEventType.STEP_FAILED,
            self._on_step_failed
        )
        await self.event_bus.subscribe(
            WorkflowEventType.CONFIRMATION_REQUIRED,
            self._on_confirmation_required
        )
    
    async def _on_workflow_started(self, event: WorkflowEvent):
        """工作流开始处理"""
        await self.notification.send(
            user_id=event.user_id,
            message=f"🚀 工作流 '{event.payload['workflow_name']}' 已开始执行"
        )
    
    async def _on_step_completed(self, event: WorkflowEvent):
        """步骤完成处理"""
        # 创建检查点
        workflow = await Workflow.load(event.workflow_id)
        await self.checkpoint.create_checkpoint(
            workflow,
            trigger=CheckpointTrigger.POST_STEP
        )
        
        # 发送进度通知
        progress = event.payload.get('progress', 0)
        await self.notification.send_progress(
            user_id=event.user_id,
            workflow_id=event.workflow_id,
            progress=progress,
            message=f"✅ 步骤 '{event.payload['step_name']}' 已完成"
        )
    
    async def _on_step_failed(self, event: WorkflowEvent):
        """步骤失败处理"""
        # 创建紧急检查点
        workflow = await Workflow.load(event.workflow_id)
        await self.checkpoint.create_checkpoint(
            workflow,
            trigger=CheckpointTrigger.EMERGENCY
        )
        
        # 发送告警通知
        await self.notification.send_alert(
            user_id=event.user_id,
            level="error",
            message=f"❌ 步骤 '{event.payload['step_name']}' 执行失败: {event.payload['error']}"
        )
    
    async def _on_confirmation_required(self, event: WorkflowEvent):
        """需要人工确认处理"""
        # 发送飞书卡片消息
        await self.notification.send_confirmation_card(
            user_id=event.user_id,
            workflow_id=event.workflow_id,
            step_id=event.step_id,
            title=event.payload['title'],
            description=event.payload['description'],
            options=event.payload['options']
        )
```

---

## 持久化设计

### 数据库Schema

```sql
-- 工作流表
CREATE TABLE workflows (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    definition JSONB NOT NULL,  -- 工作流定义
    status VARCHAR(50) NOT NULL,
    context JSONB,              -- 上下文变量
    current_step_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_by VARCHAR(100),
    priority INTEGER DEFAULT 5
);

-- 步骤执行记录表
CREATE TABLE workflow_steps (
    id UUID PRIMARY KEY,
    workflow_id UUID REFERENCES workflows(id),
    step_id VARCHAR(100) NOT NULL,
    agent_type VARCHAR(100),
    status VARCHAR(50) NOT NULL,
    input JSONB,
    output JSONB,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    execution_time_seconds FLOAT,
    retry_count INTEGER DEFAULT 0
);

-- 检查点表
CREATE TABLE workflow_checkpoints (
    id UUID PRIMARY KEY,
    workflow_id UUID REFERENCES workflows(id),
    step_id VARCHAR(100),
    checkpoint_type VARCHAR(50),
    workflow_state JSONB NOT NULL,
    step_states JSONB,
    context_variables JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    memory_usage_mb FLOAT,
    disk_usage_mb FLOAT,
    recoverable BOOLEAN DEFAULT TRUE
);

-- 事件日志表
CREATE TABLE workflow_events (
    id UUID PRIMARY KEY,
    workflow_id UUID REFERENCES workflows(id),
    step_id VARCHAR(100),
    event_type VARCHAR(100) NOT NULL,
    payload JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    user_id VARCHAR(100)
);

-- 索引
CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_workflows_created_at ON workflows(created_at);
CREATE INDEX idx_steps_workflow_id ON workflow_steps(workflow_id);
CREATE INDEX idx_checkpoints_workflow_id ON workflow_checkpoints(workflow_id);
CREATE INDEX idx_events_workflow_id ON workflow_events(workflow_id);
```

---

*文档版本: 1.0*
*最后更新: 2026-03-25*
