# -*- coding: utf-8 -*-
# @file pems.py
# @brief Personal Energy Management System Model Layer
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
个人精力管理系统(PEMS) 模型层

基于 Day/TimeSpan 时间底座，聚合 Project、Mission、Health 数据。
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.life import Day, TimeSpan, Rhythm, TimeLog
from sail_server.infrastructure.orm.project import Project, Mission, Milestone
from sail_server.infrastructure.orm.health import (
    Weight,
    Exercise,
    Sleep,
    EnergyLevel,
    Mood,
    HealthSignal,
)
from sail_server.application.dto.project import MissionState
from sail_server.application.dto.pems import (
    RhythmClass,
    EnergyBudgetResponse,
    HealthSignalSummary,
    PemsMissionBrief,
    DayViewResponse,
    TimeSpanViewResponse,
    ProjectTimelineResponse,
    InsightResponse,
    InsightSeverity,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helpers
# ============================================================================


def _get_or_create_day(db: Session, query_date: date) -> Optional[Day]:
    """获取或创建指定日期的 Day 记录"""
    day = db.query(Day).filter(Day.date == query_date).first()
    if day is not None:
        return day
    from sail_server.model.life import init_days_impl

    try:
        init_days_impl(db, query_date, query_date + timedelta(days=1))
    except Exception as e:
        logger.warning(f"Failed to init day {query_date}: {e}")
    return db.query(Day).filter(Day.date == query_date).first()


def _date_range(query_date: date) -> tuple[datetime, datetime]:
    """返回自然日的起止时间"""
    start = datetime(query_date.year, query_date.month, query_date.day)
    end = start + timedelta(days=1)
    return start, end


def _get_rhythm_for_day(db: Session, day: Day) -> tuple[str, int]:
    """获取某日的节律分类与精力系数

    Returns:
        tuple(rhythm_class, energy_multiplier_percent)
    """
    # 1. 特定日规则
    rhythm = db.query(Rhythm).filter(Rhythm.day_id == day.id).first()
    if rhythm is not None:
        return rhythm.class_, rhythm.energy_multiplier or 100

    # 2. 周期性规则
    weekday = day.date.weekday()
    rhythm = db.query(Rhythm).filter(Rhythm.weekday == weekday).first()
    if rhythm is not None:
        return rhythm.class_, rhythm.energy_multiplier or 100

    # 3. 默认规则
    if weekday < 5:
        return RhythmClass.WORKDAY, 100
    return RhythmClass.RESTDAY, 60


def _compute_health_multiplier(
    db: Session, day: Day, rhythm_class: str
) -> tuple[int, List[str]]:
    """根据健康信号计算精力修正系数"""
    warnings: List[str] = []
    multiplier = 100

    sleep = (
        db.query(Sleep).filter(Sleep.day_id == day.id).order_by(Sleep.htime.desc()).first()
    )
    if sleep is not None:
        hours = sleep.hours / 60.0
        if hours < 6:
            multiplier -= 20
            warnings.append(f"睡眠不足({hours:.1f}h)，精力预算 -20%")
        if sleep.quality <= 2:
            multiplier -= 10
            warnings.append("睡眠质量较差，精力预算 -10%")

    energy = (
        db.query(EnergyLevel)
        .filter(EnergyLevel.day_id == day.id)
        .order_by(EnergyLevel.htime.desc())
        .first()
    )
    if energy is not None and energy.score <= 2:
        multiplier -= 10
        warnings.append("精力评分较低，精力预算 -10%")

    mood = (
        db.query(Mood).filter(Mood.day_id == day.id).order_by(Mood.htime.desc()).first()
    )
    if mood is not None and mood.score <= 2:
        multiplier -= 5
        warnings.append("情绪评分较低，精力预算 -5%")

    # 连续工作日惩罚（仅对工作日）
    if rhythm_class == RhythmClass.WORKDAY:
        consecutive = 0
        cursor = day.date - timedelta(days=1)
        while True:
            prev_day = db.query(Day).filter(Day.date == cursor).first()
            if prev_day is None:
                break
            prev_rhythm, _ = _get_rhythm_for_day(db, prev_day)
            if prev_rhythm == RhythmClass.WORKDAY:
                consecutive += 1
                cursor -= timedelta(days=1)
            else:
                break
        if consecutive > 5:
            penalty = (consecutive - 5) * 5
            multiplier -= penalty
            warnings.append(f"连续工作 {consecutive} 天，精力预算 -{penalty}%")

    return max(0, multiplier), warnings


def _health_signal_summary(db: Session, day: Day) -> HealthSignalSummary:
    """汇总当日健康信号"""
    start, end = _date_range(day.date)

    sleep = (
        db.query(Sleep).filter(Sleep.day_id == day.id).order_by(Sleep.htime.desc()).first()
    )
    energy = (
        db.query(EnergyLevel)
        .filter(EnergyLevel.day_id == day.id)
        .order_by(EnergyLevel.htime.desc())
        .first()
    )
    mood = (
        db.query(Mood).filter(Mood.day_id == day.id).order_by(Mood.htime.desc()).first()
    )

    weight = (
        db.query(Weight)
        .filter(Weight.htime >= start, Weight.htime < end)
        .order_by(Weight.htime.desc())
        .first()
    )
    exercise_count = (
        db.query(Exercise)
        .filter(Exercise.htime >= start, Exercise.htime < end)
        .count()
    )

    return HealthSignalSummary(
        sleep_hours=sleep.hours / 60.0 if sleep else None,
        sleep_quality=sleep.quality if sleep else None,
        energy_level=energy.score if energy else None,
        mood=mood.score if mood else None,
        weight_value=float(weight.value) if weight and weight.value else None,
        exercise_count=exercise_count,
    )


def _project_name(db: Session, project_id: Optional[int]) -> Optional[str]:
    if project_id is None:
        return None
    project = db.query(Project).filter(Project.id == project_id).first()
    return project.name if project else None


def _mission_to_brief(db: Session, mission: Mission) -> PemsMissionBrief:
    return PemsMissionBrief(
        id=mission.id,
        name=mission.name,
        project_id=mission.project_id,
        project_name=_project_name(db, mission.project_id),
        state=mission.state,
        energy_cost=mission.energy_cost or 0,
        planned_minutes=mission.planned_minutes or 0,
        health_constraint=mission.health_constraint or "normal",
    )


def _missions_for_day(db: Session, day: Day) -> List[Mission]:
    """获取归属于某日的任务（含通过 ddl 兼容旧数据）"""
    start, end = _date_range(day.date)
    return (
        db.query(Mission)
        .filter(
            (Mission.day_id == day.id)
            | (
                (Mission.day_id.is_(None))
                & (Mission.ddl >= start)
                & (Mission.ddl < end)
            )
        )
        .order_by(Mission.energy_cost.desc())
        .all()
    )


def _challenge_checkins(db: Session, day: Day) -> Dict[str, str]:
    """简单打卡状态：按 challenge 项目分组"""
    challenges = (
        db.query(Project)
        .filter(Project.name.like("#challenge#%"))
        .all()
    )
    start, end = _date_range(day.date)
    result: Dict[str, str] = {}
    for challenge in challenges:
        parts = challenge.name.split("#")
        title = parts[-1] if len(parts) >= 4 else challenge.name
        mission = (
            db.query(Mission)
            .filter(
                Mission.project_id == challenge.id,
                (
                    (Mission.day_id == day.id)
                    | (
                        (Mission.day_id.is_(None))
                        & (Mission.ddl >= start)
                        & (Mission.ddl < end)
                    )
                ),
            )
            .first()
        )
        if mission is None:
            continue
        if mission.state == MissionState.DONE:
            result[title] = "success"
        elif mission.state == MissionState.CANCELED:
            result[title] = "skipped"
        else:
            result[title] = "pending"
    return result


def _compute_energy_budget(
    db: Session, day: Day
) -> EnergyBudgetResponse:
    """计算某日精力预算"""
    rhythm_class, rhythm_multiplier = _get_rhythm_for_day(db, day)
    health_multiplier, warnings = _compute_health_multiplier(db, day, rhythm_class)

    base_energy = 100
    budget = int(base_energy * (rhythm_multiplier / 100.0) * (health_multiplier / 100.0))

    missions = _missions_for_day(db, day)
    planned = sum(m.energy_cost or 0 for m in missions if m.state not in (
        MissionState.DONE, MissionState.CANCELED
    ))
    actual = sum(m.energy_cost or 0 for m in missions if m.state == MissionState.DONE)
    actual_log = (
        db.query(func.coalesce(func.sum(TimeLog.energy_cost), 0))
        .filter(TimeLog.day_id == day.id)
        .scalar()
    )
    actual += actual_log or 0

    if planned > budget:
        warnings.append(
            f"已安排任务精力({planned})超出预算({budget})，建议减少或拆分任务"
        )

    return EnergyBudgetResponse(
        date=day.date,
        day_id=day.id,
        rhythm=rhythm_class,
        base_energy=base_energy,
        health_multiplier=health_multiplier,
        energy_budget=budget,
        energy_planned=planned,
        energy_actual=actual or 0,
        warning_messages=warnings,
    )


def _generate_insights(
    db: Session, day: Day, budget: EnergyBudgetResponse
) -> List[InsightResponse]:
    """基于规则生成当日洞察"""
    insights: List[InsightResponse] = []
    start, end = _date_range(day.date)

    # 逾期任务
    overdue = (
        db.query(Mission)
        .filter(
            Mission.ddl < start,
            Mission.state.notin_([MissionState.DONE, MissionState.CANCELED]),
        )
        .all()
    )
    if overdue:
        insights.append(
            InsightResponse(
                type="overdue",
                severity=InsightSeverity.DANGER,
                title="存在逾期任务",
                message=f"有 {len(overdue)} 个任务已逾期，建议优先处理或重新排期。",
            )
        )

    # 精力过载
    if budget.energy_planned > budget.energy_budget:
        insights.append(
            InsightResponse(
                type="energy_overload",
                severity=InsightSeverity.WARNING,
                title="当日精力过载",
                message=f"已安排精力 {budget.energy_planned} 超过预算 {budget.energy_budget}。",
            )
        )

    # 健康异常
    sleep = (
        db.query(Sleep).filter(Sleep.day_id == day.id).order_by(Sleep.htime.desc()).first()
    )
    if sleep and sleep.hours / 60.0 < 6:
        insights.append(
            InsightResponse(
                type="sleep_short",
                severity=InsightSeverity.WARNING,
                title="睡眠不足",
                message="昨晚睡眠少于 6 小时，今日建议减少高强度任务。",
            )
        )

    # 运动缺失（工作日）
    if budget.rhythm == RhythmClass.WORKDAY:
        exercise_count = (
            db.query(Exercise)
            .filter(Exercise.htime >= start, Exercise.htime < end)
            .count()
        )
        if exercise_count == 0:
            insights.append(
                InsightResponse(
                    type="exercise_missing",
                    severity=InsightSeverity.INFO,
                    title="今日暂无运动记录",
                    message="工作日建议安排轻度运动以维持精力。",
                )
            )

    return insights


# ============================================================================
# Day View
# ============================================================================


def get_day_view_impl(db: Session, query_date: date) -> DayViewResponse:
    """获取某日 PEMS 完整视图"""
    day = _get_or_create_day(db, query_date)
    if day is None:
        raise ValueError(f"无法获取或创建日期: {query_date}")

    budget = _compute_energy_budget(db, day)
    health = _health_signal_summary(db, day)
    missions = _missions_for_day(db, day)
    planned = [
        _mission_to_brief(db, m)
        for m in missions
        if m.state not in (MissionState.DONE, MissionState.CANCELED)
    ]
    completed = [
        _mission_to_brief(db, m) for m in missions if m.state == MissionState.DONE
    ]
    checkins = _challenge_checkins(db, day)
    insights = _generate_insights(db, day, budget)
    note = (day.ref or {}).get("note")

    return DayViewResponse(
        date=day.date,
        day_id=day.id,
        rhythm=budget.rhythm,
        energy_budget=budget,
        health_signals=health,
        planned_missions=planned,
        completed_missions=completed,
        challenge_checkins=checkins,
        insights=insights,
        note=note,
    )


def plan_mission_on_day_impl(
    db: Session, query_date: date, mission_id: int
) -> Optional[PemsMissionBrief]:
    """将任务安排到指定日期"""
    day = _get_or_create_day(db, query_date)
    if day is None:
        raise ValueError(f"无法获取或创建日期: {query_date}")

    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if mission is None:
        return None

    mission.day_id = day.id
    mission.ddl = datetime(
        query_date.year, query_date.month, query_date.day, 23, 59, 59
    )
    db.commit()
    db.refresh(mission)
    return _mission_to_brief(db, mission)


def log_health_on_day_impl(
    db: Session,
    query_date: date,
    sleep_hours: Optional[float] = None,
    sleep_quality: Optional[int] = None,
    energy_level: Optional[int] = None,
    mood: Optional[int] = None,
    note: Optional[str] = None,
) -> HealthSignalSummary:
    """在某日快速记录健康信号"""
    day = _get_or_create_day(db, query_date)
    if day is None:
        raise ValueError(f"无法获取或创建日期: {query_date}")

    htime = datetime(query_date.year, query_date.month, query_date.day, 9, 0, 0)

    if sleep_hours is not None or sleep_quality is not None:
        sleep = Sleep(
            day_id=day.id,
            htime=htime,
            hours=int(round((sleep_hours or 0) * 60)),
            quality=sleep_quality or 3,
            description=note or "",
        )
        db.add(sleep)

    if energy_level is not None:
        energy = EnergyLevel(
            day_id=day.id,
            htime=htime,
            score=energy_level,
            description=note or "",
        )
        db.add(energy)

    if mood is not None:
        mood_rec = Mood(
            day_id=day.id,
            htime=htime,
            score=mood,
            description=note or "",
        )
        db.add(mood_rec)

    if note is not None:
        ref = day.ref or {}
        ref["note"] = note
        day.ref = ref

    db.commit()
    return _health_signal_summary(db, day)


# ============================================================================
# TimeSpan View
# ============================================================================


def get_timespan_view_impl(db: Session, span_id: int) -> TimeSpanViewResponse:
    """获取周期视图"""
    span = db.query(TimeSpan).filter(TimeSpan.id == span_id).first()
    if span is None:
        raise ValueError(f"TimeSpan 不存在: {span_id}")

    start_day = db.query(Day).filter(Day.id == span.start_day_id).first()
    end_day = db.query(Day).filter(Day.id == span.end_day_id).first()
    start_date = start_day.date if start_day else date.min
    end_date = end_day.date if end_day else date.min

    ref = span.ref or {}
    projects = db.query(Project).filter(Project.timespan_id == span_id).all()
    project_ids = [p.id for p in projects]

    energy_capacity = ref.get("energy_capacity", 0)
    energy_consumed = sum(p.energy_budget or 0 for p in projects)

    day_count = (
        db.query(Day)
        .filter(Day.date >= start_date, Day.date <= end_date)
        .count()
    )

    return TimeSpanViewResponse(
        id=span.id,
        class_=span.class_,
        name=span.name,
        start_date=start_date,
        end_date=end_date,
        theme=ref.get("theme"),
        energy_capacity=energy_capacity,
        energy_consumed=energy_consumed,
        project_ids=project_ids,
        health_goals=ref.get("health_goals", {}),
        review_note=ref.get("review_note"),
        focus_areas=ref.get("focus_areas", []),
        day_count=day_count,
    )


def review_timespan_impl(
    db: Session, span_id: int, review_note: str, theme: Optional[str], focus_areas: Optional[List[str]]
) -> TimeSpanViewResponse:
    """提交周期复盘"""
    span = db.query(TimeSpan).filter(TimeSpan.id == span_id).first()
    if span is None:
        raise ValueError(f"TimeSpan 不存在: {span_id}")

    ref = span.ref or {}
    ref["review_note"] = review_note
    if theme is not None:
        ref["theme"] = theme
    if focus_areas is not None:
        ref["focus_areas"] = list(focus_areas)
    span.ref = ref
    db.commit()
    db.refresh(span)
    return get_timespan_view_impl(db, span_id)


# ============================================================================
# Project Timeline
# ============================================================================


def get_project_timeline_impl(db: Session, project_id: int) -> ProjectTimelineResponse:
    """获取项目时间线"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise ValueError(f"Project 不存在: {project_id}")

    milestones = (
        db.query(Milestone)
        .filter(Milestone.project_id == project_id)
        .order_by(Milestone.day_id)
        .all()
    )
    milestone_list = []
    for m in milestones:
        day = db.query(Day).filter(Day.id == m.day_id).first()
        milestone_list.append(
            {
                "id": m.id,
                "name": m.name,
                "date": day.date.isoformat() if day else None,
                "state": m.state,
                "energy_weight": m.energy_weight,
            }
        )

    missions = (
        db.query(Mission)
        .filter(Mission.project_id == project_id)
        .order_by(Mission.day_id)
        .all()
    )
    mission_briefs = [_mission_to_brief(db, m) for m in missions]

    mission_ids = [m.id for m in missions]
    timelogs = []
    if mission_ids:
        logs = (
            db.query(TimeLog)
            .filter(TimeLog.mission_id.in_(mission_ids))
            .order_by(TimeLog.start_time)
            .all()
        )
        for log in logs:
            timelogs.append(
                {
                    "id": log.id,
                    "mission_id": log.mission_id,
                    "day_id": log.day_id,
                    "duration_minutes": log.duration_minutes,
                    "energy_cost": log.energy_cost,
                    "description": log.description,
                }
            )

    return ProjectTimelineResponse(
        project_id=project.id,
        project_name=project.name,
        timespan_id=project.timespan_id,
        energy_budget=project.energy_budget or 0,
        milestones=milestone_list,
        missions=mission_briefs,
        timelogs=timelogs,
    )


# ============================================================================
# Energy Budget & Insights
# ============================================================================


def get_energy_budget_impl(db: Session, query_date: date) -> EnergyBudgetResponse:
    """获取某日精力预算"""
    day = _get_or_create_day(db, query_date)
    if day is None:
        raise ValueError(f"无法获取或创建日期: {query_date}")
    return _compute_energy_budget(db, day)


def get_insight_daily_impl(db: Session, query_date: date) -> List[InsightResponse]:
    """获取每日洞察"""
    day = _get_or_create_day(db, query_date)
    if day is None:
        raise ValueError(f"无法获取或创建日期: {query_date}")
    budget = _compute_energy_budget(db, day)
    return _generate_insights(db, day, budget)


def get_insight_weekly_impl(db: Session, query_date: date) -> List[InsightResponse]:
    """获取双周洞察（包含该日的双周）"""
    day = _get_or_create_day(db, query_date)
    if day is None:
        raise ValueError(f"无法获取或创建日期: {query_date}")

    span = (
        db.query(TimeSpan)
        .filter(
            TimeSpan.class_ == "biweek",
            TimeSpan.start_day_id <= day.id,
            TimeSpan.end_day_id >= day.id,
        )
        .first()
    )
    if span is None:
        return [
            InsightResponse(
                type="no_biweek",
                severity=InsightSeverity.INFO,
                title="未找到双周周期",
                message="当前日期尚未生成双周时间跨度。",
            )
        ]

    start_day = db.query(Day).filter(Day.id == span.start_day_id).first()
    end_day = db.query(Day).filter(Day.id == span.end_day_id).first()
    start_date = start_day.date if start_day else query_date
    end_date = end_day.date if end_day else query_date

    insights: List[InsightResponse] = []

    # 项目进度
    projects = db.query(Project).filter(Project.timespan_id == span.id).all()
    for project in projects:
        total = (
            db.query(Mission)
            .filter(Mission.project_id == project.id)
            .count()
        )
        done = (
            db.query(Mission)
            .filter(
                Mission.project_id == project.id,
                Mission.state == MissionState.DONE,
            )
            .count()
        )
        if total > 0:
            progress = done / total
            if progress < 0.3:
                insights.append(
                    InsightResponse(
                        type="project_progress",
                        severity=InsightSeverity.WARNING,
                        title=f"项目进度偏低: {project.name}",
                        message=f"双周进度 {progress:.0%}，建议加速推进。",
                    )
                )

    # 健康运动量
    exercise_count = (
        db.query(Exercise)
        .filter(Exercise.htime >= datetime(start_date.year, start_date.month, start_date.day))
        .filter(Exercise.htime < datetime(end_date.year, end_date.month, end_date.day) + timedelta(days=1))
        .count()
    )
    if exercise_count < 3:
        insights.append(
            InsightResponse(
                type="weekly_exercise",
                severity=InsightSeverity.INFO,
                title="双周运动不足",
                message=f"本双周仅运动 {exercise_count} 次，建议安排更多运动。",
            )
        )

    return insights
