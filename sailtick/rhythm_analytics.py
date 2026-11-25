# -*- coding: utf-8 -*-
# @file rhythm_analytics.py
# @brief SailTick 夜间节奏与项目倒排深度分析引擎（替代人工调权重与精力曲线）
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""RhythmAnalyticsEngine — 夜间确定性节奏学习与项目风险评估。

设计理念：
- 不再要求人手动维护 24 段精力曲线或 5 维评分权重；
- 每晚从近 21 天真实的时间块执行结果（DONE vs SKIPPED）和活跃重要项目（venture）进度中，
  自动学习：
  1. 哪些时段完成率最高（golden_windows）vs 最常被跳过/打断（low_adherence_windows）；
  2. 近期排程是否过载（overload_signal），动态提示慢脑留白减量；
  3. 每个重要项目的倒排风险（on_track / attention / at_risk / stalled / overdue）与温和推进建议；
  4. 提炼出最多 1-2 个高价值发问建议，供白天 Tick 渐进式理解用户。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

_PASSIVE_BLOCK_TYPES = {"sleep", "commute", "meal", "rest", "buffer", "occupied", "micro_rest"}

_SLOT_LABELS = {
    "morning": "上午(06-12)",
    "afternoon": "下午(12-18)",
    "evening": "晚间(18-22)",
    "late_night": "深夜(22-06)",
}


def _hour_bucket(hour: int) -> str:
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "late_night"


