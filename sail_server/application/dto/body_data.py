# -*- coding: utf-8 -*-
# @file body_data.py
# @brief Body Data (身体数据) Pydantic DTOs and metric registry
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""
身体数据模块 DTOs 与指标注册表。

通用身体数据管理：每行一条记录，``data`` 为 JSON dict，只存放本次实际测量/记录的指标。

核心语义约定：
    - ``data`` JSON 中**不存在**某个 key = 本次未测量（与测量值为 null/0 严格区分）；
    - 图表端缺测点断线、不补零、不插值；
    - 自定义指标 key 必须带 ``x_`` 前缀（如 ``x_uric_acid``），其余 key 必须命中内置注册表。

三端（后端 / site 前端 / Android）共享同一份内置指标清单，修改时需同步：
    - ``sail_server/application/dto/body_data.py``（本文件，权威定义）
    - ``site/src/lib/data/body_data.ts``（前端镜像，首屏 fallback）
    - ``android/.../core/network/dto/BodyDataDtos.kt``（Android 镜像）
"""

import math
import re
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================================
# Naming helpers（与 dto/health.py 保持一致，兼容 Android camelCase）
# ============================================================================


def _to_lower_camel_case(snake_str: str) -> str:
    """将 snake_case 转换为 lowerCamelCase，用于兼容 Android 客户端字段命名。"""
    components = snake_str.split("_")
    if len(components) == 1:
        return components[0]
    return components[0] + "".join(part.title() for part in components[1:])


# ============================================================================
# Metric Registry（指标注册表）
# ============================================================================


class BodyMetricCategory(str, Enum):
    """指标分类：body 身体测量 / intake 饮食补给 / fitness 预留（本期不内置）。"""

    BODY = "body"
    INTAKE = "intake"
    FITNESS = "fitness"


class BodyMetricDefinition(BaseModel):
    """单个指标的定义（注册表条目）。"""

    model_config = ConfigDict(
        alias_generator=_to_lower_camel_case,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    key: str = Field(description="指标 key，唯一标识")
    label_zh: str = Field(description="中文标签")
    label_en: str = Field(description="英文标签")
    unit: str = Field(description="单位，如 kg / cm / % / g / ml / mg")
    category: BodyMetricCategory = Field(description="指标分类")
    precision: int = Field(default=1, description="展示用小数位数")
    min: Optional[float] = Field(default=None, description="合法下限（含），None 不校验")
    max: Optional[float] = Field(default=None, description="合法上限（含），None 不校验")
    higher_is_better: bool = Field(default=True, description="该指标偏高是否通常更好（仅信息展示）")
    builtin: bool = Field(default=True, description="是否内置指标；自定义指标为 False")


BUILTIN_METRICS: List[BodyMetricDefinition] = [
    BodyMetricDefinition(
        key="weight", label_zh="体重", label_en="Weight", unit="kg",
        category=BodyMetricCategory.BODY, precision=1, min=20.0, max=300.0,
        higher_is_better=False,
    ),
    BodyMetricDefinition(
        key="height", label_zh="身高", label_en="Height", unit="cm",
        category=BodyMetricCategory.BODY, precision=1, min=100.0, max=250.0,
    ),
    BodyMetricDefinition(
        key="chest", label_zh="胸围", label_en="Chest", unit="cm",
        category=BodyMetricCategory.BODY, precision=1, min=40.0, max=200.0,
    ),
    BodyMetricDefinition(
        key="waist", label_zh="腰围", label_en="Waist", unit="cm",
        category=BodyMetricCategory.BODY, precision=1, min=40.0, max=200.0,
        higher_is_better=False,
    ),
    BodyMetricDefinition(
        key="hip", label_zh="臀围", label_en="Hip", unit="cm",
        category=BodyMetricCategory.BODY, precision=1, min=40.0, max=250.0,
        higher_is_better=False,
    ),
    BodyMetricDefinition(
        key="body_fat_pct", label_zh="体脂率", label_en="Body Fat", unit="%",
        category=BodyMetricCategory.BODY, precision=1, min=1.0, max=70.0,
        higher_is_better=False,
    ),
    BodyMetricDefinition(
        key="muscle_mass", label_zh="肌肉量", label_en="Muscle Mass", unit="kg",
        category=BodyMetricCategory.BODY, precision=1, min=5.0, max=150.0,
    ),
    BodyMetricDefinition(
        key="protein_powder", label_zh="蛋白粉", label_en="Protein Powder", unit="g",
        category=BodyMetricCategory.INTAKE, precision=0, min=0.0, max=300.0,
    ),
    BodyMetricDefinition(
        key="creatine", label_zh="肌酸", label_en="Creatine", unit="g",
        category=BodyMetricCategory.INTAKE, precision=1, min=0.0, max=50.0,
    ),
    BodyMetricDefinition(
        key="water", label_zh="饮水量", label_en="Water", unit="ml",
        category=BodyMetricCategory.INTAKE, precision=0, min=0.0, max=8000.0,
    ),
    BodyMetricDefinition(
        key="caffeine", label_zh="咖啡因", label_en="Caffeine", unit="mg",
        category=BodyMetricCategory.INTAKE, precision=0, min=0.0, max=1000.0,
        higher_is_better=False,
    ),
]

#: 内置指标 key -> 定义 的快速索引
BUILTIN_METRIC_MAP: Dict[str, BodyMetricDefinition] = {m.key: m for m in BUILTIN_METRICS}

#: 合法 key 的格式：小写字母开头，仅含小写字母/数字/下划线
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

#: 自定义指标前缀（逃生舱：其他可能的指标）
CUSTOM_KEY_PREFIX = "x_"


def validate_metric_key(key: str) -> bool:
    """校验指标 key 是否合法。

    合法 key = 命中内置注册表，或带 ``x_`` 前缀的自定义指标。
    """
    if not isinstance(key, str) or not KEY_PATTERN.match(key):
        return False
    return key in BUILTIN_METRIC_MAP or key.startswith(CUSTOM_KEY_PREFIX)


def allowed_metric_keys() -> List[str]:
    """返回全部合法的内置指标 key（供校验错误信息使用）。"""
    return sorted(BUILTIN_METRIC_MAP.keys())


# ============================================================================
# Body Data DTOs
# ============================================================================


class BodyDataCreateRequest(BaseModel):
    """创建身体数据记录请求。

    ``data`` 中只出现本次实际测量/记录的指标；未测量 key 一律不出现。
    """

    htime: Optional[float] = Field(default=None, description="发生时间戳（秒），None 为当前时间")
    data: Dict[str, float] = Field(description="本次实际测量/记录的指标集合")
    tag: str = Field(default="raw", description="记录标签")
    description: str = Field(default="", description="记录描述")

    @model_validator(mode="after")
    def _validate_data(self) -> "BodyDataCreateRequest":
        if not self.data:
            raise ValueError(
                "data must contain at least one metric key; "
                f"allowed builtin keys: {allowed_metric_keys()}, "
                f"or custom keys prefixed with '{CUSTOM_KEY_PREFIX}'"
            )
        for key, value in self.data.items():
            if not validate_metric_key(key):
                raise ValueError(
                    f"unknown metric key '{key}'; allowed builtin keys: "
                    f"{allowed_metric_keys()}, or custom keys prefixed with '{CUSTOM_KEY_PREFIX}'"
                )
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"metric '{key}' value must be a finite number, got {value!r}")
            if not math.isfinite(float(value)):
                raise ValueError(f"metric '{key}' value must be a finite number, got {value!r}")
            definition = BUILTIN_METRIC_MAP.get(key)
            if definition is not None:
                if definition.min is not None and value < definition.min:
                    raise ValueError(
                        f"metric '{key}' value {value} below minimum {definition.min}"
                    )
                if definition.max is not None and value > definition.max:
                    raise ValueError(
                        f"metric '{key}' value {value} above maximum {definition.max}"
                    )
        return self


class BodyDataUpdateRequest(BaseModel):
    """更新身体数据记录请求。所有字段可选；``data`` 整体替换。"""

    htime: Optional[float] = Field(default=None, description="发生时间戳（秒）")
    data: Optional[Dict[str, float]] = Field(default=None, description="本次实际测量/记录的指标集合")
    tag: Optional[str] = Field(default=None, description="记录标签")
    description: Optional[str] = Field(default=None, description="记录描述")

    @model_validator(mode="after")
    def _validate_data(self) -> "BodyDataUpdateRequest":
        if self.data is None:
            return self
        if not self.data:
            raise ValueError(
                "data must contain at least one metric key; "
                f"allowed builtin keys: {allowed_metric_keys()}, "
                f"or custom keys prefixed with '{CUSTOM_KEY_PREFIX}'"
            )
        for key, value in self.data.items():
            if not validate_metric_key(key):
                raise ValueError(
                    f"unknown metric key '{key}'; allowed builtin keys: "
                    f"{allowed_metric_keys()}, or custom keys prefixed with '{CUSTOM_KEY_PREFIX}'"
                )
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"metric '{key}' value must be a finite number, got {value!r}")
            if not math.isfinite(float(value)):
                raise ValueError(f"metric '{key}' value must be a finite number, got {value!r}")
            definition = BUILTIN_METRIC_MAP.get(key)
            if definition is not None:
                if definition.min is not None and value < definition.min:
                    raise ValueError(
                        f"metric '{key}' value {value} below minimum {definition.min}"
                    )
                if definition.max is not None and value > definition.max:
                    raise ValueError(
                        f"metric '{key}' value {value} above maximum {definition.max}"
                    )
        return self


class BodyDataResponse(BaseModel):
    """身体数据记录响应（camelCase 别名兼容 Android）。"""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=_to_lower_camel_case,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: int = Field(description="记录ID")
    htime: float = Field(description="发生时间戳（秒）")
    data: Dict[str, float] = Field(description="本次实际测量/记录的指标集合")
    tag: str = Field(default="raw", description="记录标签")
    description: str = Field(default="", description="记录描述")
    source: str = Field(default="manual", description="记录来源")
    weight_id: Optional[int] = Field(default=None, description="dual-write 关联的 weights 表记录 ID")


class BodyDataSeriesPoint(BaseModel):
    """单指标时序点。"""

    id: int = Field(description="所属 body_data 记录 ID")
    htime: float = Field(description="发生时间戳（秒）")
    value: float = Field(description="该指标本次测量值")


class BodyDataSeriesResponse(BaseModel):
    """单指标时序响应。"""

    metric: str = Field(description="指标 key")
    unit: str = Field(description="指标单位")
    points: List[BodyDataSeriesPoint] = Field(default_factory=list, description="时序点（按时间升序）")
