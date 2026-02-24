/**
 * @file challenge.ts
 * @brief Challenge API - 基于 Project/Mission API 的高层封装
 * @description 提供打卡挑战的语义化 API，底层复用 project/mission API
 */

import {
  type ChallengeCreateProps,
  type ChallengeData,
  type CheckInData,
  type ChallengeStats,
  type ChallengeTypeValue,
  buildChallengeName,
  parseChallengeName,
  projectToChallenge,
  missionsToCheckIns,
  calculateChallengeStats,
  getTodayMissionId,
  ChallengeStatus,
  CheckInStatus,
  ChallengeTypeLabels,
  dateToQBW,
} from '@lib/data/challenge'
import {
  type ProjectCreateProps,
  type MissionCreateProps,
  MissionState,
} from '@lib/data/project'

import {
  api_get_projects,
  api_create_project,
  api_delete_project,
  api_get_missions,
  api_create_mission,
  api_done_mission,
  api_cancel_mission,
  api_pending_mission,
} from './project'

// ============================================
// Challenge API
// ============================================

/**
 * 获取所有挑战（Project 列表中筛选）
 * 注意：这个函数返回的 startDate 可能不准确（基于 QBW 格式）
 * 如果需要精确的日期，请使用 api_get_challenge_detail
 */
export const api_get_challenges = async (): Promise<ChallengeData[]> => {
  const projects = await api_get_projects()
  const challenges: ChallengeData[] = []

  for (const project of projects) {
    const parsed = parseChallengeName(project.name)
    if (!parsed) continue

    // 尝试获取 missions 来确定正确的开始日期
    let correctStartDate: Date | null = null
    try {
      const missions = await api_get_missions(project.id)
      if (missions.length > 0) {
        const sortedMissions = [...missions].sort((a, b) => {
          const aTime = a.ddl ? new Date(a.ddl).getTime() : 0
          const bTime = b.ddl ? new Date(b.ddl).getTime() : 0
          return aTime - bTime
        })
        const firstMission = sortedMissions[0]
        if (firstMission.ddl) {
          const firstDayEnd = new Date(firstMission.ddl)
          correctStartDate = new Date(firstDayEnd.getFullYear(), firstDayEnd.getMonth(), firstDayEnd.getDate())
        }
      }
    } catch (err) {
      console.warn(`Failed to get missions for project ${project.id}:`, err)
    }

    const challenge = projectToChallenge(project, correctStartDate)
    if (challenge) {
      challenges.push(challenge)
    }
  }

  // 按开始时间倒序排列（最新的在前）
  return challenges.sort((a, b) => b.startDate.getTime() - a.startDate.getTime())
}

/**
 * 获取单个挑战详情（含打卡记录）
 */
export const api_get_challenge_detail = async (
  challengeId: number
): Promise<{ challenge: ChallengeData; checkIns: CheckInData[] } | null> => {
  const projects = await api_get_projects()
  const project = projects.find(p => p.id === challengeId)

  if (!project) {
    return null
  }

  // 先获取 missions 来确定正确的开始日期
  const missions = await api_get_missions(challengeId)

  // 从 missions 推断正确的开始日期（第一个 mission 的 ddl 对应的日期即为第一天的结束日期，
  // 因此开始日期是 ddl 对应日期的当天凌晨）
  let correctStartDate: Date | null = null
  if (missions.length > 0) {
    // 按 ddl 排序获取第一个 mission
    const sortedMissions = [...missions].sort((a, b) => {
      const aTime = a.ddl ? new Date(a.ddl).getTime() : 0
      const bTime = b.ddl ? new Date(b.ddl).getTime() : 0
      return aTime - bTime
    })
    const firstMission = sortedMissions[0]
    if (firstMission.ddl) {
      // 第一个 mission 的 ddl 是第一天的 23:59:59
      // 因此开始日期是该日期的当天凌晨
      const firstDayEnd = new Date(firstMission.ddl)
      correctStartDate = new Date(firstDayEnd.getFullYear(), firstDayEnd.getMonth(), firstDayEnd.getDate())
    }
  }

  const challenge = projectToChallenge(project, correctStartDate)
  if (!challenge) {
    return null
  }

  const checkIns = missionsToCheckIns(missions, challenge.startDate)

  return { challenge, checkIns }
}

/**
 * 获取活跃中的挑战
 */
export const api_get_active_challenges = async (): Promise<ChallengeData[]> => {
  const challenges = await api_get_challenges()
  return challenges.filter(c => c.status === ChallengeStatus.ACTIVE)
}

