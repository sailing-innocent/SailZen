# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import yaml
import sys
from pathlib import Path


@dataclass
class AgentConfig:
    """All agent settings."""

    app_id: str = ""
    app_secret: str = ""
    base_port: int = 4096
    max_sessions: int = 10
    callback_timeout: int = 300
    auto_restart: bool = False
    config_path: Optional[str] = None
    # Named project shortcuts
    projects: List[Dict[str, str]] = field(default_factory=list)
    # Admin notification settings
    admin_chat_id: Optional[str] = None  # 管理员chat_id，用于接收启动/关闭通知


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


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
        # LLM settings (optional, fallback to environment variables)
        config.llm_provider = data.get("llm_provider") or None
        config.llm_api_key = data.get("llm_api_key") or None
        # Admin notification settings
        config.admin_chat_id = data.get("admin_chat_id") or None
    except Exception as exc:
        print(f"Warning: Failed to load config: {exc}")
    return config


def create_default_config(config_path: str) -> None:
    p = Path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    content = """\
# Feishu OpenCode Bridge Configuration
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

# Session settings
base_port: 4096     # Starting port for opencode serve instances
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
"""
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created config: {config_path}")
    print("Please edit and add your Feishu credentials.")
