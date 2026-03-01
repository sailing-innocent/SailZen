# -*- coding: utf-8 -*-
# @file necessity.py
# @brief Necessity Pydantic DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
物资管理模块 Pydantic DTOs

原位置: sail_server/data/necessity.py
"""

from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Residence DTOs
# ============================================================================

class ResidenceBase(BaseModel):
    """住所基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description="住所名称")
    code: str = Field(default="", description="住所代码")
    type: int = Field(default=2, description="住所类型")
    address: str = Field(default="", description="地址")
    description: str = Field(default="", description="描述")
    is_portable: bool = Field(default=False, description="是否便携")
    priority: int = Field(default=10, description="优先级")


class ResidenceCreateRequest(ResidenceBase):
    """创建住所请求"""
    pass


class ResidenceUpdateRequest(BaseModel):
    """更新住所请求"""
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = Field(default=None, description="住所名称")
    code: Optional[str] = Field(default=None, description="住所代码")
    type: Optional[int] = Field(default=None, description="住所类型")
    address: Optional[str] = Field(default=None, description="地址")
    description: Optional[str] = Field(default=None, description="描述")
    is_portable: Optional[bool] = Field(default=None, description="是否便携")
    priority: Optional[int] = Field(default=None, description="优先级")


class ResidenceResponse(ResidenceBase):
    """住所响应"""
    id: int = Field(description="住所ID")
    ctime: datetime = Field(description="创建时间")
    mtime: datetime = Field(description="修改时间")


class ResidenceListResponse(BaseModel):
    """住所列表响应"""
    residences: List[ResidenceResponse]
    total: int


# ============================================================================
# Container DTOs
# ============================================================================

class ContainerBase(BaseModel):
    """容器基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    residence_id: int = Field(description="所属住所ID")
    parent_id: Optional[int] = Field(default=None, description="父容器ID")
    name: str = Field(description="容器名称")
    type: int = Field(default=99, description="容器类型")
    description: str = Field(default="", description="描述")
    capacity: Optional[int] = Field(default=None, description="容量")


class ContainerCreateRequest(ContainerBase):
    """创建容器请求"""
    pass


class ContainerUpdateRequest(BaseModel):
    """更新容器请求"""
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = Field(default=None, description="容器名称")
    type: Optional[int] = Field(default=None, description="容器类型")
    description: Optional[str] = Field(default=None, description="描述")
    capacity: Optional[int] = Field(default=None, description="容量")


class ContainerResponse(ContainerBase):
    """容器响应"""
    id: int = Field(description="容器ID")
    ctime: datetime = Field(description="创建时间")
    mtime: datetime = Field(description="修改时间")


class ContainerListResponse(BaseModel):
    """容器列表响应"""
    containers: List[ContainerResponse]
    total: int


# ============================================================================
# ItemCategory DTOs
# ============================================================================

class ItemCategoryBase(BaseModel):
    """物资类别基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    parent_id: Optional[int] = Field(default=None, description="父类别ID")
    name: str = Field(description="类别名称")
    code: str = Field(default="", description="类别代码")
    icon: str = Field(default="", description="图标")
    is_consumable: bool = Field(default=False, description="是否消耗品")
    default_unit: str = Field(default="个", description="默认单位")
    description: str = Field(default="", description="描述")


class ItemCategoryCreateRequest(ItemCategoryBase):
    """创建物资类别请求"""
    pass


class ItemCategoryUpdateRequest(BaseModel):
    """更新物资类别请求"""
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = Field(default=None, description="类别名称")
    code: Optional[str] = Field(default=None, description="类别代码")
    icon: Optional[str] = Field(default=None, description="图标")
    is_consumable: Optional[bool] = Field(default=None, description="是否消耗品")
    default_unit: Optional[str] = Field(default=None, description="默认单位")
    description: Optional[str] = Field(default=None, description="描述")


class ItemCategoryResponse(ItemCategoryBase):
    """物资类别响应"""
    id: int = Field(description="类别ID")
    ctime: datetime = Field(description="创建时间")
    mtime: datetime = Field(description="修改时间")


class ItemCategoryListResponse(BaseModel):
    """物资类别列表响应"""
    categories: List[ItemCategoryResponse]
    total: int


# ============================================================================
# Item DTOs
# ============================================================================

