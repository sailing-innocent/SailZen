# -*- coding: utf-8 -*-
# @file session_fallbacks.py
# @brief Fallback helpers for codemaker sessions.
# @author sailing-innocent
# @date 2026-05-31
# @version 1.0
# ---------------------------------

from __future__ import annotations

import asyncio
import logging
import time
from typing import Set

from sail.opencode.client import OpencodeAsyncClient

logger = logging.getLogger(__name__)


async def snapshot_message_ids(
    client: OpencodeAsyncClient,
    session_id: str,
    limit: int = 50,
) -> Set[str]:
    """Return IDs already present before the prompt is sent."""
    try:
        existing = await client.get_messages(session_id, limit=limit)
        return {m.id for m in existing if m.id}
    except Exception as exc:
        logger.debug("snapshot_message_ids failed: %s", exc)
        return set()


async def fetch_final_message(
    client: OpencodeAsyncClient,
    session_id: str,
    pre_existing_ids: Set[str],
    retries: int = 2,
) -> str:
    """Fetch latest assistant text created after the initial snapshot."""
    for attempt in range(retries):
        if attempt > 0:
            await asyncio.sleep(2.0)
        try:
            messages = await client.get_messages(session_id, limit=20)
            for msg in reversed(messages):
                if msg.id in pre_existing_ids:
                    continue
                if msg.role == "assistant" and msg.text_content.strip():
                    return msg.text_content.strip()
        except Exception as exc:
            logger.warning("fetch_final_message error: %s", exc)
    return "（任务完成，无文字输出）"


async def poll_until_idle(
    client: OpencodeAsyncClient,
    session_id: str,
    pre_existing_ids: Set[str],
    timeout: float,
    started_at: float,
    poll_interval: float = 10.0,
) -> str:
    """Poll session status until idle, then fetch final message."""
    idle_count = 0
    while time.time() - started_at < timeout:
        try:
            statuses = await client.get_session_status()
            status = statuses.get(session_id, {})
            if isinstance(status, dict) and status.get("type") == "idle":
                idle_count += 1
            else:
                idle_count = 0
            if idle_count >= 2:
                return await fetch_final_message(
                    client, session_id, pre_existing_ids
                )
        except Exception as exc:
            logger.debug("poll_until_idle status check failed: %s", exc)
        await asyncio.sleep(poll_interval)
    return "（任务超时，无法获取结果）"
