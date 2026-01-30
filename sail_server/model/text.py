# -*- coding: utf-8 -*-
# @file text.py
# @brief The Text Content Model - Business Logic
# @author sailing-innocent
# @date 2025-01-29
# @version 1.0
# ---------------------------------

import re
import hashlib
from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from sail_server.data.text import (
    Work, Edition, DocumentNode, IngestJob,
    WorkData, EditionData, DocumentNodeData, DocumentNodeUpdateRequest, IngestJobData,
    TextImportRequest, ChapterListItem
)


# ============================================================================
# Work CRUD Operations
# ============================================================================

def create_work_impl(db: Session, work_data: WorkData) -> WorkData:
    """创建作品"""
    work = work_data.create_orm()
    db.add(work)
    db.commit()
    db.refresh(work)
    return WorkData.read_from_orm(work)


def get_work_impl(db: Session, work_id: int) -> Optional[WorkData]:
    """获取单个作品"""
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        return None
    
    # 统计版本数和章节数
    edition_count = db.query(func.count(Edition.id)).filter(Edition.work_id == work_id).scalar() or 0
    chapter_count = db.query(func.count(DocumentNode.id)).join(Edition).filter(
        Edition.work_id == work_id,
        DocumentNode.node_type == 'chapter'
    ).scalar() or 0
    total_chars = db.query(func.sum(Edition.char_count)).filter(Edition.work_id == work_id).scalar() or 0
    
    return WorkData.read_from_orm(work, edition_count, chapter_count, total_chars)


def get_works_impl(db: Session, skip: int = 0, limit: int = 20) -> List[WorkData]:
    """获取作品列表"""
    works = db.query(Work).order_by(Work.updated_at.desc()).offset(skip).limit(limit).all()
    result = []
    for work in works:
        edition_count = db.query(func.count(Edition.id)).filter(Edition.work_id == work.id).scalar() or 0
        chapter_count = db.query(func.count(DocumentNode.id)).join(Edition).filter(
            Edition.work_id == work.id,
            DocumentNode.node_type == 'chapter'
        ).scalar() or 0
        total_chars = db.query(func.sum(Edition.char_count)).filter(Edition.work_id == work.id).scalar() or 0
        result.append(WorkData.read_from_orm(work, edition_count, chapter_count, total_chars or 0))
    return result


def update_work_impl(db: Session, work_id: int, work_data: WorkData) -> Optional[WorkData]:
    """更新作品"""
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        return None
    work_data.update_orm(work)
    db.commit()
    db.refresh(work)
    return WorkData.read_from_orm(work)


def delete_work_impl(db: Session, work_id: int) -> Optional[WorkData]:
    """删除作品"""
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        return None
    work_data = WorkData.read_from_orm(work)
    db.delete(work)
    db.commit()
    return work_data


# ============================================================================
# Edition CRUD Operations
# ============================================================================

def create_edition_impl(db: Session, edition_data: EditionData) -> EditionData:
    """创建版本"""
    edition = edition_data.create_orm()
    db.add(edition)
    db.commit()
    db.refresh(edition)
    return EditionData.read_from_orm(edition)


def get_edition_impl(db: Session, edition_id: int) -> Optional[EditionData]:
    """获取单个版本"""
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return None
    
    chapter_count = db.query(func.count(DocumentNode.id)).filter(
        DocumentNode.edition_id == edition_id,
        DocumentNode.node_type == 'chapter'
    ).scalar() or 0
    
    return EditionData.read_from_orm(edition, chapter_count)


def get_editions_by_work_impl(db: Session, work_id: int) -> List[EditionData]:
    """获取作品的所有版本"""
    editions = db.query(Edition).filter(Edition.work_id == work_id).order_by(Edition.ingest_version.desc()).all()
    result = []
    for edition in editions:
        chapter_count = db.query(func.count(DocumentNode.id)).filter(
            DocumentNode.edition_id == edition.id,
            DocumentNode.node_type == 'chapter'
        ).scalar() or 0
        result.append(EditionData.read_from_orm(edition, chapter_count))
    return result


def update_edition_impl(db: Session, edition_id: int, edition_data: EditionData) -> Optional[EditionData]:
    """更新版本"""
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return None
    edition_data.update_orm(edition)
    db.commit()
    db.refresh(edition)
    return EditionData.read_from_orm(edition)


