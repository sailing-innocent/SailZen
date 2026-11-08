# -*- coding: utf-8 -*-
# @file test_dag_client_contract.py
# @brief dag_client 共享引擎接口契约测试（SailTick 依赖的最小接口集）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""dag_client 接口契约测试。

背景：SailTick 复用 sailzen.dag_client 作为执行引擎（生产 /dag-pipeline
页面在用）。本测试锁定 SailTick 依赖的最小接口集，防止共享引擎被无意破坏：

  - DAGScheduler.create_run / on_node_completed / get_queued_nodes / pause / resume
  - DAGExecutor 构造签名 + execute_node_sync 单节点执行
  - NodeRegistry.register / create（自定义节点类型）
  - DAGStore.run_dir / init_run_storage / save_artifact
  - EventBus.subscribe / emit / unsubscribe + 外部 handler

设计文档：doc/design/agent-system/sailtick.md §风险与缓解。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest
import pytest_asyncio

from sailzen.dag_client.database import Database as DAGDatabase
from sailzen.dag_client.events import EventBus
from sailzen.dag_client.executor import DAGExecutor
from sailzen.dag_client.models import NodeStatus, RunStatus, make_dag_definition
from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult
from sailzen.dag_client.nodes.registry import NodeRegistry
from sailzen.dag_client.repositories import DatabaseCompat
from sailzen.dag_client.scheduler import DAGScheduler
from sailzen.dag_client.store import DAGStore


# ── Fixtures ────────────────────────────────────────────────────────────────


class DAGEnv:
    """测试环境：db_compat + 已注册的 definition_id。"""

    def __init__(self, raw: DAGDatabase, db: DatabaseCompat, definition_id: str):
        self.raw = raw
        self.db = db
        self.definition_id = definition_id


@pytest_asyncio.fixture()
async def dag_db(tmp_path):
    """独立的 SQLite dag_client 数据库（经 DatabaseCompat 适配）。

    生产接线方式见 sailzen/dag_client/app.py:
    ``DatabaseCompat(raw_db)`` 才是 DAGScheduler/DAGExecutor 需要的 db_compat。
    注意：dag_runs.definition_id 存在外键，必须先注册 definition 才能 create_run。
    """
    raw = DAGDatabase(str(tmp_path / "dag_contract.db"))
    await raw.connect()
    db = DatabaseCompat(raw)
    definition = await db.upsert_definition(
        make_dag_definition("contract_test", SIMPLE_TEMPLATE, "contract test def")
    )
    yield DAGEnv(raw, db, definition["id"])
    await raw.close()


@pytest.fixture()
def store(tmp_path):
    return DAGStore(str(tmp_path / "dag_data"))


SIMPLE_TEMPLATE: Dict[str, Any] = {
    "nodes": [
        {"id": "n1", "type": "test_echo", "params": {"msg": "hello"}},
        {"id": "n2", "type": "test_echo", "depends_on": ["n1"], "params": {"msg": "world"}},
    ],
    "edges": [],
}


class EchoNode(NodeExecutor):
    """测试用节点：回显 params.msg。"""

    node_type = "test_echo"

    async def execute(self, ctx: NodeContext) -> NodeResult:
        return NodeResult.ok(
            data={"echo": ctx.params.get("msg", ""), "upstream": ctx.upstream_results},
            output=f"echo:{ctx.params.get('msg', '')}",
        )


# ── DAGScheduler ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scheduler_create_run_persists_and_queues_ready(dag_db):
    """create_run 必须持久化 run/nodes/edges 并将无依赖节点置为 QUEUED。"""
    scheduler = DAGScheduler(dag_db.db)
    run = await scheduler.create_run(
        definition_id=dag_db.definition_id,
        template=SIMPLE_TEMPLATE,
        name="contract",
        params={"k": "v"},
    )

    assert run["definition_id"] == dag_db.definition_id
    assert run["params"] == {"k": "v"}
    # 注意契约：create_run 返回的是创建时的快照（status=pending），
    # 权威状态需从 DB 重新读取（调度器随后将其置为 running）。
    run_fresh = await dag_db.db.get_run(run["id"])
    assert run_fresh["status"] == RunStatus.RUNNING.value

    nodes = await dag_db.db.get_nodes(run["id"])
    assert {n["node_id"] for n in nodes} == {"n1", "n2"}
    by_id = {n["node_id"]: n for n in nodes}
    assert by_id["n1"]["status"] == NodeStatus.QUEUED.value  # 无依赖 → 立即就绪
    assert by_id["n2"]["status"] == NodeStatus.PENDING.value  # 等待 n1

    edges = await dag_db.db.get_edges(run["id"])
    assert [(e["from_node"], e["to_node"]) for e in edges] == [("n1", "n2")]


