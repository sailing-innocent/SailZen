# -*- coding: utf-8 -*-
# @file unified_scheduler.py
# @brief Unified Agent Scheduler - 统一任务调度器
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# 统一 Agent 任务调度器
# - 支持优先级队列
# - 资源限制控制
# - 进度通知 (WebSocket)
# - 任务持久化和恢复

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.orm import Session

from sail_server.data.unified_agent import (
    UnifiedAgentTask,
    UnifiedAgentStep,
    UnifiedAgentEvent,
    TaskStatus,
    StepType,
)
from sail_server.application.dto.unified_agent import (
    UnifiedAgentTaskCreateRequest,
    UnifiedAgentTaskResponse,
    UnifiedTaskProgressResponse,
    UnifiedTaskResultResponse,
)
from sail_server.model.unified_agent import (
    UnifiedTaskDAO,
    UnifiedStepDAO,
    UnifiedEventDAO,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 配置类
# ============================================================================

@dataclass
class SchedulerConfig:
    """调度器配置"""
    max_concurrent_tasks: int = 5           # 最大并发任务数
    max_tasks_per_user: int = 3             # 每用户最大任务数
    poll_interval_seconds: float = 2.0      # 轮询间隔
    task_timeout_seconds: int = 3600        # 任务超时时间
    enable_priority_preemption: bool = True  # 启用优先级抢占
    token_rate_limit_per_minute: int = 100000  # Token 速率限制
    default_task_priority: int = 5          # 默认任务优先级


@dataclass
class ResourceUsage:
    """资源使用情况"""
    running_tasks: int = 0
    tokens_used_last_minute: int = 0
    cost_used_today: float = 0.0
    
    def can_accept_new_task(self, config: SchedulerConfig) -> bool:
        """检查是否可以接受新任务"""
        return (
            self.running_tasks < config.max_concurrent_tasks and
            self.tokens_used_last_minute < config.token_rate_limit_per_minute
        )


# ============================================================================
# 任务队列项
# ============================================================================

class TaskPriority:
    """任务优先级常量"""
    CRITICAL = 1    # 紧急任务
    HIGH = 3        # 高优先级
    NORMAL = 5      # 正常优先级
    LOW = 7         # 低优先级
    BACKGROUND = 10  # 后台任务


@dataclass(order=True)
class TaskQueueItem:
    """任务队列项（用于优先级队列）"""
    # 优先级队列使用第一个字段排序，数值越小优先级越高
    priority_score: float
    
    # 非比较字段
    task_id: int = field(compare=False)
    priority: int = field(compare=False)
    created_at: datetime = field(compare=False)
    task_type: str = field(compare=False)
    
    @classmethod
    def calculate_priority_score(
        cls,
        priority: int,
        created_at: datetime,
        wait_time_boost: bool = True
    ) -> float:
        """
        计算优先级分数
        
        分数 = 基础优先级 + 等待时间加成
        分数越低，优先级越高
        """
        score = float(priority)
        
        if wait_time_boost:
            # 等待时间越长，优先级越高（分数降低）
            wait_seconds = (datetime.utcnow() - created_at).total_seconds()
            wait_boost = max(0, wait_seconds / 300)  # 每5分钟降低1分
            score -= min(wait_boost, 2.0)  # 最多降低2分
        
        return score


# ============================================================================
# 进度回调
# ============================================================================

@dataclass
class TaskProgressEvent:
    """任务进度事件"""
    task_id: int
    event_type: str  # started | progress | step | completed | failed | cancelled
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


ProgressCallback = Callable[[TaskProgressEvent], None]


# ============================================================================
# 统一调度器
# ============================================================================

class UnifiedAgentScheduler:
    """
    统一 Agent 任务调度器
    
    职责：
    1. 管理任务队列（优先级队列）
    2. 控制并发和资源使用
    3. 调度任务执行
    4. 进度通知
    5. 任务状态持久化
    """
    
    def __init__(
        self,
        db_session_factory: Callable[[], Session],
        config: Optional[SchedulerConfig] = None,
    ):
        self.db_factory = db_session_factory
        self.config = config or SchedulerConfig()
        
        # 任务队列
        self._task_queue: asyncio.PriorityQueue[TaskQueueItem] = asyncio.PriorityQueue()
        
        # 运行中的任务
        self._running_tasks: Dict[int, asyncio.Task] = {}  # task_id -> asyncio.Task
        self._running_task_info: Dict[int, Dict[str, Any]] = {}  # task_id -> 任务信息
        
        # 资源使用
        self._resource_usage = ResourceUsage()
        
        # 回调
        self._progress_callbacks: List[ProgressCallback] = []
        self._task_callbacks: Dict[int, List[ProgressCallback]] = {}  # task_id -> callbacks
        
        # 控制
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # 统计
        self._stats = {
            "total_scheduled": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
        }
    
    # ========================================================================
    # 生命周期管理
    # ========================================================================
    
    async def start(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        
        # 启动调度循环
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        # 启动清理循环
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # 恢复未完成的任务
        await self._recover_pending_tasks()
        
        logger.info("UnifiedAgentScheduler started")
    
    async def stop(self):
        """停止调度器"""
        if not self._running:
            return
        
        self._running = False
        
        # 取消调度循环
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        # 取消清理循环
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 取消所有运行中的任务
        async with self._lock:
            for task_id, task in list(self._running_tasks.items()):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                # 更新数据库状态
                with self.db_factory() as db:
                    dao = UnifiedTaskDAO(db)
                    dao.mark_as_cancelled(task_id)
        
        logger.info("UnifiedAgentScheduler stopped")
    
    async def _recover_pending_tasks(self):
        """恢复未完成的 pending 任务到队列"""
        with self.db_factory() as db:
            dao = UnifiedTaskDAO(db)
            pending_tasks = dao.get_pending_tasks(limit=100)
            
            for task in pending_tasks:
                item = TaskQueueItem(
                    priority_score=TaskQueueItem.calculate_priority_score(
                        task.priority, task.created_at
                    ),
                    task_id=task.id,
                    priority=task.priority,
                    created_at=task.created_at,
                    task_type=task.task_type,
                )
                await self._task_queue.put(item)
                self._stats["total_scheduled"] += 1
            
            logger.info(f"Recovered {len(pending_tasks)} pending tasks")
    
    # ========================================================================
    # 调度循环
    # ========================================================================
    
    async def _scheduler_loop(self):
        """主调度循环"""
        logger.info("Scheduler loop started")
        loop_count = 0
        
        while self._running:
            try:
                loop_count += 1
                if loop_count % 10 == 0:  # 每10次循环记录一次日志
                    logger.debug(f"Scheduler loop iteration {loop_count}, queue size: {self._task_queue.qsize()}, running tasks: {len(self._running_tasks)}")
                
                # 检查资源限制
                if not self._resource_usage.can_accept_new_task(self.config):
                    logger.debug(f"Resource limit reached, waiting... (running: {self._resource_usage.running_tasks})")
                    await asyncio.sleep(self.config.poll_interval_seconds)
                    continue
                
                # 获取队列中的任务
                try:
                    item = await asyncio.wait_for(
                        self._task_queue.get(),
                        timeout=self.config.poll_interval_seconds
                    )
                    logger.info(f"Got task from queue: task_id={item.task_id}, priority={item.priority}")
                except asyncio.TimeoutError:
                    continue
                
                # 检查任务是否仍有效
                with self.db_factory() as db:
                    dao = UnifiedTaskDAO(db)
                    task = dao.get_by_id(item.task_id)
                    
                    if not task:
                        logger.warning(f"Task {item.task_id} not found in database, skipping")
                        continue
                    
                    if task.status not in [TaskStatus.PENDING, TaskStatus.SCHEDULED]:
                        logger.info(f"Task {item.task_id} status is '{task.status}', not pending/scheduled, skipping")
                        continue
                    
                    logger.info(f"Task {item.task_id} is valid (status={task.status}), checking resource limits...")
                    
                    # 检查并发限制
                    if len(self._running_tasks) >= self.config.max_concurrent_tasks:
                        logger.info(f"Max concurrent tasks reached ({len(self._running_tasks)}/{self.config.max_concurrent_tasks})")
                        # 如果启用了抢占且当前任务优先级更高
                        if (self.config.enable_priority_preemption and 
                            item.priority <= TaskPriority.HIGH):
                            logger.info(f"Trying to preempt lower priority task for high priority task {item.task_id}")
                            await self._preempt_lowest_priority_task()
                        else:
                            # 重新放回队列
                            logger.info(f"Re-queueing task {item.task_id}")
                            await self._task_queue.put(item)
                            await asyncio.sleep(self.config.poll_interval_seconds)
                            continue
                    
                    # 启动任务执行
                    logger.info(f"Starting task execution: task_id={item.task_id}")
                    await self._start_task_execution(task.id)
                
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)
                await asyncio.sleep(self.config.poll_interval_seconds)
        
        logger.info("Scheduler loop stopped")
    
    async def _cleanup_loop(self):
        """清理循环 - 处理超时任务等"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                
                # 检查超时任务
                async with self._lock:
                    current_time = datetime.utcnow()
                    for task_id, info in list(self._running_task_info.items()):
                        start_time = info.get("started_at")
                        if start_time:
                            elapsed = (current_time - start_time).total_seconds()
                            if elapsed > self.config.task_timeout_seconds:
                                logger.warning(f"Task {task_id} timed out, cancelling...")
                                await self.cancel_task(task_id, reason="timeout")
                
                # 重置速率限制计数器
                self._resource_usage.tokens_used_last_minute = 0
                
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _preempt_lowest_priority_task(self) -> bool:
        """抢占优先级最低的任务"""
        if not self._running_task_info:
            return False
        
        # 找到优先级最低的任务
        lowest_priority_task = None
        lowest_priority = -1
        
        for task_id, info in self._running_task_info.items():
            if info.get("priority", 5) > lowest_priority:
                lowest_priority = info["priority"]
                lowest_priority_task = task_id
        
        # 如果最低优先级任务比新任务优先级高，不抢占
        if lowest_priority <= TaskPriority.HIGH:
            return False
        
        # 暂停低优先级任务
        if lowest_priority_task:
            logger.info(f"Preempting task {lowest_priority_task} (priority={lowest_priority})")
            await self._pause_task(lowest_priority_task)
            return True
        
        return False
    
    async def _pause_task(self, task_id: int):
        """暂停任务（放回队列）"""
        # 取消运行中的 asyncio.Task
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
        
        # 更新数据库状态
        with self.db_factory() as db:
            dao = UnifiedTaskDAO(db)
            dao.update(task_id, status=TaskStatus.PENDING)
        
        # 从运行列表移除
        async with self._lock:
            self._running_tasks.pop(task_id, None)
            info = self._running_task_info.pop(task_id, None)
            if info:
                self._resource_usage.running_tasks -= 1
        
        # 重新加入队列
        if info:
            item = TaskQueueItem(
                priority_score=TaskQueueItem.calculate_priority_score(
                    info.get("priority", 5),
                    info.get("created_at", datetime.utcnow()),
                    wait_time_boost=False  # 暂停的任务不增加等待加成
                ),
                task_id=task_id,
                priority=info.get("priority", 5),
                created_at=info.get("created_at", datetime.utcnow()),
                task_type=info.get("task_type", "general"),
            )
            await self._task_queue.put(item)
    
    # ========================================================================
    # 任务管理
    # ========================================================================
    
    async def schedule_task(
        self,
        task_data: UnifiedAgentTaskCreateRequest,
        immediate: bool = False
    ) -> UnifiedAgentTaskResponse:
        """
        调度新任务
        
        Args:
            task_data: 任务数据
            immediate: 是否立即执行（忽略队列）
        
        Returns:
            UnifiedAgentTaskResponse: 创建的任务响应
        """
        logger.info(f"Scheduling task: type={task_data.task_type}, priority={task_data.priority}")
        
        with self.db_factory() as db:
            dao = UnifiedTaskDAO(db)
            
            # 创建任务记录
            orm = dao.create(task_data)
            logger.info(f"Task record created: id={orm.id}, status={orm.status}")
            
            # 创建队列项
            item = TaskQueueItem(
                priority_score=TaskQueueItem.calculate_priority_score(
                    orm.priority, orm.created_at
                ),
                task_id=orm.id,
                priority=orm.priority,
                created_at=orm.created_at,
                task_type=orm.task_type,
            )
            logger.info(f"Task queue item created: task_id={item.task_id}, priority_score={item.priority_score}")
            
            if immediate and self._resource_usage.can_accept_new_task(self.config):
                # 立即执行
                logger.info(f"Starting task {orm.id} immediately")
                await self._start_task_execution(orm.id)
            else:
                # 加入队列
                logger.info(f"Adding task {orm.id} to queue (queue size before: {self._task_queue.qsize()})")
                await self._task_queue.put(item)
                dao.mark_as_scheduled(orm.id)
                logger.info(f"Task {orm.id} added to queue, status set to 'scheduled'")
            
            self._stats["total_scheduled"] += 1
            
            # 返回 Pydantic 响应模型
            return UnifiedAgentTaskResponse.model_validate(orm)
    
    async def _start_task_execution(self, task_id: int):
        """开始执行任务"""
        logger.info(f"Starting task execution: task_id={task_id}")
        
        async with self._lock:
            # 创建执行 Task
            exec_task = asyncio.create_task(
                self._execute_task_wrapper(task_id),
                name=f"task_{task_id}"
            )
            self._running_tasks[task_id] = exec_task
            self._resource_usage.running_tasks += 1
            logger.info(f"Task {task_id} added to running tasks (total running: {len(self._running_tasks)})")
        
        # 更新数据库状态
        with self.db_factory() as db:
            dao = UnifiedTaskDAO(db)
            task = dao.mark_as_running(task_id)
            
            if task:
                self._running_task_info[task_id] = {
                    "started_at": datetime.utcnow(),
                    "priority": task.priority,
                    "created_at": task.created_at,
                    "task_type": task.task_type,
                }
                logger.info(f"Task {task_id} marked as running in database")
        
        # 发送事件
        self._emit_event(TaskProgressEvent(
            task_id=task_id,
            event_type="started",
            data={"timestamp": datetime.utcnow().isoformat()}
        ))
        logger.info(f"Task {task_id} started event emitted")
    
    async def _execute_task_wrapper(self, task_id: int):
        """任务执行包装器（处理异常和清理）"""
        logger.info(f"Task wrapper started: task_id={task_id}")
        try:
            await self._execute_task(task_id)
            logger.info(f"Task wrapper completed successfully: task_id={task_id}")
        except asyncio.CancelledError:
            logger.info(f"Task {task_id} was cancelled")
            with self.db_factory() as db:
                dao = UnifiedTaskDAO(db)
                dao.mark_as_cancelled(task_id)
            
            self._emit_event(TaskProgressEvent(
                task_id=task_id,
                event_type="cancelled",
                data={"timestamp": datetime.utcnow().isoformat()}
            ))
            raise
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            with self.db_factory() as db:
                dao = UnifiedTaskDAO(db)
                dao.mark_as_failed(task_id, str(e), error_code="EXECUTION_ERROR")
            
            self._stats["total_failed"] += 1
            
            self._emit_event(TaskProgressEvent(
                task_id=task_id,
                event_type="failed",
                data={
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            ))
        finally:
            # 清理
            logger.info(f"Cleaning up task {task_id}")
            async with self._lock:
                self._running_tasks.pop(task_id, None)
                self._running_task_info.pop(task_id, None)
                self._resource_usage.running_tasks -= 1
                logger.info(f"Task {task_id} cleaned up from running tasks")
    
    async def _execute_task(self, task_id: int):
        """
        执行任务（子类应重写此方法）
        
        默认实现：创建一个简单的执行步骤，实际应由 Agent 实现
        """
        logger.info(f"Executing task: task_id={task_id}")
        
        with self.db_factory() as db:
            dao = UnifiedTaskDAO(db)
            step_dao = UnifiedStepDAO(db)
            event_dao = UnifiedEventDAO(db)
            
            task = dao.get_by_id(task_id)
            if not task:
                raise ValueError(f"Task not found: {task_id}")
            
            logger.info(f"Task {task_id} found: type={task.task_type}, status={task.status}")
            
            # 创建开始步骤
            step_number = step_dao.get_next_step_number(task_id)
            logger.info(f"Creating step {step_number} for task {task_id}")
            step = step_dao.create(
                task_id=task_id,
                step_number=step_number,
                step_type=StepType.THOUGHT,
                title="Task Started",
                content=f"Starting {task.task_type} task",
            )
            logger.info(f"Step created: step_id={step.id}")
            
            # 记录事件
            event = event_dao.create(
                task_id=task_id,
                event_type="task_started",
                event_data={"step_id": step.id}
            )
            logger.info(f"Event created: event_id={event.id}")
            
            # 更新进度
            dao.update_progress(task_id, 10, "executing")
            logger.info(f"Task {task_id} progress updated to 10%")
            
            # 发送进度事件
            self._emit_event(TaskProgressEvent(
                task_id=task_id,
                event_type="progress",
                data={"progress": 10, "phase": "executing"}
            ))
            
            # TODO: 这里应该调用具体的 Agent 执行
            # 目前只是模拟执行
            logger.info(f"Task {task_id}: simulating execution (sleep 1s)...")
            await asyncio.sleep(1)
            
            # 完成步骤
            step_number += 1
            logger.info(f"Creating completion step {step_number} for task {task_id}")
            step_dao.create(
                task_id=task_id,
                step_number=step_number,
                step_type=StepType.COMPLETION,
                title="Task Completed",
                content="Task execution completed",
            )
            
            # 标记完成
            dao.mark_as_completed(task_id, result_data={"message": "Task completed"})
            logger.info(f"Task {task_id} marked as completed")
            
            # 记录事件
            event_dao.create(
                task_id=task_id,
                event_type="task_completed",
                event_data={"result": "success"}
            )
            
            self._stats["total_completed"] += 1
            
            # 发送完成事件
            self._emit_event(TaskProgressEvent(
                task_id=task_id,
                event_type="completed",
                data={
                    "progress": 100,
                    "timestamp": datetime.utcnow().isoformat()
                }
            ))
            logger.info(f"Task {task_id} execution completed")
    
    async def cancel_task(self, task_id: int, reason: str = "user_request") -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务 ID
            reason: 取消原因
        
        Returns:
            bool: 是否成功取消
        """
        # 检查是否在运行中
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            return True
        
        # 检查是否在队列中（需要从队列中移除）
        # asyncio.PriorityQueue 不支持直接移除，需要在取出时检查
        
        # 更新数据库状态
        with self.db_factory() as db:
            dao = UnifiedTaskDAO(db)
            task = dao.get_by_id(task_id)
            
            if task and task.status in [TaskStatus.PENDING, TaskStatus.SCHEDULED]:
                dao.mark_as_cancelled(task_id)
                
                # 记录事件
                event_dao = UnifiedEventDAO(db)
                event_dao.create(
                    task_id=task_id,
                    event_type="task_cancelled",
                    event_data={"reason": reason}
                )
                
                self._stats["total_cancelled"] += 1
                
                # 发送事件
                self._emit_event(TaskProgressEvent(
                    task_id=task_id,
                    event_type="cancelled",
                    data={"reason": reason}
                ))
                
                return True
        
        return False
    
    def get_task_progress(self, task_id: int) -> Optional[UnifiedTaskProgressResponse]:
        """获取任务进度"""
        with self.db_factory() as db:
            dao = UnifiedTaskDAO(db)
            result = dao.get_with_step_count(task_id)
            
            if not result:
                return None
            
            task, step_count = result
            
            # 计算预计剩余时间
            estimated_remaining = None
            if task.started_at and task.progress > 0 and task.progress < 100:
                elapsed = (datetime.utcnow() - task.started_at).total_seconds()
                estimated_total = elapsed / (task.progress / 100)
                estimated_remaining = int(estimated_total - elapsed)
            
            return UnifiedTaskProgressResponse(
                task_id=task.id,
                status=task.status,
                progress=task.progress,
                current_phase=task.current_phase,
                current_step=step_count,
                total_steps=None,  # 无法预知总步骤数
                estimated_remaining_seconds=estimated_remaining,
                error_message=task.error_message,
                actual_tokens=task.actual_tokens,
                actual_cost=task.actual_cost,
                started_at=task.started_at,
                updated_at=task.updated_at,
            )
    
    # ========================================================================
    # 事件和回调
    # ========================================================================
    
    def subscribe(self, callback: ProgressCallback):
        """订阅所有任务进度事件"""
        self._progress_callbacks.append(callback)
    
    def unsubscribe(self, callback: ProgressCallback):
        """取消订阅"""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)
    
    def subscribe_task(self, task_id: int, callback: ProgressCallback):
        """订阅特定任务进度"""
        if task_id not in self._task_callbacks:
            self._task_callbacks[task_id] = []
        self._task_callbacks[task_id].append(callback)
    
    def unsubscribe_task(self, task_id: int, callback: ProgressCallback):
        """取消订阅特定任务"""
        if task_id in self._task_callbacks:
            try:
                self._task_callbacks[task_id].remove(callback)
            except ValueError:
                pass
    
    def _emit_event(self, event: TaskProgressEvent):
        """发送事件"""
        # 全局回调
        for callback in self._progress_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
        
        # 特定任务回调
        if event.task_id in self._task_callbacks:
            for callback in self._task_callbacks[event.task_id]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Task progress callback error: {e}")
    
    # ========================================================================
    # 查询和统计
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取调度器统计"""
        return {
            **self._stats,
            "running_tasks": len(self._running_tasks),
            "queued_tasks": self._task_queue.qsize(),
            "resource_usage": {
                "running_tasks": self._resource_usage.running_tasks,
                "tokens_used_last_minute": self._resource_usage.tokens_used_last_minute,
            },
        }
    
    def get_running_tasks(self) -> List[int]:
        """获取运行中的任务 ID 列表"""
        return list(self._running_tasks.keys())
    
    def is_running(self) -> bool:
        """检查调度器是否运行中"""
        return self._running


# ============================================================================
# 全局实例
# ============================================================================

_scheduler_instance: Optional[UnifiedAgentScheduler] = None


def get_unified_scheduler(
    db_session_factory: Optional[Callable[[], Session]] = None,
    config: Optional[SchedulerConfig] = None,
) -> UnifiedAgentScheduler:
    """获取全局调度器实例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        if db_session_factory is None:
            from sail_server.db import get_db_session
            db_session_factory = get_db_session
        _scheduler_instance = UnifiedAgentScheduler(db_session_factory, config)
    return _scheduler_instance


def set_unified_scheduler(scheduler: UnifiedAgentScheduler):
    """设置全局调度器实例"""
    global _scheduler_instance
    _scheduler_instance = scheduler
