# -*- coding: utf-8 -*-
# @file backup_prod_db.py
# @brief Read-only production PostgreSQL backup utility (direct pg_dump or SSH pg_dump)
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""云端生产 PostgreSQL 只读备份脚本。

特性：
- 凭据收敛：直接复用 .env.prod 中的 POSTGRE_URI，不在命令行暴露密码。
- 双模式支持：
  * direct（默认）：本机调用 PostgreSQL/pgAdmin4 自带的 pg_dump -Fc 直接只读导出。
  * ssh：通过 SSH 在云端本机执行 pg_dump -Fc 再经 scp 拉回本地（适合 5432 不对外开放）。
- 自动完整性校验（pg_restore --list）、写入最新指针文件 LATEST_PROD_DUMP.txt、
  以及按保留天数自动滚动清理旧备份。

用法:
    uv run python scripts/ops/backup_prod_db.py
    uv run python scripts/ops/backup_prod_db.py --mode ssh
    uv run python scripts/ops/backup_prod_db.py --dry-run
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops.common import (
    OpsConfig,
    configure_console_utf8,
    format_bytes,
    load_ops_config,
    require_pg_binary,
    run_ssh_command,
    scp_download,
)

LATEST_POINTER_FILE = "LATEST_PROD_DUMP.txt"


def verify_dump_file(dump_path: Path, cfg: OpsConfig) -> int:
    """使用 pg_restore --list 校验自定义格式 dump 可正常解析，返回条目数。"""
    pg_restore = require_pg_binary("pg_restore", preferred_dir=cfg.pg_bin_dir)
    proc = subprocess.run(
        [str(pg_restore), "--list", str(dump_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"备份文件完整性校验失败 ({dump_path.name}): {err}")
    entries = [
        line for line in proc.stdout.splitlines() if line.strip() and not line.lstrip().startswith(";")
    ]
    if not entries:
        raise RuntimeError(f"备份文件为空（未包含任何数据库对象）: {dump_path}")
    return len(entries)


def prune_old_backups(backup_dir: Path, keep_days: int) -> List[Path]:
    """按保留天数清理旧的 prod_*.dump 备份文件（至少保留最新 3 份以防误删）。"""
    if keep_days <= 0 or not backup_dir.is_dir():
        return []

    dumps = sorted(
        backup_dir.glob("prod_*.dump"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if len(dumps) <= 3:
        return []

    cutoff = datetime.now() - timedelta(days=keep_days)
    removed: List[Path] = []
    for dump in dumps[3:]:
        mtime = datetime.fromtimestamp(dump.stat().st_mtime)
        if mtime < cutoff:
            dump.unlink(missing_ok=True)
            removed.append(dump)
    return removed


def _backup_direct(cfg: OpsConfig, output_path: Path, dry_run: bool) -> None:
    prod_pg = cfg.get_prod_pg()
    pg_dump = require_pg_binary("pg_dump", preferred_dir=cfg.pg_bin_dir)

    cmd = [
        str(pg_dump),
        *prod_pg.base_cli_args(),
        "--format=custom",
        "--compress=6",
        "--no-owner",
        "--no-acl",
        "--file",
        str(output_path),
    ]
    print(f"[Backup/direct] Source : {prod_pg.masked_uri}")
    print(f"[Backup/direct] Tool   : {pg_dump}")
    print(f"[Backup/direct] Output : {output_path}")

    if dry_run:
        print("[DryRun] 将执行只读 pg_dump -Fc（未实际写入）")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    env = prod_pg.to_pg_env()
    env["PGCONNECT_TIMEOUT"] = "15"

    t0 = time.monotonic()
    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
    )
    elapsed = time.monotonic() - t0
    if proc.returncode != 0:
        output_path.unlink(missing_ok=True)
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"pg_dump 失败 (exit={proc.returncode}): {detail}")

    print(f"[Backup/direct] 导出完成，耗时 {elapsed:.1f}s")


def _backup_ssh(cfg: OpsConfig, output_path: Path, dry_run: bool) -> None:
    remote_tmp = f"/tmp/{output_path.name}"
    db_name = shlex.quote(cfg.remote_pg_db)
    pg_user = shlex.quote(cfg.remote_pg_user)
    remote_dump_cmd = (
        f"sudo -u {pg_user} pg_dump --format=custom --compress=6 --no-owner --no-acl "
        f"-d {db_name} -f {shlex.quote(remote_tmp)}"
    )

    print(f"[Backup/ssh] SSH Host   : {cfg.ssh_host}")
    print(f"[Backup/ssh] Remote DB  : {cfg.remote_pg_db} (user={cfg.remote_pg_user})")
    print(f"[Backup/ssh] Output     : {output_path}")

    if dry_run:
        print(f"[DryRun] 将通过 SSH 执行: {remote_dump_cmd}")
        print(f"[DryRun] 并通过 SCP 拉回至 {output_path} 后清理远端临时文件")
        return

    t0 = time.monotonic()
    try:
        run_ssh_command(cfg, remote_dump_cmd, timeout=1800)
        scp_download(cfg, remote_tmp, output_path, timeout=1800)
    finally:
        # 无论成功失败尽量清理远端 /tmp 备份文件，避免敏感数据滞留
        try:
            run_ssh_command(cfg, f"rm -f {shlex.quote(remote_tmp)}", check=False, timeout=30)
        except Exception:
            pass

    elapsed = time.monotonic() - t0
    print(f"[Backup/ssh] 远端导出并拉回完成，耗时 {elapsed:.1f}s")


def backup_prod_database(
    cfg: OpsConfig,
    *,
    mode: Optional[str] = None,
    output: Optional[Path] = None,
    keep_days: Optional[int] = None,
    verify: bool = True,
    dry_run: bool = False,
) -> Path:
    """执行一次生产库只读备份，返回本地 dump 文件路径。"""
    resolved_mode = (mode or cfg.backup_mode).lower()
    if resolved_mode not in {"direct", "ssh"}:
        raise ValueError(f"不支持的备份模式: {resolved_mode!r}")

    backup_dir = cfg.backup_dir
    if output is not None:
        output_path = output.resolve()
    else:
        db_tag = cfg.remote_pg_db
        if resolved_mode == "direct":
            try:
                db_tag = cfg.get_prod_pg().database
            except Exception:
                pass
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = backup_dir / f"prod_{db_tag}_{stamp}.dump"

    if resolved_mode == "direct":
        _backup_direct(cfg, output_path, dry_run=dry_run)
    else:
        _backup_ssh(cfg, output_path, dry_run=dry_run)

    if dry_run:
        return output_path

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"备份文件生成异常（不存在或为 0 字节）: {output_path}")

    size_str = format_bytes(output_path.stat().st_size)
    print(f"[Backup] 文件大小: {size_str}")

    if verify:
        entry_count = verify_dump_file(output_path, cfg)
        print(f"[Backup] 完整性校验通过 (pg_restore --list: {entry_count} 个对象条目)")

    # 更新最新备份指针
    pointer = backup_dir / LATEST_POINTER_FILE
    backup_dir.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(output_path) + "\n", encoding="utf-8")

    retention = cfg.backup_keep_days if keep_days is None else keep_days
    removed = prune_old_backups(backup_dir, retention)
    if removed:
        print(f"[Backup] 已按保留策略 ({retention} 天) 清理 {len(removed)} 份旧备份")

    return output_path


