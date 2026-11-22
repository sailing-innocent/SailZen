# -*- coding: utf-8 -*-
# @file doctor.py
# @brief Environment and DevOps readiness diagnostic for SailZen
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""双环境运维体检工具。

用法:
    uv run python scripts/ops/doctor.py
    uv run python scripts/ops/doctor.py --check-remote    # 额外探测生产 PG 连通性与 SSH 免密登录
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops.common import (
    OpsConfig,
    PgConnInfo,
    configure_console_utf8,
    find_pg_binary,
    get_pg_binary_version,
    load_ops_config,
    mask_secret,
    run_ssh_command,
)


def _check_pg_connection(psql_bin: Path, pg_info: PgConnInfo) -> Tuple[bool, str]:
    """只读执行 SELECT version() 验证 PostgreSQL 连通性。"""
    cmd = [
        str(psql_bin),
        *pg_info.base_cli_args(),
        "-t",
        "-A",
        "-c",
        "SELECT version();",
    ]
    env = pg_info.to_pg_env()
    env["PGCONNECT_TIMEOUT"] = "8"
    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
        )
    except subprocess.TimeoutExpired:
        return False, "连接超时 (12s)"
    except Exception as exc:
        return False, str(exc)

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, err[0] if err else f"exit={proc.returncode}"

    ver_line = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else "connected"
    return True, ver_line


def run_doctor(cfg: OpsConfig, check_remote: bool = False) -> int:
    rows: List[Tuple[str, str, str]] = []
    warnings = 0
    errors = 0

    def add(status: str, item: str, detail: str) -> None:
        nonlocal warnings, errors
        if status == "WARN":
            warnings += 1
        elif status == "FAIL":
            errors += 1
        rows.append((status, item, detail))

    # 1. 环境配置文件检查
    if cfg.ops_env_path.is_file():
        add("OK", ".env.ops", f"已加载 ({len(cfg.ops_vars)} 项)")
    else:
        add("WARN", ".env.ops", "未创建（可 Copy-Item .env.ops.template .env.ops；当前使用默认/兜底配置）")

    if cfg.dev_env_path.is_file():
        dev_backend = cfg.dev_vars.get("DB_BACKEND", "postgres")
        add("OK", cfg.dev_env_path.name, f"已加载 (DB_BACKEND={dev_backend})")
    else:
        add("FAIL", cfg.dev_env_path.name, "不存在，请从 .env.template 复制")

    if cfg.prod_env_path.is_file():
        tok = mask_secret(cfg.prod_vars.get("SAILZEN_API_TOKEN", ""))
        add("OK", cfg.prod_env_path.name, f"已加载 (SAILZEN_API_TOKEN={tok})")
    else:
        add("WARN", cfg.prod_env_path.name, "不存在，云端备份与体检将缺少 POSTGRE_URI")

    # 2. 本机工具链检查
    for tool in ("uv", "pnpm", "git", "ssh", "scp"):
        hit = shutil.which(tool)
        if hit:
            add("OK", f"CLI:{tool}", hit)
        else:
            add("WARN" if tool in {"ssh", "scp"} else "FAIL", f"CLI:{tool}", "未在 PATH 找到")

    # 3. PostgreSQL / pgAdmin4 客户端工具探测
    psql_bin = None
    for tool in ("pg_dump", "pg_restore", "psql"):
        found = find_pg_binary(tool, preferred_dir=cfg.pg_bin_dir)
        if found:
            ver = get_pg_binary_version(found)
            add("OK", f"PG:{tool}", f"{found} [{ver}]")
            if tool == "psql":
                psql_bin = found
        else:
            add("FAIL", f"PG:{tool}", "未找到（请安装 PostgreSQL / pgAdmin 4 或配置 OPS_PG_BIN_DIR）")

    # 4. 本地调试库配置与安全检查
    dev_pg = None
    try:
        dev_pg = cfg.get_dev_pg()
        if dev_pg.is_local:
            add("OK", "本地调试库 (.env.dev)", f"{dev_pg.masked_uri} [安全: 本机地址]")
        else:
            add(
                "FAIL",
                "本地调试库 (.env.dev)",
                f"{dev_pg.masked_uri} [危险: 非本机地址！restore_local_db 将拦截]",
            )
    except Exception as exc:
        add("WARN", "本地调试库 (.env.dev)", str(exc))

    # 5. 生产库配置检查（不连库，仅校验配置解析）
    prod_pg = None
    try:
        prod_pg = cfg.get_prod_pg()
        if prod_pg.is_local:
            add("WARN", "生产库 (.env.prod)", f"{prod_pg.masked_uri} [提示: 指向本机，若是开发机请确认]")
        else:
            add("OK", "生产库 (.env.prod)", f"{prod_pg.masked_uri} (backup_mode={cfg.backup_mode})")
    except Exception as exc:
        add("WARN", "生产库 (.env.prod)", str(exc))

    # 6. 可选：本机 PG 连通性测试
    if psql_bin and dev_pg and dev_pg.is_local:
        ok, msg = _check_pg_connection(psql_bin, dev_pg)
        add("OK" if ok else "WARN", "连通性: 本地 PG", msg)

    # 7. 可选：远端只读连通性测试（--check-remote）
    if check_remote:
        if psql_bin and prod_pg:
            ok, msg = _check_pg_connection(psql_bin, prod_pg)
            add("OK" if ok else "FAIL", "连通性: 生产 PG (只读)", msg)

        if cfg.ssh_host:
            try:
                proc = run_ssh_command(cfg, "echo ok && hostname", timeout=15)
                out = " / ".join(line.strip() for line in proc.stdout.splitlines() if line.strip())
                add("OK", f"连通性: SSH ({cfg.ssh_host})", out or "connected")
            except Exception as exc:
                add("FAIL", f"连通性: SSH ({cfg.ssh_host})", str(exc).splitlines()[0])
        else:
            add("WARN", "连通性: SSH", "未配置 OPS_SSH_HOST，跳过 SSH 探测")
    else:
        ssh_hint = cfg.ssh_host or "<未配置>"
        add(
            "OK",
            "SSH 目标配置",
            f"host={ssh_hint}, repo={cfg.remote_repo}, service={cfg.remote_server_service}（加 --check-remote 实测）",
        )

    # 输出表格
    print("\n=== SailZen DevOps Doctor ===\n")
    for status, item, detail in rows:
        tag = {"OK": "[OK]  ", "WARN": "[WARN]", "FAIL": "[FAIL]"}[status]
        print(f"{tag} {item:<24} {detail}")

    print(f"\nSummary: {len(rows)} checks, {warnings} warning(s), {errors} failure(s).")
    if not cfg.ops_env_path.is_file():
        print("Tip: 复制模板开始配置自动化部署 -> Copy-Item .env.ops.template .env.ops")
    return 1 if errors > 0 else 0


def main() -> int:
    configure_console_utf8()
    parser = argparse.ArgumentParser(description="SailZen 双环境运维诊断工具")
    parser.add_argument("--ops-env", default=None, help="指定运维配置文件路径（默认 .env.ops）")
    parser.add_argument(
        "--check-remote",
        action="store_true",
        help="实测生产 PostgreSQL 只读连通性与云端 SSH 免密登录",
    )
    args = parser.parse_args()
    cfg = load_ops_config(args.ops_env)
    return run_doctor(cfg, check_remote=args.check_remote)


if __name__ == "__main__":
    raise SystemExit(main())
