/**
 * @file necessity.ts
 * @brief Necessity (生活物资) Request API
 * @author sailing-innocent
 * @date 2026-02-01
 */

import {
  type ResidenceData,
  type ResidenceCreateProps,
  type ContainerData,
  type ContainerCreateProps,
  type ContainerTreeNode,
  type ItemCategoryData,
  type ItemCategoryCreateProps,
  type CategoryTreeNode,
  type ItemData,
  type ItemCreateProps,
  type ItemQueryParams,
  type ItemPaginatedParams,
  type PaginatedResponse,
  type InventoryData,
  type InventoryCreateProps,
  type InventoryStats,
  type TransferInventoryProps,
  type ConsumeInventoryProps,
  type ReplenishInventoryProps,
  type JourneyData,
  type JourneyCreateProps,
  type JourneyItemCreateProps,
  type ExpiringItem,
} from '@lib/data/necessity'

import { SERVER_URL, API_BASE } from './config'
const NECESSITY_API_BASE = API_BASE + '/necessity'

// ============ Residence APIs ============

export const api_get_residences = async (residence_type?: number): Promise<ResidenceData[]> => {
  let api = `${SERVER_URL}/${NECESSITY_API_BASE}/residence/`
  if (residence_type !== undefined) {
    api += `?residence_type=${residence_type}`
  }
  const response = await fetch(api)
  if (!response.ok) {
    throw new Error('Failed to fetch residences')
  }
  return response.json()
}

export const api_get_residence = async (id: number): Promise<ResidenceData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/residence/${id}`)
  if (!response.ok) {
    throw new Error('Failed to fetch residence')
  }
  return response.json()
}

export const api_create_residence = async (data: ResidenceCreateProps): Promise<ResidenceData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/residence/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to create residence')
  }
  return response.json()
}

export const api_update_residence = async (id: number, data: ResidenceCreateProps): Promise<ResidenceData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/residence/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to update residence')
  }
  return response.json()
}

export const api_delete_residence = async (id: number): Promise<{ id: number; status: string }> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/residence/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete residence')
  }
  return response.json()
}

export const api_get_portable_residence = async (): Promise<ResidenceData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/residence/portable`)
  if (!response.ok) {
    throw new Error('Failed to fetch portable residence')
  }
  return response.json()
}

export const api_get_residence_inventory = async (residenceId: number): Promise<InventoryData[]> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/residence/${residenceId}/inventory`)
  if (!response.ok) {
    throw new Error('Failed to fetch residence inventory')
  }
  return response.json()
}

export const api_get_residence_low_stock = async (residenceId: number): Promise<InventoryData[]> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/residence/${residenceId}/low-stock`)
  if (!response.ok) {
    throw new Error('Failed to fetch residence low stock')
  }
  return response.json()
}

// ============ Container APIs ============

export const api_get_containers = async (residenceId?: number): Promise<ContainerData[]> => {
  let api = `${SERVER_URL}/${NECESSITY_API_BASE}/container/`
  if (residenceId !== undefined) {
    api += `?residence_id=${residenceId}`
  }
  const response = await fetch(api)
  if (!response.ok) {
    throw new Error('Failed to fetch containers')
  }
  return response.json()
}

export const api_get_container = async (id: number): Promise<ContainerData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/container/${id}`)
  if (!response.ok) {
    throw new Error('Failed to fetch container')
  }
  return response.json()
}

export const api_create_container = async (data: ContainerCreateProps): Promise<ContainerData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/container/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to create container')
  }
  return response.json()
}

export const api_update_container = async (id: number, data: ContainerCreateProps): Promise<ContainerData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/container/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to update container')
  }
  return response.json()
}

export const api_delete_container = async (id: number): Promise<{ id: number; status: string }> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/container/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete container')
  }
  return response.json()
}

export const api_get_container_tree = async (residenceId: number): Promise<ContainerTreeNode[]> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/container/tree/${residenceId}`)
  if (!response.ok) {
    throw new Error('Failed to fetch container tree')
  }
  return response.json()
}

// ============ Category APIs ============

export const api_get_categories = async (): Promise<ItemCategoryData[]> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/category/`)
  if (!response.ok) {
    throw new Error('Failed to fetch categories')
  }
  return response.json()
}

export const api_get_category = async (id: number): Promise<ItemCategoryData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/category/${id}`)
  if (!response.ok) {
    throw new Error('Failed to fetch category')
  }
  return response.json()
}

export const api_create_category = async (data: ItemCategoryCreateProps): Promise<ItemCategoryData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/category/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to create category')
  }
  return response.json()
}

