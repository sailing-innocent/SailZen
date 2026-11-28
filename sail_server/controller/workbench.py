# -*- coding: utf-8 -*-
# @file workbench.py
# @brief SailZen Workbench Controller (/api/v1/workbench)
# @author sailing-innocent
# @date 2026-11-27
# @version 1.0
# ---------------------------------

from __future__ import annotations

import json
import logging
import os
import re
from contextlib import contextmanager
from datetime import date as date_type
from pathlib import Path
from typing import Generator, Optional

from litestar import Controller, Request, get, put
from litestar.exceptions import ClientException, NotAuthorizedException, NotFoundException
from litestar.response import File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sail_server.config.paths import get_vscode_releases_dir

from sail_server.application.dto.workbench import (
    WorkbenchBootstrapResponse,
    WorkbenchContextPackResponse,
    WorkbenchProjectItem,
    WorkbenchProjectMetaUpdateRequest,
)
from sail_server.model.rhythm import (
    RhythmBadRequestError,
    RhythmNotFoundError,
    RhythmStateConflictError,
)
from sail_server.model.workbench import (
    build_workbench_context_pack_impl,
    get_workbench_bootstrap_impl,
    update_workbench_project_meta_impl,
)

logger = logging.getLogger(__name__)


def _check_auth(request: Request) -> None:
    expected = os.environ.get("SAILZEN_API_TOKEN", "")
    if not expected:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {expected}":
        raise NotAuthorizedException(detail="invalid or missing bearer token")


@contextmanager
def _map_errors():
    try:
        yield
    except RhythmNotFoundError as exc:
        raise NotFoundException(detail=str(exc)) from exc
    except RhythmStateConflictError as exc:
        raise ClientException(status_code=409, detail=str(exc)) from exc
    except (RhythmBadRequestError, ValueError) as exc:
        raise ClientException(status_code=400, detail=str(exc)) from exc


class WorkbenchController(Controller):
    """VS Code 工作与创作工作台聚合控制器。"""

    path = "/"

    @get("/bootstrap")
    async def bootstrap(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: Optional[date_type] = None,
    ) -> WorkbenchBootstrapResponse:
        """GET /api/v1/workbench/bootstrap?date=YYYY-MM-DD"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_workbench_bootstrap_impl(db, date)

    @put("/project/{venture_id:int}")
    async def update_project_meta(
        self,
        venture_id: int,
        data: WorkbenchProjectMetaUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> WorkbenchProjectItem:
        """PUT /api/v1/workbench/project/{venture_id}"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return update_workbench_project_meta_impl(db, venture_id, data)

    @get("/context-pack/{venture_id:int}")
    async def get_context_pack(
        self,
        venture_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> WorkbenchContextPackResponse:
        """GET /api/v1/workbench/context-pack/{venture_id}"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return build_workbench_context_pack_impl(db, venture_id)


# ============================================================================
# VS Code Extension VSIX OTA Release Controller (/api/v1/workbench/release)
# ============================================================================

VSIX_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+\.vsix$")
VSIX_MEDIA_TYPE = "application/vsix"


class WorkbenchReleaseInfo(BaseModel):
    """VS Code 插件最新 VSIX Release 元数据响应。"""

    version: str = Field(description="插件 semver 版本号（如 0.3.0）")
    file_name: str = Field(description="VSIX 文件名")
    size: int = Field(description="VSIX 字节大小")
    sha256: str = Field(default="", description="VSIX SHA-256 十六进制校验和")
    release_notes: str = Field(default="", description="版本更新说明")
    published_at: str = Field(default="", description="发布时间（ISO-8601）")
    download_path: str = Field(description="VSIX 下载相对路径")


def _validate_vsix_filename(filename: str) -> str:
    if not filename or not VSIX_FILENAME_PATTERN.fullmatch(filename) or ".." in filename:
        raise ClientException(status_code=400, detail="invalid vsix filename")
    return filename


def _resolve_vsix_path(releases_dir: Path, filename: str) -> Path:
    safe_name = _validate_vsix_filename(filename)
    root = releases_dir.resolve()
    target = (root / safe_name).resolve()
    if target.parent != root:
        raise ClientException(status_code=400, detail="invalid vsix path")
    if not target.is_file():
        raise NotFoundException(detail=f"vsix not found: {safe_name}")
    return target


def _load_latest_vsix_release(releases_dir: Path) -> tuple[WorkbenchReleaseInfo, Path]:
    manifest_path = releases_dir / "latest.json"
    if not manifest_path.is_file():
        raise NotFoundException(detail="no vscode workbench release published yet")

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NotFoundException(detail=f"invalid vsix release manifest: {exc}") from exc

    if not isinstance(raw, dict):
        raise NotFoundException(detail="invalid vsix release manifest payload")

    file_name = str(raw.get("file_name") or "").strip()
    vsix_path = _resolve_vsix_path(releases_dir, file_name)

    version = str(raw.get("version") or "").strip()
    if not version:
        raise NotFoundException(detail="missing version in vsix release manifest")

    api_endpoint = os.environ.get("API_ENDPOINT", "/api/v1").rstrip("/")
    download_path = f"{api_endpoint}/workbench/release/download/{vsix_path.name}"

    info = WorkbenchReleaseInfo(
        version=version,
        file_name=vsix_path.name,
        size=int(raw.get("size") or vsix_path.stat().st_size),
        sha256=str(raw.get("sha256") or ""),
        release_notes=str(raw.get("release_notes") or ""),
        published_at=str(raw.get("published_at") or ""),
        download_path=download_path,
    )
    return info, vsix_path


class WorkbenchReleaseController(Controller):
    """VS Code 插件 VSIX OTA 分发控制器（/api/v1/workbench/release）。"""

    path = "/release"

    @get("/latest")
    async def get_latest_release(self, request: Request) -> WorkbenchReleaseInfo:
        """获取最新 VS Code 插件 VSIX 元数据。"""
        _check_auth(request)
        info, _ = _load_latest_vsix_release(get_vscode_releases_dir())
        return info

    @get("/latest.vsix")
    async def download_latest_vsix(self, request: Request) -> File:
        """直接流式下载最新版 VSIX。"""
        _check_auth(request)
        _, vsix_path = _load_latest_vsix_release(get_vscode_releases_dir())
        return File(
            path=str(vsix_path),
            filename=vsix_path.name,
            media_type=VSIX_MEDIA_TYPE,
        )

    @get("/download/{filename:str}")
    async def download_vsix(self, request: Request, filename: str) -> File:
        """按文件名流式下载指定 VSIX。"""
        _check_auth(request)
        vsix_path = _resolve_vsix_path(get_vscode_releases_dir(), filename)
        return File(
            path=str(vsix_path),
            filename=vsix_path.name,
            media_type=VSIX_MEDIA_TYPE,
        )
