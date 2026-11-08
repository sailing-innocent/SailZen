# -*- coding: utf-8 -*-
# @file test_dev_guard.py
# @brief 自我开发护栏负例测试 + 完整任务流（tmp git repo）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sailtick.config import SelfDevConfig
from sailtick.dev.guard import GuardError, SelfDevGuard
from sailtick.dev.repo import DevRepo
from sailtick.dev.tasks import DevTask, DevTaskResult, DevTaskRunner


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if check:
        assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


@pytest.fixture()
def git_repo(tmp_path) -> Path:
    """初始化一个带 main 提交的 tmp git 仓库。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test")
    _git(repo, "config", "user.name", "test")
    (repo / "sailtick").mkdir()
    (repo / "sailtick" / "__init__.py").write_text("# pkg\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "data").mkdir()
    (repo / ".env").write_text("SECRET=1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    return repo


def make_config(repo: Path) -> SelfDevConfig:
    return SelfDevConfig(
        repo_dir=str(repo),
        branch="agent/sailtick-dev",
        whitelist_dirs=["sailtick", "tests/sailtick"],
        protected_paths=["data", ".env", ".env.dev", ".git"],
    )


# ── guard 负例 ──────────────────────────────────────────────────────────────


def test_guard_rejects_outside_repo(git_repo):
    guard = SelfDevGuard(make_config(git_repo))
    with pytest.raises(GuardError):
        guard.assert_path_allowed("C:/Windows/system32/x.txt")


def test_guard_rejects_protected_paths(git_repo):
    guard = SelfDevGuard(make_config(git_repo))
    with pytest.raises(GuardError):
        guard.assert_path_allowed("data/secret.db")
    with pytest.raises(GuardError):
        guard.assert_path_allowed(".env")
    with pytest.raises(GuardError):
        guard.assert_path_allowed("data/nested/deep/file.txt")


def test_guard_rejects_non_whitelist(git_repo):
    guard = SelfDevGuard(make_config(git_repo))
    with pytest.raises(GuardError):
        guard.assert_path_allowed("sail_server/app.py")
    with pytest.raises(GuardError):
        guard.assert_path_allowed("README.md")


def test_guard_allows_whitelist(git_repo):
    guard = SelfDevGuard(make_config(git_repo))
    p = guard.assert_path_allowed("sailtick/new_module.py")
    assert p.name == "new_module.py"
    p2 = guard.assert_path_allowed("tests/sailtick/test_x.py")
    assert "tests" in str(p2)


def test_guard_branch_check(git_repo):
    guard = SelfDevGuard(make_config(git_repo))
    guard.assert_branch_allowed("agent/sailtick-dev")
    with pytest.raises(GuardError):
        guard.assert_branch_allowed("main")
    with pytest.raises(GuardError):
        guard.assert_branch_allowed("feature/other")


def test_repo_never_push(git_repo):
    repo = DevRepo(make_config(git_repo))
    with pytest.raises(GuardError):
        repo.never_push()


# ── 完整任务流 ──────────────────────────────────────────────────────────────


class FakeInbox:
    def __init__(self):
        self.approvals = []

    async def create_ticket(self, **kwargs):
        self.approvals.append(kwargs)
        return {"id": len(self.approvals)}


@pytest.mark.asyncio
async def test_dev_task_full_flow(git_repo):
    """跑通一次『AI 改小功能 → dev 分支 → 测试 → 提交 → approval 票据』。

    全程触碰不到 main / data / .env。
    """
    cfg = make_config(git_repo)
    inbox = FakeInbox()
    runner = DevTaskRunner(cfg, inbox=inbox)
    runner._run_tests = lambda task: (True, "1 passed")  # 环境无 uv/pytest 时替身

    task = DevTask(
        id="add-greeting",
        title="Add greeting module",
        description="sailtick 增加 hello 模块",
        files=["sailtick/hello.py"],
    )
    result = await runner.run_task(task, {"sailtick/hello.py": "def hello():\n    return 'hi'\n"})

    assert isinstance(result, DevTaskResult)
    assert result.success is True
    assert result.commit is not None
    assert result.ticket_id == 1

    # 分支与提交验证
    assert DevRepo(cfg).current_branch() == "agent/sailtick-dev"
    log = _git(git_repo, "log", "--oneline")
    assert "Add greeting module" in log
    # main 分支保持干净
    main_log = _git(git_repo, "log", "--oneline", "main")
    assert "Add greeting module" not in main_log
    # approval 票据内容
    assert inbox.approvals[0]["ticket_type"] == "approval"
    assert "review" in inbox.approvals[0]["title"]


@pytest.mark.asyncio
async def test_dev_task_refuses_undeclared_file(git_repo):
    """task.files 未声明的文件拒绝写入。"""
    cfg = make_config(git_repo)
    runner = DevTaskRunner(cfg)
    task = DevTask(id="t1", title="t", description="", files=["sailtick/a.py"])
    result = await runner.run_task(task, {"sailtick/b.py": "x"})
    assert result.success is False
    assert "not declared" in result.error


@pytest.mark.asyncio
async def test_dev_task_refuses_protected_file(git_repo):
    """写入 .env / data 的尝试被 guard 拦截。"""
    cfg = make_config(git_repo)
    runner = DevTaskRunner(cfg)
    task = DevTask(id="t1", title="t", description="", files=[".env"])
    result = await runner.run_task(task, {".env": "HACKED=1"})
    assert result.success is False


@pytest.mark.asyncio
async def test_dev_task_test_failure_no_commit(git_repo):
    """测试失败时不提交。"""
    cfg = make_config(git_repo)
    runner = DevTaskRunner(cfg)
    runner._run_tests = lambda task: (False, "1 failed")
    task = DevTask(id="t1", title="bad change", description="", files=["sailtick/x.py"])
    result = await runner.run_task(task, {"sailtick/x.py": "broken"})
    assert result.success is False
    assert result.error == "tests failed"
    assert _git(git_repo, "log", "--oneline", "agent/sailtick-dev", check=False) == "" or \
        "bad change" not in _git(git_repo, "log", "--oneline")
