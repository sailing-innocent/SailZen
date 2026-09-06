/**
 * @file rhythm.test.ts
 * @brief Rhythm Dashboard data type helpers unit tests
 */

import { BlockType, BlockStatus, PolicyRuleType, CheckinResult } from './rhythm'

describe('rhythm data constants', () => {
  test('BlockType values are defined', () => {
    expect(BlockType.WORK_WINDOW).toBe('work_window')
    expect(BlockType.CAREER).toBe('career')
    expect(BlockType.PRECEPT).toBe('precept')
    expect(BlockType.HABIT).toBe('habit')
  })

  test('BlockStatus values are defined', () => {
    expect(BlockStatus.PLANNED).toBe('PLANNED')
    expect(BlockStatus.DONE).toBe('DONE')
    expect(BlockStatus.SKIPPED).toBe('SKIPPED')
  })

  test('PolicyRuleType values are defined', () => {
    expect(PolicyRuleType.PROTECT_WINDOW).toBe('protect_window')
    expect(PolicyRuleType.DOMAIN_CAP).toBe('domain_cap')
  })

  test('CheckinResult values are defined', () => {
    expect(CheckinResult.KEPT).toBe('kept')
    expect(CheckinResult.DONE).toBe('done')
    expect(CheckinResult.MISSED).toBe('missed')
  })
})
