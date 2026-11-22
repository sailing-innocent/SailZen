# -*- coding: utf-8 -*-
# @file app_release.py
# @brief Android APK OTA Release Controller
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""Android APK OTA 自动更新分发控制器。

REST 契约（/api/v1/app）:
- GET /release/latest                获取最新发布元数据（latest.json）
- GET /release/latest.apk            直接流式下载最新 APK
- GET /release/download/{filename}   按文件名流式下载指定 APK

存储位置：
- 默认 <SERVER_DATA_DIR>/app_releases/（可通过环境变量 APP_RELEASES_PATH 覆写）
- 发布端通过 scripts/ops/publish_android_apk.py 经 SCP 原子写入 .apk 与 latest.json

鉴权：复用 SAILZEN_API_TOKEN 可选 Bearer 模式（未配置则放行）。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from litestar import Controller, Request, get
from litestar.exceptions import ClientException, NotAuthorizedException, NotFoundException
from litestar.response import File
from pydantic import BaseModel, Field

from sail_server.config.paths import get_app_releases_dir

APK_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+\.apk$")
APK_MEDIA_TYPE = "application/vnd.android.package-archive"


def _check_auth(request: Request) -> None:
    """可选 Bearer Token 鉴权：env SAILZEN_API_TOKEN 未设置则放行。"""
    expected = os.environ.get("SAILZEN_API_TOKEN", "").strip()
    if not expected:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {expected}":
        raise NotAuthorizedException(detail="invalid or missing bearer token")


def _validate_apk_filename(filename: str) -> str:
    if not filename or not APK_FILENAME_PATTERN.fullmatch(filename) or ".." in filename:
        raise ClientException(status_code=400, detail="invalid apk filename")
    return filename


def _resolve_apk_path(releases_dir: Path, filename: str) -> Path:
    safe_name = _validate_apk_filename(filename)
    root = releases_dir.resolve()
    target = (root / safe_name).resolve()
    if target.parent != root:
        raise ClientException(status_code=400, detail="invalid apk path")
    if not target.is_file():
        raise NotFoundException(detail=f"apk not found: {safe_name}")
    return target


class AppReleaseInfo(BaseModel):
    """Android 最新 Release 元数据响应。"""

    version_code: int = Field(description="Android versionCode（递增整数）")
    version_name: str = Field(description="Android versionName（如 0.2.0）")
    file_name: str = Field(description="APK 文件名")
    size: int = Field(description="APK 字节大小")
    sha256: str = Field(default="", description="APK SHA-256 十六进制校验和")
    release_notes: str = Field(default="", description="版本更新说明")
    published_at: str = Field(default="", description="发布时间（ISO-8601）")
    download_path: str = Field(description="APK 下载相对路径")


def _load_latest_release(releases_dir: Path) -> tuple[AppReleaseInfo, Path]:
    manifest_path = releases_dir / "latest.json"
    if not manifest_path.is_file():
        raise NotFoundException(detail="no android release published yet")

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NotFoundException(detail=f"invalid release manifest: {exc}") from exc

    if not isinstance(raw, dict):
        raise NotFoundException(detail="invalid release manifest payload")

    file_name = str(raw.get("file_name") or "").strip()
    apk_path = _resolve_apk_path(releases_dir, file_name)

    api_endpoint = os.environ.get("API_ENDPOINT", "/api/v1").rstrip("/")
    download_path = f"{api_endpoint}/app/release/download/{apk_path.name}"

    try:
        version_code = int(raw["version_code"])
    except (KeyError, TypeError, ValueError) as exc:
        raise NotFoundException(detail="invalid version_code in release manifest") from exc

    info = AppReleaseInfo(
        version_code=version_code,
        version_name=str(raw.get("version_name") or ""),
        file_name=apk_path.name,
        size=int(raw.get("size") or apk_path.stat().st_size),
        sha256=str(raw.get("sha256") or ""),
        release_notes=str(raw.get("release_notes") or ""),
        published_at=str(raw.get("published_at") or ""),
        download_path=download_path,
    )
    return info, apk_path


class AppReleaseController(Controller):
    """Android 应用发布与 OTA 下载控制器。"""

    path = "/release"

    @get("/latest")
    async def get_latest_release(self, request: Request) -> AppReleaseInfo:
        """获取最新 Android Release 元数据。"""
        _check_auth(request)
        releases_dir = get_app_releases_dir()
        info, _ = _load_latest_release(releases_dir)
        return info

    @get("/latest.apk")
    async def download_latest_apk(self, request: Request) -> File:
        """直接流式下载最新版 APK。"""
        _check_auth(request)
        releases_dir = get_app_releases_dir()
        _, apk_path = _load_latest_release(releases_dir)
        return File(
            path=str(apk_path),
            filename=apk_path.name,
            media_type=APK_MEDIA_TYPE,
        )

    @get("/download/{filename:str}")
    async def download_apk(self, request: Request, filename: str) -> File:
        """按文件名流式下载指定 APK。"""
        _check_auth(request)
        releases_dir = get_app_releases_dir()
        apk_path = _resolve_apk_path(releases_dir, filename)
        return File(
            path=str(apk_path),
            filename=apk_path.name,
            media_type=APK_MEDIA_TYPE,
        )
