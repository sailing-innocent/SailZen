/**
 * @file challenge.ts
 * @brief Challenge (打卡挑战) Data Types
 * @description 基于 Project/Mission 体系的通用打卡挑战功能
 * 
 * 设计原则:
 * - Challenge = Project (项目名称遵循 #challenge#<type>#<days>#<title> 格式)
 * - Daily CheckIn = Mission (每天一个任务)
 * - Mission State: PENDING=未打卡, DONE=成功, CANCELED=失败
 */

import { type ProjectData, type MissionData, MissionState } from './project'
import { QBWDate } from '@lib/utils/qbw_date'

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
  id: number              // Project ID
  title: string           // 挑战标题
  type: ChallengeTypeValue
  days: number            // 总天数
  startDate: Date
  endDate: Date
  status: ChallengeStatusValue
  project: ProjectData    // 原始 Project 数据
}

// 每日打卡记录

export enum CheckInStatus {
  PENDING = 'pending',   // 未打卡
  SUCCESS = 'success',   // 成功 (MissionState.DONE)
  FAILED = 'failed',     // 失败 (MissionState.CANCELED)
  FUTURE = 'future',     // 未来日期（还未到）
}

export interface CheckInData {
  day: number             // 第几天 (1-based)
  mission: MissionData    // 原始 Mission 数据
  status: CheckInStatus
  date: Date              // 该天对应的日期
}


export type CheckInStatusValue = typeof CheckInStatus[keyof typeof CheckInStatus]

// 挑战统计
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

/**
 * 构建 Challenge Project 名称
 * 格式: #challenge#<type>#<days>#<title>
 */
export function buildChallengeName(type: ChallengeTypeValue, days: number, title: string): string {
  return `${CHALLENGE_PREFIX}${type}#${days}#${title}`
}

/**
 * 解析 Challenge Project 名称
 */
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
  const title = titleParts.join('#') // 标题中可能包含#

  if (isNaN(days) || !title) {
    return null
  }

  return {
    type: type as ChallengeTypeValue,
    days,
    title,
  }
}

/**
 * 判断是否为 Challenge Project
 */
export function isChallengeProject(name: string): boolean {
  return name.startsWith(CHALLENGE_PREFIX)
}

/**
 * 将 Mission State 转换为 CheckIn Status
 */
export function missionStateToCheckInStatus(
  state: number | undefined,
  isFuture: boolean
): CheckInStatusValue {
  if (isFuture) {
    return CheckInStatus.FUTURE
  }

  switch (state) {
    case MissionState.DONE:
      return CheckInStatus.SUCCESS
    case MissionState.CANCELED:
      return CheckInStatus.FAILED
    case MissionState.PENDING:
    default:
      return CheckInStatus.PENDING
  }
}

/**
 * 将 CheckIn Status 转换为 Mission State
 */
export function checkInStatusToMissionState(status: CheckInStatusValue): number {
  switch (status) {
    case CheckInStatus.SUCCESS:
      return MissionState.DONE
    case CheckInStatus.FAILED:
      return MissionState.CANCELED
    case CheckInStatus.PENDING:
    case CheckInStatus.FUTURE:
    default:
      return MissionState.PENDING
  }
}

/**
 * 计算挑战日期（第N天对应的日期）
 */
export function calculateChallengeDate(startDate: Date, day: number): Date {
  const date = new Date(startDate)
  date.setDate(date.getDate() + (day - 1))
  return date
}

/**
 * 计算当天是第几天
 */
export function calculateCurrentDay(startDate: Date, totalDays: number): number {
  const now = new Date()
  const start = new Date(startDate)
  start.setHours(0, 0, 0, 0)
  const today = new Date(now)
  today.setHours(0, 0, 0, 0)

  const diffDays = Math.floor((today.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return 0 // 还未开始
  if (diffDays >= totalDays) return totalDays + 1 // 已结束
  return diffDays + 1 // 1-based
}

/**
 * 判断某一天是否是未来
 */
export function isFutureDay(startDate: Date, day: number): boolean {
  const targetDate = calculateChallengeDate(startDate, day)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return targetDate > today
}

/**
 * 判断某一天是否是今天
 */
export function isTodayDay(startDate: Date, day: number): boolean {
  const targetDate = calculateChallengeDate(startDate, day)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  targetDate.setHours(0, 0, 0, 0)
  return targetDate.getTime() === today.getTime()
}

/**
 * 将 Date 转换为 QBW 格式 (YYYYQQWW)
 */
export function dateToQBW(date: Date): number {
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  const quarter = Math.floor((month - 1) / 3) + 1

  // 找到该日期所在的双周
  const qbwDate = QBWDate.from_date(date)
  return qbwDate.to_int()
}

/**
 * 将 QBW 格式 (YYYYQQWW) 转换为 Date (返回该双周的开始日期)
 */
export function qbwToDate(qbw: number): Date {
  const qbwDate = QBWDate.from_int(qbw)
  return qbwDate.get_start_date()
}

/**
 * 从 ProjectData 转换为 ChallengeData
 * 使用 QBW 格式的时间
 * @param correctStartDate 可选的正确开始日期（从 missions 推断），如果提供则优先使用
 */
export function projectToChallenge(project: ProjectData, correctStartDate?: Date | null): ChallengeData | null {
  const parsed = parseChallengeName(project.name)
  if (!parsed) {
    return null
  }

  // 使用正确的开始日期（如果提供），否则使用 QBW 格式转换
  const startDate = correctStartDate ?? qbwToDate(project.start_time_qbw)

  // 结束日期根据开始日期和天数计算
  const endDate = new Date(startDate)
  endDate.setDate(endDate.getDate() + parsed.days - 1)
  endDate.setHours(23, 59, 59, 999)

  const now = new Date()

  // 确定状态
  let status: ChallengeStatusValue = ChallengeStatus.ACTIVE
  if (now > endDate) {
    status = ChallengeStatus.COMPLETED
  }

  return {
    id: project.id,
    title: parsed.title,
    type: parsed.type,
    days: parsed.days,
    startDate,
    endDate,
    status,
    project,
  }
}

/**
 * 从 MissionData 列表构建 CheckInData 列表
 */
export function missionsToCheckIns(
  missions: MissionData[],
  startDate: Date
): CheckInData[] {
  // 按 ddl 排序
  const sortedMissions = [...missions].sort((a, b) => {
    const aTime = a.ddl ? new Date(a.ddl).getTime() : 0
    const bTime = b.ddl ? new Date(b.ddl).getTime() : 0
    return aTime - bTime
  })

  return sortedMissions.map((mission, index) => {
    const day = index + 1
    const isFuture = isFutureDay(startDate, day)

    return {
      day,
      mission,
      status: missionStateToCheckInStatus(mission.state, isFuture),
      date: calculateChallengeDate(startDate, day),
    }
  })
}

/**
 * 计算挑战统计
 */
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

/**
 * 获取今日的 Mission ID
 */
export function getTodayMissionId(
  checkIns: CheckInData[],
  startDate: Date
): number | null {
  const todayCheckIn = checkIns.find(c => isTodayDay(startDate, c.day))
  return todayCheckIn ? todayCheckIn.mission.id : null
}

/**
 * 格式化日期显示
 */
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
