# -*- coding: utf-8 -*-
# @file weather.py
# @brief Weather Model Layer (query / update / record consolidation / loop)
# @author sailing-innocent
# @date 2026-07-20
# @version 1.0
# ---------------------------------

"""
天气业务模型层

天气数据不建表，整体存入 Day ORM 的 JSONB ``ref["weather"]``::

    {
        "updated_at": "2026-07-18T08:30:00+08:00",
        "cities": {
            "杭州": {
                "kind": "forecast" | "record",
                "weather_code": 61,
                "temp_max": 33.5, "temp_min": 26.1,
                "temp_current": None, "humidity": None, "wind_speed": None,
                "source": "open-meteo" | "open-meteo-archive",
                "fetched_at": "2026-07-19T00:10:00+08:00",
            },
        },
    }

固化策略（每次更新循环对每个配置城市执行）：

1. 拉取 forecast（含 current 与 daily），对 [today, today+N) 每个日期
   upsert ``kind=forecast`` 数据（覆盖写，逐步更新）。
2. 对 [today-lookback, today-1] 范围内仍非 record 的日期补拉 archive，
   写入 ``kind=record`` —— 实现"当天过去后留下天气记录"；record 写入后
   不可变，后续任何写入都会跳过。
3. 所有写库按 get -> merge -> assign 模式更新 ``day.ref``（整体重新赋值
   以触发 SQLAlchemy JSONB 变更检测），保留 ref 其他 key；单城市失败
   只记日志与 errors，不影响其他城市。

时区：today 判定统一使用 Asia/Shanghai（与 Open-Meteo timezone 参数、
journal 日期语义一致），服务器可部署在任意时区。
"""

import asyncio
import json
import logging
import os
import random
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from sail_server.application.dto.weather import (
    CityWeather,
    DayWeatherResponse,
    WeatherRefreshResponse,
)
from sail_server.infrastructure.orm.life import Day
from sail_server.utils.weather import WeatherFetchError, fetch_archive, fetch_forecast

logger = logging.getLogger(__name__)

# ============================================================================
# Constants & Configuration
# ============================================================================

WEATHER_REF_KEY = "weather"

SH_TZ = ZoneInfo("Asia/Shanghai")

DEFAULT_FORECAST_DAYS = 7
DEFAULT_RECORD_LOOKBACK_DAYS = 3
DEFAULT_UPDATE_INTERVAL_MINUTES = 60
MAX_BACKOFF_SECONDS = 30 * 60


@dataclass(frozen=True)
class CitySpec:
    """天气跟踪城市（名称 + 经纬度）"""

    name: str
    latitude: float
    longitude: float


DEFAULT_CITIES: List[CitySpec] = [
    CitySpec(name="杭州", latitude=30.2741, longitude=120.1551),
    CitySpec(name="上海", latitude=31.2304, longitude=121.4737),
    CitySpec(name="合肥", latitude=31.8206, longitude=117.2272),
]


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"[weather] invalid int env {name}={raw!r}, use {default}")
        return default


def read_cities_from_env() -> List[CitySpec]:
    """解析 WEATHER_CITIES（JSON 数组），缺省/解析失败回退 DEFAULT_CITIES"""
    raw = os.environ.get("WEATHER_CITIES")
    if not raw:
        return list(DEFAULT_CITIES)
    try:
        data = json.loads(raw)
        cities = [
            CitySpec(
                name=str(c["name"]),
                latitude=float(c["latitude"]),
                longitude=float(c["longitude"]),
            )
            for c in data
        ]
        if cities:
            return cities
        logger.warning("[weather] WEATHER_CITIES is empty, fallback to defaults")
        return list(DEFAULT_CITIES)
    except Exception as e:
        logger.error(f"[weather] failed to parse WEATHER_CITIES: {e}; use defaults")
        return list(DEFAULT_CITIES)


def _today_sh() -> date_type:
    """Asia/Shanghai 时区下的今天"""
    return datetime.now(SH_TZ).date()


# ============================================================================
# Query
# ============================================================================


