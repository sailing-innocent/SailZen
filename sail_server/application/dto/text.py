# -*- coding: utf-8 -*-
# @file text.py
# @brief Text & Content 2.0 Pydantic DTOs
# @author sailing-innocent
# @date 2026-11-26
# @version 2.0
# ---------------------------------

"""
文本与内容阅读库模块 Pydantic DTOs（Content 2.0）
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Reading Progress Summary (embedded in WorkResponse)
# ============================================================================


class ReadingProgressSummary(BaseModel):
    """嵌入式阅读进度摘要（随 WorkResponse 返回，避免前端 N+1 请求）。"""

    model_config = ConfigDict(from_attributes=True)

    edition_id: int
    node_id: Optional[int] = None
    sort_index: int = 0
    char_offset: int = 0
    scroll_offset: int = 0
    page_index: int = 0
    mode: str = "scroll"
    progress_pct: float = 0.0
    total_read_seconds: int = 0
    client_device: str = ""
    last_read_at: Optional[datetime] = None


# ============================================================================
# Work DTOs
# ============================================================================


class WorkBase(BaseModel):
    """作品基础信息"""

    model_config = ConfigDict(from_attributes=True)

    slug: str = Field(description="唯一标识符")
    title: str = Field(description="作品标题")
    original_title: Optional[str] = Field(default=None, description="原始标题")
    author: Optional[str] = Field(default=None, description="作者")
    language_primary: str = Field(default="zh", description="主要语言")
    work_type: str = Field(
        default="web_novel",
        description="作品类型: web_novel | book | paper | article | script | reference",
    )
    status: str = Field(default="ongoing", description="作品状态")
    synopsis: Optional[str] = Field(default=None, description="简介")
    pillar: str = Field(
        default="fiction",
        description="素养归属: tech | history | aesthetics | fiction | general",
    )
    reading_status: str = Field(
        default="queued",
        description="阅读状态: inbox | queued | reading | paused | finished | dropped",
    )
    reading_track: str = Field(
        default="leisure",
        description="阅读轨道: mainline | project | leisure",
    )
    priority: int = Field(default=3, description="优先级 1-5 (1 最高)")
    source_url: Optional[str] = Field(default=None, description="原始来源链接/arXiv")
    vault_slug: Optional[str] = Field(default=None, description="本地 Vault 笔记标识")
    is_original: bool = Field(default=False, description="是否为原创创作作品")


class WorkCreateRequest(WorkBase):
    """创建作品请求"""

    meta_data: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class WorkUpdateRequest(BaseModel):
    """更新作品请求"""

    model_config = ConfigDict(from_attributes=True)

    title: Optional[str] = Field(default=None, description="作品标题")
    original_title: Optional[str] = Field(default=None, description="原始标题")
    author: Optional[str] = Field(default=None, description="作者")
    work_type: Optional[str] = Field(default=None, description="作品类型")
    status: Optional[str] = Field(default=None, description="作品状态")
    synopsis: Optional[str] = Field(default=None, description="简介")
    pillar: Optional[str] = Field(default=None, description="素养归属")
    reading_status: Optional[str] = Field(default=None, description="阅读状态")
    reading_track: Optional[str] = Field(default=None, description="阅读轨道")
    priority: Optional[int] = Field(default=None, description="优先级 1-5")
    source_url: Optional[str] = Field(default=None, description="原始来源链接")
    vault_slug: Optional[str] = Field(default=None, description="本地 Vault 笔记标识")
    is_original: Optional[bool] = Field(default=None, description="是否原创")
    meta_data: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class WorkResponse(WorkBase):
    """作品响应"""

    id: int = Field(description="作品ID")
    meta_data: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    edition_count: int = Field(default=0, description="版本数量")
    chapter_count: int = Field(default=0, description="章节数量")
    total_chars: int = Field(default=0, description="总字符数")
    progress: Optional[ReadingProgressSummary] = Field(
        default=None, description="当前云端阅读进度"
    )
    topic_ids: List[int] = Field(default_factory=list, description="关联专题 ID 列表")
    asset_count: int = Field(default=0, description="关联附件数(如 PDF 原件)")


class WorkListResponse(BaseModel):
    """作品列表响应"""

    works: List[WorkResponse]
    total: int


# ============================================================================
# Edition DTOs
# ============================================================================


class EditionBase(BaseModel):
    """版本基础信息"""

    model_config = ConfigDict(from_attributes=True)

    work_id: int = Field(description="所属作品ID")
    edition_name: Optional[str] = Field(default=None, description="版本名称")
    language: str = Field(default="zh", description="语言")
    source_format: str = Field(default="txt", description="源格式")
    canonical: bool = Field(default=False, description="是否规范版本")
    description: Optional[str] = Field(default=None, description="版本描述")


class EditionCreateRequest(EditionBase):
    """创建版本请求"""

    source_path: Optional[str] = Field(default=None, description="源文件路径")
    meta_data: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class EditionUpdateRequest(BaseModel):
    """更新版本请求"""

    model_config = ConfigDict(from_attributes=True)

    edition_name: Optional[str] = Field(default=None, description="版本名称")
    canonical: Optional[bool] = Field(default=None, description="是否规范版本")
    status: Optional[str] = Field(default=None, description="版本状态")
    description: Optional[str] = Field(default=None, description="版本描述")


class EditionResponse(EditionBase):
    """版本响应"""

    id: int = Field(description="版本ID")
    source_path: Optional[str] = Field(default=None, description="源文件路径")
    source_checksum: Optional[str] = Field(default=None, description="源文件校验和")
    ingest_version: int = Field(default=1, description="导入版本")
    word_count: Optional[int] = Field(default=None, description="字数")
    char_count: Optional[int] = Field(default=None, description="字符数")
    status: str = Field(default="draft", description="版本状态")
    meta_data: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class EditionListResponse(BaseModel):
    """版本列表响应"""

    editions: List[EditionResponse]
    total: int


# ============================================================================
# DocumentNode & Volume TOC DTOs
# ============================================================================


class DocumentNodeBase(BaseModel):
    """文档节点基础信息"""

    model_config = ConfigDict(from_attributes=True)

    edition_id: int = Field(description="所属版本ID")
    node_type: str = Field(default="chapter", description="节点类型")
    label: Optional[str] = Field(default=None, description="显示标签")
    title: Optional[str] = Field(default="", description="节点标题")
    raw_text: Optional[str] = Field(default=None, description="节点内容")
    path: Optional[str] = Field(default=None, description="节点路径")
    sort_index: int = Field(default=0, description="排序索引")
    depth: int = Field(default=1, description="层级深度")


class DocumentNodeCreateRequest(DocumentNodeBase):
    """创建文档节点请求"""

    parent_id: Optional[int] = Field(default=None, description="父节点ID")
    sort_order: Optional[int] = Field(default=None, description="排序顺序")
    meta_data: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class DocumentNodeUpdateRequest(BaseModel):
    """更新文档节点请求"""

    model_config = ConfigDict(from_attributes=True)

    label: Optional[str] = Field(default=None, description="显示标签")
    title: Optional[str] = Field(default=None, description="节点标题")
    raw_text: Optional[str] = Field(default=None, description="节点内容")
    sort_order: Optional[int] = Field(default=None, description="排序顺序")
    parent_id: Optional[int] = Field(default=None, description="父节点ID(分卷归属)")
    meta_data: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class DocumentNodeResponse(DocumentNodeBase):
    """文档节点响应"""

    id: int = Field(description="节点ID")
    parent_id: Optional[int] = Field(default=None, description="父节点ID")
    sort_index: int = Field(default=0, description="排序索引")
    word_count: Optional[int] = Field(default=None, description="字数")
    char_count: Optional[int] = Field(default=None, description="字符数")
    meta_data: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class DocumentNodeListResponse(BaseModel):
    """文档节点列表响应"""

    nodes: List[DocumentNodeResponse]
    total: int


class TocChapterItem(BaseModel):
    """目录树中的章节项"""

    id: int
    parent_id: Optional[int] = None
    sort_index: int
    label: Optional[str] = None
    title: Optional[str] = None
    char_count: Optional[int] = None
    path: str
    node_type: str = "chapter"


class TocVolumeItem(BaseModel):
    """目录树中的分卷项"""

    id: int
    sort_index: int
    label: Optional[str] = None
    title: str
    summary: str = ""
    chapter_count: int = 0
    total_chars: int = 0
    chapters: List[TocChapterItem] = Field(default_factory=list)


class EditionTocResponse(BaseModel):
    """版本树形目录（分卷 + 未归卷章节）"""

    edition_id: int
    total_chapters: int
    volume_count: int
    volumes: List[TocVolumeItem] = Field(default_factory=list)
    ungrouped_chapters: List[TocChapterItem] = Field(default_factory=list)


class VolumeCreateRequest(BaseModel):
    """创建分卷请求（可选直接指定章节区间归卷）"""

    label: Optional[str] = Field(default=None, description="卷号标签，如 '第一卷'")
    title: str = Field(description="卷标题")
    summary: str = Field(default="", description="卷纲简介")
    sort_index: Optional[int] = Field(default=None, description="卷排序索引")
    start_sort_index: Optional[int] = Field(default=None, description="起始章节 sort_index (含)")
    end_sort_index: Optional[int] = Field(default=None, description="结束章节 sort_index (含)")


class VolumeAssignRequest(BaseModel):
    """批量将章节归入某分卷（支持节点 ID 列表或 sort_index 区间）"""

    node_ids: Optional[List[int]] = None
    start_sort_index: Optional[int] = None
    end_sort_index: Optional[int] = None


class AutoVolumeRequest(BaseModel):
    """自动识别/应用分卷请求"""

    dry_run: bool = Field(default=True, description="True 仅预览，False 实际落库")
    chapter_chunk_size: Optional[int] = Field(
        default=None,
        description="若无显式卷标，可选按固定章数切卷（如 100）",
    )


class AutoVolumePreviewItem(BaseModel):
    label: str
    title: str
    start_sort_index: int
    end_sort_index: int
    chapter_count: int


class AutoVolumeResponse(BaseModel):
    edition_id: int
    dry_run: bool
    strategy: str
    volumes: List[AutoVolumePreviewItem] = Field(default_factory=list)
    applied_volumes: int = 0
    assigned_chapters: int = 0


# ============================================================================
# Reading Progress, Sessions & Stats DTOs
# ============================================================================


class ReadingProgressUpsertRequest(BaseModel):
    """上报/更新阅读进度"""

    edition_id: int
    node_id: Optional[int] = None
    sort_index: int = 0
    char_offset: int = 0
    scroll_offset: int = 0
    page_index: int = 0
    mode: str = "scroll"
    client_device: str = "web"
    last_read_at: Optional[datetime] = None
    delta_seconds: int = Field(default=0, description="可选本次增量阅读时长（秒）")


class ReadingProgressResponse(BaseModel):
    """阅读进度完整响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    work_id: int
    edition_id: int
    node_id: Optional[int] = None
    sort_index: int = 0
    char_offset: int = 0
    scroll_offset: int = 0
    page_index: int = 0
    mode: str = "scroll"
    progress_pct: float = 0.0
    total_read_seconds: int = 0
    client_device: str = ""
    last_read_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ReadingProgressSyncItem(BaseModel):
    work_id: int
    edition_id: int
    node_id: Optional[int] = None
    sort_index: int = 0
    char_offset: int = 0
    scroll_offset: int = 0
    page_index: int = 0
    mode: str = "scroll"
    client_device: str = "android"
    last_read_at: Optional[datetime] = None
    delta_seconds: int = 0


