# -*- coding: utf-8 -*-
# @file necessity.py
# @brief The Necessity (生活物资) Data Model
# @author sailing-innocent
# @date 2026-02-01
# @version 2.0
# ---------------------------------

"""
物资管理模块数据层

ORM 模型和 Enums 已从 infrastructure.orm.necessity 迁移
DTO 模型已从 application.dto.necessity 迁移

此文件保留向后兼容的导出和遗留的 dataclass DTOs
（因为 controller 层仍使用 Litestar DataclassDTO）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

# 从 infrastructure.orm 导入 ORM 模型和 Enums
from sail_server.infrastructure.orm.necessity import (
    # Enums
    ResidenceType,
    ContainerType,
    ItemType,
    ItemState,
    JourneyStatus,
    JourneyItemStatus,
    ReplenishmentSource,
    # ORM Models
    Residence,
    Container,
    ItemCategory,
    Item,
    Inventory,
    Journey,
    JourneyItem,
    Consumption,
    Replenishment,
)

# 从 application.dto 导入 Pydantic DTOs
from sail_server.application.dto.necessity import (
    ResidenceBase,
    ResidenceCreateRequest,
    ResidenceUpdateRequest,
    ResidenceResponse,
    ResidenceListResponse,
    ContainerBase,
    ContainerCreateRequest,
    ContainerUpdateRequest,
    ContainerResponse,
    ContainerListResponse,
    ItemCategoryBase,
    ItemCategoryCreateRequest,
    ItemCategoryUpdateRequest,
    ItemCategoryResponse,
    ItemCategoryListResponse,
    ItemBase,
    ItemCreateRequest,
    ItemUpdateRequest,
    ItemResponse,
    ItemListResponse,
    InventoryBase,
    InventoryCreateRequest,
    InventoryUpdateRequest,
    InventoryResponse,
    InventoryListResponse,
    JourneyBase,
    JourneyCreateRequest,
    JourneyUpdateRequest,
    JourneyResponse,
    JourneyListResponse,
    JourneyItemBase,
    JourneyItemCreateRequest,
    JourneyItemUpdateRequest,
    JourneyItemResponse,
    JourneyItemListResponse,
    ConsumptionBase,
    ConsumptionCreateRequest,
    ConsumptionResponse,
    ConsumptionListResponse,
    ReplenishmentBase,
    ReplenishmentCreateRequest,
    ReplenishmentResponse,
    ReplenishmentListResponse,
)


# ============================================================================
# Legacy Dataclass DTOs (保留以兼容现有 controller)
# TODO: 迁移到 Pydantic DTOs 后删除
# ============================================================================

@dataclass
class ResidenceData:
    """住所数据 (legacy dataclass)"""
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
    """容器数据 (legacy dataclass)"""
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
    """物资类别数据 (legacy dataclass)"""
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
    """物资数据 (legacy dataclass)"""
    id: int = field(default=-1)
    name: str = field(default="")
    category_id: Optional[int] = field(default=None)
    type: int = field(default=ItemType.UNIQUE)
    brand: str = field(default="")
    model: str = field(default="")
    serial_number: str = field(default="")
    description: str = field(default="")
    purchase_date: Optional[float] = field(default=None)
    purchase_price: str = field(default="")
    warranty_until: Optional[float] = field(default=None)
    expire_date: Optional[float] = field(default=None)
    importance: int = field(default=3)
    portability: int = field(default=3)
    tags: str = field(default="")
    image_url: str = field(default="")
    state: int = field(default=ItemState.ACTIVE)
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)


@dataclass
class InventoryData:
    """库存数据 (legacy dataclass)"""
    id: int = field(default=-1)
    item_id: int = field(default=-1)
    residence_id: int = field(default=-1)
    container_id: Optional[int] = field(default=None)
    quantity: str = field(default="1")
    unit: str = field(default="个")
    min_quantity: str = field(default="0")
    max_quantity: str = field(default="0")
    last_check_time: Optional[float] = field(default=None)
    notes: str = field(default="")
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)
    # Extended fields for display
    item_name: str = field(default="")
    residence_name: str = field(default="")
    container_name: str = field(default="")


@dataclass
class JourneyData:
    """旅程数据 (legacy dataclass)"""
    id: int = field(default=-1)
    from_residence_id: int = field(default=-1)
    to_residence_id: int = field(default=-1)
    depart_time: Optional[float] = field(default=None)
    arrive_time: Optional[float] = field(default=None)
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
    """旅程物资数据 (legacy dataclass)"""
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
    """消耗记录数据 (legacy dataclass)"""
    id: int = field(default=-1)
    inventory_id: int = field(default=-1)
    quantity: str = field(default="0")
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
    reason: str = field(default="")
    ctime: datetime = field(default_factory=datetime.now)


@dataclass
class ReplenishmentData:
    """补货记录数据 (legacy dataclass)"""
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
    # Pydantic DTOs
    "ResidenceBase",
    "ResidenceCreateRequest",
    "ResidenceUpdateRequest",
    "ResidenceResponse",
    "ResidenceListResponse",
    "ContainerBase",
    "ContainerCreateRequest",
    "ContainerUpdateRequest",
    "ContainerResponse",
    "ContainerListResponse",
    "ItemCategoryBase",
    "ItemCategoryCreateRequest",
    "ItemCategoryUpdateRequest",
    "ItemCategoryResponse",
    "ItemCategoryListResponse",
    "ItemBase",
    "ItemCreateRequest",
    "ItemUpdateRequest",
    "ItemResponse",
    "ItemListResponse",
    "InventoryBase",
    "InventoryCreateRequest",
    "InventoryUpdateRequest",
    "InventoryResponse",
    "InventoryListResponse",
    "JourneyBase",
    "JourneyCreateRequest",
    "JourneyUpdateRequest",
    "JourneyResponse",
    "JourneyListResponse",
    "JourneyItemBase",
    "JourneyItemCreateRequest",
    "JourneyItemUpdateRequest",
    "JourneyItemResponse",
    "JourneyItemListResponse",
    "ConsumptionBase",
    "ConsumptionCreateRequest",
    "ConsumptionResponse",
    "ConsumptionListResponse",
    "ReplenishmentBase",
    "ReplenishmentCreateRequest",
    "ReplenishmentResponse",
    "ReplenishmentListResponse",
    # Legacy Dataclass DTOs
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
