# -*- coding: utf-8 -*-
# @file runner.py
# @brief Agent Runner - 管理单个 Agent 的执行生命周期
# @author sailing-innocent
# @date 2025-02-25
# @version 1.0
# ---------------------------------

import asyncio
import logging
import random
from datetime import datetime
from typing import Dict, Any, Optional, Callable

from sail_server.data.agent import (
    AgentTask, AgentStep, AgentOutput,
    AgentStepData
)
from sail_server.db import get_db_session

logger = logging.getLogger("sail_server.agent_runner")


class AgentRunner:
    """
    Agent 运行器 - 管理单个 Agent 的执行生命周期
    
    职责：
    1. 加载 Agent 配置
    2. 执行 Agent 逻辑（调用 LLM、工具等）
    3. 记录执行步骤
    4. 更新任务状态
    5. 生成输出结果
    
    当前实现为 Mock 版本，用于调试 UI 状态：
    - 随机延时模拟执行时间
    - 随机失败情况模拟错误处理
    """
    
    # Mock 配置
    MOCK_MIN_DELAY = 0.3  # 最小步骤延时（秒）
    MOCK_MAX_DELAY = 1.0  # 最大步骤延时（秒）
    MOCK_FAILURE_RATE = 0.05  # 失败率（5%）
    MOCK_MIN_STEPS = 2  # 最小步骤数
    MOCK_MAX_STEPS = 4  # 最大步骤数
    
    def __init__(self, task_id: int, event_callback: Optional[Callable] = None):
        self.task_id = task_id
        self.event_callback = event_callback
        self._cancelled = False
        self._current_step = 0
        self._start_time: Optional[datetime] = None
    
    async def start(self):
        """启动 Agent 执行"""
        self._start_time = datetime.utcnow()
        
        with get_db_session() as db:
            task = db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
            if not task:
                logger.error(f"Task {self.task_id} not found")
                return
            
            # 更新任务状态
            task.status = 'running'
            task.started_at = self._start_time
            
            # 更新 Prompt 状态
            prompt = task.prompt
            prompt.status = 'processing'
            prompt.started_at = self._start_time
            
            db.commit()
        
        self._emit_event('task_started', {'started_at': self._start_time.isoformat()})
        logger.info(f"Task {self.task_id} started")
        
        try:
            # 执行 Agent 逻辑（Mock）
            await self._run_mock_logic()
            
            # 标记完成
            if not self._cancelled:
                await self._complete_task()
            
        except asyncio.CancelledError:
            await self._cancel_task()
            raise
        except Exception as e:
            logger.error(f"Task {self.task_id} failed: {e}")
            await self._fail_task(str(e))
    
    async def _run_mock_logic(self):
        """
        Mock Agent 核心逻辑
        
        模拟执行过程：
        1. 随机生成步骤数
        2. 每个步骤随机延时
        3. 随机失败情况
        """
        # 随机决定步骤数
        total_steps = random.randint(self.MOCK_MIN_STEPS, self.MOCK_MAX_STEPS)
        
        for i in range(total_steps):
            if self._cancelled:
                break
            
            self._current_step = i + 1
            
            # 模拟思考步骤
            await self._add_step(
                'thought', 
                f'思考步骤 {i+1}/{total_steps}', 
                f'正在分析问题... (Mock 思考内容)',
                {'iteration': i + 1}
            )
            
            # 随机延时
            delay = random.uniform(self.MOCK_MIN_DELAY, self.MOCK_MAX_DELAY)
            await asyncio.sleep(delay)
            
            if self._cancelled:
                break
            
            # 模拟行动步骤
            await self._add_step(
                'action', 
                f'执行步骤 {i+1}/{total_steps}', 
                f'执行相应操作... (Mock 执行内容)',
                {'delay_ms': int(delay * 1000)}
            )
            
            # 更新进度
            progress = int((i + 1) / total_steps * 100)
            await self._update_progress(progress)
            
            # 随机失败（在最后一个步骤前检查）
            if i < total_steps - 1 and random.random() < self.MOCK_FAILURE_RATE:
                await self._add_step(
                    'error',
                    '执行出错',
                    'Mock 随机错误：模拟执行失败情况',
                    {'error_type': 'mock_failure'}
                )
                raise Exception("Mock random failure")
            
            # 随机延时
            await asyncio.sleep(random.uniform(self.MOCK_MIN_DELAY, self.MOCK_MAX_DELAY))
        
        if not self._cancelled:
            # 完成步骤
            await self._add_step(
                'completion', 
                '任务完成', 
                '所有步骤已执行完毕 (Mock 完成)',
                {'total_steps': total_steps}
            )
    
    async def _add_step(self, step_type: str, title: str, content: str, meta_data: Dict = None):
        """添加执行步骤"""
        step_start = datetime.utcnow()
        
        with get_db_session() as db:
            step = AgentStep(
                task_id=self.task_id,
                step_number=self._current_step,
                step_type=step_type,
                title=title,
                content=content,
                content_summary=content[:100] + '...' if len(content) > 100 else content,
                meta_data=meta_data or {},
            )
            db.add(step)
            db.commit()
            db.refresh(step)
            
            step_data = AgentStepData.read_from_orm(step)
        
        # 计算步骤耗时
        duration_ms = int((datetime.utcnow() - step_start).total_seconds() * 1000)
        
        self._emit_event('step_update', {
            'step': {
                'id': step_data.id,
                'task_id': step_data.task_id,
                'step_number': step_data.step_number,
                'step_type': step_data.step_type,
                'title': step_data.title,
                'content_summary': step_data.content_summary,
                'meta_data': step_data.meta_data,
                'created_at': step_data.created_at.isoformat() if step_data.created_at else None,
            },
            'step_number': self._current_step,
        })
        
        logger.debug(f"Task {self.task_id} step {self._current_step}: {title}")
    
    async def _update_progress(self, progress: int):
        """更新任务进度"""
        with get_db_session() as db:
            task = db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
            task.progress = progress
            db.commit()
        
        self._emit_event('progress_update', {'progress': progress})
    
    async def _complete_task(self):
        """标记任务完成"""
        completed_at = datetime.utcnow()
        output_id = None
        
        with get_db_session() as db:
            task = db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
            task.status = 'completed'
            task.progress = 100
            task.completed_at = completed_at
            
            # 创建输出结果
            output = AgentOutput(
                task_id=self.task_id,
                output_type='text',
                content='Mock Agent 执行完成的结果内容。\n\n这是一个模拟的输出结果，用于测试前端 UI 状态显示。',
                meta_data={'mock': True, 'total_steps': self._current_step}
            )
            db.add(output)
            db.flush()  # Flush to get the ID
            output_id = output.id
            
            # 更新 Prompt 状态
            prompt = task.prompt
            prompt.status = 'completed'
            prompt.completed_at = completed_at
            
            db.commit()
        
        self._emit_event('task_completed', {
            'completed_at': completed_at.isoformat(),
            'output_id': output_id,
        })
        
        logger.info(f"Task {self.task_id} completed")
    
    async def _fail_task(self, error_message: str):
        """标记任务失败"""
        failed_at = datetime.utcnow()
        
        with get_db_session() as db:
            task = db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
            task.status = 'failed'
            task.error_message = error_message
            task.completed_at = failed_at
            
            # 创建错误输出
            output = AgentOutput(
                task_id=self.task_id,
                output_type='error',
                content=error_message,
                meta_data={'mock': True, 'error': True}
            )
            db.add(output)
            
            # 更新 Prompt 状态
            prompt = task.prompt
            prompt.status = 'failed'
            prompt.completed_at = failed_at
            
            db.commit()
        
        self._emit_event('task_failed', {
            'error_message': error_message,
            'failed_at': failed_at.isoformat(),
        })
        
        logger.info(f"Task {self.task_id} failed: {error_message}")
    
    async def _cancel_task(self):
        """取消任务"""
        cancelled_at = datetime.utcnow()
        
        with get_db_session() as db:
            task = db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
            task.status = 'cancelled'
            task.completed_at = cancelled_at
            
            prompt = task.prompt
            prompt.status = 'cancelled'
            prompt.completed_at = cancelled_at
            
            db.commit()
        
        self._emit_event('task_cancelled', {
            'cancelled_at': cancelled_at.isoformat(),
        })
        
        logger.info(f"Task {self.task_id} cancelled")
    
    async def cancel(self):
        """取消执行"""
        self._cancelled = True
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """发送事件"""
        if self.event_callback:
            self.event_callback(self.task_id, event_type, data)
