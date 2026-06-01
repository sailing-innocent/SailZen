# -*- coding: utf-8 -*-
# @file __init__.py
# @brief SailZen DAG Client
# @author sailing-innocent
# @date 2025-06-02
# @version 3.0
# ---------------------------------
"""SailZen DAG Client — 通用有向无环图驱动智能体框架。

核心特性:
  - 配置驱动：通过 sail.yaml 定义 DAG 结构、节点类型、依赖关系
  - 自定义节点：内置 skill/shell/python 节点，支持动态扩展
  - 独立存储：SQLite 数据库 + 独立文件系统，可备份/恢复/迁移
  - SSE 实时流：支持运行状态实时推送
  - OpenCode 原生集成：与 opencode 协议服务器直接交互
  - 与 sail_server 完全解耦：可独立运行

快速开始::

    # 1. 创建 sail.yaml 配置
    # 2. 启动服务
    python -m sailzen.dag_client
    # 3. 访问 http://localhost:9050/api/v1/dag/health
"""

__version__ = "3.0.0"

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult
from sailzen.dag_client.nodes.registry import NodeRegistry
from sailzen.dag_client.config import load_config, DAGClientConfig

__all__ = [
    "NodeContext", "NodeExecutor", "NodeResult", "NodeRegistry",
    "load_config", "DAGClientConfig",
]
