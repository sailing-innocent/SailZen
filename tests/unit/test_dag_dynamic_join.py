# -*- coding: utf-8 -*-
# @file test_dag_dynamic_join.py
# @brief DAG 动态分支 join_to 机制测试
# @author sailing-innocent
# @date 2026-07-13
# @version 1.0
# ---------------------------------

"""测试 DAG Executor 的 _handle_dynamic_nodes 对 depends_on / join_to 的支持。"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile

import pytest
import pytest_asyncio

from sailzen.dag_client.database import Database
from sailzen.dag_client.repositories import DatabaseCompat
from sailzen.dag_client.executor import DAGExecutor
from sailzen.dag_client.models import NodeStatus, make_dag_run, make_dag_node, make_dag_edge
from sailzen.dag_client.nodes.registry import NodeRegistry
from sailzen.dag_client.store import DAGStore


@pytest_asyncio.fixture
async def db_compat():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "dag_client.db")
    db = Database(db_path)
    await db.connect()
    compat = DatabaseCompat(db)
    yield compat
    await db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def event_bus():
    class Bus:
        def __init__(self):
            self.events = []

        async def emit(self, event):
            self.events.append(event)

    return Bus()


@pytest.mark.asyncio
async def test_dynamic_join_to_blocks_static_merge(db_compat, event_bus):
    """验证 batch_split 动态生成的 analyze 节点通过 join_to 阻塞 merge 节点。"""
    tmpdir = tempfile.mkdtemp()
    store = DAGStore(tmpdir)

    # 构造一个最小调度器桩，只提供 unlock_dependents 行为
    class FakeScheduler:
        def __init__(self):
            self.is_paused = False
            self.unlocked = []

        async def get_queued_nodes(self, run_id=None, limit=10):
            return []

    scheduler = FakeScheduler()
    executor = DAGExecutor(
        db_compat=db_compat,
        scheduler=scheduler,
        event_bus=event_bus,
        node_registry=NodeRegistry(),
        store=store,
        opencode_client=None,
    )

    from sailzen.dag_client.models import make_dag_definition
    definition = make_dag_definition("test_def", {"nodes": []})
    await db_compat.upsert_definition(definition)

    run = make_dag_run(definition["id"])
    await db_compat.create_run(run)

    # 静态节点: batch_split -> merge_character
    batch_split = make_dag_node(run["id"], "batch_split", "batch_split")
    merge_character = make_dag_node(run["id"], "merge_character", "batch_merge")
    await db_compat.create_node(batch_split)
    await db_compat.create_node(merge_character)
    await db_compat.create_edge(make_dag_edge(run["id"], "batch_split", "merge_character"))

    # batch_split 完成，动态生成 batch_fetch_0 和 analyze_character_0
    parent_node = batch_split
    next_nodes = [
        {
            "id": "batch_fetch_0",
            "type": "text_fetch",
            "depends_on": ["batch_split"],
        },
        {
            "id": "analyze_character_0",
            "type": "skill",
            "depends_on": ["batch_fetch_0"],
            "join_to": ["merge_character"],
        },
    ]

    await executor._handle_dynamic_nodes(parent_node, next_nodes)

    # 检查动态节点和边都已创建
    edges = await db_compat.get_edges(run["id"])
    edge_pairs = {(e["from_node"], e["to_node"], e["edge_type"]) for e in edges}

    assert ("batch_split", "merge_character", "dependency") in edge_pairs
    assert ("batch_split", "batch_fetch_0", "dependency") in edge_pairs
    assert ("batch_fetch_0", "analyze_character_0", "dependency") in edge_pairs
    assert ("analyze_character_0", "merge_character", "dependency") in edge_pairs

    # 此时 merge_character 不应被解锁，因为 analyze_character_0 还未完成
    nodes = {n["node_id"]: n for n in await db_compat.get_nodes(run["id"])}
    assert nodes["batch_fetch_0"]["status"] == NodeStatus.PENDING.value
    assert nodes["analyze_character_0"]["status"] == NodeStatus.PENDING.value
    assert nodes["merge_character"]["status"] == NodeStatus.PENDING.value

    shutil.rmtree(tmpdir, ignore_errors=True)
