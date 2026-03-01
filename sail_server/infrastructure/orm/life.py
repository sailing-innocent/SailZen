# -*- coding: utf-8 -*-
# @file life.py
# @brief Life ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
生活服务模块 ORM 模型

从 sail_server/data/life.py 迁移
"""

from sqlalchemy import Column, Integer, String, BigInteger

from sail_server.infrastructure.orm import ORMBase


class ServiceAccount(ORMBase):
    """服务资产，存在有效期限"""

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
