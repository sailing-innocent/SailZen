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

from sqlalchemy import Column, Integer, String, TIMESTAMP, func

from sail_server.infrastructure.orm import ORMBase


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
