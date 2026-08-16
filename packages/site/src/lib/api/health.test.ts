/**
 * @file health.test.ts
 * @brief The Health API Test
 * @author sailing-innocent
 * @date 2025-05-21
 */

import {
  api_get_weight,
  api_get_weights,
  api_update_weight_plan,
  api_delete_weight_plan,
  api_get_weight_plan_expected,
  api_get_weight_plan_checkin_status,
} from './health'

test('api_get_weight', async () => {
  const result = await api_get_weight(1)
  expect(result).toHaveProperty('id')
  expect(result).toHaveProperty('value')
  expect(result).toHaveProperty('htime')
})

test('api_get_weights', async () => {
  const result = await api_get_weights(0, 10)
  expect(result.length).toBeGreaterThan(0)
  expect(result.length).toBeLessThanOrEqual(10)
  expect(result[0]).toHaveProperty('id')
  expect(result[0]).toHaveProperty('value')
  expect(result[0]).toHaveProperty('htime')
})

test('api_update_weight_plan builds PUT request', async () => {
  // This test assumes a running server; it verifies the function resolves and returns shape.
  const result = await api_update_weight_plan(1, { target_weight: 70 })
  expect(result).toHaveProperty('id')
  expect(result).toHaveProperty('target_weight')
})

test('api_delete_weight_plan resolves without throwing', async () => {
  await expect(api_delete_weight_plan(1)).resolves.toBeUndefined()
})

test('api_get_weight_plan_expected returns points array', async () => {
  const now = Math.floor(Date.now() / 1000)
  const start = now - 7 * 24 * 60 * 60
  const end = now
  const result = await api_get_weight_plan_expected(start, end)
  expect(Array.isArray(result)).toBe(true)
})

test('api_get_weight_plan_checkin_status returns status or null', async () => {
  const result = await api_get_weight_plan_checkin_status(1)
  expect(result === null || typeof result === 'object').toBe(true)
})
