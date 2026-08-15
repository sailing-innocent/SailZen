# -*- coding: utf-8 -*-
# @file rhythm_pems_scope_check.py
# @brief PEMS → Rhythm 合并范围检查脚本
# @author sailing-innocent
# @date 2026-10-27

"""
扫描 PEMS 遗留源码（sail_server/model/pems_legacy.py）与当前 Rhythm 实现，
输出每个 PEMS 公共函数/端点在 Rhythm 中的等价实现状态。

用法:
    uv run python scripts/rhythm_pems_scope_check.py

退出码:
    0  全部已覆盖
    1  存在待完成项
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PEMS_MODEL = ROOT / "sail_server" / "model" / "pems_legacy.py"
RHYTHM_MODEL = ROOT / "sail_server" / "model" / "rhythm.py"
RHYTHM_PLANNER = ROOT / "sail_server" / "model" / "rhythm_planner.py"
RHYTHM_CONTROLLER = ROOT / "sail_server" / "controller" / "rhythm.py"

# PEMS 公共函数 → Rhythm 等价实现标识（函数名或 endpoint）
SCOPE = {
    "_compute_energy_budget": {
        "rhythm_impl": "get_or_create_profile",
        "note": "精力预算统一使用 rhythm_energy_profile.daily_energy_budget + planner",
    },
    "get_day_view_impl": {
        "rhythm_impl": "get_rhythm_day_view_impl",
        "note": "统一日视图合并时间线/能量/打卡/健康信号",
    },
    "plan_mission_on_day_impl": {
        "rhythm_impl": "update_affair_impl / transit_affair_state_impl",
        "note": "通过 affair.day_id + state 转移实现排期",
    },
    "log_health_on_day_impl": {
        "rhythm_impl": "health_checkin_impl",
        "note": "双写 health 表与 rhythm_discipline_logs",
    },
    "get_timespan_view_impl": {
        "rhythm_impl": "review_timespan_impl",
        "note": "GET /api/v1/rhythm/review/timespan/{project_id}",
    },
    "review_timespan_impl": {
        "rhythm_impl": "review_timespan_impl",
        "note": "周期复盘聚合",
    },
    "get_project_timeline_impl": {
        "rhythm_impl": "project_timeline_impl",
        "note": "GET /api/v1/rhythm/review/project/{project_id}",
    },
    "get_energy_budget_impl": {
        "rhythm_impl": "get_energy_profile_impl",
        "note": "GET /api/v1/rhythm/energy/profile",
    },
    "get_insight_daily_impl": {
        "rhythm_impl": "get_day_review_impl (rhythm_planner.py)",
        "note": "GET /api/v1/rhythm/review/day",
    },
    "get_insight_weekly_impl": {
        "rhythm_impl": "get_week_review_impl (rhythm_planner.py)",
        "note": "GET /api/v1/rhythm/review/week",
    },
    "_challenge_checkins": {
        "rhythm_impl": "checkin_impl / RhythmDisciplineLog",
        "note": "#challenge# 项目转换为 precept/habit，打卡由 discipline log 承接",
    },
}


def _extract_functions(path: Path) -> set:
    if not path.exists():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def _file_contains(path: Path, patterns: list) -> bool:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return any(re.search(p, text) for p in patterns)


def main() -> int:
    pems_funcs = _extract_functions(PEMS_MODEL)
    rhythm_funcs = _extract_functions(RHYTHM_MODEL) | _extract_functions(RHYTHM_PLANNER)
    controller_text = RHYTHM_CONTROLLER.read_text(encoding="utf-8")

    uncovered = []
    print("=" * 70)
    print("PEMS → Rhythm 合并范围检查")
    print("=" * 70)

    for func, target in SCOPE.items():
        impl = target["rhythm_impl"]
        covered = False
        if "/api/v1/rhythm/" in impl:
            endpoint = impl.split("/api/v1/rhythm/")[-1]
            # 移除路由参数类型标注与占位
            covered = re.sub(r"\{[^}]+:int\}", r"{\\d+}", endpoint).replace("{", r"\\{").replace("}", r"\\}") in controller_text
        else:
            impl_names = {n.strip() for n in re.split(r"[/()]", impl) if n.strip()}
            covered = bool(impl_names & rhythm_funcs)

        status = "已覆盖" if covered else "待完成"
        print(f"\n[PEMS] {func}")
        print(f"  Rhythm: {impl}")
        print(f"  状态: {status}")
        print(f"  说明: {target['note']}")
        if not covered:
            uncovered.append(func)

    # 额外检查 PEMS 遗留 API 是否已删除
    print("\n" + "=" * 70)
    print("PEMS API 残留检查")
    print("=" * 70)
    server_text = (ROOT / "server.py").read_text(encoding="utf-8")
    pems_routes_gone = "pems_router" not in server_text
    print(f"  /api/v1/pems 路由已删除: {'是' if pems_routes_gone else '否'}")
    if not pems_routes_gone:
        uncovered.append("pems_router")

    print("\n" + "=" * 70)
    if uncovered:
        print(f"存在 {len(uncovered)} 个待完成项:")
        for item in uncovered:
            print(f"  - {item}")
        return 1

    print("所有 PEMS 功能 scope 已在 Rhythm 话语下重写。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
