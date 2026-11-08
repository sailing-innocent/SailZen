# -*- coding: utf-8 -*-
# @file memory.py
# @brief SailTick 四层记忆（profile/episodic/semantic/procedural）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""AgentMemory — 四层记忆管理。

从旧 autonomous_agent/memory.py 三层迁移，扩展:
  - profile 层独立成 st_profile 表（confidence + source 三态）
  - episodic 层独立成 st_episodes 表（Tick 事件流）
  - semantic/procedural 存 st_memories（带 TTL）

设计文档: sailtick.md §5
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sailtick.db import TickDatabase

logger = logging.getLogger(__name__)


class AgentMemory:
    """四层记忆管理器。"""

    def __init__(self, db: TickDatabase):
        self.db = db

    # ── profile 层（用户画像） ────────────────────────────────────────

    async def set_profile(
        self, key: str, value: Any, confidence: float = 0.8, source: str = "asked"
    ) -> dict:
        return await self.db.set_profile(key, value, confidence, source)

    async def get_profile(self, key: str) -> Optional[Any]:
        row = await self.db.get_profile(key)
        return row["value"] if row else None

    async def get_profile_full(self, key: str) -> Optional[dict]:
        return await self.db.get_profile(key)

    async def list_profile(self) -> List[dict]:
        return await self.db.list_profile()

    # ── episodic 层（Tick 事件流） ────────────────────────────────────

    async def save_episode(self, tick_id: Optional[str], kind: str, content: Any) -> dict:
        return await self.db.create_episode(tick_id, kind, content)

    async def list_episodes(self, tick_id: Optional[str] = None, limit: int = 100) -> List[dict]:
        return await self.db.list_episodes(tick_id=tick_id, limit=limit)

    # ── semantic / procedural 层 ──────────────────────────────────────

    async def save(self, memory_type: str, key: str, value: Any, ttl_days: Optional[int] = None) -> dict:
        expires = (
            (datetime.now() + timedelta(days=ttl_days)).isoformat() if ttl_days else None
        )
        return await self.db.create_memory(
            memory_type=memory_type,
            key=key,
            value=value,
            ttl_seconds=ttl_days * 86400 if ttl_days else None,
            expires_at=expires,
        )

    async def get(self, memory_type: str, key: str) -> Optional[Any]:
        row = await self.db.get_memory(memory_type, key)
        return row["value"] if row else None

    async def list(self, memory_type: str, key_prefix: Optional[str] = None) -> List[dict]:
        return await self.db.list_memories(memory_type=memory_type, key_prefix=key_prefix)

    async def update(self, memory_type: str, key: str, value: Any) -> dict:
        existing = await self.db.get_memory(memory_type, key)
        if existing:
            await self.db.delete_memory(existing["id"])
        return await self.save(memory_type, key, value)

    # ── 汇总 ──────────────────────────────────────────────────────────

    async def summary_for_prompt(self) -> Dict[str, Any]:
        """供上下文组装使用的记忆摘要（设计文档 §4 token 预算 ~2k）。"""
        profile = await self.list_profile()
        profile_lines = [
            f"- {p['key']} = {p['value']} (confidence={p['confidence']}, source={p['source']})"
            for p in profile
        ]
        semantic = await self.list("semantic")
        semantic_lines = [f"- {m['key']}: {m['value']}" for m in semantic[:20]]
        procedural = await self.list("procedural")
        proc_lines = [f"- {m['key']}: {m['value']}" for m in procedural[:10]]

        return {
            "profile": "\n".join(profile_lines) if profile_lines else "(空)",
            "semantic": "\n".join(semantic_lines) if semantic_lines else "(空)",
            "procedural": "\n".join(proc_lines) if proc_lines else "(空)",
        }

    async def cleanup_expired(self) -> int:
        count = await self.db.cleanup_expired_memories()
        if count > 0:
            logger.info("Cleaned up %d expired memories", count)
        return count
