# -*- coding: utf-8 -*-
# @file test_app_release_api.py
# @brief Android APK OTA Release API tests
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""验证 /api/v1/app/release/* 元数据读取、APK 流式下载、鉴权与路径穿越防护。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from litestar import Litestar, Router
from litestar.plugins.pydantic import PydanticPlugin
from litestar.testing import TestClient

from sail_server.controller.app_release import AppReleaseController

pytestmark = pytest.mark.server

BASE = "/api/v1/app/release"


@pytest.fixture(scope="function")
def app_client(tmp_path: Path, monkeypatch):
    releases_dir = tmp_path / "app_releases"
    releases_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APP_RELEASES_PATH", str(releases_dir))
    monkeypatch.delenv("SAILZEN_API_TOKEN", raising=False)

    app_release_router = Router(path="/app", route_handlers=[AppReleaseController])
    api_router = Router(path="/api/v1", route_handlers=[app_release_router])
    app = Litestar(
        route_handlers=[api_router],
        plugins=[PydanticPlugin(prefer_alias=True)],
    )
    with TestClient(app=app) as client:
        yield client, releases_dir


def _seed_release(releases_dir: Path, *, version_code: int = 2, version_name: str = "0.2.0"):
    apk_bytes = b"PK\x03\x04fake-apk-payload-for-sailzen"
    sha = hashlib.sha256(apk_bytes).hexdigest()
    apk_name = f"SailZen-{version_name}-vc{version_code}-release.apk"
    (releases_dir / apk_name).write_bytes(apk_bytes)
    manifest = {
        "version_code": version_code,
        "version_name": version_name,
        "file_name": apk_name,
        "size": len(apk_bytes),
        "sha256": sha,
        "release_notes": "支持应用内自动更新",
        "published_at": "2026-11-22T22:45:00+08:00",
    }
    (releases_dir / "latest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return apk_name, apk_bytes, sha


def test_latest_returns_404_when_unpublished(app_client):
    client, _ = app_client
    resp = client.get(f"{BASE}/latest")
    assert resp.status_code == 404


def test_latest_and_download_apk_success(app_client):
    client, releases_dir = app_client
    apk_name, apk_bytes, sha = _seed_release(releases_dir, version_code=5, version_name="0.3.0")

    resp = client.get(f"{BASE}/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version_code"] == 5
    assert data["version_name"] == "0.3.0"
    assert data["file_name"] == apk_name
    assert data["size"] == len(apk_bytes)
    assert data["sha256"] == sha
    assert data["release_notes"] == "支持应用内自动更新"
    assert data["download_path"] == f"{BASE}/download/{apk_name}"

    dl = client.get(data["download_path"])
    assert dl.status_code == 200
    assert dl.content == apk_bytes
    assert "application/vnd.android.package-archive" in dl.headers.get("content-type", "")

    latest_dl = client.get(f"{BASE}/latest.apk")
    assert latest_dl.status_code == 200
    assert latest_dl.content == apk_bytes


def test_bearer_token_auth_enforced_when_configured(app_client, monkeypatch):
    client, releases_dir = app_client
    apk_name, _, _ = _seed_release(releases_dir)
    monkeypatch.setenv("SAILZEN_API_TOKEN", "secret-ota-token")

    assert client.get(f"{BASE}/latest").status_code == 401
    assert client.get(f"{BASE}/download/{apk_name}").status_code == 401
    assert client.get(
        f"{BASE}/latest", headers={"Authorization": "Bearer wrong-token"}
    ).status_code == 401

    ok = client.get(f"{BASE}/latest", headers={"Authorization": "Bearer secret-ota-token"})
    assert ok.status_code == 200


def test_download_rejects_invalid_or_traversal_filenames(app_client):
    client, releases_dir = app_client
    _seed_release(releases_dir)

    for bad_name in ("latest.json", "foo..bar.apk", "not-an-apk.txt"):
        resp = client.get(f"{BASE}/download/{bad_name}")
        assert resp.status_code == 400

    assert client.get(f"{BASE}/download/missing-release.apk").status_code == 404
