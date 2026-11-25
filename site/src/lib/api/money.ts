/**
 * @file money.ts
 * @brief Money Request API
 * @author sailing-innocent
 * @date 2024-12-26
 */

import {
  type TransactionCreateProps,
  type TransactionData,
  type AccountData,
  type AccountCreateProps,
  type TransactionResponse,
  type TransactionDataStats,
  type TransactionDataStatsRequest,
  type TransactionQueryParams,
  type PaginatedTransactionResponse,
  type BatchStatsQuery,
  type BatchStatsResult,
  type BudgetData,
  type BudgetCreateProps,
  type BudgetQueryParams,
  type BudgetStats,
  type BudgetStatsParams,
  type BudgetAnalysis,
  type BudgetConsumeProps,
  type BudgetResponse,
  type FinanceTagData,
  type FinanceTagCreateProps,
  type FinanceTagUpdateProps,
  type FinanceOverview,
  type AccountReconcileRequest,
  type AccountReconcileResponse,
  type BalanceCheckpoint,
  type HygieneProposal,
  type HygieneScanResult,
  type TransactionLineItem,
} from '@lib/data/money'

import { SERVER_URL, API_BASE } from './config'
const FINANCE_API_BASE = API_BASE + '/finance'

const api_recalc_account_balance = async (index: number): Promise<AccountData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/account/recalc_balance/${index}`)
  return response.json()
}

const api_update_account_balance = async (index: number): Promise<AccountData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/account/update_balance/${index}`)
  return response.json()
}

const api_get_account = async (index: number): Promise<AccountData> => {
  const url = `${SERVER_URL}/${FINANCE_API_BASE}/account/${index}`
  // console.log(url)
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error('Failed to fetch account')
  }
  return response.json()
}

const api_create_account = async (account: AccountCreateProps): Promise<AccountData> => {
  const content = JSON.stringify(account)
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/account/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: content,
  })
  return response.json()
}

const api_get_accounts = async (): Promise<AccountData[]> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/account/`)
  return response.json()
}

const api_fix_account_balance = async (id: number, balance_fix: string): Promise<AccountData> => {
  const content = JSON.stringify({
    id: id,
    balance: balance_fix,
  })
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/account/fix_balance/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: content,
  })
  return response.json()
}

const api_get_transactions = async (N: number): Promise<TransactionData[]> => {
  let api = `${SERVER_URL}/${FINANCE_API_BASE}/transaction/`
  api = api + `?limit=` + N.toString()
  const response = await fetch(api)

  return response.json()
}

/**
 * Get paginated transactions with filtering and sorting
 */
const api_get_transactions_paginated = async (params: TransactionQueryParams = {}): Promise<PaginatedTransactionResponse> => {
  const urlParams = new URLSearchParams()
  
  if (params.page !== undefined) urlParams.append('page', params.page.toString())
  if (params.page_size !== undefined) urlParams.append('page_size', params.page_size.toString())
  if (params.from_time !== undefined) urlParams.append('from_time', params.from_time.toString())
  if (params.to_time !== undefined) urlParams.append('to_time', params.to_time.toString())
  if (params.tags) urlParams.append('tags', params.tags)
  if (params.tag_op) urlParams.append('tag_op', params.tag_op)
  if (params.description) urlParams.append('description', params.description)
  if (params.min_value !== undefined) urlParams.append('min_value', params.min_value.toString())
  if (params.max_value !== undefined) urlParams.append('max_value', params.max_value.toString())
  if (params.sort_by) urlParams.append('sort_by', params.sort_by)
  if (params.sort_order) urlParams.append('sort_order', params.sort_order)
  
  const queryString = urlParams.toString()
  const api = `${SERVER_URL}/${FINANCE_API_BASE}/transaction/paginated/${queryString ? '?' + queryString : ''}`
  
  const response = await fetch(api)
  if (!response.ok) {
    throw new Error('Failed to fetch paginated transactions')
  }
  return response.json()
}

const api_get_transactions_stats = async (request: TransactionDataStatsRequest): Promise<TransactionDataStats> => {
  let api = `${SERVER_URL}/${FINANCE_API_BASE}/transaction/stats/`
  const params = new URLSearchParams()
  
  if (request.tags && request.tags.length > 0) {
    params.append('tags', request.tags.join(','))
  }
  
  if (request.tag_op) {
    params.append('tag_op', request.tag_op)
  }
  
  params.append('return_list', request.return_list.toString())
  params.append('from_time', request.from_time.toString())
  params.append('to_time', request.to_time.toString())
  
  api = api + '?' + params.toString()
  const response = await fetch(api)
  return response.json()
}

/**
 * Get transaction statistics for multiple queries in a single request
 * This is much more efficient than making many individual requests
 */
const api_get_transactions_stats_batch = async (queries: BatchStatsQuery[]): Promise<BatchStatsResult[]> => {
  const api = `${SERVER_URL}/${FINANCE_API_BASE}/transaction/stats/batch/`
  
  const response = await fetch(api, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(queries),
  })
  
  if (!response.ok) {
    throw new Error('Failed to fetch batch transaction stats')
  }
  
  return response.json()
}

const api_create_transaction = async (transaction: TransactionCreateProps): Promise<TransactionData> => {
  const content = JSON.stringify(transaction)
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/transaction/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: content,
  })
  if (!response.ok) {
    throw new Error('Failed to create transaction')
  }
  return response.json()
}

const api_delete_transaction = async (id: number): Promise<TransactionResponse> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/transaction/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete transaction')
  }
  return response.json()
}

const api_update_transaction = async (id: number, transaction: TransactionCreateProps): Promise<TransactionData> => {
  const content = JSON.stringify(transaction)
  // console.log(content)
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/transaction/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: content,
  })

  if (!response.ok) {
    throw new Error('Failed to update transaction')
  }
  return response.json()
}
// Budget API
const api_get_budgets = async (params?: BudgetQueryParams): Promise<BudgetData[]> => {
  let api = `${SERVER_URL}/${FINANCE_API_BASE}/budget/`
  if (params) {
    const urlParams = new URLSearchParams()
    if (params.skip !== undefined) urlParams.append('skip', params.skip.toString())
    if (params.limit !== undefined) urlParams.append('limit', params.limit.toString())
    if (params.from_time !== undefined) urlParams.append('from_time', params.from_time.toString())
    if (params.to_time !== undefined) urlParams.append('to_time', params.to_time.toString())
    if (params.tags) urlParams.append('tags', params.tags)
    if (params.tag_op) urlParams.append('tag_op', params.tag_op)
    const queryString = urlParams.toString()
    if (queryString) api = api + '?' + queryString
  }
  const response = await fetch(api)
  if (!response.ok) {
    throw new Error('Failed to fetch budgets')
  }
  return response.json()
}

const api_get_budget = async (id: number): Promise<BudgetData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/${id}`)
  if (!response.ok) {
    throw new Error('Failed to fetch budget')
  }
  return response.json()
}

