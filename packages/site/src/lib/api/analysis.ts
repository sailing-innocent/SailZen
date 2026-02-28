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
  EvidenceUpdateRequest,
  TextEvidence,
  AnalysisStats,
  LLMProvidersResponse,
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
 * @returns 创建的证�?
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
 * 获取指定章节的所有证�?
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
 * 获取指定目标的所有证�?
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
 * 更新证据
 * @param evidenceId 证据ID
 * @param data 更新数据
 * @returns 更新后的证据
 */
export async function api_update_evidence(
  evidenceId: string,
  data: EvidenceUpdateRequest
): Promise<TextEvidence> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/evidence/${evidenceId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to update evidence: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 删除证据
 * @param evidenceId 证据ID
 * @returns 删除的证�?
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
 * 获取版本的统计分析数�?
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

// ============================================================================
// Character API
// ============================================================================

import type { Character, CharacterProfile, RelationGraphData } from '@lib/data/analysis'

/**
 * 获取版本的人物列�?
 * @param editionId 版本ID
 * @param roleType 角色类型（可选）
 * @returns 人物列表
 */
export async function api_get_characters_by_edition(
  editionId: number,
  roleType?: string
): Promise<Character[]> {
  const url = new URL(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/edition/${editionId}`)
  if (roleType) {
    url.searchParams.append('role_type', roleType)
  }
  const response = await fetch(url.toString())
  if (!response.ok) {
    throw new Error(`Failed to get characters: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 创建人物
 * @param editionId 版本ID
 * @param data 人物数据
 * @returns 创建的人�?
 */
export async function api_create_character(
  editionId: number,
  data: {
    canonical_name: string
    role_type: string
    description?: string
  }
): Promise<Character> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...data, edition_id: editionId }),
  })
  if (!response.ok) {
    throw new Error(`Failed to create character: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 删除人物
 * @param characterId 人物ID
 */
export async function api_delete_character(characterId: string): Promise<void> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${characterId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete character: ${response.statusText}`)
  }
}

/**
 * 获取人物详情
 * @param characterId 人物ID
 * @returns 人物详情
 */
export async function api_get_character_profile(characterId: string): Promise<CharacterProfile> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${characterId}/profile`)
  if (!response.ok) {
    throw new Error(`Failed to get character profile: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 添加人物别名
 * @param characterId 人物ID
 * @param alias 别名
 * @param aliasType 别名类型
 * @returns 创建的别�?
 */
export async function api_add_character_alias(
  characterId: string,
  alias: string,
  aliasType: string
): Promise<{ id: string; alias: string; alias_type: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${characterId}/alias`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alias, alias_type: aliasType }),
  })
  if (!response.ok) {
    throw new Error(`Failed to add character alias: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 删除人物别名
 * @param aliasId 别名ID
 */
export async function api_remove_character_alias(aliasId: string): Promise<void> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/alias/${aliasId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to remove character alias: ${response.statusText}`)
  }
}

/**
 * 添加人物属�?
 * @param characterId 人物ID
 * @param data 属性数�?
 * @returns 创建的属�?
 */
export async function api_add_character_attribute(
  characterId: string,
  data: {
    category: string
    key: string
    value: string
    confidence?: number
  }
): Promise<{ id: string; category: string; key: string; value: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${characterId}/attribute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to add character attribute: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 删除人物属�?
 * @param attributeId 属性ID
 */
export async function api_delete_character_attribute(attributeId: string): Promise<void> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/attribute/${attributeId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete character attribute: ${response.statusText}`)
  }
}

/**
 * 获取关系图谱数据
 * @param editionId 版本ID
 * @returns 关系图谱数据
 */
