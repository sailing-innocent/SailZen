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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text
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

#: 过期扫描 SQL 过滤：把 last_delivered_at + expire_after_minutes 的判定下推到数据库，
#: 避免加载全部历史 DELIVERED 行。表达式按后端区分（SQLite / PostgreSQL）。
_SQLITE_EXPIRED_CLAUSE = (
    "datetime(last_delivered_at, '+' || COALESCE(expire_after_minutes, 240) || ' minutes') <= :now"
)
_PG_EXPIRED_CLAUSE = (
    "last_delivered_at + (COALESCE(expire_after_minutes, 240) || ' minutes')::interval <= :now"
)

#: OPENED 无完成回落时长（设计文档 §2.3.1：30 分钟）
OPEN_FALLBACK_MINUTES = 30

#: 无 rule 时的默认重试策略
DEFAULT_MAX_RETRY = 0
DEFAULT_RETRY_INTERVAL_MINUTES = 60

#: 每轮扫描单表最大处理行数，防止启动/重连时阻塞事件循环
DEFAULT_SCAN_BATCH_SIZE = 200


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"[reminder] invalid int env {name}={raw!r}, use {default}")
        return default


def _build_expired_filter(db: Session, now: datetime):
    """构造过期判定 SQL 过滤条件（后端相关），直接由数据库索引驱动。

    SQLite: datetime(last_delivered_at, '+' || expire_after_minutes || ' minutes') <= now
    PostgreSQL: last_delivered_at + (expire_after_minutes || ' minutes')::interval <= now
    """
    backend = db.bind.dialect.name if db.bind else "sqlite"
    if backend == "sqlite":
        return text(_SQLITE_EXPIRED_CLAUSE).bindparams(
            now=now.strftime("%Y-%m-%d %H:%M:%S")
        )
    return text(_PG_EXPIRED_CLAUSE).bindparams(now=now)


