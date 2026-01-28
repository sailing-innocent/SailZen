# 前端性能分析框架

本文档介绍前端性能的量化方法、分析工具和监控框架实现方案，为 `packages/site` 提供系统化的性能度量能力。

## 目录

1. [核心性能指标](#1-核心性能指标)
2. [性能分析工具](#2-性能分析工具)
3. [性能监控框架实现](#3-性能监控框架实现)
4. [自动化性能测试](#4-自动化性能测试)
5. [性能基准与预算](#5-性能基准与预算)
6. [实施指南](#6-实施指南)

---

## 1. 核心性能指标

### 1.1 Web Vitals 核心指标

Google 定义的用户体验核心指标：

| 指标 | 全称 | 含义 | 良好阈值 | 需改进阈值 |
|------|------|------|---------|-----------|
| **LCP** | Largest Contentful Paint | 最大内容绘制时间 | ≤ 2.5s | > 4.0s |
| **INP** | Interaction to Next Paint | 交互到下一次绘制 | ≤ 200ms | > 500ms |
| **CLS** | Cumulative Layout Shift | 累计布局偏移 | ≤ 0.1 | > 0.25 |

### 1.2 辅助性能指标

| 指标 | 全称 | 含义 | 建议阈值 |
|------|------|------|---------|
| **FCP** | First Contentful Paint | 首次内容绘制 | ≤ 1.8s |
| **TTFB** | Time to First Byte | 首字节时间 | ≤ 800ms |
| **FID** | First Input Delay | 首次输入延迟 | ≤ 100ms |
| **TBT** | Total Blocking Time | 总阻塞时间 | ≤ 200ms |
| **TTI** | Time to Interactive | 可交互时间 | ≤ 3.8s |

### 1.3 React 特定指标

| 指标 | 含义 | 测量方式 |
|------|------|---------|
| **组件渲染时间** | 单个组件的渲染耗时 | React Profiler |
| **重渲染次数** | 不必要的重复渲染 | React DevTools |
| **提交阶段耗时** | React 提交 DOM 更新的时间 | React Profiler |
| **Effect 执行时间** | useEffect 回调执行时间 | 自定义计时 |

### 1.4 业务相关指标

针对本项目的特定指标：

| 指标 | 含义 | 目标值 |
|------|------|-------|
| **交易列表加载时间** | 从请求到渲染完成 | ≤ 1s |
| **图表渲染时间** | 图表组件从数据到显示 | ≤ 500ms |
| **筛选响应时间** | 过滤条件变化到结果显示 | ≤ 100ms |
| **页面切换时间** | 路由切换到内容显示 | ≤ 300ms |

---

## 2. 性能分析工具

### 2.1 浏览器开发者工具

#### Chrome DevTools Performance 面板

**使用方法**：

1. 打开 DevTools (F12) → Performance 标签
2. 点击录制按钮或 Ctrl+E
3. 执行需要分析的操作
4. 停止录制，分析结果

**关键分析项**：

```
┌─────────────────────────────────────────────────────────────┐
│ Summary（概览）                                              │
├─────────────────────────────────────────────────────────────┤
│ Loading    │ 网络请求和解析时间                               │
│ Scripting  │ JavaScript 执行时间（重点关注）                  │
│ Rendering  │ 样式计算、布局                                   │
│ Painting   │ 绘制、合成                                       │
│ Idle       │ 空闲时间                                         │
└─────────────────────────────────────────────────────────────┘
```

**常见问题定位**：

- **Long Task（长任务）**：超过 50ms 的任务，会阻塞主线程
- **Layout Thrashing**：频繁的强制同步布局
- **Excessive Repaints**：不必要的重绘

#### Memory 面板

**使用场景**：检测内存泄漏

```
1. 打开 Memory 标签
2. 选择 "Heap snapshot"
3. 操作前拍摄快照 A
4. 执行操作（如打开/关闭对话框多次）
5. 操作后拍摄快照 B
6. 对比两个快照，查看 "Objects allocated between Snapshot A and B"
```

### 2.2 React DevTools Profiler

**安装**：Chrome/Firefox 扩展 "React Developer Tools"

**使用方法**：

```
1. 打开 React DevTools → Profiler 标签
2. 点击录制按钮
3. 与应用交互
4. 停止录制
5. 分析火焰图和排名图
```

**关键信息**：

- **Commit 列表**：每次 React 提交（DOM 更新）
- **火焰图**：组件渲染层级和时间
- **排名图**：按渲染时间排序的组件列表
- **组件详情**：Props/State 变化原因

**识别问题**：

```
灰色组件 → 本次未重新渲染（良好）
黄色/橙色/红色 → 渲染耗时逐渐增加（需关注）

常见问题：
- 父组件更新导致所有子组件重渲染
- Props 引用变化导致的无效渲染
- Context 变化导致的大范围重渲染
```

### 2.3 Lighthouse

**使用方式**：

1. **Chrome DevTools 内置**：DevTools → Lighthouse 标签
2. **命令行**：`npx lighthouse <url>`
3. **CI 集成**：`lighthouse-ci`

**报告指标**：

```
Performance Score: 0-100
├── First Contentful Paint (10%)
├── Speed Index (10%)
├── Largest Contentful Paint (25%)
├── Total Blocking Time (30%)
└── Cumulative Layout Shift (25%)
```

**命令行使用**：

```bash
# 基本使用
npx lighthouse http://localhost:5173 --view

# 生成 JSON 报告
npx lighthouse http://localhost:5173 --output json --output-path ./report.json

# 移动端模拟
npx lighthouse http://localhost:5173 --preset perf --form-factor mobile
```

### 2.4 Web Vitals 库

**安装**：

```bash
pnpm add web-vitals
```

**基础使用**：

```typescript
import { onCLS, onINP, onLCP, onFCP, onTTFB } from 'web-vitals'

// 简单日志输出
onCLS(console.log)
onINP(console.log)
onLCP(console.log)
onFCP(console.log)
onTTFB(console.log)
```

### 2.5 其他推荐工具

| 工具 | 用途 | 特点 |
|------|------|------|
| **why-did-you-render** | 检测不必要的重渲染 | 开发时自动提示 |
| **@welldone-software/why-did-you-render** | 同上，更新版本 | React 18 支持 |
| **Bundle Analyzer** | 分析打包体积 | webpack/vite 插件 |
| **Source Map Explorer** | 分析 bundle 组成 | 可视化依赖 |

---

## 3. 性能监控框架实现

### 3.1 项目结构

```
src/lib/perf/
├── index.ts              # 导出入口
├── metrics.ts            # 指标定义和收集
├── reporter.ts           # 数据上报
├── hooks/
│   ├── useRenderTime.ts  # 渲染时间 Hook
│   ├── useTraceUpdate.ts # 更新追踪 Hook
│   └── usePerformance.ts # 综合性能 Hook
├── components/
│   ├── PerfProvider.tsx  # 性能监控 Provider
│   └── PerfOverlay.tsx   # 开发环境性能面板
└── utils/
    ├── timing.ts         # 计时工具
    └── storage.ts        # 本地存储
```

### 3.2 核心实现

#### 3.2.1 性能指标收集器 (metrics.ts)

```typescript
// src/lib/perf/metrics.ts
import { onCLS, onINP, onLCP, onFCP, onTTFB, Metric } from 'web-vitals'

export interface PerformanceMetrics {
  // Web Vitals
  lcp?: number
  inp?: number
  cls?: number
  fcp?: number
  ttfb?: number
  
  // 自定义指标
  customMetrics: Map<string, number>
  
  // 渲染追踪
  renderCounts: Map<string, number>
  renderTimes: Map<string, number[]>
}

class MetricsCollector {
  private metrics: PerformanceMetrics = {
    customMetrics: new Map(),
    renderCounts: new Map(),
    renderTimes: new Map(),
  }
  
  private listeners: Set<(metrics: PerformanceMetrics) => void> = new Set()
  
  constructor() {
    this.initWebVitals()
  }
  
  private initWebVitals() {
    const handleMetric = (metric: Metric) => {
      const key = metric.name.toLowerCase() as keyof PerformanceMetrics
      ;(this.metrics as any)[key] = metric.value
      this.notify()
    }
    
    onCLS(handleMetric)
    onINP(handleMetric)
    onLCP(handleMetric)
    onFCP(handleMetric)
    onTTFB(handleMetric)
  }
  
  // 记录自定义指标
  recordMetric(name: string, value: number) {
    this.metrics.customMetrics.set(name, value)
    this.notify()
  }
  
  // 记录组件渲染
  recordRender(componentName: string, duration: number) {
    // 更新渲染次数
    const currentCount = this.metrics.renderCounts.get(componentName) || 0
    this.metrics.renderCounts.set(componentName, currentCount + 1)
    
    // 记录渲染时间
    const times = this.metrics.renderTimes.get(componentName) || []
    times.push(duration)
    // 只保留最近 100 次
    if (times.length > 100) times.shift()
    this.metrics.renderTimes.set(componentName, times)
    
    // 超过阈值警告
    if (duration > 16) {
      console.warn(
        `[Perf] ${componentName} render took ${duration.toFixed(2)}ms (> 16ms frame budget)`
      )
    }
  }
  
  // 获取组件平均渲染时间
  getAverageRenderTime(componentName: string): number {
    const times = this.metrics.renderTimes.get(componentName)
    if (!times || times.length === 0) return 0
    return times.reduce((a, b) => a + b, 0) / times.length
  }
  
  // 订阅指标变化
  subscribe(listener: (metrics: PerformanceMetrics) => void) {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }
  
  private notify() {
    this.listeners.forEach(listener => listener(this.metrics))
  }
  
  // 获取当前所有指标
  getMetrics(): PerformanceMetrics {
    return { ...this.metrics }
  }
  
  // 获取性能报告
  getReport(): object {
    const renderStats: Record<string, { count: number; avgTime: number }> = {}
    
    this.metrics.renderCounts.forEach((count, name) => {
      renderStats[name] = {
        count,
        avgTime: this.getAverageRenderTime(name),
      }
    })
    
    return {
      webVitals: {
        lcp: this.metrics.lcp,
        inp: this.metrics.inp,
        cls: this.metrics.cls,
        fcp: this.metrics.fcp,
        ttfb: this.metrics.ttfb,
      },
      customMetrics: Object.fromEntries(this.metrics.customMetrics),
      renderStats,
      timestamp: new Date().toISOString(),
    }
  }
}

// 单例导出
export const metricsCollector = new MetricsCollector()
```

#### 3.2.2 计时工具 (timing.ts)

```typescript
// src/lib/perf/utils/timing.ts

export class Timer {
  private startTime: number = 0
  private marks: Map<string, number> = new Map()
  
  start() {
    this.startTime = performance.now()
    return this
  }
  
  mark(name: string) {
    this.marks.set(name, performance.now())
    return this
  }
  
  measure(fromMark?: string): number {
    const endTime = performance.now()
    const startTime = fromMark 
      ? (this.marks.get(fromMark) || this.startTime)
      : this.startTime
    return endTime - startTime
  }
  
  end(): number {
    return this.measure()
  }
}

// 便捷函数：测量异步操作
export async function measureAsync<T>(
  name: string,
  fn: () => Promise<T>,
  onComplete?: (duration: number) => void
): Promise<T> {
  const timer = new Timer().start()
  try {
    return await fn()
  } finally {
    const duration = timer.end()
    onComplete?.(duration)
    if (import.meta.env.DEV) {
      console.log(`[Perf] ${name}: ${duration.toFixed(2)}ms`)
    }
  }
}

// 便捷函数：测量同步操作
export function measureSync<T>(
  name: string,
  fn: () => T,
  onComplete?: (duration: number) => void
): T {
  const timer = new Timer().start()
  try {
    return fn()
  } finally {
    const duration = timer.end()
    onComplete?.(duration)
    if (import.meta.env.DEV) {
      console.log(`[Perf] ${name}: ${duration.toFixed(2)}ms`)
    }
  }
}
```

#### 3.2.3 渲染时间 Hook (useRenderTime.ts)

```typescript
// src/lib/perf/hooks/useRenderTime.ts
import { useRef, useEffect } from 'react'
import { metricsCollector } from '../metrics'

export function useRenderTime(componentName: string) {
  const renderStartTime = useRef(performance.now())
  const renderCount = useRef(0)
  
  // 每次渲染开始时记录时间
  renderStartTime.current = performance.now()
  renderCount.current += 1
  
  useEffect(() => {
    // commit 阶段完成后计算渲染时间
    const duration = performance.now() - renderStartTime.current
    metricsCollector.recordRender(componentName, duration)
  })
  
  return {
    renderCount: renderCount.current,
  }
}
```

#### 3.2.4 更新追踪 Hook (useTraceUpdate.ts)

```typescript
// src/lib/perf/hooks/useTraceUpdate.ts
import { useRef, useEffect } from 'react'

export function useTraceUpdate(componentName: string, props: Record<string, any>) {
  const prevPropsRef = useRef<Record<string, any>>({})
  
  useEffect(() => {
    const prevProps = prevPropsRef.current
    const changedProps: Record<string, { from: any; to: any }> = {}
    
    // 检查每个 prop 的变化
    const allKeys = new Set([...Object.keys(prevProps), ...Object.keys(props)])
    
    allKeys.forEach(key => {
      if (prevProps[key] !== props[key]) {
        changedProps[key] = {
          from: prevProps[key],
          to: props[key],
        }
      }
    })
    
    if (Object.keys(changedProps).length > 0) {
      console.log(`[Trace] ${componentName} updated:`, changedProps)
    }
    
    prevPropsRef.current = props
  })
}

// 使用示例
// function MyComponent(props) {
//   useTraceUpdate('MyComponent', props)
//   return <div>...</div>
// }
```

#### 3.2.5 性能 Provider (PerfProvider.tsx)

```typescript
// src/lib/perf/components/PerfProvider.tsx
import React, { createContext, useContext, useEffect, useState, Profiler } from 'react'
import { metricsCollector, PerformanceMetrics } from '../metrics'

interface PerfContextValue {
  metrics: PerformanceMetrics
  isEnabled: boolean
  toggleEnabled: () => void
}

const PerfContext = createContext<PerfContextValue | null>(null)

export function usePerfContext() {
  const context = useContext(PerfContext)
  if (!context) {
    throw new Error('usePerfContext must be used within PerfProvider')
  }
  return context
}

interface PerfProviderProps {
  children: React.ReactNode
  enabled?: boolean
}

export function PerfProvider({ children, enabled = true }: PerfProviderProps) {
  const [isEnabled, setIsEnabled] = useState(enabled)
  const [metrics, setMetrics] = useState<PerformanceMetrics>(metricsCollector.getMetrics())
  
  useEffect(() => {
    if (!isEnabled) return
    
    return metricsCollector.subscribe(setMetrics)
  }, [isEnabled])
  
  const handleRender = (
    id: string,
    phase: 'mount' | 'update' | 'nested-update',
    actualDuration: number,
    baseDuration: number,
    startTime: number,
    commitTime: number
  ) => {
    if (!isEnabled) return
    
    metricsCollector.recordRender(id, actualDuration)
    
    // 开发环境警告慢渲染
    if (import.meta.env.DEV && actualDuration > 16) {
      console.warn(
        `[Profiler] ${id} (${phase}): ${actualDuration.toFixed(2)}ms actual, ${baseDuration.toFixed(2)}ms base`
      )
    }
  }
  
  return (
    <PerfContext.Provider
      value={{
        metrics,
        isEnabled,
        toggleEnabled: () => setIsEnabled(prev => !prev),
      }}
    >
      {isEnabled ? (
        <Profiler id="App" onRender={handleRender}>
          {children}
        </Profiler>
      ) : (
        children
      )}
    </PerfContext.Provider>
  )
}
```

#### 3.2.6 开发环境性能面板 (PerfOverlay.tsx)

```typescript
// src/lib/perf/components/PerfOverlay.tsx
import React, { useState, useEffect } from 'react'
import { usePerfContext } from './PerfProvider'
import { metricsCollector } from '../metrics'

export function PerfOverlay() {
  const { metrics, isEnabled, toggleEnabled } = usePerfContext()
  const [isExpanded, setIsExpanded] = useState(false)
  const [fps, setFps] = useState(60)
  
  // FPS 计算
  useEffect(() => {
    if (!isEnabled) return
    
    let frameCount = 0
    let lastTime = performance.now()
    let rafId: number
    
    const measureFps = () => {
      frameCount++
      const now = performance.now()
      
      if (now - lastTime >= 1000) {
        setFps(Math.round(frameCount * 1000 / (now - lastTime)))
        frameCount = 0
        lastTime = now
      }
      
      rafId = requestAnimationFrame(measureFps)
    }
    
    rafId = requestAnimationFrame(measureFps)
    return () => cancelAnimationFrame(rafId)
  }, [isEnabled])
  
  // 只在开发环境显示
  if (!import.meta.env.DEV) return null
  
  const getVitalColor = (value: number | undefined, good: number, poor: number) => {
    if (value === undefined) return 'text-gray-400'
    if (value <= good) return 'text-green-500'
    if (value <= poor) return 'text-yellow-500'
    return 'text-red-500'
  }
  
  return (
    <div className="fixed bottom-4 right-4 z-50">
      {/* 收起状态：只显示 FPS */}
      {!isExpanded && (
        <button
          onClick={() => setIsExpanded(true)}
          className="bg-black/80 text-white px-3 py-2 rounded-lg text-sm font-mono"
        >
          {fps} FPS
          {metrics.lcp && ` | LCP: ${metrics.lcp.toFixed(0)}ms`}
        </button>
      )}
      
      {/* 展开状态：完整面板 */}
      {isExpanded && (
        <div className="bg-black/90 text-white p-4 rounded-lg min-w-[300px] font-mono text-xs">
          <div className="flex justify-between items-center mb-3">
            <span className="font-bold">Performance Monitor</span>
            <div className="flex gap-2">
              <button
                onClick={toggleEnabled}
                className={`px-2 py-1 rounded ${isEnabled ? 'bg-green-600' : 'bg-gray-600'}`}
              >
                {isEnabled ? 'ON' : 'OFF'}
              </button>
              <button
                onClick={() => setIsExpanded(false)}
                className="px-2 py-1 rounded bg-gray-600"
              >
                ×
              </button>
            </div>
          </div>
          
          {/* FPS */}
          <div className="mb-3">
            <span className={fps >= 55 ? 'text-green-500' : fps >= 30 ? 'text-yellow-500' : 'text-red-500'}>
              FPS: {fps}
            </span>
          </div>
          
          {/* Web Vitals */}
          <div className="mb-3 space-y-1">
            <div className="text-gray-400">Web Vitals</div>
            <div className={getVitalColor(metrics.lcp, 2500, 4000)}>
              LCP: {metrics.lcp?.toFixed(0) || '-'}ms
            </div>
            <div className={getVitalColor(metrics.inp, 200, 500)}>
              INP: {metrics.inp?.toFixed(0) || '-'}ms
            </div>
            <div className={getVitalColor(metrics.cls, 0.1, 0.25)}>
              CLS: {metrics.cls?.toFixed(3) || '-'}
            </div>
            <div className={getVitalColor(metrics.fcp, 1800, 3000)}>
              FCP: {metrics.fcp?.toFixed(0) || '-'}ms
            </div>
            <div className={getVitalColor(metrics.ttfb, 800, 1800)}>
              TTFB: {metrics.ttfb?.toFixed(0) || '-'}ms
            </div>
          </div>
          
          {/* 渲染统计 */}
          <div className="space-y-1">
            <div className="text-gray-400">Render Stats (Top 5)</div>
            {Array.from(metrics.renderCounts.entries())
              .sort((a, b) => b[1] - a[1])
              .slice(0, 5)
              .map(([name, count]) => (
                <div key={name} className="flex justify-between">
                  <span className="truncate max-w-[180px]">{name}</span>
                  <span>
                    {count}x | {metricsCollector.getAverageRenderTime(name).toFixed(1)}ms
                  </span>
                </div>
              ))}
          </div>
          
          {/* 导出报告 */}
          <button
            onClick={() => {
              const report = metricsCollector.getReport()
              console.log('[Perf Report]', report)
              navigator.clipboard.writeText(JSON.stringify(report, null, 2))
              alert('Performance report copied to clipboard')
            }}
            className="mt-3 w-full bg-blue-600 py-1 rounded"
          >
            Export Report
          </button>
        </div>
      )}
    </div>
  )
}
```

### 3.3 使用方式

#### 在应用入口集成

```typescript
// src/main.tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { PerfProvider, PerfOverlay } from '@/lib/perf'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PerfProvider enabled={import.meta.env.DEV}>
      <App />
      <PerfOverlay />
    </PerfProvider>
  </React.StrictMode>
)
```

#### 在组件中使用

```typescript
// 示例：在 TransactionsDataTable 中使用
import { useRenderTime, measureAsync } from '@/lib/perf'

const TransactionsDataTable: React.FC = () => {
  // 追踪渲染时间
  const { renderCount } = useRenderTime('TransactionsDataTable')
  
  // 追踪数据加载时间
  useEffect(() => {
    measureAsync('fetchTransactions', async () => {
      await fetchTransactions(maxTransactions)
    }, (duration) => {
      metricsCollector.recordMetric('transactions_load_time', duration)
    })
  }, [])
  
  // ...
}
```

---

## 4. 自动化性能测试

### 4.1 使用 Playwright 进行性能测试

**安装**：

```bash
pnpm add -D @playwright/test
```

**配置文件**：

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/performance',
  use: {
    baseURL: 'http://localhost:5173',
  },
})
```

**性能测试示例**：

```typescript
// tests/performance/money-page.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Money Page Performance', () => {
  test('should load within performance budget', async ({ page }) => {
    // 开始性能追踪
    await page.goto('/money')
    
    // 使用 Performance API
    const metrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming
      const paint = performance.getEntriesByType('paint')
      
      return {
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.startTime,
        loadComplete: navigation.loadEventEnd - navigation.startTime,
        firstPaint: paint.find(p => p.name === 'first-paint')?.startTime,
        firstContentfulPaint: paint.find(p => p.name === 'first-contentful-paint')?.startTime,
      }
    })
    
    console.log('Performance Metrics:', metrics)
    
    // 断言性能预算
    expect(metrics.domContentLoaded).toBeLessThan(3000)
    expect(metrics.firstContentfulPaint).toBeLessThan(2000)
  })
  
  test('should render transaction table efficiently', async ({ page }) => {
    await page.goto('/money')
    
    // 等待表格加载
    await page.waitForSelector('[data-testid="transactions-table"]')
    
    // 测量滚动性能
    const scrollMetrics = await page.evaluate(async () => {
      const table = document.querySelector('[data-testid="transactions-table"]')
      if (!table) return null
      
      const frames: number[] = []
      let lastTime = performance.now()
      
      // 滚动并测量帧率
      return new Promise<{ avgFrameTime: number; minFps: number }>((resolve) => {
        const measureFrame = () => {
          const now = performance.now()
          frames.push(now - lastTime)
          lastTime = now
          
          if (frames.length < 60) {
            requestAnimationFrame(measureFrame)
          } else {
            const avgFrameTime = frames.reduce((a, b) => a + b) / frames.length
            const minFps = 1000 / Math.max(...frames)
            resolve({ avgFrameTime, minFps })
          }
        }
        
        // 触发滚动
        table.scrollTop = 0
        requestAnimationFrame(() => {
          table.scrollTo({ top: 1000, behavior: 'smooth' })
          requestAnimationFrame(measureFrame)
        })
      })
    })
    
    if (scrollMetrics) {
      expect(scrollMetrics.avgFrameTime).toBeLessThan(20) // 50+ FPS
      expect(scrollMetrics.minFps).toBeGreaterThan(30)
    }
  })
})
```

### 4.2 Lighthouse CI 集成

**安装**：

```bash
pnpm add -D @lhci/cli
```

**配置文件**：

```javascript
// lighthouserc.js
module.exports = {
  ci: {
    collect: {
      url: ['http://localhost:5173/', 'http://localhost:5173/money', 'http://localhost:5173/health'],
      numberOfRuns: 3,
      startServerCommand: 'pnpm preview',
      startServerReadyPattern: 'Local:',
    },
    assert: {
      assertions: {
        'categories:performance': ['error', { minScore: 0.8 }],
        'first-contentful-paint': ['warn', { maxNumericValue: 2000 }],
        'largest-contentful-paint': ['error', { maxNumericValue: 3000 }],
        'cumulative-layout-shift': ['warn', { maxNumericValue: 0.1 }],
        'total-blocking-time': ['warn', { maxNumericValue: 300 }],
      },
    },
    upload: {
      target: 'temporary-public-storage',
    },
  },
}
```

**运行**：

```bash
npx lhci autorun
```

### 4.3 Bundle 分析

**Vite 配置**：

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  plugins: [
    visualizer({
      filename: 'dist/bundle-analysis.html',
      open: true,
      gzipSize: true,
      brotliSize: true,
    }),
  ],
})
```

