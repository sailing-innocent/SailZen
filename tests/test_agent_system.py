# -*- coding: utf-8 -*-
# @file test_agent_system.py
# @brief Agent System Tests (DEPRECATED)
# @author sailing-innocent
# @date 2025-02-25
# @version 2.0
# ---------------------------------

"""
⚠️ 此测试文件已弃用 (DEPRECATED)

弃用原因：
- Agent 系统已完全重构为 Unified Agent 架构
- 旧版数据模型 (UserPrompt, AgentTask, AgentStep 等) 已移除
- 新版架构使用 UnifiedAgentTask, UnifiedAgentStep 等模型

替代测试：
- tests/model/test_unified_agent.py - Unified Agent 模型测试
- tests/test_unified_agent_system.py - Unified Agent 系统测试（待创建）

如需查看旧版代码，请参考 git 历史记录。
"""

import pytest

pytest.skip(
    "此测试文件已弃用，Agent 系统已重构为 Unified Agent 架构。"
    "请使用 tests/model/test_unified_agent.py 进行替代测试。",
    allow_module_level=True
)
