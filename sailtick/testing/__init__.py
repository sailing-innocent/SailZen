# -*- coding: utf-8 -*-
# @file __init__.py
# @brief SailTick 测试体系基础设施包（VirtualClock / FakeServer / Trajectory / Sandbox）
# @author sailing-innocent
# @date 2026-11-21
# @version 1.0
# ---------------------------------
"""SailTick 辅助测试体系包。

四层测试架构:
  Layer 1: 单元与组件功能测试 (tests/sailtick/test_unit_components.py 等)
  Layer 2: Mock LLM 轨迹回放测试 (sailtick.testing.trajectory)
  Layer 3: 真实 API 短周期可控沙盒测试 (sailtick.testing.sandbox)
  Layer 4: 一键开关与监控灰度测试 (sailtick.canary + tests/sailtick/test_canary_monitor.py)
"""

from sailtick.testing.clock import VirtualClock
from sailtick.testing.fake_server import SimulatedSailServer
from sailtick.testing.sandbox import (
    SANDBOX_SCENARIOS,
    LiveSandboxRunner,
    SandboxConfig,
    SandboxEvaluator,
    SandboxReport,
)
from sailtick.testing.trajectory import (
    BUILTIN_SCENARIOS,
    ScriptedLLM,
    TrajectoryReport,
    TrajectoryRunner,
    TrajectoryScenario,
    TrajectoryStep,
    TrajectoryTickSpec,
)

__all__ = [
    "VirtualClock",
    "SimulatedSailServer",
    "TrajectoryStep",
    "ScriptedLLM",
    "TrajectoryTickSpec",
    "TrajectoryScenario",
    "TrajectoryReport",
    "TrajectoryRunner",
    "BUILTIN_SCENARIOS",
    "SandboxConfig",
    "SandboxEvaluator",
    "SandboxReport",
    "LiveSandboxRunner",
    "SANDBOX_SCENARIOS",
]
