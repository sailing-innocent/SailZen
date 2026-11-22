/**
 * @file sailtick_trace_panel.tsx
 * @brief SailTick AI 全链路 Trace 监控与瀑布流调试面板
 * @author sailing-innocent
 * @date 2026-11-23
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  api_get_ai_trace_detail,
  api_get_ai_trace_stats,
  api_get_sailtick_live,
  api_list_ai_traces,
  api_trigger_sailtick_slot,
  type AITraceDetail,
  type AITraceSpan,
  type AITraceStats,
  type AITraceSummary,
  type SailTickLiveStatus,
} from '@lib/api/telemetry'
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  Copy,
  Cpu,
  Play,
  Radio,
  ShieldAlert,
  Sparkles,
  XCircle,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const SLOTS = [
  { value: 'morning_checkin', label: '早间巡检 (06:00)' },
  { value: 'midday_checkin', label: '午间巡检 (12:00)' },
  { value: 'evening_review', label: '晚间复盘 (18:00)' },
  { value: 'pre_sleep_report', label: '睡前日报 (21:45)' },
  { value: 'nightly_maintenance', label: '夜间维护 (00:00)' },
]

const STAGE_COLOR: Record<string, string> = {
  wake: 'bg-sky-500',
  scan: 'bg-cyan-500',
  plan: 'bg-violet-500',
  llm_call: 'bg-fuchsia-600',
  throttle: 'bg-amber-500',
  work: 'bg-emerald-500',
  ticket_emit: 'bg-teal-500',
  work_action: 'bg-green-600',
  handoff: 'bg-indigo-500',
  canary: 'bg-orange-500',
}

function formatMs(ms: number | null | undefined): string {
  const v = Number(ms ?? 0)
  if (v < 1000) return `${Math.round(v)}ms`
  return `${(v / 1000).toFixed(2)}s`
}

function formatTimeShort(iso: string | null | undefined): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 19)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function statusBadgeVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'failed' || status === 'error') return 'destructive'
  if (status === 'completed' || status === 'ok') return 'default'
  if (status === 'degraded' || status === 'paused') return 'secondary'
  return 'outline'
}

interface SailTickTracePanelProps {
  windowDays: number
  refreshNonce: number
  onLiveStatusChange?: (live: SailTickLiveStatus | null) => void
}

const SailTickTracePanel: React.FC<SailTickTracePanelProps> = ({
  windowDays,
  refreshNonce,
  onLiveStatusChange,
}) => {
  const [live, setLive] = useState<SailTickLiveStatus | null>(null)
  const [stats, setStats] = useState<AITraceStats | null>(null)
  const [traces, setTraces] = useState<AITraceSummary[]>([])
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const [traceDetail, setTraceDetail] = useState<AITraceDetail | null>(null)
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null)

  const [slotFilter, setSlotFilter] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [planFilter, setPlanFilter] = useState<string>('')

  const [triggerSlot, setTriggerSlot] = useState<string>('morning_checkin')
  const [triggerBusy, setTriggerBusy] = useState(false)
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadList = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [liveRes, statsRes, listRes] = await Promise.all([
        api_get_sailtick_live().catch(() => null),
        api_get_ai_trace_stats({ service: 'sailtick', days: windowDays }),
        api_list_ai_traces({
          service: 'sailtick',
          slot: slotFilter || undefined,
          status: statusFilter || undefined,
          plan_source: planFilter || undefined,
          days: windowDays,
          limit: 60,
        }),
      ])
      setLive(liveRes)
      onLiveStatusChange?.(liveRes)
      setStats(statsRes)
      setTraces(listRes)
      setSelectedTraceId((prev) => {
        if (prev && listRes.some((t) => t.trace_id === prev)) return prev
        return listRes[0]?.trace_id ?? null
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [windowDays, slotFilter, statusFilter, planFilter, onLiveStatusChange])

  useEffect(() => {
    loadList()
  }, [loadList, refreshNonce])

  useEffect(() => {
    if (!selectedTraceId) {
      setTraceDetail(null)
      setSelectedSpanId(null)
      return
    }
    let cancelled = false
    setDetailLoading(true)
    api_get_ai_trace_detail(selectedTraceId)
      .then((det) => {
        if (cancelled) return
        setTraceDetail(det)
        // 默认优先选中报错 Span 或 LLM 调用 Span，便于一眼看到 AI 输入输出
        const preferred =
          det.spans.find((s) => s.status === 'error') ??
          det.spans.find((s) => s.stage === 'llm_call') ??
          det.spans[0] ??
          null
        setSelectedSpanId(preferred?.span_id ?? null)
      })
      .catch(() => {
        if (!cancelled) setTraceDetail(null)
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedTraceId])

  const selectedSpan: AITraceSpan | null = useMemo(() => {
    if (!traceDetail) return null
    return traceDetail.spans.find((s) => s.span_id === selectedSpanId) ?? traceDetail.spans[0] ?? null
  }, [traceDetail, selectedSpanId])

  const waterfallBounds = useMemo(() => {
    if (!traceDetail || traceDetail.spans.length === 0) {
      return { baseMs: 0, totalMs: 1 }
    }
    const startTimes = traceDetail.spans
      .map((s) => (s.started_at ? new Date(s.started_at).getTime() : NaN))
      .filter((t) => !Number.isNaN(t))
    const baseMs = startTimes.length > 0 ? Math.min(...startTimes) : 0
    const endTimes = traceDetail.spans.map((s) => {
      const st = s.started_at ? new Date(s.started_at).getTime() : baseMs
      const en = s.ended_at ? new Date(s.ended_at).getTime() : st + (s.duration_ms || 0)
      return Math.max(en, st + (s.duration_ms || 0))
    })
    const maxEnd = endTimes.length > 0 ? Math.max(...endTimes) : baseMs + 1
    const totalMs = Math.max(traceDetail.duration_ms || 0, maxEnd - baseMs, 1)
    return { baseMs, totalMs }
  }, [traceDetail])

  const handleTrigger = async () => {
    setTriggerBusy(true)
    setTriggerMsg(null)
    try {
      const suffix = `debug_${Date.now().toString(36)}`
      const res = await api_trigger_sailtick_slot(triggerSlot, suffix)
      if (!res.reachable) {
        setTriggerMsg(`SailTick Daemon 不可达: ${res.error ?? 'offline'}`)
      } else {
        setTriggerMsg(`已触发 ${triggerSlot}（异步执行中，数秒后点击刷新查看 Trace）`)
        setTimeout(() => {
          loadList()
        }, 3500)
      }
    } catch (e) {
      setTriggerMsg(`触发失败: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setTriggerBusy(false)
    }
  }

  const copyText = (key: string, text: string) => {
    navigator.clipboard?.writeText(text).then(() => {
      setCopiedKey(key)
      setTimeout(() => setCopiedKey(null), 1800)
    })
  }

  const canary = live?.health?.canary
  const monitorMetrics = live?.monitor?.metrics
  const dailyTokens = live?.health?.daily_tokens ?? monitorMetrics?.daily_tokens ?? 0
  const dailyTokenCap = monitorMetrics?.daily_token_cap ?? 1_000_000
  const tokenPct = Math.min(100, dailyTokenCap > 0 ? (dailyTokens / dailyTokenCap) * 100 : 0)

  return (
    <div className="space-y-4">
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-4 text-sm text-destructive">
            加载 SailTick Trace 失败：{error}
          </CardContent>
        </Card>
      )}

      {/* 1. 实时 Daemon 状态与手动试运行触发 */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Radio
                className={`h-4 w-4 ${live?.reachable ? 'text-emerald-500' : 'text-muted-foreground'}`}
              />
              SailTick Daemon 实时态
              <Badge variant={live?.reachable ? 'default' : 'outline'}>
                {live?.reachable ? '在线' : '离线 / 本地未启动'}
              </Badge>
              {canary && (
                <Badge variant={canary.circuit_breaker_open ? 'destructive' : 'secondary'}>
                  模式: {canary.mode}
                  {canary.circuit_breaker_open ? ' · 熔断开启' : ''}
                </Badge>
              )}
            </CardTitle>

            <div className="flex flex-wrap items-center gap-2">
              <select
                className="h-8 rounded-md border bg-background px-2 text-xs"
                value={triggerSlot}
                onChange={(e) => setTriggerSlot(e.target.value)}
              >
                {SLOTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
              <Button
                size="sm"
                variant="outline"
                onClick={handleTrigger}
                disabled={triggerBusy || !live?.reachable}
              >
                <Play className="h-3.5 w-3.5 mr-1" />
                {triggerBusy ? '触发中...' : '手动试跑一次'}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-xs">
          {triggerMsg && (
            <div className="rounded-md bg-muted px-3 py-2 text-foreground">{triggerMsg}</div>
          )}
          {live?.reachable ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <div className="text-muted-foreground font-medium">今日 Token 预算</div>
                <div className="flex items-center justify-between">
                  <span className="font-mono font-semibold">
                    {dailyTokens.toLocaleString()} / {dailyTokenCap.toLocaleString()}
                  </span>
                  <span className="text-muted-foreground">{tokenPct.toFixed(1)}%</span>
                </div>
                <Progress value={tokenPct} className="h-1.5" />
              </div>

              <div className="space-y-1.5">
                <div className="text-muted-foreground font-medium">外部依赖健康</div>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(live.health?.deps ?? {}).map(([dep, info]) => (
                    <Badge
                      key={dep}
                      variant={info.status === 'ok' ? 'secondary' : 'destructive'}
                      className="font-mono text-[11px]"
                    >
                      {dep}: {info.status ?? 'unknown'}
                    </Badge>
                  ))}
                  {Object.keys(live.health?.deps ?? {}).length === 0 && (
                    <span className="text-muted-foreground">尚无扫描记录</span>
                  )}
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="text-muted-foreground font-medium">下次计划唤醒</div>
                <div className="space-y-0.5 font-mono text-[11px]">
                  {(live.schedules ?? []).slice(0, 3).map((sc, i) => (
                    <div key={sc.id ?? i} className="flex justify-between gap-2">
                      <span className="truncate">{sc.slot || sc.name}</span>
                      <span className="text-muted-foreground shrink-0">
                        {formatTimeShort(sc.next_run_time)}
                      </span>
                    </div>
                  ))}
                  {(live.schedules ?? []).length === 0 && (
                    <span className="text-muted-foreground">无活跃排程</span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-muted-foreground">
              当前无法连接到 SailTick 管理端口（{live?.api_base ?? 'http://127.0.0.1:9070'}），
              下方仍可正常浏览所有已落库的历史 AI Trace 记录。
            </div>
          )}

          {live?.monitor?.alerts && live.monitor.alerts.length > 0 && (
            <div className="space-y-1 pt-1">
              {live.monitor.alerts.map((al, i) => (
                <div
                  key={`${al.code}-${i}`}
                  className="flex items-center gap-2 rounded border border-amber-500/40 bg-amber-500/10 px-2.5 py-1.5 text-amber-800 dark:text-amber-300"
                >
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                  <span className="font-mono font-semibold">{al.code}</span>
                  <span>{al.message}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 2. 窗口期核心 KPI 概览 */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Bot className="h-3.5 w-3.5" /> Tick 唤醒与成功率
            </div>
            <div className="text-2xl font-bold mt-1">
              {stats ? `${(stats.success_rate * 100).toFixed(1)}%` : '-'}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              总计 {stats?.total_traces ?? 0} · 成功 {stats?.completed_count ?? 0} · 失败{' '}
              <span className={(stats?.failed_count ?? 0) > 0 ? 'text-destructive font-semibold' : ''}>
                {stats?.failed_count ?? 0}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Sparkles className="h-3.5 w-3.5" /> LLM 降级率
            </div>
            <div
              className={`text-2xl font-bold mt-1 ${
                (stats?.fallback_rate ?? 0) >= 0.3 ? 'text-amber-600' : ''
              }`}
            >
              {stats ? `${(stats.fallback_rate * 100).toFixed(1)}%` : '-'}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              LLM {stats?.llm_plan_count ?? 0} · 降级 {stats?.fallback_plan_count ?? 0} (错{' '}
              {stats?.fallback_error_count ?? 0})
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" /> 平均端到端 / LLM 耗时
            </div>
            <div className="text-2xl font-bold mt-1">{formatMs(stats?.avg_duration_ms)}</div>
            <div className="text-xs text-muted-foreground mt-1">
              LLM 平均 {formatMs(stats?.avg_llm_latency_ms)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Cpu className="h-3.5 w-3.5" /> Token 与成本
            </div>
            <div className="text-2xl font-bold mt-1">
              {(stats?.total_tokens ?? 0).toLocaleString()}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              估算 ${(stats?.total_cost_usd ?? 0).toFixed(4)}
            </div>
          </CardContent>
        </Card>

        <Card className="col-span-2 lg:col-span-1">
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <ShieldAlert className="h-3.5 w-3.5" /> 票据与动作执行
            </div>
            <div className="text-2xl font-bold mt-1">
              {stats?.total_tickets_created ?? 0} / {stats?.total_actions_executed ?? 0}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              限流 {stats?.total_tickets_throttled ?? 0} · 动作失败 {stats?.total_actions_failed ?? 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 3. 每日趋势图（有数据时显示） */}
      {stats && stats.daily_trend.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">近 {windowDays} 天唤醒执行与降级趋势</CardTitle>
          </CardHeader>
          <CardContent className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.daily_trend}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="completed" name="成功" stackId="a" fill="#10b981" />
                <Bar dataKey="fallback" name="含降级" fill="#f59e0b" />
                <Bar dataKey="failed" name="失败" stackId="a" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* 4. 主体：Trace 列表 + 瀑布流详情检查器 */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        {/* 左侧：过滤 + Trace 列表 */}
        <Card className="xl:col-span-5">
          <CardHeader className="pb-2 space-y-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">执行链路记录 ({traces.length})</CardTitle>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <select
                className="h-7 rounded border bg-background px-2 text-xs"
                value={slotFilter}
                onChange={(e) => setSlotFilter(e.target.value)}
              >
                <option value="">全部 Slot</option>
                {SLOTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.value}
                  </option>
                ))}
              </select>
              <select
                className="h-7 rounded border bg-background px-2 text-xs"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">全部状态</option>
                <option value="completed">completed</option>
                <option value="failed">failed</option>
                <option value="paused">paused</option>
                <option value="skipped">skipped</option>
              </select>
              <select
                className="h-7 rounded border bg-background px-2 text-xs"
                value={planFilter}
                onChange={(e) => setPlanFilter(e.target.value)}
              >
                <option value="">全部规划源</option>
                <option value="llm">llm</option>
                <option value="fallback">fallback</option>
                <option value="fallback_error">fallback_error</option>
              </select>
            </div>
          </CardHeader>
          <CardContent className="p-2 max-h-[680px] overflow-y-auto space-y-1.5">
            {loading && traces.length === 0 && (
              <div className="text-center text-xs text-muted-foreground py-8">加载中...</div>
            )}
            {!loading && traces.length === 0 && (
              <div className="text-center text-xs text-muted-foreground py-10 space-y-1">
                <div>当前时间窗口内暂无 SailTick AI Trace 记录</div>
                <div>SailTick 下次唤醒或点击上方「手动试跑一次」后，完整执行链路将自动上报至此。</div>
              </div>
            )}
            {traces.map((t) => {
              const active = t.trace_id === selectedTraceId
              return (
                <button
                  key={t.trace_id}
                  type="button"
                  onClick={() => setSelectedTraceId(t.trace_id)}
                  className={`w-full text-left rounded-md border p-2.5 transition-colors ${
                    active ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                      {t.status === 'failed' ? (
                        <XCircle className="h-3.5 w-3.5 text-destructive shrink-0" />
                      ) : t.status === 'completed' ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                      ) : (
                        <Clock className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                      )}
                      <span className="font-mono text-xs font-semibold truncate">{t.slot || 'tick'}</span>
                      <Badge variant="outline" className="text-[10px] px-1 py-0">
                        {t.mode}
                      </Badge>
                    </div>
                    <span className="text-[11px] font-mono text-muted-foreground shrink-0">
                      {formatMs(t.duration_ms)}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5 mt-1.5 text-[11px]">
                    <Badge variant={statusBadgeVariant(t.status)} className="text-[10px] px-1.5 py-0">
                      {t.status}
                    </Badge>
                    <Badge
                      variant={
                        t.plan_source === 'llm'
                          ? 'secondary'
                          : t.plan_source === 'fallback_error'
                            ? 'destructive'
                            : 'outline'
                      }
                      className="text-[10px] px-1.5 py-0"
                    >
                      plan:{t.plan_source}
                    </Badge>
                    <span className="text-muted-foreground font-mono">
                      {t.total_tokens.toLocaleString()} tok
                    </span>
                    <span className="text-muted-foreground">
                      · {t.tickets_created}票/{t.actions_executed}动
                    </span>
                    <span className="ml-auto text-muted-foreground font-mono">
                      {formatTimeShort(t.started_at)}
                    </span>
                  </div>

                  {(t.error || t.summary) && (
                    <div
                      className={`mt-1.5 text-xs line-clamp-2 ${
                        t.error ? 'text-destructive' : 'text-muted-foreground'
                      }`}
                    >
                      {t.error ? `Error: ${t.error}` : t.summary}
                    </div>
                  )}
                </button>
              )
            })}
          </CardContent>
        </Card>

        {/* 右侧：全链路 Waterfall + Span / LLM 详情检查器 */}
        <Card className="xl:col-span-7">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center justify-between gap-2">
              <span>执行瀑布流与 AI 输入输出检视</span>
              {traceDetail && (
                <span className="text-[11px] font-mono text-muted-foreground">
                  trace: {traceDetail.trace_id.slice(0, 12)} · trigger: {traceDetail.trigger_source}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {detailLoading && (
              <div className="text-center text-xs text-muted-foreground py-10">加载链路详情...</div>
            )}
            {!detailLoading && !traceDetail && (
              <div className="text-center text-xs text-muted-foreground py-12">
                请在左侧选择一条 Trace 查看唤醒 → SCAN → PLAN → LLM → WORK → HANDOFF 完整时间线。
              </div>
            )}
            {!detailLoading && traceDetail && (
              <>
                {/* Trace 顶栏概要 */}
                <div className="rounded-md bg-muted/40 p-3 text-xs space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-sm">{traceDetail.slot}</span>
                    <Badge variant={statusBadgeVariant(traceDetail.status)}>{traceDetail.status}</Badge>
                    <Badge variant="outline">mode: {traceDetail.mode}</Badge>
                    <Badge variant="outline">plan: {traceDetail.plan_source}</Badge>
                    <span className="font-mono text-muted-foreground">
                      总耗时 {formatMs(traceDetail.duration_ms)}
                    </span>
                    <span className="font-mono text-muted-foreground">
                      Tokens {traceDetail.prompt_tokens} in + {traceDetail.completion_tokens} out ={' '}
                      {traceDetail.total_tokens} (${traceDetail.cost_usd.toFixed(5)})
                    </span>
                  </div>
                  {traceDetail.summary && <div className="text-foreground/90">{traceDetail.summary}</div>}
                  {traceDetail.error && (
                    <div className="text-destructive font-mono break-all">
                      错误：{traceDetail.error}
                    </div>
                  )}
                </div>

                {/* Waterfall 时间线 */}
                <div className="space-y-1">
                  <div className="text-xs font-semibold text-muted-foreground">
                    阶段时间线（点击任意 Span 查看详情）
                  </div>
                  <div className="border rounded-md divide-y max-h-64 overflow-y-auto">
                    {traceDetail.spans.map((sp) => {
                      const stMs = sp.started_at ? new Date(sp.started_at).getTime() : waterfallBounds.baseMs
                      const offsetPct = Math.max(
                        0,
                        Math.min(96, ((stMs - waterfallBounds.baseMs) / waterfallBounds.totalMs) * 100),
                      )
                      const widthPct = Math.max(
                        1.5,
                        Math.min(100 - offsetPct, ((sp.duration_ms || 0) / waterfallBounds.totalMs) * 100),
                      )
                      const isChild = Boolean(sp.parent_span_id)
                      const isSelected = selectedSpan?.span_id === sp.span_id
                      const barColor =
                        sp.status === 'error'
                          ? 'bg-destructive'
                          : sp.status === 'degraded'
                            ? 'bg-amber-500'
                            : sp.status === 'skipped'
                              ? 'bg-muted-foreground/50'
                              : STAGE_COLOR[sp.stage] ?? 'bg-primary'

                      return (
                        <button
                          key={sp.span_id}
                          type="button"
                          onClick={() => setSelectedSpanId(sp.span_id)}
                          className={`w-full grid grid-cols-12 items-center gap-2 px-2.5 py-1.5 text-left text-xs transition-colors ${
                            isSelected ? 'bg-primary/10' : 'hover:bg-muted/40'
                          }`}
                        >
                          <div className={`col-span-5 flex items-center gap-1.5 min-w-0 ${isChild ? 'pl-4' : ''}`}>
                            <span className={`h-2 w-2 rounded-full shrink-0 ${barColor}`} />
                            <span className="font-mono text-[10px] uppercase text-muted-foreground shrink-0">
                              {sp.stage}
                            </span>
                            <span className="truncate font-medium">{sp.name}</span>
                          </div>
                          <div className="col-span-5 h-3 bg-muted/60 rounded relative overflow-hidden">
                            <div
                              className={`h-full rounded ${barColor}`}
                              style={{ marginLeft: `${offsetPct}%`, width: `${widthPct}%` }}
                            />
                          </div>
                          <div className="col-span-2 text-right font-mono text-[11px] text-muted-foreground">
                            {formatMs(sp.duration_ms)}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* Span 详情检视区 */}
                {selectedSpan && (
                  <div className="border rounded-md p-3 space-y-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Badge variant={statusBadgeVariant(selectedSpan.status)}>
                          {selectedSpan.stage} · {selectedSpan.status}
                        </Badge>
                        <span className="font-semibold">{selectedSpan.name}</span>
                      </div>
                      <span className="font-mono text-muted-foreground">
                        {formatMs(selectedSpan.duration_ms)} ({formatTimeShort(selectedSpan.started_at)})
                      </span>
                    </div>

                    {selectedSpan.input_summary && (
                      <div>
                        <span className="text-muted-foreground font-medium">输入摘要：</span>
                        <span className="font-mono">{selectedSpan.input_summary}</span>
                      </div>
                    )}
                    {selectedSpan.output_summary && (
                      <div>
                        <span className="text-muted-foreground font-medium">输出摘要：</span>
                        <span className="font-mono">{selectedSpan.output_summary}</span>
                      </div>
                    )}
                    {selectedSpan.error && (
                      <div className="rounded bg-destructive/10 border border-destructive/30 p-2 font-mono text-destructive break-all">
                        {selectedSpan.error}
                      </div>
                    )}

                    {/* LLM Call 专属富检视（Prompt / Response / Reasoning / Meta） */}
                    {selectedSpan.stage === 'llm_call' ? (
                      <Tabs defaultValue="response" className="w-full">
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                          <TabsList className="h-8">
                            <TabsTrigger value="response" className="text-xs">
                              AI 原始输出
                            </TabsTrigger>
                            <TabsTrigger value="prompt" className="text-xs">
                              Prompt 输入 ({String(selectedSpan.payload?.prompt_chars ?? 0)} chars)
                            </TabsTrigger>
                            {Boolean(selectedSpan.payload?.reasoning_content) && (
                              <TabsTrigger value="reasoning" className="text-xs">
                                思维链 (Reasoning)
                              </TabsTrigger>
                            )}
                            <TabsTrigger value="meta" className="text-xs">
                              调用参数
                            </TabsTrigger>
                          </TabsList>
                          <div className="font-mono text-[11px] text-muted-foreground">
                            {String(selectedSpan.payload?.provider ?? '')}/
                            {String(selectedSpan.payload?.model ?? '')} · finish=
                            {String(selectedSpan.payload?.finish_reason ?? 'stop')}
                          </div>
                        </div>

                        <TabsContent value="response" className="space-y-1.5">
                          <div className="flex justify-end">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 text-xs"
                              onClick={() =>
                                copyText('resp', String(selectedSpan.payload?.response_text ?? ''))
                              }
                            >
                              <Copy className="h-3 w-3 mr-1" />
                              {copiedKey === 'resp' ? '已复制' : '复制输出'}
                            </Button>
                          </div>
                          <pre className="max-h-72 overflow-auto rounded bg-muted p-2.5 font-mono text-[11px] whitespace-pre-wrap break-words">
                            {String(selectedSpan.payload?.response_text ?? '(空)')}
                          </pre>
                        </TabsContent>

                        <TabsContent value="prompt" className="space-y-1.5">
                          <div className="flex justify-end">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 text-xs"
                              onClick={() =>
                                copyText('prompt', String(selectedSpan.payload?.prompt_text ?? ''))
                              }
                            >
                              <Copy className="h-3 w-3 mr-1" />
                              {copiedKey === 'prompt' ? '已复制' : '复制 Prompt'}
                            </Button>
                          </div>
                          <pre className="max-h-72 overflow-auto rounded bg-muted p-2.5 font-mono text-[11px] whitespace-pre-wrap break-words">
                            {String(selectedSpan.payload?.prompt_text ?? '(未捕获)')}
                          </pre>
                        </TabsContent>

                        {Boolean(selectedSpan.payload?.reasoning_content) && (
                          <TabsContent value="reasoning">
                            <pre className="max-h-72 overflow-auto rounded bg-muted p-2.5 font-mono text-[11px] whitespace-pre-wrap break-words">
                              {String(selectedSpan.payload?.reasoning_content ?? '')}
                            </pre>
                          </TabsContent>
                        )}

                        <TabsContent value="meta">
                          <pre className="max-h-60 overflow-auto rounded bg-muted p-2.5 font-mono text-[11px] whitespace-pre-wrap">
                            {JSON.stringify(
                              {
                                provider: selectedSpan.payload?.provider,
                                model: selectedSpan.payload?.model,
                                latency_ms: selectedSpan.payload?.latency_ms,
                                finish_reason: selectedSpan.payload?.finish_reason,
                                parse_ok: selectedSpan.payload?.parse_ok,
                                prompt_tokens: selectedSpan.payload?.prompt_tokens,
                                completion_tokens: selectedSpan.payload?.completion_tokens,
                                total_tokens: selectedSpan.payload?.total_tokens,
                                cost_usd: selectedSpan.payload?.cost_usd,
                              },
                              null,
                              2,
                            )}
                          </pre>
                        </TabsContent>
                      </Tabs>
                    ) : (
                      <div className="space-y-1">
                        <div className="text-muted-foreground font-medium">结构化载荷 (Payload)</div>
                        <pre className="max-h-64 overflow-auto rounded bg-muted p-2.5 font-mono text-[11px] whitespace-pre-wrap break-words">
                          {JSON.stringify(selectedSpan.payload ?? {}, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default SailTickTracePanel
