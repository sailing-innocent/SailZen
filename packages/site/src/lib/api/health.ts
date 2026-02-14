/**
 * @file health.ts
 * @brief My Health Data API
 * @author sailing-innocent
 * @date 2024-12-29
 */

import { SERVER_URL, API_BASE } from './config'
import {
  type WeightCreateProps,
  type WeightData,
  type WeightStatsResponse,
  type ExerciseCreateProps,
  type ExerciseData,
  type WeightAnalysisResult,
  type WeightPredictionResponse,
  type WeightPlanCreateProps,
  type WeightPlanData,
  type WeightPlanProgress,
  type WeightRecordWithStatus,
} from '@lib/data/health'

const HEALTH_API_BASE = API_BASE + '/health'

// ==================== Weight APIs ====================

const api_get_weight = async (index: number): Promise<WeightData> => {
  try {
    const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/weight/${index}`)
    if (!response.ok) {
      throw new Error(`Error fetching weight data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch weight data:', error)
    throw error
  }
}

const api_get_weights = async (
  skip: number = 0,
  limit: number = -1,
  start: number = -1,
  end: number = -1
): Promise<WeightData[]> => {
  try {
    const api_with_param =
      `${SERVER_URL}/${HEALTH_API_BASE}/weight?skip=` +
      skip.toString() +
      `&limit=` +
      limit.toString() +
      `&start=` +
      start.toString() +
      `&end=` +
      end.toString()
    const response = await fetch(api_with_param)
    if (!response.ok) {
      throw new Error(`Error fetching weights data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch weights data:', error)
    throw error
  }
}

const api_get_weights_avg = async (start: number = -1, end: number = -1): Promise<WeightStatsResponse> => {
  try {
    const api_with_param =
      `${SERVER_URL}/${HEALTH_API_BASE}/weight/avg?start=` + start.toString() + `&end=` + end.toString()
    const response = await fetch(api_with_param)
    if (!response.ok) {
      throw new Error(`Error fetching weights data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch weights data:', error)
    throw error
  }
}

const api_create_weight = async (newWeight: WeightCreateProps): Promise<WeightData> => {
  try {
    const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/weight/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(newWeight),
    })
    if (!response.ok) {
      throw new Error(`Error creating weight data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to create weight data:', error)
    throw error
  }
}

// ==================== Weight Analysis APIs ====================

const api_analyze_weight_trend = async (
  start: number = -1,
  end: number = -1,
  modelType: string = 'linear'
): Promise<WeightAnalysisResult> => {
  try {
    const params = new URLSearchParams()
    if (start > 0) params.append('start', start.toString())
    if (end > 0) params.append('end', end.toString())
    params.append('model_type', modelType)

    const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/weight/analysis?${params}`)
    if (!response.ok) {
      throw new Error(`Error analyzing weight trend: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to analyze weight trend:', error)
    throw error
  }
}

const api_predict_weight = async (
  targetTime: number,
  modelType: string = 'linear',
  start: number = -1,
  end: number = -1
): Promise<WeightPredictionResponse> => {
  try {
    const params = new URLSearchParams()
    params.append('target_time', targetTime.toString())
    params.append('model_type', modelType)
    if (start > 0) params.append('start', start.toString())
    if (end > 0) params.append('end', end.toString())

    const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/weight/prediction?${params}`)
    if (!response.ok) {
      throw new Error(`Error predicting weight: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to predict weight:', error)
    throw error
  }
}

// ==================== Weight Plan APIs ====================

const api_create_weight_plan = async (plan: WeightPlanCreateProps): Promise<WeightPlanData> => {
  try {
    const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/weight/plan/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(plan),
    })
    if (!response.ok) {
      throw new Error(`Error creating weight plan: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to create weight plan:', error)
    throw error
  }
}

const api_get_weight_plan = async (): Promise<WeightPlanData | null> => {
  try {
    const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/weight/plan/`)
    if (!response.ok) {
      if (response.status === 404) {
        return null
      }
      throw new Error(`Error fetching weight plan: ${response.statusText}`)
    }
    const data = await response.json()
    // Check if the response is a valid plan (has positive id)
    if (!data || data.id === -1) {
      return null
    }
    return data
  } catch (error) {
    console.error('Failed to fetch weight plan:', error)
    return null
  }
}

const api_get_weight_plan_progress = async (planId?: number): Promise<WeightPlanProgress | null> => {
  try {
    const params = new URLSearchParams()
    if (planId) params.append('plan_id', planId.toString())

    const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/weight/plan/progress?${params}`)
    if (!response.ok) {
      if (response.status === 404) {
        return null
      }
      throw new Error(`Error fetching weight plan progress: ${response.statusText}`)
    }
    const data = await response.json()
    // Check if valid progress data (has valid plan)
    if (!data || !data.plan || data.plan.id === -1) {
      return null
    }
    return data
  } catch (error) {
    console.error('Failed to fetch weight plan progress:', error)
    return null
  }
}

const api_get_weights_with_status = async (
  start?: number,
  end?: number,
  planId?: number
): Promise<WeightRecordWithStatus[]> => {
  try {
    const params = new URLSearchParams()
    // Only add params if they have valid values
    if (start !== undefined && start !== null && start > 0) {
      params.append('start', start.toString())
    }
    if (end !== undefined && end !== null && end > 0) {
      params.append('end', end.toString())
    }
    if (planId !== undefined && planId !== null) {
      params.append('plan_id', planId.toString())
    }

    const queryString = params.toString()
    const url = `${SERVER_URL}/${HEALTH_API_BASE}/weight/plan/weights-with-status${queryString ? '?' + queryString : ''}`

    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`Error fetching weights with status: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch weights with status:', error)
    return []
  }
}

// ==================== Exercise APIs ====================

const api_get_exercises = async (
  skip: number = 0,
  limit: number = -1,
  start: number = -1,
  end: number = -1
): Promise<ExerciseData[]> => {
  try {
    const api_with_param =
      `${SERVER_URL}/${HEALTH_API_BASE}/exercise?skip=` +
      skip.toString() +
      `&limit=` +
      limit.toString() +
      `&start=` +
      start.toString() +
      `&end=` +
      end.toString()
    const response = await fetch(api_with_param)
    if (!response.ok) {
      throw new Error(`Error fetching exercise data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch exercise data:', error)
    throw error
  }
}

const api_create_exercise = async (newExercise: ExerciseCreateProps): Promise<ExerciseData> => {
  try {
    const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/exercise/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(newExercise),
    })
    if (!response.ok) {
      throw new Error(`Error creating exercise data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to create exercise data:', error)
    throw error
  }
}

const api_delete_exercise = async (id: number): Promise<void> => {
  try {
    const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/exercise/${id}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      throw new Error(`Error deleting exercise data: ${response.statusText}`)
    }
  } catch (error) {
    console.error('Failed to delete exercise data:', error)
    throw error
  }
}

// prettier-ignore
export {
  api_get_weight,
  api_get_weights,
  api_create_weight,
  api_analyze_weight_trend,
  api_predict_weight,
  api_create_weight_plan,
  api_get_weight_plan,
  api_get_weight_plan_progress,
  api_get_weights_with_status,
  api_get_exercises,
  api_create_exercise,
  api_delete_exercise,
}
