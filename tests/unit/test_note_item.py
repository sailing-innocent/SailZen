# -*- coding: utf-8 -*-
# @file test_note_item.py
# @brief NoteItem ORM / DAO / Model 单元测试
# @author sailing-innocent
# @date 2026-08-06
# @version 1.0
# ---------------------------------

"""NoteItem 后端单元测试（依赖数据库）。"""

from __future__ import annotations

import pytest

from sail_server.infrastructure.orm.text import NoteItem, Work
from sail_server.data.dao.text import NoteItemDAO  # direct module import avoids broken __init__
from sail_server.application.dto.text import NoteItemCreateRequest, NoteItemUpdateRequest
from sail_server.model.text import (
    create_note_item_impl,
    get_note_item_impl,
    get_note_items_impl,
    update_note_item_impl,
    delete_note_item_impl,
)


@pytest.mark.db
class TestNoteItemDAO:
    def test_create_and_get(self, db):
        dao = NoteItemDAO(db)
        note = NoteItem(
            category="character",
            setting_file="notes/text/characters/alice.md",
            title="Alice",
            slug="alice",
            meta_data={"tags": ["protagonist"]},
        )
        created = dao.create(note)
        assert created.id is not None

        found = dao.get_by_id(created.id)
        assert found is not None
        assert found.title == "Alice"

    def test_filter_by_category(self, db):
        dao = NoteItemDAO(db)
        dao.create(
            NoteItem(
                category="character",
                setting_file="notes/text/characters/a.md",
                title="A",
                slug="a",
            )
        )
        dao.create(
            NoteItem(
                category="setting",
                setting_file="notes/text/settings/b.md",
                title="B",
                slug="b",
            )
        )
        results = dao.get_by_category("character")
        assert len(results) == 1
        assert results[0].slug == "a"

    def test_filter_notes(self, db):
        dao = NoteItemDAO(db)
        dao.create(
            NoteItem(
                category="character",
                setting_file="notes/text/characters/c.md",
                title="C",
                slug="c",
                work_id=1,
            )
        )
        results = dao.filter_notes(category="character", work_id=1)
        assert len(results) == 1


@pytest.mark.db
class TestNoteItemModel:
    def test_create_and_get(self, db):
        req = NoteItemCreateRequest(
            category="character",
            setting_file="notes/text/characters/bob.md",
            title="Bob",
            slug="bob",
            work_id=None,
            edition_id=None,
            meta_data={"tags": ["mage"]},
        )
        created = create_note_item_impl(db, req)
        assert created.id is not None
        assert created.title == "Bob"

        found = get_note_item_impl(db, created.id)
        assert found is not None
        assert found.slug == "bob"

    def test_update_and_delete(self, db):
        req = NoteItemCreateRequest(
            category="setting",
            setting_file="notes/text/settings/magic.md",
            title="Magic",
            slug="magic",
        )
        created = create_note_item_impl(db, req)

        updated = update_note_item_impl(
            db, created.id, NoteItemUpdateRequest(title="Magic System")
        )
        assert updated is not None
        assert updated.title == "Magic System"

        deleted = delete_note_item_impl(db, created.id)
        assert deleted is not None
        assert get_note_item_impl(db, created.id) is None

    def test_list_filter(self, db):
        create_note_item_impl(
            db,
            NoteItemCreateRequest(
                category="character",
                setting_file="notes/text/characters/x.md",
                title="X",
                slug="x",
            ),
        )
        create_note_item_impl(
            db,
            NoteItemCreateRequest(
                category="outline",
                setting_file="notes/text/outlines/y.md",
                title="Y",
                slug="y",
            ),
        )
        results = get_note_items_impl(db, category="outline")
        assert len(results) >= 1
        assert all(r.category == "outline" for r in results)
