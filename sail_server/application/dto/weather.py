# -*- coding: utf-8 -*-
# @file weather.py
# @brief Weather Pydantic DTOs
# @author sailing-innocent
# @date 2026-07-20
# @version 1.0
# ---------------------------------

"""
天气服务 Pydantic DTOs

天气数据整体存储在 Day ORM 的 JSONB `ref["weather"]` 中，本模块定义
API 层查询/刷新天气时使用的请求与响应模型。

数据语义：
- kind=forecast：当天及未来日期，随每次更新被最新预报覆盖（逐步更新）。
- kind=record：日期已过去，来自 Open-Meteo archive 的历史实测，写入后不可变。
"""

from datetime import date as date_type
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class CityWeather(BaseModel):
    """单城市某日天气数据"""

    model_config = ConfigDict(from_attributes=True)

    city: str = Field(description="城市名称")
    kind: Literal["forecast", "record"] = Field(description="数据类型: forecast | record")
    weather_code: Optional[int] = Field(default=None, description="WMO 天气代码")
    temp_max: Optional[float] = Field(default=None, description="最高气温(°C)")
    temp_min: Optional[float] = Field(default=None, description="最低气温(°C)")
    temp_current: Optional[float] = Field(
        default=None, description="当前气温(°C)，仅 forecast 且为今天时可能有值"
    )
    humidity: Optional[float] = Field(default=None, description="相对湿度(%)")
    wind_speed: Optional[float] = Field(default=None, description="风速(km/h)")
    source: Optional[str] = Field(
        default=None, description="数据来源: open-meteo | open-meteo-archive"
    )
    fetched_at: Optional[datetime] = Field(default=None, description="数据拉取时间")


class DayWeatherResponse(BaseModel):
    """某日天气查询响应"""

    model_config = ConfigDict(from_attributes=True)

    date: date_type = Field(description="查询日期")
    available: bool = Field(description="是否有可用天气数据")
    kind: str = Field(
        description="汇总数据类型: date < today -> record；否则 -> forecast"
    )
    cities: List[CityWeather] = Field(default_factory=list, description="城市天气列表")
    updated_at: Optional[datetime] = Field(
        default=None, description="该日天气最近一次写入时间"
    )


class WeatherRefreshResponse(BaseModel):
    """手动触发天气更新的响应统计"""

    model_config = ConfigDict(from_attributes=True)

    status: str = Field(description="执行状态: success | partial | failed")
    cities: int = Field(description="参与更新的城市数量")
    forecast_days_written: int = Field(description="写入 forecast 的 (城市,日期) 条数")
    records_written: int = Field(description="新固化的 record 条数")
    errors: List[str] = Field(default_factory=list, description="单城市错误信息列表")
