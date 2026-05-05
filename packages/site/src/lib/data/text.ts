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
<<<<<<< HEAD
// Chapter Insert Types
// ============================================================================

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
=======
>>>>>>> ai
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

<<<<<<< HEAD

=======
>>>>>>> ai
