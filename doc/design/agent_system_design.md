# SailZen AI Agent 系统设计文档

## 概述

本设计实现一个基础的 AI Agent 系统，支持：
1. 持续轮询未处理的 User Prompt
2. 基于优先级自动调度 Agent 执行任务
3. 实时跟踪和监控 Agent 状态
4. 向前端反馈执行状态和结果

---

## 1. 数据模型设计

### 1.1 核心 ORM 模型

```python
# sail_server/data/agent.py

# ============================================================================
# ORM Models - User Prompt 队列
# ============================================================================

class UserPrompt(ORMBase):
    """
    用户提示表 - 存储用户提交的待处理请求
    状态流转: pending -> scheduled -> processing -> completed/failed/cancelled
    """
    __tablename__ = "user_prompts"

    id = Column(Integer, primary_key=True)
    
    # 用户请求内容
    content = Column(Text, nullable=False)  # 用户的原始请求内容
    prompt_type = Column(String, default='general')  # general | code | analysis | writing | data
    context = Column(JSONB, default={})  # 附加上下文信息
    
    # 优先级和调度
    priority = Column(Integer, default=5)  # 1-10, 1为最高优先级
    status = Column(String, default='pending')  # pending | scheduled | processing | completed | failed | cancelled
    
    # 关联信息
    created_by = Column(String, nullable=True)  # 用户标识
    session_id = Column(String, nullable=True)  # 会话ID，用于关联一组相关请求
    parent_prompt_id = Column(Integer, ForeignKey("user_prompts.id", ondelete="SET NULL"), nullable=True)
    
    # 时间戳
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    scheduled_at = Column(TIMESTAMP, nullable=True)  # 计划执行时间
    started_at = Column(TIMESTAMP, nullable=True)   # 实际开始时间
    completed_at = Column(TIMESTAMP, nullable=True)  # 完成时间
    
    # 关联
    agent_tasks = relationship("AgentTask", back_populates="prompt", cascade="all, delete-orphan")


# ============================================================================
# ORM Models - Agent 任务
# ============================================================================

class AgentTask(ORMBase):
    """
    Agent 任务表 - 记录每个 Agent 执行实例
    状态流转: created -> preparing -> running -> paused -> completed/failed/cancelled
    """
    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey("user_prompts.id", ondelete="CASCADE"), nullable=False)
    
    # Agent 配置
    agent_type = Column(String, default='general')  # general | coder | analyst | writer
    agent_config = Column(JSONB, default={})  # Agent 特定配置
    
    # 执行状态
    status = Column(String, default='created')  # created | preparing | running | paused | completed | failed | cancelled
    progress = Column(Integer, default=0)  # 0-100 百分比
    
    # 时间戳
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    started_at = Column(TIMESTAMP, nullable=True)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    completed_at = Column(TIMESTAMP, nullable=True)
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    
    # 资源限制
    max_iterations = Column(Integer, default=100)  # 最大迭代次数
    timeout_seconds = Column(Integer, default=3600)  # 超时时间
    
    # 关联
    prompt = relationship("UserPrompt", back_populates="agent_tasks")
    steps = relationship("AgentStep", back_populates="task", cascade="all, delete-orphan", order_by="AgentStep.step_number")
    outputs = relationship("AgentOutput", back_populates="task", cascade="all, delete-orphan")


class AgentStep(ORMBase):
    """
    Agent 执行步骤表 - 记录 Agent 的每一步操作
    """
    __tablename__ = "agent_steps"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False)
    
    # 步骤信息
    step_number = Column(Integer, nullable=False)
    step_type = Column(String, nullable=False)  # thought | action | observation | error | completion
    
    # 内容
    title = Column(String, nullable=True)  # 步骤标题
    content = Column(Text, nullable=True)  # 详细内容
    content_summary = Column(String, nullable=True)  # 内容摘要（用于列表展示）
    
    # 元数据
    meta_data = Column(JSONB, default={})  # 附加信息，如工具调用参数等
    
    # 时间戳
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    duration_ms = Column(Integer, nullable=True)  # 步骤执行耗时
    
    # 关联
    task = relationship("AgentTask", back_populates="steps")


class AgentOutput(ORMBase):
    """
    Agent 输出结果表 - 存储 Agent 的最终产出
    """
    __tablename__ = "agent_outputs"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False)
    
    # 输出内容
    output_type = Column(String, nullable=False)  # text | code | file | json | error
    content = Column(Text, nullable=True)  # 文本内容
    file_path = Column(String, nullable=True)  # 文件路径（如果是文件输出）
    
    # 元数据
    meta_data = Column(JSONB, default={})  # 如代码语言、文件类型等
    
    # 审核状态
    review_status = Column(String, default='pending')  # pending | approved | rejected
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(TIMESTAMP, nullable=True)
    review_notes = Column(Text, nullable=True)
    
    # 关联
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    task = relationship("AgentTask", back_populates="outputs")


# ============================================================================
# ORM Models - Agent 调度器状态
# ============================================================================

class AgentSchedulerState(ORMBase):
    """
    Agent 调度器状态表 - 单例表，记录调度器运行状态
    """
    __tablename__ = "agent_scheduler_state"

    id = Column(Integer, primary_key=True, default=1)  # 单例
    
    # 调度器状态
    is_running = Column(Boolean, default=False)  # 调度器是否运行中
    last_poll_at = Column(TIMESTAMP, nullable=True)  # 上次轮询时间
    active_agent_count = Column(Integer, default=0)  # 当前活跃 Agent 数量
    max_concurrent_agents = Column(Integer, default=3)  # 最大并发数
    
    # 统计信息
    total_processed = Column(Integer, default=0)  # 总共处理数量
    total_failed = Column(Integer, default=0)     # 失败数量
    
    # 时间戳
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
```

