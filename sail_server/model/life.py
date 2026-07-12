# -*- coding: utf-8 -*-
# @file life.py
# @brief Life Time Management Model Layer
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
生活时间管理模型层

提供 Day 与 TimeSpan 的 CRUD 操作和时间系统初始化逻辑。
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging

from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.life import Day, TimeSpan
from sail_server.application.dto.life import (
    TimeSpanClass,
    DayCreateRequest,
    DayUpdateRequest,
    DayResponse,
    TimeSpanCreateRequest,
    TimeSpanUpdateRequest,
    TimeSpanResponse,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Internal Helpers: DTO Conversion
# ============================================================================


def _day_to_response(day: Day) -> DayResponse:
    """将 Day ORM 对象转换为响应 DTO"""
    return DayResponse(
        id=day.id,
        date=day.date,
        ref=day.ref or {},
        created_at=day.created_at,
        updated_at=day.updated_at,
    )


def _timespan_to_response(span: TimeSpan) -> TimeSpanResponse:
    """将 TimeSpan ORM 对象转换为响应 DTO"""
    return TimeSpanResponse(
        id=span.id,
        class_=TimeSpanClass(span.class_) if span.class_ else TimeSpanClass.CUSTOM,
        name=span.name,
        start_day_id=span.start_day_id,
        end_day_id=span.end_day_id,
        child_span_ids=span.child_span_ids or [],
        ref=span.ref or {},
        created_at=span.created_at,
        updated_at=span.updated_at,
    )


# ============================================================================
# Day CRUD
# ============================================================================


def create_day_impl(db: Session, request: DayCreateRequest) -> DayResponse:
    """创建自然日"""
    existing = db.query(Day).filter(Day.date == request.date).first()
    if existing:
        raise ValueError(f"日期已存在: {request.date}")

    day = Day(date=request.date, ref=request.ref or {})
    db.add(day)
    db.commit()
    db.refresh(day)
    logger.info(f"Created day: {day.date} (id={day.id})")
    return _day_to_response(day)


def get_day_impl(db: Session, day_id: int) -> Optional[DayResponse]:
    """通过 ID 获取自然日"""
    day = db.query(Day).filter(Day.id == day_id).first()
    if day is None:
        return None
    return _day_to_response(day)


def get_day_by_date_impl(db: Session, query_date: date) -> Optional[DayResponse]:
    """通过日期获取自然日"""
    day = db.query(Day).filter(Day.date == query_date).first()
    if day is None:
        return None
    return _day_to_response(day)


def get_days_impl(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = -1,
) -> List[DayResponse]:
    """获取自然日列表"""
    query = db.query(Day)
    if start_date is not None:
        query = query.filter(Day.date >= start_date)
    if end_date is not None:
        query = query.filter(Day.date < end_date)
    query = query.order_by(Day.date)
    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)
    return [_day_to_response(d) for d in query.all()]


def update_day_impl(
    db: Session, day_id: int, request: DayUpdateRequest
) -> Optional[DayResponse]:
    """更新自然日"""
    day = db.query(Day).filter(Day.id == day_id).first()
    if day is None:
        return None

    if request.ref is not None:
        day.ref = request.ref

    db.commit()
    db.refresh(day)
    logger.info(f"Updated day: {day.date} (id={day.id})")
    return _day_to_response(day)


def delete_day_impl(db: Session, day_id: int) -> Optional[DayResponse]:
    """删除自然日"""
    day = db.query(Day).filter(Day.id == day_id).first()
    if day is None:
        return None

    response = _day_to_response(day)
    db.delete(day)
    db.commit()
    logger.info(f"Deleted day: {day.date} (id={day_id})")
    return response


# ============================================================================
# TimeSpan CRUD
# ============================================================================


