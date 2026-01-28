# 生活物资管理

## 1. 概述

生活物资管理模块是 SailZen 系统中的实物资产管理核心功能，用于追踪和管理分布在多个住所的生活物资，支持旅程携带、日常消耗补充和物资定位。

### 1.1 场景背景

当前生活轨迹涉及多个住所：

| 住所 | 定位 | 特点 | 存放物资类型 |
|------|------|------|-------------|
| 合肥住所 | 稳定仓库 | 最稳定，长期存储 | 重要证件原件（毕业证、户口本）、季节性物品、备用电器 |
| 杭州住所 | 后备仓库 | 周末频繁往返 | 换洗衣物、游戏机等电器、上海住所的补给物资 |
| 上海住所 | 工作住所 | 保持最小生活必须 | 必要换洗衣物、被褥、洗漱用品、健康护理用品 |
| 随身携带 | 移动仓库 | 随人移动 | 身份证、护照、银行卡、手机、iPad、笔记本等 |

核心需求：
- **物资定位**：追踪物资当前所在位置
- **旅程管理**：记录每次住所间的往返及携带物资
- **消耗追踪**：管理日常消耗品的库存和补充
- **智能提醒**：物资不足、证件过期等提醒

### 1.2 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (packages/site)                  │
├─────────────────────────────────────────────────────────────┤
│  Pages: necessity.tsx                                        │
│  Components: residence_*, item_*, journey_*, inventory_*     │
│  Store: Zustand (useResidenceStore, useItemsStore,          │
│         useJourneyStore, useInventoryStore)                  │
│  API Client: lib/api/necessity.ts                           │
├─────────────────────────────────────────────────────────────┤
│                    Backend (sail_server)                     │
├─────────────────────────────────────────────────────────────┤
│  Controllers: necessity.py (Residence/Item/Journey)          │
│  Models: model/necessity.py                                  │
│  Data: data/necessity.py (ORM models)                        │
│  Utils: utils/inventory.py (库存计算、消耗预测)               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 核心概念与数据模型

### 2.1 住所 (Residence)

住所是物资存储的顶级位置，代表一个物理空间。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| name | String | 住所名称（必填） |
| code | String | 住所代码（如 HF/HZ/SH，唯一） |
| type | Integer | 住所类型（枚举） |
| address | String | 详细地址 |
| description | String | 描述 |
| is_portable | Boolean | 是否可移动（用于"随身携带"） |
| priority | Integer | 补货优先级（数字越小越优先） |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

**住所类型枚举**：

| 类型 | 值 | 说明 |
|------|-----|------|
| STABLE | 0 | 稳定仓库（长期存储） |
| BACKUP | 1 | 后备仓库（备用物资） |
| LIVING | 2 | 生活住所（日常居住） |
| PORTABLE | 3 | 随身携带 |

### 2.2 存储位置 (Container)

存储位置是住所内的具体存储单元，如衣柜、抽屉、背包等。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| residence_id | Integer | 所属住所ID（外键） |
| parent_id | Integer | 父容器ID（支持嵌套，可为空） |
| name | String | 容器名称（必填） |
| type | Integer | 容器类型 |
| description | String | 描述 |
| capacity | Integer | 容量（可选，用于容量管理） |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

**容器类型枚举**：

| 类型 | 值 | 说明 |
|------|-----|------|
| ROOM | 0 | 房间 |
| CABINET | 1 | 柜子/衣柜 |
| DRAWER | 2 | 抽屉 |
| BOX | 3 | 箱子/盒子 |
| BAG | 4 | 包/背包 |
| SHELF | 5 | 架子 |
| OTHER | 99 | 其他 |

### 2.3 物资类别 (ItemCategory)

物资的分类体系，支持层级分类。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| parent_id | Integer | 父类别ID（可为空） |
| name | String | 类别名称（必填） |
| code | String | 类别代码（唯一） |
| icon | String | 图标标识 |
| is_consumable | Boolean | 是否为消耗品 |
| default_unit | String | 默认计量单位 |
| description | String | 描述 |

**预设类别**：

