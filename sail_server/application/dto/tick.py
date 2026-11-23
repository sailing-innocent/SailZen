# -*- coding: utf-8 -*-
# @file tick.py
# @brief SailTick Ticket Pydantic DTOs
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 票据 DTOs。

时间字段语义与 reminder 模块对齐：服务端→客户端 naive datetime；
客户端→服务端 ISO-8601 字符串归一化为 naive 本地时间。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_naive_local(v: Any) -> Optional[datetime]:
    """把带 tz 的 ISO 字符串 / datetime 归一化为 naive 本地时间。"""
    if v is None:
        return None
    if isinstance(v, str):
        v = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.astimezone().replace(tzinfo=None)
    return v


class TicketCreateRequest(BaseModel):
    """创建票据（SailTick agent / 手工测试）。"""

    model_config = ConfigDict(from_attributes=True)
    tick_id: str = Field(default="", description="创建它的 tick 实例 id")
    type: str = Field(default="question", description="question|task|approval|info")
    topic: str = Field(default="", description="话题标识，用于防重复询问与冷却控制")
    title: str = Field(description="标题")
    body: str = Field(default="", description="正文（Markdown）")
    meta: Dict[str, Any] = Field(default_factory=dict, description="扩展元信息（如 quick_replies）")
    priority: str = Field(default="normal", description="low|normal|high|urgent")
    channel: str = Field(default="web", description="web|mobile|plugin")
    expected_reply_by: Optional[datetime] = Field(default=None, description="期待回复时间")
    fallback_assumption: str = Field(default="", description="超期后 AI 采用的假设")
    push: str = Field(default="auto", description="auto|force|none（创建时是否推送手机）")
    _naive = field_validator("expected_reply_by", mode="before")(_to_naive_local)


class TicketReplyRequest(BaseModel):
    """用户回复票据。"""

    reply: str = Field(description="回复内容")


class TicketResolveRequest(BaseModel):
    """关闭票据。"""

    resolution: str = Field(default="", description="关闭说明")


class TicketSnoozeRequest(BaseModel):
    """暂缓票据。"""

    hours: int = Field(default=24, description="暂缓小时数")


class TicketResponse(BaseModel):
    """票据响应。"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    tick_id: str
    type: str
    topic: str = ""
    title: str
    body: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    status: str
    expected_reply_by: Optional[datetime]
    replied_at: Optional[datetime]
    reply: Optional[str]
    resolved_at: Optional[datetime]
    resolution: Optional[str]
    fallback_assumption: str
    priority: str
    channel: str
    created_at: datetime
    updated_at: datetime


class TicketListResponse(BaseModel):
    items: List[TicketResponse]
    total: int


# ── 用户主动消息 / 静默餐饮上报 DTOs ────────────────────────────────────────


class TickMessageCreateRequest(BaseModel):
    """用户主动发送餐饮/日常状态消息（AI 无需立即回复，静默收集并于睡前日报整合）。"""

    model_config = ConfigDict(from_attributes=True)
    direction: str = Field(default="user_to_agent", description="user_to_agent | agent_to_user")
    category: str = Field(default="diet", description="diet | weight | daily_info | mood | exercise | general")
    content: str = Field(description="自然语言消息正文")
    meta: Dict[str, Any] = Field(default_factory=dict, description="可选结构化元信息（如 meal_type / calories）")
    source_channel: str = Field(default="android", description="android | web | sailtick")
    auto_log_diet: bool = Field(
        default=True,
        description="当 category=diet 时是否同步落一条轻量 DietLog，便于健康页即时展示",
    )


class TickMessageResponse(BaseModel):
    """异步消息响应。"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    direction: str
    category: str
    content: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    source_channel: str
    status: str
    ingested_by_tick_id: Optional[str] = None
    created_at: datetime
    ingested_at: Optional[datetime] = None


class TickMessageIngestRequest(BaseModel):
    """SailTick 批量标记已吸收的用户消息。"""

    message_ids: List[int] = Field(default_factory=list, description="已吸收的消息 ID 列表")
    tick_id: str = Field(default="", description="执行吸收的 tick_id")


# ── 每日睡前体重与健康日报 DTOs ─────────────────────────────────────────────