def create_timespan_impl(db: Session, request: TimeSpanCreateRequest) -> TimeSpanResponse:
    """创建时间跨度"""
    # 校验起始/结束自然日存在
    start_day = db.query(Day).filter(Day.id == request.start_day_id).first()
    end_day = db.query(Day).filter(Day.id == request.end_day_id).first()
    if start_day is None:
        raise ValueError(f"起始自然日不存在: {request.start_day_id}")
    if end_day is None:
        raise ValueError(f"结束自然日不存在: {request.end_day_id}")
    if start_day.date > end_day.date:
        raise ValueError("起始自然日不能晚于结束自然日")

    # 校验子时间跨度存在（若提供）
    child_ids = request.child_span_ids or []
    if child_ids:
        existing_children = (
            db.query(TimeSpan.id).filter(TimeSpan.id.in_(child_ids)).all()
        )
        existing_ids = {r[0] for r in existing_children}
        missing = set(child_ids) - existing_ids
        if missing:
            raise ValueError(f"子时间跨度不存在: {missing}")

    existing = (
        db.query(TimeSpan)
        .filter(TimeSpan.class_ == request.class_.value, TimeSpan.name == request.name)
        .first()
    )
    if existing:
        raise ValueError(
            f"时间跨度已存在: class={request.class_.value}, name={request.name}"
        )

    span = TimeSpan(
        class_=request.class_.value,
        name=request.name,
        start_day_id=request.start_day_id,
        end_day_id=request.end_day_id,
        child_span_ids=list(child_ids),
        ref=request.ref or {},
    )
    db.add(span)
    db.commit()
    db.refresh(span)
    logger.info(
        f"Created timespan: {span.class_}/{span.name} (id={span.id})"
    )
    return _timespan_to_response(span)


def get_timespan_impl(db: Session, span_id: int) -> Optional[TimeSpanResponse]:
    """通过 ID 获取时间跨度"""
    span = db.query(TimeSpan).filter(TimeSpan.id == span_id).first()
    if span is None:
        return None
    return _timespan_to_response(span)


def get_timespan_by_name_impl(
    db: Session, span_class: TimeSpanClass, name: str
) -> Optional[TimeSpanResponse]:
    """通过类型和名称获取时间跨度"""
    span = (
        db.query(TimeSpan)
        .filter(TimeSpan.class_ == span_class.value, TimeSpan.name == name)
        .first()
    )
    if span is None:
        return None
    return _timespan_to_response(span)


def get_timespans_impl(
    db: Session,
    span_class: Optional[TimeSpanClass] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    name: Optional[str] = None,
    skip: int = 0,
    limit: int = -1,
) -> List[TimeSpanResponse]:
    """获取时间跨度列表"""
    query = db.query(TimeSpan)

    if span_class is not None:
        query = query.filter(TimeSpan.class_ == span_class.value)
    if name is not None:
        query = query.filter(TimeSpan.name.contains(name))

    # 日期范围过滤：要求跨度完全落在范围内
    if start_date is not None or end_date is not None:
        day_query = db.query(Day.id, Day.date)
        date_to_id = {d.date: d.id for d in day_query.all()}
        if start_date is not None:
            start_id = date_to_id.get(start_date)
            if start_id is not None:
                query = query.filter(TimeSpan.end_day_id >= start_id)
        if end_date is not None:
            # end_date 为排他边界，取前一天的 day_id
            end_day = end_date - timedelta(days=1)
            end_id = date_to_id.get(end_day)
            if end_id is not None:
                query = query.filter(TimeSpan.start_day_id <= end_id)

    query = query.order_by(TimeSpan.class_, TimeSpan.name)
    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)
    return [_timespan_to_response(s) for s in query.all()]


def get_timespan_children_impl(
    db: Session, span_id: int
) -> List[TimeSpanResponse]:
    """获取指定时间跨度的子时间跨度"""
    span = db.query(TimeSpan).filter(TimeSpan.id == span_id).first()
    if span is None:
        return []

    child_ids = span.child_span_ids or []
    if not child_ids:
        return []

    children = (
        db.query(TimeSpan).filter(TimeSpan.id.in_(child_ids)).order_by(TimeSpan.name).all()
    )
    return [_timespan_to_response(s) for s in children]