def delete_edition_impl(db: Session, edition_id: int) -> Optional[EditionData]:
    """删除版本"""
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return None
    edition_data = EditionData.read_from_orm(edition)
    db.delete(edition)
    db.commit()
    return edition_data


# ============================================================================
# DocumentNode CRUD Operations
# ============================================================================

def get_document_node_impl(db: Session, node_id: int, include_content: bool = True) -> Optional[DocumentNodeData]:
    """获取单个文档节点"""
    node = db.query(DocumentNode).filter(DocumentNode.id == node_id).first()
    if not node:
        return None
    
    children_count = db.query(func.count(DocumentNode.id)).filter(
        DocumentNode.parent_id == node_id
    ).scalar() or 0
    
    return DocumentNodeData.read_from_orm(node, children_count, include_content)


def get_chapter_list_impl(db: Session, edition_id: int) -> List[ChapterListItem]:
    """获取版本的章节列表（目录）"""
    nodes = db.query(DocumentNode).filter(
        DocumentNode.edition_id == edition_id,
        DocumentNode.node_type == 'chapter'
    ).order_by(DocumentNode.sort_index).all()
    
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


def get_chapter_content_impl(db: Session, edition_id: int, chapter_index: int) -> Optional[DocumentNodeData]:
    """获取指定章节的内容"""
    node = db.query(DocumentNode).filter(
        DocumentNode.edition_id == edition_id,
        DocumentNode.node_type == 'chapter',
        DocumentNode.sort_index == chapter_index
    ).first()
    
    if not node:
        return None
    
    return DocumentNodeData.read_from_orm(node, 0, True)


def update_document_node_impl(db: Session, node_id: int, update_data: DocumentNodeUpdateRequest) -> Optional[DocumentNodeData]:
    """更新文档节点（仅更新可编辑字段）"""
    node = db.query(DocumentNode).filter(DocumentNode.id == node_id).first()
    if not node:
        return None

    # 仅更新传入的字段
    if update_data.label is not None:
        node.label = update_data.label
    if update_data.title is not None:
        node.title = update_data.title
    if update_data.raw_text is not None:
        node.raw_text = update_data.raw_text
        # 重新计算字符数
        node.char_count = len(update_data.raw_text)
        node.word_count = len(update_data.raw_text.split())
    if update_data.meta_data:
        node.meta_data = update_data.meta_data

    db.commit()
    db.refresh(node)

    # 更新版本的总字符数
    _update_edition_stats(db, node.edition_id)

    return DocumentNodeData.read_from_orm(node, 0, True)


def _update_edition_stats(db: Session, edition_id: int):
    """更新版本的统计信息"""
    total_chars = db.query(func.sum(DocumentNode.char_count)).filter(
        DocumentNode.edition_id == edition_id
    ).scalar() or 0
    
    total_words = db.query(func.sum(DocumentNode.word_count)).filter(
        DocumentNode.edition_id == edition_id
    ).scalar() or 0
    
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if edition:
        edition.char_count = total_chars
        edition.word_count = total_words
        db.commit()


# ============================================================================
# Text Import Logic
# ============================================================================

# 常用的章节识别模式
DEFAULT_CHAPTER_PATTERNS = [
    r'^第[一二三四五六七八九十百千万零〇\d]+章[^\n]*',  # 中文章节: 第一章、第1章
    r'^第[一二三四五六七八九十百千万零〇\d]+节[^\n]*',  # 中文节: 第一节
    r'^Chapter\s+\d+[^\n]*',  # 英文章节: Chapter 1
    r'^CHAPTER\s+\d+[^\n]*',  # 大写英文章节
    r'^\d+\.\s+[^\n]+',  # 数字章节: 1. Title
    r'^【[^\】]+】',  # 【章节标题】
]


