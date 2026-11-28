/**
 * @file DomainAssistantBar.tsx
 * @brief 分域 SailTick 对话 + 分域待回票据 + 日报分域摘录组件（支持跨端共享 owner:{domain} 会话）
 * @author sailing-innocent
 * @date 2026-11-28
 */

import React, { useCallback, useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  api_get_domain_summary,
  api_get_quick_chat_history,
  api_quick_chat,
  api_reply_ticket,
  api_send_coach_message,
  api_snooze_ticket,
  type DomainSummary,
  type QuickChatHistoryItem,
  type TickDomain,
  type TickTicket,
} from '@lib/api/tick'
import { useUserInboxStore } from '@lib/store/user'
import { BellOff, Check, Loader2, Moon, Send, Sparkles } from 'lucide-react'

const DOMAIN_PERSONA_LABEL: Record<TickDomain, string> = {
  health: '健康教练',
  rhythm: '节奏规划师',
  finance: '财务秘书',
  general: '生活总管',
}

export interface DomainAssistantBarProps {
  domain: TickDomain
  surface: string
  title?: string
  placeholder?: string
  quickPrompts?: string[]
  showTickets?: boolean
  showReportSection?: boolean
  showQuickChat?: boolean
  contextHints?: Record<string, unknown>
  onDataChanged?: () => void
  onChatSuccess?: (res: { rhythm_updated?: boolean; finance_updated?: boolean }) => void
}