```
├── 证件文件 (DOCUMENT)
│   ├── 身份证件 (ID_DOC)
│   ├── 金融卡证 (FINANCE_DOC)
│   └── 学历证件 (EDU_DOC)
├── 电子设备 (ELECTRONICS)
│   ├── 通讯设备 (COMM_DEVICE)
│   ├── 计算设备 (COMPUTE_DEVICE)
│   └── 娱乐设备 (ENTERTAINMENT_DEVICE)
├── 衣物 (CLOTHING)
│   ├── 上装 (TOPS)
│   ├── 下装 (BOTTOMS)
│   ├── 内衣 (UNDERWEAR)
│   └── 鞋袜 (FOOTWEAR)
├── 日用消耗 (DAILY_CONSUMABLE)
│   ├── 洗漱用品 (TOILETRY)
│   ├── 护理用品 (CARE_PRODUCT)
│   └── 清洁用品 (CLEANING)
├── 家居用品 (HOME)
│   ├── 床上用品 (BEDDING)
│   └── 厨房用品 (KITCHEN)
└── 健康护理 (HEALTH)
    ├── 常备药品 (MEDICINE)
    └── 护理器具 (CARE_TOOL)
```

### 2.4 物资 (Item)

物资是管理的基本单元，代表一个具体的物品或一类消耗品。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| name | String | 物资名称（必填） |
| category_id | Integer | 类别ID（外键） |
| type | Integer | 物资类型（唯一/批量） |
| brand | String | 品牌 |
| model | String | 型号/规格 |
| serial_number | String | 序列号（唯一物品） |
| description | String | 描述 |
| purchase_date | DATE | 购买日期 |
| purchase_price | String | 购买价格 |
| warranty_until | DATE | 保修截止日期 |
| expire_date | DATE | 有效期/过期日期 |
| importance | Integer | 重要程度（1-5） |
| portability | Integer | 便携性（1-5，5最便携） |
| tags | String | 标签（逗号分隔） |
| image_url | String | 图片URL |
| state | Integer | 状态 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

**物资类型**：

| 类型 | 值 | 说明 |
|------|-----|------|
| UNIQUE | 0 | 唯一物品（如证件、电器） |
| BULK | 1 | 批量物品（如消耗品） |

**物资状态**：

| 状态 | 值 | 说明 |
|------|-----|------|
| ACTIVE | 0 | 正常使用 |
| STORED | 1 | 存储中（不常用） |
| LENDING | 2 | 借出 |
| REPAIRING | 3 | 维修中 |
| DISPOSED | 4 | 已处置/丢弃 |
| LOST | 5 | 丢失 |

### 2.5 库存记录 (Inventory)

记录物资在具体位置的库存状态。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| item_id | Integer | 物资ID（外键） |
| residence_id | Integer | 住所ID（外键） |
| container_id | Integer | 容器ID（外键，可为空） |
| quantity | Decimal | 数量 |
| unit | String | 单位 |
| min_quantity | Decimal | 最小库存警戒值 |
| max_quantity | Decimal | 最大库存值 |
| last_check_time | TIMESTAMP | 最后盘点时间 |
| notes | String | 备注 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

**唯一约束**：`(item_id, residence_id, container_id)` 联合唯一

### 2.6 旅程 (Journey)

记录住所间的往返及物资携带情况。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| from_residence_id | Integer | 出发住所ID |
| to_residence_id | Integer | 目的住所ID |
| depart_time | TIMESTAMP | 出发时间 |
| arrive_time | TIMESTAMP | 到达时间 |
| status | Integer | 旅程状态 |
| transport_mode | String | 交通方式 |
| notes | String | 备注 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

**旅程状态**：

| 状态 | 值 | 说明 |
|------|-----|------|
| PLANNED | 0 | 计划中 |
| IN_TRANSIT | 1 | 进行中 |
| COMPLETED | 2 | 已完成 |
| CANCELLED | 3 | 已取消 |

### 2.7 旅程物资 (JourneyItem)

记录旅程中携带的物资清单。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| journey_id | Integer | 旅程ID（外键） |
| item_id | Integer | 物资ID（外键） |
| quantity | Decimal | 携带数量 |
| is_return | Boolean | 是否归还（否则为转移） |
| from_container_id | Integer | 来源容器ID |
| to_container_id | Integer | 目的容器ID |
| status | Integer | 物资状态 |
| notes | String | 备注 |

**物资携带状态**：

