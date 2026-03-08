# -*- coding: utf-8 -*-
# @file text.py
# @brief Text Content Controller
# @author sailing-innocent
# @date 2025-01-29
# @version 1.0
# ---------------------------------

from __future__ import annotations
from litestar import Controller, delete, get, post, put, Request
from litestar.exceptions import NotFoundException
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
)
from sail_server.model.text import (
    create_work_impl, get_work_impl, get_works_impl, update_work_impl, delete_work_impl,
    create_edition_impl, get_edition_impl, get_editions_by_work_impl, update_edition_impl, delete_edition_impl,
    get_document_node_impl, get_chapter_list_impl, get_chapter_content_impl, update_document_node_impl,
    import_text_impl, append_chapters_impl, insert_chapter_impl,
    search_works_impl, search_content_impl,
)

from sqlalchemy.orm import Session
from typing import Generator, List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# Request/Response Models
# ============================================================================

class TextImportRequest(BaseModel):
    """文本导入请求"""
    title: str = Field(description="作品标题")
    author: Optional[str] = Field(default=None, description="作者")
    content: str = Field(description="文本内容")
    chapter_pattern: Optional[str] = Field(default=None, description="章节匹配模式")


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
    sort_order: int = Field(description="排序顺序")
    label: str = Field(description="章节标签")
    title: str = Field(description="章节标题")
    level: int = Field(description="层级")


class ImportResponse(BaseModel):
    """导入响应"""
    work: WorkResponse
    edition: EditionResponse
    chapter_count: int
    message: str = "导入成功"


class AsyncImportRequest(BaseModel):
    """异步导入请求"""
    file_id: str = Field(description="上传文件ID")
    work_title: str = Field(description="作品标题")
    work_author: Optional[str] = Field(default=None, description="作者")
    edition_name: Optional[str] = Field(default="原始导入", description="版本名称")
    enable_ai_parsing: bool = Field(default=True, description="启用AI解析")
    priority: int = Field(default=5, description="任务优先级(1-10)")


class AsyncImportResponse(BaseModel):
    """异步导入响应"""
    task_id: int
    status: str
    message: str = "导入任务已创建"


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str
    file_name: str
    file_size: int
    encoding: Optional[str] = None
    message: str = "文件上传成功"


class ImportTaskResponse(BaseModel):
    """导入任务详情响应"""
    id: int
    task_type: str
    status: str
    work_title: str
    work_author: Optional[str] = None
    progress: int
    current_phase: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class ImportTaskListResponse(BaseModel):
    """导入任务列表响应"""
    tasks: List[ImportTaskResponse]
    total: int


class AppendResponse(BaseModel):
    """追加章节响应"""
    edition_id: int
    new_chapter_count: int
    message: str = "追加成功"


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
        limit: int = 20,
    ) -> List[WorkResponse]:
        """获取作品列表"""
        db = next(router_dependency)
        works = get_works_impl(db, skip, limit)
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
        logger.info(f"Get chapter list for edition {edition_id}: {len(chapters)} chapters")
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
            raise NotFoundException(detail=f"Chapter {chapter_index} in edition {edition_id} not found")
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
        logger.info(f"Search content in edition {edition_id} with keyword '{keyword}': {len(results)} results")
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
            db, edition_id, data.sort_index, 
            data.label, data.title, data.content, data.meta_data
        )
        if not chapter:
            raise NotFoundException(detail=f"Edition with ID {edition_id} not found")
        logger.info(f"Inserted chapter at position {data.sort_index} in edition {edition_id}")
        return ChapterInsertResponse(
            chapter=chapter,
            message=f"成功插入章节到位置 {data.sort_index}"
        )


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
        logger.info(f"Imported text: {work.title}, {chapter_count} chapters")
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
        logger.info(f"Appended {new_count} chapters to edition {edition_id}")
        return AppendResponse(
            edition_id=edition_id,
            new_chapter_count=new_count,
            message=f"成功追加 {new_count} 章"
        )


# ============================================================================
# Async Import Controller
# ============================================================================

