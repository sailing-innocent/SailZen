/**
 * @file necessity.ts
 * @brief Necessity (生活物资) data types
 * @author sailing-innocent
 * @date 2026-02-01
 */

// Enums

export enum ResidenceType {
  STABLE = 0,     // 稳定仓库（长期存储）
  BACKUP = 1,     // 后备仓库（备用物资）
  LIVING = 2,     // 生活住所（日常居住）
  PORTABLE = 3,   // 随身携带
}

export const ResidenceTypeLabels: Record<ResidenceType, string> = {
  [ResidenceType.STABLE]: '稳定仓库',
  [ResidenceType.BACKUP]: '后备仓库',
  [ResidenceType.LIVING]: '生活住所',
  [ResidenceType.PORTABLE]: '随身携带',
}

export enum ContainerType {
  ROOM = 0,       // 房间
  CABINET = 1,    // 柜子/衣柜
  DRAWER = 2,     // 抽屉
  BOX = 3,        // 箱子/盒子
  BAG = 4,        // 包/背包
  SHELF = 5,      // 架子
  OTHER = 99,     // 其他
}

export const ContainerTypeLabels: Record<ContainerType, string> = {
  [ContainerType.ROOM]: '房间',
  [ContainerType.CABINET]: '柜子',
  [ContainerType.DRAWER]: '抽屉',
  [ContainerType.BOX]: '箱子',
  [ContainerType.BAG]: '背包',
  [ContainerType.SHELF]: '架子',
  [ContainerType.OTHER]: '其他',
}

export enum ItemType {
  UNIQUE = 0,     // 唯一物品（如证件、电器）
  BULK = 1,       // 批量物品（如消耗品）
}

export const ItemTypeLabels: Record<ItemType, string> = {
  [ItemType.UNIQUE]: '唯一物品',
  [ItemType.BULK]: '批量物品',
}

export enum ItemState {
  ACTIVE = 0,     // 正常使用
  STORED = 1,     // 存储中（不常用）
  LENDING = 2,    // 借出
  REPAIRING = 3,  // 维修中
  DISPOSED = 4,   // 已处置/丢弃
  LOST = 5,       // 丢失
}

export const ItemStateLabels: Record<ItemState, string> = {
  [ItemState.ACTIVE]: '正常使用',
  [ItemState.STORED]: '存储中',
  [ItemState.LENDING]: '借出',
  [ItemState.REPAIRING]: '维修中',
  [ItemState.DISPOSED]: '已处置',
  [ItemState.LOST]: '丢失',
}

export enum JourneyStatus {
  PLANNED = 0,    // 计划中
  IN_TRANSIT = 1, // 进行中
  COMPLETED = 2,  // 已完成
  CANCELLED = 3,  // 已取消
}

export const JourneyStatusLabels: Record<JourneyStatus, string> = {
  [JourneyStatus.PLANNED]: '计划中',
  [JourneyStatus.IN_TRANSIT]: '进行中',
  [JourneyStatus.COMPLETED]: '已完成',
  [JourneyStatus.CANCELLED]: '已取消',
}

export enum JourneyItemStatus {
  PENDING = 0,    // 待打包
  PACKED = 1,     // 已打包
  TRANSFERRED = 2, // 已转移
  UNPACKED = 3,   // 已拆包
}

export const JourneyItemStatusLabels: Record<JourneyItemStatus, string> = {
  [JourneyItemStatus.PENDING]: '待打包',
  [JourneyItemStatus.PACKED]: '已打包',
  [JourneyItemStatus.TRANSFERRED]: '已转移',
  [JourneyItemStatus.UNPACKED]: '已拆包',
}

export enum ReplenishmentSource {
  PURCHASE = 0,   // 购买
  TRANSFER = 1,   // 调拨（从其他住所）
  GIFT = 2,       // 赠送
  RETURN = 3,     // 归还
}

export const ReplenishmentSourceLabels: Record<ReplenishmentSource, string> = {
  [ReplenishmentSource.PURCHASE]: '购买',
  [ReplenishmentSource.TRANSFER]: '调拨',
  [ReplenishmentSource.GIFT]: '赠送',
  [ReplenishmentSource.RETURN]: '归还',
}

// Data Interfaces

export interface ResidenceData {
  id: number
  name: string
  code: string
  type: ResidenceType
  address: string
  description: string
  is_portable: boolean
  priority: number
  ctime?: string
  mtime?: string
}

export interface ContainerData {
  id: number
  residence_id: number
  parent_id: number | null
  name: string
  type: ContainerType
  description: string
  capacity: number | null
  ctime?: string
  mtime?: string
}

export interface ContainerTreeNode {
  id: number
  name: string
  type: ContainerType
  description: string
  parent_id: number | null
  children: ContainerTreeNode[]
}

