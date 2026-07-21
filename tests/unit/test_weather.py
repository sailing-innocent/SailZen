# -*- coding: utf-8 -*-
# @file test_weather.py
# @brief Unit tests for weather service (Day.ref['weather'] based)
# @author sailing-innocent
# @date 2026-07-20
# @version 1.0
# ---------------------------------

"""
天气服务单元测试

覆盖：
- get_day_weather_impl：无数据 available=false；forecast/record kind 汇总
- update_weather_impl（mock fetch_forecast / fetch_archive）：
  forecast 覆盖写、record 固化且不可变、ref 其他 key 保留、
  单城市失败隔离与 errors 收集
- DTO 序列化往返

使用 SQLite 内存数据库，避免依赖 PostgreSQL；网络层全部 mock。
"""

import pytest
from datetime import date, timedelta
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from sail_server.infrastructure.orm.orm_base import ORMBase
from sail_server.infrastructure.orm.life import Day
from sail_server.application.dto.weather import (
    CityWeather,
    DayWeatherResponse,
    WeatherRefreshResponse,
)
from sail_server.model.weather import (
    CitySpec,
    get_day_weather_impl,
    update_weather_impl,
)

TODAY = date(2026, 7, 20)
YESTERDAY = TODAY - timedelta(days=1)

CITY_A = CitySpec(name="杭州", latitude=30.2741, longitude=120.1551)
CITY_B = CitySpec(name="上海", latitude=31.2304, longitude=121.4737)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def weather_engine():
    """创建 SQLite 内存引擎

    使用 StaticPool 让 asyncio.to_thread 中的写库线程与测试线程共享
    同一个内存数据库连接（否则每个线程会得到独立的空库）。
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ORMBase.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db(weather_engine) -> Generator[Session, None, None]:
    """提供独立的数据库会话，测试后回滚"""
    SessionLocal = sessionmaker(bind=weather_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def db_factory(weather_engine):
    """update_weather_impl 需要的会话工厂"""
    SessionLocal = sessionmaker(bind=weather_engine)
    return SessionLocal


def _make_forecast(days: int = 3, temp_max_base: float = 33.0):
    """构造 [TODAY, TODAY+days) 的假 forecast 数据"""
    return {
        "daily": {
            (TODAY + timedelta(days=i)).isoformat(): {
                "weather_code": 61,
                "temp_max": temp_max_base + i,
                "temp_min": 25.0 + i,
            }
            for i in range(days)
        },
        "current": {
            "temperature": 30.5,
            "humidity": 70.0,
            "weather_code": 61,
            "wind_speed": 12.0,
        },
    }


def _make_archive(target: date, temp_max: float = 28.0):
    return {
        target.isoformat(): {
            "weather_code": 3,
            "temp_max": temp_max,
            "temp_min": 22.0,
        }
    }


def _patch_fetchers(monkeypatch, forecast_payload=None, archive_payload=None):
    """把 model 层引用的 Open-Meteo fetcher 替换为假实现"""

    async def fake_forecast(lat, lon, forecast_days=7, timezone="Asia/Shanghai"):
        return forecast_payload if forecast_payload is not None else _make_forecast()

    async def fake_archive(lat, lon, target_date, timezone="Asia/Shanghai"):
        if archive_payload is not None:
            return archive_payload
        return _make_archive(target_date)

    monkeypatch.setattr(
        "sail_server.model.weather.fetch_forecast", fake_forecast
    )
    monkeypatch.setattr("sail_server.model.weather.fetch_archive", fake_archive)


# ============================================================================
# get_day_weather_impl Tests
# ============================================================================


class TestGetDayWeather:
    def test_day_not_exists_available_false(self, db):
        resp = get_day_weather_impl(db, TODAY, today=TODAY)
        assert resp.available is False
        assert resp.cities == []
        assert resp.kind == "forecast"
        assert resp.updated_at is None

    def test_day_without_weather_available_false(self, db):
        db.add(Day(date=TODAY, ref={"mood": "good"}))
        db.commit()
        resp = get_day_weather_impl(db, TODAY, today=TODAY)
        assert resp.available is False
        assert resp.cities == []

    def test_past_date_kind_is_record(self, db):
        db.add(
            Day(
                date=YESTERDAY,
                ref={
                    "weather": {
                        "updated_at": "2026-07-20T00:10:00+08:00",
                        "cities": {
                            "杭州": {
                                "kind": "record",
                                "weather_code": 61,
                                "temp_max": 30.0,
                                "temp_min": 24.0,
                                "source": "open-meteo-archive",
                                "fetched_at": "2026-07-20T00:10:00+08:00",
                            }
                        },
                    }
                },
            )
        )
        db.commit()
        resp = get_day_weather_impl(db, YESTERDAY, today=TODAY)
        assert resp.available is True
        assert resp.kind == "record"
        assert len(resp.cities) == 1
        city = resp.cities[0]
        assert city.city == "杭州"
        assert city.kind == "record"
        assert city.temp_max == 30.0
        assert resp.updated_at is not None

    def test_today_kind_is_forecast(self, db):
        db.add(
            Day(
                date=TODAY,
                ref={
                    "weather": {
                        "updated_at": "2026-07-20T08:00:00+08:00",
                        "cities": {
                            "上海": {
                                "kind": "forecast",
                                "weather_code": 0,
                                "temp_max": 35.0,
                                "temp_min": 27.0,
                                "temp_current": 31.0,
                                "source": "open-meteo",
                                "fetched_at": "2026-07-20T08:00:00+08:00",
                            }
                        },
                    }
                },
            )
        )
        db.commit()
        resp = get_day_weather_impl(db, TODAY, today=TODAY)
        assert resp.available is True
        assert resp.kind == "forecast"
        assert resp.cities[0].temp_current == 31.0


# ============================================================================
# update_weather_impl Tests
# ============================================================================


class TestUpdateWeather:
    @pytest.mark.asyncio
    async def test_forecast_written_and_overwritable(
        self, db_factory, monkeypatch
    ):
        """今天/未来日期写入 forecast，且重复执行可覆盖更新"""
        _patch_fetchers(monkeypatch)

        result = await update_weather_impl(
            db_factory, cities=[CITY_A], today=TODAY, forecast_days=3
        )
        assert result.status == "success"
        assert result.cities == 1
        assert result.forecast_days_written == 3
        assert result.errors == []

        resp = get_day_weather_impl(db_factory(), TODAY, today=TODAY)
        assert resp.available is True
        assert resp.kind == "forecast"
        city = resp.cities[0]
        assert city.kind == "forecast"
        assert city.temp_max == 33.0
        # 今天的 forecast 带上 current 数据
        assert city.temp_current == 30.5
        assert city.humidity == 70.0

        # 第二轮：温度变化，覆盖写
        _patch_fetchers(monkeypatch, forecast_payload=_make_forecast(temp_max_base=40.0))
        result2 = await update_weather_impl(
            db_factory, cities=[CITY_A], today=TODAY, forecast_days=3
        )
        assert result2.forecast_days_written == 3
        resp2 = get_day_weather_impl(db_factory(), TODAY, today=TODAY)
        assert resp2.cities[0].temp_max == 40.0

    @pytest.mark.asyncio
    async def test_record_written_once_and_immutable(
        self, db_factory, monkeypatch
    ):
        """昨天首次写入 record，再次执行不覆盖 record、甚至不再请求 archive"""
        calls = {"archive": 0}

        async def counting_archive(lat, lon, target_date, timezone="Asia/Shanghai"):
            calls["archive"] += 1
            return _make_archive(target_date, temp_max=28.0)

        _patch_fetchers(monkeypatch)
        monkeypatch.setattr("sail_server.model.weather.fetch_archive", counting_archive)

        result1 = await update_weather_impl(
            db_factory, cities=[CITY_A], today=TODAY, forecast_days=3, lookback_days=1
        )
        assert result1.records_written == 1
        assert calls["archive"] == 1

        resp = get_day_weather_impl(db_factory(), YESTERDAY, today=TODAY)
        assert resp.available is True
        assert resp.kind == "record"
        assert resp.cities[0].kind == "record"
        assert resp.cities[0].temp_max == 28.0
        assert resp.cities[0].source == "open-meteo-archive"

        # 第二轮：archive 数据变了，但 record 不可变，且不再发请求
        async def changed_archive(lat, lon, target_date, timezone="Asia/Shanghai"):
            calls["archive"] += 1
            return _make_archive(target_date, temp_max=99.0)

        monkeypatch.setattr("sail_server.model.weather.fetch_archive", changed_archive)
        result2 = await update_weather_impl(
            db_factory, cities=[CITY_A], today=TODAY, forecast_days=3, lookback_days=1
        )
        assert result2.records_written == 0
        assert calls["archive"] == 1  # 未再调用

        resp2 = get_day_weather_impl(db_factory(), YESTERDAY, today=TODAY)
        assert resp2.cities[0].temp_max == 28.0  # 仍是首次固化的值

    @pytest.mark.asyncio
    async def test_ref_other_keys_preserved(self, db_factory, monkeypatch):
        """ref 中预先存在的其他 key 更新后仍保留"""
        db = db_factory()
        db.add(Day(date=TODAY, ref={"mood": "good"}))
        db.commit()
        db.close()

        _patch_fetchers(monkeypatch)
        await update_weather_impl(
            db_factory, cities=[CITY_A], today=TODAY, forecast_days=3
        )

        db = db_factory()
        day = db.query(Day).filter(Day.date == TODAY).first()
        assert day.ref["mood"] == "good"
        assert "weather" in day.ref
        db.close()

    @pytest.mark.asyncio
    async def test_single_city_failure_isolated(self, db_factory, monkeypatch):
        """单城市 fetch 抛错不影响其他城市，错误收集进 errors"""

        async def failing_forecast(lat, lon, forecast_days=7, timezone="Asia/Shanghai"):
            if lat == CITY_A.latitude:
                raise RuntimeError("network down")
            return _make_forecast()

        _patch_fetchers(monkeypatch)
        monkeypatch.setattr(
            "sail_server.model.weather.fetch_forecast", failing_forecast
        )

        result = await update_weather_impl(
            db_factory, cities=[CITY_A, CITY_B], today=TODAY, forecast_days=3
        )
        assert result.status == "partial"
        assert len(result.errors) == 1
        assert "杭州" in result.errors[0]
        # 上海照常写入
        assert result.forecast_days_written == 3
        resp = get_day_weather_impl(db_factory(), TODAY, today=TODAY)
        assert [c.city for c in resp.cities] == ["上海"]

    @pytest.mark.asyncio
    async def test_all_cities_failed_status_failed(self, db_factory, monkeypatch):
        async def failing_forecast(lat, lon, forecast_days=7, timezone="Asia/Shanghai"):
            raise RuntimeError("network down")

        monkeypatch.setattr(
            "sail_server.model.weather.fetch_forecast", failing_forecast
        )
        result = await update_weather_impl(
            db_factory, cities=[CITY_A], today=TODAY, forecast_days=3
        )
        assert result.status == "failed"
        assert result.forecast_days_written == 0
        assert len(result.errors) == 1


# ============================================================================
# DTO Serialization Tests
# ============================================================================


class TestDTO:
    def test_day_weather_response_roundtrip(self):
        resp = DayWeatherResponse(
            date=TODAY,
            available=True,
            kind="forecast",
            cities=[
                CityWeather(
                    city="杭州",
                    kind="forecast",
                    weather_code=61,
                    temp_max=33.5,
                    temp_min=26.1,
                    temp_current=30.2,
                    humidity=70.0,
                    wind_speed=12.5,
                    source="open-meteo",
                    fetched_at="2026-07-20T08:30:00+08:00",
                )
            ],
            updated_at="2026-07-20T08:30:00+08:00",
        )
        json_str = resp.model_dump_json()
        resp2 = DayWeatherResponse.model_validate_json(json_str)
        assert resp2 == resp
        assert resp2.cities[0].city == "杭州"

    def test_weather_refresh_response_defaults(self):
        resp = WeatherRefreshResponse(
            status="success", cities=3, forecast_days_written=21, records_written=3
        )
        assert resp.errors == []
