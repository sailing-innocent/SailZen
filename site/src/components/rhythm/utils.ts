/**
 * @file utils.ts
 * @brief Rhythm Dashboard 组件共享工具
 */

import type { TimeBlockData } from '@lib/data/rhythm'

export const formatTime = (iso: string): string => {
  if (!iso) return '--:--'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

export const formatDate = (iso: string): string => {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

export const blockTypeColor = (type: string): string => {
  const map: Record<string, string> = {
    sleep: 'bg-slate-400',
    commute: 'bg-blue-300',
    work_window: 'bg-blue-500',
    micro_rest: 'bg-green-300',
    meal: 'bg-orange-300',
    precept: 'bg-purple-500',
    habit: 'bg-teal-500',
    fixed: 'bg-red-400',
    focus: 'bg-indigo-500',
    light: 'bg-yellow-300',
    career: 'bg-pink-500',
    rest: 'bg-gray-300',
    buffer: 'bg-emerald-200',
    async_kickoff: 'bg-violet-500',
    async_review: 'bg-violet-400',
    async_wait: 'bg-violet-200',
  }
  return map[type] ?? 'bg-gray-400'
}

export const blockTypeLabel = (type: string): string => {
  const map: Record<string, string> = {
    sleep: '睡眠',
    commute: '通勤',
    work_window: '工作窗',
    micro_rest: '微休息',
    meal: '用餐',
    precept: '戒律',
    habit: '习惯',
    fixed: '刚性',
    focus: '专注',
    light: '轻松',
    career: '事业',
    rest: '休息',
    buffer: '缓冲',
    async_kickoff: '回调启动',
    async_review: '回调审阅',
    async_wait: '回调等待',
  }
  return map[type] ?? type
}

export const sortBlocks = (blocks: TimeBlockData[]): TimeBlockData[] => {
  return [...blocks].sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())
}

export const minutesToHours = (minutes: number): number => Math.round((minutes / 60) * 10) / 10
