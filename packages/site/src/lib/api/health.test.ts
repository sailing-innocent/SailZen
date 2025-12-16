/**
 * @file health.test.ts
 * @brief The Health API Test
 * @author sailing-innocent
 * @date 2025-05-21
 */

import { api_get_weight, api_get_weights } from './health'

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
