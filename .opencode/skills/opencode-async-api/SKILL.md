# OpenCode 异步任务 API 指南 (SSE 版本)

## 概述

本 skill 描述如何正确使用 OpenCode Server 的异步 API 和 SSE 事件流进行长时间运行的任务。

**重要**: 本文档适用于 **SSE (Server-Sent Events)** 模式，这是 OpenCode 推荐的实时通信方式。

## 核心 API 端点

### 1. 异步发送消息
```
POST /session/:id/prompt_async
```
- **功能**: 发送消息但不等待响应（立即返回 204 No Content）
- **用途**: 启动长时间运行的任务，避免 HTTP 超时
- **注意**: 消息会被添加到会话中，AI 会开始处理

### 2. SSE 事件流（推荐）
```
GET /event
```
- **返回**: Server-Sent Events 流（全局事件流，包含所有会话的事件）
- **用途**: 实时接收消息更新、工具调用、完成事件
- **优势**: 比轮询更高效、实时，能立即检测到任务完成

### 3. 会话状态查询（备用）
```
GET /session/status
```
- **返回**: `{ sessionID: SessionStatus }`
- **用途**: 轮询获取会话状态（当 SSE 不可用时作为 fallback）

## 关键数据结构

### SessionStatus（会话状态）
```typescript
type SessionStatus =
  | { type: "idle" }           // ⭐ 会话空闲 = 任务完成
  | { type: "busy" }           // 处理中
  | { type: "retry", attempt, message, next }  // 重试中
```

**关键**: `status.type === "idle"` 表示会话空闲，任务已完成！

### SSE 事件类型

#### 1. session.idle（⭐ 任务完成）
```typescript
{
  type: "session.idle"
  properties: {
    sessionID: string  // 哪个会话进入了空闲状态
  }
}
```
**这是任务完成的最可靠信号！**

#### 2. session.status（状态变化）
```typescript
{
  type: "session.status"
  properties: {
    sessionID: string
    status: SessionStatus  // { type: "idle" | "busy" | "retry" }
  }
}
```
当 `status.type` 变为 `"idle"` 时，表示任务完成。

#### 3. message.part.updated（内容更新）
```typescript
{
  type: "message.part.updated"
  properties: {
    part: Part
    delta?: string  // 增量文本（如果有）
  }
}
```
Part 类型包括:
- `TextPart`: `{ type: "text", text: string }`
- `ToolPart`: `{ type: "tool", tool: string, state: ToolState }`
- `ReasoningPart`: `{ type: "reasoning", text: string }`
- `StepStartPart`: `{ type: "step-start" }`
- `StepFinishPart`: `{ type: "step-finish", reason: string }`

#### 4. message.updated（消息更新）
```typescript
{
  type: "message.updated"
  properties: {
    info: AssistantMessage
  }
}
```

### AssistantMessage（助手消息）
```typescript
type AssistantMessage = {
  id: string
  sessionID: string
  role: "assistant"
  time: {
    created: number
    completed?: number   // ⚠️ 不要依赖这个字段！
  }
  finish?: string        // 完成原因（如 "stop", "length"）
  cost: number
  tokens: {...}
  ...
}
```

**⚠️ 警告**: 不要依赖 `time.completed` 字段来判断任务完成！
- 这个字段不是可靠的完成标志
- 应该使用 `session.idle` 事件或 `session.status` 的 `type: "idle"`

### StepFinishPart（步骤完成）
```typescript
type StepFinishPart = {
  type: "step-finish"
  reason: string      // 如 "stop", "end_turn", "length"
  cost: number
  tokens: {...}
}
```

**注意**: `step-finish` 表示一个步骤完成，但不一定是整个任务完成！
- 一个任务可能包含多个步骤
- 应该以 `session.idle` 作为最终完成信号

## ✅ 正确的完成检测（SSE 模式）

