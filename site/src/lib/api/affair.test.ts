/**
 * @file affair.test.ts
 * @brief Rhythm Affair API client unit tests
 */

describe('api_get_affairs query parameters', () => {
  beforeEach(() => {
    jest.resetModules()
    process.env.SERVER_URL = 'http://test-server'
  })

  afterEach(() => {
    jest.restoreAllMocks()
    delete process.env.SERVER_URL
  })

  test('sends multi-valued kind as repeated query params, not comma-separated', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ affairs: [], total: 0 }),
    })
    global.fetch = fetchMock as unknown as typeof fetch

    const { api_get_affairs } = await import('./affair')
    await api_get_affairs({
      kind: ['venture', 'task_oneoff'],
      state: 'INBOX',
      domain: 'work',
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('kind=venture')
    expect(url).toContain('kind=task_oneoff')
    expect(url).not.toContain('kind=venture,task_oneoff')
    expect(url).toContain('state=INBOX')
    expect(url).toContain('domain=work')
  })

  test('sends multi-valued state/domain as repeated query params in one request', async () => {
    // 后端 list_affairs_impl 的 state/domain/kind 均支持多值数组，
    // 无需 state×domain 笛卡尔积循环，单请求即可拿到并集。
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ affairs: [], total: 0 }),
    })
    global.fetch = fetchMock as unknown as typeof fetch

    const { api_get_affairs } = await import('./affair')
    await api_get_affairs({
      kind: 'venture',
      state: ['INBOX', 'ACTIVE'],
      domain: ['work', 'career'],
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const url = fetchMock.mock.calls[0][0] as string

    // state/domain 以重复 query param 传递多值
    expect(url).toContain('state=INBOX')
    expect(url).toContain('state=ACTIVE')
    expect(url).toContain('domain=work')
    expect(url).toContain('domain=career')
    expect(url).not.toContain('state=INBOX,ACTIVE')
    expect(url).toContain('kind=venture')
  })
})
