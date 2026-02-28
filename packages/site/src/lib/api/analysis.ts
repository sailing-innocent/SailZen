/**
 * @file analysis.ts
 * @brief Analysis API Client
 * @author sailing-innocent
 * @date 2025-02-28
 */

import type {
  TextRangeSelection,
  TextRangePreview,
  TextRangeContent,
  RangeSelectionModeInfo,
  EvidenceCreateRequest,
  TextEvidence,
  AnalysisStats,
} from '@lib/data/analysis'
import { SERVER_URL, API_BASE } from './config'

const ANALYSIS_API_BASE = `${API_BASE}/analysis`

// ============================================================================
// Text Range API
// ============================================================================

/**
 * 预览文本范围
 * @param data 范围选择参数
 * @returns 预览结果
 */
export async function api_preview_range(data: TextRangeSelection): Promise<TextRangePreview> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/range/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to preview range: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}

/**
 * 获取文本范围内容
 * @param data 范围选择参数
 * @returns 内容结果
 */
export async function api_get_range_content(data: TextRangeSelection): Promise<TextRangeContent> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/range/content`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to get range content: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}

/**
 * 获取所有支持的选择模式
 * @returns 选择模式列表
 */
export async function api_get_selection_modes(): Promise<RangeSelectionModeInfo[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/range/modes`)
  if (!response.ok) {
    throw new Error(`Failed to get selection modes: ${response.statusText}`)
  }
  return response.json()
}

// ============================================================================
// Evidence API
// ============================================================================

/**
 * 创建证据
 * @param data 证据创建请求
 * @returns 创建的证据
 */
export async function api_create_evidence(data: EvidenceCreateRequest): Promise<TextEvidence> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/evidence/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to create evidence: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}

/**
 * 获取单个证据
 * @param evidenceId 证据ID
 * @returns 证据信息
 */
export async function api_get_evidence(evidenceId: string): Promise<TextEvidence> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/evidence/${evidenceId}`)
  if (!response.ok) {
    throw new Error(`Failed to get evidence: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 获取指定章节的所有证据
 * @param nodeId 节点ID
 * @param evidenceType 证据类型（可选）
 * @returns 证据列表
 */
export async function api_get_chapter_evidence(
  nodeId: number,
  evidenceType?: string
): Promise<TextEvidence[]> {
  const url = new URL(`${SERVER_URL}/${ANALYSIS_API_BASE}/evidence/chapter/${nodeId}`)
  if (evidenceType) {
    url.searchParams.append('evidence_type', evidenceType)
  }
  const response = await fetch(url.toString())
  if (!response.ok) {
    throw new Error(`Failed to get chapter evidence: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 获取指定目标的所有证据
 * @param targetType 目标类型
 * @param targetId 目标ID
 * @returns 证据列表
 */
export async function api_get_target_evidence(
  targetType: string,
  targetId: string
): Promise<TextEvidence[]> {
  const response = await fetch(
    `${SERVER_URL}/${ANALYSIS_API_BASE}/evidence/target/${targetType}/${targetId}`
  )
  if (!response.ok) {
    throw new Error(`Failed to get target evidence: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 删除证据
 * @param evidenceId 证据ID
 * @returns 删除的证据
 */
export async function api_delete_evidence(evidenceId: string): Promise<TextEvidence> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/evidence/${evidenceId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete evidence: ${response.statusText}`)
  }
  return response.json()
}

// ============================================================================
// Stats API
// ============================================================================

/**
 * 获取版本的统计分析数据
 * @param editionId 版本ID
 * @returns 统计信息
 */
export async function api_get_analysis_stats(editionId: number): Promise<AnalysisStats> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/stats/${editionId}`)
  if (!response.ok) {
    throw new Error(`Failed to get analysis stats: ${response.statusText}`)
  }
  return response.json()
}
