# -*- coding: utf-8 -*-
# @file health.py
# @brief Health DAO
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
健康管理模块 DAO

从 sail_server/data/health.py 迁移数据访问逻辑
"""

from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.health import Weight, BodySize, Exercise, WeightPlan
from sail_server.data.dao.base import BaseDAO


class WeightDAO(BaseDAO[Weight]):
    """体重记录 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, Weight)

    def get_by_tag(self, tag: str) -> List[Weight]:
        """通过标签获取体重记录"""
        return (
            self.db.query(Weight)
            .filter(Weight.tag == tag)
            .order_by(Weight.htime.desc())
            .all()
        )

    def get_latest(self) -> Optional[Weight]:
        """获取最新体重记录"""
        return self.db.query(Weight).order_by(Weight.htime.desc()).first()


class BodySizeDAO(BaseDAO[BodySize]):
    """身体尺寸 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, BodySize)

    def get_by_tag(self, tag: str) -> List[BodySize]:
        """通过标签获取身体尺寸记录"""
        return (
            self.db.query(BodySize)
            .filter(BodySize.tag == tag)
            .order_by(BodySize.htime.desc())
            .all()
        )

    def get_latest(self) -> Optional[BodySize]:
        """获取最新身体尺寸记录"""
        return self.db.query(BodySize).order_by(BodySize.htime.desc()).first()


class ExerciseDAO(BaseDAO[Exercise]):
    """运动记录 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, Exercise)

    def get_latest(self, limit: int = 10) -> List[Exercise]:
        """获取最新运动记录"""
        return (
            self.db.query(Exercise).order_by(Exercise.htime.desc()).limit(limit).all()
        )


class WeightPlanDAO(BaseDAO[WeightPlan]):
    """体重计划 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, WeightPlan)

    def get_active_plans(self) -> List[WeightPlan]:
        """获取所有活跃计划（未过期的）"""
        return (
            self.db.query(WeightPlan)
            .filter(WeightPlan.target_time >= func.current_timestamp())
            .order_by(WeightPlan.target_time)
            .all()
        )

    def get_latest_plan(self) -> Optional[WeightPlan]:
        """获取最新创建的体重计划"""
        return self.db.query(WeightPlan).order_by(WeightPlan.created_at.desc()).first()
