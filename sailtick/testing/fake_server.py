# -*- coding: utf-8 -*-
# @file fake_server.py
# @brief 内存态 sail_server 仿真器（经 httpx.MockTransport 完整走通 HTTP 客户端协议）
# @author sailing-innocent
# @date 2026-11-21
# @version 1.0
# ---------------------------------
"""SimulatedSailServer — 有状态内存 sail_server 仿真器。

特点:
  - 经 httpx.MockTransport 接入真实 TicketInbox 与 DataScanner，
    不绕过 HTTP 序列化、URL 路由、状态码与鉴权头校验。
  - 实现完整票据状态机 (pending -> replied -> resolved / expired / snoozed)。
  - 支持虚拟时钟驱动的超期判定 (expire-overdue)。
  - 支持预设健康/饮食/睡眠/心情/餐饮消费/打卡/笔记信号与运行中动态追加。
  - 支持一键故障注入 (reachable=False / fail_ticket_create=True / auth_token 校验)。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from sailtick.datascan import DataScanner
from sailtick.inbox import TicketInbox


class SimulatedSailServer:
    """有状态的 sail_server HTTP 仿真器。"""

    def __init__(
        self,
        clock: Callable[[], datetime] = datetime.now,
        auth_token: str = "",
    ):
        self._clock = clock
        self.auth_token = auth_token
        self.reachable: bool = True
        self.fail_ticket_create: bool = False

        self.tickets: List[Dict[str, Any]] = []
        self._next_id: int = 1
        self.requests_log: List[Dict[str, Any]] = []

        # 可控健康与生活数据源
        self.signals: Dict[str, List[Dict[str, Any]]] = {
            "weight": [],
            "sleep": [],
            "diet": [],
            "exercise": [],
            "mood": [],
            "finance": [],
            "rhythm": [],
            "notes": [],
        }

    # ── 数据种子与用户行为模拟 ─────────────────────────────────────────

    def seed_weight(self, date: str, value: float, note: str = "") -> None:
        self.signals["weight"].append({"date": date, "value": value, "unit": "kg", "note": note})

    def seed_signal(self, name: str, item: Dict[str, Any]) -> None:
        self.signals.setdefault(name, []).append(item)

    def simulate_user_reply(self, ticket_id: int, reply: str) -> Dict[str, Any]:
        """在 Tick 间隙模拟用户在 /tick 网页回复票据。"""
        for t in self.tickets:
            if t["id"] == ticket_id:
                t["status"] = "replied"
                t["reply"] = reply
                t["replied_at"] = self._clock().isoformat()
                return t
        raise KeyError(f"ticket #{ticket_id} not found")

    def simulate_user_reply_latest_pending(self, reply: str) -> Optional[Dict[str, Any]]:
        """模拟用户回复最新一张 pending 票据。"""
        pending = [t for t in self.tickets if t["status"] == "pending"]
        if not pending:
            return None
        return self.simulate_user_reply(pending[-1]["id"], reply)

    # ── HTTP 协议处理（httpx.MockTransport handler） ───────────────────

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests_log.append(
            {
                "method": request.method,
                "url": str(request.url),
                "at": self._clock().isoformat(),
            }
        )
        if not self.reachable:
            raise httpx.ConnectError("SimulatedSailServer is down")

        if self.auth_token:
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {self.auth_token}":
                return httpx.Response(401, json={"detail": "unauthorized"})

        parsed = urlparse(str(request.url))
        path = parsed.path
        qs = parse_qs(parsed.query)

        # 健康检查
        if request.method == "GET" and path.endswith("/api/v1/health"):
            return httpx.Response(200, json={"status": "ok"})

        # 票据 API
        if path.endswith("/api/v1/tick/tickets"):
            if request.method == "GET":
                status_filter = (qs.get("status") or [None])[0]
                items = list(self.tickets)
                if status_filter:
                    items = [t for t in items if t["status"] == status_filter]
                return httpx.Response(200, json=items)
            if request.method == "POST":
                if self.fail_ticket_create:
                    return httpx.Response(500, json={"detail": "injected ticket write failure"})
                payload = json.loads(request.content.decode("utf-8"))
                now_iso = self._clock().isoformat()
                ticket = {
                    "id": self._next_id,
                    "tick_id": payload.get("tick_id", ""),
                    "type": payload.get("type", "info"),
                    "title": payload.get("title", ""),
                    "body": payload.get("body", ""),
                    "priority": payload.get("priority", "normal"),
                    "channel": payload.get("channel", "web"),
                    "status": "pending",
                    "expected_reply_by": payload.get("expected_reply_by"),
                    "fallback_assumption": payload.get("fallback_assumption", ""),
                    "reply": None,
                    "replied_at": None,
                    "resolved_at": None,
                    "resolution": None,
                    "created_at": now_iso,
                }
                self._next_id += 1
                self.tickets.append(ticket)
                return httpx.Response(201, json=ticket)

        if "/api/v1/tick/tickets/" in path:
            tail = path.split("/api/v1/tick/tickets/", 1)[1]
            parts = tail.split("/")
            try:
                tid = int(parts[0])
            except ValueError:
                return httpx.Response(400, json={"detail": "invalid id"})
            ticket = next((t for t in self.tickets if t["id"] == tid), None)
            if ticket is None:
                return httpx.Response(404, json={"detail": "not found"})

            if len(parts) == 1 and request.method == "GET":
                return httpx.Response(200, json=ticket)
            if len(parts) == 2 and request.method == "POST":
                action = parts[1]
                payload = json.loads(request.content.decode("utf-8")) if request.content else {}
                if action == "reply":
                    ticket["status"] = "replied"
                    ticket["reply"] = payload.get("reply", "")
                    ticket["replied_at"] = self._clock().isoformat()
                    return httpx.Response(201, json=ticket)
                if action == "resolve":
                    ticket["status"] = "resolved"
                    ticket["resolution"] = payload.get("resolution", "")
                    ticket["resolved_at"] = self._clock().isoformat()
                    return httpx.Response(201, json=ticket)
                if action == "snooze":
                    hours = int(payload.get("hours", 24))
                    ticket["status"] = "snoozed"
                    ticket["expected_reply_by"] = (
                        self._clock() + timedelta(hours=hours)
                    ).isoformat()
                    return httpx.Response(201, json=ticket)

        if request.method == "GET" and path.endswith("/api/v1/tick/replies"):
            since_raw = (qs.get("since") or [None])[0]
            replied = [t for t in self.tickets if t["status"] in ("replied", "resolved")]
            if since_raw:
                replied = [
                    t for t in replied if (t.get("replied_at") or "") >= since_raw
                ]
            return httpx.Response(200, json=replied)

        if request.method == "POST" and path.endswith("/api/v1/tick/expire-overdue"):
            now = self._clock()
            expired = 0
            for t in self.tickets:
                if t["status"] == "pending" and t.get("expected_reply_by"):
                    try:
                        due = datetime.fromisoformat(t["expected_reply_by"])
                        if due < now:
                            t["status"] = "expired"
                            expired += 1
                    except ValueError:
                        pass
            return httpx.Response(201, json={"expired": expired})

        # 健康与生活数据 API
        if request.method == "GET":
            if path.endswith("/health/body_data/series") or path.endswith("/health/body-data"):
                return httpx.Response(200, json=list(self.signals["weight"]))
            if path.endswith("/health/sleep"):
                return httpx.Response(200, json=list(self.signals["sleep"]))
            if path.endswith("/health/diet"):
                return httpx.Response(200, json=list(self.signals["diet"]))
            if path.endswith("/health/exercise"):
                return httpx.Response(200, json=list(self.signals["exercise"]))
            if path.endswith("/health/mood"):
                return httpx.Response(200, json=list(self.signals["mood"]))
            if path.endswith("/money/transactions"):
                return httpx.Response(200, json=list(self.signals["finance"]))
            if path.endswith("/rhythm/checkins"):
                return httpx.Response(200, json=list(self.signals["rhythm"]))
            if path.endswith("/text/notes"):
                return httpx.Response(200, json=list(self.signals["notes"]))

        return httpx.Response(404, json={"detail": f"unhandled route: {request.method} {path}"})

    # ── 客户端工厂 ────────────────────────────────────────────────────

    def _make_client(self) -> httpx.AsyncClient:
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return httpx.AsyncClient(
            transport=httpx.MockTransport(self.handle_request),
            base_url="http://simulated-sail-server",
            headers=headers,
        )

    def create_inbox(self) -> TicketInbox:
        inbox = TicketInbox(
            "http://simulated-sail-server/api/v1",
            auth_token=self.auth_token,
            clock=self._clock,
        )
        inbox._client = self._make_client()
        return inbox

    def create_scanner(self, max_package_chars: int = 12000) -> DataScanner:
        scanner = DataScanner(
            "http://simulated-sail-server/api/v1",
            auth_token=self.auth_token,
            max_package_chars=max_package_chars,
        )
        scanner._client = self._make_client()
        return scanner
