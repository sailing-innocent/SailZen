/**
 * @file file_storage.ts
 * @brief File Storage API Client
 * @author sailing-innocent
 * @date 2026-03-14
 */

import type {
  FileUploadResponse,
  FileListResponse,
  FileDeleteResponse,
  FileContentResponse,
} from '@lib/data/file_storage'
import { SERVER_URL, API_BASE } from './config'

const FILE_STORAGE_API_BASE = `${API_BASE}/file-storage`

/**
 * 上传文件
 * @param file 要上传的文件（限制1MB）
 * @returns 上传结果
 */
export async function api_upload_file(file: File): Promise<FileUploadResponse> {
  const formData = new FormData()
  formData.append('data', file)

  const response = await fetch(`${SERVER_URL}/${FILE_STORAGE_API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '上传失败' }))
    throw new Error(error.detail || `上传失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 获取文件列表
 * @returns 文件列表
 */
export async function api_list_files(): Promise<FileListResponse> {
  const response = await fetch(`${SERVER_URL}/${FILE_STORAGE_API_BASE}/list`)

  if (!response.ok) {
    throw new Error(`获取文件列表失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 下载文件
 * @param filename 文件名
 */
export function api_download_file(filename: string): void {
  const url = `${SERVER_URL}/${FILE_STORAGE_API_BASE}/download/${encodeURIComponent(filename)}`
  window.open(url, '_blank')
}

/**
 * 获取文件内容（预览）
 * @param filename 文件名
 * @returns 文件内容
 */
export async function api_get_file_content(filename: string): Promise<FileContentResponse> {
  const response = await fetch(
    `${SERVER_URL}/${FILE_STORAGE_API_BASE}/content/${encodeURIComponent(filename)}`
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '获取文件内容失败' }))
    throw new Error(error.detail || `获取文件内容失败: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 删除文件
 * @param filename 文件名
 * @returns 删除结果
 */
export async function api_delete_file(filename: string): Promise<FileDeleteResponse> {
  const response = await fetch(
    `${SERVER_URL}/${FILE_STORAGE_API_BASE}/delete/${encodeURIComponent(filename)}`,
    {
      method: 'DELETE',
    }
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '删除失败' }))
    throw new Error(error.detail || `删除失败: ${response.statusText}`)
  }

  return response.json()
}