export const DomainAssistantBar: React.FC<DomainAssistantBarProps> = ({
  domain,
  surface,
  title,
  placeholder,
  quickPrompts = [],
  showTickets = true,
  showReportSection = true,
  showQuickChat = true,
  contextHints,
  onDataChanged,
  onChatSuccess,
}) => {
  const inboxVersion = useUserInboxStore((s) => s.inboxVersion)
  const syncInbox = useUserInboxStore((s) => s.syncInbox)

  const [summary, setSummary] = useState<DomainSummary | null>(null)
  const [history, setHistory] = useState<QuickChatHistoryItem[]>([])
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({})
  const [busyTicketId, setBusyTicketId] = useState<number | null>(null)

  const [chatInput, setChatInput] = useState('')
  const [chatBusy, setChatBusy] = useState(false)
  const [chatNote, setChatNote] = useState<string | null>(null)
  const [routedHint, setRoutedHint] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const tasks: Array<Promise<unknown>> = []
    if (showTickets || showReportSection) {
      tasks.push(
        api_get_domain_summary(domain)
          .then((s) => setSummary(s))
          .catch(() => {}),
      )
    }
    if (showQuickChat) {
      tasks.push(
        api_get_quick_chat_history(domain, 12)
          .then((items) => setHistory(items))
          .catch(() => {}),
      )
    }
    await Promise.all(tasks)
  }, [domain, showTickets, showReportSection, showQuickChat])

  useEffect(() => {
    void refresh()
  }, [refresh, inboxVersion])

  const handleReplyTicket = async (ticket: TickTicket, explicit?: string) => {
    const text = (explicit ?? replyDrafts[ticket.id] ?? '').trim()
    if (!text) return
    setBusyTicketId(ticket.id)
    try {
      await api_reply_ticket(ticket.id, text)
      setReplyDrafts((prev) => ({ ...prev, [ticket.id]: '' }))
      await Promise.all([refresh(), syncInbox(false)])
      onDataChanged?.()
    } finally {
      setBusyTicketId(null)
    }
  }

  const handleSnoozeTicket = async (ticketId: number) => {
    setBusyTicketId(ticketId)
    try {
      await api_snooze_ticket(ticketId, 24)
      await Promise.all([refresh(), syncInbox(false)])
    } finally {
      setBusyTicketId(null)
    }
  }

  const sendChat = async (rawText?: string) => {
    const text = (rawText ?? chatInput).trim()
    if (!text || chatBusy) return
    setChatBusy(true)
    setChatNote(null)
    setRoutedHint(null)
    setHistory((prev) => [...prev, { role: 'user', content: text, domain, surface }])
    setChatInput('')
    try {
      const res = await api_quick_chat(text, {
        channel: surface,
        domain,
        surface,
        context_hints: contextHints,
      })
      setHistory((prev) => [...prev, { role: 'assistant', content: res.reply, domain: res.domain ?? domain }])
      if (res.routed_domain && res.routed_domain !== domain) {
        setRoutedHint(`检测到跨域意图，已协同转交「${DOMAIN_PERSONA_LABEL[res.routed_domain] ?? res.routed_domain}」处理`)
      }
      if (res.rhythm_updated) setChatNote('已同步更新日程画布 ✓')
      else if (res.finance_updated) setChatNote('已同步更新财务账单 ✓')
      onChatSuccess?.(res)
      if (res.rhythm_updated || res.finance_updated) {
        onDataChanged?.()
      }
    } catch {
      try {
        await api_send_coach_message({
          content: `[${DOMAIN_PERSONA_LABEL[domain]}] ${text}`,
          category: domain === 'health' ? 'diet' : 'daily_info',
          source_channel: 'web',
          auto_log_diet: false,
        })
        setHistory((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: 'SailTick 快脑暂未在线，已将你的消息写入异步消息箱，下次 Tick 唤醒时自动吸收处理。',
          },
        ])
      } catch (e) {
        setChatNote(`发送失败：${e instanceof Error ? e.message : String(e)}`)
      }
    } finally {
      setChatBusy(false)
    }
  }

  const tickets = summary?.pending_tickets ?? []
  const reportSection = summary?.latest_report_section ?? null
  const personaName = DOMAIN_PERSONA_LABEL[domain]

  return (
    <div className="space-y-3">
      {/* 1. 本域待回票据（严格分域隔离） */}
      {showTickets && tickets.length > 0 && (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Sparkles className="h-4 w-4 text-primary" />
                {personaName}待确认（{summary?.pending_ticket_count ?? tickets.length}）
              </span>
              <Badge variant="outline" className="text-[11px] font-normal">
                仅显示本域 · 有空再回
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {tickets.slice(0, 3).map((t) => {
              const quickReplies = Array.isArray(t.meta?.quick_replies)
                ? (t.meta?.quick_replies as string[])
                : []
              const busy = busyTicketId === t.id
              return (
                <div key={t.id} className="rounded-md border bg-background p-2.5 space-y-2">
                  <div className="text-sm font-medium">{t.title}</div>
                  {t.body && (
                    <p className="text-xs text-muted-foreground whitespace-pre-wrap">{t.body}</p>
                  )}
                  {quickReplies.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {quickReplies.map((qr) => (
                        <Button
                          key={qr}
                          type="button"
                          size="sm"
                          variant="secondary"
                          className="h-6 text-xs px-2"
                          disabled={busy}
                          onClick={() => void handleReplyTicket(t, qr)}
                        >
                          {qr}
                        </Button>
                      ))}
                    </div>
                  )}
                  <div className="flex gap-1.5">
                    <Input
                      className="h-7 text-xs"
                      placeholder="简短回复一句即可…"
                      value={replyDrafts[t.id] ?? ''}
                      disabled={busy}
                      onChange={(e) =>
                        setReplyDrafts((prev) => ({ ...prev, [t.id]: e.target.value }))
                      }
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') void handleReplyTicket(t)
                      }}
                    />
                    <Button
                      size="sm"
                      className="h-7 text-xs px-2.5"
                      disabled={busy || !(replyDrafts[t.id] ?? '').trim()}
                      onClick={() => void handleReplyTicket(t)}
                    >
                      <Check className="h-3.5 w-3.5 mr-1" />
                      回复
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-2"
                      disabled={busy}
                      title="延后 24h"
                      onClick={() => void handleSnoozeTicket(t.id)}
                    >
                      <BellOff className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}

      {/* 2. 睡前日报本域摘录 */}
      {showReportSection && reportSection && (reportSection.summary || reportSection.body_markdown) && (
        <Card>
          <CardHeader className="pb-1.5">
            <CardTitle className="text-sm flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Moon className="h-3.5 w-3.5 text-violet-500" />
                {reportSection.title || `${personaName}日报摘录`}
              </span>
              {summary?.latest_report_date && (
                <Badge variant="secondary" className="text-[11px]">
                  {summary.latest_report_date}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs space-y-1.5">
            {reportSection.summary && (
              <p className="text-foreground/90 leading-relaxed">{reportSection.summary}</p>
            )}
            {Array.isArray(reportSection.tomorrow_focus) && reportSection.tomorrow_focus.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {reportSection.tomorrow_focus.map((tip, i) => (
                  <Badge key={i} variant="outline" className="text-[11px] font-normal">
                    明日：{tip}
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 3. 本域持久化快反对话（多端共享 owner:{domain}） */}
      {showQuickChat && (
        <Card className="border-primary/20">
          <CardContent className="pt-3.5 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 text-sm font-medium">
                <Sparkles className="h-4 w-4 text-primary" />
                <span>{title || `与 ${personaName} 对话`}</span>
              </div>
              <Badge variant="secondary" className="text-[10px] font-normal">
                多端共享会话 · {personaName}
              </Badge>
            </div>

            {history.length > 0 && (
              <div className="max-h-48 overflow-y-auto space-y-1.5 rounded-md border bg-muted/25 p-2">
                {history.slice(-8).map((m, idx) => (
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

            <div className="flex gap-2">
              <Input
                className="h-8 text-xs"
                placeholder={placeholder || `跟 ${personaName} 说一声…`}
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void sendChat()
                }}
                disabled={chatBusy}
              />
              <Button
                size="sm"
                className="h-8 text-xs shrink-0"
                disabled={chatBusy || !chatInput.trim()}
                onClick={() => void sendChat()}
              >
                {chatBusy ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Send className="h-3.5 w-3.5 mr-1" />
                )}
                发送
              </Button>
            </div>

            {quickPrompts.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {quickPrompts.map((p) => (
                  <button
                    key={p}
                    type="button"
                    disabled={chatBusy}
                    className="text-[11px] px-2 py-0.5 rounded-full border bg-background hover:bg-muted transition-colors disabled:opacity-50"
                    onClick={() => void sendChat(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}

            {routedHint && (
              <div className="text-[11px] text-amber-700 dark:text-amber-300">{routedHint}</div>
            )}
            {chatNote && (
              <div className="text-[11px] text-emerald-600 font-medium">{chatNote}</div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default DomainAssistantBar
