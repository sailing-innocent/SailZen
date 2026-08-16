# -*- coding: utf-8 -*-
# @file health.py
# @brief Health Pydantic DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
健康模块 Pydantic DTOs

原位置: sail_server/data/health.py
"""

from datetime import datetime, date as date_type
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_serializer


# ============================================================================
# Weight DTOs
# ============================================================================


class WeightBase(BaseModel):
    """体重记录基础信息"""

    model_config = ConfigDict(from_attributes=True)

    value: float = Field(description="体重值 (kg)")
    tag: str = Field(default="raw", description="记录标签")
    description: Optional[str] = Field(default="", description="记录描述")


class WeightCreateRequest(WeightBase):
    """创建体重记录请求"""

    htime: Optional[float] = Field(default=None, description="发生时间戳")


class WeightResponse(WeightBase):
    """体重记录响应"""

    id: int = Field(description="记录ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class WeightListResponse(BaseModel):
    """体重记录列表响应"""

    weights: List[WeightResponse]
    total: int


# ============================================================================
# BodySize DTOs
# ============================================================================


class BodySizeBase(BaseModel):
    """身体尺寸基础信息"""

    model_config = ConfigDict(from_attributes=True)

    waist: float = Field(description="腰围 (cm)")
    hip: float = Field(description="臀围 (cm)")
    chest: float = Field(description="胸围 (cm)")
    tag: str = Field(default="daily", description="记录标签")


class BodySizeCreateRequest(BodySizeBase):
    """创建身体尺寸记录请求"""

    htime: Optional[float] = Field(default=None, description="发生时间戳")


class BodySizeResponse(BodySizeBase):
    """身体尺寸记录响应"""

    id: int = Field(description="记录ID")
    htime: float = Field(description="发生时间戳")


class BodySizeListResponse(BaseModel):
    """身体尺寸记录列表响应"""

    body_sizes: List[BodySizeResponse]
    total: int


# ============================================================================
# Exercise DTOs
# ============================================================================


class ExerciseBase(BaseModel):
    """运动记录基础信息"""

    model_config = ConfigDict(from_attributes=True)

    description: str = Field(default="", description="运动描述")
    exercise_type: str = Field(default="", description="运动类型，如 running / walking / strength")
    duration_minutes: int = Field(default=0, ge=0, description="运动时长（分钟）")
    calories: int = Field(default=0, ge=0, description="消耗热量（千卡）")
    completed: bool = Field(default=True, description="是否完成")
    source: str = Field(default="health", description="来源：health / exercise_plan / rhythm")


class ExerciseCreateRequest(ExerciseBase):
    """创建运动记录请求"""

    htime: Optional[float] = Field(default=None, description="发生时间戳")


class ExerciseResponse(ExerciseBase):
    """运动记录响应"""

    id: int = Field(description="记录ID")
    htime: float = Field(description="发生时间戳")


class ExerciseListResponse(BaseModel):
    """运动记录列表响应"""

    exercises: List[ExerciseResponse]
    total: int


# ============================================================================
# WeightPlan DTOs
# ============================================================================


class WeightPlanCurveType(str, Enum):
    """体重计划目标曲线类型"""

    LINEAR = "linear"
    POLYNOMIAL = "polynomial"
    EXPONENTIAL = "exponential"


class WeightPlanBase(BaseModel):
    """体重计划基础信息"""

    model_config = ConfigDict(from_attributes=True)

    target_weight: str = Field(description="目标体重 (kg)")
    initial_weight: Optional[str] = Field(
        default=None, description="起始体重 (kg)，None 则自动取 start_time 后第一次记录"
    )
    curve_type: WeightPlanCurveType = Field(
        default=WeightPlanCurveType.LINEAR, description="目标曲线类型"
    )
    description: str = Field(default="", description="计划描述")


class WeightPlanCreateRequest(WeightPlanBase):
    """创建体重计划请求"""

    start_time: Optional[datetime] = Field(default=None, description="计划开始时间")
    target_time: Optional[datetime] = Field(default=None, description="计划目标时间")
    notify_enabled: bool = Field(default=False, description="是否启用 Rhythm 提醒")
    notify_time: Optional[str] = Field(
        default="08:30", pattern=r"^\d{2}:\d{2}$", description="提醒时间 HH:MM"
    )
    feedback_enabled: bool = Field(
        default=False, description="记录体重时是否同步 Rhythm 打卡"
    )


class WeightPlanUpdateRequest(WeightPlanBase):
    """更新体重计划请求"""

    start_time: Optional[datetime] = Field(default=None, description="计划开始时间")
    target_time: Optional[datetime] = Field(default=None, description="计划目标时间")
    notify_enabled: bool = Field(default=False, description="是否启用 Rhythm 提醒")
    notify_time: Optional[str] = Field(
        default="08:30", pattern=r"^\d{2}:\d{2}$", description="提醒时间 HH:MM"
    )
    feedback_enabled: bool = Field(
        default=False, description="记录体重时是否同步 Rhythm 打卡"
    )


class WeightPlanResponse(WeightPlanBase):
    """体重计划响应"""

    id: int = Field(description="计划ID")
    start_time: datetime = Field(description="计划开始时间")
    target_time: datetime = Field(description="计划目标时间")
    created_at: datetime = Field(description="创建时间")
    notify_enabled: bool = Field(description="是否启用 Rhythm 提醒")
    notify_time: Optional[str] = Field(description="提醒时间 HH:MM")
    feedback_enabled: bool = Field(description="记录体重时是否同步 Rhythm 打卡")
    rhythm_affair_id: Optional[int] = Field(
        default=None, description="关联 Rhythm 事务 ID"
    )

    @field_serializer("start_time", "target_time", "created_at")
    def serialize_datetime(self, value: datetime) -> float:
        return value.timestamp()


class WeightExpectedPoint(BaseModel):
    """按日期范围返回的预期体重单点"""

    htime: float = Field(description="当天 00:00:00 时间戳（秒）")
    expected_weight: float = Field(description="预期体重 (kg)")


class WeightExpectedRangeResponse(BaseModel):
    """按日期范围返回的预期体重响应"""

    plan: WeightPlanResponse = Field(description="当前活跃计划")
    points: List[WeightExpectedPoint] = Field(description="区间内每一天的预期体重")


class WeightPlanListResponse(BaseModel):
    """体重计划列表响应"""

    weight_plans: List[WeightPlanResponse]
    total: int


# ============================================================================
# Sleep DTOs
# ============================================================================


class SleepBase(BaseModel):
    """睡眠记录基础信息"""

    model_config = ConfigDict(from_attributes=True)

    hours: float = Field(description="睡眠时长(小时)")
    quality: int = Field(default=3, description="睡眠质量 1-5")
    description: Optional[str] = Field(default="", description="描述")


class SleepCreateRequest(SleepBase):
    """创建睡眠记录请求"""

    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class SleepResponse(SleepBase):
    """睡眠记录响应"""

    id: int = Field(description="记录ID")
    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class SleepListResponse(BaseModel):
    """睡眠记录列表响应"""

    sleeps: List[SleepResponse]
    total: int


# ============================================================================
# Energy Level DTOs
# ============================================================================


class EnergyLevelBase(BaseModel):
    """精力评分基础信息"""

    model_config = ConfigDict(from_attributes=True)

    score: int = Field(description="精力评分 1-5")
    description: Optional[str] = Field(default="", description="描述")


class EnergyLevelCreateRequest(EnergyLevelBase):
    """创建精力评分请求"""

    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class EnergyLevelResponse(EnergyLevelBase):
    """精力评分响应"""

    id: int = Field(description="记录ID")
    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class EnergyLevelListResponse(BaseModel):
    """精力评分列表响应"""

    energy_levels: List[EnergyLevelResponse]
    total: int


# ============================================================================
# Mood DTOs
# ============================================================================


class MoodBase(BaseModel):
    """情绪评分基础信息"""

    model_config = ConfigDict(from_attributes=True)

    score: int = Field(description="情绪评分 1-5")
    description: Optional[str] = Field(default="", description="描述")


class MoodCreateRequest(MoodBase):
    """创建情绪评分请求"""

    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class MoodResponse(MoodBase):
    """情绪评分响应"""

    id: int = Field(description="记录ID")
    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class MoodListResponse(BaseModel):
    """情绪评分列表响应"""

    moods: List[MoodResponse]
    total: int


# ============================================================================
# Medication DTOs
# ============================================================================


class MedicationBase(BaseModel):
    """用药/保健品记录基础信息"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="药品/保健品名")
    dosage: Optional[str] = Field(default="", description="剂量，如 500mg")
    frequency: str = Field(default="daily", description="daily / weekly / as_needed")
    schedule_times: List[str] = Field(default_factory=list, description="服用时间点，如 [\"08:00\", \"20:00\"]")
    planned_date: Optional[date_type] = Field(default=None, description="计划服用日期")
    taken: bool = Field(default=False, description="是否已服用")
    note: Optional[str] = Field(default="", description="备注")
    is_supplement: bool = Field(default=False, description="是否保健品")


