# -*- coding: utf-8 -*-
# @file state.py
# @brief 依赖健康状态管理
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""DependencyState — 跟踪外部依赖（sail_server / LLM）健康。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


class DependencyState:
    def __init__(self):
        self._deps: Dict[str, Dict[str, Any]] = {}

    def update(self, name: str, status: str, **extra: Any) -> None:
        self._deps[name] = {
            "status": status,  # ok | degraded | down
            "checked_at": datetime.now().isoformat(),
            **extra,
        }

    def get(self, name: str) -> Dict[str, Any]:
        return self._deps.get(name, {"status": "unknown"})

    def all_ok(self, *names: str) -> bool:
        targets = names or tuple(self._deps.keys())
        return all(self._deps.get(n, {}).get("status") in ("ok", "degraded") for n in targets)

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._deps)
