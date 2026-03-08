/**
 * @file text.ts
 * @brief Text Content Data Types
 * @author sailing-innocent
 * @date 2025-01-29
 */

// ============================================================================
// Work Types
// ============================================================================

export interface Work {
  id: number
  slug: string
  title: string
  original_title?: string
  author?: string
  language_primary: string
  work_type: string
  status: string
  synopsis?: string
  meta_data: Record<string, unknown>
  created_at?: string
  updated_at?: string
  edition_count: number
  chapter_count: number
  total_chars: number
}

export interface WorkCreate {
  title: string
  original_title?: string
  author?: string
  language_primary?: string
  work_type?: string
  status?: string
  synopsis?: string
  meta_data?: Record<string, unknown>
}

// ============================================================================
// Edition Types
// ============================================================================

export interface Edition {
  id: number
  work_id: number
  edition_name?: string
  language: string
  source_format: string
  canonical: boolean
  source_path?: string
  source_checksum?: string
  ingest_version: number
  word_count?: number
  char_count?: number
  description?: string
  status: string
  meta_data: Record<string, unknown>
  created_at?: string
  updated_at?: string
  chapter_count: number
}

export interface EditionCreate {
  work_id: number
  edition_name?: string
  language?: string
  source_format?: string
  canonical?: boolean
  description?: string
  meta_data?: Record<string, unknown>
}

// ============================================================================
// Document Node Types
// ============================================================================

export interface DocumentNode {
  id: number
  edition_id: number
  parent_id?: number
  node_type: string
  sort_index: number
  depth: number
  label?: string
  title?: string
  raw_text?: string
  word_count?: number
  char_count?: number
  path: string
  status: string
  meta_data: Record<string, unknown>
  created_at?: string
  updated_at?: string
  children_count: number
}

export interface DocumentNodeUpdate {
  label?: string
  title?: string
  raw_text?: string
  meta_data?: Record<string, unknown>
}

export interface ChapterListItem {
  id: number
  sort_index: number
  label?: string
  title?: string
  char_count?: number
  path: string
}

// ============================================================================
// Import Types
// ============================================================================

export interface TextImportRequest {
  work_title: string
  content: string
  work_author?: string
  work_synopsis?: string
  edition_name?: string
  language?: string
  chapter_pattern?: string
  meta_data?: Record<string, unknown>
}

export interface ImportResponse {
  work: Work
  edition: Edition
  chapter_count: number
  message: string
}

export interface AppendResponse {
  edition_id: number
  new_chapter_count: number
  message: string
}

export interface ChapterInsertRequest {
  edition_id: number
  sort_index: number  // 插入位置（0-based），插入后该位置及之后的章节会后移
  label?: string      // 章节标签，如 "第一章"
  title?: string      // 章节标题
  content: string     // 章节内容
  meta_data?: Record<string, unknown>
}

export interface ChapterInsertResponse {
  chapter: DocumentNode
  message: string
}

// ============================================================================
// Helper Functions
// ============================================================================

export function formatCharCount(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万字`
  }
  return `${count}字`
}

export function getWorkStatusLabel(status: string): string {
  const statusMap: Record<string, string> = {
    ongoing: '连载中',
    completed: '已完结',
    hiatus: '暂停',
  }
  return statusMap[status] || status
}

export function getWorkTypeLabel(type: string): string {
  const typeMap: Record<string, string> = {
    web_novel: '网络小说',
    novel: '小说',
    essay: '散文',
  }
  return typeMap[type] || type
}

// ============================================================================
// Async Import Task Types
// ============================================================================

export type ImportTaskStatus = 'pending' | 'scheduled' | 'running' | 'completed' | 'failed' | 'cancelled'

export type ImportStage = 'upload' | 'preprocess' | 'parse' | 'store'

export interface ImportTask {
  id: number
  task_type: string
  status: ImportTaskStatus
  work_title: string
  work_author?: string
  progress: number
  current_phase?: string
  created_at: string
  started_at?: string
  completed_at?: string
  result?: {
    work_id?: number
    edition_id?: number
    chapter_count?: number
    total_chars?: number
    processing_time_seconds?: number
    warnings?: string[]
  }
  error_message?: string
}

export interface ImportTaskProgress {
  stage: ImportStage
  overall_progress: number
  stage_progress: number
  message: string
  chapters_found: number
  chapters_processed: number
  eta_seconds?: number
}

export interface FileUploadResponse {
  file_id: string
  file_name: string
  file_size: number
  encoding?: string
  message: string
}

export interface AsyncImportRequest {
  file_id: string
  work_title: string
  work_author?: string
  edition_name?: string
  enable_ai_parsing?: boolean
  priority?: number
}

export interface AsyncImportResponse {
  task_id: number
  status: string
  message: string
}
