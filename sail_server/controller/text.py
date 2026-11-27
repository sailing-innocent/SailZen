# -*- coding: utf-8 -*-
# @file text.py
# @brief Text Content Controller
# @author sailing-innocent
# @date 2025-01-29
# @version 1.0
# ---------------------------------

from __future__ import annotations
from litestar import Controller, delete, get, post, put, Request
from litestar.exceptions import NotFoundException, HTTPException
import logging

logger = logging.getLogger(__name__)

from sail_server.application.dto.text import (
    WorkCreateRequest,
    WorkUpdateRequest,
    WorkResponse,
    EditionCreateRequest,
    EditionUpdateRequest,
    EditionResponse,
    DocumentNodeResponse,
    DocumentNodeUpdateRequest,
    EditionTocResponse,
    VolumeCreateRequest,
    VolumeAssignRequest,
    TocVolumeItem,
    AutoVolumeRequest,
    AutoVolumeResponse,
    WorkClipsExportResponse,
    NoteItemCreateRequest,
    NoteItemUpdateRequest,
    NoteItemResponse,
    NoteItemListResponse,
    NoteItemContentResponse,
    NoteLinkGraphResponse,
    NOTE_CATEGORIES,
)
from sail_server.model.content_library import (
    get_edition_toc_impl,
    create_volume_impl,
    assign_chapters_to_volume_impl,
    delete_volume_impl,
    auto_volume_edition_impl,
    export_work_clips_markdown_impl,
)
from sail_server.model.text import (
    create_work_impl,
    get_work_impl,
    get_works_impl,
    update_work_impl,
    delete_work_impl,
    create_edition_impl,
    get_edition_impl,
    get_editions_by_work_impl,
    update_edition_impl,
    delete_edition_impl,
    get_document_node_impl,
    get_chapter_list_impl,
    get_chapter_content_impl,
    update_document_node_impl,
    insert_chapter_impl,
    search_works_impl,
    search_content_impl,
    batch_insert_chapters_impl,
    get_chapter_count_impl,
    ChapterBatchItem,
    create_note_item_impl,
    get_note_item_impl,
    get_note_items_impl,
    update_note_item_impl,
    delete_note_item_impl,
)

from sqlalchemy.orm import Session
from typing import Generator, List, Optional
from pydantic import BaseModel, Field
from pathlib import Path

from sail_server.utils.note_links import build_link_graph
from sail_server.config.paths import SERVER_DATA_DIR


# ============================================================================
# Request/Response Models
# ============================================================================


class ChapterInsertRequest(BaseModel):
    """插入章节请求"""

    sort_index: int = Field(description="插入位置")
    label: str = Field(description="章节标签")
    title: str = Field(description="章节标题")
    content: str = Field(description="章节内容")
    meta_data: Optional[dict] = Field(default=None, description="元数据")


class ChapterListItem(BaseModel):
    """章节列表项"""

    id: int = Field(description="节点ID")
    sort_index: int = Field(description="排序索引")
    label: str = Field(description="章节标签")
    title: str = Field(description="章节标题")
    char_count: Optional[int] = Field(default=None, description="字符数")
    path: str = Field(description="节点路径")
    parent_id: Optional[int] = Field(default=None, description="所属分卷节点ID")
    volume_title: Optional[str] = Field(default=None, description="所属分卷标题")


class AppendResponse(BaseModel):
    """追加章节响应"""

    edition_id: int
    new_chapter_count: int
    message: str = "追加成功"


class WorkEditionCreateRequest(BaseModel):
    title: str
    author: Optional[str] = None
    edition_name: str = "原始导入"
    language: str = "zh"
    work_type: str = "web_novel"
    source_format: str = "txt"
    pillar: str = "fiction"
    reading_status: str = "queued"
    reading_track: str = "leisure"
    synopsis: Optional[str] = None
    source_url: Optional[str] = None
    topic_id: Optional[int] = None
    meta_data: Optional[dict] = None


class WorkEditionCreateResponse(BaseModel):
    work: WorkResponse
    edition: EditionResponse


class ChapterBatchUploadItem(BaseModel):
    label: str
    title: str
    content: str
    chapter_type: str = "standard"
    volume_label: Optional[str] = None
    volume_title: Optional[str] = None
    parent_id: Optional[int] = None
    meta_data: Optional[dict] = None


