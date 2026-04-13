# -*- coding: utf-8 -*-
# @file dag_pipeline.py
# @brief DAG Pipeline ORM Models (PipelineRun, NodeRun)
# @author sailing-innocent
# @date 2026-04-13
# @version 1.0
# ---------------------------------

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Enum,
    ForeignKey,
    Text,
    Boolean,
)
from sqlalchemy.orm import relationship

from sail_server.infrastructure.orm.orm_base import ORMBase
from sail_server.data.types import JSONB


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    waiting = "waiting"
    skipped = "skipped"


class PipelineRun(ORMBase):
    __tablename__ = "dag_pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_id = Column(String(64), nullable=False)
    pipeline_name = Column(String(128), nullable=False)
    params = Column(JSONB, default={})
    status = Column(Enum(RunStatus), default=RunStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    node_runs = relationship(
        "NodeRun",
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )


class NodeRun(ORMBase):
    __tablename__ = "dag_node_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id = Column(
        Integer, ForeignKey("dag_pipeline_runs.id"), nullable=False
    )
    node_id = Column(String(64), nullable=False)
    node_name = Column(String(128), nullable=False)
    node_type = Column(String(32), nullable=False)
    description = Column(Text, default="")
    depends_on = Column(JSONB, default=[])
    status = Column(Enum(RunStatus), default=RunStatus.pending)
    logs = Column(JSONB, default=[])
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)
    is_dynamic = Column(Boolean, default=False)
    can_spawn = Column(Boolean, default=False)

    pipeline_run = relationship("PipelineRun", back_populates="node_runs")