def get_timespans_by_day_impl(db: Session, query_date: date) -> List[TimeSpanResponse]:
    """获取包含指定日期的所有时间跨度"""
    day = db.query(Day).filter(Day.date == query_date).first()
    if day is None:
        return []

    spans = (
        db.query(TimeSpan)
        .filter(
            TimeSpan.start_day_id <= day.id,
            TimeSpan.end_day_id >= day.id,
        )
        .order_by(TimeSpan.class_, TimeSpan.name)
        .all()
    )
    return [_timespan_to_response(s) for s in spans]


def update_timespan_impl(
    db: Session, span_id: int, request: TimeSpanUpdateRequest
) -> Optional[TimeSpanResponse]:
    """更新时间跨度"""
    span = db.query(TimeSpan).filter(TimeSpan.id == span_id).first()
    if span is None:
        return None

    if request.class_ is not None:
        span.class_ = request.class_.value
    if request.name is not None:
        span.name = request.name
    if request.start_day_id is not None:
        span.start_day_id = request.start_day_id
    if request.end_day_id is not None:
        span.end_day_id = request.end_day_id
    if request.child_span_ids is not None:
        span.child_span_ids = list(request.child_span_ids)
    if request.ref is not None:
        span.ref = request.ref

    # 校验起始/结束自然日存在且顺序正确
    start_day = db.query(Day).filter(Day.id == span.start_day_id).first()
    end_day = db.query(Day).filter(Day.id == span.end_day_id).first()
    if start_day is None:
        raise ValueError(f"起始自然日不存在: {span.start_day_id}")
    if end_day is None:
        raise ValueError(f"结束自然日不存在: {span.end_day_id}")
    if start_day.date > end_day.date:
        raise ValueError("起始自然日不能晚于结束自然日")

    db.commit()
    db.refresh(span)
    logger.info(f"Updated timespan: {span.class_}/{span.name} (id={span.id})")
    return _timespan_to_response(span)


def delete_timespan_impl(db: Session, span_id: int) -> Optional[TimeSpanResponse]:
    """删除时间跨度"""
    span = db.query(TimeSpan).filter(TimeSpan.id == span_id).first()
    if span is None:
        return None

    response = _timespan_to_response(span)
    db.delete(span)
    db.commit()
    logger.info(f"Deleted timespan: {span.class_}/{span.name} (id={span_id})")
    return response


# ============================================================================
# TimeSpan Definition Helpers
# ============================================================================


class _SpanDef:
    """内部使用的临时时间跨度定义"""

    def __init__(
        self,
        class_: str,
        name: str,
        start_date: date,
        end_date: date,
        child_names: Optional[List[str]] = None,
    ):
        self.class_ = class_
        self.name = name
        self.start_date = start_date
        self.end_date = end_date
        self.child_names = child_names or []


def _monday_of(date: date) -> date:
    """获取指定日期所在周的周一"""
    return date - timedelta(days=date.weekday())


def _add_months(d: date, months: int) -> date:
    """给日期增加若干月份"""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def _last_day_of_month(year: int, month: int) -> date:
    """获取指定月份的最后一天"""
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _iter_weeks(global_start: date, global_end: date) -> List[_SpanDef]:
    """生成周跨度定义

    周从 global_start 所在周的周一开始顺序编号，名称格式 W{index:04d}。
    首尾周的日期会被截断到全局范围内。
    """
    weeks = []
    cursor = _monday_of(global_start)
    index = 1
    while cursor < global_end:
        week_start = max(cursor, global_start)
        week_end_natural = cursor + timedelta(days=6)
        week_end = min(week_end_natural, global_end - timedelta(days=1))
        if week_start <= week_end:
            weeks.append(
                _SpanDef(
                    class_=TimeSpanClass.WEEK.value,
                    name=f"W{index:04d}",
                    start_date=week_start,
                    end_date=week_end,
                )
            )
        cursor += timedelta(days=7)
        index += 1
    return weeks


