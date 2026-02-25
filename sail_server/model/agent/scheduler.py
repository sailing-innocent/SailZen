# -*- coding: utf-8 -*-
# @file scheduler.py
# @brief Agent Scheduler - 核心调度逻辑
# @author sailing-innocent
# @date 2025-02-25
# @version 1.0
# ---------------------------------

import asyncio
import logging
import random
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List
from sqlalchemy.orm import Session

from sail_server.data.agent import (
    UserPrompt, AgentTask, AgentSchedulerState,
    AgentStreamEvent
)
from sail_server.db import get_db_session
from .runner import AgentRunner

logger = logging.getLogger("sail_server.agent_scheduler")


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
    
    def __init__(self, poll_interval=5.0):
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._active_agents: Dict[int, AgentRunner] = {}  # task_id -> AgentRunner
        self._event_callbacks: List[Callable] = []  # 状态变更回调
        self._lock = asyncio.Lock()
    
    async def start(self):
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        
        # 初始化调度器状态
        with get_db_session() as db:
            state = db.query(AgentSchedulerState).first()
            if not state:
                state = AgentSchedulerState()
                db.add(state)
            state.is_running = True
            db.commit()
        
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
        
        # 更新调度器状态
        with get_db_session() as db:
            state = db.query(AgentSchedulerState).first()
            if state:
                state.is_running = False
                db.commit()
        
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
            runner = AgentRunner(task.id, self._on_agent_event)
            self._active_agents[task.id] = runner
            
            # 异步启动 Agent（不阻塞调度循环）
            asyncio.create_task(runner.start())
            
            # 触发事件
            self._emit_event('task_scheduled', {'task_id': task.id, 'prompt_id': prompt.id})
            
            logger.info(f"Scheduled task {task.id} for prompt {prompt.id}")
    
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
            
            # 更新调度器统计
            with get_db_session() as db:
                state = db.query(AgentSchedulerState).first()
                if state:
                    state.active_agent_count = len(self._active_agents)
                    if event_type == 'task_completed':
                        state.total_processed += 1
                    elif event_type == 'task_failed':
                        state.total_failed += 1
                    db.commit()
    
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
    
    async def cancel_task(self, task_id: int) -> bool:
        """取消指定任务"""
        runner = self._active_agents.get(task_id)
        if runner:
            await runner.cancel()
            return True
        return False
    
    def get_active_tasks(self) -> List[int]:
        """获取当前活跃的任务ID列表"""
        return list(self._active_agents.keys())


# 全局调度器实例
_scheduler_instance: Optional[AgentScheduler] = None


def get_agent_scheduler() -> AgentScheduler:
    """获取全局调度器实例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = AgentScheduler()
    return _scheduler_instance


def set_agent_scheduler(scheduler: AgentScheduler):
    """设置全局调度器实例"""
    global _scheduler_instance
    _scheduler_instance = scheduler
