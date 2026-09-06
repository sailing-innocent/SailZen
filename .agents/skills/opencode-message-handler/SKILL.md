# OpenCode Message Handler Skill

## 概述

本 Skill 用于处理 OpenCode 的消息格式和日志记录。基于 OpenCode 源码 `message-v2.ts` 实现。

## 消息结构

```typescript
interface WithParts {
  info: MessageInfo
  parts: Part[]
}
```

### MessageInfo

- **id**: 消息唯一标识
- **role**: "user" | "assistant"
- **sessionID**: 所属 session
- **time**: 时间戳
- **agent**: 使用的 agent 名称
- **model**: { providerID, modelID }

Assistant 特有字段：
- **finish**: 结束原因 ("stop" | "tool-calls" | ...)
- **cost**: 成本（美元）
- **tokens**: { input, output, reasoning, cache }
- **error**: 错误信息（如果有）

## Part 类型

### 1. text
文本内容。
```typescript
{
  type: "text",
  text: string,
  synthetic?: boolean,  // 是否合成
  ignored?: boolean,    // 是否被忽略
  time?: { start, end }
}
```

### 2. reasoning
推理过程。
```typescript
{
  type: "reasoning",
  text: string,
  time: { start, end }
}
```

### 3. tool
工具调用。
```typescript
{
  type: "tool",
  callID: string,
  tool: string,
  state: ToolState,
  metadata?: Record<string, any>
}
```

**ToolState**:
- **pending**: { status: "pending", input, raw }
- **running**: { status: "running", input, title?, time: { start } }
- **completed**: { status: "completed", input, output, title, time: { start, end } }
- **error**: { status: "error", input, error, time: { start, end } }

### 4. step-start / step-finish
步骤标记。
```typescript
{
  type: "step-start",
  snapshot?: string  // 快照ID
}

{
  type: "step-finish",
  reason: string,     // "stop" | "tool-calls"
  cost: number,
  tokens: { input, output, reasoning, cache: { read, write } }
}
```

### 5. file
文件附件。
```typescript
{
  type: "file",
  mime: string,
  filename?: string,
  url: string,
  source?: FileSource
}
```

### 6. 其他类型
- **snapshot**: 代码快照
- **patch**: 代码补丁
- **agent**: Agent 信息
- **subtask**: 子任务
- **retry**: 重试信息
- **compaction**: 上下文压缩

## 常见问题

### Q: 为什么消息 parts 为空？
A: 可能原因：
1. 消息还在流式传输中（中间状态）
2. 消息是占位符或心跳消息
3. 消息被过滤了

### Q: 如何判断任务完成？
A: 检测到 `step-finish` part，且 `reason` 为 "stop"。

### Q: Tool 调用失败怎么看？
A: Tool part 的 `state.status` 为 "error"，查看 `state.error`。

## 相关文件

- `sail_bot/opencode_message_logger.py`: 消息日志记录器
- `sail_bot/async_task_manager.py`: 异步任务管理器
- `.opencode/opencode.json`: OpenCode 配置
