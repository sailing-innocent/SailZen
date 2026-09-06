/**
 * @file money.test.ts
 * @brief Tests for money store functionality against mock data
 * @author sailing-innocent
 * @date 2025-08-12
 */

import { useAccountsStore, useTransactionsStore } from './money'
import { useServerStore } from './index'
import {
  api_get_accounts,
  api_get_account,
  api_create_account,
  api_fix_account_balance,
  api_recalc_account_balance,
  api_get_transactions,
  api_create_transaction,
  api_delete_transaction,
  api_update_transaction,
} from '@lib/api/money'
import { type AccountData, type TransactionCreateProps } from '@lib/data/money'

// Mock data expectations based on mock/data/*.json
const MOCK_ACCOUNTS: AccountData[] = [
  {
    id: 1,
    name: '现金',
    description: '现金账户',
    balance: '1000.00',
    state: 1,
    mtime: expect.any(Number),
  },
  {
    id: 2,
    name: '银行卡',
    description: '银行储蓄卡',
    balance: '5000.00',
    state: 1,
    mtime: expect.any(Number),
  },
  {
    id: 3,
    name: '支付宝',
    description: '支付宝余额',
    balance: '500.00',
    state: 1,
    mtime: expect.any(Number),
  },
]

describe('Server Health Check', () => {
  test('server should be healthy', async () => {
    // Fetch server health status
    await useServerStore.getState().fetchServerHealth()
    const serverHealth = useServerStore.getState().serverHealth
    expect(serverHealth).toBeDefined()
    expect(typeof serverHealth).toBe('boolean')
    expect(serverHealth).toBe(true)
  })
})

describe('Accounts API Tests', () => {
  test('api_get_accounts should return mock accounts', async () => {
    const accounts = await api_get_accounts()
    expect(Array.isArray(accounts)).toBe(true)
    expect(accounts.length).toBe(3)

    // Check each account matches mock data structure
    accounts.forEach((account, index) => {
      expect(account).toMatchObject(MOCK_ACCOUNTS[index])
      expect(typeof account.id).toBe('number')
      expect(typeof account.name).toBe('string')
      expect(typeof account.description).toBe('string')
      expect(typeof account.balance).toBe('string')
      expect(typeof account.state).toBe('number')
      expect(typeof account.mtime).toBe('number')
    })
  })

  test('api_get_account should return specific account', async () => {
    const account = await api_get_account(1)
    expect(account).toMatchObject(MOCK_ACCOUNTS[0])
    expect(account.id).toBe(1)
    expect(account.name).toBe('现金')
    expect(account.balance).toBe('1000.00')
  })

  //   test('api_create_account should create new account', async () => {
  //     const newAccountName = '测试账户'
  //     const newAccount = await api_create_account({ name: newAccountName })

  //     expect(newAccount).toBeDefined()
  //     expect(newAccount.name).toBe(newAccountName)
  //     expect(newAccount.id).toBeGreaterThan(3) // Should get new ID
  //     expect(newAccount.balance).toBe('0.00') // New accounts start with 0 balance
  //     expect(newAccount.state).toBe(1)
  //     expect(typeof newAccount.mtime).toBe('number')
  //   })

  //   test('api_fix_account_balance should update account balance', async () => {
  //     const newBalance = '1500.00'
  //     const updatedAccount = await api_fix_account_balance(1, newBalance)

  //     expect(updatedAccount).toBeDefined()
  //     expect(updatedAccount.id).toBe(1)
  //     expect(updatedAccount.balance).toBe(newBalance)
  //     expect(updatedAccount.name).toBe('现金')
  //   })

  //   test('api_recalc_account_balance should recalculate balance from transactions', async () => {
  //     const recalcedAccount = await api_recalc_account_balance(1)

  //     expect(recalcedAccount).toBeDefined()
  //     expect(recalcedAccount.id).toBe(1)
  //     expect(typeof recalcedAccount.balance).toBe('string')
  //     // Balance should be calculated based on transactions: -100.00 (outgoing)
  //     expect(parseFloat(recalcedAccount.balance)).toBeLessThanOrEqual(0)
  //   })
})