class RhythmAnalyticsEngine:
    """夜间节奏与项目倒排确定性分析引擎。"""

    def __init__(self, clock: Callable[[], datetime] = datetime.now):
        self._clock = clock

    def analyze(self, deep_pkg: Dict[str, Any]) -> Dict[str, Any]:
        rhythm_range = deep_pkg.get("rhythm_history") or {}
        days = rhythm_range.get("days") if isinstance(rhythm_range, dict) else []
        days = days if isinstance(days, list) else []
        projects = deep_pkg.get("rhythm_projects") or []
        projects = projects if isinstance(projects, list) else []
        affairs = deep_pkg.get("rhythm_affairs") or []
        affairs = affairs if isinstance(affairs, list) else []

        bucket_stats: Dict[str, Dict[str, int]] = {
            k: {"done": 0, "skipped": 0, "planned": 0}
            for k in ("morning", "afternoon", "evening", "late_night")
        }
        total_done = 0
        total_skipped = 0
        total_planned_active = 0
        days_with_blocks = 0
        daily_block_counts: List[int] = []

        for day_item in days:
            if not isinstance(day_item, dict):
                continue
            blocks = day_item.get("blocks") or []
            active_in_day = 0
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                btype = str(b.get("block_type") or "")
                if btype in _PASSIVE_BLOCK_TYPES:
                    continue
                status = str(b.get("status") or "PLANNED")
                start_raw = str(b.get("start_time") or "")
                hour = 10
                if len(start_raw) >= 13:
                    try:
                        hour = int(start_raw[11:13])
                    except ValueError:
                        hour = 10
                bucket = _hour_bucket(hour)
                active_in_day += 1
                if status == "DONE":
                    total_done += 1
                    bucket_stats[bucket]["done"] += 1
                elif status == "SKIPPED":
                    total_skipped += 1
                    bucket_stats[bucket]["skipped"] += 1
                else:
                    total_planned_active += 1
                    bucket_stats[bucket]["planned"] += 1
            if active_in_day > 0:
                days_with_blocks += 1
                daily_block_counts.append(active_in_day)

        evaluated = total_done + total_skipped
        adherence_rate = round(total_done / evaluated, 3) if evaluated > 0 else None
        avg_blocks_per_day = (
            round(sum(daily_block_counts) / len(daily_block_counts), 1)
            if daily_block_counts
            else 0.0
        )

        # 识别黄金高效时段 & 高跳过时段
        slot_rates: List[Dict[str, Any]] = []
        for k, st in bucket_stats.items():
            denom = st["done"] + st["skipped"]
            if denom >= 2:
                slot_rates.append(
                    {
                        "slot": k,
                        "label": _SLOT_LABELS[k],
                        "done": st["done"],
                        "skipped": st["skipped"],
                        "rate": round(st["done"] / denom, 3),
                    }
                )
        slot_rates.sort(key=lambda x: x["rate"], reverse=True)
        golden_windows = [s["label"] for s in slot_rates if s["rate"] >= 0.65][:2]
        low_adherence_windows = [s["label"] for s in slot_rates if s["rate"] < 0.45][:2]

        overload_signal = bool(
            (adherence_rate is not None and evaluated >= 4 and adherence_rate < 0.55)
            or avg_blocks_per_day > 6.0
        )

        # 评估活跃项目（venture）倒排风险
        project_risks: List[Dict[str, Any]] = []
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            title = str(proj.get("title") or "未命名项目")
            days_left = proj.get("days_left")
            recent_14d_h = float(proj.get("recent_14d_hours") or 0.0)
            completion = float(proj.get("completion_ratio") or 0.0)
            milestones = proj.get("milestones") or []
            pending_ms = [
                m.get("title")
                for m in milestones
                if isinstance(m, dict) and m.get("state") not in ("DONE", "CANCELED")
            ]

            risk = "on_track"
            hint = "节奏平稳，保持每周小步推进即可"
            if days_left is not None and days_left < 0 and completion < 1.0:
                risk = "overdue"
                hint = f"已超过原定目标日 {abs(int(days_left))} 天，建议与用户轻量确认新目标日或精简范围"
            elif days_left is not None and days_left <= 14 and completion < 0.8:
                if recent_14d_h < 1.0:
                    risk = "at_risk"
                    hint = f"距目标仅剩 {days_left} 天且近 14 天几乎无推进，建议明日优先排入 1 个 45 分钟核心起步块"
                else:
                    risk = "attention"
                    hint = f"距目标剩 {days_left} 天，聚焦推进下一个里程碑"
            elif recent_14d_h < 0.5 and completion < 1.0:
                risk = "stalled"
                hint = "近两周暂无实际投入，建议拆成 30 分钟极简起步任务或确认是否暂缓"

            project_risks.append(
                {
                    "affair_id": proj.get("affair_id"),
                    "title": title,
                    "target_date": proj.get("target_date"),
                    "days_left": days_left,
                    "completion_ratio": completion,
                    "recent_14d_hours": recent_14d_h,
                    "next_milestone": pending_ms[0] if pending_ms else None,
                    "risk": risk,
                    "action_hint": hint,
                }
            )

        # 统计逾期一次性任务
        now = self._clock()
        overdue_tasks = 0
        for a in affairs:
            if not isinstance(a, dict):
                continue
            if a.get("kind") == "venture" or a.get("state") in ("DONE", "CANCELED", "ARCHIVED"):
                continue
            ddl = a.get("urgency_ddl")
            if ddl:
                try:
                    dt = datetime.fromisoformat(str(ddl).replace("Z", "+00:00"))
                    if dt.tzinfo is not None:
                        dt = dt.astimezone().replace(tzinfo=None)
                    if dt < now:
                        overdue_tasks += 1
                except ValueError:
                    pass

        insights: List[str] = []
        if adherence_rate is not None:
            insights.append(
                f"近 21 天日程遵循率 {int(adherence_rate * 100)}%（完成 {total_done} 块 / 跳过 {total_skipped} 块，日均 {avg_blocks_per_day} 块）"
            )
        if golden_windows:
            insights.append(f"高效黄金时段：{'、'.join(golden_windows)}，适合放核心深度任务")
        if low_adherence_windows:
            insights.append(f"高跳过/易被打断时段：{'、'.join(low_adherence_windows)}，建议留白或放轻量事项")
        if overload_signal:
            insights.append("近期排程偏满导致跳过偏多，明日应主动减量，每天核心聚焦不超过 2–3 件事")

        high_risk_projects = [p for p in project_risks if p["risk"] in ("overdue", "at_risk", "stalled")]
        for p in high_risk_projects[:2]:
            insights.append(f"项目「{p['title']}」[{p['risk']}]：{p['action_hint']}")

        suggested_questions: List[Dict[str, str]] = []
        if high_risk_projects:
            top = high_risk_projects[0]
            suggested_questions.append(
                {
                    "topic": f"project_check_{top.get('affair_id') or 'main'}",
                    "question": f"「{top['title']}」最近推进有点卡住，这周想继续推、拆小一点，还是先调整下目标时间？",
                    "why": top["action_hint"],
                }
            )
        elif not projects:
            suggested_questions.append(
                {
                    "topic": "rhythm_key_projects",
                    "question": "最近 1-3 个月里，你最想推进的 1-2 个重要项目或目标是什么？大概期望什么时候完成？",
                    "why": "了解核心主线后，SailTick 可以帮你自动倒排并融进每天轻松可执行的日程里",
                }
            )

        return {
            "snapshot_date": now.strftime("%Y-%m-%d"),
            "days_analyzed": days_with_blocks,
            "total_done_blocks": total_done,
            "total_skipped_blocks": total_skipped,
            "total_pending_blocks": total_planned_active,
            "adherence_rate": adherence_rate,
            "avg_blocks_per_day": avg_blocks_per_day,
            "golden_windows": golden_windows,
            "low_adherence_windows": low_adherence_windows,
            "overload_signal": overload_signal,
            "overdue_tasks_count": overdue_tasks,
            "active_projects_count": len(project_risks),
            "project_risks": project_risks,
            "insights": insights,
            "suggested_questions": suggested_questions,
        }
