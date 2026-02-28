/**
 * @file character_detection.ts
 * @brief Character Detection API Client
 * @author sailing-innocent
 * @date 2025-03-01
 */

import type {
  CharacterDetectionConfig,
  CharacterDetectionResponse,
  TextRangeSelection,
} from '@lib/data/analysis'
import { SERVER_URL, API_BASE } from './config'

const CHARACTER_DETECTION_API_BASE = `${API_BASE}/analysis/character-detection`

/**
 * 创建人物检测任务
 * @param data 检测请求数据
 * @returns 检测响应
 */
export async function api_create_character_detection(data: {
  edition_id: number
  range_selection: TextRangeSelection
  config?: CharacterDetectionConfig
  work_title?: string
  known_characters?: string[]
}): Promise<CharacterDetectionResponse> {
  const response = await fetch(`${SERVER_URL}/${CHARACTER_DETECTION_API_BASE}/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to create character detection: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}

/**
 * 预览人物检测（快速预览前N章）
 * @param data 预览请求数据
 * @returns 预览结果
 */
export async function api_preview_character_detection(data: {
  edition_id: number
  chapter_count?: number
  work_title?: string
}): Promise<{
  success: boolean
  preview_characters?: Array<{
    canonical_name: string
    role_type: string
    role_confidence: number
    mention_count: number
    description: string
  }>
  total_detected?: number
  metadata?: Record<string, unknown>
  error?: string
}> {
  const response = await fetch(`${SERVER_URL}/${CHARACTER_DETECTION_API_BASE}/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to preview character detection: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}

/**
 * 保存检测结果到数据库
 * @param data 保存请求数据
 * @returns 保存结果
 */
export async function api_save_detection_result(data: {
  characters: Array<Record<string, unknown>>
  auto_deduplicate?: boolean
}): Promise<{
  success: boolean
  saved_count?: number
  saved_characters?: Array<{
    character_id: number
    canonical_name: string
    aliases_created: number
    attributes_created: number
  }>
  deduplication?: {
    merged_count: number
    merged_groups: number[][]
    remaining_candidates: number
  }
  error?: string
}> {
  const response = await fetch(`${SERVER_URL}/${CHARACTER_DETECTION_API_BASE}/task/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to save detection result: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}

/**
 * 获取人物去重候选
 * @param editionId 版本ID
 * @param minSimilarity 最小相似度阈值
 * @returns 去重候选列表
 */
export async function api_get_deduplication_candidates(
  editionId: number,
  minSimilarity: number = 0.7
): Promise<{
  success: boolean
  candidates?: Array<{
    character1_id: number
    character2_id: number
    character1_name: string
    character2_name: string
    similarity_score: number
    merge_reason: string
    suggested_action: string
  }>
  statistics?: {
    total_characters: number
    high_confidence_duplicates: number
    medium_confidence_duplicates: number
    total_candidates: number
  }
  error?: string
}> {
  const response = await fetch(
    `${SERVER_URL}/${CHARACTER_DETECTION_API_BASE}/deduplicate/${editionId}?min_similarity=${minSimilarity}`
  )
  if (!response.ok) {
    throw new Error(`Failed to get deduplication candidates: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 合并两个人物
 * @param data 合并请求数据
 * @returns 合并结果
 */
export async function api_merge_characters(data: {
  target_character_id: number
  source_character_id: number
}): Promise<{
  success: boolean
  merged_character_id?: number
  merged_character_name?: string
  error?: string
}> {
  const response = await fetch(`${SERVER_URL}/${CHARACTER_DETECTION_API_BASE}/merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to merge characters: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}

/**
 * 批量导入人物
 * @param data 批量导入请求数据
 * @returns 导入结果
 */
export async function api_batch_import_characters(data: {
  edition_id: number
  characters: Array<Record<string, unknown>>
  auto_deduplicate?: boolean
}): Promise<{
  success: boolean
  imported_count?: number
  error_count?: number
  imported?: Array<{
    index: number
    character_id: number
    canonical_name: string
    aliases_created: number
    attributes_created: number
  }>
  errors?: Array<{ index: number; error: string }>
  deduplication?: {
    merged_count: number
    merged_groups: number[][]
    remaining_candidates: number
  }
  error?: string
}> {
  const response = await fetch(`${SERVER_URL}/${CHARACTER_DETECTION_API_BASE}/batch-import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to batch import characters: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}
