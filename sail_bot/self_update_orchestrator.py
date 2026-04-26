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

更新完成通知机制:
    1. 请求更新前调用 save_pending_update(chat_id, message_id, reason) 持久化上下文
    2. Bot 以 exit code 42 退出，watcher 执行 git pull 并重启
    3. Bot 重启后调用 load_and_clear_pending_update() 获取上下文并发送完成通知
"""

import json
import logging
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

EXIT_CODE_SELF_UPDATE = 42

# 持久化文件路径：用于在更新重启后通知用户
PENDING_UPDATE_FILE = Path.home() / ".sailzen" / "pending_update.json"


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
        return {
            "success": True,
            "message": f"更新已触发，即将重启 (exit code {EXIT_CODE_SELF_UPDATE})",
        }

    def should_exit(self) -> bool:
        """主循环轮询：是否应该退出。"""
        with self._lock:
            return self._should_exit

    @property
    def exit_code(self) -> int:
        """获取退出码。"""
        with self._lock:
            return self._exit_code

    # ── 更新完成通知持久化 ─────────────────────────────────────────

    @staticmethod
    def save_pending_update(
        chat_id: str,
        message_id: Optional[str] = None,
        reason: str = "",
    ) -> None:
        """保存更新上下文到持久化文件，供重启后读取。

        Args:
            chat_id: 目标会话 ID（必需）
            message_id: 原卡片消息 ID（可选，用于更新原卡片）
            reason: 更新原因
        """
        try:
            PENDING_UPDATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data: Dict[str, Any] = {
                "chat_id": chat_id,
                "message_id": message_id,
                "reason": reason,
                "updated_at": datetime.now().isoformat(),
            }
            PENDING_UPDATE_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info(
                "[SelfUpdate] Pending update context saved for chat %s", chat_id
            )
        except Exception as exc:
            logger.warning(
                "[SelfUpdate] Failed to save pending update context: %s", exc
            )

    @staticmethod
    def load_and_clear_pending_update() -> Optional[Dict[str, Any]]:
        """加载并清除更新上下文。

        Returns:
            更新上下文字典，如果没有则返回 None
        """
        if not PENDING_UPDATE_FILE.exists():
            return None

        try:
            data = json.loads(PENDING_UPDATE_FILE.read_text(encoding="utf-8"))
            # 检查时间戳，超过 10 分钟的视为过期
            updated_at_str = data.get("updated_at", "")
            if updated_at_str:
                updated_at = datetime.fromisoformat(updated_at_str)
                if (datetime.now() - updated_at).total_seconds() > 600:
                    logger.info("[SelfUpdate] Pending update expired, ignoring")
                    PENDING_UPDATE_FILE.unlink(missing_ok=True)
                    return None

            PENDING_UPDATE_FILE.unlink(missing_ok=True)
            logger.info(
                "[SelfUpdate] Pending update context loaded for chat %s",
                data.get("chat_id"),
            )
            return data
        except Exception as exc:
            logger.warning(
                "[SelfUpdate] Failed to load pending update context: %s", exc
            )
            PENDING_UPDATE_FILE.unlink(missing_ok=True)
            return None

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
                capture_output=True,
                text=True,
                check=True,
            )
            return Path(result.stdout.strip())
        except Exception:
            return Path(__file__).parent.parent


def get_exit_code_for_restart() -> int:
    """Get the exit code that signals watcher to restart with update."""
    return EXIT_CODE_SELF_UPDATE
