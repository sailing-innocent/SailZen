/**
 * @file health.ts
 * @brief My Health Data API
 * @author sailing-innocent
 * @date 2024-12-29
 */

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
