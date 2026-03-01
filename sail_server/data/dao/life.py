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
from datetime import datetime

from sail_server.infrastructure.orm.life import ServiceAccount
from sail_server.data.dao.base import BaseDAO


class ServiceAccountDAO(BaseDAO[ServiceAccount]):
    """服务账户 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, ServiceAccount)
    
    def get_by_name(self, name: str) -> Optional[ServiceAccount]:
        """通过名称获取账户"""
        return self.db.query(ServiceAccount).filter(
            ServiceAccount.name == name
        ).first()
    
    def get_by_entry(self, entry: str) -> List[ServiceAccount]:
        """通过入口网站/应用名称获取账户"""
        return self.db.query(ServiceAccount).filter(
            ServiceAccount.entry == entry
        ).all()
    
    def get_expired_accounts(self, current_time: int) -> List[ServiceAccount]:
        """获取已过期账户"""
        return self.db.query(ServiceAccount).filter(
            ServiceAccount.expire_time < current_time
        ).order_by(ServiceAccount.expire_time).all()
    
    def get_expiring_soon(self, current_time: int, threshold_seconds: int = 86400) -> List[ServiceAccount]:
        """获取即将过期的账户（默认24小时内）"""
        threshold = current_time + threshold_seconds
        return self.db.query(ServiceAccount).filter(
            ServiceAccount.expire_time >= current_time,
            ServiceAccount.expire_time <= threshold
        ).order_by(ServiceAccount.expire_time).all()
