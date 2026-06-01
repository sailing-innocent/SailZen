# -*- coding: utf-8 -*-
# @file registry.py
# @brief 节点类型注册表
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""节点类型注册表 — 支持内置节点和动态加载自定义节点。

Usage::

    from sailzen.dag_client.nodes.registry import NodeRegistry
    from sailzen.dag_client.nodes.base import NodeExecutor

    registry = NodeRegistry()
    registry.register("my_node", MyNodeExecutor)

    executor = registry.create("my_node")
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable, Dict, List, Optional, Type

from sailzen.dag_client.nodes.base import NodeExecutor

logger = logging.getLogger(__name__)


class NodeRegistry:
    """节点执行器注册表。"""

    def __init__(self):
        self._registry: Dict[str, Type[NodeExecutor]] = {}
        self._register_builtin()

    def _register_builtin(self) -> None:
        """注册所有内置节点类型。"""
        # 延迟导入避免循环依赖
        try:
            from sailzen.dag_client.nodes.skill_node import SkillNode
            self.register("skill", SkillNode)
        except Exception as exc:
            logger.warning("Failed to register skill node: %s", exc)

        try:
            from sailzen.dag_client.nodes.shell_node import ShellNode
            self.register("shell", ShellNode)
        except Exception as exc:
            logger.warning("Failed to register shell node: %s", exc)

        try:
            from sailzen.dag_client.nodes.python_node import PythonNode
            self.register("python", PythonNode)
        except Exception as exc:
            logger.warning("Failed to register python node: %s", exc)

    def register(self, node_type: str, executor_cls: Type[NodeExecutor]) -> None:
        """注册节点类型。"""
        if not issubclass(executor_cls, NodeExecutor):
            raise TypeError(f"Executor must inherit NodeExecutor, got {executor_cls}")
        self._registry[node_type] = executor_cls
        logger.info("Registered node type: %s -> %s", node_type, executor_cls.__name__)

    def unregister(self, node_type: str) -> None:
        """注销节点类型。"""
        self._registry.pop(node_type, None)

    def create(self, node_type: str) -> NodeExecutor:
        """创建节点执行器实例。"""
        cls = self._registry.get(node_type)
        if not cls:
            raise ValueError(f"Unknown node type: {node_type}. "
                             f"Registered: {list(self._registry.keys())}")
        return cls()

    def list_types(self) -> List[str]:
        """列出所有已注册节点类型。"""
        return sorted(self._registry.keys())

    def load_from_config(self, configs: List[Any]) -> None:
        """从配置动态加载节点类型。

        Config item::

            {"name": "custom", "handler": "my_module.MyNodeClass"}
        """
        for cfg in configs:
            name = cfg.name if hasattr(cfg, "name") else cfg["name"]
            handler = cfg.handler if hasattr(cfg, "handler") else cfg["handler"]
            try:
                cls = self._import_class(handler)
                self.register(name, cls)
            except Exception as exc:
                logger.error("Failed to load node type %s from %s: %s", name, handler, exc)

    @staticmethod
    def _import_class(import_path: str) -> Type[NodeExecutor]:
        """从模块路径导入类。"""
        module_path, _, class_name = import_path.rpartition(".")
        if not module_path:
            raise ValueError(f"Invalid import path: {import_path}")
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        if not issubclass(cls, NodeExecutor):
            raise TypeError(f"{import_path} is not a NodeExecutor subclass")
        return cls
