# -*- coding: utf-8 -*-
# @file config.py
# @brief sail.yaml 配置加载与解析
# @author sailing-innocent
# @date 2025-06-02
# @version 3.0
# ---------------------------------
"""SailZen DAG Client 配置系统。

配置源优先级（从高到低）：
  1. 环境变量（SAIL_DAG_*）
  2. sail.yaml 文件
  3. 内置默认值

配置示例见项目根目录 sail.yaml.template。
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_NAME = "sail.yaml"


# ═══════════════════════════════════════════════════════════════════════
#  数据类定义
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class OpencodeConfig:
    """OpenCode 服务器连接配置。"""
    host: str = "127.0.0.1"
    port: int = 4096
    timeout: float = 30.0
    sse_timeout: float = 14400.0


@dataclass
class NodeTypeConfig:
    """节点类型定义。"""
    name: str
    handler: str  # import path, e.g. "sailzen.dag_client.nodes.skill_node.SkillNode"
    default_timeout: int = 3600
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DAGNodeTemplate:
    """DAG 模板中的节点定义。"""
    id: str
    type: str
    name: str = ""
    depends_on: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    timeout: Optional[int] = None
    retries: int = 3
    required_skills: List[str] = field(default_factory=list)


@dataclass
class DAGPipelineTemplate:
    """可复用的 DAG 流水线模板。"""
    id: str
    name: str = ""
    description: str = ""
    nodes: List[DAGNodeTemplate] = field(default_factory=list)
    global_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DAGClientConfig:
    """dag_client 根配置。"""
    name: str = "default"
    db_path: str = "data/dag_client.db"
    data_dir: str = "data/dag"
    log_dir: str = "logs/dag"
    opencode: OpencodeConfig = field(default_factory=OpencodeConfig)
    node_types: List[NodeTypeConfig] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    pipelines: List[DAGPipelineTemplate] = field(default_factory=list)
    api_port: int = 9050
    api_host: str = "0.0.0.0"
    auto_start: bool = True
    max_concurrent_runs: int = 5
    heartbeat_interval: int = 30
    agent_pipelines_dir: Optional[str] = None  # Optional: agent pipeline definitions directory


# ═══════════════════════════════════════════════════════════════════════
#  加载逻辑
# ═══════════════════════════════════════════════════════════════════════


def _env_override(cfg: DAGClientConfig) -> None:
    """用 SAIL_DAG_* 环境变量覆盖配置。"""
    if host := os.environ.get("SAIL_DAG_OPENCODE_HOST"):
        cfg.opencode.host = host
    if port := os.environ.get("SAIL_DAG_OPENCODE_PORT"):
        cfg.opencode.port = int(port)
    if db := os.environ.get("SAIL_DAG_DB_PATH"):
        cfg.db_path = db
    if data := os.environ.get("SAIL_DAG_DATA_DIR"):
        cfg.data_dir = data
    if log := os.environ.get("SAIL_DAG_LOG_DIR"):
        cfg.log_dir = log
    if api_port := os.environ.get("SAIL_DAG_API_PORT"):
        cfg.api_port = int(api_port)
    if api_host := os.environ.get("SAIL_DAG_API_HOST"):
        cfg.api_host = api_host
    if max_runs := os.environ.get("SAIL_DAG_MAX_CONCURRENT"):
        cfg.max_concurrent_runs = int(max_runs)


def _load_opencode(raw: Dict[str, Any]) -> OpencodeConfig:
    return OpencodeConfig(
        host=raw.get("host", "127.0.0.1"),
        port=raw.get("port", 4096),
        timeout=raw.get("timeout", 30.0),
        sse_timeout=raw.get("sse_timeout", 14400.0),
    )


def _load_node_types(raw_list: List[Dict[str, Any]]) -> List[NodeTypeConfig]:
    result = []
    for raw in raw_list:
        result.append(NodeTypeConfig(
            name=raw["name"],
            handler=raw["handler"],
            default_timeout=raw.get("default_timeout", 3600),
            params=raw.get("params", {}),
        ))
    return result


def _load_pipeline_nodes(raw_list: List[Dict[str, Any]]) -> List[DAGNodeTemplate]:
    result = []
    for raw in raw_list:
        result.append(DAGNodeTemplate(
            id=raw["id"],
            type=raw["type"],
            name=raw.get("name", raw["id"]),
            depends_on=raw.get("depends_on", []),
            params=raw.get("params", {}),
            timeout=raw.get("timeout"),
            retries=raw.get("retries", 3),
            required_skills=raw.get("required_skills", []),
        ))
    return result


def _load_pipelines(raw_list: List[Dict[str, Any]]) -> List[DAGPipelineTemplate]:
    result = []
    for raw in raw_list:
        result.append(DAGPipelineTemplate(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            description=raw.get("description", ""),
            nodes=_load_pipeline_nodes(raw.get("nodes", [])),
            global_params=raw.get("global_params", {}),
        ))
    return result


def load_config(path: Optional[str] = None) -> DAGClientConfig:
    """从 sail.yaml 加载 DAG Client 配置。

    Args:
        path: 配置文件路径。默认查找当前目录的 sail.yaml，
              或通过 SAIL_CONFIG 环境变量指定。

    Returns:
        DAGClientConfig 实例
    """
    config_path = Path(path or os.environ.get("SAIL_CONFIG", DEFAULT_CONFIG_NAME))
    if not config_path.is_absolute():
        # 尝试从工作目录向上查找
        cwd = Path.cwd()
        candidates = [cwd / config_path]
        for parent in cwd.parents:
            candidates.append(parent / config_path)
        for c in candidates:
            if c.exists():
                config_path = c
                break

    raw: Dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        logger.info("Loaded config from %s", config_path)
    else:
        logger.warning("Config file not found: %s, using defaults", config_path)

    dag_raw = raw.get("dag_client", {})

    cfg = DAGClientConfig(
        name=dag_raw.get("name", "default"),
        db_path=dag_raw.get("db_path", "data/dag_client.db"),
        data_dir=dag_raw.get("data_dir", "data/dag"),
        log_dir=dag_raw.get("log_dir", "logs/dag"),
        opencode=_load_opencode(dag_raw.get("opencode", {})),
        node_types=_load_node_types(dag_raw.get("node_types", [])),
        required_skills=dag_raw.get("required_skills", []),
        pipelines=_load_pipelines(dag_raw.get("pipelines", [])),
        api_port=dag_raw.get("api_port", 9050),
        api_host=dag_raw.get("api_host", "0.0.0.0"),
        auto_start=dag_raw.get("auto_start", True),
        max_concurrent_runs=dag_raw.get("max_concurrent_runs", 5),
        heartbeat_interval=dag_raw.get("heartbeat_interval", 30),
        agent_pipelines_dir=dag_raw.get("agent_pipelines_dir", None),
    )

    _env_override(cfg)

    # 解析为绝对路径
    config_root = config_path.parent if config_path.exists() else Path.cwd()
    cfg.db_path = str((config_root / cfg.db_path).resolve())
    cfg.data_dir = str((config_root / cfg.data_dir).resolve())
    cfg.log_dir = str((config_root / cfg.log_dir).resolve())
    if cfg.agent_pipelines_dir and not Path(cfg.agent_pipelines_dir).is_absolute():
        cfg.agent_pipelines_dir = str((config_root / cfg.agent_pipelines_dir).resolve())

    return cfg
