# -*- coding: utf-8 -*-
# @file content_v2.py
# @brief Content 2.0 Controllers (Multi-Format Import, Progress, Topics<->Rhythm, Assets, Vault Index)
# @author sailing-innocent
# @date 2026-11-26
# @version 1.0
# ---------------------------------

from __future__ import annotations

import logging
from typing import Generator, List, Optional

from litestar import Controller, Request, delete, get, post, put
from litestar.datastructures import UploadFile
from litestar.exceptions import HTTPException, NotFoundException
from litestar.params import Body
from litestar.response import File
from sqlalchemy.orm import Session

from sail_server.application.dto.text import (
    ArxivImportRequest,
    ContentAssetResponse,
    ContentTopicCreateRequest,
    ContentTopicDetailResponse,
    ContentTopicResponse,
    ContentTopicUpdateRequest,
    ContentTopicWorkAttachRequest,
    ContentTopicWorkItem,
    MultiFormatImportResponse,
    ReadingOverviewResponse,
    ReadingProgressResponse,
    ReadingProgressSyncRequest,
    ReadingProgressSyncResponse,
    ReadingProgressUpsertRequest,
    ReadingSessionCreateRequest,
    ReadingSessionResponse,
    TopicPushRhythmTaskRequest,
    TopicRhythmTaskSummary,
    VaultNoteIndexItem,
    VaultNoteIndexSyncRequest,
    VaultNoteIndexSyncResponse,
)
from sail_server.controller.text import WorkEditionCreateRequest, WorkEditionCreateResponse
from sail_server.model.content_ingest import (
    import_arxiv_impl,
    import_epub_impl,
    import_pdf_impl,
)
from sail_server.model.content_library import (
    MAX_CONTENT_ASSET_BYTES,
    attach_work_to_topic_impl,
    create_topic_impl,
    delete_content_asset_impl,
    delete_topic_impl,
    detach_work_from_topic_impl,
    get_content_asset_impl,
    get_reading_overview_impl,
    get_reading_progress_impl,
    get_topic_detail_impl,
    list_content_assets_impl,
    list_topics_impl,
    list_vault_note_index_impl,
    push_topic_rhythm_task_impl,
    record_reading_session_impl,
    resolve_asset_file_path,
    save_content_asset_impl,
    sync_reading_progress_batch_impl,
    sync_vault_note_index_impl,
    update_topic_impl,
    upsert_reading_progress_impl,
)
from sail_server.model.text import create_work_with_edition_impl

logger = logging.getLogger(__name__)


# ============================================================================
# 1. Import Controller (/api/v1/text/import)
# ============================================================================