const api_create_budget = async (budget: BudgetCreateProps): Promise<BudgetData> => {
  const content = JSON.stringify(budget)
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: content,
  })
  if (!response.ok) {
    throw new Error('Failed to create budget')
  }
  return response.json()
}

const api_update_budget = async (id: number, budget: BudgetCreateProps): Promise<BudgetData> => {
  const content = JSON.stringify(budget)
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: content,
  })
  if (!response.ok) {
    throw new Error('Failed to update budget')
  }
  return response.json()
}

const api_delete_budget = async (id: number): Promise<BudgetResponse> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete budget')
  }
  return response.json()
}

const api_get_budget_stats = async (params?: BudgetStatsParams): Promise<BudgetStats> => {
  let api = `${SERVER_URL}/${FINANCE_API_BASE}/budget/stats/`
  if (params) {
    const urlParams = new URLSearchParams()
    if (params.from_time !== undefined) urlParams.append('from_time', params.from_time.toString())
    if (params.to_time !== undefined) urlParams.append('to_time', params.to_time.toString())
    if (params.tags) urlParams.append('tags', params.tags)
    if (params.tag_op) urlParams.append('tag_op', params.tag_op)
    if (params.return_list !== undefined) urlParams.append('return_list', params.return_list.toString())
    const queryString = urlParams.toString()
    if (queryString) api = api + '?' + queryString
  }
  const response = await fetch(api)
  if (!response.ok) {
    throw new Error('Failed to fetch budget stats')
  }
  return response.json()
}

const api_get_budget_analysis = async (id: number): Promise<BudgetAnalysis> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/${id}/analysis`)
  if (!response.ok) {
    throw new Error('Failed to fetch budget analysis')
  }
  return response.json()
}

const api_consume_budget = async (id: number, consume: BudgetConsumeProps): Promise<TransactionData> => {
  const content = JSON.stringify(consume)
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/${id}/consume`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: content,
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to consume budget' }))
    throw new Error(errorData.detail || 'Failed to consume budget')
  }
  return response.json()
}

