# -*- coding: utf-8 -*-
# @file orm.py
# @brief The ORM Base Class
# @author sailing-innocent
# @date 2025-04-21
# @version 1.0
# ---------------------------------

from sqlalchemy.orm import DeclarativeBase

# set 2100 as the default end time
TIME_START = 0
TIME_END = 4102416000  # 2100,01,01,00,00,00
MAX_TIME = 9999999999999999999999


# Base class for ORM
class ORMBase(DeclarativeBase):
    pass