def _generate_rhythm_daily_brief(db: Session, now: datetime) -> int:
    """基于 Rhythm 画像与当日数据生成日常提醒（早安/三餐/工作焦点/运动/体重）。

    幂等：同一天同类 brief 只生成一次。
    """
    from datetime import time as _time

    from sail_server.infrastructure.orm.health import Weight, WeightPlan
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

    def _make_time(hour: int, minute: int) -> datetime:
        return datetime.combine(today, _time(hour, minute))

    # 起床提醒：sleep_end
    sleep_end = str(profile.sleep_end or "07:00")
    h, m = int(sleep_end.split(":")[0]), int(sleep_end.split(":")[1])
    _create("rhythm.daily_brief", "早安，准备开始一天", "查看今日 Rhythm 安排", _make_time(h, m), {"sub_type": "wake_up"})

    # 三餐提醒
    for label, hh, mm in [("早餐", 8, 0), ("午餐", 12, 0), ("晚餐", 18, 30)]:
        _create(
            "rhythm.meal",
            f"{label}时间",
            f"记录{label}",
            _make_time(hh, mm),
            {"meal_type": label, "collection_type": "meal"},
        )

    def _today_plan_reminder_exists(plan_id: int) -> bool:
        """检查今天是否已为指定体重计划生成 rhythm.weight 提醒。"""
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today + timedelta(days=1), datetime.min.time())
        # 加 limit 避免历史数据过多时全量加载；同一天同类型计划提醒通常 <= 几个
        reminders = (
            db.query(Reminder)
            .filter(
                Reminder.type == "rhythm.weight",
                Reminder.trigger_time >= start,
                Reminder.trigger_time < end,
            )
            .limit(50)
            .all()
        )
        for r in reminders:
            payload = r.payload or {}
            if payload.get("plan_id") == plan_id:
                return True
        return False

    # 体重计划个性化提醒：每个 notify_enabled=True 的计划按 notify_time 提醒一次
    has_weight = False
    if day_id:
        day_start = datetime.combine(today, datetime.min.time())
        has_weight = (
            db.query(Weight).filter(Weight.htime >= day_start).first() is not None
        )

    active_plans = (
        db.query(WeightPlan)
        .filter(
            WeightPlan.notify_enabled == True,
            WeightPlan.target_time >= datetime.combine(today, datetime.min.time()),
        )
        .all()
    )
    for plan in active_plans:
        if has_weight or _today_plan_reminder_exists(plan.id):
            continue
        notify_time = plan.notify_time or "08:30"
        try:
            hh, mm = map(int, notify_time.split(":"))
        except ValueError:
            hh, mm = 8, 30
        trigger = datetime.combine(today, _time(hh, mm))
        quiet_hours = profile.spare_time_windows or DEFAULT_QUIET_HOURS
        if is_in_quiet_hours(quiet_hours, trigger):
            continue
        r = Reminder(
            type="rhythm.weight",
            title="记录体重",
            body=f"计划 #{plan.id} 体重打卡",
            priority="normal",
            source="rhythm",
            state=STATE_PENDING,
            trigger_time=trigger,
            expire_after_minutes=120,
            payload={
                "collection_type": "weight",
                "plan_id": plan.id,
                "affair_id": plan.rhythm_affair_id,
            },
        )
        db.add(r)
        db.flush()
        _add_event(db, r.id, "created", {"source": "rhythm_weight_plan"})
        created += 1

    # 默认体重提醒（无计划或计划未启用提醒时兜底）
    if not has_weight:
        _create(
            "rhythm.weight",
            "记录今日体重",
            "早起体重打卡",
            _make_time(8, 30),
            {"collection_type": "weight"},
        )

    # 工作焦点
    _create(
        "rhythm.work_focus",
        "进入工作焦点",
        "查看今日 focus 块并开始执行",
                    _make_time(9, 30),
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
                _make_time(19, 0),
                {"collection_type": "exercise", "affair_id": exercise_habit.id},
            )

    # 睡眠提醒：sleep_start 前 30 分钟
    sleep_start = str(profile.sleep_start or "23:30")
    h, m = int(sleep_start.split(":")[0]), int(sleep_start.split(":")[1])
    _create(
        "rhythm.daily_brief",
        "准备入睡",
        f"{sleep_start} 睡眠窗即将开始",
        _make_time(h, m) - timedelta(minutes=30),
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
    batch_size = _env_int("REMINDER_SCAN_BATCH_SIZE", DEFAULT_SCAN_BATCH_SIZE)

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
        # 按 batch 处理，避免历史 PENDING 堆积时一次加载全部行
        while True:
            rows = (
                db.query(Reminder)
                .filter(
                    Reminder.state == STATE_PENDING,
                    Reminder.trigger_time <= now,
                )
                .order_by(Reminder.trigger_time)
                .limit(batch_size)
                .all()
            )
            if not rows:
                break
            for r in rows:
                r.state = STATE_DELIVERED
                r.last_delivered_at = now
                _add_event(db, r.id, "delivered", {})
                pushed_payloads.append(read_from_reminder(r).model_dump(mode="json"))
                stats["delivered"] += 1
            db.commit()
            if len(rows) < batch_size:
                break

        # --------------------------------------------------------------
        # 2. snooze 重投：SNOOZED AND next_trigger_time <= now
        # --------------------------------------------------------------
        while True:
            rows = (
                db.query(Reminder)
                .filter(
                    Reminder.state == STATE_SNOOZED,
                    Reminder.next_trigger_time.isnot(None),
                    Reminder.next_trigger_time <= now,
                )
                .order_by(Reminder.next_trigger_time)
                .limit(batch_size)
                .all()
            )
            if not rows:
                break
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
                pushed_payloads.append(read_from_reminder(r).model_dump(mode="json"))
                stats["redelivered"] += 1
            db.commit()
            if len(rows) < batch_size:
                break

        # --------------------------------------------------------------
        # 3. OPENED 回落：OPENED AND updated_at <= now - 30min
        # --------------------------------------------------------------
        fallback_before = now - timedelta(minutes=OPEN_FALLBACK_MINUTES)
        while True:
            rows = (
                db.query(Reminder)
                .filter(
                    Reminder.state == STATE_OPENED,
                    Reminder.updated_at.isnot(None),
                    Reminder.updated_at <= fallback_before,
                )
                .order_by(Reminder.updated_at)
                .limit(batch_size)
                .all()
            )
            if not rows:
                break
            for r in rows:
                r.state = STATE_DELIVERED
                r.last_delivered_at = now
                _add_event(db, r.id, "redelivered", {"reason": "open_timeout"})
                pushed_payloads.append(read_from_reminder(r).model_dump(mode="json"))
                stats["fallback"] += 1
            db.commit()
            if len(rows) < batch_size:
                break

        # --------------------------------------------------------------
        # 4. 过期处理：DELIVERED AND last_delivered_at + expire_after_minutes <= now
        # --------------------------------------------------------------
        # 历史 DELIVERED 可能极多，把过期判定下推到数据库（利用复合索引），
        # 只加载确实可能过期的行，并按 batch 处理避免单次事务过大。
        expired_filter = _build_expired_filter(db, now)
        while True:
            rows = (
                db.query(Reminder)
                .filter(
                    Reminder.state == STATE_DELIVERED,
                    Reminder.last_delivered_at.isnot(None),
                    expired_filter,
                )
                .order_by(Reminder.last_delivered_at)
                .limit(batch_size)
                .all()
            )
            if not rows:
                break
            for r in rows:
                expire_minutes = r.expire_after_minutes or 240
                # 数据库过滤已做，二次校验保证测试注入 now 时行为一致
                if r.last_delivered_at + timedelta(minutes=expire_minutes) > now:
                    continue  # 未过期
                r.state = STATE_EXPIRED
                _add_event(
                    db, r.id, "expired", {"expire_after_minutes": expire_minutes}
                )
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
                    retry_policy.get(
                        "retry_interval_minutes", DEFAULT_RETRY_INTERVAL_MINUTES
                    )
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
            if len(rows) < batch_size:
                break
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
    """提醒调度后台循环：启动后稍等再执行，然后按间隔循环。

    - 启动时先 sleep 一小段时间，避免启动高峰与首个连接/请求竞争；
    - 间隔取 REMINDER_SCAN_INTERVAL_SECONDS（默认 30s）；
    - 未捕获异常按指数退避（60s 起、30min 封顶）后继续；
    - 任务被取消（服务关闭）时向上抛 CancelledError 安静退出；
    - DB 扫描在专属单线程 Executor 中执行，避免占满默认线程池；
    - 推送经 run_coroutine_threadsafe 回事件循环。
    """
    from sail_server.utils.reminder_ws import get_reminder_push_manager

    interval_seconds = interval_seconds or _env_int(
        "REMINDER_SCAN_INTERVAL_SECONDS", DEFAULT_SCAN_INTERVAL_SECONDS
    )
    initial_delay = _env_int("REMINDER_SCAN_INITIAL_DELAY_SECONDS", 2)
    manager = get_reminder_push_manager()
    loop = asyncio.get_running_loop()
    # 单线程专用 Executor：扫描任务串行执行，且不挤占其他 to_thread 用户
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reminder_scan")

    def push(payload: Dict[str, Any]) -> None:
        # 无在线设备时不视为错误（WorkManager 轮询 /pending 兜回）
        asyncio.run_coroutine_threadsafe(manager.broadcast_reminder(payload), loop)

    logger.info(
        f"[reminder] scan loop started, interval={interval_seconds}s, "
        f"initial_delay={initial_delay}s"
    )

    # 启动时短暂等待，让服务器先完成启动握手、避免首个请求被阻塞
    try:
        await asyncio.sleep(initial_delay)
    except asyncio.CancelledError:
        logger.info("[reminder] scan loop cancelled during initial delay")
        executor.shutdown(wait=False)
        raise

    backoff_seconds = 0
    try:
        while True:
            try:
                stats = await loop.run_in_executor(
                    executor, scan_once, db_factory, push
                )
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
                    min(MAX_BACKOFF_SECONDS, backoff_seconds * 2)
                    if backoff_seconds
                    else 60
                )
                sleep_seconds = backoff_seconds
            await asyncio.sleep(sleep_seconds)
    finally:
        executor.shutdown(wait=False)