def parse_chapters(content: str, pattern: Optional[str] = None) -> List[Tuple[str, str, int, int]]:
    """
    解析文本内容，识别章节
    
    返回: [(chapter_title, chapter_content, start_pos, end_pos), ...]
    """
    if not content:
        return []
    
    # 合并所有模式
    if pattern:
        patterns = [pattern]
    else:
        patterns = DEFAULT_CHAPTER_PATTERNS
    
    combined_pattern = '|'.join(f'({p})' for p in patterns)
    
    # 查找所有章节标题
    matches = list(re.finditer(combined_pattern, content, re.MULTILINE))
    
    if not matches:
        # 如果没有找到章节，把整个内容作为一章
        return [("正文", content.strip(), 0, len(content))]
    
    chapters = []
    for i, match in enumerate(matches):
        title = match.group().strip()
        start = match.start()
        
        # 确定章节内容的结束位置
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)
        
        # 提取章节内容（不包括标题行）
        chapter_content = content[match.end():end].strip()
        
        chapters.append((title, chapter_content, start, end))
    
    return chapters


def import_text_impl(db: Session, request: TextImportRequest) -> Tuple[WorkData, EditionData, int]:
    """
    导入文本内容
    
    流程:
    1. 创建或获取作品
    2. 创建新版本
    3. 解析章节
    4. 创建文档节点
    5. 更新统计信息
    
    返回: (work_data, edition_data, chapter_count)
    """
    # 1. 创建作品
    work_data = WorkData(
        title=request.work_title,
        author=request.work_author,
        synopsis=request.work_synopsis,
        language_primary=request.language,
        meta_data=request.meta_data,
    )
    work = work_data.create_orm()
    db.add(work)
    db.flush()  # 获取ID但不提交
    
    # 2. 创建版本
    content_hash = hashlib.sha256(request.content.encode('utf-8')).hexdigest()[:16]
    edition_data = EditionData(
        work_id=work.id,
        edition_name=request.edition_name or "原始导入",
        language=request.language,
        source_checksum=content_hash,
        status="draft",
    )
    edition = edition_data.create_orm()
    db.add(edition)
    db.flush()
    
    # 3. 解析章节
    chapters = parse_chapters(request.content, request.chapter_pattern)
    
    # 4. 创建文档节点
    total_chars = 0
    for i, (title, content, start, end) in enumerate(chapters):
        char_count = len(content)
        total_chars += char_count
        
        # 尝试分离 label 和 title
        label, chapter_title = _parse_chapter_title(title)
        
        node = DocumentNode(
            edition_id=edition.id,
            parent_id=None,
            node_type='chapter',
            sort_index=i,
            depth=1,
            label=label,
            title=chapter_title,
            raw_text=content,
            word_count=len(content.split()),
            char_count=char_count,
            path=f"{i:04d}",
            status='active',
        )
        db.add(node)
    
    # 5. 更新版本统计
    edition.char_count = total_chars
    edition.word_count = sum(len(c[1].split()) for c in chapters)
    edition.status = 'active'
    
    db.commit()
    db.refresh(work)
    db.refresh(edition)
    
    return (
        WorkData.read_from_orm(work, 1, len(chapters), total_chars),
        EditionData.read_from_orm(edition, len(chapters)),
        len(chapters)
    )


def _parse_chapter_title(title: str) -> Tuple[str, str]:
    """
    分离章节标签和标题
    例如: "第一章 风起云涌" -> ("第一章", "风起云涌")
    """
    # 尝试匹配常见格式
    patterns = [
        r'^(第[一二三四五六七八九十百千万零〇\d]+章)\s*(.*)$',
        r'^(第[一二三四五六七八九十百千万零〇\d]+节)\s*(.*)$',
        r'^(Chapter\s+\d+)\s*(.*)$',
        r'^(CHAPTER\s+\d+)\s*(.*)$',
        r'^(\d+\.)\s*(.+)$',
        r'^【([^\】]+)】\s*(.*)$',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, title, re.IGNORECASE)
        if match:
            label = match.group(1).strip()
            chapter_title = match.group(2).strip() if match.group(2) else None
            return label, chapter_title
    
    return title, None


