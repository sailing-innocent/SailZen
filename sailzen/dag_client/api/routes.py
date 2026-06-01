# -*- coding: utf-8 -*-
# @file routes.py
# @brief HTTP API 路由
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""SailZen DAG Client HTTP API 路由。

端点设计::

  GET  /health                    健康检查
  GET  /definitions               列出 DAG 定义
  GET  /definitions/{id}          获取 DAG 定义
  POST /definitions               创建 DAG 定义
  DELETE /definitions/{id}        删除 DAG 定义

  GET  /runs                      列出运行
  GET  /runs/{id}                 获取运行详情
  POST /runs                      创建运行（从定义）
  POST /runs/{id}/cancel          取消运行
  POST /runs/{id}/pause           暂停调度
  POST /runs/{id}/resume          恢复调度

  GET  /runs/{id}/nodes           列出节点
  GET  /runs/{id}/nodes/{nid}     获取节点详情
  POST /runs/{id}/nodes/{nid}/retry   重试节点
  POST /runs/{id}/nodes/{nid}/skip    跳过节点

  GET  /agents                    列出 Agent
  POST /agents/{id}/heartbeat     Agent 心跳

  GET  /events                    列出事件日志
  GET  /skills/check              检查必需 skills
  POST /backup                    创建备份
  GET  /backups                   列出备份
  POST /restore                   恢复备份
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from litestar import Router, get, post, delete, Request
from litestar.response import Response

from sailzen.dag_client.config import DAGClientConfig
from sailzen.dag_client.deps import get_db, get_scheduler, get_event_bus, get_store, get_bridge
from sailzen.dag_client.models import (
    RunStatus, NodeStatus,
    make_dag_definition, make_dag_run, make_event_log, _now_iso,
)
from sailzen.dag_client.scheduler import DAGScheduler

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────

def _ok(data: Any = None) -> Response:
    return Response({"success": True, "data": data})

def _err(message: str, status: int = 400, data: Any = None) -> Response:
    return Response({"success": False, "error": message, "data": data}, status_code=status)


# ── Health ──────────────────────────────────────────────────────────

@get("/health")
async def health_check() -> Response:
    db = get_db()
    db_ok = await db.check_integrity()
    stats = await db.get_stats() if db_ok else {}
    bridge = get_bridge()
    opencode_ok = await bridge.health_check() if bridge else False
    return _ok({
        "healthy": db_ok,
        "db_stats": stats,
        "opencode_connected": opencode_ok,
    })


# ── Definitions ─────────────────────────────────────────────────────

@get("/definitions")
async def list_definitions() -> Response:
    defs = await get_db().get_definitions()
    return _ok(defs)


@get("/definitions/{def_id:str}")
async def get_definition(def_id: str) -> Response:
    d = await get_db().get_definition(def_id)
    if not d:
        return _err("Definition not found", 404)
    return _ok(d)


@post("/definitions")
async def create_definition(data: dict) -> Response:
    template = data.get("template", {})
    if not template.get("nodes"):
        return _err("Template must contain nodes")
    d = make_dag_definition(
        name=data.get("name", "unnamed"),
        template=template,
        description=data.get("description", ""),
    )
    created = await get_db().upsert_definition(d)
    return _ok(created)


@delete("/definitions/{def_id:str}")
async def delete_definition(def_id: str) -> Response:
    ok = await get_db().repos.definition.delete(def_id)
    if not ok:
        return _err("Definition not found", 404)
    return _ok()


# ── Runs ────────────────────────────────────────────────────────────