/**
 * 创建新挑战
 * 1. 创建 Project
 * 2. 批量创建 N 个 Mission（每天一个）
 */
export const api_create_challenge = async (
  props: ChallengeCreateProps
): Promise<ChallengeData> => {
  const { title, type, days, startDate, description = '' } = props

  // 1. 计算结束日期
  const endDate = new Date(startDate)
  endDate.setDate(endDate.getDate() + days - 1)
  endDate.setHours(23, 59, 59, 0)

  // 2. 创建 Project (使用 QBW 格式)
  const projectProps: ProjectCreateProps = {
    name: buildChallengeName(type, days, title),
    description: description || `${ChallengeTypeLabels[type]} - ${days}天打卡挑战`,
    start_time_qbw: dateToQBW(startDate),
    end_time_qbw: dateToQBW(endDate),
  }

  const project = await api_create_project(projectProps)

  // 3. 批量创建 Mission（每天一个）
  const missionPromises: Promise<unknown>[] = []

  for (let day = 1; day <= days; day++) {
    // 计算该天的截止日期（当天23:59:59）
    const dayDeadline = new Date(startDate)
    dayDeadline.setDate(dayDeadline.getDate() + (day - 1))
    dayDeadline.setHours(23, 59, 59, 0)

    const missionProps: MissionCreateProps = {
      name: `第${day}天`,
      description: `第 ${day}/${days} 天打卡 - ${title}`,
      parent_id: 0, // 无父任务
      project_id: project.id,
      ddl: Math.floor(dayDeadline.getTime() / 1000),
    }

    missionPromises.push(api_create_mission(missionProps))
  }

  // 等待所有 Mission 创建完成
  await Promise.all(missionPromises)

  // 4. 转换为 ChallengeData 返回
  const challenge = projectToChallenge(project)
  if (!challenge) {
    throw new Error('Failed to create challenge')
  }

  return challenge
}

/**
 * 删除挑战（连同所有 Mission）
 */
export const api_delete_challenge = async (challengeId: number): Promise<boolean> => {
  const result = await api_delete_project(challengeId)
  return result.status === 'success'
}

/**
 * 中止挑战（将所有未完成的 Mission 标记为 CANCELED）
 */
export const api_abort_challenge = async (
  challengeId: number
): Promise<boolean> => {
  const detail = await api_get_challenge_detail(challengeId)
  if (!detail) {
    return false
  }

  const { checkIns } = detail

  // 将所有 PENDING 状态的 Mission 标记为 CANCELED
  const abortPromises = checkIns
    .filter(c => c.status === CheckInStatus.PENDING)
    .map(c => api_cancel_mission(c.mission.id))

  await Promise.all(abortPromises)
  return true
}

// ============================================
// CheckIn API (每日打卡)
// ============================================

/**
 * 今日打卡 - 成功
 */
export const api_check_in_success = async (missionId: number): Promise<void> => {
  await api_done_mission(missionId)
}

/**
 * 今日打卡 - 失败
 */
export const api_check_in_failed = async (missionId: number): Promise<void> => {
  await api_cancel_mission(missionId)
}

/**
 * 重置打卡状态（回到 PENDING）
 */
export const api_reset_check_in = async (missionId: number): Promise<void> => {
  await api_pending_mission(missionId)
}

/**
 * 快速打卡（获取今日任务并标记成功）
 * 适用于用户知道 challengeId 但不知道 missionId 的场景
 */
export const api_quick_check_in = async (
  challengeId: number,
  success: boolean
): Promise<void> => {
  const detail = await api_get_challenge_detail(challengeId)
  if (!detail) {
    throw new Error('Challenge not found')
  }

  const todayMissionId = getTodayMissionId(detail.checkIns, detail.challenge.startDate)
  if (!todayMissionId) {
    throw new Error('No check-in for today')
  }

  if (success) {
    await api_check_in_success(todayMissionId)
  } else {
    await api_check_in_failed(todayMissionId)
  }
}

// ============================================
// 统计 API
// ============================================

/**
 * 获取挑战统计信息
 */
export const api_get_challenge_stats = async (
  challengeId: number
): Promise<ChallengeStats | null> => {
  const detail = await api_get_challenge_detail(challengeId)
  if (!detail) {
    return null
  }

  return calculateChallengeStats(
    detail.checkIns,
    detail.challenge.startDate,
    detail.challenge.days
  )
}


