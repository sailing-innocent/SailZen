# -*- coding: utf-8 -*-
# @file base.py
# @brief DAO Base Class
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
DAO (Data Access Object) 基类

提供通用的 CRUD 操作，所有具体 DAO 应继承此类。
"""

from typing import TypeVar, Generic, List, Optional, Type, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from sail_server.infrastructure.orm import ORMBase

T = TypeVar("T", bound=ORMBase)


class BaseDAO(Generic[T]):
    """DAO 基类
    
    泛型参数 T 为 ORM 模型类
    
    示例:
        class CharacterDAO(BaseDAO[Character]):
            def __init__(self, db: Session):
                super().__init__(db, Character)
    """
    
    def __init__(self, db: Session, model_class: Type[T]):
        """初始化 DAO
        
        Args:
            db: SQLAlchemy Session
            model_class: ORM 模型类
        """
        self.db = db
        self.model_class = model_class
    
    # ========================================================================
    # Basic CRUD Operations
    # ========================================================================
    
    def get_by_id(self, id: int) -> Optional[T]:
        """通过 ID 获取记录
        
        Args:
            id: 记录 ID
            
        Returns:
            ORM 对象或 None
        """
        return self.db.get(self.model_class, id)
    
    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None
    ) -> List[T]:
        """获取所有记录（分页）
        
        Args:
            skip: 跳过记录数
            limit: 返回记录数
            order_by: 排序字段
            
        Returns:
            ORM 对象列表
        """
        query = select(self.model_class)
        
        if order_by and hasattr(self.model_class, order_by):
            query = query.order_by(getattr(self.model_class, order_by))
        
        query = query.offset(skip).limit(limit)
        return list(self.db.execute(query).scalars().all())
    
    def create(self, obj: T) -> T:
        """创建记录
        
        Args:
            obj: ORM 对象
            
        Returns:
            创建后的 ORM 对象（包含生成的 ID）
        """
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj
    
    def create_many(self, objs: List[T]) -> List[T]:
        """批量创建记录
        
        Args:
            objs: ORM 对象列表
            
        Returns:
            创建后的 ORM 对象列表
        """
        self.db.add_all(objs)
        self.db.commit()
        for obj in objs:
            self.db.refresh(obj)
        return objs
    
    def update(self, id: int, data: Dict[str, Any]) -> Optional[T]:
        """更新记录
        
        Args:
            id: 记录 ID
            data: 更新数据字典
            
        Returns:
            更新后的 ORM 对象或 None
        """
        obj = self.get_by_id(id)
        if not obj:
            return None
        
        for key, value in data.items():
            if hasattr(obj, key) and value is not None:
                setattr(obj, key, value)
        
        self.db.commit()
        self.db.refresh(obj)
        return obj
    
    def delete(self, id: int) -> bool:
        """删除记录
        
        Args:
            id: 记录 ID
            
        Returns:
            是否删除成功
        """
        obj = self.get_by_id(id)
        if not obj:
            return False
        
        self.db.delete(obj)
        self.db.commit()
        return True
    
    def delete_many(self, ids: List[int]) -> int:
        """批量删除记录
        
        Args:
            ids: 记录 ID 列表
            
        Returns:
            删除的记录数
        """
        count = 0
        for id in ids:
            if self.delete(id):
                count += 1
        return count
    
    # ========================================================================
    # Count Operations
    # ========================================================================
    
    def count(self) -> int:
        """获取记录总数
        
        Returns:
            记录总数
        """
        query = select(func.count()).select_from(self.model_class)
        return self.db.execute(query).scalar_one()
    
    def exists(self, id: int) -> bool:
        """检查记录是否存在
        
        Args:
            id: 记录 ID
            
        Returns:
            是否存在
        """
        return self.get_by_id(id) is not None
    
    # ========================================================================
    # Filter Operations
    # ========================================================================
    
    def filter_by(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        **filters
    ) -> List[T]:
        """条件查询
        
        Args:
            skip: 跳过记录数
            limit: 返回记录数
            order_by: 排序字段
            **filters: 过滤条件（字段名=值）
            
        Returns:
            ORM 对象列表
        """
        query = select(self.model_class)
        
        # 应用过滤条件
        for key, value in filters.items():
            if hasattr(self.model_class, key) and value is not None:
                query = query.where(getattr(self.model_class, key) == value)
        
        # 排序
        if order_by and hasattr(self.model_class, order_by):
            query = query.order_by(getattr(self.model_class, order_by))
        
        # 分页
        query = query.offset(skip).limit(limit)
        
        return list(self.db.execute(query).scalars().all())