export const api_update_category = async (id: number, data: ItemCategoryCreateProps): Promise<ItemCategoryData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/category/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to update category')
  }
  return response.json()
}

export const api_delete_category = async (id: number): Promise<{ id: number; status: string }> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/category/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete category')
  }
  return response.json()
}

export const api_get_category_tree = async (): Promise<CategoryTreeNode[]> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/category/tree`)
  if (!response.ok) {
    throw new Error('Failed to fetch category tree')
  }
  return response.json()
}

export const api_seed_categories = async (): Promise<ItemCategoryData[]> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/category/seed`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Failed to seed categories')
  }
  return response.json()
}

// ============ Item APIs ============

export const api_get_items = async (params?: ItemQueryParams): Promise<ItemData[]> => {
  let api = `${SERVER_URL}/${NECESSITY_API_BASE}/item/`
  if (params) {
    const urlParams = new URLSearchParams()
    if (params.skip !== undefined) urlParams.append('skip', params.skip.toString())
    if (params.limit !== undefined) urlParams.append('limit', params.limit.toString())
    if (params.category_id !== undefined) urlParams.append('category_id', params.category_id.toString())
    if (params.item_type !== undefined) urlParams.append('item_type', params.item_type.toString())
    if (params.state !== undefined) urlParams.append('state', params.state.toString())
    if (params.tags) urlParams.append('tags', params.tags)
    const queryString = urlParams.toString()
    if (queryString) api += '?' + queryString
  }
  const response = await fetch(api)
  if (!response.ok) {
    throw new Error('Failed to fetch items')
  }
  return response.json()
}

export const api_get_items_paginated = async (params?: ItemPaginatedParams): Promise<PaginatedResponse<ItemData>> => {
  let api = `${SERVER_URL}/${NECESSITY_API_BASE}/item/paginated/`
  if (params) {
    const urlParams = new URLSearchParams()
    if (params.page !== undefined) urlParams.append('page', params.page.toString())
    if (params.page_size !== undefined) urlParams.append('page_size', params.page_size.toString())
    if (params.category_id !== undefined) urlParams.append('category_id', params.category_id.toString())
    if (params.item_type !== undefined) urlParams.append('item_type', params.item_type.toString())
    if (params.state !== undefined) urlParams.append('state', params.state.toString())
    if (params.tags) urlParams.append('tags', params.tags)
    if (params.keyword) urlParams.append('keyword', params.keyword)
    if (params.sort_by) urlParams.append('sort_by', params.sort_by)
    if (params.sort_order) urlParams.append('sort_order', params.sort_order)
    const queryString = urlParams.toString()
    if (queryString) api += '?' + queryString
  }
  const response = await fetch(api)
  if (!response.ok) {
    throw new Error('Failed to fetch items')
  }
  return response.json()
}

export const api_get_item = async (id: number): Promise<ItemData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/item/${id}`)
  if (!response.ok) {
    throw new Error('Failed to fetch item')
  }
  return response.json()
}

export const api_create_item = async (data: ItemCreateProps): Promise<ItemData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/item/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to create item')
  }
  return response.json()
}

export const api_update_item = async (id: number, data: ItemCreateProps): Promise<ItemData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/item/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to update item')
  }
  return response.json()
}

export const api_delete_item = async (id: number): Promise<{ id: number; status: string }> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/item/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete item')
  }
  return response.json()
}

export const api_search_items = async (keyword: string, limit: number = 20): Promise<ItemData[]> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/item/search/?keyword=${encodeURIComponent(keyword)}&limit=${limit}`)
  if (!response.ok) {
    throw new Error('Failed to search items')
  }
  return response.json()
}

export const api_get_expiring_items = async (days: number = 30): Promise<ExpiringItem[]> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/item/expiring/?days=${days}`)
  if (!response.ok) {
    throw new Error('Failed to fetch expiring items')
  }
  return response.json()
}

export const api_get_portable_items = async (minPortability: number = 4): Promise<ItemData[]> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/item/portable/?min_portability=${minPortability}`)
  if (!response.ok) {
    throw new Error('Failed to fetch portable items')
  }
  return response.json()
}

export const api_get_item_locations = async (itemId: number): Promise<InventoryData[]> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/item/${itemId}/locations`)
  if (!response.ok) {
    throw new Error('Failed to fetch item locations')
  }
  return response.json()
}

// ============ Inventory APIs ============

export const api_get_inventories = async (): Promise<InventoryData[]> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/inventory/`)
  if (!response.ok) {
    throw new Error('Failed to fetch inventories')
  }
  return response.json()
}

