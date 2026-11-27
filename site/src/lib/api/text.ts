/**
 * @file text.ts
 * @brief Text & Content 2.0 API Client
 * @author sailing-innocent
 * @date 2026-11-26
 */

import type {
  AutoVolumeResponse,
  ChapterListItem,
  ContentAsset,
  ContentTopic,
  ContentTopicDetail,
  ContentTopicWorkItem,
  DocumentNode,
  DocumentNodeUpdate,
  Edition,
  EditionCreate,
  EditionToc,
  MultiFormatImportResponse,
  ReadingOverview,
  ReadingProgress,
  TopicRhythmTaskSummary,
  VaultNoteIndexItem,
  Work,
  WorkCreate,
  WorkUpdate,
} from '@lib/data/text'
import { API_BASE, SERVER_URL, authHeaders } from './config'

const TEXT_API_BASE = `${API_BASE}/text`

const buildUrl = (path: string, query?: Record<string, unknown>): string => {
  const base =
    SERVER_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost')
  const url = new URL(`${SERVER_URL}/${TEXT_API_BASE}${path}`, base)
  if (query) {
    Object.entries(query).forEach(([k, v]) => {
      if (v === undefined || v === null || v === '') return
      url.searchParams.set(k, String(v))
    })
  }
  return url.toString()
}

const jsonHeaders = () => ({ 'Content-Type': 'application/json', ...authHeaders() })

async function handleJson<T>(response: Response, label: string): Promise<T> {
  if (!response.ok) {
    const txt = await response.text().catch(() => '')
    throw new Error(`${label} (${response.status}): ${txt.slice(0, 200) || response.statusText}`)
  }
  return response.json()
}

// ============================================================================
// Work API
// ============================================================================

export interface WorkQueryParams {
  skip?: number
  limit?: number
  work_type?: string
  pillar?: string
  reading_status?: string
  reading_track?: string
  topic_id?: number
}

export async function api_get_works(params: WorkQueryParams = {}): Promise<Work[]> {
  const response = await fetch(buildUrl('/work', { skip: 0, limit: 100, ...params }), {
    headers: authHeaders(),
  })
  return handleJson<Work[]>(response, '加载作品列表失败')
}

export async function api_search_works(keyword: string, skip = 0, limit = 50): Promise<Work[]> {
  const response = await fetch(buildUrl('/work/search', { keyword, skip, limit }), {
    headers: authHeaders(),
  })
  return handleJson<Work[]>(response, '搜索作品失败')
}

export async function api_get_work(work_id: number): Promise<Work> {
  const response = await fetch(buildUrl(`/work/${work_id}`), { headers: authHeaders() })
  return handleJson<Work>(response, '加载作品失败')
}

export async function api_create_work(data: WorkCreate): Promise<Work> {
  const response = await fetch(buildUrl('/work/'), {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(data),
  })
  return handleJson<Work>(response, '创建作品失败')
}

export async function api_update_work(work_id: number, data: WorkUpdate): Promise<Work> {
  const response = await fetch(buildUrl(`/work/${work_id}`), {
    method: 'PUT',
    headers: jsonHeaders(),
    body: JSON.stringify(data),
  })
  return handleJson<Work>(response, '更新作品失败')
}

export async function api_delete_work(work_id: number): Promise<Work> {
  const response = await fetch(buildUrl(`/work/${work_id}`), {
    method: 'DELETE',
    headers: authHeaders(),
  })
  return handleJson<Work>(response, '删除作品失败')
}

// ============================================================================
// Edition, Volumes & TOC API
// ============================================================================

export async function api_get_edition(edition_id: number): Promise<Edition> {
  const response = await fetch(buildUrl(`/edition/${edition_id}`), { headers: authHeaders() })
  return handleJson<Edition>(response, '加载版本失败')
}

export async function api_get_editions_by_work(work_id: number): Promise<Edition[]> {
  const response = await fetch(buildUrl(`/edition/work/${work_id}`), { headers: authHeaders() })
  return handleJson<Edition[]>(response, '加载版本列表失败')
}

export async function api_create_edition(data: EditionCreate): Promise<Edition> {
  const response = await fetch(buildUrl('/edition/'), {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(data),
  })
  return handleJson<Edition>(response, '创建版本失败')
}

export async function api_get_chapter_list(edition_id: number): Promise<ChapterListItem[]> {
  const response = await fetch(buildUrl(`/edition/${edition_id}/chapters`), {
    headers: authHeaders(),
  })
  return handleJson<ChapterListItem[]>(response, '加载章节列表失败')
}

