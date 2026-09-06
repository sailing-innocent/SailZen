/**
 * @file rhythm.test.ts
 * @brief Rhythm Dashboard API client unit tests
 */

describe('rhythm API client', () => {
  beforeEach(() => {
    jest.resetModules()
    process.env.SERVER_URL = 'http://test-server'
  })

  afterEach(() => {
    jest.restoreAllMocks()
    delete process.env.SERVER_URL
  })

  test('api_get_dashboard sends date query param', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        date: '2026-10-26',
        timeline: { date: '2026-10-26', day_id: 1, plan_version: 1, blocks: [], domain_minutes: { life: 0, work: 0, career: 0 }, energy_consumed: 0, energy_budget: 100, buffer_total_minutes: 0, buffer_free_minutes: 0, warnings: [] },
        day_review: { scope: 'day', period_key: '2026-10-26', rhythm_score: 80 },
        week_review: { scope: 'week', period_key: 'W2026-44', rhythm_score: 75 },
        today_checkins: { date: '2026-10-26', precepts: [], habits: [] },
        energy_profile: { id: 1, name: 'default', is_default: true, daily_energy_budget: 100, curve_template: {}, sleep_start: '23:30', sleep_end: '07:00', work_hours_cap: 8, spare_time_windows: {}, min_buffer_ratio: 0.15, life_weight: 1, work_weight: 1, career_weight: 0.6, score_weights: {} },
        policies: [],
        conflicts: { date: '2026-10-26', encroachments: [] },
        inbox_summary: [],
        overdue_summary: [],
        today_due_summary: [],
      }),
    })
    global.fetch = fetchMock as unknown as typeof fetch

    const { api_get_dashboard } = await import('./rhythm')
    const res = await api_get_dashboard('2026-10-26')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/rhythm/dashboard')
    expect(fetchMock.mock.calls[0][0]).toContain('date=2026-10-26')
    expect(res.timeline.energy_budget).toBe(100)
    expect(res.energy_profile.is_default).toBe(true)
  })

  test('api_plan_day sends preserve_done default true', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ date: '2026-10-26', day_id: 1, plan_version: 2, blocks: [], warnings: [], unplaced: [] }),
    })
    global.fetch = fetchMock as unknown as typeof fetch

    const { api_plan_day } = await import('./rhythm')
    await api_plan_day('2026-10-26')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const init = fetchMock.mock.calls[0][1] as RequestInit
    const body = JSON.parse(init.body as string)
    expect(body).toMatchObject({ date: '2026-10-26', preserve_done: true, force: false })
  })
})
