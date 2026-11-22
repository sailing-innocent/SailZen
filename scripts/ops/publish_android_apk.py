# -*- coding: utf-8 -*-
# @file publish_android_apk.py
# @brief Auto-bump Android versionCode, build signed Release APK, and publish to cloud via SCP
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""SailZen Android Release APK 一键打包与 SCP 自动发布脚本。

完整流程：
1. 读取 android/version.properties，默认自动递增 VERSION_CODE（可 --no-bump 或 --version-name）。
2. 执行 Release 安全护栏校验（公网 SERVER_URL + 正式签名证书）。
3. 执行 Gradle assembleRelease（若构建失败自动回滚 version.properties）。
4. 计算产物 SHA256 与体积，通过 SCP 原子上传 APK 至云端 <remote_app_releases_dir>/。
5. 原子写入 latest.json，并清理云端超出保留数量的旧版 APK（默认保留最近 5 个）。
6. 探活云端 /api/v1/app/release/latest 确认线上已生效。

用法:
    uv run python scripts/ops/publish_android_apk.py --dry-run
    uv run python scripts/ops/publish_android_apk.py -m "修复健康打卡同步"
    uv run python scripts/ops/publish_android_apk.py --version-name 0.3.0 -m "支持应用内自动更新"
    uv run python scripts/ops/publish_android_apk.py --apk android/app/build/outputs/apk/release/SailZen-xxx.apk --no-bump
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops.build_android_release import (
    ANDROID_DIR,
    check_release_guardrails,
    resolve_release_server_url,
)
from scripts.ops.common import (
    OpsConfig,
    configure_console_utf8,
    format_bytes,
    load_ops_config,
    run_ssh_command,
    scp_upload,
)

VERSION_PROPS_PATH = ANDROID_DIR / "version.properties"
DEFAULT_KEEP_APKS = 5


@dataclass(frozen=True)
class AndroidVersion:
    """android/version.properties 版本信息。"""

    version_code: int
    version_name: str


def read_android_version(path: Path = VERSION_PROPS_PATH) -> AndroidVersion:
    """读取 android/version.properties。"""
    version_code = 1
    version_name = "0.2.0"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k == "VERSION_CODE" and v:
                version_code = int(v)
            elif k == "VERSION_NAME" and v:
                version_name = v
    return AndroidVersion(version_code=version_code, version_name=version_name)


def write_android_version(version: AndroidVersion, path: Path = VERSION_PROPS_PATH) -> None:
    """持久化 android/version.properties。"""
    content = (
        "# SailZen Android 版本元数据（scripts/ops/publish_android_apk.py 每次发布自动递增 VERSION_CODE）\n"
        f"VERSION_CODE={version.version_code}\n"
        f"VERSION_NAME={version.version_name}\n"
    )
    path.write_text(content, encoding="utf-8")


def compute_next_version(
    current: AndroidVersion,
    *,
    bump: bool = True,
    version_name: Optional[str] = None,
) -> AndroidVersion:
    """计算目标版本号。"""
    next_code = current.version_code + 1 if bump else current.version_code
    next_name = version_name.strip() if version_name and version_name.strip() else current.version_name
    return AndroidVersion(version_code=next_code, version_name=next_name)


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_release_manifest(
    *,
    version: AndroidVersion,
    apk_path: Path,
    sha256: str,
    release_notes: str = "",
    published_at: Optional[str] = None,
) -> Dict[str, object]:
    """构造云端 latest.json 元数据载荷。"""
    ts = published_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return {
        "version_code": version.version_code,
        "version_name": version.version_name,
        "file_name": apk_path.name,
        "size": apk_path.stat().st_size,
        "sha256": sha256,
        "release_notes": release_notes.strip(),
        "published_at": ts,
    }