---

## 2. 数据传输对象 (DTO)

```python
# sail_server/data/agent.py (continued)

# ============================================================================
# Data Transfer Objects - User Prompt
# ============================================================================

@dataclass
class UserPromptData:
    """用户提示数据传输对象"""
    content: str
    id: int = field(default=-1)
    prompt_type: str = "general"
    context: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    status: str = "pending"
    created_by: Optional[str] = None
    session_id: Optional[str] = None
    parent_prompt_id: Optional[int] = None
    created_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm: UserPrompt):
        return cls(
            id=orm.id,
            content=orm.content,
            prompt_type=orm.prompt_type,
            context=orm.context or {},
            priority=orm.priority,
            status=orm.status,
            created_by=orm.created_by,
            session_id=orm.session_id,
            parent_prompt_id=orm.parent_prompt_id,
            created_at=orm.created_at,
            scheduled_at=orm.scheduled_at,
            started_at=orm.started_at,
            completed_at=orm.completed_at,
        )

    def create_orm(self) -> UserPrompt:
        return UserPrompt(
            content=self.content,
            prompt_type=self.prompt_type,
            context=self.context,
            priority=self.priority,
            status=self.status,
            created_by=self.created_by,
            session_id=self.session_id,
            parent_prompt_id=self.parent_prompt_id,
        )


@dataclass
class UserPromptCreateRequest:
    """创建用户提示请求"""
    content: str
    prompt_type: str = "general"
    context: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    session_id: Optional[str] = None
    parent_prompt_id: Optional[int] = None


# ============================================================================
# Data Transfer Objects - Agent Task
# ============================================================================

@dataclass
class AgentTaskData:
    """Agent 任务数据传输对象"""
    prompt_id: int
    id: int = field(default=-1)
    agent_type: str = "general"
    agent_config: Dict[str, Any] = field(default_factory=dict)
    status: str = "created"
    progress: int = 0
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    current_step: Optional['AgentStepData'] = None  # 当前步骤
    step_count: int = 0
    
    @classmethod
    def read_from_orm(cls, orm: AgentTask, current_step=None, step_count: int = 0):
        return cls(
            id=orm.id,
            prompt_id=orm.prompt_id,
            agent_type=orm.agent_type,
            agent_config=orm.agent_config or {},
            status=orm.status,
            progress=orm.progress,
            created_at=orm.created_at,
            started_at=orm.started_at,
            updated_at=orm.updated_at,
            completed_at=orm.completed_at,
            error_message=orm.error_message,
            error_code=orm.error_code,
            current_step=current_step,
            step_count=step_count,
        )


@dataclass
class AgentStepData:
    """Agent 步骤数据传输对象"""
    task_id: int
    step_number: int
    step_type: str
    id: int = field(default=-1)
    title: Optional[str] = None
    content: Optional[str] = None
    content_summary: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    @classmethod
    def read_from_orm(cls, orm: AgentStep):
        return cls(
            id=orm.id,
            task_id=orm.task_id,
            step_number=orm.step_number,
            step_type=orm.step_type,
            title=orm.title,
            content=orm.content,
            content_summary=orm.content_summary,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            duration_ms=orm.duration_ms,
        )


@dataclass
class AgentOutputData:
    """Agent 输出数据传输对象"""
    task_id: int
    output_type: str
    id: int = field(default=-1)
    content: Optional[str] = None
    file_path: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)
    review_status: str = "pending"
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm: AgentOutput):
        return cls(
            id=orm.id,
            task_id=orm.task_id,
            output_type=orm.output_type,
            content=orm.content,
            file_path=orm.file_path,
            meta_data=orm.meta_data or {},
            review_status=orm.review_status,
            reviewed_by=orm.reviewed_by,
            reviewed_at=orm.reviewed_at,
            review_notes=orm.review_notes,
            created_at=orm.created_at,
        )


# ============================================================================
# Data Transfer Objects - Scheduler State
# ============================================================================

@dataclass
class SchedulerStateData:
    """调度器状态数据传输对象"""
    is_running: bool = False
    last_poll_at: Optional[datetime] = None
    active_agent_count: int = 0
    max_concurrent_agents: int = 3
    total_processed: int = 0
    total_failed: int = 0
    updated_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm: AgentSchedulerState):
        return cls(
            is_running=orm.is_running,
            last_poll_at=orm.last_poll_at,
            active_agent_count=orm.active_agent_count,
            max_concurrent_agents=orm.max_concurrent_agents,
            total_processed=orm.total_processed,
            total_failed=orm.total_failed,
            updated_at=orm.updated_at,
        )


# ============================================================================
# Response Models
# ============================================================================

@dataclass
class AgentTaskDetailResponse:
    """Agent 任务详情响应"""
    task: AgentTaskData
    steps: List[AgentStepData]
    outputs: List[AgentOutputData]
    prompt: UserPromptData


@dataclass
class AgentStreamEvent:
    """Agent 实时流事件 - 用于 WebSocket/SSE"""
    event_type: str  # task_started | step_update | progress_update | task_completed | task_failed | output_ready
    task_id: int
    timestamp: datetime
    data: Dict[str, Any]  # 事件特定数据
```

