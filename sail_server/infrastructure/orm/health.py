# -*- coding: utf-8 -*-
# @file health.py
# @brief Health ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
健康管理模块 ORM 模型

从 sail_server/data/health.py 迁移
"""

from sqlalchemy import Column, Date, Float, Integer, String, ForeignKey, TIMESTAMP, func, Boolean
from sqlalchemy.orm import relationship

from sail_server.infrastructure.orm import ORMBase
from sail_server.data.types import JSONB


class Weight(ORMBase):
    """体重记录"""

    __tablename__ = "weights"
    id = Column(Integer, primary_key=True)
    value = Column(String)  # float in kg
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # happen time
    tag = Column(
        String, default="daily"
    )  # tag for the weight record, e.g. raw, daily, weekly, monthly, yearly (calculated from raw data)
    description = Column(String, default="")  # description of the weight record


class BodySize(ORMBase):
    """身体尺寸记录"""

    __tablename__ = "body_size"
    id = Column(Integer, primary_key=True)
    waist = Column(String)  # waist circumference in cm
    hip = Column(String)  # hip circumference in cm
    chest = Column(String)  # chest circumference in cm
    tag = Column(
        String, default="daily"
    )  # tag for the body size record, e.g. daily, weekly, monthly, yearly (calculated from raw data)
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # happen time


class Exercise(ORMBase):
    """运动记录"""

    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True)
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # happen time
    description = Column(String, default="")  # natural language description
    exercise_type = Column(String, default="")  # 运动类型，如 running / walking / strength
    duration_minutes = Column(Integer, default=0)  # 运动时长（分钟）
    calories = Column(Integer, default=0)  # 消耗热量（千卡）
    completed = Column(Boolean, default=True)  # 是否完成
    source = Column(String, default="health")  # 来源：health / exercise_plan / rhythm


class WeightPlan(ORMBase):
    """体重计划"""

    __tablename__ = "weight_plans"
    id = Column(Integer, primary_key=True)
    target_weight = Column(String)  # target weight value in kg
    start_time = Column(
        TIMESTAMP, server_default=func.current_timestamp()
    )  # plan start time
    target_time = Column(TIMESTAMP)  # plan target time
    description = Column(String, default="")  # plan description
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # 新增字段：起始体重、曲线类型、Rhythm 提醒与反馈联动
    initial_weight = Column(String, nullable=True)  # initial weight in kg; None means auto-detect
    curve_type = Column(String, default="linear")  # linear / polynomial / exponential
    notify_enabled = Column(Boolean, default=False)  # enable Rhythm reminder
    notify_time = Column(String, default="08:30")  # HH:MM reminder time
    rhythm_affair_id = Column(
        Integer, ForeignKey("rhythm_affairs.id"), nullable=True
    )
    feedback_enabled = Column(Boolean, default=False)  # sync weight record to Rhythm checkin


class Sleep(ORMBase):
    """睡眠记录"""

    __tablename__ = "sleeps"
    id = Column(Integer, primary_key=True)
    day_id = Column(
        Integer, ForeignKey("days.id"), nullable=True, default=None, index=True
    )
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())
    hours = Column(Integer, default=0)  # minutes, stored as total minutes
    quality = Column(Integer, default=3)  # 1-5
    description = Column(String, default="")

    day = relationship("Day", foreign_keys=[day_id])


class EnergyLevel(ORMBase):
    """精力评分记录"""

    __tablename__ = "energy_levels"
    id = Column(Integer, primary_key=True)
    day_id = Column(
        Integer, ForeignKey("days.id"), nullable=True, default=None, index=True
    )
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())
    score = Column(Integer, default=3)  # 1-5
    description = Column(String, default="")

    day = relationship("Day", foreign_keys=[day_id])


class Mood(ORMBase):
    """情绪评分记录"""

    __tablename__ = "moods"
    id = Column(Integer, primary_key=True)
    day_id = Column(
        Integer, ForeignKey("days.id"), nullable=True, default=None, index=True
    )
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())
    score = Column(Integer, default=3)  # 1-5
    description = Column(String, default="")

    day = relationship("Day", foreign_keys=[day_id])


class HealthSignal(ORMBase):
    """统一健康信号索引表

    将体重、运动、睡眠、精力、情绪等记录统一索引到自然日。
    """

    __tablename__ = "health_signals"
    id = Column(Integer, primary_key=True)
    signal_type = Column(String(32), nullable=False, index=True)
    ref_id = Column(Integer, nullable=False)
    day_id = Column(
        Integer, ForeignKey("days.id"), nullable=True, default=None, index=True
    )
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())
    value_json = Column(JSONB, default=dict)
    score = Column(Integer, nullable=True)

    day = relationship("Day", foreign_keys=[day_id])


class Medication(ORMBase):
    """用药/保健品记录"""

    __tablename__ = "medications"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # 药品/保健品名
    dosage = Column(String, default="")  # 剂量，如 "500mg"
    frequency = Column(String, default="daily")  # daily / weekly / as_needed
    schedule_times = Column(JSONB, default=list)  # ["08:00", "20:00"]
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # 本次记录时间
    planned_date = Column(Date)  # 计划服用日期
    taken = Column(Boolean, default=False)  # 是否已服用
    taken_at = Column(TIMESTAMP, nullable=True)  # 实际服用时间
    note = Column(String, default="")
    is_supplement = Column(Boolean, default=False)  # 是否保健品


class DietLog(ORMBase):
    """饮食记录"""

    __tablename__ = "diet_logs"
    id = Column(Integer, primary_key=True)
    meal_type = Column(String, default="snack")  # breakfast/lunch/dinner/snack
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())
    description = Column(String, default="")  # 文字描述
    photo_path = Column(String, nullable=True)  # 照片路径（未来扩展）
    # 营养实际值（单位克， nullable 表示未填写）
    calories = Column(Float, nullable=True)
    carbs = Column(Float, nullable=True)  # 碳水化合物
    sugar = Column(Float, nullable=True)
    protein = Column(Float, nullable=True)
    fat = Column(Float, nullable=True)
    fiber = Column(Float, nullable=True)
    sodium = Column(Float, nullable=True)  # 钠 mg
    # 微量元素（可 JSON 扩展）
    micronutrients = Column(JSONB, default=dict)


class NutritionGoal(ORMBase):
    """每日营养目标"""

    __tablename__ = "nutrition_goals"
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True)  # 目标日期
    calories = Column(Float, nullable=True)
    carbs = Column(Float, nullable=True)
    sugar = Column(Float, nullable=True)
    protein = Column(Float, nullable=True)
    fat = Column(Float, nullable=True)
    fiber = Column(Float, nullable=True)
    sodium = Column(Float, nullable=True)
    micronutrients = Column(JSONB, default=dict)


class SleepScheduleGoal(ORMBase):
    """作息目标"""

    __tablename__ = "sleep_schedule_goals"
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True)
    bed_time = Column(String, default="23:00")  # "23:00"
    wake_time = Column(String, default="07:00")  # "07:00"
    target_hours = Column(Float, default=8.0)  # 目标睡眠时长
