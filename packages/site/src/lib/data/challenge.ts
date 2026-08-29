/**
 * @file challenge.ts
 * @brief Challenge (打卡挑战) Data Types — Rhythm Affair 版
 * @description
 *   基于 Rhythm 统一事务模型的打卡挑战功能。
 *   - Challenge 根 = task_oneff affair（domain=life，title 带 #challenge#...）
 *   - 每日打卡 = 子 task_oneoff affair（parent_id=根，第 N 天一个）
 *   - 成功打卡 → 子 affair finish → DONE
 *   - 失败打卡 → 子 affair cancel → CANCELED
 *   - 重置 → 重新创建 INBOX 子 affair（DONE/CANCELED 为终态不可回退）
 */

import { type AffairData, AffairState } from './affair'

// ============================================
// Challenge 类型常量
// ============================================

export const ChallengeType = {
  NO_SNACK: 'no_snack',       // 禁止零食
  NO_SUGAR: 'no_sugar',       // 戒糖
  EARLY_SLEEP: 'early_sleep', // 早睡
  DRINK_WATER: 'drink_water', // 喝水打卡
  EXERCISE: 'exercise',       // 运动打卡
  READING: 'reading',         // 阅读打卡
  MEDITATION: 'meditation',   // 冥想打卡
  CUSTOM: 'custom',           // 自定义
} as const

export type ChallengeTypeValue = typeof ChallengeType[keyof typeof ChallengeType]

export const ChallengeTypeLabels: Record<ChallengeTypeValue, string> = {
  [ChallengeType.NO_SNACK]: '禁止零食',
  [ChallengeType.NO_SUGAR]: '戒糖',
  [ChallengeType.EARLY_SLEEP]: '早睡',
  [ChallengeType.DRINK_WATER]: '喝水打卡',
  [ChallengeType.EXERCISE]: '运动打卡',
  [ChallengeType.READING]: '阅读打卡',
  [ChallengeType.MEDITATION]: '冥想打卡',
  [ChallengeType.CUSTOM]: '自定义',
}

export const ChallengeTypeIcons: Record<ChallengeTypeValue, string> = {
  [ChallengeType.NO_SNACK]: '🍿',
  [ChallengeType.NO_SUGAR]: '🍬',
  [ChallengeType.EARLY_SLEEP]: '😴',
  [ChallengeType.DRINK_WATER]: '💧',
  [ChallengeType.EXERCISE]: '💪',
  [ChallengeType.READING]: '📚',
  [ChallengeType.MEDITATION]: '🧘',
  [ChallengeType.CUSTOM]: '🎯',
}

// ============================================
// Challenge 状态
// ============================================

export const ChallengeStatus = {
  ACTIVE: 'active',       // 进行中
  COMPLETED: 'completed', // 已完成（所有天数结束）
  ABORTED: 'aborted',     // 已中止（用户提前终止）
} as const

export type ChallengeStatusValue = typeof ChallengeStatus[keyof typeof ChallengeStatus]

// ============================================
// Challenge 数据类型
// ============================================

export interface ChallengeCreateProps {
  title: string           // 挑战标题
  type: ChallengeTypeValue // 挑战类型
  days: number            // 挑战天数（默认14天）
  startDate: Date         // 开始日期
  description?: string    // 可选描述
}

export interface ChallengeData {
  id: number              // 根 affair ID
  title: string           // 挑战标题
  type: ChallengeTypeValue
  days: number            // 总天数
  startDate: Date
  endDate: Date
  status: ChallengeStatusValue
  rootAffair: AffairData  // 原始根 affair
}

export enum CheckInStatus {
  PENDING = 'pending',   // 未打卡
  SUCCESS = 'success',   // 成功 (DONE)
  FAILED = 'failed',     // 失败 (CANCELED)
  FUTURE = 'future',     // 未来日期（还未到）
}

export interface CheckInData {
  day: number             // 第几天 (1-based)
  affair: AffairData      // 对应子 affair
  status: CheckInStatus
  date: Date              // 该天对应的日期
}

export type CheckInStatusValue = typeof CheckInStatus[keyof typeof CheckInStatus]

