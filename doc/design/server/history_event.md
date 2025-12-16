# History Events API 文档

## 概述

History Events API 提供了完整的历史事件管理功能，支持事件的增删改查、层级关系管理、关联事件检索和关键词搜索。

## 表结构

### history_events

| 字段名 | 类型 | 说明 | 必填 |
|--------|------|------|------|
| id | INTEGER | 主键ID | 自动生成 |
| receive_time | TIMESTAMP | 接收消息的时间，默认为创建时间 | 自动生成 |
| title | VARCHAR | 事件标题 | ✓ |
| description | TEXT | 事件描述 | ✓ |
| rar_tags | VARCHAR[] | 手动标注的标签 | ✗ |
| tags | VARCHAR[] | 机器处理后用于检索的标签 | ✗ |
| start_time | TIMESTAMP | 估计的开始时间 | ✗ |
| end_time | TIMESTAMP | 估计的结束时间 | ✗ |
| related_events | INTEGER[] | 相关事件的ID列表 | ✗ |
| parent_event | INTEGER | 父事件ID | ✗ |
| details | JSONB | 更多细节信息 | ✗ |

## API 端点

基础路径: `/api/history/event`

### 1. 创建事件

**POST** `/api/history/event/`

创建一个新的历史事件。最低要求只需提供 `title` 和 `description`。

**请求体示例：**
```json
{
  "title": "2025年关税战",
  "description": "中美贸易摩擦升级，双方互征关税"
}
```

**完整请求体示例：**
```json
{
  "title": "2025年10月11日 中方制裁稀土船舶，美方加征100%关税",
  "description": "详细描述事件经过...",
  "rar_tags": ["贸易战", "中美关系", "经济"],
  "tags": ["trade", "us-china", "economy"],
  "start_time": "2025-10-11T00:00:00",
  "end_time": "2025-10-11T23:59:59",
  "parent_event": 123,
  "related_events": [124, 125],
  "details": {
    "participants": ["中国", "美国"],
    "location": "全球",
    "impact": "全球贸易受影响",
    "comments": "这是一个重要的历史转折点"
  }
}
```

**响应示例：**
```json
{
  "id": 126,
  "receive_time": "2025-10-12T10:30:00",
  "title": "2025年10月11日 中方制裁稀土船舶，美方加征100%关税",
  "description": "详细描述事件经过...",
  "rar_tags": ["贸易战", "中美关系", "经济"],
  "tags": ["trade", "us-china", "economy"],
  "start_time": "2025-10-11T00:00:00",
  "end_time": "2025-10-11T23:59:59",
  "parent_event": 123,
  "related_events": [124, 125],
  "details": {
    "participants": ["中国", "美国"],
    "location": "全球",
    "impact": "全球贸易受影响",
    "comments": "这是一个重要的历史转折点"
  }
}
```

### 2. 获取事件列表

**GET** `/api/history/event`

获取历史事件列表，支持分页和过滤。

**查询参数：**
- `skip` (int, 默认: 0): 跳过的记录数
- `limit` (int, 默认: 10): 返回的最大记录数
- `parent_id` (int, 可选): 父事件ID，用于获取子事件
- `tags` (string, 可选): 标签过滤，多个标签用逗号分隔

**示例请求：**
```
GET /api/history/event?skip=0&limit=10
GET /api/history/event?parent_id=123
GET /api/history/event?tags=trade,economy
```

### 3. 获取单个事件

**GET** `/api/history/event/{event_id}`

根据ID获取单个历史事件的详细信息。

**示例请求：**
```
GET /api/history/event/126
```

### 4. 获取子事件

**GET** `/api/history/event/{event_id}/children`

获取指定事件的所有子事件（一级子事件）。

**示例请求：**
```
GET /api/history/event/123/children
```

这将返回所有 `parent_event` 为 123 的事件。

### 5. 获取相关事件

**GET** `/api/history/event/{event_id}/related`

获取与指定事件相关的所有事件。

**示例请求：**
```
GET /api/history/event/126/related
```

这将返回在事件 126 的 `related_events` 字段中列出的所有事件。

### 6. 搜索事件

**GET** `/api/history/event/search`

通过关键词搜索历史事件（在标题和描述中搜索）。

**查询参数：**
- `keyword` (string, 必填): 搜索关键词
- `skip` (int, 默认: 0): 跳过的记录数
- `limit` (int, 默认: 10): 返回的最大记录数

**示例请求：**
```
GET /api/history/event/search?keyword=关税&skip=0&limit=10
```

### 7. 更新事件

