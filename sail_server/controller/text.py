# -*- coding: utf-8 -*-
# @file text.py
# @brief Text Content Controller
# @author sailing-innocent
# @date 2025-01-29
# @version 1.0
# ---------------------------------

from __future__ import annotations
from litestar.dto import DataclassDTO
from litestar.dto.config import DTOConfig
from litestar import Controller, delete, get, post, put, Request
from litestar.exceptions import NotFoundException

from sail_server.data.text import (
    WorkData, EditionData, DocumentNodeData, 
    TextImportRequest, ChapterListItem
)
from sail_server.model.text import (
    create_work_impl, get_work_impl, get_works_impl, update_work_impl, delete_work_impl,
    create_edition_impl, get_edition_impl, get_editions_by_work_impl, update_edition_impl, delete_edition_impl,
    get_document_node_impl, get_chapter_list_impl, get_chapter_content_impl, update_document_node_impl,
    import_text_impl, append_chapters_impl,
    search_works_impl, search_content_impl,
)

from sqlalchemy.orm import Session
from typing import Generator, List, Optional
from dataclasses import dataclass, field


# ============================================================================
# DTOs
# ============================================================================

class WorkDataWriteDTO(DataclassDTO[WorkData]):
    """创建作品时使用的DTO"""
    config = DTOConfig(
        include={
            "title", "original_title", "author", "language_primary",
            "work_type", "status", "synopsis", "meta_data",
        },
    )


class WorkDataReadDTO(DataclassDTO[WorkData]):
    """读取作品时使用的DTO"""
    pass


class EditionDataWriteDTO(DataclassDTO[EditionData]):
    """创建版本时使用的DTO"""
    config = DTOConfig(
        include={
            "work_id", "edition_name", "language", "source_format",
            "canonical", "description", "meta_data",
        },
    )


class EditionDataReadDTO(DataclassDTO[EditionData]):
    """读取版本时使用的DTO"""
    pass


class DocumentNodeDataWriteDTO(DataclassDTO[DocumentNodeData]):
    """更新文档节点时使用的DTO"""
    config = DTOConfig(
        include={
            "label", "title", "raw_text", "meta_data",
        },
    )


class DocumentNodeDataReadDTO(DataclassDTO[DocumentNodeData]):
    """读取文档节点时使用的DTO"""
    pass


class TextImportRequestDTO(DataclassDTO[TextImportRequest]):
    """文本导入请求DTO"""
    pass


# ============================================================================
# Response Models
# ============================================================================

@dataclass
class ImportResponse:
    """导入响应"""
    work: WorkData
    edition: EditionData
    chapter_count: int
    message: str = "导入成功"


@dataclass
class AppendResponse:
    """追加章节响应"""
    edition_id: int
    new_chapter_count: int
    message: str = "追加成功"


# ============================================================================
# Work Controller
# ============================================================================