class ItemBase(BaseModel):
    """物资基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description="物资名称")
    category_id: Optional[int] = Field(default=None, description="所属类别ID")
    type: int = Field(default=0, description="物资类型")
    brand: str = Field(default="", description="品牌")
    model: str = Field(default="", description="型号")
    serial_number: str = Field(default="", description="序列号")
    description: str = Field(default="", description="描述")
    importance: int = Field(default=3, description="重要程度")
    portability: int = Field(default=3, description="便携性")
    tags: str = Field(default="", description="标签")
    image_url: str = Field(default="", description="图片URL")
    state: int = Field(default=0, description="物资状态")


class ItemCreateRequest(ItemBase):
    """创建物资请求"""
    purchase_date: Optional[datetime] = Field(default=None, description="购买日期")
    purchase_price: str = Field(default="", description="购买价格")
    warranty_until: Optional[datetime] = Field(default=None, description="保修截止日期")
    expire_date: Optional[datetime] = Field(default=None, description="过期日期")


class ItemUpdateRequest(BaseModel):
    """更新物资请求"""
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = Field(default=None, description="物资名称")
    category_id: Optional[int] = Field(default=None, description="所属类别ID")
    type: Optional[int] = Field(default=None, description="物资类型")
    brand: Optional[str] = Field(default=None, description="品牌")
    model: Optional[str] = Field(default=None, description="型号")
    serial_number: Optional[str] = Field(default=None, description="序列号")
    description: Optional[str] = Field(default=None, description="描述")
    importance: Optional[int] = Field(default=None, description="重要程度")
    portability: Optional[int] = Field(default=None, description="便携性")
    tags: Optional[str] = Field(default=None, description="标签")
    image_url: Optional[str] = Field(default=None, description="图片URL")
    state: Optional[int] = Field(default=None, description="物资状态")


class ItemResponse(ItemBase):
    """物资响应"""
    id: int = Field(description="物资ID")
    purchase_date: Optional[datetime] = Field(default=None, description="购买日期")
    purchase_price: str = Field(default="", description="购买价格")
    warranty_until: Optional[datetime] = Field(default=None, description="保修截止日期")
    expire_date: Optional[datetime] = Field(default=None, description="过期日期")
    ctime: datetime = Field(description="创建时间")
    mtime: datetime = Field(description="修改时间")


class ItemListResponse(BaseModel):
    """物资列表响应"""
    items: List[ItemResponse]
    total: int


# ============================================================================
# Inventory DTOs
# ============================================================================

class InventoryBase(BaseModel):
    """库存基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    item_id: int = Field(description="物资ID")
    residence_id: int = Field(description="所属住所ID")
    container_id: Optional[int] = Field(default=None, description="所属容器ID")
    quantity: Decimal = Field(default=Decimal("1"), description="数量")
    unit: str = Field(default="个", description="单位")
    min_quantity: Decimal = Field(default=Decimal("0"), description="最小库存警戒值")
    max_quantity: Decimal = Field(default=Decimal("0"), description="最大库存值")
    notes: str = Field(default="", description="备注")


class InventoryCreateRequest(InventoryBase):
    """创建库存请求"""
    pass


class InventoryUpdateRequest(BaseModel):
    """更新库存请求"""
    model_config = ConfigDict(from_attributes=True)
    
    container_id: Optional[int] = Field(default=None, description="所属容器ID")
    quantity: Optional[Decimal] = Field(default=None, description="数量")
    unit: Optional[str] = Field(default=None, description="单位")
    min_quantity: Optional[Decimal] = Field(default=None, description="最小库存警戒值")
    max_quantity: Optional[Decimal] = Field(default=None, description="最大库存值")
    notes: Optional[str] = Field(default=None, description="备注")


class InventoryResponse(InventoryBase):
    """库存响应"""
    id: int = Field(description="库存ID")
    last_check_time: Optional[datetime] = Field(default=None, description="最后检查时间")
    ctime: datetime = Field(description="创建时间")
    mtime: datetime = Field(description="修改时间")
    # 扩展字段
    item_name: str = Field(default="", description="物资名称")
    residence_name: str = Field(default="", description="住所名称")
    container_name: str = Field(default="", description="容器名称")


class InventoryListResponse(BaseModel):
    """库存列表响应"""
    inventories: List[InventoryResponse]
    total: int


# ============================================================================
# Journey DTOs
# ============================================================================