export async function api_get_relation_graph(editionId: number): Promise<RelationGraphData> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/edition/${editionId}/relation-graph`)
  if (!response.ok) {
    throw new Error(`Failed to get relation graph: ${response.statusText}`)
  }
  return response.json()
}

// ============================================================================
// Setting API
// ============================================================================

import type { Setting, SettingDetail, SettingType } from '@lib/data/analysis'

/**
 * 获取版本的设定列�?
 * @param editionId 版本ID
 * @param settingType 设定类型（可选）
 * @returns 设定列表
 */
export async function api_get_settings_by_edition(
  editionId: number,
  settingType?: SettingType
): Promise<Setting[]> {
  const url = new URL(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/edition/${editionId}`)
  if (settingType) {
    url.searchParams.append('setting_type', settingType)
  }
  const response = await fetch(url.toString())
  if (!response.ok) {
    throw new Error(`Failed to get settings: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 创建设定
 * @param editionId 版本ID
 * @param data 设定数据
 * @returns 创建的设�?
 */
export async function api_create_setting(
  editionId: number,
  data: {
    name: string
    setting_type: SettingType
    description?: string
    importance?: string
  }
): Promise<Setting> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...data, edition_id: editionId }),
  })
  if (!response.ok) {
    throw new Error(`Failed to create setting: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 删除设定
 * @param settingId 设定ID
 */
export async function api_delete_setting(settingId: string): Promise<void> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/${settingId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete setting: ${response.statusText}`)
  }
}

/**
 * 获取设定详情
 * @param settingId 设定ID
 * @returns 设定详情
 */
export async function api_get_setting_detail(settingId: string): Promise<SettingDetail> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/${settingId}/detail`)
  if (!response.ok) {
    throw new Error(`Failed to get setting detail: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 获取设定类型列表
 * @returns 设定类型列表
 */
export async function api_get_setting_types(): Promise<{ types: SettingType[]; labels: Record<SettingType, string> }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/types`)
  if (!response.ok) {
    throw new Error(`Failed to get setting types: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 添加设定属�?
 * @param settingId 设定ID
 * @param data 属性数�?
 * @returns 创建的属�?
 */
export async function api_add_setting_attribute(
  settingId: string,
  data: {
    key: string
    value: string
    description?: string
  }
): Promise<{ id: string; key: string; value: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/${settingId}/attribute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to add setting attribute: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 删除设定属�?
 * @param attributeId 属性ID
 */
export async function api_delete_setting_attribute(attributeId: string): Promise<void> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/attribute/${attributeId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete setting attribute: ${response.statusText}`)
  }
}

// ============================================================================
// Outline API
// ============================================================================

import type { Outline, OutlineTree, OutlineTreeNode, OutlineType, OutlineNodeType } from '@lib/data/analysis'

/**
 * 获取版本的大纲列�?
 * @param editionId 版本ID
 * @param outlineType 大纲类型（可选）
 * @returns 大纲列表
 */
export async function api_get_outlines_by_edition(
  editionId: number,
  outlineType?: OutlineType
): Promise<Outline[]> {
  const url = new URL(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/edition/${editionId}`)
  if (outlineType) {
    url.searchParams.append('outline_type', outlineType)
  }
  const response = await fetch(url.toString())
  if (!response.ok) {
    throw new Error(`Failed to get outlines: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 创建大纲
 * @param editionId 版本ID
 * @param data 大纲数据
 * @returns 创建的大�?
 */
export async function api_create_outline(
  editionId: number,
  data: {
    name: string
    outline_type: OutlineType
    description?: string
  }
): Promise<Outline> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      title: data.name,
      outline_type: data.outline_type,
      description: data.description,
      edition_id: editionId 
    }),
  })
  if (!response.ok) {
    throw new Error(`Failed to create outline: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 删除大纲
 * @param outlineId 大纲ID
 */
export async function api_delete_outline(outlineId: string): Promise<void> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/${outlineId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete outline: ${response.statusText}`)
  }
}

/**
 * 获取大纲�?
 * @param outlineId 大纲ID
 * @returns 大纲�?
 */
