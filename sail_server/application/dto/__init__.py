# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Pydantic DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
Pydantic DTO (Data Transfer Object) 包

Phase 3 重构目标：将 dataclass DTOs 从 data/ 层迁移至此

命名规范:
- *Request: 请求 DTO (创建、更新)
- *Response: 响应 DTO
- *Filter: 查询过滤 DTO
- *ListResponse: 列表响应 DTO (包含分页信息)

当前迁移状态：
- [ ] finance 模块（试点）
- [ ] health 模块
- [ ] text 模块
- [ ] analysis 模块
- [ ] 其他模块
"""

# 注意: 在 Phase 3 完成前，DTOs 仍然主要从 data/ 层导入
# from sail_server.data.finance import AccountData

# Phase 3 完成后，将改为从 application.dto 导入
# from sail_server.application.dto.finance import AccountCreateRequest, AccountResponse
