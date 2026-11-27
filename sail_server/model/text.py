# -*- coding: utf-8 -*-
# @file text.py
# @brief The Text Content Model - Business Logic
# @author sailing-innocent
# @date 2025-01-29
# @version 2.0
# ---------------------------------

import re
from typing import Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import logging

from litestar.exceptions import ClientException
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from sail_server.config.paths import SERVER_DATA_DIR

from sailzen_orm.text import (
    Work,
    Edition,
    DocumentNode,
    NoteItem,
    ReadingProgress,
    ContentTopicWork,
    ContentAsset,
)
from sail_server.application.dto.text import (
    WorkCreateRequest,
    WorkUpdateRequest,
    WorkResponse,
    ReadingProgressSummary,
    EditionCreateRequest,
    EditionUpdateRequest,
    EditionResponse,
    DocumentNodeCreateRequest,
    DocumentNodeUpdateRequest,
    DocumentNodeResponse,
    NoteItemCreateRequest,
    NoteItemUpdateRequest,
    NoteItemResponse,
)


# ============================================================================
# Chapter List Item (View-specific structure)
# ============================================================================


@dataclass
class ChapterListItem:
    """章节列表项 - 用于目录展示"""

    id: int
    sort_index: int
    label: Optional[str]
    title: Optional[str]
    char_count: Optional[int]
    path: str
    parent_id: Optional[int] = None
    volume_title: Optional[str] = None


# ============================================================================
# Work CRUD Operations
# ============================================================================


def _enrich_works_batch(
    db: Session, works: List[Work], user_id: int = 1
) -> List[WorkResponse]:
    """批量将 Work ORM 对象组装为富响应（含章节统计、云端进度、专题关联与附件数，零 N+1）。"""
    if not works:
        return []
    work_ids = [w.id for w in works]
    stats_map = _calculate_works_stats_batch(db, work_ids)

    prog_rows = (
        db.query(ReadingProgress)
        .filter(ReadingProgress.user_id == user_id, ReadingProgress.work_id.in_(work_ids))
        .all()
    )
    prog_map = {
        p.work_id: ReadingProgressSummary.model_validate(p) for p in prog_rows
    }

    topic_rows = (
        db.query(ContentTopicWork.work_id, ContentTopicWork.topic_id)
        .filter(ContentTopicWork.work_id.in_(work_ids))
        .all()
    )
    topic_map: dict[int, List[int]] = {wid: [] for wid in work_ids}
    for wid, tid in topic_rows:
        topic_map.setdefault(wid, []).append(tid)

    asset_rows = (
        db.query(ContentAsset.work_id, func.count(ContentAsset.id))
        .filter(ContentAsset.work_id.in_(work_ids))
        .group_by(ContentAsset.work_id)
        .all()
    )
    asset_map = {wid: int(cnt or 0) for wid, cnt in asset_rows}

    result: List[WorkResponse] = []
    for work in works:
        stats = stats_map.get(
            work.id, {"edition_count": 0, "chapter_count": 0, "total_chars": 0}
        )
        result.append(
            WorkResponse(
                id=work.id,
                slug=work.slug,
                title=work.title,
                original_title=work.original_title,
                author=work.author,
                language_primary=work.language_primary or "zh",
                work_type=work.work_type or "web_novel",
                status=work.status or "ongoing",
                synopsis=work.synopsis,
                pillar=getattr(work, "pillar", None) or "fiction",
                reading_status=getattr(work, "reading_status", None) or "queued",
                reading_track=getattr(work, "reading_track", None) or "leisure",
                priority=getattr(work, "priority", None) or 3,
                source_url=getattr(work, "source_url", None),
                vault_slug=getattr(work, "vault_slug", None),
                is_original=bool(getattr(work, "is_original", False)),
                meta_data=work.meta_data or {},
                created_at=work.created_at,
                updated_at=work.updated_at,
                progress=prog_map.get(work.id),
                topic_ids=topic_map.get(work.id, []),
                asset_count=asset_map.get(work.id, 0),
                **stats,
            )
        )
    return result


