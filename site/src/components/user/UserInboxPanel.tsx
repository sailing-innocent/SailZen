/**
 * @file UserInboxPanel.tsx
 * @brief 全局统一收件箱抽屉 + UserProfile 设置弹层（供 Pagebar 与 MobileNav 共享）
 * @author sailing-innocent
 * @date 2026-11-24
 */

import React, { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserInboxStore } from '@lib/store/user'
import { INBOX_ACTIVE_STATUSES, type InboxItem } from '@lib/api/inbox'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Bell,
  BellOff,
  Check,
  CheckCheck,
  ExternalLink,
  Inbox,
  RefreshCw,
  Send,
  Smartphone,
  Sparkles,
  User,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react'

const DOMAIN_LABEL: Record<string, string> = {
  sailtick: 'AI 教练',
  rhythm: '节奏',
  health: '健康',
  finance: '财务',
  system: '系统',
  manual: '提醒',
}

const STATUS_LABEL: Record<string, string> = {
  pending: '待触发',
  delivered: '待处理',
  snoozed: '已延后',
  opened: '处理中',
  answered: '已答复',
  resolved: '已完成',
  dismissed: '已忽略',
  expired: '已过期',
  canceled: '已撤销',
}

function formatSourceTag(source: string): string {
  if (!source) return ''
  if (source.startsWith('auto:')) {
    return `自动消解 (${source.replace(/^auto:/, '')})`
  }
  return source
}