@pytest.mark.asyncio
async def test_scheduler_on_node_completed_unlocks_dependents(dag_db):
    """节点成功后，后继节点必须由 PENDING 转为 QUEUED。"""
    scheduler = DAGScheduler(dag_db.db)
    run = await scheduler.create_run(dag_db.definition_id, SIMPLE_TEMPLATE)

    nodes = await dag_db.db.get_nodes(run["id"])
    n1 = next(n for n in nodes if n["node_id"] == "n1")
    n2 = next(n for n in nodes if n["node_id"] == "n2")

    # 手动将 n1 置为 RUNNING 再回调完成（模拟 executor 行为）
    await dag_db.db.update_node_status(
        n1["id"], NodeStatus.RUNNING.value, expected_statuses=[NodeStatus.QUEUED.value]
    )
    await scheduler.on_node_completed(n1["id"], success=True, result={"ok": True})

    n2_after = await dag_db.db.get_node(n2["id"])
    assert n2_after["status"] == NodeStatus.QUEUED.value

    # n2 也完成后 run 应 COMPLETED
    await dag_db.db.update_node_status(
        n2["id"], NodeStatus.RUNNING.value, expected_statuses=[NodeStatus.QUEUED.value]
    )
    await scheduler.on_node_completed(n2["id"], success=True)
    run_after = await dag_db.db.get_run(run["id"])
    assert run_after["status"] == RunStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_scheduler_pause_resume(dag_db):
    scheduler = DAGScheduler(dag_db.db)
    assert scheduler.is_paused is False
    scheduler.pause()
    assert scheduler.is_paused is True
    scheduler.resume()
    assert scheduler.is_paused is False


# ── NodeRegistry ────────────────────────────────────────────────────────────


def test_registry_register_and_create_custom_node():
    """外部包必须能在运行时注册自定义节点类型并实例化。"""
    registry = NodeRegistry()
    registry.register("test_echo", EchoNode)
    assert "test_echo" in registry.list_types()

    node = registry.create("test_echo")
    assert isinstance(node, EchoNode)

    with pytest.raises(ValueError):
        registry.create("nonexistent_type")


def test_registry_builtin_types_present():
    registry = NodeRegistry()
    types = registry.list_types()
    # SailTick pipelines 依赖的内置类型
    for builtin in ("skill", "shell", "python", "text_fetch"):
        assert builtin in types


# ── DAGExecutor ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_executor_constructs_with_documented_signature(dag_db, store):
    """DAGExecutor 构造签名契约：6 个命名参数，opencode_client 可选。"""
    scheduler = DAGScheduler(dag_db.db)
    registry = NodeRegistry()
    registry.register("test_echo", EchoNode)
    bus = EventBus()

    executor = DAGExecutor(
        db_compat=dag_db.db,
        scheduler=scheduler,
        event_bus=bus,
        node_registry=registry,
        store=store,
        opencode_client=None,
    )
    assert executor.registry is registry
    assert executor.opencode_client is None


@pytest.mark.asyncio
async def test_executor_execute_node_sync_runs_registered_node(dag_db, store, tmp_path):
    """execute_node_sync 必须执行节点并把结果/状态写回。"""
    scheduler = DAGScheduler(dag_db.db)
    registry = NodeRegistry()
    registry.register("test_echo", EchoNode)
    bus = EventBus()
    executor = DAGExecutor(
        db_compat=dag_db.db,
        scheduler=scheduler,
        event_bus=bus,
        node_registry=registry,
        store=store,
        opencode_client=None,
    )

    run = await scheduler.create_run(dag_db.definition_id, SIMPLE_TEMPLATE)
    queued = await scheduler.get_queued_nodes(run["id"])
    assert len(queued) == 1 and queued[0]["node_id"] == "n1"

    result = await executor.execute_node_sync(queued[0]["id"])
    assert result.success is True
    assert result.data["echo"] == "hello"

    node_after = await dag_db.db.get_node(queued[0]["id"])
    assert node_after["status"] == NodeStatus.SUCCESS.value
    assert node_after["result"]["echo"] == "hello"

    nodes = await dag_db.db.get_nodes(run["id"])
    n2 = next(n for n in nodes if n["node_id"] == "n2")
    assert n2["status"] == NodeStatus.QUEUED.value


# ── DAGStore
# ── DAGStore ────────────────────────────────────────────────────────────────


def test_store_run_dir_and_artifacts(store: DAGStore, tmp_path):
    """run_dir 必须位于 data_dir/runs/<run_id> 下，产物可存取。"""
    rd = store.init_run_storage("run_abc")
    assert rd == Path(str(tmp_path / "dag_data")) / "runs" / "run_abc"
    assert rd.exists()

    store.save_artifact("run_abc", "out.txt", "hello 世界")
    assert store.read_artifact("run_abc", "out.txt") == "hello 世界"
    assert "out.txt" in store.list_artifacts("run_abc")
    assert store.read_artifact("run_abc", "missing.txt") is None


# ── EventBus ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_event_bus_subscribe_emit_unsubscribe():
    import asyncio

    bus = EventBus()

    received: List[dict] = []

    async def _handler(ev: dict) -> None:
        received.append(ev)

    bus.add_handler(_handler)

    q = bus.subscribe("run_1")
    await bus.emit({"type": "node.completed", "entity_id": "run_1", "run_id": "run_1", "data": {}})

    payload = await asyncio.wait_for(q.get(), timeout=1.0)
    assert '"node.completed"' in payload
    assert received and received[0]["type"] == "node.completed"

    bus.unsubscribe("run_1", q)
    assert bus.subscriber_count == 0
