# -*- coding: utf-8 -*-
# @file reminder_scheduler.py
# @brief Reminder Scheduler (提醒调度扫描循环)
# @author sailing-innocent
# @date 2026-08-03
# @version 1.0
# ---------------------------------

"""
提醒调度器（Android App M1）

结构完全仿照 model/weather.py::weather_update_loop（asyncio 无限循环 +
指数退避 + CancelledError 安静退出），在 server.py::on_startup 中
asyncio.create_task 启动、on_shutdown cancel。

> 设计文档 §5.4 写的是 APScheduler，实施时采用与 weather 一致的
> asyncio loop：零新基础设施、启停钩子现成、30s 扫描粒度足够。
> scan_once 为纯同步函数，便于单元测试直接调用，后续如需替换
> APScheduler 触发器可平滑迁移。

每轮扫描（scan_once）执行四类处理：

1. 到点投递：PENDING AND trigger_time<=now → DELIVERED + delivered 事件 + WS 推送
2. snooze 重投：SNOOZED AND next_trigger_time<=now → DELIVERED + delivered{redelivery} + 推送
3. OPENED 回落：OPENED AND updated_at<=now-30min → DELIVERED + redelivered{open_timeout} + 推送
4. 过期处理：DELIVERED AND last_delivered_at<=now-expire_after_minutes → EXPIRED + expired 事件，
   随后按 rule.retry_policy：retry_count<max_retry → 回 PENDING（retry_count+1），否则 → ARCHIVED
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.life import Day
from sail_server.infrastructure.orm.reminder import Reminder, ReminderRule
from sail_server.model.reminder import (
    DEFAULT_QUIET_HOURS,
    STATE_ARCHIVED,
    STATE_DELIVERED,
    STATE_EXPIRED,
    STATE_OPENED,
    STATE_PENDING,
    STATE_SNOOZED,
    _add_event,
    is_in_quiet_hours,
    read_from_reminder,
)

logger = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL_SECONDS = 30
MAX_BACKOFF_SECONDS = 30 * 60

#: OPENED 无完成回落时长（设计文档 §2.3.1：30 分钟）
OPEN_FALLBACK_MINUTES = 30

#: 无 rule 时的默认重试策略
DEFAULT_MAX_RETRY = 0
DEFAULT_RETRY_INTERVAL_MINUTES = 60


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"[reminder] invalid int env {name}={raw!r}, use {default}")
        return default


def _generate_rhythm_daily_brief(db: Session, now: datetime) -> int:
    """基于 Rhythm 画像与当日数据生成日常提醒（早安/三餐/工作焦点/运动/体重）。

    幂等：同一天同类 brief 只生成一次。
    """
    from datetime import time as _time

    from sail_server.infrastructure.orm.health import Weight
    from sail_server.infrastructure.orm.rhythm import (
        RhythmAffair,
        RhythmDisciplineLog,
    )
    from sail_server.model.rhythm import get_or_create_profile

    profile = get_or_create_profile(db)
    today = now.date()
    day = db.query(Day).filter(Day.date == today).first()
    day_id = day.id if day else None

    created = 0

    def _today_exists(type_: str) -> bool:
        return (
            db.query(Reminder)
            .filter(
                Reminder.type == type_,
                Reminder.trigger_time >= datetime.combine(today, datetime.min.time()),
                Reminder.trigger_time < datetime.combine(today + timedelta(days=1), datetime.min.time()),
            )
            .first()
            is not None
        )

    def _create(type_: str, title: str, body: str, trigger: datetime, payload: Dict[str, Any]) -> None:
        nonlocal created
        if _today_exists(type_):
            return
        quiet_hours = profile.spare_time_windows or DEFAULT_QUIET_HOURS
        if is_in_quiet_hours(quiet_hours, trigger):
            return
        r = Reminder(
            type=type_,
            title=title,
            body=body,
            priority="normal",
            source="rhythm",
            state=STATE_PENDING,
            trigger_time=trigger,
            expire_after_minutes=120,
            payload=payload,
        )
        db.add(r)
        db.flush()
        _add_event(db, r.id, "created", {"source": "rhythm_daily_brief"})
        created += 1

    def _time(hour: int, minute: int) -> datetime:
        return datetime.combine(today, _time(hour, minute))

    # 起床提醒：sleep_end
    sleep_end = str(profile.sleep_end or "07:00")
    h, m = int(sleep_end.split(":")[0]), int(sleep_end.split(":")[1])
    _create("rhythm.daily_brief", "早安，准备开始一天", "查看今日 Rhythm 安排", _time(h, m), {"sub_type": "wake_up"})

    # 三餐提醒
    for label, hh, mm in [("早餐", 8, 0), ("午餐", 12, 0), ("晚餐", 18, 30)]:
        _create(
            "rhythm.meal",
            f"{label}时间",
            f"记录{label}",
            _time(hh, mm),
            {"meal_type": label, "collection_type": "meal"},
        )

    # 体重（若今日无体重记录）
    has_weight = False
    if day_id:
        day_start = datetime.combine(today, datetime.min.time())
        has_weight = db.query(Weight).filter(Weight.htime >= day_start).first() is not None
    if not has_weight:
        _create(
            "rhythm.weight",
            "记录今日体重",
            "早起体重打卡",
            _time(8, 30),
            {"collection_type": "weight"},
        )

    # 工作焦点
    _create(
        "rhythm.work_focus",
        "进入工作焦点",
        "查看今日 focus 块并开始执行",
        _time(9, 30),
        {"sub_type": "morning_focus"},
    )

    # 运动习惯：若存在 habit 且今日无完成记录
    exercise_habit = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == "habit",
            RhythmAffair.title.ilike("%运动%"),
            RhythmAffair.state == "ACTIVE",
        )
        .first()
    )
    if exercise_habit and day_id:
        done_today = (
            db.query(RhythmDisciplineLog)
            .filter(
                RhythmDisciplineLog.affair_id == exercise_habit.id,
                RhythmDisciplineLog.log_date == today,
                RhythmDisciplineLog.result == "done",
            )
            .first()
            is not None
        )
        if not done_today:
            _create(
                "rhythm.exercise",
                "运动打卡",
                exercise_habit.title,
                _time(19, 0),
                {"collection_type": "exercise", "affair_id": exercise_habit.id},
            )

    # 睡眠提醒：sleep_start 前 30 分钟
    sleep_start = str(profile.sleep_start or "23:30")
    h, m = int(sleep_start.split(":")[0]), int(sleep_start.split(":")[1])
    _create(
        "rhythm.daily_brief",
        "准备入睡",
        f"{sleep_start} 睡眠窗即将开始",
        _time(h, m) - timedelta(minutes=30),
        {"sub_type": "sleep_prep"},
    )

    db.commit()
    return created


def scan_once(
    db_factory: Callable[[], Session],
    push: Optional[Callable[[Dict[str, Any]], None]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, int]:
    """执行一轮调度扫描（纯同步函数，单元测试可直接调用）。

    :param db_factory: 会话工厂
    :param push: 推送回调（接收 ReminderResponse dict），None 表示仅落库不推送
    :param now: 注入当前时间（测试用），默认服务器本地时间
    :return: 各类处理计数
    """
    now = now or datetime.now()
    stats: Dict[str, int] = {
        "delivered": 0,
        "redelivered": 0,
        "fallback": 0,
        "expired": 0,
        "retried": 0,
        "archived": 0,
        "rhythm_brief_created": 0,
    }
    pushed_payloads: List[Dict[str, Any]] = []

    db = db_factory()
    try:
        # --------------------------------------------------------------
        # 0. Rhythm 日常 brief 生成
        # --------------------------------------------------------------
        try:
            stats["rhythm_brief_created"] = _generate_rhythm_daily_brief(db, now)
        except Exception as e:
            logger.warning(f"[reminder] rhythm daily brief generation failed: {e}")
            stats["rhythm_brief_created"] = 0

        # --------------------------------------------------------------
        # 1. 到点投递：PENDING AND trigger_time <= now
        # --------------------------------------------------------------
        rows = (
            db.query(Reminder)
            .filter(
                Reminder.state == STATE_PENDING,
                Reminder.trigger_time <= now,
            )
            .all()
        )
        for r in rows:
            r.state = STATE_DELIVERED
            r.last_delivered_at = now
            _add_event(db, r.id, "delivered", {})
            db.commit()
            pushed_payloads.append(read_from_reminder(r).model_dump(mode="json"))
            stats["delivered"] += 1

        # --------------------------------------------------------------
        # 2. snooze 重投：SNOOZED AND next_trigger_time <= now
        # --------------------------------------------------------------
        rows = (
            db.query(Reminder)
            .filter(
                Reminder.state == STATE_SNOOZED,
                Reminder.next_trigger_time.isnot(None),
                Reminder.next_trigger_time <= now,
            )
            .all()
        )
        for r in rows:
            r.state = STATE_DELIVERED
            r.last_delivered_at = now
            r.next_trigger_time = None
            _add_event(
                db,
                r.id,
                "delivered",
                {"redelivery": True, "snooze_count": r.snooze_count or 0},
            )
            db.commit()
            pushed_payloads.append(read_from_reminder(r).model_dump(mode="json"))
            stats["redelivered"] += 1

        # --------------------------------------------------------------
        # 3. OPENED 回落：OPENED AND updated_at <= now - 30min
        # --------------------------------------------------------------
        fallback_before = now - timedelta(minutes=OPEN_FALLBACK_MINUTES)
        rows = (
            db.query(Reminder)
            .filter(
                Reminder.state == STATE_OPENED,
                Reminder.updated_at.isnot(None),
                Reminder.updated_at <= fallback_before,
            )
            .all()
        )
        for r in rows:
            r.state = STATE_DELIVERED
            r.last_delivered_at = now
            _add_event(db, r.id, "redelivered", {"reason": "open_timeout"})
            db.commit()
            pushed_payloads.append(read_from_reminder(r).model_dump(mode="json"))
            stats["fallback"] += 1

        # --------------------------------------------------------------
        # 4. 过期处理：DELIVERED AND last_delivered_at <= now - expire_after_minutes
        # --------------------------------------------------------------
        rows = (
            db.query(Reminder)
            .filter(
                Reminder.state == STATE_DELIVERED,
                Reminder.last_delivered_at.isnot(None),
            )
            .all()
        )
        for r in rows:
            expire_minutes = r.expire_after_minutes or 240
            if r.last_delivered_at + timedelta(minutes=expire_minutes) > now:
                continue  # 未过期
            r.state = STATE_EXPIRED
            _add_event(db, r.id, "expired", {"expire_after_minutes": expire_minutes})
            stats["expired"] += 1

            # 按 rule.retry_policy 决定重投或归档
            retry_policy: Dict[str, Any] = {}
            if r.rule_id is not None:
                rule = (
                    db.query(ReminderRule)
                    .filter(ReminderRule.id == r.rule_id)
                    .first()
                )
                if rule is not None:
                    retry_policy = rule.retry_policy or {}
            max_retry = int(retry_policy.get("max_retry", DEFAULT_MAX_RETRY))
            retry_interval = int(
                retry_policy.get("retry_interval_minutes", DEFAULT_RETRY_INTERVAL_MINUTES)
            )

            if (r.retry_count or 0) < max_retry:
                r.retry_count = (r.retry_count or 0) + 1
                r.state = STATE_PENDING
                r.trigger_time = now + timedelta(minutes=retry_interval)
                _add_event(
                    db,
                    r.id,
                    "redelivered",
                    {
                        "reason": "retry",
                        "retry_count": r.retry_count,
                        "next_trigger_time": r.trigger_time.isoformat(),
                    },
                )
                stats["retried"] += 1
            else:
                r.state = STATE_ARCHIVED
                stats["archived"] += 1
            db.commit()
    finally:
        db.close()

    # 推送在 DB 事务全部结束后进行（推送失败不影响状态机）
    if push is not None:
        for payload in pushed_payloads:
            try:
                push(payload)
            except Exception as e:
                logger.warning(f"[reminder] push failed for {payload.get('id')}: {e}")

    return stats


async def reminder_scan_loop(
    db_factory: Callable[[], Session],
    interval_seconds: Optional[int] = None,
) -> None:
    """提醒调度后台循环：启动后立即执行一轮，然后按间隔循环。

    - 间隔取 REMINDER_SCAN_INTERVAL_SECONDS（默认 30s）；
    - 未捕获异常按指数退避（60s 起、30min 封顶）后继续；
    - 任务被取消（服务关闭）时向上抛 CancelledError 安静退出；
    - DB 扫描在 to_thread 中执行，推送经 run_coroutine_threadsafe 回事件循环。
    """
    from sail_server.utils.reminder_ws import get_reminder_push_manager

    interval_seconds = interval_seconds or _env_int(
        "REMINDER_SCAN_INTERVAL_SECONDS", DEFAULT_SCAN_INTERVAL_SECONDS
    )
    manager = get_reminder_push_manager()
    loop = asyncio.get_running_loop()

    def push(payload: Dict[str, Any]) -> None:
        # 无在线设备时不视为错误（WorkManager 轮询 /pending 兜回）
        asyncio.run_coroutine_threadsafe(manager.broadcast_reminder(payload), loop)

    logger.info(f"[reminder] scan loop started, interval={interval_seconds}s")
    backoff_seconds = 0
    while True:
        try:
            stats = await asyncio.to_thread(scan_once, db_factory, push)
            if any(stats.values()):
                logger.info(f"[reminder] scan round done: {stats}")
            backoff_seconds = 0
            sleep_seconds = interval_seconds
        except asyncio.CancelledError:
            logger.info("[reminder] scan loop cancelled")
            raise
        except Exception as e:
            logger.error(f"[reminder] scan round failed: {e}")
            backoff_seconds = (
                min(MAX_BACKOFF_SECONDS, backoff_seconds * 2) if backoff_seconds else 60
            )
            sleep_seconds = backoff_seconds
        await asyncio.sleep(sleep_seconds)