export interface ChallengeStats {
  totalDays: number
  successDays: number
  failedDays: number
  pendingDays: number
  successRate: number // 0-100
  currentDay: number  // 当前是第几天（从1开始，如果已结束则为总天数+1）
  isTodayChecked: boolean
}

// ============================================
// 工具函数
// ============================================

const CHALLENGE_PREFIX = '#challenge#'

export function buildChallengeName(type: ChallengeTypeValue, days: number, title: string): string {
  return `${CHALLENGE_PREFIX}${type}#${days}#${title}`
}

export function parseChallengeName(name: string): { type: ChallengeTypeValue; days: number; title: string } | null {
  if (!name.startsWith(CHALLENGE_PREFIX)) {
    return null
  }

  const parts = name.slice(CHALLENGE_PREFIX.length).split('#')
  if (parts.length < 3) {
    return null
  }

  const [type, daysStr, ...titleParts] = parts
  const days = parseInt(daysStr, 10)
  const title = titleParts.join('#')

  if (isNaN(days) || !title) {
    return null
  }

  return {
    type: type as ChallengeTypeValue,
    days,
    title,
  }
}

/** 判断 affair title 是否为 Challenge 根 */
export function isChallengeAffair(name: string): boolean {
  return name.startsWith(CHALLENGE_PREFIX)
}

export function affairStateToCheckInStatus(
  state: AffairState | undefined,
  isFuture: boolean
): CheckInStatusValue {
  if (isFuture) {
    return CheckInStatus.FUTURE
  }

  switch (state) {
    case AffairState.DONE:
      return CheckInStatus.SUCCESS
    case AffairState.CANCELED:
      return CheckInStatus.FAILED
    case AffairState.INBOX:
    case AffairState.PLANNED:
    case AffairState.SCHEDULED:
    case AffairState.DOING:
    default:
      return CheckInStatus.PENDING
  }
}

export function checkInStatusToAffairState(status: CheckInStatusValue): AffairState {
  switch (status) {
    case CheckInStatus.SUCCESS:
      return AffairState.DONE
    case CheckInStatus.FAILED:
      return AffairState.CANCELED
    case CheckInStatus.PENDING:
    case CheckInStatus.FUTURE:
    default:
      return AffairState.INBOX
  }
}

export function calculateChallengeDate(startDate: Date, day: number): Date {
  const date = new Date(startDate)
  date.setDate(date.getDate() + (day - 1))
  return date
}