| 状态 | 值 | 说明 |
|------|-----|------|
| PENDING | 0 | 待打包 |
| PACKED | 1 | 已打包 |
| TRANSFERRED | 2 | 已转移 |
| UNPACKED | 3 | 已拆包 |

### 2.8 消耗记录 (Consumption)

记录消耗品的使用情况，用于预测补货需求。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| inventory_id | Integer | 库存记录ID（外键） |
| quantity | Decimal | 消耗数量 |
| htime | TIMESTAMP | 发生时间 |
| reason | String | 消耗原因 |
| ctime | TIMESTAMP | 创建时间 |

### 2.9 补货记录 (Replenishment)

记录物资的补充情况。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| inventory_id | Integer | 库存记录ID（外键） |
| quantity | Decimal | 补充数量 |
| source | Integer | 来源类型 |
| source_residence_id | Integer | 来源住所ID（调拨时） |
| cost | String | 花费（购买时） |
| transaction_id | Integer | 关联交易ID（外键，可选） |
| htime | TIMESTAMP | 发生时间 |
| notes | String | 备注 |
| ctime | TIMESTAMP | 创建时间 |

**来源类型**：

| 类型 | 值 | 说明 |
|------|-----|------|
| PURCHASE | 0 | 购买 |
| TRANSFER | 1 | 调拨（从其他住所） |
| GIFT | 2 | 赠送 |
| RETURN | 3 | 归还 |

---

## 3. 后端 API 接口

### 3.1 住所接口 (`/api/v1/necessity/residence`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取住所列表 |
| GET | `/{id}` | 获取住所详情（含容器树） |
| POST | `/` | 创建住所 |
| PUT | `/{id}` | 更新住所 |
| DELETE | `/{id}` | 删除住所 |
| GET | `/{id}/inventory` | 获取住所全部库存 |
| GET | `/{id}/low-stock` | 获取住所低库存物资 |

### 3.2 容器接口 (`/api/v1/necessity/container`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取容器列表（支持按住所筛选） |
| GET | `/{id}` | 获取容器详情 |
| POST | `/` | 创建容器 |
| PUT | `/{id}` | 更新容器 |
| DELETE | `/{id}` | 删除容器 |
| GET | `/{id}/items` | 获取容器内物资 |
| GET | `/tree/{residence_id}` | 获取住所容器树 |

### 3.3 物资类别接口 (`/api/v1/necessity/category`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取类别列表 |
| GET | `/tree` | 获取类别树 |
| POST | `/` | 创建类别 |
| PUT | `/{id}` | 更新类别 |
| DELETE | `/{id}` | 删除类别 |

### 3.4 物资接口 (`/api/v1/necessity/item`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取物资列表（支持分页、筛选） |
| GET | `/{id}` | 获取物资详情 |
| POST | `/` | 创建物资 |
| PUT | `/{id}` | 更新物资 |
| DELETE | `/{id}` | 删除物资 |
| GET | `/{id}/locations` | 获取物资所有存放位置 |
| GET | `/{id}/history` | 获取物资移动历史 |
| GET | `/search` | 搜索物资 |
| GET | `/expiring` | 获取即将过期物资 |
| GET | `/portable` | 获取可随身携带物资清单 |

**查询参数**：
- `skip`, `limit`: 分页
- `category_id`: 按类别筛选
- `residence_id`: 按住所筛选
- `type`: 按物资类型筛选
- `state`: 按状态筛选
- `tags`: 按标签筛选
- `keyword`: 关键词搜索

### 3.5 库存接口 (`/api/v1/necessity/inventory`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取库存列表 |
| GET | `/{id}` | 获取库存详情 |
| POST | `/` | 创建库存记录 |
| PUT | `/{id}` | 更新库存 |
| DELETE | `/{id}` | 删除库存记录 |
| POST | `/{id}/consume` | 记录消耗 |
| POST | `/{id}/replenish` | 记录补货 |
| POST | `/transfer` | 库存转移 |
| GET | `/low-stock` | 获取全局低库存清单 |
| GET | `/stats` | 获取库存统计 |

**库存转移请求**：
```json
{
  "item_id": 1,
  "from_residence_id": 2,
  "to_residence_id": 3,
  "quantity": 5,
  "from_container_id": 10,
  "to_container_id": 20
}
```

