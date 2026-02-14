/**
 * @file health.ts
 * @brief My Health Data API
 * @author sailing-innocent
 * @date 2024-12-29
 */

import { SERVER_URL, API_BASE } from './config'
import { type WeightCreateProps, type WeightData, type WeightStatsResponse, type ExerciseCreateProps, type ExerciseData } from '@lib/data/health'

const HEALTH_API_BASE = API_BASE + '/health'

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

const api_get_weights = async (skip: number = 0, limit: number = -1, start: number = -1, end: number = -1): Promise<WeightData[]> => {
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
    const api_with_param = `${SERVER_URL}/${HEALTH_API_BASE}/weight/avg?start=` + start.toString() + `&end=` + end.toString()
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

// Exercise APIs
const api_get_exercises = async (skip: number = 0, limit: number = -1, start: number = -1, end: number = -1): Promise<ExerciseData[]> => {
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
  api_get_exercises,
  api_create_exercise,
  api_delete_exercise,
}
