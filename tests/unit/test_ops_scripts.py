# -*- coding: utf-8 -*-
# @file test_ops_scripts.py
# @brief Unit tests for SailZen DevOps scripts (config convergence, PG guardrails, backup pruning)
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""验证 scripts/ops/ 核心安全护栏、凭据收敛与备份清理逻辑。"""

import os
import time
from pathlib import Path

import pytest

from scripts.ops.backup_prod_db import backup_prod_database, prune_old_backups
from scripts.ops.common import (
    OpsConfig,
    assert_local_pg_target,
    mask_uri,
    parse_postgres_uri,
)
from scripts.ops.restore_local_db import restore_local_database


def _make_cfg(
    tmp_path: Path,
    *,
    ops_vars: dict | None = None,
    prod_vars: dict | None = None,
    dev_vars: dict | None = None,
) -> OpsConfig:
    return OpsConfig(
        ops_env_path=tmp_path / ".env.ops",
        prod_env_path=tmp_path / ".env.prod",
        dev_env_path=tmp_path / ".env.dev",
        ops_vars=ops_vars or {},
        prod_vars=prod_vars or {},
        dev_vars=dev_vars or {},
    )


def test_parse_postgres_uri_and_masking():
    uri = "postgresql+psycopg://sail_user:s3cr3t%40pwd@47.100.1.2:5433/main"
    info = parse_postgres_uri(uri)

    assert info.host == "47.100.1.2"
    assert info.port == 5433
    assert info.user == "sail_user"
    assert info.password == "s3cr3t@pwd"
    assert info.database == "main"
    assert not info.is_local

    # 密码绝不出现在脱敏 URI 或 CLI 参数中，仅通过 PGPASSWORD 环境变量传递
    assert "s3cr3t" not in info.masked_uri
    assert "s3cr3t" not in mask_uri(uri)
    cli_args = info.base_cli_args()
    assert all("s3cr3t" not in a for a in cli_args)
    assert info.to_pg_env({})["PGPASSWORD"] == "s3cr3t@pwd"


def test_local_pg_guardrail_blocks_remote_host():
    local_info = parse_postgres_uri("postgresql://postgres:pwd@127.0.0.1:5432/sailzen_dev")
    assert_local_pg_target(local_info)  # 不抛异常

    remote_info = parse_postgres_uri("postgresql://postgres:pwd@118.25.10.20:5432/main")
    with pytest.raises(RuntimeError, match="安全拦截"):
        assert_local_pg_target(remote_info)


def test_restore_local_database_blocks_remote_dev_uri(tmp_path: Path):
    dump_file = tmp_path / "prod_main_20261122_120000.dump"
    dump_file.write_bytes(b"PGDMP")

    cfg = _make_cfg(
        tmp_path,
        dev_vars={
            "DB_BACKEND": "postgres",
            "POSTGRE_URI": "postgresql://postgres:pwd@47.100.1.2:5432/main",
        },
    )
    with pytest.raises(RuntimeError, match="安全拦截"):
        restore_local_database(cfg, dump_path=dump_file, dry_run=True)


def test_ops_config_converges_credentials_from_env_prod(tmp_path: Path, monkeypatch):
    # 清除可能干扰的进程环境变量
    for key in ("OPS_SSH_HOST", "OPS_REMOTE_PUBLIC_URL", "OPS_BACKUP_MODE"):
        monkeypatch.delenv(key, raising=False)

    cfg = _make_cfg(
        tmp_path,
        ops_vars={"OPS_SSH_USER": "ubuntu"},
        prod_vars={
            "POSTGRE_URI": "postgresql://postgres:pwd@118.25.10.20:5432/main",
            "SERVER_PORT": "1974",
            "SAILZEN_API_TOKEN": "tok-secret-1234",
            "OPS_BACKUP_MODE": "ssh",
        },
        dev_vars={
            "POSTGRE_URI": "postgresql://postgres:localpwd@localhost:5432/sailzen_dev",
            "SERVER_PORT": "4399",
        },
    )

    # .env.ops 未设置 OPS_BACKUP_MODE 时自动兜底读取 .env.prod
    assert cfg.backup_mode == "ssh"
    # 未设置 OPS_SSH_HOST / OPS_REMOTE_PUBLIC_URL 时自动从 .env.prod 的 POSTGRE_URI 推导
    assert cfg.ssh_host == "118.25.10.20"
    assert cfg.get_server_url("prod") == "http://118.25.10.20:1974"
    assert cfg.get_server_url("dev") == "http://127.0.0.1:4399"
    assert cfg.get_api_token("prod") == "tok-secret-1234"


def test_prune_old_backups_keeps_at_least_three(tmp_path: Path):
    now = time.time()
    old_ts = now - 30 * 86400

    files = []
    for idx in range(5):
        f = tmp_path / f"prod_main_2026100{idx}_000000.dump"
        f.write_bytes(b"dump")
        ts = old_ts + idx * 60
        os.utime(f, (ts, ts))
        files.append(f)

    removed = prune_old_backups(tmp_path, keep_days=14)
    # 5 份全过期，但策略强制至少保留最新 3 份，因此只删除最旧的 2 份
    assert len(removed) == 2
    remaining = sorted(p.name for p in tmp_path.glob("prod_*.dump"))
    assert len(remaining) == 3
    assert files[4].name in remaining


def test_backup_prod_dry_run_does_not_write(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "scripts.ops.backup_prod_db.require_pg_binary",
        lambda tool, preferred_dir=None: Path(f"C:/mock/{tool}.exe"),
    )
    cfg = _make_cfg(
        tmp_path,
        ops_vars={"OPS_BACKUP_DIR": str(tmp_path / "backups"), "OPS_BACKUP_MODE": "direct"},
        prod_vars={"POSTGRE_URI": "postgresql://postgres:pwd@118.25.10.20:5432/main"},
    )
    out = backup_prod_database(cfg, dry_run=True)
    assert not out.exists()


def test_db_sync_covers_all_core_orm_tables():
    from scripts import db_sync

    tables = set(db_sync.get_table_names())
    # 确保新增模块（rhythm / reminder / tick）均被纳入 ORM 元数据
    assert "rhythm_affairs" in tables
    assert "reminders" in tables
    assert "sail_tick_tickets" in tables
    # sailtick 隔离库（st_*）严禁出现在主库元数据中
    assert not any(t.startswith("st_") for t in tables)