export async function api_get_edition_toc(edition_id: number): Promise<EditionToc> {
  const response = await fetch(buildUrl(`/edition/${edition_id}/toc`), { headers: authHeaders() })
  return handleJson<EditionToc>(response, '加载分卷目录失败')
}

export async function api_auto_volume_edition(
  edition_id: number,
  dry_run = true,
  chapter_chunk_size?: number
): Promise<AutoVolumeResponse> {
  const response = await fetch(buildUrl(`/edition/${edition_id}/auto-volume`), {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ dry_run, chapter_chunk_size }),
  })
  return handleJson<AutoVolumeResponse>(response, '自动分卷失败')
}

export async function api_get_chapter_content(
  edition_id: number,
  chapter_index: number
): Promise<DocumentNode> {
  const response = await fetch(buildUrl(`/edition/${edition_id}/chapter/${chapter_index}`), {
    headers: authHeaders(),
  })
  return handleJson<DocumentNode>(response, '加载章节内容失败')
}

export async function api_get_node(node_id: number, include_content = true): Promise<DocumentNode> {
  const response = await fetch(buildUrl(`/node/${node_id}`, { include_content }), {
    headers: authHeaders(),
  })
  return handleJson<DocumentNode>(response, '加载节点失败')
}

export async function api_update_node(
  node_id: number,
  data: DocumentNodeUpdate
): Promise<DocumentNode> {
  const response = await fetch(buildUrl(`/node/${node_id}`), {
    method: 'PUT',
    headers: jsonHeaders(),
    body: JSON.stringify(data),
  })
  return handleJson<DocumentNode>(response, '更新节点失败')
}

// ============================================================================
// Multi-Format Import API (EPUB / PDF / arXiv)
// ============================================================================

export async function api_import_epub(
  file: File,
  opts: {
    pillar?: string
    reading_track?: string
    work_type?: string
    topic_id?: number
    title?: string
    author?: string
  } = {}
): Promise<MultiFormatImportResponse> {
  const form = new FormData()
  form.append('data', file)
  const response = await fetch(buildUrl('/import/epub', opts), {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })
  return handleJson<MultiFormatImportResponse>(response, 'EPUB 导入失败')
}

export async function api_import_pdf(
  file: File,
  opts: {
    pillar?: string
    reading_track?: string
    work_type?: string
    topic_id?: number
    title?: string
    author?: string
    source_url?: string
  } = {}
): Promise<MultiFormatImportResponse> {
  const form = new FormData()
  form.append('data', file)
  const response = await fetch(buildUrl('/import/pdf', opts), {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })
  return handleJson<MultiFormatImportResponse>(response, 'PDF 导入失败')
}

export async function api_import_arxiv(payload: {
  arxiv_id_or_url: string
  pillar?: string
  reading_track?: string
  topic_id?: number
  download_pdf?: boolean
}): Promise<MultiFormatImportResponse> {
  const response = await fetch(buildUrl('/import/arxiv'), {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(payload),
  })
  return handleJson<MultiFormatImportResponse>(response, 'arXiv 论文导入失败')
}

// ============================================================================
// Cloud Reading Progress & Stats API
// ============================================================================

export async function api_get_reading_overview(): Promise<ReadingOverview> {
  const response = await fetch(buildUrl('/progress/overview'), { headers: authHeaders() })
  return handleJson<ReadingOverview>(response, '加载阅读概览失败')
}

export async function api_get_reading_progress(work_id: number): Promise<ReadingProgress | null> {
  const response = await fetch(buildUrl(`/progress/${work_id}`), { headers: authHeaders() })
  if (response.status === 404) return null
  return handleJson<ReadingProgress>(response, '加载阅读进度失败')
}

export async function api_upsert_reading_progress(
  work_id: number,
  payload: {
    edition_id: number
    node_id?: number
    sort_index: number
    char_offset?: number
    scroll_offset?: number
    page_index?: number
    mode?: string
    client_device?: string
    delta_seconds?: number
  }
): Promise<ReadingProgress> {
  const response = await fetch(buildUrl(`/progress/${work_id}`), {
    method: 'PUT',
    headers: jsonHeaders(),
    body: JSON.stringify({ client_device: 'web', mode: 'scroll', ...payload }),
  })
  return handleJson<ReadingProgress>(response, '同步阅读进度失败')
}

export async function api_record_reading_session(payload: {
  work_id: number
  edition_id: number
  start_node_id?: number
  end_node_id?: number
  duration_sec: number
  chars_read?: number
  source_client?: string
}): Promise<void> {
  await fetch(buildUrl('/progress/session'), {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ source_client: 'web', ...payload }),
  })
}

