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
RELEASE_REQUIRED_SIGNING_KEYS = (
    "SAILZEN_STORE_FILE",
    "SAILZEN_STORE_PASSWORD",
    "SAILZEN_KEY_ALIAS",
    "SAILZEN_KEY_PASSWORD",
)


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


def check_release_guardrails(
    *, allow_debug_signing: bool = False, allow_empty_url: bool = False
) -> List[str]:
    """校验 Release 构建所需配置，返回缺失/告警项列表。"""
    merged_props: Dict[str, str] = {}
    merged_props.update(_read_gradle_properties(Path.home() / ".gradle" / "gradle.properties"))
    merged_props.update(_read_gradle_properties(ANDROID_DIR / "gradle.properties"))

    issues: List[str] = []
    if not allow_empty_url:
        url = _resolve_prop("SAILZEN_RELEASE_SERVER_URL", merged_props)
        if not url:
            issues.append(
                "缺少 SAILZEN_RELEASE_SERVER_URL（请在 ~/.gradle/gradle.properties 或环境变量中配置公网服务地址）"
            )
    if not allow_debug_signing:
        missing = [k for k in RELEASE_REQUIRED_SIGNING_KEYS if not _resolve_prop(k, merged_props)]
        if missing:
            issues.append(
                f"缺少 Release 签名配置: {', '.join(missing)}（请在 ~/.gradle/gradle.properties 配置，严禁入库）"
            )
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