**运行分析**：

```bash
pnpm build
# 自动打开 bundle-analysis.html
```

---

## 5. 性能基准与预算

### 5.1 性能预算定义

```typescript
// src/lib/perf/budget.ts
export const PERFORMANCE_BUDGET = {
  // 页面加载
  pageLoad: {
    fcp: 1800,      // First Contentful Paint
    lcp: 2500,      // Largest Contentful Paint
    tti: 3800,      // Time to Interactive
    tbt: 200,       // Total Blocking Time
  },
  
  // 交互响应
  interaction: {
    inp: 200,       // Interaction to Next Paint
    filterResponse: 100,  // 筛选响应时间
    navigationDelay: 300, // 页面切换时间
  },
  
  // 渲染性能
  render: {
    frameTime: 16,        // 单帧时间（60fps）
    componentRender: 16,  // 组件渲染时间
    listRender: 100,      // 长列表渲染
    chartRender: 500,     // 图表渲染
  },
  
  // 资源大小
  bundle: {
    mainJs: 200 * 1024,   // 主 JS 包（200KB）
    mainCss: 50 * 1024,   // 主 CSS（50KB）
    totalInitial: 500 * 1024, // 初始加载总大小
  },
  
  // 内存
  memory: {
    heapLimit: 50 * 1024 * 1024, // 50MB 堆内存
    detachedNodes: 100,   // 分离的 DOM 节点数
  },
}

// 检查是否超出预算
export function checkBudget(metric: string, value: number): {
  passed: boolean
  budget: number
  overage?: number
} {
  const parts = metric.split('.')
  let budget: number | undefined
  
  let current: any = PERFORMANCE_BUDGET
  for (const part of parts) {
    current = current?.[part]
  }
  budget = current
  
  if (budget === undefined) {
    return { passed: true, budget: Infinity }
  }
  
  const passed = value <= budget
  return {
    passed,
    budget,
    overage: passed ? undefined : value - budget,
  }
}
```

