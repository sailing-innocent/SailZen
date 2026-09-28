/**
 * @file blog.ts
 * @brief Blog API Client
 * @author sailing-innocent
 * @date 2026-05-05
 */

import type {
  BlogUploadResponse,
  BlogListResponse,
  BlogDeleteResponse,
  BlogContentResponse,
} from '@lib/data/blog'
import { SERVER_URL, API_BASE, parseErrorDetail } from './config'

const BLOG_API_BASE = `${API_BASE}/blog`

/** 上传 Markdown 文章 */
export async function api_upload_article(file: File): Promise<BlogUploadResponse> {
  const formData = new FormData()
  formData.append('data', file)
  const response = await fetch(`${SERVER_URL}/${BLOG_API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!response.ok) {
    const detail = parseErrorDetail(await response.text().catch(() => ''))
    throw new Error(detail || `上传失败: ${response.statusText}`)
  }
  return response.json()
}

/** 获取文章列表（按创建时间倒序） */
export async function api_list_articles(): Promise<BlogListResponse> {
  const response = await fetch(`${SERVER_URL}/${BLOG_API_BASE}/list`)
  if (!response.ok) {
    const detail = parseErrorDetail(await response.text().catch(() => ''))
    throw new Error(detail || `获取文章列表失败: ${response.statusText}`)
  }
  return response.json()
}

/** 获取文章 Markdown 原文 */
export async function api_get_article_content(filename: string): Promise<BlogContentResponse> {
  const response = await fetch(
    `${SERVER_URL}/${BLOG_API_BASE}/content/${encodeURIComponent(filename)}`
  )
  if (!response.ok) {
    const detail = parseErrorDetail(await response.text().catch(() => ''))
    throw new Error(detail || `获取文章内容失败: ${response.statusText}`)
  }
  return response.json()
}

/** 下载 Markdown 原文件 */
export function api_download_article(filename: string): void {
  const url = `${SERVER_URL}/${BLOG_API_BASE}/download/${encodeURIComponent(filename)}`
  window.open(url, '_blank')
}

/** 删除文章 */
export async function api_delete_article(filename: string): Promise<BlogDeleteResponse> {
  const response = await fetch(
    `${SERVER_URL}/${BLOG_API_BASE}/delete/${encodeURIComponent(filename)}`,
    {
      method: 'DELETE',
    }
  )
  if (!response.ok) {
    const detail = parseErrorDetail(await response.text().catch(() => ''))
    throw new Error(detail || `删除失败: ${response.statusText}`)
  }
  return response.json()
}
