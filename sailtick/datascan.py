# -*- coding: utf-8 -*-
# @file datascan.py
# @brief 数据扫描：组装本 Tick 数据包（token 预算截断）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""DataScanner — 从 sail_server 拉取健康/财务/rhythm 数据，组装数据包。

信号源映射（设计文档 §8）：
  体重/身体数据  GET /health/body_data/series?metric=weight
  饮食           GET /health/diet（容错）
  运动           GET /health/exercise
  睡眠           GET /health/sleep
  心情           GET /health/mood
  餐饮消费       GET /money/transactions（tag 过滤，容错）
  打卡/复盘      GET /rhythm/checkins（容错）
  笔记           GET /text/notes（摘要，容错）

容错原则：任一源失败不阻塞 Tick，记 None + warning；sail_server 整体不可达时
返回只含 health_ok=False 的包，Tick 转为仅本地维护。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# 信号截断优先级（设计文档 §8）
SIGNAL_PRIORITY = ["weight", "sleep", "diet", "exercise", "mood", "finance", "rhythm", "notes"]


class DataScanner:
    """数据包组装器。"""

    def __init__(self, api_base: str, auth_token: str = "", max_package_chars: int = 12000):
        self.api_base = api_base.rstrip("/")
        self.auth_token = auth_token
        self.max_package_chars = max_package_chars
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
        try:
            client = self._get_client()
            # 真正的健康端点在 /api/v1/health（根 /health 是静态站 302）
            resp = await client.get(f"{self.api_base}/health")
            return resp.status_code == 200
        except Exception:
            return False

    # ── 采集 ──────────────────────────────────────────────────────────

    async def _fetch(self, path: str, params: Optional[dict] = None) -> Optional[Any]:
        try:
            client = self._get_client()
            resp = await client.get(f"{self.api_base}{path}", params=params or {})
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("datascan fetch %s failed: %s", path, exc)
            return None

    async def collect(self, days: int = 7) -> Dict[str, Any]:
        """采集最近 N 天各源数据。任何源失败返回 None 值。"""
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        weight = await self._fetch(
            "/health/body_data/series", {"metric": "weight", "start": since}
        )
        if weight is None:
            # 兼容 sail_server kebab-case 路由 /api/v1/health/body-data
            weight = await self._fetch(
                "/health/body-data", {"metric": "weight", "start": since}
            )
        sleep = await self._fetch("/health/sleep", {"start": since, "limit": 20})
        diet = await self._fetch("/health/diet", {"start": since, "limit": 20})
        exercise = await self._fetch("/health/exercise", {"start": since, "limit": 20})
        mood = await self._fetch("/health/mood", {"start": since, "limit": 20})
        finance = await self._fetch(
            "/money/transactions", {"start": since, "tag": "餐饮", "limit": 20}
        )
        rhythm = await self._fetch("/rhythm/checkins", {"start": since, "limit": 20})
        notes = await self._fetch("/text/notes", {"limit": 10})

        return {
            "collected_at": datetime.now().isoformat(),
            "window_days": days,
            "weight": self._simplify_series(weight),
            "sleep": self._simplify_list(sleep),
            "diet": self._simplify_list(diet),
            "exercise": self._simplify_list(exercise),
            "mood": self._simplify_list(mood),
            "finance_food": self._simplify_list(finance),
            "rhythm_checkins": self._simplify_list(rhythm),
            "notes": self._simplify_list(notes),
        }

    # ── 精简与截断 ────────────────────────────────────────────────────

    @staticmethod
    def _simplify_series(raw: Any, limit: int = 14) -> Optional[List[Dict[str, Any]]]:
        if raw is None:
            return None
        items: List[Any] = []
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("items") or raw.get("data") or raw.get("series") or []
        out = []
        for it in items[-limit:]:
            if isinstance(it, dict):
                out.append(
                    {
                        k: it.get(k)
                        for k in ("date", "time", "value", "metric", "unit", "weight", "note")
                        if k in it
                    }
                )
        return out

    @staticmethod
    def _simplify_list(raw: Any, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        if raw is None:
            return None
        items: List[Any] = []
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("items") or raw.get("data") or []
        out = []
        for it in items[-limit:]:
            if isinstance(it, dict):
                # 每源最多保留 6 个字段，控制 token
                out.append({k: v for k, v in list(it.items())[:6]})
        return out

    def truncate(self, package: Dict[str, Any]) -> Dict[str, Any]:
        """按 SIGNAL_PRIORITY 截断到 token 预算内。"""
        result: Dict[str, Any] = {
            "collected_at": package.get("collected_at"),
            "window_days": package.get("window_days"),
            "health_ok": package.get("health_ok", True),
        }

        def size(obj: Any) -> int:
            return len(json.dumps(obj, ensure_ascii=False, default=str))

        remaining = self.max_package_chars - size(result)
        for signal in SIGNAL_PRIORITY:
            data = package.get(signal)
            if data is None:
                result[signal] = None
                continue
            need = size(data)
            if need <= remaining:
                result[signal] = data
                remaining -= need
            else:
                # 简单二分截断列表（单条仍超预算则丢弃该信号）
                if isinstance(data, list):
                    keep = data
                    while len(keep) > 1 and size(keep) > remaining:
                        keep = keep[: max(1, len(keep) // 2)]
                    result[signal] = keep if size(keep) <= remaining else None
                else:
                    result[signal] = None
                remaining = self.max_package_chars - size(result)
        return result

    async def scan(self, days: int = 7) -> Dict[str, Any]:
        """完整数据扫描流程：采集 + 精简 + 截断。"""
        if not await self.health():
            return {"health_ok": False, "reason": "sail_server unreachable"}
        package = await self.collect(days=days)
        package["health_ok"] = True
        return self.truncate(package)

    def describe(self, package: Dict[str, Any]) -> str:
        """给 PLAN prompt 使用的数据包摘要文本。"""
        if not package.get("health_ok"):
            return "数据包不可用（sail_server 不可达），本 Tick 仅做本地维护。"

        lines: List[str] = [f"数据窗口: 最近 {package.get('window_days', 7)} 天"]
        weight = package.get("weight") or []
        if weight:
            vals = [w.get("value") or w.get("weight") for w in weight if isinstance(w, dict)]
            vals = [v for v in vals if v is not None]
            if vals:
                lines.append(f"体重: 最新 {vals[-1]}kg，区间 {min(vals)}~{max(vals)}kg，共 {len(vals)} 条记录")
        for key, label in (
            ("sleep", "睡眠"), ("diet", "饮食"), ("exercise", "运动"), ("mood", "心情"),
            ("finance_food", "餐饮消费"), ("rhythm_checkins", "打卡"),
        ):
            items = package.get(key)
            if items:
                lines.append(f"{label}: {len(items)} 条记录")
        return "\n".join(lines)