def create_work_impl(db: Session, work_data: WorkCreateRequest) -> WorkResponse:
    """创建作品"""
    work = Work(
        slug=work_data.slug,
        title=work_data.title,
        original_title=work_data.original_title,
        author=work_data.author,
        language_primary=work_data.language_primary,
        work_type=work_data.work_type,
        status=work_data.status,
        synopsis=work_data.synopsis,
        pillar=work_data.pillar,
        reading_status=work_data.reading_status,
        reading_track=work_data.reading_track,
        priority=work_data.priority,
        source_url=work_data.source_url,
        vault_slug=work_data.vault_slug or f"read.{work_data.slug}",
        is_original=work_data.is_original,
        meta_data=work_data.meta_data or {},
    )
    db.add(work)
    db.commit()
    db.refresh(work)
    return _enrich_works_batch(db, [work])[0]


def _calculate_works_stats_batch(db: Session, work_ids: List[int]) -> dict[int, dict]:
    """批量计算多个作品的统计信息（2 次聚合 SQL，消除 N+1 查询）。"""
    stats_map: dict[int, dict] = {
        wid: {"edition_count": 0, "chapter_count": 0, "total_chars": 0}
        for wid in work_ids
    }
    if not work_ids:
        return stats_map

    edition_rows = (
        db.query(
            Edition.work_id,
            func.count(Edition.id),
            func.coalesce(func.sum(Edition.char_count), 0),
        )
        .filter(Edition.work_id.in_(work_ids))
        .group_by(Edition.work_id)
        .all()
    )
    for wid, ed_cnt, char_sum in edition_rows:
        if wid in stats_map:
            stats_map[wid]["edition_count"] = int(ed_cnt or 0)
            stats_map[wid]["total_chars"] = int(char_sum or 0)

    chapter_rows = (
        db.query(
            Edition.work_id,
            func.count(DocumentNode.id),
        )
        .join(Edition, DocumentNode.edition_id == Edition.id)
        .filter(
            Edition.work_id.in_(work_ids),
            DocumentNode.node_type == "chapter",
        )
        .group_by(Edition.work_id)
        .all()
    )
    for wid, chap_cnt in chapter_rows:
        if wid in stats_map:
            stats_map[wid]["chapter_count"] = int(chap_cnt or 0)

    return stats_map


def _calculate_work_stats(db: Session, work: Work) -> dict:
    """计算单个作品的统计信息。"""
    return _calculate_works_stats_batch(db, [work.id]).get(
        work.id, {"edition_count": 0, "chapter_count": 0, "total_chars": 0}
    )


def get_work_impl(db: Session, work_id: int) -> Optional[WorkResponse]:
    """获取单个作品"""
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        return None
    return _enrich_works_batch(db, [work])[0]


def get_works_impl(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    work_type: Optional[str] = None,
    pillar: Optional[str] = None,
    reading_status: Optional[str] = None,
    reading_track: Optional[str] = None,
    topic_id: Optional[int] = None,
) -> List[WorkResponse]:
    """获取作品列表（支持按素养、类型、阅读状态、轨道与专题筛选）。"""
    q = db.query(Work)
    if work_type:
        q = q.filter(Work.work_type == work_type)
    if pillar:
        q = q.filter(Work.pillar == pillar)
    if reading_status:
        q = q.filter(Work.reading_status == reading_status)
    if reading_track:
        q = q.filter(Work.reading_track == reading_track)
    if topic_id is not None:
        q = q.join(ContentTopicWork, ContentTopicWork.work_id == Work.id).filter(
            ContentTopicWork.topic_id == topic_id
        )
    works = q.order_by(Work.updated_at.desc()).offset(skip).limit(limit).all()
    return _enrich_works_batch(db, works)