### 5.2 性能评分系统

```typescript
// src/lib/perf/scoring.ts

interface ScoreResult {
  score: number       // 0-100
  grade: 'A' | 'B' | 'C' | 'D' | 'F'
  details: Record<string, { value: number; score: number; weight: number }>
}

export function calculatePerformanceScore(metrics: {
  lcp?: number
  inp?: number
  cls?: number
  fcp?: number
  tbt?: number
}): ScoreResult {
  const weights = {
    lcp: 0.25,
    inp: 0.25,
    cls: 0.25,
    fcp: 0.15,
    tbt: 0.10,
  }
  
  const thresholds = {
    lcp: { good: 2500, poor: 4000 },
    inp: { good: 200, poor: 500 },
    cls: { good: 0.1, poor: 0.25 },
    fcp: { good: 1800, poor: 3000 },
    tbt: { good: 200, poor: 600 },
  }
  
  const scoreMetric = (value: number, good: number, poor: number): number => {
    if (value <= good) return 100
    if (value >= poor) return 0
    return 100 * (1 - (value - good) / (poor - good))
  }
  
  const details: ScoreResult['details'] = {}
  let totalScore = 0
  let totalWeight = 0
  
  for (const [key, weight] of Object.entries(weights)) {
    const value = metrics[key as keyof typeof metrics]
    if (value !== undefined) {
      const { good, poor } = thresholds[key as keyof typeof thresholds]
      const score = scoreMetric(value, good, poor)
      details[key] = { value, score, weight }
      totalScore += score * weight
      totalWeight += weight
    }
  }
  
  const finalScore = totalWeight > 0 ? totalScore / totalWeight : 0
  
  const getGrade = (score: number): ScoreResult['grade'] => {
    if (score >= 90) return 'A'
    if (score >= 75) return 'B'
    if (score >= 50) return 'C'
    if (score >= 25) return 'D'
    return 'F'
  }
  
  return {
    score: Math.round(finalScore),
    grade: getGrade(finalScore),
    details,
  }
}
```

