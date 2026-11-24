/**
 * @file user.ts
 * @brief Unified Web UserProfile & Global Inbox Zustand Store + Real-Time User WS Sync
 * @author sailing-innocent
 * @date 2026-11-24
 */

import { create } from 'zustand'
import {
  api_list_user_devices,
  api_register_web_device,
  api_update_user_profile,
  api_user_bootstrap,
  type UserDevice,
  type UserProfile,
  type UserProfileUpdatePayload,
} from '@lib/api/user'
import {
  INBOX_ACTIVE_STATUSES,
  api_inbox_dismiss,
  api_inbox_mark_read,
  api_inbox_read_all,
  api_inbox_reply,
  api_inbox_resolve,
  api_inbox_snooze,
  api_sync_inbox,
  type InboxItem,
} from '@lib/api/inbox'
import { buildUserWsUrl, getWebDeviceId } from '@lib/api/config'

export interface UserInboxState {
  // User 面（单用户免登录静默引导）
  bootstrapped: boolean
  authMode: string
  requiresLogin: boolean
  profile: UserProfile | null
  devices: UserDevice[]
  onlineDeviceCount: number
  wsConnected: boolean

  // 统一收件箱状态（单调游标对账）
  itemsById: Record<number, InboxItem>
  latestSyncSeq: number
  unreadCount: number
  activeCount: number
  loadingInbox: boolean
  inboxVersion: number // 递增触发 /tick 与 /health 教练面板联动刷新

  // Actions
  bootstrap: () => Promise<void>
  refreshProfile: () => Promise<void>
  updateProfile: (payload: UserProfileUpdatePayload) => Promise<UserProfile | null>
  syncInbox: (full?: boolean) => Promise<void>
  replyItem: (itemId: number, reply: string, source?: string) => Promise<void>
  resolveItem: (itemId: number, summary?: string, source?: string) => Promise<void>
  snoozeItem: (
    itemId: number,
    option?: '15m' | '1h' | 'tonight' | 'tomorrow' | '24h',
  ) => Promise<void>
  dismissItem: (itemId: number, reason?: string) => Promise<void>
  markRead: (itemId: number) => Promise<void>
  markAllRead: () => Promise<void>
  connectWs: () => void
  disconnectWs: () => void
}

let wsInstance: WebSocket | null = null
let wsReconnectTimer: ReturnType<typeof setTimeout> | null = null
let wsPingTimer: ReturnType<typeof setInterval> | null = null
let wsStopped = false

function recomputeCounts(itemsById: Record<number, InboxItem>): {
  activeCount: number
  unreadCount: number
} {
  let activeCount = 0
  let unreadCount = 0
  for (const item of Object.values(itemsById)) {
    if (INBOX_ACTIVE_STATUSES.has(item.status)) {
      activeCount++
      if (!item.is_read) {
        unreadCount++
      }
    }
  }
  return { activeCount, unreadCount }
}

