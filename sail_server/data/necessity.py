# -*- coding: utf-8 -*-
# @file necessity.py
# @brief The Necessity (生活物资) Data Model
# @author sailing-innocent
# @date 2026-02-01
# @version 1.0
# ---------------------------------

from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, Boolean, Numeric, func
from .orm import ORMBase
from sqlalchemy.orm import relationship
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import IntEnum

__all__ = [
    # Enums
    "ResidenceType",
    "ContainerType",
    "ItemType",
    "ItemState",
    "JourneyStatus",
    "JourneyItemStatus",
    "ReplenishmentSource",
    # ORM Models
    "Residence",
    "Container",
    "ItemCategory",
    "Item",
    "Inventory",
    "Journey",
    "JourneyItem",
    "Consumption",
    "Replenishment",
    # Data Classes
    "ResidenceData",
    "ContainerData",
    "ItemCategoryData",
    "ItemData",
    "InventoryData",
    "JourneyData",
    "JourneyItemData",
    "ConsumptionData",
    "ReplenishmentData",
]


# ------------------------------------
# Enums
# ------------------------------------

class ResidenceType(IntEnum):
    """住所类型"""
    STABLE = 0      # 稳定仓库（长期存储）
    BACKUP = 1      # 后备仓库（备用物资）
    LIVING = 2      # 生活住所（日常居住）
    PORTABLE = 3    # 随身携带


class ContainerType(IntEnum):
    """容器类型"""
    ROOM = 0        # 房间
    CABINET = 1     # 柜子/衣柜
    DRAWER = 2      # 抽屉
    BOX = 3         # 箱子/盒子
    BAG = 4         # 包/背包
    SHELF = 5       # 架子
    OTHER = 99      # 其他


class ItemType(IntEnum):
    """物资类型"""
    UNIQUE = 0      # 唯一物品（如证件、电器）
    BULK = 1        # 批量物品（如消耗品）


class ItemState(IntEnum):
    """物资状态"""
    ACTIVE = 0      # 正常使用
    STORED = 1      # 存储中（不常用）
    LENDING = 2     # 借出
    REPAIRING = 3   # 维修中
    DISPOSED = 4    # 已处置/丢弃
    LOST = 5        # 丢失


class JourneyStatus(IntEnum):
    """旅程状态"""
    PLANNED = 0     # 计划中
    IN_TRANSIT = 1  # 进行中
    COMPLETED = 2   # 已完成
    CANCELLED = 3   # 已取消


class JourneyItemStatus(IntEnum):
    """旅程物资状态"""
    PENDING = 0     # 待打包
    PACKED = 1      # 已打包
    TRANSFERRED = 2 # 已转移
    UNPACKED = 3    # 已拆包


class ReplenishmentSource(IntEnum):
    """补货来源类型"""
    PURCHASE = 0    # 购买
    TRANSFER = 1    # 调拨（从其他住所）
    GIFT = 2        # 赠送
    RETURN = 3      # 归还


# ------------------------------------
# ORM Models
# ------------------------------------

class Residence(ORMBase):
    """住所表"""
    __tablename__ = "residences"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True)
    type = Column(Integer, default=ResidenceType.LIVING)
    address = Column(String)
    description = Column(String)
    is_portable = Column(Boolean, default=False)
    priority = Column(Integer, default=10)  # 补货优先级，数字越小越优先
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    containers = relationship("Container", back_populates="residence", cascade="all, delete-orphan")
    inventories = relationship("Inventory", back_populates="residence", cascade="all, delete-orphan")
    journeys_from = relationship("Journey", back_populates="from_residence", foreign_keys="Journey.from_residence_id")
    journeys_to = relationship("Journey", back_populates="to_residence", foreign_keys="Journey.to_residence_id")


class Container(ORMBase):
    """容器/存储位置表"""
    __tablename__ = "containers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    residence_id = Column(Integer, ForeignKey("residences.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("containers.id"), nullable=True)
    name = Column(String, nullable=False)
    type = Column(Integer, default=ContainerType.OTHER)
    description = Column(String)
    capacity = Column(Integer)  # 可选，用于容量管理
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    residence = relationship("Residence", back_populates="containers")
    parent = relationship("Container", remote_side=[id], back_populates="children")
    children = relationship("Container", back_populates="parent", cascade="all, delete-orphan")
    inventories = relationship("Inventory", back_populates="container", cascade="all, delete-orphan")