class ChapterBatchUploadRequest(BaseModel):
    chapters: List[ChapterBatchUploadItem]
    start_index: int = 0


class ChapterBatchUploadResponse(BaseModel):
    edition_id: int
    accepted: int
    total_chapters: int


class ChapterInsertResponse(BaseModel):
    """插入章节响应"""

    chapter: DocumentNodeResponse
    message: str = "插入成功"


# ============================================================================
# Work Controller
# ============================================================================


class WorkController(Controller):
    """作品管理控制器"""

    path = "/work"

    @get("")
    async def get_works(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        skip: int = 0,
        limit: int = 50,
        work_type: Optional[str] = None,
        pillar: Optional[str] = None,
        reading_status: Optional[str] = None,
        reading_track: Optional[str] = None,
        topic_id: Optional[int] = None,
    ) -> List[WorkResponse]:
        """获取作品列表（支持素养、类型、阅读状态、轨道与专题筛选）"""
        db = next(router_dependency)
        works = get_works_impl(
            db,
            skip=skip,
            limit=limit,
            work_type=work_type,
            pillar=pillar,
            reading_status=reading_status,
            reading_track=reading_track,
            topic_id=topic_id,
        )
        logger.info(f"Get works: {len(works)}")
        return works

    @get("/search")
    async def search_works(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        keyword: str,
        skip: int = 0,
        limit: int = 20,
    ) -> List[WorkResponse]:
        """搜索作品"""
        db = next(router_dependency)
        works = search_works_impl(db, keyword, skip, limit)
        logger.info(f"Search works with keyword '{keyword}': {len(works)}")
        return works

    @get("/{work_id:int}")
    async def get_work(
        self,
        work_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WorkResponse:
        """获取单个作品"""
        db = next(router_dependency)
        work = get_work_impl(db, work_id)
        if not work:
            raise NotFoundException(detail=f"Work with ID {work_id} not found")
        logger.info(f"Get work {work_id}: {work.title}")
        return work

    @post("/")
    async def create_work(
        self,
        data: WorkCreateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WorkResponse:
        """创建作品"""
        db = next(router_dependency)
        work = create_work_impl(db, data)
        logger.info(f"Created work: {work.title}")
        return work

    @put("/{work_id:int}")
    async def update_work(
        self,
        work_id: int,
        data: WorkUpdateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WorkResponse:
        """更新作品"""
        db = next(router_dependency)
        work = update_work_impl(db, work_id, data)
        if not work:
            raise NotFoundException(detail=f"Work with ID {work_id} not found")
        logger.info(f"Updated work {work_id}: {work.title}")
        return work

    @delete("/{work_id:int}", status_code=200)
    async def delete_work(
        self,
        work_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WorkResponse:
        """删除作品"""
        db = next(router_dependency)
        work = delete_work_impl(db, work_id)
        if not work:
            raise NotFoundException(detail=f"Work with ID {work_id} not found")
        logger.info(f"Deleted work {work_id}")
        return work

    @get("/{work_id:int}/export-clips")
    async def export_work_clips(
        self,
        work_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WorkClipsExportResponse:
        """导出作品划线批注与阅读总览卡为 Dendron 规范 Markdown"""
        db = next(router_dependency)
        res = export_work_clips_markdown_impl(db, work_id)
        if not res:
            raise NotFoundException(detail=f"Work with ID {work_id} not found")
        return res


# ============================================================================
# Edition Controller
# ============================================================================


class EditionController(Controller):
    """版本管理控制器"""

    path = "/edition"

    @get("/{edition_id:int}")
    async def get_edition(
        self,
        edition_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> EditionResponse:
        """获取单个版本"""
        db = next(router_dependency)
        edition = get_edition_impl(db, edition_id)
        if not edition:
            raise NotFoundException(detail=f"Edition with ID {edition_id} not found")
        logger.info(f"Get edition {edition_id}")
        return edition

    @get("/work/{work_id:int}")
    async def get_editions_by_work(
        self,
        work_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> List[EditionResponse]:
        """获取作品的所有版本"""
        db = next(router_dependency)
        editions = get_editions_by_work_impl(db, work_id)
        logger.info(f"Get editions for work {work_id}: {len(editions)}")
        return editions

    @post("/")
    async def create_edition(
        self,
        data: EditionCreateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> EditionResponse:
        """创建版本"""
        db = next(router_dependency)
        edition = create_edition_impl(db, data)
        logger.info(f"Created edition: {edition.edition_name}")
        return edition

    @put("/{edition_id:int}")
    async def update_edition(
        self,
        edition_id: int,
        data: EditionUpdateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> EditionResponse:
        """更新版本"""
        db = next(router_dependency)
        edition = update_edition_impl(db, edition_id, data)
        if not edition:
            raise NotFoundException(detail=f"Edition with ID {edition_id} not found")
        logger.info(f"Updated edition {edition_id}")
        return edition

    @delete("/{edition_id:int}", status_code=200)
    async def delete_edition(
        self,
        edition_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> EditionResponse:
        """删除版本"""
        db = next(router_dependency)
        edition = delete_edition_impl(db, edition_id)
        if not edition:
            raise NotFoundException(detail=f"Edition with ID {edition_id} not found")
        logger.info(f"Deleted edition {edition_id}")
        return edition

    @get("/{edition_id:int}/chapters")
    async def get_chapter_list(
        self,
        edition_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> List[ChapterListItem]:
        """获取版本的章节列表（目录）"""
        db = next(router_dependency)
        chapters = get_chapter_list_impl(db, edition_id)
        logger.info(
            f"Get chapter list for edition {edition_id}: {len(chapters)} chapters"
        )
        return chapters

    @get("/{edition_id:int}/chapter/{chapter_index:int}")
    async def get_chapter_content(
        self,
        edition_id: int,
        chapter_index: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> DocumentNodeResponse:
        """获取指定章节的内容"""
        db = next(router_dependency)
        chapter = get_chapter_content_impl(db, edition_id, chapter_index)
        if not chapter:
            raise NotFoundException(
                detail=f"Chapter {chapter_index} in edition {edition_id} not found"
            )
        logger.info(f"Get chapter {chapter_index} for edition {edition_id}")
        return chapter

    @get("/{edition_id:int}/search")
    async def search_content(
        self,
        edition_id: int,
        keyword: str,
        router_dependency: Generator[Session, None, None],
        request: Request,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DocumentNodeResponse]:
        """搜索版本中的内容"""
        db = next(router_dependency)
        results = search_content_impl(db, edition_id, keyword, skip, limit)
        logger.info(
            f"Search content in edition {edition_id} with keyword '{keyword}': {len(results)} results"
        )
        return results

    @post("/{edition_id:int}/chapter/insert")
    async def insert_chapter(
        self,
        edition_id: int,
        data: ChapterInsertRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ChapterInsertResponse:
        """
        向版本的指定位置插入新章节

        插入后，目标位置及之后的章节会自动后移
        """
        db = next(router_dependency)
        chapter = insert_chapter_impl(
            db,
            edition_id,
            data.sort_index,
            data.label,
            data.title,
            data.content,
            data.meta_data,
        )
        if not chapter:
            raise NotFoundException(detail=f"Edition with ID {edition_id} not found")
        logger.info(
            f"Inserted chapter at position {data.sort_index} in edition {edition_id}"
        )
        return ChapterInsertResponse(
            chapter=chapter, message=f"成功插入章节到位置 {data.sort_index}"
        )

    @post("/{edition_id:int}/chapters/batch")
    async def batch_upload_chapters(
        self,
        edition_id: int,
        data: ChapterBatchUploadRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ChapterBatchUploadResponse:
        db = next(router_dependency)
        items = [
            ChapterBatchItem(
                label=ch.label,
                title=ch.title,
                content=ch.content,
                chapter_type=ch.chapter_type,
                volume_label=ch.volume_label,
                volume_title=ch.volume_title,
                parent_id=ch.parent_id,
                meta_data=ch.meta_data or {},
            )
            for ch in data.chapters
        ]
        accepted = batch_insert_chapters_impl(db, edition_id, items, data.start_index)
        if accepted == 0:
            raise NotFoundException(detail=f"Edition {edition_id} not found")
        total = get_chapter_count_impl(db, edition_id)
        logger.info(
            f"Batch uploaded {accepted} chapters to edition {edition_id}, total={total}"
        )
        return ChapterBatchUploadResponse(
            edition_id=edition_id,
            accepted=accepted,
            total_chapters=total,
        )

    @get("/{edition_id:int}/chapters/count")
    async def get_chapters_count(
        self,
        edition_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        db = next(router_dependency)
        count = get_chapter_count_impl(db, edition_id)
        return {"edition_id": edition_id, "count": count}

    @get("/{edition_id:int}/toc")
    async def get_edition_toc(
        self,
        edition_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> EditionTocResponse:
        """获取版本分卷树形目录"""
        db = next(router_dependency)
        toc = get_edition_toc_impl(db, edition_id)
        if not toc:
            raise NotFoundException(detail=f"Edition {edition_id} not found")
        return toc

    @post("/{edition_id:int}/volumes")
    async def create_volume(
        self,
        edition_id: int,
        data: VolumeCreateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> TocVolumeItem:
        """创建分卷（并可选将区间章节归入该卷）"""
        db = next(router_dependency)
        vol = create_volume_impl(db, edition_id, data)
        if not vol:
            raise NotFoundException(detail=f"Edition {edition_id} not found")
        return vol

    @post("/{edition_id:int}/volumes/{volume_id:int}/assign")
    async def assign_volume_chapters(
        self,
        edition_id: int,
        volume_id: int,
        data: VolumeAssignRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """批量将章节归入指定分卷"""
        db = next(router_dependency)
        cnt = assign_chapters_to_volume_impl(db, edition_id, volume_id, data)
        if cnt is None:
            raise NotFoundException(detail=f"Volume {volume_id} not found in edition {edition_id}")
        return {"edition_id": edition_id, "volume_id": volume_id, "assigned": cnt}

    @delete("/{edition_id:int}/volumes/{volume_id:int}", status_code=200)
    async def delete_volume(
        self,
        edition_id: int,
        volume_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """删除分卷（安全解绑卷下章节，不删正文）"""
        db = next(router_dependency)
        ok = delete_volume_impl(db, edition_id, volume_id)
        if not ok:
            raise NotFoundException(detail=f"Volume {volume_id} not found in edition {edition_id}")
        return {"deleted": True, "volume_id": volume_id}

    @post("/{edition_id:int}/auto-volume")
    async def auto_volume_edition(
        self,
        edition_id: int,
        data: AutoVolumeRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> AutoVolumeResponse:
        """自动识别/应用分卷结构（支持 dry_run 预览）"""
        db = next(router_dependency)
        res = auto_volume_edition_impl(db, edition_id, data)
        if not res:
            raise NotFoundException(detail=f"Edition {edition_id} not found")
        return res


# ============================================================================
# Document Node Controller
# ============================================================================


class DocumentNodeController(Controller):
    """文档节点控制器"""

    path = "/node"

    @get("/{node_id:int}")
    async def get_node(
        self,
        node_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
        include_content: bool = True,
    ) -> DocumentNodeResponse:
        """获取单个文档节点"""
        db = next(router_dependency)
        node = get_document_node_impl(db, node_id, include_content)
        if not node:
            raise NotFoundException(detail=f"Node with ID {node_id} not found")
        logger.info(f"Get node {node_id}")
        return node

    @put("/{node_id:int}")
    async def update_node(
        self,
        node_id: int,
        data: DocumentNodeUpdateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> DocumentNodeResponse:
        """更新文档节点"""
        db = next(router_dependency)
        node = update_document_node_impl(db, node_id, data)
        if not node:
            raise NotFoundException(detail=f"Node with ID {node_id} not found")
        logger.info(f"Updated node {node_id}")
        return node


# ============================================================================
# NoteItem Controller
# ============================================================================


class NoteContentUpdateRequest(BaseModel):
    """笔记 Markdown 内容更新请求"""

    content: str = Field(description="Markdown 原始内容")


def _resolve_note_file_path(setting_file: str) -> Path:
    """解析 note 文件绝对路径，限制在 workspace 内防止路径遍历"""
    # 支持以 workspace/notes 或 notes 开头的相对路径
    rel = setting_file
    if rel.startswith("/"):
        rel = rel.lstrip("/")
    # 统一基于 SERVER_DATA_DIR 解析
    base = SERVER_DATA_DIR
    target = (base / rel).resolve()
    base_resolved = base.resolve()
    # 路径安全检查
    try:
        target.relative_to(base_resolved)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid note file path (outside workspace): {setting_file}"
        )
    return target


class NoteItemController(Controller):
    """笔记索引与 Markdown 内容控制器"""

    path = "/note"

    @get("")
    async def list_notes(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        category: Optional[str] = None,
        work_id: Optional[int] = None,
        edition_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> NoteItemListResponse:
        """获取笔记索引列表"""
        db = next(router_dependency)
        notes = get_note_items_impl(db, category, work_id, edition_id, skip, limit)
        total = len(notes)  # 简化，实际可额外 count
        logger.info(
            f"List notes: category={category}, work={work_id}, edition={edition_id}, count={len(notes)}"
        )
        return NoteItemListResponse(notes=notes, total=total)

    @post("/")
    async def create_note(
        self,
        data: NoteItemCreateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> NoteItemResponse:
        """创建笔记索引"""
        db = next(router_dependency)
        note = create_note_item_impl(db, data)
        logger.info(f"Created note item {note.id}: {note.setting_file}")
        return note

    @get("/{note_id:int}")
    async def get_note(
        self,
        note_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> NoteItemResponse:
        """获取单个笔记索引"""
        db = next(router_dependency)
        note = get_note_item_impl(db, note_id)
        if not note:
            raise NotFoundException(detail=f"Note item with ID {note_id} not found")
        logger.info(f"Get note item {note_id}")
        return note

    @put("/{note_id:int}")
    async def update_note(
        self,
        note_id: int,
        data: NoteItemUpdateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> NoteItemResponse:
        """更新笔记索引"""
        db = next(router_dependency)
        note = update_note_item_impl(db, note_id, data)
        if not note:
            raise NotFoundException(detail=f"Note item with ID {note_id} not found")
        logger.info(f"Updated note item {note_id}")
        return note

    @delete("/{note_id:int}", status_code=200)
    async def delete_note(
        self,
        note_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> NoteItemResponse:
        """删除笔记索引"""
        db = next(router_dependency)
        note = delete_note_item_impl(db, note_id)
        if not note:
            raise NotFoundException(detail=f"Note item with ID {note_id} not found")
        logger.info(f"Deleted note item {note_id}")
        return note

    @get("/{note_id:int}/content")
    async def get_note_content(
        self,
        note_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> NoteItemContentResponse:
        """获取笔记 Markdown 原始内容"""
        db = next(router_dependency)
        note = get_note_item_impl(db, note_id)
        if not note:
            raise NotFoundException(detail=f"Note item with ID {note_id} not found")
        file_path = _resolve_note_file_path(note.setting_file)
        if not file_path.exists():
            content = ""
        else:
            content = file_path.read_text(encoding="utf-8")
        logger.info(f"Get note content {note_id}, size={len(content)}")
        return NoteItemContentResponse(
            id=note.id, setting_file=note.setting_file, content=content
        )

    @put("/{note_id:int}/content")
    async def update_note_content(
        self,
        note_id: int,
        data: NoteContentUpdateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> NoteItemContentResponse:
        """更新笔记 Markdown 原始内容"""
        db = next(router_dependency)
        note = get_note_item_impl(db, note_id)
        if not note:
            raise NotFoundException(detail=f"Note item with ID {note_id} not found")
        file_path = _resolve_note_file_path(note.setting_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # 清理 NUL 字符，避免 PostgreSQL text 字段问题
        content = data.content.replace("\x00", "")
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Updated note content {note_id}, size={len(content)}")
        return NoteItemContentResponse(
            id=note.id, setting_file=note.setting_file, content=content
        )

    @get("/links")
    async def get_note_links(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> NoteLinkGraphResponse:
        """获取所有笔记的双向链接图谱"""
        db = next(router_dependency)
        notes = get_note_items_impl(db, skip=0, limit=10000)
        graph = build_link_graph(
            [(n.id, n.title or n.slug or str(n.id), n.setting_file) for n in notes],
            workspace_root=SERVER_DATA_DIR,
        )
        logger.info(f"Get note link graph: {len(graph.get('nodes', []))} nodes")
        return NoteLinkGraphResponse(**graph)
