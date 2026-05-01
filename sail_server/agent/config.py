# -*- coding: utf-8 -*-
# @file config.py
# @brief Agent configuration
# @author sailing-innocent
# @date 2026-08-24
# @version 1.0
# ---------------------------------

import os
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

import yaml


@dataclass
class VaultConfig:
    name: str
    url: str
    local_path: str
    branch: str = "main"
    sync_interval_minutes: int = 30
    engine_port_file: Optional[str] = None


@dataclass
class AnalysisConfig:
    enabled: bool = True
    scan_interval_minutes: int = 60
    orphan_detection: bool = True
    daily_gap_detection: bool = True
    todo_extraction: bool = True
    broken_link_detection: bool = True
    schema_drift_detection: bool = False


@dataclass
class PatchConfig:
    enabled: bool = True
    cron: str = "0 23 * * *"
    output_dir: str = "./patches"
    auto_generate_topic: bool = True


@dataclass
class AdminAPIConfig:
    host: str = "127.0.0.1"
    port: int = 1975
    auth_token: Optional[str] = None


@dataclass
class AgentConfig:
    name: str = "shadow-agent"
    data_dir: str = "./data/agent"
    log_level: str = "INFO"
    admin_api: AdminAPIConfig = field(default_factory=AdminAPIConfig)
    vaults: List[VaultConfig] = field(default_factory=list)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    patch: PatchConfig = field(default_factory=PatchConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "AgentConfig":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        agent = raw.get("agent", {})

        vaults = [VaultConfig(**v) for v in agent.get("vaults", [])]
        analysis = AnalysisConfig(**agent.get("analysis", {}))
        patch = PatchConfig(**agent.get("patch", {}))
        api = AdminAPIConfig(**agent.get("admin_api", {}))

        # Inject env vars
        if api.auth_token and api.auth_token.startswith("${"):
            env_key = api.auth_token.strip("${}")
            api.auth_token = os.environ.get(env_key)

        return cls(
            name=agent.get("name", "shadow-agent"),
            data_dir=agent.get("data_dir", "./data/agent"),
            log_level=agent.get("log_level", "INFO"),
            admin_api=api,
            vaults=vaults,
            analysis=analysis,
            patch=patch,
        )
