# -*- coding: utf-8 -*-
# @file weather.py
# @brief Open-Meteo async HTTP client (forecast / archive)
# @author sailing-innocent
# @date 2026-07-20
# @version 1.0
# ---------------------------------

"""
Open-Meteo API 异步客户端（无需 API key）

- forecast: https://api.open-meteo.com/v1/forecast
  未来 N 天预报 + 当前天气。
- archive: https://archive-api.open-meteo.com/v1/archive
  历史实测（通常 T+1 凌晨后可用），用于把过去的日期固化为"天气记录"。

返回值统一为纯 dict 内部结构，无 DB 依赖，便于单元测试 mock。
"""

from datetime import date as date_type
from typing import Any, Dict, Optional

import httpx

FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"

DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_TIMEOUT_SECONDS = 10.0

_DAILY_FIELDS = "weather_code,temperature_2m_max,temperature_2m_min"
_CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "weather_code,wind_speed_10m"
)


class WeatherFetchError(Exception):
    """Open-Meteo 拉取失败（网络错误 / 非 200 / 数据不完整）"""


def _daily_to_internal(daily: Dict[str, Any]) -> Dict[str, Dict[str, Optional[float]]]:
    """把 Open-Meteo 的 daily 并列数组结构转为 {date_str: {...}} 映射"""
    out: Dict[str, Dict[str, Optional[float]]] = {}
    times = daily.get("time") or []
    codes = daily.get("weather_code") or []
    maxs = daily.get("temperature_2m_max") or []
    mins = daily.get("temperature_2m_min") or []
    for i, t in enumerate(times):
        out[t] = {
            "weather_code": codes[i] if i < len(codes) else None,
            "temp_max": maxs[i] if i < len(maxs) else None,
            "temp_min": mins[i] if i < len(mins) else None,
        }
    return out


async def fetch_forecast(
    latitude: float,
    longitude: float,
    forecast_days: int = 7,
    timezone: str = DEFAULT_TIMEZONE,
) -> Dict[str, Any]:
    """拉取未来 N 天天气预报（含当前天气）

    返回结构::

        {
            "daily": {"2026-07-20": {"weather_code": 61, "temp_max": 33.5,
                                      "temp_min": 26.1}, ...},
            "current": {"temperature": 30.2, "humidity": 70,
                         "weather_code": 3, "wind_speed": 12.5} | None,
        }

    :raises WeatherFetchError: 网络错误或 HTTP 非 200
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": _DAILY_FIELDS,
        "current": _CURRENT_FIELDS,
        "timezone": timezone,
        "forecast_days": forecast_days,
    }
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.get(FORECAST_API_URL, params=params)
        except httpx.HTTPError as e:
            raise WeatherFetchError(f"forecast request failed: {e}") from e
    if resp.status_code != 200:
        raise WeatherFetchError(f"forecast HTTP {resp.status_code}")

    payload = resp.json()
    daily_raw = payload.get("daily")
    if not daily_raw or not daily_raw.get("time"):
        raise WeatherFetchError("forecast response missing daily data")

    current_raw = payload.get("current") or {}
    current: Optional[Dict[str, Any]] = None
    if current_raw:
        current = {
            "temperature": current_raw.get("temperature_2m"),
            "humidity": current_raw.get("relative_humidity_2m"),
            "weather_code": current_raw.get("weather_code"),
            "wind_speed": current_raw.get("wind_speed_10m"),
        }

    return {"daily": _daily_to_internal(daily_raw), "current": current}


async def fetch_archive(
    latitude: float,
    longitude: float,
    target_date: date_type,
    timezone: str = DEFAULT_TIMEZONE,
) -> Dict[str, Dict[str, Optional[float]]]:
    """拉取某日历史实测天气（archive API）

    返回结构::

        {"2026-07-19": {"weather_code": 61, "temp_max": 33.5, "temp_min": 26.1}}

    :raises WeatherFetchError: 网络错误、HTTP 非 200 或该日期无数据
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": _DAILY_FIELDS,
        "timezone": timezone,
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat(),
    }
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.get(ARCHIVE_API_URL, params=params)
        except httpx.HTTPError as e:
            raise WeatherFetchError(f"archive request failed: {e}") from e
    if resp.status_code != 200:
        raise WeatherFetchError(f"archive HTTP {resp.status_code}")

    payload = resp.json()
    daily_raw = payload.get("daily")
    if not daily_raw or not daily_raw.get("time"):
        raise WeatherFetchError(f"archive response missing data for {target_date}")

    internal = _daily_to_internal(daily_raw)
    key = target_date.isoformat()
    if key not in internal:
        raise WeatherFetchError(f"archive has no entry for {target_date}")
    return internal
