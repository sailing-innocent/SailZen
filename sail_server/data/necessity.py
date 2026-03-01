# -*- coding: utf-8 -*-
# @file necessity.py
# @brief The Necessity (生活物资) Data Model - Re-export Module
# @author sailing-innocent
# @date 2026-02-01
# @version 2.0
# ---------------------------------

"""
物资管理模块数据层 - Re-export 模块

此模块仅用于重新导出以下组件：
- Enums: 从 infrastructure.orm.necessity 导入
- ORM Models: 从 infrastructure.orm.necessity 导入
- Pydantic DTOs: 从 application.dto.necessity 导入

注意：所有遗留的 dataclass DTOs 已被移除，请直接使用 Pydantic DTOs
"""

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
]
