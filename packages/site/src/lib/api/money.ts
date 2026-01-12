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
}