class ItemCategory(ORMBase):
    """物资类别表"""
    __tablename__ = "item_categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("item_categories.id"), nullable=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True)
    icon = Column(String)
    is_consumable = Column(Boolean, default=False)
    default_unit = Column(String)
    description = Column(String)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    parent = relationship("ItemCategory", remote_side=[id], back_populates="children")
    children = relationship("ItemCategory", back_populates="parent", cascade="all, delete-orphan")
    items = relationship("Item", back_populates="category")


class Item(ORMBase):
    """物资表"""
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("item_categories.id"), nullable=True)
    type = Column(Integer, default=ItemType.UNIQUE)
    brand = Column(String)
    model = Column(String)  # 型号/规格
    serial_number = Column(String)  # 序列号（唯一物品）
    description = Column(String)
    purchase_date = Column(TIMESTAMP)
    purchase_price = Column(String)
    warranty_until = Column(TIMESTAMP)
    expire_date = Column(TIMESTAMP)  # 有效期/过期日期
    importance = Column(Integer, default=3)  # 重要程度 1-5
    portability = Column(Integer, default=3)  # 便携性 1-5，5最便携
    tags = Column(String)  # 标签（逗号分隔）
    image_url = Column(String)
    state = Column(Integer, default=ItemState.ACTIVE)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    category = relationship("ItemCategory", back_populates="items")
    inventories = relationship("Inventory", back_populates="item", cascade="all, delete-orphan")
    journey_items = relationship("JourneyItem", back_populates="item", cascade="all, delete-orphan")


class Inventory(ORMBase):
    """库存记录表"""
    __tablename__ = "inventories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    residence_id = Column(Integer, ForeignKey("residences.id"), nullable=False)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=True)
    quantity = Column(Numeric(10, 2), default=1)
    unit = Column(String, default="个")
    min_quantity = Column(Numeric(10, 2), default=0)  # 最小库存警戒值
    max_quantity = Column(Numeric(10, 2), default=0)  # 最大库存值
    last_check_time = Column(TIMESTAMP)
    notes = Column(String)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    item = relationship("Item", back_populates="inventories")
    residence = relationship("Residence", back_populates="inventories")
    container = relationship("Container", back_populates="inventories")
    consumptions = relationship("Consumption", back_populates="inventory", cascade="all, delete-orphan")
    replenishments = relationship("Replenishment", back_populates="inventory", cascade="all, delete-orphan")


class Journey(ORMBase):
    """旅程表"""
    __tablename__ = "journeys"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_residence_id = Column(Integer, ForeignKey("residences.id"), nullable=False)
    to_residence_id = Column(Integer, ForeignKey("residences.id"), nullable=False)
    depart_time = Column(TIMESTAMP)
    arrive_time = Column(TIMESTAMP)
    status = Column(Integer, default=JourneyStatus.PLANNED)
    transport_mode = Column(String)  # 交通方式
    notes = Column(String)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    from_residence = relationship("Residence", back_populates="journeys_from", foreign_keys=[from_residence_id])
    to_residence = relationship("Residence", back_populates="journeys_to", foreign_keys=[to_residence_id])
    items = relationship("JourneyItem", back_populates="journey", cascade="all, delete-orphan")


class JourneyItem(ORMBase):
    """旅程物资表"""
    __tablename__ = "journey_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    journey_id = Column(Integer, ForeignKey("journeys.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Numeric(10, 2), default=1)
    is_return = Column(Boolean, default=False)  # 是否归还（否则为转移）
    from_container_id = Column(Integer, ForeignKey("containers.id"), nullable=True)
    to_container_id = Column(Integer, ForeignKey("containers.id"), nullable=True)
    status = Column(Integer, default=JourneyItemStatus.PENDING)
    notes = Column(String)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    journey = relationship("Journey", back_populates="items")
    item = relationship("Item", back_populates="journey_items")


class Consumption(ORMBase):
    """消耗记录表"""
    __tablename__ = "consumptions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    inventory_id = Column(Integer, ForeignKey("inventories.id"), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # 发生时间
    reason = Column(String)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    inventory = relationship("Inventory", back_populates="consumptions")


class Replenishment(ORMBase):
    """补货记录表"""
    __tablename__ = "replenishments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    inventory_id = Column(Integer, ForeignKey("inventories.id"), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    source = Column(Integer, default=ReplenishmentSource.PURCHASE)
    source_residence_id = Column(Integer, ForeignKey("residences.id"), nullable=True)  # 调拨时的来源住所
    cost = Column(String)  # 花费（购买时）
    transaction_id = Column(Integer, nullable=True)  # 关联交易ID（外键，可选）
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # 发生时间
    notes = Column(String)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    inventory = relationship("Inventory", back_populates="replenishments")