class WorkController(Controller):
    """作品管理控制器"""
    dto = WorkDataWriteDTO
    return_dto = WorkDataReadDTO
    path = "/work"
    
    @get("")
    async def get_works(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        skip: int = 0,
        limit: int = 20,
    ) -> List[WorkData]:
        """获取作品列表"""
        db = next(router_dependency)
        works = get_works_impl(db, skip, limit)
        request.logger.info(f"Get works: {len(works)}")
        return works
    
    @get("/search")
    async def search_works(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        keyword: str,
        skip: int = 0,
        limit: int = 20,
    ) -> List[WorkData]:
        """搜索作品"""
        db = next(router_dependency)
        works = search_works_impl(db, keyword, skip, limit)
        request.logger.info(f"Search works with keyword '{keyword}': {len(works)}")
        return works
    
    @get("/{work_id:int}")
    async def get_work(
        self,
        work_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WorkData:
        """获取单个作品"""
        db = next(router_dependency)
        work = get_work_impl(db, work_id)
        if not work:
            raise NotFoundException(detail=f"Work with ID {work_id} not found")
        request.logger.info(f"Get work {work_id}: {work.title}")
        return work
    
    @post("/")
    async def create_work(
        self,
        data: WorkData,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WorkData:
        """创建作品"""
        db = next(router_dependency)
        work = create_work_impl(db, data)
        request.logger.info(f"Created work: {work.title}")
        return work
    
    @put("/{work_id:int}")
    async def update_work(
        self,
        work_id: int,
        data: WorkData,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WorkData:
        """更新作品"""
        db = next(router_dependency)
        work = update_work_impl(db, work_id, data)
        if not work:
            raise NotFoundException(detail=f"Work with ID {work_id} not found")
        request.logger.info(f"Updated work {work_id}: {work.title}")
        return work
    
    @delete("/{work_id:int}", status_code=200)
    async def delete_work(
        self,
        work_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WorkData:
        """删除作品"""
        db = next(router_dependency)
        work = delete_work_impl(db, work_id)
        if not work:
            raise NotFoundException(detail=f"Work with ID {work_id} not found")
        request.logger.info(f"Deleted work {work_id}")
        return work


# ============================================================================
# Edition Controller
# ============================================================================

class EditionController(Controller):
    """版本管理控制器"""
    dto = EditionDataWriteDTO
    return_dto = EditionDataReadDTO
    path = "/edition"
    
    @get("/{edition_id:int}")
    async def get_edition(
        self,
        edition_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> EditionData:
        """获取单个版本"""
        db = next(router_dependency)
        edition = get_edition_impl(db, edition_id)
        if not edition:
            raise NotFoundException(detail=f"Edition with ID {edition_id} not found")
        request.logger.info(f"Get edition {edition_id}")
        return edition
    
    @get("/work/{work_id:int}")
    async def get_editions_by_work(
        self,
        work_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> List[EditionData]:
        """获取作品的所有版本"""
        db = next(router_dependency)
        editions = get_editions_by_work_impl(db, work_id)
        request.logger.info(f"Get editions for work {work_id}: {len(editions)}")
        return editions
    
    @post("/")
    async def create_edition(
        self,
        data: EditionData,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> EditionData:
        """创建版本"""
        db = next(router_dependency)
        edition = create_edition_impl(db, data)
        request.logger.info(f"Created edition: {edition.edition_name}")
        return edition
    
    @put("/{edition_id:int}")
    async def update_edition(
        self,
        edition_id: int,
        data: EditionData,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> EditionData:
        """更新版本"""
        db = next(router_dependency)
        edition = update_edition_impl(db, edition_id, data)
        if not edition:
            raise NotFoundException(detail=f"Edition with ID {edition_id} not found")
        request.logger.info(f"Updated edition {edition_id}")
        return edition
    
    @delete("/{edition_id:int}", status_code=200)
    async def delete_edition(
        self,
        edition_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> EditionData:
        """删除版本"""
        db = next(router_dependency)
        edition = delete_edition_impl(db, edition_id)
        if not edition:
            raise NotFoundException(detail=f"Edition with ID {edition_id} not found")
        request.logger.info(f"Deleted edition {edition_id}")
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
        request.logger.info(f"Get chapter list for edition {edition_id}: {len(chapters)} chapters")
        return chapters
    
    @get("/{edition_id:int}/chapter/{chapter_index:int}")
    async def get_chapter_content(
        self,
        edition_id: int,
        chapter_index: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> DocumentNodeData:
        """获取指定章节的内容"""
        db = next(router_dependency)
        chapter = get_chapter_content_impl(db, edition_id, chapter_index)
        if not chapter:
            raise NotFoundException(detail=f"Chapter {chapter_index} in edition {edition_id} not found")
        request.logger.info(f"Get chapter {chapter_index} for edition {edition_id}")
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
    ) -> List[DocumentNodeData]:
        """搜索版本中的内容"""
        db = next(router_dependency)
        results = search_content_impl(db, edition_id, keyword, skip, limit)
        request.logger.info(f"Search content in edition {edition_id} with keyword '{keyword}': {len(results)} results")
        return results


# ============================================================================
# Document Node Controller
# ============================================================================

class DocumentNodeController(Controller):
    """文档节点控制器"""
    dto = DocumentNodeDataWriteDTO
    return_dto = DocumentNodeDataReadDTO
    path = "/node"
    
    @get("/{node_id:int}")
    async def get_node(
        self,
        node_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
        include_content: bool = True,
    ) -> DocumentNodeData:
        """获取单个文档节点"""
        db = next(router_dependency)
        node = get_document_node_impl(db, node_id, include_content)
        if not node:
            raise NotFoundException(detail=f"Node with ID {node_id} not found")
        request.logger.info(f"Get node {node_id}")
        return node
    
    @put("/{node_id:int}")
    async def update_node(
        self,
        node_id: int,
        data: DocumentNodeData,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> DocumentNodeData:
        """更新文档节点"""
        db = next(router_dependency)
        node = update_document_node_impl(db, node_id, data)
        if not node:
            raise NotFoundException(detail=f"Node with ID {node_id} not found")
        request.logger.info(f"Updated node {node_id}")
        return node


# ============================================================================
# Import Controller
# ============================================================================

class ImportController(Controller):
    """导入控制器"""
    path = "/import"
    
    @post("/")
    async def import_text(
        self,
        data: TextImportRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ImportResponse:
        """
        导入文本
        
        接收原始文本内容，自动解析章节并创建作品
        """
        db = next(router_dependency)
        work, edition, chapter_count = import_text_impl(db, data)
        request.logger.info(f"Imported text: {work.title}, {chapter_count} chapters")
        return ImportResponse(
            work=work,
            edition=edition,
            chapter_count=chapter_count,
            message=f"成功导入《{work.title}》，共 {chapter_count} 章"
        )
    
    @post("/append/{edition_id:int}")
    async def append_chapters(
        self,
        edition_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
        content: str,
        chapter_pattern: Optional[str] = None,
    ) -> AppendResponse:
        """
        追加章节到现有版本
        """
        db = next(router_dependency)
        new_count = append_chapters_impl(db, edition_id, content, chapter_pattern)
        if new_count == 0:
            raise NotFoundException(detail=f"Edition with ID {edition_id} not found or no chapters parsed")
        request.logger.info(f"Appended {new_count} chapters to edition {edition_id}")
        return AppendResponse(
            edition_id=edition_id,
            new_chapter_count=new_count,
            message=f"成功追加 {new_count} 章"
        )