class ReadingProgressSyncRequest(BaseModel):
    items: List[ReadingProgressSyncItem] = Field(default_factory=list)


class ReadingProgressSyncResponse(BaseModel):
    updated: int
    skipped_stale: int
    progress_list: List[ReadingProgressResponse] = Field(default_factory=list)


class ReadingSessionCreateRequest(BaseModel):
    work_id: int
    edition_id: int
    start_node_id: Optional[int] = None
    end_node_id: Optional[int] = None
    duration_sec: int = Field(ge=0)
    chars_read: int = Field(default=0, ge=0)
    source_client: str = "web"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class ReadingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_id: int
    edition_id: int
    start_node_id: Optional[int] = None
    end_node_id: Optional[int] = None
    duration_sec: int
    chars_read: int
    source_client: str
    started_at: datetime
    ended_at: datetime


class PillarStatItem(BaseModel):
    pillar: str
    work_count: int = 0
    reading_count: int = 0
    finished_count: int = 0
    read_seconds_7d: int = 0
    read_seconds_30d: int = 0


class ReadingOverviewResponse(BaseModel):
    total_works: int
    reading_count: int
    mainline_reading: List[WorkResponse] = Field(default_factory=list)
    stalled_mainline: List[WorkResponse] = Field(default_factory=list)
    pillar_stats: List[PillarStatItem] = Field(default_factory=list)
    total_read_seconds_7d: int = 0
    total_read_seconds_30d: int = 0
    active_topic_count: int = 0


