# -*- coding: utf-8 -*-
# @file telemetry_collector.py
# @brief In-memory API performance/usage telemetry collector with periodic DB flush
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""SailZen 服务端轻量 API 性能/使用埋点收集器。

设计要点：
- 零同步 DB 开销：每次 HTTP 请求仅在内存中做 O(1) 计数和有界采样（threading.Lock 极短临界区）
- 路径规范化：将数字 ID / UUID 替换为 `{id}`，自动归属到 SailZen 业务模块
- 定期刷盘（默认每 30 秒 + 停机兜底）：upsert 到 `sys_api_metric_buckets`，同时落盘慢请求/5xx 离散事件到 `sys_telemetry_events`
- 实时可见：读取统计时自动合并 DB 已刷盘数据与内存未刷盘增量
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 超过该耗时（ms）的请求记录为慢请求事件
SLOW_REQUEST_THRESHOLD_MS = float(os.environ.get("TELEMETRY_SLOW_MS", "300"))
# 刷盘周期（秒）
FLUSH_INTERVAL_SECONDS = int(os.environ.get("TELEMETRY_FLUSH_SECONDS", "30"))
# 单桶内存样本上限（用于计算 P50/P95/P99）
MAX_SAMPLES_PER_BUCKET = 512

_UUID_RE = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?=/|$)"
)
_HEX32_RE = re.compile(r"/[0-9a-fA-F]{24,64}(?=/|$)")
_INT_ID_RE = re.compile(r"/\d+(?=/|$)")
_DATE_RE = re.compile(r"/\d{4}-\d{2}-\d{2}(?=/|$)")
_RELEASE_DOWNLOAD_RE = re.compile(r"^(/api/v\d+/(?:app|workbench)/release/download/)[^/]+$")


def is_binary_download_endpoint(endpoint: str) -> bool:
    """判断是否为大文件/二进制下载端点（不计入常规 API 慢请求告警，避免污染业务慢接口榜单）。"""
    lower = (endpoint or "").lower()
    return (
        "/app/release/download/" in lower
        or lower.endswith("/app/release/latest.apk")
        or "/workbench/release/download/" in lower
        or lower.endswith("/workbench/release/latest.vsix")
        or (("/file_storage/" in lower or "/file-storage/" in lower) and "/download" in lower)
    )

KNOWN_MODULES = {
    "finance": "finance",
    "health": "health",
    "rhythm": "rhythm",
    "tick": "tick",
    "text": "text",
    "necessity": "necessity",
    "file-storage": "file_storage",
    "file_storage": "file_storage",
    "blog": "blog",
    "life": "life",
    "reminder": "reminder",
    "history": "history",
    "app": "app_release",
    "workbench": "workbench",
    "user": "user",
    "inbox": "inbox",
    "telemetry": "telemetry",
}


def normalize_api_path(path: str) -> Tuple[str, str]:
    """将请求路径规范化为 (module, normalized_endpoint)。"""
    clean = path.split("?", 1)[0].rstrip("/") or "/"
    parts = [p for p in clean.split("/") if p]
    module = "system"
    if len(parts) >= 3 and parts[0] == "api" and parts[1].startswith("v"):
        seg = parts[2].lower()
        module = KNOWN_MODULES.get(seg, seg)
    elif parts:
        module = KNOWN_MODULES.get(parts[0].lower(), "system")

    norm = _UUID_RE.sub("/{uuid}", clean)
    norm = _HEX32_RE.sub("/{id}", norm)
    norm = _DATE_RE.sub("/{date}", norm)
    norm = _INT_ID_RE.sub("/{id}", norm)
    norm = _RELEASE_DOWNLOAD_RE.sub(r"\1{filename}", norm)
    return module, norm[:256]