def _find_latest_release_apk(apk_dir: Path, version_code: int) -> Path:
    if not apk_dir.is_dir():
        raise FileNotFoundError(f"未找到 Release 输出目录: {apk_dir}")
    tagged = sorted(
        apk_dir.glob(f"*-vc{version_code}-*.apk"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if tagged:
        return tagged[0]
    all_apks = sorted(
        apk_dir.glob("*.apk"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not all_apks:
        raise FileNotFoundError(f"未在 {apk_dir} 找到生成的 Release APK")
    return all_apks[0]


def _build_release_apk(
    *,
    version: AndroidVersion,
    with_tests: bool = False,
) -> Path:
    gradlew = ANDROID_DIR / ("gradlew.bat" if sys.platform.startswith("win") else "gradlew")
    if not gradlew.is_file():
        raise FileNotFoundError(f"未找到 Gradle Wrapper: {gradlew}")

    tasks: List[str] = []
    if with_tests:
        tasks.append("testDebugUnitTest")
    tasks.append("assembleRelease")

    cmd = [
        str(gradlew),
        *tasks,
        f"-PSAILZEN_VERSION_CODE={version.version_code}",
        f"-PSAILZEN_VERSION_NAME={version.version_name}",
    ]
    print(f"[Android] Exec: {' '.join(cmd)} (cwd={ANDROID_DIR})")
    proc = subprocess.run(cmd, cwd=str(ANDROID_DIR))
    if proc.returncode != 0:
        raise RuntimeError(f"Gradle assembleRelease 构建失败 (exit={proc.returncode})")

    apk_dir = ANDROID_DIR / "app" / "build" / "outputs" / "apk" / "release"
    return _find_latest_release_apk(apk_dir, version.version_code)


def _upload_apk_and_manifest(
    cfg: OpsConfig,
    *,
    apk_path: Path,
    manifest: Dict[str, object],
    keep: int = DEFAULT_KEEP_APKS,
    dry_run: bool = False,
) -> None:
    remote_dir = cfg.remote_app_releases_dir
    remote_apk_part = f"{remote_dir}/{apk_path.name}.part"
    remote_apk_final = f"{remote_dir}/{apk_path.name}"
    remote_manifest_tmp = f"{remote_dir}/latest.json.tmp"
    remote_manifest_final = f"{remote_dir}/latest.json"

    print(f"[Cloud] 目标目录: {remote_dir}")
    print(f"[Cloud] 目标文件: {apk_path.name} ({format_bytes(int(manifest['size']))})")
    print(f"[Cloud] SHA256 : {manifest['sha256']}")

    if dry_run:
        print("[DryRun] 将通过 SCP 原子上传 APK 与 latest.json，并保留最近 "
              f"{max(1, keep)} 个 APK。")
        print("[DryRun] latest.json 预览:")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return

    # 1. 确保云端目录存在
    run_ssh_command(cfg, f"mkdir -p {shlex.quote(remote_dir)}", timeout=30)

    # 2. SCP 上传 APK 到 .part 临时文件，再原子 mv
    print(f"[SCP] 上传 APK -> {remote_apk_part}")
    scp_upload(cfg, apk_path, remote_apk_part, timeout=600)
    run_ssh_command(
        cfg,
        f"chmod 644 {shlex.quote(remote_apk_part)} && mv -f {shlex.quote(remote_apk_part)} {shlex.quote(remote_apk_final)}",
        timeout=30,
    )

    # 3. 写入 latest.json 并原子替换
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

    # 4. 清理超出保留数量的旧版 APK（绝不删刚发布的包）
    keep_n = max(1, keep)
    prune_cmd = (
        f"cd {shlex.quote(remote_dir)} && "
        f"ls -1t *.apk 2>/dev/null | tail -n +{keep_n + 1} | "
        f"grep -vxF {shlex.quote(apk_path.name)} | "
        "xargs -r rm -f"
    )
    run_ssh_command(cfg, prune_cmd, check=False, timeout=30)
    print(f"[OK] APK 与 latest.json 已原子发布至云端（保留最近 {keep_n} 个历史包）")


def _verify_live_endpoint(cfg: OpsConfig, expected_version_code: int, expected_sha256: str) -> bool:
    try:
        base_url = cfg.get_server_url("prod")
    except RuntimeError as exc:
        print(f"[Warn] 跳过线上探活: {exc}")
        return False

    api_ep = cfg.get_api_endpoint("prod")
    url = f"{base_url}{api_ep}/app/release/latest"
    req = urllib.request.Request(url, method="GET")
    token = cfg.get_api_token("prod")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        live_code = int(body.get("version_code", -1))
        live_sha = str(body.get("sha256", ""))
        if live_code == expected_version_code and live_sha == expected_sha256:
            print(f"[OK] 云端接口探活通过: {url} (versionCode={live_code})")
            return True
        print(
            f"[Warn] 云端接口返回值与刚发布版本不一致: live_code={live_code}, "
            f"expected={expected_version_code}（请检查云端 SERVER_DATA_DIR 与 OPS_REMOTE_APP_RELEASES_DIR 是否一致）"
        )
        return False
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(
                f"[Warn] 云端探活返回 404 ({url})：若尚未将最新后端代码部署上云，"
                "请先执行 `uv run python scripts/ops/deploy_cloud.py --backend-only`。"
            )
        else:
            print(f"[Warn] 云端探活失败 HTTP {exc.code} ({url})")
        return False
    except Exception as exc:
        print(f"[Warn] 云端探活请求异常 ({url}): {exc}")
        return False


def publish_android_apk(
    cfg: OpsConfig,
    *,
    notes: str = "",
    version_name: Optional[str] = None,
    bump: bool = True,
    existing_apk: Optional[Path] = None,
    keep: int = DEFAULT_KEEP_APKS,
    with_tests: bool = False,
    allow_debug_signing: bool = False,
    allow_empty_url: bool = False,
    skip_verify: bool = False,
    dry_run: bool = False,
    version_props_path: Path = VERSION_PROPS_PATH,
) -> Dict[str, object]:
    """执行完整发布闭环，返回生成的 manifest 字典。"""
    current_ver = read_android_version(version_props_path)
    target_ver = compute_next_version(current_ver, bump=bump, version_name=version_name)
    print(
        f"[Version] 当前: v{current_ver.version_name} (code={current_ver.version_code}) "
        f"-> 目标: v{target_ver.version_name} (code={target_ver.version_code})"
    )

    if existing_apk is None:
        issues = check_release_guardrails(
            allow_debug_signing=allow_debug_signing,
            allow_empty_url=allow_empty_url,
        )
        if issues:
            detail = "\n".join(f"  - {item}" for item in issues)
            raise RuntimeError(f"Android Release 构建护栏未通过：\n{detail}")
        print("[OK] Release 服务器地址与正式签名护栏校验通过")

        # 探活 Release 锁定的服务端地址，避免打出指向错误端口（如漏写 :4399）的不可用包
        release_url = resolve_release_server_url()
        if release_url and not allow_empty_url:
            health_url = f"{release_url}{cfg.get_api_endpoint('prod')}/health"
            try:
                with urllib.request.urlopen(health_url, timeout=8) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"HTTP {resp.status}")
                print(f"[OK] Release 服务器地址可达性校验通过: {health_url}")
            except Exception as exc:
                raise RuntimeError(
                    f"Release 锁定的服务器地址无法连通 ({health_url}): {exc}\n"
                    "请检查 android/keystore.properties 中的 SAILZEN_RELEASE_SERVER_URL（是否漏写端口号，如 :4399）"
                ) from exc

    if dry_run:
        if existing_apk is not None:
            apk_path = existing_apk.resolve()
            if not apk_path.is_file():
                raise FileNotFoundError(f"指定的 APK 不存在: {apk_path}")
            manifest = build_release_manifest(
                version=target_ver,
                apk_path=apk_path,
                sha256=compute_sha256(apk_path),
                release_notes=notes,
            )
        else:
            fake_name = f"SailZen-{target_ver.version_name}-vc{target_ver.version_code}-release.apk"
            manifest = {
                "version_code": target_ver.version_code,
                "version_name": target_ver.version_name,
                "file_name": fake_name,
                "size": 0,
                "sha256": "<computed-after-build>",
                "release_notes": notes.strip(),
                "published_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            }
            apk_path = Path(fake_name)
        _upload_apk_and_manifest(cfg, apk_path=apk_path, manifest=manifest, keep=keep, dry_run=True)
        print("[DryRun] 演练完成，未修改 version.properties，未构建也未上传。")
        return manifest

    original_props_text: Optional[str] = (
        version_props_path.read_text(encoding="utf-8") if version_props_path.is_file() else None
    )
    version_changed = target_ver != current_ver

    try:
        if version_changed:
            write_android_version(target_ver, version_props_path)
            print(f"[Version] 已写入 {version_props_path.name}: VERSION_CODE={target_ver.version_code}, VERSION_NAME={target_ver.version_name}")

        if existing_apk is not None:
            apk_path = existing_apk.resolve()
            if not apk_path.is_file():
                raise FileNotFoundError(f"指定的 APK 不存在: {apk_path}")
        else:
            apk_path = _build_release_apk(version=target_ver, with_tests=with_tests)

        sha256 = compute_sha256(apk_path)
        manifest = build_release_manifest(
            version=target_ver,
            apk_path=apk_path,
            sha256=sha256,
            release_notes=notes,
        )
        _upload_apk_and_manifest(cfg, apk_path=apk_path, manifest=manifest, keep=keep, dry_run=False)
    except Exception:
        if version_changed:
            if original_props_text is not None:
                version_props_path.write_text(original_props_text, encoding="utf-8")
            elif version_props_path.exists():
                version_props_path.unlink()
            print("[Rollback] 构建/发布异常，已自动回滚 android/version.properties", file=sys.stderr)
        raise

    if not skip_verify:
        _verify_live_endpoint(cfg, target_ver.version_code, str(manifest["sha256"]))

    return manifest


def main() -> int:
    configure_console_utf8()
    parser = argparse.ArgumentParser(
        description="SailZen Android Release APK 自动递增 versionCode + 构建 + SCP 发布上云"
    )
    parser.add_argument("-m", "--notes", default="", help="本次更新说明（展示在手机更新弹窗中）")
    parser.add_argument("--version-name", default=None, help="可选：同步更新 VERSION_NAME（例如 0.3.0）")
    parser.add_argument("--no-bump", action="store_true", help="跳过自动递增 VERSION_CODE（用于重传同一版本）")
    parser.add_argument("--apk", default=None, help="跳过 Gradle 构建，直接发布指定路径的 APK 文件")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP_APKS, help="云端保留最近 N 个 APK（默认 5）")
    parser.add_argument("--with-tests", action="store_true", help="构建前先运行 testDebugUnitTest")
    parser.add_argument("--allow-debug-signing", action="store_true", help="允许回退 debug 签名（仅演练/测试用）")
    parser.add_argument("--allow-empty-url", action="store_true", help="允许未配置 SAILZEN_RELEASE_SERVER_URL")
    parser.add_argument("--skip-verify", action="store_true", help="上传后跳过线上 /api/v1/app/release/latest 探活")
    parser.add_argument("--dry-run", action="store_true", help="仅做前置护栏与参数演练，不修改文件/不构建/不上传")
    args = parser.parse_args()

    cfg = load_ops_config()
    try:
        publish_android_apk(
            cfg,
            notes=args.notes,
            version_name=args.version_name,
            bump=not args.no_bump,
            existing_apk=Path(args.apk) if args.apk else None,
            keep=args.keep,
            with_tests=args.with_tests,
            allow_debug_signing=args.allow_debug_signing,
            allow_empty_url=args.allow_empty_url,
            skip_verify=args.skip_verify,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
