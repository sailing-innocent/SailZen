# -*- coding: utf-8 -*-
# @file run_analysis.py
# @brief 数据收集编排器 —— 统一调用各引擎，输出结构化证据包
# @author sailing-innocent
# @date 2026-06-07
# @version 2.0
# ---------------------------------
"""
数据收集编排器（纯工具层）

职责：
1. 调用 sailzen CLI 导出财务和健康原始数据
2. 调用各分析引擎生成结构化证据
3. 将证据包统一输出到工作目录

不做：
- 不做业务判断
- 不写结论
- 不生成报告

输出文件：
- finance_evidence_{label}.json  —— 财务指标与异常点
- health_evidence_{label}.json   —— 体重/运动原始指标
- journal_raw_{label}.json       —— 日记原文集合

使用方式：
    python run_analysis.py --start 2025-01-01 --end 2025-12-31 --label 2025
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import AnalysisConfig, resolve_server_url
from finance_analyzer import FinanceEngine
from health_analyzer import HealthEngine
from journal_fetcher import JournalFetcher


WORK_DIR = Path("data/temp/wellness")


def ensure_workdir():
    WORK_DIR.mkdir(parents=True, exist_ok=True)


def export_finance(output: Path) -> bool:
    cmd = ["sailzen", "finance", "pull", "--output", str(output)]
    print(f"[Export] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[Export] 失败: {result.stderr}")
        return False
    print(f"[Export] 成功: {output}")
    return True


def export_health_weight(output: Path, start: str, end: str) -> bool:
    cmd = ["sailzen", "health", "pull-weight", "--start", start, "--end", end, "--output", str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[Export] 体重导出失败: {result.stderr}")
        return False
    print(f"[Export] 成功: {output}")
    return True


def export_health_exercise(output: Path, start: str, end: str) -> bool:
    cmd = ["sailzen", "health", "pull-exercise", "--start", start, "--end", end, "--output", str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[Export] 运动导出失败: {result.stderr}")
        return False
    print(f"[Export] 成功: {output}")
    return True


def run_collection(
    start: datetime,
    end: datetime,
    label: str,
    exclude_mortgage: bool = True,
    height_m: float = 1.75,
    journal_dir: str = "D:/ws/vault/notes",
    skip_export: bool = False,
) -> dict[str, Path]:
    """
    执行数据收集，返回证据包文件路径映射
    """
    ensure_workdir()
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    finance_csv = WORK_DIR / f"finance_{label}.csv"
    weight_csv = WORK_DIR / f"health_weight_{label}.csv"
    exercise_csv = WORK_DIR / f"health_exercise_{label}.csv"
    finance_json = WORK_DIR / f"finance_evidence_{label}.json"
    health_json = WORK_DIR / f"health_evidence_{label}.json"
    journal_json = WORK_DIR / f"journal_raw_{label}.json"

    # 1. 导出原始数据
    if not skip_export:
        print("=" * 60)
        print("📥 数据导出")
        print("=" * 60)
        export_finance(finance_csv)
        export_health_weight(weight_csv, start_str, end_str)
        export_health_exercise(exercise_csv, start_str, end_str)
        print()

    # 2. 财务证据
    print("=" * 60)
    print("💰 财务指标计算")
    print("=" * 60)
    if finance_csv.exists():
        config = AnalysisConfig(exclude_mortgage=exclude_mortgage)
        fe = FinanceEngine(config)
        fe.load_csv(str(finance_csv))
        ev = fe.analyze(start, end, label)
        import json
        from dataclasses import asdict
        def ser(o):
            if isinstance(o, list): return [ser(i) for i in o]
            if hasattr(o, "__dataclass_fields__"): return {k: ser(v) for k, v in asdict(o).items()}
            return o
        with open(finance_json, "w", encoding="utf-8") as f:
            json.dump(ser(ev), f, ensure_ascii=False, indent=2)
        print(f"输出: {finance_json}")
    else:
        print(f"跳过: {finance_csv} 不存在")
    print()

    # 3. 健康证据
    print("=" * 60)
    print("❤️ 健康指标计算")
    print("=" * 60)
    he = HealthEngine(height_m=height_m)
    if weight_csv.exists():
        he.load_weight_csv(str(weight_csv))
    if exercise_csv.exists():
        he.load_exercise_csv(str(exercise_csv))
    ev = he.analyze(start, end, label)
    with open(health_json, "w", encoding="utf-8") as f:
        json.dump(ser(ev), f, ensure_ascii=False, indent=2)
    print(f"输出: {health_json}")
    print()

    # 4. 日记原文
    print("=" * 60)
    print("📓 日记原文收集")
    print("=" * 60)
    jf = JournalFetcher(journal_dir)
    collection = jf.fetch(start, end, label)
    with open(journal_json, "w", encoding="utf-8") as f:
        json.dump(ser(collection), f, ensure_ascii=False, indent=2)
    print(f"输出: {journal_json}")
    print(f"  覆盖: {collection.days_with_journal}/{collection.total_days_in_period} 天 ({collection.coverage_rate:.1f}%)")
    print()

    return {
        "finance": finance_json,
        "health": health_json,
        "journal": journal_json,
    }


def main():
    parser = argparse.ArgumentParser(description="数据收集编排器")
    parser.add_argument("--start", required=True, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--label", required=True, help="证据包标签（如 2025, 2026Q2, 2026-05）")
    parser.add_argument("--include-mortgage", action="store_true", help="包含房贷账户")
    parser.add_argument("--height", type=float, default=1.75)
    parser.add_argument("--journal-dir", default="D:/ws/vault/notes")
    parser.add_argument("--skip-export", action="store_true")
    args = parser.parse_args()

    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")

    paths = run_collection(
        start=start_dt,
        end=end_dt,
        label=args.label,
        exclude_mortgage=not args.include_mortgage,
        height_m=args.height,
        journal_dir=args.journal_dir,
        skip_export=args.skip_export,
    )

    print("=" * 60)
    print("✅ 证据包收集完成")
    print("=" * 60)
    for name, path in paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