export interface ItemCategoryData {
  id: number
  parent_id: number | null
  name: string
  code: string
  icon: string
  is_consumable: boolean
  default_unit: string
  description: string
  ctime?: string
  mtime?: string
}

export interface CategoryTreeNode {
  id: number
  name: string
  code: string
  icon: string
  is_consumable: boolean
  default_unit: string
  parent_id: number | null
  children: CategoryTreeNode[]
}

export interface ItemData {
  id: number
  name: string
  category_id: number | null
  type: ItemType
  brand: string
  model: string
  serial_number: string
  description: string
  purchase_date: number | null  // timestamp
  purchase_price: string
  warranty_until: number | null  // timestamp
  expire_date: number | null     // timestamp
  importance: number  // 1-5
  portability: number  // 1-5
  tags: string
  image_url: string
  state: ItemState
  ctime?: string
  mtime?: string
}

export interface InventoryData {
  id: number
  item_id: number
  residence_id: number
  container_id: number | null
  quantity: string
  unit: string
  min_quantity: string
  max_quantity: string
  last_check_time: number | null  // timestamp
  notes: string
  item_name?: string
  residence_name?: string
  container_name?: string
  ctime?: string
  mtime?: string
}

export interface JourneyData {
  id: number
  from_residence_id: number
  to_residence_id: number
  depart_time: number | null  // timestamp
  arrive_time: number | null  // timestamp
  status: JourneyStatus
  transport_mode: string
  notes: string
  from_residence_name?: string
  to_residence_name?: string
  items?: JourneyItemData[]
  ctime?: string
  mtime?: string
}

export interface JourneyItemData {
  id: number
  journey_id: number
  item_id: number
  quantity: string
  is_return: boolean
  from_container_id: number | null
  to_container_id: number | null
  status: JourneyItemStatus
  notes: string
  item_name?: string
  ctime?: string
  mtime?: string
}

export interface ConsumptionData {
  id: number
  inventory_id: number
  quantity: string
  htime: number  // timestamp
  reason: string
  ctime?: string
}

export interface ReplenishmentData {
  id: number
  inventory_id: number
  quantity: string
  source: ReplenishmentSource
  source_residence_id: number | null
  cost: string
  transaction_id: number | null
  htime: number  // timestamp
  notes: string
  ctime?: string
}

// Create/Update Props (without id, ctime, mtime)

export interface ResidenceCreateProps {
  name: string
  code?: string
  type?: ResidenceType
  address?: string
  description?: string
  is_portable?: boolean
  priority?: number
}

export interface ContainerCreateProps {
  residence_id: number
  parent_id?: number | null
  name: string
  type?: ContainerType
  description?: string
  capacity?: number | null
}

export interface ItemCategoryCreateProps {
  parent_id?: number | null
  name: string
  code?: string
  icon?: string
  is_consumable?: boolean
  default_unit?: string
  description?: string
}

export interface ItemCreateProps {
  name: string
  category_id?: number | null
  type?: ItemType
  brand?: string
  model?: string
  serial_number?: string
  description?: string
  purchase_date?: number | null
  purchase_price?: string
  warranty_until?: number | null
  expire_date?: number | null
  importance?: number
  portability?: number
  tags?: string
  image_url?: string
  state?: ItemState
}

export interface InventoryCreateProps {
  item_id: number
  residence_id: number
  container_id?: number | null
  quantity?: string
  unit?: string
  min_quantity?: string
  max_quantity?: string
  last_check_time?: number | null
  notes?: string
}

export interface JourneyCreateProps {
  from_residence_id: number
  to_residence_id: number
  depart_time?: number | null
  arrive_time?: number | null
  status?: JourneyStatus
  transport_mode?: string
  notes?: string
}

export interface JourneyItemCreateProps {
  item_id: number
  quantity?: string
  is_return?: boolean
  from_container_id?: number | null
  to_container_id?: number | null
  notes?: string
}

export interface TransferInventoryProps {
  item_id: number
  from_residence_id: number
  to_residence_id: number
  quantity: string
  from_container_id?: number | null
  to_container_id?: number | null
}

export interface ConsumeInventoryProps {
  quantity: string
  reason?: string
}

export interface ReplenishInventoryProps {
  quantity: string
  source?: ReplenishmentSource
  source_residence_id?: number | null
  cost?: string
  transaction_id?: number | null
  notes?: string
}

// Query params

export interface ItemQueryParams {
  skip?: number
  limit?: number
  category_id?: number
  item_type?: number
  state?: number
  tags?: string
  keyword?: string
}

export interface ItemPaginatedParams {
  page?: number
  page_size?: number
  category_id?: number
  item_type?: number
  state?: number
  tags?: string
  keyword?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

// Stats

export interface InventoryStats {
  total_items: number
  total_quantity: string
  low_stock_count: number
}

export interface ExpiringItem {
  item: ItemData
  days_remaining: number
  severity: 'urgent' | 'warning'
}
