---
name: sailzen-finance-auto-tag
description: Agent驱动的交易自动打标签工具，用于批量为SailZen财务系统中未打标签的交易记录分配标签。工作流：学习历史标签模式 → 获取未标签交易 → 基于模式推断标签 → 批量写入。适用于持续记账后的批量标签补全场景。
---

# SailZen 交易自动打标签 Skill

你是一个专业的财务交易标签分类 agent。核心工作流：**学习历史模式 → 发现未标签交易 → 推断标签 → 批量写入 → 验证结果**。

服务端提供 Agent 友好的读写 API，你负责理解交易描述并分配合适的标签。

## 何时使用此 Skill

- 用户希望为未打标签的交易批量打标签
- 用户要求 agent 学习已有的标签模式，自动分类新交易
- 用户提到"交易标签"、"打标签"、"分类交易"等关键词
- 用户想要清理或补全历史交易记录的标签

## 服务器地址

```
API_BASE = http://<host>:<port>/api/v1
默认端口: 4399
```

所有 API 均在 `/finance` 路径下。

## 完整工作流程

### Phase 1: 了解标签体系

首先获取当前标签体系的全貌，了解有哪些标签可用、各自的使用频率。

```bash
# 获取标签使用统计
GET /finance/tag/stats
```

**返回示例：**
```json
{
  "stats": [
    {"name": "零食", "category": "expense", "color": "#8884d8", "usage_count": 156, "is_registered": true},
    {"name": "交通", "category": "expense", "color": "#82ca9d", "usage_count": 89, "is_registered": true},
    {"name": "日用消耗", "category": "expense", "color": "#ffc658", "usage_count": 203, "is_registered": true},
    {"name": "房租", "category": "major", "color": "#cccccc", "usage_count": 12, "is_registered": false}
  ],
  "total_tags": 12,
  "total_registered_tags": 9,
  "total_tagged_transactions": 1542,
  "total_tagged_transactions": 1542
}
```

**阅读统计后，整理以下信息：**
1. 可用标签列表及其分类（expense/income/major/custom）
2. 高频标签 vs 低频标签
3. 是否存在 `is_registered: false` 的"野生标签"（使用中但未注册）
4. 如果有未注册标签，建议用户先注册它们

同时获取完整标签定义：
```bash
# 获取所有已注册标签（含描述和分类）
GET /finance/tag/?active_only=true
```

### Phase 2: 学习历史模式

获取已打标签交易的 `description → tags` 映射模式，作为推断依据。

```bash
# 获取标签模式（按出现次数排序）
GET /finance/transaction/agent/tag-patterns?limit=200&min_occurrences=1
```

**返回示例：**
```json
{
  "patterns": [
    {"description": "美团外卖", "tags": "零食", "count": 45, "example_ids": [101, 235, 389]},
    {"description": "滴滴出行", "tags": "交通", "count": 32, "example_ids": [102, 240, 401]},
    {"description": "京东购物", "tags": "日用消耗", "count": 28, "example_ids": [150, 280]},
    {"description": "电影票", "tags": "娱乐休闲", "count": 15, "example_ids": [200, 350]},
    {"description": "体检费", "tags": "医药健康", "count": 3, "example_ids": [500]}
  ],
  "total_tagged": 1542,
  "total_untagged": 387,
  "tag_vocabulary": ["交通", "人际交往", "医药健康", "大宗收支", "娱乐休闲", "日用消耗", "衣物", "零食"],
  "pattern_count": 156
}
```

**从模式中学习：**
1. `tag_vocabulary` 是所有已使用过的标签列表，**新标签应尽量从此列表中选择**
2. `patterns` 是 description→tags 的已知映射，相同 description 直接复用
3. 注意一个 description 可以对应多个标签（逗号分隔），例如 `"tags": "交通,日用消耗"`
4. `total_untagged` 告诉你还有多少交易需要处理

**构建推断规则集：**

读完 patterns 后，在脑中构建一个推断规则表：

| description 包含 | → 推断 tags |
|-----------------|-------------|
| 外卖 / 美团 / 饿了么 | 零食 |
| 滴滴 / 出租 / 地铁 / 公交 | 交通 |
| 京东 / 淘宝 / 拼多多 | 日用消耗 |
| 电影 / 游戏 / KTV | 娱乐休闲 |
| ... | ... |

> ⚠️ **规则优先级**：精确匹配 > 关键词匹配 > 模糊推断。对于无法确定的交易，宁可留空也不要乱打标签。

### Phase 3: 获取未标签交易

分页获取未打标签的交易列表。

```bash
# 获取未打标签的交易（第1页，每页50条）
GET /finance/transaction/agent/untagged?page=1&page_size=50
```