### 3.6 旅程接口 (`/api/v1/necessity/journey`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取旅程列表 |
| GET | `/{id}` | 获取旅程详情（含物资清单） |
| POST | `/` | 创建旅程 |
| PUT | `/{id}` | 更新旅程 |
| DELETE | `/{id}` | 删除旅程 |
| POST | `/{id}/start` | 开始旅程 |
| POST | `/{id}/complete` | 完成旅程 |
| POST | `/{id}/cancel` | 取消旅程 |
| GET | `/{id}/items` | 获取旅程物资清单 |
| POST | `/{id}/items` | 添加旅程物资 |
| DELETE | `/{id}/items/{item_id}` | 移除旅程物资 |
| POST | `/{id}/pack` | 标记物资已打包 |
| POST | `/{id}/unpack` | 标记物资已拆包 |
| GET | `/suggest-items/{from_id}/{to_id}` | 获取建议携带物资 |

**创建旅程请求**：
```json
{
  "from_residence_id": 3,
  "to_residence_id": 2,
  "depart_time": "2024-01-20T08:00:00",
  "arrive_time": "2024-01-20T12:00:00",
  "transport_mode": "高铁",
  "items": [
    {
      "item_id": 1,
      "quantity": 1,
      "is_return": false
    }
  ]
}
```

### 3.7 消耗与补货接口 (`/api/v1/necessity/consumption`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取消耗记录 |
| GET | `/stats` | 获取消耗统计 |
| GET | `/predict/{item_id}` | 预测补货时间 |

---

## 4. 前端功能模块

### 4.1 主页面布局 (`necessity.tsx`)

页面采用响应式设计：
- **桌面端**：住所概览(30%) + 物资管理(70%)
- **移动端**：垂直堆叠布局，优先显示当前住所

主要区域：
1. 住所切换与概览区
2. 物资清单区
3. 旅程管理区
4. 库存预警区

### 4.2 住所管理组件

| 组件 | 文件 | 功能 |
|------|------|------|
| ResidenceSelector | `residence_selector.tsx` | 住所切换下拉框 |
| ResidenceCard | `residence_card.tsx` | 住所概览卡片 |
| ResidenceOverview | `residence_overview.tsx` | 住所详情与统计 |
| ContainerTree | `container_tree.tsx` | 容器树形结构 |
| ContainerAddDialog | `container_add_dialog.tsx` | 添加容器对话框 |

### 4.3 物资管理组件

| 组件 | 文件 | 功能 |
|------|------|------|
| ItemsDataTable | `items_data_table.tsx` | 物资列表表格 |
| ItemCard | `item_card.tsx` | 物资卡片（图文） |
| ItemAddDialog | `item_add_dialog.tsx` | 添加物资对话框 |
| ItemEditDialog | `item_edit_dialog.tsx` | 编辑物资对话框 |
| ItemDetailSheet | `item_detail_sheet.tsx` | 物资详情侧边栏 |
| ItemFilters | `item_filters.tsx` | 物资筛选器 |
| ItemSearch | `item_search.tsx` | 物资搜索框 |
| CategorySelector | `category_selector.tsx` | 类别选择器（树形） |

### 4.4 库存管理组件

| 组件 | 文件 | 功能 |
|------|------|------|
| InventoryTable | `inventory_table.tsx` | 库存表格 |
| InventoryCard | `inventory_card.tsx` | 库存卡片 |
| ConsumeDialog | `consume_dialog.tsx` | 消耗记录对话框 |
| ReplenishDialog | `replenish_dialog.tsx` | 补货记录对话框 |
| TransferDialog | `transfer_dialog.tsx` | 库存转移对话框 |
| LowStockAlert | `low_stock_alert.tsx` | 低库存预警组件 |
| ExpiringAlert | `expiring_alert.tsx` | 即将过期预警组件 |

### 4.5 旅程管理组件

| 组件 | 文件 | 功能 |
|------|------|------|
| JourneyTimeline | `journey_timeline.tsx` | 旅程时间线 |
| JourneyCard | `journey_card.tsx` | 旅程卡片 |
| JourneyAddDialog | `journey_add_dialog.tsx` | 创建旅程对话框 |
| JourneyDetailSheet | `journey_detail_sheet.tsx` | 旅程详情侧边栏 |
| JourneyItemList | `journey_item_list.tsx` | 旅程物资清单 |
| PackingChecklist | `packing_checklist.tsx` | 打包清单（可勾选） |
| JourneySuggestions | `journey_suggestions.tsx` | 建议携带物资 |

