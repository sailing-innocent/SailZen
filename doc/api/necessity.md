# 物资管理 API

> **版本**: v1.0 | **更新**: 2026-03-01 | **状态**: 已完成

---

## 📋 功能概述

物资管理模块提供生活物资的库存管理、住所管理、行程管理等功能。

### 核心概念

| 概念 | 说明 |
|------|------|
| **住所 (Residence)** | 存放物品的地方，如家、办公室 |
| **容器 (Container)** | 住所内的储物容器，如箱子、抽屉 |
| **物品分类 (Category)** | 物品的分类体系 |
| **物品 (Item)** | 具体的物品定义 |
| **库存 (Inventory)** | 物品在特定位置的存量 |
| **行程 (Journey)** | 携带物品的行程/搬家计划 |

---

## 🏠 住所 API

### 获取住所列表

```http
GET /api/v1/necessity/residence
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| residence_type | int | 否 | 住所类型筛选 |

**响应:**
```json
[
  {
    "id": 1,
    "name": "家里",
    "description": "主要住所",
    "address": "地址",
    "residence_type": 1,
    "is_portable": false,
    "htime": 1700000000
  }
]
```

---

### 获取单个住所

```http
GET /api/v1/necessity/residence/{residence_id}
```

---

### 创建住所

```http
POST /api/v1/necessity/residence
```

**请求体:**
```json
{
  "name": "新家",
  "description": "描述",
  "address": "地址",
  "residence_type": 1,
  "is_portable": false
}
```

---

### 更新住所

```http
PUT /api/v1/necessity/residence/{residence_id}
```

---

### 删除住所

```http
DELETE /api/v1/necessity/residence/{residence_id}
```

---

### 获取便携住所

```http
GET /api/v1/necessity/residence/portable
```

获取当前携带的住所（如背包）。

---

### 获取住所库存

```http
GET /api/v1/necessity/residence/{residence_id}/inventory
```

---

### 获取住所低库存物品

```http
GET /api/v1/necessity/residence/{residence_id}/low-stock
```

---

## 📦 容器 API

### 获取容器列表

```http
GET /api/v1/necessity/container
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| residence_id | int | 否 | 按住所筛选 |

---

### 获取容器树

```http
GET /api/v1/necessity/container/tree/{residence_id}
```

获取住所的容器层级结构。

---

### 其他容器操作

同标准 CRUD：
- `GET /api/v1/necessity/container/{id}`
- `POST /api/v1/necessity/container`
- `PUT /api/v1/necessity/container/{id}`
- `DELETE /api/v1/necessity/container/{id}`

---

## 🏷️ 分类 API

### 获取分类列表

```http
GET /api/v1/necessity/category
```

---

### 获取分类树

```http
GET /api/v1/necessity/category/tree
```

---

### 初始化默认分类

```http
POST /api/v1/necessity/category/seed
```

创建预设的分类体系。

---

## 📋 物品 API

### 获取物品列表

```http
GET /api/v1/necessity/item
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数 |
| limit | int | 否 | 返回记录数 |
| category_id | int | 否 | 分类筛选 |
| item_type | int | 否 | 物品类型筛选 |
| state | int | 否 | 状态筛选 |
| tags | string | 否 | 标签筛选 |

---

### 分页获取物品

```http
GET /api/v1/necessity/item/paginated/
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码（默认 1） |
| page_size | int | 否 | 每页大小 |
| keyword | string | 否 | 关键词搜索 |
| sort_by | string | 否 | 排序字段 |
| sort_order | string | 否 | 排序方向 |

---

### 搜索物品

```http
GET /api/v1/necessity/item/search/?keyword=关键词&limit=20
```

---

### 获取即将过期物品

```http
GET /api/v1/necessity/item/expiring/?days=30
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| days | int | 否 | 多少天内过期（默认 30） |

---

### 获取便携物品

```http
GET /api/v1/necessity/item/portable/?min_portability=4
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| min_portability | int | 否 | 最小便携度（1-5，默认 4） |

---

### 获取物品位置

```http
GET /api/v1/necessity/item/{item_id}/locations
```

返回该物品在哪些位置有库存。

---

## 📊 库存 API

### 获取库存列表

```http
GET /api/v1/necessity/inventory
```

---

### 创建库存记录

```http
POST /api/v1/necessity/inventory
```

**请求体:**
```json
{
  "item_id": 1,
  "residence_id": 1,
  "container_id": 1,       // 可选
  "quantity": "10",        // 数量
  "unit": "个",            // 单位
  "min_stock": "2",        // 最低库存预警
  "expiry_date": 1700000000,  // 过期时间（可选）
  "notes": "备注"
}
```

---

### 消费库存

```http
POST /api/v1/necessity/inventory/{inventory_id}/consume
```

**请求体:**
```json
{
  "quantity": "2",         // 消费数量
  "notes": "消费备注"
}
```

---

### 补充库存

```http
POST /api/v1/necessity/inventory/{inventory_id}/replenish
```

**请求体:**
```json
{
  "quantity": "5",         // 补充数量
  "notes": "补充备注"
}
```

---

### 转移库存