# ============================================================================
# Content Topic & Rhythm Venture Linkage DTOs
# ============================================================================


class ContentTopicCreateRequest(BaseModel):
    slug: Optional[str] = None
    title: str
    description: str = ""
    pillar: str = "tech"
    status: str = "active"
    rhythm_venture_id: Optional[int] = None
    vault_prefix: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    meta_data: Dict[str, Any] = Field(default_factory=dict)


class ContentTopicUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    pillar: Optional[str] = None
    status: Optional[str] = None
    rhythm_venture_id: Optional[int] = None
    vault_prefix: Optional[str] = None
    keywords: Optional[List[str]] = None
    meta_data: Optional[Dict[str, Any]] = None


class ContentTopicWorkAttachRequest(BaseModel):
    work_id: int
    role: str = "core"  # core | reference | background | inspiration
    sort_index: int = 0
    note: str = ""


class ContentTopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: str = ""
    pillar: str = "tech"
    status: str = "active"
    rhythm_venture_id: Optional[int] = None
    vault_prefix: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    meta_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    work_count: int = 0
    avg_progress_pct: float = 0.0
    venture_title: Optional[str] = None


class ContentTopicWorkItem(BaseModel):
    id: int
    topic_id: int
    work_id: int
    role: str = "core"
    sort_index: int = 0
    note: str = ""
    work: WorkResponse


class ContentAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_id: Optional[int] = None
    topic_id: Optional[int] = None
    asset_kind: str = "attachment"
    storage_key: str
    original_name: str
    mime_type: str
    size_bytes: int
    sha256: str = ""
    meta_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    file_url: str = ""


class VaultNoteIndexItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    fname: str
    namespace: str = "read"
    title: str = ""
    summary: str = ""
    tags: List[str] = Field(default_factory=list)
    links: List[str] = Field(default_factory=list)
    work_id: Optional[int] = None
    topic_id: Optional[int] = None
    pillar: Optional[str] = None
    era: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    content_hash: str = ""
    source_vault: str = "local"
    synced_at: Optional[datetime] = None


class VaultNoteIndexSyncRequest(BaseModel):
    items: List[VaultNoteIndexItem] = Field(default_factory=list)
    source_vault: str = "local"


class VaultNoteIndexSyncResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    total_processed: int


class TopicRhythmTaskSummary(BaseModel):
    id: int
    title: str
    kind: str
    state: str
    est_minutes: int = 30
    urgency_ddl: Optional[datetime] = None
    ref: Dict[str, Any] = Field(default_factory=dict)


class ContentTopicDetailResponse(BaseModel):
    topic: ContentTopicResponse
    works: List[ContentTopicWorkItem] = Field(default_factory=list)
    assets: List[ContentAssetResponse] = Field(default_factory=list)
    vault_notes: List[VaultNoteIndexItem] = Field(default_factory=list)
    venture: Optional[TopicRhythmTaskSummary] = None
    rhythm_tasks: List[TopicRhythmTaskSummary] = Field(default_factory=list)


class TopicPushRhythmTaskRequest(BaseModel):
    title: str
    description: str = ""
    work_id: Optional[int] = None
    edition_id: Optional[int] = None
    node_id: Optional[int] = None
    est_minutes: int = 45
    importance: int = 3
    urgency_ddl: Optional[datetime] = None


class WorkClipsExportResponse(BaseModel):
    work_id: int
    work_title: str
    vault_slug: str
    clips_filename: str
    card_filename: str
    annotation_count: int
    clips_markdown: str
    card_markdown: str


