# -*- coding: utf-8 -*-
# @file __init__.py
# @brief SailTick — 私人减肥监督教练（常驻 Tick 驱动 Agent）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick: private weight-loss coach daemon.

每 6 小时唤醒一次（00/06/12/18 Asia/Shanghai），每次 3 小时工作预算，
每 Tick 从零组装上下文（system prompt + handoff + 记忆摘要 + 数据扫描）。

设计文档: doc/design/agent-system/sailtick.md
迁移说明: doc/design/agent-system/sailtick-migration-notes.md
"""

__version__ = "1.0.0"