class AsyncImportController(Controller):
    """异步导入控制器"""
    path = "/import-async"
    
    @post("/upload")
    async def upload_file(
        self,
        data: bytes,
        router_dependency: Generator[Session, None, None],
        request: Request,
        filename: str = "upload.txt",
        encoding: Optional[str] = None,
    ) -> FileUploadResponse:
        """
        上传文件
        
        接收文件数据并保存到临时目录，返回 file_id 用于后续导入
        """
        from sail_server.utils.text_import import get_temp_file_manager
        
        temp_manager = get_temp_file_manager()
        
        # 验证文件
        is_valid, error = temp_manager.validate_file(filename, len(data))
        if not is_valid:
            raise NotFoundException(detail=error)
        
        # 保存文件
        info = temp_manager.save_upload(data, filename, encoding)
        
        logger.info(f"File uploaded: {filename} -> {info.file_id}")
        
        return FileUploadResponse(
            file_id=info.file_id,
            file_name=filename,
            file_size=info.file_size,
            encoding=info.encoding,
        )
    
    @post("/")
    async def create_import_task(
        self,
        data: AsyncImportRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> AsyncImportResponse:
        """
        创建异步导入任务
        
        创建后台任务处理文本导入，支持大文件和AI解析
        """
        db = next(router_dependency)
        
        # 验证文件存在
        from sail_server.utils.text_import import get_temp_file_manager
        temp_manager = get_temp_file_manager()
        file_info = temp_manager.get_file(data.file_id)
        
        if not file_info:
            raise NotFoundException(detail=f"File not found: {data.file_id}")
        
        # 创建统一任务
        from sail_server.application.dto.unified_agent import UnifiedAgentTaskCreateRequest
        from sail_server.model.unified_agent import UnifiedTaskDAO
        
        task_data = UnifiedAgentTaskCreateRequest(
            task_type="text_import",
            priority=data.priority,
            payload={
                "file_id": data.file_id,
                "work_title": data.work_title,
                "work_author": data.work_author,
                "edition_name": data.edition_name,
                "enable_ai_parsing": data.enable_ai_parsing,
            }
        )
        
        task_dao = UnifiedTaskDAO(db)
        task = task_dao.create(task_data)
        
        logger.info(f"Async import task created: {task.id} for {data.work_title}")
        
        return AsyncImportResponse(
            task_id=task.id,
            status=task.status,
            message="导入任务已创建，正在排队处理"
        )
    
    @get("/tasks")
    async def list_import_tasks(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> ImportTaskListResponse:
        """
        获取导入任务列表
        
        支持按状态筛选和分页
        """
        db = next(router_dependency)
        
        from sail_server.model.unified_agent import UnifiedTaskDAO
        
        task_dao = UnifiedTaskDAO(db)
        
        # 获取任务列表（只获取 text_import 类型的任务）
        tasks = task_dao.get_by_type("text_import", status, skip, limit)
        total = task_dao.count_by_type("text_import", status)
        
        task_responses = []
        for task in tasks:
            # 从 payload 中提取作品信息
            payload = task.payload or {}
            work_title = payload.get("work_title", "Unknown")
            work_author = payload.get("work_author")
            
            task_responses.append(ImportTaskResponse(
                id=task.id,
                task_type=task.task_type,
                status=task.status,
                work_title=work_title,
                work_author=work_author,
                progress=task.progress,
                current_phase=task.current_phase,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
                result=task.result,
                error_message=task.error_message,
            ))
        
        return ImportTaskListResponse(
            tasks=task_responses,
            total=total
        )
    
    @get("/tasks/{task_id:int}")
    async def get_import_task(
        self,
        task_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ImportTaskResponse:
        """
        获取导入任务详情
        """
        db = next(router_dependency)
        
        from sail_server.model.unified_agent import UnifiedTaskDAO
        
        task_dao = UnifiedTaskDAO(db)
        task = task_dao.get_by_id(task_id)
        
        if not task or task.task_type != "text_import":
            raise NotFoundException(detail=f"Import task with ID {task_id} not found")
        
        # 从 payload 中提取作品信息
        payload = task.payload or {}
        work_title = payload.get("work_title", "Unknown")
        work_author = payload.get("work_author")
        
        return ImportTaskResponse(
            id=task.id,
            task_type=task.task_type,
            status=task.status,
            work_title=work_title,
            work_author=work_author,
            progress=task.progress,
            current_phase=task.current_phase,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            result=task.result,
            error_message=task.error_message,
        )
    
    @post("/tasks/{task_id:int}/cancel")
    async def cancel_import_task(
        self,
        task_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> Dict[str, str]:
        """
        取消导入任务
        """
        db = next(router_dependency)
        
        from sail_server.model.unified_agent import UnifiedTaskDAO
        from sail_server.application.dto.unified_agent import TaskStatus
        
        task_dao = UnifiedTaskDAO(db)
        task = task_dao.get_by_id(task_id)
        
        if not task or task.task_type != "text_import":
            raise NotFoundException(detail=f"Import task with ID {task_id} not found")
        
        if task.status not in [TaskStatus.PENDING, TaskStatus.SCHEDULED, TaskStatus.RUNNING]:
            return {"message": f"Task cannot be cancelled (status: {task.status})"}
        
        # 标记为取消
        task_dao.mark_as_cancelled(task_id)
        
        logger.info(f"Import task {task_id} cancelled")
        
        return {"message": "任务已取消"}
    
    @delete("/tasks/{task_id:int}")
    async def delete_import_task(
        self,
        task_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> Dict[str, str]:
        """
        删除导入任务记录
        
        只删除任务记录，不删除已导入的作品数据
        """
        db = next(router_dependency)
        
        from sail_server.model.unified_agent import UnifiedTaskDAO
        
        task_dao = UnifiedTaskDAO(db)
        task = task_dao.get_by_id(task_id)
        
        if not task or task.task_type != "text_import":
            raise NotFoundException(detail=f"Import task with ID {task_id} not found")
        
        # 删除任务
        task_dao.delete(task_id)
        
        # 清理临时文件
        payload = task.payload or {}
        file_id = payload.get("file_id")
        if file_id:
            from sail_server.utils.text_import import get_temp_file_manager
            temp_manager = get_temp_file_manager()
            temp_manager.delete_file(file_id)
        
        logger.info(f"Import task {task_id} deleted")
        
        return {"message": "任务已删除"}
