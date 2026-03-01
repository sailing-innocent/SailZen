# -*- coding: utf-8 -*-
# @file life.py
# @brief Personal Information Storage
# @author sailing-innocent
# @date 2025-02-03
# @version 2.0
# ---------------------------------

"""
生活服务模块数据层

ORM 模型已从 infrastructure.orm.life 迁移
DTO 模型已从 application.dto.life 迁移

此文件保留向后兼容的导出和遗留的 dataclass DTOs
（因为 controller 层仍使用 Litestar DataclassDTO）
"""

from dataclasses import dataclass, field

# 从 infrastructure.orm 导入 ORM 模型
from sail_server.infrastructure.orm.life import (
    ServiceAccount,
)

# 从 application.dto 导入 Pydantic DTOs
from sail_server.application.dto.life import (
    ServiceAccountBase,
    ServiceAccountCreateRequest,
    ServiceAccountUpdateRequest,
    ServiceAccountResponse,
    ServiceAccountListResponse,
)


# ============================================================================
# Legacy Dataclass DTOs (保留以兼容现有 controller)
# TODO: 迁移到 Pydantic DTOs 后删除
# ============================================================================

@dataclass
class ServiceAccountData:
    """服务账户数据 (legacy dataclass)"""
    id: int = field(default=None)
    name: str = field(default="")
    entry: str = field(default="")
    username: str = field(default="")
    password: str = field(default="")
    desp: str = field(default="")
    expire_time: int = field(default=0)


__all__ = [
    # ORM Models
    "ServiceAccount",
    # Pydantic DTOs
    "ServiceAccountBase",
    "ServiceAccountCreateRequest",
    "ServiceAccountUpdateRequest",
    "ServiceAccountResponse",
    "ServiceAccountListResponse",
    # Legacy Dataclass DTOs
    "ServiceAccountData",
]
