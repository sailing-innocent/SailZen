# 物资管理设计

## 核心模型

| 模型 | 说明 | 关键字段 |
|------|------|----------|
| Residence | 住所 | name, code, type |
| Item | 物资 | name, category_id, importance, portability |
| Inventory | 库存 | item_id, residence_id, quantity, min_quantity |
| Journey | 旅程 | from_residence_id, to_residence_id |

## 住所类型

| 类型 | 值 | 说明 |
|------|-----|------|
| STABLE_STORAGE | 0 | 稳定仓库 |
| TEMPORARY_STORAGE | 1 | 临时存放 |
| CURRENT_LIVING | 2 | 当前居住 |
| PORTABLE | 3 | 随身携带 |

## API 概览

```
GET  /api/v1/necessity/residence/          # 住所列表
GET  /api/v1/necessity/item/               # 物资列表
GET  /api/v1/necessity/inventory/          # 库存列表
POST /api/v1/necessity/inventory/{id}/consume   # 消耗库存
POST /api/v1/necessity/inventory/{id}/replenish # 补货
POST /api/v1/necessity/journey/            # 创建旅程
```
