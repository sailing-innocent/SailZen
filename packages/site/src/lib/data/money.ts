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

// Budget types and enums
export enum BudgetType {
  EXPENSE = 0,  // 支出预算
  INCOME = 1,   // 收入预算
}

export const BudgetTypeLabels: Record<BudgetType, string> = {
  [BudgetType.EXPENSE]: '支出预算',
  [BudgetType.INCOME]: '收入预算',
}

export enum PeriodType {
  ONCE = 0,       // 一次性
  MONTHLY = 1,    // 月度
  QUARTERLY = 2,  // 季度
  YEARLY = 3,     // 年度
}

export const PeriodTypeLabels: Record<PeriodType, string> = {
  [PeriodType.ONCE]: '一次性',
  [PeriodType.MONTHLY]: '月度',
  [PeriodType.QUARTERLY]: '季度',
  [PeriodType.YEARLY]: '年度',
}

export enum BudgetItemStatus {
  PENDING = 0,     // 待执行
  IN_PROGRESS = 1, // 进行中
  COMPLETED = 2,   // 已完成
  REFUNDED = 3,    // 已退还
}

export const BudgetItemStatusLabels: Record<BudgetItemStatus, string> = {
  [BudgetItemStatus.PENDING]: '待执行',
  [BudgetItemStatus.IN_PROGRESS]: '进行中',
  [BudgetItemStatus.COMPLETED]: '已完成',
  [BudgetItemStatus.REFUNDED]: '已退还',
}

export enum BudgetCategory {
  GENERAL = '',
  RENT = 'rent',
  MORTGAGE = 'mortgage',
  SALARY = 'salary',
  PROJECT = 'project',
}

export const BudgetCategoryLabels: Record<BudgetCategory, string> = {
  [BudgetCategory.GENERAL]: '通用',
  [BudgetCategory.RENT]: '租房',
  [BudgetCategory.MORTGAGE]: '房贷',
  [BudgetCategory.SALARY]: '工资',
  [BudgetCategory.PROJECT]: '项目',
}

export interface BudgetCreateProps {
  name: string
  amount: string
  description?: string
  tags?: string
  budget_type?: BudgetType
  period_type?: PeriodType
  start_date?: number
  end_date?: number
  category?: string
  htime?: number
}

export interface BudgetData extends BudgetCreateProps {
  id: number
  mtime: number
  items?: BudgetItemData[]
}

export interface BudgetItemData {
  id: number
  budget_id: number
  name: string
  amount: string
  description?: string
  is_refundable: number
  refund_amount: string
  status: BudgetItemStatus
  period_count: number
  current_period: number
  due_date?: number
  ctime?: string
  mtime?: string
}

export interface BudgetItemCreateProps {
  name: string
  amount: string
  description?: string
  is_refundable?: number
  period_count?: number
  due_date?: number
}

// Budget template props
export interface RentBudgetProps {
  name: string
  monthly_rent: string
  deposit: string
  start_date: number
  end_date: number
  description?: string
  tags?: string
}

export interface MortgageBudgetProps {
  name: string
  down_payment: string
  monthly_payment: string
  monthly_interest: string
  loan_months: number
  start_date: number
  description?: string
  tags?: string
}

export interface SalaryBudgetProps {
  name: string
  monthly_salary: string
  year: number
  annual_bonus?: string
  description?: string
  tags?: string
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
