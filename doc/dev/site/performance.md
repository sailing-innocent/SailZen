# 性能问题优化文档

本文档记录了 `packages/site` 前端应用中识别出的性能问题及其优化建议，重点关注财务管理页面（MoneyPage）和体重管理页面（HealthPage）的性能问题。

## 目录

1. [问题概览](#问题概览)
2. [数据加载与状态管理问题](#1-数据加载与状态管理问题)
3. [渲染性能问题](#2-渲染性能问题)
4. [图表渲染问题](#3-图表渲染问题)
5. [移动端特定问题](#4-移动端特定问题)
6. [内存管理问题](#5-内存管理问题)
7. [表格性能问题](#6-表格性能问题)
8. [Effect 依赖问题](#7-effect-依赖问题)
9. [优化实施路线图](#优化实施路线图)

---

## 问题概览

当前应用在以下场景下出现明显卡顿：

- **财务管理页面**：一次性加载 2048 条交易记录，加载账户、预算数据，并渲染多个统计图表
- **体重管理页面**：加载 4096 条体重记录并渲染 LineChart 图表

主要问题类别：

| 类别 | 严重程度 | 影响范围 |
|------|---------|---------|
| 大数据集无分页加载 | 🔴 高 | 所有页面 |
| 组件缺少 Memoization | 🔴 高 | 列表/表格组件 |
| 图表重复渲染 | 🟡 中 | 统计页面 |
| Store 选择器优化不足 | 🟡 中 | 全局 |
| 内存中对象重复创建 | 🟡 中 | 表格单元格 |

---

## 1. 数据加载与状态管理问题

### 1.1 大数据集一次性加载（严重）

**问题描述**：

```typescript
// transactions_data_table.tsx:20
const maxTransactions = 2048

// health.tsx:60
fetchWeights(0, 4096, startDateUnix, endDateUnix)
```

应用一次性从后端加载全部数据到内存，无服务端分页：

- 交易记录：最多 2048 条
- 体重记录：最多 4096 条

**影响**：
- 首次加载时间长，用户感知明显延迟
- 大量数据占用内存，移动端内存有限更易卡顿
- 所有过滤、排序、分页都在客户端进行，计算密集

**优化建议**：

```typescript
// 实现服务端分页
interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  pageSize: number
}

// 修改 fetchTransactions 支持分页
fetchTransactions: async (page: number, pageSize: number, filters?: TransactionFilters) => {
  const response = await api_get_transactions_paginated(page, pageSize, filters)
  set({ 
    transactions: response.data,
    totalCount: response.total,
    isLoading: false 
  })
}
```

### 1.2 Store 设计导致的重复加载

**问题描述**：

```typescript
// money.ts:268-282 - consumeBudget 每次都重新加载所有预算
consumeBudget: async (id: number, consume: BudgetConsumeProps) => {
  const transaction = await api_consume_budget(id, consume)
  // 触发重新加载
  set((state: BudgetsState) => ({ ...state, isLoading: true }))
  // 重新获取所有预算
  const budgets = await api_get_budgets()
  set({ budgets: budgets, isLoading: false })
  return transaction
}
```

每次单项操作（消费、链接、取消链接）都会重新加载整个预算列表。

**优化建议**：

```typescript
// 仅更新受影响的单项
consumeBudget: async (id: number, consume: BudgetConsumeProps) => {
  const transaction = await api_consume_budget(id, consume)
  // 只更新受影响的预算
  const updatedBudget = await api_get_budget(id)
  set((state: BudgetsState) => ({
    ...state,
    budgets: state.budgets.map(b => b.id === id ? updatedBudget : b)
  }))
  return transaction
}
```

### 1.3 Statistics 组件 API 调用过多

**问题描述**：

```typescript
// statistics.tsx:226-237
const results = await Promise.all(
  allRequests.map(async ({ key, request }) => {
    try {
      const stats = await api_get_transactions_stats(request)
      return { key, stats }
    } catch (error) {
      return { key, stats: null }
    }
  })
)
```

对于每个时间周期 × 每个标签都发起独立的 API 请求。例如：
- 12 个月 × 9 个标签 = 108 次 API 调用
- 加上总支出、大宗项目等额外调用

**优化建议**：

1. **后端聚合**：实现批量统计 API，一次请求返回所有统计数据
2. **请求合并**：将多个标签的请求合并为一次
3. **缓存策略**：实现数据缓存，相同时间范围内不重复请求

```typescript
// 建议的批量 API
interface BatchStatsRequest {
  periods: Array<{ from: number; to: number; key: string }>
  tags: string[]
}

const stats = await api_get_transactions_stats_batch(batchRequest)
```

---

## 2. 渲染性能问题

### 2.1 组件缺少 Memoization（严重）

**问题描述**：

```typescript
// transaction_column.tsx:84-105 - 每行都创建新的 Dialog 组件
{
  id: 'edit',
  header: 'Edit',
  cell: ({ row }) => {
    return (
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="outline">Edit</Button>
        </DialogTrigger>
        <DialogContent>
          <TransactionEditCard transactionId={row.original.id} />
        </DialogContent>
      </Dialog>
    )
  },
}
```

每次表格渲染时，每行都会创建新的 Dialog 和 TransactionEditCard 实例。

**优化建议**：

```typescript
// 1. 使用 React.memo 包装行组件
const MemoizedEditCell = React.memo(({ transactionId }: { transactionId: number }) => {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline">Edit</Button>
      </DialogTrigger>
      <DialogContent>
        <TransactionEditCard transactionId={transactionId} />
      </DialogContent>
    </Dialog>
  )
})

// 2. 或者使用单一 Dialog 实例配合状态管理
const [editingId, setEditingId] = useState<number | null>(null)
// 只渲染一个 Dialog，根据 editingId 切换内容
```

### 2.2 列表渲染中的重复计算

**问题描述**：

```typescript
// transactions_data_table.tsx:144-171
const transactionsDisplay: TransactionDisplayProps[] = useMemo(() => {
  return filteredTransactions.map((transaction) => {
    // 每次都使用 find() 查找账户
    const fromAccount = accounts.find((acc) => acc.id === transaction.from_acc_id)
    const toAccount = accounts.find((acc) => acc.id === transaction.to_acc_id)
    // ...
  })
}, [filteredTransactions, accounts])
```

对于每条交易记录，都使用 `Array.find()` 查找账户，时间复杂度 O(n×m)。

**优化建议**：

```typescript
// 使用 Map 进行 O(1) 查找
const accountsMap = useMemo(() => {
  return new Map(accounts.map(acc => [acc.id, acc]))
}, [accounts])

const transactionsDisplay = useMemo(() => {
  return filteredTransactions.map((transaction) => {
    const fromAccount = accountsMap.get(transaction.from_acc_id)
    const toAccount = accountsMap.get(transaction.to_acc_id)
    return {
      ...transaction,
      from_acc_name: fromAccount?.name || 'Unknown',
      to_acc_name: toAccount?.name || 'Unknown',
    }
  })
}, [filteredTransactions, accountsMap])
```

### 2.3 标签解析重复执行

**问题描述**：

```typescript
// transaction_column.tsx:67-81
cell: ({ row }) => {
  const tags: string = row.getValue('tags')
  // 每次渲染都重新解析
  const tagList = tags
    .split(',')
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0)
  // ...
}
```

每次表格单元格渲染时都重新解析标签字符串。

**优化建议**：

```typescript
// 在数据预处理阶段完成解析
interface TransactionDisplayProps extends TransactionData {
  from_acc_name: string
  to_acc_name: string
  parsedTags: string[]  // 预解析的标签数组
}

// 在 transactionsDisplay useMemo 中预处理
parsedTags: transaction.tags
  .split(',')
  .map(tag => tag.trim())
  .filter(tag => tag.length > 0)
```

### 2.4 Zustand Store 选择器问题

**问题描述**：

```typescript
// transactions_data_table.tsx:53-60
const transactions = useTransactionsStore((state: TransactionsState) => state.transactions)
const isLoading = useTransactionsStore((state: TransactionsState) => state.isLoading)
const fetchTransactions = useTransactionsStore((state: TransactionsState) => state.fetchTransactions)
const createTransaction = useTransactionsStore((state: TransactionsState) => state.createTransaction)
```

多个独立的 Store 选择器调用，每次 Store 更新都会触发多次组件重新评估。

**优化建议**：

```typescript
// 使用浅比较合并多个选择器
import { shallow } from 'zustand/shallow'

const { transactions, isLoading, fetchTransactions, createTransaction } = useTransactionsStore(
  (state) => ({
    transactions: state.transactions,
    isLoading: state.isLoading,
    fetchTransactions: state.fetchTransactions,
    createTransaction: state.createTransaction,
  }),
  shallow
)
```

---

## 3. 图表渲染问题

### 3.1 WeightChart 数据处理

**问题描述**：

```typescript
// weight_chart.tsx:15-18
const data = weights.map((weight) => ({
  value: parseFloat(weight.value),
  timestamp: weight.htime * 1000,
}))
```

每次组件渲染都创建新的数据数组，导致 Recharts 完全重新渲染。

**优化建议**：

```typescript
// 使用 useMemo 缓存图表数据
const chartData = useMemo(() => {
  return weights.map((weight) => ({
    value: parseFloat(weight.value),
    timestamp: weight.htime * 1000,
  }))
}, [weights])

// chartConfig 也需要缓存
const chartConfig = useMemo(() => ({
  desktop: { label: 'Desktop', color: '#2563eb' },
  mobile: { label: 'Mobile', color: '#60a5fa' },
}), [])
```

### 3.2 Statistics 图表性能

**问题描述**：

```typescript
// statistics.tsx:467-480
<ChartTooltip
  content={
    <ChartTooltipContent
      formatter={(_value, _name) => {
        const value = _value as number
        // 每次 tooltip 显示都创建新的 Money 对象
        const money = new Money(value)
        return (
          <div>
            <div>{_name}:{money.toFormattedString()}</div>
          </div>
        )
      }}
    />
  }
/>
```

Tooltip formatter 内部创建对象会导致频繁的内存分配。

**优化建议**：

```typescript
// 1. 使用稳定的 formatter 函数
const tooltipFormatter = useCallback((_value: number, _name: string) => {
  return (
    <div>
      <div>{_name}: {new Money(_value).toFormattedString()}</div>
    </div>
  )
}, [])

// 2. 或者预格式化数据
const formattedData = useMemo(() => 
  overallExpenseData.map(item => ({
    ...item,
    '支出总体_formatted': new Money(item['支出总体'] as number).toFormattedString(),
    // ...
  }))
, [overallExpenseData])
```

### 3.3 多图表同时渲染

**问题描述**：

Statistics 组件同时渲染多个 LineChart：
- 支出总体趋势图
- 日常消费趋势图
- 大宗项目详情
- 日常消费详情

所有图表在组件加载时一起渲染，加重初始渲染负担。

**优化建议**：

```typescript
// 使用虚拟化或懒加载
import { useInView } from 'react-intersection-observer'

const ChartSection = ({ data, config }) => {
  const { ref, inView } = useInView({
    triggerOnce: true,
    rootMargin: '200px',
  })

  return (
    <div ref={ref}>
      {inView ? (
        <LineChart data={data} {...config} />
      ) : (
        <Skeleton className="h-[300px]" />
      )}
    </div>
  )
}
```

---

## 4. 移动端特定问题

### 4.1 useIsMobile Hook 重复创建监听器

**问题描述**：

```typescript
// use-mobile.ts
export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined)

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    }
    mql.addEventListener("change", onChange)
    // ...
  }, [])

  return !!isMobile
}
```

每个使用 `useIsMobile` 的组件都会创建独立的 MediaQuery 监听器。在一个页面中可能有 10+ 个组件使用此 Hook。

**优化建议**：

```typescript
// 使用全局 Context 共享移动端状态
const MobileContext = React.createContext<boolean>(false)

export function MobileProvider({ children }: { children: React.ReactNode }) {
  const [isMobile, setIsMobile] = React.useState(
    typeof window !== 'undefined' ? window.innerWidth < MOBILE_BREAKPOINT : false
  )

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    const onChange = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    mql.addEventListener("change", onChange)
    return () => mql.removeEventListener("change", onChange)
  }, [])

  return (
    <MobileContext.Provider value={isMobile}>
      {children}
    </MobileContext.Provider>
  )
}

export function useIsMobile() {
  return React.useContext(MobileContext)
}
```

### 4.2 条件样式导致的布局抖动

**问题描述**：

```typescript
// transactions_data_table.tsx:178
<CardHeader className={`${isMobile ? 'px-4 py-3' : ''}`}>

// 多处使用条件 className
className={`${isMobile ? 'w-full order-2' : 'w-[30%] min-w-[300px]'}`}
```

当 `isMobile` 状态变化时（如旋转屏幕），会导致大量 DOM 元素的样式重新计算。

**优化建议**：

```typescript
// 使用 CSS 媒体查询代替 JS 条件判断
// 在 CSS 中定义响应式样式
.card-header {
  @apply px-4 py-3;
  
  @screen md {
    @apply px-6 py-4;
  }
}

// 组件中使用固定类名
<CardHeader className="card-header">
```

### 4.3 移动端分页状态变化

**问题描述**：

```typescript
// transactions_data_table.tsx:46-51
React.useEffect(() => {
  setPagination(prev => ({
    ...prev,
    pageSize: isMobile ? 5 : 10,
  }))
}, [isMobile])
```

`isMobile` 变化时会更新分页状态，可能导致数据重新过滤和表格重新渲染。

**优化建议**：

```typescript
// 使用 CSS 隐藏行而非改变数据量
// 或者将 pageSize 与 isMobile 解耦
const getInitialPageSize = () => {
  if (typeof window === 'undefined') return 10
  return window.innerWidth < 768 ? 5 : 10
}

const [pagination, setPagination] = React.useState<PaginationState>({
  pageIndex: 0,
  pageSize: getInitialPageSize(),
})
// 不再响应 isMobile 变化更新 pageSize
```

---

## 5. 内存管理问题

### 5.1 渲染时重复创建对象

**问题描述**：

```typescript
// transaction_column.tsx:56-62
cell: ({ row }) => {
  const value: number = parseFloat(row.getValue('value'))
  // 每次渲染创建新的 Intl.NumberFormat 实例
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'CNY',
  }).format(value)
}

// budgets_data_table.tsx:42-43
cell: ({ row }) => {
  // 每次渲染创建新的 Money 实例
  const amount = new Money(row.getValue('amount') as string)
  return <div className="text-right font-semibold">{amount.format()}</div>
}
```

**优化建议**：

```typescript
// 1. 缓存格式化器实例
const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'CNY',
})

// 在列定义外部创建
cell: ({ row }) => {
  const value = parseFloat(row.getValue('value'))
  return currencyFormatter.format(value)
}

// 2. 对于 Money 类，考虑静态格式化方法
class Money {
  static format(value: string | number): string {
    // 避免创建实例
    return formatMoneyValue(value)
  }
}
```

### 5.2 闭包捕获问题

**问题描述**：

```typescript
// budgets_data_table.tsx:466-497
<Button
  onClick={async (e) => {
    e.stopPropagation()
    if (window.confirm('确定要取消链接此交易记录吗？')) {
      try {
        await unlinkTransaction(transaction.id)
        const analysis = await getBudgetAnalysis(budget.id)
        setBudgetsWithStats((prev) =>
          prev.map((b) =>
            b.id === budget.id
              ? { ...b, transactions: analysis.transactions || [] }
              : b
          )
        )
        setDataUpdated(false)
      } catch (error) {
        // ...
      }
    }
  }}
>
```

内联事件处理器捕获了外部作用域的多个变量（`transaction`, `budget`, `unlinkTransaction` 等），每行都创建新的闭包。

**优化建议**：

```typescript
// 使用 useCallback 并通过参数传递必要数据
const handleUnlinkTransaction = useCallback(async (transactionId: number, budgetId: number) => {
  if (!window.confirm('确定要取消链接此交易记录吗？')) return
  
  try {
    await unlinkTransaction(transactionId)
    const analysis = await getBudgetAnalysis(budgetId)
    setBudgetsWithStats((prev) =>
      prev.map((b) =>
        b.id === budgetId ? { ...b, transactions: analysis.transactions || [] } : b
      )
    )
    setDataUpdated(false)
  } catch (error) {
    console.error('Error unlinking transaction:', error)
    alert('取消链接失败，请稍后重试')
  }
}, [unlinkTransaction, getBudgetAnalysis])

// 使用时
<Button onClick={() => handleUnlinkTransaction(transaction.id, budget.id)}>
```

---

## 6. 表格性能问题

### 6.1 TanStack Table 配置重复创建

**问题描述**：

```typescript
// data_table.tsx:38-57
const tableConfig = React.useMemo(() => ({
  data,
  columns,
  getCoreRowModel: getCoreRowModel(),
  getPaginationRowModel: getPaginationRowModel(),
  getSortedRowModel: getSortedRowModel(),
  getFilteredRowModel: getFilteredRowModel(),
  // ... 更多配置
}), [data, columns, sorting, columnFilters, pagination, setPagination, keepPaginationOnDataChange])
```

虽然使用了 `useMemo`，但依赖项过多（7个），任一变化都会重新创建配置对象。

**优化建议**：

```typescript
// 分离静态配置和动态状态
const staticConfig = useMemo(() => ({
  getCoreRowModel: getCoreRowModel(),
  getPaginationRowModel: getPaginationRowModel(),
  getSortedRowModel: getSortedRowModel(),
  getFilteredRowModel: getFilteredRowModel(),
  autoResetPageIndex: !keepPaginationOnDataChange,
  enableRowSelection: false,
  enableMultiRowSelection: false,
}), [keepPaginationOnDataChange])

const table = useReactTable({
  data,
  columns,
  ...staticConfig,
  state: { sorting, columnFilters, pagination },
  onSortingChange: setSorting,
  onColumnFiltersChange: setColumnFilters,
  onPaginationChange: setPagination,
})
```

### 6.2 客户端完整数据处理

**问题描述**：

当前所有过滤、排序、分页都在客户端进行：

```typescript
// transactions_data_table.tsx:86-126
const filteredTransactions = useMemo(() => {
  return transactions.filter((transaction) => {
    // 日期过滤
    // 标签过滤
    // 金额过滤
    return true
  })
}, [transactions, filters])
```

对于 2000+ 条记录，每次过滤条件变化都要遍历全部数据。

**优化建议**：

1. **服务端过滤**：将过滤逻辑移至后端
2. **防抖处理**：过滤条件变化时添加防抖

```typescript
import { useDebouncedValue } from '@mantine/hooks'  // 或自行实现

const [debouncedFilters] = useDebouncedValue(filters, 300)

const filteredTransactions = useMemo(() => {
  return transactions.filter((transaction) => {
    // 使用 debouncedFilters
  })
}, [transactions, debouncedFilters])
```

---

## 7. Effect 依赖问题

### 7.1 级联 Effect

**问题描述**：

```typescript
// health.tsx:56-75
React.useEffect(() => {
  fetchWeights(0, 4096, startDateUnix, endDateUnix)
}, [fetchWeights, startDate, endDate])

React.useEffect(() => {
  // 当 dateSpan 变化时更新 startDate 和 endDate
  setStartDate(newStartDate)
  setEndDate(now)
}, [dateSpan])
```

`dateSpan` 变化 → 触发第二个 Effect → 更新 `startDate/endDate` → 触发第一个 Effect → 发起 API 请求

这种级联可能导致多次不必要的渲染。

**优化建议**：

```typescript
// 合并为单一 Effect
React.useEffect(() => {
  let startDateToUse = startDate
  let endDateToUse = endDate
  
  // 如果有预设时间段，使用预设计算
  if (dateSpan !== 'custom') {
    const option = dateSpanSelectOptions.find((opt) => opt.value === dateSpan)
    if (option) {
      startDateToUse = option.getDate()
      endDateToUse = new Date()
    }
  }
  
  const startDateUnix = Math.floor(startDateToUse.getTime() / 1000)
  const endDateUnix = Math.floor(endDateToUse.getTime() / 1000)
  fetchWeights(0, 4096, startDateUnix, endDateUnix)
}, [fetchWeights, dateSpan, startDate, endDate])
```

### 7.2 Statistics Effect 依赖不稳定

**问题描述**：

```typescript
// statistics.tsx:336-337
useEffect(() => {
  const fetchStatistics = async () => { /* ... */ }
  fetchStatistics()
}, [selectedTimeRange, getSupportedTags])
```

`getSupportedTags` 是从 Store 获取的函数引用，每次 Store 更新都可能变化。

**优化建议**：

```typescript
// 直接获取标签列表作为依赖
const supportedTags = useTransactionsStore((state) => state.getSupportedTags())

useEffect(() => {
  const fetchStatistics = async () => {
    // 使用 supportedTags
  }
  fetchStatistics()
}, [selectedTimeRange, supportedTags])  // 使用数据而非函数
```

---

## 优化实施路线图

### 第一阶段：立即可行的优化（1-2天）

1. **添加 useMemo/useCallback**
   - 缓存 `transactionsDisplay` 中的 accounts Map
   - 缓存图表数据和配置
   - 稳定化事件处理器

2. **Store 选择器优化**
   - 使用 `shallow` 比较合并多个选择器

3. **移除渲染时对象创建**
   - 缓存 `Intl.NumberFormat` 实例
   - 预处理标签解析

### 第二阶段：中期优化（3-5天）

1. **useIsMobile 重构**
   - 实现 MobileProvider Context

2. **表格优化**
   - 分离 TanStack Table 静态/动态配置
   - 添加过滤防抖

3. **图表懒加载**
   - 实现图表区域 IntersectionObserver


---

## 性能监控建议

### 开发阶段

```typescript
// 在开发环境启用 React Profiler
import { Profiler } from 'react'

const onRenderCallback = (
  id: string,
  phase: 'mount' | 'update',
  actualDuration: number,
) => {
  if (actualDuration > 16) {  // 超过 16ms 一帧的警告
    console.warn(`[Perf] ${id} ${phase}: ${actualDuration.toFixed(2)}ms`)
  }
}

<Profiler id="MoneyPage" onRender={onRenderCallback}>
  <MoneyPage />
</Profiler>
```

### 生产环境

1. **使用 Lighthouse 定期检测**
2. **接入 Web Vitals 监控**
3. **设置性能预算**

```typescript
// 示例：Web Vitals 报告
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals'

getCLS(console.log)
getFID(console.log)
getFCP(console.log)
getLCP(console.log)
getTTFB(console.log)
```

---

## 更新记录

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-01-28 | v1.0 | 初始文档，包含问题分析和优化建议 |