### 方法 1: 监听 session.idle 事件（⭐ 推荐）
```python
async def wait_for_completion(session_id, event_stream):
    """通过 SSE 事件流等待任务完成"""
    async for event in event_stream:
        data = json.loads(event.data)
        
        # 只处理目标会话的事件
        if data.get("properties", {}).get("sessionID") != session_id:
            continue
        
        event_type = data.get("type")
        
        # ⭐ 关键: session.idle 表示任务完成
        if event_type == "session.idle":
            print(f"任务完成: {session_id}")
            return True
        
        # 备选: session.status 变为 idle
        if event_type == "session.status":
            status = data.get("properties", {}).get("status", {})
            if status.get("type") == "idle":
                print(f"任务完成: {session_id}")
                return True
    
    return False
```

### 方法 2: 累积内容 + 空闲检测
```python
async def stream_and_collect(session_id, event_stream):
    """流式接收内容并检测完成"""
    accumulated_text = []
    
    async for event in event_stream:
        data = json.loads(event.data)
        
        # 过滤非目标会话的事件
        props = data.get("properties", {})
        if props.get("sessionID") != session_id:
            continue
        
        event_type = data.get("type")
        
        # 累积文本内容
        if event_type == "message.part.updated":
            part = props.get("part", {})
            if part.get("type") == "text":
                delta = props.get("delta", "")
                accumulated_text.append(delta)
        
        # ⭐ 检测完成
        if event_type == "session.idle":
            return "".join(accumulated_text)
        
        if event_type == "session.status":
            status = props.get("status", {})
            if status.get("type") == "idle":
                return "".join(accumulated_text)
    
    return "".join(accumulated_text)
```

### 方法 3: 备选轮询（SSE 不可用时）
```python
async def poll_for_idle(session_id, port, timeout=600):
    """当 SSE 不可用时，轮询检查会话状态"""
    start = time.time()
    
    while time.time() - start < timeout:
        # 查询 /session/status
        response = httpx.get(f"http://localhost:{port}/session/status")
        statuses = response.json()
        
        status = statuses.get(session_id, {}).get("type")
        
        if status == "idle":
            # 会话空闲，获取最终消息
            messages = httpx.get(
                f"http://localhost:{port}/session/{session_id}/message",
                params={"limit": 10}
            ).json()
            
            # 找到最新的助手消息
            for msg in reversed(messages):
                if msg["info"]["role"] == "assistant":
                    parts = msg.get("parts", [])
                    content = "".join(
                        p["text"] for p in parts if p["type"] == "text"
                    )
                    return content
        
        await asyncio.sleep(2)  # 轮询间隔
    
    raise TimeoutError("任务超时")
```

## ❌ 常见的错误

### ❌ 错误 1: 依赖 message.time.completed
```python
# 错误！这个字段不可靠
if message["time"].get("completed"):
    return True
```

### ❌ 错误 2: 仅检查 step-finish
```python
# 错误！step-finish 只表示一个步骤完成，不是整个任务
if part["type"] == "step-finish":
    return True
```

### ❌ 错误 3: 只看 message.part.updated 的 text
```python
# 错误！这样会在中间过程就误判为完成
if part["type"] == "text" and part.get("text"):
    return part["text"]  # 可能只是部分内容
```

### ❌ 错误 4: 忽略 sessionID 过滤
```python
# 错误！全局 /event 流包含所有会话的事件
async for event in event_stream:
    data = json.loads(event.data)
    # 没有检查 sessionID，可能处理错误会话的事件！
    if data["type"] == "session.idle":
        return True  # 可能是其他会话的空闲事件
```

## 📝 完整实现示例