def update_work_impl(
    db: Session, work_id: int, work_data: WorkUpdateRequest
) -> Optional[WorkResponse]:
    """更新作品"""
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        return None

    updatable = (
        "title",
        "original_title",
        "author",
        "work_type",
        "status",
        "synopsis",
        "pillar",
        "reading_status",
        "reading_track",
        "priority",
        "source_url",
        "vault_slug",
        "is_original",
        "meta_data",
    )
    for field_name in updatable:
        val = getattr(work_data, field_name, None)
        if val is not None:
            setattr(work, field_name, val)

    db.commit()
    db.refresh(work)
    return _enrich_works_batch(db, [work])[0]


def delete_work_impl(db: Session, work_id: int) -> Optional[WorkResponse]:
    """删除作品"""
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        return None
    work_data = WorkResponse.model_validate(work)
    db.delete(work)
    db.commit()
    return work_data


# ============================================================================
# Edition CRUD Operations
# ============================================================================


def create_edition_impl(
    db: Session, edition_data: EditionCreateRequest
) -> EditionResponse:
    """创建版本"""
    edition = Edition(
        work_id=edition_data.work_id,
        edition_name=edition_data.edition_name,
        language=edition_data.language,
        source_format=edition_data.source_format,
        canonical=edition_data.canonical,
        description=edition_data.description,
        source_path=edition_data.source_path,
        meta_data=edition_data.meta_data or {},
    )
    db.add(edition)
    db.commit()
    db.refresh(edition)
    return EditionResponse.model_validate(edition)


def get_edition_impl(db: Session, edition_id: int) -> Optional[EditionResponse]:
    """获取单个版本"""
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return None
    return EditionResponse.model_validate(edition)


def get_editions_by_work_impl(db: Session, work_id: int) -> List[EditionResponse]:
    """获取作品的所有版本"""
    editions = (
        db.query(Edition)
        .filter(Edition.work_id == work_id)
        .order_by(Edition.ingest_version.desc())
        .all()
    )
    return [EditionResponse.model_validate(edition) for edition in editions]


def update_edition_impl(
    db: Session, edition_id: int, edition_data: EditionUpdateRequest
) -> Optional[EditionResponse]:
    """更新版本"""
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return None

    # 仅更新传入的字段
    if edition_data.edition_name is not None:
        edition.edition_name = edition_data.edition_name
    if edition_data.canonical is not None:
        edition.canonical = edition_data.canonical
    if edition_data.status is not None:
        edition.status = edition_data.status
    if edition_data.description is not None:
        edition.description = edition_data.description

    db.commit()
    db.refresh(edition)
    return EditionResponse.model_validate(edition)


def delete_edition_impl(db: Session, edition_id: int) -> Optional[EditionResponse]:
    """删除版本"""
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return None
    edition_data = EditionResponse.model_validate(edition)
    db.delete(edition)
    db.commit()
    return edition_data


# ============================================================================
# DocumentNode CRUD Operations
# ============================================================================


def get_document_node_impl(
    db: Session, node_id: int, include_content: bool = True
) -> Optional[DocumentNodeResponse]:
    """获取单个文档节点"""
    node = db.query(DocumentNode).filter(DocumentNode.id == node_id).first()
    if not node:
        return None
    return DocumentNodeResponse.model_validate(node)


def get_chapter_list_impl(db: Session, edition_id: int) -> List[ChapterListItem]:
    """获取版本的章节列表（目录，附带可选所属分卷信息，向后兼容扁平结构）。"""
    volumes = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "volume",
        )
        .all()
    )
    vol_title_map = {
        v.id: (f"{v.label} {v.title}".strip() if v.label else (v.title or ""))
        for v in volumes
    }

    nodes = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.edition_id == edition_id, DocumentNode.node_type == "chapter"
        )
        .order_by(DocumentNode.sort_index)
        .all()
    )

    return [
        ChapterListItem(
            id=node.id,
            sort_index=node.sort_index,
            label=node.label,
            title=node.title,
            char_count=node.char_count,
            path=node.path,
            parent_id=node.parent_id,
            volume_title=vol_title_map.get(node.parent_id) if node.parent_id else None,
        )
        for node in nodes
    ]


