# -*- coding: utf-8 -*-
# @file agent.py
# @brief Agent ORM Models
# @author sailing-innocent
# @date 2026-08-24
# @version 1.0
# ---------------------------------

"""
Shadow Agent ORM models for 24h automation.
"""

from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from sail_server.infrastructure.orm.orm_base import ORMBase


class JobStatus(str, PyEnum):
    pending = "pending"
    running = "running"
    pending_review = "pending_review"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class JobType(str, PyEnum):
    vault_sync = "vault_sync"
    note_analysis = "note_analysis"
    patch_gen = "patch_gen"
    task_exec = "task_exec"
    stub_create = "stub_create"
    daily_fill = "daily_fill"


class AgentJob(ORMBase):
    __tablename__ = "agent_jobs"

    id = Column(Integer, primary_key=True)
    job_type = Column(String(64), nullable=False)
    status = Column(String(32), default=JobStatus.pending.value)
    params = Column(JSON, default=dict)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    auto_approved = Column(Boolean, default=False)
    created_by = Column(String(32), default="system")
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class AgentConfig(ORMBase):
    __tablename__ = "agent_configs"

    key = Column(String(128), primary_key=True)
    value = Column(JSON, nullable=False)
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
