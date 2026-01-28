# 移动端适配

本文档记录 `packages/site` 前端项目的移动端适配现状分析、问题清单、修复方案和组件化优化建议。

---

## 1. 当前适配机制

### 1.1 核心 Hook

项目已实现统一的移动端检测 Hook：

```typescript
// src/hooks/use-mobile.ts
const MOBILE_BREAKPOINT = 768

export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined)
  // 使用 window.matchMedia 监听窗口变化
  // ...
  return !!isMobile
}
```

**断点**: 768px（与 Tailwind 的 `md:` 断点一致）

### 1.2 已适配组件（可作为参考模式）

| 组件 | 适配策略 | 位置 |
|------|----------|------|
| `PageLayout` | 移动端使用 `MobileNav`，桌面端使用侧边栏 | `src/components/page_layout.tsx` |
| `Statistics` | 使用 `useIsMobile` 切换 `flex-col`/`flex-row` | `src/components/statistics.tsx` |
| `TransactionsDataTable` | 移动端减少分页数量、隐藏部分列 | `src/components/transactions_data_table.tsx` |
| `BudgetsDataTable` | 移动端隐藏部分列 `hidden md:block` | `src/components/budgets_data_table.tsx` |
| `MobileNav` | 使用 Sheet 组件实现抽屉导航 | `src/components/mobile_nav.tsx` |

---

## 2. 问题清单

### 2.1 严重问题（P0）

#### 2.1.1 Project 页面布局未适配

**文件**: `src/pages/project.tsx`

**问题描述**:
```tsx
<div className="grid grid-cols-5 gap-6">
    <div className="col-span-3">
        <ProjectMissionBoard />
    </div>
    <div className="col-span-2">
        <QuarterBiweekCalendar />
    </div>
</div>
```

- `grid-cols-5` 固定 5 列布局，移动端会严重挤压
- `col-span-3` 和 `col-span-2` 无法在移动端正确显示
- 两个大组件横向排列，移动端完全无法使用

**影响**: 移动端布局完全错乱，内容不可读

---

#### 2.1.2 Project Mission Board 横向溢出

**文件**: `src/components/project_mission_board.tsx`

**问题描述**:
```tsx
<div className="flex flex-row items-center justify-center">
    <ProjectMissionColumn ... />
    {projects.map((project) => (
        <ProjectMissionColumn ... />
    ))}
</div>
```

- 使用 `flex-row` 横向布局，多个项目列并排
- 未检测移动端，也无 `overflow-x-auto`
- 随着项目增加，横向溢出越严重

**影响**: 移动端内容超出屏幕，需要横向滚动或完全不可见

---

#### 2.1.3 体重页面完全未适配

**文件**: `src/pages/health.tsx`

**问题描述**:
```tsx
<div className="flex gap-4">
    <DatePicker label="Start Date" ... />
    <DatePicker label="End Date" ... />
    <div className="flex flex-col gap-3">
        <Select className="w-[180px]"> ... </Select>
    </div>
    <div className="flex flex-col gap-3">
        <Dialog> ... </Dialog>
    </div>
</div>
```

- 4 个控件横向排列，移动端完全溢出
- 未使用 `useIsMobile`
- 固定宽度 `w-[180px]`、`w-48` 不适应移动端
- 日期选择器无响应式处理

**影响**: 移动端表单控件横向溢出，无法正常操作

---

#### 2.1.4 体重图表未适配

**文件**: `src/components/weight_chart.tsx`

**问题描述**:
```tsx
<LineChart data={data} margin={{ right: 30, left: 30 }}>
```

- 未使用 `useIsMobile`
- 固定 margin 值，移动端可能不够紧凑
- 图表最小高度 `min-h-[200px]` 可能过大

**影响**: 图表在移动端显示效果不佳

---

### 2.2 中等问题（P1）

#### 2.2.1 季度双周日历不适配

**文件**: `src/components/quarter_biweek_calendar.tsx`

**问题描述**:
```tsx
<Calendar
    numberOfMonths={3}  // 固定显示3个月
    ...
/>

<div className="flex flex-wrap items-center gap-3 mb-4">
    <Select>年份</Select>
    <Select>月份</Select>
    <Select>季度</Select>
    <Select>双周</Select>
    <Button>今天</Button>
</div>
```

