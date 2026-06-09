# -*- coding: utf-8 -*-
# @file scheduler.py
# @brief 通用 DAG 调度引擎
# @author sailing-innocent
# @date 2025-06-02
# @version 3.0
# ---------------------------------
"""SailZen DAG Client 通用 DAG 调度引擎。

核心职责:
  1. 从 DAGDefinition 模板实例化 DAGRun + DAGNode + DAGEdge
  2. 拓扑排序 + 依赖驱动调度
  3. 节点完成回调 → 解锁后继
  4. 支持动态分支（节点执行结果可添加新节点）

与旧版区别:
  - 不再硬编码 GlobalBatch/NeteaseBatch 业务逻辑
  - DAG 结构完全由配置/模板驱动
  - 节点类型通过 NodeRegistry 动态解析
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set, Tuple

from sailzen.dag_client.models import (
    RunStatus, NodeStatus,
    make_dag_run, make_dag_node, make_dag_edge,
    make_event_log, _now_iso,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  DAG Builder
# ═══════════════════════════════════════════════════════════════════════


def build_dag_from_template(
    definition_id: str,
    template: dict,
    run_params: dict = None,
) -> Tuple[dict, List[dict], List[dict]]:
    """从模板构建 DAG 实例。

    Args:
        definition_id: DAG 定义 ID
        template: {"nodes": [...], "edges": [...]}
        run_params: 运行时参数

    Returns:
        (run_dict, nodes_list, edges_list)
    """
    run = make_dag_run(definition_id, params=run_params or {})
    run_id = run["id"]

    nodes: List[dict] = []
    edges: List[dict] = []

    template_nodes = template.get("nodes", [])
    template_edges = template.get("edges", [])

    # 构建节点
    for tn in template_nodes:
        node = make_dag_node(
            run_id=run_id,
            node_id=tn["id"],
            node_type=tn.get("type", "skill"),
            name=tn.get("name", tn["id"]),
            priority=tn.get("priority", 100),
            params=tn.get("params", {}),
            timeout=tn.get("timeout", 3600),
            max_retries=tn.get("retries", 3),
        )
        nodes.append(node)

    # 构建边
    for te in template_edges:
        edge = make_dag_edge(
            run_id=run_id,
            from_node=te["from"],
            to_node=te["to"],
            edge_type=te.get("type", "dependency"),
            condition=te.get("condition"),
        )
        edges.append(edge)

    # 如果没有显式边，根据 depends_on 构建
    if not edges:
        for tn in template_nodes:
            for dep in tn.get("depends_on", []):
                edge = make_dag_edge(
                    run_id=run_id,
                    from_node=dep,
                    to_node=tn["id"],
                )
                edges.append(edge)

    return run, nodes, edges


def get_ready_nodes(nodes: List[dict], edges: List[dict]) -> List[dict]:
    """获取依赖已全部 SUCCESS 的 PENDING 节点。

    支持 dependency 和 trigger 两种边类型：
      - dependency: 标准依赖，所有前驱必须 SUCCESS
      - trigger: 父节点完成后自动触发（用于动态分支）
    """
    terminal_statuses = {
        NodeStatus.SUCCESS.value,
        NodeStatus.SKIPPED.value,
        NodeStatus.CANCELLED.value,
    }
    completed_ids = {n["node_id"] for n in nodes if n["status"] in terminal_statuses}

    deps_map: Dict[str, Set[str]] = {}
    trigger_map: Dict[str, Set[str]] = {}
    for e in edges:
        if e["edge_type"] == "dependency":
            deps_map.setdefault(e["to_node"], set()).add(e["from_node"])
        elif e["edge_type"] == "trigger":
            trigger_map.setdefault(e["to_node"], set()).add(e["from_node"])

    ready = []
    for n in nodes:
        if n["status"] != NodeStatus.PENDING.value:
            continue
        deps = deps_map.get(n["node_id"], set())
        triggers = trigger_map.get(n["node_id"], set())
        # dependency 必须全部完成
        if deps and not all(d in completed_ids for d in deps):
            continue
        # trigger 边也必须全部完成（父节点触发）
        if triggers and not all(d in completed_ids for d in triggers):
            continue
        ready.append(n)
    return ready


def topological_sort(nodes: List[dict], edges: List[dict]) -> List[str]:
    """返回拓扑排序后的 node_id 列表。"""
    node_ids = {n["node_id"] for n in nodes}
    in_degree: Dict[str, int] = {n: 0 for n in node_ids}
    adj: Dict[str, List[str]] = {n: [] for n in node_ids}

    for e in edges:
        if e["edge_type"] == "dependency":
            adj[e["from_node"]].append(e["to_node"])
            in_degree[e["to_node"]] += 1

    queue = [n for n, d in in_degree.items() if d == 0]
    result = []
    while queue:
        n = queue.pop(0)
        result.append(n)
        for m in adj[n]:
            in_degree[m] -= 1
            if in_degree[m] == 0:
                queue.append(m)

    if len(result) != len(node_ids):
        raise ValueError("DAG contains cycles")
    return result


# ═══════════════════════════════════════════════════════════════════════
#  TaskScheduler
# ═══════════════════════════════════════════════════════════════════════

class DAGScheduler:
    """通用 DAG 调度器。"""

    def __init__(self, db_compat):
        self.db = db_compat
        self._paused = False

    async def create_run(
        self,
        definition_id: str,
        template: dict,
        name: str = "",
        params: dict = None,
    ) -> dict:
        """从模板创建一次 DAG 运行。"""
        run, nodes, edges = build_dag_from_template(definition_id, template, params)
        if name:
            run["name"] = name

        # 持久化
        await self.db.create_run(run)
        for n in nodes:
            await self.db.create_node(n)
        for e in edges:
            await self.db.create_edge(e)

        # 初始就绪节点入队
        ready = get_ready_nodes(nodes, edges)
        for n in ready:
            n["status"] = NodeStatus.QUEUED.value
            n["queued_at"] = _now_iso()
            await self.db.upsert_node(n)

        await self.db.update_run_status(run["id"], RunStatus.RUNNING.value, started_at=_now_iso())
        await self.db.log_event(make_event_log(
            "run.created", "run", run["id"],
            new_state={"nodes": len(nodes), "edges": len(edges), "ready": len(ready)},
        ))

        logger.info(
            "DAGRun %s created: %d nodes, %d edges, %d ready",
            run["id"], len(nodes), len(edges), len(ready),
        )
        return run

    async def on_node_completed(
        self,
        node_db_id: str,
        success: bool,
        result: dict = None,
        error: dict = None,
    ) -> None:
        """节点完成回调。"""
        node = await self.db.get_node(node_db_id)
        if not node:
            logger.error("Node not found: %s", node_db_id)
            return

        old_status = node["status"]
        run_id = node["run_id"]

        if success:
            updated = await self.db.update_node_status(
                node_db_id,
                NodeStatus.SUCCESS.value,
                expected_statuses=[NodeStatus.RUNNING.value, NodeStatus.ASSIGNED.value],
                result=result,
                completed_at=_now_iso(),
            )
            if not updated:
                latest = await self.db.get_node(node_db_id)
                if latest and latest.get("status") == NodeStatus.SUCCESS.value:
                    node = latest
                else:
                    return
            await self._unlock_dependents(run_id, node)
            await self._check_run_completion(run_id)
        else:
            if node["retry_count"] < node["max_retries"]:
                node["retry_count"] += 1
                updated = await self.db.update_node_status(
                    node_db_id,
                    NodeStatus.QUEUED.value,
                    expected_statuses=[NodeStatus.RUNNING.value, NodeStatus.ASSIGNED.value],
                    force=True,
                    error=error,
                    retry_count=node["retry_count"],
                    queued_at=_now_iso(),
                    started_at=None,
                    completed_at=None,
                )
                if updated:
                    logger.info(
                        "Retrying node %s (%s): attempt %d/%d",
                        node_db_id[:8], node.get("node_id"),
                        node["retry_count"], node["max_retries"],
                    )
            else:
                updated = await self.db.update_node_status(
                    node_db_id,
                    NodeStatus.BLOCKED.value,
                    expected_statuses=[NodeStatus.RUNNING.value, NodeStatus.ASSIGNED.value],
                    error=error,
                    completed_at=_now_iso(),
                )
                if updated:
                    await self._check_run_completion(run_id)

        await self.db.log_event(make_event_log(
            "node.completed", "node", node_db_id,
            old_state={"status": old_status},
            new_state={"status": node["status"], "success": success},
        ))

    async def _unlock_dependents(self, run_id: str, completed_node: dict) -> None:
        """解锁依赖于已完成节点的后继。"""
        nodes = await self.db.get_nodes(run_id)
        edges = await self.db.get_edges(run_id)

        terminal_statuses = {
            NodeStatus.SUCCESS.value,
            NodeStatus.SKIPPED.value,
            NodeStatus.CANCELLED.value,
        }
        completed_ids = {n["node_id"] for n in nodes if n["status"] in terminal_statuses}
        completed_ids.add(completed_node["node_id"])

        deps_map: Dict[str, Set[str]] = {}
        trigger_map: Dict[str, Set[str]] = {}
        for e in edges:
            if e["edge_type"] == "dependency":
                deps_map.setdefault(e["to_node"], set()).add(e["from_node"])
            elif e["edge_type"] == "trigger":
                trigger_map.setdefault(e["to_node"], set()).add(e["from_node"])

        for n in nodes:
            if n["status"] != NodeStatus.PENDING.value:
                continue
            deps = deps_map.get(n["node_id"], set())
            triggers = trigger_map.get(n["node_id"], set())
            # dependency 必须全部完成
            if deps and not all(d in completed_ids for d in deps):
                continue
            # trigger 边也必须全部完成
            if triggers and not all(d in completed_ids for d in triggers):
                continue
            queued = await self.db.update_node_status(
                n["id"],
                NodeStatus.QUEUED.value,
                expected_statuses=[NodeStatus.PENDING.value],
                queued_at=_now_iso(),
            )
            if queued:
                logger.info("Unlocked node %s (%s)", n["id"][:8], n["node_id"])

    async def _check_run_completion(self, run_id: str) -> None:
        """检查 DAGRun 是否已完成。"""
        nodes = await self.db.get_nodes(run_id)
        incomplete = [
            n for n in nodes
            if n["status"] not in {
                NodeStatus.SUCCESS.value,
                NodeStatus.CANCELLED.value,
                NodeStatus.SKIPPED.value,
            }
        ]
        if incomplete:
            # 如果有节点 BLOCKED/FAILED 且没有可执行的节点，标记 run 失败
            blocked_failed = [n for n in incomplete if n["status"] in {
                NodeStatus.BLOCKED.value, NodeStatus.FAILED.value,
            }]
            ready = [n for n in incomplete if n["status"] in {
                NodeStatus.PENDING.value, NodeStatus.QUEUED.value, NodeStatus.ASSIGNED.value,
            }]
            if blocked_failed and not ready:
                await self.db.update_run_status(
                    run_id, RunStatus.FAILED.value, completed_at=_now_iso())
                logger.info("DAGRun %s FAILED (blocked/failed nodes, no ready)", run_id)
            return

        await self.db.update_run_status(
            run_id, RunStatus.COMPLETED.value, completed_at=_now_iso())
        logger.info("DAGRun %s COMPLETED", run_id)

    async def get_queued_nodes(self, run_id: Optional[str] = None, limit: int = 10) -> List[dict]:
        if run_id:
            nodes = await self.db.get_nodes(run_id, status=NodeStatus.QUEUED.value)
        else:
            nodes = await self.db.get_nodes_by_status(NodeStatus.QUEUED.value)
        return nodes[:limit]

    async def assign_node(self, node_db_id: str, agent_id: str) -> bool:
        node = await self.db.get_node(node_db_id)
        agent = await self.db.get_agent(agent_id)
        if not node or not agent:
            return False
        updated = await self.db.update_node_status(
            node_db_id,
            NodeStatus.ASSIGNED.value,
            expected_statuses=[NodeStatus.QUEUED.value],
            started_at=_now_iso(),
        )
        if not updated:
            return False
        await self.db.update_agent_status(
            agent_id, AgentStatus.BUSY.value, current_node_id=node_db_id)
        await self.db.log_event(make_event_log(
            "node.assigned", "node", node_db_id,
            new_state={"agent_id": agent_id},
        ))
        return True

    def pause(self) -> None:
        self._paused = True
        logger.warning("Scheduler PAUSED")

    def resume(self) -> None:
        self._paused = False
        logger.info("Scheduler RESUMED")

    @property
    def is_paused(self) -> bool:
        return self._paused
