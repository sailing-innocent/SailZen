# -*- coding: utf-8 -*-
# @file life.py
# @brief Personal Information Storage
# @author sailing-innocent
# @date 2025-02-03
# @version 2.0
# ---------------------------------

"""
生活服务模块数据层

此模块仅用于重新导出 ORM 模型和 Pydantic DTOs：
- ORM 模型来自 infrastructure.orm.life
- Pydantic DTOs 来自 application.dto.life
"""

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

__all__ = [
    # ORM Models
    "ServiceAccount",
    # Pydantic DTOs
    "ServiceAccountBase",
    "ServiceAccountCreateRequest",
    "ServiceAccountUpdateRequest",
    "ServiceAccountResponse",
    "ServiceAccountListResponse",
]