- `numberOfMonths={3}` 固定显示 3 个月，移动端空间不足
- 5 个控件横向排列，`flex-wrap` 虽有但布局仍然拥挤
- 未使用 `useIsMobile` 动态调整月数

**影响**: 移动端日历过窄，选择器按钮拥挤

---

#### 2.2.2 Project Mission Column 无响应式

**文件**: `src/components/project_mission_column.tsx`

**问题描述**:
```tsx
<div className="flex flex-col items-center justify-center">
    <h1 className="text-2xl font-bold mb-4">Project Mission Column</h1>
    ...
</div>
```

- 未使用 `useIsMobile`
- 标题 `text-2xl` 固定大小
- 无响应式间距和字体调整

**影响**: 配合 Board 组件使用时，在移动端显示不佳

---

#### 2.2.3 统计图表固定高度

**文件**: `src/components/statistics.tsx`

**问题描述**:
```tsx
<ChartContainer config={chartConfig} className="h-[300px]">
```

- 图表高度固定 `h-[300px]`
- 移动端屏幕较小时，300px 高度可能过大
- 图例在小屏幕上可能拥挤

**影响**: 移动端图表占用空间过大

---

### 2.3 轻微问题（P2）

#### 2.3.1 `use-mobile.ts` 初始状态

**问题**:
```tsx
const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined)
// ...
return !!isMobile  // 初始为 false
```

- 初始值为 `undefined`，转换为 `false`
- 首次渲染可能显示桌面布局，然后闪烁为移动布局
- 无 SSR 支持

**影响**: 首屏可能出现布局闪烁

---

#### 2.3.2 缺少 CSS 媒体查询降级

**问题**: 
- 完全依赖 JavaScript 检测移动端
- 若 JS 未加载或延迟，无响应式布局

**影响**: JavaScript 未执行时无响应式能力

---

## 3. 修复方案

### 3.1 Project 页面修复

**文件**: `src/pages/project.tsx`

```tsx
import { useIsMobile } from '@/hooks/use-mobile'

const ProjectPage = () => {
    const isMobile = useIsMobile()
    
    return (
        <PageLayout>
            <div className="flex items-center justify-between px-2 md:px-0">
                <div className="text-xl md:text-2xl font-bold">项目管理</div>
                <div className="flex gap-2">
                    <AddMissionDialog />
                    <AddProjectDialog />
                </div>
            </div>
            
            {/* 响应式网格布局 */}
            <div className={`grid gap-4 md:gap-6 ${
                isMobile 
                    ? 'grid-cols-1' 
                    : 'grid-cols-5'
            }`}>
                <div className={isMobile ? '' : 'col-span-3'}>
                    <ProjectMissionBoard projects={projects} missions={missions} />
                </div>
                <div className={isMobile ? '' : 'col-span-2'}>
                    <QuarterBiweekCalendar />
                </div>
            </div>
        </PageLayout>
    )
}
```

**或使用纯 Tailwind 方案**:
```tsx
<div className="grid grid-cols-1 lg:grid-cols-5 gap-4 md:gap-6">
    <div className="lg:col-span-3">
        <ProjectMissionBoard />
    </div>
    <div className="lg:col-span-2">
        <QuarterBiweekCalendar />
    </div>
</div>
```

---

### 3.2 Project Mission Board 修复

**文件**: `src/components/project_mission_board.tsx`

```tsx
import { useIsMobile } from '@/hooks/use-mobile'

const ProjectMissionBoard: React.FC<ProjectMissionBoardProps> = ({ projects, missions }) => {
    const isMobile = useIsMobile()
    
    return (
        <div className="flex flex-col items-center justify-center">
            <h1 className={`font-bold mb-4 ${isMobile ? 'text-lg' : 'text-2xl'}`}>
                Project Mission Board
            </h1>
            
            {/* 移动端垂直布局，桌面端横向滚动 */}
            <div className={`flex items-start gap-4 ${
                isMobile 
                    ? 'flex-col w-full' 
                    : 'flex-row overflow-x-auto pb-4'
            }`}>
                <ProjectMissionColumn 
                    key={NullProject.id} 
                    project={NullProject} 
                    missions={groupedMissions[NullProject.id] || []} 
                />
                {projects.map((project) => (
                    <ProjectMissionColumn 
                        key={project.id} 
                        project={project} 
                        missions={groupedMissions[project.id] || []} 
                    />
                ))}
            </div>            
        </div>
    )
}
```

