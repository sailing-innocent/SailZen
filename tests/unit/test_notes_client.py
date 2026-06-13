# -*- coding: utf-8 -*-
# @file test_notes_client.py
# @brief NotesClient CLI 单元测试
# @author sailing-innocent
# @date 2026-07-13
# @version 1.0
# ---------------------------------

"""NotesClient 本地 Markdown 笔记库单元测试。"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from sailzen.cli.notes_client import NotesClient, Note, _parse_tags


class TestNotesClient:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.client = NotesClient(self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_empty(self):
        assert self.client.list_notes() == []

    def test_write_and_get(self):
        note = Note(
            fname="daily.2026-07-13",
            title="今日记录",
            body="测试正文",
            tags=["dev"],
        )
        path = self.client.write(note)
        assert path.exists()

        loaded = self.client.get("daily.2026-07-13")
        assert loaded is not None
        assert loaded.title == "今日记录"
        assert loaded.body == "测试正文"
        assert loaded.tags == ["dev"]

    def test_list_and_prefix_filter(self):
        self.client.write(Note(fname="daily.2026-07-13", title="A"))
        self.client.write(Note(fname="daily.2026-07-14", title="B"))
        self.client.write(Note(fname="seeds.python", title="C"))

        all_notes = self.client.list_notes()
        assert len(all_notes) == 3

        daily_notes = self.client.list_notes(prefix="daily")
        assert len(daily_notes) == 2

    def test_search(self):
        self.client.write(Note(fname="daily.2026-07-13", body="学习 Python"))
        self.client.write(Note(fname="daily.2026-07-14", body="休息"))

        results = self.client.search("Python")
        assert len(results) == 1
        assert results[0][0] == "daily.2026-07-13"

    def test_delete(self):
        self.client.write(Note(fname="daily.2026-07-13", title="A"))
        assert self.client.delete("daily.2026-07-13") is True
        assert self.client.get("daily.2026-07-13") is None
        assert self.client.delete("daily.2026-07-13") is False

    def test_frontmatter_parsing(self):
        md = """---
id: daily.2026-07-13
title: 测试
tags:
  - tag1
  - tag2
created: 2026-01-01T00:00:00
updated: 2026-01-02T00:00:00
---

正文内容
"""
        path = Path(self.tmpdir) / "daily" / "2026-07-13.md"
        path.parent.mkdir(parents=True)
        path.write_text(md, encoding="utf-8")

        note = self.client.get("daily.2026-07-13")
        assert note.title == "测试"
        assert note.tags == ["tag1", "tag2"]
        assert note.body.strip() == "正文内容"


class TestTagParser:
    def test_parse_tags(self):
        assert _parse_tags("a,b,c") == ["a", "b", "c"]
        assert _parse_tags(" a , b ") == ["a", "b"]
        assert _parse_tags("") == []
        assert _parse_tags(None) == []
