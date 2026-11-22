# -*- coding: utf-8 -*-
# @file init_android_signing.py
# @brief One-command self-signed Android Release keystore & android/keystore.properties initializer
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""一键初始化 Android 自签名 Release 证书与项目本地 android/keystore.properties。

说明：
- Android 所有 Release 包（包括上架商店的正式包）本质上都是通过 JDK `keytool` 生成的自签名证书；
  只要长期固定使用同一份 .jks 证书，后续所有 OTA APK 即可直接覆盖安装，无需卸载重装。
- 产物全部落在项目本地且已在 android/.gitignore 忽略的路径下：
  - android/keystore/sailzen-release.jks
  - android/keystore.properties
  无需手动寻找或修改系统用户目录（~/.gradle/gradle.properties）。

用法:
    uv run python scripts/ops/init_android_signing.py --server-url http://101.43.22.254
    uv run python scripts/ops/init_android_signing.py --server-url http://101.43.22.254 --alias sailzen
"""

from __future__ import annotations

import argparse
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops.build_android_release import ANDROID_DIR
from scripts.ops.common import configure_console_utf8, load_ops_config

DEFAULT_KEYSTORE_REL = "keystore/sailzen-release.jks"
DEFAULT_PROPS_PATH = ANDROID_DIR / "keystore.properties"
DEFAULT_ALIAS = "sailzen"
DEFAULT_VALIDITY_DAYS = 10000  # ~27 年，个人项目一次生成终身使用


def _find_keytool() -> Path:
    hit = shutil.which("keytool")
    if hit:
        return Path(hit)
    raise FileNotFoundError("未在 PATH 中找到 JDK `keytool`，请确认已安装 JDK 17+。")


def init_android_signing(
    *,
    server_url: str,
    android_dir: Path = ANDROID_DIR,
    keystore_rel: str = DEFAULT_KEYSTORE_REL,
    alias: str = DEFAULT_ALIAS,
    password: Optional[str] = None,
    validity_days: int = DEFAULT_VALIDITY_DAYS,
    force: bool = False,
) -> tuple[Path, Path]:
    """生成自签名 JKS 证书并写入 android/keystore.properties。"""
    clean_url = server_url.strip().rstrip("/")
    if not clean_url:
        raise ValueError("server_url 不能为空，例如 http://101.43.22.254")
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        raise ValueError(f"server_url 必须以 http:// 或 https:// 开头，当前值: {clean_url!r}")

    keystore_path = (android_dir / keystore_rel).resolve()
    props_path = (android_dir / "keystore.properties").resolve()

    if keystore_path.exists() and not force:
        raise FileExistsError(
            f"证书已存在: {keystore_path}（避免误覆盖导致手机无法覆盖安装！如需强行重建请加 --force）"
        )
    if props_path.exists() and not force:
        raise FileExistsError(
            f"配置文件已存在: {props_path}（如需覆盖请加 --force，或直接手动编辑该文件）"
        )

    keytool = _find_keytool()
    pwd = (password or "").strip() or secrets.token_urlsafe(18)
    if len(pwd) < 6:
        raise ValueError("keystore 密码长度至少为 6 位")

    keystore_path.parent.mkdir(parents=True, exist_ok=True)
    if keystore_path.exists() and force:
        keystore_path.unlink()

    cmd = [
        str(keytool),
        "-genkeypair",
        "-v",
        "-storetype",
        "PKCS12",
        "-keystore",
        str(keystore_path),
        "-alias",
        alias,
        "-keyalg",
        "RSA",
        "-keysize",
        "2048",
        "-validity",
        str(validity_days),
        "-storepass",
        pwd,
        "-keypass",
        pwd,
        "-dname",
        "CN=SailZen Personal, OU=Personal, O=SailZen, L=Local, ST=Local, C=CN",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"keytool 生成自签名证书失败 (exit={proc.returncode}):\n{detail}")

    props_content = (
        "# SailZen Android 本地自签名 Release 配置（已在 android/.gitignore 中忽略，严禁提交）\n"
        f"SAILZEN_RELEASE_SERVER_URL={clean_url}\n"
        f"SAILZEN_RELEASE_STORE_FILE={keystore_rel.replace(chr(92), '/')}\n"
        f"SAILZEN_RELEASE_STORE_PASSWORD={pwd}\n"
        f"SAILZEN_RELEASE_KEY_ALIAS={alias}\n"
        f"SAILZEN_RELEASE_KEY_PASSWORD={pwd}\n"
    )
    props_path.write_text(props_content, encoding="utf-8")
    return keystore_path, props_path


def main() -> int:
    configure_console_utf8()
    parser = argparse.ArgumentParser(
        description="一键生成 Android 自签名 Release 证书与 android/keystore.properties"
    )
    parser.add_argument(
        "--server-url",
        default=None,
        help="公网服务器地址（留空时自动从 .env.ops/.env.prod 推导，如 http://101.43.22.254:4399）",
    )
    parser.add_argument("--alias", default=DEFAULT_ALIAS, help=f"证书别名（默认 {DEFAULT_ALIAS}）")
    parser.add_argument("--password", default=None, help="自定义证书密码（留空则自动生成强随机密码）")
    parser.add_argument("--force", action="store_true", help="强制覆盖已有证书与配置文件（慎用！）")
    args = parser.parse_args()

    resolved_url = args.server_url
    if not resolved_url:
        try:
            resolved_url = load_ops_config().get_server_url("prod")
            print(f"[Config] 自动从 .env.prod/.env.ops 推导公网地址: {resolved_url}")
        except RuntimeError as exc:
            print(f"[FAIL] 未指定 --server-url 且无法自动推导: {exc}", file=sys.stderr)
            return 1

    try:
        keystore_path, props_path = init_android_signing(
            server_url=resolved_url,
            alias=args.alias,
            password=args.password,
            force=args.force,
        )
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    print("[OK] Android 自签名 Release 证书初始化完成：")
    print(f"  Keystore : {keystore_path}")
    print(f"  Config   : {props_path}")
    print("\n[提示]")
    print("  1. 以上两个文件均已在 android/.gitignore 中忽略，不会被 git 提交。")
    print("  2. 请将这两个文件单独备份到网盘/密码管理器：以后换电脑只要还原它们，手机就能无缝覆盖更新。")
    print("  3. 现在可以运行 `uv run python scripts/ops/publish_android_apk.py --dry-run` 验证护栏。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
