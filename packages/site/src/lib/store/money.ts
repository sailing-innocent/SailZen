/**
 * @file money.ts
 * @brief The Store for Money Accounts
 * @author sailing-innocent
 * @date 2024-12-26
 */

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import {
  type AccountData,
  type AccountOption,
  type TransactionData,
  type TransactionCreateProps,
  type TransactionQueryParams,
  type PaginatedTransactionResponse,
  type BudgetData,
  type BudgetCreateProps,
  type BudgetQueryParams,
  type BudgetStats,
  type BudgetStatsParams,
  type BudgetAnalysis,
  type BudgetConsumeProps,
} from '@lib/data/money'

import {
  api_get_accounts,
  api_create_account,
  api_update_account_balance,
  api_recalc_account_balance,
  api_fix_account_balance,
  api_get_transactions,
  api_get_transactions_paginated,
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
  type BatchLinkResult,
} from '@lib/api/money'

export interface AccountsState {
  accounts: AccountData[]
  isLoading: boolean
  getOptions: () => AccountOption[]
  fetchAccounts: () => void
  updateAccount: (id: number, refresh: boolean) => void
  fixAccount: (id: number, newBalance: string) => void
  createAccount: (name: string) => void
}

export const useAccountsStore: UseBoundStore<StoreApi<AccountsState>> = create<AccountsState>((set) => ({
  accounts: [],
  isLoading: false,
  getOptions: (): AccountOption[] => {
    const accounts = useAccountsStore.getState().accounts
    const options = accounts.map((account: AccountData) => {
      return {
        id: account.id,
        name: account.name,
        state: account.state,
      }
    })
    options.unshift({ id: -1, name: 'other', state: 0 })
    return options
  },
  fetchAccounts: async () => {
    set({ isLoading: true })
    try {
      const accounts = await api_get_accounts()

      accounts
        .sort( // sort by balance descending
          (a: AccountData, b: AccountData) => parseFloat(b.balance) - parseFloat(a.balance))

      // set the state with fetched accounts
      set({ accounts: accounts, isLoading: false })

    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },
  updateAccount: async (id: number, refresh: boolean) => {
    const update_func = refresh ? api_recalc_account_balance : api_update_account_balance
    const new_account = await update_func(id)
    set((state: AccountsState): AccountsState => {
      const index = state.accounts.findIndex((account: AccountData) => account.id === new_account.id)
      const newState: AccountsState = {
        ...state,
        accounts: [...state.accounts],
      }
      if (index !== -1) {
        newState.accounts[index] = new_account
        return newState // trigger re-render
      } else {
        console.log('Account not found')
        return state
      }
    })
  },
  fixAccount: async (id: number, newBalance: string) => {
    const new_account = await api_fix_account_balance(id, newBalance)
    set((state: AccountsState): AccountsState => {
      const index = state.accounts.findIndex((account: AccountData) => account.id === new_account.id)
      const newState: AccountsState = {
        ...state,
        accounts: [...state.accounts],
      }
      if (index !== -1) {
        newState.accounts[index] = new_account
        return newState // trigger re-render
      } else {
        console.log('Account not found')
        return state
      }
    })
  },
  createAccount: async (name: string) => {
    const new_account = await api_create_account({ name: name })
    set((state: AccountsState): AccountsState => {
      return {
        ...state,
        accounts: [...state.accounts, new_account],
      }
    })
  },
}))

export interface PaginationMeta {
  total: number
  page: number
  pageSize: number
  totalPages: number
  hasNext: boolean
  hasPrev: boolean
}

export interface TransactionsState {
  transactions: TransactionData[]
  isLoading: boolean
  // Pagination state
  pagination: PaginationMeta
  // Legacy method
  fetchTransactions: (N: number) => Promise<TransactionData[]>
  // New paginated method
  fetchTransactionsPaginated: (params: TransactionQueryParams) => Promise<PaginatedTransactionResponse>
  createTransaction: (transaction: TransactionCreateProps) => Promise<TransactionData>
  updateTransaction: (id: number, transaction: TransactionCreateProps) => Promise<TransactionData>
  deleteTransaction: (id: number) => Promise<boolean>
  getSupportedTags: () => string[]
}

const defaultPagination: PaginationMeta = {
  total: 0,
  page: 1,
  pageSize: 20,
  totalPages: 1,
  hasNext: false,
  hasPrev: false,
}

export const useTransactionsStore: UseBoundStore<StoreApi<TransactionsState>> = create<TransactionsState>((set) => ({
  transactions: [],
  isLoading: false,
  pagination: defaultPagination,
  fetchTransactions: async (N: number): Promise<TransactionData[]> => {
    set({ isLoading: true })
    try {
      const transactions = await api_get_transactions(N)
      set({ transactions: transactions, isLoading: false })
      return transactions
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },
  fetchTransactionsPaginated: async (params: TransactionQueryParams): Promise<PaginatedTransactionResponse> => {
    set({ isLoading: true })
    try {
      const response = await api_get_transactions_paginated(params)
      set({
        transactions: response.data,
        isLoading: false,
        pagination: {
          total: response.total,
          page: response.page,
          pageSize: response.page_size,
          totalPages: response.total_pages,
          hasNext: response.has_next,
          hasPrev: response.has_prev,
        },
      })
      return response
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },
  createTransaction: async (transaction: TransactionCreateProps): Promise<TransactionData> => {
    const new_transaction = await api_create_transaction(transaction)
    set((state: TransactionsState): TransactionsState => {
      return {
        ...state,
        transactions: [...state.transactions, new_transaction],
        pagination: {
          ...state.pagination,
          total: state.pagination.total + 1,
        },
      }
    })
    return new_transaction
  },
  updateTransaction: async (id: number, transaction: TransactionCreateProps): Promise<TransactionData> => {
    const updated_transaction = await api_update_transaction(id, transaction)
    set((state: TransactionsState): TransactionsState => {
      const index = state.transactions.findIndex((t: TransactionData) => t.id === updated_transaction.id)
      const newState: TransactionsState = {
        ...state,
        transactions: [...state.transactions],
      }
      if (index !== -1) {
        newState.transactions[index] = updated_transaction
        return newState // trigger re-render
      } else {
        console.log('Transaction not found')
        return state
      }
    })
    return updated_transaction
  },
  deleteTransaction: async (id: number): Promise<boolean> => {
    const response = await api_delete_transaction(id)
    set((state: TransactionsState): TransactionsState => {
      const newState: TransactionsState = {
        ...state,
        transactions: state.transactions.filter((t: TransactionData) => t.id !== id),
        pagination: {
          ...state.pagination,
          total: Math.max(0, state.pagination.total - 1),
        },
      }
      return newState // trigger re-render
    })
    return response.status === 'success'
  },
  getSupportedTags: (): string[] => {
    return ['零食', '交通', '日用消耗', '大宗电器', '娱乐休闲', '人际交往', '医药健康', '衣物', '大宗收支']
  },
}))

export interface BudgetsState {
  budgets: BudgetData[]
  isLoading: boolean
  fetchBudgets: (params?: BudgetQueryParams) => Promise<BudgetData[]>
  createBudget: (budget: BudgetCreateProps) => Promise<BudgetData>
  updateBudget: (id: number, budget: BudgetCreateProps) => Promise<BudgetData>
  deleteBudget: (id: number) => Promise<boolean>
  consumeBudget: (id: number, consume: BudgetConsumeProps) => Promise<TransactionData>
  linkTransaction: (budget_id: number, transaction_id: number) => Promise<TransactionData>
  linkTransactionsBatch: (budget_id: number, transaction_ids: number[]) => Promise<BatchLinkResult>
  unlinkTransaction: (transaction_id: number) => Promise<TransactionData>
  getBudgetStats: (params?: BudgetStatsParams) => Promise<BudgetStats>
  getBudgetAnalysis: (id: number) => Promise<BudgetAnalysis>
}

export const useBudgetsStore: UseBoundStore<StoreApi<BudgetsState>> = create<BudgetsState>((set) => ({
  budgets: [],
  isLoading: false,
  fetchBudgets: async (params?: BudgetQueryParams): Promise<BudgetData[]> => {
    set({ isLoading: true })
    try {
      const budgets = await api_get_budgets(params)
      set({ budgets: budgets, isLoading: false })
      return budgets
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },
  createBudget: async (budget: BudgetCreateProps): Promise<BudgetData> => {
    const new_budget = await api_create_budget(budget)
    set((state: BudgetsState): BudgetsState => {
      return {
        ...state,
        budgets: [...state.budgets, new_budget],
      }
    })
    return new_budget
  },
  updateBudget: async (id: number, budget: BudgetCreateProps): Promise<BudgetData> => {
    const updated_budget = await api_update_budget(id, budget)
    set((state: BudgetsState): BudgetsState => {
      const index = state.budgets.findIndex((b: BudgetData) => b.id === updated_budget.id)
      const newState: BudgetsState = {
        ...state,
        budgets: [...state.budgets],
      }
      if (index !== -1) {
        newState.budgets[index] = updated_budget
        return newState // trigger re-render
      } else {
        console.log('Budget not found')
        return state
      }
    })
    return updated_budget
  },
  deleteBudget: async (id: number): Promise<boolean> => {
    const response = await api_delete_budget(id)
    set((state: BudgetsState): BudgetsState => {
      const newState: BudgetsState = {
        ...state,
        budgets: state.budgets.filter((b: BudgetData) => b.id !== id),
      }
      return newState // trigger re-render
    })
    return response.status === 'success'
  },
  consumeBudget: async (id: number, consume: BudgetConsumeProps): Promise<TransactionData> => {
    const transaction = await api_consume_budget(id, consume)
    // Refresh budgets to update remaining amounts
    set((state: BudgetsState) => {
      // Trigger refresh by setting isLoading
      return { ...state, isLoading: true }
    })
    // Fetch updated budgets
    try {
      const budgets = await api_get_budgets()
      set({ budgets: budgets, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
    }
    return transaction
  },
  linkTransaction: async (budget_id: number, transaction_id: number): Promise<TransactionData> => {
    const transaction = await api_link_transaction_to_budget(budget_id, transaction_id)
    // Refresh budgets to update remaining amounts
    set((state: BudgetsState) => {
      return { ...state, isLoading: true }
    })
    try {
      const budgets = await api_get_budgets()
      set({ budgets: budgets, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
    }
    return transaction
  },
  linkTransactionsBatch: async (budget_id: number, transaction_ids: number[]): Promise<BatchLinkResult> => {
    const result = await api_link_transactions_batch(budget_id, transaction_ids)
    // Refresh budgets to update remaining amounts
    set((state: BudgetsState) => {
      return { ...state, isLoading: true }
    })
    try {
      const budgets = await api_get_budgets()
      set({ budgets: budgets, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
    }
    return result
  },
  unlinkTransaction: async (transaction_id: number): Promise<TransactionData> => {
    const transaction = await api_unlink_transaction_from_budget(transaction_id)
    // Refresh budgets to update remaining amounts
    set((state: BudgetsState) => {
      return { ...state, isLoading: true }
    })
    try {
      const budgets = await api_get_budgets()
      set({ budgets: budgets, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
    }
    return transaction
  },
  getBudgetStats: async (params?: BudgetStatsParams): Promise<BudgetStats> => {
    return await api_get_budget_stats(params)
  },
  getBudgetAnalysis: async (id: number): Promise<BudgetAnalysis> => {
    return await api_get_budget_analysis(id)
  },
}))
