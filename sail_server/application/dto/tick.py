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


class HealthCoachSummaryResponse(BaseModel):
    """健康页 AI 教练聚合视图（供 Web /health 与 Android HealthHome 一次拉取）。"""

    active_plan: Optional[Dict[str, Any]] = None
    plan_progress: Optional[Dict[str, Any]] = None
    latest_report: Optional[DailyReportResponse] = None
    pending_tickets: List[TicketResponse] = Field(default_factory=list)
    pending_ticket_count: int = 0
    today_messages: List[TickMessageResponse] = Field(default_factory=list)
