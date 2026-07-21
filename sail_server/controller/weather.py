# -*- coding: utf-8 -*-
# @file weather.py
# @brief Weather Controller
# @author sailing-innocent
# @date 2026-07-20
# @version 1.0
# ---------------------------------

"""
天气控制器

- ``GET  /api/v1/life/weather?date=YYYY-MM-DD`` 查询某日天气
  （date 缺省为服务器本地今天；无数据时 available=false，HTTP 200）。
- ``POST /api/v1/life/weather/refresh`` 手动触发一次更新循环
  （便于调试/验收），返回更新统计。
"""

import logging
from datetime import date as date_type
from typing import Generator, Optional

from litestar import Controller, get, post, Request
from litestar.exceptions import HTTPException
from sqlalchemy.orm import Session

from sail_server.application.dto.weather import (
    DayWeatherResponse,
    WeatherRefreshResponse,
)
from sail_server.model.weather import get_day_weather_impl, update_weather_impl

logger = logging.getLogger(__name__)


class WeatherController(Controller):
    path = "/weather"

    @get("/")
    async def get_day_weather(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        date: Optional[date_type] = None,
    ) -> DayWeatherResponse:
        """查询某日天气（缺省为今天）"""
        try:
            db = next(router_dependency)
            if date is None:
                from sail_server.model.weather import _today_sh

                date = _today_sh()
            return get_day_weather_impl(db, date)
        except Exception as e:
            logger.error(f"Error getting weather for {date}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @post("/refresh")
    async def refresh_weather(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WeatherRefreshResponse:
        """手动触发一次天气更新循环（forecast 刷新 + record 固化）"""
        try:
            from sail_server.db import Database

            return await update_weather_impl(
                Database.get_instance().get_db_session
            )
        except Exception as e:
            logger.error(f"Error refreshing weather: {e}")
            raise HTTPException(status_code=500, detail=str(e))
