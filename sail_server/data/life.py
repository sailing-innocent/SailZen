# -*- coding: utf-8 -*-
# @file info.py
# @brief Peronsal Information Storage
# @author sailing-innocent
# @date 2025-02-03
# @version 1.0
# ---------------------------------

from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger, TIMESTAMP, func
from sail_server.data.types import JSONB
from .orm import ORMBase
from sqlalchemy.orm import relationship
from sail_server.utils.time_utils import QuarterBiWeekTime
from dataclasses import dataclass, field


# 服务资产，存在有效期限
class ServiceAccount(ORMBase):
    __tablename__ = "service_account"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)  # account name
    entry = Column(String(255), nullable=False)  # entry website/app name
    username = Column(String(255), nullable=False)  # username
    password = Column(String(255), nullable=False)  # password
    desp = Column(String(255), nullable=True)  # account description
    expire_time = Column(
        BigInteger, nullable=False
    )  # expire time, store as timestamp in seconds


@dataclass
class ServiceAccountData:
    id: int = field(default=None)
    name: str = field(default="")
    entry: str = field(default="")
    username: str = field(default="")
    password: str = field(default="")
    desp: str = field(default="")
    expire_time: int = field(default=0)
