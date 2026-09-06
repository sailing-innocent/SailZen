/**
 * @file rhythm.test.ts
 * @brief Rhythm store 错误分片隔离与 dashboard 聚合测试
 */

import { useRhythmStore } from './rhythm'
import type { AffairData } from '@lib/data/affair'

jest.mock('@lib/api/rhythm', () => ({
  api_get_dashboard: jest.fn(),
  api_get_day_timeline: jest.fn(),
  api_plan_day: jest.fn(),
  api_rebalance_day: jest.fn(),
  api_get_conflicts: jest.fn(),
  api_get_day_review: jest.fn(),
  api_get_week_review: jest.fn(),
  api_update_review_summary: jest.fn(),
  api_get_encroachments: jest.fn(),
  api_get_domain_trend: jest.fn(),
  api_get_today_checkins: jest.fn(),
  api_checkin: jest.fn(),
  api_list_checkins: jest.fn(),
  api_get_energy_profile: jest.fn(),
  api_upsert_energy_profile: jest.fn(),
  api_list_policies: jest.fn(),
  api_create_policy: jest.fn(),
  api_update_policy: jest.fn(),
  api_delete_policy: jest.fn(),
  api_list_templates: jest.fn(),
  api_upsert_template: jest.fn(),
  api_delete_template: jest.fn(),
  api_get_habit_heatmap: jest.fn(),
  api_get_venture_burndown: jest.fn(),
  api_set_block_status: jest.fn(),
  api_move_block: jest.fn(),
  api_create_time_block: jest.fn(),
  api_recalibrate_profile: jest.fn(),
  api_ensure_default_templates: jest.fn(),
}))

jest.mock('@lib/api/affair', () => ({
  api_create_affair: jest.fn(),
  api_update_affair: jest.fn(),
  api_delete_affair: jest.fn(),
  api_transit_affair_state: jest.fn(),
  api_confirm_hint: jest.fn(),
  api_split_affair: jest.fn(),
  api_get_affairs: jest.fn(),
}))

const rhythmApi = jest.requireMock('@lib/api/rhythm') as {
  api_get_dashboard: jest.Mock
  api_get_day_timeline: jest.Mock
  api_plan_day: jest.Mock
  api_recalibrate_profile: jest.Mock
}
const affairApi = jest.requireMock('@lib/api/affair') as {
  api_get_affairs: jest.Mock
}

const makeAffair = (overrides: Partial<AffairData>): AffairData =>
  ({
    id: 1,
    title: 't',
    kind: 'generic',
    state: 'INBOX',
    ...overrides,
  } as AffairData)

const makeDashboard = (overrides: Record<string, unknown> = {}) => ({
  date: '2026-10-26',
  timeline: { date: '2026-10-26', day_id: 1, plan_version: 1, blocks: [] },
  day_review: { scope: 'day', period_key: '2026-10-26' },
  week_review: { scope: 'week', period_key: 'W2026-44' },
  today_checkins: { date: '2026-10-26', precepts: [], habits: [] },
  energy_profile: { id: 1, name: 'default', is_default: true },
  policies: [],
  conflicts: { date: '2026-10-26', encroachments: [] },
  inbox_summary: [],
  overdue_summary: [],
  today_due_summary: [],
  degraded: [],
  ...overrides,
})

describe('rhythm store error sharding', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    useRhythmStore.getState().clearError()
    useRhythmStore.setState({
      dashboard: null,
      dayTimeline: null,
      inbox: [],
      activeAffairs: [],
      allAffairs: [],
      degraded: [],
      isLoading: false,
      error: null,
    })
  })

  it('dashboard failure only sets dashboard shard error', async () => {
    rhythmApi.api_get_dashboard.mockRejectedValue(new Error('dashboard boom'))
    await expect(
      useRhythmStore.getState().fetchDashboard('2026-10-26')
    ).rejects.toThrow('dashboard boom')
    const state = useRhythmStore.getState()
    expect(state.sections.dashboard.error).toContain('dashboard boom')
    // 其他分片不被污染
    expect(state.sections.timeline.error).toBeNull()
    expect(state.sections.affairs.error).toBeNull()
    expect(state.sections.checkins.error).toBeNull()
  })

  it('timeline failure does not pollute dashboard shard', async () => {
    rhythmApi.api_get_day_timeline.mockRejectedValue(new Error('timeline boom'))
    await expect(
      useRhythmStore.getState().fetchDayTimeline('2026-10-26')
    ).rejects.toThrow('timeline boom')
    const state = useRhythmStore.getState()
    expect(state.sections.timeline.error).toContain('timeline boom')
    expect(state.sections.dashboard.error).toBeNull()
  })

  it('retrySection re-runs the shard fetch', async () => {
    rhythmApi.api_get_day_timeline
      .mockRejectedValueOnce(new Error('timeline boom'))
      .mockResolvedValueOnce({ date: '2026-10-26', day_id: 1, plan_version: 1, blocks: [] })
    const store = useRhythmStore.getState()
    await expect(store.fetchDayTimeline('2026-10-26')).rejects.toThrow()
    expect(useRhythmStore.getState().sections.timeline.error).toContain('timeline boom')
    await store.retrySection('timeline')
    const state = useRhythmStore.getState()
    expect(state.sections.timeline.error).toBeNull()
    expect(state.dayTimeline).not.toBeNull()
  })
})

