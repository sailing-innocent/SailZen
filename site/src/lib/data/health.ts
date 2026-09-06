/**
 * @file health.ts
 * @brief My Health Data API
 * @author sailing-innocent
 * @date 2024-12-29
 */

// Weight Data Types
export interface WeightCreateProps {
  value: string
  htime: number
  tag?: string
  description?: string
}

export interface WeightData extends WeightCreateProps {
  id: number
}

export interface WeightStatsResponse {
  result: number
}

// Exercise Data Types
export interface ExerciseCreateProps {
  htime: number
  description: string
}

export interface ExerciseData extends ExerciseCreateProps {
  id: number
}

// Weight Analysis Types
export interface WeightPredictionPoint {
  htime: number
  value: number
  is_actual: boolean
}

export interface WeightAnalysisResult {
  model_type: string
  slope: number
  intercept: number
  r_squared: number
  current_weight: number
  current_trend: 'decreasing' | 'stable' | 'increasing'
  predicted_weights: WeightPredictionPoint[]
}

export interface WeightPredictionResponse {
  predicted_weight: number
  target_time: number
}

// Weight Plan Types
export type WeightPlanCurveType = 'linear' | 'polynomial' | 'exponential'

export interface WeightPlanCreateProps {
  targetWeight: string
  initialWeight?: string | null
  startTime: number
  targetTime: number
  description?: string
  curveType: WeightPlanCurveType
  notifyEnabled: boolean
  notifyTime?: string
  feedbackEnabled: boolean
}

export interface WeightPlanData extends WeightPlanCreateProps {
  id: number
  createdAt: number
  rhythmAffairId?: number | null
}

export interface WeightExpectedPoint {
  htime: number
  expected_weight: number
}

export interface WeightRecordWithStatus {
  id: number
  value: number
  htime: number
  tag?: string
  description?: string
  expected_value: number
  status: 'above' | 'below' | 'normal'
  diff: number
}

export interface DailyPrediction {
  htime: number
  expected_weight: number
  actual_weight: number | null
  day: number
}

export interface WeightPlanProgress {
  plan: WeightPlanData
  control_rate: number
  current_weight: number
  expected_current_weight: number
  daily_predictions: DailyPrediction[]
  is_on_track: boolean
}

export interface WeightExpectedRangeResponse {
  plan: WeightPlanData
  points: WeightExpectedPoint[]
}

export interface WeightPlanCheckinStatus {
  plan_id: number
  affair_id: number
  today_done: boolean
  streak: number
}