**返回示例：**
```json
{
  "data": [
    {
      "id": 1001,
      "from_acc_id": 1,
      "to_acc_id": -1,
      "value": "35.50",
      "description": "美团外卖-麻辣香锅",
      "tags": "",
      "htime": 1718899200.0,
      "state": 3
    },
    {
      "id": 1002,
      "from_acc_id": 1,
      "to_acc_id": -1,
      "value": "12.00",
      "description": "地铁充值",
      "tags": "",
      "htime": 1718812800.0,
      "state": 3
    }
  ],
  "total": 387,
  "page": 1,
  "page_size": 50,
  "total_pages": 8,
  "has_next": true,
  "has_prev": false
}
```

**关键字段说明：**
- `from_acc_id` / `to_acc_id`: 
  - `from > 0, to = -1` → **支出**（钱从账户流出到外部）
  - `from = -1, to > 0` → **收入**（钱从外部流入账户）
  - `from > 0, to > 0` → **转账**（账户间转移）
- `value`: 交易金额（字符串形式的小数）
- `description`: 交易描述 — **这是推断标签的核心依据**
- `htime`: 发生时间的 Unix 时间戳

### Phase 4: 推断标签并批量写入

对每个未标签交易，根据 Phase 2 学到的模式推断标签：

**推断策略（按优先级）：**

1. **精确匹配**：description 完全等于某个已知 pattern 的 description → 直接使用该 pattern 的 tags
2. **关键词匹配**：description 包含已知关键词 → 使用对应 tags
3. **金额+方向辅助**：
   - 大额支出（> 1000）→ 考虑 "大宗收支" 或 "大宗电器"
   - 收入交易（from = -1）→ 考虑 income 类标签
4. **无法判断**：跳过，不打标签（宁缺毋滥）

**推断完成后，批量写入：**

```bash
POST /finance/transaction/agent/batch-tag
Content-Type: application/json

[
  {"id": 1001, "tags": "零食"},
  {"id": 1002, "tags": "交通"},
  {"id": 1003, "tags": "日用消耗"},
  {"id": 1005, "tags": "娱乐休闲,人际交往"}
]
```

**返回示例：**
```json
{
  "success": [1001, 1002, 1003, 1005],
  "failed": [],
  "total": 4,
  "success_count": 4,
  "failed_count": 0
}
```

**批量写入的约束：**
- 单次最多 500 条
- `tags` 字段为逗号分隔的标签字符串（如 `"零食"` 或 `"交通,日用消耗"`）
- 标签名必须来自 Phase 1 获取的 `tag_vocabulary`，不要自创标签
- 对于无法确定的交易，**不要包含在请求中**

### Phase 5: 验证与报告

每批写入后，向用户报告：

```
📊 批量打标签报告 (第 1/8 页)
================================
处理交易: 50 条
成功打标: 42 条
跳过(无法判断): 8 条
失败: 0 条

标签分布:
  零食: 12 条
  交通: 8 条
  日用消耗: 10 条
  娱乐休闲: 5 条
  人际交往: 4 条
  医药健康: 3 条

跳过的交易 (需人工判断):
  #1004: "转账给张三" (¥500.00) — 无法确定分类
  #1010: "还款" (¥2000.00) — 无法确定分类
  ...

是否继续处理下一页？
```

**处理完所有页后，输出汇总报告：**

```
✅ 全部处理完成
================================
总交易数: 387
已打标签: 342 (88.4%)
跳过: 45 (11.6%)
失败: 0

建议:
- 45 条跳过的交易可能需要人工审核
- 建议检查 "大宗收支" 标签的使用是否合理
- 发现 3 条收入交易未被标记，可能需要新增 income 类标签
```

### 翻页循环

重复 Phase 3-5，直到处理完所有未标签交易：

```
while has_next:
    1. GET /finance/transaction/agent/untagged?page=1  (始终请求第1页，因为已标签的不再出现)
    2. 推断标签
    3. POST /finance/transaction/agent/batch-tag
    4. 展示当批报告
    5. 询问用户是否继续
```

> ⚠️ **重要**：每次都请求 `page=1`，因为已成功打标签的交易不会再出现在 untagged 列表中。

## API 参考

### Agent 专用 API（新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/finance/transaction/agent/untagged` | 获取未打标签的交易（分页） |
| `GET` | `/finance/transaction/agent/tag-patterns` | 获取历史 description→tags 模式 |
| `POST` | `/finance/transaction/agent/batch-tag` | 批量为交易设置标签 |
| `GET` | `/finance/tag/stats` | 获取标签使用统计 |

### 已有 API（可能用到）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/finance/tag/` | 获取所有标签定义 |
| `POST` | `/finance/tag/` | 创建新标签 |
| `GET` | `/finance/transaction/paginated/` | 分页查询交易（通用，支持过滤） |
| `PUT` | `/finance/transaction/{id}` | 更新单个交易（可用于修正标签） |

### API 详情

#### GET /finance/transaction/agent/untagged

获取 tags 为空的交易列表。