def get_chapter_content_impl(
    db: Session, edition_id: int, chapter_index: int
) -> Optional[DocumentNodeResponse]:
    """获取指定章节的内容"""
    node = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "chapter",
            DocumentNode.sort_index == chapter_index,
        )
        .first()
    )

    if not node:
        return None

    return DocumentNodeResponse.model_validate(node)


def update_document_node_impl(
    db: Session, node_id: int, update_data: DocumentNodeUpdateRequest
) -> Optional[DocumentNodeResponse]:
    """更新文档节点（仅更新可编辑字段）"""
    node = db.query(DocumentNode).filter(DocumentNode.id == node_id).first()
    if not node:
        return None

    if update_data.label is not None:
        node.label = update_data.label
    if update_data.title is not None:
        node.title = update_data.title
    if update_data.raw_text is not None:
        # 清理文本内容
        cleaned_text = sanitize_text(update_data.raw_text)
        node.raw_text = cleaned_text
        # 重新计算字符数
        node.char_count = len(cleaned_text)
        node.word_count = len(cleaned_text.split())
    if update_data.sort_order is not None:
        node.sort_index = update_data.sort_order
    if update_data.parent_id is not None:
        node.parent_id = update_data.parent_id or None
    if update_data.meta_data is not None:
        node.meta_data = update_data.meta_data

    db.commit()
    db.refresh(node)

    # 更新版本的总字符数
    _update_edition_stats(db, node.edition_id)

    return DocumentNodeResponse.model_validate(node)


def _update_edition_stats(db: Session, edition_id: int):
    """更新版本的统计信息"""
    total_chars = (
        db.query(func.sum(DocumentNode.char_count))
        .filter(DocumentNode.edition_id == edition_id)
        .scalar()
        or 0
    )

    total_words = (
        db.query(func.sum(DocumentNode.word_count))
        .filter(DocumentNode.edition_id == edition_id)
        .scalar()
        or 0
    )

    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if edition:
        edition.char_count = total_chars
        edition.word_count = total_words
        db.commit()


def sanitize_text(text: str) -> str:
    """
    清理文本内容，移除不支持的特殊字符

    PostgreSQL text 字段不支持 NUL (0x00) 字符
    """
    if not text:
        return text
    # 移除 NUL 字符
    return text.replace("\x00", "")


# ============================================================================
# Search and Query
# ============================================================================


def search_works_impl(
    db: Session, keyword: str, skip: int = 0, limit: int = 20
) -> List[WorkResponse]:
    """搜索作品"""
    works = (
        db.query(Work)
        .filter(
            (Work.title.ilike(f"%{keyword}%"))
            | (Work.author.ilike(f"%{keyword}%"))
            | (Work.synopsis.ilike(f"%{keyword}%"))
        )
        .order_by(Work.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [WorkResponse.model_validate(work) for work in works]


def search_content_impl(
    db: Session, edition_id: int, keyword: str, skip: int = 0, limit: int = 50
) -> List[DocumentNodeResponse]:
    """搜索版本中的内容"""
    nodes = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.raw_text.ilike(f"%{keyword}%"),
        )
        .order_by(DocumentNode.sort_index)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [DocumentNodeResponse.model_validate(node) for node in nodes]


# ============================================================================
# Chapter Insert Operations
# ============================================================================


def insert_chapter_impl(
    db: Session,
    edition_id: int,
    sort_index: int,
    label: Optional[str],
    title: Optional[str],
    content: str,
    meta_data: dict = None,
) -> Optional[DocumentNodeResponse]:
    """
    向版本的指定位置插入新章节

    Args:
        edition_id: 版本ID
        sort_index: 插入位置（0-based），插入后该位置及之后的章节会后移
        label: 章节标签，如 "第一章"
        title: 章节标题
        content: 章节内容
        meta_data: 元数据

    Returns:
        新创建的章节数据，如果版本不存在则返回 None
    """
    # 检查版本是否存在
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return None

    # 获取当前章节总数
    chapter_count = (
        db.query(func.count(DocumentNode.id))
        .filter(
            DocumentNode.edition_id == edition_id, DocumentNode.node_type == "chapter"
        )
        .scalar()
        or 0
    )

    # 规范化 sort_index：确保在有效范围内
    if sort_index < 0:
        sort_index = 0
    if sort_index > chapter_count:
        sort_index = chapter_count

    # 将目标位置及之后的章节 sort_index 后移
    nodes_to_shift = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "chapter",
            DocumentNode.sort_index >= sort_index,
        )
        .order_by(DocumentNode.sort_index.desc())
        .all()
    )

    for node in nodes_to_shift:
        node.sort_index += 1
        node.path = f"{node.sort_index:04d}"

    # 创建新章节（清理文本内容）
    content = sanitize_text(content)
    char_count = len(content)
    word_count = len(content.split())

    new_node = DocumentNode(
        edition_id=edition_id,
        parent_id=None,
        node_type="chapter",
        sort_index=sort_index,
        depth=1,
        label=label,
        title=title,
        raw_text=content,
        word_count=word_count,
        char_count=char_count,
        path=f"{sort_index:04d}",
        status="active",
        meta_data=meta_data or {},
    )
    db.add(new_node)

    # 更新版本统计
    edition.char_count = (edition.char_count or 0) + char_count
    edition.word_count = (edition.word_count or 0) + word_count

    db.commit()
    db.refresh(new_node)

    return DocumentNodeResponse.model_validate(new_node)


