/**
 * @file body_data.test.ts
 * @brief The Body Data API Test
 * @author sailing-innocent
 * @date 2026-09-06
 *
 * 与 health.test.ts 一致：依赖 mock server (localhost:3001) 运行。
 * 启动：pnpm mock:start；运行：pnpm test。
 */

import {
  api_get_body_data_list,
  api_get_body_data,
  api_create_body_data,
  api_update_body_data,
  api_delete_body_data,
  api_get_body_metrics,
  api_get_body_series,
  api_analyze_body_metric,
} from './body_data'

test('api_get_body_metrics returns builtin metric registry', async () => {
  const result = await api_get_body_metrics()
  expect(Array.isArray(result)).toBe(true)
  const weight = result.find((m) => m.key === 'weight')
  expect(weight).toBeDefined()
  expect(weight).toHaveProperty('labelZh')
  expect(weight).toHaveProperty('unit')
})

test('api_get_body_data_list returns records with data map', async () => {
  const result = await api_get_body_data_list(0, 10)
  expect(Array.isArray(result)).toBe(true)
  expect(result.length).toBeGreaterThan(0)
  expect(result[0]).toHaveProperty('id')
  expect(result[0]).toHaveProperty('htime')
  expect(result[0]).toHaveProperty('data')
  expect(typeof result[0].data).toBe('object')
})

test('api_get_body_data_list filters by metric', async () => {
  const result = await api_get_body_data_list(0, -1, -1, -1, 'weight')
  expect(Array.isArray(result)).toBe(true)
  expect(result.length).toBeGreaterThan(0)
  for (const record of result) {
    expect(typeof record.data.weight).toBe('number')
  }
})

test('api_get_body_series returns points only from records that measured the metric', async () => {
  const result = await api_get_body_series('weight')
  expect(result).toHaveProperty('metric', 'weight')
  expect(result).toHaveProperty('unit')
  expect(Array.isArray(result.points)).toBe(true)
  expect(result.points.length).toBeGreaterThan(0)
  for (const point of result.points) {
    expect(point).toHaveProperty('htime')
    expect(typeof point.value).toBe('number')
  }
})

test('api_analyze_body_metric returns analysis structure', async () => {
  const result = await api_analyze_body_metric('weight', 'linear')
  expect(result).toHaveProperty('metric', 'weight')
  expect(result).toHaveProperty('model_type', 'linear')
  expect(typeof result.slope).toBe('number')
  expect(typeof result.r_squared).toBe('number')
  expect(Array.isArray(result.predicted_points)).toBe(true)
})

test('api_create_body_data dual-writes weight and supports update/delete', async () => {
  const now = Math.floor(Date.now() / 1000)
  // Create: data contains weight -> dual-write to weights table
  const created = await api_create_body_data({
    htime: now,
    data: { weight: 71.0, waist: 84.0 },
    tag: 'jest-test',
    description: 'body data api test',
  })
  expect(created).toHaveProperty('id')
  expect(typeof created.data.weight).toBe('number')
  expect(created.weightId !== null && created.weightId !== undefined).toBe(true)

  // Read back by id
  const fetched = await api_get_body_data(created.id)
  expect(fetched.id).toBe(created.id)
  expect(fetched.data.waist).toBe(84.0)

  // Update: replace data
  const updated = await api_update_body_data(created.id, {
    data: { weight: 71.5 },
    description: 'updated',
  })
  expect(updated.data.weight).toBe(71.5)
  expect(updated.data.waist).toBeUndefined()

  // Delete: cleans up
  await expect(api_delete_body_data(created.id)).resolves.toBeUndefined()
  await expect(api_get_body_data(created.id)).rejects.toThrow()
})