---

## 6. 实施指南

### 6.1 快速开始

1. **创建性能模块目录**

```bash
mkdir -p src/lib/perf/hooks src/lib/perf/components src/lib/perf/utils
```

2. **安装依赖**

```bash
pnpm add web-vitals
pnpm add -D @playwright/test @lhci/cli rollup-plugin-visualizer
```

3. **复制核心文件**

按照上述代码创建以下文件：
- `src/lib/perf/metrics.ts`
- `src/lib/perf/utils/timing.ts`
- `src/lib/perf/hooks/useRenderTime.ts`
- `src/lib/perf/components/PerfProvider.tsx`
- `src/lib/perf/components/PerfOverlay.tsx`
- `src/lib/perf/index.ts`

4. **导出入口**

```typescript
// src/lib/perf/index.ts
export { metricsCollector, type PerformanceMetrics } from './metrics'
export { Timer, measureAsync, measureSync } from './utils/timing'
export { useRenderTime } from './hooks/useRenderTime'
export { useTraceUpdate } from './hooks/useTraceUpdate'
export { PerfProvider, usePerfContext } from './components/PerfProvider'
export { PerfOverlay } from './components/PerfOverlay'
export { PERFORMANCE_BUDGET, checkBudget } from './budget'
export { calculatePerformanceScore } from './scoring'
```

