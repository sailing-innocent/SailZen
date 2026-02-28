/**
 * @file analysis.ts
 * @brief Analysis Data Types
 * @author sailing-innocent
 * @date 2025-02-28
 */

// ============================================================================
// Text Range Selection Types
// ============================================================================

export type RangeSelectionMode =
  | 'single_chapter'
  | 'chapter_range'
  | 'multi_chapter'
  | 'full_edition'
  | 'current_to_end'
  | 'custom_range'

export interface RangeSelectionModeInfo {
  value: RangeSelectionMode
  label: string
  description: string
  params: string[]
}

export interface TextRangeSelection {
  edition_id: number
  mode: RangeSelectionMode
  chapter_index?: number
  start_index?: number
  end_index?: number
  chapter_indices?: number[]
  node_ids?: number[]
  meta_data?: Record<string, unknown>
}

export interface SelectedChapterInfo {
  id: number
  sort_index: number
  label?: string
  title?: string
  char_count?: number
  word_count?: number
}

export interface TextRangePreview {
  edition_id: number
  mode: RangeSelectionMode
  chapter_count: number
  total_chars: number
  total_words: number
  estimated_tokens: number
  selected_chapters: SelectedChapterInfo[]
  preview_text?: string
  warnings: string[]
  meta_data?: Record<string, unknown>
}

export interface ChapterContent {
  id: number
  sort_index: number
  label?: string
  title?: string
  char_count?: number
  word_count?: number
  content: string
}

export interface TextRangeContent {
  edition_id: number
  mode: RangeSelectionMode
  full_text: string
  chapters: ChapterContent[]
  chapter_count: number
  total_chars: number
  total_words: number
  estimated_tokens: number
  meta_data?: Record<string, unknown>
}

// ============================================================================
// Evidence Types
// ============================================================================

export interface TextEvidence {
  id: string
  edition_id: number
  node_id: number
  start_offset: number
  end_offset: number
  selected_text: string
  evidence_type: string
  target_type?: string
  target_id?: string
  content: string
  context?: string
  created_at: string
  updated_at?: string
  meta_data?: Record<string, unknown>
}

export interface EvidenceCreateRequest {
  edition_id: number
  node_id: number
  start_offset: number
  end_offset: number
  selected_text: string
  evidence_type: string
  content: string
  target_type?: string
  target_id?: string
  context?: string
  meta_data?: Record<string, unknown>
}

// ============================================================================
// Analysis Task Types
// ============================================================================

export type AnalysisTaskType =
  | 'outline_extraction'
  | 'character_detection'
  | 'setting_extraction'
  | 'relation_analysis'
  | 'consistency_check'
  | 'custom_analysis'

export type AnalysisTaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface AnalysisTask {
  id: string
  edition_id: number
  task_type: AnalysisTaskType
  status: AnalysisTaskStatus
  range_selection: TextRangeSelection
  config?: Record<string, unknown>
  progress: number
  current_step?: string
  created_at: string
  started_at?: string
  completed_at?: string
  result?: Record<string, unknown>
  error_message?: string
  meta_data?: Record<string, unknown>
}

export interface AnalysisTaskRequest {
  edition_id: number
  task_type: AnalysisTaskType
  range_selection: TextRangeSelection
  config?: Record<string, unknown>
  priority?: number
  meta_data?: Record<string, unknown>
}

// ============================================================================
// Stats Types
// ============================================================================

export interface AnalysisStats {
  edition_id: number
  total_tasks: number
  completed_tasks: number
  pending_tasks: number
  failed_tasks: number
  total_evidence: number
  character_count: number
  setting_count: number
  outline_node_count: number
}

// ============================================================================
// Helper Functions
// ============================================================================

export function formatTokenCount(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万`
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K`
  }
  return `${count}`
}

export function formatCharCount(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万字`
  }
  return `${count}字`
}

export function getRangeModeLabel(mode: RangeSelectionMode): string {
  const labels: Record<RangeSelectionMode, string> = {
    single_chapter: '单章选择',
    chapter_range: '连续章节',
    multi_chapter: '多章选择',
    full_edition: '整部作品',
    current_to_end: '到结尾',
    custom_range: '自定义范围',
  }
  return labels[mode] || mode
}

export function getTaskStatusLabel(status: AnalysisTaskStatus): string {
  const labels: Record<AnalysisTaskStatus, string> = {
    pending: '待处理',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return labels[status] || status
}

export function getTaskStatusColor(status: AnalysisTaskStatus): string {
  const colors: Record<AnalysisTaskStatus, string> = {
    pending: 'bg-yellow-500',
    running: 'bg-blue-500',
    completed: 'bg-green-500',
    failed: 'bg-red-500',
    cancelled: 'bg-gray-500',
  }
  return colors[status] || 'bg-gray-500'
}

export function getTaskTypeLabel(type: AnalysisTaskType): string {
  const labels: Record<AnalysisTaskType, string> = {
    outline_extraction: '大纲提取',
    character_detection: '人物检测',
    setting_extraction: '设定提取',
    relation_analysis: '关系分析',
    consistency_check: '一致性检查',
    custom_analysis: '自定义分析',
  }
  return labels[type] || type
}

/**
 * 创建范围选择对象
 */
export function createRangeSelection(
  editionId: number,
  mode: RangeSelectionMode,
  params: Partial<Omit<TextRangeSelection, 'edition_id' | 'mode'>> = {}
): TextRangeSelection {
  return {
    edition_id: editionId,
    mode,
    ...params,
  }
}

/**
 * 获取默认的范围选择
 */
export function getDefaultRangeSelection(editionId: number): TextRangeSelection {
  return {
    edition_id: editionId,
    mode: 'full_edition',
  }
}