# ------------------------------------
# Data Classes
# ------------------------------------

@dataclass
class ResidenceData:
    id: int = field(default=-1)
    name: str = field(default="")
    code: str = field(default="")
    type: int = field(default=ResidenceType.LIVING)
    address: str = field(default="")
    description: str = field(default="")
    is_portable: bool = field(default=False)
    priority: int = field(default=10)
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)


@dataclass
class ContainerData:
    id: int = field(default=-1)
    residence_id: int = field(default=-1)
    parent_id: Optional[int] = field(default=None)
    name: str = field(default="")
    type: int = field(default=ContainerType.OTHER)
    description: str = field(default="")
    capacity: Optional[int] = field(default=None)
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)


@dataclass
class ItemCategoryData:
    id: int = field(default=-1)
    parent_id: Optional[int] = field(default=None)
    name: str = field(default="")
    code: str = field(default="")
    icon: str = field(default="")
    is_consumable: bool = field(default=False)
    default_unit: str = field(default="个")
    description: str = field(default="")
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)


@dataclass
class ItemData:
    id: int = field(default=-1)
    name: str = field(default="")
    category_id: Optional[int] = field(default=None)
    type: int = field(default=ItemType.UNIQUE)
    brand: str = field(default="")
    model: str = field(default="")
    serial_number: str = field(default="")
    description: str = field(default="")
    purchase_date: Optional[float] = field(default=None)  # timestamp
    purchase_price: str = field(default="")
    warranty_until: Optional[float] = field(default=None)  # timestamp
    expire_date: Optional[float] = field(default=None)  # timestamp
    importance: int = field(default=3)
    portability: int = field(default=3)
    tags: str = field(default="")
    image_url: str = field(default="")
    state: int = field(default=ItemState.ACTIVE)
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)


@dataclass
class InventoryData:
    id: int = field(default=-1)
    item_id: int = field(default=-1)
    residence_id: int = field(default=-1)
    container_id: Optional[int] = field(default=None)
    quantity: str = field(default="1")
    unit: str = field(default="个")
    min_quantity: str = field(default="0")
    max_quantity: str = field(default="0")
    last_check_time: Optional[float] = field(default=None)  # timestamp
    notes: str = field(default="")
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)
    # Extended fields for display
    item_name: str = field(default="")
    residence_name: str = field(default="")
    container_name: str = field(default="")


@dataclass
class JourneyData:
    id: int = field(default=-1)
    from_residence_id: int = field(default=-1)
    to_residence_id: int = field(default=-1)
    depart_time: Optional[float] = field(default=None)  # timestamp
    arrive_time: Optional[float] = field(default=None)  # timestamp
    status: int = field(default=JourneyStatus.PLANNED)
    transport_mode: str = field(default="")
    notes: str = field(default="")
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)
    # Extended fields for display
    from_residence_name: str = field(default="")
    to_residence_name: str = field(default="")
    items: List["JourneyItemData"] = field(default_factory=list)


@dataclass
class JourneyItemData:
    id: int = field(default=-1)
    journey_id: int = field(default=-1)
    item_id: int = field(default=-1)
    quantity: str = field(default="1")
    is_return: bool = field(default=False)
    from_container_id: Optional[int] = field(default=None)
    to_container_id: Optional[int] = field(default=None)
    status: int = field(default=JourneyItemStatus.PENDING)
    notes: str = field(default="")
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)
    # Extended fields for display
    item_name: str = field(default="")


@dataclass
class ConsumptionData:
    id: int = field(default=-1)
    inventory_id: int = field(default=-1)
    quantity: str = field(default="0")
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
    reason: str = field(default="")
    ctime: datetime = field(default_factory=datetime.now)


@dataclass
class ReplenishmentData:
    id: int = field(default=-1)
    inventory_id: int = field(default=-1)
    quantity: str = field(default="0")
    source: int = field(default=ReplenishmentSource.PURCHASE)
    source_residence_id: Optional[int] = field(default=None)
    cost: str = field(default="")
    transaction_id: Optional[int] = field(default=None)
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
    notes: str = field(default="")
    ctime: datetime = field(default_factory=datetime.now)