@dataclass
class ChapterBatchItem:
    label: str
    title: str
    content: str
    chapter_type: str = "standard"
    meta_data: dict = field(default_factory=dict)
    volume_label: Optional[str] = None
    volume_title: Optional[str] = None
    parent_id: Optional[int] = None


def _make_slug(title: str, max_length: int = 50) -> str:
    slug = re.sub(r"\s+", "_", title.strip())
    slug = re.sub(r"[^\w\u4e00-\u9fff-]", "", slug)
    return (slug or "work")[:max_length]


def create_work_with_edition_impl(
    db: Session,
    title: str,
    author: Optional[str] = None,
    edition_name: str = "原始导入",
    language: str = "zh",
    work_type: str = "web_novel",
    source_format: str = "txt",
    pillar: str = "fiction",
    reading_status: str = "queued",
    reading_track: str = "leisure",
    synopsis: Optional[str] = None,
    source_url: Optional[str] = None,
    topic_id: Optional[int] = None,
    meta_data: Optional[dict] = None,
) -> Tuple[WorkResponse, EditionResponse]:
    slug = _make_slug(title)
    if db.query(Work).filter(Work.slug == slug).first():
        slug = f"{slug}-{int(datetime.now().timestamp())}"

    work = Work(
        slug=slug,
        title=title,
        author=author,
        language_primary=language,
        work_type=work_type,
        synopsis=synopsis,
        pillar=pillar,
        reading_status=reading_status,
        reading_track=reading_track,
        source_url=source_url,
        vault_slug=f"read.{slug}",
        meta_data=meta_data or {},
    )
    db.add(work)
    db.flush()

    edition = Edition(
        work_id=work.id,
        edition_name=edition_name,
        language=language,
        source_format=source_format,
        canonical=True,
        status="active",
        meta_data={},
    )
    db.add(edition)
    db.flush()

    if topic_id is not None:
        exists_link = (
            db.query(ContentTopicWork)
            .filter(
                ContentTopicWork.topic_id == topic_id,
                ContentTopicWork.work_id == work.id,
            )
            .first()
        )
        if not exists_link:
            db.add(ContentTopicWork(topic_id=topic_id, work_id=work.id, role="core"))

    db.commit()
    db.refresh(work)
    db.refresh(edition)
    return _enrich_works_batch(db, [work])[0], EditionResponse.model_validate(edition)


