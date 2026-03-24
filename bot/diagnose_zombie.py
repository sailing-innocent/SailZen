#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file diagnose_zombie.py
# @brief 诊断并清理僵尸进程和文件句柄
# @author opencode
# @date 2026-03-24
# ---------------------------------
"""
诊断脚本：检查并清理飞书机器人相关的僵尸进程和文件句柄

使用方法:
    uv run bot/diagnose_zombie.py
"""

import subprocess
import sys
import os
from pathlib import Path


def check_python_processes():
    """检查所有Python进程，特别是feishu_agent相关的进程"""
    print("=" * 60)
    print("正在检查 Python 进程...")
    print("=" * 60)

    if sys.platform == "win32":
        # Windows: 使用 tasklist 和 findstr
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/V"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            print(f"找到 {len(lines) - 1} 个 Python 进程：")

            feishu_pids = []
            for line in lines[1:]:  # 跳过标题行
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    pid = parts[1]
                    cmd_line = line

                    # 检查是否是feishu_agent相关
                    if "feishu" in line.lower() or "opencode" in line.lower():
                        print(f"\n⚠️  可能的飞书机器人进程:")
                        print(f"   PID: {pid}")
                        feishu_pids.append(pid)

            return feishu_pids
        else:
            print(f"获取进程列表失败: {result.stderr}")
            return []
    else:
        # Linux/Mac: 使用 ps 命令
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

        feishu_pids = []
        for line in result.stdout.split("\n"):
            if "feishu_agent" in line.lower() or (
                "python" in line.lower() and "opencode" in line.lower()
            ):
                parts = line.split()
                if len(parts) >= 2:
                    pid = parts[1]
                    print(f"⚠️  发现进程: PID={pid}")
                    print(f"   {line}")
                    feishu_pids.append(pid)

        return feishu_pids


def check_open_files():
    """检查打开的文件句柄（特别是日志文件）"""
    print("\n" + "=" * 60)
    print("正在检查日志文件...")
    print("=" * 60)

    log_dir = Path.home() / ".config" / "feishu-agent" / "logs"

    if log_dir.exists():
        log_files = list(log_dir.glob("*.log"))
        print(f"日志目录: {log_dir}")
        print(f"日志文件数量: {len(log_files)}")

        for log_file in log_files:
            size = log_file.stat().st_size
            print(f"  - {log_file.name}: {size} bytes")

        return log_files
    else:
        print(f"日志目录不存在: {log_dir}")
        return []


def check_network_ports():
    """检查网络端口占用"""
    print("\n" + "=" * 60)
    print("正在检查网络端口占用...")
    print("=" * 60)

    if sys.platform == "win32":
        result = subprocess.run(
            ["netstat", "-ano", "|", "findstr", ":4096"],
            capture_output=True,
            text=True,
            shell=True,
            encoding="utf-8",
            errors="ignore",
        )
    else:
        result = subprocess.run(["lsof", "-i", ":4096"], capture_output=True, text=True)

    if result.stdout:
        print("端口 4096 及其附近的占用情况:")
        print(result.stdout)
    else:
        print("端口 4096 未被占用")


def kill_zombie_processes(pids):
    """杀死僵尸进程"""
    if not pids:
        print("\n✅ 没有发现僵尸进程")
        return

    print("\n" + "=" * 60)
    print("正在清理僵尸进程...")
    print("=" * 60)

    for pid in pids:
        print(f"终止进程 PID {pid}...")
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", pid, "/T", "/F"],
                    check=False,
                    capture_output=True,
                )
            else:
                os.kill(int(pid), 9)
            print(f"  ✅ PID {pid} 已终止")
        except Exception as e:
            print(f"  ❌ 终止失败: {e}")


def main():
    print("🔍 飞书机器人僵尸进程诊断工具")
    print("=" * 60)

    # 检查Python进程
    feishu_pids = check_python_processes()

    # 检查日志文件
    log_files = check_open_files()

    # 检查网络端口
    check_network_ports()

    # 总结
    print("\n" + "=" * 60)
    print("诊断总结:")
    print("=" * 60)

    if feishu_pids:
        print(f"⚠️  发现 {len(feishu_pids)} 个可能的僵尸进程")
        print("\n建议操作:")
        print("1. 手动重启机器人前运行此脚本清理")
        print("2. 或直接使用以下命令清理:")
        print(f"   uv run python bot/diagnose_zombie.py --kill")

        # 询问是否清理
        response = input("\n是否立即清理这些进程? [y/N]: ")
        if response.lower() == "y":
            kill_zombie_processes(feishu_pids)
            print("\n✅ 清理完成")
            print("现在可以安全地启动新的飞书机器人实例")
        else:
            print("\n跳过清理")
    else:
        print("✅ 没有发现僵尸进程")

    if len(log_files) > 10:
        print(f"\n⚠️  警告: 日志文件数量较多 ({len(log_files)} 个)")
        print("建议定期清理日志文件以释放磁盘空间")


if __name__ == "__main__":
    main()
