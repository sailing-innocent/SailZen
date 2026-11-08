# -*- coding: utf-8 -*-
# @file tasks.py
# @brief 自我开发任务执行器（需求 → dev 分支 → 测试 → 提交 → 合入票据）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""DevTaskRunner — 自我开发工作流。

流程（设计文档 D5）:
  1. guard 校验分支与目标文件（白名单）
  2. 写入文件内容（内容由 nightly Tick 的 LLM 生成，runner 只负责执行与校验）
  3. 跑测试门槛（默认 ``pytest tests/sailtick -m "not current"``）
  4. 提交到 agent/sailtick-dev
  5. 开 approval 票据「请 review 合入」

任何一步失败即中止，不留半成品提交（测试失败时不提交）。
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional

from sailtick.config import SelfDevConfig
from sailtick.dev.guard import GuardError, SelfDevGuard
from sailtick.dev.repo import DevRepo

logger = logging.getLogger(__name__)

DEFAULT_TEST_CMD = ["uv", "run", "pytest", "tests/sailtick", "-m", "not current", "-q"]


@dataclass
class DevTask:
    """一个开发任务定义。"""

    id: str
    title: str
    description: str
    files: List[str]  # 仓库相对路径，须全部在白名单内
    test_cmd: Optional[List[str]] = None


@dataclass
class DevTaskResult:
    """任务结果。"""

    success: bool
    task_id: str
    commit: Optional[str] = None
    ticket_id: Optional[int] = None
    test_output: str = ""
    error: Optional[str] = None
    summary: str = ""


class DevTaskRunner:
    """开发任务执行器。"""

    def __init__(self, config: SelfDevConfig, inbox=None):
        self.config = config
        self.repo = DevRepo(config)
        self.guard = SelfDevGuard(config)
        self.inbox = inbox  # TicketInbox，可选

    # ── 主流程 ────────────────────────────────────────────────────────

    async def run_task(self, task: DevTask, file_contents: Dict[str, str]) -> DevTaskResult:
        """执行一个开发任务。"""
        logger.info("[dev] task start: %s (%s)", task.id, task.title)
        try:
            self.repo.checkout_dev()
            self._write_files(task, file_contents)
        except Exception as exc:
            logger.exception("[dev] task %s failed at write stage", task.id)
            return DevTaskResult(success=False, task_id=task.id, error=f"write: {exc}")

        ok, test_output = self._run_tests(task)
        if not ok:
            logger.warning("[dev] task %s failed tests; NOT committing", task.id)
            return DevTaskResult(
                success=False, task_id=task.id,
                test_output=test_output[-2000:],
                error="tests failed",
            )

        try:
            commit = self.repo.commit_all(f"[sailtick-dev] {task.title}\n\n{task.description}")
        except Exception as exc:
            logger.exception("[dev] task %s failed at commit stage", task.id)
            return DevTaskResult(
                success=False, task_id=task.id, test_output=test_output[-2000:],
                error=f"commit: {exc}",
            )

        ticket_id = await self._open_approval_ticket(task, commit)
        summary = f"task {task.id} done: commit {commit}"
        logger.info("[dev] %s", summary)
        return DevTaskResult(
            success=True, task_id=task.id, commit=commit,
            ticket_id=ticket_id, test_output=test_output[-1000:], summary=summary,
        )

    # ── 步骤 ──────────────────────────────────────────────────────────

    def _write_files(self, task: DevTask, file_contents: Dict[str, str]) -> None:
        """guard 校验后写文件。"""
        assert self.repo.repo is not None
        for rel, content in file_contents.items():
            if rel not in task.files:
                raise GuardError(f"file {rel!r} not declared in task.files")
            path = self.guard.assert_path_allowed(rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            logger.info("[dev] wrote %s (%d chars)", rel, len(content))

    def _run_tests(self, task: DevTask) -> tuple[bool, str]:
        """测试门槛。返回 (通过?, 输出)。"""
        cmd = task.test_cmd or DEFAULT_TEST_CMD
        logger.info("[dev] running tests: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd, cwd=self.repo.repo, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=900,
            )
            output = (result.stdout or "") + (result.stderr or "")
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, "tests timed out (>900s)"
        except FileNotFoundError as exc:
            # 环境缺 uv 等，视为环境失败（不提交）
            return False, f"test runner not found: {exc}"

    async def _open_approval_ticket(self, task: DevTask, commit: str) -> Optional[int]:
        """开「请 review 合入」approval 票据。"""
        if self.inbox is None:
            return None
        try:
            diff = self.repo.diff_stat()
            ticket = await self.inbox.create_ticket(
                tick_id=f"dev-{task.id}",
                ticket_type="approval",
                title=f"[review] {task.title}",
                body=(
                    f"自我开发任务 `{task.id}` 已完成并提交到 `{self.config.branch}`。\n\n"
                    f"**描述**: {task.description}\n\n"
                    f"**提交**: `{commit}`\n\n"
                    f"**改动**:\n```\n{diff[:1500]}\n```\n\n"
                    f"测试已通过。请 review 后合入 main（agent 无 push 权限）。"
                ),
                priority="normal",
                expected_reply_hours=72,
                fallback_assumption="未 review 前不合入，任务留存在 dev 分支",
                channel="web",
            )
            return ticket.get("id")
        except Exception as exc:
            logger.warning("[dev] approval ticket failed (non-fatal): %s", exc)
            return None
