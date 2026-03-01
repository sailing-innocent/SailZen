# -*- coding: utf-8 -*-
# @file unified_agent.py
# @brief Unified Agent DAO
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
统一 Agent 任务模块 DAO

从 sail_server/data/unified_agent.py 迁移数据访问逻辑
"""

from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.unified_agent import (
    UnifiedAgentTask, UnifiedAgentStep, UnifiedAgentEvent
)
from sail_server.data.dao.base import BaseDAO


# ============================================================================
# UnifiedAgentTask DAO
# ============================================================================

class UnifiedAgentTaskDAO(BaseDAO[UnifiedAgentTask]):
    """统一 Agent 任务 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, UnifiedAgentTask)
    
    def get_by_edition(self, edition_id: int) -> List[UnifiedAgentTask]:
        """获取版本的所有任务"""
        return self.db.query(UnifiedAgentTask).filter(
            UnifiedAgentTask.edition_id == edition_id
        ).order_by(UnifiedAgentTask.created_at.desc()).all()
    
    def get_by_status(self, status: str) -> List[UnifiedAgentTask]:
        """获取指定状态的所有任务"""
        return self.db.query(UnifiedAgentTask).filter(
            UnifiedAgentTask.status == status
        ).order_by(UnifiedAgentTask.priority, UnifiedAgentTask.created_at).all()
    
    def get_by_task_type(self, task_type: str) -> List[UnifiedAgentTask]:
        """获取指定类型的所有任务"""
        return self.db.query(UnifiedAgentTask).filter(
            UnifiedAgentTask.task_type == task_type
        ).order_by(UnifiedAgentTask.created_at.desc()).all()
    
    def get_pending_tasks(self, limit: int = 100) -> List[UnifiedAgentTask]:
        """获取待处理任务（按优先级排序）"""
        return self.db.query(UnifiedAgentTask).filter(
            UnifiedAgentTask.status == "pending"
        ).order_by(
            UnifiedAgentTask.priority,
            UnifiedAgentTask.created_at
        ).limit(limit).all()
    
    def get_running_tasks(self) -> List[UnifiedAgentTask]:
        """获取正在运行的任务"""
        return self.db.query(UnifiedAgentTask).filter(
            UnifiedAgentTask.status == "running"
        ).order_by(UnifiedAgentTask.started_at).all()
    
    def get_with_steps(self, task_id: int) -> Optional[UnifiedAgentTask]:
        """获取任务及其所有步骤"""
        task = self.get_by_id(task_id)
        if task:
            # 触发加载步骤
            _ = task.steps
        return task
    
    def update_progress(self, task_id: int, progress: int, current_phase: Optional[str] = None) -> bool:
        """更新任务进度"""
        task = self.get_by_id(task_id)
        if not task:
            return False
        task.progress = progress
        if current_phase:
            task.current_phase = current_phase
        self.db.commit()
        return True
    
    def update_cost(self, task_id: int, actual_tokens: int, actual_cost: float) -> bool:
        """更新任务成本"""
        task = self.get_by_id(task_id)
        if not task:
            return False
        task.actual_tokens = actual_tokens
        task.actual_cost = actual_cost
        self.db.commit()
        return True


# ============================================================================
# UnifiedAgentStep DAO
# ============================================================================

class UnifiedAgentStepDAO(BaseDAO[UnifiedAgentStep]):
    """统一 Agent 步骤 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, UnifiedAgentStep)
    
    def get_by_task(self, task_id: int) -> List[UnifiedAgentStep]:
        """获取任务的所有步骤"""
        return self.db.query(UnifiedAgentStep).filter(
            UnifiedAgentStep.task_id == task_id
        ).order_by(UnifiedAgentStep.step_number).all()
    
    def get_by_step_type(self, task_id: int, step_type: str) -> List[UnifiedAgentStep]:
        """获取任务指定类型的步骤"""
        return self.db.query(UnifiedAgentStep).filter(
            UnifiedAgentStep.task_id == task_id,
            UnifiedAgentStep.step_type == step_type
        ).order_by(UnifiedAgentStep.step_number).all()
    
    def get_latest_step(self, task_id: int) -> Optional[UnifiedAgentStep]:
        """获取任务的最新步骤"""
        return self.db.query(UnifiedAgentStep).filter(
            UnifiedAgentStep.task_id == task_id
        ).order_by(UnifiedAgentStep.step_number.desc()).first()
    
    def count_by_task(self, task_id: int) -> int:
        """统计任务的步骤数"""
        return self.db.query(func.count(UnifiedAgentStep.id)).filter(
            UnifiedAgentStep.task_id == task_id
        ).scalar()


# ============================================================================
# UnifiedAgentEvent DAO
# ============================================================================

class UnifiedAgentEventDAO(BaseDAO[UnifiedAgentEvent]):
    """统一 Agent 事件 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, UnifiedAgentEvent)
    
    def get_by_task(self, task_id: int) -> List[UnifiedAgentEvent]:
        """获取任务的所有事件"""
        return self.db.query(UnifiedAgentEvent).filter(
            UnifiedAgentEvent.task_id == task_id
        ).order_by(UnifiedAgentEvent.created_at).all()
    
    def get_by_event_type(self, event_type: str, limit: int = 100) -> List[UnifiedAgentEvent]:
        """获取指定类型的事件"""
        return self.db.query(UnifiedAgentEvent).filter(
            UnifiedAgentEvent.event_type == event_type
        ).order_by(UnifiedAgentEvent.created_at.desc()).limit(limit).all()
    
    def get_recent_events(self, limit: int = 100) -> List[UnifiedAgentEvent]:
        """获取最近的事件"""
        return self.db.query(UnifiedAgentEvent).order_by(
            UnifiedAgentEvent.created_at.desc()
        ).limit(limit).all()
