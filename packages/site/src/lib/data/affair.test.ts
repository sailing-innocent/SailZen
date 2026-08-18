/**
 * @file affair.test.ts
 * @brief Affair data helpers unit tests
 */

import {
  AffairState,
  projectStateToAffairState,
  missionStateToAffairState,
  parseDdl,
  getDdlTimestamp,
  isAffairOverdue,
  getHoursUntilDeadline,
  formatDeadline,
  getAffairPriority,
} from './affair'

describe('Affair state mapping', () => {
  it('maps project states correctly', () => {
    expect(projectStateToAffairState(0)).toBe(AffairState.ARCHIVED)
    expect(projectStateToAffairState(1)).toBe(AffairState.INBOX)
    expect(projectStateToAffairState(2)).toBe(AffairState.INBOX)
    expect(projectStateToAffairState(3)).toBe(AffairState.ACTIVE)
    expect(projectStateToAffairState(4)).toBe(AffairState.PAUSED)
    expect(projectStateToAffairState(5)).toBe(AffairState.DONE)
    expect(projectStateToAffairState(6)).toBe(AffairState.ARCHIVED)
    expect(projectStateToAffairState(undefined)).toBe(AffairState.INBOX)
  })

  it('maps mission states correctly', () => {
    expect(missionStateToAffairState(0)).toBe(AffairState.INBOX)
    expect(missionStateToAffairState(1)).toBe(AffairState.PLANNED)
    expect(missionStateToAffairState(2)).toBe(AffairState.DOING)
    expect(missionStateToAffairState(3)).toBe(AffairState.DONE)
    expect(missionStateToAffairState(4)).toBe(AffairState.CANCELED)
    expect(missionStateToAffairState(undefined)).toBe(AffairState.INBOX)
  })
})

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
