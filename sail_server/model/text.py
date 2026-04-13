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
from sqlalchemy.orm import Session
from sqlalchemy import func

from sail_server.infrastructure.orm.text import (
    Work,
    Edition,
    DocumentNode,
    IngestJob,
)
from sail_server.application.dto.text import (
    WorkCreateRequest,
    WorkUpdateRequest,
    WorkResponse,
    EditionCreateRequest,
    EditionUpdateRequest,
    EditionResponse,
    DocumentNodeCreateRequest,
    DocumentNodeUpdateRequest,
    DocumentNodeResponse,
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


# ============================================================================
# Text Import Request (Model-specific structure)
# ============================================================================


# ============================================================================
# Work CRUD Operations
# ============================================================================


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
        meta_data=work_data.meta_data or {},
    )
    db.add(work)
    db.commit()
    db.refresh(work)
    stats = _calculate_work_stats(db, work)
    return WorkResponse(
        id=work.id,
        slug=work.slug,
        title=work.title,
        original_title=work.original_title,
        author=work.author,
        language_primary=work.language_primary,
        work_type=work.work_type,
        status=work.status,
        synopsis=work.synopsis,
        meta_data=work.meta_data or {},
        created_at=work.created_at,
        updated_at=work.updated_at,
        **stats,
    )


def _calculate_work_stats(db: Session, work: Work) -> dict:
    """计算作品的统计信息"""
    # 版本数量
    edition_count = (
        db.query(func.count(Edition.id)).filter(Edition.work_id == work.id).scalar()
        or 0
    )

    # 章节数量和总字符数（所有版本的章节总和）
    chapter_count = 0
    total_chars = 0

    for edition in work.editions:
        edition_chapters = (
            db.query(func.count(DocumentNode.id))
            .filter(
                DocumentNode.edition_id == edition.id,
                DocumentNode.node_type == "chapter",
            )
            .scalar()
            or 0
        )
        chapter_count += edition_chapters
        total_chars += edition.char_count or 0

    return {
        "edition_count": edition_count,
        "chapter_count": chapter_count,
        "total_chars": total_chars,
    }


def get_work_impl(db: Session, work_id: int) -> Optional[WorkResponse]:
    """获取单个作品"""
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        return None

    stats = _calculate_work_stats(db, work)
    return WorkResponse(
        id=work.id,
        slug=work.slug,
        title=work.title,
        original_title=work.original_title,
        author=work.author,
        language_primary=work.language_primary,
        work_type=work.work_type,
        status=work.status,
        synopsis=work.synopsis,
        meta_data=work.meta_data or {},
        created_at=work.created_at,
        updated_at=work.updated_at,
        **stats,
    )


def get_works_impl(db: Session, skip: int = 0, limit: int = 20) -> List[WorkResponse]:
    """获取作品列表"""
    works = (
        db.query(Work).order_by(Work.updated_at.desc()).offset(skip).limit(limit).all()
    )
    result = []
    for work in works:
        stats = _calculate_work_stats(db, work)
        result.append(
            WorkResponse(
                id=work.id,
                slug=work.slug,
                title=work.title,
                original_title=work.original_title,
                author=work.author,
                language_primary=work.language_primary,
                work_type=work.work_type,
                status=work.status,
                synopsis=work.synopsis,
                meta_data=work.meta_data or {},
                created_at=work.created_at,
                updated_at=work.updated_at,
                **stats,
            )
        )
    return result


def update_work_impl(
    db: Session, work_id: int, work_data: WorkUpdateRequest
) -> Optional[WorkResponse]:
    """更新作品"""
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        return None

    # 仅更新传入的字段
    if work_data.title is not None:
        work.title = work_data.title
    if work_data.author is not None:
        work.author = work_data.author
    if work_data.status is not None:
        work.status = work_data.status
    if work_data.synopsis is not None:
        work.synopsis = work_data.synopsis

    db.commit()
    db.refresh(work)
    return WorkResponse.model_validate(work)


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
    """获取版本的章节列表（目录）"""
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

    # 仅更新传入的字段
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
        meta_data=meta_data or {},
    )
    db.add(work)
    db.flush()

    edition = Edition(
        work_id=work.id,
        edition_name=edition_name,
        language=language,
        status="active",
        meta_data={},
    )
    db.add(edition)
    db.commit()
    db.refresh(work)
    db.refresh(edition)
    return WorkResponse.model_validate(work), EditionResponse.model_validate(edition)


def batch_insert_chapters_impl(
    db: Session,
    edition_id: int,
    chapters: List[ChapterBatchItem],
    start_index: int = 0,
) -> int:
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return 0

    total_chars = 0
    total_words = 0
    for i, ch in enumerate(chapters):
        content = sanitize_text(ch.content)
        char_count = len(content)
        total_chars += char_count
        total_words += len(content.split())
        sort_index = start_index + i
        node = DocumentNode(
            edition_id=edition_id,
            parent_id=None,
            node_type="chapter",
            sort_index=sort_index,
            depth=1,
            label=ch.label or "",
            title=ch.title or "",
            raw_text=content,
            word_count=len(content.split()),
            char_count=char_count,
            path=f"{sort_index:04d}",
            status="active",
            meta_data=ch.meta_data or {},
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