### 4.6 统计与可视化组件

| 组件 | 文件 | 功能 |
|------|------|------|
| InventoryStats | `inventory_stats.tsx` | 库存统计仪表盘 |
| ConsumptionChart | `consumption_chart.tsx` | 消耗趋势图 |
| ResidenceDistribution | `residence_distribution.tsx` | 住所物资分布图 |
| CategoryPieChart | `category_pie_chart.tsx` | 类别分布饼图 |

---

## 5. 状态管理 (Zustand)

### 5.1 ResidenceStore

```typescript
interface ResidenceStore {
  // 状态
  residences: ResidenceData[]
  currentResidence: ResidenceData | null
  containers: ContainerData[]
  isLoading: boolean

  // 方法
  fetchResidences: () => Promise<void>
  setCurrentResidence: (id: number) => void
  fetchContainers: (residenceId: number) => Promise<void>
  createResidence: (data: ResidenceCreateProps) => Promise<void>
  updateResidence: (id: number, data: Partial<ResidenceData>) => Promise<void>
  deleteResidence: (id: number) => Promise<void>
  createContainer: (data: ContainerCreateProps) => Promise<void>
  updateContainer: (id: number, data: Partial<ContainerData>) => Promise<void>
  deleteContainer: (id: number) => Promise<void>
}
```

### 5.2 ItemsStore

```typescript
interface ItemsStore {
  // 状态
  items: ItemData[]
  categories: CategoryData[]
  isLoading: boolean
  filters: ItemFilters

  // 方法
  fetchItems: (params?: ItemQueryParams) => Promise<void>
  fetchCategories: () => Promise<void>
  createItem: (data: ItemCreateProps) => Promise<void>
  updateItem: (id: number, data: Partial<ItemData>) => Promise<void>
  deleteItem: (id: number) => Promise<void>
  getItemLocations: (id: number) => Promise<InventoryData[]>
  searchItems: (keyword: string) => Promise<ItemData[]>
  setFilters: (filters: Partial<ItemFilters>) => void
  getExpiringItems: (days: number) => Promise<ItemData[]>
  getPortableItems: () => Promise<ItemData[]>
}

interface ItemFilters {
  categoryId?: number
  residenceId?: number
  type?: number
  state?: number
  tags?: string[]
  keyword?: string
}
```

### 5.3 InventoryStore

```typescript
interface InventoryStore {
  // 状态
  inventory: InventoryData[]
  lowStockItems: InventoryData[]
  isLoading: boolean

  // 方法
  fetchInventory: (params?: InventoryQueryParams) => Promise<void>
  fetchLowStock: () => Promise<void>
  createInventory: (data: InventoryCreateProps) => Promise<void>
  updateInventory: (id: number, data: Partial<InventoryData>) => Promise<void>
  deleteInventory: (id: number) => Promise<void>
  recordConsumption: (id: number, quantity: number, reason?: string) => Promise<void>
  recordReplenishment: (id: number, data: ReplenishmentProps) => Promise<void>
  transferInventory: (data: TransferProps) => Promise<void>
  getInventoryStats: () => Promise<InventoryStats>
}
```

### 5.4 JourneyStore

```typescript
interface JourneyStore {
  // 状态
  journeys: JourneyData[]
  currentJourney: JourneyData | null
  isLoading: boolean

  // 方法
  fetchJourneys: (params?: JourneyQueryParams) => Promise<void>
  createJourney: (data: JourneyCreateProps) => Promise<void>
  updateJourney: (id: number, data: Partial<JourneyData>) => Promise<void>
  deleteJourney: (id: number) => Promise<void>
  startJourney: (id: number) => Promise<void>
  completeJourney: (id: number) => Promise<void>
  cancelJourney: (id: number) => Promise<void>
  addJourneyItem: (journeyId: number, item: JourneyItemProps) => Promise<void>
  removeJourneyItem: (journeyId: number, itemId: number) => Promise<void>
  packItem: (journeyId: number, itemId: number) => Promise<void>
  unpackItem: (journeyId: number, itemId: number) => Promise<void>
  getSuggestedItems: (fromId: number, toId: number) => Promise<ItemData[]>
}
```

