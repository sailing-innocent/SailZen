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

// Budget types
export interface BudgetCreateProps {
  name: string
  amount: string
  description?: string
  tags?: string
  htime?: number
}

export interface BudgetData extends BudgetCreateProps {
  id: number
  mtime: number
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
