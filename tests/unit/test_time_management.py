# -*- coding: utf-8 -*-
# @file test_time_management.py
# @brief Unit tests for time management (Day / TimeSpan)
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
时间管理模块单元测试

覆盖 Day / TimeSpan 的生成算法、CRUD、初始化幂等性。
使用 SQLite 内存数据库，避免依赖 PostgreSQL。
"""

import pytest
from datetime import date, timedelta
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from sail_server.infrastructure.orm.orm_base import ORMBase
from sail_server.infrastructure.orm.life import Day, TimeSpan
from sail_server.application.dto.life import (
    TimeSpanClass,
    DayCreateRequest,
    DayUpdateRequest,
    TimeSpanCreateRequest,
    TimeSpanUpdateRequest,
)
from sail_server.model.life import (
    create_day_impl,
    get_day_impl,
    get_day_by_date_impl,
    get_days_impl,
    update_day_impl,
    delete_day_impl,
    create_timespan_impl,
    get_timespan_impl,
    get_timespan_by_name_impl,
    get_timespans_impl,
    get_timespan_children_impl,
    get_timespans_by_day_impl,
    update_timespan_impl,
    delete_timespan_impl,
    init_days_impl,
    init_time_system_impl,
    _iter_weeks,
    _iter_months,
    _iter_biweeks,
    _iter_bimonths,
    _iter_quarters,
    _iter_hyears,
    _iter_years,
    _monday_of,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def life_engine():
    """创建 SQLite 内存引擎"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    ORMBase.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db(life_engine) -> Generator[Session, None, None]:
    """提供独立的数据库会话，测试后回滚"""
    SessionLocal = sessionmaker(bind=life_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ============================================================================
# Day CRUD Tests
# ============================================================================


class TestDayCRUD:
    def test_create_and_get_day(self, db):
        request = DayCreateRequest(date=date(2026, 3, 1), ref={"diary_path": "/diary/2026-03-01.md"})
        created = create_day_impl(db, request)
        assert created.id is not None
        assert created.date == date(2026, 3, 1)

        fetched = get_day_impl(db, created.id)
        assert fetched is not None
        assert fetched.date == created.date

    def test_get_day_by_date(self, db):
        create_day_impl(db, DayCreateRequest(date=date(2026, 3, 1)))
        fetched = get_day_by_date_impl(db, date(2026, 3, 1))
        assert fetched is not None
        assert fetched.date == date(2026, 3, 1)

    def test_duplicate_day_raises(self, db):
        create_day_impl(db, DayCreateRequest(date=date(2026, 3, 1)))
        with pytest.raises(ValueError):
            create_day_impl(db, DayCreateRequest(date=date(2026, 3, 1)))

    def test_update_day_ref(self, db):
        created = create_day_impl(db, DayCreateRequest(date=date(2026, 3, 1)))
        updated = update_day_impl(db, created.id, DayUpdateRequest(ref={"note": "updated"}))
        assert updated is not None
        assert updated.ref == {"note": "updated"}

    def test_delete_day(self, db):
        created = create_day_impl(db, DayCreateRequest(date=date(2026, 3, 1)))
        deleted = delete_day_impl(db, created.id)
        assert deleted is not None
        assert get_day_impl(db, created.id) is None


# ============================================================================
# TimeSpan CRUD Tests
# ============================================================================


class TestTimeSpanCRUD:
    def test_create_and_get_timespan(self, db):
        d1 = create_day_impl(db, DayCreateRequest(date=date(2026, 3, 1)))
        d2 = create_day_impl(db, DayCreateRequest(date=date(2026, 3, 7)))

        request = TimeSpanCreateRequest(
            class_=TimeSpanClass.WEEK,
            name="W0001",
            start_day_id=d1.id,
            end_day_id=d2.id,
        )
        created = create_timespan_impl(db, request)
        assert created.id is not None
        assert created.name == "W0001"

        fetched = get_timespan_impl(db, created.id)
        assert fetched is not None
        assert fetched.name == "W0001"

    def test_get_timespan_by_name(self, db):
        d1 = create_day_impl(db, DayCreateRequest(date=date(2026, 3, 1)))
        d2 = create_day_impl(db, DayCreateRequest(date=date(2026, 3, 7)))
        create_timespan_impl(
            db,
            TimeSpanCreateRequest(
                class_=TimeSpanClass.WEEK,
                name="W0001",
                start_day_id=d1.id,
                end_day_id=d2.id,
            ),
        )

        fetched = get_timespan_by_name_impl(db, TimeSpanClass.WEEK, "W0001")
        assert fetched is not None
        assert fetched.class_ == TimeSpanClass.WEEK

    def test_update_timespan_child_spans(self, db):
        d1 = create_day_impl(db, DayCreateRequest(date=date(2026, 3, 1)))
        d2 = create_day_impl(db, DayCreateRequest(date=date(2026, 3, 7)))
        parent = create_timespan_impl(
            db,
            TimeSpanCreateRequest(
                class_=TimeSpanClass.BIWEEK,
                name="B0001",
                start_day_id=d1.id,
                end_day_id=d2.id,
            ),
        )
        child = create_timespan_impl(
            db,
            TimeSpanCreateRequest(
                class_=TimeSpanClass.WEEK,
                name="W0001",
                start_day_id=d1.id,
                end_day_id=d2.id,
            ),
        )

        updated = update_timespan_impl(
            db, parent.id, TimeSpanUpdateRequest(child_span_ids=[child.id])
        )
        assert updated is not None
        assert updated.child_span_ids == [child.id]

        children = get_timespan_children_impl(db, parent.id)
        assert len(children) == 1
        assert children[0].id == child.id

    def test_get_timespans_by_day(self, db):
        d1 = create_day_impl(db, DayCreateRequest(date=date(2026, 3, 1)))
        d2 = create_day_impl(db, DayCreateRequest(date=date(2026, 3, 7)))
        create_timespan_impl(
            db,
            TimeSpanCreateRequest(
                class_=TimeSpanClass.WEEK,
                name="W0001",
                start_day_id=d1.id,
                end_day_id=d2.id,
            ),
        )

        spans = get_timespans_by_day_impl(db, date(2026, 3, 1))
        assert len(spans) == 1
        assert spans[0].name == "W0001"


# ============================================================================
# Span Generation Algorithm Tests
# ============================================================================


class TestSpanGeneration:
    def test_monday_of(self):
        # 2026-03-01 is Sunday
        assert _monday_of(date(2026, 3, 1)) == date(2026, 2, 23)
        # 2026-03-02 is Monday
        assert _monday_of(date(2026, 3, 2)) == date(2026, 3, 2)

    def test_week_generation(self):
        # 2026-03-02 is Monday
        weeks = _iter_weeks(date(2026, 3, 2), date(2026, 3, 23))
        assert len(weeks) == 3
        assert weeks[0].name == "W0001"
        assert weeks[0].start_date == date(2026, 3, 2)
        assert weeks[0].end_date == date(2026, 3, 8)
        assert weeks[1].name == "W0002"
        assert weeks[2].name == "W0003"

    def test_biweek_generation(self):
        weeks = _iter_weeks(date(2026, 3, 2), date(2026, 3, 23))
        biweeks = _iter_biweeks(weeks)
        assert len(biweeks) == 2
        assert biweeks[0].name == "B0001"
        assert biweeks[0].child_names == ["W0001", "W0002"]
        assert biweeks[1].name == "B0002"
        assert biweeks[1].child_names == ["W0003"]

    def test_month_generation(self):
        months = _iter_months(date(2026, 1, 1), date(2026, 4, 1))
        assert len(months) == 3
        assert months[0].name == "Y2026M01"
        assert months[0].start_date == date(2026, 1, 1)
        assert months[0].end_date == date(2026, 1, 31)
        assert months[1].name == "Y2026M02"
        assert months[2].name == "Y2026M03"

    def test_month_generation_leap_year(self):
        months = _iter_months(date(2024, 2, 1), date(2024, 3, 1))
        assert len(months) == 1
        assert months[0].name == "Y2024M02"
        assert months[0].end_date == date(2024, 2, 29)

    def test_bimonth_generation(self):
        months = _iter_months(date(2026, 1, 1), date(2026, 5, 1))
        bimonths = _iter_bimonths(months)
        assert len(bimonths) == 2
        assert bimonths[0].name == "Y2026BM1"
        assert bimonths[0].child_names == ["Y2026M01", "Y2026M02"]
        assert bimonths[1].name == "Y2026BM2"
        assert bimonths[1].child_names == ["Y2026M03", "Y2026M04"]

    def test_quarter_generation(self):
        months = _iter_months(date(2026, 1, 1), date(2026, 7, 1))
        quarters = _iter_quarters(months)
        assert len(quarters) == 2
        assert quarters[0].name == "Y2026Q1"
        assert quarters[0].child_names == ["Y2026M01", "Y2026M02", "Y2026M03"]
        assert quarters[1].name == "Y2026Q2"

    def test_hyear_generation(self):
        months = _iter_months(date(2026, 1, 1), date(2027, 1, 1))
        quarters = _iter_quarters(months)
        hyears = _iter_hyears(quarters)
        assert len(hyears) == 2
        assert hyears[0].name == "Y2026H1"
        assert hyears[0].child_names == ["Y2026Q1", "Y2026Q2"]
        assert hyears[1].name == "Y2026H2"

    def test_year_generation(self):
        months = _iter_months(date(2026, 1, 1), date(2027, 1, 1))
        quarters = _iter_quarters(months)
        hyears = _iter_hyears(quarters)
        years = _iter_years(hyears)
        assert len(years) == 1
        assert years[0].name == "Y2026"
        assert years[0].child_names == ["Y2026H1", "Y2026H2"]


# ============================================================================
# Initialization Tests
# ============================================================================


class TestInitialization:
    def test_init_days_count(self, db):
        start = date(2026, 3, 1)
        end = date(2026, 3, 10)
        count = init_days_impl(db, start, end)
        assert count == 9

        days = get_days_impl(db, start, end)
        assert len(days) == 9

    def test_init_days_idempotent(self, db):
        start = date(2026, 3, 1)
        end = date(2026, 3, 10)
        assert init_days_impl(db, start, end) == 9
        assert init_days_impl(db, start, end) == 0

    def test_init_time_system_idempotent(self, db):
        start = date(2026, 1, 1)
        end = date(2027, 1, 1)

        result1 = init_time_system_impl(db, start, end)
        assert result1["days_created"] == 365
        assert result1["total_spans"] > 0

        result2 = init_time_system_impl(db, start, end)
        assert result2["days_created"] == 0
        assert result2["total_spans"] == result1["total_spans"]

    def test_year_child_relationship_after_init(self, db):
        start = date(2026, 1, 1)
        end = date(2027, 1, 1)
        init_time_system_impl(db, start, end)

        year = get_timespan_by_name_impl(db, TimeSpanClass.YEAR, "Y2026")
        assert year is not None
        children = get_timespan_children_impl(db, year.id)
        assert len(children) == 2
        assert {c.name for c in children} == {"Y2026H1", "Y2026H2"}

    def test_full_range_day_count(self, db):
        start = date(1999, 4, 19)
        end = date(2100, 1, 1)
        count = init_days_impl(db, start, end)
        expected = (end - start).days
        assert count == expected
        assert expected == 36782


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    def test_partial_week_at_start(self, db):
        # 2026-03-01 is Sunday; start on Sunday, end next Monday
        weeks = _iter_weeks(date(2026, 3, 1), date(2026, 3, 9))
        assert len(weeks) == 2
        # First week is truncated to only Sunday
        assert weeks[0].start_date == date(2026, 3, 1)
        assert weeks[0].end_date == date(2026, 3, 1)
        # Second week is Monday-Sunday
        assert weeks[1].start_date == date(2026, 3, 2)
        assert weeks[1].end_date == date(2026, 3, 8)

    def test_timespan_invalid_day_ids(self, db):
        with pytest.raises(ValueError):
            create_timespan_impl(
                db,
                TimeSpanCreateRequest(
                    class_=TimeSpanClass.WEEK,
                    name="W0001",
                    start_day_id=999,
                    end_day_id=999,
                ),
            )
