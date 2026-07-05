# -*- coding: utf-8 -*-
# @file test_note_client.py
# @brief NoteClient CLI 单元测试
# @author sailing-innocent
# @date 2026-08-06
# @version 1.0
# ---------------------------------

"""sailzen.cli.note_client 单元测试（使用 unittest.mock）。"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from sailzen.cli.note_client import NoteItemClient


@pytest.fixture
def workspace():
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def client(workspace: str):
    return NoteItemClient("http://localhost:8000", workspace)


class MockResponse:
    """模拟 requests.Response"""

    def __init__(self, json_data=None, status_code=200, text=""):
        self.json_data = json_data
        self.status_code = status_code
        self.text = text

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class TestNoteItemClient:
    def test_list_notes(self, client: NoteItemClient):
        mock_resp = MockResponse(
            json_data={
                "notes": [
                    {
                        "id": 1,
                        "category": "character",
                        "title": "Alice",
                        "slug": "alice",
                        "setting_file": "notes/text/characters/alice.md",
                    }
                ],
                "total": 1,
            }
        )
        with patch.object(client.session, "get", return_value=mock_resp):
            notes = client.list_notes()
        assert len(notes) == 1
        assert notes[0]["title"] == "Alice"

    def test_create_note(self, client: NoteItemClient, workspace: str):
        def side_effect(url, **kwargs):
            if url.endswith("/api/v1/text/note/"):
                return MockResponse(
                    json_data={
                        "id": 42,
                        "category": "character",
                        "title": "Alice",
                        "slug": "alice",
                        "setting_file": "notes/text/characters/alice.md",
                    }
                )
            if "/content" in url:
                return MockResponse(
                    json_data={
                        "id": 42,
                        "setting_file": "notes/text/characters/alice.md",
                        "content": "test",
                    }
                )
            return MockResponse(status_code=404)

        with patch.object(client.session, "post", side_effect=side_effect):
            with patch.object(client.session, "put", side_effect=side_effect):
                created = client.create_note(
                    {
                        "category": "character",
                        "setting_file": "notes/text/characters/alice.md",
                        "title": "Alice",
                        "slug": "alice",
                    }
                )
        assert created["id"] == 42

    def test_write_and_read_local_note(self, client: NoteItemClient, workspace: str):
        setting_file = "notes/text/characters/bob.md"
        content = "---\ntitle: Bob\ncategory: character\n---\n\nBob 是一名战士。"
        path = client.write_local_note(setting_file, content)
        assert path.exists()

        meta, body = client.read_local_note(path)
        assert meta["title"] == "Bob"
        assert "战士" in body

    def test_scan_local_notes(self, client: NoteItemClient, workspace: str):
        root = Path(workspace)
        (root / "notes/text/characters").mkdir(parents=True)
        (root / "notes/text/settings").mkdir(parents=True)
        (root / "notes/text/characters/a.md").write_text("A", encoding="utf-8")
        (root / "notes/text/settings/b.md").write_text("B", encoding="utf-8")

        files = client.scan_local_notes()
        assert len(files) == 2

    def test_guess_category_from_path(self):
        from sailzen.cli.note_client import _guess_category_from_path

        assert _guess_category_from_path("notes/text/characters/alice.md") == "character"
        assert _guess_category_from_path("notes/text/settings/magic.md") == "setting"
        assert _guess_category_from_path("notes/text/history/event.md") == "history"
