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
    assert "sail_tick_messages" in tables
    assert "sail_tick_daily_reports" in tables
    # sailtick 隔离库（st_*）严禁出现在主库元数据中
    assert not any(t.startswith("st_") for t in tables)


def test_sailtick_service_unit_has_no_template_placeholder_and_valid_cli_order():
    """验证 scripts/sailtick.service 修复了 %I 模板误用、--config 参数顺序与 .env.prod 加载。"""
    unit_text = (Path(__file__).resolve().parents[2] / "scripts" / "sailtick.service").read_text(
        encoding="utf-8"
    )
    assert "%I" not in unit_text
    assert "EnvironmentFile=-/home/ubuntu/repos/SailZen/.env.prod" in unit_text
    assert "-m sailtick --config sailtick.yaml run" in unit_text


def test_sailtick_cli_accepts_config_before_and_after_subcommand():
    """验证 sailtick CLI 同时兼容 `--config X run` 和 `run --config X`。"""
    import subprocess
    import sys

    for args in (
        ["--config", "sailtick.yaml", "trigger", "--help"],
        ["trigger", "--config", "sailtick.yaml", "--help"],
    ):
        proc = subprocess.run(
            [sys.executable, "-m", "sailtick", *args],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr


def test_android_release_guardrails_reject_missing_config(monkeypatch, tmp_path):
    """验证 build_android_release.py 在缺少公网 URL 或正式签名配置时拒绝静默编译。"""
    from scripts.ops import build_android_release

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for k in (
        "SAILZEN_RELEASE_SERVER_URL",
        "SAILZEN_STORE_FILE",
        "SAILZEN_STORE_PASSWORD",
        "SAILZEN_KEY_ALIAS",
        "SAILZEN_KEY_PASSWORD",
    ):
        monkeypatch.delenv(k, raising=False)

    issues = build_android_release.check_release_guardrails()
    assert len(issues) == 2
    assert any("SAILZEN_RELEASE_SERVER_URL" in msg for msg in issues)
    assert any("签名配置" in msg for msg in issues)


def test_health_check_probes_cover_upgraded_health_and_tick_routes():
    from scripts.ops.health_check import CORE_READONLY_ENDPOINTS

    paths = {path for _, path in CORE_READONLY_ENDPOINTS}
    assert "/health/dashboard" in paths
    assert "/health/weight/plan" in paths
    assert "/health/diet" in paths
    assert "/tick/health-summary" in paths
    assert "/tick/reports" in paths
    assert "/tick/messages" in paths


def test_deploy_cloud_remote_site_build_sets_ci_and_site_filter(monkeypatch, tmp_path):
    """验证云端非交互 SSH 构建前端时设置 CI=true（避免 pnpm NO_TTY 报错）且限定 --filter=sail-site。"""
    from scripts.ops import deploy_cloud

    captured: list[str] = []

    def fake_ssh(cfg, cmd, **kwargs):
        captured.append(cmd)
        return None

    monkeypatch.setattr(deploy_cloud, "run_ssh_command", fake_ssh)
    cfg = _make_cfg(tmp_path, ops_vars={"OPS_SITE_BUILD_MODE": "remote"})
    swapped = deploy_cloud._deploy_site(cfg, site_build_mode="remote", dry_run=False)
    assert swapped is True
    assert len(captured) == 1
    assert "export CI=true" in captured[0]
    assert "--filter=sail-site" in captured[0]

def test_check_llm_keys_masking_and_placeholder_detection():
    from scripts.ops.check_llm_keys import is_placeholder_key, mask_api_key

    assert mask_api_key("") == "<unset>"
    assert mask_api_key("short") == "*****"
    assert mask_api_key("sk-kimi-1234567890abcd") == "sk-k...abcd"
    assert is_placeholder_key("sk-xxxxxxxxxxxxxxxx") is True
    assert is_placeholder_key("your-api-key") is True
    assert is_placeholder_key("sk-kimi-realkey1234") is False