---

### 3.3 体重页面修复

**文件**: `src/pages/health.tsx`

```tsx
import { useIsMobile } from '@/hooks/use-mobile'

const HealthPage = () => {
    const isMobile = useIsMobile()
    
    return (
        <PageLayout>
            <div className={isMobile ? 'text-lg' : 'text-xl'}>体重管理</div>
            
            {/* 响应式控件布局 */}
            <div className={`flex gap-3 ${isMobile ? 'flex-col' : 'flex-row flex-wrap'}`}>
                <div className={`flex gap-3 ${isMobile ? 'flex-col' : 'flex-row'}`}>
                    <DatePicker label="Start Date" ... />
                    <DatePicker label="End Date" ... />
                </div>
                
                <div className="flex flex-col gap-2">
                    <Label htmlFor="date-span" className="px-1 text-sm">
                        Date Span
                    </Label>
                    <Select ...>
                        <SelectTrigger className={isMobile ? 'w-full' : 'w-[180px]'}>
                            <SelectValue placeholder="Select DateSpan" />
                        </SelectTrigger>
                        ...
                    </Select>
                </div>
                
                <div className="flex flex-col gap-2">
                    <Label htmlFor="add-weight" className="px-1 text-sm">
                        Add Weight
                    </Label>
                    <Dialog>
                        <DialogTrigger className={isMobile ? 'w-full' : 'w-48'}>
                            <Input id="add-weight" placeholder="Add Weight" />
                        </DialogTrigger>
                        ...
                    </Dialog>
                </div>
            </div>
            
            <WeightChart />
        </PageLayout>
    )
}
```

---

### 3.4 体重图表修复

**文件**: `src/components/weight_chart.tsx`

```tsx
import { useIsMobile } from '@/hooks/use-mobile'

const WeightChart: React.FC = () => {
    const isMobile = useIsMobile()
    
    return (
        <div className="flex flex-col items-center justify-center">
            <h2 className={`font-bold mb-4 ${isMobile ? 'text-lg' : 'text-xl'}`}>
                Weight Chart
            </h2>
            
            {isLoading ? (
                <div className="w-full space-y-3">Loading...</div>
            ) : weights.length > 0 ? (
                <div className="w-full">
                    <ChartContainer 
                        config={chartConfig} 
                        className={isMobile ? 'min-h-[150px] w-full' : 'min-h-[200px] w-full'}
                    >
                        <LineChart 
                            data={data} 
                            margin={isMobile 
                                ? { right: 10, left: 10, top: 10, bottom: 10 } 
                                : { right: 30, left: 30 }
                            }
                        >
                            ...
                        </LineChart>
                    </ChartContainer>
                </div>
            ) : (
                <div>No weight data available.</div>
            )}
        </div>
    )
}
```

---

### 3.5 季度双周日历修复

**文件**: `src/components/quarter_biweek_calendar.tsx`

```tsx
import { useIsMobile } from '@/hooks/use-mobile'

export default function QuarterBiweekCalendar() {
    const isMobile = useIsMobile()
    
    return (
        <Card className="w-full">
            <CardHeader className={isMobile ? 'px-3 py-2' : ''}>
                <CardTitle className={isMobile ? 'text-lg' : ''}>
                    季度与双周日历
                </CardTitle>
            </CardHeader>
            <CardContent className={isMobile ? 'px-2' : ''}>
                {/* 响应式选择器布局 */}
                <div className={`flex flex-wrap items-center gap-2 mb-4 ${
                    isMobile ? 'flex-col' : ''
                }`}>
                    <div className={`flex gap-2 ${isMobile ? 'w-full' : ''}`}>
                        <Select value={String(year)} ...>
                            <SelectTrigger className={isMobile ? 'flex-1' : ''}>
                                <SelectValue placeholder="选择年份" />
                            </SelectTrigger>
                            ...
                        </Select>
                        
                        <Select value={String(quarter)} ...>
                            <SelectTrigger className={isMobile ? 'flex-1' : ''}>
                                <SelectValue placeholder="选择季度" />
                            </SelectTrigger>
                            ...
                        </Select>
                    </div>
                    
                    <div className={`flex gap-2 ${isMobile ? 'w-full' : ''}`}>
                        <Select value={biweekIndex ? String(biweekIndex) : undefined} ...>
                            <SelectTrigger className={isMobile ? 'flex-1' : ''}>
                                <SelectValue placeholder="选择双周" />
                            </SelectTrigger>
                            ...
                        </Select>
                        
                        <Button variant="outline" ...>今天</Button>
                    </div>
                </div>

                {/* 响应式日历 */}
                <div className="overflow-x-auto">
                    <Calendar
                        key={`${year}-${quarter}-single`}
                        month={calendarMonthAnchor}
                        numberOfMonths={isMobile ? 1 : 3}  // 移动端显示1个月
                        ...
                    />
                </div>
                
                ...
            </CardContent>
        </Card>
    )
}
```

