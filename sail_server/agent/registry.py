# -*- coding: utf-8 -*-
# @file registry.py
# @brief Agent Registry
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# Agent 注册表
# 管理所有可用的 Agent 实例

import logging
from typing import Dict, Type, Optional, List
from threading import Lock

from .base import BaseAgent, AgentInfo

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Agent 注册表

    管理所有 Agent 类的注册和获取。
    使用单例模式确保全局唯一。

    示例：
        # 注册 Agent
        registry = AgentRegistry()
        registry.register(MyAgent)

        # 获取 Agent
        agent = registry.get_agent("my_agent")

        # 列出所有 Agent
        agents = registry.list_agents()
    """

    _instance: Optional["AgentRegistry"] = None
    _lock: Lock = Lock()

    def __new__(cls) -> "AgentRegistry":
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化注册表"""
        # 避免重复初始化
        if getattr(self, "_initialized", False):
            return

        self._agents: Dict[str, Type[BaseAgent]] = {}
        """Agent 类型 -> Agent 类的映射"""

        self._task_type_mapping: Dict[str, str] = {}
        """任务类型 -> Agent 类型的映射"""

        self._initialized = True

    def register(self, agent_class: Type[BaseAgent], override: bool = False) -> bool:
        """
        注册 Agent 类

        Args:
            agent_class: Agent 类（必须是 BaseAgent 的子类）
            override: 是否覆盖已存在的注册

        Returns:
            bool: 是否注册成功

        Raises:
            TypeError: 如果 agent_class 不是 BaseAgent 的子类
            ValueError: 如果 Agent 类型已存在且 override=False
        """
        # 验证类型
        if not issubclass(agent_class, BaseAgent):
            raise TypeError(
                f"Agent class must inherit from BaseAgent, got {agent_class}"
            )

        # 获取 Agent 类型
        # 创建一个临时实例来获取 agent_type
        try:
            temp_instance = agent_class.__new__(agent_class)
            agent_type = (
                agent_class.agent_type.fget(temp_instance)
                if hasattr(agent_class.agent_type, "fget")
                else None
            )  # type: ignore

            # 如果无法从 property 获取，尝试直接实例化
            if agent_type is None:
                temp_instance = agent_class()
                agent_type = temp_instance.agent_type
        except Exception as e:
            logger.error(f"Failed to get agent_type from {agent_class}: {e}")
            raise ValueError(f"Cannot determine agent_type for {agent_class}")

        # 检查是否已存在
        if agent_type in self._agents and not override:
            raise ValueError(
                f"Agent type '{agent_type}' is already registered. Use override=True to replace."
            )

        # 注册
        self._agents[agent_type] = agent_class

        # 更新任务类型映射
        try:
            temp_instance = agent_class()
            agent_info = temp_instance.agent_info
            for task_type in agent_info.supported_task_types:
                self._task_type_mapping[task_type] = agent_type
        except Exception as e:
            logger.warning(
                f"Failed to get supported_task_types from {agent_class}: {e}"
            )

        logger.info(f"Registered agent: {agent_type} ({agent_class.__name__})")
        return True

    def unregister(self, agent_type: str) -> bool:
        """
        注销 Agent

        Args:
            agent_type: Agent 类型标识

        Returns:
            bool: 是否成功注销
        """
        if agent_type not in self._agents:
            return False

        del self._agents[agent_type]

        # 清理任务类型映射
        self._task_type_mapping = {
            k: v for k, v in self._task_type_mapping.items() if v != agent_type
        }

        logger.info(f"Unregistered agent: {agent_type}")
        return True

    def get_agent(self, agent_type: str) -> Optional[BaseAgent]:
        """
        获取 Agent 实例

        Args:
            agent_type: Agent 类型标识

        Returns:
            Optional[BaseAgent]: Agent 实例，如果不存在则返回 None
        """
        agent_class = self._agents.get(agent_type)
        if agent_class is None:
            return None

        try:
            return agent_class()
        except Exception as e:
            logger.error(f"Failed to instantiate agent {agent_type}: {e}")
            return None

    def get_agent_for_task(self, task_type: str) -> Optional[BaseAgent]:
        """
        根据任务类型获取 Agent 实例

        Args:
            task_type: 任务类型

        Returns:
            Optional[BaseAgent]: Agent 实例，如果不存在则返回 None
        """
        agent_type = self._task_type_mapping.get(task_type)
        if agent_type is None:
            # 尝试直接使用任务类型作为 Agent 类型
            return self.get_agent(task_type)

        return self.get_agent(agent_type)

    def list_agents(self) -> List[AgentInfo]:
        """
        列出所有注册的 Agent 信息

        Returns:
            List[AgentInfo]: Agent 信息列表
        """
        result = []
        for agent_type, agent_class in self._agents.items():
            try:
                agent = agent_class()
                result.append(agent.agent_info)
            except Exception as e:
                logger.warning(f"Failed to get info for agent {agent_type}: {e}")

        return result

    def list_agent_types(self) -> List[str]:
        """
        列出所有注册的 Agent 类型

        Returns:
            List[str]: Agent 类型列表
        """
        return list(self._agents.keys())

    def is_registered(self, agent_type: str) -> bool:
        """
        检查 Agent 类型是否已注册

        Args:
            agent_type: Agent 类型标识

        Returns:
            bool: 是否已注册
        """
        return agent_type in self._agents

    def clear(self):
        """清空所有注册"""
        self._agents.clear()
        self._task_type_mapping.clear()
        logger.info("Cleared all agent registrations")

    def get_stats(self) -> Dict[str, int]:
        """
        获取注册表统计

        Returns:
            Dict[str, int]: 统计信息
        """
        return {
            "total_agents": len(self._agents),
            "task_type_mappings": len(self._task_type_mapping),
        }


# ============================================================================
# 便捷函数
# ============================================================================

_registry_instance: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """
    获取全局 Agent 注册表实例

    Returns:
        AgentRegistry: Agent 注册表实例
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentRegistry()
    return _registry_instance


def set_agent_registry(registry: AgentRegistry):
    """
    设置全局 Agent 注册表实例

    Args:
        registry: Agent 注册表实例
    """
    global _registry_instance
    _registry_instance = registry


def register_agent(agent_class: Type[BaseAgent], override: bool = False) -> bool:
    """
    便捷函数：注册 Agent

    Args:
        agent_class: Agent 类
        override: 是否覆盖已存在的注册

    Returns:
        bool: 是否注册成功
    """
    return get_agent_registry().register(agent_class, override)


def get_agent(agent_type: str) -> Optional[BaseAgent]:
    """
    便捷函数：获取 Agent 实例

    Args:
        agent_type: Agent 类型标识

    Returns:
        Optional[BaseAgent]: Agent 实例
    """
    return get_agent_registry().get_agent(agent_type)


def auto_register_agents():
    """
    自动注册所有可用的 Agent

    扫描并注册项目中定义的所有 Agent 类。
    """
    registry = get_agent_registry()

    # 这里可以添加自动发现逻辑
    # 目前手动注册已知的 Agent

    try:
        from .novel_analysis import NovelAnalysisAgent

        registry.register(NovelAnalysisAgent)
    except ImportError as e:
        logger.warning(f"Failed to register NovelAnalysisAgent: {e}")

    try:
        from .general import GeneralAgent

        registry.register(GeneralAgent)
    except ImportError as e:
        logger.warning(f"Failed to register GeneralAgent: {e}")

    logger.info(f"Auto-registered {registry.get_stats()['total_agents']} agents")