def get_day_weather_impl(
    db: Session,
    query_date: date_type,
    today: Optional[date_type] = None,
) -> DayWeatherResponse:
    """查询某日天气。

    day 不存在或无天气数据时返回 ``available=False``（HTTP 200，由插件
    渲染"暂无数据"，不走错误路径）。
    """
    today = today or _today_sh()
    kind = "record" if query_date < today else "forecast"

    day = db.query(Day).filter(Day.date == query_date).first()
    if day is None:
        return DayWeatherResponse(
            date=query_date, available=False, kind=kind, cities=[], updated_at=None
        )

    weather = (day.ref or {}).get(WEATHER_REF_KEY) or {}
    cities_map = weather.get("cities") or {}
    cities: List[CityWeather] = []
    for name, payload in cities_map.items():
        if not isinstance(payload, dict):
            continue
        # 容错：只接受 CityWeather 认识的字段，丢弃存储中的冗余 key
        known = {k: v for k, v in payload.items() if k in CityWeather.model_fields}
        if known.get("kind") not in ("forecast", "record"):
            known["kind"] = "forecast"  # 存储中的非法 kind 兜底，避免校验失败
        cities.append(CityWeather(city=name, **known))

    updated_at = weather.get("updated_at")
    return DayWeatherResponse(
        date=query_date,
        available=len(cities) > 0,
        kind=kind,
        cities=cities,
        updated_at=updated_at,
    )


# ============================================================================
# Update (forecast refresh + record consolidation)
# ============================================================================


def _write_city_weather(
    db: Session,
    day_date: date_type,
    city_name: str,
    entry: Dict[str, Any],
) -> bool:
    """把单城市天气写入指定日期的 Day.ref['weather']（merge 语义）。

    record 不可变：已有 ``kind == "record"`` 的数据一律跳过。
    ref 中的其他 key 原样保留；``day.ref`` 整体重新赋值以触发
    SQLAlchemy JSONB 变更检测（禁止原地 mutate）。

    :return: True 表示发生了写入
    """
    day = db.query(Day).filter(Day.date == day_date).first()
    if day is None:
        # init_time_system_impl 已铺底 1999~2100 的 Day 行，此处兜底创建
        day = Day(date=day_date, ref={})
        db.add(day)
        db.flush()

    ref: Dict[str, Any] = dict(day.ref or {})
    weather: Dict[str, Any] = dict(ref.get(WEATHER_REF_KEY) or {})
    cities: Dict[str, Any] = dict(weather.get("cities") or {})

    existing = cities.get(city_name)
    if existing and existing.get("kind") == "record":
        return False

    cities[city_name] = entry
    weather["cities"] = cities
    weather["updated_at"] = datetime.now(SH_TZ).isoformat()
    ref[WEATHER_REF_KEY] = weather
    day.ref = ref
    db.commit()
    return True


def _write_forecast_days(
    db_factory: Callable[[], Session],
    city: CitySpec,
    forecast: Dict[str, Any],
    today: date_type,
    fetched_at: str,
) -> int:
    """把一次 forecast 拉取结果写入 [today, today+N) 的各日期（同步，线程内执行）"""
    current = forecast.get("current")
    written = 0
    db = db_factory()
    try:
        for date_str, d in (forecast.get("daily") or {}).items():
            day_date = date_type.fromisoformat(date_str)
            if day_date < today:
                continue  # 预报不含过去日期，防御性跳过
            is_today = day_date == today
            entry = {
                "kind": "forecast",
                "weather_code": d.get("weather_code"),
                "temp_max": d.get("temp_max"),
                "temp_min": d.get("temp_min"),
                "temp_current": current.get("temperature")
                if is_today and current
                else None,
                "humidity": current.get("humidity") if is_today and current else None,
                "wind_speed": current.get("wind_speed")
                if is_today and current
                else None,
                "source": "open-meteo",
                "fetched_at": fetched_at,
            }
            if _write_city_weather(db, day_date, city.name, entry):
                written += 1
    finally:
        db.close()
    return written


def _pending_record_dates(
    db_factory: Callable[[], Session],
    city_name: str,
    today: date_type,
    lookback_days: int,
) -> List[date_type]:
    """找出 [today-lookback, today-1] 内该城市尚未固化为 record 的日期"""
    pending: List[date_type] = []
    db = db_factory()
    try:
        for offset in range(1, lookback_days + 1):
            d = today - timedelta(days=offset)
            day = db.query(Day).filter(Day.date == d).first()
            if day is None:
                pending.append(d)
                continue
            cities_map = ((day.ref or {}).get(WEATHER_REF_KEY) or {}).get(
                "cities"
            ) or {}
            existing = cities_map.get(city_name)
            if not existing or existing.get("kind") != "record":
                pending.append(d)
    finally:
        db.close()
    return pending


def _write_record_entry(
    db_factory: Callable[[], Session],
    day_date: date_type,
    city_name: str,
    entry: Dict[str, Any],
) -> bool:
    db = db_factory()
    try:
        return _write_city_weather(db, day_date, city_name, entry)
    finally:
        db.close()