def append_chapters_impl(db: Session, edition_id: int, content: str, chapter_pattern: Optional[str] = None) -> int:
    """
    追加章节到现有版本
    
    返回: 新增章节数
    """
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return 0
    
    # 获取当前最大 sort_index
    max_index = db.query(func.max(DocumentNode.sort_index)).filter(
        DocumentNode.edition_id == edition_id,
        DocumentNode.node_type == 'chapter'
    ).scalar() or -1
    
    # 解析新章节
    chapters = parse_chapters(content, chapter_pattern)
    
    # 创建新节点
    total_new_chars = 0
    for i, (title, chapter_content, start, end) in enumerate(chapters):
        char_count = len(chapter_content)
        total_new_chars += char_count
        
        label, chapter_title = _parse_chapter_title(title)
        sort_index = max_index + 1 + i
        
        node = DocumentNode(
            edition_id=edition_id,
            parent_id=None,
            node_type='chapter',
            sort_index=sort_index,
            depth=1,
            label=label,
            title=chapter_title,
            raw_text=chapter_content,
            word_count=len(chapter_content.split()),
            char_count=char_count,
            path=f"{sort_index:04d}",
            status='active',
        )
        db.add(node)
    
    # 更新版本统计
    edition.char_count = (edition.char_count or 0) + total_new_chars
    edition.word_count = (edition.word_count or 0) + sum(len(c[1].split()) for c in chapters)
    
    db.commit()
    
    return len(chapters)


# ============================================================================
# Search and Query
# ============================================================================

def search_works_impl(db: Session, keyword: str, skip: int = 0, limit: int = 20) -> List[WorkData]:
    """搜索作品"""
    works = db.query(Work).filter(
        (Work.title.ilike(f"%{keyword}%")) |
        (Work.author.ilike(f"%{keyword}%")) |
        (Work.synopsis.ilike(f"%{keyword}%"))
    ).order_by(Work.updated_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for work in works:
        edition_count = db.query(func.count(Edition.id)).filter(Edition.work_id == work.id).scalar() or 0
        chapter_count = db.query(func.count(DocumentNode.id)).join(Edition).filter(
            Edition.work_id == work.id,
            DocumentNode.node_type == 'chapter'
        ).scalar() or 0
        total_chars = db.query(func.sum(Edition.char_count)).filter(Edition.work_id == work.id).scalar() or 0
        result.append(WorkData.read_from_orm(work, edition_count, chapter_count, total_chars or 0))
    
    return result


def search_content_impl(db: Session, edition_id: int, keyword: str, skip: int = 0, limit: int = 50) -> List[DocumentNodeData]:
    """搜索版本中的内容"""
    nodes = db.query(DocumentNode).filter(
        DocumentNode.edition_id == edition_id,
        DocumentNode.raw_text.ilike(f"%{keyword}%")
    ).order_by(DocumentNode.sort_index).offset(skip).limit(limit).all()
    
    return [DocumentNodeData.read_from_orm(node, 0, True) for node in nodes]


# ============================================================================
# Chapter Insert Operations
# ============================================================================

def insert_chapter_impl(db: Session, edition_id: int, sort_index: int, label: Optional[str],
                        title: Optional[str], content: str, meta_data: dict = None) -> Optional[DocumentNodeData]:
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
    chapter_count = db.query(func.count(DocumentNode.id)).filter(
        DocumentNode.edition_id == edition_id,
        DocumentNode.node_type == 'chapter'
    ).scalar() or 0
    
    # 规范化 sort_index：确保在有效范围内
    if sort_index < 0:
        sort_index = 0
    if sort_index > chapter_count:
        sort_index = chapter_count
    
    # 将目标位置及之后的章节 sort_index 后移
    nodes_to_shift = db.query(DocumentNode).filter(
        DocumentNode.edition_id == edition_id,
        DocumentNode.node_type == 'chapter',
        DocumentNode.sort_index >= sort_index
    ).order_by(DocumentNode.sort_index.desc()).all()
    
    for node in nodes_to_shift:
        node.sort_index += 1
        node.path = f"{node.sort_index:04d}"
    
    # 创建新章节
    char_count = len(content)
    word_count = len(content.split())
    
    new_node = DocumentNode(
        edition_id=edition_id,
        parent_id=None,
        node_type='chapter',
        sort_index=sort_index,
        depth=1,
        label=label,
        title=title,
        raw_text=content,
        word_count=word_count,
        char_count=char_count,
        path=f"{sort_index:04d}",
        status='active',
        meta_data=meta_data or {},
    )
    db.add(new_node)
    
    # 更新版本统计
    edition.char_count = (edition.char_count or 0) + char_count
    edition.word_count = (edition.word_count or 0) + word_count
    
    db.commit()
    db.refresh(new_node)
    
    return DocumentNodeData.read_from_orm(new_node, 0, True)
