/**
 * @file money.ts
 * @brief Money Data Interface
 * @author sailing-innocent
 * @date 2024-12-26
 */

export interface TransactionCreateProps {
  from_acc_id: number
  to_acc_id: number
  value: string
  description: string
  tags: string
  htime: number
}

export interface TransactionData extends TransactionCreateProps {
  id: number
  budget_id?: number | null
}

export interface TransactionDataStatsRequest {
  tags?: string[]
  tag_op?: 'and' | 'or'
  return_list: boolean
  from_time: number
  to_time: number
}

export interface TransactionDataStats {
  total_count: number
  income_count: number
  expense_count: number
  income_total: string
  expense_total: string
  net_total: string
  data?: TransactionData[]
}

// Batch stats request types
export interface BatchStatsQuery {
  id: string
  from_time?: number
  to_time?: number
  tags?: string
  tag_op?: 'and' | 'or'
  return_list?: boolean
  skip?: number
  limit?: number
  description?: string
  min_value?: number
  max_value?: number
}

export interface BatchStatsResult {
  id: string
  stats: TransactionDataStats | null
  error?: string
}


export interface TransactionResponse {
  id: number
  status: string
  message: string
}

export interface AccountCreateProps {
  name: string
}

export interface AccountOption extends AccountCreateProps {
  id: number
  state?: number
}

export interface AccountData extends AccountOption {
  description: string
  balance: string
  state: number
  mtime: number
}

// ============ Budget Unified Model ============
// 通用预算系统 - 所有业务场景使用相同的数据结构

/**
 * 预算项方向（收入/支出）
 */
export enum BudgetDirection {
  EXPENSE = 0,  // 支出
  INCOME = 1,   // 收入
}

export const BudgetDirectionLabels: Record<BudgetDirection, string> = {
  [BudgetDirection.EXPENSE]: '支出',
  [BudgetDirection.INCOME]: '收入',
}

/**
 * 预算项金额类型
 */
export enum ItemType {
  FIXED = 0,     // 固定金额（如押金、首付、年终奖）
  PERIODIC = 1,  // 周期性金额（如月租、月供、月薪）
}

export const ItemTypeLabels: Record<ItemType, string> = {
  [ItemType.FIXED]: '固定金额',
  [ItemType.PERIODIC]: '周期性',
}

/**
 * 预算项状态
 */
export enum ItemStatus {
  PENDING = 0,     // 待执行
  IN_PROGRESS = 1, // 进行中
  COMPLETED = 2,   // 已完成
  REFUNDED = 3,    // 已退还
}

export const ItemStatusLabels: Record<ItemStatus, string> = {
  [ItemStatus.PENDING]: '待执行',
  [ItemStatus.IN_PROGRESS]: '进行中',
  [ItemStatus.COMPLETED]: '已完成',
  [ItemStatus.REFUNDED]: '已退还',
}

/**
 * 预算创建属性
 */
export interface BudgetCreateProps {
  name: string
  total_amount: string  // 预算金额
  description?: string
  tags?: string
  start_date?: number
  end_date?: number
  htime?: number
  items?: BudgetItemCreateProps[]  // 创建时可以带子项
}

/**
 * 预算数据
 */
export interface BudgetData {
  id: number
  name: string
  description: string
  tags: string
  start_date?: number
  end_date?: number
  total_amount: string  // 由子项汇总计算
  direction: number  // 0=支出, 1=收入
  htime: number
  mtime: number
  items?: BudgetItemData[]
}

/**
 * 预算子项创建属性
 * 
 * 示例配置：
 * - 押金：{ name: "押金", direction: EXPENSE, item_type: FIXED, amount: "7000", period_count: 1, is_refundable: 1 }
 * - 月租：{ name: "月租", direction: EXPENSE, item_type: PERIODIC, amount: "3500", period_count: 12, is_refundable: 0 }
 * - 首付：{ name: "首付", direction: EXPENSE, item_type: FIXED, amount: "500000", period_count: 1, is_refundable: 0 }
 * - 月供：{ name: "月供", direction: EXPENSE, item_type: PERIODIC, amount: "8000", period_count: 360, is_refundable: 0 }
 * - 月薪：{ name: "月薪", direction: INCOME, item_type: PERIODIC, amount: "20000", period_count: 12, is_refundable: 0 }
 * - 年终奖：{ name: "年终奖", direction: INCOME, item_type: FIXED, amount: "50000", period_count: 1, is_refundable: 0 }
 */
export interface BudgetItemCreateProps {
  name: string
  description?: string
  direction?: BudgetDirection  // 默认: EXPENSE
  item_type?: ItemType         // 默认: FIXED
  amount: string
  period_count?: number        // 默认: 1
  is_refundable?: number       // 默认: 0
  due_date?: number
}

/**
 * 预算子项数据
 */
export interface BudgetItemData {
  id: number
  budget_id: number
  name: string
  description: string
  
  // 核心属性
  direction: BudgetDirection
  item_type: ItemType
  amount: string               // 固定型=总额，周期型=单期金额
  period_count: number
  
  // 可退还
  is_refundable: number
  refund_amount: string
  
  // 进度
  current_period: number
  status: ItemStatus
  
