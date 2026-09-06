/**
 * @file body_data.ts
 * @brief Body Data (身体数据) shared types + builtin metric registry mirror
 * @author sailing-innocent
 * @date 2026-09-06
 *
 * 后端权威定义: sail_server/application/dto/body_data.py
 * 本文件为前端镜像（首屏 fallback + 类型约束），修改指标时需三端同步
 * （后端 DTO / 本文件 / android core/network/dto/BodyDataDtos.kt）。
 *
 * 核心语义：data JSON 中不存在某 key = 本次未测量（与 null/0 严格区分）。
 */

export type BodyMetricCategory = 'body' | 'intake' | 'fitness'

/** 指标定义（与后端 BodyMetricDefinition 对齐，lowerCamelCase） */
export interface BodyMetricDef {
  key: string
  labelZh: string
  labelEn: string
  unit: string
  category: BodyMetricCategory
  precision: number
  min?: number
  max?: number
  higherIsBetter: boolean
  builtin: boolean
}

/** 身体数据记录 */
export interface BodyDataRecord {
  id: number
  htime: number
  /** 本次实际测量/记录的指标集合；未测量 key 一律不出现 */
  data: Record<string, number>
  tag: string
  description: string
  source: string
  weightId?: number | null
}

/** 创建身体数据记录参数 */
export interface BodyDataCreateProps {
  htime?: number
  data: Record<string, number>
  tag?: string
  description?: string
}

/** 单指标时序点 */
export interface BodyDataSeriesPoint {
  id: number
  htime: number
  value: number
}

/** 单指标时序响应 */
export interface BodyDataSeriesResponse {
  metric: string
  unit: string
  points: BodyDataSeriesPoint[]
}

/** 更新身体数据记录参数（仅传需要修改的字段；data 传则表示整体替换） */
export interface BodyDataUpdateProps {
  htime?: number
  data?: Record<string, number>
  tag?: string
  description?: string
}

/** 指标定义列表响应（后端 /metrics 动态下发：内置 + 扫描发现的 x_ 自定义指标） */
export type BodyMetricSchemaResponse = BodyMetricDef[]

/** 趋势预测点：实际测量点 + 未来 30 天预测点 */
export interface BodyMetricPredictedPoint {
  htime: number
  value: number
  is_actual: boolean
}

/** 单指标趋势分析响应（后端 /analysis） */
export interface BodyMetricAnalysisResult {
  metric: string
  unit: string
  model_type: string
  slope: number
  intercept: number
  r_squared: number
  current_value: number
  current_trend: string
  predicted_points: BodyMetricPredictedPoint[]
}

/** 内置指标注册表（与后端 BUILTIN_METRICS 保持一致） */
export const BUILTIN_METRICS: BodyMetricDef[] = [
  { key: 'weight', labelZh: '体重', labelEn: 'Weight', unit: 'kg', category: 'body', precision: 1, min: 20, max: 300, higherIsBetter: false, builtin: true },
  { key: 'height', labelZh: '身高', labelEn: 'Height', unit: 'cm', category: 'body', precision: 1, min: 100, max: 250, higherIsBetter: true, builtin: true },
  { key: 'chest', labelZh: '胸围', labelEn: 'Chest', unit: 'cm', category: 'body', precision: 1, min: 40, max: 200, higherIsBetter: true, builtin: true },
  { key: 'waist', labelZh: '腰围', labelEn: 'Waist', unit: 'cm', category: 'body', precision: 1, min: 40, max: 200, higherIsBetter: false, builtin: true },
  { key: 'hip', labelZh: '臀围', labelEn: 'Hip', unit: 'cm', category: 'body', precision: 1, min: 40, max: 250, higherIsBetter: false, builtin: true },
  { key: 'body_fat_pct', labelZh: '体脂率', labelEn: 'Body Fat', unit: '%', category: 'body', precision: 1, min: 1, max: 70, higherIsBetter: false, builtin: true },
  { key: 'muscle_mass', labelZh: '肌肉量', labelEn: 'Muscle Mass', unit: 'kg', category: 'body', precision: 1, min: 5, max: 150, higherIsBetter: true, builtin: true },
  { key: 'protein_powder', labelZh: '蛋白粉', labelEn: 'Protein Powder', unit: 'g', category: 'intake', precision: 0, min: 0, max: 300, higherIsBetter: true, builtin: true },
  { key: 'creatine', labelZh: '肌酸', labelEn: 'Creatine', unit: 'g', category: 'intake', precision: 1, min: 0, max: 50, higherIsBetter: true, builtin: true },
  { key: 'water', labelZh: '饮水量', labelEn: 'Water', unit: 'ml', category: 'intake', precision: 0, min: 0, max: 8000, higherIsBetter: true, builtin: true },
  { key: 'caffeine', labelZh: '咖啡因', labelEn: 'Caffeine', unit: 'mg', category: 'intake', precision: 0, min: 0, max: 1000, higherIsBetter: false, builtin: true },
]

const METRIC_MAP = new Map<string, BodyMetricDef>(BUILTIN_METRICS.map((m) => [m.key, m]))

/** 按 key 查指标定义（含未知 key 兜底） */
export const metricDef = (key: string): BodyMetricDef | undefined => METRIC_MAP.get(key)

/** 指标中文标签（自定义 x_ 指标回退为 key 本身） */
export const metricLabel = (key: string): string => METRIC_MAP.get(key)?.labelZh ?? key

/** 指标单位（未知 key 返回空串） */
export const metricUnit = (key: string): string => METRIC_MAP.get(key)?.unit ?? ''

/** 按指标精度格式化数值 */
export const formatMetricValue = (key: string, value: number): string => {
  const def = METRIC_MAP.get(key)
  const precision = def?.precision ?? 1
  return value.toFixed(precision)
}