---

## 3. 核心调度器设计

```python
# sail_server/model/agent/scheduler.py

class AgentScheduler:
    """
    Agent 调度器 - 核心调度逻辑
    
    职责：
    1. 持续轮询数据库中的待处理 User Prompt
    2. 根据优先级选择最紧急的任务
    3. 管理 Agent 生命周期（创建、启动、监控、清理）
    4. 更新任务状态到数据库
    5. 触发状态变更事件（用于前端实时更新）
    """
    
    def __init__(self, db_session_factory, poll_interval=5.0):
        self.db_factory = db_session_factory
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._active_agents: Dict[int, 'AgentRunner'] = {}  # task_id -> AgentRunner
        self._event_callbacks: List[Callable] = []  # 状态变更回调
        self._lock = asyncio.Lock()
    
    async def start(self):
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Agent scheduler started")
    
    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # 取消所有运行的 Agent
        for runner in self._active_agents.values():
            await runner.cancel()
        logger.info("Agent scheduler stopped")
    
    async def _poll_loop(self):
        """主轮询循环"""
        while self._running:
            try:
                await self._poll_and_schedule()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def _poll_and_schedule(self):
        """轮询并调度任务"""
        with get_db_session() as db:
            # 获取调度器状态
            state = db.query(AgentSchedulerState).first()
            if not state:
                state = AgentSchedulerState()
                db.add(state)
                db.commit()
            
            # 检查并发限制
            available_slots = state.max_concurrent_agents - len(self._active_agents)
            if available_slots <= 0:
                return
            
            # 获取最紧急的待处理 Prompt
            pending_prompts = db.query(UserPrompt).filter(
                UserPrompt.status == 'pending'
            ).order_by(
                UserPrompt.priority.asc(),  # 优先级高的在前
                UserPrompt.created_at.asc()  # 同优先级按时间
            ).limit(available_slots).all()
            
            for prompt in pending_prompts:
                await self._schedule_prompt(db, prompt)
            
            # 更新调度器状态
            state.last_poll_at = datetime.utcnow()
            state.active_agent_count = len(self._active_agents)
            db.commit()
    
    async def _schedule_prompt(self, db: Session, prompt: UserPrompt):
        """调度一个 Prompt 执行"""
        async with self._lock:
            # 更新 Prompt 状态
            prompt.status = 'scheduled'
            prompt.scheduled_at = datetime.utcnow()
            
            # 创建 Agent Task
            task = AgentTask(
                prompt_id=prompt.id,
                agent_type=self._determine_agent_type(prompt),
                agent_config=self._build_agent_config(prompt),
                status='created',
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 创建 Agent Runner 并启动
            runner = AgentRunner(task.id, self.db_factory, self._on_agent_event)
            self._active_agents[task.id] = runner
            
            # 异步启动 Agent（不阻塞调度循环）
            asyncio.create_task(runner.start())
            
            # 触发事件
            self._emit_event('task_scheduled', {'task_id': task.id, 'prompt_id': prompt.id})
    
    def _determine_agent_type(self, prompt: UserPrompt) -> str:
        """根据 Prompt 内容决定使用哪种 Agent"""
        type_mapping = {
            'code': 'coder',
            'analysis': 'analyst',
            'writing': 'writer',
        }
        return type_mapping.get(prompt.prompt_type, 'general')
    
    def _build_agent_config(self, prompt: UserPrompt) -> Dict[str, Any]:
        """构建 Agent 配置"""
        return {
            'prompt_content': prompt.content,
            'context': prompt.context,
            'max_iterations': 100,
            'timeout_seconds': 3600,
        }
    
    def _on_agent_event(self, task_id: int, event_type: str, data: Dict[str, Any]):
        """Agent 事件回调"""
        # 转发事件到前端
        self._emit_event(event_type, {'task_id': task_id, **data})
        
        # 如果任务完成或失败，从活跃列表中移除
        if event_type in ('task_completed', 'task_failed', 'task_cancelled'):
            self._active_agents.pop(task_id, None)
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """触发状态变更事件"""
        event = AgentStreamEvent(
            event_type=event_type,
            task_id=data.get('task_id', 0),
            timestamp=datetime.utcnow(),
            data=data
        )
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
    
    def subscribe(self, callback: Callable[[AgentStreamEvent], None]):
        """订阅状态变更事件"""
        self._event_callbacks.append(callback)
    
    def unsubscribe(self, callback: Callable[[AgentStreamEvent], None]):
        """取消订阅"""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)
```

