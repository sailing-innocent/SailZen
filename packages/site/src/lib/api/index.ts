/**
 * @file index.ts
 * @brief The API Interface
 * @author sailing-innocent
 * @date 2024-12-26
 */

export * from './config'
export * from './money'
export * from './health'
export * from './project'

import { SERVER_URL, API_BASE } from './config'

export const api_get_health = async (): Promise<boolean> => {
  try {
    const response = await fetch(`${SERVER_URL}/${API_BASE}/health`)
    return response.ok
  } catch (error) {
    console.error('Failed to fetch server health:', error)
    return false
  }
}