describe('Transactions API Tests', () => {
  test('api_get_transactions should return mock transactions', async () => {
    const transactions = await api_get_transactions(10)
    expect(Array.isArray(transactions)).toBe(true)
    expect(transactions.length).toBeGreaterThanOrEqual(2)

    // Check transaction structure
    transactions.forEach((transaction) => {
      expect(typeof transaction.id).toBe('number')
      expect(typeof transaction.from_acc_id).toBe('number')
      expect(typeof transaction.to_acc_id).toBe('number')
      expect(typeof transaction.value).toBe('string')
      expect(typeof transaction.description).toBe('string')
      expect(typeof transaction.tags).toBe('string')
      expect(typeof transaction.htime).toBe('number')
    })

    // Transactions should be sorted by htime descending (most recent first)
    for (let i = 0; i < transactions.length - 1; i++) {
      expect(transactions[i].htime).toBeGreaterThanOrEqual(transactions[i + 1].htime)
    }
  })

  //   test('api_create_transaction should create new transaction', async () => {
  //     const newTransaction: TransactionCreateProps = {
  //       from_acc_id: 1,
  //       to_acc_id: 3,
  //       value: '200.00',
  //       description: '测试交易',
  //       tags: 'test',
  //       htime: Date.now(),
  //     }

  //     const createdTransaction = await api_create_transaction(newTransaction)

  //     expect(createdTransaction).toBeDefined()
  //     expect(createdTransaction.id).toBeGreaterThan(2) // Should get new ID
  //     expect(createdTransaction.from_acc_id).toBe(newTransaction.from_acc_id)
  //     expect(createdTransaction.to_acc_id).toBe(newTransaction.to_acc_id)
  //     expect(createdTransaction.value).toBe(newTransaction.value)
  //     expect(createdTransaction.description).toBe(newTransaction.description)
  //     expect(createdTransaction.tags).toBe(newTransaction.tags)
  //   })

  //   test('api_update_transaction should update existing transaction', async () => {
  //     // First get a transaction to update
  //     const transactions = await api_get_transactions(10)
  //     const transactionToUpdate = transactions[0]

  //     const updatedData: TransactionCreateProps = {
  //       from_acc_id: transactionToUpdate.from_acc_id,
  //       to_acc_id: transactionToUpdate.to_acc_id,
  //       value: '999.99',
  //       description: '更新后的描述',
  //       tags: 'updated',
  //       htime: transactionToUpdate.htime,
  //     }

  //     const updatedTransaction = await api_update_transaction(transactionToUpdate.id, updatedData)

  //     expect(updatedTransaction).toBeDefined()
  //     expect(updatedTransaction.id).toBe(transactionToUpdate.id)
  //     expect(updatedTransaction.value).toBe('999.99')
  //     expect(updatedTransaction.description).toBe('更新后的描述')
  //     expect(updatedTransaction.tags).toBe('updated')
  //   })

  //   test('api_delete_transaction should delete transaction', async () => {
  //     // First create a transaction to delete
  //     const newTransaction: TransactionCreateProps = {
  //       from_acc_id: 1,
  //       to_acc_id: 2,
  //       value: '50.00',
  //       description: '待删除的交易',
  //       tags: 'delete-test',
  //       htime: Date.now(),
  //     }

  //     const createdTransaction = await api_create_transaction(newTransaction)
  //     const response = await api_delete_transaction(createdTransaction.id)

  //     expect(response).toBeDefined()
  //     expect(response.status).toBe('success')
  //     expect(response.id).toBe(createdTransaction.id)
  //   })
})

