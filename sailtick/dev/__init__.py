# -*- coding: utf-8 -*-
# @file __init__.py
# @brief SailTick 自我开发能力（agent/sailtick-dev 分支隔离 + 硬护栏）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 自我开发模块。

安全协议（设计文档 D5）:
  - 仅在 agent/sailtick-dev 本地分支工作；严禁 push origin（项目铁律）
  - 严禁 checkout main / 写 main
  - 严禁动 data/ 与 .env*
  - 仅允许改动 whitelist 目录
完成任务后自动开 approval 票据，由用户 review 合入。
"""

from sailtick.dev.guard import GuardError, SelfDevGuard
from sailtick.dev.repo import DevRepo
from sailtick.dev.tasks import DevTaskRunner

__all__ = ["GuardError", "SelfDevGuard", "DevRepo", "DevTaskRunner"]
