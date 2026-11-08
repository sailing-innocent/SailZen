# -*- coding: utf-8 -*-
# @file config.py
# @brief Agent runtime configuration loader
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""Agent configuration system.

Configuration sources (highest to lowest priority):
  1. Environment variables (AGENT_*)
  2. agent.yaml file
  3. Built-in defaults
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_NAME = "agent.yaml"


# ═══════════════════════════════════════════════════════════════════════
#  Data classes
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class LLMProviderConfig:
    """LLM provider configuration."""
    api_key: str = ""
    model: str = ""
    base_url: str = ""


@dataclass
class LLMConfig:
    """LLM gateway configuration."""
    providers: Dict[str, LLMProviderConfig] = field(default_factory=dict)
    default_reasoning: str = "kimi"
    default_generation: str = "deepseek"


@dataclass
class SailServerConfig:
    """sail_server HTTP API configuration."""
    api_base: str = "http://localhost:1974/api/v1"
    auth_token: str = ""


@dataclass
class OpencodeConfig:
    """OpenCode server configuration."""
    host: str = "127.0.0.1"
    port: int = 4096


@dataclass
class NotificationConfig:
    """Notification channel configuration."""
    default_channel: str = "lark_im"
    lark_user_open_id: str = ""
    quiet_hours_start: int = 23
    quiet_hours_end: int = 8


@dataclass
class AutonomyConfig:
    """Autonomy level configuration."""
    default_level: str = "fully_autonomous"  # fully_autonomous | suggestion | alert_and_wait
    approval_required_for: List[str] = field(default_factory=list)


