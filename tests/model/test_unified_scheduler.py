# -*- coding: utf-8 -*-
# @file test_unified_scheduler.py
# @brief Unit tests for Unified Agent Scheduler
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from sail_server.model.unified_scheduler import (
    UnifiedAgentScheduler,
    SchedulerConfig,
    TaskQueueItem,
    TaskPriority,
    TaskProgressEvent,
    ResourceUsage,
)
from sail_server.data.unified_agent import (
    UnifiedTaskData,
    TaskStatus,
    TaskType,
)
from sail_server.utils.websocket_manager import (
    WebSocketManager,
    WSMessage,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    return MagicMock(spec=Session)


@pytest.fixture
def db_session_factory(mock_db_session):
    """数据库会话工厂"""
    def factory():
        return mock_db_session
    return factory


@pytest.fixture
def scheduler_config():
    """调度器配置"""
    return SchedulerConfig(
        max_concurrent_tasks=3,
        max_tasks_per_user=2,
        poll_interval_seconds=0.1,
        task_timeout_seconds=60,
    )


@pytest.fixture
def scheduler(db_session_factory, scheduler_config):
    """调度器实例"""
    return UnifiedAgentScheduler(db_session_factory, scheduler_config)


# ============================================================================
# Test TaskQueueItem
# ============================================================================

class TestTaskQueueItem:
    """测试任务队列项"""
    
    def test_priority_score_calculation(self):
        """测试优先级分数计算"""
        now = datetime.utcnow()
        
        # 高优先级任务
        score_high = TaskQueueItem.calculate_priority_score(
            TaskPriority.HIGH, now, wait_time_boost=False
        )
        
        # 低优先级任务
        score_low = TaskQueueItem.calculate_priority_score(
            TaskPriority.LOW, now, wait_time_boost=False
        )
        
        # 高优先级分数应该更低（排序更靠前）
        assert score_high < score_low
    
    def test_wait_time_boost(self):
        """测试等待时间加成"""
        # 创建一个10分钟前的任务
        old_time = datetime.utcnow()
        old_time = old_time.replace(minute=old_time.minute - 10)
        
        score_with_boost = TaskQueueItem.calculate_priority_score(
            TaskPriority.NORMAL, old_time, wait_time_boost=True
        )
        
        score_without_boost = TaskQueueItem.calculate_priority_score(
            TaskPriority.NORMAL, old_time, wait_time_boost=False
        )
        
        # 有等待加成的分数应该更低（优先级更高）
        assert score_with_boost < score_without_boost
    
    def test_queue_item_ordering(self):
        """测试队列项排序"""
        now = datetime.utcnow()
        
        item1 = TaskQueueItem(
            priority_score=1.0,
            task_id=1,
            priority=TaskPriority.HIGH,
            created_at=now,
            task_type="general",
        )
        
        item2 = TaskQueueItem(
            priority_score=2.0,
            task_id=2,
            priority=TaskPriority.LOW,
            created_at=now,
            task_type="general",
        )
        
        # 优先级队列中，分数小的排前面
        assert item1 < item2


# ============================================================================
# Test ResourceUsage
# ============================================================================

class TestResourceUsage:
    """测试资源使用"""
    
    def test_can_accept_new_task(self):
        """测试资源检查"""
        config = SchedulerConfig(
            max_concurrent_tasks=5,
            token_rate_limit_per_minute=10000,
        )
        
        usage = ResourceUsage(
            running_tasks=3,
            tokens_used_last_minute=5000,
        )
        
        # 应该可以接受新任务
        assert usage.can_accept_new_task(config) is True
        
        # 超过并发限制
        usage.running_tasks = 5
        assert usage.can_accept_new_task(config) is False
        
        # 超过 Token 限制
        usage.running_tasks = 3
        usage.tokens_used_last_minute = 15000
        assert usage.can_accept_new_task(config) is False


# ============================================================================
# Test UnifiedAgentScheduler
# ============================================================================

@pytest.mark.asyncio
class TestUnifiedAgentScheduler:
    """测试统一调度器"""
    
    async def test_start_stop(self, scheduler):
        """测试启动和停止"""
        # Mock _recover_pending_tasks
        with patch.object(scheduler, '_recover_pending_tasks', return_value=None):
            await scheduler.start()
            assert scheduler.is_running() is True
            
            await scheduler.stop()
            assert scheduler.is_running() is False
    
    async def test_schedule_task(self, scheduler, mock_db_session):
        """测试调度任务"""
        # Mock DAO
        mock_task = Mock()
        mock_task.id = 1
        mock_task.priority = 5
        mock_task.created_at = datetime.utcnow()
        mock_task.task_type = "general"
        mock_task.status = TaskStatus.PENDING
        mock_task.estimated_cost = None  # 修复：设置 estimated_cost 为 None
        mock_task.actual_cost = 0.0
        mock_task.actual_tokens = 0
        mock_task.started_at = None
        mock_task.completed_at = None
        mock_task.cancelled_at = None
        mock_task.updated_at = datetime.utcnow()
        mock_task.error_message = None
        mock_task.error_code = None
        mock_task.current_phase = None
        mock_task.progress = 0
        mock_task.result_data = None
        mock_task.review_status = "pending"
        mock_task.config = {}
        mock_task.edition_id = None
        mock_task.target_node_ids = None
        mock_task.target_scope = None
        mock_task.llm_provider = None
        mock_task.llm_model = None
        mock_task.prompt_template_id = None
        mock_task.estimated_tokens = None
        mock_task.sub_type = None
        
        with patch('sail_server.model.unified_scheduler.UnifiedTaskDAO') as MockDAO, \
             patch('sail_server.model.unified_scheduler.UnifiedStepDAO') as MockStepDAO:
            mock_dao = MockDAO.return_value
            mock_dao.create.return_value = mock_task
            mock_dao.mark_as_scheduled.return_value = mock_task
            
            mock_step_dao = MockStepDAO.return_value
            mock_step_dao.get_next_step_number.return_value = 1
            
            task_data = UnifiedTaskData(
                task_type=TaskType.GENERAL,
                priority=5,
            )
            
            result = await scheduler.schedule_task(task_data)
            
            assert result is not None
            assert scheduler._stats["total_scheduled"] == 1
    
    async def test_cancel_task(self, scheduler, mock_db_session):
        """测试取消任务"""
        # Mock DAO
        mock_task = Mock()
        mock_task.id = 1
        mock_task.status = TaskStatus.PENDING
        
        with patch('sail_server.model.unified_scheduler.UnifiedTaskDAO') as MockDAO:
            mock_dao = MockDAO.return_value
            mock_dao.get_by_id.return_value = mock_task
            mock_dao.mark_as_cancelled.return_value = mock_task
            
            result = await scheduler.cancel_task(1)
            
            assert result is True
            assert scheduler._stats["total_cancelled"] == 1
    
    async def test_cancel_nonexistent_task(self, scheduler):
        """测试取消不存在的任务"""
        with patch('sail_server.model.unified_scheduler.UnifiedTaskDAO') as MockDAO:
            mock_dao = MockDAO.return_value
            mock_dao.get_by_id.return_value = None
            
            result = await scheduler.cancel_task(999)
            
            assert result is False
    
    async def test_progress_callback(self, scheduler):
        """测试进度回调"""
        events = []
        
        def callback(event: TaskProgressEvent):
            events.append(event)
        
        scheduler.subscribe(callback)
        
        # 发送测试事件
        event = TaskProgressEvent(
            task_id=1,
            event_type="started",
            data={"test": True}
        )
        scheduler._emit_event(event)
        
        assert len(events) == 1
        assert events[0].task_id == 1
        assert events[0].event_type == "started"
        
        # 取消订阅
        scheduler.unsubscribe(callback)
        scheduler._emit_event(event)
        
        # 事件数应该不变
        assert len(events) == 1
    
    async def test_task_specific_callback(self, scheduler):
        """测试特定任务回调"""
        events_task1 = []
        events_task2 = []
        
        def callback1(event: TaskProgressEvent):
            events_task1.append(event)
        
        def callback2(event: TaskProgressEvent):
            events_task2.append(event)
        
        scheduler.subscribe_task(1, callback1)
        scheduler.subscribe_task(2, callback2)
        
        # 发送任务1的事件
        event1 = TaskProgressEvent(task_id=1, event_type="progress", data={})
        scheduler._emit_event(event1)
        
        assert len(events_task1) == 1
        assert len(events_task2) == 0
        
        # 发送任务2的事件
        event2 = TaskProgressEvent(task_id=2, event_type="progress", data={})
        scheduler._emit_event(event2)
        
        assert len(events_task1) == 1
        assert len(events_task2) == 1
    
    def test_get_stats(self, scheduler):
        """测试获取统计信息"""
        stats = scheduler.get_stats()
        
        assert "total_scheduled" in stats
        assert "total_completed" in stats
        assert "total_failed" in stats
        assert "running_tasks" in stats
        assert "queued_tasks" in stats


# ============================================================================
# Test WebSocket Manager
# ============================================================================

@pytest.mark.asyncio
class TestWebSocketManager:
    """测试 WebSocket 管理器"""
    
    @pytest.fixture
    def ws_manager(self):
        """WebSocket 管理器实例"""
        return WebSocketManager()
    
    async def test_connect_disconnect(self, ws_manager):
        """测试连接和断开"""
        messages = []
        
        def send_callback(msg: str):
            messages.append(msg)
        
        # 连接
        result = await ws_manager.connect("client1", send_callback)
        assert result is True
        assert ws_manager.is_client_connected("client1") is True
        
        # 验证收到了欢迎消息
        assert len(messages) == 1
        
        # 断开
        await ws_manager.disconnect("client1")
        assert ws_manager.is_client_connected("client1") is False
    
    async def test_subscribe_unsubscribe_task(self, ws_manager):
        """测试任务订阅和取消订阅"""
        messages = []
        
        def send_callback(msg: str):
            messages.append(msg)
        
        await ws_manager.connect("client1", send_callback)
        
        # 订阅任务
        result = await ws_manager.subscribe_task("client1", 1)
        assert result is True
        
        # 验证收到了确认消息
        assert len(messages) == 2  # welcome + subscribed
        
        # 取消订阅
        result = await ws_manager.unsubscribe_task("client1", 1)
        assert result is True
    
    async def test_send_to_task_subscribers(self, ws_manager):
        """测试发送给任务订阅者"""
        client1_messages = []
        client2_messages = []
        
        await ws_manager.connect("client1", lambda msg: client1_messages.append(msg))
        await ws_manager.connect("client2", lambda msg: client2_messages.append(msg))
        
        # client1 订阅任务1
        await ws_manager.subscribe_task("client1", 1)
        
        # client2 订阅任务2
        await ws_manager.subscribe_task("client2", 2)
        
        # 发送消息给任务1的订阅者
        await ws_manager.send_to_task_subscribers(1, WSMessage(
            type="progress",
            task_id=1,
            data={"progress": 50}
        ))
        
        # client1 应该收到消息
        assert len(client1_messages) == 3  # welcome + subscribed + progress
        
        # client2 不应该收到消息
        assert len(client2_messages) == 2  # welcome + subscribed
    
    async def test_broadcast(self, ws_manager):
        """测试广播消息"""
        client1_messages = []
        client2_messages = []
        
        await ws_manager.connect("client1", lambda msg: client1_messages.append(msg))
        await ws_manager.connect("client2", lambda msg: client2_messages.append(msg))
        
        # 广播消息
        count = await ws_manager.broadcast(WSMessage(
            type="announcement",
            data={"message": "Hello all"}
        ))
        
        assert count == 2
        assert len(client1_messages) == 2  # welcome + announcement
        assert len(client2_messages) == 2  # welcome + announcement
    
    async def test_handle_message(self, ws_manager):
        """测试消息处理"""
        messages = []
        
        await ws_manager.connect("client1", lambda msg: messages.append(msg))
        
        # 发送 ping 消息
        await ws_manager.handle_message("client1", '{"type": "ping"}')
        
        # 应该收到 pong 响应
        assert any("pong" in msg for msg in messages)
        
        # 发送订阅消息
        await ws_manager.handle_message("client1", '{"type": "subscribe", "task_id": 1}')
        
        # 应该收到订阅确认
        assert any("subscribed" in msg for msg in messages)
    
    async def test_handle_invalid_json(self, ws_manager):
        """测试处理无效 JSON"""
        messages = []
        
        await ws_manager.connect("client1", lambda msg: messages.append(msg))
        
        # 发送无效 JSON
        await ws_manager.handle_message("client1", "invalid json")
        
        # 应该收到错误消息
        assert any("error" in msg for msg in messages)
    
    def test_get_stats(self, ws_manager):
        """测试获取统计信息"""
        stats = ws_manager.get_stats()
        
        assert "total_connections" in stats
        assert "total_messages_sent" in stats
        assert "total_messages_received" in stats
        assert "active_connections" in stats


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
class TestSchedulerIntegration:
    """集成测试"""
    
    async def test_full_task_lifecycle(self, scheduler, mock_db_session):
        """测试完整的任务生命周期"""
        # Mock DAO - 需要设置所有必需的属性
        mock_task = Mock()
        mock_task.id = 1
        mock_task.priority = 5
        mock_task.created_at = datetime.utcnow()
        mock_task.task_type = "general"
        mock_task.status = TaskStatus.PENDING
        mock_task.started_at = None
        mock_task.progress = 0
        mock_task.actual_tokens = 0
        mock_task.actual_cost = 0.0
        mock_task.error_message = None
        mock_task.error_code = None
        mock_task.updated_at = datetime.utcnow()
        mock_task.completed_at = None
        mock_task.cancelled_at = None
        mock_task.current_phase = None
        mock_task.result_data = None
        mock_task.review_status = "pending"
        mock_task.config = {}
        mock_task.edition_id = None
        mock_task.target_node_ids = None
        mock_task.target_scope = None
        mock_task.llm_provider = None
        mock_task.llm_model = None
        mock_task.prompt_template_id = None
        mock_task.estimated_tokens = None
        mock_task.estimated_cost = None
        mock_task.sub_type = None
        
        events = []
        
        def callback(event: TaskProgressEvent):
            events.append(event)
        
        scheduler.subscribe(callback)
        
        with patch('sail_server.model.unified_scheduler.UnifiedTaskDAO') as MockTaskDAO, \
             patch('sail_server.model.unified_scheduler.UnifiedStepDAO') as MockStepDAO, \
             patch('sail_server.model.unified_scheduler.UnifiedEventDAO') as MockEventDAO:
            
            mock_task_dao = MockTaskDAO.return_value
            mock_step_dao = MockStepDAO.return_value
            mock_event_dao = MockEventDAO.return_value
            
            mock_task_dao.create.return_value = mock_task
            mock_task_dao.mark_as_scheduled.return_value = mock_task
            mock_task_dao.mark_as_running.return_value = mock_task
            mock_task_dao.mark_as_completed.return_value = mock_task
            mock_task_dao.get_by_id.return_value = mock_task
            
            mock_step = Mock()
            mock_step.id = 1
            mock_step_dao.create.return_value = mock_step
            mock_step_dao.get_next_step_number.return_value = 1
            
            mock_event = Mock()
            mock_event_dao.create.return_value = mock_event
            
            # 1. 创建任务
            task_data = UnifiedTaskData(
                task_type=TaskType.GENERAL,
                priority=5,
            )
            
            result = await scheduler.schedule_task(task_data)
            assert result is not None
            
            # 2. 启动调度器并等待任务执行
            with patch.object(scheduler, '_recover_pending_tasks', return_value=None):
                await scheduler.start()
                
                # 等待任务开始执行
                await asyncio.sleep(0.2)
                
                # 手动触发任务执行（因为队列是空的，我们需要直接启动）
                await scheduler._start_task_execution(1)
                
                # 等待任务完成
                await asyncio.sleep(2)
                
                await scheduler.stop()
            
            # 3. 验证事件
            event_types = [e.event_type for e in events]
            assert "started" in event_types
            assert "progress" in event_types
            assert "completed" in event_types or "failed" in event_types


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.asyncio
class TestSchedulerPerformance:
    """性能测试"""
    
    async def test_high_frequency_scheduling(self, scheduler):
        """测试高频调度"""
        # Mock DAO - 需要设置所有必需的属性
        mock_task = Mock()
        mock_task.id = 1
        mock_task.priority = 5
        mock_task.created_at = datetime.utcnow()
        mock_task.task_type = "general"
        mock_task.status = TaskStatus.PENDING
        mock_task.estimated_cost = None
        mock_task.actual_cost = 0.0
        mock_task.actual_tokens = 0
        mock_task.started_at = None
        mock_task.completed_at = None
        mock_task.cancelled_at = None
        mock_task.updated_at = datetime.utcnow()
        mock_task.error_message = None
        mock_task.error_code = None
        mock_task.current_phase = None
        mock_task.progress = 0
        mock_task.result_data = None
        mock_task.review_status = "pending"
        mock_task.config = {}
        mock_task.edition_id = None
        mock_task.target_node_ids = None
        mock_task.target_scope = None
        mock_task.llm_provider = None
        mock_task.llm_model = None
        mock_task.prompt_template_id = None
        mock_task.estimated_tokens = None
        mock_task.sub_type = None
        
        with patch('sail_server.model.unified_scheduler.UnifiedTaskDAO') as MockDAO, \
             patch('sail_server.model.unified_scheduler.UnifiedStepDAO') as MockStepDAO:
            mock_dao = MockDAO.return_value
            mock_dao.create.return_value = mock_task
            mock_dao.mark_as_scheduled.return_value = mock_task
            
            mock_step_dao = MockStepDAO.return_value
            mock_step_dao.get_next_step_number.return_value = 1
            
            # 快速调度多个任务
            start_time = datetime.utcnow()
            
            for i in range(10):
                task_data = UnifiedTaskData(
                    task_type=TaskType.GENERAL,
                    priority=5,
                )
                await scheduler.schedule_task(task_data)
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            
            # 应该在合理时间内完成
            assert elapsed < 1.0
            assert scheduler._stats["total_scheduled"] == 10
