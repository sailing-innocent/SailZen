# -*- coding: utf-8 -*-
# @file __init__.py
# @brief SailZen Autonomous Agent System
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""SailZen Autonomous Agent System.

A sovereign runtime that consumes sail_server via HTTP API only.
Built as a layer ON TOP OF sailzen.dag_client, not inside sail_server.

Core principles:
  1. Zero Main-DB Touch: The agent never opens a session to sail_server.db.
  2. Sovereign SQLite: agent.db lives in data/agent/db/ and is excluded from sync.
  3. Skill-First Execution: Complex workflows are executed via OpenCode Skills.
  4. Direct LLM for Reasoning: Independent LLMGateway for agent decisions.
  5. Cron-Native: Scheduling is a first-class citizen.
"""

from __future__ import annotations

__version__ = "1.0.0"

from sailzen.autonomous_agent.config import AgentConfig, load_agent_config
from sailzen.autonomous_agent.db import AgentDatabase
from sailzen.autonomous_agent.store import AgentStore
from sailzen.autonomous_agent.daemon import AgentDaemon

__all__ = [
    "AgentConfig",
    "load_agent_config",
    "AgentDatabase",
    "AgentStore",
    "AgentDaemon",
]
