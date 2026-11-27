# -*- coding: utf-8 -*-
# @file workbench.py
# @brief SailZen Workbench Pydantic DTOs (VS Code 工作与创作工作台聚合契约)
# @author sailing-innocent
# @date 2026-11-27
# @version 1.0
# ---------------------------------

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from sail_server.application.dto.rhythm import (
    AffairResponse,
    DayTimelineResponse,
    VentureProgressResponse,
)
from sail_server.application.dto.text import (
    ContentTopicResponse,
    DocumentNodeResponse,
)
from sail_server.application.dto.tick import TicketResponse


class ProjectArchetype(str, Enum):
    """工作与创作项目类型"""

    NOVEL = "novel"
    GAME = "game"
    RESEARCH = "research"
    ENGINEERING = "engineering"
    GENERAL = "general"


class WorkbenchProjectMeta(BaseModel):
    """云端项目语义元数据（跨机器唯一，严禁包含本机绝对路径或盘符）。"""

    slug: str = Field(default="", max_length=100, description="跨机器唯一语义标识，如 hat-factory")
    archetype: ProjectArchetype = Field(default=ProjectArchetype.GENERAL, description="项目类型")
    vault_namespace: str = Field(default="", max_length=160, description="关联 Vault 命名空间前缀，如 project.hat-factory")
    repo_hints: List[str] = Field(default_factory=list, description="语义仓库名或 remote 提示（无盘符）")
    topic_id: Optional[int] = Field(default=None, description="关联 Content 2.0 专题 ID")
    original_work_id: Optional[int] = Field(default=None, description="关联原创作品 Work ID（长篇小说/书籍）")

    @field_validator("slug")
    @classmethod
    def _clean_slug(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "-")

    @field_validator("repo_hints")
    @classmethod
    def _validate_repo_hints(cls, hints: List[str]) -> List[str]:
        cleaned: List[str] = []
        for h in hints:
            item = h.strip()
            if not item:
                continue
            # 防止把本机绝对路径写入云端语义层
            if (len(item) >= 2 and item[1] == ":") or item.startswith("/") or "\\" in item:
                raise ValueError(f"repo_hints must be semantic identifiers, not local paths: {item}")
            if item not in cleaned:
                cleaned.append(item)
        return cleaned


class WorkbenchProjectMetaUpdateRequest(BaseModel):
    """更新 Venture 语义元数据请求"""

    slug: Optional[str] = Field(default=None, max_length=100)
    archetype: Optional[ProjectArchetype] = None
    vault_namespace: Optional[str] = Field(default=None, max_length=160)
    repo_hints: Optional[List[str]] = None
    topic_id: Optional[int] = None
    original_work_id: Optional[int] = None


class WorkbenchProjectItem(BaseModel):
    """工作台项目视图项（Venture 倒排 + 语义绑定）"""

    progress: VentureProgressResponse
    workbench: WorkbenchProjectMeta


class WorkbenchBootstrapResponse(BaseModel):
    """工作台启动单次聚合响应（1 RTT 点亮 4 面板）"""

    date: date_type
    timeline: DayTimelineResponse
    projects: List[WorkbenchProjectItem] = Field(default_factory=list)
    focus_affairs: List[AffairResponse] = Field(default_factory=list)
    overdue_affairs: List[AffairResponse] = Field(default_factory=list)
    topics: List[ContentTopicResponse] = Field(default_factory=list)
    pending_tickets: List[TicketResponse] = Field(default_factory=list)
    degraded: List[str] = Field(default_factory=list)


class WorkbenchContextPackResponse(BaseModel):
    """供本地 IDE Coding/Writing Agent 消费的结构化项目上下文包"""

    venture_id: int
    slug: str
    title: str
    archetype: ProjectArchetype
    markdown: str
    generated_at: datetime


class ChapterSyncRequest(BaseModel):
    """原创作品单章幂等同步请求"""

    node_id: Optional[int] = Field(default=None, description="已知 DocumentNode ID（可选）")
    source_slug: Optional[str] = Field(default=None, max_length=160, description="本地文件/章节稳定标识（幂等匹配键）")
    label: str = Field(default="", max_length=120, description="章节标签，如 第一章")
    title: str = Field(min_length=1, max_length=255, description="章节标题")
    content: str = Field(default="", description="章节正文 Markdown/纯文本")
    parent_id: Optional[int] = Field(default=None, description="所属分卷 volume 节点 ID（可选）")
    sort_index: Optional[int] = Field(default=None, description="排序序号（新建默认追加至末尾）")
    meta_data: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")


class ChapterSyncResponse(BaseModel):
    """原创作品单章同步响应"""

    action: str = Field(description="created | updated")
    edition_id: int
    node: DocumentNodeResponse
    edition_char_count: int
    edition_word_count: int
