"""
Agent API Router - 处理Agent相关的HTTP请求
"""
from fastapi import APIRouter, HTTPException
from typing import List

from app.models.agent_schemas import (
    AgentRegisterRequest, AgentRegisterResponse,
    HeartbeatRequest, HeartbeatResponse,
    AgentOut, TaskOut, SessionOut,
    TaskCreateRequest, TaskResultRequest,
    SessionCreateRequest, SessionUpdateRequest,
    DashboardStats, AgentWithTasks
)
from app.services.agent_manager import agent_manager

router = APIRouter(prefix="/agents", tags=["agents"])


# ================== Agent Registration & Heartbeat ==================

@router.post("/register", response_model=AgentRegisterResponse)
async def register_agent(request: AgentRegisterRequest):
    """注册Agent"""
    agent = await agent_manager.register_agent(request.model_dump())
    return AgentRegisterResponse(
        agent_id=agent.id,
        heartbeat_interval=30,
        config=agent.config,
        manager_host=None  # 在实际部署中填充
    )


@router.post("/{agent_id}/heartbeat", response_model=HeartbeatResponse)
async def agent_heartbeat(agent_id: str, request: HeartbeatRequest):
    """Agent心跳"""
    result = await agent_manager.heartbeat(agent_id, request.model_dump())
    if not result.get("ack"):
        raise HTTPException(status_code=404, detail=result.get("error", "Agent not found"))
    return HeartbeatResponse(**result)


# ================== Agent Query ==================

@router.get("", response_model=List[AgentOut])
async def list_agents():
    """列出所有Agent"""
    agents = await agent_manager.get_all_agents()
    return [AgentOut(
        id=a.id,
        name=a.name,
        host=a.host,
        port=a.port,
        platform=a.platform.value,
        role=a.role.value,
        capabilities=a.capabilities,
        status=a.status.value,
        current_task_id=a.current_task_id,
        opencode_port=a.opencode_port,
        working_dir=a.working_dir,
        heartbeat_at=a.heartbeat_at,
        registered_at=a.registered_at
    ) for a in agents]


@router.get("/online", response_model=List[AgentOut])
async def list_online_agents():
    """列出在线Agent"""
    agents = await agent_manager.get_online_agents()
    return [AgentOut(
        id=a.id,
        name=a.name,
        host=a.host,
        port=a.port,
        platform=a.platform.value,
        role=a.role.value,
        capabilities=a.capabilities,
        status=a.status.value,
        current_task_id=a.current_task_id,
        opencode_port=a.opencode_port,
        working_dir=a.working_dir,
        heartbeat_at=a.heartbeat_at,
        registered_at=a.registered_at
    ) for a in agents]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str):
    """获取单个Agent"""
    agent = await agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentOut(
        id=agent.id,
        name=agent.name,
        host=agent.host,
        port=agent.port,
        platform=agent.platform.value,
        role=agent.role.value,
        capabilities=agent.capabilities,
        status=agent.status.value,
        current_task_id=agent.current_task_id,
        opencode_port=agent.opencode_port,
        working_dir=agent.working_dir,
        heartbeat_at=agent.heartbeat_at,
        registered_at=agent.registered_at
    )


@router.get("/{agent_id}/detail", response_model=AgentWithTasks)
async def get_agent_detail(agent_id: str):
    """获取Agent详情（含任务和会话）"""
    agent = await agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    sessions = await agent_manager.get_agent_sessions(agent_id)
    tasks = await agent_manager.get_all_tasks(20)
    agent_tasks = [t for t in tasks if t.agent_id == agent_id]
    
    current_task = None
    if agent.current_task_id:
        current_task = await agent_manager.get_task(agent.current_task_id)
    
    return AgentWithTasks(
        agent=AgentOut(
            id=agent.id,
            name=agent.name,
            host=agent.host,
            port=agent.port,
            platform=agent.platform.value,
            role=agent.role.value,
            capabilities=agent.capabilities,
            status=agent.status.value,
            current_task_id=agent.current_task_id,
            opencode_port=agent.opencode_port,
            working_dir=agent.working_dir,
            heartbeat_at=agent.heartbeat_at,
            registered_at=agent.registered_at
        ),
        current_task=TaskOut(
            id=current_task.id,
            agent_id=current_task.agent_id,
            task_type=current_task.task_type.value,
            status=current_task.status,
            priority=current_task.priority,
            payload=current_task.payload,
            result=current_task.result,
            error=current_task.error,
            retry_count=current_task.retry_count,
            created_at=current_task.created_at,
            started_at=current_task.started_at,
            completed_at=current_task.completed_at
        ) if current_task else None,
        recent_tasks=[TaskOut(
            id=t.id,
            agent_id=t.agent_id,
            task_type=t.task_type.value,
            status=t.status,
            priority=t.priority,
            payload=t.payload,
            result=t.result,
            error=t.error,
            retry_count=t.retry_count,
            created_at=t.created_at,
            started_at=t.started_at,
            completed_at=t.completed_at
        ) for t in agent_tasks[:10]],
        active_sessions=[SessionOut(
            id=s.id,
            agent_id=s.agent_id,
            task_id=s.task_id,
            session_key=s.session_key,
            skill=s.skill,
            working_dir=s.working_dir,
            status=s.status.value,
            context=s.context,
            result=s.result,
            logs=s.logs,
            started_at=s.started_at,
            completed_at=s.completed_at,
            last_activity_at=s.last_activity_at
        ) for s in sessions if s.status.value in ("starting", "running")]
    )