export const useUserInboxStore = create<UserInboxState>((set, get) => ({
  bootstrapped: false,
  authMode: 'single_user_auto',
  requiresLogin: false,
  profile: null,
  devices: [],
  onlineDeviceCount: 0,
  wsConnected: false,

  itemsById: {},
  latestSyncSeq: 0,
  unreadCount: 0,
  activeCount: 0,
  loadingInbox: false,
  inboxVersion: 0,

  bootstrap: async () => {
    try {
      const boot = await api_user_bootstrap()
      set({
        bootstrapped: true,
        authMode: boot.auth_mode,
        requiresLogin: boot.requires_login,
        profile: boot.user,
        devices: boot.devices,
        onlineDeviceCount: boot.online_device_count,
        unreadCount: boot.unread_inbox_count,
        activeCount: boot.active_inbox_count,
      })
      // 静默注册浏览器设备 + 拉取全量收件箱 + 建立 WS 同步
      api_register_web_device(getWebDeviceId()).catch(() => {})
      await get().syncInbox(true)
      get().connectWs()
    } catch (err) {
      console.warn('[UserInboxStore] bootstrap skipped:', err)
      set({ bootstrapped: true })
    }
  },

  refreshProfile: async () => {
    try {
      const [boot, devices] = await Promise.all([
        api_user_bootstrap(),
        api_list_user_devices().catch(() => get().devices),
      ])
      set({
        profile: boot.user,
        devices,
        onlineDeviceCount: boot.online_device_count,
      })
    } catch (err) {
      console.warn('[UserInboxStore] refreshProfile failed:', err)
    }
  },

  updateProfile: async (payload) => {
    const updated = await api_update_user_profile(payload)
    set({ profile: updated })
    return updated
  },

  syncInbox: async (full = false) => {
    set({ loadingInbox: true })
    try {
      const since = full ? 0 : get().latestSyncSeq
      const res = await api_sync_inbox(since, 200)
      const nextMap: Record<number, InboxItem> = full ? {} : { ...get().itemsById }
      for (const item of res.changes) {
        nextMap[item.id] = item
      }
      // 兜底对账：本地仍为活跃态但不在服务端 active_ids 中的条目自动标为 resolved
      const activeSet = new Set(res.active_ids)
      for (const [idStr, item] of Object.entries(nextMap)) {
        if (INBOX_ACTIVE_STATUSES.has(item.status) && !activeSet.has(item.id)) {
          nextMap[Number(idStr)] = { ...item, status: 'resolved', is_read: true }
        }
      }
      set((s) => ({
        itemsById: nextMap,
        latestSyncSeq: Math.max(s.latestSyncSeq, res.latest_seq),
        unreadCount: res.unread_count,
        activeCount: res.active_count,
        loadingInbox: false,
        inboxVersion: s.inboxVersion + 1,
      }))
    } catch (err) {
      console.warn('[UserInboxStore] syncInbox failed:', err)
      set({ loadingInbox: false })
    }
  },

  replyItem: async (itemId, reply, source = 'web:inbox') => {
    const updated = await api_inbox_reply(itemId, reply, source)
    set((s) => {
      const nextMap = { ...s.itemsById, [updated.id]: updated }
      const counts = recomputeCounts(nextMap)
      return {
        itemsById: nextMap,
        latestSyncSeq: Math.max(s.latestSyncSeq, updated.sync_seq),
        ...counts,
        inboxVersion: s.inboxVersion + 1,
      }
    })
  },

  resolveItem: async (itemId, summary = '', source = 'web:inbox') => {
    const updated = await api_inbox_resolve(itemId, summary, source)
    set((s) => {
      const nextMap = { ...s.itemsById, [updated.id]: updated }
      const counts = recomputeCounts(nextMap)
      return {
        itemsById: nextMap,
        latestSyncSeq: Math.max(s.latestSyncSeq, updated.sync_seq),
        ...counts,
        inboxVersion: s.inboxVersion + 1,
      }
    })
  },

  snoozeItem: async (itemId, option = '24h') => {
    const updated = await api_inbox_snooze(itemId, option)
    set((s) => {
      const nextMap = { ...s.itemsById, [updated.id]: updated }
      const counts = recomputeCounts(nextMap)
      return {
        itemsById: nextMap,
        latestSyncSeq: Math.max(s.latestSyncSeq, updated.sync_seq),
        ...counts,
        inboxVersion: s.inboxVersion + 1,
      }
    })
  },

  dismissItem: async (itemId, reason = '') => {
    const updated = await api_inbox_dismiss(itemId, reason)
    set((s) => {
      const nextMap = { ...s.itemsById, [updated.id]: updated }
      const counts = recomputeCounts(nextMap)
      return {
        itemsById: nextMap,
        latestSyncSeq: Math.max(s.latestSyncSeq, updated.sync_seq),
        ...counts,
        inboxVersion: s.inboxVersion + 1,
      }
    })
  },

  markRead: async (itemId) => {
    const updated = await api_inbox_mark_read(itemId)
    set((s) => {
      const nextMap = { ...s.itemsById, [updated.id]: updated }
      const counts = recomputeCounts(nextMap)
      return {
        itemsById: nextMap,
        latestSyncSeq: Math.max(s.latestSyncSeq, updated.sync_seq),
        ...counts,
      }
    })
  },

  markAllRead: async () => {
    await api_inbox_read_all()
    await get().syncInbox(false)
  },

  connectWs: () => {
    if (typeof window === 'undefined' || typeof WebSocket === 'undefined') return
    if (wsInstance && (wsInstance.readyState === WebSocket.OPEN || wsInstance.readyState === WebSocket.CONNECTING)) {
      return
    }
    const url = buildUserWsUrl()
    if (!url) return
    wsStopped = false

    try {
      const ws = new WebSocket(url)
      wsInstance = ws

      ws.onopen = () => {
        set({ wsConnected: true })
        if (wsPingTimer) clearInterval(wsPingTimer)
        wsPingTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, 30000)
      }

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(String(ev.data)) as {
            type?: string
            data?: Record<string, unknown>
          }
          if (!msg || !msg.type) return

          if (msg.type === 'connected') {
            const serverSeq = Number(msg.data?.latest_sync_seq ?? 0)
            if (serverSeq > get().latestSyncSeq) {
              get().syncInbox(false)
            }
          } else if (msg.type === 'inbox.item_upserted' && msg.data) {
            const item = msg.data as unknown as InboxItem
            if (typeof item.id === 'number') {
              set((s) => {
                const nextMap = { ...s.itemsById, [item.id]: item }
                const counts = recomputeCounts(nextMap)
                return {
                  itemsById: nextMap,
                  latestSyncSeq: Math.max(s.latestSyncSeq, item.sync_seq || 0),
                  ...counts,
                  inboxVersion: s.inboxVersion + 1,
                }
              })
            }
          } else if (msg.type === 'inbox.item_resolved' && msg.data) {
            const itemId = Number(msg.data.inbox_item_id ?? 0)
            const seq = Number(msg.data.sync_seq ?? 0)
            if (itemId > 0) {
              set((s) => {
                const existing = s.itemsById[itemId]
                const nextMap = { ...s.itemsById }
                if (existing) {
                  nextMap[itemId] = {
                    ...existing,
                    status: (String(msg.data?.status || 'resolved') as InboxItem['status']),
                    is_read: true,
                    sync_seq: Math.max(existing.sync_seq, seq),
                    resolution_source: String(msg.data?.resolution_source || existing.resolution_source || ''),
                    resolution_summary: String(msg.data?.resolution_summary || existing.resolution_summary || ''),
                    reply_text:
                      msg.data?.reply_text !== undefined
                        ? (msg.data.reply_text as string | null)
                        : existing.reply_text,
                  }
                }
                const counts = recomputeCounts(nextMap)
                return {
                  itemsById: nextMap,
                  latestSyncSeq: Math.max(s.latestSyncSeq, seq),
                  ...counts,
                  inboxVersion: s.inboxVersion + 1,
                }
              })
            } else {
              get().syncInbox(false)
            }
          } else if (msg.type === 'profile.updated' && msg.data) {
            set({ profile: msg.data as unknown as UserProfile })
          }
        } catch {
          // ignore malformed frames
        }
      }

      ws.onclose = () => {
        wsInstance = null
        set({ wsConnected: false })
        if (wsPingTimer) {
          clearInterval(wsPingTimer)
          wsPingTimer = null
        }
        if (!wsStopped) {
          if (wsReconnectTimer) clearTimeout(wsReconnectTimer)
          wsReconnectTimer = setTimeout(() => {
            get().connectWs()
          }, 5000)
        }
      }

      ws.onerror = () => {
        // onclose handles reconnect
      }
    } catch {
      // ignore ws init error in restricted environments
    }
  },

  disconnectWs: () => {
    wsStopped = true
    if (wsReconnectTimer) {
      clearTimeout(wsReconnectTimer)
      wsReconnectTimer = null
    }
    if (wsPingTimer) {
      clearInterval(wsPingTimer)
      wsPingTimer = null
    }
    if (wsInstance) {
      wsInstance.close()
      wsInstance = null
    }
    set({ wsConnected: false })
  },
}))
