# -*- coding: utf-8 -*-
# @file publish_vscode_vsix.py
# @brief Auto-bump SailZen Workbench version, build & test VSIX, and publish to cloud via SCP
# @author sailing-innocent
# @date 2026-11-28
# @version 1.0
# ---------------------------------
"""SailZen VS Code Workbench 插件 VSIX 一键打包与 SCP 自动发布脚本（OTA）。

完整流程（对齐 scripts/ops/publish_android_apk.py）：
1. 读取 packages/sailzen-workbench/package.json，支持 --bump patch|minor|major|none 或 --version X.Y.Z。
2. 执行 typecheck + jest 单元测试 + vsce package（若构建失败自动回滚 package.json）。
3. 计算产物 SHA256 与体积，通过 SCP 原子上传 VSIX 至云端 <remote_vscode_releases_dir>/。
4. 原子写入 latest.json，并清理云端超出保留数量的旧版 VSIX（默认保留最近 5 个）。
5. 探活云端 /api/v1/workbench/release/latest 确认线上已生效。

用法:
    uv run python scripts/ops/publish_vscode_vsix.py --dry-run
    uv run python scripts/ops/publish_vscode_vsix.py -m "新增 Pin 书架与小说章节回写"
    uv run python scripts/ops/publish_vscode_vsix.py --bump minor -m "Phase 3 正式版"
    uv run python scripts/ops/publish_vscode_vsix.py --no-bump --vsix packages/sailzen-workbench/sailzen-workbench-0.3.0.vsix
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops.common import (
    OpsConfig,
    configure_console_utf8,
    format_bytes,
    load_ops_config,
    run_ssh_command,
    scp_upload,
)

WORKBENCH_DIR = PROJECT_ROOT / "packages" / "sailzen-workbench"
PACKAGE_JSON_PATH = WORKBENCH_DIR / "package.json"
DEFAULT_KEEP_VSIXS = 5
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def read_workbench_version(pkg_path: Path = PACKAGE_JSON_PATH) -> str:
    data = json.loads(pkg_path.read_text(encoding="utf-8"))
    ver = str(data.get("version") or "").strip()
    if not SEMVER_RE.fullmatch(ver):
        raise ValueError(f"package.json 版本号格式非法: {ver!r}")
    return ver


def write_workbench_version(version: str, pkg_path: Path = PACKAGE_JSON_PATH) -> None:
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(f"目标版本号格式非法（需 X.Y.Z）: {version!r}")
    text = pkg_path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'("version"\s*:\s*")([^"]+)(")',
        rf'\g<1>{version}\g<3>',
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"未能在 {pkg_path} 中定位 version 字段")
    pkg_path.write_text(updated, encoding="utf-8")


def compute_next_semver(
    current: str,
    *,
    bump: str = "patch",
    explicit_version: Optional[str] = None,
) -> str:
    if explicit_version and explicit_version.strip():
        target = explicit_version.strip()
        if not SEMVER_RE.fullmatch(target):
            raise ValueError(f"--version 格式非法（需 X.Y.Z）: {target!r}")
        return target

    m = SEMVER_RE.fullmatch(current.strip())
    if not m:
        raise ValueError(f"当前版本号格式非法: {current!r}")
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))

    if bump == "none":
        return current
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "major":
        return f"{major + 1}.0.0"
    raise ValueError(f"不支持的 bump 类型: {bump!r}")


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_vsix_manifest(
    *,
    version: str,
    vsix_path: Path,
    sha256: str,
    release_notes: str = "",
    published_at: Optional[str] = None,
) -> Dict[str, object]:
    ts = published_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return {
        "version": version,
        "file_name": vsix_path.name,
        "size": vsix_path.stat().st_size,
        "sha256": sha256,
        "release_notes": release_notes.strip(),
        "published_at": ts,
    }


def _build_vsix(*, version: str, skip_tests: bool = False) -> Path:
    pnpm_bin = shutil.which("pnpm") or ("pnpm.cmd" if sys.platform.startswith("win") else "pnpm")
    steps = [
        [pnpm_bin, "--filter=sailzen-workbench", "run", "typecheck"],
    ]
    if not skip_tests:
        steps.append([pnpm_bin, "--filter=sailzen-workbench", "run", "test"])
    steps.append([pnpm_bin, "--filter=sailzen-workbench", "run", "package"])

    for cmd in steps:
        print(f"[Workbench] Exec: {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        if proc.returncode != 0:
            raise RuntimeError(f"命令执行失败 (exit={proc.returncode}): {' '.join(cmd)}")

    expected = WORKBENCH_DIR / f"sailzen-workbench-{version}.vsix"
    if expected.is_file():
        return expected
    candidates = sorted(
        WORKBENCH_DIR.glob("*.vsix"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"未在 {WORKBENCH_DIR} 找到生成的 VSIX")
    return candidates[0]


def _upload_vsix_and_manifest(
    cfg: OpsConfig,
    *,
    vsix_path: Path,
    manifest: Dict[str, object],
    keep: int = DEFAULT_KEEP_VSIXS,
    dry_run: bool = False,
) -> None:
    remote_dir = cfg.remote_vscode_releases_dir
    remote_part = f"{remote_dir}/{vsix_path.name}.part"
    remote_final = f"{remote_dir}/{vsix_path.name}"
    remote_manifest_tmp = f"{remote_dir}/latest.json.tmp"
    remote_manifest_final = f"{remote_dir}/latest.json"

    print(f"[Cloud] 目标目录: {remote_dir}")
    print(f"[Cloud] 目标文件: {vsix_path.name} ({format_bytes(int(manifest['size']))})")
    print(f"[Cloud] SHA256 : {manifest['sha256']}")

    if dry_run:
        print(f"[DryRun] 将通过 SCP 原子上传 VSIX 与 latest.json，并保留最近 {max(1, keep)} 个包。")
        print("[DryRun] latest.json 预览:")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return

    run_ssh_command(cfg, f"mkdir -p {shlex.quote(remote_dir)}", timeout=30)

    print(f"[SCP] 上传 VSIX -> {remote_part}")
    scp_upload(cfg, vsix_path, remote_part, timeout=180)
    run_ssh_command(
        cfg,
        f"chmod 644 {shlex.quote(remote_part)} && mv -f {shlex.quote(remote_part)} {shlex.quote(remote_final)}",
        timeout=30,
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", encoding="utf-8", delete=False
    ) as tf:
        json.dump(manifest, tf, ensure_ascii=False, indent=2)
        tf.write("\n")
        tmp_local_json = Path(tf.name)

    try:
        print(f"[SCP] 上传元数据 -> {remote_manifest_tmp}")
        scp_upload(cfg, tmp_local_json, remote_manifest_tmp, timeout=60)
        run_ssh_command(
            cfg,
            f"chmod 644 {shlex.quote(remote_manifest_tmp)} && mv -f {shlex.quote(remote_manifest_tmp)} {shlex.quote(remote_manifest_final)}",
            timeout=30,
        )
    finally:
        tmp_local_json.unlink(missing_ok=True)

    keep_n = max(1, keep)
    prune_cmd = (
        f"cd {shlex.quote(remote_dir)} && "
        f"ls -1t *.vsix 2>/dev/null | tail -n +{keep_n + 1} | "
        f"grep -vxF {shlex.quote(vsix_path.name)} | "
        "xargs -r rm -f"
    )
    run_ssh_command(cfg, prune_cmd, check=False, timeout=30)
    print(f"[OK] VSIX 与 latest.json 已原子发布至云端（保留最近 {keep_n} 个历史包）")


def _verify_live_endpoint(cfg: OpsConfig, expected_version: str, expected_sha256: str) -> bool:
    try:
        base_url = cfg.get_server_url("prod")
    except RuntimeError as exc:
        print(f"[Warn] 跳过线上探活: {exc}")
        return False

    api_ep = cfg.get_api_endpoint("prod")
    url = f"{base_url}{api_ep}/workbench/release/latest"
    req = urllib.request.Request(url, method="GET")
    token = cfg.get_api_token("prod")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        live_ver = str(body.get("version", ""))
        live_sha = str(body.get("sha256", ""))
        if live_ver == expected_version and live_sha == expected_sha256:
            print(f"[OK] 云端接口探活通过: {url} (version={live_ver})")
            return True
        print(
            f"[Warn] 云端接口返回值与刚发布版本不一致: live={live_ver}, expected={expected_version}"
        )
        return False
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(
                f"[Warn] 云端探活返回 404 ({url})：请先将含 /api/v1/workbench/release 的后端部署上云。"
            )
        else:
            print(f"[Warn] 云端探活失败 HTTP {exc.code} ({url})")
        return False
    except Exception as exc:
        print(f"[Warn] 云端探活请求异常 ({url}): {exc}")
        return False


def publish_vscode_vsix(
    cfg: OpsConfig,
    *,
    notes: str = "",
    bump: str = "patch",
    explicit_version: Optional[str] = None,
    existing_vsix: Optional[Path] = None,
    keep: int = DEFAULT_KEEP_VSIXS,
    skip_tests: bool = False,
    skip_verify: bool = False,
    dry_run: bool = False,
    pkg_json_path: Path = PACKAGE_JSON_PATH,
) -> Dict[str, object]:
    current_ver = read_workbench_version(pkg_json_path)
    target_ver = compute_next_semver(
        current_ver, bump=bump, explicit_version=explicit_version
    )
    print(f"[Version] 当前: v{current_ver} -> 目标: v{target_ver}")

    if dry_run:
        if existing_vsix is not None:
            vsix_path = existing_vsix.resolve()
            if not vsix_path.is_file():
                raise FileNotFoundError(f"指定的 VSIX 不存在: {vsix_path}")
            manifest = build_vsix_manifest(
                version=target_ver,
                vsix_path=vsix_path,
                sha256=compute_sha256(vsix_path),
                release_notes=notes,
            )
        else:
            fake_name = f"sailzen-workbench-{target_ver}.vsix"
            manifest = {
                "version": target_ver,
                "file_name": fake_name,
                "size": 0,
                "sha256": "<computed-after-build>",
                "release_notes": notes.strip(),
                "published_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            }
            vsix_path = Path(fake_name)
        _upload_vsix_and_manifest(cfg, vsix_path=vsix_path, manifest=manifest, keep=keep, dry_run=True)
        print("[DryRun] 演练完成，未修改 package.json，未构建也未上传。")
        return manifest

    original_text = pkg_json_path.read_text(encoding="utf-8")
    version_changed = target_ver != current_ver

    try:
        if version_changed:
            write_workbench_version(target_ver, pkg_json_path)
            print(f"[Version] 已更新 {pkg_json_path.name} -> {target_ver}")

        if existing_vsix is not None:
            vsix_path = existing_vsix.resolve()
            if not vsix_path.is_file():
                raise FileNotFoundError(f"指定的 VSIX 不存在: {vsix_path}")
        else:
            vsix_path = _build_vsix(version=target_ver, skip_tests=skip_tests)

        sha256 = compute_sha256(vsix_path)
        manifest = build_vsix_manifest(
            version=target_ver,
            vsix_path=vsix_path,
            sha256=sha256,
            release_notes=notes,
        )
        _upload_vsix_and_manifest(cfg, vsix_path=vsix_path, manifest=manifest, keep=keep, dry_run=False)
    except Exception:
        if version_changed:
            pkg_json_path.write_text(original_text, encoding="utf-8")
            print("[Rollback] 构建/发布异常，已自动回滚 package.json 版本号", file=sys.stderr)
        raise

    if not skip_verify:
        _verify_live_endpoint(cfg, target_ver, str(manifest["sha256"]))

    return manifest


def main() -> int:
    configure_console_utf8()
    parser = argparse.ArgumentParser(
        description="SailZen VS Code Workbench VSIX 自动构建 + SCP 发布上云（OTA）"
    )
    parser.add_argument("-m", "--notes", default="", help="本次更新说明（展示在 VS Code 更新弹窗中）")
    parser.add_argument(
        "--bump",
        choices=["patch", "minor", "major", "none"],
        default="patch",
        help="版本号递增策略（默认 patch）",
    )
    parser.add_argument("--no-bump", action="store_true", help="等价于 --bump none（重传当前版本）")
    parser.add_argument("--version", dest="explicit_version", default=None, help="显式指定版本号（如 0.4.0）")
    parser.add_argument("--vsix", default=None, help="跳过构建，直接发布指定路径的 .vsix 文件")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP_VSIXS, help="云端保留最近 N 个 VSIX（默认 5）")
    parser.add_argument("--skip-tests", action="store_true", help="跳过 Jest 单元测试")
    parser.add_argument("--skip-verify", action="store_true", help="上传后跳过线上 /api/v1/workbench/release/latest 探活")
    parser.add_argument("--dry-run", action="store_true", help="演练模式：不改版本号、不构建、不上传")
    args = parser.parse_args()

    bump_mode = "none" if args.no_bump else args.bump
    cfg = load_ops_config()
    try:
        publish_vscode_vsix(
            cfg,
            notes=args.notes,
            bump=bump_mode,
            explicit_version=args.explicit_version,
            existing_vsix=Path(args.vsix) if args.vsix else None,
            keep=args.keep,
            skip_tests=args.skip_tests,
            skip_verify=args.skip_verify,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
