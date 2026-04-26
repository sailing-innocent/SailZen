# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import logging
import yaml
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_VALID_LLM_PROVIDERS = frozenset(
    ["moonshot", "openai", "google", "deepseek", "anthropic"]
)


@dataclass
class AgentConfig:
    app_id: str = ""
    app_secret: str = ""
    base_port: int = 4096
    max_sessions: int = 10
    callback_timeout: int = 300
    auto_restart: bool = False
    config_path: Optional[str] = None
    projects: List[Dict[str, str]] = field(default_factory=list)
    admin_chat_id: Optional[str] = None
    default_chat_id: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    cli_tool: str = "opencode-cli"

    def validate(self) -> List[str]:
        """Return list of validation warnings (empty = all good)."""
        warnings = []
        if not self.app_id:
            warnings.append("app_id is empty - Feishu connection will fail")
        if not self.app_secret:
            warnings.append("app_secret is empty - Feishu connection will fail")
        if not (1024 <= self.base_port <= 65535):
            warnings.append(f"base_port {self.base_port} out of range [1024, 65535]")
        if self.max_sessions < 1 or self.max_sessions > 50:
            warnings.append(f"max_sessions {self.max_sessions} out of range [1, 50]")
        if self.llm_provider and self.llm_provider not in _VALID_LLM_PROVIDERS:
            warnings.append(
                f"Unknown llm_provider: {self.llm_provider} (valid: {', '.join(_VALID_LLM_PROVIDERS)})"
            )
        for p in self.projects:
            path = p.get("path", "")
            if path:
                try:
                    resolved = Path(path).expanduser()
                    if not resolved.exists():
                        warnings.append(f"Project path does not exist: {path}")
                except Exception:
                    warnings.append(f"Invalid project path: {path}")
        return warnings


def load_config(config_path: str) -> AgentConfig:
    config = AgentConfig(config_path=config_path)
    p = Path(config_path)
    if not p.exists():
        return config
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        config.app_id = data.get("app_id", "")
        config.app_secret = data.get("app_secret", "")
        config.base_port = data.get("base_port", 4096)
        config.max_sessions = data.get("max_sessions", 10)
        config.callback_timeout = data.get("callback_timeout", 300)
        config.auto_restart = data.get("auto_restart", False)
        raw_projects = data.get("projects", [])
        config.projects = [
            {
                "slug": p.get("slug", ""),
                "path": p.get("path", ""),
                "label": p.get("label", ""),
            }
            for p in raw_projects
            if p.get("path")
        ]
        config.llm_provider = data.get("llm_provider") or None
        config.llm_api_key = data.get("llm_api_key") or None
        config.admin_chat_id = data.get("admin_chat_id") or None
        config.default_chat_id = data.get("default_chat_id") or None
        config.cli_tool = data.get("cli_tool", "opencode-cli")

        warnings = config.validate()
        for w in warnings:
            logger.warning("Config: %s", w)

    except Exception as exc:
        logger.error("Failed to load config %s: %s", config_path, exc)
    return config


def create_default_config(config_path: str) -> None:
    p = Path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    content = """\
# Feishu Agent Bridge Configuration
# Usage: uv run bot/feishu_agent.py -c bot/opencode.bot.yaml

# Feishu App Credentials (Required)
# Get from: https://open.feishu.cn/app
app_id: ""
app_secret: ""

# Optional: Named project shortcuts
# Use slug in Feishu: '启动 sailzen'
projects:
  - slug: "sailzen"
    path: "~/repos/SailZen"
    label: "SailZen"

# CLI tool for agent runtime (must support `serve` subcommand with opencode-compatible API)
# Examples: opencode-cli, kimix
cli_tool: "opencode-cli"

# Session settings
base_port: 4096     # Starting port for agent serve instances
max_sessions: 10
callback_timeout: 300
auto_restart: false

# Optional: LLM settings for intent understanding
# If not set, falls back to environment variables (MOONSHOT_API_KEY, etc.)
# Supported providers: moonshot, openai, google, deepseek, anthropic
# llm_provider: "moonshot"
# llm_api_key: "your-api-key-here"

# Optional: Admin notification settings
# admin_chat_id: "oc_xxxxxxxxxxxxxxxx"  # 管理员的chat_id，用于接收启动/关闭通知
# 可以通过在飞书中 @机器人 并查看消息的 chat_id 获取
# 或者先跟机器人单聊，然后查看收到的消息的 chat_id

# Optional: Default chat for proactive messages
# default_chat_id: "oc_xxxxxxxxxxxxxxxx"  # 默认chat_id，用于机器人主动发送消息（如长期任务通知）
# 不设置时，主动发送功能将不可用
"""
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created config: {config_path}")
    print("Please edit and add your Feishu credentials.")
