# -*- coding: utf-8 -*-
# @file test_note_links.py
# @brief note_links 工具单元测试
# @author sailing-innocent
# @date 2026-08-06
# @version 1.0
# ---------------------------------

"""sail_server.utils.note_links 单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from sail_server.utils.note_links import (
    parse_wiki_links,
    build_link_graph,
    make_note_slug,
    make_note_setting_file,
    normalize_note_content,
)


class TestParseWikiLinks:
    def test_simple_link(self):
        content = "请参考 [[魔法体系]] 相关设定。"
        links = parse_wiki_links(content)
        assert len(links) == 1
        assert links[0]["target"] == "魔法体系"
        assert links[0]["display"] == "魔法体系"

    def test_link_with_heading(self):
        content = "[[王都#皇宫]] 是权力中心。"
        links = parse_wiki_links(content)
        assert len(links) == 1
        assert links[0]["target"] == "王都"
        assert links[0]["heading"] == "皇宫"

    def test_link_with_display(self):
        content = "[[魔法体系|法术]]"
        links = parse_wiki_links(content)
        assert len(links) == 1
        assert links[0]["target"] == "魔法体系"
        assert links[0]["display"] == "法术"

    def test_category_slug_link(self):
        content = "[[settings/魔法体系]]"
        links = parse_wiki_links(content)
        assert links[0]["target"] == "settings/魔法体系"

    def test_no_link(self):
        content = "普通 Markdown [链接](http://example.com)"
        links = parse_wiki_links(content)
        assert len(links) == 0


class TestBuildLinkGraph:
    def test_graph_with_workspace(self, tmp_path: Path):
        notes = [
            (1, "主角", "notes/text/characters/protagonist.md"),
            (2, "魔法体系", "notes/text/settings/magic.md"),
        ]
        # 创建文件
        file1 = tmp_path / "notes/text/characters/protagonist.md"
        file2 = tmp_path / "notes/text/settings/magic.md"
        file1.parent.mkdir(parents=True, exist_ok=True)
        file2.parent.mkdir(parents=True, exist_ok=True)
        file1.write_text("主角使用 [[settings/魔法体系]]。", encoding="utf-8")
        file2.write_text("魔法体系设定。", encoding="utf-8")

        graph = build_link_graph(notes, workspace_root=tmp_path)
        assert len(graph["nodes"]) == 2
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["source"] == 1
        assert graph["edges"][0]["target"] == 2


class TestSlugAndSettingFile:
    def test_make_slug(self):
        assert make_note_slug("Alice Mage") == "Alice_Mage"
        assert make_note_slug("魔法体系") == "魔法体系"

    def test_make_setting_file(self):
        assert make_note_setting_file("character", "alice") == "notes/text/characters/alice.md"
        assert make_note_setting_file("history", "event-1") == "notes/text/history/event-1.md"


class TestNormalizeNoteContent:
    def test_add_frontmatter(self):
        content = "## 描述\n一个魔法师。"
        result = normalize_note_content(
            content, note_id=42, category="character", title="Alice", slug="alice"
        )
        assert result.startswith("---")
        assert "id: 42" in result
        assert "category: character" in result
        assert "## 描述" in result

    def test_merge_existing_frontmatter(self):
        content = "---\ntitle: Old\ncategory: character\n---\n\n正文"
        result = normalize_note_content(
            content, note_id=42, category="character", title="Alice", slug="alice"
        )
        assert result.startswith("---")
        assert "id: 42" in result
        assert "title: Alice" in result
        assert "正文" in result
