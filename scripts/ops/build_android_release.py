# -*- coding: utf-8 -*-
# @file build_android_release.py
# @brief Guarded Android APK builder (verifies release server URL & signing config, outputs SHA256)
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""SailZen Android APK 规范化构建脚本（DevOps Phase 1）。

安全护栏：
1. Release 构建默认强校验 SAILZEN_RELEASE_SERVER_URL（来自环境变量或 ~/.gradle/gradle.properties），
   防止误编译出 SERVER_URL="" 的不可用包。
2. Release 构建默认强校验正式签名配置（SAILZEN_STORE_FILE / STORE_PASSWORD / KEY_ALIAS / KEY_PASSWORD），
   防止静默回退到 debug keystore 导致手机覆盖安装报签名冲突。
3. 构建完成后自动计算并输出 APK 路径、体积与 SHA256 校验和。

用法:
    uv run python scripts/ops/build_android_release.py --dry-run
    uv run python scripts/ops/build_android_release.py --debug
    uv run python scripts/ops/build_android_release.py
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops.common import configure_console_utf8, format_bytes

ANDROID_DIR = PROJECT_ROOT / "android"
# 兼容 SAILZEN_RELEASE_*（build.gradle.kts 主用）与 SAILZEN_* 两种前缀
RELEASE_REQUIRED_SIGNING_KEY_GROUPS = (
    ("SAILZEN_RELEASE_STORE_FILE", "SAILZEN_STORE_FILE"),
    ("SAILZEN_RELEASE_STORE_PASSWORD", "SAILZEN_STORE_PASSWORD"),
    ("SAILZEN_RELEASE_KEY_ALIAS", "SAILZEN_KEY_ALIAS"),
    ("SAILZEN_RELEASE_KEY_PASSWORD", "SAILZEN_KEY_PASSWORD"),
)
RELEASE_REQUIRED_SIGNING_KEYS = tuple(group[0] for group in RELEASE_REQUIRED_SIGNING_KEY_GROUPS)


def _read_gradle_properties(path: Path) -> Dict[str, str]:
    props: Dict[str, str] = {}
    if not path.is_file():
        return props
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        props[k.strip()] = v.strip()
    return props


def _resolve_prop(key: str, gradle_props: Dict[str, str]) -> str:
    return (os.environ.get(key) or gradle_props.get(key) or "").strip()


def resolve_release_server_url() -> str:
    """按统一优先级解析 Release 构建将锁定的 SAILZEN_RELEASE_SERVER_URL。"""
    merged_props: Dict[str, str] = {}
    merged_props.update(_read_gradle_properties(Path.home() / ".gradle" / "gradle.properties"))
    merged_props.update(_read_gradle_properties(ANDROID_DIR / "gradle.properties"))
    merged_props.update(_read_gradle_properties(ANDROID_DIR / "keystore.properties"))
    return _resolve_prop("SAILZEN_RELEASE_SERVER_URL", merged_props).rstrip("/")


