/**
 * @file text.ts
 * @brief Text Content API
 * @author sailing-innocent
 * @date 2025-01-29
 */

import type {
  Work,
  WorkCreate,
  Edition,
  EditionCreate,
  DocumentNode,
  DocumentNodeUpdate,
  ChapterListItem,
<<<<<<< HEAD
  ChapterInsertRequest,
  ChapterInsertResponse,
=======
>>>>>>> ai
} from '@lib/data/text'
import { SERVER_URL, API_BASE } from './config'

const TEXT_API_BASE = `${API_BASE}/text`

// ============================================================================
// Work API
// ============================================================================

export async function api_get_works(skip = 0, limit = 20): Promise<Work[]> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/work?skip=${skip}&limit=${limit}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch works: ${response.statusText}`)
  }
  return response.json()
}

export async function api_search_works(keyword: string, skip = 0, limit = 20): Promise<Work[]> {
  const response = await fetch(
    `${SERVER_URL}/${TEXT_API_BASE}/work/search?keyword=${encodeURIComponent(keyword)}&skip=${skip}&limit=${limit}`
  )
  if (!response.ok) {
    throw new Error(`Failed to search works: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_work(work_id: number): Promise<Work> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/work/${work_id}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch work: ${response.statusText}`)
  }
  return response.json()
}

export async function api_create_work(data: WorkCreate): Promise<Work> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/work/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to create work: ${response.statusText}`)
  }
  return response.json()
}

export async function api_update_work(work_id: number, data: WorkCreate): Promise<Work> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/work/${work_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to update work: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_work(work_id: number): Promise<Work> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/work/${work_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete work: ${response.statusText}`)
  }
  return response.json()
}

// ============================================================================
// Edition API
// ============================================================================

export async function api_get_edition(edition_id: number): Promise<Edition> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/edition/${edition_id}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch edition: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_editions_by_work(work_id: number): Promise<Edition[]> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/edition/work/${work_id}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch editions: ${response.statusText}`)
  }
  return response.json()
}

export async function api_create_edition(data: EditionCreate): Promise<Edition> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/edition/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to create edition: ${response.statusText}`)
  }
  return response.json()
}

export async function api_update_edition(edition_id: number, data: EditionCreate): Promise<Edition> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/edition/${edition_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to update edition: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_edition(edition_id: number): Promise<Edition> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/edition/${edition_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete edition: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_chapter_list(edition_id: number): Promise<ChapterListItem[]> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/edition/${edition_id}/chapters`)
  if (!response.ok) {
    throw new Error(`Failed to fetch chapter list: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_chapter_content(edition_id: number, chapter_index: number): Promise<DocumentNode> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/edition/${edition_id}/chapter/${chapter_index}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch chapter content: ${response.statusText}`)
  }
  return response.json()
}

export async function api_search_content(
  edition_id: number,
  keyword: string,
  skip = 0,
  limit = 50
): Promise<DocumentNode[]> {
  const response = await fetch(
    `${SERVER_URL}/${TEXT_API_BASE}/edition/${edition_id}/search?keyword=${encodeURIComponent(keyword)}&skip=${skip}&limit=${limit}`
  )
  if (!response.ok) {
    throw new Error(`Failed to search content: ${response.statusText}`)
  }
  return response.json()
}

// ============================================================================
// Document Node API
// ============================================================================

export async function api_get_node(node_id: number, include_content = true): Promise<DocumentNode> {
  const response = await fetch(
    `${SERVER_URL}/${TEXT_API_BASE}/node/${node_id}?include_content=${include_content}`
  )
  if (!response.ok) {
    throw new Error(`Failed to fetch node: ${response.statusText}`)
  }
  return response.json()
}

export async function api_update_node(node_id: number, data: DocumentNodeUpdate): Promise<DocumentNode> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/node/${node_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to update node: ${response.statusText}`)
  }
  return response.json()
}
<<<<<<< HEAD

// ============================================================================
// Chapter Insert API
// ============================================================================

export async function api_insert_chapter(
  edition_id: number,
  data: Omit<ChapterInsertRequest, 'edition_id'>
): Promise<ChapterInsertResponse> {
  const response = await fetch(`${SERVER_URL}/${TEXT_API_BASE}/edition/${edition_id}/chapter/insert`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...data, edition_id }),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to insert chapter: ${response.statusText} - ${errorText}`)
  }
  return response.json()
}
=======
>>>>>>> ai
