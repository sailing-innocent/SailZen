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
