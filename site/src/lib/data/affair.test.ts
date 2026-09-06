/**
 * @file affair.test.ts
 * @brief Affair data helpers unit tests
 */

import {
  AffairState,
  parseDdl,
  getDdlTimestamp,
  isAffairOverdue,
  getHoursUntilDeadline,
  formatDeadline,
  getAffairPriority,
} from './affair'

describe('Affair DDL helpers', () => {
  it('parses ISO datetime', () => {
    const date = parseDdl('2026-10-27T12:00:00Z')
    expect(date).toBeInstanceOf(Date)
    expect(date?.toISOString()).toBe('2026-10-27T12:00:00.000Z')
  })

  it('parses seconds timestamp', () => {
    const nowSeconds = Math.floor(Date.now() / 1000)
    const date = parseDdl(nowSeconds)
    expect(date).toBeInstanceOf(Date)
    expect(getDdlTimestamp(date)).toBe(nowSeconds)
  })

  it('returns null for invalid values', () => {
    expect(parseDdl(null)).toBeNull()
    expect(parseDdl(undefined)).toBeNull()
    expect(parseDdl('')).toBeNull()
    expect(parseDdl('invalid')).toBeNull()
  })

  it('detects overdue affairs', () => {
    const past = Math.floor(Date.now() / 1000) - 3600
    const future = Math.floor(Date.now() / 1000) + 3600
    expect(isAffairOverdue(past, AffairState.PLANNED)).toBe(true)
    expect(isAffairOverdue(future, AffairState.PLANNED)).toBe(false)
    expect(isAffairOverdue(past, AffairState.DONE)).toBe(false)
    expect(isAffairOverdue(past, AffairState.CANCELED)).toBe(false)
  })

  it('calculates hours until deadline', () => {
    const future = Math.floor(Date.now() / 1000) + 2 * 3600
    const hours = getHoursUntilDeadline(future)
    expect(hours).toBeGreaterThan(1.9)
    expect(hours).toBeLessThan(2.1)
    expect(getHoursUntilDeadline(null)).toBe(Infinity)
  })

  it('formats deadline', () => {
    const past = Math.floor(Date.now() / 1000) - 25 * 3600
    expect(formatDeadline(past)).toMatch(/已逾期 1 天/)

    const future = new Date(Date.now() + 2 * 60 * 60 * 1000)
    expect(formatDeadline(future)).toMatch(/\d+ 小时后/)
  })
})

describe('Affair priority', () => {
  it('returns urgent for overdue', () => {
    const past = Math.floor(Date.now() / 1000) - 60
    expect(getAffairPriority(past, AffairState.PLANNED)).toBe('urgent')
  })

  it('returns low for done', () => {
    expect(getAffairPriority(null, AffairState.DONE)).toBe('low')
  })
})

describe('syncVentureTargetDate', () => {
  it('sets urgency_ddl to 00:00 of target_date when target set', async () => {
    const { syncVentureTargetDate, defaultVentureMeta } = await import('./affair')
    const patch = syncVentureTargetDate({
      ...defaultVentureMeta(),
      target_date: '2028-04-19',
    })
    expect(patch.clear_urgency_ddl).toBeUndefined()
    expect(patch.urgency_ddl).toBeDefined()
    // DDL 归一化到目标日 00:00（本地时区）
    const ddl = new Date(patch.urgency_ddl!)
    expect(ddl.getHours()).toBe(0)
    expect(ddl.getMinutes()).toBe(0)
    expect(patch.kind_meta.target_date).toBe('2028-04-19')
  })

  it('sends clear_urgency_ddl when target_date cleared', async () => {
    const { syncVentureTargetDate, defaultVentureMeta } = await import('./affair')
    const patch = syncVentureTargetDate({ ...defaultVentureMeta(), target_date: null })
    expect(patch.clear_urgency_ddl).toBe(true)
    expect(patch.urgency_ddl).toBeUndefined()
    expect(patch.kind_meta.target_date).toBeNull()
  })

  it('keeps other meta fields intact', async () => {
    const { syncVentureTargetDate, defaultVentureMeta } = await import('./affair')
    const patch = syncVentureTargetDate({
      ...defaultVentureMeta(),
      target_date: '2029-01-01',
      weekly_budget_hours: 10,
      total_est_hours: 120,
    })
    expect(patch.kind_meta.weekly_budget_hours).toBe(10)
    expect(patch.kind_meta.total_est_hours).toBe(120)
  })
})
