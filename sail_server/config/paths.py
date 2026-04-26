# -*- coding: utf-8 -*-
# @file paths.py
# @brief Unified data directory configuration for SailZen Server
# @author sailing-innocent
# @date 2026-04-13
# @version 1.0
# ---------------------------------
#
# 所有 sail_server 内的文件/数据资源路径都应该通过此模块获取，
# 而不是使用 __file__ 相对路径或硬编码路径。
#
# 环境变量:
#   SERVER_DATA_DIR  — 服务器数据根目录 (默认: data)
#
# 用法:
#   from sail_server.config.paths import (
#       SERVER_DATA_DIR,
#       get_data_path,
#       PIPELINES_DIR,
#       FILE_STORAGE_DIR,
#       CONTROL_PLANE_DIR,
#       SQLITE_DB_PATH,
#   )
# ---------------------------------

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# 核心: 统一数据根目录
# ---------------------------------------------------------------------------
# 优先从环境变量 SERVER_DATA_DIR 读取；未设置时默认为项目根下的 "data" 目录
SERVER_DATA_DIR: Path = Path(os.environ.get("SERVER_DATA_DIR", "data")).resolve()


def get_data_path(*parts: str) -> Path:
    """基于 SERVER_DATA_DIR 拼接子路径，并确保父目录存在。

    Examples:
        get_data_path("pipelines")           -> <SERVER_DATA_DIR>/pipelines
    """
    p = SERVER_DATA_DIR.joinpath(*parts)
    return p


def ensure_data_path(*parts: str) -> Path:
    """同 get_data_path，但会自动创建父目录。"""
    p = get_data_path(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def ensure_data_dir(*parts: str) -> Path:
    """基于 SERVER_DATA_DIR 拼接子目录路径，并确保目录存在。"""
    p = SERVER_DATA_DIR.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# 预定义的常用路径
# ---------------------------------------------------------------------------

# DAG Pipeline 定义文件目录
PIPELINES_DIR: Path = SERVER_DATA_DIR / "pipelines"

# 文件存储目录 (如果环境变量 FILE_STORAGE_PATH 存在则优先使用，保持向后兼容)
FILE_STORAGE_DIR: Path = Path(
    os.environ.get("FILE_STORAGE_PATH", str(SERVER_DATA_DIR / "file_storage"))
).resolve()

# SQLite 数据库文件路径
SQLITE_DB_PATH: Path = Path(
    os.environ.get("SQLITE_PATH", str(SERVER_DATA_DIR / "sailzen.db"))
).resolve()


