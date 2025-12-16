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
}

export interface TransactionDataStatsRequest {
  tags: string[]
  tag_op: 'and' | 'or'
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
}

export interface AccountData extends AccountOption {
  description: string
  balance: string
  state: number
  mtime: number
}
