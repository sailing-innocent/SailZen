# -*- coding: utf-8 -*-
# @file base.py
# @brief Base Agent Abstract Class
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# Agent 基类定义
# 所有具体的 Agent 实现都需要继承此类

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime
from enum import Enum
from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.unified_agent import UnifiedAgentTask
from sail_server.application.dto.unified_agent import TaskStatus
from sail_server.utils.llm.gateway import LLMGateway


# ============================================================================
# 数据类型定义
# ============================================================================

@dataclass
class AgentContext:
    """
    Agent 执行上下文
    
    包含 Agent 执行任务所需的所有依赖
    """
    db_session: Session
    """数据库会话"""
    
    llm_gateway: LLMGateway
    """LLM 网关"""
    
    config: Dict[str, Any] = field(default_factory=dict)
    """额外配置参数"""
    
    user_id: Optional[int] = None
    """用户 ID"""
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)


@dataclass
class AgentExecutionResult:
    """
    Agent 执行结果
    """
    success: bool
    """是否成功"""
    
    result_data: Dict[str, Any] = field(default_factory=dict)
    """结果数据"""
    
    error_message: Optional[str] = None
    """错误信息（失败时）"""
    
    error_code: Optional[str] = None
    """错误码"""
    
    execution_time_seconds: float = 0.0
    """执行时间（秒）"""
    
    total_tokens: int = 0
    """总 Token 消耗"""
    
    total_cost: float = 0.0
    """总成本（美元）"""
    
    steps_completed: int = 0
    """完成的步骤数"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """额外元数据"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "execution_time_seconds": self.execution_time_seconds,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
            "steps_completed": self.steps_completed,
            "metadata": self.metadata,
        }


@dataclass
class CostEstimate:
    """
    成本预估
    """
    estimated_tokens: int
    """预估 Token 数"""
    
    estimated_cost: float
    """预估成本（美元）"""
    
    confidence: float = 0.8
    """预估置信度 (0-1)"""
    
    breakdown: Dict[str, Any] = field(default_factory=dict)
    """成本细分"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "estimated_tokens": self.estimated_tokens,
            "estimated_cost": round(self.estimated_cost, 6),
            "confidence": self.confidence,
            "breakdown": self.breakdown,
        }


@dataclass
class ValidationResult:
    """
    任务验证结果
    """
    valid: bool
    """是否有效"""
    
    errors: List[str] = field(default_factory=list)
    """错误信息列表"""
    
    warnings: List[str] = field(default_factory=list)
    """警告信息列表"""
    
    def add_error(self, message: str):
        """添加错误"""
        self.errors.append(message)
        self.valid = False
    
    def add_warning(self, message: str):
        """添加警告"""
        self.warnings.append(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class ProgressUpdate:
    """
    进度更新
    """
    progress: int
    """进度百分比 (0-100)"""
    
    phase: Optional[str] = None
    """当前阶段"""
    
    message: Optional[str] = None
    """进度消息"""
    
    step_number: Optional[int] = None
    """当前步骤号"""
    
    total_steps: Optional[int] = None
    """总步骤数"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """额外元数据"""


# 进度回调函数类型
ProgressCallback = Callable[[ProgressUpdate], None]


@dataclass
class AgentInfo:
    """
    Agent 信息
    """
    agent_type: str
    """Agent 类型标识"""
    
    name: str
    """显示名称"""
    
    description: str
    """描述"""
    
    version: str = "1.0"
    """版本号"""
    
    supported_task_types: List[str] = field(default_factory=list)
    """支持的任务类型列表"""
    
    capabilities: List[str] = field(default_factory=list)
    """能力列表"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_type": self.agent_type,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "supported_task_types": self.supported_task_types,
            "capabilities": self.capabilities,
        }


# ============================================================================
# BaseAgent 抽象类
# ============================================================================

class BaseAgent(ABC):
    """
    Agent 基类
    
    所有具体的 Agent 实现都需要继承此类，并实现抽象方法。
    
    示例：
        class MyAgent(BaseAgent):
            @property
            def agent_type(self) -> str:
                return "my_agent"
            
            async def execute(self, task, context, callback):
                # 实现执行逻辑
                pass
    """
    
    @property
    @abstractmethod
    def agent_type(self) -> str:
        """
        Agent 类型标识
        
        Returns:
            str: 唯一的 Agent 类型标识符
        """
        pass
    
    @property
    def agent_info(self) -> AgentInfo:
        """
        Agent 信息
        
        子类可以重写此方法提供更详细的信息
        
        Returns:
            AgentInfo: Agent 信息
        """
        return AgentInfo(
            agent_type=self.agent_type,
            name=self.agent_type,
            description=f"{self.agent_type} agent",
            supported_task_types=[self.agent_type],
        )
    
    @abstractmethod
    async def execute(
        self,
        task: UnifiedAgentTask,
        context: AgentContext,
        callback: Optional[ProgressCallback] = None
    ) -> AgentExecutionResult:
        """
        执行 Agent 任务
        
        这是 Agent 的核心方法，子类必须实现具体的执行逻辑。
        
        Args:
            task: 统一任务对象
            context: 执行上下文
            callback: 进度回调函数（可选）
        
        Returns:
            AgentExecutionResult: 执行结果
        """
        pass
    
    @abstractmethod
    def estimate_cost(self, task: UnifiedAgentTask) -> CostEstimate:
        """
        预估任务成本
        
        子类需要实现成本预估逻辑，用于预算控制。
        
        Args:
            task: 统一任务对象
        
        Returns:
            CostEstimate: 成本预估
        """
        pass
    
    @abstractmethod
    def validate_task(self, task: UnifiedAgentTask) -> ValidationResult:
        """
        验证任务配置
        
        子类需要实现任务验证逻辑，确保任务配置正确。
        
        Args:
            task: 统一任务对象
        
        Returns:
            ValidationResult: 验证结果
        """
        pass
    
    def pre_execute(self, task: UnifiedAgentTask, context: AgentContext) -> None:
        """
        执行前钩子
        
        子类可以重写此方法在执行前进行准备工作。
        
        Args:
            task: 统一任务对象
            context: 执行上下文
        """
        pass
    
    def post_execute(
        self,
        task: UnifiedAgentTask,
        context: AgentContext,
        result: AgentExecutionResult
    ) -> None:
        """
        执行后钩子
        
        子类可以重写此方法在执行后进行清理工作。
        
        Args:
            task: 统一任务对象
            context: 执行上下文
            result: 执行结果
        """
        pass
    
    def _notify_progress(
        self,
        callback: Optional[ProgressCallback],
        progress: int,
        phase: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs
    ):
        """
        通知进度更新
        
        辅助方法，用于安全地调用进度回调。
        
        Args:
            callback: 进度回调函数
            progress: 进度百分比
            phase: 当前阶段
            message: 进度消息
            **kwargs: 额外元数据
        """
        if callback:
            try:
                update = ProgressUpdate(
                    progress=progress,
                    phase=phase,
                    message=message,
                    metadata=kwargs
                )
                callback(update)
            except Exception as e:
                # 忽略回调错误，避免影响主流程
                import logging
                logging.getLogger(__name__).warning(f"Progress callback error: {e}")
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(type={self.agent_type})>"
