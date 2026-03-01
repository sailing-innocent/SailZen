# -*- coding: utf-8 -*-
# @file __init__.py
# @brief ORM Models Package
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
SQLAlchemy ORM 模型包

Phase 2 重构目标：将 ORM 模型从 data/ 层迁移至此

当前迁移状态：
- [ ] analysis 模块（进行中）
- [ ] finance 模块（待开始）
- [ ] health 模块（待开始）
- [ ] text 模块（待开始）
- [ ] 其他模块（待开始）
"""

from sail_server.data.orm import ORMBase

__all__ = ["ORMBase"]
