# -*- coding: utf-8 -*-
# @file project.py
# @brief Project DAO
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
项目模块 DAO

从 sail_server/data/project.py 迁移数据访问逻辑
"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.project import Project, Mission
from sail_server.data.dao.base import BaseDAO


class ProjectDAO(BaseDAO[Project]):
    """项目 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, Project)
    
    def get_by_name(self, name: str) -> Optional[Project]:
        """通过名称获取项目"""
        return self.db.query(Project).filter(Project.name == name).first()
    
    def get_active_projects(self) -> List[Project]:
        """获取所有活跃项目（非取消状态）"""
        # 状态 0-4 为有效状态，6 为取消状态
        return self.db.query(Project).filter(
            Project.state.in_([0, 1, 2, 3, 4, 5])
        ).order_by(Project.ctime.desc()).all()
    
    def get_by_state(self, state: int) -> List[Project]:
        """通过状态获取项目"""
        return self.db.query(Project).filter(
            Project.state == state
        ).order_by(Project.ctime.desc()).all()
    
    def get_projects_by_time_range(
        self, 
        start_qbw: int, 
        end_qbw: int
    ) -> List[Project]:
        """获取指定时间范围内的项目
        
        Args:
            start_qbw: 开始时间（YYYYQQWW 格式）
            end_qbw: 结束时间（YYYYQQWW 格式）
            
        Returns:
            项目列表
        """
        return self.db.query(Project).filter(
            (Project.start_time_qbw >= start_qbw) &
            (Project.end_time_qbw <= end_qbw)
        ).order_by(Project.start_time_qbw).all()


class MissionDAO(BaseDAO[Mission]):
    """任务 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, Mission)
    
    def get_by_project(self, project_id: int) -> List[Mission]:
        """获取项目的所有任务"""
        return self.db.query(Mission).filter(
            Mission.project_id == project_id
        ).order_by(Mission.ctime.desc()).all()
    
    def get_by_parent(self, parent_id: int) -> List[Mission]:
        """获取父任务的所有子任务"""
        return self.db.query(Mission).filter(
            Mission.parent_id == parent_id
        ).order_by(Mission.lft).all()
    
    def get_root_missions(self) -> List[Mission]:
        """获取所有根任务（没有父任务）"""
        return self.db.query(Mission).filter(
            Mission.parent_id.is_(None)
        ).order_by(Mission.ctime.desc()).all()
    
    def get_by_state(self, state: int) -> List[Mission]:
        """通过状态获取任务"""
        return self.db.query(Mission).filter(
            Mission.state == state
        ).order_by(Mission.ctime.desc()).all()
    
    def get_pending_missions(self) -> List[Mission]:
        """获取所有待处理任务"""
        return self.db.query(Mission).filter(
            Mission.state == 0
        ).order_by(Mission.ddl).all()
    
    def get_doing_missions(self) -> List[Mission]:
        """获取所有进行中任务"""
        return self.db.query(Mission).filter(
            Mission.state == 2
        ).order_by(Mission.ddl).all()
    
    def get_by_tree_id(self, tree_id: int) -> List[Mission]:
        """通过树ID获取任务"""
        return self.db.query(Mission).filter(
            Mission.tree_id == tree_id
        ).order_by(Mission.lft).all()