export const api_get_inventory = async (id: number): Promise<InventoryData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/inventory/${id}`)
  if (!response.ok) {
    throw new Error('Failed to fetch inventory')
  }
  return response.json()
}

export const api_create_inventory = async (data: InventoryCreateProps): Promise<InventoryData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/inventory/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to create inventory')
  }
  return response.json()
}

export const api_update_inventory = async (id: number, data: InventoryCreateProps): Promise<InventoryData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/inventory/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to update inventory')
  }
  return response.json()
}

export const api_delete_inventory = async (id: number): Promise<{ id: number; status: string }> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/inventory/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete inventory')
  }
  return response.json()
}

export const api_consume_inventory = async (id: number, data: ConsumeInventoryProps): Promise<InventoryData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/inventory/${id}/consume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to consume inventory')
  }
  return response.json()
}

export const api_replenish_inventory = async (id: number, data: ReplenishInventoryProps): Promise<InventoryData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/inventory/${id}/replenish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to replenish inventory')
  }
  return response.json()
}

export const api_transfer_inventory = async (data: TransferInventoryProps): Promise<{ source: InventoryData; destination: InventoryData; transferred_quantity: string }> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/inventory/transfer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to transfer inventory')
  }
  return response.json()
}

export const api_get_low_stock = async (residenceId?: number): Promise<InventoryData[]> => {
  let api = `${SERVER_URL}/${NECESSITY_API_BASE}/inventory/low-stock/`
  if (residenceId !== undefined) {
    api += `?residence_id=${residenceId}`
  }
  const response = await fetch(api)
  if (!response.ok) {
    throw new Error('Failed to fetch low stock')
  }
  return response.json()
}

export const api_get_inventory_stats = async (residenceId?: number): Promise<InventoryStats> => {
  let api = `${SERVER_URL}/${NECESSITY_API_BASE}/inventory/stats/`
  if (residenceId !== undefined) {
    api += `?residence_id=${residenceId}`
  }
  const response = await fetch(api)
  if (!response.ok) {
    throw new Error('Failed to fetch inventory stats')
  }
  return response.json()
}

// ============ Journey APIs ============

export const api_get_journeys = async (status?: number, fromResidenceId?: number, toResidenceId?: number): Promise<JourneyData[]> => {
  let api = `${SERVER_URL}/${NECESSITY_API_BASE}/journey/`
  const params = new URLSearchParams()
  if (status !== undefined) params.append('status', status.toString())
  if (fromResidenceId !== undefined) params.append('from_residence_id', fromResidenceId.toString())
  if (toResidenceId !== undefined) params.append('to_residence_id', toResidenceId.toString())
  const queryString = params.toString()
  if (queryString) api += '?' + queryString
  
  const response = await fetch(api)
  if (!response.ok) {
    throw new Error('Failed to fetch journeys')
  }
  return response.json()
}

export const api_get_journey = async (id: number): Promise<JourneyData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/journey/${id}`)
  if (!response.ok) {
    throw new Error('Failed to fetch journey')
  }
  return response.json()
}

export const api_create_journey = async (data: JourneyCreateProps): Promise<JourneyData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/journey/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to create journey')
  }
  return response.json()
}

export const api_update_journey = async (id: number, data: JourneyCreateProps): Promise<JourneyData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/journey/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to update journey')
  }
  return response.json()
}

export const api_delete_journey = async (id: number): Promise<{ id: number; status: string }> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/journey/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete journey')
  }
  return response.json()
}

export const api_start_journey = async (id: number): Promise<JourneyData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/journey/${id}/start`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Failed to start journey')
  }
  return response.json()
}

export const api_complete_journey = async (id: number): Promise<JourneyData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/journey/${id}/complete`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Failed to complete journey')
  }
  return response.json()
}

export const api_cancel_journey = async (id: number): Promise<JourneyData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/journey/${id}/cancel`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Failed to cancel journey')
  }
  return response.json()
}

export const api_add_journey_item = async (journeyId: number, data: JourneyItemCreateProps): Promise<JourneyData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/journey/${journeyId}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error('Failed to add journey item')
  }
  return response.json()
}

export const api_remove_journey_item = async (journeyId: number, itemId: number): Promise<JourneyData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/journey/${journeyId}/items/${itemId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to remove journey item')
  }
  return response.json()
}

export const api_pack_journey_item = async (journeyId: number, itemId: number): Promise<JourneyData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/journey/${journeyId}/pack/${itemId}`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Failed to pack journey item')
  }
  return response.json()
}

export const api_unpack_journey_item = async (journeyId: number, itemId: number): Promise<JourneyData> => {
  const response = await fetch(`${SERVER_URL}/${NECESSITY_API_BASE}/journey/${journeyId}/unpack/${itemId}`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Failed to unpack journey item')
  }
  return response.json()
}