const api_link_transaction_to_budget = async (budget_id: number, transaction_id: number): Promise<TransactionData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/${budget_id}/link/${transaction_id}`, {
    method: 'POST',
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to link transaction' }))
    throw new Error(errorData.detail || 'Failed to link transaction')
  }
  return response.json()
}

interface BatchLinkResult {
  success: number[]
  failed: { id: number; error: string }[]
  total: number
  success_count: number
  failed_count: number
}

const api_link_transactions_batch = async (budget_id: number, transaction_ids: number[]): Promise<BatchLinkResult> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/${budget_id}/link-batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ transaction_ids }),
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to link transactions batch' }))
    throw new Error(errorData.detail || 'Failed to link transactions batch')
  }
  return response.json()
}

const api_unlink_transaction_from_budget = async (transaction_id: number): Promise<TransactionData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/unlink/${transaction_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to unlink transaction' }))
    throw new Error(errorData.detail || 'Failed to unlink transaction')
  }
  return response.json()
}

// ============ Budget Item APIs ============

import type { BudgetItemCreateProps, BudgetItemData, BudgetData as FullBudgetData } from '@lib/data/money'

const api_get_budget_items = async (budget_id: number): Promise<BudgetItemData[]> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/${budget_id}/items`)
  if (!response.ok) {
    throw new Error('Failed to fetch budget items')
  }
  return response.json()
}

const api_create_budget_item = async (budget_id: number, item: BudgetItemCreateProps): Promise<BudgetItemData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/${budget_id}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(item),
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to create item' }))
    throw new Error(errorData.detail || 'Failed to create budget item')
  }
  return response.json()
}

const api_update_budget_item = async (item_id: number, item: Partial<BudgetItemData>): Promise<BudgetItemData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/items/${item_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(item),
  })
  if (!response.ok) {
    throw new Error('Failed to update budget item')
  }
  return response.json()
}

const api_delete_budget_item = async (item_id: number): Promise<{ id: number; status: string }> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/items/${item_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete budget item')
  }
  return response.json()
}

const api_record_item_refund = async (item_id: number, refund_amount: string): Promise<BudgetItemData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/items/${item_id}/refund`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refund_amount }),
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to record refund' }))
    throw new Error(errorData.detail || 'Failed to record refund')
  }
  return response.json()
}

const api_advance_item_period = async (item_id: number): Promise<BudgetItemData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/items/${item_id}/advance`, {
    method: 'POST',
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to advance period' }))
    throw new Error(errorData.detail || 'Failed to advance period')
  }
  return response.json()
}

const api_get_budget_detail = async (budget_id: number): Promise<FullBudgetData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/budget/${budget_id}/detail`)
  if (!response.ok) {
    throw new Error('Failed to fetch budget detail')
  }
  return response.json()
}

/**
 * 创建带子项的预算（统一接口）
 * 
 * 使用此接口替代原来的模板 API（rent/mortgage/salary）
 * 所有预算创建都使用相同的数据结构
 */
const api_create_budget_with_items = async (
  budget: { name: string; total_amount?: string; description?: string; tags?: string; start_date?: number; end_date?: number; htime?: number },
  items: BudgetItemCreateProps[]
): Promise<FullBudgetData> => {
  // 先创建预算
  const budgetResponse = await api_create_budget({
    name: budget.name,
    total_amount: budget.total_amount || '0',  // 如果有传入金额则使用，否则会被子项汇总覆盖
    description: budget.description,
    tags: budget.tags,
    htime: budget.htime || Date.now() / 1000,
  })
  
  // 再创建子项
  for (const item of items) {
    await api_create_budget_item(budgetResponse.id, item)
  }
  
  // 返回完整预算
  return api_get_budget_detail(budgetResponse.id)
}

// ============ Finance Tag API ============

const api_get_finance_tags = async (category?: string, activeOnly: boolean = true): Promise<FinanceTagData[]> => {
  const params = new URLSearchParams()
  if (category) params.append('category', category)
  params.append('active_only', activeOnly.toString())
  const url = `${SERVER_URL}/${FINANCE_API_BASE}/tag/?${params.toString()}`
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error('Failed to fetch finance tags')
  }
  return response.json()
}

const api_create_finance_tag = async (tag: FinanceTagCreateProps): Promise<FinanceTagData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/tag/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tag),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || 'Failed to create finance tag')
  }
  return response.json()
}

const api_update_finance_tag = async (tagId: number, tag: FinanceTagUpdateProps): Promise<FinanceTagData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/tag/${tagId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tag),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || 'Failed to update finance tag')
  }
  return response.json()
}

const api_delete_finance_tag = async (tagId: number): Promise<void> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/tag/${tagId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete finance tag')
  }
}

const api_seed_finance_tags = async (): Promise<{ status: string; created_count: number; message: string }> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/tag/seed`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Failed to seed finance tags')
  }
  return response.json()
}

// ============ Finance 2.0 (SailTick Secretary) APIs ============

