/**
 * @file venture_plan_sync.ts
 * @brief Venture 元数据变更后的计划同步辅助
 * @description
 *   当 venture 的目标日、周预算或总预估小时发生变化后，重新触发未来若干天的
 *   plan/day 排程，使事业块能按最新目标日倒排。
 */

import { api_plan_day } from '@lib/api/rhythm'

/**
 * Venture 元数据变更后，从今天起重新排程以同步目标日变化。
 * M1：仅重排今天；如需批量可在调用处扩展 days 参数。
 */
export async function syncPlanAfterVentureChange(
  startDate: Date | string = new Date(),
  days = 1
): Promise<void> {
  const start = new Date(startDate)
  for (let i = 0; i < days; i++) {
    const d = new Date(start)
    d.setDate(d.getDate() + i)
    await api_plan_day(d, { preserve_done: true, force: true })
  }
}
