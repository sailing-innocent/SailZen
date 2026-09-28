# -*- coding: utf-8 -*-
# @file test_blog_api.py
# @brief Blog (Markdown review) API tests
# @author sailing-innocent
# @date 2026-05-05
# @version 1.0
# ---------------------------------
"""
博客模块 API 测试：
- 上传 Markdown 文件（multipart），返回内部文件名 + 预览地址
- 列表 / 内容 / 下载 / 删除 全链路
- 安全：非法文件名模式（路径遍历）返回 404
- 校验：非 UTF-8 内容 400，超大文件 413
"""
import pytest
from litestar import Litestar, Router
from litestar.plugins.pydantic import PydanticPlugin
from litestar.testing import TestClient

import sail_server.controller.blog as blog_module
from sail_server.controller.blog import BlogController

pytestmark = pytest.mark.server

BASE = "/api/v1/blog"

SAMPLE_MD = """# 测试报告

## 第一节

- 条目 A
- 条目 B

| 列1 | 列2 |
| --- | --- |
| a   | b   |

```python
print("hello")
```
"""


@pytest.fixture(scope="function")
def storage_dir(tmp_path, monkeypatch):
    """把博客存储目录指到临时目录，避免污染真实数据目录"""
    monkeypatch.setattr(blog_module, "STORAGE_DIR", tmp_path)
    return tmp_path


@pytest.fixture(scope="function")
def client(storage_dir) -> TestClient:
    """挂载 BlogController 的测试 App"""
    router = Router(path=BASE, route_handlers=[BlogController])
    app = Litestar(route_handlers=[router], plugins=[PydanticPlugin(prefer_alias=True)])
    with TestClient(app=app) as c:
        yield c


def _upload(client: TestClient, content: bytes, filename: str = "report.md"):
    return client.post(
        f"{BASE}/upload",
        files={"data": (filename, content, "text/markdown")},
    )


# ============================================================================
# 上传
# ============================================================================


class TestUpload:
    def test_upload_markdown_success(self, client: TestClient, storage_dir):
        resp = _upload(client, SAMPLE_MD.encode("utf-8"))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["original_name"] == "report.md"
        assert data["title"] == "测试报告"
        assert data["size"] == len(SAMPLE_MD.encode("utf-8"))
        assert data["filename"].endswith(".md")
        assert data["preview_url"] == f"/blog?content={data['filename']}"
        # 文件真实落盘
        assert (storage_dir / data["filename"]).exists()

    def test_upload_without_heading_uses_original_name(self, client: TestClient):
        resp = _upload(client, b"plain text content\n", filename="note.md")
        assert resp.status_code == 201, resp.text
        assert resp.json()["title"] == "note.md"

    def test_upload_rejects_binary(self, client: TestClient):
        resp = _upload(client, b"\xff\xfe\x00\x01binary")
        assert resp.status_code == 400

    def test_upload_rejects_oversize(self, client: TestClient):
        big = b"a" * (blog_module.MAX_FILE_SIZE + 1)
        resp = _upload(client, big)
        assert resp.status_code == 413


# ============================================================================
# 列表 / 内容 / 下载 / 删除
# ============================================================================


class TestCrud:
    def test_list_content_download_delete_flow(self, client: TestClient):
        # 上传两篇
        r1 = _upload(client, "# 第一篇\n\nalpha\n".encode("utf-8"))
        r2 = _upload(client, "# 第二篇\n\nbeta\n".encode("utf-8"))
        f1 = r1.json()["filename"]
        f2 = r2.json()["filename"]

        # 列表
        resp = client.get(f"{BASE}/list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        names = [a["filename"] for a in data["articles"]]
        assert f1 in names and f2 in names
        titles = {a["filename"]: a["title"] for a in data["articles"]}
        assert titles[f1] == "第一篇"
        assert titles[f2] == "第二篇"

        # 内容
        resp = client.get(f"{BASE}/content/{f1}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["content"] == "# 第一篇\n\nalpha\n"
        assert "第一篇" in body["content"]
        assert body["title"] == "第一篇"

        # 下载（保留原始文件名）
        resp = client.get(f"{BASE}/download/{f1}")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]
        assert resp.content.decode("utf-8") == "# 第一篇\n\nalpha\n"
        assert "第一篇" in resp.content.decode("utf-8")

        # 删除 f1
        resp = client.delete(f"{BASE}/delete/{f1}")
        assert resp.status_code == 200

        # 删除后内容 404，列表只剩一篇
        assert client.get(f"{BASE}/content/{f1}").status_code == 404
        assert client.get(f"{BASE}/download/{f1}").status_code == 404
        assert client.delete(f"{BASE}/delete/{f1}").status_code == 404
        data = client.get(f"{BASE}/list").json()
        assert data["total"] == 1
        assert data["articles"][0]["filename"] == f2

    def test_metadata_removed_after_delete(self, client: TestClient, storage_dir):
        resp = _upload(client, SAMPLE_MD.encode("utf-8"))
        filename = resp.json()["filename"]
        meta = blog_module.load_metadata()
        assert filename in meta
        client.delete(f"{BASE}/delete/{filename}")
        meta = blog_module.load_metadata()
        assert filename not in meta


# ============================================================================
# 安全
# ============================================================================


class TestSecurity:
    @pytest.mark.parametrize("bad_name", ["../secret.md", "..", "a/b.md", "plain.md", "x.md.txt"])
    def test_invalid_filename_rejected(self, client: TestClient, bad_name: str):
        assert client.get(f"{BASE}/content/{bad_name}").status_code == 404
        assert client.get(f"{BASE}/download/{bad_name}").status_code == 404
        assert client.delete(f"{BASE}/delete/{bad_name}").status_code == 404