---

## 6. 核心业务逻辑

### 6.1 库存管理

**消耗记录处理**：
```python
async def record_consumption(inventory_id: int, quantity: Decimal, reason: str = None):
    """记录消耗并更新库存"""
    inventory = await get_inventory(inventory_id)
    
    # 创建消耗记录
    consumption = Consumption(
        inventory_id=inventory_id,
        quantity=quantity,
        reason=reason,
        htime=datetime.now()
    )
    await save_consumption(consumption)
    
    # 更新库存
    inventory.quantity -= quantity
    await update_inventory(inventory)
    
    # 检查是否低于警戒值
    if inventory.quantity <= inventory.min_quantity:
        await create_low_stock_alert(inventory)
    
    return inventory
```

**补货预测**：
```python
async def predict_replenishment(item_id: int, residence_id: int) -> ReplenishmentPrediction:
    """基于历史消耗预测补货时间"""
    # 获取近30天消耗记录
    consumptions = await get_consumptions(
        item_id=item_id,
        residence_id=residence_id,
        days=30
    )
    
    if not consumptions:
        return None
    
    # 计算平均日消耗量
    total_consumed = sum(c.quantity for c in consumptions)
    avg_daily = total_consumed / 30
    
    # 获取当前库存
    inventory = await get_inventory(item_id, residence_id)
    current_quantity = inventory.quantity
    min_quantity = inventory.min_quantity
    
    # 预测何时达到警戒值
    if avg_daily > 0:
        days_until_low = (current_quantity - min_quantity) / avg_daily
        predicted_date = datetime.now() + timedelta(days=days_until_low)
    else:
        days_until_low = float('inf')
        predicted_date = None
    
    return ReplenishmentPrediction(
        item_id=item_id,
        current_quantity=current_quantity,
        avg_daily_consumption=avg_daily,
        days_until_low_stock=days_until_low,
        predicted_low_stock_date=predicted_date,
        recommended_replenish_quantity=avg_daily * 30  # 建议补充30天用量
    )
```

### 6.2 旅程物资管理

**开始旅程**：
```python
async def start_journey(journey_id: int):
    """开始旅程，将物资移至"随身携带"状态"""
    journey = await get_journey(journey_id)
    portable_residence = await get_portable_residence()
    
    for journey_item in journey.items:
        # 从来源减少库存
        await decrease_inventory(
            item_id=journey_item.item_id,
            residence_id=journey.from_residence_id,
            container_id=journey_item.from_container_id,
            quantity=journey_item.quantity
        )
        
        # 增加到随身携带
        await increase_inventory(
            item_id=journey_item.item_id,
            residence_id=portable_residence.id,
            quantity=journey_item.quantity
        )
        
        journey_item.status = JourneyItemStatus.PACKED
    
    journey.status = JourneyStatus.IN_TRANSIT
    await update_journey(journey)
```

**完成旅程**：
```python
async def complete_journey(journey_id: int):
    """完成旅程，将物资移至目的地"""
    journey = await get_journey(journey_id)
    portable_residence = await get_portable_residence()
    
    for journey_item in journey.items:
        # 从随身携带减少
        await decrease_inventory(
            item_id=journey_item.item_id,
            residence_id=portable_residence.id,
            quantity=journey_item.quantity
        )
        
        # 增加到目的地
        await increase_inventory(
            item_id=journey_item.item_id,
            residence_id=journey.to_residence_id,
            container_id=journey_item.to_container_id,
            quantity=journey_item.quantity
        )
        
        journey_item.status = JourneyItemStatus.TRANSFERRED
    
    journey.status = JourneyStatus.COMPLETED
    journey.arrive_time = datetime.now()
    await update_journey(journey)
```