@get("/runs")
async def list_runs(
    definition_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> Response:
    runs = await get_db().get_runs(definition_id=definition_id, status=status)
    return _ok(runs[:limit])


@get("/runs/{run_id:str}")
async def get_run(run_id: str) -> Response:
    run = await get_db().get_run(run_id)
    if not run:
        return _err("Run not found", 404)
    nodes = await get_db().get_nodes(run_id)
    edges = await get_db().get_edges(run_id)
    return _ok({**run, "nodes": nodes, "edges": edges})


@post("/runs")
async def create_run(data: dict) -> Response:
    def_id = data.get("definition_id")
    if not def_id:
        return _err("Missing definition_id")
    definition = await get_db().get_definition(def_id)
    if not definition:
        return _err("Definition not found", 404)

    scheduler = get_scheduler()
    run = await scheduler.create_run(
        definition_id=def_id,
        template=definition.get("template", {}),
        name=data.get("name", ""),
        params=data.get("params", {}),
    )
    return _ok(run)


@post("/runs/{run_id:str}/cancel")
async def cancel_run(run_id: str) -> Response:
    db = get_db()
    run = await db.get_run(run_id)
    if not run:
        return _err("Run not found", 404)
    if run["status"] in {RunStatus.COMPLETED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value}:
        return _err("Run already in terminal state")

    await db.update_run_status(run_id, RunStatus.CANCELLED.value, completed_at=_now_iso())
    nodes = await db.get_nodes(run_id)
    for n in nodes:
        if n["status"] not in {
            NodeStatus.SUCCESS.value, NodeStatus.FAILED.value,
            NodeStatus.BLOCKED.value, NodeStatus.CANCELLED.value,
        }:
            await db.update_node_status(
                n["id"], NodeStatus.CANCELLED.value,
                expected_statuses=[
                    NodeStatus.PENDING.value, NodeStatus.QUEUED.value,
                    NodeStatus.ASSIGNED.value, NodeStatus.RUNNING.value,
                ],
            )
    await db.log_event(make_event_log("run.cancelled", "run", run_id))
    return _ok()


@post("/runs/{run_id:str}/pause")
async def pause_run(run_id: str) -> Response:
    get_scheduler().pause()
    return _ok()


@post("/runs/{run_id:str}/resume")
async def resume_run(run_id: str) -> Response:
    get_scheduler().resume()
    return _ok()


# ── Nodes ───────────────────────────────────────────────────────────

@get("/runs/{run_id:str}/nodes")
async def list_nodes(run_id: str, status: Optional[str] = None) -> Response:
    nodes = await get_db().get_nodes(run_id, status=status)
    return _ok(nodes)


@get("/runs/{run_id:str}/nodes/{node_db_id:str}")
async def get_node(run_id: str, node_db_id: str) -> Response:
    node = await get_db().get_node(node_db_id)
    if not node or node["run_id"] != run_id:
        return _err("Node not found", 404)
    runs = await get_db().get_node_runs(node_db_id)
    return _ok({**node, "runs": runs})


@post("/runs/{run_id:str}/nodes/{node_db_id:str}/retry")
async def retry_node(run_id: str, node_db_id: str) -> Response:
    db = get_db()
    node = await db.get_node(node_db_id)
    if not node or node["run_id"] != run_id:
        return _err("Node not found", 404)
    ok = await db.update_node_status(
        node_db_id,
        NodeStatus.QUEUED.value,
        expected_statuses=[NodeStatus.FAILED.value, NodeStatus.BLOCKED.value],
        force=True,
        retry_count=node.get("retry_count", 0) + 1,
        queued_at=_now_iso(),
        started_at=None,
        completed_at=None,
    )
    if not ok:
        return _err("Cannot retry node in current state")
    await db.log_event(make_event_log("node.retried", "node", node_db_id))
    return _ok()


@post("/runs/{run_id:str}/nodes/{node_db_id:str}/skip")
async def skip_node(run_id: str, node_db_id: str) -> Response:
    db = get_db()
    node = await db.get_node(node_db_id)
    if not node or node["run_id"] != run_id:
        return _err("Node not found", 404)
    ok = await db.update_node_status(
        node_db_id, NodeStatus.SKIPPED.value,
        expected_statuses=[
            NodeStatus.PENDING.value, NodeStatus.QUEUED.value,
            NodeStatus.FAILED.value, NodeStatus.BLOCKED.value,
        ],
        force=True,
        completed_at=_now_iso(),
    )
    if not ok:
        return _err("Cannot skip node in current state")
    await db.log_event(make_event_log("node.skipped", "node", node_db_id))
    # 解锁后继
    await get_scheduler()._unlock_dependents(run_id, {**node, "status": NodeStatus.SKIPPED.value, "node_id": node["node_id"]})
    await get_scheduler()._check_run_completion(run_id)
    return _ok()


# ── Agents ──────────────────────────────────────────────────────────

@get("/agents")
async def list_agents(status: Optional[str] = None) -> Response:
    agents = await get_db().get_agents(status=status)
    return _ok(agents)


@post("/agents/{agent_id:str}/heartbeat")
async def agent_heartbeat(agent_id: str, data: dict = None) -> Response:
    db = get_db()
    agent = await db.get_agent(agent_id)
    if not agent:
        return _err("Agent not found", 404)
    await db.update_agent_status(
        agent_id, data.get("status", "online") if data else "online",
        heartbeat_at=_now_iso(),
    )
    return _ok()


# ── Events ──────────────────────────────────────────────────────────

@get("/events")
async def list_events(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 100,
) -> Response:
    events = await get_db().get_event_logs(entity_type, entity_id, limit)
    return _ok(events)


# ── Skills ──────────────────────────────────────────────────────────

@get("/skills/check")
async def check_skills() -> Response:
    bridge = get_bridge()
    if not bridge:
        return _err("OpenCode bridge not available", 503)
    required = await get_db().get_required_skills()
    required_names = [s["skill_name"] for s in required]
    available = await bridge.list_available_skills()
    result = {
        "required": required_names,
        "available": available,
        "status": {s: s in available for s in required_names},
    }
    return _ok(result)


# ── Backup ──────────────────────────────────────────────────────────

@post("/backup")
async def create_backup(data: dict = None) -> Response:
    store = get_store()
    label = data.get("label") if data else None
    path = store.backup(label=label)
    return _ok({"backup_path": str(path)})


@get("/backups")
async def list_backups() -> Response:
    store = get_store()
    backups = store.list_backups()
    return _ok([{"path": str(b), "name": b.name, "size": b.stat().st_size} for b in backups])


@post("/restore")
async def restore_backup(data: dict) -> Response:
    path = data.get("path")
    if not path:
        return _err("Missing path")
    store = get_store()
    try:
        store.restore(path, wipe=data.get("wipe", False))
        return _ok()
    except Exception as exc:
        return _err(str(exc))


# ── Router ──────────────────────────────────────────────────────────

def create_api_router() -> Router:
    return Router(
        path="/api/v1/dag",
        route_handlers=[
            health_check,
            list_definitions,
            get_definition,
            create_definition,
            delete_definition,
            list_runs,
            get_run,
            create_run,
            cancel_run,
            pause_run,
            resume_run,
            list_nodes,
            get_node,
            retry_node,
            skip_node,
            list_agents,
            agent_heartbeat,
            list_events,
            check_skills,
            create_backup,
            list_backups,
            restore_backup,
        ],
    )
