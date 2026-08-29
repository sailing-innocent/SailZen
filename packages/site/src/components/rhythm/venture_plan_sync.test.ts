/**
 * @file venture_plan_sync.test.ts
 * @brief Venture 计划同步辅助单元测试
 */

import { syncPlanAfterVentureChange } from './venture_plan_sync'

jest.mock('@lib/api/rhythm', () => ({
  api_plan_day: jest.fn(),
}))

const { api_plan_day } = jest.requireMock('@lib/api/rhythm') as {
  api_plan_day: jest.Mock
}

describe('syncPlanAfterVentureChange', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    api_plan_day.mockResolvedValue({ date: '2026-10-26', blocks: [] })
  })

  const calledDate = (n?: number): string => {
    const args = n === undefined ? api_plan_day.mock.calls[0] : api_plan_day.mock.calls[n - 1]
    const d = args[0] as Date
    return d.toISOString().split('T')[0]
  }

  test('calls api_plan_day once for today by default', async () => {
    await syncPlanAfterVentureChange('2026-10-26')
    expect(api_plan_day).toHaveBeenCalledTimes(1)
    expect(calledDate()).toBe('2026-10-26')
    expect(api_plan_day).toHaveBeenCalledWith(expect.any(Date), { preserve_done: true, force: true })
  })

  test('calls api_plan_day for N consecutive days', async () => {
    await syncPlanAfterVentureChange('2026-10-26', 3)
    expect(api_plan_day).toHaveBeenCalledTimes(3)
    expect(calledDate(1)).toBe('2026-10-26')
    expect(calledDate(2)).toBe('2026-10-27')
    expect(calledDate(3)).toBe('2026-10-28')
    expect(api_plan_day).toHaveBeenCalledWith(expect.any(Date), { preserve_done: true, force: true })
  })
})