**智能建议携带物资**：
```python
async def suggest_journey_items(from_residence_id: int, to_residence_id: int) -> List[SuggestedItem]:
    """基于目的地需求建议携带物资"""
    suggestions = []
    
    # 1. 获取目的地低库存物资
    low_stock = await get_low_stock_items(to_residence_id)
    for inv in low_stock:
        # 检查来源地是否有库存
        source_inv = await get_inventory(inv.item_id, from_residence_id)
        if source_inv and source_inv.quantity > 0:
            suggestions.append(SuggestedItem(
                item=inv.item,
                reason="目的地库存不足",
                suggested_quantity=min(
                    source_inv.quantity,
                    inv.max_quantity - inv.quantity
                )
            ))
    
    # 2. 必备随身物品（重要证件、常用电子设备）
    portable_essentials = await get_portable_essentials()
    for item in portable_essentials:
        if item.id not in [s.item.id for s in suggestions]:
            suggestions.append(SuggestedItem(
                item=item,
                reason="必备随身物品",
                suggested_quantity=1
            ))
    
    # 3. 基于历史旅程推荐
    past_journeys = await get_similar_journeys(from_residence_id, to_residence_id)
    frequently_carried = get_frequently_carried_items(past_journeys)
    for item, frequency in frequently_carried:
        if item.id not in [s.item.id for s in suggestions]:
            suggestions.append(SuggestedItem(
                item=item,
                reason=f"历史携带频率：{frequency}%",
                suggested_quantity=1
            ))
    
    return suggestions
```

### 6.3 过期提醒

```python
async def check_expiring_items(days_ahead: int = 30) -> List[ExpiringAlert]:
    """检查即将过期的物资"""
    alerts = []
    threshold_date = datetime.now().date() + timedelta(days=days_ahead)
    
    items = await get_items_with_expire_date()
    for item in items:
        if item.expire_date and item.expire_date <= threshold_date:
            days_remaining = (item.expire_date - datetime.now().date()).days
            
            # 获取该物资的所有库存位置
            inventories = await get_item_inventories(item.id)
            
            alerts.append(ExpiringAlert(
                item=item,
                days_remaining=days_remaining,
                locations=inventories,
                severity='urgent' if days_remaining <= 7 else 'warning'
            ))
    
    return sorted(alerts, key=lambda a: a.days_remaining)
```

---

## 7. 典型使用场景

### 7.1 日常消耗品管理

1. 在上海住所使用洗发水
2. 打开物资管理页面，找到该洗发水
3. 点击"记录消耗"，输入消耗量
4. 系统自动更新库存，当低于警戒值时显示预警
5. 查看补货预测，了解预计何时需要补充

### 7.2 周末杭州往返

1. 创建旅程：上海 → 杭州，选择出发时间
2. 系统推荐携带物资（基于历史和杭州住所需求）
3. 勾选要携带的物资，系统生成打包清单
4. 出发时标记"开始旅程"，物资状态变为随身携带
5. 到达杭州后标记"完成旅程"，物资自动转移到杭州住所
6. 返程时重复以上流程

### 7.3 补充上海住所物资

1. 查看上海住所低库存预警
2. 确认杭州住所有对应物资库存
3. 创建杭州→上海旅程
4. 添加需要补充的物资到旅程清单
5. 完成旅程后，上海住所库存自动增加

### 7.4 重要证件管理

1. 添加身份证为"唯一物品"，设置高重要性和高便携性
2. 默认位置设为"随身携带"
3. 查看合肥住所存放的毕业证、户口本原件
4. 为护照设置有效期，系统在到期前提醒更换

### 7.5 季节性物品管理

1. 冬季衣物存放在合肥住所
2. 标记为"存储中"状态
3. 换季时，创建旅程将部分衣物带到上海
4. 系统记录物品移动历史，方便追溯

---

## 8. 与其他模块的联动

### 8.1 与生活预算模块联动

**物资购买关联交易**：
- 补货时可选择创建关联的支出交易
- 自动归类到相应的预算标签（如"日用消耗"）
- 统计物资类别的月度/年度花费

```typescript
// 补货时创建交易
async function replenishWithTransaction(
  inventoryId: number,
  quantity: number,
  cost: string,
  accountId: number
) {
  // 1. 创建补货记录
  const replenishment = await recordReplenishment(inventoryId, {
    quantity,
    source: 'PURCHASE',
    cost
  });
  
  // 2. 创建关联交易
  const item = await getItemByInventoryId(inventoryId);
  const transaction = await createTransaction({
    from_acc_id: accountId,
    to_acc_id: -1,  // 外部支出
    value: cost,
    description: `购买: ${item.name}`,
    tags: mapCategoryToTags(item.category_id)
  });
  
  // 3. 关联补货记录和交易
  await linkReplenishmentTransaction(replenishment.id, transaction.id);
}
```

