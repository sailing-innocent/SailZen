# -*- coding: utf-8 -*-
# @file memory.py
# @brief AgentMemory — short-term + long-term memory manager
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""AgentMemory — tiered memory system.

Tiers:
  - short_term: Last 24h execution logs, recent reminders. TTL = 7 days.
  - long_term: User preferences, learned patterns. Permanent.
  - context: Current session state, active goals. In-memory + periodic checkpoint.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sailzen.autonomous_agent.db import AgentDatabase

logger = logging.getLogger(__name__)


class AgentMemory:
    """Tiered memory manager for the autonomous agent."""

    def __init__(self, db: AgentDatabase):
        self.db = db
        self._in_memory_context: Dict[str, Any] = {}

    # ── Short-term memory ─────────────────────────────────────────────

    async def save_short_term(self, key: str, value: Any, ttl_days: int = 7) -> dict:
        """Save short-term memory with TTL."""
        expires = (datetime.now() + timedelta(days=ttl_days)).isoformat()
        data = {
            "memory_type": "short_term",
            "key": key,
            "value": json.dumps(value, ensure_ascii=False, default=str),
            "ttl_seconds": ttl_days * 86400,
            "expires_at": expires,
        }
        return await self.db.create_memory(data)

    async def get_short_term(self, key: str) -> Optional[Any]:
        """Retrieve short-term memory by key."""
        row = await self.db.get_memory("short_term", key)
        if not row:
            return None
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]

    async def list_short_term(self, key_prefix: Optional[str] = None) -> List[dict]:
        """List all short-term memories."""
        return await self.db.list_memories(memory_type="short_term", key_prefix=key_prefix)

    # ── Long-term memory ──────────────────────────────────────────────

    async def save_long_term(self, key: str, value: Any) -> dict:
        """Save permanent long-term memory."""
        data = {
            "memory_type": "long_term",
            "key": key,
            "value": json.dumps(value, ensure_ascii=False, default=str),
            "ttl_seconds": None,
            "expires_at": None,
        }
        return await self.db.create_memory(data)

    async def get_long_term(self, key: str) -> Optional[Any]:
        """Retrieve long-term memory by key."""
        row = await self.db.get_memory("long_term", key)
        if not row:
            return None
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]

    async def update_long_term(self, key: str, value: Any) -> dict:
        """Update or create long-term memory."""
        existing = await self.db.get_memory("long_term", key)
        if existing:
            await self.db.delete_memory(existing["id"])
        return await self.save_long_term(key, value)

    # ── Context memory (in-memory + checkpoint) ───────────────────────

    def set_context(self, key: str, value: Any) -> None:
        """Set in-memory context."""
        self._in_memory_context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get in-memory context."""
        return self._in_memory_context.get(key, default)

    def clear_context(self) -> None:
        """Clear all in-memory context."""
        self._in_memory_context.clear()

    async def checkpoint_context(self, label: str = "auto") -> dict:
        """Save current in-memory context to database."""
        data = {
            "memory_type": "context",
            "key": f"checkpoint_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "value": json.dumps(self._in_memory_context, ensure_ascii=False, default=str),
            "ttl_seconds": 30 * 86400,  # 30 days
            "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
        }
        return await self.db.create_memory(data)

    async def restore_context(self, checkpoint_key: str) -> bool:
        """Restore in-memory context from a checkpoint."""
        row = await self.db.get_memory("context", checkpoint_key)
        if not row:
            return False
        try:
            self._in_memory_context = json.loads(row["value"])
            return True
        except (json.JSONDecodeError, TypeError):
            return False

    # ── Maintenance ───────────────────────────────────────────────────

    async def cleanup_expired(self) -> int:
        """Remove expired short-term and context memories."""
        count = await self.db.cleanup_expired_memories()
        if count > 0:
            logger.info("Cleaned up %d expired memories", count)
        return count

    async def get_working_summary(self) -> dict:
        """Get a summary of current working memory for LLM context."""
        short_term = await self.list_short_term()
        long_term_recent = await self.db.list_memories(memory_type="long_term")
        long_term_recent = long_term_recent[:10]  # Last 10

        return {
            "active_context": self._in_memory_context,
            "recent_short_term_count": len(short_term),
            "recent_long_term_keys": [m["key"] for m in long_term_recent],
        }
