/**
 * @file sailtick_coach_panel.tsx
 * @brief 健康页 SailTick AI 教练面板：渐进提问回复 + 静默餐饮上报 + 每日睡前健康日报
 * @author sailing-innocent
 * @date 2026-11-22
 */
import React, { useCallback, useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  api_get_health_coach_summary,
  api_list_daily_reports,
  api_reply_ticket,
  api_send_coach_message,
  api_snooze_ticket,
  type DailyReport,
  type HealthCoachSummary,
  type TickMessageCategory,
  type TickTicket,
} from '@lib/api/tick'
import { BellOff, Check, ChevronDown, ChevronUp, Moon, Send, Sparkles, Utensils } from 'lucide-react'
import { useUserInboxStore } from '@lib/store/user'
import { DomainAssistantBar } from '@components/tick/DomainAssistantBar'

interface SailTickCoachPanelProps {
  onDataChanged?: () => void
}

const MEAL_CHIPS: Array<{ label: string; category: TickMessageCategory; mealType?: string }> = [
  { label: '早餐', category: 'diet', mealType: 'breakfast' },
  { label: '午餐', category: 'diet', mealType: 'lunch' },
  { label: '晚餐', category: 'diet', mealType: 'dinner' },
  { label: '加餐/零食', category: 'diet', mealType: 'snack' },
  { label: '日常状态', category: 'daily_info' },
]