const api_get_finance_overview = async (month?: string): Promise<FinanceOverview> => {
  const qs = month ? `?month=${encodeURIComponent(month)}` : ''
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/overview${qs}`)
  if (!response.ok) {
    throw new Error('Failed to fetch finance overview')
  }
  return response.json()
}

const api_reconcile_account_balance = async (
  payload: AccountReconcileRequest,
): Promise<AccountReconcileResponse> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/account/reconcile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to reconcile account' }))
    throw new Error(err.detail || 'Failed to reconcile account')
  }
  return response.json()
}

const api_get_balance_checkpoints = async (
  accountId?: number,
  limit: number = 30,
): Promise<BalanceCheckpoint[]> => {
  const params = new URLSearchParams()
  if (accountId !== undefined) params.append('account_id', String(accountId))
  params.append('limit', String(limit))
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/account/checkpoints?${params.toString()}`)
  if (!response.ok) {
    throw new Error('Failed to fetch balance checkpoints')
  }
  return response.json()
}

const api_update_transaction_meta = async (
  txId: number,
  payload: {
    items?: TransactionLineItem[]
    links?: Record<string, unknown>
    entry_kind?: string
    exclude_from_stats?: boolean
    sync_tags_from_items?: boolean
  },
): Promise<TransactionData> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/transaction/${txId}/meta`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error('Failed to update transaction meta')
  }
  return response.json()
}

const api_run_hygiene_scan = async (options?: {
  days?: number | null
  auto_apply_safe?: boolean
  min_auto_confidence?: number
  created_by?: string
}): Promise<HygieneScanResult> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/hygiene/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      days: options?.days ?? 90,
      auto_apply_safe: options?.auto_apply_safe ?? true,
      min_auto_confidence: options?.min_auto_confidence ?? 0.9,
      created_by: options?.created_by ?? 'web_user',
    }),
  })
  if (!response.ok) {
    throw new Error('Failed to run hygiene scan')
  }
  return response.json()
}

const api_list_hygiene_proposals = async (params?: {
  status?: string
  autonomy_level?: string
  proposal_type?: string
  limit?: number
}): Promise<HygieneProposal[]> => {
  const search = new URLSearchParams()
  if (params?.status) search.append('status', params.status)
  if (params?.autonomy_level) search.append('autonomy_level', params.autonomy_level)
  if (params?.proposal_type) search.append('proposal_type', params.proposal_type)
  if (params?.limit) search.append('limit', String(params.limit))
  const qs = search.toString()
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/hygiene/proposals${qs ? '?' + qs : ''}`)
  if (!response.ok) {
    throw new Error('Failed to fetch hygiene proposals')
  }
  return response.json()
}

const api_approve_hygiene_proposal = async (id: number): Promise<HygieneProposal> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/hygiene/proposals/${id}/approve`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Failed to approve proposal')
  }
  return response.json()
}

const api_dismiss_hygiene_proposal = async (id: number): Promise<HygieneProposal> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/hygiene/proposals/${id}/dismiss`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Failed to dismiss proposal')
  }
  return response.json()
}

const api_revert_hygiene_proposal = async (id: number): Promise<HygieneProposal> => {
  const response = await fetch(`${SERVER_URL}/${FINANCE_API_BASE}/hygiene/proposals/${id}/revert`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Failed to revert proposal')
  }
  return response.json()
}

export {
  api_get_account,
  api_create_account,
  api_get_accounts,
  api_update_account_balance,
  api_recalc_account_balance,
  api_fix_account_balance,
  api_get_transactions,
  api_get_transactions_paginated,
  api_get_transactions_stats,
  api_get_transactions_stats_batch,
  api_create_transaction,
  api_delete_transaction,
  api_update_transaction,
  api_get_budgets,
  api_get_budget,
  api_create_budget,
  api_update_budget,
  api_delete_budget,
  api_get_budget_stats,
  api_get_budget_analysis,
  api_consume_budget,
  api_link_transaction_to_budget,
  api_link_transactions_batch,
  api_unlink_transaction_from_budget,
  // Budget Items
  api_get_budget_items,
  api_create_budget_item,
  api_update_budget_item,
  api_delete_budget_item,
  api_record_item_refund,
  api_advance_item_period,
  api_get_budget_detail,
  // Unified budget creation
  api_create_budget_with_items,
  // Finance Tags
  api_get_finance_tags,
  api_create_finance_tag,
  api_update_finance_tag,
  api_delete_finance_tag,
  api_seed_finance_tags,
  // Finance 2.0 (SailTick Secretary)
  api_get_finance_overview,
  api_reconcile_account_balance,
  api_get_balance_checkpoints,
  api_update_transaction_meta,
  api_run_hygiene_scan,
  api_list_hygiene_proposals,
  api_approve_hygiene_proposal,
  api_dismiss_hygiene_proposal,
  api_revert_hygiene_proposal,
}

export type { BatchLinkResult }
