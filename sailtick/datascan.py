# -*- coding: utf-8 -*-
# @file datascan.py
# @brief 数据扫描：组装本 Tick 数据包（真实 sail_server 路由 + 体重监控摘要 + token 预算截断）
# @author sailing-innocent
# @date 2026-10-27
# @version 2.0
# ---------------------------------
"""DataScanner — 从 sail_server 拉取健康/财务/rhythm/用户主动消息，组装数据包。

真实 sail_server 路由映射（v2.0 修复全部 404/422 漂移）:
  体重/身体数据  GET /health/body-data/series?metric=weight&start=<unix>&end=<unix>
                 （回退 GET /health/weight?start=<unix>&end=<unix>&limit=60）
  活跃体重计划   GET /health/weight/plan/progress
  饮食           GET /health/diet?start=<unix>&end=<unix>&limit=100
  睡眠           GET /health/sleep?start=<unix>&end=<unix>&limit=30
  运动           GET /health/exercise?start=<unix>&end=<unix>&limit=30
  心情           GET /health/mood?start=<unix>&end=<unix>&limit=30
  用户主动消息   GET /tick/messages?status=unread&limit=50
  餐饮消费       GET /finance/transaction?start=<unix>&end=<unix>&limit=100（按餐饮关键词/标签筛选）
  打卡/复盘      GET /rhythm/checkin?limit=30

容错原则：任一源失败不阻塞 Tick，记 None + warning；sail_server 整体不可达时
返回只含 health_ok=False 的包，Tick 转为仅本地维护。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# 信号截断优先级（高价值监控摘要与用户主动输入最优先保留）
SIGNAL_PRIORITY = [
    "weight_monitor",
    "weight",
    "user_messages",
    "rhythm",
    "diet",
    "active_plan",
    "sleep",
    "exercise",
    "mood",
    "finance_food",
    "rhythm_checkins",
    "notes",
]

FOOD_KEYWORDS = (
    "餐", "饭", "外卖", "食堂", "咖啡", "奶茶", "零食", "早餐", "午饭", "晚饭",
    "吃", "食品", "超市", "水果", "烧烤", "火锅", "聚餐", "面", "粉", "汉堡",
    "炸鸡", "甜品", "蛋糕", "饮料", "夜宵", "宵夜", "麦当劳", "肯德基", "瑞幸",
    "星巴克", "霸王茶姬", "喜茶", "蜜雪", "便利店", "美团", "饿了么",
)

SNACK_DRINK_KEYWORDS = (
    "零食", "奶茶", "咖啡", "甜品", "蛋糕", "饮料", "冰淇淋", "雪糕",
    "炸鸡", "薯片", "糖", "瑞幸", "星巴克", "霸王茶姬", "喜茶", "蜜雪", "便利店",
)

SOCIAL_DINING_KEYWORDS = (
    "聚餐", "火锅", "烧烤", "酒", "应酬", "请客", "大餐", "自助", "烤肉", "日料",
)

TAKEOUT_KEYWORDS = ("外卖", "美团", "饿了么", "京东外卖")


class DataScanner:
    """数据包组装器。"""

    def __init__(
        self,
        api_base: str,
        auth_token: str = "",
        max_package_chars: int = 12000,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.api_base = api_base.rstrip("/")
        self.auth_token = auth_token
        self.max_package_chars = max_package_chars
        self._clock = clock
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
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
        try:
            client = self._get_client()
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
            if not resp.text or not resp.text.strip():
                return None
            return resp.json()
        except Exception as exc:
            logger.warning("datascan fetch %s failed: %s", path, exc)
            return None

    async def collect(self, days: int = 7) -> Dict[str, Any]:
        """采集最近 N 天各源数据并计算体重更新监控摘要。"""
        now = self._clock()
        start_dt = now - timedelta(days=days)
        start_ts = start_dt.timestamp()
        end_ts = now.timestamp()

        # 1. 体重序列（优先 kebab-case /health/body-data/series，回退 /health/weight 与历史 mock 路径）
        weight_raw = await self._fetch(
            "/health/body-data/series",
            {"metric": "weight", "start": start_ts, "end": end_ts},
        )
        if not self._simplify_series(weight_raw, limit=21):
            alt_w = await self._fetch(
                "/health/weight", {"start": start_ts, "end": end_ts, "limit": 60}
            )
            if self._simplify_series(alt_w, limit=21):
                weight_raw = alt_w
            else:
                legacy_w = await self._fetch(
                    "/health/body_data/series",
                    {"metric": "weight", "start": start_ts, "end": end_ts},
                )
                if self._simplify_series(legacy_w, limit=21):
                    weight_raw = legacy_w

        # 2. 活跃体重计划进度
        plan_progress = await self._fetch("/health/weight/plan/progress")

        # 3. 饮食 / 睡眠 / 运动 / 心情（统一传 Unix 时间戳）
        diet = await self._fetch("/health/diet", {"start": start_ts, "end": end_ts, "limit": 80})
        sleep = await self._fetch("/health/sleep", {"start": start_ts, "end": end_ts, "limit": 20})
        exercise = await self._fetch("/health/exercise", {"start": start_ts, "end": end_ts, "limit": 20})
        mood = await self._fetch("/health/mood", {"start": start_ts, "end": end_ts, "limit": 20})

        # 4. 用户主动上报的未吸收餐饮/日常消息
        user_messages = await self._fetch(
            "/tick/messages", {"status": "unread", "direction": "user_to_agent", "limit": 50}
        )

        # 5. 餐饮消费、节奏全景（今日/明日时间线 + 重要项目倒排 + 焦点事务 + 占用）与打卡
        finance_raw = await self._fetch_transactions_window(
            start_ts=start_ts, end_ts=end_ts, max_pages=1, page_size=80
        )
        rhythm_raw = await self._fetch("/rhythm/checkin", {"limit": 20})
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        rhythm_dash_raw = await self._fetch("/rhythm/dashboard", {"date": today_str})
        rhythm_tomorrow_raw = await self._fetch("/rhythm/timeline/day", {"date": tomorrow_str})
        rhythm_snapshot = self._simplify_rhythm(rhythm_dash_raw, rhythm_tomorrow_raw, today_str)

        weight_series = self._simplify_series(weight_raw, limit=21)
        weight_monitor = self._compute_weight_monitor(weight_series, plan_progress, now)
        diet_items = self._simplify_diet(diet, limit=25)
        msg_items = self._simplify_messages(user_messages, limit=30)

        return {
            "collected_at": now.isoformat(),
            "window_days": days,
            "weight_monitor": weight_monitor,
            "weight": weight_series,
            "active_plan": self._simplify_plan(plan_progress),
            "diet": diet_items,
            "user_messages": msg_items,
            "rhythm": rhythm_snapshot,
            "sleep": self._simplify_list(sleep, limit=10),
            "exercise": self._simplify_list(exercise, limit=10),
            "mood": self._simplify_list(mood, limit=10),
            "finance_food": self._filter_food_transactions(finance_raw, limit=12),
            "rhythm_checkins": self._simplify_list(rhythm_raw, limit=10),
            "notes": None,
        }

    async def _fetch_transactions_window(
        self,
        start_ts: float,
        end_ts: float,
        max_pages: int = 1,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """拉取时间窗口内的财务交易（优先 /finance/transaction/paginated/，404 时回退旧接口）。"""
        collected: List[Dict[str, Any]] = []
        paginated_supported = True
        for page in range(1, max(1, max_pages) + 1):
            resp = await self._fetch(
                "/finance/transaction/paginated/",
                {
                    "page": page,
                    "page_size": min(100, max(1, page_size)),
                    "from_time": start_ts,
                    "to_time": end_ts,
                    "sort_by": "htime",
                    "sort_order": "desc",
                },
            )
            if resp is None:
                if page == 1:
                    paginated_supported = False
                break
            if isinstance(resp, dict):
                items = resp.get("data") or resp.get("items") or []
                collected.extend(it for it in items if isinstance(it, dict))
                if not resp.get("has_next") or not items:
                    break
            elif isinstance(resp, list):
                collected.extend(it for it in resp if isinstance(it, dict))
                break
            else:
                break

        if not paginated_supported:
            legacy = await self._fetch(
                "/finance/transaction", {"start": start_ts, "end": end_ts, "limit": page_size}
            )
            if isinstance(legacy, list):
                collected = [it for it in legacy if isinstance(it, dict)]
            elif isinstance(legacy, dict):
                collected = [
                    it for it in (legacy.get("items") or legacy.get("data") or [])
                    if isinstance(it, dict)
                ]
        return collected

    async def collect_deep(self, days: int = 90) -> Dict[str, Any]:
        """夜间深度自维护专用：长周期全量数据拉取（不经 prompt 字符截断，供数学建模与深度洞察）。"""
        if not await self.health():
            return {"health_ok": False, "window_days": days, "reason": "sail_server unreachable"}

        now = self._clock()
        start_dt = now - timedelta(days=max(7, int(days)))
        start_ts = start_dt.timestamp()
        end_ts = now.timestamp()

        # 1. 长周期体重序列（优先 body-data/series，回退 /health/weight）
        weight_raw = await self._fetch(
            "/health/body-data/series",
            {"metric": "weight", "start": start_ts, "end": end_ts},
        )
        weight_series = self._simplify_series(weight_raw, limit=500) or []
        if not weight_series:
            alt_w = await self._fetch(
                "/health/weight", {"start": start_ts, "end": end_ts, "limit": 500}
            )
            weight_series = self._simplify_series(alt_w, limit=500) or []

        # 2. 活跃体重计划进度
        plan_progress = await self._fetch("/health/weight/plan/progress")

        # 3. 饮食 / 睡眠 / 运动 / 心情（放宽条数）
        diet_raw = await self._fetch("/health/diet", {"start": start_ts, "end": end_ts, "limit": 500})
        sleep_raw = await self._fetch("/health/sleep", {"start": start_ts, "end": end_ts, "limit": 120})
        exercise_raw = await self._fetch("/health/exercise", {"start": start_ts, "end": end_ts, "limit": 120})
        mood_raw = await self._fetch("/health/mood", {"start": start_ts, "end": end_ts, "limit": 120})

        # 4. 长周期财务交易分页拉取（最多 6 页 = 600 条，覆盖 90 天日常消费）
        tx_all = await self._fetch_transactions_window(
            start_ts=start_ts, end_ts=end_ts, max_pages=6, page_size=100
        )

        # 5. 最近用户消息（含已吸收，用于提取食物/习惯）
        recent_messages = await self._fetch(
            "/tick/messages", {"direction": "user_to_agent", "limit": 100}
        )

        # 6. 近 21 天 Rhythm 执行历史 + 活跃项目 + 焦点事务（供夜间节奏分析器学习作息与风险）
        rhythm_start = (now - timedelta(days=20)).strftime("%Y-%m-%d")
        rhythm_end = now.strftime("%Y-%m-%d")
        rhythm_history = await self._fetch(
            "/rhythm/timeline/range",
            {"start_date": rhythm_start, "end_date": rhythm_end},
        )
        rhythm_projects = await self._fetch("/rhythm/venture/projects")
        rhythm_affairs_raw = await self._fetch("/rhythm/affair", {"limit": 100})
        rhythm_affairs = (
            rhythm_affairs_raw.get("affairs", [])
            if isinstance(rhythm_affairs_raw, dict)
            else (rhythm_affairs_raw if isinstance(rhythm_affairs_raw, list) else [])
        )

        food_tx = self._classify_food_transactions(tx_all)
        weight_monitor = self._compute_weight_monitor(weight_series, plan_progress, now)

        return {
            "health_ok": True,
            "collected_at": now.isoformat(),
            "window_days": days,
            "weight_monitor": weight_monitor,
            "weight": weight_series,
            "active_plan": self._simplify_plan(plan_progress),
            "diet": self._simplify_diet(diet_raw, limit=300) or [],
            "sleep": self._simplify_list(sleep_raw, limit=120) or [],
            "exercise": self._simplify_list(exercise_raw, limit=120) or [],
            "mood": self._simplify_list(mood_raw, limit=120) or [],
            "transactions_total": len(tx_all),
            "finance_food": food_tx,
            "user_messages": self._simplify_messages(recent_messages, limit=100) or [],
            "rhythm_history": rhythm_history if isinstance(rhythm_history, dict) else {},
            "rhythm_projects": rhythm_projects if isinstance(rhythm_projects, list) else [],
            "rhythm_affairs": rhythm_affairs,
        }

    @classmethod
    def _classify_food_transactions(cls, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对长周期交易做精细餐饮分类：meal / takeout / snack_drink / social_dining / late_night。"""
        out: List[Dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            tags = str(it.get("tags") or "")
            desc = str(it.get("description") or "")
            cat = str(it.get("category") or "")
            text = f"{tags} {desc} {cat}"
            if not any(kw in text for kw in FOOD_KEYWORDS):
                continue
            dt = cls._parse_ts(it)
            try:
                val = abs(float(it.get("value") or 0.0))
            except (ValueError, TypeError):
                val = 0.0
            subtypes: List[str] = []
            if any(kw in text for kw in SNACK_DRINK_KEYWORDS):
                subtypes.append("snack_drink")
            if any(kw in text for kw in SOCIAL_DINING_KEYWORDS) or val >= 120.0:
                subtypes.append("social_dining")
            if any(kw in text for kw in TAKEOUT_KEYWORDS):
                subtypes.append("takeout")
            if dt is not None and (dt.hour >= 21 or dt.hour < 4):
                subtypes.append("late_night")
            if not subtypes:
                subtypes.append("regular_meal")
            out.append(
                {
                    "time": dt.strftime("%Y-%m-%d %H:%M") if dt else str(it.get("htime", "")),
                    "date": dt.strftime("%Y-%m-%d") if dt else "",
                    "weekday": dt.weekday() if dt else None,  # 0=Mon .. 6=Sun
                    "hour": dt.hour if dt else None,
                    "value": round(val, 2),
                    "tags": tags,
                    "description": desc[:80],
                    "subtypes": subtypes,
                }
            )
        return out

    # ── 体重监控分析 ──────────────────────────────────────────────────

    @staticmethod
    def _parse_ts(item: Dict[str, Any]) -> Optional[datetime]:
        ht = item.get("htime")
        if isinstance(ht, (int, float)) and ht > 0:
            try:
                return datetime.fromtimestamp(float(ht))
            except (ValueError, OSError):
                pass
        for key in ("time", "date", "created_at"):
            v = item.get(key)
            if isinstance(v, str) and v.strip():
                try:
                    dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
                    return dt.replace(tzinfo=None) if dt.tzinfo else dt
                except ValueError:
                    try:
                        return datetime.strptime(v[:10], "%Y-%m-%d")
                    except ValueError:
                        continue
        return None

    @classmethod
    def _compute_weight_monitor(
        cls,
        series: Optional[List[Dict[str, Any]]],
        plan_progress: Optional[Dict[str, Any]],
        now: datetime,
    ) -> Dict[str, Any]:
        """构建体重更新监控摘要：最新值、距上次测量小时数、7日均值、趋势、异常波动预警。"""
        summary: Dict[str, Any] = {
            "record_count": 0,
            "latest_kg": None,
            "latest_id": None,
            "latest_at": None,
            "hours_since_last": None,
            "recorded_today": False,
            "delta_from_prev": None,
            "avg_7d": None,
            "trend_7d": "unknown",
            "needs_weight_nudge": False,
            "rapid_swing_alert": False,
        }
        if not series:
            summary["needs_weight_nudge"] = True
            return summary

        parsed: List[tuple[Optional[datetime], float, Any]] = []
        for item in series:
            val = item.get("value")
            if val is None:
                val = item.get("weight")
            try:
                fval = float(val)
            except (ValueError, TypeError):
                continue
            dt = cls._parse_ts(item)
            parsed.append((dt, fval, item.get("id")))

        if not parsed:
            summary["needs_weight_nudge"] = True
            return summary

        # 按时间升序
        parsed.sort(key=lambda x: x[0] or datetime.min)
        latest_dt, latest_val, latest_id = parsed[-1]
        summary["record_count"] = len(parsed)
        summary["latest_kg"] = round(latest_val, 2)
        summary["latest_id"] = latest_id
        if latest_dt is not None:
            summary["latest_at"] = latest_dt.strftime("%Y-%m-%d %H:%M")
            hours_ago = max(0.0, (now - latest_dt).total_seconds() / 3600.0)
            summary["hours_since_last"] = round(hours_ago, 1)
            summary["recorded_today"] = latest_dt.date() == now.date()
            summary["needs_weight_nudge"] = hours_ago >= 36.0

        if len(parsed) >= 2:
            prev_dt, prev_val, _ = parsed[-2]
            delta = round(latest_val - prev_val, 2)
            summary["delta_from_prev"] = delta
            if abs(delta) >= 1.5 and latest_dt and prev_dt:
                if (latest_dt - prev_dt).total_seconds() <= 36 * 3600:
                    summary["rapid_swing_alert"] = True

        recent_vals = [v for _, v, _ in parsed[-7:]]
        summary["avg_7d"] = round(sum(recent_vals) / len(recent_vals), 2)
        if len(parsed) >= 2:
            net = parsed[-1][1] - parsed[0][1]
            if net <= -0.3:
                summary["trend_7d"] = "decreasing"
            elif net >= 0.3:
                summary["trend_7d"] = "increasing"
            else:
                summary["trend_7d"] = "stable"

        if isinstance(plan_progress, dict) and plan_progress.get("plan"):
            p = plan_progress["plan"]
            summary["plan_target_kg"] = p.get("targetWeight") or p.get("target_weight")
            summary["plan_expected_today_kg"] = plan_progress.get("expected_current_weight")
            summary["plan_managed_by"] = p.get("managedBy") or p.get("managed_by") or "manual"
            summary["plan_phase"] = p.get("phaseName") or p.get("phase_name") or ""

        return summary

    # ── 精简与截断 ────────────────────────────────────────────────────

    @classmethod
    def _simplify_series(cls, raw: Any, limit: int = 21) -> Optional[List[Dict[str, Any]]]:
        if raw is None:
            return None
        items: List[Any] = []
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            # 兼容 BodyDataSeriesResponse {"points": [...]} 及其他包装结构
            items = (
                raw.get("points")
                or raw.get("items")
                or raw.get("data")
                or raw.get("series")
                or raw.get("weights")
                or []
            )
        out = []
        for it in items[-limit:]:
            if not isinstance(it, dict):
                continue
            val = it.get("value")
            if val is None and isinstance(it.get("data"), dict):
                val = it["data"].get("weight")
            if val is None:
                val = it.get("weight")
            if val is None:
                continue
            row: Dict[str, Any] = {"value": val}
            if "id" in it:
                row["id"] = it["id"]
            dt = cls._parse_ts(it)
            if dt is not None:
                row["date"] = dt.strftime("%Y-%m-%d %H:%M")
                row["htime"] = dt.timestamp()
            elif "date" in it:
                row["date"] = it["date"]
            if it.get("note") or it.get("description"):
                row["note"] = (it.get("note") or it.get("description"))[:80]
            out.append(row)
        return out

    @classmethod
    def _simplify_diet(cls, raw: Any, limit: int = 25) -> Optional[List[Dict[str, Any]]]:
        if raw is None:
            return None
        items = raw if isinstance(raw, list) else (raw.get("items") or raw.get("data") or [])
        out = []
        for it in items[:limit]:
            if not isinstance(it, dict):
                continue
            dt = cls._parse_ts(it)
            row: Dict[str, Any] = {
                "meal_type": it.get("meal_type", "snack"),
                "description": str(it.get("description") or "")[:120],
            }
            if dt:
                row["time"] = dt.strftime("%Y-%m-%d %H:%M")
            if it.get("calories") is not None:
                row["calories"] = it["calories"]
            if it.get("protein") is not None:
                row["protein"] = it["protein"]
            out.append(row)
        return out

    @staticmethod
    def _simplify_messages(raw: Any, limit: int = 30) -> Optional[List[Dict[str, Any]]]:
        if raw is None:
            return None
        items = raw if isinstance(raw, list) else (raw.get("items") or [])
        out = []
        for it in items[:limit]:
            if not isinstance(it, dict):
                continue
            raw_meta = it.get("meta") if isinstance(it.get("meta"), dict) else {}
            compact_meta: Dict[str, Any] = {}
            for k in ("meal_type", "scene", "coach_advice", "draft_id"):
                if raw_meta.get(k) not in (None, ""):
                    compact_meta[k] = raw_meta[k]
            out.append(
                {
                    "id": it.get("id"),
                    "category": it.get("category", "general"),
                    "content": str(it.get("content") or "")[:240],
                    "meta": compact_meta,
                    "created_at": str(it.get("created_at") or "")[:19],
                }
            )
        return out

    @staticmethod
    def _simplify_plan(raw: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(raw, dict) or not raw.get("plan"):
            return None
        p = raw["plan"]
        return {
            "id": p.get("id"),
            "target_weight": p.get("targetWeight") or p.get("target_weight"),
            "initial_weight": p.get("initialWeight") or p.get("initial_weight"),
            "curve_type": p.get("curveType") or p.get("curve_type"),
            "managed_by": p.get("managedBy") or p.get("managed_by") or "manual",
            "plan_version": p.get("planVersion") or p.get("plan_version") or "",
            "phase_name": p.get("phaseName") or p.get("phase_name") or "",
            "tolerance_kg": p.get("toleranceKg") or p.get("tolerance_kg") or 0.5,
            "ai_summary": p.get("aiSummary") or p.get("ai_summary") or "",
            "expected_current_weight": raw.get("expected_current_weight"),
            "control_rate": raw.get("control_rate"),
            "is_on_track": raw.get("is_on_track"),
        }

    @classmethod
    def _filter_food_transactions(cls, raw: Any, limit: int = 12) -> Optional[List[Dict[str, Any]]]:
        if raw is None:
            return None
        items = raw if isinstance(raw, list) else (raw.get("items") or raw.get("data") or [])
        out = []
        for it in items:
            if not isinstance(it, dict):
                continue
            text = f"{it.get('tags', '')} {it.get('description', '')} {it.get('category', '')}"
            if any(kw in text for kw in FOOD_KEYWORDS):
                dt = cls._parse_ts(it)
                out.append(
                    {
                        "time": dt.strftime("%Y-%m-%d %H:%M") if dt else str(it.get("htime", "")),
                        "value": it.get("value"),
                        "tags": it.get("tags", ""),
                        "description": str(it.get("description") or "")[:60],
                    }
                )
            if len(out) >= limit:
                break
        return out

    @classmethod
    def _simplify_list(cls, raw: Any, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
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
                row = {k: v for k, v in list(it.items())[:6]}
                dt = cls._parse_ts(it)
                if dt and "time" not in row and "date" not in row:
                    row["time"] = dt.strftime("%Y-%m-%d %H:%M")
                out.append(row)
        return out

    @staticmethod
    def _simplify_blocks(blocks: Any, limit: int = 16) -> List[Dict[str, Any]]:
        if not isinstance(blocks, list):
            return []
        out: List[Dict[str, Any]] = []
        for b in blocks[:limit]:
            if not isinstance(b, dict):
                continue
            ref = b.get("ref") if isinstance(b.get("ref"), dict) else {}
            start_s = str(b.get("start_time") or "")
            end_s = str(b.get("end_time") or "")
            out.append(
                {
                    "id": b.get("id"),
                    "affair_id": b.get("affair_id"),
                    "title": b.get("affair_title") or ref.get("label") or b.get("block_type") or "",
                    "type": b.get("block_type"),
                    "start": start_s[11:16] if len(start_s) >= 16 else start_s,
                    "end": end_s[11:16] if len(end_s) >= 16 else end_s,
                    "status": b.get("status"),
                    "pinned": bool(b.get("pinned")),
                }
            )
        return out

    @classmethod
    def _simplify_rhythm(
        cls,
        dash_raw: Any,
        tomorrow_raw: Any,
        today_str: str,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(dash_raw, dict):
            return None
        tl = dash_raw.get("timeline") if isinstance(dash_raw.get("timeline"), dict) else {}
        projects_out: List[Dict[str, Any]] = []
        for p in (dash_raw.get("projects") or [])[:8]:
            if not isinstance(p, dict):
                continue
            ms = p.get("milestones") or []
            pending_ms = [
                {"id": m.get("id"), "title": m.get("title")}
                for m in ms
                if isinstance(m, dict) and m.get("state") not in ("DONE", "CANCELED")
            ][:3]
            projects_out.append(
                {
                    "id": p.get("affair_id"),
                    "title": p.get("title"),
                    "target_date": p.get("target_date"),
                    "days_left": p.get("days_left"),
                    "completion": p.get("completion_ratio"),
                    "recent_14d_hours": p.get("recent_14d_hours"),
                    "next_milestones": pending_ms,
                }
            )

        def _compact_affairs(raw_list: Any, limit: int) -> List[Dict[str, Any]]:
            if not isinstance(raw_list, list):
                return []
            res = []
            for a in raw_list[:limit]:
                if not isinstance(a, dict):
                    continue
                res.append(
                    {
                        "id": a.get("id"),
                        "title": a.get("title"),
                        "kind": a.get("kind"),
                        "state": a.get("state"),
                        "ddl": str(a.get("urgency_ddl") or "")[:16] or None,
                        "est_minutes": a.get("est_minutes"),
                    }
                )
            return res

        return {
            "today_date": today_str,
            "ai_rationale": tl.get("ai_rationale") or "",
            "completed_minutes": tl.get("completed_minutes", 0),
            "planned_minutes": tl.get("planned_minutes", 0),
            "today_blocks": cls._simplify_blocks(tl.get("blocks"), limit=16),
            "tomorrow_blocks": cls._simplify_blocks(
                tomorrow_raw.get("blocks") if isinstance(tomorrow_raw, dict) else [],
                limit=10,
            ),
            "projects": projects_out,
            "focus_affairs": _compact_affairs(dash_raw.get("focus_affairs"), 10),
            "overdue_affairs": _compact_affairs(dash_raw.get("overdue_affairs"), 6),
            "inbox_affairs": _compact_affairs(dash_raw.get("inbox_affairs"), 6),
            "occupancies": [
                {
                    "id": o.get("id"),
                    "start": o.get("start"),
                    "end": o.get("end"),
                    "type": o.get("occupancy_type"),
                    "label": o.get("label"),
                }
                for o in (dash_raw.get("occupancies") or [])[:6]
                if isinstance(o, dict)
            ],
        }

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

        wm = package.get("weight_monitor") or {}
        if wm.get("latest_kg") is not None:
            parts = [f"最新 {wm['latest_kg']}kg"]
            if wm.get("latest_at"):
                parts.append(f"时间 {wm['latest_at']}")
            if wm.get("delta_from_prev") is not None:
                parts.append(f"较上次 {wm['delta_from_prev']:+.2f}kg")
            if wm.get("avg_7d") is not None:
                parts.append(f"7日均 {wm['avg_7d']}kg ({wm.get('trend_7d', 'unknown')})")
            if wm.get("recorded_today"):
                parts.append("今日已称重")
            elif wm.get("needs_weight_nudge"):
                parts.append(f"已 {wm.get('hours_since_last')}h 未称重（可温和提醒）")
            if wm.get("rapid_swing_alert"):
                parts.append("⚠ 24h 波动较大，先关切饮水/睡眠/压力")
            lines.append("体重监控: " + "，".join(parts))
        else:
            lines.append("体重监控: 最近窗口无体重记录（需要温和建立基线）")

        ap = package.get("active_plan")
        if isinstance(ap, dict):
            lines.append(
                f"当前健康页计划: managed_by={ap.get('managed_by')} curve={ap.get('curve_type')} "
                f"target={ap.get('target_weight')}kg phase={ap.get('phase_name') or '(未设)'} "
                f"expected_today={ap.get('expected_current_weight')}kg"
            )
        else:
            lines.append("当前健康页计划: 暂无活跃计划（可由 SailTick 创建 AI 动态计划）")

        diet = package.get("diet") or []
        if diet:
            preview = "; ".join(
                f"[{d.get('time', '')[5:16]} {d.get('meal_type')}] {d.get('description', '')}"
                for d in diet[:8]
            )
            lines.append(f"饮食记录({len(diet)}条): {preview}")

        msgs = package.get("user_messages") or []
        if msgs:
            preview = "; ".join(
                f"#{m.get('id')}[{m.get('category')}] {m.get('content', '')}"
                for m in msgs[:10]
            )
            lines.append(f"用户主动发来的待整合消息({len(msgs)}条): {preview}")

        rhythm = package.get("rhythm")
        if isinstance(rhythm, dict):
            t_blocks = rhythm.get("today_blocks") or []
            if t_blocks:
                blk_str = "; ".join(
                    f"#{b.get('id')}[{b.get('start')}-{b.get('end')} {b.get('status')}{' 📌' if b.get('pinned') else ''}] {b.get('title')}"
                    for b in t_blocks[:10]
                )
                lines.append(
                    f"今日日程({rhythm.get('today_date')}, 已完成{rhythm.get('completed_minutes', 0)}/{rhythm.get('planned_minutes', 0)}min): {blk_str}"
                )
            else:
                lines.append(f"今日日程({rhythm.get('today_date')}): 尚未排布（可由 SailTick 通过 rhythm_sync_timeline 自主落库）")
            if rhythm.get("ai_rationale"):
                lines.append(f"当前日程排布说明: {rhythm['ai_rationale']}")
            occs = rhythm.get("occupancies") or []
            if occs:
                occ_str = "; ".join(f"{o.get('start')}-{o.get('end')} {o.get('label')}" for o in occs)
                lines.append(f"今日刚性占用(会议/请假): {occ_str}")
            projs = rhythm.get("projects") or []
            if projs:
                proj_str = "; ".join(
                    f"#{p.get('id')}「{p.get('title')}」(目标:{p.get('target_date') or '未定'}, 剩{p.get('days_left')}天, 完成{int((p.get('completion') or 0)*100)}%, 近14d:{p.get('recent_14d_hours')}h)"
                    for p in projs[:6]
                )
                lines.append(f"活跃重要项目({len(projs)}个): {proj_str}")
            overdue = rhythm.get("overdue_affairs") or []
            if overdue:
                ov_str = "; ".join(f"#{a.get('id')}{a.get('title')}(ddl:{a.get('ddl')})" for a in overdue[:5])
                lines.append(f"逾期事务({len(overdue)}项): {ov_str}")
            focus = rhythm.get("focus_affairs") or []
            if focus:
                f_str = "; ".join(
                    f"#{a.get('id')}{a.get('title')}({a.get('est_minutes')}min{', ddl:'+str(a.get('ddl')) if a.get('ddl') else ''})"
                    for a in focus[:8]
                )
                lines.append(f"待办焦点({len(focus)}项): {f_str}")
            inbox_af = rhythm.get("inbox_affairs") or []
            if inbox_af:
                ib_str = "; ".join(f"#{a.get('id')}{a.get('title')}" for a in inbox_af[:5])
                lines.append(f"待整理随手记({len(inbox_af)}项): {ib_str}")

        for key, label in (
            ("sleep", "睡眠"),
            ("exercise", "运动"),
            ("mood", "心情"),
            ("finance_food", "餐饮消费"),
            ("rhythm_checkins", "打卡"),
        ):
            items = package.get(key)
            if items:
                lines.append(f"{label}: {len(items)} 条记录")
        return "\n".join(lines)