class MedicationCreateRequest(MedicationBase):
    """创建用药记录请求"""

    htime: Optional[float] = Field(default=None, description="发生时间戳")
    taken_at: Optional[float] = Field(default=None, description="实际服用时间戳")


class MedicationUpdateRequest(BaseModel):
    """更新用药记录请求（仅允许更新服用状态与时间）"""

    taken: bool = Field(default=True, description="是否已服用")
    taken_at: Optional[float] = Field(default=None, description="实际服用时间戳")
    note: Optional[str] = Field(default=None, description="备注")


class MedicationResponse(MedicationBase):
    """用药记录响应"""

    id: int = Field(description="记录ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")
    taken_at: Optional[float] = Field(default=None, description="实际服用时间戳")


class MedicationListResponse(BaseModel):
    """用药记录列表响应"""

    medications: List[MedicationResponse]
    total: int


class MedicationTodayDto(BaseModel):
    """今日用药清单与完成率"""

    date: str = Field(description="日期 YYYY-MM-DD")
    medications: List[MedicationResponse] = Field(default_factory=list)
    total: int = 0
    taken: int = 0
    compliance: float = Field(default=0.0, description="完成率 0-1")


class MedicationStatsDto(BaseModel):
    """近 N 天用药依从性统计"""

    days: int = Field(description="统计天数")
    total: int = 0
    taken: int = 0
    compliance: float = 0.0


