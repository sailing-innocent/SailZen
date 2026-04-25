# -*- coding: utf-8 -*-
# @file self_update_orchestrator.py
# @brief Simplified self-update: exit code 42 → watcher restarts
# @author sailing-innocent
# @date 2026-04-25
# @version 3.0
# ---------------------------------
"""Simplified self-update for Feishu Bot.

退出约定:
    0:  正常退出，不重启
    42: 需要自更新重启（watcher 负责 git pull + restart）

用法:
    orchestrator = SelfUpdateOrchestrator()
    orchestrator.request_update(reason="用户手动触发")
    # ... 在主循环中检查 ...
    if orchestrator.should_exit():
        return orchestrator.exit_code  # 42
"""

import logging
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

EXIT_CODE_SELF_UPDATE = 42


class SelfUpdateOrchestrator:
    """精简的自更新协调器。

    唯一职责：在收到更新请求后，可选执行 git pull，然后
    标记 should_exit=True + exit_code=42，由外层主循环检测并退出。
    Watcher 脚本看到 exit code 42 后会执行 git pull 并重启进程。
    """

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self._workspace_root = workspace_root or self._find_workspace_root()
        self._should_exit = False
        self._exit_code = 0
        self._reason: str = ""
        self._requested_at: Optional[str] = None
        self._lock = threading.Lock()

    # ── 公共 API ──────────────────────────────────────────────────

    def request_update(
        self,
        reason: str = "手动触发",
        perform_git_pull: bool = False,
    ) -> dict:
        """请求自更新。

        Args:
            reason: 更新原因（用于日志）
            perform_git_pull: 是否在退出前先 git pull（watcher 也会做，通常不需要）

        Returns:
            {"success": bool, "message": str}
        """
        with self._lock:
            if self._should_exit:
                return {"success": False, "message": "更新已在进行中"}

        logger.info("[SelfUpdate] 收到更新请求: %s", reason)
        self._reason = reason
        self._requested_at = datetime.now().isoformat()

        # 可选的 git pull（watcher 也会做，这里是 best-effort）
        if perform_git_pull:
            self._try_git_pull()

        with self._lock:
            self._should_exit = True
            self._exit_code = EXIT_CODE_SELF_UPDATE

        logger.info("[SelfUpdate] 已标记退出 (code=%d)", EXIT_CODE_SELF_UPDATE)
        return {"success": True, "message": f"更新已触发，即将重启 (exit code {EXIT_CODE_SELF_UPDATE})"}

    def should_exit(self) -> bool:
        """主循环轮询：是否应该退出。"""
        with self._lock:
            return self._should_exit

    @property
    def exit_code(self) -> int:
        """获取退出码。"""
        with self._lock:
            return self._exit_code

    # ── 内部方法 ──────────────────────────────────────────────────

    def _try_git_pull(self) -> None:
        """Best-effort git pull。"""
        try:
            result = subprocess.run(
                ["git", "pull"],
                cwd=self._workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("[SelfUpdate] git pull 成功: %s", result.stdout.strip())
            else:
                logger.warning("[SelfUpdate] git pull 失败: %s", result.stderr.strip())
        except Exception as exc:
            logger.warning("[SelfUpdate] git pull 异常: %s", exc)

    @staticmethod
    def _find_workspace_root() -> Path:
        """从 git 或文件位置推断工作区根目录。"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
            )
            return Path(result.stdout.strip())
        except Exception:
            return Path(__file__).parent.parent


def get_exit_code_for_restart() -> int:
    """Get the exit code that signals watcher to restart with update."""
    return EXIT_CODE_SELF_UPDATE