def batch_insert_chapters_impl(
    db: Session,
    edition_id: int,
    chapters: List[ChapterBatchItem],
    start_index: int = 0,
) -> int:
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return 0

    # 预先加载已有分卷（按 (label, title) 复用，支持分批上传自动挂载同卷）
    existing_volumes = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "volume",
        )
        .order_by(DocumentNode.sort_index)
        .all()
    )
    vol_cache: dict[tuple[str, str], DocumentNode] = {
        ((v.label or "").strip(), (v.title or "").strip()): v for v in existing_volumes
    }
    next_vol_idx = len(existing_volumes)

    total_chars = 0
    total_words = 0
    for i, ch in enumerate(chapters):
        content = sanitize_text(ch.content)
        char_count = len(content)
        total_chars += char_count
        total_words += len(content.split())
        sort_index = start_index + i

        parent_id = ch.parent_id
        vol_path_prefix = ""
        if parent_id is None and (ch.volume_label or ch.volume_title):
            v_key = ((ch.volume_label or "").strip(), (ch.volume_title or "").strip())
            vol_node = vol_cache.get(v_key)
            if vol_node is None:
                vol_node = DocumentNode(
                    edition_id=edition_id,
                    parent_id=None,
                    node_type="volume",
                    sort_index=next_vol_idx,
                    depth=0,
                    label=v_key[0] or f"第{next_vol_idx + 1}卷",
                    title=v_key[1] or v_key[0] or f"第{next_vol_idx + 1}卷",
                    raw_text=None,
                    word_count=0,
                    char_count=0,
                    path=f"V{next_vol_idx:04d}",
                    status="active",
                    meta_data={},
                )
                db.add(vol_node)
                db.flush()
                vol_cache[v_key] = vol_node
                next_vol_idx += 1
            parent_id = vol_node.id
            vol_path_prefix = f"{vol_node.path}."

        node_path = f"{vol_path_prefix}{sort_index:04d}"
        node = DocumentNode(
            edition_id=edition_id,
            parent_id=parent_id,
            node_type="chapter",
            sort_index=sort_index,
            depth=1 if parent_id is not None else 1,
            label=ch.label or "",
            title=ch.title or "",
            raw_text=content,
            word_count=len(content.split()),
            char_count=char_count,
            path=node_path,
            status="active",
            meta_data={**(ch.meta_data or {}), "chapter_type": ch.chapter_type},
        )
        db.add(node)

    edition.char_count = (edition.char_count or 0) + total_chars
    edition.word_count = (edition.word_count or 0) + total_words
    db.commit()
    return len(chapters)


def get_chapter_count_impl(db: Session, edition_id: int) -> int:
    return (
        db.query(func.count(DocumentNode.id))
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "chapter",
        )
        .scalar()
        or 0
    )


# ============================================================================
# NoteItem CRUD Operations
# ============================================================================


