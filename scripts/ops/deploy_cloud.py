# -*- coding: utf-8 -*-
# @file deploy_cloud.py
# @brief Automated cloud deployment with pre-deploy DB backup, atomic site_dist swap, health gate, and rollback
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""SailZen 公网 Linux 云服务器自动化部署与回滚脚本。

完整闭环：
1. 本地预检门禁：body_metrics codegen 校验 + 核心单元测试/路由挂载回归测试（可 --skip-local-tests）。
2. 部署前强制备份云端生产 PostgreSQL（复用 backup_prod_db.py，失败即中止发布）。
3. 记录云端当前 commit（PREV_COMMIT），用于异常自动回滚。
4. （除非 --backend-only）本地构建 site（pnpm run build-site），打包上传并原子替换云端 SITE_DIST
   （自动保留 SITE_DIST.prev 以支持瞬间回滚）。
5. （除非 --site-only）同步云端代码（git pull --ff-only 或 patch 上传应用）并执行 uv sync。
6. 重启云端 sailzen-server.service（--with-sailtick 时一并重启 sailtick.service）。
7. 执行线上健康体检（health_check.py --env prod），不通过则自动回滚至 PREV_COMMIT 与上一版 site_dist，
   并拉取 journalctl 诊断日志！

用法:
    uv run python scripts/ops/deploy_cloud.py --dry-run
    uv run python scripts/ops/deploy_cloud.py
    uv run python scripts/ops/deploy_cloud.py --site-only
    uv run python scripts/ops/deploy_cloud.py --backend-only --sync-mode patch
    uv run python scripts/ops/deploy_cloud.py --rollback <commit_sha>
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops.backup_prod_db import backup_prod_database
from scripts.ops.common import (
    OpsConfig,
    configure_console_utf8,
    load_ops_config,
    run_ssh_command,
    scp_upload,
)
from scripts.ops.health_check import print_report, run_health_check


def _systemctl_prefix(cfg: OpsConfig) -> str:
    return "sudo systemctl" if cfg.remote_use_sudo else "systemctl"