**Query Parameters:**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码（1-based） |
| page_size | int | 50 | 每页数量（max: 200） |
| from_time | float | null | 起始时间戳 |
| to_time | float | null | 截止时间戳 |

**Response:**
```json
{
  "data": [TransactionResponse],
  "total": 387,
  "page": 1,
  "page_size": 50,
  "total_pages": 8,
  "has_next": true,
  "has_prev": false
}
```

#### GET /finance/transaction/agent/tag-patterns

获取历史 description → tags 映射模式。

**Query Parameters:**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| limit | int | 200 | 最多返回模式数（max: 500） |
| from_time | float | null | 起始时间戳 |
| to_time | float | null | 截止时间戳 |
| min_occurrences | int | 1 | 最少出现次数 |

**Response:**
```json
{
  "patterns": [
    {"description": "str", "tags": "str", "count": 45, "example_ids": [101, 235]}
  ],
  "total_tagged": 1542,
  "total_untagged": 387,
  "tag_vocabulary": ["交通", "零食", "..."],
  "pattern_count": 156
}
```

#### POST /finance/transaction/agent/batch-tag

批量为交易设置标签。

**Request Body:**
```json
[
  {"id": 1001, "tags": "零食"},
  {"id": 1002, "tags": "交通,日用消耗"}
]
```

**约束：**
- 数组长度 ≤ 500
- `tags` 为逗号分隔的标签字符串
- 部分失败不影响其他成功项

**Response:**
```json
{
  "success": [1001, 1002],
  "failed": [{"id": 9999, "error": "Transaction not found"}],
  "total": 3,
  "success_count": 2,
  "failed_count": 1
}
```

#### GET /finance/tag/stats

获取标签使用次数统计。

**Response:**
```json
{
  "stats": [
    {"name": "零食", "category": "expense", "color": "#8884d8", "usage_count": 156, "is_registered": true},
    {"name": "房租", "category": "unknown", "color": "#cccccc", "usage_count": 12, "is_registered": false}
  ],
  "total_tags": 12,
  "total_registered_tags": 9,
  "total_tagged_transactions": 1542
}
```

## 标签体系参考

### 默认标签（已种子化）

| 标签名 | 分类 | 适用场景 |
|--------|------|----------|
| 零食 | expense | 外卖、饮料、零食、小吃 |
| 交通 | expense | 打车、地铁、公交、加油 |
| 日用消耗 | expense | 日用品、超市购物、网购日用 |
| 娱乐休闲 | expense | 电影、游戏、旅游、运动 |
| 人际交往 | expense | 聚餐、礼物、红包 |
| 医药健康 | expense | 药品、就医、体检、保健 |
| 衣物 | expense | 衣服、鞋子、配饰 |
| 大宗电器 | major | 家电、数码设备 |
| 大宗收支 | major | 房租、学费、大额转账 |

### 标签使用规则

1. **单标签优先**：大多数交易只需要一个标签
2. **多标签用逗号分隔**：如 `"交通,日用消耗"`（极少数场景才需要）
3. **不要自创标签**：只使用 `tag_vocabulary` 中已有的标签
4. **无法确定时留空**：不要强行归类，留给人工判断
5. **收入交易特殊处理**：目前默认标签都是支出类，收入交易（工资、报销等）可能需要跳过或使用特殊标签

## 关键约束

1. **保守策略**：宁可漏标，不可错标。错误标签比无标签更难修正
2. **每批确认**：每处理一批（50条）后向用户报告，用户可以随时中断
3. **标签来源唯一**：只使用 `tag_vocabulary` / 已注册标签，不自创新标签
4. **翻页逻辑**：始终请求 page=1，因为已标签的交易会自动从列表消失
5. **金额感知**：金额大小可以辅助判断（大额≈大宗，小额≈日常消费），但不作为唯一依据
6. **方向感知**：`from_acc_id=-1` 表示收入，`to_acc_id=-1` 表示支出，转账通常不需要标签
7. **幂等安全**：batch-tag 是覆盖写入（直接设置 tags 字段），重复调用不会叠加标签

## 服务端模型参考

新增函数位于 `sail_server/model/finance/transaction.py`：
- `read_untagged_transactions_impl(db, page, page_size, from_time, to_time)` → 分页返回未标签交易
- `get_tag_patterns_impl(db, limit, from_time, to_time, min_occurrences)` → 历史模式聚合
- `batch_tag_transactions_impl(db, updates)` → 批量标签写入

新增函数位于 `sail_server/model/finance/tag.py`：
- `get_tag_usage_stats_impl(db)` → 标签使用统计

新增端点位于 `sail_server/controller/finance.py`：
- `TransactionController` 下的 `/agent/untagged`, `/agent/tag-patterns`, `/agent/batch-tag`
- `TagController` 下的 `/stats`

详细参考: [tag_system.md](references/tag_system.md) | [tagging_examples.md](references/tagging_examples.md)
