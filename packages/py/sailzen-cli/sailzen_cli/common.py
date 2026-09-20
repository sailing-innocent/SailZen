# -*- coding: utf-8 -*-
# @file common.py
# @brief Shared helpers for sailzen-cli commands
# @author sailing-innocent
# @date 2026-09-20
# @version 2.0
# ---------------------------------

from __future__ import annotations

import os

import click


# ============================================================================
# Environment / Server URL Resolution
# ============================================================================

def _load_env_file(env_path: str) -> dict:
    """手动解析 .env 文件（不依赖 python-dotenv）"""
    env = {}
    if not os.path.isfile(env_path):
        return env
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                env[key] = value
    return env


def _resolve_default_server_url() -> str:
    """
    解析默认服务器地址。
    优先级：
      1. SAIL_SERVER_URL 环境变量
      2. .env.prod / .env.dev 中的 SERVER_HOST + SERVER_PORT
      3. http://localhost:8000
    """
    env_url = os.environ.get("SAIL_SERVER_URL")
    if env_url:
        return env_url

    cwd = os.getcwd()
    for env_name in (".env.prod", ".env.dev", ".env"):
        env_path = os.path.join(cwd, env_name)
        if os.path.isfile(env_path):
            env = _load_env_file(env_path)
            host = env.get("SERVER_HOST", "localhost")
            port = env.get("SERVER_PORT", "8000")
            return f"http://{host}:{port}"

    return "http://localhost:8000"


# ============================================================================
# Constants
# ============================================================================

DEFAULT_PAGE_SIZE = 100  # 每页拉取数量（API 最大 100）
API_TIMEOUT = 30  # HTTP 请求超时（秒）
REQUEST_DELAY = 0.1  # 请求间隔（秒），避免打爆服务器


# ============================================================================
# Click option helpers
# ============================================================================

def server_option(f):
    return click.option(
        "--server",
        default=lambda: os.environ.get("SAIL_SERVER_URL", _resolve_default_server_url()),
        show_default="from SAIL_SERVER_URL / .env / localhost:8000",
        help="sail_server 地址 (环境变量: SAIL_SERVER_URL)",
    )(f)
