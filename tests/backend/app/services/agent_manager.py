"""
Agent Manager Service - 管理Agent注册、心跳、任务分发
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.agent_models import (
    Agent, AgentTask, OpenCodeSession,
    AgentStatus, AgentRole, Platform, TaskType, SessionStatus
)
from app.services.mock_skills import SkillRegistry, SkillResult


class AgentManager:
    """Agent管理器 - 单例模式"""
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._active_sessions: Dict[str, asyncio.Task] = {}
        self._heartbeat_checker_task: Optional[asyncio.Task] = None
        self._task_dispatcher_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动后台任务"""
        if self._heartbeat_checker_task is None:
            self._heartbeat_checker_task = asyncio.create_task(self._heartbeat_check_loop())
        if self._task_dispatcher_task is None:
            self._task_dispatcher_task = asyncio.create_task(self._task_dispatch_loop())
    
    async def stop(self):
        """停止后台任务"""
        if self._heartbeat_checker_task:
            self._heartbeat_checker_task.cancel()
            self._heartbeat_checker_task = None
        if self._task_dispatcher_task:
            self._task_dispatcher_task.cancel()
            self._task_dispatcher_task = None
    
    # ================== Agent Registration ==================
    
    async def register_agent(self, data: dict) -> Agent:
        """注册Agent"""
        async with AsyncSessionLocal() as db:
            # 检查是否已存在
            result = await db.execute(select(Agent).where(Agent.id == data["id"]))
            existing = result.scalar_one_or_none()
            
            if existing:
                # 更新现有Agent
                for key, value in data.items():
                    if hasattr(existing, key) and key != "id":
                        setattr(existing, key, value)
                existing.status = AgentStatus.online
                existing.heartbeat_at = datetime.utcnow()
                await db.commit()
                await db.refresh(existing)
                return existing
            
            # 创建新Agent
            agent = Agent(
                id=data["id"],
                name=data["name"],
                host=data["host"],
                port=data.get("port", 8080),
                platform=Platform(data["platform"]),
                role=AgentRole(data.get("role", "worker")),
                capabilities=data.get("capabilities", []),
                status=AgentStatus.online,
                opencode_port=data.get("opencode_port"),
                working_dir=data.get("working_dir"),
                config=data.get("config", {}),
                heartbeat_at=datetime.utcnow()
            )
            db.add(agent)
            await db.commit()
            await db.refresh(agent)
            return agent
    
    async def heartbeat(self, agent_id: str, data: dict) -> dict:
        """处理心跳"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            
            if not agent:
                return {"ack": False, "error": "Agent not found"}
            
            # 更新心跳
            agent.heartbeat_at = datetime.utcnow()
            agent.status = AgentStatus(data.get("status", "online"))
            agent.current_task_id = data.get("current_task_id")
            await db.commit()
            
            # 获取待分配任务
            pending_tasks = await self._get_pending_tasks_for_agent(db, agent_id)
            
            return {
                "ack": True,
                "pending_tasks": [
                    {
                        "id": t.id,
                        "task_type": t.task_type.value,
                        "priority": t.priority,
                        "payload": t.payload
                    }
                    for t in pending_tasks
                ],
                "commands": []
            }
    
    async def _get_pending_tasks_for_agent(self, db: AsyncSession, agent_id: str) -> List[AgentTask]:
        """获取分配给Agent的待处理任务"""
        result = await db.execute(
            select(AgentTask).where(
                AgentTask.agent_id == agent_id,
                AgentTask.status == "assigned"
            ).order_by(AgentTask.priority, AgentTask.created_at)
        )
        return list(result.scalars().all())
    
    # ================== Agent Query ==================
    
    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取单个Agent"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Agent).where(Agent.id == agent_id))
            return result.scalar_one_or_none()
    
    async def get_all_agents(self) -> List[Agent]:
        """获取所有Agent"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Agent).order_by(Agent.registered_at.desc()))
            return list(result.scalars().all())
    
    async def get_online_agents(self) -> List[Agent]:
        """获取在线Agent"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Agent).where(Agent.status == AgentStatus.online)
            )
            return list(result.scalars().all())
    
    async def get_agents_by_capability(self, capability: str) -> List[Agent]:
        """根据能力获取Agent"""
        all_agents = await self.get_online_agents()
        return [a for a in all_agents if capability in a.capabilities]
    
    # ================== Task Management ==================
    
    async def create_task(self, data: dict) -> AgentTask:
        """创建任务"""
        task_id = str(uuid.uuid4())[:8]
        
        async with AsyncSessionLocal() as db:
            # 如果未指定agent_id，自动分配
            agent_id = data.get("agent_id")
            if not agent_id:
                agent_id = await self._auto_assign_agent(db, data["task_type"])
            
            task = AgentTask(
                id=task_id,
                agent_id=agent_id,
                task_type=TaskType(data["task_type"]),
                status="pending" if not agent_id else "assigned",
                priority=data.get("priority", 100),
                payload=data.get("payload", {})
            )
            db.add(task)
            await db.commit()
            await db.refresh(task)
            return task
    
    async def _auto_assign_agent(self, db: AsyncSession, task_type: str) -> Optional[str]:
        """自动分配Agent"""
        # 任务类型到能力的映射
        capability_map = {
            "globalbatch": "globalbatch",
            "build_win": "build_win",
            "build_ios": "build_ios",
            "review": "review",
            "git_commit": "git",
            "notify": "notify"
        }
        
        required_cap = capability_map.get(task_type, task_type)
        
        # 获取具有该能力的在线Agent
        result = await db.execute(
            select(Agent).where(
                Agent.status == AgentStatus.online
            )
        )
        agents = list(result.scalars().all())
        
        # 过滤具有所需能力的Agent
        capable_agents = [a for a in agents if required_cap in a.capabilities]
        
        if not capable_agents:
            return None
        
        # 选择负载最低的Agent
        capable_agents.sort(key=lambda a: a.current_task_id is not None)
        return capable_agents[0].id
    
    async def get_task(self, task_id: str) -> Optional[AgentTask]:
        """获取任务"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
            return result.scalar_one_or_none()
    
    async def get_all_tasks(self, limit: int = 50) -> List[AgentTask]:
        """获取所有任务"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentTask).order_by(AgentTask.created_at.desc()).limit(limit)
            )
            return list(result.scalars().all())
    
    async def update_task_status(self, task_id: str, status: str, result: dict = None, error: str = None):
        """更新任务状态"""
        async with AsyncSessionLocal() as db:
            task_result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
            task = task_result.scalar_one_or_none()
            
            if not task:
                return
            
            task.status = status
            if status == "running":
                task.started_at = datetime.utcnow()
            elif status in ("success", "failed"):
                task.completed_at = datetime.utcnow()
                task.result = result
                task.error = error
            
            await db.commit()
    
    async def report_task_result(self, task_id: str, success: bool, result: dict, error: str = None, logs: List[str] = None):
        """上报任务结果"""
        status = "success" if success else "failed"
        result_data = {
            "success": success,
            "data": result,
            "logs": logs or []
        }
        await self.update_task_status(task_id, status, result_data, error)
        
        # 更新Agent状态
        async with AsyncSessionLocal() as db:
            task_result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
            task = task_result.scalar_one_or_none()
            if task and task.agent_id:
                agent_result = await db.execute(select(Agent).where(Agent.id == task.agent_id))
                agent = agent_result.scalar_one_or_none()
                if agent and agent.current_task_id == task_id:
                    agent.current_task_id = None
                    agent.status = AgentStatus.online
                    await db.commit()
    
    # ================== Session Management ==================
    
    async def create_session(self, data: dict) -> OpenCodeSession:
        """创建OpenCode会话"""
        session_id = str(uuid.uuid4())[:8]
        session_key = f"session_{session_id}_{datetime.now().strftime('%H%M%S')}"
        
        async with AsyncSessionLocal() as db:
            session = OpenCodeSession(
                id=session_id,
                agent_id=data["agent_id"],
                task_id=data["task_id"],
                session_key=session_key,
                skill=data["skill"],
                working_dir=data["working_dir"],
                status=SessionStatus.starting,
                context=data.get("context", {}),
                logs=[]
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            
            # 启动会话执行
            task = asyncio.create_task(self._execute_session(session_id))
            self._active_sessions[session_id] = task
            
            return session
    
    async def _execute_session(self, session_id: str):
        """执行会话（使用Mock Skill）"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(OpenCodeSession).where(OpenCodeSession.id == session_id))
            session = result.scalar_one_or_none()
            
            if not session:
                return
            
            # 更新状态为运行中
            session.status = SessionStatus.running
            await db.commit()
            
            # 获取Skill
            skill = SkillRegistry.get(session.skill)
            if not skill:
                session.status = SessionStatus.failed
                session.result = {"error": f"Skill not found: {session.skill}"}
                session.completed_at = datetime.utcnow()
                await db.commit()
                return
            
            # 更新Task状态
            await self.update_task_status(session.task_id, "running")
            
            # 执行Skill
            async def on_progress(progress_data: dict):
                async with AsyncSessionLocal() as progress_db:
                    res = await progress_db.execute(
                        select(OpenCodeSession).where(OpenCodeSession.id == session_id)
                    )
                    s = res.scalar_one_or_none()
                    if s:
                        s.logs = s.logs + [progress_data.get("log", "")]
                        s.last_activity_at = datetime.utcnow()
                        await progress_db.commit()
            
            try:
                skill_result: SkillResult = await skill.execute(
                    context={
                        **session.context,
                        "working_dir": session.working_dir
                    },
                    on_progress=on_progress
                )
                
                # 更新会话结果
                async with AsyncSessionLocal() as final_db:
                    res = await final_db.execute(
                        select(OpenCodeSession).where(OpenCodeSession.id == session_id)
                    )
                    final_session = res.scalar_one_or_none()
                    if final_session:
                        final_session.status = SessionStatus.completed if skill_result.success else SessionStatus.failed
                        final_session.result = {
                            "success": skill_result.success,
                            "data": skill_result.data,
                            "error": skill_result.error
                        }
                        final_session.logs = skill_result.logs
                        final_session.completed_at = datetime.utcnow()
                        await final_db.commit()
                
                # 上报任务结果
                await self.report_task_result(
                    session.task_id,
                    skill_result.success,
                    skill_result.data,
                    skill_result.error,
                    skill_result.logs
                )
                
            except Exception as e:
                async with AsyncSessionLocal() as err_db:
                    res = await err_db.execute(
                        select(OpenCodeSession).where(OpenCodeSession.id == session_id)
                    )
                    err_session = res.scalar_one_or_none()
                    if err_session:
                        err_session.status = SessionStatus.failed
                        err_session.result = {"error": str(e)}
                        err_session.completed_at = datetime.utcnow()
                        await err_db.commit()
                
                await self.report_task_result(session.task_id, False, {}, str(e))
            
            finally:
                self._active_sessions.pop(session_id, None)
    
    async def get_session(self, session_id: str) -> Optional[OpenCodeSession]:
        """获取会话"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(OpenCodeSession).where(OpenCodeSession.id == session_id))
            return result.scalar_one_or_none()
    
    async def get_agent_sessions(self, agent_id: str) -> List[OpenCodeSession]:
        """获取Agent的所有会话"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(OpenCodeSession).where(
                    OpenCodeSession.agent_id == agent_id
                ).order_by(OpenCodeSession.started_at.desc())
            )
            return list(result.scalars().all())
    
    async def get_active_sessions(self) -> List[OpenCodeSession]:
        """获取所有活跃会话"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(OpenCodeSession).where(
                    OpenCodeSession.status.in_([SessionStatus.starting, SessionStatus.running])
                )
            )
            return list(result.scalars().all())
    
    # ================== Background Tasks ==================
    
    async def _heartbeat_check_loop(self):
        """心跳检测循环"""
        while True:
            try:
                await asyncio.sleep(30)
                await self._check_agent_heartbeats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Heartbeat check error: {e}")
    
    async def _check_agent_heartbeats(self):
        """检查Agent心跳"""
        threshold = datetime.utcnow() - timedelta(seconds=90)
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Agent).where(
                    Agent.status == AgentStatus.online,
                    Agent.heartbeat_at < threshold
                )
            )
            stale_agents = result.scalars().all()
            
            for agent in stale_agents:
                agent.status = AgentStatus.offline
            
            await db.commit()
    
    async def _task_dispatch_loop(self):
        """任务分发循环"""
        while True:
            try:
                await asyncio.sleep(5)
                await self._dispatch_pending_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Task dispatch error: {e}")
    
    async def _dispatch_pending_tasks(self):
        """分发待处理任务"""
        async with AsyncSessionLocal() as db:
            # 获取未分配的任务
            result = await db.execute(
                select(AgentTask).where(
                    AgentTask.status == "pending",
                    AgentTask.agent_id == None
                ).order_by(AgentTask.priority, AgentTask.created_at).limit(10)
            )
            pending_tasks = result.scalars().all()
            
            for task in pending_tasks:
                agent_id = await self._auto_assign_agent(db, task.task_type.value)
                if agent_id:
                    task.agent_id = agent_id
                    task.status = "assigned"
            
            await db.commit()
    
    # ================== Dashboard Stats ==================
    
    async def get_stats(self) -> dict:
        """获取统计数据"""
        async with AsyncSessionLocal() as db:
            # Agent统计
            agents_result = await db.execute(select(Agent))
            agents = list(agents_result.scalars().all())
            
            # Task统计
            tasks_result = await db.execute(select(AgentTask))
            tasks = list(tasks_result.scalars().all())
            
            return {
                "total_agents": len(agents),
                "online_agents": len([a for a in agents if a.status == AgentStatus.online]),
                "busy_agents": len([a for a in agents if a.status == AgentStatus.busy]),
                "total_tasks": len(tasks),
                "pending_tasks": len([t for t in tasks if t.status == "pending"]),
                "running_tasks": len([t for t in tasks if t.status == "running"]),
                "completed_tasks": len([t for t in tasks if t.status == "success"]),
                "failed_tasks": len([t for t in tasks if t.status == "failed"]),
            }


# 全局实例
agent_manager = AgentManager()