class DailyReportUpsertRequest(BaseModel):
    """SailTick 创建/更新每日睡前体重与健康日报。"""

    model_config = ConfigDict(from_attributes=True)
    report_date: str = Field(description="报告日期 YYYY-MM-DD")
    tick_id: str = Field(default="", description="生成报告的 tick_id")
    title: str = Field(description="报告标题")
    summary: str = Field(default="", description="精炼摘要（推送正文与健康页首屏卡片）")
    body_markdown: str = Field(default="", description="完整 Markdown 日报")
    weight_snapshot: Dict[str, Any] = Field(default_factory=dict, description="体重快照与趋势")
    diet_summary: Dict[str, Any] = Field(default_factory=dict, description="当日餐饮整合摘要")
    plan_update: Dict[str, Any] = Field(default_factory=dict, description="AI 动态计划状态与调整说明")
    tomorrow_focus: List[str] = Field(default_factory=list, description="明日 1-3 条轻量建议")
    push: bool = Field(default=True, description="是否推送睡前日报通知到 Android")


class DailyReportResponse(BaseModel):
    """每日睡前健康日报响应。"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    report_date: str
    tick_id: str
    title: str
    summary: str
    body_markdown: str
    weight_snapshot: Dict[str, Any] = Field(default_factory=dict)
    diet_summary: Dict[str, Any] = Field(default_factory=dict)
    plan_update: Dict[str, Any] = Field(default_factory=dict)
    tomorrow_focus: List[str] = Field(default_factory=list)
    pushed: bool = False
    created_at: datetime
    updated_at: datetime


class IntakeEntryDto(BaseModel):
    """单条可编辑的识图结构化候选记录。"""

    selected: bool = Field(default=True, description="是否勾选落库")
    kind: str = Field(
        default="daily_info",
        description="diet | canteen_menu | sleep | exercise | weight | mood | daily_info",
    )
    title: str = Field(default="", description="条目展示标题")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="识别置信度 0-1")
    data: Dict[str, Any] = Field(default_factory=dict, description="对应领域结构化字段")


class CommittedRefDto(BaseModel):
    """落库后生成的关联记录引用。"""

    kind: str
    id: int
    label: str = ""


class ImageIntakeDraftResponse(BaseModel):
    """图片识图草稿响应（供前端弹出确认卡片微调后落库）。"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str = "pending_confirm"
    source_channel: str = "android"
    ticket_id: Optional[int] = None
    media_key: str
    media_url: str = ""
    media_mime: str = "image/jpeg"
    media_size: int = 0
    original_filename: str = ""
    user_note: str = ""
    scene: str = "general"
    summary: str = ""
    coach_advice: str = ""
    ocr_text: str = ""
    entries: List[IntakeEntryDto] = Field(default_factory=list)
    committed_refs: List[CommittedRefDto] = Field(default_factory=list)
    model_used: str = "deepseek-flash"
    usage: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    committed_at: Optional[datetime] = None


class ImageIntakeCommitRequest(BaseModel):
    """人工确认微调后提交落库的请求。"""

    entries: List[IntakeEntryDto] = Field(default_factory=list, description="确认后的条目列表")
    summary: Optional[str] = Field(default=None, description="可选覆盖识别摘要")
    user_note: Optional[str] = Field(default=None, description="可选补充用户备注")
    ticket_id: Optional[int] = Field(default=None, description="若关联票据则同时回复该票据")
    reply_text: Optional[str] = Field(default=None, description="自定义票据回复文案（留空则自动生成）")


class ImageIntakeCommitResponse(BaseModel):
    """确认落库响应。"""

    draft: ImageIntakeDraftResponse
    committed_refs: List[CommittedRefDto] = Field(default_factory=list)
    message_id: Optional[int] = None
    replied_ticket_id: Optional[int] = None


class HealthCoachSummaryResponse(BaseModel):
    """健康页 AI 教练聚合视图（供 Web /health 与 Android HealthHome 一次拉取）。"""

    active_plan: Optional[Dict[str, Any]] = None
    plan_progress: Optional[Dict[str, Any]] = None
    latest_report: Optional[DailyReportResponse] = None
    pending_tickets: List[TicketResponse] = Field(default_factory=list)
    pending_ticket_count: int = 0
    today_messages: List[TickMessageResponse] = Field(default_factory=list)
    pending_intake_drafts: List[ImageIntakeDraftResponse] = Field(default_factory=list)


class QuickChatRequest(BaseModel):
    """白天快速反应对话请求（转发至同机 SailTick daemon /chat/quick）。"""

    text: str = Field(description="用户即时消息，如早下班安排/聚餐调计划/设提醒")
    channel: str = Field(default="api", description="qq | android | cli | api")
    user_id: str = Field(default="owner", description="用户标识")
    session_id: Optional[str] = Field(default=None, description="可选会话 ID")
    target_type: str = Field(default="private", description="private | group")
    target_id: Optional[str] = Field(default=None, description="可选回复目标 ID")
