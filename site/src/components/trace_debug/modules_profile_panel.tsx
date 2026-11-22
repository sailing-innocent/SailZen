/**
 * @file modules_profile_panel.tsx
 * @brief SailZen 全业务板块 Profile、前端使用热力与系统运行时监控面板
 * @author sailing-innocent
 * @date 2026-11-23
 */
import React, { useCallback, useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  api_get_modules_profile,
  api_get_runtime_profile,
  type ModulesProfile,
  type SystemRuntimeProfile,
} from '@lib/api/telemetry'
import { AlertTriangle, Database, Eye, HardDrive, Server, Smartphone } from 'lucide-react'

function formatUptime(sec: number): string {
  const s = Math.max(0, Math.floor(sec))
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m ${s % 60}s`
}

function formatMetricVal(k: string, v: unknown): string {
  if (v === null || v === undefined) return '-'
  if (typeof v === 'number') {
    if (k.endsWith('_ratio') || k.endsWith('_rate')) return `${(v * 100).toFixed(1)}%`
    if (k.endsWith('_mb')) return `${v} MB`
    return v.toLocaleString()
  }
  return String(v)
}

const METRIC_LABEL: Record<string, string> = {
  accounts: '账户数',
  transactions_total: '总交易',
  transactions_window: '窗口交易',
  budgets: '预算数',
  untagged_count: '未打标',
  untagged_ratio: '未打标率',
  body_data_total: '身体数据总计',
  body_data_window: '窗口身体数据',
  weight_window: '窗口体重',
  diet_window: '窗口饮食',
  exercise_window: '窗口运动',
  sleep_window: '窗口睡眠',
  mood_window: '窗口情绪',
  weight_plans: '体重计划',
  affairs_total: '事务总计',
  affairs_active: '活跃事务',
  affairs_inbox: '收件箱',
  discipline_logs_window: '窗口打卡',
  time_blocks_total: '时间块',
  reviews_total: '复盘数',
  tickets_total: '总票据',
  tickets_pending: '待回票据',
  tickets_expired: '已超期',
  ticket_reply_rate: '回复率',
  messages_unread: '未读消息',
  daily_reports: '睡前日报',
  traces_window: '窗口 Trace',
  trace_success_rate: 'Trace 成功率',
  llm_fallback_rate: 'LLM 降级率',
  tokens_window: '窗口 Tokens',
  online_ws_devices: '在线 WS 设备',
  registered_devices: '注册设备',
  reminders_total: '提醒总计',
  reminders_active: '待处理提醒',
  reminders_resolved: '已完成提醒',
  works: '作品数',
  editions: '版本数',
  document_nodes: '章节节点',
  note_items: '笔记索引',
  total_chars: '总字数',
  residences: '住所',
  containers: '容器',
  items: '物资件数',
  storage_files: '存储文件',
  storage_mb: '存储占用',
  blog_files: '博客文件',
  blog_mb: '博客占用',
}

interface ModulesProfilePanelProps {
  windowDays: number
  refreshNonce: number
  onRuntimeLoaded?: (rt: SystemRuntimeProfile | null) => void
}

const ModulesProfilePanel: React.FC<ModulesProfilePanelProps> = ({
  windowDays,
  refreshNonce,
  onRuntimeLoaded,
}) => {
  const [modulesProf, setModulesProf] = useState<ModulesProfile | null>(null)
  const [runtime, setRuntime] = useState<SystemRuntimeProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [mRes, rRes] = await Promise.all([
        api_get_modules_profile(windowDays),
        api_get_runtime_profile(),
      ])
      setModulesProf(mRes)
      setRuntime(rRes)
      onRuntimeLoaded?.(rRes)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [windowDays, onRuntimeLoaded])

  useEffect(() => {
    load()
  }, [load, refreshNonce])

  return (
    <div className="space-y-4">
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-4 text-sm text-destructive">
            加载模块与运行时 Profile 失败：{error}
          </CardContent>
        </Card>
      )}

      {/* 1. SailZen 各业务板块 Profile 网格 */}
      <div>
        <div className="text-sm font-semibold mb-2">
          SailZen 各业务板块数据规模、活跃度与接口健康（近 {windowDays} 天）
        </div>
        {loading && !modulesProf && (
          <div className="text-xs text-muted-foreground py-6">加载中...</div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {(modulesProf?.modules ?? []).map((mod) => {
            const dotClass =
              mod.status === 'warning'
                ? 'bg-amber-500'
                : mod.status === 'healthy'
                  ? 'bg-emerald-500'
                  : 'bg-muted-foreground/40'
            return (
              <Card key={mod.key} className="flex flex-col">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <span className={`h-2 w-2 rounded-full ${dotClass}`} />
                      {mod.label}
                    </CardTitle>
                    <Badge
                      variant={
                        mod.status === 'warning'
                          ? 'destructive'
                          : mod.status === 'healthy'
                            ? 'secondary'
                            : 'outline'
                      }
                      className="text-[10px]"
                    >
                      {mod.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{mod.summary}</p>
                </CardHeader>
                <CardContent className="pt-0 mt-auto space-y-2.5 text-xs">
                  <div className="grid grid-cols-2 gap-x-2 gap-y-1 rounded bg-muted/40 p-2">
                    {Object.entries(mod.metrics).map(([k, v]) => (
                      <div key={k} className="flex items-center justify-between gap-1">
                        <span className="text-muted-foreground truncate">
                          {METRIC_LABEL[k] ?? k}
                        </span>
                        <span className="font-mono font-medium shrink-0">
                          {formatMetricVal(k, v)}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground border-t pt-1.5 font-mono">
                    <span>API: {mod.api_requests_window} req</span>
                    <span>P95: {Math.round(mod.api_p95_ms)}ms</span>
                    <span>Err: {(mod.api_error_rate * 100).toFixed(1)}%</span>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>

      {/* 2. Web 前端页面访问热力 & 前端异常 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <Card className="lg:col-span-6">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Eye className="h-4 w-4 text-primary" />
              Web 页面访问频次与停留时长（近 {windowDays} 天）
            </CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-muted-foreground text-left">
                  <th className="py-1.5 pr-2">页面路径</th>
                  <th className="py-1.5 pr-2 text-right">访问次数</th>
                  <th className="py-1.5 pr-2 text-right">平均停留</th>
                  <th className="py-1.5 text-right">累计停留</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {(modulesProf?.page_usage ?? []).map((p) => (
                  <tr key={p.path}>
                    <td className="py-1.5 pr-2 font-mono">{p.path}</td>
                    <td className="py-1.5 pr-2 text-right font-mono">{p.views}</td>
                    <td className="py-1.5 pr-2 text-right font-mono">{p.avg_dwell_sec}s</td>
                    <td className="py-1.5 text-right font-mono">{p.total_dwell_sec}s</td>
                  </tr>
                ))}
                {(modulesProf?.page_usage ?? []).length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-muted-foreground">
                      尚无页面访问埋点（切换页面后将自动聚合上报）
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card className="lg:col-span-6">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              前端 JS 运行时异常 ({modulesProf?.recent_client_errors.length ?? 0})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs max-h-64 overflow-y-auto">
            {(modulesProf?.recent_client_errors ?? []).map((err, i) => (
              <div
                key={err.id ?? i}
                className="rounded border border-destructive/30 bg-destructive/5 p-2 space-y-0.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono font-semibold text-destructive truncate">
                    {err.name}
                  </span>
                  <span className="font-mono text-[11px] text-muted-foreground shrink-0">
                    {err.created_at.slice(5, 19).replace('T', ' ')}
                  </span>
                </div>
                {Boolean(err.detail?.path) && (
                  <div className="text-[11px] text-muted-foreground font-mono">
                    path: {String(err.detail.path)}
                    {err.detail.filename ? ` · ${String(err.detail.filename)}:${String(err.detail.lineno ?? '')}` : ''}
                  </div>
                )}
              </div>
            ))}
            {(modulesProf?.recent_client_errors ?? []).length === 0 && (
              <div className="py-6 text-center text-muted-foreground">
                近 {windowDays} 天无前端 JS 未捕获异常 ✓
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 3. 系统运行时 Profile */}
      {runtime && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Server className="h-4 w-4 text-primary" />
              SailZen Server 运行时 Profile
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="space-y-1.5">
              <div className="font-medium text-muted-foreground flex items-center gap-1">
                <Server className="h-3.5 w-3.5" /> 进程与运行状态
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">运行时长</span>
                <span className="font-mono font-semibold">{formatUptime(runtime.uptime_seconds)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Python / DB</span>
                <span className="font-mono">
                  {runtime.python_version} / {runtime.db_backend}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">进程 RSS 内存</span>
                <span className="font-mono">
                  {runtime.memory_rss_mb != null ? `${runtime.memory_rss_mb} MB` : 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">启动以来请求 / 5xx</span>
                <span className="font-mono">
                  {runtime.total_requests_since_boot.toLocaleString()} / {runtime.total_errors_since_boot}
                </span>
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="font-medium text-muted-foreground flex items-center gap-1">
                <Smartphone className="h-3.5 w-3.5" /> WS 在线设备 & 数据目录
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">在线 Android WS</span>
                <span className="font-mono font-semibold">{runtime.online_ws_devices.length}</span>
              </div>
              {runtime.online_ws_devices.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {runtime.online_ws_devices.map((id) => (
                    <Badge key={id} variant="outline" className="font-mono text-[10px]">
                      {id}
                    </Badge>
                  ))}
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-muted-foreground flex items-center gap-1">
                  <HardDrive className="h-3 w-3" /> 数据目录体积
                </span>
                <span className="font-mono">{runtime.data_dir_size_mb} MB</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">内存待刷盘桶数</span>
                <span className="font-mono">{runtime.unflushed_buckets}</span>
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="font-medium text-muted-foreground flex items-center gap-1">
                <Database className="h-3.5 w-3.5" /> 可观测表规模
              </div>
              {Object.entries(runtime.table_counts).map(([tbl, cnt]) => (
                <div key={tbl} className="flex justify-between">
                  <span className="font-mono text-muted-foreground">{tbl}</span>
                  <span className="font-mono">{cnt.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default ModulesProfilePanel
