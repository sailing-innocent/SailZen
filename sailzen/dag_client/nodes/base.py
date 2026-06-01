# -*- coding: utf-8 -*-
# @file base.py
# @brief DAG 节点执行基类
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""DAG 节点执行抽象基类。

所有自定义节点必须继承 NodeExecutor 并实现 execute 方法。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class NodeContext:
    """节点执行上下文。"""
    run_id: str
    node_id: str
    node_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    upstream_results: Dict[str, Any] = field(default_factory=dict)
    global_params: Dict[str, Any] = field(default_factory=dict)
    store: Any = None  # DAGStore instance
    opencode_client: Any = None  # OpencodeAsyncClient instance
    working_dir: str = ""
    skill_registry: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeResult:
    """节点执行结果。"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    output: Optional[str] = None  # 人类可读输出
    next_nodes: List[str] = field(default_factory=list)  # 动态分支

    @staticmethod
    def ok(data: Any = None, output: str = "", artifacts: List[str] = None) -> "NodeResult":
        return NodeResult(success=True, data=data, output=output, artifacts=artifacts or [])

    @staticmethod
    def fail(error: str, data: Any = None) -> "NodeResult":
        return NodeResult(success=False, error=error, data=data)


class NodeExecutor(ABC):
    """节点执行器基类。"""

    node_type: str = "abstract"

    @abstractmethod
    async def execute(self, ctx: NodeContext) -> NodeResult:
        """执行节点逻辑。

        Args:
            ctx: 节点执行上下文。

        Returns:
            NodeResult
        """
        ...

    async def pre_execute(self, ctx: NodeContext) -> None:
        """可选：执行前钩子。"""
        pass

    async def post_execute(self, ctx: NodeContext, result: NodeResult) -> None:
        """可选：执行后钩子。"""
        pass

    def required_skills(self, params: Dict[str, Any]) -> List[str]:
        """返回此节点需要的 skill 列表（用于前置检查）。"""
        return []

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数合法性，返回错误信息或 None。"""
        return None