---

## 4. Agent Runner 设计

```python
# sail_server/model/agent/runner.py

class AgentRunner:
    """
    Agent 运行器 - 管理单个 Agent 的执行生命周期
    
    职责：
    1. 加载 Agent 配置
    2. 执行 Agent 逻辑（调用 LLM、工具等）
    3. 记录执行步骤
    4. 更新任务状态
    5. 生成输出结果
    """
    
    def __init__(self, task_id: int, db_factory, event_callback):
        self.task_id = task_id
        self.db_factory = db_factory
        self.event_callback = event_callback
        self._cancelled = False
        self._current_step = 0
    
    async def start(self):
        """启动 Agent 执行"""
        start_time = datetime.utcnow()
        
        with get_db_session() as db:
            task = db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
            if not task:
                logger.error(f"Task {self.task_id} not found")
                return
            
            # 更新任务状态
            task.status = 'running'
            task.started_at = start_time
            
            # 更新 Prompt 状态
            prompt = task.prompt
            prompt.status = 'processing'
            prompt.started_at = start_time
            
            db.commit()
        
        self._emit_event('task_started', {'started_at': start_time.isoformat()})
        
        try:
            # 执行 Agent 逻辑
            await self._run_agent_logic()
            
            # 标记完成
            await self._complete_task()
            
        except asyncio.CancelledError:
            await self._cancel_task()
            raise
        except Exception as e:
            await self._fail_task(str(e))
    
    async def _run_agent_logic(self):
        """Agent 核心逻辑 - 可扩展为不同类型的 Agent"""
        # 示例：简单的迭代执行
        max_iterations = 10  # 从配置中读取
        
        for i in range(max_iterations):
            if self._cancelled:
                break
            
            self._current_step = i + 1
            
            # 记录思考步骤
            await self._add_step('thought', f'思考步骤 {i+1}', '正在分析问题...')
            
            # 模拟执行（实际应调用 LLM）
            await asyncio.sleep(0.5)
            
            # 记录行动步骤
            await self._add_step('action', f'执行步骤 {i+1}', '执行相应操作...')
            
            # 更新进度
            progress = int((i + 1) / max_iterations * 100)
            await self._update_progress(progress)
            
            # 模拟完成条件
            if i >= max_iterations - 1:
                await self._add_step('completion', '任务完成', '所有步骤已执行完毕')
                break
    
    async def _add_step(self, step_type: str, title: str, content: str, meta_data: Dict = None):
        """添加执行步骤"""
        with get_db_session() as db:
            step = AgentStep(
                task_id=self.task_id,
                step_number=self._current_step,
                step_type=step_type,
                title=title,
                content=content,
                content_summary=content[:100] + '...' if len(content) > 100 else content,
                meta_data=meta_data or {},
            )
            db.add(step)
            db.commit()
            db.refresh(step)
            
            step_data = AgentStepData.read_from_orm(step)
        
        self._emit_event('step_update', {
            'step': step_data,
            'step_number': self._current_step,
        })
    
    async def _update_progress(self, progress: int):
        """更新任务进度"""
        with get_db_session() as db:
            task = db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
            task.progress = progress
            db.commit()
        
        self._emit_event('progress_update', {'progress': progress})
    
    async def _complete_task(self):
        """标记任务完成"""
        completed_at = datetime.utcnow()
        
        with get_db_session() as db:
            task = db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
            task.status = 'completed'
            task.progress = 100
            task.completed_at = completed_at
            
            # 创建输出结果
            output = AgentOutput(
                task_id=self.task_id,
                output_type='text',
                content='Agent 执行完成的结果内容...',
            )
            db.add(output)
            
            # 更新 Prompt 状态
            prompt = task.prompt
            prompt.status = 'completed'
            prompt.completed_at = completed_at
            
            db.commit()
        
        self._emit_event('task_completed', {
            'completed_at': completed_at.isoformat(),
            'output_id': output.id,
        })
    
    async def _fail_task(self, error_message: str):
        """标记任务失败"""
        failed_at = datetime.utcnow()
        
        with get_db_session() as db:
            task = db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
            task.status = 'failed'
            task.error_message = error_message
            task.completed_at = failed_at
            
            # 更新 Prompt 状态
            prompt = task.prompt
            prompt.status = 'failed'
            prompt.completed_at = failed_at
            
            db.commit()
        
        self._emit_event('task_failed', {
            'error_message': error_message,
            'failed_at': failed_at.isoformat(),
        })
    
    async def _cancel_task(self):
        """取消任务"""
        cancelled_at = datetime.utcnow()
        
        with get_db_session() as db:
            task = db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
            task.status = 'cancelled'
            task.completed_at = cancelled_at
            
            prompt = task.prompt
            prompt.status = 'cancelled'
            prompt.completed_at = cancelled_at
            
            db.commit()
        
        self._emit_event('task_cancelled', {
            'cancelled_at': cancelled_at.isoformat(),
        })
    
    async def cancel(self):
        """取消执行"""
        self._cancelled = True
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """发送事件"""
        if self.event_callback:
            self.event_callback(self.task_id, event_type, data)
```

