/**
 * @file text.ts
 * @brief Text & Content 2.0 Data Types
 * @author sailing-innocent
 * @date 2026-11-26
 */

// ============================================================================
// Progress & Work Types
// ============================================================================

export interface ReadingProgressSummary {
  edition_id: number
  node_id?: number | null
  sort_index: number
  char_offset: number
  scroll_offset: number
  page_index: number
  mode: string
  progress_pct: number
  total_read_seconds: number
  client_device: string
  last_read_at?: string | null
}

export interface ReadingProgress extends ReadingProgressSummary {
  id: number
  user_id: number
  work_id: number
  updated_at?: string | null
}

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
  pillar: string
  reading_status: string
  reading_track: string
  priority: number
  source_url?: string | null
  vault_slug?: string | null
  is_original: boolean
  meta_data: Record<string, unknown>
  created_at?: string
  updated_at?: string
  edition_count: number
  chapter_count: number
  total_chars: number
  progress?: ReadingProgressSummary | null
  topic_ids: number[]
  asset_count: number
}

export interface WorkUpdate {
  title?: string
  original_title?: string
  author?: string
  language_primary?: string
  work_type?: string
  status?: string
  synopsis?: string
  pillar?: string
  reading_status?: string
  reading_track?: string
  priority?: number
  source_url?: string
  vault_slug?: string
  is_original?: boolean
  meta_data?: Record<string, unknown>
}

export type WorkCreate = WorkUpdate & { title: string }

// ============================================================================
// Edition & Volume TOC Types
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
  chapter_count?: number
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

export interface DocumentNode {
  id: number
  edition_id: number
  parent_id?: number | null
  node_type: string
  sort_index: number
  depth: number
  label?: string
  title?: string
  raw_text?: string
  word_count?: number
  char_count?: number
  path: string
  status?: string
  meta_data: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface DocumentNodeUpdate {
  label?: string
  title?: string
  raw_text?: string
  parent_id?: number | null
  meta_data?: Record<string, unknown>
}

export interface ChapterListItem {
  id: number
  sort_index: number
  label?: string
  title?: string
  char_count?: number
  path: string
  parent_id?: number | null
  volume_title?: string | null
}

export interface TocChapterItem {
  id: number
  parent_id?: number | null
  sort_index: number
  label?: string
  title?: string
  char_count?: number
  path: string
  node_type: string
}

export interface TocVolumeItem {
  id: number
  sort_index: number
  label?: string
  title: string
  summary: string
  chapter_count: number
  total_chars: number
  chapters: TocChapterItem[]
}

export interface EditionToc {
  edition_id: number
  total_chapters: number
  volume_count: number
  volumes: TocVolumeItem[]
  ungrouped_chapters: TocChapterItem[]
}

export interface AutoVolumePreviewItem {
  label: string
  title: string
  start_sort_index: number
  end_sort_index: number
  chapter_count: number
}

export interface AutoVolumeResponse {
  edition_id: number
  dry_run: boolean
  strategy: string
  volumes: AutoVolumePreviewItem[]
  applied_volumes: number
  assigned_chapters: number
}

// ============================================================================
// Stats, Topics, Assets, Vault Index & Multi-Format Import Types
// ============================================================================

export interface PillarStatItem {
  pillar: string
  work_count: number
  reading_count: number
  finished_count: number
  read_seconds_7d: number
  read_seconds_30d: number
}

export interface ReadingOverview {
  total_works: number
  reading_count: number
  mainline_reading: Work[]
  stalled_mainline: Work[]
  pillar_stats: PillarStatItem[]
  total_read_seconds_7d: number
  total_read_seconds_30d: number
  active_topic_count: number
}

export interface ContentTopic {
  id: number
  slug: string
  title: string
  description: string
  pillar: string
  status: string
  rhythm_venture_id?: number | null
  vault_prefix?: string | null
  keywords: string[]
  meta_data: Record<string, unknown>
  created_at: string
  updated_at: string
  work_count: number
  avg_progress_pct: number
  venture_title?: string | null
}

export interface ContentTopicWorkItem {
  id: number
  topic_id: number
  work_id: number
  role: string
  sort_index: number
  note: string
  work: Work
}

export interface ContentAsset {
  id: number
  work_id?: number | null
  topic_id?: number | null
  asset_kind: string
  storage_key: string
  original_name: string
  mime_type: string
  size_bytes: number
  sha256: string
  meta_data: Record<string, unknown>
  created_at: string
  file_url: string
}

export interface VaultNoteIndexItem {
  id?: number
  fname: string
  namespace: string
  title: string
  summary: string
  tags: string[]
  links: string[]
  work_id?: number | null
  topic_id?: number | null
  pillar?: string | null
  era?: string | null
  year_start?: number | null
  year_end?: number | null
  content_hash: string
  synced_at?: string | null
}

export interface TopicRhythmTaskSummary {
  id: number
  title: string
  kind: string
  state: string
  est_minutes: number
  urgency_ddl?: string | null
  ref: Record<string, unknown>
}

export interface ContentTopicDetail {
  topic: ContentTopic
  works: ContentTopicWorkItem[]
  assets: ContentAsset[]
  vault_notes: VaultNoteIndexItem[]
  venture?: TopicRhythmTaskSummary | null
  rhythm_tasks: TopicRhythmTaskSummary[]
}

export interface MultiFormatImportResponse {
  work: Work
  edition: Edition
  volume_count: number
  chapter_count: number
  asset?: ContentAsset | null
  parser_used: string
  message: string
}

// ============================================================================
// Helper Labels & Formatters
// ============================================================================

export function formatCharCount(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万字`
  }
  return `${count}字`
}

export function formatDurationMinutes(seconds: number): string {
  const mins = Math.round((seconds || 0) / 60)
  if (mins >= 60) {
    return `${(mins / 60).toFixed(1)}h`
  }
  return `${mins}m`
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
    web_novel: '网文',
    novel: '小说',
    book: '书籍',
    paper: '论文',
    article: '长文',
    script: '剧本',
    reference: '资料',
    essay: '散文',
  }
  return typeMap[type] || type
}

export function getPillarLabel(pillar: string): string {
  const map: Record<string, string> = {
    tech: '技术',
    history: '历史',
    aesthetics: '审美',
    fiction: '小说',
    interdisciplinary: '跨领域',
    general: '综合',
  }
  return map[pillar] || pillar
}

export function getReadingStatusLabel(status: string): string {
  const map: Record<string, string> = {
    inbox: '收件箱',
    queued: '待读',
    reading: '在读',
    paused: '搁置',
    finished: '已读完',
    dropped: '弃坑',
  }
  return map[status] || status
}

export function getReadingTrackLabel(track: string): string {
  const map: Record<string, string> = {
    mainline: '主线',
    project: '项目',
    leisure: '消遣',
  }
  return map[track] || track
}
