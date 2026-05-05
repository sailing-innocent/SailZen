# -*- coding: utf-8 -*-
# @file necessity.py
# @brief Necessity DAO
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
物资管理模块 DAO

从 sail_server/data/necessity.py 迁移数据访问逻辑
"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.necessity import (
    Residence,
    Container,
    ItemCategory,
    Item,
    Inventory,
    Journey,
    JourneyItem,
    ItemState,
    JourneyStatus,
)
from sail_server.data.dao.base import BaseDAO


class ResidenceDAO(BaseDAO[Residence]):
    """住所 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, Residence)

    def get_by_code(self, code: str) -> Optional[Residence]:
        """通过编码获取住所"""
        return self.db.query(Residence).filter(Residence.code == code).first()

    def get_by_name(self, name: str) -> Optional[Residence]:
        """通过名称获取住所"""
        return self.db.query(Residence).filter(Residence.name == name).first()

    def get_active_residences(self) -> List[Residence]:
        """获取所有活跃住所（按优先级排序）"""
        return self.db.query(Residence).order_by(Residence.priority.asc()).all()


class ContainerDAO(BaseDAO[Container]):
    """容器 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, Container)

    def get_by_residence(self, residence_id: int) -> List[Container]:
        """获取住所的所有容器"""
        return (
            self.db.query(Container)
            .filter(Container.residence_id == residence_id)
            .order_by(Container.name)
            .all()
        )

    def get_by_parent(self, parent_id: int) -> List[Container]:
        """获取父容器的所有子容器"""
        return (
            self.db.query(Container)
            .filter(Container.parent_id == parent_id)
            .order_by(Container.name)
            .all()
        )

    def get_root_containers(self, residence_id: int) -> List[Container]:
        """获取住所的顶层容器（无父容器）"""
        return (
            self.db.query(Container)
            .filter(
                Container.residence_id == residence_id, Container.parent_id.is_(None)
            )
            .order_by(Container.name)
            .all()
        )


class ItemCategoryDAO(BaseDAO[ItemCategory]):
    """物资类别 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, ItemCategory)

    def get_by_code(self, code: str) -> Optional[ItemCategory]:
        """通过编码获取类别"""
        return self.db.query(ItemCategory).filter(ItemCategory.code == code).first()

    def get_by_name(self, name: str) -> Optional[ItemCategory]:
        """通过名称获取类别"""
        return self.db.query(ItemCategory).filter(ItemCategory.name == name).first()

    def get_root_categories(self) -> List[ItemCategory]:
        """获取顶层类别（无父类别）"""
        return (
            self.db.query(ItemCategory)
            .filter(ItemCategory.parent_id.is_(None))
            .order_by(ItemCategory.name)
            .all()
        )

    def get_children(self, parent_id: int) -> List[ItemCategory]:
        """获取父类别的所有子类别"""
        return (
            self.db.query(ItemCategory)
            .filter(ItemCategory.parent_id == parent_id)
            .order_by(ItemCategory.name)
            .all()
        )

    def get_consumable_categories(self) -> List[ItemCategory]:
        """获取所有消耗品类别的"""
        return (
            self.db.query(ItemCategory)
            .filter(ItemCategory.is_consumable == True)
            .order_by(ItemCategory.name)
            .all()
        )


class ItemDAO(BaseDAO[Item]):
    """物资 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, Item)

    def get_by_category(self, category_id: int) -> List[Item]:
        """获取类别的所有物资"""
        return (
            self.db.query(Item)
            .filter(Item.category_id == category_id)
            .order_by(Item.name)
            .all()
        )

    def get_by_name(self, name: str) -> List[Item]:
        """通过名称模糊搜索物资"""
        return (
            self.db.query(Item)
            .filter(Item.name.ilike(f"%{name}%"))
            .order_by(Item.name)
            .all()
        )

    def get_active_items(self) -> List[Item]:
        """获取所有活跃物资"""
        return (
            self.db.query(Item)
            .filter(Item.state == ItemState.ACTIVE)
            .order_by(Item.name)
            .all()
        )

    def get_by_serial_number(self, serial_number: str) -> Optional[Item]:
        """通过序列号获取物资"""
        return self.db.query(Item).filter(Item.serial_number == serial_number).first()

    def get_by_tags(self, tags: str) -> List[Item]:
        """通过标签搜索物资（模糊匹配）"""
        return (
            self.db.query(Item)
            .filter(Item.tags.ilike(f"%{tags}%"))
            .order_by(Item.name)
            .all()
        )


