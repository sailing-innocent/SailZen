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
from typing import Any, Callable, Dict, List, Optional

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

    def __init__(
        self,
        api_base: str,
        auth_token: str = "",
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.api_base = api_base.rstrip("/")
        self.auth_token = auth_token or os.environ.get("SAILZEN_API_TOKEN", "")
        self._clock = clock
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"X-SailZen-Client": "sailtick"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            is_local = "127.0.0.1" in self.api_base or "localhost" in self.api_base
            self._client = httpx.AsyncClient(
                timeout=15.0, headers=headers, trust_env=not is_local
            )
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
        channel: str = "mobile",
        push: str = "auto",
        topic: str = "",
        meta: Optional[Dict[str, Any]] = None,
        domain: str = "",
        persona: str = "",
        target_clients: Optional[List[str]] = None,
        deep_link: str = "",
    ) -> Dict[str, Any]:
        """创建票据。expected_reply_by 默认按类型宽松设置；显式传递 domain/persona/target_clients/push/topic/meta。"""
        hours = expected_reply_hours
        if hours is None:
            hours = DEFAULT_REPLY_HOURS.get(ticket_type, 48)
        expected_by = (
            (self._clock() + timedelta(hours=hours)).isoformat() if hours > 0 else None
        )
        payload: Dict[str, Any] = {
            "tick_id": tick_id,
            "type": ticket_type,
            "domain": domain or "",
            "persona": persona or "",
            "target_clients": list(target_clients) if target_clients is not None else [],
            "deep_link": deep_link or "",
            "topic": topic or "",
            "title": title,
            "body": body,
            "meta": meta or {},
            "priority": priority,
            "channel": channel,
            "push": push,
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

    # ── 用户主动消息 / 睡前日报 / AI 动态体重计划写回 ─────────────────────

    async def list_user_messages(
        self,
        status: str = "unread",
        direction: str = "user_to_agent",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        client = self._get_client()
        resp = await client.get(
            f"{self.api_base}/tick/messages",
            params={"status": status, "direction": direction, "limit": limit},
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("items", [])

    async def ingest_user_messages(self, message_ids: List[int], tick_id: str) -> int:
        if not message_ids:
            return 0
        client = self._get_client()
        resp = await client.post(
            f"{self.api_base}/tick/messages/ingest",
            json={"message_ids": message_ids, "tick_id": tick_id},
        )
        if resp.status_code == 404:
            return 0
        resp.raise_for_status()
        return int(resp.json().get("ingested", 0))

    async def upsert_daily_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        client = self._get_client()
        resp = await client.post(f"{self.api_base}/tick/reports", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def sync_ai_weight_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        client = self._get_client()
        resp = await client.post(f"{self.api_base}/health/weight/plan/ai-sync", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def create_diet_log(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        client = self._get_client()
        resp = await client.post(f"{self.api_base}/health/diet", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def create_weight_log(self, weight_kg: float, note: str = "") -> Dict[str, Any]:
        """快速写入体重记录（body-data metric=weight）。"""
        client = self._get_client()
        payload: Dict[str, Any] = {"data": {"weight": round(float(weight_kg), 2)}}
        if note:
            payload["description"] = note
        resp = await client.post(f"{self.api_base}/health/body-data", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def create_user_message(
        self,
        content: str,
        category: str = "daily_info",
        meta: Optional[Dict[str, Any]] = None,
        source_channel: str = "qq",
        auto_log_diet: bool = False,
    ) -> Dict[str, Any]:
        """将快反对话中捕获的计划微调/日常信息写入 SailTickMessage 供慢脑吸收。"""
        client = self._get_client()
        payload = {
            "direction": "user_to_agent",
            "category": category,
            "content": content,
            "meta": meta or {},
            "source_channel": source_channel,
            "auto_log_diet": auto_log_diet,
        }
        resp = await client.post(f"{self.api_base}/tick/messages", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def create_reminder(
        self,
        title: str,
        trigger_time: datetime,
        body: str = "",
        priority: str = "normal",
        rem_type: str = "agent.quick_reminder",
        payload: Optional[Dict[str, Any]] = None,
        expire_after_minutes: int = 240,
    ) -> Dict[str, Any]:
        """在 sail_server 创建一条真实 Reminder（Android App 到点弹窗推送）。"""
        client = self._get_client()
        req = {
            "type": rem_type,
            "title": title,
            "body": body,
            "priority": priority,
            "source": "agent",
            "trigger_time": trigger_time.isoformat(),
            "expire_after_minutes": expire_after_minutes,
            "payload": payload or {},
        }
        resp = await client.post(f"{self.api_base}/reminder/", json=req)
        resp.raise_for_status()
        return resp.json()

    async def list_pending_reminders(self) -> List[Dict[str, Any]]:
        """查询当前活跃待触发的提醒。"""
        client = self._get_client()
        resp = await client.get(f"{self.api_base}/reminder/pending")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("items", [])

    async def cancel_reminder(self, reminder_id: int) -> bool:
        """撤销 sail_server 上的指定提醒（同时自动消解关联收件箱条目）。"""
        try:
            client = self._get_client()
            resp = await client.delete(f"{self.api_base}/reminder/{int(reminder_id)}")
            if resp.status_code in (404, 409):
                return False
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.warning("cancel_reminder(%s) failed: %s", reminder_id, exc)
            return False

    # ── 统一 UserProfile 读写 ───────────────────────────────────────────

    async def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """拉取 sail_server 统一 UserProfile（安静时段、目标体重、跨端偏好）。"""
        try:
            client = self._get_client()
            resp = await client.get(f"{self.api_base}/user/profile", timeout=8.0)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.debug("get_user_profile skipped (non-fatal): %s", exc)
            return None

    async def update_user_health_profile(self, health_patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """将高置信度学到的公开画像字段回写到 UserProfile.health_profile。"""
        if not health_patch:
            return None
        try:
            client = self._get_client()
            resp = await client.patch(
                f"{self.api_base}/user/profile",
                json={"health_profile": health_patch},
                timeout=8.0,
            )
            if resp.status_code >= 400:
                return None
            return resp.json()
        except Exception as exc:
            logger.debug("update_user_health_profile skipped (non-fatal): %s", exc)
            return None

    # ── AI Trace 上报 ───────────────────────────────────────────────────

    async def report_ai_trace(self, trace_payload: Dict[str, Any]) -> bool:
        """上报单次 Tick 全链路 AI Trace 至 sail_server（非致命，失败仅记日志）。"""
        try:
            client = self._get_client()
            resp = await client.post(
                f"{self.api_base}/telemetry/ai-traces",
                json=trace_payload,
                timeout=8.0,
            )
            if resp.status_code >= 400:
                logger.warning(
                    "report_ai_trace rejected: status=%s body=%s",
                    resp.status_code,
                    resp.text[:200],
                )
                return False
            return True
        except Exception as exc:
            logger.debug("report_ai_trace skipped (non-fatal): %s", exc)
            return False
