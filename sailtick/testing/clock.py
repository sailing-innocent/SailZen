# -*- coding: utf-8 -*-
# @file clock.py
# @brief 确定性虚拟时钟（供多 Tick 轨迹测试、安静时段与票据超期测试）
# @author sailing-innocent
# @date 2026-11-21
# @version 1.0
# ---------------------------------
"""VirtualClock — 可拨动虚拟时钟。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


class VirtualClock:
    """确定性可控时钟，可作为 clock 回调注入 TickEngine / NotificationEngine / FakeServer。"""

    def __init__(self, initial: Optional[datetime] = None):
        self._now = initial or datetime(2026, 11, 9, 6, 0, 0)

    def __call__(self) -> datetime:
        return self._now

    @property
    def now(self) -> datetime:
        return self._now

    def set(self, dt: datetime) -> datetime:
        self._now = dt
        return self._now

    def advance(
        self,
        *,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
    ) -> datetime:
        self._now = self._now + timedelta(
            days=days, hours=hours, minutes=minutes, seconds=seconds
        )
        return self._now