class InventoryDAO(BaseDAO[Inventory]):
    """库存 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, Inventory)

    def get_by_item(self, item_id: int) -> List[Inventory]:
        """获取物资的所有库存记录"""
        return self.db.query(Inventory).filter(Inventory.item_id == item_id).all()

    def get_by_residence(self, residence_id: int) -> List[Inventory]:
        """获取住所的所有库存"""
        return (
            self.db.query(Inventory)
            .filter(Inventory.residence_id == residence_id)
            .all()
        )

    def get_by_container(self, container_id: int) -> List[Inventory]:
        """获取容器的所有库存"""
        return (
            self.db.query(Inventory)
            .filter(Inventory.container_id == container_id)
            .all()
        )

    def get_by_residence_and_item(
        self, residence_id: int, item_id: int
    ) -> Optional[Inventory]:
        """获取指定住所和物资的库存记录"""
        return (
            self.db.query(Inventory)
            .filter(
                Inventory.residence_id == residence_id, Inventory.item_id == item_id
            )
            .first()
        )

    def get_low_stock(self, residence_id: Optional[int] = None) -> List[Inventory]:
        """获取低库存记录（低于最小警戒值）"""
        query = self.db.query(Inventory).filter(
            Inventory.quantity <= Inventory.min_quantity,
            Inventory.min_quantity > 0,
        )
        if residence_id:
            query = query.filter(Inventory.residence_id == residence_id)
        return query.all()


class JourneyDAO(BaseDAO[Journey]):
    """旅程 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, Journey)

    def get_by_from_residence(self, residence_id: int) -> List[Journey]:
        """获取从指定住所出发的旅程"""
        return (
            self.db.query(Journey)
            .filter(Journey.from_residence_id == residence_id)
            .order_by(Journey.depart_time.desc())
            .all()
        )

    def get_by_to_residence(self, residence_id: int) -> List[Journey]:
        """获取到达指定住所的旅程"""
        return (
            self.db.query(Journey)
            .filter(Journey.to_residence_id == residence_id)
            .order_by(Journey.arrive_time.desc())
            .all()
        )

    def get_by_status(self, status: JourneyStatus) -> List[Journey]:
        """获取指定状态的旅程"""
        return (
            self.db.query(Journey)
            .filter(Journey.status == status)
            .order_by(Journey.ctime.desc())
            .all()
        )

    def get_active_journeys(self) -> List[Journey]:
        """获取进行中的旅程"""
        return (
            self.db.query(Journey)
            .filter(Journey.status == JourneyStatus.IN_TRANSIT)
            .order_by(Journey.depart_time.desc())
            .all()
        )

    def get_with_items(self, journey_id: int) -> Optional[Journey]:
        """获取旅程及其物资"""
        journey = self.get_by_id(journey_id)
        if journey:
            # 触发加载子项
            _ = journey.items
        return journey


class JourneyItemDAO(BaseDAO[JourneyItem]):
    """旅程物资 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, JourneyItem)

    def get_by_journey(self, journey_id: int) -> List[JourneyItem]:
        """获取旅程的所有物资"""
        return (
            self.db.query(JourneyItem)
            .filter(JourneyItem.journey_id == journey_id)
            .all()
        )

    def get_by_item(self, item_id: int) -> List[JourneyItem]:
        """获取物资的所有旅程记录"""
        return (
            self.db.query(JourneyItem)
            .filter(JourneyItem.item_id == item_id)
            .order_by(JourneyItem.ctime.desc())
            .all()
        )
