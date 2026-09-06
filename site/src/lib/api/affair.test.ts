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

  test('expands multi-valued state/domain into separate requests', async () => {
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

    expect(fetchMock).toHaveBeenCalledTimes(2 * 2)
    const urls = fetchMock.mock.calls.map((call) => call[0] as string)

    // Each request contains exactly one state and one domain value
    const stateDomainPairs = urls.map((url) => {
      const state = new URL(url).searchParams.get('state')
      const domain = new URL(url).searchParams.get('domain')
      return `${state}:${domain}`
    })
    expect(new Set(stateDomainPairs).size).toBe(4)
    expect(stateDomainPairs).toEqual(
      expect.arrayContaining(['INBOX:work', 'INBOX:career', 'ACTIVE:work', 'ACTIVE:career'])
    )

    // kind is preserved in every request
    for (const url of urls) {
      expect(url).toContain('kind=venture')
    }
  })
})