```http
POST /api/v1/necessity/inventory/transfer
```

**请求体:**
```json
{
  "source_inventory_id": 1,
  "destination_residence_id": 2,
  "destination_container_id": 3,  // 可选
  "quantity": "5",
  "notes": "转移备注"
}
```

---

### 获取低库存物品

```http
GET /api/v1/necessity/inventory/low-stock/?residence_id=1
```

---

### 获取库存统计

```http
GET /api/v1/necessity/inventory/stats/?residence_id=1
```

---

## 🚗 行程 API

### 获取行程列表

```http
GET /api/v1/necessity/journey
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | int | 否 | 状态筛选 |
| from_residence_id | int | 否 | 出发地筛选 |
| to_residence_id | int | 否 | 目的地筛选 |

---

### 获取单个行程

```http
GET /api/v1/necessity/journey/{journey_id}
```

---

### 创建行程

```http
POST /api/v1/necessity/journey
```

**请求体:**
```json
{
  "name": "出差",
  "description": "出差行程",
  "from_residence_id": 1,
  "to_residence_id": 2,
  "planned_departure": 1700000000,
  "planned_return": 1700000000
}
```

---

### 更新行程

```http
PUT /api/v1/necessity/journey/{journey_id}
```

---

### 删除行程

```http
DELETE /api/v1/necessity/journey/{journey_id}
```

---

### 开始行程

```http
POST /api/v1/necessity/journey/{journey_id}/start
```

---

### 完成行程

```http
POST /api/v1/necessity/journey/{journey_id}/complete
```

---

### 取消行程

```http
POST /api/v1/necessity/journey/{journey_id}/cancel
```

---

### 添加行程物品

```http
POST /api/v1/necessity/journey/{journey_id}/items
```

**请求体:**
```json
{
  "item_id": 1,
  "quantity": "2",
  "is_packed": false
}
```

---

### 移除行程物品

```http
DELETE /api/v1/necessity/journey/{journey_id}/items/{item_id}
```

---

### 打包物品

```http
POST /api/v1/necessity/journey/{journey_id}/pack/{item_id}
```

标记物品已打包。

---

### 解包物品

```http
POST /api/v1/necessity/journey/{journey_id}/unpack/{item_id}
```

标记物品未打包。

---

## 🖥️ 前端 API 客户端

### 导入

```typescript
import {
  // 住所
  api_get_residences,
  api_get_residence,
  api_create_residence,
  api_update_residence,
  api_delete_residence,
  api_get_portable_residence,
  api_get_residence_inventory,
  api_get_residence_low_stock,
  
  // 容器
  api_get_containers,
  api_get_container_tree,
  
  // 分类
  api_get_categories,
  api_get_category_tree,
  api_seed_categories,
  
  // 物品
  api_get_items,
  api_get_items_paginated,
  api_search_items,
  api_get_expiring_items,
  api_get_portable_items,
  api_get_item_locations,
  
  // 库存
  api_get_inventories,
  api_create_inventory,
  api_consume_inventory,
  api_replenish_inventory,
  api_transfer_inventory,
  api_get_low_stock,
  api_get_inventory_stats,
  
  // 行程
  api_get_journeys,
  api_create_journey,
  api_start_journey,
  api_complete_journey,
  api_add_journey_item,
  api_pack_journey_item,
} from '@lib/api/necessity'
```

### 使用示例

```typescript
// 创建住所
const home = await api_create_residence({
  name: '家里',
  description: '主要住所',
  address: '某市某区',
  residence_type: 1,
  is_portable: false
})

// 初始化默认分类
await api_seed_categories()

// 创建物品
const item = await api_create_item({
  name: '洗发水',
  description: '日常用品',
  category_id: 1,
  item_type: 1,
  default_unit: '瓶',
  portability: 4  // 便携度 1-5
})

// 创建库存
const inventory = await api_create_inventory({
  item_id: item.id,
  residence_id: home.id,
  quantity: '3',
  unit: '瓶',
  min_stock: '1',
  expiry_date: Date.now() / 1000 + 365 * 24 * 3600  // 1年后过期
})

// 消费库存
await api_consume_inventory(inventory.id, {
  quantity: '1',
  notes: '使用一瓶'
})

// 补充库存
await api_replenish_inventory(inventory.id, {
  quantity: '2',
  notes: '购买补充'
})

// 获取即将过期物品
const expiring = await api_get_expiring_items(30)  // 30天内

// 获取低库存物品
const lowStock = await api_get_low_stock(home.id)

// 创建行程
const journey = await api_create_journey({
  name: '出差',
  from_residence_id: home.id,
  to_residence_id: 2,
  planned_departure: Date.now() / 1000 + 7 * 24 * 3600
})

// 添加行程物品
await api_add_journey_item(journey.id, {
  item_id: item.id,
  quantity: '1',
  is_packed: false
})

// 打包物品
await api_pack_journey_item(journey.id, item.id)

// 开始行程
await api_start_journey(journey.id)

// 完成行程
await api_complete_journey(journey.id)
```

---

*本文档由 AI Agent 维护，如有疑问请参考源代码或联系开发团队。*
