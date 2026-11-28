/**
 * @file tick.tsx
 * @brief SailTick 页面 — AI 教练票据收件箱 + 快速记体重
 * @author sailing-innocent
 * @date 2026-10-27
 *
 * MVP（设计文档 §7）:
 *  - 待回票据列表（按期待回复时间排序）+ 回复框
 *  - 今日计划摘要（最近一条 replied/resolved 票据的 reply 或最近票据提示）
 *  - 快速记体重（调 health body_data API）
 *  - 历史票据折叠区
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import PageLayout from '@components/page_layout'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useIsMobile } from '@/hooks/use-mobile'
import { ImageIntakePanel } from '@components/tick/ImageIntakePanel'
import {
  api_list_tickets,
  api_reply_ticket,
  api_resolve_ticket,
  api_snooze_ticket,
  api_quick_log_weight,
  api_send_coach_message,
  api_list_daily_reports,
  api_list_intake_drafts,
  api_quick_chat,
  api_get_quick_chat_history,
  api_search_memory,
  type DailyReport,
  type ImageIntakeDraft,
  type MemorySearchHit,
  type QuickChatHistoryItem,
  type TickDomain,
  type TickTicket,
  type TicketPriority,
} from '@lib/api/tick'
import { format, isPast } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { MessageCircle, Scale, Check, Clock, BellOff, Send, Moon, Camera, Sparkles, Calendar, Search } from 'lucide-react'
import { useUserInboxStore } from '@lib/store/user'

const TICK_DOMAIN_TABS: Array<{ key: 'all' | TickDomain; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'health', label: '健康教练' },
  { key: 'rhythm', label: '节奏规划师' },
  { key: 'finance', label: '财务秘书' },
  { key: 'general', label: '生活总管' },
]

const DOMAIN_BADGE_LABEL: Record<string, string> = {
  health: '健康',
  rhythm: '规划',
  finance: '财务',
  general: '总管',
}

const PRIORITY_LABEL: Record<TicketPriority, string> = {
  low: '低',
  normal: '普通',
  high: '高',
  urgent: '紧急',
}

const PRIORITY_VARIANT: Record<TicketPriority, 'secondary' | 'default' | 'destructive'> = {
  low: 'secondary',
  normal: 'secondary',
  high: 'default',
  urgent: 'destructive',
}

const TYPE_LABEL: Record<string, string> = {
  question: '提问',
  task: '配合事项',
  approval: '待审批',
  info: '通知',
}

function deadlineLabel(t: TickTicket): string {
  if (!t.expected_reply_by) return '无期限'
  const d = new Date(t.expected_reply_by)
  const overdue = isPast(d) && t.status === 'pending'
  return `${overdue ? '已超期 ' : ''}${format(d, 'MM-dd HH:mm')}`
}

const TickPage: React.FC = () => {
  const isMobile = useIsMobile()
  const [pending, setPending] = useState<TickTicket[]>([])
  const [history, setHistory] = useState<TickTicket[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({})
  const [weightInput, setWeightInput] = useState('')
  const [weightMsg, setWeightMsg] = useState<string | null>(null)
  const [dietInput, setDietInput] = useState('')
  const [dietMsg, setDietMsg] = useState<string | null>(null)
  const [quickInput, setQuickInput] = useState('')
  const [quickBusy, setQuickBusy] = useState(false)
  const [quickHistory, setQuickHistory] = useState<QuickChatHistoryItem[]>([])
  const [ticketDomainFilter, setTicketDomainFilter] = useState<'all' | TickDomain>('all')
  const [memQuery, setMemQuery] = useState('')
  const [memBusy, setMemBusy] = useState(false)
  const [memHits, setMemHits] = useState<MemorySearchHit[]>([])
  const [memSearched, setMemSearched] = useState(false)
  const [reports, setReports] = useState<DailyReport[]>([])
  const [pendingDrafts, setPendingDrafts] = useState<ImageIntakeDraft[]>([])
  const [linkedTicket, setLinkedTicket] = useState<{ id: number; title: string } | null>(null)
  const [externalFileReq, setExternalFileReq] = useState<{
    file: File
    ticketId: number
    ticketTitle: string
  } | null>(null)
  const ticketFileInputRef = useRef<HTMLInputElement | null>(null)
  const ticketTargetRef = useRef<{ id: number; title: string } | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [p, h, reps, drafts, qHist] = await Promise.all([
        api_list_tickets({ limit: 100 }),
        api_list_tickets({ status: 'replied', limit: 20 }),
        api_list_daily_reports(7).catch(() => [] as DailyReport[]),
        api_list_intake_drafts({ status: 'pending_confirm', limit: 5 }).catch(
          () => [] as ImageIntakeDraft[],
        ),
        api_get_quick_chat_history('general', 12).catch(() => [] as QuickChatHistoryItem[]),
      ])
      setPending(p.filter((t) => t.status === 'pending' || t.status === 'snoozed'))
      setHistory(h)
      setReports(reps)
      setPendingDrafts(drafts)
      setQuickHistory(qHist)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const inboxVersion = useUserInboxStore((s) => s.inboxVersion)
  const syncInbox = useUserInboxStore((s) => s.syncInbox)

  useEffect(() => {
    refresh()
  }, [refresh, inboxVersion])

  const latestReply = useMemo(
    () => history.find((t) => t.reply)?.reply ?? null,
    [history],
  )

  const submitReply = async (id: number) => {
    const text = replyDrafts[id]?.trim()
    if (!text) return
    await api_reply_ticket(id, text)
    setReplyDrafts((d) => ({ ...d, [id]: '' }))
    await Promise.all([refresh(), syncInbox(false)])
  }

  const resolve = async (id: number) => {
    await api_resolve_ticket(id)
    await Promise.all([refresh(), syncInbox(false)])
  }

  const snooze = async (id: number) => {
    await api_snooze_ticket(id, 24)
    await Promise.all([refresh(), syncInbox(false)])
  }

  const logWeight = async () => {
    const w = parseFloat(weightInput)
    if (!w || w <= 0) return
    try {
      await api_quick_log_weight(w)
      setWeightMsg(`已记录 ${w}kg ✓`)
      setWeightInput('')
    } catch (e) {
      setWeightMsg(`记录失败: ${e instanceof Error ? e.message : e}`)
    }
    setTimeout(() => setWeightMsg(null), 4000)
  }

  const sendDietNote = async () => {
    const text = dietInput.trim()
    if (!text) return
    try {
      await api_send_coach_message({ content: text, category: 'diet', source_channel: 'web' })
      setDietMsg('已静默收集，将在今晚睡前日报中整合 ✓')
      setDietInput('')
    } catch (e) {
      setDietMsg(`发送失败: ${e instanceof Error ? e.message : e}`)
    }
    setTimeout(() => setDietMsg(null), 4000)
  }

  const sendQuickChat = async (override?: string) => {
    const text = (override ?? quickInput).trim()
    if (!text || quickBusy) return
    setQuickBusy(true)
    setQuickHistory((prev) => [...prev, { role: 'user', content: text, domain: 'general', surface: 'web_tick' }])
    setQuickInput('')
    try {
      const res = await api_quick_chat(text, {
        channel: 'web_tick',
        domain: 'general',
        surface: 'web_tick',
      })
      setQuickHistory((prev) => [...prev, { role: 'assistant', content: res.reply, domain: res.domain ?? 'general' }])
    } catch (e) {
      setQuickHistory((prev) => [
        ...prev,
        { role: 'assistant', content: `快反助手暂不可用：${e instanceof Error ? e.message : String(e)}` },
      ])
    } finally {
      setQuickBusy(false)
    }
  }

  const runMemorySearch = async () => {
    const q = memQuery.trim()
    if (!q || memBusy) return
    setMemBusy(true)
    setMemSearched(true)
    try {
      const hits = await api_search_memory(q, ticketDomainFilter === 'all' ? undefined : ticketDomainFilter, 8)
      setMemHits(hits)
    } catch {
      setMemHits([])
    } finally {
      setMemBusy(false)
    }
  }

  const filteredPending = useMemo(
    () =>
      ticketDomainFilter === 'all'
        ? pending
        : pending.filter((t) => (t.domain || 'general') === ticketDomainFilter),
    [pending, ticketDomainFilter],
  )

  return (
    <PageLayout>
      <div className={`p-4 mx-auto w-full ${isMobile ? '' : 'max-w-3xl'}`}>
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold flex items-center gap-2">
            <MessageCircle className="h-5 w-5 text-primary" />
            SailTick Personal Agent
          </h1>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" asChild>
              <a href="/rhythm">
                <Calendar className="h-3.5 w-3.5 mr-1" />
                日程画布
              </a>
            </Button>
            <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
              刷新
            </Button>
          </div>
        </div>

        {/* 即时快反对话（日程/项目/健康统一入口） */}
        <Card className="mb-4 border-primary/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              随时对话（日程重排 · 项目跟进 · 饮食运动 · 定时提醒）
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            <div className="flex gap-2">
              <Input
                placeholder="例如：/today、下午加会帮我重排、下班前提醒我买洗衣液"
                value={quickInput}
                onChange={(e) => setQuickInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendQuickChat()}
                disabled={quickBusy}
              />
              <Button onClick={() => sendQuickChat()} disabled={quickBusy || !quickInput.trim()}>
                {quickBusy ? '处理中' : '发送'}
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {['/today', '/projects', '/brief', '/remind'].map((cmd) => (
                <Button
                  key={cmd}
                  variant="secondary"
                  size="sm"
                  className="h-7 text-xs"
                  disabled={quickBusy}
                  onClick={() => sendQuickChat(cmd)}
                >
                  {cmd}
                </Button>
              ))}
            </div>
            {quickHistory.length > 0 && (
              <div className="max-h-48 overflow-y-auto space-y-1.5 rounded-md border bg-muted/25 p-2.5">
                {quickHistory.slice(-8).map((m, idx) => (
                  <div
                    key={m.id ?? `${m.role}-${idx}`}
                    className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[88%] rounded-md px-2.5 py-1.5 text-xs whitespace-pre-wrap leading-relaxed ${
                        m.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-background border text-foreground'
                      }`}
                    >
                      {m.content}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* FTS5 长期记忆与知识毫秒检索 */}
        <Card className="mb-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Search className="h-4 w-4 text-primary" />
              长期记忆与知识快查（FTS5）
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex gap-2">
              <Input
                placeholder="检索已沉淀的长期规律、食物热量或偏好（如：食堂、聚餐、下班）"
                value={memQuery}
                onChange={(e) => setMemQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && void runMemorySearch()}
                disabled={memBusy}
              />
              <Button
                variant="outline"
                onClick={() => void runMemorySearch()}
                disabled={memBusy || !memQuery.trim()}
              >
                {memBusy ? '检索中' : '检索'}
              </Button>
            </div>
            {memSearched && (
              <div className="space-y-1.5">
                {memHits.length === 0 ? (
                  <p className="text-xs text-muted-foreground">未命中相关记忆条目。</p>
                ) : (
                  memHits.map((h) => (
                    <div key={`${h.entity_type}-${h.entity_id}`} className="rounded border bg-muted/30 px-2.5 py-1.5 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{h.title}</span>
                        <Badge variant="outline" className="text-[10px]">
                          {DOMAIN_BADGE_LABEL[h.domain] ?? h.domain} · {h.entity_type}
                        </Badge>
                      </div>
                      <p className="text-muted-foreground mt-0.5">{h.summary}</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {error && (
          <Card className="mb-4 border-destructive">
            <CardContent className="pt-4 text-sm text-destructive">
              加载失败：{error}（请确认 sail_server 已启动且票据 API 可用）
            </CardContent>
          </Card>
        )}

        {/* 今日状态摘要 */}
        <Card className="mb-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">今日状态</CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-2">
            <p className="text-muted-foreground">
              待回票据 <span className="font-semibold text-foreground">{pending.length}</span> 张
              {pending.length > 0 && '，按期待回复时间排序'}
            </p>
            {latestReply && (
              <p className="text-muted-foreground">
                最近回复：<span className="text-foreground">{latestReply}</span>
              </p>
            )}
          </CardContent>
        </Card>

        {/* 通用拍照/传图智能记录（DeepSeek Vision + OCR） */}
        <ImageIntakePanel
          initialDrafts={pendingDrafts}
          linkedTicket={linkedTicket}
          onClearLinkedTicket={() => setLinkedTicket(null)}
          onCommitted={() => {
            void refresh()
          }}
          externalFileRequest={externalFileReq}
          onConsumeExternalFile={() => setExternalFileReq(null)}
        />
        <input
          ref={ticketFileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            e.target.value = ''
            const target = ticketTargetRef.current
            if (f && target) {
              setLinkedTicket(target)
              setExternalFileReq({ file: f, ticketId: target.id, ticketTitle: target.title })
            }
          }}
        />

        {/* 快速记体重 */}
        <Card className="mb-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Scale className="h-4 w-4" />
              快速记体重
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input
                type="number"
                step="0.1"
                placeholder="kg，如 72.5"
                value={weightInput}
                onChange={(e) => setWeightInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && logWeight()}
              />
              <Button onClick={logWeight} disabled={!weightInput}>
                记录
              </Button>
            </div>
            {weightMsg && <p className="text-xs text-muted-foreground mt-2">{weightMsg}</p>}
          </CardContent>
        </Card>

        {/* 主动发送餐饮/状态（无需即时回复） */}
        <Card className="mb-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Send className="h-4 w-4" />
              随手发餐饮/状态（静默收集）
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input
                placeholder="例如：午饭吃了牛肉面少面+卤蛋"
                value={dietInput}
                onChange={(e) => setDietInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendDietNote()}
              />
              <Button onClick={sendDietNote} disabled={!dietInput.trim()}>
                发送
              </Button>
            </div>
            {dietMsg && <p className="text-xs text-muted-foreground mt-2">{dietMsg}</p>}
          </CardContent>
        </Card>

        {/* 最新睡前日报（支持分域结构化展示） */}
        {reports.length > 0 && (
          <Card className="mb-4">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Moon className="h-4 w-4 text-violet-500" />
                  {reports[0].title}
                </span>
                <Badge variant="secondary">{reports[0].report_date}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-2.5">
              <p className="text-foreground/90">{reports[0].summary}</p>
              {reports[0].sections && Object.keys(reports[0].sections).length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {(['health', 'rhythm', 'finance', 'chief'] as const).map((secKey) => {
                    const sec = reports[0].sections?.[secKey]
                    if (!sec || !sec.summary) return null
                    const labelMap: Record<string, string> = {
                      health: '健康教练',
                      rhythm: '节奏规划师',
                      finance: '财务秘书',
                      chief: '生活总管',
                    }
                    return (
                      <div key={secKey} className="rounded-md border bg-muted/30 p-2 text-xs space-y-1">
                        <div className="font-medium text-foreground">{labelMap[secKey]}</div>
                        <div className="text-muted-foreground leading-relaxed">{sec.summary}</div>
                      </div>
                    )
                  })}
                </div>
              )}
              {reports[0].body_markdown && (
                <pre className="whitespace-pre-wrap text-xs bg-muted/40 rounded p-2.5 font-sans">
                  {reports[0].body_markdown}
                </pre>
              )}
            </CardContent>
          </Card>
        )}

        {/* 待回票据（按业务域过滤） */}
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <h2 className="text-sm font-semibold text-muted-foreground">
            待回票据（{filteredPending.length} / {pending.length}）
          </h2>
          <div className="flex flex-wrap gap-1">
            {TICK_DOMAIN_TABS.map((tab) => (
              <Button
                key={tab.key}
                size="sm"
                variant={ticketDomainFilter === tab.key ? 'default' : 'outline'}
                className="h-6 px-2 text-xs"
                onClick={() => setTicketDomainFilter(tab.key)}
              >
                {tab.label}
              </Button>
            ))}
          </div>
        </div>
        <div className="space-y-3 mb-6">
          {filteredPending.map((t) => (
            <Card key={t.id}>
              <CardContent className="pt-4">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="font-medium leading-snug">{t.title}</div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Badge variant="outline" className="text-[11px]">
                      {DOMAIN_BADGE_LABEL[t.domain || 'general'] ?? t.domain}
                    </Badge>
                    <Badge variant={PRIORITY_VARIANT[t.priority]}>
                      {PRIORITY_LABEL[t.priority]}
                    </Badge>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <Badge variant="outline">{TYPE_LABEL[t.type] ?? t.type}</Badge>
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {deadlineLabel(t)}
                  </span>
                </div>
                {t.body && (
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap mb-3">
                    {t.body}
                  </p>
                )}
                <div className="flex gap-2">
                  <Input
                    placeholder="回复，或点右侧相机传图回复…"
                    value={replyDrafts[t.id] ?? ''}
                    onChange={(e) =>
                      setReplyDrafts((d) => ({ ...d, [t.id]: e.target.value }))
                    }
                    onKeyDown={(e) => e.key === 'Enter' && submitReply(t.id)}
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    title="拍照或传截图回复此问题"
                    onClick={() => {
                      ticketTargetRef.current = { id: t.id, title: t.title }
                      ticketFileInputRef.current?.click()
                    }}
                  >
                    <Camera className="h-4 w-4" />
                  </Button>
                  <Button size="sm" onClick={() => submitReply(t.id)}>
                    <Check className="h-4 w-4" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => snooze(t.id)} title="暂缓 24h">
                    <BellOff className="h-4 w-4" />
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => resolve(t.id)} title="关闭">
                    关闭
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
          {!loading && pending.length === 0 && !error && (
            <p className="text-sm text-muted-foreground text-center py-6">
              没有待回票据。AI 教练下次唤醒时会发来新的问题或建议。
            </p>
          )}
        </div>

        {/* 历史票据 */}
        <Button
          variant="ghost"
          className="w-full"
          onClick={() => setShowHistory((s) => !s)}
        >
          {showHistory ? '收起历史' : `展开历史（${history.length}）`}
        </Button>
        {showHistory && (
          <div className="space-y-2 mt-2">
            {history.map((t) => (
              <Card key={t.id} className="opacity-70">
                <CardContent className="pt-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{t.title}</span>
                    <span className="text-xs text-muted-foreground">
                      {format(new Date(t.updated_at), 'MM-dd HH:mm', { locale: zhCN })}
                    </span>
                  </div>
                  {t.reply && (
                    <p className="text-xs text-muted-foreground mt-1">回复：{t.reply}</p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </PageLayout>
  )
}

export default TickPage
