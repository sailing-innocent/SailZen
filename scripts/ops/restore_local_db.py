# -*- coding: utf-8 -*-
# @file restore_local_db.py
# @brief Reconstruct local PostgreSQL debug database from a production snapshot
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""从生产快照重构并覆盖本地 PostgreSQL 调试库（默认 .env.dev 指向的本机库）。

核心能力：
1. 随时覆盖更新：
   - 默认直接用最新本地快照快速覆盖本机调试库（秒级完成）；
   - 加 --pull 可先从云端只读拉取最新快照，再一键覆盖本地调试库。
2. 硬性安全护栏：
   - 目标库配置严格读取自 .env.dev 的 POSTGRE_URI；
   - 强制校验目标 Host 必须为 localhost / 127.0.0.1 / ::1，严禁覆盖任何远端库！
3. 还原收尾闭环：
   - 自动断开残留连接并 DROP + CREATE 重建本地库（或 --no-recreate 原地清空）；
   - 支持并行 pg_restore (-j) 加速导入；
   - 自动执行 public 全表自增序列（serial/identity）修复，杜绝 key-id already exists；
   - 默认运行 sail_server 幂等 SQL 迁移自检并打印核心业务表行数核验。

用法:
    uv run python scripts/ops/restore_local_db.py                  # 用最新快照快速覆盖本地调试库
    uv run python scripts/ops/restore_local_db.py --pull           # 先从云端拉最新快照，再覆盖本地调试库
    uv run python scripts/ops/restore_local_db.py --dump path.dump # 指定快照文件覆盖
    uv run python scripts/ops/restore_local_db.py --dry-run        # 仅预览不执行
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops.backup_prod_db import LATEST_POINTER_FILE, backup_prod_database
from scripts.ops.common import (
    OpsConfig,
    PgConnInfo,
    assert_local_pg_target,
    configure_console_utf8,
    format_bytes,
    load_ops_config,
    require_pg_binary,
)

SEQUENCE_REPAIR_SQL = """
DO $$
DECLARE
    rec RECORD;
    max_val BIGINT;
BEGIN
    FOR rec IN
        SELECT
            n.nspname AS schema_name,
            c.relname AS table_name,
            a.attname AS column_name,
            pg_get_serial_sequence(format('%I.%I', n.nspname, c.relname), a.attname) AS seq_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE c.relkind = 'r'
          AND n.nspname = 'public'
          AND a.attnum > 0
          AND NOT a.attisdropped
    LOOP
        IF rec.seq_name IS NOT NULL THEN
            EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %I.%I', rec.column_name, rec.schema_name, rec.table_name)
                INTO max_val;
            IF max_val > 0 THEN
                EXECUTE format('SELECT setval(%L, %s, true)', rec.seq_name, max_val);
            ELSE
                EXECUTE format('SELECT setval(%L, 1, false)', rec.seq_name);
            END IF;
        END IF;
    END LOOP;
END $$;
""".strip()


