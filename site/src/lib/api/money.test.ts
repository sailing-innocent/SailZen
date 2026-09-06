import {
  api_get_account,
  // api_create_account,
  api_get_accounts,
  // api_update_account_balance,
  // api_recalc_account_balance,
  // api_fix_account_balance,
  api_get_transactions,
  // api_create_transaction,
  // api_delete_transaction,
  // api_update_transaction,
} from './money'

// import { type TransactionCreateProps, type TransactionData, type AccountData, type AccountCreateProps } from '@lib/data/money'

test('api_get_account', async () => {
  const result = await api_get_account(1)
  expect(result).toBeDefined()
  expect(result).toHaveProperty('id')
  expect(result).toHaveProperty('name')
  expect(result).toHaveProperty('description')
  expect(result).toHaveProperty('mtime')
  expect(result).toHaveProperty('balance')
})

test('api_get_accounts', async () => {
  const result = await api_get_accounts()
  expect(result.length).toBeGreaterThan(0)
  expect(result[0]).toHaveProperty('id')
  expect(result[0]).toHaveProperty('name')
  expect(result[0]).toHaveProperty('description')
  expect(result[0]).toHaveProperty('mtime')
  expect(result[0]).toHaveProperty('balance')
})

test('api_get_transactions', async () => {
  const result = await api_get_transactions(10)
  expect(result.length).toBeGreaterThan(0)
  expect(result[0]).toHaveProperty('id')
  expect(result[0]).toHaveProperty('from_acc_id')
  expect(result[0]).toHaveProperty('to_acc_id')
  expect(result[0]).toHaveProperty('value')
  expect(result[0]).toHaveProperty('description')
  expect(result[0]).toHaveProperty('tags')
  expect(result[0]).toHaveProperty('htime')
})