```python
import asyncio
import httpx
import json

class OpenCodeTaskManager:
    def __init__(self, port=4096):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
    
    async def submit_task(self, session_id: str, text: str) -> bool:
        """提交异步任务"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/session/{session_id}/prompt_async",
                json={"parts": [{"type": "text", "text": text}]}
            )
            return response.status_code == 204
    
    async def stream_events(self, session_id: str, timeout=600):
        """流式接收事件并检测完成"""
        accumulated = []
        start_time = asyncio.get_event_loop().time()
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET", 
                f"{self.base_url}/event",
                timeout=httpx.Timeout(timeout, read=timeout)
            ) as response:
                async for line in response.aiter_lines():
                    # 解析 SSE 事件
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])  # 去掉 "data: " 前缀
                        except json.JSONDecodeError:
                            continue
                        
                        # 只处理目标会话的事件
                        props = data.get("properties", {})
                        if props.get("sessionID") != session_id:
                            continue
                        
                        event_type = data.get("type")
                        
                        # 累积文本
                        if event_type == "message.part.updated":
                            part = props.get("part", {})
                            if part.get("type") == "text":
                                delta = props.get("delta", "")
                                accumulated.append(delta)
                                yield {"type": "delta", "content": delta}
                            elif part.get("type") == "tool":
                                yield {"type": "tool", "tool": part.get("tool")}
                        
                        # ⭐ 检测完成
                        if event_type == "session.idle":
                            yield {"type": "complete", "content": "".join(accumulated)}
                            return
                        
                        if event_type == "session.status":
                            status = props.get("status", {})
                            if status.get("type") == "idle":
                                yield {"type": "complete", "content": "".join(accumulated)}
                                return
                    
                    # 检查超时
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        raise TimeoutError("任务执行超时")
    
    async def run_task(self, session_id: str, text: str, timeout=600) -> str:
        """运行任务并返回结果"""
        # 1. 提交任务
        ok = await self.submit_task(session_id, text)
        if not ok:
            raise RuntimeError("提交任务失败")
        
        # 2. 流式接收结果
        content_parts = []
        async for event in self.stream_events(session_id, timeout):
            if event["type"] == "delta":
                content_parts.append(event["content"])
            elif event["type"] == "complete":
                return event["content"]
        
        # 如果流结束但没有收到 complete，尝试获取最终结果
        return "".join(content_parts)

# 使用示例
async def main():
    manager = OpenCodeTaskManager(port=4096)
    
    # 先创建会话
    async with httpx.AsyncClient() as client:
        response = await client.post("http://127.0.0.1:4096/session")
        session_id = response.json()["id"]
    
    # 运行任务
    result = await manager.run_task(
        session_id,
        "帮我查看当前目录的文件"
    )
    print(f"结果: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 🔍 调试技巧

1. **启用详细日志**: 记录每个 SSE 事件的类型和 sessionID
2. **检查 sessionID**: 确保只处理目标会话的事件
3. **打印原始事件**: 在开发时打印完整的 SSE 事件数据
4. **监控状态转换**: 记录从 `busy` → `idle` 的状态变化

```python
# 调试日志示例
async def debug_stream(event_stream):
    async for event in event_stream:
        data = json.loads(event.data)
        event_type = data.get("type", "unknown")
        props = data.get("properties", {})
        session_id = props.get("sessionID", "N/A")
        
        print(f"[{event_type}] session={session_id[:8]}... props={list(props.keys())}")
```

## 🎯 总结

| 检测方式 | 可靠性 | 推荐度 | 说明 |
|---------|-------|-------|------|
| `session.idle` 事件 | ⭐⭐⭐⭐⭐ | ✅ 首选 | 最可靠的完成信号 |
| `session.status` → `type: "idle"` | ⭐⭐⭐⭐⭐ | ✅ 备选 | 同样可靠 |
| `message.time.completed` | ⭐⭐ | ❌ 不推荐 | 不可靠 |
| `step-finish` part | ⭐⭐⭐ | ⚠️ 仅参考 | 步骤完成≠任务完成 |

**核心原则**:
1. 使用 SSE 事件流 `/event` 实时接收更新
2. 监听 `session.idle` 作为完成信号
3. 过滤事件时严格检查 `sessionID`
4. 累积 `TextPart` 的内容获取完整输出