def main() -> int:
    configure_console_utf8()
    parser = argparse.ArgumentParser(description="SailZen 云端生产 PostgreSQL 只读备份")
    parser.add_argument("--ops-env", default=None, help="指定运维配置文件路径（默认 .env.ops）")
    parser.add_argument(
        "--mode",
        choices=("direct", "ssh"),
        default=None,
        help="覆盖 OPS_BACKUP_MODE（direct=本机直连只读导出，ssh=云端本机导出后拉回）",
    )
    parser.add_argument("--output", default=None, help="指定输出 .dump 文件路径")
    parser.add_argument("--keep-days", type=int, default=None, help="本地备份保留天数（0 表示不清理）")
    parser.add_argument("--no-verify", action="store_true", help="跳过 pg_restore --list 校验")
    parser.add_argument("--dry-run", action="store_true", help="仅打印备份计划，不实际执行")
    args = parser.parse_args()

    cfg = load_ops_config(args.ops_env)
    try:
        dump_path = backup_prod_database(
            cfg,
            mode=args.mode,
            output=Path(args.output) if args.output else None,
            keep_days=args.keep_days,
            verify=not args.no_verify,
            dry_run=args.dry_run,
        )
        print(f"\n[OK] 生产库备份完成: {dump_path}")
        return 0
    except Exception as exc:
        print(f"\n[FAIL] 备份失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