export function calculateCurrentDay(startDate: Date, totalDays: number): number {
  const now = new Date()
  const start = new Date(startDate)
  start.setHours(0, 0, 0, 0)
  const today = new Date(now)
  today.setHours(0, 0, 0, 0)

  const diffDays = Math.floor((today.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return 0
  if (diffDays >= totalDays) return totalDays + 1
  return diffDays + 1
}

export function isFutureDay(startDate: Date, day: number): boolean {
  const targetDate = calculateChallengeDate(startDate, day)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return targetDate > today
}

export function isTodayDay(startDate: Date, day: number): boolean {
  const targetDate = calculateChallengeDate(startDate, day)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  targetDate.setHours(0, 0, 0, 0)
  return targetDate.getTime() === today.getTime()
}

/** 从根 affair 和子 affairs 构建 ChallengeData */
export function rootAffairToChallenge(root: AffairData, childAffairs: AffairData[]): ChallengeData | null {
  const parsed = parseChallengeName(root.title)
  if (!parsed) {
    return null
  }

  // 从子 affair 的 urgency_ddl 推断开始/结束日期
  const sortedChildren = [...childAffairs]
    .filter(c => c.parent_id === root.id)
    .sort((a, b) => {
      const aTime = a.urgency_ddl ? new Date(a.urgency_ddl).getTime() : 0
      const bTime = b.urgency_ddl ? new Date(b.urgency_ddl).getTime() : 0
      return aTime - bTime
    })

  let startDate = new Date(root.ctime ?? Date.now())
  if (sortedChildren.length > 0 && sortedChildren[0].urgency_ddl) {
    const firstDdl = new Date(sortedChildren[0].urgency_ddl)
    startDate = new Date(firstDdl.getFullYear(), firstDdl.getMonth(), firstDdl.getDate())
  }

  const endDate = new Date(startDate)
  endDate.setDate(endDate.getDate() + parsed.days - 1)
  endDate.setHours(23, 59, 59, 999)

  const now = new Date()
  let status: ChallengeStatusValue = ChallengeStatus.ACTIVE
  if (now > endDate) {
    status = ChallengeStatus.COMPLETED
  }

  return {
    id: root.id,
    title: parsed.title,
    type: parsed.type,
    days: parsed.days,
    startDate,
    endDate,
    status,
    rootAffair: root,
  }
}

/** 从子 affair 列表构建 CheckInData 列表 */
export function childAffairsToCheckIns(
  childAffairs: AffairData[],
  startDate: Date,
  totalDays: number,
  rootId: number
): CheckInData[] {
  const children = childAffairs
    .filter(c => c.parent_id === rootId)
    .sort((a, b) => {
      const aTime = a.urgency_ddl ? new Date(a.urgency_ddl).getTime() : 0
      const bTime = b.urgency_ddl ? new Date(b.urgency_ddl).getTime() : 0
      return aTime - bTime
    })

  const checkIns: CheckInData[] = []
  for (let day = 1; day <= totalDays; day++) {
    const affair = children[day - 1]
    const isFuture = isFutureDay(startDate, day)
    checkIns.push({
      day,
      affair: affair ?? makePlaceholderChild(rootId, day, startDate),
      status: affair ? affairStateToCheckInStatus(affair.state, isFuture) : CheckInStatus.PENDING,
      date: calculateChallengeDate(startDate, day),
    })
  }
  return checkIns
}

function makePlaceholderChild(rootId: number, day: number, startDate: Date): AffairData {
  const date = calculateChallengeDate(startDate, day)
  const ddl = new Date(date)
  ddl.setHours(23, 59, 59, 999)
  return {
    id: 0,
    title: `第${day}天`,
    description: '',
    kind: 'task_oneoff',
    domain: 'life',
    state: AffairState.INBOX,
    kind_meta: {},
    importance: 3,
    urgency_ddl: ddl.toISOString(),
    energy_cost: 0,
    money_cost: 0,
    budget_id: null,
    est_minutes: 0,
    splittable: false,
    min_chunk_minutes: 30,
    fallback_plan: '',
    recurrence_rule_id: null,
    day_id: null,
    timespan_id: null,
    parent_id: rootId,
    info_collection_type: null,
    ai_hint: {},
    score: 0,
    ref: {},
  }
}

export function calculateChallengeStats(
  checkIns: CheckInData[],
  startDate: Date,
  totalDays: number
): ChallengeStats {
  const successDays = checkIns.filter(c => c.status === CheckInStatus.SUCCESS).length
  const failedDays = checkIns.filter(c => c.status === CheckInStatus.FAILED).length
  const pendingDays = checkIns.filter(c => c.status === CheckInStatus.PENDING).length

  const completedDays = successDays + failedDays
  const successRate = completedDays > 0 ? Math.round((successDays / completedDays) * 100) : 0

  const currentDay = calculateCurrentDay(startDate, totalDays)
  const todayCheckIn = checkIns.find(c => isTodayDay(startDate, c.day))
  const isTodayChecked = todayCheckIn ? todayCheckIn.status !== CheckInStatus.PENDING : false

  return {
    totalDays,
    successDays,
    failedDays,
    pendingDays,
    successRate,
    currentDay,
    isTodayChecked,
  }
}

export function getTodayAffairId(
  checkIns: CheckInData[],
  startDate: Date
): number | null {
  const todayCheckIn = checkIns.find(c => isTodayDay(startDate, c.day))
  return todayCheckIn ? todayCheckIn.affair.id : null
}

export function formatChallengeDate(date: Date): string {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const targetDate = new Date(date.getFullYear(), date.getMonth(), date.getDate())

  if (targetDate.getTime() === today.getTime()) {
    return '今天'
  }

  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  if (targetDate.getTime() === tomorrow.getTime()) {
    return '明天'
  }

  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  if (targetDate.getTime() === yesterday.getTime()) {
    return '昨天'
  }

  return `${date.getMonth() + 1}/${date.getDate()}`
}