@dataclass
class AgentConfig:
    """Autonomous Agent root configuration."""
    name: str = "sailzen-autonomous-agent"
    data_dir: str = "data/agent"
    db_path: str = "data/agent/db/agent.db"
    log_dir: str = "logs/agent"

    # Daemon settings
    heartbeat_interval: int = 30
    max_concurrent_pipelines: int = 3

    # Scheduler settings
    timezone: str = "Asia/Shanghai"
    job_store: str = "sqlalchemy"

    # Sub-configs
    llm: LLMConfig = field(default_factory=LLMConfig)
    sail_server: SailServerConfig = field(default_factory=SailServerConfig)
    opencode: OpencodeConfig = field(default_factory=OpencodeConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    autonomy: AutonomyConfig = field(default_factory=AutonomyConfig)

    # Pipeline definitions
    pipelines_dir: str = "sailzen/autonomous_agent/pipelines"
    api_port: int = 9060
    api_host: str = "0.0.0.0"


# ═══════════════════════════════════════════════════════════════════════
#  Load logic
# ═══════════════════════════════════════════════════════════════════════


def _env_override(cfg: AgentConfig) -> None:
    """Apply AGENT_* environment variable overrides."""
    if db_path := os.environ.get("AGENT_DB_PATH"):
        cfg.db_path = db_path
    if data_dir := os.environ.get("AGENT_DATA_DIR"):
        cfg.data_dir = data_dir
    if api_port := os.environ.get("AGENT_API_PORT"):
        cfg.api_port = int(api_port)
    if api_host := os.environ.get("AGENT_API_HOST"):
        cfg.api_host = api_host
    if tz := os.environ.get("AGENT_TIMEZONE"):
        cfg.timezone = tz

    # LLM provider keys
    kimi_key = os.environ.get("KIMI_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if kimi_key:
        if "kimi" not in cfg.llm.providers:
            cfg.llm.providers["kimi"] = LLMProviderConfig()
        cfg.llm.providers["kimi"].api_key = kimi_key
    if deepseek_key:
        if "deepseek" not in cfg.llm.providers:
            cfg.llm.providers["deepseek"] = LLMProviderConfig()
        cfg.llm.providers["deepseek"].api_key = deepseek_key

    # Notifications
    if lark_user := os.environ.get("LARK_USER_OPEN_ID"):
        cfg.notifications.lark_user_open_id = lark_user


def _load_llm_providers(raw: Dict[str, Any]) -> Dict[str, LLMProviderConfig]:
    result = {}
    for name, prov in raw.items():
        result[name] = LLMProviderConfig(
            api_key=_resolve_env_vars(prov.get("api_key", "")),
            model=prov.get("model", ""),
            base_url=prov.get("base_url", ""),
        )
    return result


def _resolve_env_vars(value: str) -> str:
    """Resolve ${VAR} or $VAR in config strings."""
    if not isinstance(value, str):
        return value
    import re

    def replacer(match):
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, "")

    # Match ${VAR} or $VAR
    return re.sub(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)', replacer, value)


def load_agent_config(path: Optional[str] = None) -> AgentConfig:
    """Load agent configuration from agent.yaml.

    Args:
        path: Config file path. Defaults to agent.yaml in cwd or project root.

    Returns:
        AgentConfig instance
    """
    config_path = Path(path or os.environ.get("AGENT_CONFIG", DEFAULT_CONFIG_NAME))
    if not config_path.is_absolute():
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
        logger.info("Loaded agent config from %s", config_path)
    else:
        logger.warning("Agent config file not found: %s, using defaults", config_path)

    agent_raw = raw.get("agent", {})

    llm_raw = agent_raw.get("llm", {})
    llm_cfg = LLMConfig(
        providers=_load_llm_providers(llm_raw.get("providers", {})),
        default_reasoning=llm_raw.get("default_reasoning", "kimi"),
        default_generation=llm_raw.get("default_generation", "deepseek"),
    )

    sail_raw = agent_raw.get("sail_server", {})
    sail_cfg = SailServerConfig(
        api_base=sail_raw.get("api_base", "http://localhost:1974/api/v1"),
        auth_token=_resolve_env_vars(sail_raw.get("auth_token", "")),
    )

    opencode_raw = agent_raw.get("opencode", {})
    opencode_cfg = OpencodeConfig(
        host=opencode_raw.get("host", "127.0.0.1"),
        port=opencode_raw.get("port", 4096),
    )

    notify_raw = agent_raw.get("notifications", {})
    notify_cfg = NotificationConfig(
        default_channel=notify_raw.get("default_channel", "lark_im"),
        lark_user_open_id=_resolve_env_vars(notify_raw.get("lark", {}).get("user_open_id", "")),
        quiet_hours_start=notify_raw.get("quiet_hours_start", 23),
        quiet_hours_end=notify_raw.get("quiet_hours_end", 8),
    )

    autonomy_raw = agent_raw.get("autonomy", {})
    autonomy_cfg = AutonomyConfig(
        default_level=autonomy_raw.get("default_level", "fully_autonomous"),
        approval_required_for=autonomy_raw.get("approval_required_for", []),
    )

    cfg = AgentConfig(
        name=agent_raw.get("name", "sailzen-autonomous-agent"),
        data_dir=agent_raw.get("data_dir", "data/agent"),
        db_path=agent_raw.get("db_path", "data/agent/db/agent.db"),
        log_dir=agent_raw.get("log_dir", "logs/agent"),
        heartbeat_interval=agent_raw.get("daemon", {}).get("heartbeat_interval", 30),
        max_concurrent_pipelines=agent_raw.get("daemon", {}).get("max_concurrent_pipelines", 3),
        timezone=agent_raw.get("scheduler", {}).get("timezone", "Asia/Shanghai"),
        job_store=agent_raw.get("scheduler", {}).get("job_store", "sqlalchemy"),
        llm=llm_cfg,
        sail_server=sail_cfg,
        opencode=opencode_cfg,
        notifications=notify_cfg,
        autonomy=autonomy_cfg,
        pipelines_dir=agent_raw.get("pipelines_dir", "sailzen/autonomous_agent/pipelines"),
        api_port=agent_raw.get("api_port", 9060),
        api_host=agent_raw.get("api_host", "0.0.0.0"),
    )

    _env_override(cfg)

    # Resolve to absolute paths
    config_root = config_path.parent if config_path.exists() else Path.cwd()
    cfg.db_path = str((config_root / cfg.db_path).resolve())
    cfg.data_dir = str((config_root / cfg.data_dir).resolve())
    cfg.log_dir = str((config_root / cfg.log_dir).resolve())
    if not Path(cfg.pipelines_dir).is_absolute():
        cfg.pipelines_dir = str((config_root / cfg.pipelines_dir).resolve())

    return cfg
