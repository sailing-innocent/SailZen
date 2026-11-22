/**
 * @file api_profile_panel.tsx
 * @brief SailZen 服务端 API 性能、吞吐、延迟分布与慢请求 Profile 面板
 * @author sailing-innocent
 * @date 2026-11-23
 */
import React, { useCallback, useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api_get_api_profile, type ApiProfile } from '@lib/api/telemetry'
import { AlertCircle, Gauge, Network, Timer } from 'lucide-react'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function formatTimeShort(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 19)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

interface ApiProfilePanelProps {
  windowHours: number
  refreshNonce: number
}

const ApiProfilePanel: React.FC<ApiProfilePanelProps> = ({ windowHours, refreshNonce }) => {
  const [profile, setProfile] = useState<ApiProfile | null>(null)
  const [endpointMode, setEndpointMode] = useState<'slow' | 'hot'>('slow')
  const [includeSelf, setIncludeSelf] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api_get_api_profile(windowHours, includeSelf)
      setProfile(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [windowHours, includeSelf])

  useEffect(() => {
    load()
  }, [load, refreshNonce])

  const endpoints =
    endpointMode === 'slow'
      ? profile?.top_slow_endpoints ?? []
      : profile?.top_called_endpoints ?? []

  return (
    <div className="space-y-4">
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-4 text-sm text-destructive">
            加载 API Profile 失败：{error}
          </CardContent>
        </Card>
      )}

      {/* 1. 全局性能 KPI */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Network className="h-3.5 w-3.5" /> API 总请求量
            </div>
            <div className="text-2xl font-bold mt-1">
              {(profile?.total_requests ?? 0).toLocaleString()}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              下行流量 {formatBytes(profile?.total_bytes_out ?? 0)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Gauge className="h-3.5 w-3.5" /> P50 / P95 / P99 延迟
            </div>
            <div className="text-2xl font-bold mt-1">
              {profile ? `${Math.round(profile.p95_ms)}ms` : '-'}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              P50 {Math.round(profile?.p50_ms ?? 0)}ms · P99 {Math.round(profile?.p99_ms ?? 0)}ms · 均值{' '}
              {Math.round(profile?.avg_ms ?? 0)}ms
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <AlertCircle className="h-3.5 w-3.5" /> 错误率 (4xx / 5xx)
            </div>
            <div
              className={`text-2xl font-bold mt-1 ${
                (profile?.total_5xx ?? 0) > 0 ? 'text-destructive' : ''
              }`}
            >
              {profile ? `${(profile.error_rate * 100).toFixed(2)}%` : '-'}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              4xx: {profile?.total_4xx ?? 0} · 5xx: {profile?.total_5xx ?? 0}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Timer className="h-3.5 w-3.5" /> 慢请求 (&ge;{profile?.slow_threshold_ms ?? 300}ms)
            </div>
            <div className="text-2xl font-bold mt-1">{profile?.slow_requests_count ?? 0}</div>
            <div className="text-xs text-muted-foreground mt-1">
              峰值延迟 {Math.round(profile?.max_ms ?? 0)}ms
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 2. 模块请求量与 P95 延迟对比图 + 客户端分布 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <Card className="lg:col-span-8">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm">各模块请求量与 P95 延迟分布</CardTitle>
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={includeSelf}
                onChange={(e) => setIncludeSelf(e.target.checked)}
              />
              包含 telemetry 自身请求
            </label>
          </CardHeader>
          <CardContent className="h-64">
            {profile && profile.by_module.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={profile.by_module}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="module" tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="left" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="right" orientation="right" unit="ms" tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar yAxisId="left" dataKey="req_count" name="请求数" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="p95_ms"
                    name="P95 (ms)"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                {loading ? '加载中...' : '当前时间窗口暂无业务 API 流量数据'}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">客户端流量来源</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5 text-xs">
            {Object.entries(profile?.by_client ?? {})
              .sort((a, b) => b[1] - a[1])
              .map(([client, cnt]) => {
                const pct =
                  profile && profile.total_requests > 0
                    ? Math.round((cnt / profile.total_requests) * 100)
                    : 0
                return (
                  <div key={client} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="font-mono text-[11px]">
                        {client}
                      </Badge>
                      <span className="font-mono text-muted-foreground">
                        {cnt.toLocaleString()} ({pct}%)
                      </span>
                    </div>
                    <div className="h-1.5 rounded bg-muted overflow-hidden">
                      <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
            {Object.keys(profile?.by_client ?? {}).length === 0 && (
              <div className="text-muted-foreground py-6 text-center">暂无流量记录</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 3. 端点性能排行（最慢 / 最热） */}
      <Card>
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm">接口端点 Profile 排行</CardTitle>
          <div className="flex gap-1.5">
            <Button
              size="sm"
              variant={endpointMode === 'slow' ? 'default' : 'outline'}
              className="h-7 text-xs"
              onClick={() => setEndpointMode('slow')}
            >
              最慢端点 (P95)
            </Button>
            <Button
              size="sm"
              variant={endpointMode === 'hot' ? 'default' : 'outline'}
              className="h-7 text-xs"
              onClick={() => setEndpointMode('hot')}
            >
              最高频端点
            </Button>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b text-muted-foreground text-left">
                <th className="py-2 pr-2">模块</th>
                <th className="py-2 pr-2">端点</th>
                <th className="py-2 pr-2 text-right">请求数</th>
                <th className="py-2 pr-2 text-right">均值</th>
                <th className="py-2 pr-2 text-right">P95</th>
                <th className="py-2 pr-2 text-right">峰值</th>
                <th className="py-2 text-right">错误率</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {endpoints.map((ep) => (
                <tr key={`${ep.method}-${ep.endpoint}`} className="hover:bg-muted/30">
                  <td className="py-1.5 pr-2">
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {ep.module}
                    </Badge>
                  </td>
                  <td className="py-1.5 pr-2 font-mono">
                    <span className="font-semibold mr-1.5">{ep.method}</span>
                    {ep.endpoint}
                  </td>
                  <td className="py-1.5 pr-2 text-right font-mono">{ep.req_count}</td>
                  <td className="py-1.5 pr-2 text-right font-mono">{Math.round(ep.avg_ms)}ms</td>
                  <td
                    className={`py-1.5 pr-2 text-right font-mono font-semibold ${
                      ep.p95_ms >= 300 ? 'text-amber-600' : ''
                    }`}
                  >
                    {Math.round(ep.p95_ms)}ms
                  </td>
                  <td className="py-1.5 pr-2 text-right font-mono">{Math.round(ep.max_ms)}ms</td>
                  <td
                    className={`py-1.5 text-right font-mono ${
                      ep.err_5xx > 0 ? 'text-destructive font-semibold' : ''
                    }`}
                  >
                    {(ep.error_rate * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
              {endpoints.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-muted-foreground">
                    暂无端点性能记录
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* 4. 最近慢请求 & 5xx 异常明细 */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">
            最近慢请求与 5xx 异常明细 ({profile?.recent_notable.length ?? 0})
          </CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b text-muted-foreground text-left">
                <th className="py-2 pr-2">时间</th>
                <th className="py-2 pr-2">类型</th>
                <th className="py-2 pr-2">接口</th>
                <th className="py-2 pr-2">来源</th>
                <th className="py-2 pr-2 text-right">状态码</th>
                <th className="py-2 text-right">耗时</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {(profile?.recent_notable ?? []).map((ev, idx) => (
                <tr key={ev.id ?? `mem-${idx}`} className="hover:bg-muted/30">
                  <td className="py-1.5 pr-2 font-mono text-muted-foreground whitespace-nowrap">
                    {formatTimeShort(ev.created_at)}
                  </td>
                  <td className="py-1.5 pr-2">
                    <Badge
                      variant={ev.category === 'api_error' ? 'destructive' : 'secondary'}
                      className="text-[10px]"
                    >
                      {ev.category}
                    </Badge>
                  </td>
                  <td className="py-1.5 pr-2 font-mono">
                    <div>{ev.name}</div>
                    {Boolean(ev.detail?.error) && (
                      <div className="text-destructive text-[11px] truncate max-w-md">
                        {String(ev.detail.error)}
                      </div>
                    )}
                  </td>
                  <td className="py-1.5 pr-2 font-mono">{ev.client_source}</td>
                  <td className="py-1.5 pr-2 text-right font-mono">{ev.status_code ?? '-'}</td>
                  <td className="py-1.5 text-right font-mono font-semibold">
                    {ev.duration_ms != null ? `${Math.round(ev.duration_ms)}ms` : '-'}
                  </td>
                </tr>
              ))}
              {(profile?.recent_notable ?? []).length === 0 && (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-muted-foreground">
                    暂无慢请求或 5xx 异常，运行健康 ✓
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}

export default ApiProfilePanel
