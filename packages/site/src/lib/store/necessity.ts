/**
 * @file necessity.ts
 * @brief Necessity (生活物资) Zustand Store
 * @author sailing-innocent
 * @date 2026-02-01
 */

import { create } from 'zustand'
import {
  type ResidenceData,
  type ResidenceCreateProps,
  type ContainerData,
  type ContainerCreateProps,
  type ItemCategoryData,
  type ItemCategoryCreateProps,
  type CategoryTreeNode,
  type ItemData,
  type ItemCreateProps,
  type ItemQueryParams,
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

import {
  api_get_residences,
  api_get_residence,
  api_create_residence,
  api_update_residence,
  api_delete_residence,
  api_get_portable_residence,
  api_get_residence_inventory,
  api_get_containers,
  api_create_container,
  api_update_container,
  api_delete_container,
  api_get_container_tree,
  api_get_categories,
  api_create_category,
  api_update_category,
  api_delete_category,
  api_get_category_tree,
  api_seed_categories,
  api_get_items,
  api_get_item,
  api_create_item,
  api_update_item,
  api_delete_item,
  api_search_items,
  api_get_expiring_items,
  api_get_portable_items,
  api_get_item_locations,
  api_get_inventories,
  api_create_inventory,
  api_update_inventory,
  api_delete_inventory,
  api_consume_inventory,
  api_replenish_inventory,
  api_transfer_inventory,
  api_get_low_stock,
  api_get_inventory_stats,
  api_get_journeys,
  api_get_journey,
  api_create_journey,
  api_update_journey,
  api_delete_journey,
  api_start_journey,
  api_complete_journey,
  api_cancel_journey,
  api_add_journey_item,
  api_remove_journey_item,
} from '@lib/api/necessity'

// ============ Residence Store ============

interface ResidenceStore {
  residences: ResidenceData[]
  currentResidence: ResidenceData | null
  portableResidence: ResidenceData | null
  containers: ContainerData[]
  isLoading: boolean
  error: string | null

  fetchResidences: () => Promise<void>
  setCurrentResidence: (residence: ResidenceData | null) => void
  fetchContainers: (residenceId: number) => Promise<void>
  createResidence: (data: ResidenceCreateProps) => Promise<ResidenceData>
  updateResidence: (id: number, data: ResidenceCreateProps) => Promise<ResidenceData>
  deleteResidence: (id: number) => Promise<void>
  createContainer: (data: ContainerCreateProps) => Promise<ContainerData>
  updateContainer: (id: number, data: ContainerCreateProps) => Promise<ContainerData>
  deleteContainer: (id: number) => Promise<void>
  fetchPortableResidence: () => Promise<void>
}

export const useResidenceStore = create<ResidenceStore>((set, get) => ({
  residences: [],
  currentResidence: null,
  portableResidence: null,
  containers: [],
  isLoading: false,
  error: null,

  fetchResidences: async () => {
    set({ isLoading: true, error: null })
    try {
      const residences = await api_get_residences()
      set({ residences, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },

  setCurrentResidence: (residence) => {
    set({ currentResidence: residence })
    if (residence) {
      get().fetchContainers(residence.id)
    }
  },

  fetchContainers: async (residenceId) => {
    try {
      const containers = await api_get_containers(residenceId)
      set({ containers })
    } catch (error) {
      set({ error: (error as Error).message })
    }
  },

  createResidence: async (data) => {
    const residence = await api_create_residence(data)
    set((state) => ({ residences: [...state.residences, residence] }))
    return residence
  },

  updateResidence: async (id, data) => {
    const residence = await api_update_residence(id, data)
    set((state) => ({
      residences: state.residences.map((r) => (r.id === id ? residence : r)),
      currentResidence: state.currentResidence?.id === id ? residence : state.currentResidence,
    }))
    return residence
  },

  deleteResidence: async (id) => {
    await api_delete_residence(id)
    set((state) => ({
      residences: state.residences.filter((r) => r.id !== id),
      currentResidence: state.currentResidence?.id === id ? null : state.currentResidence,
    }))
  },

  createContainer: async (data) => {
    const container = await api_create_container(data)
    set((state) => ({ containers: [...state.containers, container] }))
    return container
  },

  updateContainer: async (id, data) => {
    const container = await api_update_container(id, data)
    set((state) => ({
      containers: state.containers.map((c) => (c.id === id ? container : c)),
    }))
    return container
  },

  deleteContainer: async (id) => {
    await api_delete_container(id)
    set((state) => ({
      containers: state.containers.filter((c) => c.id !== id),
    }))
  },

  fetchPortableResidence: async () => {
    try {
      const portableResidence = await api_get_portable_residence()
      set({ portableResidence })
    } catch (error) {
      set({ error: (error as Error).message })
    }
  },
}))

// ============ Category Store ============

interface CategoryStore {
  categories: ItemCategoryData[]
  categoryTree: CategoryTreeNode[]
  isLoading: boolean
  error: string | null

  fetchCategories: () => Promise<void>
  fetchCategoryTree: () => Promise<void>
  createCategory: (data: ItemCategoryCreateProps) => Promise<ItemCategoryData>
  updateCategory: (id: number, data: ItemCategoryCreateProps) => Promise<ItemCategoryData>
  deleteCategory: (id: number) => Promise<void>
  seedCategories: () => Promise<void>
}

export const useCategoryStore = create<CategoryStore>((set) => ({
  categories: [],
  categoryTree: [],
  isLoading: false,
  error: null,

  fetchCategories: async () => {
    set({ isLoading: true, error: null })
    try {
      const categories = await api_get_categories()
      set({ categories, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },

  fetchCategoryTree: async () => {
    try {
      const categoryTree = await api_get_category_tree()
      set({ categoryTree })
    } catch (error) {
      set({ error: (error as Error).message })
    }
  },

  createCategory: async (data) => {
    const category = await api_create_category(data)
    set((state) => ({ categories: [...state.categories, category] }))
    return category
  },

  updateCategory: async (id, data) => {
    const category = await api_update_category(id, data)
    set((state) => ({
      categories: state.categories.map((c) => (c.id === id ? category : c)),
    }))
    return category
  },

  deleteCategory: async (id) => {
    await api_delete_category(id)
    set((state) => ({
      categories: state.categories.filter((c) => c.id !== id),
    }))
  },

  seedCategories: async () => {
    set({ isLoading: true })
    try {
      const categories = await api_seed_categories()
      set({ categories, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },
}))

// ============ Items Store ============

interface ItemsStore {
  items: ItemData[]
  currentItem: ItemData | null
  expiringItems: ExpiringItem[]
  isLoading: boolean
  error: string | null
  filters: ItemQueryParams

  fetchItems: (params?: ItemQueryParams) => Promise<void>
  fetchItem: (id: number) => Promise<void>
  createItem: (data: ItemCreateProps) => Promise<ItemData>
  updateItem: (id: number, data: ItemCreateProps) => Promise<ItemData>
  deleteItem: (id: number) => Promise<void>
  searchItems: (keyword: string) => Promise<ItemData[]>
  fetchExpiringItems: (days?: number) => Promise<void>
  fetchPortableItems: () => Promise<ItemData[]>
  getItemLocations: (id: number) => Promise<InventoryData[]>
  setFilters: (filters: Partial<ItemQueryParams>) => void
  setCurrentItem: (item: ItemData | null) => void
}

export const useItemsStore = create<ItemsStore>((set, get) => ({
  items: [],
  currentItem: null,
  expiringItems: [],
  isLoading: false,
  error: null,
  filters: {},

  fetchItems: async (params) => {
    set({ isLoading: true, error: null })
    try {
      const mergedParams = { ...get().filters, ...params }
      const items = await api_get_items(mergedParams)
      set({ items, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },

  fetchItem: async (id) => {
    try {
      const item = await api_get_item(id)
      set({ currentItem: item })
    } catch (error) {
      set({ error: (error as Error).message })
    }
  },

  createItem: async (data) => {
    const item = await api_create_item(data)
    set((state) => ({ items: [...state.items, item] }))
    return item
  },

  updateItem: async (id, data) => {
    const item = await api_update_item(id, data)
    set((state) => ({
      items: state.items.map((i) => (i.id === id ? item : i)),
      currentItem: state.currentItem?.id === id ? item : state.currentItem,
    }))
    return item
  },

  deleteItem: async (id) => {
    await api_delete_item(id)
    set((state) => ({
      items: state.items.filter((i) => i.id !== id),
      currentItem: state.currentItem?.id === id ? null : state.currentItem,
    }))
  },

  searchItems: async (keyword) => {
    return await api_search_items(keyword)
  },

  fetchExpiringItems: async (days = 30) => {
    try {
      const expiringItems = await api_get_expiring_items(days)
      set({ expiringItems })
    } catch (error) {
      set({ error: (error as Error).message })
    }
  },

  fetchPortableItems: async () => {
    return await api_get_portable_items()
  },

  getItemLocations: async (id) => {
    return await api_get_item_locations(id)
  },

  setFilters: (filters) => {
    set((state) => ({ filters: { ...state.filters, ...filters } }))
  },

  setCurrentItem: (item) => {
    set({ currentItem: item })
  },
}))

// ============ Inventory Store ============

interface InventoryStore {
  inventories: InventoryData[]
  lowStockItems: InventoryData[]
  stats: InventoryStats | null
  isLoading: boolean
  error: string | null

  fetchInventories: () => Promise<void>
  fetchInventoriesByResidence: (residenceId: number) => Promise<void>
  createInventory: (data: InventoryCreateProps) => Promise<InventoryData>
  updateInventory: (id: number, data: InventoryCreateProps) => Promise<InventoryData>
  deleteInventory: (id: number) => Promise<void>
  recordConsumption: (id: number, data: ConsumeInventoryProps) => Promise<InventoryData>
  recordReplenishment: (id: number, data: ReplenishInventoryProps) => Promise<InventoryData>
  transferInventory: (data: TransferInventoryProps) => Promise<void>
  fetchLowStock: (residenceId?: number) => Promise<void>
  fetchStats: (residenceId?: number) => Promise<void>
}

export const useInventoryStore = create<InventoryStore>((set) => ({
  inventories: [],
  lowStockItems: [],
  stats: null,
  isLoading: false,
  error: null,

  fetchInventories: async () => {
    set({ isLoading: true, error: null })
    try {
      const inventories = await api_get_inventories()
      set({ inventories, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },

  fetchInventoriesByResidence: async (residenceId) => {
    set({ isLoading: true, error: null })
    try {
      const inventories = await api_get_residence_inventory(residenceId)
      set({ inventories, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },

  createInventory: async (data) => {
    const inventory = await api_create_inventory(data)
    set((state) => ({ inventories: [...state.inventories, inventory] }))
    return inventory
  },

  updateInventory: async (id, data) => {
    const inventory = await api_update_inventory(id, data)
    set((state) => ({
      inventories: state.inventories.map((i) => (i.id === id ? inventory : i)),
    }))
    return inventory
  },

  deleteInventory: async (id) => {
    await api_delete_inventory(id)
    set((state) => ({
      inventories: state.inventories.filter((i) => i.id !== id),
    }))
  },

  recordConsumption: async (id, data) => {
    const inventory = await api_consume_inventory(id, data)
    set((state) => ({
      inventories: state.inventories.map((i) => (i.id === id ? inventory : i)),
    }))
    return inventory
  },

  recordReplenishment: async (id, data) => {
    const inventory = await api_replenish_inventory(id, data)
    set((state) => ({
      inventories: state.inventories.map((i) => (i.id === id ? inventory : i)),
    }))
    return inventory
  },

  transferInventory: async (data) => {
    await api_transfer_inventory(data)
    // Refresh inventories after transfer
    const inventories = await api_get_inventories()
    set({ inventories })
  },

  fetchLowStock: async (residenceId) => {
    try {
      const lowStockItems = await api_get_low_stock(residenceId)
      set({ lowStockItems })
    } catch (error) {
      set({ error: (error as Error).message })
    }
  },

  fetchStats: async (residenceId) => {
    try {
      const stats = await api_get_inventory_stats(residenceId)
      set({ stats })
    } catch (error) {
      set({ error: (error as Error).message })
    }
  },
}))

// ============ Journey Store ============

interface JourneyStore {
  journeys: JourneyData[]
  currentJourney: JourneyData | null
  isLoading: boolean
  error: string | null

  fetchJourneys: (status?: number) => Promise<void>
  fetchJourney: (id: number) => Promise<void>
  createJourney: (data: JourneyCreateProps) => Promise<JourneyData>
  updateJourney: (id: number, data: JourneyCreateProps) => Promise<JourneyData>
  deleteJourney: (id: number) => Promise<void>
  startJourney: (id: number) => Promise<JourneyData>
  completeJourney: (id: number) => Promise<JourneyData>
  cancelJourney: (id: number) => Promise<JourneyData>
  addJourneyItem: (journeyId: number, data: JourneyItemCreateProps) => Promise<void>
  removeJourneyItem: (journeyId: number, itemId: number) => Promise<void>
  setCurrentJourney: (journey: JourneyData | null) => void
}

export const useJourneyStore = create<JourneyStore>((set, get) => ({
  journeys: [],
  currentJourney: null,
  isLoading: false,
  error: null,

  fetchJourneys: async (status) => {
    set({ isLoading: true, error: null })
    try {
      const journeys = await api_get_journeys(status)
      set({ journeys, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },

  fetchJourney: async (id) => {
    try {
      const journey = await api_get_journey(id)
      set({ currentJourney: journey })
    } catch (error) {
      set({ error: (error as Error).message })
    }
  },

  createJourney: async (data) => {
    const journey = await api_create_journey(data)
    set((state) => ({ journeys: [...state.journeys, journey] }))
    return journey
  },

  updateJourney: async (id, data) => {
    const journey = await api_update_journey(id, data)
    set((state) => ({
      journeys: state.journeys.map((j) => (j.id === id ? journey : j)),
      currentJourney: state.currentJourney?.id === id ? journey : state.currentJourney,
    }))
    return journey
  },

  deleteJourney: async (id) => {
    await api_delete_journey(id)
    set((state) => ({
      journeys: state.journeys.filter((j) => j.id !== id),
      currentJourney: state.currentJourney?.id === id ? null : state.currentJourney,
    }))
  },

  startJourney: async (id) => {
    const journey = await api_start_journey(id)
    set((state) => ({
      journeys: state.journeys.map((j) => (j.id === id ? journey : j)),
      currentJourney: state.currentJourney?.id === id ? journey : state.currentJourney,
    }))
    return journey
  },

  completeJourney: async (id) => {
    const journey = await api_complete_journey(id)
    set((state) => ({
      journeys: state.journeys.map((j) => (j.id === id ? journey : j)),
      currentJourney: state.currentJourney?.id === id ? journey : state.currentJourney,
    }))
    return journey
  },

  cancelJourney: async (id) => {
    const journey = await api_cancel_journey(id)
    set((state) => ({
      journeys: state.journeys.map((j) => (j.id === id ? journey : j)),
      currentJourney: state.currentJourney?.id === id ? journey : state.currentJourney,
    }))
    return journey
  },

  addJourneyItem: async (journeyId, data) => {
    const journey = await api_add_journey_item(journeyId, data)
    set((state) => ({
      journeys: state.journeys.map((j) => (j.id === journeyId ? journey : j)),
      currentJourney: state.currentJourney?.id === journeyId ? journey : state.currentJourney,
    }))
  },

  removeJourneyItem: async (journeyId, itemId) => {
    const journey = await api_remove_journey_item(journeyId, itemId)
    set((state) => ({
      journeys: state.journeys.map((j) => (j.id === journeyId ? journey : j)),
      currentJourney: state.currentJourney?.id === journeyId ? journey : state.currentJourney,
    }))
  },

  setCurrentJourney: (journey) => {
    set({ currentJourney: journey })
  },
}))
