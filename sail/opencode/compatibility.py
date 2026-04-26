# -*- coding: utf-8 -*-
# @file compatibility.py
# @brief CLI tool compatibility checker for opencode-compatible agent runtimes
# @author sailing-innocent
# @date 2026-04-25
# @version 1.0
# ---------------------------------
"""sail.opencode.compatibility — 检查命令行工具是否兼容 opencode serve API。

兼容性检查分为四个等级：
1. 命令存在性 — shutil.which
2. serve 子命令支持 — `{tool} serve --help`
3. 协议兼容性 — 启动临时进程，检查 /global/health
4. API 端点 — 验证 /session (POST/GET)、/event (GET SSE)

Usage::

    from sail.opencode.compatibility import check_cli_compatibility
    report = check_cli_compatibility("opencode-cli")
    if report.is_compatible:
        print("OK")
    else:
        print(report.to_text())
"""

from __future__ import annotations

import shutil
import subprocess
import socket
import time
import signal
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from sail.opencode.client import check_health_sync


@dataclass
class CompatibilityReport:
    """CLI 工具兼容性检查报告。"""

    tool: str
    found: bool = False
    serve_help_ok: bool = False
    health_ok: bool = False
    api_ok: bool = False
    errors: List[str] = field(default_factory=list)

    @property
    def is_compatible(self) -> bool:
        """是否完全兼容。"""
        return self.found and self.serve_help_ok and self.health_ok and self.api_ok

    def to_text(self) -> str:
        """生成人类可读的报告文本。"""
        lines = [f"=== Compatibility Report: {self.tool} ==="]
        lines.append(f"  Command found:      {'✅' if self.found else '❌'}")
        lines.append(f"  serve --help:       {'✅' if self.serve_help_ok else '❌'}")
        lines.append(f"  /global/health:     {'✅' if self.health_ok else '❌'}")
        lines.append(f"  API endpoints:      {'✅' if self.api_ok else '❌'}")
        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f"  • {err}")
        lines.append(f"\nResult: {'✅ Compatible' if self.is_compatible else '❌ Not compatible'}")
        return "\n".join(lines)


def _find_free_port() -> int:
    """找到一个可用端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _kill_process(pid: int) -> None:
    """终止指定 PID 的进程。"""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False, capture_output=True,
            )
        else:
            import os
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def check_cli_compatibility(
    cli_tool: str,
    port: int = 0,
    startup_timeout: float = 15.0,
    api_timeout: float = 5.0,
) -> CompatibilityReport:
    """检查指定 CLI 工具是否兼容 opencode serve API。

    Args:
        cli_tool: 命令名，如 "opencode-cli" 或 "kimix"
        port: 指定端口（0 则自动分配）
        startup_timeout: 启动等待超时（秒）
        api_timeout: API 测试超时（秒）

    Returns:
        CompatibilityReport
    """
    report = CompatibilityReport(tool=cli_tool)

    # Level 1: 命令存在性
    tool_path = shutil.which(cli_tool)
    if not tool_path:
        report.errors.append(f"Command '{cli_tool}' not found in PATH")
        return report
    report.found = True

    # Level 2: serve --help
    try:
        result = subprocess.run(
            [cli_tool, "serve", "--help"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if result.returncode != 0:
            report.errors.append(
                f"'{cli_tool} serve --help' exited with code {result.returncode}"
            )
            return report
        report.serve_help_ok = True
    except subprocess.TimeoutExpired:
        report.errors.append(f"'{cli_tool} serve --help' timed out")
        return report
    except Exception as exc:
        report.errors.append(f"'{cli_tool} serve --help' failed: {exc}")
        return report

    # Level 3 & 4: 启动临时进程并测试 API
    test_port = port or _find_free_port()
    proc: Optional[subprocess.Popen] = None
    try:
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE

        proc = subprocess.Popen(
            [cli_tool, "serve", "--hostname", "127.0.0.1", "--port", str(test_port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **kwargs,
        )

        # 等待 health 就绪
        t0 = time.monotonic()
        health_ok = False
        while time.monotonic() - t0 < startup_timeout:
            if check_health_sync(test_port, timeout=1.0):
                health_ok = True
                break
            time.sleep(0.5)

        if not health_ok:
            report.errors.append(
                f"Health check failed after {startup_timeout}s on port {test_port}"
            )
            return report
        report.health_ok = True

        # Level 4: API 端点测试
        base = f"http://127.0.0.1:{test_port}"
        with httpx.Client(timeout=api_timeout) as client:
            # GET /session
            try:
                resp = client.get(f"{base}/session")
                if resp.status_code != 200:
                    report.errors.append(f"GET /session returned {resp.status_code}")
                    return report
            except Exception as exc:
                report.errors.append(f"GET /session failed: {exc}")
                return report

            # POST /session
            try:
                resp = client.post(f"{base}/session", json={"title": "compat-test"})
                if resp.status_code not in (200, 201):
                    report.errors.append(f"POST /session returned {resp.status_code}")
                    return report
            except Exception as exc:
                report.errors.append(f"POST /session failed: {exc}")
                return report

            # GET /event (SSE 流，只检查能连接即可)
            try:
                with client.stream("GET", f"{base}/event", timeout=3.0) as stream:
                    # 读取前几行确认 SSE 流正常
                    line_count = 0
                    for line in stream.iter_lines():
                        line_count += 1
                        if line_count >= 3:
                            break
                    if line_count == 0:
                        report.errors.append("GET /event returned empty stream")
                        return report
            except Exception as exc:
                report.errors.append(f"GET /event failed: {exc}")
                return report

        report.api_ok = True

    except Exception as exc:
        report.errors.append(f"Unexpected error during API test: {exc}")
    finally:
        if proc is not None:
            _kill_process(proc.pid)
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()

    return report
