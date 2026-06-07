# -*- coding: utf-8 -*-
# @file health_analyzer.py
# @brief 健康数据引擎 —— 只输出原始指标，不做健康判断
# @author sailing-innocent
# @date 2026-06-07
# @version 2.0
# ---------------------------------
"""
健康数据引擎（纯工具层）

职责：
1. 读取体重/运动 CSV，按时间范围过滤
2. 计算体重变化指标（斜率、极值、变化率）
3. 计算 BMI 序列
4. 统计运动频率
5. 输出结构化 JSON 供 LLM 解读

不做的：
- 不做 "A/B/C/D" 评分
- 不写 "肥胖/正常" 等结论
- 不生成建议文字

使用方式：
    python health_analyzer.py --weight-csv weights.csv \
        --exercise-csv exercises.csv --start 2025-01-01 --end 2025-12-31 \
        --height 1.75 --output health_evidence.json
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from common import read_csv, write_json, parse_htime, WeightRecord


# ============================================================================
# 输出数据结构（纯数据）
# ============================================================================

@dataclass
class WeightPoint:
    id: int
    value: float
    date: Optional[str] = None  # ISO date
    note: str = ""


@dataclass
class WeightMetrics:
    start_weight: float = 0.0
    end_weight: float = 0.0
    min_weight: float = 0.0
    max_weight: float = 0.0
    avg_weight: float = 0.0
    median_weight: float = 0.0
    std_weight: float = 0.0
    change_kg: float = 0.0
    change_pct: float = 0.0
    days_span: int = 0
    records_count: int = 0
    recording_rate: float = 0.0
    weekly_change: float = 0.0
    monthly_change: float = 0.0
    daily_records: list[WeightPoint] = field(default_factory=list)
    monthly_avg: dict[str, float] = field(default_factory=dict)
    plateau_periods: list[tuple[str, str, float]] = field(default_factory=list)  # (start, end, change)


@dataclass
class BMISeries:
    height_m: float = 1.75
    bmi_start: float = 0.0
    bmi_end: float = 0.0
    bmi_min: float = 0.0
    bmi_max: float = 0.0
    bmi_avg: float = 0.0
    target_bmi_low: float = 18.5
    target_bmi_high: float = 24.0
    target_weight_low: float = 0.0
    target_weight_high: float = 0.0


@dataclass
class ExerciseMetrics:
    total_sessions: int = 0
    total_duration_min: float = 0.0
    sessions_by_type: dict[str, int] = field(default_factory=dict)
    sessions_by_week: dict[str, int] = field(default_factory=dict)
    sessions_by_month: dict[str, int] = field(default_factory=dict)
    records: list[dict] = field(default_factory=list)
    data_completeness_note: str = ""  # 数据完整性说明，由LLM判断


@dataclass
class HealthEvidence:
    period: str = ""
    weight: WeightMetrics = field(default_factory=WeightMetrics)
    bmi: BMISeries = field(default_factory=BMISeries)
    exercise: ExerciseMetrics = field(default_factory=ExerciseMetrics)
    data_source_note: str = ""  # 数据来源说明


# ============================================================================
# 健康数据引擎
# ============================================================================

class HealthEngine:
    def __init__(self, height_m: float = 1.75):
        self.height_m = height_m
        self.weights: list[WeightRecord] = []
        self.exercises: list[dict] = []

    def load_weight_csv(self, csv_path: str) -> "HealthEngine":
        rows = read_csv(csv_path)
        self.weights = [WeightRecord.from_row(r) for r in rows if r.get("value")]
        # 优先按 ctime 排序，如果 ctime 为空则按 id 排序（id 通常代表录入顺序）
        self.weights.sort(key=lambda w: (w.ctime or datetime(1970, 1, 1), w.id))
        return self

    def load_exercise_csv(self, csv_path: str) -> "HealthEngine":
        self.exercises = read_csv(csv_path)
        return self

    def filter_period(self, start: datetime, end: datetime) -> tuple[list[WeightRecord], list[dict]]:
        # 体重记录：如果 ctime 为空，不过滤（保留所有记录），因为API可能不返回时间戳
        w = [r for r in self.weights if r.ctime is None or (start <= r.ctime <= end)]
        e = [r for r in self.exercises if parse_htime(r.get("ctime", "")) and start <= parse_htime(r.get("ctime", "")) <= end]
        return w, e

    def analyze(self, start: datetime, end: datetime, label: str = "") -> HealthEvidence:
        weights, exercises = self.filter_period(start, end)
        ev = HealthEvidence(period=label or f"{start.date()} ~ {end.date()}")

        if weights:
            ev.weight = self._calc_weight_metrics(weights, start, end)
            ev.bmi = self._calc_bmi_series(ev.weight)

        if exercises:
            ev.exercise = self._calc_exercise_metrics(exercises, start, end)

        # 数据来源完整性说明（只陈述事实，不做推断）
        notes = []
        if not weights:
            notes.append("体重记录：该时段无记录")
        else:
            notes.append(f"体重记录：{ev.weight.records_count} 条，覆盖 {ev.weight.recording_rate:.1f}% 天数")
        if not exercises:
            notes.append("运动记录：该时段无记录（注意：用户可能通过其他方式运动但未录入系统）")
        else:
            notes.append(f"运动记录：{ev.exercise.total_sessions} 条")
        ev.data_source_note = "；".join(notes)

        return ev

    def _calc_weight_metrics(self, weights: list[WeightRecord], start: datetime, end: datetime) -> WeightMetrics:
        wm = WeightMetrics()
        values = [w.value for w in weights]
        wm.start_weight = values[0]
        wm.end_weight = values[-1]
        wm.min_weight = min(values)
        wm.max_weight = max(values)
        wm.avg_weight = sum(values) / len(values)
        wm.records_count = len(weights)

        values_sorted = sorted(values)
        wm.median_weight = values_sorted[len(values_sorted) // 2]
        if len(values) > 1:
            wm.std_weight = math.sqrt(sum((v - wm.avg_weight) ** 2 for v in values) / len(values))

        wm.change_kg = wm.end_weight - wm.start_weight
        if wm.start_weight > 0:
            wm.change_pct = wm.change_kg / wm.start_weight * 100

        if weights[0].ctime and weights[-1].ctime:
            wm.days_span = (weights[-1].ctime - weights[0].ctime).days
        else:
            # ctime 缺失时，用记录数估算天数（假设每天一条）
            wm.days_span = wm.records_count
        weeks = max(1, wm.days_span / 7)
        months = max(1, wm.days_span / 30)
        wm.weekly_change = wm.change_kg / weeks
        wm.monthly_change = wm.change_kg / months

        total_days = max(1, (end - start).days + 1)
        wm.recording_rate = wm.records_count / total_days * 100

        # 日记录
        wm.daily_records = [
            WeightPoint(id=w.id, value=w.value, date=w.ctime.strftime("%Y-%m-%d") if w.ctime else None, note=w.note)
            for w in weights
        ]

        # 月均值（仅当 ctime 存在时计算）
        monthly: dict[str, list[float]] = defaultdict(list)
        for w in weights:
            if w.ctime:
                key = w.ctime.strftime("%Y-%m")
                monthly[key].append(w.value)
        wm.monthly_avg = {k: sum(v)/len(v) for k, v in sorted(monthly.items())}
        if not wm.monthly_avg:
            wm.monthly_avg = {"unknown": wm.avg_weight}

        # 平台期：连续14条记录变化 < 0.3kg（ctime 缺失时用索引代替日期）
        if len(weights) >= 14:
            for i in range(len(weights) - 14):
                window = weights[i:i+15]
                change = abs(window[-1].value - window[0].value)
                if change < 0.3:
                    s = window[0].ctime.strftime("%Y-%m-%d") if window[0].ctime else f"record-{window[0].id}"
                    e = window[-1].ctime.strftime("%Y-%m-%d") if window[-1].ctime else f"record-{window[-1].id}"
                    wm.plateau_periods.append((s, e, change))

        return wm

    def _calc_bmi_series(self, wm: WeightMetrics) -> BMISeries:
        bmi = BMISeries(height_m=self.height_m)
        h2 = self.height_m ** 2
        bmi.bmi_start = wm.start_weight / h2
        bmi.bmi_end = wm.end_weight / h2
        bmi.bmi_min = wm.min_weight / h2
        bmi.bmi_max = wm.max_weight / h2
        bmi.bmi_avg = wm.avg_weight / h2
        bmi.target_weight_low = bmi.target_bmi_low * h2
        bmi.target_weight_high = bmi.target_bmi_high * h2
        return bmi

    def _calc_exercise_metrics(self, exercises: list[dict], start: datetime, end: datetime) -> ExerciseMetrics:
        em = ExerciseMetrics()
        em.total_sessions = len(exercises)

        for e in exercises:
            val = float(e.get("value", 0) or 0)
            unit = e.get("unit", "min")
            if unit in ("min", "分钟"):
                em.total_duration_min += val
            elif unit in ("hour", "h", "小时"):
                em.total_duration_min += val * 60

            name = e.get("name", "unknown")
            em.sessions_by_type[name] = em.sessions_by_type.get(name, 0) + 1

            dt = parse_htime(e.get("ctime", ""))
            if dt:
                em.sessions_by_week[dt.strftime("%Y-W%W")] = em.sessions_by_week.get(dt.strftime("%Y-W%W"), 0) + 1
                em.sessions_by_month[dt.strftime("%Y-%m")] = em.sessions_by_month.get(dt.strftime("%Y-%m"), 0) + 1

        em.records = exercises
        return em


def main():
    parser = argparse.ArgumentParser(description="健康数据引擎 —— 输出证据供 LLM 解读")
    parser.add_argument("--weight-csv", required=True)
    parser.add_argument("--exercise-csv", default=None)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--height", type=float, default=1.75)
    parser.add_argument("--output", "-o", default="health_evidence.json")
    args = parser.parse_args()

    engine = HealthEngine(height_m=args.height)
    engine.load_weight_csv(args.weight_csv)
    if args.exercise_csv:
        engine.load_exercise_csv(args.exercise_csv)

    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")

    evidence = engine.analyze(start_dt, end_dt)

    def serialize(obj):
        if isinstance(obj, list):
            return [serialize(i) for i in obj]
        if hasattr(obj, "__dataclass_fields__"):
            return {k: serialize(v) for k, v in asdict(obj).items()}
        return obj

    write_json(args.output, serialize(evidence))
    print(f"证据包已输出: {args.output}")
    wt = evidence.weight
    if wt.records_count > 0:
        print(f"  体重记录: {wt.records_count} 条, 变化 {wt.change_kg:+.1f}kg")
    print(f"  运动记录: {evidence.exercise.total_sessions} 条")


if __name__ == "__main__":
    main()
