# -*- coding: utf-8 -*-
# @file lifecycle_manager.py
# @brief Bot lifecycle management (startup, shutdown, cleanup)
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Bot lifecycle manager.

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

from ..session_state import SessionState

if TYPE_CHECKING:
    from ..agent import FeishuBotAgent


class LifecycleManager:
    """Manages the bot's lifecycle from startup to shutdown."""

    def __init__(self, agent: "FeishuBotAgent"):
        self.agent = agent

    def on_startup(self) -> None:
        """Handle bot startup including state recovery."""
        print("[Startup] 恢复会话状态...")

        # Validate project paths
        valid_projects = []
        for p in self.agent.config.projects:
            path = p.get("path", "")
            if not path:
                continue
            try:
                resolved = Path(path).expanduser().resolve()
                if resolved.exists():
                    valid_projects.append(str(resolved))
                else:
                    print(f"[Startup] 警告: 配置项目路径不存在: {path}")
            except Exception as e:
                print(f"[Startup] 警告: 无法解析路径 {path}: {e}")

        # Recover session states
        recovered_count = 0
        error_count = 0

        for entry in self.agent.state_store.all_entries():
            path = entry.path

            # Check if path is in valid config
            if path not in valid_projects:
                try:
                    if not Path(path).exists():
                        print(f"[Startup] 跳过不在配置中的路径: {path}")
                        self.agent.state_store.force_set(
                            path,
                            SessionState.ERROR,
                            last_error="Path not in configuration",
                        )
                        error_count += 1
                        continue
                except Exception:
                    pass

            if entry.state in (
                SessionState.RUNNING,
                SessionState.STARTING,
            ):
                session = self.agent.session_mgr._sessions.get(path)
                port = entry.port or (session.port if session else None)
                if port and self.agent.session_mgr._is_port_open(port):
                    print(f"[Startup] Reconnected to {path} on port {port}")
                    if session:
                        session.process_status = "running"
                    recovered_count += 1
                else:
                    print(f"[Startup] Cannot recover {path}, marking error")
                    self.agent.state_store.force_set(
                        path,
                        SessionState.ERROR,
                        last_error="Process not found on startup",
                    )
                    error_count += 1

        if recovered_count > 0 or error_count > 0:
            print(
                f"[Startup] 状态恢复完成: {recovered_count} 个成功, {error_count} 个失败"
            )

    def on_shutdown(self) -> None:
        """Handle bot shutdown including cleanup."""
        print("\n[Shutdown] Cleaning up resources...")

        # Send shutdown notification
        self._notify_shutdown()

        self.agent._health_monitor.stop()

        # Stop async task manager
        from ..async_task_manager import task_manager

        task_manager.stop()
        print("[Shutdown] Async task manager stopped")

        # Stop all sessions
        sessions = self.agent.session_mgr.list_sessions()
        for s in sessions:
            if s.process_status in ("running", "starting"):
                print(f"[Shutdown] Stopping {s.path}")
                self.agent.session_mgr.stop_session(s.path)

        # Clean up file handles
        for s in sessions:
            if s._stdout_log or s._stderr_log:
                print(f"[Shutdown] Cleaning up file handles for {s.path}")
                if s._stdout_log:
                    try:
                        s._stdout_log.close()
                    except Exception:
                        pass
                    s._stdout_log = None
                if s._stderr_log:
                    try:
                        s._stderr_log.close()
                    except Exception:
                        pass
                    s._stderr_log = None

        self.agent.state_store.save_to_disk()
        print("[Shutdown] Cleanup complete")

    def cleanup_previous_instances(self) -> None:
        """Cleanup zombie processes from previous instances."""
        print("\n[Cleanup] 检查之前遗留的进程和文件句柄...")

        killed_count = 0
        try:
            if sys.platform == "win32":
                # Windows: Use tasklist and taskkill
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/V"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                )

                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    for line in lines[1:]:  # Skip header
                        if "feishu_agent" in line.lower() or "opencode" in line.lower():
                            parts = line.strip('"').split('","')
                            if len(parts) >= 2:
                                pid = parts[1]
                                print(f"[Cleanup] 发现遗留进程 PID {pid}，正在终止...")
                                subprocess.run(
                                    ["taskkill", "/PID", pid, "/T", "/F"],
                                    check=False,
                                    capture_output=True,
                                )
                                killed_count += 1
            else:
                # Linux/Mac: Use ps and kill
                result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
                for line in result.stdout.split("\n"):
                    if "feishu_agent" in line.lower() or (
                        "python" in line.lower() and "opencode" in line.lower()
                    ):
                        parts = line.split()
                        if len(parts) >= 2:
                            pid = parts[1]
                            print(f"[Cleanup] 发现遗留进程 PID {pid}，正在终止...")
                            try:
                                os.kill(int(pid), signal.SIGTERM)
                                killed_count += 1
                            except Exception as e:
                                print(f"[Cleanup] 终止失败: {e}")
        except Exception as e:
            print(f"[Cleanup] 进程检查失败: {e}")

        # Clear ports
        port_cleared = 0
        base_port = self.agent.config.base_port
        for port in range(base_port, base_port + 20):
            if self.agent.session_mgr._is_port_open(port):
                print(f"[Cleanup] 端口 {port} 被占用，尝试释放...")
                try:
                    if sys.platform == "win32":
                        result = subprocess.run(
                            ["netstat", "-ano", "|", "findstr", f":{port}"],
                            capture_output=True,
                            text=True,
                            shell=True,
                        )
                        if result.stdout:
                            for line in result.stdout.split("\n"):
                                parts = line.strip().split()
                                if len(parts) >= 5:
                                    pid = parts[-1]
                                    print(
                                        f"[Cleanup] 终止占用端口 {port} 的进程 PID {pid}"
                                    )
                                    subprocess.run(
                                        ["taskkill", "/PID", pid, "/F"],
                                        check=False,
                                        capture_output=True,
                                    )
                                    port_cleared += 1
                    else:
                        result = subprocess.run(
                            ["lsof", "-ti", f":{port}"], capture_output=True, text=True
                        )
                        if result.stdout:
                            pid = result.stdout.strip()
                            print(f"[Cleanup] 终止占用端口 {port} 的进程 PID {pid}")
                            os.kill(int(pid), signal.SIGKILL)
                            port_cleared += 1
                except Exception as e:
                    print(f"[Cleanup] 端口 {port} 释放失败: {e}")

        # Clean invalid sessions
        invalid_sessions = 0
        for entry in list(self.agent.state_store.all_entries()):
            if entry.state in (
                SessionState.RUNNING,
                SessionState.STARTING,
            ):
                port = entry.port
                if port and not self.agent.session_mgr._is_port_open(port):
                    print(f"[Cleanup] 清理无效会话状态: {entry.path}")
                    self.agent.state_store.force_set(
                        entry.path,
                        SessionState.ERROR,
                        last_error="Process terminated during cleanup",
                    )
                    invalid_sessions += 1

        # Clean orphaned entries
        config_paths = set()
        for p in self.agent.config.projects:
            if p.get("path"):
                try:
                    resolved = str(Path(p["path"]).expanduser().resolve())
                    config_paths.add(resolved)
                except Exception:
                    config_paths.add(p["path"])

        orphaned_entries = 0
        for entry in list(self.agent.state_store.all_entries()):
            if entry.path not in config_paths:
                path_exists = False
                try:
                    path_exists = Path(entry.path).exists()
                except Exception:
                    pass

                if not path_exists:
                    print(f"[Cleanup] 清理孤立状态记录: {entry.path}")
                    self.agent.state_store.remove(entry.path)
                    orphaned_entries += 1

        total_cleaned = (
            killed_count + port_cleared + invalid_sessions + orphaned_entries
        )
        if total_cleaned > 0:
            print(
                f"[Cleanup] 清理完成: 终止 {killed_count} 进程, 释放 {port_cleared} 端口, "
                f"清理 {invalid_sessions} 会话, 移除 {orphaned_entries} 记录"
            )
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

            sessions = self.agent.session_mgr.list_sessions()
            running_count = sum(1 for s in sessions if s.process_status == "running")

            message = (
                f"🤖 **Feishu Bot 已启动**\n\n"
                f"📍 **主机**: {hostname}\n"
                f"🖥️ **系统**: {system}\n"
                f"🕐 **时间**: {now}\n\n"
                f"📊 **状态**: 运行中\n"
                f"💻 **会话数**: {running_count} 个运行中\n\n"
                f"✅ 机器人已就绪"
            )

            self.agent._send_to_chat(admin_chat_id, message)
            print(f"[AdminNotify] 启动通知已发送")
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

            sessions = self.agent.session_mgr.list_sessions()
            running_count = sum(1 for s in sessions if s.process_status == "running")

            message = (
                f"🛑 **Feishu Bot 已关闭**\n\n"
                f"📍 **主机**: {hostname}\n"
                f"🕐 **时间**: {now}\n\n"
                f"📊 **关闭前状态**:\n"
                f"💻 正在运行: {running_count} 个\n\n"
                f"⏹️ 机器人已停止"
            )

            self.agent._send_to_chat(admin_chat_id, message)
            print(f"[AdminNotify] 关闭通知已发送")
        except Exception:
            pass
