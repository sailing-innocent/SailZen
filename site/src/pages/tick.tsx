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
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import PageLayout from '@components/page_layout'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useIsMobile } from '@/hooks/use-mobile'
import {
  api_list_tickets,
  api_reply_ticket,
  api_resolve_ticket,
  api_snooze_ticket,
  api_quick_log_weight,
  api_send_coach_message,
  api_list_daily_reports,
  type DailyReport,
  type TickTicket,
  type TicketPriority,
} from '@lib/api/tick'
import { format, isPast } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { MessageCircle, Scale, Check, Clock, BellOff, Send, Moon } from 'lucide-react'

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
  const [reports, setReports] = useState<DailyReport[]>([])

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [p, h, reps] = await Promise.all([
        api_list_tickets({ limit: 100 }),
        api_list_tickets({ status: 'replied', limit: 20 }),
        api_list_daily_reports(7).catch(() => [] as DailyReport[]),
      ])
      setPending(p.filter((t) => t.status === 'pending' || t.status === 'snoozed'))
      setHistory(h)
      setReports(reps)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const latestReply = useMemo(
    () => history.find((t) => t.reply)?.reply ?? null,
    [history],
  )

  const submitReply = async (id: number) => {
    const text = replyDrafts[id]?.trim()
    if (!text) return
    await api_reply_ticket(id, text)
    setReplyDrafts((d) => ({ ...d, [id]: '' }))
    await refresh()
  }

  const resolve = async (id: number) => {
    await api_resolve_ticket(id)
    await refresh()
  }

  const snooze = async (id: number) => {
    await api_snooze_ticket(id, 24)
    await refresh()
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

  return (
    <PageLayout>
      <div className={`p-4 mx-auto w-full ${isMobile ? '' : 'max-w-3xl'}`}>
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold flex items-center gap-2">
            <MessageCircle className="h-5 w-5 text-primary" />
            SailTick 教练
          </h1>
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
            刷新
          </Button>
        </div>

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

        {/* 最新睡前日报 */}
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
            <CardContent className="text-sm space-y-2">
              <p className="text-foreground/90">{reports[0].summary}</p>
              {reports[0].body_markdown && (
                <pre className="whitespace-pre-wrap text-xs bg-muted/40 rounded p-2.5 font-sans">
                  {reports[0].body_markdown}
                </pre>
              )}
            </CardContent>
          </Card>
        )}

        {/* 待回票据 */}
        <h2 className="text-sm font-semibold mb-2 text-muted-foreground">
          待回票据（{pending.length}）
        </h2>
        <div className="space-y-3 mb-6">
          {pending.map((t) => (
            <Card key={t.id}>
              <CardContent className="pt-4">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="font-medium leading-snug">{t.title}</div>
                  <Badge variant={PRIORITY_VARIANT[t.priority]}>
                    {PRIORITY_LABEL[t.priority]}
                  </Badge>
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
                    placeholder="回复…"
                    value={replyDrafts[t.id] ?? ''}
                    onChange={(e) =>
                      setReplyDrafts((d) => ({ ...d, [t.id]: e.target.value }))
                    }
                    onKeyDown={(e) => e.key === 'Enter' && submitReply(t.id)}
                  />
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