# ================== Task Management ==================

@router.post("/tasks", response_model=TaskOut)
async def create_task(request: TaskCreateRequest):
    """创建任务"""
    task = await agent_manager.create_task(request.model_dump())
    return TaskOut(
        id=task.id,
        agent_id=task.agent_id or "",
        task_type=task.task_type.value,
        status=task.status,
        priority=task.priority,
        payload=task.payload,
        result=task.result,
        error=task.error,
        retry_count=task.retry_count,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at
    )


@router.get("/tasks", response_model=List[TaskOut])
async def list_tasks(limit: int = 50):
    """列出所有任务"""
    tasks = await agent_manager.get_all_tasks(limit)
    return [TaskOut(
        id=t.id,
        agent_id=t.agent_id or "",
        task_type=t.task_type.value,
        status=t.status,
        priority=t.priority,
        payload=t.payload,
        result=t.result,
        error=t.error,
        retry_count=t.retry_count,
        created_at=t.created_at,
        started_at=t.started_at,
        completed_at=t.completed_at
    ) for t in tasks]


@router.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task(task_id: str):
    """获取任务详情"""
    task = await agent_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskOut(
        id=task.id,
        agent_id=task.agent_id or "",
        task_type=task.task_type.value,
        status=task.status,
        priority=task.priority,
        payload=task.payload,
        result=task.result,
        error=task.error,
        retry_count=task.retry_count,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at
    )


@router.post("/tasks/{task_id}/result")
async def report_task_result(task_id: str, request: TaskResultRequest):
    """上报任务结果"""
    await agent_manager.report_task_result(
        task_id,
        request.success,
        request.result,
        request.error,
        request.logs
    )
    return {"success": True}


# ================== Session Management ==================

@router.post("/sessions", response_model=SessionOut)
async def create_session(request: SessionCreateRequest):
    """创建OpenCode会话"""
    session = await agent_manager.create_session(request.model_dump())
    return SessionOut(
        id=session.id,
        agent_id=session.agent_id,
        task_id=session.task_id,
        session_key=session.session_key,
        skill=session.skill,
        working_dir=session.working_dir,
        status=session.status.value,
        context=session.context,
        result=session.result,
        logs=session.logs,
        started_at=session.started_at,
        completed_at=session.completed_at,
        last_activity_at=session.last_activity_at
    )


@router.get("/sessions", response_model=List[SessionOut])
async def list_active_sessions():
    """列出活跃会话"""
    sessions = await agent_manager.get_active_sessions()
    return [SessionOut(
        id=s.id,
        agent_id=s.agent_id,
        task_id=s.task_id,
        session_key=s.session_key,
        skill=s.skill,
        working_dir=s.working_dir,
        status=s.status.value,
        context=s.context,
        result=s.result,
        logs=s.logs,
        started_at=s.started_at,
        completed_at=s.completed_at,
        last_activity_at=s.last_activity_at
    ) for s in sessions]


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(session_id: str):
    """获取会话详情"""
    session = await agent_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionOut(
        id=session.id,
        agent_id=session.agent_id,
        task_id=session.task_id,
        session_key=session.session_key,
        skill=session.skill,
        working_dir=session.working_dir,
        status=session.status.value,
        context=session.context,
        result=session.result,
        logs=session.logs,
        started_at=session.started_at,
        completed_at=session.completed_at,
        last_activity_at=session.last_activity_at
    )


# ================== Dashboard ==================

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """获取Dashboard统计数据"""
    stats = await agent_manager.get_stats()
    return DashboardStats(**stats)


# ================== Skills ==================

@router.get("/skills")
async def list_skills():
    """列出可用的Skills"""
    from app.services.mock_skills import SkillRegistry
    return SkillRegistry.list_skills()
