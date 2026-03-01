# -*- coding: utf-8 -*-
# @file text.py
# @brief Text data module - re-exports ORM models and Pydantic DTOs
# @author sailing-innocent
# @date 2025-01-29
# @version 3.0
# ---------------------------------

"""
文本管理模块数据层 - 重新导出模块

此模块仅作为重新导出模块，提供统一的导入入口：
- ORM 模型从 infrastructure.orm.text 导入
- Pydantic DTOs 从 application.dto.text 导入
"""

# 从 infrastructure.orm 导入 ORM 模型
from sail_server.infrastructure.orm.text import (
    Work,
    Edition,
    DocumentNode,
    IngestJob,
)

# 从 application.dto 导入 Pydantic DTOs
from sail_server.application.dto.text import (
    WorkBase,
    WorkCreateRequest,
    WorkUpdateRequest,
    WorkResponse,
    WorkListResponse,
    EditionBase,
    EditionCreateRequest,
    EditionUpdateRequest,
    EditionResponse,
    EditionListResponse,
    DocumentNodeBase,
    DocumentNodeCreateRequest,
    DocumentNodeUpdateRequest,
    DocumentNodeResponse,
    DocumentNodeListResponse,
    IngestJobBase,
    IngestJobCreateRequest,
    IngestJobResponse,
    IngestJobListResponse,
)

__all__ = [
    # ORM Models
    "Work",
    "Edition",
    "DocumentNode",
    "IngestJob",
    # Pydantic DTOs
    "WorkBase",
    "WorkCreateRequest",
    "WorkUpdateRequest",
    "WorkResponse",
    "WorkListResponse",
    "EditionBase",
    "EditionCreateRequest",
    "EditionUpdateRequest",
    "EditionResponse",
    "EditionListResponse",
    "DocumentNodeBase",
    "DocumentNodeCreateRequest",
    "DocumentNodeUpdateRequest",
    "DocumentNodeResponse",
    "DocumentNodeListResponse",
    "IngestJobBase",
    "IngestJobCreateRequest",
    "IngestJobResponse",
    "IngestJobListResponse",
]
