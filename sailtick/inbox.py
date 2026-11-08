# -*- coding: utf-8 -*-
# @file inbox.py
# @brief 票据客户端（sail_server /api/v1/tick/*）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""TicketInbox — sail_server 票据表的 httpx 客户端。

票据存于 SailZen 主库（共享数据，网页/手机/插件都经 sail_server 访问），
agent 侧永不等待阻塞：pending 超期自动 fallback（设计文档 §6）。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# 票据类型 → 默认期待回复时长
DEFAULT_REPLY_HOURS = {
    "question": 48,
    "task": 24,
    "approval": 72,
    "info": 0,  # info 无需回复
}


class TicketInbox:
    """主库票据客户端。"""

    def __init__(self, api_base: str, auth_token: str = ""):
        self.api_base = api_base.rstrip("/")
        self.auth_token = auth_token or os.environ.get("SAILZEN_API_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            self._client = httpx.AsyncClient(timeout=15.0, headers=headers)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health(self) -> bool:
        """sail_server 是否可达。"""
        try:
            client = self._get_client()
            # 注意：根路径 /health 是静态站 302；真正的健康端点在 /api/v1/health
            resp = await client.get(f"{self.api_base}/health")
            return resp.status_code == 200
        except Exception as exc:
            logger.warning("sail_server health check failed: %s", exc)
            return False

    # ── 读 ────────────────────────────────────────────────────────────

    async def list_tickets(
        self, status: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        client = self._get_client()
        resp = await client.get(f"{self.api_base}/tick/tickets", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("items", [])

    async def pending_tickets(self) -> List[Dict[str, Any]]:
        return await self.list_tickets(status="pending")

    async def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        client = self._get_client()
        resp = await client.get(f"{self.api_base}/tick/tickets/{ticket_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    # ── 写 ────────────────────────────────────────────────────────────

    async def create_ticket(
        self,
        tick_id: str,
        ticket_type: str,
        title: str,
        body: str,
        priority: str = "normal",
        expected_reply_hours: Optional[int] = None,
        fallback_assumption: str = "",
        channel: str = "web",
    ) -> Dict[str, Any]:
        """创建票据。expected_reply_by 默认按类型宽松设置。"""
        hours = expected_reply_hours
        if hours is None:
            hours = DEFAULT_REPLY_HOURS.get(ticket_type, 48)
        expected_by = (
            (datetime.now() + timedelta(hours=hours)).isoformat() if hours > 0 else None
        )
        payload = {
            "tick_id": tick_id,
            "type": ticket_type,
            "title": title,
            "body": body,
            "priority": priority,
            "channel": channel,
            "expected_reply_by": expected_by,
            "fallback_assumption": fallback_assumption,
        }
        client = self._get_client()
        resp = await client.post(f"{self.api_base}/tick/tickets", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def reply_ticket(self, ticket_id: int, reply: str) -> Dict[str, Any]:
        """用户回复（网页/手机端调用；agent 侧主要用于测试与同步）。"""
        client = self._get_client()
        resp = await client.post(
            f"{self.api_base}/tick/tickets/{ticket_id}/reply", json={"reply": reply}
        )
        resp.raise_for_status()
        return resp.json()

    async def resolve_ticket(self, ticket_id: int, resolution: str = "") -> Dict[str, Any]:
        client = self._get_client()
        resp = await client.post(
            f"{self.api_base}/tick/tickets/{ticket_id}/resolve",
            json={"resolution": resolution},
        )
        resp.raise_for_status()
        return resp.json()

    async def snooze_ticket(self, ticket_id: int, hours: int = 24) -> Dict[str, Any]:
        client = self._get_client()
        resp = await client.post(
            f"{self.api_base}/tick/tickets/{ticket_id}/snooze", json={"hours": hours}
        )
        resp.raise_for_status()
        return resp.json()

    # ── 同步 ──────────────────────────────────────────────────────────

    async def sync_replies_since(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """拉取自某时刻以来被回复/关闭的票据（SCAN 阶段调用）。"""
        params: Dict[str, Any] = {}
        if since:
            params["since"] = since.isoformat()
        client = self._get_client()
        resp = await client.get(f"{self.api_base}/tick/replies", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("items", [])

    async def expire_overdue(self) -> int:
        """将超期 pending 票据置为 expired（服务器端幂等），返回处理数。"""
        client = self._get_client()
        resp = await client.post(f"{self.api_base}/tick/expire-overdue")
        resp.raise_for_status()
        data = resp.json()
        return int(data.get("expired", 0))