export const GlobalInboxDrawerButton: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  const navigate = useNavigate()
  const itemsById = useUserInboxStore((s) => s.itemsById)
  const activeCount = useUserInboxStore((s) => s.activeCount)
  const unreadCount = useUserInboxStore((s) => s.unreadCount)
  const wsConnected = useUserInboxStore((s) => s.wsConnected)
  const loadingInbox = useUserInboxStore((s) => s.loadingInbox)
  const syncInbox = useUserInboxStore((s) => s.syncInbox)
  const replyItem = useUserInboxStore((s) => s.replyItem)
  const resolveItem = useUserInboxStore((s) => s.resolveItem)
  const snoozeItem = useUserInboxStore((s) => s.snoozeItem)
  const dismissItem = useUserInboxStore((s) => s.dismissItem)
  const markAllRead = useUserInboxStore((s) => s.markAllRead)

  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<'active' | 'history'>('active')
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({})
  const [busyId, setBusyId] = useState<number | null>(null)

  const { activeItems, historyItems } = useMemo(() => {
    const all = Object.values(itemsById).sort((a, b) => (b.sync_seq || 0) - (a.sync_seq || 0))
    const act: InboxItem[] = []
    const hist: InboxItem[] = []
    for (const item of all) {
      if (INBOX_ACTIVE_STATUSES.has(item.status)) {
        act.push(item)
      } else {
        hist.push(item)
      }
    }
    return { activeItems: act, historyItems: hist.slice(0, 40) }
  }, [itemsById])

  const handleReply = async (item: InboxItem, explicit?: string) => {
    const text = (explicit ?? replyDrafts[item.id] ?? '').trim()
    if (!text) return
    setBusyId(item.id)
    try {
      await replyItem(item.id, text, 'web:inbox_drawer')
      setReplyDrafts((prev) => ({ ...prev, [item.id]: '' }))
    } finally {
      setBusyId(null)
    }
  }

  const handleAction = async (itemId: number, fn: () => Promise<void>) => {
    setBusyId(itemId)
    try {
      await fn()
    } finally {
      setBusyId(null)
    }
  }

  const jumpToTarget = (item: InboxItem) => {
    const rawLink = typeof item.action_schema?.deep_link === 'string' ? item.action_schema.deep_link : ''
    let target = '/health'
    if (rawLink.startsWith('/health/coach') || item.source_domain === 'sailtick') {
      target = '/tick'
    } else if (rawLink.startsWith('/rhythm') || item.source_domain === 'rhythm') {
      target = '/rhythm'
    } else if (rawLink.startsWith('/health')) {
      target = '/health'
    }
    setOpen(false)
    navigate(target)
  }

  const shownItems = tab === 'active' ? activeItems : historyItems

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        {compact ? (
          <Button variant="ghost" size="icon" className="relative" title="统一收件箱">
            <Inbox className="h-5 w-5" />
            {activeCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-primary text-primary-foreground text-[10px] font-semibold flex items-center justify-center">
                {activeCount > 99 ? '99+' : activeCount}
              </span>
            )}
          </Button>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-between gap-2 h-8 px-2.5 text-xs"
          >
            <span className="flex items-center gap-1.5 truncate">
              <Inbox className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">统一收件箱</span>
            </span>
            <span className="flex items-center gap-1 shrink-0">
              {wsConnected ? (
                <Wifi className="h-3 w-3 text-emerald-500" />
              ) : (
                <WifiOff className="h-3 w-3 text-muted-foreground" />
              )}
              {activeCount > 0 && (
                <Badge variant="default" className="h-4 px-1.5 text-[10px]">
                  {activeCount}
                </Badge>
              )}
            </span>
          </Button>
        )}
      </SheetTrigger>
      <SheetContent side="right" className="w-full sm:max-w-md flex flex-col p-0">
        <SheetHeader className="px-4 pt-4 pb-3 border-b">
          <div className="flex items-center justify-between pr-6">
            <SheetTitle className="flex items-center gap-2 text-base">
              <Bell className="h-4 w-4 text-primary" />
              统一收件箱
              <Badge variant={wsConnected ? 'secondary' : 'outline'} className="text-[10px]">
                {wsConnected ? '多端实时同步' : '离线模式'}
              </Badge>
            </SheetTitle>
            <div className="flex items-center gap-1">
              {unreadCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => markAllRead()}
                >
                  <CheckCheck className="h-3.5 w-3.5 mr-1" />
                  全标已读
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => syncInbox(true)}
                disabled={loadingInbox}
                title="强制全量对账"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loadingInbox ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
          <div className="flex gap-1.5 pt-2">
            <Button
              size="sm"
              variant={tab === 'active' ? 'default' : 'outline'}
              className="h-7 text-xs flex-1"
              onClick={() => setTab('active')}
            >
              待处理 ({activeItems.length})
            </Button>
            <Button
              size="sm"
              variant={tab === 'history' ? 'default' : 'outline'}
              className="h-7 text-xs flex-1"
              onClick={() => setTab('history')}
            >
              已处理 / 自动消解 ({historyItems.length})
            </Button>
          </div>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
          {shownItems.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              {tab === 'active'
                ? '全部消息已清空，多端保持一致 ✓'
                : '暂无最近处理记录'}
            </div>
          ) : (
            shownItems.map((item) => {
              const quickReplies = Array.isArray(item.action_schema?.quick_replies)
                ? (item.action_schema.quick_replies as string[])
                : []
              const allowReply =
                item.item_kind === 'question' || Boolean(item.action_schema?.allow_text_reply)
              const isActive = INBOX_ACTIVE_STATUSES.has(item.status)
              const isBusy = busyId === item.id

              return (
                <div
                  key={item.id}
                  className={`rounded-lg border p-3 space-y-2 text-sm transition-colors ${
                    isActive ? 'bg-card' : 'bg-muted/35 opacity-85'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-medium leading-snug flex items-center gap-1.5">
                      {item.source_domain === 'sailtick' && (
                        <Sparkles className="h-3.5 w-3.5 text-indigo-500 shrink-0" />
                      )}
                      <span>{item.title}</span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Badge variant="outline" className="text-[10px]">
                        {DOMAIN_LABEL[item.source_domain] || item.source_domain}
                      </Badge>
                      <Badge
                        variant={isActive ? 'secondary' : 'outline'}
                        className="text-[10px]"
                      >
                        {STATUS_LABEL[item.status] || item.status}
                      </Badge>
                    </div>
                  </div>

                  {item.body && (
                    <p className="text-xs text-muted-foreground whitespace-pre-wrap line-clamp-4">
                      {item.body}
                    </p>
                  )}

                  {!isActive && (item.resolution_summary || item.resolution_source) && (
                    <div className="rounded bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200/70 dark:border-emerald-900 px-2.5 py-1.5 text-xs text-emerald-800 dark:text-emerald-200 space-y-0.5">
                      {item.resolution_summary && <div>{item.resolution_summary}</div>}
                      {item.resolution_source && (
                        <div className="text-[10px] opacity-75">
                          消解来源：{formatSourceTag(item.resolution_source)}
                        </div>
                      )}
                    </div>
                  )}

                  {isActive && quickReplies.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-0.5">
                      {quickReplies.map((qr) => (
                        <Button
                          key={qr}
                          type="button"
                          size="sm"
                          variant="secondary"
                          className="h-6 text-xs px-2"
                          disabled={isBusy}
                          onClick={() => handleReply(item, qr)}
                        >
                          {qr}
                        </Button>
                      ))}
                    </div>
                  )}

                  {isActive && allowReply && (
                    <div className="flex gap-1.5 pt-0.5">
                      <Input
                        className="h-8 text-xs"
                        placeholder="直接回复，全端同步关闭…"
                        value={replyDrafts[item.id] ?? ''}
                        disabled={isBusy}
                        onChange={(e) =>
                          setReplyDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))
                        }
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleReply(item)
                        }}
                      />
                      <Button
                        size="sm"
                        className="h-8 px-2.5"
                        disabled={isBusy || !(replyDrafts[item.id] ?? '').trim()}
                        onClick={() => handleReply(item)}
                      >
                        <Send className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )}

                  {isActive && (
                    <div className="flex items-center justify-between pt-1 border-t border-border/50">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 px-2 text-xs text-muted-foreground"
                        onClick={() => jumpToTarget(item)}
                      >
                        <ExternalLink className="h-3 w-3 mr-1" />
                        去对应页
                      </Button>
                      <div className="flex items-center gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-2 text-xs"
                          disabled={isBusy}
                          onClick={() =>
                            handleAction(item.id, () => resolveItem(item.id, '在 Web 收件箱完成'))
                          }
                        >
                          <Check className="h-3 w-3 mr-1" />
                          完成
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-2 text-xs"
                          disabled={isBusy}
                          onClick={() => handleAction(item.id, () => snoozeItem(item.id, '1h'))}
                          title="延后 1 小时"
                        >
                          <BellOff className="h-3 w-3 mr-1" />
                          延后
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-2 text-xs text-muted-foreground"
                          disabled={isBusy}
                          onClick={() => handleAction(item.id, () => dismissItem(item.id))}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

export const UserProfileDialogButton: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  const profile = useUserInboxStore((s) => s.profile)
  const devices = useUserInboxStore((s) => s.devices)
  const authMode = useUserInboxStore((s) => s.authMode)
  const updateProfile = useUserInboxStore((s) => s.updateProfile)
  const refreshProfile = useUserInboxStore((s) => s.refreshProfile)

  const [open, setOpen] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [quietEnabled, setQuietEnabled] = useState(true)
  const [quietStart, setQuietStart] = useState('23:00')
  const [quietEnd, setQuietEnd] = useState('08:00')
  const [autoResolve, setAutoResolve] = useState(true)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  const handleOpenChange = (next: boolean) => {
    setOpen(next)
    if (next) {
      refreshProfile()
      setDisplayName(profile?.display_name ?? 'SailZen Owner')
      setQuietEnabled(profile?.quiet_hours?.enabled !== false)
      setQuietStart(profile?.quiet_hours?.start ?? '23:00')
      setQuietEnd(profile?.quiet_hours?.end ?? '08:00')
      setAutoResolve(profile?.notification_prefs?.auto_resolve_on_domain_action !== false)
      setFeedback(null)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setFeedback(null)
    try {
      await updateProfile({
        display_name: displayName.trim() || 'SailZen Owner',
        quiet_hours: {
          enabled: quietEnabled,
          start: quietStart || '23:00',
          end: quietEnd || '08:00',
        },
        notification_prefs: {
          auto_resolve_on_domain_action: autoResolve,
        },
      })
      setFeedback('已保存并同步至所有在线设备 ✓')
    } catch (e) {
      setFeedback(`保存失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        {compact ? (
          <Button variant="ghost" size="icon" title="个人资料与多端设置">
            <User className="h-5 w-5" />
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2 h-8 px-2 text-xs text-muted-foreground hover:text-foreground"
          >
            <User className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate font-medium text-foreground">
              {profile?.display_name || 'SailZen Owner'}
            </span>
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <User className="h-4 w-4 text-primary" />
            用户档案（UserProfile）
          </DialogTitle>
          <DialogDescription>
            当前模式：<span className="font-mono text-xs">{authMode}</span>（单用户免登录自动打开，配置全端同步）
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="up-name">显示名称</Label>
            <Input
              id="up-name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </div>

          <div className="rounded-lg border p-3 space-y-2.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="up-quiet" className="text-sm font-medium">
                全局安静时段（Android / SailTick / Reminder 统一生效）
              </Label>
              <Switch id="up-quiet" checked={quietEnabled} onCheckedChange={setQuietEnabled} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">开始时间</Label>
                <Input
                  value={quietStart}
                  onChange={(e) => setQuietStart(e.target.value)}
                  placeholder="23:00"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">结束时间</Label>
                <Input
                  value={quietEnd}
                  onChange={(e) => setQuietEnd(e.target.value)}
                  placeholder="08:00"
                />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="space-y-0.5 pr-3">
              <div className="text-sm font-medium">业务域动作自动消解收件箱</div>
              <div className="text-xs text-muted-foreground">
                在健康页记录饮食/体重/运动/睡眠后，自动关闭对应提问与提醒并撤回手机通知
              </div>
            </div>
            <Switch checked={autoResolve} onCheckedChange={setAutoResolve} />
          </div>

          <div className="space-y-1.5">
            <div className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
              <Smartphone className="h-3.5 w-3.5" />
              已绑定终端（{devices.length}）
            </div>
            <div className="max-h-32 overflow-y-auto space-y-1">
              {devices.length === 0 ? (
                <div className="text-xs text-muted-foreground">暂无设备记录</div>
              ) : (
                devices.map((d) => (
                  <div
                    key={d.device_id}
                    className="flex items-center justify-between text-xs rounded border px-2.5 py-1.5"
                  >
                    <span className="truncate">
                      {d.device_name || d.device_id} ({d.client_type})
                    </span>
                    <Badge variant={d.is_online ? 'default' : 'secondary'} className="text-[10px]">
                      {d.is_online ? '在线' : '离线'}
                    </Badge>
                  </div>
                ))
              )}
            </div>
          </div>

          {feedback && <div className="text-xs text-emerald-600">{feedback}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            关闭
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? '保存中...' : '保存并同步'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
