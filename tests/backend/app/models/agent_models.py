"""
CubeClaw Multi-Agent System Data Models
"""
import enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Enum, JSON, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AgentStatus(str, enum.Enum):
    online = "online"
    offline = "offline"
    busy = "busy"
    maintenance = "maintenance"


class AgentRole(str, enum.Enum):
    manager = "manager"       # 主Agent，协调任务
    worker = "worker"         # 从Agent，执行任务


class Platform(str, enum.Enum):
    windows = "windows"
    macos = "macos"
    linux = "linux"


class TaskType(str, enum.Enum):
    globalbatch = "globalbatch"
    build_win = "build_win"
    build_ios = "build_ios"
    review = "review"
    git_commit = "git_commit"
    notify = "notify"


class SessionStatus(str, enum.Enum):
    starting = "starting"
    running = "running"
    completed = "completed"
    failed = "failed"
    timeout = "timeout"


class Agent(Base):
    """Agent 实体 - 运行在各机器上的Agent实例"""
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g., "win-dev-01"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    host: Mapped[str] = mapped_column(String(256), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=8080)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    role: Mapped[AgentRole] = mapped_column(Enum(AgentRole), default=AgentRole.worker)
    capabilities: Mapped[list] = mapped_column(JSON, default=[])
    status: Mapped[AgentStatus] = mapped_column(Enum(AgentStatus), default=AgentStatus.offline)
    current_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    opencode_port: Mapped[int | None] = mapped_column(Integer, nullable=True)  # OpenCode Server port
    working_dir: Mapped[str | None] = mapped_column(String(512), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default={})
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentTask(Base):
    """Agent任务 - Manager分发给Agent的任务"""
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/assigned/running/success/failed
    priority: Mapped[int] = mapped_column(Integer, default=100)
    payload: Mapped[dict] = mapped_column(JSON, default={})
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OpenCodeSession(Base):
    """OpenCode会话 - Agent与OpenCode的交互会话"""
    __tablename__ = "opencode_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_key: Mapped[str] = mapped_column(String(128), unique=True)  # OpenCode session ID
    skill: Mapped[str] = mapped_column(String(64), nullable=False)
    working_dir: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.starting)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    logs: Mapped[list] = mapped_column(JSON, default=[])
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class POPOMessage(Base):
    """POPO消息 - Agent间通信消息记录"""
    __tablename__ = "popo_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False)  # start_session/task_result/heartbeat/command
    sender: Mapped[str] = mapped_column(String(64), nullable=False)
    receiver: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/sent/acked/failed
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