def resolve_latest_dump(cfg: OpsConfig, explicit_dump: Optional[Path]) -> Path:
    """定位待还原的 .dump 文件：优先显式参数，其次 LATEST_PROD_DUMP.txt，再次按时间倒序查找。"""
    if explicit_dump is not None:
        resolved = explicit_dump.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"指定的备份文件不存在: {resolved}")
        return resolved

    backup_dir = cfg.backup_dir
    pointer = backup_dir / LATEST_POINTER_FILE
    if pointer.is_file():
        candidate_raw = pointer.read_text(encoding="utf-8").strip()
        if candidate_raw:
            candidate = Path(candidate_raw)
            if not candidate.is_absolute():
                candidate = (backup_dir / candidate).resolve()
            if candidate.is_file():
                return candidate

    if backup_dir.is_dir():
        dumps = sorted(
            backup_dir.glob("prod_*.dump"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if dumps:
            return dumps[0]

    raise FileNotFoundError(
        f"未在 {backup_dir} 找到可用备份文件。请先运行: uv run python scripts/ops/backup_prod_db.py"
    )


def _run_psql_sql(psql_bin: Path, pg_info: PgConnInfo, sql: str, *, database: str) -> None:
    cmd = [
        str(psql_bin),
        *pg_info.base_cli_args(database=database),
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
    ]
    proc = subprocess.run(
        cmd,
        env=pg_info.to_pg_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"psql 执行失败 (db={database}): {detail}")


def _recreate_local_database(psql_bin: Path, dev_pg: PgConnInfo) -> None:
    """断开目标库连接并 DROP + CREATE 本地调试库。"""
    db_ident = dev_pg.database.replace('"', '""')
    db_literal = dev_pg.database.replace("'", "''")

    terminate_sql = (
        "SELECT pg_terminate_backend(pid) "
        f"FROM pg_stat_activity WHERE datname = '{db_literal}' AND pid <> pg_backend_pid();"
    )
    _run_psql_sql(psql_bin, dev_pg, terminate_sql, database="postgres")
    _run_psql_sql(psql_bin, dev_pg, f'DROP DATABASE IF EXISTS "{db_ident}";', database="postgres")
    _run_psql_sql(
        psql_bin,
        dev_pg,
        f'CREATE DATABASE "{db_ident}" WITH ENCODING \'UTF8\';',
        database="postgres",
    )


def _run_local_migrations(cfg: OpsConfig) -> None:
    """在子进程中以 .env.dev 配置运行 sail_server 幂等 SQL 迁移与 ORM 补表。"""
    code = (
        "from sail.utils import read_env; "
        "read_env('dev'); "
        "from sail_server.db import Database; "
        "Database.get_instance(); "
        "print('[Migration] Local dev DB schema & migrations verified')"
    )
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"本地迁移自检失败: {detail}")
    for line in proc.stdout.splitlines():
        if line.strip():
            print(f"  {line}")


def _print_local_db_summary(psql_bin: Path, dev_pg: PgConnInfo) -> None:
    """查询并打印本地调试库表数量与核心业务表行数，确认快照覆盖成功。"""
    summary_sql = """
    SELECT
        c.relname AS table_name,
        (xpath('/row/cnt/text()', query_to_xml(format('SELECT count(*) AS cnt FROM %I.%I', n.nspname, c.relname), false, true, '')))[1]::text::int AS row_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r' AND n.nspname = 'public'
    ORDER BY row_count DESC, c.relname ASC;
    """
    cmd = [
        str(psql_bin),
        *dev_pg.base_cli_args(),
        "-t",
        "-A",
        "-F",
        "|",
        "-c",
        summary_sql,
    ]
    proc = subprocess.run(
        cmd,
        env=dev_pg.to_pg_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0:
        return
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.strip().split("|")
        if len(parts) == 2 and parts[1].isdigit():
            rows.append((parts[0], int(parts[1])))
    if not rows:
        return
    total_rows = sum(cnt for _, cnt in rows)
    top_preview = ", ".join(f"{name}={cnt}" for name, cnt in rows[:8])
    print(f"[Restore] 数据核验: 共 {len(rows)} 张表, 累计 {total_rows} 行")
    print(f"[Restore] Top 表行数: {top_preview}")


def restore_local_database(
    cfg: OpsConfig,
    *,
    dump_path: Optional[Path] = None,
    pull_from_prod: bool = False,
    backup_mode: Optional[str] = None,
    recreate_db: bool = True,
    jobs: int = 4,
    skip_migrations: bool = False,
    dry_run: bool = False,
) -> Path:
    """将生产 dump 还原覆盖至 .env.dev 指向的本地 PostgreSQL 调试库。"""
    dev_pg = cfg.get_dev_pg()
    # 硬护栏：绝不允许覆盖任何非本机数据库
    assert_local_pg_target(dev_pg)

    if pull_from_prod:
        print("[Restore] 0/4 先从云端生产库只读拉取最新快照...")
        pulled = backup_prod_database(cfg, mode=backup_mode, dry_run=dry_run)
        if dry_run:
            print(f"[DryRun] 将使用刚拉取的快照覆盖本地库: {dev_pg.masked_uri}")
            return pulled
        dump_path = pulled

    resolved_dump = resolve_latest_dump(cfg, dump_path)
    psql_bin = require_pg_binary("psql", preferred_dir=cfg.pg_bin_dir)
    pg_restore_bin = require_pg_binary("pg_restore", preferred_dir=cfg.pg_bin_dir)

    print(f"[Restore] Dump File : {resolved_dump} ({format_bytes(resolved_dump.stat().st_size)})")
    print(f"[Restore] Target DB : {dev_pg.masked_uri} [安全校验通过: 本机地址]")
    print(f"[Restore] Strategy  : {'DROP+CREATE 重建覆盖' if recreate_db else '就地 --clean 覆盖'} (jobs={jobs})")

    if dry_run:
        print("[DryRun] 将执行：重建/清空本地库 -> pg_restore -> 全表序列修复 -> 幂等迁移校验 -> 行数核验")
        return resolved_dump

    t0 = time.monotonic()
    if recreate_db:
        print("[Restore] 1/4 断开残留连接并重建本地调试库...")
        _recreate_local_database(psql_bin, dev_pg)
    else:
        print("[Restore] 1/4 跳过重建库（使用 pg_restore --clean --if-exists）")

    print("[Restore] 2/4 执行 pg_restore 导入快照...")
    restore_cmd = [
        str(pg_restore_bin),
        *dev_pg.base_cli_args(),
        "--no-owner",
        "--no-acl",
        "--exit-on-error",
    ]
    if jobs > 1:
        restore_cmd.extend(["-j", str(jobs)])
    if not recreate_db:
        restore_cmd.extend(["--clean", "--if-exists"])
    restore_cmd.append(str(resolved_dump))

    proc = subprocess.run(
        restore_cmd,
        env=dev_pg.to_pg_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"pg_restore 失败 (exit={proc.returncode}): {detail}")

    print("[Restore] 3/4 修复 public schema 全表自增序列...")
    _run_psql_sql(psql_bin, dev_pg, SEQUENCE_REPAIR_SQL, database=dev_pg.database)

    if skip_migrations:
        print("[Restore] 4/4 已跳过本地迁移自检 (--skip-migrations)")
    else:
        print("[Restore] 4/4 执行 ORM 建表补齐与幂等 SQL 迁移自检...")
        _run_local_migrations(cfg)

    _print_local_db_summary(psql_bin, dev_pg)

    elapsed = time.monotonic() - t0
    print(f"[Restore] 本地调试库覆盖更新完成，总耗时 {elapsed:.1f}s")
    return resolved_dump


def main() -> int:
    configure_console_utf8()
    parser = argparse.ArgumentParser(description="从云端快照覆盖更新本地 PostgreSQL 调试库")
    parser.add_argument("--ops-env", default=None, help="指定运维配置文件路径（默认 .env.ops）")
    parser.add_argument("--dump", default=None, help="指定 .dump 备份文件（默认读取最新备份）")
    parser.add_argument(
        "--pull",
        "--from-prod",
        dest="pull_from_prod",
        action="store_true",
        help="先从云端生产库只读拉取最新快照，再立即覆盖本地调试库",
    )
    parser.add_argument(
        "--mode",
        choices=("direct", "ssh"),
        default=None,
        help="配合 --pull 使用：覆盖 OPS_BACKUP_MODE（direct 或 ssh）",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="pg_restore 并行度（默认 4，遇锁竞争可设 1）",
    )
    parser.add_argument(
        "--no-recreate",
        action="store_true",
        help="不 DROP/CREATE 数据库，改为 pg_restore --clean --if-exists",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="还原后不运行 sail_server 幂等迁移自检",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅预览还原计划，不修改本地库")
    args = parser.parse_args()

    cfg = load_ops_config(args.ops_env)
    try:
        restore_local_database(
            cfg,
            dump_path=Path(args.dump) if args.dump else None,
            pull_from_prod=args.pull_from_prod,
            backup_mode=args.mode,
            recreate_db=not args.no_recreate,
            jobs=max(1, args.jobs),
            skip_migrations=args.skip_migrations,
            dry_run=args.dry_run,
        )
        print("\n[OK] 本地调试库已就绪，可运行: uv run server.py --dev")
        return 0
    except Exception as exc:
        print(f"\n[FAIL] 本地库重构失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