export const SailTickCoachPanel: React.FC<SailTickCoachPanelProps> = ({ onDataChanged }) => {
  const [summary, setSummary] = useState<HealthCoachSummary | null>(null)
  const [reports, setReports] = useState<DailyReport[]>([])
  const [selectedReportDate, setSelectedReportDate] = useState<string | null>(null)
  const [reportExpanded, setReportExpanded] = useState(false)
  const [loading, setLoading] = useState(true)

  // 静默餐饮/状态输入
  const [chipIndex, setChipIndex] = useState(1) // 默认午餐
  const [msgInput, setMsgInput] = useState('')
  const [msgFeedback, setMsgFeedback] = useState<string | null>(null)
  const [sendingMsg, setSendingMsg] = useState(false)

  // 票据快速回复
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({})

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [sum, reps] = await Promise.all([
        api_get_health_coach_summary(),
        api_list_daily_reports(7),
      ])
      setSummary(sum)
      setReports(reps)
      if (reps.length > 0) {
        setSelectedReportDate((prev) => prev ?? reps[0].report_date)
      }
    } catch (e) {
      console.warn('[SailTickCoachPanel] load failed:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  const inboxVersion = useUserInboxStore((s) => s.inboxVersion)
  const syncInbox = useUserInboxStore((s) => s.syncInbox)

  useEffect(() => {
    refresh()
  }, [refresh, inboxVersion])

  const activeReport =
    reports.find((r) => r.report_date === selectedReportDate) ?? summary?.latest_report ?? null

  const handleSendMessage = async () => {
    const content = msgInput.trim()
    if (!content || sendingMsg) return
    const chip = MEAL_CHIPS[chipIndex]
    setSendingMsg(true)
    try {
      await api_send_coach_message({
        content,
        category: chip.category,
        meta: chip.mealType ? { meal_type: chip.mealType } : {},
        source_channel: 'web',
        auto_log_diet: chip.category === 'diet',
      })
      setMsgInput('')
      setMsgFeedback('已静默记录，SailTick 将在今晚睡前日报中整合分析')
      await refresh()
      onDataChanged?.()
      setTimeout(() => setMsgFeedback(null), 4000)
    } catch (e) {
      setMsgFeedback(`提交失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setSendingMsg(false)
    }
  }

  const handleReplyTicket = async (ticket: TickTicket, explicitReply?: string) => {
    const text = (explicitReply ?? replyDrafts[ticket.id] ?? '').trim()
    if (!text) return
    await api_reply_ticket(ticket.id, text)
    setReplyDrafts((prev) => ({ ...prev, [ticket.id]: '' }))
    await Promise.all([refresh(), syncInbox(false)])
  }

  const handleSnoozeTicket = async (ticketId: number) => {
    await api_snooze_ticket(ticketId, 24)
    await Promise.all([refresh(), syncInbox(false)])
  }

  const pendingTickets = summary?.pending_tickets ?? []
  const todayMessages = summary?.today_messages ?? []

  return (
    <div className="space-y-4 my-4">
      {/* 1. AI 教练待回提问（有提问时突出展示） */}
      {pendingTickets.length > 0 && (
        <Card className="border-indigo-200 dark:border-indigo-800 bg-indigo-50/40 dark:bg-indigo-950/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-indigo-500" />
                SailTick 教练提问（{summary?.pending_ticket_count ?? pendingTickets.length}）
              </span>
              <Badge variant="outline" className="text-xs">渐进了解 · 有空再回</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {pendingTickets.slice(0, 2).map((t) => {
              const quickReplies = Array.isArray(t.meta?.quick_replies)
                ? (t.meta?.quick_replies as string[])
                : []
              return (
                <div key={t.id} className="rounded-lg border bg-background p-3 space-y-2">
                  <div className="font-medium text-sm">{t.title}</div>
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
                          className="h-7 text-xs"
                          onClick={() => handleReplyTicket(t, qr)}
                        >
                          {qr}
                        </Button>
                      ))}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <Input
                      className="h-8 text-sm"
                      placeholder="简短回复一句即可…"
                      value={replyDrafts[t.id] ?? ''}
                      onChange={(e) =>
                        setReplyDrafts((d) => ({ ...d, [t.id]: e.target.value }))
                      }
                      onKeyDown={(e) => e.key === 'Enter' && handleReplyTicket(t)}
                    />
                    <Button size="sm" className="h-8" onClick={() => handleReplyTicket(t)}>
                      <Check className="h-3.5 w-3.5 mr-1" />
                      回复
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8"
                      title="暂缓 24h"
                      onClick={() => handleSnoozeTicket(t.id)}
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

      {/* 2. 健康教练实时对话（owner:health 多端共享） */}
      <DomainAssistantBar
        domain="health"
        surface="web_health"
        title="与健康教练即时对话"
        placeholder="例如：今天食堂红烧鸡腿配青菜大概多少大卡 / 晚上想加餐怎么选"
        quickPrompts={['评估我今天的饮食热量', '给我一个低脂晚餐建议', '查看本周减脂趋势']}
        showTickets={false}
        showReportSection={false}
        onDataChanged={onDataChanged}
      />

      {/* 3. 随手记饮食 / 主动发消息（静默收集，AI 无需立即回复） */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Utensils className="h-4 w-4 text-emerald-600" />
              随手记餐饮 / 发给教练（静默收集）
            </span>
            <span className="text-xs font-normal text-muted-foreground">
              无需等待即时回复 · 睡前日报自动整合
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2.5">
          <div className="flex flex-wrap gap-1.5">
            {MEAL_CHIPS.map((chip, idx) => (
              <Button
                key={chip.label}
                type="button"
                size="sm"
                variant={chipIndex === idx ? 'default' : 'outline'}
                className="h-7 text-xs"
                onClick={() => setChipIndex(idx)}
              >
                {chip.label}
              </Button>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="例如：食堂鸡胸肉+半碗米饭+西兰花，没喝饮料"
              value={msgInput}
              onChange={(e) => setMsgInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            />
            <Button onClick={handleSendMessage} disabled={!msgInput.trim() || sendingMsg}>
              <Send className="h-4 w-4 mr-1" />
              记录
            </Button>
          </div>
          {msgFeedback && (
            <div className="text-xs text-emerald-700 dark:text-emerald-300">{msgFeedback}</div>
          )}
          {todayMessages.length > 0 && (
            <div className="pt-1 space-y-1">
              <div className="text-xs text-muted-foreground">今日已收集（{todayMessages.length}）：</div>
              {todayMessages.slice(0, 5).map((m) => (
                <div
                  key={m.id}
                  className="flex items-center justify-between gap-2 text-xs bg-muted/50 rounded px-2.5 py-1.5"
                >
                  <span className="truncate">{m.content}</span>
                  <Badge variant={m.status === 'ingested' ? 'secondary' : 'outline'} className="shrink-0 text-[10px]">
                    {m.status === 'ingested' ? '已整合' : '待日报整合'}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 3. 每日睡前体重与健康日报 */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center justify-between flex-wrap gap-2">
            <span className="flex items-center gap-2">
              <Moon className="h-4 w-4 text-violet-500" />
              每日睡前体重与健康日报
            </span>
            {reports.length > 1 && (
              <div className="flex flex-wrap gap-1">
                {reports.slice(0, 5).map((r) => (
                  <Button
                    key={r.report_date}
                    size="sm"
                    variant={activeReport?.report_date === r.report_date ? 'default' : 'ghost'}
                    className="h-6 px-2 text-xs"
                    onClick={() => setSelectedReportDate(r.report_date)}
                  >
                    {r.report_date.slice(5)}
                  </Button>
                ))}
              </div>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading && !activeReport ? (
            <div className="text-sm text-muted-foreground">加载教练日报中…</div>
          ) : !activeReport ? (
            <div className="text-sm text-muted-foreground">
              暂无睡前日报。SailTick 将在每日睡前自动整合当天的体重、餐饮与动态计划进展并推送到手机。
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div className="font-medium text-sm">
                  {activeReport.sections?.health?.title || activeReport.title}
                </div>
                <Badge variant="secondary" className="text-xs">{activeReport.report_date}</Badge>
              </div>
              <p className="text-sm text-foreground/90 leading-relaxed">
                {activeReport.sections?.health?.summary || activeReport.summary}
              </p>
              {Array.isArray(activeReport.sections?.health?.highlights) &&
                activeReport.sections.health.highlights.length > 0 && (
                  <ul className="list-disc pl-4 space-y-0.5 text-xs text-muted-foreground">
                    {activeReport.sections.health.highlights.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                )}
              {activeReport.tomorrow_focus && activeReport.tomorrow_focus.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {activeReport.tomorrow_focus.map((tip, i) => (
                    <Badge key={i} variant="outline" className="text-xs font-normal">
                      明日建议：{tip}
                    </Badge>
                  ))}
                </div>
              )}
              {activeReport.body_markdown && (
                <div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs text-muted-foreground"
                    onClick={() => setReportExpanded((v) => !v)}
                  >
                    {reportExpanded ? (
                      <>
                        <ChevronUp className="h-3.5 w-3.5 mr-1" /> 收起完整日报
                      </>
                    ) : (
                      <>
                        <ChevronDown className="h-3.5 w-3.5 mr-1" /> 展开完整日报
                      </>
                    )}
                  </Button>
                  {reportExpanded && (
                    <pre className="mt-2 whitespace-pre-wrap text-xs bg-muted/40 rounded-md p-3 font-sans leading-relaxed">
                      {activeReport.body_markdown}
                    </pre>
                  )}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default SailTickCoachPanel
