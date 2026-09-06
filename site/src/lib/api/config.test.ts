/**
 * @file config.test.ts
 * @brief API config helpers unit tests
 */

import { authHeaders, ApiError, parseErrorDetail } from './config'

describe('authHeaders', () => {
  const original = process.env.VITE_SAILZEN_API_TOKEN

  afterEach(() => {
    if (original === undefined) {
      delete process.env.VITE_SAILZEN_API_TOKEN
    } else {
      process.env.VITE_SAILZEN_API_TOKEN = original
    }
    jest.resetModules()
  })

  test('returns empty object when token unset', async () => {
    delete process.env.VITE_SAILZEN_API_TOKEN
    jest.resetModules()
    const { authHeaders: fresh } = await import('./config')
    expect(fresh()).toEqual({})
  })

  test('returns Bearer header when token set', async () => {
    process.env.VITE_SAILZEN_API_TOKEN = 'secret-token'
    jest.resetModules()
    const { authHeaders: fresh } = await import('./config')
    expect(fresh()).toEqual({ Authorization: 'Bearer secret-token' })
  })

  test('imported singleton reflects env at import time', () => {
    // AUTH_TOKEN 在模块加载时读取；未设置时为空串
    expect(typeof authHeaders()).toBe('object')
  })
})

describe('ApiError', () => {
  test('carries status and detail', () => {
    const err = new ApiError(409, 'updating affair 1: Conflict', '状态冲突')
    expect(err.status).toBe(409)
    expect(err.detail).toBe('状态冲突')
    expect(err.message).toContain('409')
    expect(err.message).toContain('状态冲突')
    expect(err).toBeInstanceOf(Error)
  })
})

describe('parseErrorDetail', () => {
  test('extracts detail from Litestar error body', () => {
    expect(parseErrorDetail('{"status_code":404,"detail":"Affair 1 not found"}')).toBe(
      'Affair 1 not found'
    )
  })

  test('truncates plain text fallback', () => {
    expect(parseErrorDetail('x'.repeat(500))).toHaveLength(300)
  })

  test('returns empty string for empty input', () => {
    expect(parseErrorDetail('')).toBe('')
  })
})