**物资成本分析**：
```typescript
interface ItemCostAnalysis {
  item_id: number
  item_name: string
  total_cost_month: string
  total_cost_year: string
  avg_unit_cost: string
  cost_trend: 'up' | 'down' | 'stable'
}
```

### 8.2 与项目管理模块联动

**项目物资需求**：
- 特定项目可关联所需物资
- 项目开始前检查物资准备情况
- 项目完成后记录物资消耗

**出差旅程与项目关联**：
- 旅程可关联项目任务
- 自动建议项目相关物资

### 8.3 与健康模块联动

**健康相关物资追踪**：
- 药品库存管理和过期提醒
- 保健品消耗记录
- 健康护理用品库存监控

---

## 9. 技术要点

### 9.1 架构模式

- **分层架构**：数据层 → 业务逻辑层 → 控制器层 → 路由层
- **DTO 模式**：区分创建/更新/读取的数据传输对象
- **树形结构**：使用邻接表模型管理容器层级和类别层级

### 9.2 数据完整性

- 外键约束确保引用完整性
- 库存变更使用事务保证原子性
- 旅程物资状态机确保流程正确性

### 9.3 查询优化

- 库存查询支持多维度筛选
- 物资搜索支持全文检索
- 历史记录分页查询

### 9.4 消耗预测算法

基于移动平均法预测消耗：
```python
def predict_consumption(consumptions: List[Consumption], window: int = 7) -> Decimal:
    """使用移动平均预测日消耗量"""
    if len(consumptions) < window:
        window = len(consumptions)
    
    recent = consumptions[-window:]
    total = sum(c.quantity for c in recent)
    days = (recent[-1].htime - recent[0].htime).days + 1
    
    return total / days if days > 0 else Decimal(0)
```

---

## 10. 数据库迁移

相关迁移文件（待创建）：

- `create_residence.sql` - 创建住所表
- `create_container.sql` - 创建容器表
- `create_item_category.sql` - 创建物资类别表
- `create_item.sql` - 创建物资表
- `create_inventory.sql` - 创建库存表
- `create_journey.sql` - 创建旅程表
- `create_journey_item.sql` - 创建旅程物资表
- `create_consumption.sql` - 创建消耗记录表
- `create_replenishment.sql` - 创建补货记录表
- `seed_categories.sql` - 初始化物资类别数据
- `seed_residences.sql` - 初始化住所数据

---

## 11. 实现优先级

### Phase 1: 基础物资管理

1. **住所管理** - 创建住所 CRUD
2. **物资类别** - 类别 CRUD 和预设数据
3. **物资管理** - 物资 CRUD 和搜索
4. **库存管理** - 库存 CRUD

### Phase 2: 库存追踪

1. **消耗记录** - 消耗 CRUD
2. **补货记录** - 补货 CRUD
3. **低库存预警** - 预警逻辑和展示
4. **过期提醒** - 过期检查和提醒

### Phase 3: 旅程管理

1. **旅程 CRUD** - 基础旅程管理
2. **旅程物资** - 物资清单管理
3. **旅程状态机** - 开始/完成/取消流程
4. **智能推荐** - 建议携带物资

### Phase 4: 高级功能

1. **消耗预测** - 基于历史数据预测
2. **容器管理** - 容器树形结构
3. **统计分析** - 库存统计和可视化
4. **模块联动** - 与预算/项目/健康联动

---

## 12. 待办事项

### 高优先级
- [ ] 设计并创建数据库表
- [ ] 实现住所/物资/库存基础 CRUD API
- [ ] 实现前端物资管理页面基础框架
- [ ] 实现库存消耗和补货功能

### 中优先级
- [ ] 实现旅程管理完整流程
- [ ] 实现低库存预警功能
- [ ] 实现物资过期提醒
- [ ] 实现物资搜索功能

### 低优先级
- [ ] 实现消耗预测算法
- [ ] 实现智能建议携带物资
- [ ] 实现与预算模块联动
- [ ] 实现统计分析功能
- [ ] 移动端适配优化