class ArxivImportRequest(BaseModel):
    arxiv_id_or_url: str = Field(description="arXiv ID (如 2405.12345) 或完整 URL")
    pillar: str = "tech"
    reading_track: str = "project"
    topic_id: Optional[int] = None
    download_pdf: bool = True


class MultiFormatImportResponse(BaseModel):
    work: WorkResponse
    edition: EditionResponse
    volume_count: int = 0
    chapter_count: int = 0
    asset: Optional[ContentAssetResponse] = None
    parser_used: str = ""
    message: str = "导入成功"


# ============================================================================
# NoteItem DTOs
# ============================================================================


NOTE_CATEGORIES = [
    "character",
    "setting",
    "geography",
    "outline",
    "plot",
    "history",
    "person",
    "timeline",
    "relationship",
    "misc",
    "annotation",
]


class NoteItemBase(BaseModel):
    """笔记索引基础信息"""

    model_config = ConfigDict(from_attributes=True)

    category: str = Field(description="笔记分类")
    setting_file: str = Field(description="Markdown 文件相对 workspace 路径")
    work_id: Optional[int] = Field(default=None, description="关联作品 ID")
    edition_id: Optional[int] = Field(default=None, description="关联版本 ID")
    title: Optional[str] = Field(default=None, description="标题缓存")
    slug: Optional[str] = Field(default=None, description="URL/文件名友好标识")


class NoteItemCreateRequest(BaseModel):
    """创建笔记索引请求"""

    model_config = ConfigDict(from_attributes=True)

    category: str = Field(description="笔记分类")
    setting_file: Optional[str] = Field(
        default=None, description="Markdown 文件相对 workspace 路径"
    )
    work_id: Optional[int] = Field(default=None, description="关联作品 ID")
    edition_id: Optional[int] = Field(default=None, description="关联版本 ID")
    title: Optional[str] = Field(default=None, description="标题缓存")
    slug: Optional[str] = Field(default=None, description="URL/文件名友好标识")
    content: Optional[str] = Field(
        default=None, description="Markdown 原始内容，创建时直接写入文件"
    )
    node_id: Optional[int] = Field(default=None, description="锚点：章节节点 ID")
    start_offset: Optional[int] = Field(default=None, description="锚点：选中起始偏移")
    end_offset: Optional[int] = Field(default=None, description="锚点：选中结束偏移")
    selected_text: Optional[str] = Field(default=None, description="锚点：选中原文片段")
    color: Optional[str] = Field(default=None, description="锚点：高亮颜色标识")
    meta_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="扩展元数据"
    )


class NoteItemUpdateRequest(BaseModel):
    """更新笔记索引请求"""

    model_config = ConfigDict(from_attributes=True)

    category: Optional[str] = Field(default=None, description="笔记分类")
    setting_file: Optional[str] = Field(
        default=None, description="Markdown 文件相对 workspace 路径"
    )
    work_id: Optional[int] = Field(default=None, description="关联作品 ID")
    edition_id: Optional[int] = Field(default=None, description="关联版本 ID")
    title: Optional[str] = Field(default=None, description="标题缓存")
    slug: Optional[str] = Field(default=None, description="URL/文件名友好标识")
    meta_data: Optional[Dict[str, Any]] = Field(default=None, description="扩展元数据")
    content: Optional[str] = Field(
        default=None, description="Markdown 原始内容（提供时写入/覆盖对应文件）"
    )


class NoteItemResponse(NoteItemBase):
    """笔记索引响应"""

    id: int = Field(description="笔记 ID")
    meta_data: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class NoteItemListResponse(BaseModel):
    """笔记索引列表响应"""

    notes: List[NoteItemResponse]
    total: int


class NoteItemContentResponse(BaseModel):
    """笔记 Markdown 内容响应"""

    id: int = Field(description="笔记 ID")
    setting_file: str = Field(description="文件路径")
    content: str = Field(description="Markdown 原始内容")


class NoteLinkGraphResponse(BaseModel):
    """双向链接图谱响应"""

    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="节点列表")
    edges: List[Dict[str, Any]] = Field(default_factory=list, description="链接边列表")