async def _update_records_for_city(
    db_factory: Callable[[], Session],
    city: CitySpec,
    today: date_type,
    lookback_days: int,
    fetched_at: str,
    errors: List[str],
) -> int:
    """对 [today-lookback, today-1] 内非 record 的日期补拉 archive 并固化"""
    pending = await asyncio.to_thread(
        _pending_record_dates, db_factory, city.name, today, lookback_days
    )
    written = 0
    for d in pending:
        try:
            archive = await fetch_archive(city.latitude, city.longitude, d)
        except WeatherFetchError as e:
            # archive 通常 T+1 凌晨后才就绪，首轮失败由 lookback 下轮补齐
            logger.warning(f"[weather] archive not ready for {city.name} {d}: {e}")
            errors.append(f"{city.name} {d}: {e}")
            continue
        payload = archive.get(d.isoformat()) or {}
        entry = {
            "kind": "record",
            "weather_code": payload.get("weather_code"),
            "temp_max": payload.get("temp_max"),
            "temp_min": payload.get("temp_min"),
            "temp_current": None,
            "humidity": None,
            "wind_speed": None,
            "source": "open-meteo-archive",
            "fetched_at": fetched_at,
        }
        wrote = await asyncio.to_thread(
            _write_record_entry, db_factory, d, city.name, entry
        )
        if wrote:
            written += 1
    return written


async def update_weather_impl(
    db_factory: Callable[[], Session],
    cities: Optional[List[CitySpec]] = None,
    today: Optional[date_type] = None,
    forecast_days: Optional[int] = None,
    lookback_days: Optional[int] = None,
) -> WeatherRefreshResponse:
    """执行一轮天气更新（forecast 刷新 + record 固化）。

    HTTP 用 await（httpx async）；同步 SQLAlchemy 写库包在
    ``asyncio.to_thread(...)`` 内，避免阻塞事件循环。
    幂等：forecast 覆盖写、record 存在即跳过；重复执行无副作用。
    每城市独立 try/except，错误收集进 errors。
    """
    cities = cities if cities is not None else read_cities_from_env()
    today = today or _today_sh()
    forecast_days = forecast_days or _env_int(
        "WEATHER_FORECAST_DAYS", DEFAULT_FORECAST_DAYS
    )
    lookback_days = lookback_days or _env_int(
        "WEATHER_RECORD_LOOKBACK_DAYS", DEFAULT_RECORD_LOOKBACK_DAYS
    )

    errors: List[str] = []
    forecast_days_written = 0
    records_written = 0
    fetched_at = datetime.now(SH_TZ).isoformat()

    for city in cities:
        try:
            forecast = await fetch_forecast(
                city.latitude, city.longitude, forecast_days
            )
            forecast_days_written += await asyncio.to_thread(
                _write_forecast_days, db_factory, city, forecast, today, fetched_at
            )
            records_written += await _update_records_for_city(
                db_factory, city, today, lookback_days, fetched_at, errors
            )
        except Exception as e:
            logger.error(f"[weather] update failed for {city.name}: {e}")
            errors.append(f"{city.name}: {e}")

    if not errors:
        status = "success"
    elif forecast_days_written + records_written > 0:
        status = "partial"
    else:
        status = "failed"
    return WeatherRefreshResponse(
        status=status,
        cities=len(cities),
        forecast_days_written=forecast_days_written,
        records_written=records_written,
        errors=errors,
    )


# ============================================================================
# Background update loop
# ============================================================================


async def weather_update_loop(
    db_factory: Callable[[], Session],
    interval_minutes: Optional[int] = None,
) -> None:
    """天气后台更新循环：启动后立即执行一轮，然后按间隔循环。

    - 每轮重新读取 env 城市配置与更新参数；
    - 每轮间隔附加随机抖动（jitter），避免整点请求突刺；
    - 未捕获异常按指数退避（最多 30 分钟）后继续；
    - 任务被取消（服务关闭）时向上抛 CancelledError 安静退出。
    """
    interval_minutes = interval_minutes or _env_int(
        "WEATHER_UPDATE_INTERVAL_MINUTES", DEFAULT_UPDATE_INTERVAL_MINUTES
    )
    backoff_seconds = 0
    while True:
        try:
            result = await update_weather_impl(
                db_factory, cities=read_cities_from_env()
            )
            logger.info(f"[weather] update round done: {result.model_dump_json()}")
            backoff_seconds = 0
            sleep_seconds = interval_minutes * 60 + random.uniform(0, 60)
        except asyncio.CancelledError:
            logger.info("[weather] update loop cancelled")
            raise
        except Exception as e:
            logger.error(f"[weather] update round failed: {e}")
            backoff_seconds = (
                min(MAX_BACKOFF_SECONDS, backoff_seconds * 2)
                if backoff_seconds
                else 60
            )
            sleep_seconds = backoff_seconds
        await asyncio.sleep(sleep_seconds)