export async function api_get_outline_tree(outlineId: string): Promise<OutlineTree> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/${outlineId}/tree`)
  if (!response.ok) {
    throw new Error(`Failed to get outline tree: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 添加大纲节点
 * @param outlineId 大纲ID
 * @param data 节点数据
 * @returns 创建的节�?
 */
export async function api_add_outline_node(
  outlineId: string,
  data: {
    parent_id?: string
    node_type: OutlineNodeType
    title: string
    content?: string
    sort_index?: number
  }
): Promise<OutlineTreeNode> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/node`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      outline_id: outlineId,
      parent_id: data.parent_id,
      node_type: data.node_type,
      title: data.title,
      summary: data.content,
      sort_index: data.sort_index ?? 0,
    }),
  })
  if (!response.ok) {
    throw new Error(`Failed to add outline node: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 删除大纲节点
 * @param nodeId 节点ID
 */
export async function api_delete_outline_node(nodeId: string): Promise<void> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/node/${nodeId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete outline node: ${response.statusText}`)
  }
}

/**
 * 添加大纲事件
 * @param nodeId 节点ID
 * @param data 事件数据
 * @returns 创建的事�?
 */
export async function api_add_outline_event(
  nodeId: string,
  data: {
    event_type: string
    description: string
    significance?: string
  }
): Promise<{ id: string; event_type: string; description: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/event`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      node_id: nodeId,
      event_type: data.event_type,
      description: data.description,
      significance: data.significance,
    }),
  })
  if (!response.ok) {
    throw new Error(`Failed to add outline event: ${response.statusText}`)
  }
  return response.json()
}

// ============================================================================
// Task API (for task_panel.tsx)
// ============================================================================

import type { AnalysisTask, AnalysisResult, CreateTaskRequest, TaskProgress, TaskExecutionPlan, LLMProvider } from '@lib/data/analysis'

/**
 * 创建分析任务
 * @param data 任务创建请求
 * @returns 创建的任�?
 */
export async function api_create_analysis_task(data: CreateTaskRequest): Promise<AnalysisTask> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to create analysis task: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 获取版本的任务列�?
 * @param editionId 版本ID
 * @returns 任务列表
 */
export async function api_get_tasks_by_edition(editionId: number): Promise<AnalysisTask[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/?edition_id=${editionId}`)
  if (!response.ok) {
    throw new Error(`Failed to get tasks: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 获取分析任务详情
 * @param taskId 任务ID
 * @returns 任务详情
 */
export async function api_get_analysis_task(taskId: number): Promise<AnalysisTask> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/${taskId}`)
  if (!response.ok) {
    throw new Error(`Failed to get analysis task: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 获取任务结果
 * @param taskId 任务ID
 * @returns 结果列表
 */
export async function api_get_task_results(taskId: number): Promise<AnalysisResult[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/result/${taskId}`)
  if (!response.ok) {
    throw new Error(`Failed to get task results: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 批准结果
 * @param resultId 结果ID
 */
export async function api_approve_result(resultId: number): Promise<void> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/result/${resultId}/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'approved' }),
  })
  if (!response.ok) {
    throw new Error(`Failed to approve result: ${response.statusText}`)
  }
}

/**
 * 拒绝结果
 * @param resultId 结果ID
 */
export async function api_reject_result(resultId: number): Promise<void> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/result/${resultId}/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'rejected' }),
  })
  if (!response.ok) {
    throw new Error(`Failed to reject result: ${response.statusText}`)
  }
}

/**
 * 应用所有已批准的结�?
 * @param taskId 任务ID
 * @returns 应用结果统计
 */
export async function api_apply_all_results(taskId: number): Promise<{ applied: number; failed: number }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/${taskId}/apply`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Failed to apply results: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 创建任务执行计划
 * @param taskId 任务ID
 * @param mode 执行模式
 * @returns 执行计划
 */
export async function api_create_task_plan(
  taskId: number,
  mode: string
): Promise<{ success: boolean; plan?: TaskExecutionPlan; error?: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/${taskId}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  })
  if (!response.ok) {
    throw new Error(`Failed to create task plan: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 异步执行任务
 * @param taskId 任务ID
 * @param config 执行配置
 * @returns 执行结果
 */
