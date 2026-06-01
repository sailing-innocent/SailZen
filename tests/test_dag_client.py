# -*- coding: utf-8 -*-
# @file test_dag_client.py
# @brief DAG Client 框架核心测试
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""SailZen DAG Client 框架核心单元测试。

测试范围（不依赖外部服务）:
  - 配置加载
  - DAG 构建与拓扑排序
  - 节点注册表
  - Store 文件操作
  - 状态机工具函数
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path

# 确保项目根目录在路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from sailzen.dag_client.config import DAGClientConfig, load_config
from sailzen.dag_client.store import DAGStore
from sailzen.dag_client.models import (
    RunStatus, NodeStatus, AgentStatus,
    make_dag_definition, make_dag_run, make_dag_node, make_dag_edge,
    status_rank, is_terminal, _new_id, _now_iso,
)
from sailzen.dag_client.scheduler import (
    build_dag_from_template, topological_sort, get_ready_nodes,
)
from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult
from sailzen.dag_client.nodes.registry import NodeRegistry


# ═══════════════════════════════════════════════════════════════════════
#  Config Tests
# ═══════════════════════════════════════════════════════════════════════

class TestConfig:
    def test_default_config(self):
        cfg = DAGClientConfig()
        assert cfg.name == "default"
        assert cfg.api_port == 9050
        assert cfg.opencode.host == "127.0.0.1"

    def test_load_from_nonexistent_file(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            pass
        os.remove(f.name)
        # 不存在的文件应该使用默认值
        cfg = load_config(f.name)
        assert cfg.name == "default"


# ═══════════════════════════════════════════════════════════════════════
#  Store Tests
# ═══════════════════════════════════════════════════════════════════════

class TestStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = DAGStore(self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_dirs(self):
        assert (self.store.data_dir / "runs").exists()
        assert (self.store.data_dir / "artifacts").exists()
        assert (self.store.data_dir / "logs").exists()
        assert (self.store.data_dir / "backups").exists()

    def test_run_storage(self):
        rd = self.store.init_run_storage("run_123")
        assert rd.exists()
        assert (rd / "artifacts").exists()
        assert (rd / "logs").exists()

    def test_save_load_config(self):
        self.store.init_run_storage("run_123")
        path = self.store.save_run_config("run_123", {"key": "value"})
        assert path.exists()
        loaded = self.store.load_run_config("run_123")
        assert loaded == {"key": "value"}

    def test_artifacts(self):
        self.store.init_run_storage("run_123")
        self.store.save_artifact("run_123", "test.txt", "hello")
        assert self.store.list_artifacts("run_123") == ["test.txt"]
        assert self.store.read_artifact("run_123", "test.txt") == "hello"

    def test_backup_restore(self):
        self.store.init_run_storage("run_123")
        self.store.save_artifact("run_123", "test.txt", "backup me")
        bp = self.store.backup(label="test")
        assert bp.exists()

        # 恢复
        self.store.restore(str(bp), wipe=True)
        assert self.store.read_artifact("run_123", "test.txt") == "backup me"


# ═══════════════════════════════════════════════════════════════════════
#  Model Tests
# ═══════════════════════════════════════════════════════════════════════

class TestModels:
    def test_status_rank(self):
        assert status_rank("pending", "node") < status_rank("running", "node")
        assert status_rank("success", "node") > status_rank("queued", "node")

    def test_is_terminal(self):
        assert is_terminal("success", "node") is True
        assert is_terminal("pending", "node") is False
        assert is_terminal("completed", "run") is True

    def test_make_dag_definition(self):
        d = make_dag_definition("test", {"nodes": []})
        assert d["name"] == "test"
        assert "id" in d

    def test_make_dag_run(self):
        r = make_dag_run("def_1", params={"x": 1})
        assert r["definition_id"] == "def_1"
        assert r["params"]["x"] == 1

    def test_make_dag_node(self):
        n = make_dag_node("run_1", "node_a", "skill", params={"skill": "test"})
        assert n["run_id"] == "run_1"
        assert n["node_id"] == "node_a"
        assert n["status"] == NodeStatus.PENDING.value


# ═══════════════════════════════════════════════════════════════════════
#  Scheduler Tests
# ═══════════════════════════════════════════════════════════════════════

class TestScheduler:
    def test_build_dag_from_template(self):
        template = {
            "nodes": [
                {"id": "a", "type": "skill"},
                {"id": "b", "type": "shell", "depends_on": ["a"]},
                {"id": "c", "type": "python", "depends_on": ["a"]},
                {"id": "d", "type": "skill", "depends_on": ["b", "c"]},
            ],
            "edges": [],
        }
        run, nodes, edges = build_dag_from_template("def_1", template, {"env": "test"})
        assert run["definition_id"] == "def_1"
        assert len(nodes) == 4
        assert len(edges) == 4  # a->b, a->c, b->d, c->d (从 depends_on 推导)
        assert run["params"]["env"] == "test"

    def test_build_dag_with_explicit_edges(self):
        template = {
            "nodes": [
                {"id": "a", "type": "skill"},
                {"id": "b", "type": "shell"},
            ],
            "edges": [
                {"from": "a", "to": "b"},
            ],
        }
        run, nodes, edges = build_dag_from_template("def_1", template)
        assert len(edges) == 1
        assert edges[0]["from_node"] == "a"
        assert edges[0]["to_node"] == "b"

    def test_topological_sort(self):
        nodes = [
            make_dag_node("run_1", "a", "skill"),
            make_dag_node("run_1", "b", "shell"),
            make_dag_node("run_1", "c", "python"),
            make_dag_node("run_1", "d", "skill"),
        ]
        edges = [
            make_dag_edge("run_1", "a", "b"),
            make_dag_edge("run_1", "a", "c"),
            make_dag_edge("run_1", "b", "d"),
            make_dag_edge("run_1", "c", "d"),
        ]
        order = topological_sort(nodes, edges)
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_topological_sort_cycle(self):
        nodes = [
            make_dag_node("run_1", "a", "skill"),
            make_dag_node("run_1", "b", "shell"),
        ]
        edges = [
            make_dag_edge("run_1", "a", "b"),
            make_dag_edge("run_1", "b", "a"),
        ]
        with pytest.raises(ValueError, match="cycles"):
            topological_sort(nodes, edges)

    def test_get_ready_nodes(self):
        nodes = [
            {**make_dag_node("run_1", "a", "skill"), "status": NodeStatus.SUCCESS.value},
            {**make_dag_node("run_1", "b", "shell"), "status": NodeStatus.PENDING.value},
            {**make_dag_node("run_1", "c", "python"), "status": NodeStatus.PENDING.value},
            {**make_dag_node("run_1", "d", "skill"), "status": NodeStatus.PENDING.value},
        ]
        edges = [
            make_dag_edge("run_1", "a", "b"),
            make_dag_edge("run_1", "a", "c"),
            make_dag_edge("run_1", "b", "d"),
            make_dag_edge("run_1", "c", "d"),
        ]
        ready = get_ready_nodes(nodes, edges)
        ready_ids = {n["node_id"] for n in ready}
        assert ready_ids == {"b", "c"}


# ═══════════════════════════════════════════════════════════════════════
#  Node Registry Tests
# ═══════════════════════════════════════════════════════════════════════

class TestNodeRegistry:
    def test_builtin_nodes(self):
        reg = NodeRegistry()
        types = reg.list_types()
        assert "skill" in types
        assert "shell" in types
        assert "python" in types

    def test_create_node(self):
        reg = NodeRegistry()
        node = reg.create("shell")
        assert node.node_type == "shell"

    def test_unknown_node(self):
        reg = NodeRegistry()
        with pytest.raises(ValueError, match="Unknown node type"):
            reg.create("nonexistent")

    def test_register_custom(self):
        class CustomNode(NodeExecutor):
            node_type = "custom"
            async def execute(self, ctx):
                return NodeResult.ok()

        reg = NodeRegistry()
        reg.register("custom", CustomNode)
        assert "custom" in reg.list_types()
        node = reg.create("custom")
        assert node.node_type == "custom"


# ═══════════════════════════════════════════════════════════════════════
#  Node Executor Tests
# ═══════════════════════════════════════════════════════════════════════

class TestNodeExecutors:
    def test_skill_node_validate(self):
        from sailzen.dag_client.nodes.skill_node import SkillNode
        node = SkillNode()
        assert node.validate_params({}) is not None
        assert node.validate_params({"skill": "test"}) is None

    def test_shell_node_validate(self):
        from sailzen.dag_client.nodes.shell_node import ShellNode
        node = ShellNode()
        assert node.validate_params({}) is not None
        assert node.validate_params({"command": "echo hi"}) is None

    def test_python_node_validate(self):
        from sailzen.dag_client.nodes.python_node import PythonNode
        node = PythonNode()
        assert node.validate_params({}) is not None
        assert node.validate_params({"code": "print(1)"}) is None

    def test_node_result_helpers(self):
        ok = NodeResult.ok(data={"x": 1}, output="done")
        assert ok.success is True
        assert ok.data["x"] == 1

        fail = NodeResult.fail("error")
        assert fail.success is False
        assert fail.error == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
