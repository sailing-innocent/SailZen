/**
 * @file challenge.ts
 * @brief Challenge API — Rhythm Affair 版
 * @description
 *   打卡挑战的高层封装。底层使用 /api/v1/rhythm/affair/* 接口：
 *   - 挑战根 = task_oneoff affair（domain=life, title 带 #challenge#...）
 *   - 每日打卡 = 子 task_oneoff affair（parent_id=根）
 */

import {
  type ChallengeCreateProps,
  type ChallengeData,
  type CheckInData,
  type ChallengeStats,
  type ChallengeTypeValue,
  buildChallengeName,
  parseChallengeName,
  rootAffairToChallenge,
  childAffairsToCheckIns,
  calculateChallengeStats,
  getTodayAffairId,
  ChallengeStatus,
  CheckInStatus,
  ChallengeTypeLabels,
} from '@lib/data/challenge'
import { AffairState } from '@lib/data/affair'
import type { AffairData, AffairCreateProps } from '@lib/data/affair'

import {
  api_get_affairs,
  api_get_affair,
  api_create_affair,
  api_delete_affair,
  api_transit_affair_state,
} from './affair'

const CHALLENGE_KIND = 'task_oneoff' as const
const CHALLENGE_DOMAIN = 'life' as const

// ============================================
// Challenge API
// ============================================

export const api_get_challenges = async (): Promise<ChallengeData[]> => {
  // 拉取所有 challenge 根（life 域的 task_oneoff，title 带前缀）
  const roots = await api_get_affairs({
    kind: CHALLENGE_KIND,
    domain: CHALLENGE_DOMAIN,
  })
  const challenges: ChallengeData[] = []

  for (const root of roots) {
    if (!parseChallengeName(root.title)) continue
    const children = await api_get_affairs({ parent_id: root.id })
    const challenge = rootAffairToChallenge(root, children)
    if (challenge) {
      challenges.push(challenge)
    }
  }

  return challenges.sort((a, b) => b.startDate.getTime() - a.startDate.getTime())
}

export const api_get_challenge_detail = async (
  challengeId: number
): Promise<{ challenge: ChallengeData; checkIns: CheckInData[] } | null> => {
  const root = await api_get_affair(challengeId)
  if (!root) return null

  const parsed = parseChallengeName(root.title)
  if (!parsed) return null

  const children = await api_get_affairs({ parent_id: root.id })
  const challenge = rootAffairToChallenge(root, children)
  if (!challenge) return null

  const checkIns = childAffairsToCheckIns(children, challenge.startDate, challenge.days, root.id)
  return { challenge, checkIns }
}

export const api_get_active_challenges = async (): Promise<ChallengeData[]> => {
  const challenges = await api_get_challenges()
  return challenges.filter(c => c.status === ChallengeStatus.ACTIVE)
}

export const api_create_challenge = async (
  props: ChallengeCreateProps
): Promise<ChallengeData> => {
  const { title, type, days, startDate, description = '' } = props
  const endDate = new Date(startDate)
  endDate.setDate(endDate.getDate() + days - 1)
  endDate.setHours(23, 59, 59, 0)

  // 1. 创建挑战根 affair
  const rootProps: AffairCreateProps = {
    title: buildChallengeName(type, days, title),
    description: description || `${ChallengeTypeLabels[type]} - ${days}天打卡挑战`,
    kind: CHALLENGE_KIND,
    domain: CHALLENGE_DOMAIN,
    urgency_ddl: Math.floor(endDate.getTime() / 1000),
  }
  const root = await api_create_affair(rootProps)

  // 2. 批量创建每日子 affair
  const childPromises: Promise<AffairData>[] = []
  for (let day = 1; day <= days; day++) {
    const dayDeadline = new Date(startDate)
    dayDeadline.setDate(dayDeadline.getDate() + (day - 1))
    dayDeadline.setHours(23, 59, 59, 0)

    const childProps: AffairCreateProps = {
      title: `第${day}天`,
      description: `第 ${day}/${days} 天打卡 - ${title}`,
      kind: CHALLENGE_KIND,
      domain: CHALLENGE_DOMAIN,
      parent_id: root.id,
      urgency_ddl: Math.floor(dayDeadline.getTime() / 1000),
    }
    childPromises.push(api_create_affair(childProps))
  }

  await Promise.all(childPromises)

  const children = await api_get_affairs({ parent_id: root.id })
  const challenge = rootAffairToChallenge(root, children)
  if (!challenge) {
    throw new Error('Failed to create challenge')
  }
  return challenge
}

export const api_delete_challenge = async (challengeId: number): Promise<boolean> => {
  // 先删除所有子 affair，再删除根（后端未级联时兜底）
  const children = await api_get_affairs({ parent_id: challengeId })
  await Promise.all(children.map(c => api_delete_affair(c.id)))
  const result = await api_delete_affair(challengeId)
  return result.status === 'success'
}

export const api_abort_challenge = async (
  challengeId: number
): Promise<boolean> => {
  const detail = await api_get_challenge_detail(challengeId)
  if (!detail) {
    return false
  }

  const { checkIns } = detail
  const pendingCheckIns = checkIns.filter(c => c.status === CheckInStatus.PENDING && c.affair.id > 0)
  await Promise.all(
    pendingCheckIns.map(c =>
      api_transit_affair_state(c.affair.id, 'cancel')
    )
  )
  return true
}

// ============================================
// CheckIn API
// ============================================

export const api_check_in_success = async (affairId: number): Promise<void> => {
  await api_transit_affair_state(affairId, 'finish')
}

export const api_check_in_failed = async (affairId: number): Promise<void> => {
  await api_transit_affair_state(affairId, 'cancel')
}

export const api_reset_check_in = async (affairId: number): Promise<void> => {
  // DONE/CANCELED 在 Affair 中为终态，无法回退。
  // 这里删除旧的终态子 affair，并创建新的 INBOX 子 affair 来"重置"。
  const original = await api_get_affair(affairId)
  if (!original) return

  await api_delete_affair(affairId)

  const childProps: AffairCreateProps = {
    title: original.title,
    description: original.description,
    kind: CHALLENGE_KIND,
    domain: CHALLENGE_DOMAIN,
    parent_id: original.parent_id,
    urgency_ddl: original.urgency_ddl,
    state: AffairState.INBOX,
  }
  await api_create_affair(childProps)
}

export const api_quick_check_in = async (
  challengeId: number,
  success: boolean
): Promise<void> => {
  const detail = await api_get_challenge_detail(challengeId)
  if (!detail) {
    throw new Error('Challenge not found')
  }

  const todayAffairId = getTodayAffairId(detail.checkIns, detail.challenge.startDate)
  if (!todayAffairId) {
    throw new Error('No check-in for today')
  }

  if (success) {
    await api_check_in_success(todayAffairId)
  } else {
    await api_check_in_failed(todayAffairId)
  }
}

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
