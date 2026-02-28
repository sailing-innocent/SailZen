/**
 * @file setting_extraction.ts
 * @brief Setting Extraction API Client
 * @author sailing-innocent
 * @date 2025-03-01
 */

import type {
  SettingExtractionConfig,
  SettingExtractionResponse,
  TextRangeSelection,
} from '@lib/data/analysis'
import { SERVER_URL, API_BASE } from './config'

const SETTING_EXTRACTION_API_BASE = `${API_BASE}/analysis/setting-extraction`

/**
 * 创建设定提取任务
 * @param data 提取请求数据
 * @returns 提取响应
 */
export async function api_create_setting_extraction(data: {
  edition_id: number
  range_selection: TextRangeSelection
  config?: SettingExtractionConfig
  work_title?: string
  known_settings?: string[]
}): Promise<{
  success: boolean
  task_id?: string
  result?: {
    settings: Array<{
      canonical_name: string
      setting_type: string
      category: string
      importance: string
      first_appearance?: Record<string, string>
      description: string
      attributes: Array<Record<string, string>>
      relations: Array<Record<string, string>>
      key_scenes: string[]
      mention_count: number
    }>
    metadata: Record<string, unknown>
  }
  message: string
  error?: string
}> {
  const response = await fetch(`${SERVER_URL}/${SETTING_EXTRACTION_API_BASE}/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to create setting extraction: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}

/**
 * 预览设定提取（快速预览前N章）
 * @param data 预览请求数据
 * @returns 预览结果
 */
export async function api_preview_setting_extraction(data: {
  edition_id: number
  chapter_count?: number
  work_title?: string
}): Promise<{
  success: boolean
  preview_settings?: Array<{
    canonical_name: string
    setting_type: string
    category: string
    importance: string
    mention_count: number
    description: string
  }>
  total_detected?: number
  metadata?: Record<string, unknown>
  error?: string
}> {
  const response = await fetch(`${SERVER_URL}/${SETTING_EXTRACTION_API_BASE}/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to preview setting extraction: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}

/**
 * 保存提取结果到数据库
 * @param data 保存请求数据
 * @returns 保存结果
 */
export async function api_save_setting_extraction_result(data: {
  settings: Array<Record<string, unknown>>
  edition_id: number
}): Promise<{
  success: boolean
  saved_count?: number
  saved_settings?: Array<{
    setting_id: number
    canonical_name: string
    attributes_created: number
  }>
  error?: string
}> {
  const response = await fetch(`${SERVER_URL}/${SETTING_EXTRACTION_API_BASE}/task/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to save extraction result: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}

/**
 * 获取设定关系图数据
 * @param editionId 版本ID
 * @returns 关系图数据
 */
export async function api_get_setting_relations(
  editionId: number
): Promise<{
  success: boolean
  nodes?: Array<{
    id: string
    name: string
    type: string
    importance: string
    category?: string
  }>
  edges?: Array<{
    id: string
    source: string
    target: string
    type: string
    description?: string
  }>
  total_nodes?: number
  total_edges?: number
  error?: string
}> {
  const response = await fetch(`${SERVER_URL}/${SETTING_EXTRACTION_API_BASE}/relations/${editionId}`)
  if (!response.ok) {
    throw new Error(`Failed to get setting relations: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 创建设定关系
 * @param data 关系数据
 * @returns 创建结果
 */
export async function api_create_setting_relation(data: {
  edition_id: number
  source_setting_id: number
  target_setting_id: number
  relation_type: string
  description?: string
}): Promise<{
  success: boolean
  relation_id?: number
  message?: string
  error?: string
}> {
  const response = await fetch(`${SERVER_URL}/${SETTING_EXTRACTION_API_BASE}/relations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to create setting relation: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}
