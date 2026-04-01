"""
Agent Schemas for API requests/responses
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Any


# ================== Agent Schemas ==================

class AgentRegisterRequest(BaseModel):
    """Agent注册请求"""
    id: str = Field(..., description="Agent唯一标识，如 win-dev-01")
    name: str = Field(..., description="显示名称")
    host: str = Field(..., description="主机地址")
    port: int = Field(default=8080)
    platform: str = Field(..., description="windows/macos/linux")
    role: str = Field(default="worker", description="manager/worker")
    capabilities: List[str] = Field(default=[], description="Agent能力列表")
    opencode_port: Optional[int] = Field(default=None, description="OpenCode Server端口")
    working_dir: Optional[str] = Field(default=None, description="工作目录")
    config: dict = Field(default={})


class AgentRegisterResponse(BaseModel):
    """Agent注册响应"""
    agent_id: str
    heartbeat_interval: int = 30
    config: dict = {}
    manager_host: Optional[str] = None


class HeartbeatRequest(BaseModel):
    """心跳请求"""
    agent_id: str
    status: str = "online"
    current_task_id: Optional[str] = None
    resource_usage: dict = Field(default={}, description="CPU/Memory/Disk使用率")
    active_sessions: int = 0


class HeartbeatResponse(BaseModel):
    """心跳响应"""
    ack: bool = True
    pending_tasks: List[dict] = []
    commands: List[dict] = []


class AgentOut(BaseModel):
    """Agent输出"""
    id: str
    name: str
    host: str
    port: int
    platform: str
    role: str
    capabilities: List[str]
    status: str
    current_task_id: Optional[str]
    opencode_port: Optional[int]
    working_dir: Optional[str]
    heartbeat_at: Optional[datetime]
    registered_at: datetime

    class Config:
        from_attributes = True


# ================== Task Schemas ==================

class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    task_type: str = Field(..., description="globalbatch/build_win/build_ios/review/git_commit/notify")
    agent_id: Optional[str] = Field(default=None, description="指定Agent执行，None则自动分配")
    priority: int = Field(default=100, description="优先级，越小越优先")
    payload: dict = Field(default={}, description="任务参数")


class TaskOut(BaseModel):
    """任务输出"""
    id: str
    agent_id: str
    task_type: str
    status: str
    priority: int
    payload: dict
    result: Optional[dict]
    error: Optional[str]
    retry_count: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskResultRequest(BaseModel):
    """任务结果上报"""
    task_id: str
    success: bool
    result: dict = {}
    error: Optional[str] = None
    logs: List[str] = []


# ================== Session Schemas ==================

class SessionCreateRequest(BaseModel):
    """创建OpenCode会话请求"""
    agent_id: str
    task_id: str
    skill: str = Field(..., description="Skill名称")
    working_dir: str
    context: dict = {}


class SessionOut(BaseModel):
    """会话输出"""
    id: str
    agent_id: str
    task_id: str
    session_key: str
    skill: str
    working_dir: str
    status: str
    context: Optional[dict]
    result: Optional[dict]
    logs: List[str]
    started_at: datetime
    completed_at: Optional[datetime]
    last_activity_at: Optional[datetime]

    class Config:
        from_attributes = True


class SessionUpdateRequest(BaseModel):
    """会话更新请求"""
    status: Optional[str] = None
    result: Optional[dict] = None
    logs: Optional[List[str]] = None


# ================== POPO Message Schemas ==================

class POPOSendRequest(BaseModel):
    """发送POPO消息请求"""
    receiver: str
    message_type: str = Field(..., description="start_session/task_result/heartbeat/command")
    payload: dict


class POPOMessageOut(BaseModel):
    """POPO消息输出"""
    id: str
    message_type: str
    sender: str
    receiver: str
    payload: dict
    status: str
    created_at: datetime
    sent_at: Optional[datetime]
    acked_at: Optional[datetime]

    class Config:
        from_attributes = True


# ================== Workflow Schemas ==================

class WorkflowCreateRequest(BaseModel):
    """创建工作流请求 - 多Agent协作任务"""
    name: str
    description: str = ""
    workflow_type: str = Field(..., description="globalbatch/neteasebatch")
    params: dict = Field(default={}, description="工作流参数")


class WorkflowStepOut(BaseModel):
    """工作流步骤"""
    step_id: str
    step_name: str
    task_type: str
    agent_id: Optional[str]
    status: str
    depends_on: List[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class WorkflowOut(BaseModel):
    """工作流输出"""
    id: str
    name: str
    description: str
    workflow_type: str
    status: str
    params: dict
    steps: List[WorkflowStepOut]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


# ================== Dashboard Schemas ==================

class DashboardStats(BaseModel):
    """Dashboard统计数据"""
    total_agents: int
    online_agents: int
    busy_agents: int
    total_tasks: int
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int


class AgentWithTasks(BaseModel):
    """Agent及其任务"""
    agent: AgentOut
    current_task: Optional[TaskOut]
    recent_tasks: List[TaskOut]
    active_sessions: List[SessionOut]
