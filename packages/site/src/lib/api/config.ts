/**
 * @file config.ts
 * @brief The API Configuration
 * @author sailing-innocent
 * @date 2024-12-26
 */

export const SERVER_URL = process.env.SERVER_URL
export const API_BASE = 'api/v1'
export function get_url() {
  return SERVER_URL
}