class ImportController(Controller):
    """多格式内容导入控制器（TXT 建壳 / EPUB / PDF / arXiv）"""

    path = "/import"

    @post("/create")
    async def create_work_with_edition(
        self,
        data: WorkEditionCreateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WorkEditionCreateResponse:
        """一步创建空 Work + Edition（兼容 sailzen-ai-text-import 分批上传流程）"""
        db = next(router_dependency)
        work, edition = create_work_with_edition_impl(
            db,
            title=data.title,
            author=data.author,
            edition_name=data.edition_name,
            language=data.language,
            work_type=data.work_type,
            source_format=data.source_format,
            pillar=data.pillar,
            reading_status=data.reading_status,
            reading_track=data.reading_track,
            synopsis=data.synopsis,
            source_url=data.source_url,
            topic_id=data.topic_id,
            meta_data=data.meta_data,
        )
        return WorkEditionCreateResponse(work=work, edition=edition)

    @post("/epub")
    async def import_epub(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        data: UploadFile = Body(media_type="multipart/form-data"),
        pillar: str = "fiction",
        reading_track: str = "mainline",
        work_type: str = "book",
        topic_id: Optional[int] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
    ) -> MultiFormatImportResponse:
        """上传并解析 EPUB（自动识别分卷与章节，并归档原件）"""
        content = await data.read()
        if not content or len(content) > MAX_CONTENT_ASSET_BYTES:
            raise HTTPException(status_code=400, detail="EPUB 文件为空或超过 100MB 限制")
        db = next(router_dependency)
        try:
            return import_epub_impl(
                db,
                epub_bytes=content,
                filename=data.filename or "book.epub",
                pillar=pillar,
                reading_track=reading_track,
                work_type=work_type,
                topic_id=topic_id,
                title_override=title,
                author_override=author,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception("EPUB import failed")
            raise HTTPException(status_code=500, detail=f"EPUB 解析失败: {e}")

    @post("/pdf")
    async def import_pdf(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        data: UploadFile = Body(media_type="multipart/form-data"),
        pillar: str = "tech",
        reading_track: str = "project",
        work_type: str = "paper",
        topic_id: Optional[int] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> MultiFormatImportResponse:
        """上传并解析 PDF（双轨保留：分节正文入阅读库 + 原 PDF 归档对照）"""
        content = await data.read()
        if not content or len(content) > MAX_CONTENT_ASSET_BYTES:
            raise HTTPException(status_code=400, detail="PDF 文件为空或超过 100MB 限制")
        db = next(router_dependency)
        try:
            return import_pdf_impl(
                db,
                pdf_bytes=content,
                filename=data.filename or "paper.pdf",
                pillar=pillar,
                reading_track=reading_track,
                work_type=work_type,
                topic_id=topic_id,
                title_override=title,
                author_override=author,
                source_url=source_url,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception("PDF import failed")
            raise HTTPException(status_code=500, detail=f"PDF 解析失败: {e}")

    @post("/arxiv")
    async def import_arxiv(
        self,
        data: ArxivImportRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> MultiFormatImportResponse:
        """通过 arXiv ID / URL 导入论文（元数据 + 分节正文 + 可选原 PDF）"""
        db = next(router_dependency)
        try:
            return import_arxiv_impl(
                db,
                arxiv_id_or_url=data.arxiv_id_or_url,
                pillar=data.pillar,
                reading_track=data.reading_track,
                topic_id=data.topic_id,
                download_pdf=data.download_pdf,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception("arXiv import failed")
            raise HTTPException(status_code=502, detail=f"arXiv 导入失败: {e}")


# ============================================================================
# 2. Reading Progress & Stats Controller (/api/v1/text/progress)
# ============================================================================


class ProgressController(Controller):
    """云端阅读进度、阅读会话与素养概览控制器"""

    path = "/progress"

    @get("/overview")
    async def get_overview(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ReadingOverviewResponse:
        """阅读库总览与三大素养投入统计（Web 看板 & SailTick 共享）"""
        db = next(router_dependency)
        return get_reading_overview_impl(db)

    @post("/sync")
    async def sync_progress_batch(
        self,
        data: ReadingProgressSyncRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ReadingProgressSyncResponse:
        """批量阅读进度同步（Android 离线对账）"""
        db = next(router_dependency)
        return sync_reading_progress_batch_impl(db, data)

    @post("/session")
    async def record_session(
        self,
        data: ReadingSessionCreateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ReadingSessionResponse:
        """上报一次阅读会话"""
        db = next(router_dependency)
        res = record_reading_session_impl(db, data)
        if not res:
            raise NotFoundException(detail=f"Work {data.work_id} not found")
        return res

    @get("/{work_id:int}")
    async def get_progress(
        self,
        work_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ReadingProgressResponse:
        db = next(router_dependency)
        prog = get_reading_progress_impl(db, work_id)
        if not prog:
            raise NotFoundException(detail=f"No reading progress for work {work_id}")
        return prog

    @put("/{work_id:int}")
    async def upsert_progress(
        self,
        work_id: int,
        data: ReadingProgressUpsertRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ReadingProgressResponse:
        db = next(router_dependency)
        prog, _ = upsert_reading_progress_impl(db, work_id, data)
        if not prog:
            raise NotFoundException(detail=f"Work {work_id} not found")
        return prog


# ============================================================================
# 3. Topic & Rhythm Linkage Controller (/api/v1/text/topic)
# ============================================================================


class TopicController(Controller):
    """研究专题与 Rhythm Venture 双向联动控制器"""

    path = "/topic"

    @get("")
    async def list_topics(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        pillar: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[ContentTopicResponse]:
        db = next(router_dependency)
        return list_topics_impl(db, pillar=pillar, status=status)

    @post("/")
    async def create_topic(
        self,
        data: ContentTopicCreateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ContentTopicResponse:
        db = next(router_dependency)
        return create_topic_impl(db, data)

    @get("/{topic_id:int}/detail")
    async def get_topic_detail(
        self,
        topic_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ContentTopicDetailResponse:
        db = next(router_dependency)
        detail = get_topic_detail_impl(db, topic_id)
        if not detail:
            raise NotFoundException(detail=f"Topic {topic_id} not found")
        return detail

    @put("/{topic_id:int}")
    async def update_topic(
        self,
        topic_id: int,
        data: ContentTopicUpdateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ContentTopicResponse:
        db = next(router_dependency)
        updated = update_topic_impl(db, topic_id, data)
        if not updated:
            raise NotFoundException(detail=f"Topic {topic_id} not found")
        return updated

    @delete("/{topic_id:int}", status_code=200)
    async def delete_topic(
        self,
        topic_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        db = next(router_dependency)
        ok = delete_topic_impl(db, topic_id)
        if not ok:
            raise NotFoundException(detail=f"Topic {topic_id} not found")
        return {"deleted": True, "topic_id": topic_id}

    @post("/{topic_id:int}/works")
    async def attach_work(
        self,
        topic_id: int,
        data: ContentTopicWorkAttachRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ContentTopicWorkItem:
        db = next(router_dependency)
        item = attach_work_to_topic_impl(db, topic_id, data)
        if not item:
            raise NotFoundException(detail="Topic or Work not found")
        return item

    @delete("/{topic_id:int}/works/{work_id:int}", status_code=200)
    async def detach_work(
        self,
        topic_id: int,
        work_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        db = next(router_dependency)
        ok = detach_work_from_topic_impl(db, topic_id, work_id)
        if not ok:
            raise NotFoundException(detail="Topic-Work association not found")
        return {"detached": True, "topic_id": topic_id, "work_id": work_id}

    @post("/{topic_id:int}/push-rhythm-task")
    async def push_rhythm_task(
        self,
        topic_id: int,
        data: TopicPushRhythmTaskRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> TopicRhythmTaskSummary:
        """从专题/论文一键推送里程碑任务到 Rhythm"""
        db = next(router_dependency)
        task = push_topic_rhythm_task_impl(db, topic_id, data)
        if not task:
            raise NotFoundException(detail=f"Topic {topic_id} not found")
        return task


# ============================================================================
# 4. Content Asset Controller (/api/v1/text/asset)
# ============================================================================


class AssetController(Controller):
    """论文 PDF 原件、EPUB 与审美参考图附件控制器"""

    path = "/asset"

    @get("")
    async def list_assets(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        work_id: Optional[int] = None,
        topic_id: Optional[int] = None,
        asset_kind: Optional[str] = None,
    ) -> List[ContentAssetResponse]:
        db = next(router_dependency)
        return list_content_assets_impl(
            db, work_id=work_id, topic_id=topic_id, asset_kind=asset_kind
        )

    @post("/upload")
    async def upload_asset(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        data: UploadFile = Body(media_type="multipart/form-data"),
        work_id: Optional[int] = None,
        topic_id: Optional[int] = None,
        asset_kind: str = "attachment",
    ) -> ContentAssetResponse:
        content = await data.read()
        if not content or len(content) > MAX_CONTENT_ASSET_BYTES:
            raise HTTPException(status_code=400, detail="附件为空或超过 100MB 限制")
        db = next(router_dependency)
        return save_content_asset_impl(
            db,
            content_bytes=content,
            original_name=data.filename or "asset.bin",
            mime_type=data.content_type or "application/octet-stream",
            asset_kind=asset_kind,
            work_id=work_id,
            topic_id=topic_id,
        )

    @get("/{asset_id:int}/file")
    async def download_asset_file(
        self,
        asset_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> File:
        db = next(router_dependency)
        asset = get_content_asset_impl(db, asset_id)
        if not asset:
            raise NotFoundException(detail=f"Asset {asset_id} not found")
        try:
            fp = resolve_asset_file_path(asset.storage_key)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid asset storage path")
        if not fp.exists():
            raise NotFoundException(detail="Asset file missing on disk")
        return File(
            path=str(fp),
            filename=asset.original_name,
            media_type=asset.mime_type or "application/octet-stream",
            content_disposition_type="inline",
        )

    @delete("/{asset_id:int}", status_code=200)
    async def delete_asset(
        self,
        asset_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        db = next(router_dependency)
        ok = delete_content_asset_impl(db, asset_id)
        if not ok:
            raise NotFoundException(detail=f"Asset {asset_id} not found")
        return {"deleted": True, "asset_id": asset_id}


# ============================================================================
# 5. Vault Content Index Controller (/api/v1/text/vault)
# ============================================================================


class VaultContentController(Controller):
    """D:\\vault 内容笔记轻量只读索引控制器（read.* / topic.* / study.*）"""

    path = "/vault"

    @post("/index/sync")
    async def sync_vault_index(
        self,
        data: VaultNoteIndexSyncRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> VaultNoteIndexSyncResponse:
        db = next(router_dependency)
        return sync_vault_note_index_impl(db, data)

    @get("/index")
    async def list_vault_index(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        namespace: Optional[str] = None,
        pillar: Optional[str] = None,
        work_id: Optional[int] = None,
        topic_id: Optional[int] = None,
        keyword: Optional[str] = None,
        limit: int = 100,
    ) -> List[VaultNoteIndexItem]:
        db = next(router_dependency)
        return list_vault_note_index_impl(
            db,
            namespace=namespace,
            pillar=pillar,
            work_id=work_id,
            topic_id=topic_id,
            keyword=keyword,
            limit=limit,
        )
