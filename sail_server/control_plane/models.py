from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sail_server.control_plane.db import ControlPlaneORMBase


class RemoteWorkspace(ControlPlaneORMBase):
    __tablename__ = "remote_workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    local_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    policy_profile: Mapped[str] = mapped_column(String(100), default="default")
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    inventory_source: Mapped[str] = mapped_column(String(50), default="edge-config")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    sessions: Mapped[list["OpenCodeSession"]] = relationship(back_populates="workspace")


class EdgeNode(ControlPlaneORMBase):
    __tablename__ = "edge_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    host_name: Mapped[str] = mapped_column(String(200), nullable=False)
    runtime_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    auth_mode: Mapped[str] = mapped_column(String(50), default="token")
    ack_cursor: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="offline")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    sessions: Mapped[list["OpenCodeSession"]] = relationship(back_populates="edge_node")


class OpenCodeSession(ControlPlaneORMBase):
    __tablename__ = "opencode_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("remote_workspaces.id"), index=True
    )
    edge_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("edge_nodes.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(50), default="stopped")
    desired_state: Mapped[str] = mapped_column(String(50), default="stopped")
    observed_state: Mapped[str] = mapped_column(String(50), default="unknown")
    branch_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    local_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    process_info: Mapped[dict] = mapped_column(JSON, default=dict)
    diagnostics: Mapped[dict] = mapped_column(JSON, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    workspace: Mapped[RemoteWorkspace] = relationship(back_populates="sessions")
    edge_node: Mapped[EdgeNode | None] = relationship(back_populates="sessions")
    actions: Mapped[list["SessionAction"]] = relationship(back_populates="session")
    events: Mapped[list["SessionEvent"]] = relationship(back_populates="session")


class SessionAction(ControlPlaneORMBase):
    __tablename__ = "session_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("opencode_sessions.id"), nullable=True, index=True
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_workspaces.id"), nullable=True, index=True
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    initiator_id: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), default="safe-auto")
    confirmation_status: Mapped[str] = mapped_column(String(50), default="not-required")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    edge_ack_status: Mapped[str] = mapped_column(String(50), default="pending")
    edge_ack_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    session: Mapped[OpenCodeSession | None] = relationship(back_populates="actions")


class SessionEvent(ControlPlaneORMBase):
    __tablename__ = "session_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    sequence_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("opencode_sessions.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_source: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    event_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    session: Mapped[OpenCodeSession | None] = relationship(back_populates="events")


class InteractionThread(ControlPlaneORMBase):
    __tablename__ = "interaction_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), default="feishu")
    chat_id: Mapped[str] = mapped_column(String(200), index=True)
    sender_open_id: Mapped[str] = mapped_column(String(200), index=True)
    active_workspace_slug: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    active_session_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    draft_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
