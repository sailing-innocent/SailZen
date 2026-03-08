# -*- coding: utf-8 -*-
# @file progress_tracker.py
# @brief Progress tracking for async outline extraction
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""进度追踪器

提供实时进度追踪和 ETA 计算
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

from .types import TaskStatus, TaskLevel, ExtractionProgress, Task
from .task_graph import TaskGraph

logger = logging.getLogger(__name__)


@dataclass
class LevelProgress:
    """单个层级的进度"""

    total: int = 0
    completed: int = 0
    running: int = 0
    failed: int = 0

    @property
    def percentage(self) -> float:
        if self.total == 0:
            return 100.0
        return (self.completed / self.total) * 100


class ProgressTracker:
    """进度追踪器"""

    # 权重配置
    LEVEL_WEIGHTS = {
        TaskLevel.CHUNK: 0.4,
        TaskLevel.SEGMENT: 0.3,
        TaskLevel.CHAPTER: 0.3,
    }

    def __init__(self, task_graph: TaskGraph, task_id: str):
        self.task_graph = task_graph
        self.task_id = task_id
        self.start_time = datetime.now()

        # 历史记录（用于 ETA 计算）
        self._completion_times: deque = deque(maxlen=100)  # 最近 100 个任务的完成时间
        self._progress_history: deque = deque(maxlen=50)  # 进度历史

        # 回调函数
        self._callbacks: List[Callable[[ExtractionProgress], None]] = []

        # 注册状态变更回调
        self.task_graph.add_status_callback(self._on_task_status_change)

        logger.info(f"ProgressTracker initialized for task {task_id}")

    def _on_task_status_change(self, task: Task) -> None:
        """任务状态变更回调"""
        if task.status == TaskStatus.COMPLETED:
            duration = task.duration_ms
            if duration:
                self._completion_times.append(duration)

        # 计算并记录进度
        progress = self.calculate_progress()
        self._progress_history.append(
            {
                "timestamp": datetime.now(),
                "progress": progress.overall_progress,
            }
        )

        # 通知回调
        for callback in self._callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    def calculate_progress(self) -> ExtractionProgress:
        """计算当前进度"""
        tasks = self.task_graph.get_all_tasks()

        # 按层级统计
        level_progress: Dict[str, Dict[str, Any]] = {}
        level_stats: Dict[TaskLevel, LevelProgress] = {}

        for level in TaskLevel:
            level_tasks = [t for t in tasks if t.level == level]
            stats = LevelProgress(total=len(level_tasks))

            for task in level_tasks:
                if task.status == TaskStatus.COMPLETED:
                    stats.completed += 1
                elif task.status == TaskStatus.RUNNING:
                    stats.running += 1
                elif task.status == TaskStatus.FAILED:
                    stats.failed += 1

            level_stats[level] = stats
            level_progress[level.name.lower()] = {
                "total": stats.total,
                "completed": stats.completed,
                "running": stats.running,
                "failed": stats.failed,
                "percentage": round(stats.percentage, 1),
            }

        # 计算总体进度（加权）
        overall = 0.0
        for level, stats in level_stats.items():
            weight = self.LEVEL_WEIGHTS.get(level, 0.33)
            overall += stats.percentage * weight

        # 计算 ETA
        eta = self._calculate_eta(tasks, overall)

        # 性能指标
        performance = self._calculate_performance_metrics(tasks)

        return ExtractionProgress(
            task_id=self.task_id,
            overall_progress=round(overall, 1),
            level_progress=level_progress,
            estimated_time_remaining=eta,
            current_status=self._get_current_status(tasks),
            performance_metrics=performance,
        )

    def _calculate_eta(
        self, tasks: List[Task], current_progress: float
    ) -> Optional[int]:
        """计算预估剩余时间（秒）"""
        if current_progress >= 100:
            return 0

        if current_progress <= 0:
            return None

        # 方法1：基于历史平均速度
        if len(self._completion_times) >= 5:
            avg_time_per_task = sum(self._completion_times) / len(
                self._completion_times
            )

            # 估算剩余任务数
            total_tasks = len(tasks)
            completed_tasks = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
            remaining_tasks = total_tasks - completed_tasks

            eta_ms = avg_time_per_task * remaining_tasks
            return int(eta_ms / 1000)

        # 方法2：基于进度速度
        if len(self._progress_history) >= 2:
            # 计算最近一段时间的进度速度
            recent = list(self._progress_history)[-10:]
            if len(recent) >= 2:
                time_span = (
                    recent[-1]["timestamp"] - recent[0]["timestamp"]
                ).total_seconds()
                progress_span = recent[-1]["progress"] - recent[0]["progress"]

                if time_span > 0 and progress_span > 0:
                    progress_per_second = progress_span / time_span
                    remaining_progress = 100 - current_progress
                    eta = remaining_progress / progress_per_second
                    return int(eta)

        return None

    def _calculate_performance_metrics(self, tasks: List[Task]) -> Dict[str, Any]:
        """计算性能指标"""
        completed_tasks = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        failed_tasks = [t for t in tasks if t.status == TaskStatus.FAILED]

        # 计算平均执行时间
        durations = [t.duration_ms for t in completed_tasks if t.duration_ms]
        avg_duration = sum(durations) / len(durations) if durations else 0

        # p99 延迟
        p99_duration = 0
        if durations:
            sorted_durations = sorted(durations)
            p99_index = int(len(sorted_durations) * 0.99)
            p99_duration = sorted_durations[min(p99_index, len(sorted_durations) - 1)]

        # 重试统计
        total_retries = sum(t.retry_count for t in tasks)

        return {
            "total_tasks": len(tasks),
            "completed_tasks": len(completed_tasks),
            "failed_tasks": len(failed_tasks),
            "avg_task_duration_ms": round(avg_duration, 1),
            "p99_task_duration_ms": round(p99_duration, 1),
            "total_retries": total_retries,
            "elapsed_seconds": int((datetime.now() - self.start_time).total_seconds()),
        }

    def _get_current_status(self, tasks: List[Task]) -> str:
        """获取当前状态"""
        if not tasks:
            return "completed"

        has_running = any(t.status == TaskStatus.RUNNING for t in tasks)
        all_completed = all(t.status == TaskStatus.COMPLETED for t in tasks)
        has_failed = any(t.status == TaskStatus.FAILED for t in tasks)

        if all_completed:
            return "completed"
        elif has_running:
            return "running"
        elif has_failed:
            return "failed"
        else:
            return "pending"

    def add_callback(self, callback: Callable[[ExtractionProgress], None]) -> None:
        """添加进度回调"""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[ExtractionProgress], None]) -> None:
        """移除进度回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def get_execution_report(self) -> Dict[str, Any]:
        """生成执行报告"""
        progress = self.calculate_progress()
        tasks = self.task_graph.get_all_tasks()

        # 按层级统计
        level_stats = {}
        for level in TaskLevel:
            level_tasks = [t for t in tasks if t.level == level]
            level_stats[level.name.lower()] = {
                "total": len(level_tasks),
                "completed": sum(
                    1 for t in level_tasks if t.status == TaskStatus.COMPLETED
                ),
                "failed": sum(1 for t in level_tasks if t.status == TaskStatus.FAILED),
            }

        return {
            "task_id": self.task_id,
            "status": progress.current_status,
            "progress": progress.overall_progress,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat()
            if progress.current_status == "completed"
            else None,
            "elapsed_seconds": progress.performance_metrics.get("elapsed_seconds", 0),
            "level_stats": level_stats,
            "performance": progress.performance_metrics,
        }

    def cleanup(self) -> None:
        """清理资源"""
        self.task_graph.remove_status_callback(self._on_task_status_change)
        self._callbacks.clear()
