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
  type BudgetData,
  type BudgetCreateProps,
  type BudgetQueryParams,
  type BudgetStats,
  type BudgetStatsParams,
  type BudgetAnalysis,
  type BudgetConsumeProps,
  type BudgetResponse,
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

export {
  api_get_account,
  api_create_account,
  api_get_accounts,
  api_update_account_balance,
  api_recalc_account_balance,
  api_fix_account_balance,
  api_get_transactions,
  api_get_transactions_stats,
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
  api_unlink_transaction_from_budget,
}