---

## 5. API 设计

```python
# sail_server/router/agent.py

from litestar import Router, Controller, get, post, put, delete, Request
from litestar.dto import DataclassDTO
from litestar.dto.config import DTOConfig
from litestar.handlers import WebsocketListener

# DTOs
class UserPromptWriteDTO(DataclassDTO[UserPromptCreateRequest]):
    config = DTOConfig(include={'content', 'prompt_type', 'context', 'priority', 'session_id'})

class UserPromptReadDTO(DataclassDTO[UserPromptData]):
    pass

class AgentTaskReadDTO(DataclassDTO[AgentTaskData]):
    pass

# ============================================================================
# Controllers
# ============================================================================

class UserPromptController(Controller):
    """用户提示控制器"""
    path = "/prompt"
    dto = UserPromptWriteDTO
    return_dto = UserPromptReadDTO
    
    @post("")
    async def create_prompt(
        self,
        router_dependency: Generator[Session, None, None],
        data: UserPromptCreateRequest,
    ) -> UserPromptData:
        """提交新的用户提示"""
        db = next(router_dependency)
        prompt_data = UserPromptData(
            content=data.content,
            prompt_type=data.prompt_type,
            context=data.context,
            priority=data.priority,
            session_id=data.session_id,
            status='pending',
        )
        prompt = prompt_data.create_orm()
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        return UserPromptData.read_from_orm(prompt)
    
    @get("")
    async def list_prompts(
        self,
        router_dependency: Generator[Session, None, None],
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[UserPromptData]:
        """获取提示列表"""
        db = next(router_dependency)
        query = db.query(UserPrompt)
        if status:
            query = query.filter(UserPrompt.status == status)
        prompts = query.order_by(UserPrompt.created_at.desc()).offset(skip).limit(limit).all()
        return [UserPromptData.read_from_orm(p) for p in prompts]
    
    @get("/{id:int}")
    async def get_prompt(
        self,
        router_dependency: Generator[Session, None, None],
        id: int,
    ) -> UserPromptData:
        """获取单个提示详情"""
        db = next(router_dependency)
        prompt = db.query(UserPrompt).filter(UserPrompt.id == id).first()
        if not prompt:
            raise NotFoundException(f"Prompt {id} not found")
        return UserPromptData.read_from_orm(prompt)
    
    @post("/{id:int}/cancel")
    async def cancel_prompt(
        self,
        router_dependency: Generator[Session, None, None],
        id: int,
    ) -> UserPromptData:
        """取消待处理的提示"""
        db = next(router_dependency)
        prompt = db.query(UserPrompt).filter(UserPrompt.id == id).first()
        if not prompt:
            raise NotFoundException(f"Prompt {id} not found")
        if prompt.status not in ('pending', 'scheduled'):
            raise ValueError(f"Cannot cancel prompt with status {prompt.status}")
        
        prompt.status = 'cancelled'
        prompt.completed_at = datetime.utcnow()
        db.commit()
        return UserPromptData.read_from_orm(prompt)


class AgentTaskController(Controller):
    """Agent 任务控制器"""
    path = "/task"
    return_dto = AgentTaskReadDTO
    
    @get("")
    async def list_tasks(
        self,
        router_dependency: Generator[Session, None, None],
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[AgentTaskData]:
        """获取任务列表"""
        db = next(router_dependency)
        query = db.query(AgentTask)
        if status:
            query = query.filter(AgentTask.status == status)
        tasks = query.order_by(AgentTask.created_at.desc()).offset(skip).limit(limit).all()
        
        result = []
        for task in tasks:
            step_count = db.query(func.count(AgentStep.id)).filter(
                AgentStep.task_id == task.id
            ).scalar() or 0
            result.append(AgentTaskData.read_from_orm(task, step_count=step_count))
        return result
    
    @get("/{id:int}")
    async def get_task(
        self,
        router_dependency: Generator[Session, None, None],
        id: int,
    ) -> AgentTaskDetailResponse:
        """获取任务详情（包含步骤和输出）"""
        db = next(router_dependency)
        task = db.query(AgentTask).filter(AgentTask.id == id).first()
        if not task:
            raise NotFoundException(f"Task {id} not found")
        
        steps = db.query(AgentStep).filter(AgentStep.task_id == id).order_by(AgentStep.step_number).all()
        outputs = db.query(AgentOutput).filter(AgentOutput.task_id == id).all()
        
        return AgentTaskDetailResponse(
            task=AgentTaskData.read_from_orm(task),
            steps=[AgentStepData.read_from_orm(s) for s in steps],
            outputs=[AgentOutputData.read_from_orm(o) for o in outputs],
            prompt=UserPromptData.read_from_orm(task.prompt),
        )
    
    @get("/{id:int}/steps")
    async def get_task_steps(
        self,
        router_dependency: Generator[Session, None, None],
        id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AgentStepData]:
        """获取任务步骤列表"""
        db = next(router_dependency)
        steps = db.query(AgentStep).filter(
            AgentStep.task_id == id
        ).order_by(AgentStep.step_number).offset(skip).limit(limit).all()
        return [AgentStepData.read_from_orm(s) for s in steps]
    
    @post("/{id:int}/cancel")
    async def cancel_task(
        self,
        router_dependency: Generator[Session, None, None],
        id: int,
    ) -> AgentTaskData:
        """取消正在运行的任务"""
        db = next(router_dependency)
        task = db.query(AgentTask).filter(AgentTask.id == id).first()
        if not task:
            raise NotFoundException(f"Task {id} not found")
        
        # TODO: 调用调度器取消任务
        task.status = 'cancelled'
        task.completed_at = datetime.utcnow()
        db.commit()
        
        return AgentTaskData.read_from_orm(task)


class SchedulerController(Controller):
    """调度器状态控制器"""
    path = "/scheduler"
    
    @get("/status")
    async def get_status(
        self,
        router_dependency: Generator[Session, None, None],
    ) -> SchedulerStateData:
        """获取调度器状态"""
        db = next(router_dependency)
        state = db.query(AgentSchedulerState).first()
        if not state:
            state = AgentSchedulerState()
            db.add(state)
            db.commit()
        return SchedulerStateData.read_from_orm(state)
    
    @post("/start")
    async def start_scheduler(
        self,
        router_dependency: Generator[Session, None, None],
    ) -> SchedulerStateData:
        """启动调度器"""
        # TODO: 调用全局调度器实例
        db = next(router_dependency)
        state = db.query(AgentSchedulerState).first()
        if not state:
            state = AgentSchedulerState()
            db.add(state)
        state.is_running = True
        db.commit()
        return SchedulerStateData.read_from_orm(state)
    
    @post("/stop")
    async def stop_scheduler(
        self,
        router_dependency: Generator[Session, None, None],
    ) -> SchedulerStateData:
        """停止调度器"""
        db = next(router_dependency)
        state = db.query(AgentSchedulerState).first()
        if state:
            state.is_running = False
            db.commit()
        return SchedulerStateData.read_from_orm(state)


# ============================================================================
# WebSocket for Real-time Updates
# ============================================================================

class AgentEventWebSocket(WebsocketListener):
    """Agent 事件 WebSocket - 实时推送状态更新"""
    path = "/ws/agent-events"
    
    async def on_accept(self, websocket) -> None:
        """连接建立时订阅事件"""
        self.websocket = websocket
        # 获取全局调度器并订阅
        scheduler = get_agent_scheduler()
        scheduler.subscribe(self._on_event)
    
    async def on_disconnect(self, websocket, close_code: int) -> None:
        """连接断开时取消订阅"""
        scheduler = get_agent_scheduler()
        scheduler.unsubscribe(self._on_event)
    
    async def _on_event(self, event: AgentStreamEvent):
        """事件回调 - 发送给客户端"""
        await self.websocket.send_json({
            'event_type': event.event_type,
            'task_id': event.task_id,
            'timestamp': event.timestamp.isoformat(),
            'data': event.data,
        })


# ============================================================================
# Router
# ============================================================================

router = Router(
    path="/agent",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        UserPromptController,
        AgentTaskController,
        SchedulerController,
        AgentEventWebSocket,
    ],
)
```

