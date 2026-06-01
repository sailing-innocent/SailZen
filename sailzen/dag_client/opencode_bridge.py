# -*- coding: utf-8 -*-
# @file opencode_bridge.py
# @brief OpenCode 协议桥接
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""SailZen DAG Client OpenCode 协议桥接层。

提供:
  - 与 OpenCode 服务器的连接管理
  - Skill 可用性检查
  - 会话生命周期管理
  - 健康检查
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sail.opencode.client import OpencodeAsyncClient

logger = logging.getLogger(__name__)


class OpenCodeBridge:
    """OpenCode 服务器桥接。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 4096, timeout: float = 30.0):
        self.host = host
        self.port = port
        self._client = OpencodeAsyncClient(
            host=host, port=port, timeout=timeout, name="dag_client"
        )

    @property
    def client(self) -> OpencodeAsyncClient:
        return self._client

    async def health_check(self) -> bool:
        """检查 OpenCode 服务器健康状态。"""
        try:
            return await self._client.health_check()
        except Exception as exc:
            logger.warning("OpenCode health check failed: %s", exc)
            return False

    async def list_available_skills(self) -> List[str]:
        """获取 OpenCode 服务器上可用的 skill 列表。"""
        try:
            agents = await self._client.list_agents()
            skills = set()
            for agent in agents:
                agent_skills = agent.get("skills", [])
                if isinstance(agent_skills, list):
                    skills.update(agent_skills)
            return sorted(skills)
        except Exception as exc:
            logger.warning("Failed to list skills: %s", exc)
            return []

    async def check_skills(self, required: List[str]) -> Dict[str, bool]:
        """检查必需 skills 是否可用。"""
        available = await self.list_available_skills()
        return {skill: skill in available for skill in required}

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> "OpenCodeBridge":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        await self.close()
        return False