// ============================================================================
// Content Topics & Rhythm Venture Linkage API
// ============================================================================

export async function api_get_topics(
  params: { pillar?: string; status?: string } = {}
): Promise<ContentTopic[]> {
  const response = await fetch(buildUrl('/topic', params), { headers: authHeaders() })
  return handleJson<ContentTopic[]>(response, '加载专题列表失败')
}

export async function api_create_topic(payload: {
  title: string
  description?: string
  pillar?: string
  rhythm_venture_id?: number | null
  keywords?: string[]
}): Promise<ContentTopic> {
  const response = await fetch(buildUrl('/topic/'), {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(payload),
  })
  return handleJson<ContentTopic>(response, '创建专题失败')
}

export async function api_update_topic(
  topic_id: number,
  payload: {
    title?: string
    description?: string
    pillar?: string
    status?: string
    rhythm_venture_id?: number | null
    keywords?: string[]
  }
): Promise<ContentTopic> {
  const response = await fetch(buildUrl(`/topic/${topic_id}`), {
    method: 'PUT',
    headers: jsonHeaders(),
    body: JSON.stringify(payload),
  })
  return handleJson<ContentTopic>(response, '更新专题失败')
}

export async function api_delete_topic(topic_id: number): Promise<void> {
  const response = await fetch(buildUrl(`/topic/${topic_id}`), {
    method: 'DELETE',
    headers: authHeaders(),
  })
  await handleJson(response, '删除专题失败')
}

export async function api_get_topic_detail(topic_id: number): Promise<ContentTopicDetail> {
  const response = await fetch(buildUrl(`/topic/${topic_id}/detail`), { headers: authHeaders() })
  return handleJson<ContentTopicDetail>(response, '加载专题详情失败')
}

export async function api_attach_work_to_topic(
  topic_id: number,
  payload: { work_id: number; role?: string; note?: string }
): Promise<ContentTopicWorkItem> {
  const response = await fetch(buildUrl(`/topic/${topic_id}/works`), {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(payload),
  })
  return handleJson<ContentTopicWorkItem>(response, '关联作品失败')
}

export async function api_detach_work_from_topic(topic_id: number, work_id: number): Promise<void> {
  const response = await fetch(buildUrl(`/topic/${topic_id}/works/${work_id}`), {
    method: 'DELETE',
    headers: authHeaders(),
  })
  await handleJson(response, '移除关联作品失败')
}

export async function api_push_topic_rhythm_task(
  topic_id: number,
  payload: {
    title: string
    description?: string
    work_id?: number
    edition_id?: number
    node_id?: number
    est_minutes?: number
    importance?: number
  }
): Promise<TopicRhythmTaskSummary> {
  const response = await fetch(buildUrl(`/topic/${topic_id}/push-rhythm-task`), {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(payload),
  })
  return handleJson<TopicRhythmTaskSummary>(response, '推送 Rhythm 任务失败')
}

// ============================================================================
// Content Assets & Vault Index API
// ============================================================================

export async function api_list_assets(
  params: { work_id?: number; topic_id?: number; asset_kind?: string } = {}
): Promise<ContentAsset[]> {
  const response = await fetch(buildUrl('/asset', params), { headers: authHeaders() })
  return handleJson<ContentAsset[]>(response, '加载附件失败')
}

export async function api_upload_asset(
  file: File,
  opts: { work_id?: number; topic_id?: number; asset_kind?: string } = {}
): Promise<ContentAsset> {
  const form = new FormData()
  form.append('data', file)
  const response = await fetch(buildUrl('/asset/upload', opts), {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })
  return handleJson<ContentAsset>(response, '上传附件失败')
}

export async function api_delete_asset(asset_id: number): Promise<void> {
  const response = await fetch(buildUrl(`/asset/${asset_id}`), {
    method: 'DELETE',
    headers: authHeaders(),
  })
  await handleJson(response, '删除附件失败')
}

export function getAssetFileUrl(asset: ContentAsset): string {
  return `${SERVER_URL}${asset.file_url}`
}

export async function api_list_vault_notes(
  params: { namespace?: string; pillar?: string; work_id?: number; topic_id?: number } = {}
): Promise<VaultNoteIndexItem[]> {
  const response = await fetch(buildUrl('/vault/index', params), { headers: authHeaders() })
  return handleJson<VaultNoteIndexItem[]>(response, '加载 Vault 索引失败')
}