---

## 6. 前端状态反馈设计

```typescript
// 前端 API 客户端示例

interface AgentAPI {
  // 提交用户提示
  createPrompt(request: PromptCreateRequest): Promise<UserPrompt>;
  
  // 获取提示列表
  listPrompts(params?: { status?: string; skip?: number; limit?: number }): Promise<UserPrompt[]>;
  
  // 获取任务详情
  getTask(id: number): Promise<AgentTaskDetail>;
  
  // 获取调度器状态
  getSchedulerStatus(): Promise<SchedulerState>;
  
  // WebSocket 实时事件
  connectEventStream(onEvent: (event: AgentStreamEvent) => void): WebSocket;
}

// 状态管理 (Zustand Store)
interface AgentStore {
  // 状态
  prompts: UserPrompt[];
  tasks: AgentTask[];
  currentTask: AgentTaskDetail | null;
  schedulerState: SchedulerState | null;
  wsConnection: WebSocket | null;
  
  // 动作
  submitPrompt(content: string, options?: PromptOptions): Promise<void>;
  loadTasks(): Promise<void>;
  loadTaskDetail(taskId: number): Promise<void>;
  connectRealtimeUpdates(): void;
  disconnectRealtimeUpdates(): void;
  
  // 实时更新处理
  handleAgentEvent(event: AgentStreamEvent): void;
}

// 组件使用示例
function AgentMonitor() {
  const { tasks, schedulerState, connectRealtimeUpdates } = useAgentStore();
  
  useEffect(() => {
    connectRealtimeUpdates();
  }, []);
  
  return (
    <div>
      <SchedulerStatus state={schedulerState} />
      <TaskList tasks={tasks} />
    </div>
  );
}
```