describe('Accounts Store Tests', () => {
  test('useAccountsStore initial state', () => {
    const accounts = useAccountsStore.getState().accounts
    expect(accounts).toBeDefined()
    expect(Array.isArray(accounts)).toBe(true)

    const getOptions = useAccountsStore.getState().getOptions
    expect(getOptions).toBeDefined()
    expect(typeof getOptions).toBe('function')

    const fetchAccounts = useAccountsStore.getState().fetchAccounts
    expect(fetchAccounts).toBeDefined()
    expect(typeof fetchAccounts).toBe('function')
  })

  test('getOptions should return account options with "other" option', () => {
    // First set some accounts in the store
    useAccountsStore.setState({ accounts: MOCK_ACCOUNTS })

    const options = useAccountsStore.getState().getOptions()
    expect(Array.isArray(options)).toBe(true)
    expect(options.length).toBe(4) // 3 accounts + 1 "other" option
    expect(options[0]).toEqual({ id: -1, name: 'other' })

    // Check remaining options
    for (let i = 1; i < options.length; i++) {
      expect(options[i].id).toBe(MOCK_ACCOUNTS[i - 1].id)
      expect(options[i].name).toBe(MOCK_ACCOUNTS[i - 1].name)
    }
  })

  test('fetchAccounts should populate store', async () => {
    await useAccountsStore.getState().fetchAccounts()
    const accounts = useAccountsStore.getState().accounts

    expect(accounts.length).toBe(3)
    accounts.forEach((account, index) => {
      expect(account).toMatchObject(MOCK_ACCOUNTS[index])
    })
  })
})

describe('Transactions Store Tests', () => {
  test('useTransactionsStore initial state', () => {
    const transactions = useTransactionsStore.getState().transactions
    expect(transactions).toBeDefined()
    expect(Array.isArray(transactions)).toBe(true)

    const fetchTransactions = useTransactionsStore.getState().fetchTransactions
    expect(fetchTransactions).toBeDefined()
    expect(typeof fetchTransactions).toBe('function')
  })

  test('fetchTransactions should populate store and return data', async () => {
    const fetchedTransactions = await useTransactionsStore.getState().fetchTransactions(10)
    const storeTransactions = useTransactionsStore.getState().transactions

    expect(fetchedTransactions).toBeDefined()
    expect(Array.isArray(fetchedTransactions)).toBe(true)
    expect(fetchedTransactions.length).toBeGreaterThanOrEqual(2)

    // Store should be updated
    expect(storeTransactions).toEqual(fetchedTransactions)
  })

  test('createTransaction should add to store', async () => {
    const initialTransactions = useTransactionsStore.getState().transactions
    const initialCount = initialTransactions.length

    const newTransaction: TransactionCreateProps = {
      from_acc_id: 2,
      to_acc_id: 1,
      value: '75.00',
      description: 'Store test transaction',
      tags: 'store-test',
      htime: Date.now(),
    }

    const createdTransaction = await useTransactionsStore.getState().createTransaction(newTransaction)
    const updatedTransactions = useTransactionsStore.getState().transactions

    expect(createdTransaction).toBeDefined()
    expect(updatedTransactions.length).toBe(initialCount + 1)
    expect(updatedTransactions).toContain(createdTransaction)
  })

  test('deleteTransaction should remove from store', async () => {
    // First create a transaction
    const newTransaction: TransactionCreateProps = {
      from_acc_id: 1,
      to_acc_id: 3,
      value: '25.00',
      description: 'Transaction to delete',
      tags: 'delete-test',
      htime: Date.now(),
    }

    const createdTransaction = await useTransactionsStore.getState().createTransaction(newTransaction)
    const beforeDeleteCount = useTransactionsStore.getState().transactions.length

    // Then delete it
    const deleteResult = await useTransactionsStore.getState().deleteTransaction(createdTransaction.id)
    const afterDeleteTransactions = useTransactionsStore.getState().transactions

    expect(deleteResult).toBe(true)
    expect(afterDeleteTransactions.length).toBe(beforeDeleteCount - 1)
    expect(afterDeleteTransactions.find((t) => t.id === createdTransaction.id)).toBeUndefined()
  })
})
