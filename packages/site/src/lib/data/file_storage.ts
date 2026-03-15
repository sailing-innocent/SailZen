/**
 * @file file_storage.ts
 * @brief File Storage Data Types
 * @author sailing-innocent
 * @date 2026-03-14
 */

export interface FileUploadResponse {
  filename: string
  original_name: string
  size: number
  message: string
}

export interface FileInfo {
  filename: string
  original_name: string
  size: number
  created_at: string
  updated_at: string
}

export interface FileListResponse {
  files: FileInfo[]
  total: number
}

export interface FileDeleteResponse {
  filename: string
  message: string
}

export interface FileContentResponse {
  filename: string
  original_name: string
  content: string
  size: number
}