**PUT** `/api/history/event/{event_id}`

更新历史事件的信息。可以部分更新，只提供需要修改的字段。

**请求体示例：**
```json
{
  "title": "更新后的标题",
  "description": "更新后的描述",
  "tags": ["updated", "tag"]
}
```

### 8. 删除事件

**DELETE** `/api/history/event/{event_id}`

删除指定的历史事件。

**示例请求：**
```
DELETE /api/history/event/126
```

## 使用场景示例

### 场景1: 创建事件层级结构

```python
# 1. 创建顶级事件
response1 = requests.post('/api/history/event/', json={
    "title": "中美从合作转向对抗",
    "description": "21世纪初至今，中美关系的重大转变"
})
parent_id = response1.json()['id']

# 2. 创建子事件
response2 = requests.post('/api/history/event/', json={
    "title": "2016年贸易战",
    "description": "贸易战开始",
    "parent_event": parent_id
})

# 3. 创建更细粒度的子事件
response3 = requests.post('/api/history/event/', json={
    "title": "2025年关税战",
    "description": "关税战升级",
    "parent_event": parent_id
})
sub_parent_id = response3.json()['id']

# 4. 创建具体日期事件
requests.post('/api/history/event/', json={
    "title": "2025年10月11日 中方制裁稀土船舶，美方加征100%关税",
    "description": "具体事件描述",
    "parent_event": sub_parent_id,
    "start_time": "2025-10-11T00:00:00"
})
```

### 场景2: 建立事件关联

```python
# 更新事件，添加相关事件
requests.put('/api/history/event/123', json={
    "title": "原标题",
    "description": "原描述",
    "related_events": [124, 125, 126]  # 关联其他事件
})
```

### 场景3: 逐步补充信息

```python
# 初始创建（最小信息）
response = requests.post('/api/history/event/', json={
    "title": "某重要事件",
    "description": "基本描述"
})
event_id = response.json()['id']

# 后续补充标签
requests.put(f'/api/history/event/{event_id}', json={
    "title": "某重要事件",
    "description": "基本描述",
    "rar_tags": ["政治", "经济"]
})

# 再补充时间信息
requests.put(f'/api/history/event/{event_id}', json={
    "title": "某重要事件",
    "description": "基本描述",
    "rar_tags": ["政治", "经济"],
    "start_time": "2025-01-01T00:00:00"
})

# 最后补充详细信息
requests.put(f'/api/history/event/{event_id}', json={
    "title": "某重要事件",
    "description": "基本描述",
    "rar_tags": ["政治", "经济"],
    "start_time": "2025-01-01T00:00:00",
    "details": {
        "participants": ["张三", "李四"],
        "comments": "后续发现这个事件很重要"
    }
})
```

### 场景4: 查询事件树

```python
# 1. 获取顶级事件的所有直接子事件
children = requests.get(f'/api/history/event/{parent_id}/children').json()

# 2. 递归获取完整事件树
def get_event_tree(event_id):
    event = requests.get(f'/api/history/event/{event_id}').json()
    children = requests.get(f'/api/history/event/{event_id}/children').json()
    event['children'] = [get_event_tree(child['id']) for child in children]
    return event

tree = get_event_tree(parent_id)
```

## 数据库迁移

运行以下 SQL 文件创建表：

```bash
psql -U your_user -d your_database -f internal/migration/create_history_events.sql
```

或者启动服务器时会自动创建表（使用 SQLAlchemy 的 `create_all()`）。

## OpenAPI 文档

启动服务器后，可以访问 `/api_docs` 查看完整的 OpenAPI 文档和交互式 API 测试界面。

## 注意事项

1. **必填字段**：创建事件时只需提供 `title` 和 `description`
2. **时间格式**：使用 ISO 8601 格式，例如 `2025-10-11T10:30:00`
3. **数组字段**：`rar_tags`、`tags`、`related_events` 都是数组，即使只有一个元素也要用数组格式
4. **JSONB 字段**：`details` 可以存储任意 JSON 结构的数据
5. **父子关系**：删除父事件不会自动删除子事件，需要手动处理
6. **关联事件**：`related_events` 是单向关联，需要手动维护双向关系

## 错误处理

所有 API 都会返回标准的 HTTP 状态码：

- `200 OK`: 成功
- `404 Not Found`: 事件不存在
- `422 Unprocessable Entity`: 请求数据格式错误
- `500 Internal Server Error`: 服务器错误

错误响应示例：
```json
{
  "detail": "Event with ID 999 not found",
  "status_code": 404
}
```

