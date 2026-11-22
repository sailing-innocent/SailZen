/**
 * @file trace_debug.tsx
 * @brief SailZen Trace & Profile Debug 专区（SailTick AI Trace + API 性能 + 全板块 Profile）
 * @author sailing-innocent
 * @date 2026-11-23
 */
import React, { useEffect, useState } from 'react'
import PageLayout from '@components/page_layout'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import SailTickTracePanel from '@/components/trace_debug/sailtick_trace_panel'
import ApiProfilePanel from '@/components/trace_debug/api_profile_panel'
import ModulesProfilePanel from '@/components/trace_debug/modules_profile_panel'
import type { SailTickLiveStatus, SystemRuntimeProfile } from '@lib/api/telemetry'
import { Activity, Bot, Gauge, Layers, RefreshCw } from 'lucide-react'

type WindowKey = '24h' | '7d' | '30d'

const WINDOW_CONFIG: Record<WindowKey, { label: string; days: number; hours: number }> = {
  '24h': { label: '24 小时', days: 1, hours: 24 },
  '7d': { label: '7 天', days: 7, hours: 168 },
  '30d': { label: '30 天', days: 30, hours: 720 },
}

const TraceDebugPage: React.FC = () => {
  const [windowKey, setWindowKey] = useState<WindowKey>('7d')
  const [autoRefreshSec, setAutoRefreshSec] = useState<number>(0)
  const [refreshNonce, setRefreshNonce] = useState<number>(0)
  const [sailtickLive, setSailtickLive] = useState<SailTickLiveStatus | null>(null)
  const [runtime, setRuntime] = useState<SystemRuntimeProfile | null>(null)

  useEffect(() => {
    if (autoRefreshSec <= 0) return
    const timer = setInterval(() => {
      setRefreshNonce((n) => n + 1)
    }, autoRefreshSec * 1000)
    return () => clearInterval(timer)
  }, [autoRefreshSec])

  const win = WINDOW_CONFIG[windowKey]

  return (
    <PageLayout>
      <div className="p-4 md:p-6 w-full max-w-7xl mx-auto space-y-4">
        {/* 顶栏标题与全局控制 */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary" />
              SailZen Trace &amp; Profile Debug
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              SailTick AI 唤醒-执行全链路追踪 · 服务端 API 性能剖析 · 全业务板块长期 Profile
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* 时间窗口切换 */}
            <div className="inline-flex rounded-md border bg-background p-0.5">
              {(Object.keys(WINDOW_CONFIG) as WindowKey[]).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setWindowKey(k)}
                  className={`px-2.5 py-1 text-xs rounded transition-colors ${
                    windowKey === k
                      ? 'bg-primary text-primary-foreground font-medium'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {WINDOW_CONFIG[k].label}
                </button>
              ))}
            </div>

            {/* 自动刷新 */}
            <select
              className="h-8 rounded-md border bg-background px-2 text-xs"
              value={autoRefreshSec}
              onChange={(e) => setAutoRefreshSec(Number(e.target.value))}
            >
              <option value={0}>自动刷新: 关</option>
              <option value={15}>每 15 秒</option>
              <option value={30}>每 30 秒</option>
            </select>

            <Button
              size="sm"
              variant="outline"
              onClick={() => setRefreshNonce((n) => n + 1)}
            >
              <RefreshCw className="h-3.5 w-3.5 mr-1" />
              刷新
            </Button>
          </div>
        </div>

        {/* 快速状态摘要条 */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge variant={sailtickLive?.reachable ? 'default' : 'outline'}>
            SailTick: {sailtickLive ? (sailtickLive.reachable ? 'Online' : 'Offline') : '...'}
          </Badge>
          {sailtickLive?.health?.canary?.mode && (
            <Badge variant="secondary">Canary: {sailtickLive.health.canary.mode}</Badge>
          )}
          {runtime && (
            <>
              <Badge variant="outline">DB: {runtime.db_backend}</Badge>
              <Badge variant="outline">
                WS 在线设备: {runtime.online_ws_devices.length}
              </Badge>
              {runtime.memory_rss_mb != null && (
                <Badge variant="outline">RSS: {runtime.memory_rss_mb} MB</Badge>
              )}
            </>
          )}
        </div>

        {/* 主功能专区 Tabs */}
        <Tabs defaultValue="sailtick" className="w-full space-y-4">
          <TabsList>
            <TabsTrigger value="sailtick" className="gap-1.5">
              <Bot className="h-4 w-4" />
              SailTick AI Trace
            </TabsTrigger>
            <TabsTrigger value="api" className="gap-1.5">
              <Gauge className="h-4 w-4" />
              API 性能 Profile
            </TabsTrigger>
            <TabsTrigger value="modules" className="gap-1.5">
              <Layers className="h-4 w-4" />
              全板块 &amp; 运行时 Profile
            </TabsTrigger>
          </TabsList>

          <TabsContent value="sailtick">
            <SailTickTracePanel
              windowDays={win.days}
              refreshNonce={refreshNonce}
              onLiveStatusChange={setSailtickLive}
            />
          </TabsContent>

          <TabsContent value="api">
            <ApiProfilePanel windowHours={win.hours} refreshNonce={refreshNonce} />
          </TabsContent>

          <TabsContent value="modules">
            <ModulesProfilePanel
              windowDays={win.days}
              refreshNonce={refreshNonce}
              onRuntimeLoaded={setRuntime}
            />
          </TabsContent>
        </Tabs>
      </div>
    </PageLayout>
  )
}

export default TraceDebugPage