---

## 7. 数据库迁移

```sql
-- migration/xxx_create_agent_tables.sql

-- 用户提示表
CREATE TABLE user_prompts (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    prompt_type VARCHAR(50) DEFAULT 'general',
    context JSONB DEFAULT '{}',
    priority INTEGER DEFAULT 5,
    status VARCHAR(50) DEFAULT 'pending',
    created_by VARCHAR(255),
    session_id VARCHAR(255),
    parent_prompt_id INTEGER REFERENCES user_prompts(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_user_prompts_status ON user_prompts(status);
CREATE INDEX idx_user_prompts_priority ON user_prompts(priority);
CREATE INDEX idx_user_prompts_created_at ON user_prompts(created_at);

-- Agent 任务表
CREATE TABLE agent_tasks (
    id SERIAL PRIMARY KEY,
    prompt_id INTEGER NOT NULL REFERENCES user_prompts(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) DEFAULT 'general',
    agent_config JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'created',
    progress INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    error_code VARCHAR(100),
    max_iterations INTEGER DEFAULT 100,
    timeout_seconds INTEGER DEFAULT 3600
);

CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX idx_agent_tasks_prompt_id ON agent_tasks(prompt_id);

-- Agent 步骤表
CREATE TABLE agent_steps (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    step_type VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    content TEXT,
    content_summary VARCHAR(200),
    meta_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER
);

CREATE INDEX idx_agent_steps_task_id ON agent_steps(task_id);
CREATE INDEX idx_agent_steps_step_number ON agent_steps(task_id, step_number);

-- Agent 输出表
CREATE TABLE agent_outputs (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    output_type VARCHAR(50) NOT NULL,
    content TEXT,
    file_path VARCHAR(500),
    meta_data JSONB DEFAULT '{}',
    review_status VARCHAR(50) DEFAULT 'pending',
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_outputs_task_id ON agent_outputs(task_id);

-- 调度器状态表（单例）
CREATE TABLE agent_scheduler_state (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    is_running BOOLEAN DEFAULT FALSE,
    last_poll_at TIMESTAMP,
    active_agent_count INTEGER DEFAULT 0,
    max_concurrent_agents INTEGER DEFAULT 3,
    total_processed INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO agent_scheduler_state (id) VALUES (1) ON CONFLICT DO NOTHING;
```