describe('rhythm store fetchDashboard aggregation', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    useRhythmStore.getState().clearError()
  })

  it('sets inbox from inbox_summary without touching activeAffairs', async () => {
    const inboxAffair = makeAffair({ id: 9, title: '待分拣' })
    const activeAffair = makeAffair({ id: 5, title: '进行中', state: 'ACTIVE' })
    rhythmApi.api_get_dashboard.mockResolvedValue(
      makeDashboard({
        inbox_summary: [{ affair: inboxAffair, reason: 'INBOX 待分拣' }],
      })
    )
    useRhythmStore.setState({ activeAffairs: [activeAffair] })
    await useRhythmStore.getState().fetchDashboard('2026-10-26')
    const state = useRhythmStore.getState()
    expect(state.inbox.map((a) => a.id)).toEqual([9])
    // 修复 I-06：activeAffairs 不再被 inbox_summary 覆盖
    expect(state.activeAffairs.map((a) => a.id)).toEqual([5])
    expect(state.inboxSummary).toHaveLength(1)
    expect(state.degraded).toEqual([])
  })

  it('exposes degraded submodules from backend', async () => {
    rhythmApi.api_get_dashboard.mockResolvedValue(
      makeDashboard({ degraded: ['day_review'] })
    )
    await useRhythmStore.getState().fetchDashboard('2026-10-26')
    expect(useRhythmStore.getState().degraded).toEqual(['day_review'])
  })
})

describe('rhythm store fetchAffairsByKind', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    useRhythmStore.getState().clearError()
  })

  it('single request populates per-kind shards', async () => {
    const venture = makeAffair({ id: 1, kind: 'venture', title: 'V' })
    const habit = makeAffair({ id: 2, kind: 'habit', title: 'H' })
    const oneoff = makeAffair({ id: 3, kind: 'task_oneoff', title: 'T' })
    affairApi.api_get_affairs.mockResolvedValue([venture, habit, oneoff])
    await useRhythmStore.getState().fetchAffairsByKind()
    expect(affairApi.api_get_affairs).toHaveBeenCalledTimes(1)
    const state = useRhythmStore.getState()
    expect(state.ventures.map((a) => a.id)).toEqual([1])
    expect(state.habits.map((a) => a.id)).toEqual([2])
    // task_oneoff 覆盖 I-06：进入 allAffairs/activeAffairs（看板数据源）
    expect(state.allAffairs.map((a) => a.id)).toEqual([1, 2, 3])
    expect(state.activeAffairs.map((a) => a.id)).toEqual([1, 2, 3])
  })
})

describe('rhythm store recalibrateProfile', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('submits current profile and adopts response (is_default cleared by backend)', async () => {
    useRhythmStore.setState({
      energyProfile: {
        id: 1,
        name: 'default',
        is_default: true,
        daily_energy_budget: 120,
      } as never,
    })
    rhythmApi.api_recalibrate_profile.mockResolvedValue({
      id: 1,
      name: 'default',
      is_default: false,
      daily_energy_budget: 120,
    })
    const result = await useRhythmStore.getState().recalibrateProfile()
    expect(rhythmApi.api_recalibrate_profile).toHaveBeenCalledWith(
      expect.objectContaining({ daily_energy_budget: 120 })
    )
    // 不再强制 name: 'default'（后端自行强制），且不再回写 is_default: true
    const passed = rhythmApi.api_recalibrate_profile.mock.calls[0][0] as Record<string, unknown>
    expect(passed.name).toBeUndefined()
    expect(passed.is_default).toBeUndefined()
    expect(result.is_default).toBe(false)
    expect(useRhythmStore.getState().energyProfile?.is_default).toBe(false)
  })
})
