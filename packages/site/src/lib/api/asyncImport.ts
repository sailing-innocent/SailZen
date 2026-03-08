/**
 * @file asyncImport.ts
 * @brief Async Import API Client
 * @author sailing-innocent
 * @date 2026-03-08
 */

import {
  ImportTask,
  ImportTaskProgress,
  FileUploadResponse,
  AsyncImportRequest,
  AsyncImportResponse,
} from '../data/text'

const API_BASE = '/api/v1/text/import-async'

/**
 * 上传文件
 */
export async function uploadFile(
  file: File,
  onProgress?: (progress: number) => void
): Promise<FileUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const formData = new FormData()
    formData.append('file', file)
    formData.append('filename', file.name)

    if (onProgress) {
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const progress = Math.round((event.loaded / event.total) * 100)
          onProgress(progress)
        }
      })
    }

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText))
      } else {
        reject(new Error(`Upload failed: ${xhr.statusText}`))
      }
    })

    xhr.addEventListener('error', () => {
      reject(new Error('Upload failed'))
    })

    xhr.open('POST', `${API_BASE}/upload`)
    xhr.send(formData)
  })
}

/**
 * 创建异步导入任务
 */
export async function createImportTask(
  request: AsyncImportRequest
): Promise<AsyncImportResponse> {
  const response = await fetch(`${API_BASE}/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to create import task: ${error}`)
  }

  return response.json()
}

/**
 * 获取导入任务列表
 */
export async function getImportTasks(
  status?: string,
  skip: number = 0,
  limit: number = 20
): Promise<{ tasks: ImportTask[]; total: number }> {
  const params = new URLSearchParams()
  if (status) params.append('status', status)
  params.append('skip', skip.toString())
  params.append('limit', limit.toString())

  const response = await fetch(`${API_BASE}/tasks?${params}`)

  if (!response.ok) {
    throw new Error('Failed to fetch import tasks')
  }

  const data = await response.json()
  return {
    tasks: data.tasks,
    total: data.total,
  }
}

/**
 * 获取导入任务详情
 */
export async function getImportTask(taskId: number): Promise<ImportTask> {
  const response = await fetch(`${API_BASE}/tasks/${taskId}`)

  if (!response.ok) {
    throw new Error('Failed to fetch import task')
  }

  return response.json()
}

/**
 * 取消导入任务
 */
export async function cancelImportTask(taskId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/tasks/${taskId}/cancel`, {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error('Failed to cancel import task')
  }
}

/**
 * 删除导入任务
 */
export async function deleteImportTask(taskId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error('Failed to delete import task')
  }
}