5. **集成到应用**

修改 `src/main.tsx`，添加 PerfProvider 和 PerfOverlay。

### 6.2 日常使用流程

```
开发阶段
├── 开启 PerfOverlay 实时监控
├── 使用 useRenderTime 追踪可疑组件
├── 使用 React DevTools Profiler 深入分析
└── 使用 Chrome Performance 分析复杂问题

提交前
├── 运行 Lighthouse 本地测试
├── 检查 Bundle 大小变化
└── 确保不违反性能预算

CI/CD
├── 自动运行 Lighthouse CI
├── 性能报告存档
└── 预算违反时阻止合并
```

### 6.3 性能问题排查流程

```
发现卡顿
    │
    ▼
┌─────────────────────────────┐
│ 1. 查看 PerfOverlay FPS     │
│    - FPS < 30: 严重问题     │
│    - FPS 30-50: 需要优化    │
│    - FPS > 50: 可接受       │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 2. 检查 Web Vitals          │
│    - LCP > 2.5s: 加载慢     │
│    - INP > 200ms: 交互慢    │
│    - CLS > 0.1: 布局抖动    │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 3. 查看渲染统计             │
│    - 高渲染次数组件         │
│    - 高平均渲染时间组件     │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 4. 深入分析                 │
│    - React Profiler         │
│    - Chrome Performance     │
│    - Memory 面板            │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 5. 定位根因                 │
│    - 不必要的重渲染？       │
│    - 大数据处理？           │
│    - 内存泄漏？             │
│    - 网络请求？             │
└─────────────────────────────┘
    │
    ▼
  实施优化并验证
```

---

## 参考资源

- [Web Vitals](https://web.dev/vitals/)
- [Chrome DevTools Performance](https://developer.chrome.com/docs/devtools/performance/)
- [React Profiler](https://react.dev/reference/react/Profiler)
- [Lighthouse](https://developer.chrome.com/docs/lighthouse/)
- [Performance Budget](https://web.dev/performance-budgets-101/)

---

## 更新记录

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-01-28 | v1.0 | 初始文档，包含性能指标、工具、监控框架实现 |
