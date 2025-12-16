# -*- coding: utf-8 -*-
# @file health.py
# @brief The Health Data Storage
# @author sailing-innocent
# @date 2025-04-21
# @version 1.0
# ---------------------------------

from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from .orm import ORMBase
from dataclasses import dataclass, field
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
# 设计原则就是可以一次测量的内容放在一张表内


# The Raw Weight Data
class Weight(ORMBase):
    __tablename__ = "weights"
    id = Column(Integer, primary_key=True)
    value = Column(String)  # float in kg
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # happen time
    tag = Column(
        String, default="daily"
    )  # tag for the weight record, e.g. raw, daily, weekly, monthly, yearly (calculated from raw data)
    description = Column(String, default="")  # description of the weight record


@dataclass
class WeightData:
    """
    The Weight Data
    """

    value: float
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
    id: int = field(default=-1)
    tag: str = field(default="raw")
    description: str = field(default="")


class BodySize(ORMBase):
    __tablename__ = "body_size"
    id = Column(Integer, primary_key=True)
    waist = Column(String)  # waist circumference in cm
    hip = Column(String)  # hip circumference in cm
    chest = Column(String)  # chest circumference in cm
    tag = Column(
        String, default="daily"
    )  # tag for the body size record, e.g. daily, weekly, monthly, yearly (calculated from raw data)
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # happen time


@dataclass
class BodySizeData:
    """
    The Body Size Data
    """

    waist: float
    hip: float
    chest: float
    tag: str = field(default="daily")
    id: int = field(default=-1)
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