def _run_local(cmd: List[str], *, desc: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    print(f"[Local] {desc}: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"{desc} 失败 (exit={proc.returncode}):\n{detail}")
    return proc


def _run_preflight_checks(dry_run: bool) -> None:
    print("\n--- Step 1: 本地发布预检门禁 ---")
    status = _run_local(["git", "status", "--short"], desc="检查工作区状态")
    dirty_lines = [line for line in status.stdout.splitlines() if line.strip()]
    if dirty_lines:
        print(f"[Warn] 当前本地工作区存在 {len(dirty_lines)} 项未提交变更（部署仅发布已提交代码或前端构建产物）")

    if dry_run:
        print("[DryRun] 将执行 generate_body_metrics.py --check 与核心 pytest 回归套件")
        return

    _run_local(
        [sys.executable, "scripts/generate_body_metrics.py", "--check"],
        desc="校验 body_metrics 三端代码生成",
    )
    _run_local(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/server/test_router_mount.py",
            "tests/unit/test_body_metrics_codegen.py",
            "tests/unit/test_ops_scripts.py",
            "-q",
        ],
        desc="运行发布门禁回归测试",
    )


def _get_remote_head(cfg: OpsConfig) -> str:
    repo = shlex.quote(cfg.remote_repo)
    proc = run_ssh_command(cfg, f"cd {repo} && git rev-parse HEAD", timeout=30)
    return proc.stdout.strip().splitlines()[-1].strip()


def _pack_site_dist(site_dist_dir: Path, archive_path: Path) -> None:
    if not site_dist_dir.is_dir() or not (site_dist_dir / "index.html").is_file():
        raise RuntimeError(f"前端构建产物不完整（缺少 index.html）: {site_dist_dir}")
    with tarfile.open(archive_path, "w:gz") as tar:
        for item in site_dist_dir.iterdir():
            tar.add(item, arcname=item.name)


def _deploy_site(cfg: OpsConfig, *, site_build_mode: str, dry_run: bool) -> bool:
    print(f"\n--- Step 5: 构建并更新云端 Web 前端 (mode={site_build_mode}) ---")
    if site_build_mode == "remote":
        repo = shlex.quote(cfg.remote_repo)
        pnpm_bin = shlex.quote(cfg.remote_pnpm_bin)
        remote_dist = shlex.quote(cfg.remote_site_dist)
        remote_prev = shlex.quote(f"{cfg.remote_site_dist}.prev")
        # 若云端 SITE_DIST 就是 site/dist 或指向 site/dist 的软链，直接 build-site 即可；
        # 否则将构建产物同步到 OPS_REMOTE_SITE_DIST 并保留 .prev 供回滚。
        build_cmd = (
            f"set -e; cd {repo}; "
            f"{pnpm_bin} build-site; "
            f"SRC_REAL=$(readlink -f {repo}/site/dist); "
            f"DST_REAL=$(readlink -f {remote_dist} 2>/dev/null || echo {remote_dist}); "
            f"if [ \"$SRC_REAL\" != \"$DST_REAL\" ]; then "
            f"  rm -rf {remote_dist}.new; cp -a \"$SRC_REAL\" {remote_dist}.new; "
            f"  if [ -d {remote_dist} ] && [ ! -L {remote_dist} ]; then rm -rf {remote_prev} && mv {remote_dist} {remote_prev}; fi; "
            f"  mv {remote_dist}.new {remote_dist}; "
            f"fi"
        )
        if dry_run:
            print(f"[DryRun] 将在云端执行: cd {cfg.remote_repo} && {cfg.remote_pnpm_bin} build-site（并按需同步至 {cfg.remote_site_dist}）")
            return False
        run_ssh_command(cfg, build_cmd, timeout=300)
        print(f"[Site] 云端 {cfg.remote_pnpm_bin} build-site 完成")
        return True

    if dry_run:
        print(f"[DryRun] 将在本机执行 pnpm run build-site -> 上传并原子替换 {cfg.remote_site_dist}")
        return False

    pnpm_cmd = ["pnpm.cmd", "run", "build-site"] if sys.platform.startswith("win") else ["pnpm", "run", "build-site"]
    _run_local(pnpm_cmd, desc="构建 Web 前端 (site/dist)", timeout=300)

    site_dist = PROJECT_ROOT / "site" / "dist"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_tar = f"/tmp/sailzen_site_dist_{stamp}.tar.gz"
    remote_dir = shlex.quote(cfg.remote_site_dist)
    remote_new = shlex.quote(f"{cfg.remote_site_dist}.new")
    remote_prev = shlex.quote(f"{cfg.remote_site_dist}.prev")

    with tempfile.TemporaryDirectory() as tmpdir:
        local_tar = Path(tmpdir) / f"site_dist_{stamp}.tar.gz"
        _pack_site_dist(site_dist, local_tar)
        print(f"[Site] 上传前端包至 {cfg.ssh_host}:{remote_tar} ...")
        scp_upload(cfg, local_tar, remote_tar, timeout=300)

    swap_cmd = (
        f"set -e; "
        f"rm -rf {remote_new}; mkdir -p {remote_new}; "
        f"tar -xzf {shlex.quote(remote_tar)} -C {remote_new}; "
        f"rm -f {shlex.quote(remote_tar)}; "
        f"if [ -d {remote_dir} ]; then rm -rf {remote_prev} && mv {remote_dir} {remote_prev}; fi; "
        f"mv {remote_new} {remote_dir}"
    )
    run_ssh_command(cfg, swap_cmd, timeout=120)
    print(f"[Site] 云端静态目录已原子更新: {cfg.remote_site_dist}（旧版保留于 .prev）")
    return True


def _sync_backend_code(cfg: OpsConfig, *, sync_mode: str, remote_head: str, dry_run: bool) -> None:
    print(f"\n--- Step 4: 同步云端代码 (mode={sync_mode}) 与 Python 依赖 ---")
    repo = shlex.quote(cfg.remote_repo)
    uv_bin = shlex.quote(cfg.remote_uv_bin)

    if sync_mode == "git":
        cmd = f"set -e; cd {repo}; git fetch origin; git pull --ff-only; {uv_bin} sync"
        if dry_run:
            print(f"[DryRun] 将在云端执行: {cmd}")
            return
        run_ssh_command(cfg, cmd, timeout=300)
        print("[Backend] 云端 git pull --ff-only & uv sync 完成")
        return

    if sync_mode == "patch":
        # 适合本机受 ALLOW_PUSH 限制未 push 到 origin 时，直接同步本地已提交 commit
        local_head = _run_local(["git", "rev-parse", "HEAD"], desc="获取本地 HEAD").stdout.strip()
        if local_head == remote_head:
            print("[Backend] 本地 HEAD 与云端 HEAD 一致，无需同步代码，仅执行 uv sync")
            if not dry_run:
                run_ssh_command(cfg, f"set -e; cd {repo}; {uv_bin} sync", timeout=300)
            return

        patch_proc = _run_local(
            ["git", "format-patch", f"{remote_head}..HEAD", "--stdout"],
            desc=f"生成增量 patch ({remote_head[:8]}..{local_head[:8]})",
        )
        if not patch_proc.stdout.strip():
            raise RuntimeError(
                f"无法生成 {remote_head[:8]}..{local_head[:8]} 增量 patch，请确认本地分支包含云端 commit"
            )

        if dry_run:
            print(f"[DryRun] 将上传增量 patch ({len(patch_proc.stdout.encode('utf-8'))} 字节) 到云端并执行 git am && uv sync")
            return

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote_patch = f"/tmp/sailzen_deploy_{stamp}.patch"
        with tempfile.TemporaryDirectory() as tmpdir:
            local_patch = Path(tmpdir) / f"deploy_{stamp}.patch"
            local_patch.write_text(patch_proc.stdout, encoding="utf-8", newline="\n")
            scp_upload(cfg, local_patch, remote_patch, timeout=120)

        apply_cmd = (
            f"set -e; cd {repo}; "
            f"git am {shlex.quote(remote_patch)} || (git am --abort; rm -f {shlex.quote(remote_patch)}; exit 1); "
            f"rm -f {shlex.quote(remote_patch)}; "
            f"{uv_bin} sync"
        )
        run_ssh_command(cfg, apply_cmd, timeout=300)
        print("[Backend] 云端 patch 应用与 uv sync 完成")
        return

    raise ValueError(f"不支持的 sync_mode: {sync_mode!r}")


def _restart_remote_services(cfg: OpsConfig, *, with_sailtick: bool, dry_run: bool) -> None:
    print("\n--- Step 6: 重启云端 systemd 服务 ---")
    ctl = _systemctl_prefix(cfg)
    services = [cfg.remote_server_service]
    if with_sailtick:
        services.append(cfg.remote_sailtick_service)

    for svc in services:
        cmd = f"{ctl} restart {shlex.quote(svc)} && {ctl} is-active {shlex.quote(svc)}"
        if dry_run:
            print(f"[DryRun] 将在云端执行: {cmd}")
        else:
            proc = run_ssh_command(cfg, cmd, timeout=60)
            print(f"[Service] {svc}: {proc.stdout.strip()}")


def _collect_remote_journal(cfg: OpsConfig) -> str:
    ctl = "sudo journalctl" if cfg.remote_use_sudo else "journalctl"
    cmd = f"{ctl} -u {shlex.quote(cfg.remote_server_service)} -n 40 --no-pager"
    proc = run_ssh_command(cfg, cmd, check=False, timeout=30)
    return (proc.stdout or proc.stderr or "").strip()


def rollback_cloud(
    cfg: OpsConfig,
    *,
    target_commit: Optional[str],
    restore_site_prev: bool,
    with_sailtick: bool,
) -> None:
    """回滚云端代码与/或前端 site_dist.prev，并重启服务。"""
    print("\n=== 执行云端自动回滚 ===")
    repo = shlex.quote(cfg.remote_repo)
    uv_bin = shlex.quote(cfg.remote_uv_bin)

    if target_commit:
        run_ssh_command(
            cfg,
            f"set -e; cd {repo}; git checkout {shlex.quote(target_commit)}; {uv_bin} sync",
            timeout=300,
        )
        print(f"[Rollback] 代码已回退至 {target_commit[:12]}")

    if restore_site_prev:
        remote_dir = shlex.quote(cfg.remote_site_dist)
        remote_prev = shlex.quote(f"{cfg.remote_site_dist}.prev")
        run_ssh_command(
            cfg,
            f"if [ -d {remote_prev} ]; then rm -rf {remote_dir} && mv {remote_prev} {remote_dir}; fi",
            timeout=60,
        )
        print("[Rollback] 已恢复上一版 site_dist.prev")

    _restart_remote_services(cfg, with_sailtick=with_sailtick, dry_run=False)


def deploy_cloud(
    cfg: OpsConfig,
    *,
    backend_only: bool = False,
    site_only: bool = False,
    with_sailtick: bool = False,
    sync_mode: str = "git",
    site_build_mode: Optional[str] = None,
    skip_backup: bool = False,
    skip_local_tests: bool = False,
    dry_run: bool = False,
) -> int:
    if backend_only and site_only:
        raise ValueError("--backend-only 与 --site-only 不能同时指定")

    resolved_site_build = (site_build_mode or cfg.site_build_mode).lower()

    if not skip_local_tests and not site_only:
        _run_preflight_checks(dry_run=dry_run)
    else:
        print("\n--- Step 1: 已跳过本地回归测试 ---")

    print("\n--- Step 2: 部署前云端生产数据库强制备份 ---")
    if skip_backup:
        print("[Warn] 已显式指定 --skip-backup，跳过生产库热备（高风险！）")
    else:
        backup_prod_database(cfg, dry_run=dry_run)

    print("\n--- Step 3: 记录云端当前版本 (PREV_COMMIT) ---")
    if dry_run:
        try:
            prev_commit = _get_remote_head(cfg)
            print(f"[DryRun] 云端当前 HEAD: {prev_commit}")
        except Exception as exc:
            prev_commit = "<remote-unreachable-in-dry-run>"
            print(f"[DryRun] 无法探测云端 HEAD（请先配置 .env.ops 的 SSH 信息）: {exc}")
    else:
        prev_commit = _get_remote_head(cfg)
        print(f"[Cloud] PREV_COMMIT = {prev_commit}")

    site_swapped = False
    code_updated = False
    try:
        # 先同步代码，再在云端/本机构建前端（确保 remote build 编译的是最新前端代码）
        if not site_only:
            _sync_backend_code(cfg, sync_mode=sync_mode, remote_head=prev_commit, dry_run=dry_run)
            code_updated = not dry_run

        if not backend_only:
            site_swapped = _deploy_site(cfg, site_build_mode=resolved_site_build, dry_run=dry_run)

        _restart_remote_services(cfg, with_sailtick=with_sailtick, dry_run=dry_run)

        print("\n--- Step 7: 线上健康体检与验收摘要 ---")
        if dry_run:
            print("[DryRun] 将执行 health_check.py --env prod（最多重试 6 次），失败自动回滚")
            print("\n[OK] Dry-run 预演完成，未对云端生产环境做出任何修改。")
            return 0

        ok, results = run_health_check(
            cfg,
            env_name="prod",
            check_web_root=True,
            with_sailtick=with_sailtick,
            retries=6,
            retry_delay=3.0,
        )
        print_report(results, "Production Post-Deploy Health Check")

        if not ok:
            raise RuntimeError("线上健康体检未通过，触发自动回滚")

        new_head = _get_remote_head(cfg)
        print(f"\n[OK] 云端部署成功！ {prev_commit[:10]} -> {new_head[:10]}")
        print("请人类进入 Stage 6 验收：检查公网 Web 与手机 Android App 核心场景。")
        return 0
    except Exception as exc:
        print(f"\n[FAIL] 部署流程异常: {exc}", file=sys.stderr)
        if not dry_run and (code_updated or site_swapped):
            journal = _collect_remote_journal(cfg)
            if journal:
                print("\n--- 云端最近日志 (journalctl) ---\n" + journal, file=sys.stderr)
            try:
                rollback_cloud(
                    cfg,
                    target_commit=prev_commit if code_updated else None,
                    restore_site_prev=site_swapped,
                    with_sailtick=with_sailtick,
                )
                print("[Rollback] 已自动回滚到部署前状态。", file=sys.stderr)
            except Exception as rb_exc:
                print(f"[CRITICAL] 自动回滚也失败，请立即人工介入 SSH 排查: {rb_exc}", file=sys.stderr)
        return 1


def main() -> int:
    configure_console_utf8()
    parser = argparse.ArgumentParser(description="SailZen 云端自动化部署与回滚工具")
    parser.add_argument("--ops-env", default=None, help="指定运维配置文件路径（默认 .env.ops）")
    parser.add_argument("--dry-run", action="store_true", help="仅预演发布计划，不修改云端")
    parser.add_argument("--backend-only", action="store_true", help="仅部署后端，不构建/同步 site_dist")
    parser.add_argument("--site-only", action="store_true", help="仅构建并原子替换前端 site_dist")
    parser.add_argument("--with-sailtick", action="store_true", help="一并重启并体检 sailtick.service")
    parser.add_argument(
        "--sync-mode",
        choices=("git", "patch"),
        default="git",
        help="云端代码同步方式（git=git pull --ff-only，patch=上传本地增量 patch 并 git am）",
    )
    parser.add_argument(
        "--site-build",
        choices=("remote", "local"),
        default=None,
        help="覆盖 OPS_SITE_BUILD_MODE（remote=云端 pnpm build-site，local=本机构建后上传）",
    )
    parser.add_argument("--skip-backup", action="store_true", help="跳过部署前生产库备份（不推荐）")
    parser.add_argument("--skip-local-tests", action="store_true", help="跳过本地预检回归测试")
    parser.add_argument("--rollback", default=None, help="手动回滚云端代码到指定 commit SHA")
    args = parser.parse_args()

    cfg = load_ops_config(args.ops_env)
    if args.rollback:
        try:
            rollback_cloud(
                cfg,
                target_commit=args.rollback,
                restore_site_prev=True,
                with_sailtick=args.with_sailtick,
            )
            ok, results = run_health_check(
                cfg,
                env_name="prod",
                check_web_root=True,
                with_sailtick=args.with_sailtick,
                retries=5,
                retry_delay=2.0,
            )
            print_report(results, "Production Post-Rollback Health Check")
            return 0 if ok else 1
        except Exception as exc:
            print(f"[FAIL] 手动回滚失败: {exc}", file=sys.stderr)
            return 1

    return deploy_cloud(
        cfg,
        backend_only=args.backend_only,
        site_only=args.site_only,
        with_sailtick=args.with_sailtick,
        sync_mode=args.sync_mode,
        site_build_mode=args.site_build,
        skip_backup=args.skip_backup,
        skip_local_tests=args.skip_local_tests,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
