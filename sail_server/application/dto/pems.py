# -*- coding: utf-8 -*-
# @file pems.py
# @brief Personal Energy Management System DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
个人精力管理系统(PEMS) 数据传输对象
"""

from datetime import date as date_type
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class RhythmClass:
    """节律分类常量"""

    WORKDAY = "workday"
    RESTDAY = "restday"
    HOLIDAY = "holiday"
    SICK = "sick"
    TRAVEL = "travel"
    FOCUS = "focus"


class EnergyBudgetResponse(BaseModel):
    """精力预算响应"""

    date: date_type = Field(description="日期")
    day_id: int = Field(description="自然日ID")
    rhythm: str = Field(default="workday", description="节律分类")
    base_energy: int = Field(default=100, description="基础精力")
    health_multiplier: int = Field(default=100, description="健康修正系数(百分比)")
    energy_budget: int = Field(default=100, description="当日精力预算")
    energy_planned: int = Field(default=0, description="已安排任务消耗")
    energy_actual: int = Field(default=0, description="实际已消耗")
    warning_messages: List[str] = Field(default_factory=list, description="预算告警")


class HealthSignalSummary(BaseModel):
    """当日健康信号摘要"""

    sleep_hours: Optional[float] = Field(default=None, description="睡眠时长")
    sleep_quality: Optional[int] = Field(default=None, description="睡眠质量 1-5")
    energy_level: Optional[int] = Field(default=None, description="精力评分 1-5")
    mood: Optional[int] = Field(default=None, description="情绪评分 1-5")
    weight_value: Optional[float] = Field(default=None, description="体重 kg")
    exercise_count: int = Field(default=0, description="运动记录数")


class PemsMissionBrief(BaseModel):
    """PEMS 任务摘要"""

    id: int = Field(description="任务ID")
    name: str = Field(description="任务名称")
    project_id: Optional[int] = Field(default=None, description="项目ID")
    project_name: Optional[str] = Field(default=None, description="项目名称")
    state: int = Field(description="任务状态")
    energy_cost: int = Field(default=0, description="预计精力消耗")
    planned_minutes: int = Field(default=0, description="预计耗时(分钟)")
    health_constraint: str = Field(default="normal", description="健康约束")


class DayViewResponse(BaseModel):
    """某日 PEMS 完整视图"""

    date: date_type = Field(description="日期")
    day_id: int = Field(description="自然日ID")
    rhythm: str = Field(default="workday", description="节律分类")
    energy_budget: EnergyBudgetResponse = Field(description="精力预算")
    health_signals: HealthSignalSummary = Field(
        default_factory=HealthSignalSummary, description="健康信号摘要"
    )
    planned_missions: List[PemsMissionBrief] = Field(default_factory=list, description="已安排任务")
    completed_missions: List[PemsMissionBrief] = Field(default_factory=list, description="已完成任务")
    challenge_checkins: Dict[str, str] = Field(
        default_factory=dict, description="打卡状态"
    )
    insights: List["InsightResponse"] = Field(default_factory=list, description="当日洞察")
    note: Optional[str] = Field(default=None, description="备注")


class TimeSpanViewResponse(BaseModel):
    """周期视图响应"""

    id: int = Field(description="TimeSpan ID")
    class_: str = Field(description="TimeSpan 类型")
    name: str = Field(description="名称")
    start_date: date_type = Field(description="开始日期")
    end_date: date_type = Field(description="结束日期")
    theme: Optional[str] = Field(default=None, description="周期主题")
    energy_capacity: int = Field(default=0, description="总精力预算")
    energy_consumed: int = Field(default=0, description="已消耗精力")
    project_ids: List[int] = Field(default_factory=list, description="关联项目ID")
    health_goals: Dict[str, Any] = Field(default_factory=dict, description="健康目标")
    review_note: Optional[str] = Field(default=None, description="复盘笔记")
    focus_areas: List[str] = Field(default_factory=list, description="关注领域")
    day_count: int = Field(default=0, description="包含天数")


class ProjectTimelineResponse(BaseModel):
    """项目时间线响应"""

    project_id: int = Field(description="项目ID")
    project_name: str = Field(description="项目名称")
    timespan_id: Optional[int] = Field(default=None, description="归属周期ID")
    energy_budget: int = Field(default=0, description="项目精力预算")
    milestones: List[Dict[str, Any]] = Field(default_factory=list, description="里程碑")
    missions: List[PemsMissionBrief] = Field(default_factory=list, description="任务")
    timelogs: List[Dict[str, Any]] = Field(default_factory=list, description="时间投入")


class InsightSeverity:
    """洞察严重级别"""

    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


class InsightResponse(BaseModel):
    """洞察/建议响应"""

    type: str = Field(description="洞察类型")
    severity: str = Field(default=InsightSeverity.INFO, description="严重级别")
    title: str = Field(description="标题")
    message: str = Field(description="内容")


class PlanMissionRequest(BaseModel):
    """为某日安排任务请求"""

    mission_id: int = Field(description="要安排的任务ID")


class TimeSpanReviewRequest(BaseModel):
    """提交周期复盘请求"""

    review_note: str = Field(description="复盘内容")
    theme: Optional[str] = Field(default=None, description="周期主题")
    focus_areas: Optional[List[str]] = Field(default=None, description="关注领域")


class HealthQuickLogRequest(BaseModel):
    """健康快速录入请求"""

    sleep_hours: Optional[float] = Field(default=None, description="睡眠时长")
    sleep_quality: Optional[int] = Field(default=None, description="睡眠质量 1-5")
    energy_level: Optional[int] = Field(default=None, description="精力评分 1-5")
    mood: Optional[int] = Field(default=None, description="情绪评分 1-5")
    note: Optional[str] = Field(default=None, description="备注")


class StatusResponse(BaseModel):
    """通用状态响应"""

    status: str = Field(default="success", description="状态")
    message: str = Field(default="", description="消息")