export async function api_execute_task_async(
  taskId: number,
  config: {
    mode: string
    llm_provider?: string
    temperature?: number
  }
): Promise<{ success: boolean; error?: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/${taskId}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  if (!response.ok) {
    throw new Error(`Failed to execute task: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 获取任务进度
 * @param taskId 任务ID
 * @returns 任务进度
 */
export async function api_get_task_progress(taskId: number): Promise<{ success: boolean; progress?: TaskProgress; error?: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/progress/${taskId}`)
  if (!response.ok) {
    throw new Error(`Failed to get task progress: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 取消运行中的任务
 * @param taskId 任务ID
 */
export async function api_cancel_running_task(taskId: number): Promise<void> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/${taskId}/cancel`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Failed to cancel task: ${response.statusText}`)
  }
}

/**
 * 获取 LLM 提供商列�?
 * @returns 提供商列表及配置信息
 */
export async function api_get_llm_providers(): Promise<LLMProvidersResponse> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/llm-providers`)
  if (!response.ok) {
    throw new Error(`Failed to get LLM providers: ${response.statusText}`)
  }
  return response.json()
}

// ============================================================================
// Outline Extraction API
// ============================================================================

import type {
  OutlineExtractionRequest,
  OutlineExtractionTask,
  OutlineExtractionProgress,
  OutlineExtractionResponse,
  OutlinePreviewResponse,
} from '@lib/data/analysis'

/**
 * 创建大纲提取任务
 * @param data 提取请求
 * @returns 任务信息
 */
export async function api_create_outline_extraction_task(
  data: OutlineExtractionRequest
): Promise<OutlineExtractionTask> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline-extraction/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to create outline extraction task: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 获取大纲提取任务进度
 * @param taskId 任务ID
 * @returns 进度信息
 */
export async function api_get_outline_extraction_progress(
  taskId: string
): Promise<OutlineExtractionProgress> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline-extraction/task/${taskId}`)
  if (!response.ok) {
    throw new Error(`Failed to get task progress: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 获取大纲提取任务详细状态（包含检查点信息�?
 * @param taskId 任务ID
 * @returns 详细状�?
 */
export async function api_get_outline_extraction_detailed_status(
  taskId: string
): Promise<import('@lib/data/analysis').OutlineExtractionDetailedStatus> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline-extraction/task/${taskId}/detailed`)
  if (!response.ok) {
    throw new Error(`Failed to get task detailed status: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 恢复失败或暂停的任务
 * @param taskId 任务ID
 * @returns 恢复结果
 */
export async function api_resume_outline_extraction_task(
  taskId: string
): Promise<import('@lib/data/analysis').ResumeTaskResponse> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline-extraction/task/${taskId}/resume`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Failed to resume task: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 获取大纲提取任务结果
 * @param taskId 任务ID
 * @returns 提取结果
 */
export async function api_get_outline_extraction_result(
  taskId: string
): Promise<OutlineExtractionResponse> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline-extraction/task/${taskId}/result`)
  if (!response.ok) {
    throw new Error(`Failed to get task result: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 保存大纲提取结果
 * @param taskId 任务ID
 * @returns 保存结果
 */
export async function api_save_outline_extraction_result(
  taskId: string
): Promise<{ success: boolean; outline_id?: number; nodes_created?: number; message?: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline-extraction/task/${taskId}/save`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Failed to save extraction result: ${response.statusText}`)
  }
  return response.json()
}

/**
 * 预览大纲提取效果
 * @param data 提取请求
 * @returns 预览结果
 */
export async function api_preview_outline_extraction(
  data: OutlineExtractionRequest
): Promise<OutlinePreviewResponse> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline-extraction/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to preview outline extraction: ${response.statusText}`)
  }
  return response.json()
}