def _iter_biweeks(weeks: List[_SpanDef]) -> List[_SpanDef]:
    """生成双周跨度定义，按周连续配对"""
    biweeks = []
    index = 1
    for i in range(0, len(weeks), 2):
        if i + 1 >= len(weeks):
            # 奇数个周时，最后一个周单独成组
            w = weeks[i]
            biweeks.append(
                _SpanDef(
                    class_=TimeSpanClass.BIWEEK.value,
                    name=f"B{index:04d}",
                    start_date=w.start_date,
                    end_date=w.end_date,
                    child_names=[w.name],
                )
            )
        else:
            w1, w2 = weeks[i], weeks[i + 1]
            biweeks.append(
                _SpanDef(
                    class_=TimeSpanClass.BIWEEK.value,
                    name=f"B{index:04d}",
                    start_date=w1.start_date,
                    end_date=w2.end_date,
                    child_names=[w1.name, w2.name],
                )
            )
        index += 1
    return biweeks


def _iter_months(global_start: date, global_end: date) -> List[_SpanDef]:
    """生成月跨度定义，名称格式 Y{year}M{month:02d}"""
    months = []
    cursor = date(global_start.year, global_start.month, 1)
    while cursor < global_end:
        month_start = max(cursor, global_start)
        month_end = min(_last_day_of_month(cursor.year, cursor.month), global_end - timedelta(days=1))
        if month_start <= month_end:
            months.append(
                _SpanDef(
                    class_=TimeSpanClass.MONTH.value,
                    name=f"Y{cursor.year}M{cursor.month:02d}",
                    start_date=month_start,
                    end_date=month_end,
                )
            )
        cursor = _add_months(cursor, 1)
        # 确保 cursor 是下个月的第一天，避免 _add_months 的日期截断导致死循环
        cursor = date(cursor.year, cursor.month, 1)
    return months