---

### 3.6 Project Mission Column 修复

**文件**: `src/components/project_mission_column.tsx`

```tsx
import { useIsMobile } from '@/hooks/use-mobile'

const ProjectMissionColumn: React.FC<ProjectMissionColumnProps> = ({ project, missions }) => {
    const isMobile = useIsMobile()
    
    return (
        <div className={`flex flex-col ${
            isMobile 
                ? 'w-full p-3 border rounded-lg mb-3' 
                : 'items-center justify-center min-w-[250px]'
        }`}>
            <h2 className={`font-bold mb-2 ${isMobile ? 'text-base' : 'text-lg'}`}>
                {projectDisplayData.name}
            </h2>
            <p className="text-sm text-muted-foreground">{projectDisplayData.description}</p>
            <p className="text-xs text-muted-foreground">
                {projectDisplayData.start_time_qbw.get_fmt_string()} - 
                {projectDisplayData.end_time_qbw.get_fmt_string()}
            </p>
            
            <div className="flex flex-col gap-2 mt-3">
                {missions.map((mission) => (
                    <div key={mission.id} className="p-2 bg-muted rounded">
                        <h3 className="text-sm font-medium">{mission.name}</h3>
                        <p className="text-xs text-muted-foreground">{mission.description}</p>
                    </div>
                ))}
            </div>
        </div>
    )
}
```

---

## 4. 组件化优化建议

### 4.1 创建响应式容器组件

建议创建统一的响应式布局组件，减少重复代码：

```tsx
// src/components/ui/responsive-container.tsx
import { useIsMobile } from '@/hooks/use-mobile'

interface ResponsiveContainerProps {
    children: React.ReactNode
    mobileClass?: string
    desktopClass?: string
    className?: string
}

export const ResponsiveContainer: React.FC<ResponsiveContainerProps> = ({
    children,
    mobileClass = 'flex-col',
    desktopClass = 'flex-row',
    className = ''
}) => {
    const isMobile = useIsMobile()
    
    return (
        <div className={`flex gap-4 ${isMobile ? mobileClass : desktopClass} ${className}`}>
            {children}
        </div>
    )
}
```

**使用示例**:
```tsx
<ResponsiveContainer mobileClass="flex-col gap-2" desktopClass="flex-row gap-6">
    <Card>...</Card>
    <Card>...</Card>
</ResponsiveContainer>
```

---

### 4.2 创建响应式网格组件

```tsx
// src/components/ui/responsive-grid.tsx
import { useIsMobile } from '@/hooks/use-mobile'

interface ResponsiveGridProps {
    children: React.ReactNode
    mobileCols?: number
    desktopCols?: number
    gap?: string
    className?: string
}

export const ResponsiveGrid: React.FC<ResponsiveGridProps> = ({
    children,
    mobileCols = 1,
    desktopCols = 3,
    gap = '4',
    className = ''
}) => {
    const isMobile = useIsMobile()
    const cols = isMobile ? mobileCols : desktopCols
    
    return (
        <div 
            className={`grid gap-${gap} ${className}`}
            style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
        >
            {children}
        </div>
    )
}
```

---

### 4.3 创建响应式图表容器

