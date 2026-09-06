# -*- coding: utf-8 -*-
# @file test_text_note.py
# @brief NoteItem（阅读批注）服务端链路加固回归测试：S1-S3
# @author sailing-innocent
# ---------------------------------
"""
覆盖：
- S1: NoteItemUpdateRequest 支持携带 content
- S2: update_note_item_impl 写正文文件
- S3: create 默认路径带 uuid 后缀防覆盖；delete 清理 notes/annotations/ 下文件
- 路径遍历统一抛 litestar ClientException（500 -> 400）
"""
import re

import pytest
from litestar.exceptions import ClientException

import sail_server.model.text as text_model
from sail_server.application.dto.text import (
    NoteItemCreateRequest,
    NoteItemUpdateRequest,
)

pytestmark = pytest.mark.server


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """把 SERVER_DATA_DIR 指到临时目录，避免污染真实 workspace"""
    monkeypatch.setattr(text_model, "SERVER_DATA_DIR", tmp_path)
    return tmp_path


def _create(**kwargs) -> NoteItemCreateRequest:
    payload = {"category": "annotation", "work_id": 1, "title": "测试批注"}
    payload.update(kwargs)
    return NoteItemCreateRequest(**payload)


class TestNoteCreate:
    def test_auto_path_has_uuid_suffix_and_writes_content(self, db, data_dir):
        note = text_model.create_note_item_impl(db, _create(content="正文 A"))
        assert re.fullmatch(
            r"notes/annotations/1/.+-[0-9a-f]{8}\.md", note.setting_file
        ), note.setting_file
        file_path = data_dir / note.setting_file
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == "正文 A"

    def test_explicit_setting_file_respected(self, db, data_dir):
        note = text_model.create_note_item_impl(
            db, _create(setting_file="notes/annotations/9/custom.md", content="x")
        )
        assert note.setting_file == "notes/annotations/9/custom.md"
        assert (data_dir / "notes/annotations/9/custom.md").exists()

    def test_meta_anchor_readback(self, db, data_dir):
        """锚点字段（node_id/offset/selected_text/color）写入 meta_data 并可回读"""
        note = text_model.create_note_item_impl(
            db,
            _create(
                node_id=42,
                start_offset=100,
                end_offset=120,
                selected_text="选中的原文",
                color="green",
            ),
        )
        meta = note.meta_data
        assert meta["node_id"] == 42
        assert meta["start_offset"] == 100
        assert meta["end_offset"] == 120
        assert meta["selected_text"] == "选中的原文"
        assert meta["color"] == "green"

    def test_same_title_generates_unique_paths(self, db, data_dir):
        """S3：同作品同标题（slug 相同前缀）两次创建不得互相覆盖文件"""
        first = text_model.create_note_item_impl(db, _create(content="第一批注"))
        second = text_model.create_note_item_impl(db, _create(content="第二批注"))
        assert first.setting_file != second.setting_file
        assert (data_dir / first.setting_file).exists()
        assert (data_dir / second.setting_file).exists()

    def test_path_traversal_raises_client_exception(self, db, data_dir):
        with pytest.raises(ClientException):
            text_model.create_note_item_impl(
                db, _create(setting_file="../evil.md", content="bad")
            )
        assert not (data_dir.parent / "evil.md").exists()


class TestNoteUpdate:
    def test_update_with_content_writes_file(self, db, data_dir):
        note = text_model.create_note_item_impl(db, _create())
        updated = text_model.update_note_item_impl(
            db, note.id, NoteItemUpdateRequest(content="更新后的正文")
        )
        assert updated is not None
        file_path = data_dir / note.setting_file
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == "更新后的正文"

    def test_update_without_content_keeps_file(self, db, data_dir):
        note = text_model.create_note_item_impl(db, _create(content="原文"))
        text_model.update_note_item_impl(
            db, note.id, NoteItemUpdateRequest(title="改名")
        )
        file_path = data_dir / note.setting_file
        assert file_path.read_text(encoding="utf-8") == "原文"


class TestNoteDelete:
    def test_delete_removes_annotation_file(self, db, data_dir):
        note = text_model.create_note_item_impl(db, _create(content="将被删除"))
        file_path = data_dir / note.setting_file
        assert file_path.exists()
        text_model.delete_note_item_impl(db, note.id)
        assert not file_path.exists()
        assert text_model.get_note_item_impl(db, note.id) is None

    def test_delete_keeps_non_annotation_file(self, db, data_dir):
        note = text_model.create_note_item_impl(
            db,
            _create(setting_file="notes/other/keep.md", content="保留我"),
        )
        file_path = data_dir / "notes/other/keep.md"
        assert file_path.exists()
        text_model.delete_note_item_impl(db, note.id)
        assert file_path.exists(), "非 notes/annotations/ 路径的文件不应被清理"