def _iter_bimonths(months: List[_SpanDef]) -> List[_SpanDef]:
    """生成双月跨度定义，名称格式 Y{year}BM{index}"""
    bimonths = []
    if not months:
        return bimonths

    # 按自然双月分组：(1,2), (3,4), (5,6), (7,8), (9,10), (11,12)
    groups: Dict[Tuple[int, int], List[_SpanDef]] = {}
    for m in months:
        # 从名称解析年和月：Y2026M01
        year = m.start_date.year
        month = m.start_date.month
        group_key = (year, (month - 1) // 2)
        groups.setdefault(group_key, []).append(m)

    for key in sorted(groups.keys()):
        group = groups[key]
        year, _ = key
        bimonth_index = (group[0].start_date.month - 1) // 2 + 1
        bimonths.append(
            _SpanDef(
                class_=TimeSpanClass.BIMONTH.value,
                name=f"Y{year}BM{bimonth_index}",
                start_date=group[0].start_date,
                end_date=group[-1].end_date,
                child_names=[m.name for m in group],
            )
        )
    return bimonths


def _iter_quarters(months: List[_SpanDef]) -> List[_SpanDef]:
    """生成季度跨度定义，名称格式 Y{year}Q{quarter}"""
    quarters = []
    if not months:
        return quarters

    groups: Dict[Tuple[int, int], List[_SpanDef]] = {}
    for m in months:
        year = m.start_date.year
        month = m.start_date.month
        quarter = (month - 1) // 3
        group_key = (year, quarter)
        groups.setdefault(group_key, []).append(m)

    for key in sorted(groups.keys()):
        group = groups[key]
        year, quarter = key
        quarters.append(
            _SpanDef(
                class_=TimeSpanClass.QUARTER.value,
                name=f"Y{year}Q{quarter + 1}",
                start_date=group[0].start_date,
                end_date=group[-1].end_date,
                child_names=[m.name for m in group],
            )
        )
    return quarters


def _iter_hyears(quarters: List[_SpanDef]) -> List[_SpanDef]:
    """生成半年跨度定义，名称格式 Y{year}H{half}"""
    hyears = []
    if not quarters:
        return hyears

    groups: Dict[Tuple[int, int], List[_SpanDef]] = {}
    for q in quarters:
        year = q.start_date.year
        quarter_index = (q.start_date.month - 1) // 3
        half = quarter_index // 2
        group_key = (year, half)
        groups.setdefault(group_key, []).append(q)

    for key in sorted(groups.keys()):
        group = groups[key]
        year, half = key
        hyears.append(
            _SpanDef(
                class_=TimeSpanClass.HYEAR.value,
                name=f"Y{year}H{half + 1}",
                start_date=group[0].start_date,
                end_date=group[-1].end_date,
                child_names=[q.name for q in group],
            )
        )
    return hyears


def _iter_years(hyears: List[_SpanDef]) -> List[_SpanDef]:
    """生成年跨度定义，名称格式 Y{year}"""
    years = []
    if not hyears:
        return years

    groups: Dict[int, List[_SpanDef]] = {}
    for h in hyears:
        year = h.start_date.year
        groups.setdefault(year, []).append(h)

    for year in sorted(groups.keys()):
        group = groups[year]
        years.append(
            _SpanDef(
                class_=TimeSpanClass.YEAR.value,
                name=f"Y{year}",
                start_date=group[0].start_date,
                end_date=group[-1].end_date,
                child_names=[h.name for h in group],
            )
        )
    return years


# ============================================================================
# Initialization Logic
# ============================================================================


def init_days_impl(
    db: Session,
    start_date: date = date(1999, 4, 19),
    end_date: date = date(2100, 1, 1),
) -> int:
    """幂等初始化自然日表

    在 [start_date, end_date) 范围内创建所有不存在的 Day 记录。

    Returns:
        int: 新创建的自然日数量
    """
    if start_date >= end_date:
        return 0

    existing_dates = {d[0] for d in db.query(Day.date).filter(
        Day.date >= start_date, Day.date < end_date
    ).all()}

    new_days = []
    cursor = start_date
    while cursor < end_date:
        if cursor not in existing_dates:
            new_days.append(Day(date=cursor, ref={}))
        cursor += timedelta(days=1)

    if new_days:
        db.add_all(new_days)
        db.commit()
        logger.info(f"Initialized {len(new_days)} new days")
    else:
        logger.info("No new days to initialize")

    return len(new_days)


def init_timespans_impl(
    db: Session,
    start_date: date = date(1999, 4, 19),
    end_date: date = date(2100, 1, 1),
) -> Dict[str, int]:
    """幂等初始化时间跨度表

    在 [start_date, end_date) 范围内创建所有不存在的自然 TimeSpan，
    并建立父子关系。

    Returns:
        Dict[str, int]: 各 class 新创建/更新的数量
    """
    if start_date >= end_date:
        return {}

    # 确保 days 已存在
    days = db.query(Day).filter(Day.date >= start_date, Day.date < end_date).all()
    if not days:
        raise ValueError("指定范围内没有 Day 记录，请先调用 init_days_impl")

    date_to_id = {d.date: d.id for d in days}
    global_start = min(date_to_id.keys())
    global_end = max(date_to_id.keys()) + timedelta(days=1)

    # 生成所有自然跨度定义
    weeks = _iter_weeks(global_start, global_end)
    biweeks = _iter_biweeks(weeks)
    months = _iter_months(global_start, global_end)
    bimonths = _iter_bimonths(months)
    quarters = _iter_quarters(months)
    hyears = _iter_hyears(quarters)
    years = _iter_years(hyears)

    all_defs = weeks + biweeks + months + bimonths + quarters + hyears + years

    # 查询已存在的跨度，按 (class, name) 索引
    existing_spans = (
        db.query(TimeSpan)
        .filter(TimeSpan.class_.in_([d.class_ for d in all_defs]))
        .all()
    )
    existing_key_to_span = {(s.class_, s.name): s for s in existing_spans}

    # 创建缺失的跨度
    created_count = 0
    new_spans = []
    for d in all_defs:
        key = (d.class_, d.name)
        if key in existing_key_to_span:
            # 可选择更新 start/end day id，但名称决定后不应变化
            continue
        start_id = date_to_id.get(d.start_date)
        end_id = date_to_id.get(d.end_date)
        if start_id is None or end_id is None:
            logger.warning(
                f"Skipping span {d.name}: day id not found for "
                f"{d.start_date} or {d.end_date}"
            )
            continue
        span = TimeSpan(
            class_=d.class_,
            name=d.name,
            start_day_id=start_id,
            end_day_id=end_id,
            child_span_ids=[],
            ref={},
        )
        new_spans.append(span)
        created_count += 1

    if new_spans:
        db.add_all(new_spans)
        db.commit()
        for span in new_spans:
            db.refresh(span)
        logger.info(f"Initialized {len(new_spans)} new timespans")

    # 重新查询所有相关跨度以建立 name -> id 映射
    refreshed_spans = (
        db.query(TimeSpan)
        .filter(TimeSpan.class_.in_([d.class_ for d in all_defs]))
        .all()
    )
    key_to_id = {(s.class_, s.name): s.id for s in refreshed_spans}

    # 建立/更新父子关系
    updated_parents = 0
    for d in all_defs:
        key = (d.class_, d.name)
        span_id = key_to_id.get(key)
        if span_id is None:
            continue
        span = db.query(TimeSpan).filter(TimeSpan.id == span_id).first()
        if span is None:
            continue

        child_ids = []
        for child_name in d.child_names:
            child_key = (_child_class(d.class_), child_name)
            child_id = key_to_id.get(child_key)
            if child_id is not None:
                child_ids.append(child_id)

        # 即使子关系无变化也写入，保证幂等且一致
        if set(span.child_span_ids or []) != set(child_ids):
            span.child_span_ids = child_ids
            updated_parents += 1

    if updated_parents > 0:
        db.commit()
        logger.info(f"Updated {updated_parents} parent timespan child relationships")

    # 统计各 class 的数量
    stats = {}
    for class_ in {d.class_ for d in all_defs}:
        stats[class_] = (
            db.query(TimeSpan).filter(TimeSpan.class_ == class_).count()
        )

    return stats


def _child_class(parent_class: str) -> str:
    """根据父类型返回对应的子类型"""
    mapping = {
        TimeSpanClass.YEAR.value: TimeSpanClass.HYEAR.value,
        TimeSpanClass.HYEAR.value: TimeSpanClass.QUARTER.value,
        TimeSpanClass.QUARTER.value: TimeSpanClass.MONTH.value,
        TimeSpanClass.BIMONTH.value: TimeSpanClass.MONTH.value,
        TimeSpanClass.BIWEEK.value: TimeSpanClass.WEEK.value,
    }
    return mapping.get(parent_class, TimeSpanClass.CUSTOM.value)


def init_time_system_impl(
    db: Session,
    start_date: date = date(1999, 4, 19),
    end_date: date = date(2100, 1, 1),
) -> Dict[str, Any]:
    """幂等初始化完整时间系统

    先初始化 Day，再初始化 TimeSpan 并建立父子关系。

    Returns:
        Dict containing days_count and timespans stats
    """
    days_count = init_days_impl(db, start_date, end_date)
    timespan_stats = init_timespans_impl(db, start_date, end_date)
    total_spans = sum(timespan_stats.values())
    logger.info(
        f"Time system initialized: {db.query(Day).count()} total days, "
        f"{total_spans} total spans"
    )
    return {
        "days_created": days_count,
        "total_days": db.query(Day).count(),
        "timespans": timespan_stats,
        "total_spans": total_spans,
    }
