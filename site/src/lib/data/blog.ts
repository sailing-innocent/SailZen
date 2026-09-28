/**
 * @file blog.ts
 * @brief Blog Data Types
 * @author sailing-innocent
 * @date 2026-05-05
 */

/** 博客上传响应 */
export interface BlogUploadResponse {
  filename: string
  original_name: string
  title: string
  size: number
  preview_url: string
  message: string
}

/** 博客文章信息 */
export interface BlogArticleInfo {
  filename: string
  original_name: string
  title: string
  size: number
  created_at: string
  updated_at: string
}

/** 博客列表响应 */
export interface BlogListResponse {
  articles: BlogArticleInfo[]
  total: number
}

/** 博客删除响应 */
export interface BlogDeleteResponse {
  filename: string
  message: string
}

/** 博客内容响应 */
export interface BlogContentResponse {
  filename: string
  original_name: string
  title: string
  content: string
  size: number
}