# ============================================================================
# Diet / Nutrition DTOs
# ============================================================================


class MealType(str, Enum):
    """餐次类型"""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class DietLogBase(BaseModel):
    """饮食记录基础信息"""

    model_config = ConfigDict(from_attributes=True)

    meal_type: MealType = Field(default=MealType.SNACK, description="餐次")
    description: Optional[str] = Field(default="", description="文字描述")
    photo_path: Optional[str] = Field(default=None, description="照片路径")
    calories: Optional[float] = Field(default=None, description="热量（千卡）")
    carbs: Optional[float] = Field(default=None, description="碳水化合物（克）")
    sugar: Optional[float] = Field(default=None, description="糖分（克）")
    protein: Optional[float] = Field(default=None, description="蛋白质（克）")
    fat: Optional[float] = Field(default=None, description="脂肪（克）")
    fiber: Optional[float] = Field(default=None, description="纤维（克）")
    sodium: Optional[float] = Field(default=None, description="钠（mg）")
    micronutrients: Optional[dict] = Field(default_factory=dict, description="微量元素")


class DietCreateRequest(DietLogBase):
    """创建饮食记录请求"""

    htime: Optional[float] = Field(default=None, description="发生时间戳")


class DietResponse(DietLogBase):
    """饮食记录响应"""

    id: int = Field(description="记录ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class DietListResponse(BaseModel):
    """饮食记录列表响应"""

    diets: List[DietResponse]
    total: int


class NutrientActualVsGoal(BaseModel):
    """单一营养素实际 vs 目标"""

    actual: Optional[float] = None
    goal: Optional[float] = None
    unit: str = "g"


class DietSummaryDto(BaseModel):
    """当日饮食汇总 + 目标对比"""

    date: str = Field(description="日期 YYYY-MM-DD")
    calories: NutrientActualVsGoal = Field(default_factory=NutrientActualVsGoal)
    carbs: NutrientActualVsGoal = Field(default_factory=NutrientActualVsGoal)
    sugar: NutrientActualVsGoal = Field(default_factory=NutrientActualVsGoal)
    protein: NutrientActualVsGoal = Field(default_factory=NutrientActualVsGoal)
    fat: NutrientActualVsGoal = Field(default_factory=NutrientActualVsGoal)
    fiber: NutrientActualVsGoal = Field(default_factory=NutrientActualVsGoal)
    sodium: NutrientActualVsGoal = Field(default_factory=NutrientActualVsGoal)
    micronutrients: dict = Field(default_factory=dict)


class NutritionGoalBase(BaseModel):
    """营养目标基础信息"""

    model_config = ConfigDict(from_attributes=True)

    date: date_type = Field(description="目标日期")
    calories: Optional[float] = Field(default=None, description="热量目标（千卡）")
    carbs: Optional[float] = Field(default=None, description="碳水目标（克）")
    sugar: Optional[float] = Field(default=None, description="糖分目标（克）")
    protein: Optional[float] = Field(default=None, description="蛋白质目标（克）")
    fat: Optional[float] = Field(default=None, description="脂肪目标（克）")
    fiber: Optional[float] = Field(default=None, description="纤维目标（克）")
    sodium: Optional[float] = Field(default=None, description="钠目标（mg）")
    micronutrients: Optional[dict] = Field(default_factory=dict, description="微量元素目标")


class NutritionGoalCreateRequest(NutritionGoalBase):
    """创建/更新营养目标请求"""

    pass


class NutritionGoalResponse(NutritionGoalBase):
    """营养目标响应"""

    id: int = Field(description="目标ID")


# ============================================================================
# Sleep Schedule DTOs
# ============================================================================


class SleepScheduleGoalBase(BaseModel):
    """作息目标基础信息"""

    model_config = ConfigDict(from_attributes=True)

    date: date_type = Field(description="目标日期")
    bed_time: str = Field(default="23:00", pattern=r"^\d{2}:\d{2}$", description="就寝时间 HH:MM")
    wake_time: str = Field(default="07:00", pattern=r"^\d{2}:\d{2}$", description="起床时间 HH:MM")
    target_hours: float = Field(default=8.0, gt=0, description="目标睡眠时长（小时）")


class SleepScheduleGoalCreateRequest(SleepScheduleGoalBase):
    """创建作息目标请求"""

    pass


class SleepScheduleGoalResponse(SleepScheduleGoalBase):
    """作息目标响应"""

    id: int = Field(description="目标ID")


# ============================================================================
# Health Dashboard DTO
# ============================================================================


class DashboardWeightItem(BaseModel):
    """体重概览项"""

    latest: Optional[float] = None
    plan_target: Optional[float] = None
    status: str = "normal"  # normal | above | below


class DashboardSleepItem(BaseModel):
    """睡眠概览项"""

    last_night_hours: Optional[float] = None
    goal: Optional[float] = None
    status: str = "normal"


class DashboardExerciseItem(BaseModel):
    """运动概览项"""

    today_minutes: int = 0
    goal_minutes: int = 0
    completed: bool = False


class DashboardMedicationItem(BaseModel):
    """用药概览项"""

    total: int = 0
    taken: int = 0
    compliance: float = 0.0


class DashboardDietItem(BaseModel):
    """饮食概览项"""

    calories_actual: Optional[float] = None
    calories_goal: Optional[float] = None
    sugar_actual: Optional[float] = None
    sugar_goal: Optional[float] = None


class DashboardMoodItem(BaseModel):
    """心情概览项"""

    score: Optional[int] = None


class HealthDashboardResponse(BaseModel):
    """健康首页聚合响应"""

    date: str = Field(description="日期 YYYY-MM-DD")
    weight: DashboardWeightItem = Field(default_factory=DashboardWeightItem)
    sleep: DashboardSleepItem = Field(default_factory=DashboardSleepItem)
    exercise: DashboardExerciseItem = Field(default_factory=DashboardExerciseItem)
    medication: DashboardMedicationItem = Field(default_factory=DashboardMedicationItem)
    diet: DashboardDietItem = Field(default_factory=DashboardDietItem)
    mood: DashboardMoodItem = Field(default_factory=DashboardMoodItem)
    warnings: List[str] = Field(default_factory=list)


# ============================================================================
# HealthSignal DTOs
# ============================================================================


class HealthSignalBase(BaseModel):
    """统一健康信号基础信息"""

    model_config = ConfigDict(from_attributes=True)

    signal_type: str = Field(description="信号类型")
    ref_id: int = Field(description="关联记录ID")
    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")
    value_json: Optional[dict] = Field(default_factory=dict, description="原始值")
    score: Optional[int] = Field(default=None, description="标准化分数")


class HealthSignalCreateRequest(HealthSignalBase):
    """创建健康信号请求"""

    pass


class HealthSignalResponse(HealthSignalBase):
    """健康信号响应"""

    id: int = Field(description="信号ID")


class HealthSignalListResponse(BaseModel):
    """健康信号列表响应"""

    health_signals: List[HealthSignalResponse]
    total: int