def check_release_guardrails(
    *, allow_debug_signing: bool = False, allow_empty_url: bool = False
) -> List[str]:
    """校验 Release 构建所需配置，返回缺失/告警项列表。

    配置查找顺序（后者覆盖前者，环境变量最高）：
    1. ~/.gradle/gradle.properties
    2. android/gradle.properties
    3. android/keystore.properties（推荐：项目本地且已 gitignore）
    4. 进程环境变量
    """
    merged_props: Dict[str, str] = {}
    merged_props.update(_read_gradle_properties(Path.home() / ".gradle" / "gradle.properties"))
    merged_props.update(_read_gradle_properties(ANDROID_DIR / "gradle.properties"))
    merged_props.update(_read_gradle_properties(ANDROID_DIR / "keystore.properties"))

    issues: List[str] = []
    if not allow_empty_url:
        url = _resolve_prop("SAILZEN_RELEASE_SERVER_URL", merged_props)
        if not url:
            issues.append(
                "缺少 SAILZEN_RELEASE_SERVER_URL（请在 android/keystore.properties 或 ~/.gradle/gradle.properties 中配置公网服务地址）"
            )
    if not allow_debug_signing:
        missing = [
            primary
            for primary, fallback in RELEASE_REQUIRED_SIGNING_KEY_GROUPS
            if not (_resolve_prop(primary, merged_props) or _resolve_prop(fallback, merged_props))
        ]
        if missing:
            issues.append(
                f"缺少 Release 签名配置: {', '.join(missing)}（可运行 `uv run python scripts/ops/init_android_signing.py --server-url <URL>` 一键生成自签名证书与 android/keystore.properties，严禁入库）"
            )
        else:
            store_raw = _resolve_prop("SAILZEN_RELEASE_STORE_FILE", merged_props) or _resolve_prop(
                "SAILZEN_STORE_FILE", merged_props
            )
            store_path = Path(store_raw)
            if not store_path.is_absolute():
                store_path = (ANDROID_DIR / store_path).resolve()
            if not store_path.is_file():
                issues.append(f"Release 签名证书文件不存在: {store_path}")
    return issues


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    configure_console_utf8()
    parser = argparse.ArgumentParser(description="SailZen Android APK 规范化构建与校验工具")
    parser.add_argument("--debug", action="store_true", help="构建 Debug APK（不校验 Release 签名与公网 URL）")
    parser.add_argument("--with-tests", action="store_true", help="构建前同时运行 testDebugUnitTest")
    parser.add_argument("--allow-debug-signing", action="store_true", help="允许 Release 回退使用 debug 签名")
    parser.add_argument("--allow-empty-url", action="store_true", help="允许 Release 未预设公网 URL")
    parser.add_argument("--dry-run", action="store_true", help="仅做前置护栏校验，不实际执行 Gradle")
    args = parser.parse_args()

    gradlew = ANDROID_DIR / ("gradlew.bat" if sys.platform.startswith("win") else "gradlew")
    if not gradlew.is_file():
        print(f"[FAIL] 未找到 Gradle Wrapper: {gradlew}", file=sys.stderr)
        return 1

    if not args.debug:
        issues = check_release_guardrails(
            allow_debug_signing=args.allow_debug_signing,
            allow_empty_url=args.allow_empty_url,
        )
        if issues:
            print("[FAIL] Android Release 构建护栏未通过：", file=sys.stderr)
            for item in issues:
                print(f"  - {item}", file=sys.stderr)
            return 1
        print("[OK] Release 服务器地址与签名配置护栏校验通过")

    tasks: List[str] = []
    if args.with_tests:
        tasks.append("testDebugUnitTest")
    tasks.append("assembleDebug" if args.debug else "assembleRelease")

    cmd = [str(gradlew), *tasks]
    print(f"[Android] Exec: {' '.join(cmd)} (cwd={ANDROID_DIR})")
    if args.dry_run:
        print("[DryRun] 前置校验完成，未执行 Gradle 构建。")
        return 0

    proc = subprocess.run(cmd, cwd=str(ANDROID_DIR))
    if proc.returncode != 0:
        print(f"[FAIL] Gradle 构建失败 (exit={proc.returncode})", file=sys.stderr)
        return proc.returncode

    variant = "debug" if args.debug else "release"
    apk_dir = ANDROID_DIR / "app" / "build" / "outputs" / "apk" / variant
    apks = sorted(apk_dir.glob("*.apk"))
    if not apks:
        print(f"[FAIL] 未在 {apk_dir} 找到生成的 APK", file=sys.stderr)
        return 1

    print("\n=== Android Build Artifact ===")
    for apk in apks:
        print(f"  APK   : {apk}")
        print(f"  Size  : {format_bytes(apk.stat().st_size)}")
        print(f"  SHA256: {_sha256(apk)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
