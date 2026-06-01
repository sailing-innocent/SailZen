# -*- coding: utf-8 -*-
# @file sse.py
# @brief SSE broadcaster for the dummy server.
# @author sailing-innocent
# @date 2026-05-31
# @version 1.0
# ---------------------------------

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Broadcast SSE events to all connected clients.

    The global ``/event`` endpoint in opencode pushes events for *all*
    sessions.  We keep a list of queues; each queue corresponds to one
    connected HTTP response stream.
    """

    def __init__(self) -> None:
        self._queues: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def subscribe(self, maxsize: int = 1000) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        async with self._lock:
            self._queues.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            if q in self._queues:
                self._queues.remove(q)

    async def broadcast(self, data: Dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, default=str)
        dead: List[asyncio.Queue] = []
        async with self._lock:
            queues = list(self._queues)
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except Exception:
                    dead.append(q)
            except Exception:
                dead.append(q)
        if dead:
            async with self._lock:
                for q in dead:
                    if q in self._queues:
                        self._queues.remove(q)

    def broadcast_sync(self, data: Dict[str, Any]) -> None:
        """Synchronous wrapper — safe to call from non-async contexts
        (e.g. inside a thread-pooled LLM callback) when an event loop
        is already running."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(data))
        except RuntimeError:
            pass
