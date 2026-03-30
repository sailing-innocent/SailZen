# -*- coding: utf-8 -*-
# @file config.py
# @brief Feishu Bot Agent Configuration
# @author sailing-innocent
# @date 2026-03-29
# @version 1.0
# ---------------------------------
"""Configuration management for Feishu Bot Agent.

This module handles all configuration loading, validation, and defaults.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def _load_dotenv():
    """Load environment variables from .env files."""
    env_files = [".env", ".env.local", ".env.dev", ".env.production"]
    for filename in env_files:
        env_path = Path(filename)
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip().strip("'\"")
                            # Only set if not already in environment
                            if key not in os.environ:
                                os.environ[key] = value
            except Exception:
                pass


# Load environment on module import
_load_dotenv()


@dataclass
class AgentConfig:
    """All agent configuration settings."""

    # Feishu credentials
    app_id: str = ""
    app_secret: str = ""

    # Server settings
    base_port: int = 4096
    max_sessions: int = 3
    callback_timeout: int = 300
    auto_restart: bool = True

    # Configuration file path
    config_path: Optional[Path] = None

    # Projects configuration
    projects: List[Dict[str, Any]] = field(default_factory=list)

    # LLM configuration
    llm_provider: str = "moonshot"
    llm_api_key: Optional[str] = None

    @classmethod
    def from_yaml(cls, path: Path) -> "AgentConfig":
        """Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Loaded AgentConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError("Config file must contain a YAML object")

        # Extract values with defaults
        feishu = data.get("feishu", {})
        server = data.get("server", {})
        llm = data.get("llm", {})

        return cls(
            app_id=feishu.get("app_id", ""),
            app_secret=feishu.get("app_secret", ""),
            base_port=server.get("base_port", 4096),
            max_sessions=server.get("max_sessions", 3),
            callback_timeout=server.get("callback_timeout", 300),
            auto_restart=server.get("auto_restart", True),
            config_path=path,
            projects=data.get("projects", []),
            llm_provider=llm.get("provider", "moonshot"),
            llm_api_key=llm.get("api_key"),
        )

    def validate(self) -> bool:
        """Validate configuration.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.app_id or not self.app_secret:
            raise ValueError(
                "Feishu app_id and app_secret are required. "
                "Set them in config file or environment variables."
            )

        if self.base_port < 1024 or self.base_port > 65535:
            raise ValueError(f"Invalid base_port: {self.base_port}")

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feishu": {
                "app_id": self.app_id,
                "app_secret": self.app_secret,
            },
            "server": {
                "base_port": self.base_port,
                "max_sessions": self.max_sessions,
                "callback_timeout": self.callback_timeout,
                "auto_restart": self.auto_restart,
            },
            "projects": self.projects,
            "llm": {
                "provider": self.llm_provider,
                "api_key": self.llm_api_key,
            },
        }


def load_config(path: Optional[Path] = None) -> AgentConfig:
    """Load configuration from file or environment.

    Args:
        path: Path to config file (optional, will search if not provided)

    Returns:
        Loaded AgentConfig
    """
    if path is None:
        # Search for config file
        search_paths = [
            Path("bot/opencode.bot.yaml"),
            Path("opencode.bot.yaml"),
            Path.home() / ".config/feishu-agent/config.yaml",
        ]
        for p in search_paths:
            if p.exists():
                path = p
                break

    if path and path.exists():
        config = AgentConfig.from_yaml(path)
    else:
        # Create from environment
        config = AgentConfig(
            app_id=os.getenv("FEISHU_APP_ID", ""),
            app_secret=os.getenv("FEISHU_APP_SECRET", ""),
            llm_api_key=os.getenv("MOONSHOT_API_KEY") or os.getenv("OPENAI_API_KEY"),
        )

    # Validate
    config.validate()
    return config


def create_default_config(path: Path) -> None:
    """Create a default configuration file.

    Args:
        path: Path where to create the config file
    """
    default_config = """# Feishu Bot Agent Configuration
# Documentation: https://github.com/your-repo/feishu-agent

# Feishu App Credentials
# Get these from: https://open.feishu.cn/app
feishu:
  app_id: "cli_xxxxxxxxxxxxxxxx"  # Your Feishu app ID
  app_secret: "xxxxxxxxxxxxxxxx"   # Your Feishu app secret

# Server Configuration
server:
  base_port: 4096        # Starting port for OpenCode sessions
  max_sessions: 3        # Maximum concurrent sessions
  callback_timeout: 300  # Task timeout in seconds
  auto_restart: true     # Auto-restart crashed sessions

# LLM Configuration (for intent understanding)
llm:
  provider: "moonshot"   # LLM provider
  api_key: null          # API key (or set MOONSHOT_API_KEY env var)

# Project Workspaces
# Each project is a workspace OpenCode can work in
projects:
  - slug: "myproject"
    path: "/path/to/project"
    description: "My project description"
    # Optional: custom server settings per project
    # server:
    #   port: 5000
"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(default_config)

    print(f"Created default config at: {path}")
    print("Please edit it with your Feishu credentials and project paths.")
