# -*- coding: utf-8 -*-
# @file project.py
# @brief Project ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
项目模块 ORM 模型

从 sail_server/data/project.py 迁移
"""

from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, func
from sqlalchemy.orm import relationship

from sail_server.infrastructure.orm.orm_base import ORMBase


class Project(ORMBase):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    state = Column(Integer)  # Project State
    start_time_qbw = Column(Integer)  # QBWTime (YYYYQQWW format)
    end_time_qbw = Column(Integer)  # QBWTime (YYYYQQWW format)
    timespan_id = Column(
        Integer, ForeignKey("timespans.id"), nullable=True, default=None, index=True
    )
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())

    timespan = relationship("TimeSpan", foreign_keys=[timespan_id])


class Milestone(ORMBase):
    """项目里程碑"""

    __tablename__ = "milestones"
    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True
    )
    name = Column(String)
    description = Column(String)
    day_id = Column(
        Integer, ForeignKey("days.id"), nullable=False, index=True
    )
    state = Column(Integer, default=0)  # 0 pending, 1 done, 2 skipped
    energy_weight = Column(Integer, default=0)


class Mission(ORMBase):
    __tablename__ = "missions"
    id = Column(Integer, primary_key=True)
    # basic Mission info
    name = Column(String)
    description = Column(String)
    parent_id = Column(
        Integer, ForeignKey("missions.id"), nullable=True, default=None
    )  # parent node id, null means no parent required
    state = Column(Integer)  # 0: pending 1: ready 2: doing 3: done 4: cancel
    ddl = Column(TIMESTAMP)  # deadline in timestamp in seconds
    project_id = Column(
        Integer, ForeignKey("projects.id"), nullable=True, default=None
    )  # project id, null means no project

    # PEMS fields
    planned_minutes = Column(Integer, default=0)
    actual_minutes = Column(Integer, default=0)
    energy_cost = Column(Integer, default=0)
    day_id = Column(
        Integer, ForeignKey("days.id"), nullable=True, default=None, index=True
    )
    milestone_id = Column(
        Integer, ForeignKey("milestones.id"), nullable=True, default=None, index=True
    )
    health_constraint = Column(
        String, default="normal"
    )  # normal | high_energy | low_energy_ok

    day = relationship("Day", foreign_keys=[day_id])

    # end basic Mission info

    # Internal use only, do not use in query
    # --------------------------------------
    # 在构建树结构时我们只会指定parent_id，执行查找前会检查距离上一个checkpoint之间是否有插入/删除操作，如果有，需要刷新lft和rgt
    # 辅助前序遍历方法，如果A节点是B节点的父节点，则A节点的lft小于B节点的lft，A节点的rgt大于B节点的rgt
    lft = Column(Integer)
    rgt = Column(Integer)
    tree_id = Column(Integer)  # tree id, used for differentiate different trees
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())
    # end internal use only