def infer_client_source(headers: list) -> str:
    """根据请求头推断客户端来源：web | android | sailtick | cli | other。"""
    hdr_map: Dict[str, str] = {}
    for k, v in headers or []:
        try:
            key = k.decode("latin1").lower() if isinstance(k, (bytes, bytearray)) else str(k).lower()
            val = v.decode("latin1") if isinstance(v, (bytes, bytearray)) else str(v)
            hdr_map[key] = val
        except Exception:
            continue

    explicit = hdr_map.get("x-sailzen-client", "").strip().lower()
    if explicit in ("web", "android", "sailtick", "cli", "vscode"):
        return explicit

    ua = hdr_map.get("user-agent", "").lower()
    if "okhttp" in ua or "sailzen-android" in ua or "android" in ua:
        return "android"
    if "python-httpx" in ua or "sailtick" in ua:
        return "sailtick"
    if "sailzen-cli" in ua or "python-requests" in ua or "curl" in ua:
        return "cli"
    if "mozilla" in ua or "chrome" in ua or "safari" in ua or "firefox" in ua or "edge" in ua:
        return "web"
    return "other"


def percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return round(sorted_vals[f], 2)
    return round(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f), 2)


@dataclass
class _BucketAccumulator:
    bucket_hour: datetime
    module: str
    method: str
    endpoint: str
    client_source: str
    req_count: int = 0
    err_4xx: int = 0
    err_5xx: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    bytes_out: int = 0
    samples: List[float] = field(default_factory=list)

    def add(self, status_code: int, duration_ms: float, bytes_out: int) -> None:
        self.req_count += 1
        if 400 <= status_code < 500:
            self.err_4xx += 1
        elif status_code >= 500:
            self.err_5xx += 1
        self.total_ms += duration_ms
        if duration_ms > self.max_ms:
            self.max_ms = duration_ms
        self.bytes_out += max(0, int(bytes_out))
        if len(self.samples) < MAX_SAMPLES_PER_BUCKET:
            self.samples.append(duration_ms)
        else:
            # 简单确定性抽样替换，保持代表性
            idx = self.req_count % MAX_SAMPLES_PER_BUCKET
            self.samples[idx] = duration_ms

    def snapshot_dict(self) -> Dict[str, Any]:
        s = sorted(self.samples)
        return {
            "bucket_hour": self.bucket_hour,
            "module": self.module,
            "method": self.method,
            "endpoint": self.endpoint,
            "client_source": self.client_source,
            "req_count": self.req_count,
            "err_4xx": self.err_4xx,
            "err_5xx": self.err_5xx,
            "total_ms": round(self.total_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "p50_ms": percentile(s, 50),
            "p95_ms": percentile(s, 95),
            "p99_ms": percentile(s, 99),
            "bytes_out": self.bytes_out,
        }


BucketKey = Tuple[datetime, str, str, str, str]


class TelemetryCollector:
    """线程安全的服务端埋点聚合器。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: Dict[BucketKey, _BucketAccumulator] = {}
        self._pending_events: Deque[Dict[str, Any]] = deque(maxlen=500)
        self._recent_notable: Deque[Dict[str, Any]] = deque(maxlen=200)
        self.started_at: datetime = datetime.now()
        self._started_mono: float = time.monotonic()
        self._total_requests_since_boot: int = 0
        self._total_errors_since_boot: int = 0
        self._last_flush_at: Optional[datetime] = None

    @property
    def uptime_seconds(self) -> float:
        return round(time.monotonic() - self._started_mono, 1)

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        bytes_out: int = 0,
        headers: Optional[list] = None,
        error_detail: Optional[str] = None,
    ) -> None:
        """记录单次 HTTP API 请求（仅追踪 /api/*，避免静态文件噪音）。"""
        if not path.startswith("/api/"):
            return
        module, endpoint = normalize_api_path(path)
        client_source = infer_client_source(headers or [])
        now = datetime.now()
        bucket_hour = now.replace(minute=0, second=0, microsecond=0)
        key: BucketKey = (bucket_hour, module, method.upper()[:12], endpoint, client_source)

        is_error = status_code >= 500 or error_detail is not None
        is_slow = (
            duration_ms >= SLOW_REQUEST_THRESHOLD_MS
            and module != "telemetry"
            and not is_binary_download_endpoint(endpoint)
        )

        with self._lock:
            self._total_requests_since_boot += 1
            if status_code >= 500:
                self._total_errors_since_boot += 1
            acc = self._buckets.get(key)
            if acc is None:
                acc = _BucketAccumulator(
                    bucket_hour=bucket_hour,
                    module=module,
                    method=method.upper()[:12],
                    endpoint=endpoint,
                    client_source=client_source,
                )
                self._buckets[key] = acc
            acc.add(status_code, round(float(duration_ms), 2), bytes_out)

            if is_error or is_slow:
                evt = {
                    "category": "api_error" if is_error else "api_slow",
                    "module": module,
                    "name": f"{method.upper()} {endpoint}",
                    "client_source": client_source,
                    "duration_ms": round(float(duration_ms), 2),
                    "status_code": int(status_code),
                    "value": None,
                    "detail": {
                        "raw_path": path[:300],
                        "bytes_out": int(bytes_out),
                        "error": (error_detail or "")[:500] if error_detail else None,
                    },
                    "created_at": now,
                }
                self._pending_events.append(evt)
                self._recent_notable.appendleft(evt)

    def snapshot_unflushed_buckets(self) -> List[Dict[str, Any]]:
        """只读快照当前未刷盘的内存桶（用于查询合并）。"""
        with self._lock:
            return [acc.snapshot_dict() for acc in self._buckets.values()]

    def snapshot_recent_notable(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._recent_notable)[:limit]

    def runtime_counters(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "started_at": self.started_at.isoformat(),
                "uptime_seconds": self.uptime_seconds,
                "total_requests_since_boot": self._total_requests_since_boot,
                "total_errors_since_boot": self._total_errors_since_boot,
                "unflushed_buckets": len(self._buckets),
                "pending_events": len(self._pending_events),
                "last_flush_at": self._last_flush_at.isoformat() if self._last_flush_at else None,
            }

    def flush_to_db(self, db_session_factory: Callable[[], Any]) -> int:
        """将内存中累计的小时桶和离散事件批量写入数据库。"""
        with self._lock:
            if not self._buckets and not self._pending_events:
                return 0
            buckets_to_flush = [acc.snapshot_dict() for acc in self._buckets.values()]
            self._buckets.clear()
            events_to_flush = list(self._pending_events)
            self._pending_events.clear()

        from sailzen_orm.telemetry import SysApiMetricBucket, SysTelemetryEvent

        flushed = 0
        db = db_session_factory()
        try:
            for b in buckets_to_flush:
                existing = (
                    db.query(SysApiMetricBucket)
                    .filter(
                        SysApiMetricBucket.bucket_hour == b["bucket_hour"],
                        SysApiMetricBucket.module == b["module"],
                        SysApiMetricBucket.method == b["method"],
                        SysApiMetricBucket.endpoint == b["endpoint"],
                        SysApiMetricBucket.client_source == b["client_source"],
                    )
                    .first()
                )
                if existing is None:
                    row = SysApiMetricBucket(
                        bucket_hour=b["bucket_hour"],
                        module=b["module"],
                        method=b["method"],
                        endpoint=b["endpoint"],
                        client_source=b["client_source"],
                        req_count=b["req_count"],
                        err_4xx=b["err_4xx"],
                        err_5xx=b["err_5xx"],
                        total_ms=b["total_ms"],
                        max_ms=b["max_ms"],
                        p50_ms=b["p50_ms"],
                        p95_ms=b["p95_ms"],
                        p99_ms=b["p99_ms"],
                        bytes_out=b["bytes_out"],
                    )
                    db.add(row)
                else:
                    prev_n = int(existing.req_count or 0)
                    add_n = int(b["req_count"])
                    tot_n = max(1, prev_n + add_n)
                    existing.req_count = prev_n + add_n
                    existing.err_4xx = int(existing.err_4xx or 0) + int(b["err_4xx"])
                    existing.err_5xx = int(existing.err_5xx or 0) + int(b["err_5xx"])
                    existing.total_ms = round(float(existing.total_ms or 0.0) + float(b["total_ms"]), 2)
                    existing.max_ms = round(max(float(existing.max_ms or 0.0), float(b["max_ms"])), 2)
                    # 加权近似融合历史分位数，P99 取保守上界
                    existing.p50_ms = round(
                        (float(existing.p50_ms or 0.0) * prev_n + float(b["p50_ms"]) * add_n) / tot_n,
                        2,
                    )
                    existing.p95_ms = round(
                        (float(existing.p95_ms or 0.0) * prev_n + float(b["p95_ms"]) * add_n) / tot_n,
                        2,
                    )
                    existing.p99_ms = round(max(float(existing.p99_ms or 0.0), float(b["p99_ms"])), 2)
                    existing.bytes_out = int(existing.bytes_out or 0) + int(b["bytes_out"])
                    existing.updated_at = datetime.now()
                flushed += 1

            for evt in events_to_flush:
                db.add(
                    SysTelemetryEvent(
                        category=evt["category"],
                        module=evt["module"],
                        name=evt["name"],
                        client_source=evt["client_source"],
                        duration_ms=evt.get("duration_ms"),
                        status_code=evt.get("status_code"),
                        value=evt.get("value"),
                        detail=evt.get("detail") or {},
                        created_at=evt.get("created_at") or datetime.now(),
                    )
                )
                flushed += 1

            db.commit()
            with self._lock:
                self._last_flush_at = datetime.now()
        except Exception as exc:
            logger.warning("[telemetry] flush_to_db failed (non-fatal): %s", exc)
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()
        return flushed

    def reset_for_tests(self) -> None:
        with self._lock:
            self._buckets.clear()
            self._pending_events.clear()
            self._recent_notable.clear()
            self._total_requests_since_boot = 0
            self._total_errors_since_boot = 0
            self._last_flush_at = None


_collector: Optional[TelemetryCollector] = None


def get_telemetry_collector() -> TelemetryCollector:
    global _collector
    if _collector is None:
        _collector = TelemetryCollector()
    return _collector


async def telemetry_flush_loop(
    db_session_factory: Callable[[], Any],
    interval_seconds: int = FLUSH_INTERVAL_SECONDS,
) -> None:
    """后台定期刷盘循环，同时按日低频清理超期（>90天）埋点数据。"""
    collector = get_telemetry_collector()
    last_prune_day: Optional[str] = None
    while True:
        try:
            await asyncio.sleep(max(5, int(interval_seconds)))
            await asyncio.to_thread(collector.flush_to_db, db_session_factory)
            today = datetime.now().strftime("%Y-%m-%d")
            if last_prune_day != today:
                last_prune_day = today
                await asyncio.to_thread(_prune_expired_records, db_session_factory, 90)
        except asyncio.CancelledError:
            # 停机前尽力做最后一次刷盘
            try:
                collector.flush_to_db(db_session_factory)
            except Exception:
                pass
            raise
        except Exception as exc:
            logger.warning("[telemetry] flush loop error: %s", exc)


def _prune_expired_records(db_session_factory: Callable[[], Any], keep_days: int = 90) -> None:
    """清理超过 keep_days 天的旧埋点，保证长期运行数据库体积可控。"""
    from sailzen_orm.telemetry import SysApiMetricBucket, SysTelemetryEvent

    cutoff = datetime.now() - timedelta(days=keep_days)
    db = db_session_factory()
    try:
        db.query(SysTelemetryEvent).filter(SysTelemetryEvent.created_at < cutoff).delete(
            synchronize_session=False
        )
        db.query(SysApiMetricBucket).filter(SysApiMetricBucket.bucket_hour < cutoff).delete(
            synchronize_session=False
        )
        db.commit()
    except Exception as exc:
        logger.debug("[telemetry] prune skipped: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()
