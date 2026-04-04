# OpenCode 异步任务 API 指南

## 概述

本 skill 描述如何正确使用 OpenCode Server 的异步 API 进行长时间运行的任务。

## 核心 API 端点

### 1. 异步发送消息
```
POST /session/:id/prompt_async
```
- **功能**: 发送消息但不等待响应（立即返回 204 No Content）
- **用途**: 启动长时间运行的任务，避免 HTTP 超时
- **注意**: 消息会被添加到会话中，AI 会开始处理

### 2. 轮询获取消息
```
GET /session/:id/message?limit=50
```
- **返回**: 消息列表 `{ info: Message, parts: Part[] }[]`
- **用途**: 轮询获取最新的消息和进度

### 3. SSE 事件流（推荐）
```
GET /event
```
- **返回**: Server-Sent Events 流
- **用途**: 实时接收消息更新、工具调用、完成事件
- **优势**: 比轮询更高效、实时

## 关键数据结构

### Message (助手消息)
```typescript
type AssistantMessage = {
  id: string
  sessionID: string
  role: "assistant"
  time: {
    created: number      // 消息创建时间
    completed?: number   // ⭐ 消息完成时间（关键字段！）
  }
  error?: ProviderAuthError | UnknownError | ...
  parentID: string
  modelID: string
  providerID: string
  mode: string
  path: { cwd: string, root: string }
  summary?: boolean
  cost: number
  tokens: { input, output, reasoning, cache }
  finish?: string       // 完成原因
}
```

**关键**: `time.completed` 字段存在时表示消息已完成！

### Part 类型

#### TextPart
```typescript
type TextPart = {
  id: string
  type: "text"
  text: string          // 实际文本内容
  time?: {
    start: number
    end?: number
  }
}
```

#### ToolPart（工具调用）
```typescript
type ToolPart = {
  id: string
  type: "tool"
  callID: string
  tool: string          // 工具名称
  state: ToolState      // 工具执行状态
}

type ToolState = 
  | { status: "pending", input, raw }
  | { status: "running", input, title?, metadata?, time }
  | { status: "completed", input, output, title, metadata, time }
  | { status: "error", input, error, metadata, time }
```

#### ReasoningPart（推理过程）
```typescript
type ReasoningPart = {
  id: string
  type: "reasoning"
  text: string
  time: { start, end? }
}
```

#### StepStartPart / StepFinishPart
```typescript
type StepFinishPart = {
  id: string
  type: "step-finish"
  reason: string
  snapshot?: string
  cost: number
  tokens: {...}
}
```

## 最佳实践

### 1. 判断任务完成
**正确方式**: 使用 `/session/status` 端点检查 `SessionStatus.type`
- `"idle"` → 任务完成 ✓
- `"busy"` → 处理中
- `"retry"` → 重试中

**错误方式**: 检查 `AssistantMessage.time.completed`
- 这个字段不是可靠的完成标志

### 2. 使用 /session/status 端点
```python
def check_session_status(session_id, port):
    response = httpx.get(f"http://localhost:{port}/session/status")
    statuses = response.json()  # { sessionID: SessionStatus }
    status = statuses.get(session_id, {})
    return status.get("type")  # "idle" | "busy" | "retry"
```

### 2. 提取最终内容
从所有 `TextPart` 中提取 `text` 字段并连接：
```python
content = "".join(part.text for part in parts if part.type == "text")
```

### 3. 跟踪工具调用
监听 `ToolPart` 的 `state.status` 变化：
- `pending` → `running` → `completed`/`error`
- 每个状态变化都可以给用户反馈

### 4. 使用 SSE 替代轮询
```javascript
const eventSource = new EventSource('http://localhost:4096/event')
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  if (data.type === 'message.updated') {
    // 处理消息更新
  }
  if (data.type === 'message.part.updated') {
    // 处理部分内容更新（实时打字效果）
  }
  if (data.type === 'session.idle') {
    // 会话进入空闲状态，任务完成
  }
}
```

## 常见错误

### ❌ 错误：仅检查消息 role 和类型
```python
# 错误！这样会在中间思考过程就误判为完成
if last_msg.role == "assistant" and last_part.type == "text":
    return True
```

### ✅ 正确：检查 completed 时间戳
```python
# 正确！只有 completed 字段存在才表示真正完成
if assistant_msg.time.get("completed"):
    return True
```

### ❌ 错误：只取最后一条 text
```python
# 错误！可能错过前面的内容
content = last_text_part.text
```

### ✅ 正确：连接所有 text parts
```python
# 正确！获取完整内容
content = "".join(p.text for p in parts if p.type == "text")
```

## 实现示例

### Python 异步任务管理器
```python
def poll_for_result(session_id, port, timeout=600):
    """轮询获取异步任务结果"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # ⭐ 关键：检查会话状态
        response = httpx.get(f"http://localhost:{port}/session/status")
        statuses = response.json()
        status = statuses.get(session_id, {}).get("type")
        
        if status == "idle":
            # 会话空闲，获取最终消息
            messages = get_messages(session_id, port)
            for msg in reversed(messages):
                if msg["info"]["role"] == "assistant":
                    parts = msg.get("parts", [])
                    content = "".join(
                        p["text"] for p in parts if p["type"] == "text"
                    )
                    return content
        
        time.sleep(3)  # 检查间隔
    
    raise TimeoutError("任务超时")
```

## 调试技巧

1. **启用详细日志**: 记录每个消息和 part 的类型
2. **查看原始响应**: 打印完整的 API 响应来理解数据结构
3. **使用时间戳**: 比较 `created` 和 `completed` 时间来估算执行时长
4. **监控工具调用**: 记录每个工具调用的状态和耗时

## 参考

- OpenCode Server 文档: https://opencode.ai/docs/server
- 类型定义: https://github.com/anomalyco/opencode/blob/dev/packages/sdk/js/src/gen/types.gen.ts
- OpenAPI 规范: http://localhost:4096/doc (本地运行时可访问)
