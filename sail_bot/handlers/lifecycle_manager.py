# -*- coding: utf-8 -*-
# @file lifecycle_manager.py
# @brief Bot lifecycle management (startup, shutdown, cleanup)
# @author sailing-innocent
# @date 2026-04-25
# @version 2.0
# ---------------------------------
"""Bot lifecycle manager.

v2.0: 使用 sail.opencode.OpenCodeProcessManager 替代旧的 session_manager。

This module handles:
- Startup: State recovery, initial cleanup
- Shutdown: Graceful cleanup, notifications
- Cleanup: Process termination, resource release
- Notifications: Admin notifications on startup/shutdown
"""

import subprocess
import os
import signal
import sys
import platform
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sail_bot.session_state import SessionState

if TYPE_CHECKING:
    from sail_bot.agent import FeishuBotAgent


class LifecycleManager:
    """Manages the bot's lifecycle from startup to shutdown."""

    def __init__(self, agent: "FeishuBotAgent"):
        self.agent = agent

    def on_startup(self) -> None:
        """Handle bot startup including state recovery."""
        print("[Startup] 恢复会话状态...")

        # Validate project paths
        for p in self.agent.config.projects:
            path = p.get("path", "")
            if path:
                try:
                    resolved = Path(path).expanduser().resolve()
                    if not resolved.exists():
                        print(f"[Startup] 警告: 配置项目路径不存在: {path}")
                except Exception as e:
                    print(f"[Startup] 警告: 无法解析路径 {path}: {e}")

        # Process manager handles state recovery on init via _load_state()
        procs = self.agent.process_mgr.list_processes()
        running = [p for p in procs if p.status.value == "running"]
        if running:
            print(f"[Startup] 恢复了 {len(running)} 个运行中的进程")
        else:
            print("[Startup] 无运行中的进程需要恢复")

    def on_shutdown(self) -> None:
        """Handle bot shutdown including cleanup."""
        print("\n[Shutdown] Cleaning up resources...")

        # Send shutdown notification
        self._notify_shutdown()

        # Stop all agent processes
        count = self.agent.process_mgr.stop_all()
        if count:
            print(f"[Shutdown] 停止了 {count} 个 agent 进程")

        self.agent.state_store.save_to_disk()
        print("[Shutdown] Cleanup complete")

    def cleanup_previous_instances(self) -> None:
        """Cleanup zombie processes from previous instances."""
        print("\n[Cleanup] 检查之前遗留的进程...")

        killed_count = 0
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/V"],
                    capture_output=True, text=True, encoding="utf-8", errors="ignore",
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    for line in lines[1:]:
                        if "feishu_agent" in line.lower() or "opencode" in line.lower():
                            parts = line.strip('"').split('","')
                            if len(parts) >= 2:
                                pid = parts[1]
                                print(f"[Cleanup] 发现遗留进程 PID {pid}，正在终止...")
                                subprocess.run(
                                    ["taskkill", "/PID", pid, "/T", "/F"],
                                    check=False, capture_output=True,
                                )
                                killed_count += 1
            else:
                result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
                for line in result.stdout.split("\n"):
                    if "feishu_agent" in line.lower() or (
                        "python" in line.lower() and "opencode" in line.lower()
                    ):
                        parts = line.split()
                        if len(parts) >= 2:
                            pid = parts[1]
                            try:
                                os.kill(int(pid), signal.SIGTERM)
                                killed_count += 1
                            except Exception:
                                pass
        except Exception as e:
            print(f"[Cleanup] 进程检查失败: {e}")

        # Clean orphaned state entries
        config_paths = set()
        for p in self.agent.config.projects:
            if p.get("path"):
                try:
                    resolved = str(Path(p["path"]).expanduser().resolve())
                    config_paths.add(resolved)
                except Exception:
                    config_paths.add(p["path"])

        orphaned = 0
        for entry in list(self.agent.state_store.all_entries()):
            if entry.path not in config_paths:
                try:
                    if not Path(entry.path).exists():
                        self.agent.state_store.remove(entry.path)
                        orphaned += 1
                except Exception:
                    pass

        if killed_count > 0 or orphaned > 0:
            print(f"[Cleanup] 清理完成: 终止 {killed_count} 进程, 移除 {orphaned} 记录")
        else:
            print("[Cleanup] 未发现遗留资源")
        print()

    def _notify_startup(self) -> None:
        """Send startup notification to admin."""
        admin_chat_id = self.agent.config.admin_chat_id
        if not admin_chat_id or not self.agent.lark_client:
            return

        try:
            hostname = platform.node() or "Unknown"
            system = platform.system()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            procs = self.agent.process_mgr.list_processes()
            running_count = sum(1 for p in procs if p.status.value == "running")

            message = (
                f"🤖 **Feishu Bot 已启动**\n\n"
                f"📍 **主机**: {hostname}\n"
                f"🖥️ **系统**: {system}\n"
                f"🕐 **时间**: {now}\n\n"
                f"📊 **状态**: 运行中\n"
                f"💻 **会话数**: {running_count} 个运行中\n\n"
                f"✅ 机器人已就绪"
            )

            self.agent.messaging.send_text(admin_chat_id, message)
            print("[AdminNotify] 启动通知已发送")
        except Exception as exc:
            print(f"[AdminNotify] 启动通知失败: {exc}")

    def _notify_shutdown(self) -> None:
        """Send shutdown notification to admin."""
        admin_chat_id = self.agent.config.admin_chat_id
        if not admin_chat_id or not self.agent.lark_client:
            return

        try:
            hostname = platform.node() or "Unknown"
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            procs = self.agent.process_mgr.list_processes()
            running_count = sum(1 for p in procs if p.status.value == "running")

            message = (
                f"🛑 **Feishu Bot 已关闭**\n\n"
                f"📍 **主机**: {hostname}\n"
                f"🕐 **时间**: {now}\n\n"
                f"📊 **关闭前状态**:\n"
                f"💻 正在运行: {running_count} 个\n\n"
                f"⏹️ 机器人已停止"
            )

            self.agent.messaging.send_text(admin_chat_id, message)
            print("[AdminNotify] 关闭通知已发送")
        except Exception:
            pass