def _note_to_response(note: NoteItem) -> NoteItemResponse:
    return NoteItemResponse(
        id=note.id,
        category=note.category,
        setting_file=note.setting_file,
        work_id=note.work_id,
        edition_id=note.edition_id,
        title=note.title,
        slug=note.slug,
        meta_data=note.meta_data or {},
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def create_note_item_impl(
    db: Session, data: NoteItemCreateRequest
) -> NoteItemResponse:
    """创建笔记索引，支持自动生成文件路径并写入 Markdown 内容"""
    # 标准化锚点元数据
    meta = dict(data.meta_data or {})
    if data.node_id is not None:
        meta["node_id"] = data.node_id
    if data.start_offset is not None:
        meta["start_offset"] = data.start_offset
    if data.end_offset is not None:
        meta["end_offset"] = data.end_offset
    if data.selected_text is not None:
        meta["selected_text"] = data.selected_text
    if data.color is not None:
        meta["color"] = data.color

    # 生成/校验文件路径
    setting_file = data.setting_file
    if not setting_file:
        work_id = data.work_id or 0
        base_slug = data.slug or _make_slug(data.title or "annotation")
        # 追加短 uuid 后缀，避免同作品下同标题/空标题批注相互覆盖文件（S3）
        setting_file = (
            f"notes/annotations/{work_id}/{base_slug}-{uuid4().hex[:8]}.md"
        )


    note = NoteItem(
        category=data.category,
        setting_file=setting_file,
        work_id=data.work_id,
        edition_id=data.edition_id,
        title=data.title,
        slug=data.slug,
        meta_data=meta,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    # 若请求携带 Markdown 内容，直接写入文件（限制在 workspace 内）
    if data.content is not None and data.content:
        file_path = _resolve_annotation_file_path(note.setting_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(sanitize_text(data.content), encoding="utf-8")

    return _note_to_response(note)


def _resolve_annotation_file_path(setting_file: str) -> Path:
    """解析 note 文件绝对路径，限制在 workspace 内防止路径遍历"""
    rel = setting_file
    if rel.startswith("/"):
        rel = rel.lstrip("/")
    target = (SERVER_DATA_DIR / rel).resolve()
    base_resolved = SERVER_DATA_DIR.resolve()
    try:
        target.relative_to(base_resolved)
    except ValueError:
        raise ClientException(
            detail=f"Invalid note file path (outside workspace): {setting_file}"
        )
    return target


def get_note_item_impl(db: Session, note_id: int) -> Optional[NoteItemResponse]:
    """获取单个笔记索引"""
    note = db.query(NoteItem).filter(NoteItem.id == note_id).first()
    if not note:
        return None
    return _note_to_response(note)


def get_note_items_impl(
    db: Session,
    category: Optional[str] = None,
    work_id: Optional[int] = None,
    edition_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[NoteItemResponse]:
    """获取笔记索引列表，支持过滤"""
    query = db.query(NoteItem)
    if category is not None:
        query = query.filter(NoteItem.category == category)
    if work_id is not None:
        query = query.filter(NoteItem.work_id == work_id)
    if edition_id is not None:
        query = query.filter(NoteItem.edition_id == edition_id)
    notes = query.order_by(NoteItem.updated_at.desc()).offset(skip).limit(limit).all()
    return [_note_to_response(note) for note in notes]


def update_note_item_impl(
    db: Session, note_id: int, data: NoteItemUpdateRequest
) -> Optional[NoteItemResponse]:
    """更新笔记索引"""
    note = db.query(NoteItem).filter(NoteItem.id == note_id).first()
    if not note:
        return None

    if data.category is not None:
        note.category = data.category
    if data.setting_file is not None:
        note.setting_file = data.setting_file
    if data.work_id is not None:
        note.work_id = data.work_id
    if data.edition_id is not None:
        note.edition_id = data.edition_id
    if data.title is not None:
        note.title = data.title
    if data.slug is not None:
        note.slug = data.slug
    if data.meta_data is not None:
        note.meta_data = data.meta_data
    db.commit()
    db.refresh(note)
    # S2：索引更新可携带正文，直接写文件（与 create 路径一致，限制在 workspace 内）
    if data.content is not None and data.content:
        file_path = _resolve_annotation_file_path(note.setting_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(sanitize_text(data.content), encoding="utf-8")
    return _note_to_response(note)



def delete_note_item_impl(db: Session, note_id: int) -> Optional[NoteItemResponse]:
    """删除笔记索引，并清理 notes/annotations/ 下的正文文件（S3）"""
    note = db.query(NoteItem).filter(NoteItem.id == note_id).first()
    if not note:
        return None
    note_data = _note_to_response(note)
    _remove_annotation_file(note.setting_file)
    db.delete(note)
    db.commit()
    return note_data


def _remove_annotation_file(setting_file: str) -> None:
    """尽力清理批注正文文件；任何异常都不阻塞索引删除"""
    rel = (setting_file or "").lstrip("/")
    if not rel.startswith("notes/annotations/"):
        return
    try:
        file_path = _resolve_annotation_file_path(rel)
        if file_path.exists():
            file_path.unlink()
    except (OSError, ClientException):
        logger.warning(f"Failed to remove annotation file: {setting_file}")
