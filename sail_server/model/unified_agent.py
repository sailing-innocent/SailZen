# -*- coding: utf-8 -*-
# @file unified_agent.py
# @brief Unified Agent Task Models - Business Logic
# @author sailing-innocent
# @date 2026-02-27
# @version 1.0
# ---------------------------------

from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func

from sail_server.infrastructure.orm.unified_agent import (
    UnifiedAgentTask,
    UnifiedAgentStep,
    UnifiedAgentEvent,
)
from sail_server.application.dto.unified_agent import TaskStatus
from sail_server.application.dto.unified_agent import (
    UnifiedAgentTaskCreateRequest,
    UnifiedAgentTaskResponse,
)


class UnifiedTaskDAO:
    """统一任务数据访问对象"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================================================
    # CRUD 操作
    # =========================================================================
    
    def create(self, data: UnifiedAgentTaskCreateRequest) -> UnifiedAgentTask:
        """创建任务"""
        # Inline the to_orm logic from the removed UnifiedTaskData
        orm = UnifiedAgentTask(
            task_type=data.task_type,
            sub_type=data.sub_type,
            edition_id=data.edition_id,
            target_node_ids=data.target_node_ids,
            target_scope=data.target_scope,
            llm_provider=data.llm_provider,
            llm_model=data.llm_model,
            prompt_template_id=data.prompt_template_id,
            priority=data.priority,
            config=data.config,
        )
        self.db.add(orm)
        self.db.commit()
        self.db.refresh(orm)
        return orm
    
    def get_by_id(self, task_id: int) -> Optional[UnifiedAgentTask]:
        """根据 ID 获取任务"""
        return self.db.query(UnifiedAgentTask).filter(
            UnifiedAgentTask.id == task_id
        ).first()
    
    def get_with_step_count(self, task_id: int) -> Optional[tuple[UnifiedAgentTask, int]]:
        """获取任务及步骤数"""
        task = self.get_by_id(task_id)
        if not task:
            return None
        step_count = self.db.query(func.count(UnifiedAgentStep.id)).filter(
            UnifiedAgentStep.task_id == task_id
        ).scalar()
        return task, step_count or 0
    
    def update(self, task_id: int, **kwargs) -> Optional[UnifiedAgentTask]:
        """更新任务字段"""
        task = self.get_by_id(task_id)
        if not task:
            return None
        
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        self.db.commit()
        self.db.refresh(task)
        return task
    
    def delete(self, task_id: int) -> bool:
        """删除任务"""
        task = self.get_by_id(task_id)
        if not task:
            return False
        self.db.delete(task)
        self.db.commit()
        return True
    
    # =========================================================================
    # 列表查询
    # =========================================================================
    
    def list_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        sub_type: Optional[str] = None,
        edition_id: Optional[int] = None,
        review_status: Optional[str] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> List[UnifiedAgentTask]:
        """列表查询任务"""
        query = self.db.query(UnifiedAgentTask)
        
        if status:
            query = query.filter(UnifiedAgentTask.status == status)
        if task_type:
            query = query.filter(UnifiedAgentTask.task_type == task_type)
        if sub_type:
            query = query.filter(UnifiedAgentTask.sub_type == sub_type)
        if edition_id:
            query = query.filter(UnifiedAgentTask.edition_id == edition_id)
        if review_status:
            query = query.filter(UnifiedAgentTask.review_status == review_status)
        
        # 排序
        order_column = getattr(UnifiedAgentTask, order_by, UnifiedAgentTask.created_at)
        query = query.order_by(desc(order_column) if order_desc else asc(order_column))
        
        return query.offset(skip).limit(limit).all()
    
    def count_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        edition_id: Optional[int] = None,
    ) -> int:
        """统计任务数量"""
        query = self.db.query(func.count(UnifiedAgentTask.id))
        
        if status:
            query = query.filter(UnifiedAgentTask.status == status)
        if task_type:
            query = query.filter(UnifiedAgentTask.task_type == task_type)
        if edition_id:
            query = query.filter(UnifiedAgentTask.edition_id == edition_id)
        
        return query.scalar() or 0
    
    # =========================================================================
    # 调度器专用查询
    # =========================================================================
    
    def get_pending_tasks(
        self,
        limit: int = 10,
        task_type: Optional[str] = None,
    ) -> List[UnifiedAgentTask]:
        """获取待处理任务（按优先级排序）"""
        query = self.db.query(UnifiedAgentTask).filter(
            UnifiedAgentTask.status == TaskStatus.PENDING
        )
        
        if task_type:
            query = query.filter(UnifiedAgentTask.task_type == task_type)
        
        return query.order_by(
            asc(UnifiedAgentTask.priority),  # 优先级高的在前
            asc(UnifiedAgentTask.created_at),  # 同优先级按时间
        ).limit(limit).all()
    
    def get_running_tasks(self) -> List[UnifiedAgentTask]:
        """获取正在运行的任务"""
        return self.db.query(UnifiedAgentTask).filter(
            UnifiedAgentTask.status == TaskStatus.RUNNING
        ).all()
    
    def get_tasks_by_edition(
        self,
        edition_id: int,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[UnifiedAgentTask]:
        """按版本获取任务"""
        query = self.db.query(UnifiedAgentTask).filter(
            UnifiedAgentTask.edition_id == edition_id
        )
        
        if status:
            query = query.filter(UnifiedAgentTask.status == status)
        if task_type:
            query = query.filter(UnifiedAgentTask.task_type == task_type)
        
        return query.order_by(desc(UnifiedAgentTask.created_at)).offset(skip).limit(limit).all()
    
    # =========================================================================
    # 状态更新
    # =========================================================================
    
    def mark_as_scheduled(self, task_id: int) -> Optional[UnifiedAgentTask]:
        """标记为已调度"""
        return self.update(
            task_id,
            status=TaskStatus.SCHEDULED,
        )
    
    def mark_as_running(self, task_id: int) -> Optional[UnifiedAgentTask]:
        """标记为运行中"""
        return self.update(
            task_id,
            status=TaskStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
    
    def mark_as_completed(
        self,
        task_id: int,
        result_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[UnifiedAgentTask]:
        """标记为已完成"""
        updates = {
            "status": TaskStatus.COMPLETED,
            "progress": 100,
            "completed_at": datetime.utcnow(),
        }
        if result_data is not None:
            updates["result_data"] = result_data
        return self.update(task_id, **updates)
    
    def mark_as_failed(
        self,
        task_id: int,
        error_message: str,
        error_code: Optional[str] = None,
    ) -> Optional[UnifiedAgentTask]:
        """标记为失败"""
        return self.update(
            task_id,
            status=TaskStatus.FAILED,
            error_message=error_message,
            error_code=error_code,
            completed_at=datetime.utcnow(),
        )
    
    def mark_as_cancelled(self, task_id: int) -> Optional[UnifiedAgentTask]:
        """标记为已取消"""
        return self.update(
            task_id,
            status=TaskStatus.CANCELLED,
            cancelled_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
    
    def update_progress(
        self,
        task_id: int,
        progress: int,
        current_phase: Optional[str] = None,
    ) -> Optional[UnifiedAgentTask]:
        """更新进度"""
        updates = {"progress": max(0, min(100, progress))}
        if current_phase:
            updates["current_phase"] = current_phase
        return self.update(task_id, **updates)
    
    def update_cost(
        self,
        task_id: int,
        actual_tokens: int,
        actual_cost: float,
    ) -> Optional[UnifiedAgentTask]:
        """更新成本"""
        return self.update(
            task_id,
            actual_tokens=actual_tokens,
            actual_cost=actual_cost,
        )
    
    def update_review_status(
        self,
        task_id: int,
        review_status: str,
    ) -> Optional[UnifiedAgentTask]:
        """更新审核状态"""
        return self.update(task_id, review_status=review_status)


class UnifiedStepDAO:
    """统一步骤数据访问对象"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        task_id: int,
        step_number: int,
        step_type: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        content_summary: Optional[str] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0,
        meta_data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
    ) -> UnifiedAgentStep:
        """创建步骤"""
        step = UnifiedAgentStep(
            task_id=task_id,
            step_number=step_number,
            step_type=step_type,
            title=title,
            content=content,
            content_summary=content_summary,
            llm_provider=llm_provider,
            llm_model=llm_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            meta_data=meta_data or {},
            duration_ms=duration_ms,
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step
    
    def get_by_id(self, step_id: int) -> Optional[UnifiedAgentStep]:
        """根据 ID 获取步骤"""
        return self.db.query(UnifiedAgentStep).filter(
            UnifiedAgentStep.id == step_id
        ).first()
    
    def get_by_task_id(
        self,
        task_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[UnifiedAgentStep]:
        """获取任务的所有步骤"""
        return self.db.query(UnifiedAgentStep).filter(
            UnifiedAgentStep.task_id == task_id
        ).order_by(asc(UnifiedAgentStep.step_number)).offset(skip).limit(limit).all()
    
    def get_last_step(self, task_id: int) -> Optional[UnifiedAgentStep]:
        """获取任务的最后一步"""
        return self.db.query(UnifiedAgentStep).filter(
            UnifiedAgentStep.task_id == task_id
        ).order_by(desc(UnifiedAgentStep.step_number)).first()
    
    def get_next_step_number(self, task_id: int) -> int:
        """获取下一步的序号"""
        last_step = self.get_last_step(task_id)
        return (last_step.step_number + 1) if last_step else 1
    
    def update(self, step_id: int, **kwargs) -> Optional[UnifiedAgentStep]:
        """更新步骤"""
        step = self.get_by_id(step_id)
        if not step:
            return None
        
        for key, value in kwargs.items():
            if hasattr(step, key):
                setattr(step, key, value)
        
        self.db.commit()
        self.db.refresh(step)
        return step
    
    def delete_by_task_id(self, task_id: int) -> int:
        """删除任务的所有步骤"""
        result = self.db.query(UnifiedAgentStep).filter(
            UnifiedAgentStep.task_id == task_id
        ).delete()
        self.db.commit()
        return result


class UnifiedEventDAO:
    """统一事件数据访问对象"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        task_id: int,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> UnifiedAgentEvent:
        """创建事件"""
        event = UnifiedAgentEvent(
            task_id=task_id,
            event_type=event_type,
            event_data=event_data or {},
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
    
    def get_by_task_id(
        self,
        task_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[UnifiedAgentEvent]:
        """获取任务的所有事件"""
        return self.db.query(UnifiedAgentEvent).filter(
            UnifiedAgentEvent.task_id == task_id
        ).order_by(desc(UnifiedAgentEvent.created_at)).offset(skip).limit(limit).all()
    
    def get_recent_events(
        self,
        task_type: Optional[str] = None,
        event_type: Optional[str] = None,
        minutes: int = 60,
        limit: int = 100,
    ) -> List[UnifiedAgentEvent]:
        """获取最近的事件"""
        from sqlalchemy import text
        
        since = datetime.utcnow().timestamp() - (minutes * 60)
        
        query = self.db.query(UnifiedAgentEvent).filter(
            func.extract('epoch', UnifiedAgentEvent.created_at) > since
        )
        
        if event_type:
            query = query.filter(UnifiedAgentEvent.event_type == event_type)
        
        # 如果需要按 task_type 过滤，需要 JOIN
        if task_type:
            query = query.join(
                UnifiedAgentTask,
                UnifiedAgentEvent.task_id == UnifiedAgentTask.id
            ).filter(UnifiedAgentTask.task_type == task_type)
        
        return query.order_by(desc(UnifiedAgentEvent.created_at)).limit(limit).all()
    
    def delete_old_events(self, days: int = 30) -> int:
        """删除旧事件"""
        from sqlalchemy import text
        
        cutoff = datetime.utcnow().timestamp() - (days * 24 * 60 * 60)
        result = self.db.query(UnifiedAgentEvent).filter(
            func.extract('epoch', UnifiedAgentEvent.created_at) < cutoff
        ).delete()
        self.db.commit()
        return result


# ============================================================================
# 便捷函数
# ============================================================================

def get_unified_task_dao(db: Session) -> UnifiedTaskDAO:
    """获取 UnifiedTaskDAO 实例"""
    return UnifiedTaskDAO(db)


def get_unified_step_dao(db: Session) -> UnifiedStepDAO:
    """获取 UnifiedStepDAO 实例"""
    return UnifiedStepDAO(db)


def get_unified_event_dao(db: Session) -> UnifiedEventDAO:
    """获取 UnifiedEventDAO 实例"""
    return UnifiedEventDAO(db)
