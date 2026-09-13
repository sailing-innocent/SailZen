/**
 * @file config.ts
 * @brief The API Configuration
 * @author sailing-innocent
 * @date 2024-12-26
 */

// 注意：未配置 SERVER_URL 时必须退化为空串（而非 undefined/"undefined" 字符串），
// 使 `${SERVER_URL}/api/...` 退化为同源相对路径；调用方若用 new URL() 需自行传 base。
export const SERVER_URL = process.env.SERVER_URL ?? ''
export const API_BASE = 'api/v1'
export function get_url() {
  return SERVER_URL
}

/**
 * 可选 Bearer Token（对应后端 SAILZEN_API_TOKEN 鉴权）。
 * 在 `.env` 中设置 VITE_SAILZEN_API_TOKEN 后，所有 rhythm API 请求自动携带
 * `Authorization: Bearer <token>`；未设置时不加头（本地开发模式）。
 */
// 模块级 process 声明：tsconfig.app.json 无 node types，而 vite define 在构建期替换该表达式；
// tsconfig.test.json 提供 @types/node，模块内声明优先且兼容两种配置。
declare const process: { env: Record<string, string | undefined> }

export const AUTH_TOKEN = process.env.VITE_SAILZEN_API_TOKEN ?? ''

export const authHeaders = (): Record<string, string> =>
  AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : {}

/** 结构化 API 错误：携带 HTTP 状态码与后端 detail 文本，便于分片错误展示。 */
export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, statusText: string, detail: string) {
    super(`Error ${status} ${statusText}${detail ? ` - ${detail}` : ''}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** 从后端错误响应体解析 detail 文本（Litestar: {"status_code":n,"detail":...}）。 */
export const parseErrorDetail = (text: string): string => {
  if (!text) return ''
  try {
    const parsed = JSON.parse(text)
    if (parsed && typeof parsed === 'object') {
      const detail = (parsed as Record<string, unknown>).detail
      if (typeof detail === 'string') return detail.slice(0, 300)
    }
  } catch {
    // 非 JSON 响应体（如网关错误页），返回截断原文
  }
  return text.slice(0, 300)
}
