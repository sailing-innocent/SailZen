# -*- coding: utf-8 -*-
# @file test_unified_agent.py
# @brief Tests for Unified Agent Models
# @author sailing-innocent
# @date 2026-02-26
# ---------------------------------

import pytest
from datetime import datetime
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from sail_server.data.orm import ORMBase
from sail_server.model.unified_agent import (
    UnifiedAgentTask,
    UnifiedAgentStep,
    UnifiedAgentEvent,
    UnifiedTaskData,
    UnifiedStepData,
    UnifiedTaskCreateRequest,
    TaskType,
    TaskStatus,
    ReviewStatus,
    StepType,
)
from sail_server.data.unified_agent import (
    UnifiedTaskDAO,
    UnifiedStepDAO,
    UnifiedEventDAO,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """创建内存数据库会话"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ORMBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def task_dao(db_session: Session) -> UnifiedTaskDAO:
    """创建 TaskDAO"""
    return UnifiedTaskDAO(db_session)


@pytest.fixture
def step_dao(db_session: Session) -> UnifiedStepDAO:
    """创建 StepDAO"""
    return UnifiedStepDAO(db_session)


@pytest.fixture
def event_dao(db_session: Session) -> UnifiedEventDAO:
    """创建 EventDAO"""
    return UnifiedEventDAO(db_session)


# ============================================================================
# UnifiedAgentTask Model Tests
# ============================================================================

class TestUnifiedAgentTask:
    """UnifiedAgentTask 模型测试"""
    
    def test_create_basic_task(self, db_session: Session):
        """测试创建基本任务"""
        task = UnifiedAgentTask(
            task_type=TaskType.GENERAL,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        db_session.commit()
        
        assert task.id is not None
        assert task.task_type == TaskType.GENERAL
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0
        assert task.priority == 5
    
    def test_create_novel_analysis_task(self, db_session: Session):
        """测试创建小说分析任务"""
        task = UnifiedAgentTask(
            task_type=TaskType.NOVEL_ANALYSIS,
            sub_type="outline_extraction",
            edition_id=1,
            target_node_ids=[1, 2, 3],
            target_scope="range",
            llm_provider="google",
            llm_model="gemini-2.0-flash",
            prompt_template_id="outline_extraction_v1",
            priority=3,
        )
        db_session.add(task)
        db_session.commit()
        
        assert task.id is not None
        assert task.task_type == TaskType.NOVEL_ANALYSIS
        assert task.sub_type == "outline_extraction"
        assert task.edition_id == 1
        assert task.target_node_ids == [1, 2, 3]
        assert task.llm_provider == "google"
        assert task.priority == 3
    
    def test_task_cost_tracking(self, db_session: Session):
        """测试任务成本追踪"""
        task = UnifiedAgentTask(
            task_type=TaskType.CODE,
            estimated_tokens=1000,
            estimated_cost=0.001,
            actual_tokens=1200,
            actual_cost=0.0012,
        )
        db_session.add(task)
        db_session.commit()
        
        assert task.estimated_tokens == 1000
        assert float(task.estimated_cost) == 0.001
        assert task.actual_tokens == 1200
        assert float(task.actual_cost) == 0.0012
    
    def test_task_result_data(self, db_session: Session):
        """测试任务结果数据"""
        result_data = {
            "outputs": [
                {"type": "outline", "data": {"title": "Test"}}
            ],
            "summary": "Test summary"
        }
        task = UnifiedAgentTask(
            task_type=TaskType.NOVEL_ANALYSIS,
            result_data=result_data,
            review_status=ReviewStatus.PENDING,
        )
        db_session.add(task)
        db_session.commit()
        
        assert task.result_data == result_data
        assert task.result_data["outputs"][0]["type"] == "outline"
        assert task.review_status == ReviewStatus.PENDING
    
    def test_task_timestamps(self, db_session: Session):
        """测试任务时间戳"""
        now = datetime.utcnow()
        task = UnifiedAgentTask(
            task_type=TaskType.GENERAL,
            started_at=now,
            completed_at=now,
            cancelled_at=now,
        )
        db_session.add(task)
        db_session.commit()
        
        assert task.created_at is not None
        assert task.started_at == now
        assert task.completed_at == now
        assert task.cancelled_at == now


# ============================================================================
# UnifiedAgentStep Model Tests
# ============================================================================

class TestUnifiedAgentStep:
    """UnifiedAgentStep 模型测试"""
    
    def test_create_basic_step(self, db_session: Session):
        """测试创建基本步骤"""
        # 先创建任务
        task = UnifiedAgentTask(task_type=TaskType.GENERAL)
        db_session.add(task)
        db_session.commit()
        
        step = UnifiedAgentStep(
            task_id=task.id,
            step_number=1,
            step_type=StepType.THOUGHT,
            title="Step 1",
            content="Test content",
        )
        db_session.add(step)
        db_session.commit()
        
        assert step.id is not None
        assert step.task_id == task.id
        assert step.step_number == 1
        assert step.step_type == StepType.THOUGHT
    
    def test_llm_step_tracking(self, db_session: Session):
        """测试 LLM 步骤追踪"""
        task = UnifiedAgentTask(task_type=TaskType.GENERAL)
        db_session.add(task)
        db_session.commit()
        
        step = UnifiedAgentStep(
            task_id=task.id,
            step_number=1,
            step_type=StepType.LLM_CALL,
            llm_provider="openai",
            llm_model="gpt-4",
            prompt_tokens=500,
            completion_tokens=200,
            cost=0.0005,
        )
        db_session.add(step)
        db_session.commit()
        
        assert step.llm_provider == "openai"
        assert step.llm_model == "gpt-4"
        assert step.prompt_tokens == 500
        assert step.completion_tokens == 200
        assert float(step.cost) == 0.0005


# ============================================================================
# UnifiedTaskDAO Tests
# ============================================================================

class TestUnifiedTaskDAO:
    """UnifiedTaskDAO 测试"""
    
    def test_create_task(self, task_dao: UnifiedTaskDAO):
        """测试创建任务"""
        data = UnifiedTaskData(
            task_type=TaskType.GENERAL,
            priority=3,
        )
        task = task_dao.create(data)
        
        assert task.id is not None
        assert task.task_type == TaskType.GENERAL
        assert task.priority == 3
    
    def test_get_by_id(self, task_dao: UnifiedTaskDAO):
        """测试根据 ID 获取任务"""
        data = UnifiedTaskData(task_type=TaskType.GENERAL)
        created = task_dao.create(data)
        
        fetched = task_dao.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.task_type == TaskType.GENERAL
    
    def test_update_task(self, task_dao: UnifiedTaskDAO):
        """测试更新任务"""
        data = UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.PENDING)
        task = task_dao.create(data)
        
        updated = task_dao.update(task.id, status=TaskStatus.RUNNING, progress=50)
        assert updated is not None
        assert updated.status == TaskStatus.RUNNING
        assert updated.progress == 50
    
    def test_delete_task(self, task_dao: UnifiedTaskDAO):
        """测试删除任务"""
        data = UnifiedTaskData(task_type=TaskType.GENERAL)
        task = task_dao.create(data)
        task_id = task.id
        
        result = task_dao.delete(task_id)
        assert result is True
        
        fetched = task_dao.get_by_id(task_id)
        assert fetched is None
    
    def test_list_tasks_by_status(self, task_dao: UnifiedTaskDAO):
        """测试按状态列表查询"""
        # 创建多个任务
        task_dao.create(UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.PENDING))
        task_dao.create(UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.PENDING))
        task_dao.create(UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.COMPLETED))
        
        pending_tasks = task_dao.list_tasks(status=TaskStatus.PENDING)
        assert len(pending_tasks) == 2
        
        completed_tasks = task_dao.list_tasks(status=TaskStatus.COMPLETED)
        assert len(completed_tasks) == 1
    
    def test_list_tasks_by_type(self, task_dao: UnifiedTaskDAO):
        """测试按类型列表查询"""
        task_dao.create(UnifiedTaskData(task_type=TaskType.GENERAL))
        task_dao.create(UnifiedTaskData(task_type=TaskType.NOVEL_ANALYSIS, sub_type="outline_extraction"))
        task_dao.create(UnifiedTaskData(task_type=TaskType.CODE))
        
        general_tasks = task_dao.list_tasks(task_type=TaskType.GENERAL)
        assert len(general_tasks) == 1
        
        novel_tasks = task_dao.list_tasks(task_type=TaskType.NOVEL_ANALYSIS)
        assert len(novel_tasks) == 1
    
    def test_get_pending_tasks(self, task_dao: UnifiedTaskDAO):
        """测试获取待处理任务"""
        # 创建不同优先级的任务
        task_dao.create(UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.PENDING, priority=5))
        task_dao.create(UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.PENDING, priority=1))
        task_dao.create(UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.PENDING, priority=3))
        task_dao.create(UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.RUNNING, priority=1))
        
        pending = task_dao.get_pending_tasks(limit=10)
        assert len(pending) == 3
        # 验证按优先级排序
        assert pending[0].priority == 1
        assert pending[1].priority == 3
        assert pending[2].priority == 5
    
    def test_mark_as_running(self, task_dao: UnifiedTaskDAO):
        """测试标记为运行中"""
        data = UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.PENDING)
        task = task_dao.create(data)
        
        updated = task_dao.mark_as_running(task.id)
        assert updated is not None
        assert updated.status == TaskStatus.RUNNING
        assert updated.started_at is not None
    
    def test_mark_as_completed(self, task_dao: UnifiedTaskDAO):
        """测试标记为已完成"""
        data = UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.RUNNING)
        task = task_dao.create(data)
        
        result_data = {"summary": "Test result"}
        updated = task_dao.mark_as_completed(task.id, result_data)
        
        assert updated is not None
        assert updated.status == TaskStatus.COMPLETED
        assert updated.progress == 100
        assert updated.completed_at is not None
        assert updated.result_data == result_data
    
    def test_mark_as_failed(self, task_dao: UnifiedTaskDAO):
        """测试标记为失败"""
        data = UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.RUNNING)
        task = task_dao.create(data)
        
        updated = task_dao.mark_as_failed(task.id, "Test error", "ERR_001")
        
        assert updated is not None
        assert updated.status == TaskStatus.FAILED
        assert updated.error_message == "Test error"
        assert updated.error_code == "ERR_001"
        assert updated.completed_at is not None
    
    def test_update_progress(self, task_dao: UnifiedTaskDAO):
        """测试更新进度"""
        data = UnifiedTaskData(task_type=TaskType.GENERAL, status=TaskStatus.RUNNING)
        task = task_dao.create(data)
        
        updated = task_dao.update_progress(task.id, 75, "Processing chunk 3/4")
        
        assert updated is not None
        assert updated.progress == 75
        assert updated.current_phase == "Processing chunk 3/4"
    
    def test_update_cost(self, task_dao: UnifiedTaskDAO):
        """测试更新成本"""
        data = UnifiedTaskData(task_type=TaskType.GENERAL)
        task = task_dao.create(data)
        
        updated = task_dao.update_cost(task.id, 1500, 0.0015)
        
        assert updated is not None
        assert updated.actual_tokens == 1500
        assert float(updated.actual_cost) == 0.0015


# ============================================================================
# UnifiedStepDAO Tests
# ============================================================================

class TestUnifiedStepDAO:
    """UnifiedStepDAO 测试"""
    
    def test_create_step(self, db_session: Session, step_dao: UnifiedStepDAO):
        """测试创建步骤"""
        # 先创建任务
        task = UnifiedAgentTask(task_type=TaskType.GENERAL)
        db_session.add(task)
        db_session.commit()
        
        step = step_dao.create(
            task_id=task.id,
            step_number=1,
            step_type=StepType.THOUGHT,
            title="Test Step",
            content="Test content",
        )
        
        assert step.id is not None
        assert step.task_id == task.id
        assert step.step_number == 1
    
    def test_get_by_task_id(self, db_session: Session, step_dao: UnifiedStepDAO):
        """测试获取任务的所有步骤"""
        task = UnifiedAgentTask(task_type=TaskType.GENERAL)
        db_session.add(task)
        db_session.commit()
        
        # 创建多个步骤
        step_dao.create(task.id, 1, StepType.THOUGHT)
        step_dao.create(task.id, 2, StepType.ACTION)
        step_dao.create(task.id, 3, StepType.COMPLETION)
        
        steps = step_dao.get_by_task_id(task.id)
        assert len(steps) == 3
        assert steps[0].step_number == 1
        assert steps[1].step_number == 2
        assert steps[2].step_number == 3
    
    def test_get_next_step_number(self, db_session: Session, step_dao: UnifiedStepDAO):
        """测试获取下一步序号"""
        task = UnifiedAgentTask(task_type=TaskType.GENERAL)
        db_session.add(task)
        db_session.commit()
        
        # 无步骤时
        assert step_dao.get_next_step_number(task.id) == 1
        
        # 创建步骤后
        step_dao.create(task.id, 1, StepType.THOUGHT)
        assert step_dao.get_next_step_number(task.id) == 2
        
        step_dao.create(task.id, 2, StepType.ACTION)
        assert step_dao.get_next_step_number(task.id) == 3


# ============================================================================
# UnifiedTaskData DTO Tests
# ============================================================================

class TestUnifiedTaskData:
    """UnifiedTaskData DTO 测试"""
    
    def test_from_orm(self, db_session: Session):
        """测试从 ORM 转换"""
        orm = UnifiedAgentTask(
            id=1,
            task_type=TaskType.NOVEL_ANALYSIS,
            sub_type="outline_extraction",
            edition_id=10,
            status=TaskStatus.RUNNING,
            progress=50,
            estimated_tokens=1000,
            actual_tokens=800,
        )
        db_session.add(orm)
        db_session.commit()
        
        dto = UnifiedTaskData.from_orm(orm, step_count=5)
        
        assert dto.id == 1
        assert dto.task_type == TaskType.NOVEL_ANALYSIS
        assert dto.sub_type == "outline_extraction"
        assert dto.edition_id == 10
        assert dto.status == TaskStatus.RUNNING
        assert dto.progress == 50
        assert dto.estimated_tokens == 1000
        assert dto.actual_tokens == 800
        assert dto.step_count == 5
    
    def test_to_orm(self):
        """测试转换为 ORM"""
        dto = UnifiedTaskData(
            id=1,
            task_type=TaskType.GENERAL,
            priority=3,
            status=TaskStatus.PENDING,
            config={"key": "value"},
        )
        
        orm = dto.to_orm()
        
        assert orm.task_type == TaskType.GENERAL
        assert orm.priority == 3
        assert orm.status == TaskStatus.PENDING
        assert orm.config == {"key": "value"}


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """集成测试"""
    
    def test_task_with_steps(self, db_session: Session, task_dao: UnifiedTaskDAO, step_dao: UnifiedStepDAO):
        """测试任务与步骤的关联"""
        # 创建任务
        task_data = UnifiedTaskData(task_type=TaskType.NOVEL_ANALYSIS)
        task = task_dao.create(task_data)
        
        # 创建步骤
        step1 = step_dao.create(task.id, 1, StepType.THOUGHT, title="分析需求")
        step2 = step_dao.create(task.id, 2, StepType.LLM_CALL, title="调用 LLM",
                               llm_provider="google", prompt_tokens=500, cost=0.0005)
        step3 = step_dao.create(task.id, 3, StepType.COMPLETION, title="完成")
        
        # 验证关联
        task_with_count = task_dao.get_with_step_count(task.id)
        assert task_with_count is not None
        assert task_with_count[1] == 3
        
        # 验证步骤
        steps = step_dao.get_by_task_id(task.id)
        assert len(steps) == 3
        assert steps[1].step_type == StepType.LLM_CALL
        assert steps[1].llm_provider == "google"
    
    def test_novel_analysis_workflow(self, task_dao: UnifiedTaskDAO):
        """测试小说分析完整工作流"""
        # 1. 创建任务
        data = UnifiedTaskData(
            task_type=TaskType.NOVEL_ANALYSIS,
            sub_type="outline_extraction",
            edition_id=1,
            target_node_ids=[1, 2, 3, 4, 5],
            target_scope="range",
            llm_provider="google",
            llm_model="gemini-2.0-flash",
            prompt_template_id="outline_extraction_v1",
            priority=2,
            estimated_tokens=5000,
            estimated_cost=0.005,
        )
        task = task_dao.create(data)
        assert task.status == TaskStatus.PENDING
        
        # 2. 调度任务
        task_dao.mark_as_scheduled(task.id)
        task = task_dao.get_by_id(task.id)
        assert task.status == TaskStatus.SCHEDULED
        
        # 3. 开始执行
        task_dao.mark_as_running(task.id)
        task = task_dao.get_by_id(task.id)
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None
        
        # 4. 更新进度
        task_dao.update_progress(task.id, 50, "Processing chunk 2/4")
        task = task_dao.get_by_id(task.id)
        assert task.progress == 50
        
        # 5. 更新成本
        task_dao.update_cost(task.id, 5200, 0.0052)
        task = task_dao.get_by_id(task.id)
        assert task.actual_tokens == 5200
        
        # 6. 完成
        result_data = {
            "outputs": [{"type": "outline", "title": "Test Outline"}],
            "summary": "Analysis completed"
        }
        task_dao.mark_as_completed(task.id, result_data)
        task = task_dao.get_by_id(task.id)
        assert task.status == TaskStatus.COMPLETED
        assert task.progress == 100
        assert task.result_data == result_data
        assert task.review_status == ReviewStatus.PENDING


# ============================================================================
# Enum Tests
# ============================================================================

class TestEnums:
    """枚举常量测试"""
    
    def test_task_type_values(self):
        """测试任务类型枚举"""
        assert TaskType.NOVEL_ANALYSIS == "novel_analysis"
        assert TaskType.CODE == "code"
        assert TaskType.WRITING == "writing"
        assert TaskType.GENERAL == "general"
        assert TaskType.DATA == "data"
    
    def test_task_status_values(self):
        """测试任务状态枚举"""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.SCHEDULED == "scheduled"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.PAUSED == "paused"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"
    
    def test_review_status_values(self):
        """测试审核状态枚举"""
        assert ReviewStatus.PENDING == "pending"
        assert ReviewStatus.APPROVED == "approved"
        assert ReviewStatus.REJECTED == "rejected"
        assert ReviewStatus.MODIFIED == "modified"
    
    def test_step_type_values(self):
        """测试步骤类型枚举"""
        assert StepType.THOUGHT == "thought"
        assert StepType.ACTION == "action"
        assert StepType.OBSERVATION == "observation"
        assert StepType.LLM_CALL == "llm_call"
        assert StepType.DATA_PROCESSING == "data_processing"
        assert StepType.ERROR == "error"
        assert StepType.COMPLETION == "completion"
