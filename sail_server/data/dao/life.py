# -*- coding: utf-8 -*-
# @file life.py
# @brief Life DAO
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
生活服务模块 DAO

从 sail_server/data/life.py 迁移数据访问逻辑
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, date

from sail_server.infrastructure.orm.life import ServiceAccount, Day, TimeSpan
from sail_server.data.dao.base import BaseDAO


class ServiceAccountDAO(BaseDAO[ServiceAccount]):
    """服务账户 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, ServiceAccount)

    def get_by_name(self, name: str) -> Optional[ServiceAccount]:
        """通过名称获取账户"""
        return self.db.query(ServiceAccount).filter(ServiceAccount.name == name).first()

    def get_by_entry(self, entry: str) -> List[ServiceAccount]:
        """通过入口网站/应用名称获取账户"""
        return self.db.query(ServiceAccount).filter(ServiceAccount.entry == entry).all()

    def get_expired_accounts(self, current_time: int) -> List[ServiceAccount]:
        """获取已过期账户"""
        return (
            self.db.query(ServiceAccount)
            .filter(ServiceAccount.expire_time < current_time)
            .order_by(ServiceAccount.expire_time)
            .all()
        )

    def get_expiring_soon(
        self, current_time: int, threshold_seconds: int = 86400
    ) -> List[ServiceAccount]:
        """获取即将过期的账户（默认24小时内）"""
        threshold = current_time + threshold_seconds
        return (
            self.db.query(ServiceAccount)
            .filter(
                ServiceAccount.expire_time >= current_time,
                ServiceAccount.expire_time <= threshold,
            )
            .order_by(ServiceAccount.expire_time)
            .all()
        )


class DayDAO(BaseDAO[Day]):
    """自然日 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, Day)

    def get_by_date(self, date: date) -> Optional[Day]:
        """通过日期获取自然日"""
        return self.db.query(Day).filter(Day.date == date).first()

    def get_by_date_range(
        self, start: date, end: date, skip: int = 0, limit: int = -1
    ) -> List[Day]:
        """通过日期范围获取自然日 [start, end)"""
        query = (
            self.db.query(Day)
            .filter(Day.date >= start, Day.date < end)
            .order_by(Day.date)
        )
        if skip > 0:
            query = query.offset(skip)
        if limit > 0:
            query = query.limit(limit)
        return query.all()

    def exists_by_date(self, date: date) -> bool:
        """检查指定日期是否存在"""
        return self.db.query(Day).filter(Day.date == date).first() is not None


class TimeSpanDAO(BaseDAO[TimeSpan]):
    """时间跨度 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, TimeSpan)

    def get_by_name(self, name: str) -> Optional[TimeSpan]:
        """通过名称获取时间跨度"""
        return self.db.query(TimeSpan).filter(TimeSpan.name == name).first()

    def get_by_class(self, span_class: str, skip: int = 0, limit: int = -1) -> List[TimeSpan]:
        """通过类型获取时间跨度"""
        query = (
            self.db.query(TimeSpan)
            .filter(TimeSpan.class_ == span_class)
            .order_by(TimeSpan.name)
        )
        if skip > 0:
            query = query.offset(skip)
        if limit > 0:
            query = query.limit(limit)
        return query.all()

    def get_by_class_and_name(
        self, span_class: str, name: str
    ) -> Optional[TimeSpan]:
        """通过类型和名称获取时间跨度"""
        return (
            self.db.query(TimeSpan)
            .filter(TimeSpan.class_ == span_class, TimeSpan.name == name)
            .first()
        )

    def get_by_day_id(self, day_id: int) -> List[TimeSpan]:
        """查找包含指定自然日的时间跨度"""
        return (
            self.db.query(TimeSpan)
            .filter(
                TimeSpan.start_day_id <= day_id,
                TimeSpan.end_day_id >= day_id,
            )
            .order_by(TimeSpan.class_, TimeSpan.name)
            .all()
        )

    def get_by_date(self, date: date) -> List[TimeSpan]:
        """查找包含指定日期的时间跨度"""
        day = self.db.query(Day).filter(Day.date == date).first()
        if day is None:
            return []
        return self.get_by_day_id(day.id)

    def get_children(self, ids: List[int]) -> List[TimeSpan]:
        """通过ID列表获取子时间跨度"""
        if not ids:
            return []
        return (
            self.db.query(TimeSpan)
            .filter(TimeSpan.id.in_(ids))
            .order_by(TimeSpan.name)
            .all()
        )
