/**
 * @file venture_plan_sync.ts
 * @brief Venture 元数据变更后的计划同步辅助
 * @description
 *   当 venture 的目标日、周预算或总预估小时发生变化后，重新触发未来若干天的
 *   plan/day 排程，使事业块能按最新目标日倒排。
 */

import { api_plan_day } from '@lib/api/rhythm'
import type { PlanDayData } from '@lib/data/rhythm'

export interface VenturePlanSyncOptions {
  /** 从今天起重排的天数（默认 1，即仅今天） */
  days?: number
  /**
   * 是否 force 重排（忽略预算不足等软警告）。
   * 目标日缩短等场景应 force；默认 true 保持 M1 行为。
   */
  force?: boolean
}

/**
 * Venture 元数据变更后，从 startDate 起重排 days 天以同步目标日变化。
 * 逐天执行并返回每天的排程结果（含 blocks/warnings/unplaced），供调用方汇总展示。
 */
export async function syncPlanAfterVentureChange(
  startDate: Date | string = new Date(),
  options: VenturePlanSyncOptions = {}
): Promise<PlanDayData[]> {
  const { days = 1, force = true } = options
  const start = new Date(startDate)
  const results: PlanDayData[] = []
  for (let i = 0; i < days; i++) {
    const d = new Date(start)
    d.setDate(d.getDate() + i)
    const result = await api_plan_day(d, { preserve_done: true, force })
    results.push(result)
  }
  return results
}
