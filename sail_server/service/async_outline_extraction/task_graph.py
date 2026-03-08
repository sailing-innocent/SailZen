# -*- coding: utf-8 -*-
# @file task_graph.py
# @brief Task graph implementation for async outline extraction
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""任务图实现

提供任务依赖管理、状态流转和自动触发机制
"""

import asyncio
from typing import Dict, List, Set, Optional, Any, Callable
from collections import deque
import logging

from .types import Task, TaskStatus, TaskLevel
from .exceptions import CircularDependencyError, TaskNotFoundError

logger = logging.getLogger(__name__)


class TaskGraph:
    """任务图管理器

    管理任务间的依赖关系，支持：
    - 循环依赖检测
    - 任务状态流转
    - 下游任务自动触发
    - 拓扑排序执行
    """

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._downstream: Dict[str, Set[str]] = {}  # 下游任务映射
        self._upstream: Dict[str, Set[str]] = {}  # 上游任务映射
        self._status_events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()
        self._status_callbacks: List[Callable[[Task], None]] = []

    def add_task(self, task: Task) -> None:
        """添加任务到图中"""
        self._tasks[task.id] = task
        self._downstream[task.id] = set()
        self._upstream[task.id] = set()
        self._status_events[task.id] = asyncio.Event()

        # 建立依赖关系
        for dep_id in task.dependencies:
            self._upstream[task.id].add(dep_id)
            if dep_id in self._downstream:
                self._downstream[dep_id].add(task.id)

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self._tasks.values())

    def get_tasks_by_level(self, level: TaskLevel) -> List[Task]:
        """获取指定层级的所有任务"""
        return [t for t in self._tasks.values() if t.level == level]

    def get_ready_tasks(self) -> List[Task]:
        """获取所有依赖已满足的可执行任务"""
        ready = []
        for task in self._tasks.values():
            if task.status == TaskStatus.PENDING:
                # 检查所有依赖是否完成
                deps_completed = all(
                    self._tasks.get(dep_id)
                    and self._tasks[dep_id].status == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                )
                if deps_completed:
                    ready.append(task)
        return ready

    def detect_cycles(self) -> Optional[List[str]]:
        """检测循环依赖

        使用 DFS 算法检测有向图中的环

        Returns:
            如果存在环，返回环中的节点ID列表；否则返回 None
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {task_id: WHITE for task_id in self._tasks}
        parent = {}

        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            color[node] = GRAY
            path.append(node)

            for neighbor in self._downstream.get(node, set()):
                if color[neighbor] == GRAY:
                    # 发现回边，存在环
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:]
                elif color[neighbor] == WHITE:
                    result = dfs(neighbor, path)
                    if result:
                        return result

            path.pop()
            color[node] = BLACK
            return None

        for task_id in self._tasks:
            if color[task_id] == WHITE:
                cycle = dfs(task_id, [])
                if cycle:
                    return cycle

        return None

    async def update_task_status(
        self,
        task_id: str,
        new_status: TaskStatus,
        result: Any = None,
        error: Optional[str] = None,
    ) -> None:
        """更新任务状态并触发下游任务检查"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(task_id)

            old_status = task.status
            task.status = new_status

            # 更新时间戳
            if new_status == TaskStatus.RUNNING:
                from datetime import datetime

                task.started_at = datetime.now()
            elif new_status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ):
                from datetime import datetime

                task.completed_at = datetime.now()

            # 更新结果和错误
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error

            # 触发状态事件
            if task_id in self._status_events:
                self._status_events[task_id].set()

            logger.debug(
                f"Task {task_id} status changed: {old_status.value} -> {new_status.value}"
            )

            # 通知回调
            for callback in self._status_callbacks:
                try:
                    callback(task)
                except Exception as e:
                    logger.error(f"Status callback error: {e}")

        # 如果任务完成，检查并触发下游任务
        if new_status == TaskStatus.COMPLETED:
            await self._trigger_downstream_tasks(task_id)

    async def _trigger_downstream_tasks(self, completed_task_id: str) -> None:
        """触发下游任务检查"""
        downstream_ids = self._downstream.get(completed_task_id, set())

        for task_id in downstream_ids:
            task = self._tasks.get(task_id)
            if not task or task.status != TaskStatus.PENDING:
                continue

            # 检查所有依赖是否完成
            all_deps_completed = all(
                self._tasks.get(dep_id)
                and self._tasks[dep_id].status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )

            if all_deps_completed:
                async with self._lock:
                    if task.status == TaskStatus.PENDING:  # 双重检查
                        task.status = TaskStatus.READY
                        logger.debug(f"Task {task_id} is now READY")

    async def wait_for_task(
        self, task_id: str, timeout: Optional[float] = None
    ) -> Task:
        """等待任务完成"""
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError(task_id)

        if task.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ):
            return task

        event = self._status_events.get(task_id)
        if event:
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass

        return task

    def add_status_callback(self, callback: Callable[[Task], None]) -> None:
        """添加状态变更回调"""
        self._status_callbacks.append(callback)

    def remove_status_callback(self, callback: Callable[[Task], None]) -> None:
        """移除状态变更回调"""
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)

    def topological_sort(self) -> List[Task]:
        """拓扑排序（Kahn算法）

        返回按依赖顺序排序的任务列表
        """
        # 计算入度
        in_degree = {task_id: 0 for task_id in self._tasks}
        for task_id, upstream in self._upstream.items():
            in_degree[task_id] = len(upstream)

        # 初始化队列（入度为0的节点）
        queue = deque([task_id for task_id, degree in in_degree.items() if degree == 0])

        sorted_tasks = []

        while queue:
            task_id = queue.popleft()
            sorted_tasks.append(self._tasks[task_id])

            # 减少下游节点的入度
            for downstream_id in self._downstream.get(task_id, set()):
                in_degree[downstream_id] -= 1
                if in_degree[downstream_id] == 0:
                    queue.append(downstream_id)

        if len(sorted_tasks) != len(self._tasks):
            raise CircularDependencyError([])

        return sorted_tasks

    def get_statistics(self) -> Dict[str, int]:
        """获取任务统计信息"""
        stats = {status.value: 0 for status in TaskStatus}
        for task in self._tasks.values():
            stats[task.status.value] += 1
        return stats

    def get_progress_percentage(self) -> float:
        """获取总体进度百分比"""
        if not self._tasks:
            return 100.0

        completed = sum(
            1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED
        )
        return (completed / len(self._tasks)) * 100