```tsx
// src/components/ui/responsive-chart.tsx
import { useIsMobile } from '@/hooks/use-mobile'

interface ResponsiveChartContainerProps {
    children: React.ReactNode
    mobileHeight?: string
    desktopHeight?: string
    config: any
}

export const ResponsiveChartContainer: React.FC<ResponsiveChartContainerProps> = ({
    children,
    mobileHeight = '200px',
    desktopHeight = '300px',
    config
}) => {
    const isMobile = useIsMobile()
    
    return (
        <ChartContainer 
            config={config} 
            className={`w-full`}
            style={{ height: isMobile ? mobileHeight : desktopHeight }}
        >
            {children}
        </ChartContainer>
    )
}
```

---

### 4.4 优化 use-mobile Hook

```tsx
// src/hooks/use-mobile.ts (改进版)
import * as React from "react"

const MOBILE_BREAKPOINT = 768

// 服务端渲染时的默认值
const getInitialValue = (): boolean => {
    if (typeof window === 'undefined') {
        return false // SSR 默认桌面端
    }
    return window.innerWidth < MOBILE_BREAKPOINT
}

export function useIsMobile() {
    const [isMobile, setIsMobile] = React.useState<boolean>(getInitialValue)

    React.useEffect(() => {
        const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
        const onChange = () => {
            setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
        }
        
        // 立即设置正确值（避免闪烁）
        setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
        
        mql.addEventListener("change", onChange)
        return () => mql.removeEventListener("change", onChange)
    }, [])

    return isMobile
}

// 导出断点常量，便于 CSS 媒体查询保持一致
export const MOBILE_BREAKPOINT_PX = MOBILE_BREAKPOINT
```

---

### 4.5 添加 CSS 媒体查询降级

在 `src/index.css` 添加基础的 CSS 媒体查询：

```css
/* 移动端基础样式降级 */
@media (max-width: 767px) {
    /* 确保 JS 未加载时也有基础响应式 */
    .mobile-stack {
        flex-direction: column !important;
    }
    
    .mobile-full-width {
        width: 100% !important;
    }
    
    .mobile-hide {
        display: none !important;
    }
    
    .mobile-small-text {
        font-size: 0.875rem !important;
    }
}
```

---

## 5. 实施优先级

| 优先级 | 任务 | 工作量 |
|--------|------|--------|
| P0 | 修复 Project 页面布局 | 1h |
| P0 | 修复 ProjectMissionBoard 横向溢出 | 1h |
| P0 | 修复体重页面布局 | 2h |
| P0 | 修复体重图表适配 | 0.5h |
| P1 | 修复季度双周日历 | 1.5h |
| P1 | 修复 ProjectMissionColumn | 0.5h |
| P1 | 优化统计图表高度 | 0.5h |
| P2 | 优化 use-mobile Hook | 0.5h |
| P2 | 添加 CSS 降级样式 | 0.5h |
| P2 | 创建响应式组件库 | 2h |

---

## 6. 测试检查清单

- [ ] Project 页面在 375px 宽度下正常显示
- [ ] ProjectMissionBoard 多项目时无横向溢出
- [ ] 体重页面表单控件可正常操作
- [ ] 体重图表在移动端清晰可读
- [ ] 季度日历在移动端显示 1 个月
- [ ] 所有按钮和输入框可正常点击
- [ ] 页面切换无明显布局闪烁
- [ ] 侧边栏在移动端正确收起

---

## 7. 隐患排查

### 7.1 潜在问题组件

以下组件虽未明显报错，但可能存在隐患：

1. **`DatePicker`** - 日历弹窗在移动端可能超出屏幕
2. **`Dialog`** - 对话框内容在移动端可能需要滚动
3. **`Select`** - 下拉菜单在移动端位置可能不合适
4. **`Tooltip`** - 移动端不支持 hover，需考虑 touch 事件

### 7.2 建议的全局检查

1. 检查所有使用 `w-[固定宽度]` 的地方
2. 检查所有 `grid-cols-N`（N > 1）的地方
3. 检查所有 `flex-row` 横向排列的地方
4. 检查所有固定 `margin`/`padding` 值

---

## 更新记录

| 日期 | 内容 |
|------|------|
| 2026-01-28 | 初始分析，完成问题清单和修复方案 |
