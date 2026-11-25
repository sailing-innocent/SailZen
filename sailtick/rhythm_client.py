# -*- coding: utf-8 -*-
# @file rhythm_client.py
# @brief SailTick Rhythm HTTP 客户端（严格经 sail_server /api/v1/rhythm/* 调度日程与项目）
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""RhythmClient — SailTick 智能体调度 Rhythm v2 API 的唯一通道。

恪守双库隔离红线：
- SailTick 绝不直连主库 PostgreSQL/SQLite；
- 所有对项目（venture）、任务（affair）、可视化时间线（timeline/ai-sync）、
  临时占用（occupancy）与习惯打卡（checkin）的读写，全部通过 HTTP 调用 sail_server。
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Union

import httpx

logger = logging.getLogger(__name__)


def _fmt_date(d: Union[date, datetime, str]) -> str:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)[:10]


class RhythmClient:
    """SailTick 调用 sail_server `/api/v1/rhythm/*` 的异步客户端。"""

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
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def health(self) -> bool:
        try:
            resp = await self._get_client().get(f"{self.api_base}/health")
            return resp.status_code == 200
        except Exception:
            return False

    # ── 读：Dashboard / Timeline / Projects / Affairs / Occupancies ────

    async def get_dashboard(self, target_date: Optional[Union[date, str]] = None) -> Dict[str, Any]:
        d_str = _fmt_date(target_date or self._clock().date())
        resp = await self._get_client().get(
            f"{self.api_base}/rhythm/dashboard", params={"date": d_str}
        )
        resp.raise_for_status()
        return resp.json()

    async def get_timeline(self, target_date: Optional[Union[date, str]] = None) -> Dict[str, Any]:
        d_str = _fmt_date(target_date or self._clock().date())
        resp = await self._get_client().get(
            f"{self.api_base}/rhythm/timeline/day", params={"date": d_str}
        )
        resp.raise_for_status()
        return resp.json()

    async def get_timeline_range(
        self, start_date: Union[date, str], end_date: Union[date, str]
    ) -> Dict[str, Any]:
        resp = await self._get_client().get(
            f"{self.api_base}/rhythm/timeline/range",
            params={"start_date": _fmt_date(start_date), "end_date": _fmt_date(end_date)},
        )
        resp.raise_for_status()
        return resp.json()

    async def list_projects(self) -> List[Dict[str, Any]]:
        resp = await self._get_client().get(f"{self.api_base}/rhythm/venture/projects")
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    async def list_affairs(
        self,
        states: Optional[List[str]] = None,
        kinds: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        params: List[tuple[str, str]] = [("limit", str(limit))]
        for s in states or []:
            params.append(("state", s))
        for k in kinds or []:
            params.append(("kind", k))
        resp = await self._get_client().get(f"{self.api_base}/rhythm/affair", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("affairs", []) if isinstance(data, dict) else []

    async def list_occupancies(
        self, target_date: Optional[Union[date, str]] = None
    ) -> List[Dict[str, Any]]:
        d_str = _fmt_date(target_date or self._clock().date())
        resp = await self._get_client().get(
            f"{self.api_base}/rhythm/occupancy", params={"date": d_str}
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("occupancies", []) if isinstance(data, dict) else []

    # ── 写：AI 自主排程时间线（核心） ──────────────────────────────────

    async def sync_ai_timeline(
        self,
        target_date: Union[date, str],
        blocks: List[Dict[str, Any]],
        rationale: str = "",
        preserve_done: bool = True,
        preserve_pinned: bool = True,
        source: str = "sailtick",
    ) -> Dict[str, Any]:
        payload = {
            "date": _fmt_date(target_date),
            "blocks": blocks,
            "rationale": rationale,
            "preserve_done": preserve_done,
            "preserve_pinned": preserve_pinned,
            "source": source,
        }
        resp = await self._get_client().post(
            f"{self.api_base}/rhythm/timeline/ai-sync", json=payload
        )
        resp.raise_for_status()
        return resp.json()

    async def create_block(
        self,
        target_date: Union[date, str],
        start_time: str,
        end_time: str,
        block_type: str = "focus",
        title: str = "",
        affair_id: Optional[int] = None,
        pinned: bool = False,
        note: str = "",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "date": _fmt_date(target_date),
            "start_time": start_time,
            "end_time": end_time,
            "block_type": block_type,
            "pinned": pinned,
            "ref": {"label": title, "source": "sailtick", "note": note},
        }
        if affair_id is not None:
            payload["affair_id"] = int(affair_id)
        resp = await self._get_client().post(
            f"{self.api_base}/rhythm/timeline/block", json=payload
        )
        resp.raise_for_status()
        return resp.json()

    async def set_block_status(self, block_id: int, status: str) -> Dict[str, Any]:
        resp = await self._get_client().post(
            f"{self.api_base}/rhythm/timeline/block/{int(block_id)}/status",
            json={"status": status},
        )
        resp.raise_for_status()
        return resp.json()

    async def move_block(
        self, block_id: int, start_time: str, end_time: str
    ) -> Dict[str, Any]:
        resp = await self._get_client().post(
            f"{self.api_base}/rhythm/timeline/block/{int(block_id)}/move",
            json={"start_time": start_time, "end_time": end_time},
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_block(self, block_id: int) -> Dict[str, Any]:
        resp = await self._get_client().delete(
            f"{self.api_base}/rhythm/timeline/block/{int(block_id)}"
        )
        resp.raise_for_status()
        return resp.json()

    # ── 写：项目 / 事务 / 里程碑 / 占用 / 打卡 ─────────────────────────

    async def create_affair(
        self,
        title: str,
        kind: str = "task_oneoff",
        domain: Optional[str] = None,
        description: str = "",
        urgency_ddl: Optional[str] = None,
        est_minutes: int = 30,
        importance: int = 3,
        kind_meta: Optional[Dict[str, Any]] = None,
        state: Optional[str] = None,
        parent_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "title": title,
            "kind": kind,
            "description": description,
            "est_minutes": int(est_minutes),
            "importance": max(1, min(5, int(importance))),
            "kind_meta": dict(kind_meta or {}),
        }
        if domain:
            payload["domain"] = domain
        if urgency_ddl:
            payload["urgency_ddl"] = urgency_ddl
        if state:
            payload["state"] = state
        if parent_id is not None:
            payload["parent_id"] = int(parent_id)
        resp = await self._get_client().post(f"{self.api_base}/rhythm/affair", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_affair(self, affair_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self._get_client().put(
            f"{self.api_base}/rhythm/affair/{int(affair_id)}", json=updates
        )
        resp.raise_for_status()
        return resp.json()

    async def transit_affair(
        self,
        affair_id: int,
        action: str,
        defer_to: Optional[str] = None,
        defer_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"action": action}
        if defer_to:
            payload["defer_to"] = defer_to
        if defer_end:
            payload["defer_end"] = defer_end
        resp = await self._get_client().post(
            f"{self.api_base}/rhythm/affair/{int(affair_id)}/state", json=payload
        )
        resp.raise_for_status()
        return resp.json()

    async def add_milestone(
        self,
        venture_id: int,
        title: str,
        description: str = "",
        urgency_ddl: Optional[str] = None,
        est_minutes: int = 60,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "title": title,
            "description": description,
            "est_minutes": int(est_minutes),
        }
        if urgency_ddl:
            payload["urgency_ddl"] = urgency_ddl
        resp = await self._get_client().post(
            f"{self.api_base}/rhythm/venture/{int(venture_id)}/milestone", json=payload
        )
        resp.raise_for_status()
        return resp.json()

    async def milestone_done(self, milestone_id: int) -> Dict[str, Any]:
        resp = await self._get_client().post(
            f"{self.api_base}/rhythm/venture/milestone/{int(milestone_id)}/done"
        )
        resp.raise_for_status()
        return resp.json()

    async def create_occupancy(
        self,
        target_date: Union[date, str],
        occupancy_type: str = "meeting",
        start: Optional[str] = None,
        end: Optional[str] = None,
        whole_day: bool = False,
        label: str = "",
        note: str = "",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "date": _fmt_date(target_date),
            "occupancy_type": occupancy_type,
            "whole_day": bool(whole_day),
            "label": label,
            "note": note,
        }
        if start:
            payload["start"] = start
        if end:
            payload["end"] = end
        resp = await self._get_client().post(
            f"{self.api_base}/rhythm/occupancy", json=payload
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_occupancy(self, block_id: int) -> Dict[str, Any]:
        resp = await self._get_client().delete(
            f"{self.api_base}/rhythm/occupancy/{int(block_id)}"
        )
        resp.raise_for_status()
        return resp.json()

    async def checkin(
        self,
        affair_id: int,
        result: str = "done",
        log_date: Optional[Union[date, str]] = None,
        note: str = "",
        source: str = "agent",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "affair_id": int(affair_id),
            "result": result,
            "note": note,
            "source": source,
        }
        if log_date:
            payload["log_date"] = _fmt_date(log_date)
        resp = await self._get_client().post(
            f"{self.api_base}/rhythm/checkin", json=payload
        )
        resp.raise_for_status()
        return resp.json()
