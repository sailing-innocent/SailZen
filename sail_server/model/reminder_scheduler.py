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

from sail_server.infrastructure.orm.reminder import Reminder, ReminderRule
from sail_server.model.reminder import (
    STATE_ARCHIVED,
    STATE_DELIVERED,
    STATE_EXPIRED,
    STATE_OPENED,
    STATE_PENDING,
    STATE_SNOOZED,
    _add_event,
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
    }
    pushed_payloads: List[Dict[str, Any]] = []

    db = db_factory()
    try:
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
