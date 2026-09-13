/**
 * @file pems.test.ts
 * @brief PEMS API client unit tests（buildUrl 回退回归）
 */

describe('api_get_day_view URL 构造', () => {
  const g = global as unknown as Record<string, unknown>

  afterEach(() => {
    jest.restoreAllMocks()
    delete g['window']
  })

  test('SERVER_URL 未配置时退回 window.location.origin，不抛 Invalid URL', async () => {
    jest.resetModules()
    delete process.env.SERVER_URL
    // 模拟浏览器环境（jest testEnvironment 为 node，需手动注入 window）
    g['window'] = { location: { origin: 'http://same-origin' } }

    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        date: '2026-09-13',
        day_id: 1,
        blocks: [],
        health_signals: [],
        insights: [],
        warnings: [],
        energy_budget: 10,
        energy_available: 5,
        energy_consumed: 3,
        note: '',
      }),
    })
    global.fetch = fetchMock as unknown as typeof fetch

    const { api_get_day_view } = await import('./pems')
    await api_get_day_view('2026-09-13')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const url = fetchMock.mock.calls[0][0] as string
    // 回归点：曾是 new URL(relative) 直接抛 "Failed to construct 'URL': Invalid URL"
    expect(url.startsWith('http://same-origin/api/v1/rhythm/timeline/day-view?')).toBe(true)
    expect(url).toContain('date=2026-09-13')
  })
})