  due_date?: number
  ctime?: string
  mtime?: string
  
  // 计算属性（只读）
  total_amount: string         // 子项总金额
  remaining_periods: number    // 剩余期数
}

// ============ 预算模板预设配置 ============
// 模板不再需要后端 API，只是前端的预设配置

/**
 * 预设模板类型
 */
export type BudgetPresetType = 'rent' | 'mortgage' | 'salary' | 'custom'

/**
 * 预设模板配置
 */
export interface BudgetPreset {
  type: BudgetPresetType
  name: string
  description: string
  defaultTags: string
  itemPresets: BudgetItemCreateProps[]
}

/**
 * 租房预算预设
 */
export const RENT_PRESET: BudgetPreset = {
  type: 'rent',
  name: '租房预算',
  description: '追踪租金和押金',
  defaultTags: 'rent,housing',
  itemPresets: [
    {
      name: '押金',
      description: '租房押金（合同结束可退还）',
      direction: BudgetDirection.EXPENSE,
      item_type: ItemType.FIXED,
      amount: '0',
      period_count: 1,
      is_refundable: 1,
    },
    {
      name: '月租金',
      description: '每月租金',
      direction: BudgetDirection.EXPENSE,
      item_type: ItemType.PERIODIC,
      amount: '0',
      period_count: 12,
      is_refundable: 0,
    },
  ],
}

/**
 * 房贷预算预设
 */
export const MORTGAGE_PRESET: BudgetPreset = {
  type: 'mortgage',
  name: '房贷预算',
  description: '追踪首付和月供',
  defaultTags: 'mortgage,housing',
  itemPresets: [
    {
      name: '首付款',
      description: '购房首付款',
      direction: BudgetDirection.EXPENSE,
      item_type: ItemType.FIXED,
      amount: '0',
      period_count: 1,
      is_refundable: 0,
    },
    {
      name: '月供',
      description: '每月还款',
      direction: BudgetDirection.EXPENSE,
      item_type: ItemType.PERIODIC,
      amount: '0',
      period_count: 360,
      is_refundable: 0,
    },
  ],
}

/**
 * 工资预算预设
 */
export const SALARY_PRESET: BudgetPreset = {
  type: 'salary',
  name: '工资收入',
  description: '追踪年度收入',
  defaultTags: 'salary,income',
  itemPresets: [
    {
      name: '月薪',
      description: '每月工资收入',
      direction: BudgetDirection.INCOME,
      item_type: ItemType.PERIODIC,
      amount: '0',
      period_count: 12,
      is_refundable: 0,
    },
    {
      name: '年终奖',
      description: '年终奖金',
      direction: BudgetDirection.INCOME,
      item_type: ItemType.FIXED,
      amount: '0',
      period_count: 1,
      is_refundable: 0,
    },
  ],
}

/**
 * 所有预设模板
 */
export const BUDGET_PRESETS: Record<BudgetPresetType, BudgetPreset> = {
  rent: RENT_PRESET,
  mortgage: MORTGAGE_PRESET,
  salary: SALARY_PRESET,
  custom: {
    type: 'custom',
    name: '自定义',
    description: '自定义预算',
    defaultTags: '',
    itemPresets: [],
  },
}

export interface BudgetQueryParams {
  skip?: number
  limit?: number
  from_time?: number
  to_time?: number
  tags?: string
  tag_op?: 'and' | 'or'
}

export interface BudgetStatsParams {
  from_time?: number
  to_time?: number
  tags?: string
  tag_op?: 'and' | 'or'
  return_list?: boolean
}

export interface BudgetStats {
  total_budget_count: number
  total_budget_amount: string
  total_used_amount: string
  total_remaining_amount: string
  budgets?: Array<{
    budget: BudgetData
    used_amount: string
    remaining_amount: string
    transaction_count: number
  }>
}

export interface BudgetAnalysis {
  budget: BudgetData
  used_amount: string
  remaining_amount: string
  usage_percentage: number
  transactions: TransactionData[]
  by_tag: Record<string, {
    amount: string
    count: number
  }>
}

export interface BudgetConsumeProps {
  from_acc_id: number
  to_acc_id: number
  value: string
  description?: string
  htime?: number
}

export interface BudgetResponse {
  id: number
  status: string
  message: string
}

// Paginated transaction types
export interface TransactionQueryParams {
  page?: number
  page_size?: number
  from_time?: number
  to_time?: number
  tags?: string
  tag_op?: 'and' | 'or'
  description?: string
  min_value?: number
  max_value?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

export type PaginatedTransactionResponse = PaginatedResponse<TransactionData>

// ============ Finance Tag Types ============

export interface FinanceTagData {
  id: number
  name: string
  color: string
  description: string
  category: string  // 'expense' | 'income' | 'major' | 'custom'
  sort_order: number
  is_active: number  // 1=active, 0=inactive
}

export interface FinanceTagCreateProps {
  name: string
  color?: string
  description?: string
  category?: string
  sort_order?: number
}

export interface FinanceTagUpdateProps {
  name?: string
  color?: string
  description?: string
  category?: string
  sort_order?: number
  is_active?: number
}
