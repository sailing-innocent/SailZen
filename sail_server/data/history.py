# -*- coding: utf-8 -*-
# @file history.py
# @brief The History Events Data Storage
# @author sailing-innocent
# @date 2025-10-12
# @version 2.0
# ---------------------------------

"""
历史事件模块数据层 - 重新导出模块

此模块仅重新导出：
- ORM 模型: HistoryEvent (来自 infrastructure.orm.history)
- Pydantic DTOs: HistoryEventBase, HistoryEventCreateRequest, HistoryEventUpdateRequest,
  HistoryEventResponse, HistoryEventListResponse (来自 application.dto.history)
"""

# 从 infrastructure.orm 导入 ORM 模型
from sail_server.infrastructure.orm.history import (
    HistoryEvent,
)

# 从 application.dto 导入 Pydantic DTOs
from sail_server.application.dto.history import (
    HistoryEventBase,
    HistoryEventCreateRequest,
    HistoryEventUpdateRequest,
    HistoryEventResponse,
    HistoryEventListResponse,
)


__all__ = [
    # ORM Models
    "HistoryEvent",
    # Pydantic DTOs
    "HistoryEventBase",
    "HistoryEventCreateRequest",
    "HistoryEventUpdateRequest",
    "HistoryEventResponse",
    "HistoryEventListResponse",
]