class JourneyBase(BaseModel):
    """旅程基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    from_residence_id: int = Field(description="出发住所ID")
    to_residence_id: int = Field(description="目标住所ID")
    depart_time: Optional[datetime] = Field(default=None, description="出发时间")
    arrive_time: Optional[datetime] = Field(default=None, description="到达时间")
    status: int = Field(default=0, description="旅程状态")
    transport_mode: str = Field(default="", description="交通方式")
    notes: str = Field(default="", description="备注")


class JourneyCreateRequest(JourneyBase):
    """创建旅程请求"""
    pass


class JourneyUpdateRequest(BaseModel):
    """更新旅程请求"""
    model_config = ConfigDict(from_attributes=True)
    
    depart_time: Optional[datetime] = Field(default=None, description="出发时间")
    arrive_time: Optional[datetime] = Field(default=None, description="到达时间")
    status: Optional[int] = Field(default=None, description="旅程状态")
    transport_mode: Optional[str] = Field(default=None, description="交通方式")
    notes: Optional[str] = Field(default=None, description="备注")


class JourneyResponse(JourneyBase):
    """旅程响应"""
    id: int = Field(description="旅程ID")
    ctime: datetime = Field(description="创建时间")
    mtime: datetime = Field(description="修改时间")
    # 扩展字段
    from_residence_name: str = Field(default="", description="出发住所名称")
    to_residence_name: str = Field(default="", description="目标住所名称")


class JourneyListResponse(BaseModel):
    """旅程列表响应"""
    journeys: List[JourneyResponse]
    total: int


# ============================================================================
# JourneyItem DTOs
# ============================================================================

class JourneyItemBase(BaseModel):
    """旅程物资基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    journey_id: int = Field(description="所属旅程ID")
    item_id: int = Field(description="物资ID")
    quantity: Decimal = Field(default=Decimal("1"), description="数量")
    is_return: bool = Field(default=False, description="是否归还")
    from_container_id: Optional[int] = Field(default=None, description="出发容器ID")
    to_container_id: Optional[int] = Field(default=None, description="目标容器ID")
    status: int = Field(default=0, description="状态")
    notes: str = Field(default="", description="备注")


class JourneyItemCreateRequest(JourneyItemBase):
    """创建旅程物资请求"""
    pass


class JourneyItemUpdateRequest(BaseModel):
    """更新旅程物资请求"""
    model_config = ConfigDict(from_attributes=True)
    
    quantity: Optional[Decimal] = Field(default=None, description="数量")
    is_return: Optional[bool] = Field(default=None, description="是否归还")
    from_container_id: Optional[int] = Field(default=None, description="出发容器ID")
    to_container_id: Optional[int] = Field(default=None, description="目标容器ID")
    status: Optional[int] = Field(default=None, description="状态")
    notes: Optional[str] = Field(default=None, description="备注")


class JourneyItemResponse(JourneyItemBase):
    """旅程物资响应"""
    id: int = Field(description="旅程物资ID")
    ctime: datetime = Field(description="创建时间")
    mtime: datetime = Field(description="修改时间")
    # 扩展字段
    item_name: str = Field(default="", description="物资名称")


class JourneyItemListResponse(BaseModel):
    """旅程物资列表响应"""
    items: List[JourneyItemResponse]
    total: int


# ============================================================================
# Consumption DTOs
# ============================================================================

class ConsumptionBase(BaseModel):
    """消耗记录基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    inventory_id: int = Field(description="库存ID")
    quantity: Decimal = Field(description="消耗数量")
    htime: Optional[datetime] = Field(default=None, description="发生时间")
    reason: str = Field(default="", description="原因")


class ConsumptionCreateRequest(ConsumptionBase):
    """创建消耗记录请求"""
    pass


class ConsumptionResponse(ConsumptionBase):
    """消耗记录响应"""
    id: int = Field(description="消耗记录ID")
    ctime: datetime = Field(description="创建时间")


class ConsumptionListResponse(BaseModel):
    """消耗记录列表响应"""
    consumptions: List[ConsumptionResponse]
    total: int


# ============================================================================
# Replenishment DTOs
# ============================================================================

class ReplenishmentBase(BaseModel):
    """补货记录基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    inventory_id: int = Field(description="库存ID")
    quantity: Decimal = Field(description="补货数量")
    source: int = Field(default=0, description="来源")
    source_residence_id: Optional[int] = Field(default=None, description="来源住所ID")
    cost: str = Field(default="", description="花费")
    transaction_id: Optional[int] = Field(default=None, description="关联交易ID")
    htime: Optional[datetime] = Field(default=None, description="发生时间")
    notes: str = Field(default="", description="备注")


class ReplenishmentCreateRequest(ReplenishmentBase):
    """创建补货记录请求"""
    pass


class ReplenishmentResponse(ReplenishmentBase):
    """补货记录响应"""
    id: int = Field(description="补货记录ID")
    ctime: datetime = Field(description="创建时间")


class ReplenishmentListResponse(BaseModel):
    """补货记录列表响应"""
    replenishments: List[ReplenishmentResponse]
    total: int
