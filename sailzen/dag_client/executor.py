# -*- coding: utf-8 -*-
# @file executor.py
# @brief DAG 节点执行器
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""SailZen DAG Client 节点执行引擎。

负责:
  1. 从调度器获取就绪节点
  2. 通过 NodeRegistry 解析并执行节点
  3. 处理执行结果（成功/失败/动态分支）
  4. 回调调度器更新状态
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sail.opencode.client import OpencodeAsyncClient

from sailzen.dag_client.nodes.base import NodeContext, NodeResult
from sailzen.dag_client.nodes.registry import NodeRegistry
from sailzen.dag_client.models import NodeStatus, make_node_run, _now_iso
from sailzen.dag_client.store import DAGStore

logger = logging.getLogger(__name__)


class DAGExecutor:
    """DAG 节点执行器。"""

    def __init__(
        self,
        db_compat,
        scheduler,
        event_bus,
        node_registry: NodeRegistry,
        store: DAGStore,
        opencode_client: Optional[OpencodeAsyncClient] = None,
    ):
        self.db = db_compat
        self.scheduler = scheduler
        self.event_bus = event_bus
        self.registry = node_registry
        self.store = store
        self.opencode_client = opencode_client
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """启动执行循环。"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("DAGExecutor started")

    async def stop(self) -> None:
        """停止执行循环。"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("DAGExecutor stopped")

    async def _loop(self) -> None:
        """主执行循环。"""
        while self._running:
            try:
                if self.scheduler.is_paused:
                    await asyncio.sleep(1)
                    continue

                # 获取就绪节点
                queued = await self.scheduler.get_queued_nodes(limit=5)
                if not queued:
                    await asyncio.sleep(1)
                    continue

                for node in queued:
                    if not self._running:
                        break
                    await self._execute_node(node)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Executor loop error")
                await asyncio.sleep(1)

    async def _execute_node(self, node: dict) -> None:
        """执行单个节点。"""
        node_db_id = node["id"]
        node_type = node["node_type"]

        # 标记为运行中
        claimed = await self.db.update_node_status(
            node_db_id,
            NodeStatus.RUNNING.value,
            expected_statuses=[NodeStatus.QUEUED.value, NodeStatus.ASSIGNED.value],
            started_at=_now_iso(),
        )
        if not claimed:
            return

        # 创建 NodeRun 记录
        attempt = await self.db.next_node_run_attempt(node_db_id)
        node_run = make_node_run(node_db_id, attempt=attempt)
        await self.db.create_node_run(node_run)

        # 获取上游结果
        upstream_results = await self._get_upstream_results(node["run_id"], node["node_id"])

        # 构建上下文
        run = await self.db.get_run(node["run_id"])
        global_params = run.get("params", {}) if run else {}

        ctx = NodeContext(
            run_id=node["run_id"],
            node_id=node["node_id"],
            node_type=node_type,
            params=node.get("params", {}),
            upstream_results=upstream_results,
            global_params=global_params,
            store=self.store,
            opencode_client=self.opencode_client,
            working_dir=self.store.run_dir(node["run_id"]),
        )

        # 执行
        executor = None
        try:
            executor = self.registry.create(node_type)
            validation_error = executor.validate_params(ctx.params)
            if validation_error:
                result = NodeResult.fail(f"Param validation: {validation_error}")
            else:
                await executor.pre_execute(ctx)
                result = await executor.execute(ctx)
                await executor.post_execute(ctx, result)
        except Exception as exc:
            logger.exception("Node execution error: %s", node_db_id)
            result = NodeResult.fail(str(exc))

        # 处理结果
        success = result.success if result else False
        await self.db.complete_node_run(
            node_run["id"], success,
            result=result.data if result else None,
            error=result.error if result else None,
        )

        # 保存产物
        if result and result.artifacts:
            pass  # store 已在节点内部处理

        # 处理动态分支
        if result and result.next_nodes:
            await self._handle_dynamic_nodes(node, result.next_nodes)

        # 回调调度器
        await self.scheduler.on_node_completed(
            node_db_id, success,
            result=result.data if result else None,
            error=result.error if result else None,
        )

        # 事件
        await self.event_bus.emit({
            "type": "node.completed" if success else "node.failed",
            "entity_type": "node",
            "entity_id": node_db_id,
            "run_id": node["run_id"],
            "data": {
                "node_id": node["node_id"],
                "node_type": node_type,
                "success": success,
                "output": result.output if result else None,
            },
        })

    async def _get_upstream_results(self, run_id: str, node_id: str) -> Dict[str, Any]:
        """获取节点的所有上游节点的执行结果。"""
        edges = await self.db.get_edges(run_id)
        upstream_node_ids = [
            e["from_node"] for e in edges
            if e["to_node"] == node_id and e["edge_type"] == "dependency"
        ]
        results = {}
        for uid in upstream_node_ids:
            node = await self.db.get_node_by_template_id(run_id, uid)
            if node:
                results[uid] = node.get("result")
        return results

    async def _handle_dynamic_nodes(self, parent_node: dict, next_node_configs: List[dict]) -> None:
        """处理动态添加的节点。"""
        run_id = parent_node["run_id"]
        from sailzen.dag_client.models import make_dag_node, make_dag_edge
        for cfg in next_node_configs:
            node = make_dag_node(
                run_id=run_id,
                node_id=cfg["id"],
                node_type=cfg.get("type", "skill"),
                name=cfg.get("name", cfg["id"]),
                priority=cfg.get("priority", 100),
                params=cfg.get("params", {}),
            )
            await self.db.create_node(node)
            edge = make_dag_edge(
                run_id=run_id,
                from_node=parent_node["node_id"],
                to_node=cfg["id"],
                edge_type="trigger",
            )
            await self.db.create_edge(edge)
            logger.info("Dynamic node added: %s -> %s", parent_node["node_id"], cfg["id"])

    async def execute_node_sync(self, node_db_id: str) -> NodeResult:
        """同步执行单个节点（用于手动触发）。"""
        node = await self.db.get_node(node_db_id)
        if not node:
            raise ValueError(f"Node not found: {node_db_id}")
        await self._execute_node(node)
        # 重新获取最新状态
        node = await self.db.get_node(node_db_id)
        return NodeResult(
            success=node.get("status") == NodeStatus.SUCCESS.value,
            data=node.get("result"),
            error=node.get("error"),
        )
