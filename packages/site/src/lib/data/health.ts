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
export interface WeightPlanCreateProps {
  target_weight: number
  start_time: number  // Can be custom date, not necessarily today
  target_time: number
  description?: string
}

export interface WeightPlanData extends WeightPlanCreateProps {
  id: number
  created_at: number
}

export interface WeightRecordWithStatus {
  id: number
  value: number
  htime: number
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