---

## 8. 与 Server 集成

```python
# server.py 修改

class SailServer:
    def init(self):
        # ... existing code ...
        
        from sail_server.router.agent import router as agent_router
        
        self.api_router = Router(
            path=self.api_endpoint,
            route_handlers=[
                # ... existing routers ...
                agent_router,
            ],
        )
        
        # ...
    
    async def on_startup(self):
        logger.info("Server starting up...")
        # 启动 Agent 调度器
        from sail_server.model.agent.scheduler import AgentScheduler, get_agent_scheduler
        scheduler = get_agent_scheduler()
        await scheduler.start()
        logger.info("Agent scheduler started")
    
    async def on_shutdown(self):
        logger.info("Server shutting down...")
        # 停止 Agent 调度器
        from sail_server.model.agent.scheduler import get_agent_scheduler
        scheduler = get_agent_scheduler()
        await scheduler.stop()
        logger.info("Agent scheduler stopped")
```

---

## 9. 文件结构

```
sail_server/
├── data/
│   ├── __init__.py
│   └── agent.py              # 数据模型和 DTOs
├── model/
│   ├── __init__.py
│   └── agent/
│       ├── __init__.py
│       ├── scheduler.py      # 调度器核心逻辑
│       ├── runner.py         # Agent 运行器
│       └── agents/           # 不同类型的 Agent 实现
│           ├── __init__.py
│           ├── base.py       # Agent 基类
│           ├── general.py    # 通用 Agent
│           ├── coder.py      # 代码 Agent
│           └── analyst.py    # 分析 Agent
├── router/
│   ├── __init__.py
│   └── agent.py              # API 路由
└── migration/
    └── xxx_create_agent_tables.sql
```

---

## 10. 总结

本设计实现了一个基础的 AI Agent 系统，核心特性包括：

1. **数据模型**：UserPrompt → AgentTask → AgentStep/AgentOutput 的层级结构
2. **优先级调度**：基于优先级和时间的调度策略
3. **并发控制**：可配置的最大并发 Agent 数量
4. **状态追踪**：完整的生命周期状态管理和进度追踪
5. **实时反馈**：WebSocket 实时推送状态更新
6. **可扩展性**：支持不同类型的 Agent 实现

后续可扩展：
- 支持更多 Agent 类型（coder, analyst, writer 等）
- 实现真正的 LLM 调用和工具使用
- 添加任务重试和失败恢复机制
- 支持更复杂的优先级策略（如权重、截止时间等）
- 添加 Agent 间的协作机制
