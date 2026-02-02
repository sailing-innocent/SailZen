# 异步任务管理器验收测试指南

## 概述

本文档描述如何验收测试 LLM 辅助小说分析工具的异步任务管理功能。该功能实现了完整的前后端任务流程：任务发布 → 执行 → 查看状态 → 审核 → 合并结果。

**注意**：当前版本使用 **Mock 模式**（模拟 LLM）进行演示，无需配置真实的 LLM API Key。

## 环境准备

### 1. 启动后端服务

```bash
# 在项目根目录
cd sail_server
uv run python ../server.py
```

后端默认运行在 `http://localhost:8000`

### 2. 启动前端服务

```bash
# 在另一个终端
cd packages/site
pnpm dev
```

前端默认运行在 `http://localhost:5173`

### 3. 确保数据库有测试数据

需要预先导入至少一部小说作品。可以使用文本导入功能：

```bash
uv run main.py <path-to-text-file>
```

---

## 验收测试流程

### 测试 1：创建分析任务

**目标**：验证可以成功创建分析任务

**步骤**：
1. 打开浏览器访问 `http://localhost:5173`
2. 导航到 **作品分析** 页面
3. 在顶部选择一个作品和版本
4. 确认默认显示 **任务管理** Tab
5. 点击 **"创建任务"** 按钮
6. 在弹出的对话框中选择任务类型（如 "大纲提取"）
7. 点击 **"创建任务"**

**预期结果**：
- [x] 对话框关闭
- [x] 任务列表中出现新创建的任务
- [x] 任务状态显示为 **"等待执行"**
- [x] 自动切换到 **"执行任务"** Tab

---

### 测试 2：生成执行计划

**目标**：验证可以生成任务执行计划（预览）

**步骤**：
1. 在任务列表中找到一个 **"等待执行"** 状态的任务
2. 点击 **"执行任务"** 按钮

**预期结果**：
- [x] 弹出执行确认对话框
- [x] 显示执行计划信息：
  - 分块数量
  - 预估 Token 数量
  - 预估成本（美元）
  - 使用的模板 ID
- [x] 可以选择 LLM 提供商（默认为 Mock）

---

### 测试 3：使用 Mock 模式执行任务

**目标**：验证 Mock 模式可以模拟 LLM 分析并生成结果

**步骤**：
1. 在执行确认对话框中，确认 LLM 选择为 **"Mock (演示模式)"**
2. 点击 **"确认并执行"**
3. 在执行任务 Tab 中，点击 **"开始执行"**
4. 观察进度条变化

**预期结果**：
- [x] 显示执行进度
- [x] 进度条逐步更新
- [x] 显示当前处理的分块信息
- [x] Mock 模式下每个分块处理需要 1-3 秒
- [x] 任务完成后显示 **"任务执行完成！"**
- [x] 出现 **"查看结果"** 按钮

---

### 测试 4：查看分析结果

**目标**：验证可以查看 LLM 生成的分析结果

**步骤**：
1. 任务完成后，点击 **"查看结果"** 按钮
2. 或者返回任务列表，找到已完成的任务，点击 **"查看结果"**

**预期结果**：
- [x] 切换到 **"审核结果"** Tab
- [x] 显示结果列表
- [x] 每个结果显示：
  - 结果类型（如 outline_node, character 等）
  - 审核状态（默认为 "待审核"）
  - 置信度百分比
  - 详细的 JSON 数据
- [x] Mock 模式生成的数据包含模拟的情节点、人物或设定

---

### 测试 5：审核结果

**目标**：验证可以批准或拒绝分析结果

**步骤**：
1. 在结果列表中找到一条 **"待审核"** 的结果
2. 点击 **"批准"** 按钮
3. 对另一条结果点击 **"拒绝"** 按钮

**预期结果**：
- [x] 批准的结果状态变为 **"已批准"**（绿色标签）
- [x] 拒绝的结果状态变为 **"已拒绝"**（红色标签）
- [x] 按钮消失，状态锁定

---

### 测试 6：应用已批准的结果

**目标**：验证可以将已批准的结果应用到主数据库

**步骤**：
1. 确保至少有一条 **"已批准"** 的结果
2. 点击右上角的 **"应用所有已批准"** 按钮

**预期结果**：
- [x] 弹出提示框显示应用结果统计
- [x] 显示成功应用的数量和失败的数量

---

### 测试 7：任务状态持久化

**目标**：验证任务状态在页面刷新后保持

**步骤**：
1. 记录当前的任务列表和状态
2. 刷新页面（F5）
3. 重新导航到作品分析页面

**预期结果**：
- [x] 所有任务仍然存在
- [x] 任务状态保持不变
- [x] 已完成任务的结果数量正确显示

---

### 测试 8：不同任务类型

**目标**：验证不同类型的分析任务都能正常工作

**步骤**：
重复测试 1-4，分别创建以下类型的任务：
1. **大纲提取** (outline_extraction)
2. **人物识别** (character_detection)
3. **设定提取** (setting_extraction)

**预期结果**：
- [x] 每种类型都能成功创建
- [x] Mock 模式为每种类型生成相应的模拟数据：
  - 大纲提取：生成 plot_points 和 overall_summary
  - 人物识别：生成 characters 数组
  - 设定提取：生成 settings 数组

---

## API 端点测试

可以使用 curl 或 Postman 直接测试 API：

### 创建任务

```bash
curl -X POST http://localhost:8000/api/v1/analysis/task/ \
  -H "Content-Type: application/json" \
  -d '{
    "edition_id": 1,
    "task_type": "outline_extraction",
    "target_scope": "full",
    "target_node_ids": [],
    "parameters": {}
  }'
```

### 获取执行计划

```bash
curl -X POST http://localhost:8000/api/v1/analysis/task-execution/1/plan \
  -H "Content-Type: application/json" \
  -d '{"mode": "llm_direct"}'
```

### 执行任务（Mock 模式）

```bash
curl -X POST http://localhost:8000/api/v1/analysis/task-execution/1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "llm_direct",
    "llm_provider": "mock",
    "temperature": 0.3
  }'
```

### 获取任务进度

```bash
curl http://localhost:8000/api/v1/analysis/task-execution/1/progress
```

### 获取任务结果

```bash
curl http://localhost:8000/api/v1/analysis/task/1/results
```

### 批准结果

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/task/result/1/approve?reviewer=test"
```

### 获取 LLM 提供商列表

```bash
curl http://localhost:8000/api/v1/analysis/llm/providers
```

---

## Mock 模式说明

Mock 模式是专门为测试和演示设计的，具有以下特点：

1. **无需 API Key**：不需要配置任何 LLM 服务的密钥
2. **模拟延迟**：每个分块处理模拟 1-3 秒的延迟
3. **随机数据**：生成的分析结果是随机的模拟数据
4. **完整流程**：虽然数据是模拟的，但整个任务管理流程是真实的

### Mock 数据示例

**大纲提取**：
```json
{
  "plot_points": [
    {
      "title": "模拟情节点 1",
      "type": "conflict",
      "importance": "major",
      "summary": "这是一个模拟生成的情节描述...",
      "characters": ["角色1", "角色2"]
    }
  ],
  "overall_summary": "本段章节主要讲述了故事的发展过程..."
}
```

**人物识别**：
```json
{
  "characters": [
    {
      "canonical_name": "张三",
      "aliases": ["张三大人", "小三"],
      "role_type": "protagonist",
      "description": "这是张三的角色描述...",
      "mention_count": 25
    }
  ]
}
```

---

## 常见问题

### Q: 任务执行时卡住怎么办？
A: Mock 模式下每个分块需要 1-3 秒处理时间。如果长时间无响应，检查后端控制台是否有错误日志。

### Q: 刷新页面后进度丢失？
A: 这是正常行为。进度信息存储在内存中，页面刷新后需要重新从数据库加载。已完成的任务状态会保留。

### Q: 结果数据看起来很奇怪？
A: Mock 模式生成的是随机模拟数据，不代表真实的分析结果。正式使用时需要配置真实的 LLM API。

### Q: 如何使用真实的 LLM？
A: 在执行任务时选择其他 LLM 提供商（如 OpenAI、Anthropic），并在相应的环境变量中配置 API Key。

---

## 技术架构

```
前端 (React/TypeScript)
    │
    ├── TaskPanel 组件
    │   ├── 任务列表
    │   ├── 执行任务
    │   └── 审核结果
    │
    ├── API 调用层 (analysis.ts)
    │   ├── api_create_analysis_task
    │   ├── api_execute_task
    │   ├── api_get_task_progress
    │   └── api_approve_result
    │
    └── SSE 连接 (可选的实时更新)
        └── createTaskStatusEventSource

后端 (Python/Litestar)
    │
    ├── TaskExecutionController
    │   ├── POST /plan - 创建执行计划
    │   ├── POST /execute - 同步执行
    │   ├── POST /execute-async - 异步执行
    │   ├── GET /progress - 获取进度
    │   └── GET /status-stream - SSE 推送
    │
    ├── AnalysisTaskRunner
    │   ├── create_execution_plan
    │   ├── run_task
    │   └── _process_chunk_with_llm
    │
    └── LLMClient
        ├── LLMProvider.MOCK
        └── _complete_mock
            ├── _generate_mock_outline
            ├── _generate_mock_characters
            └── _generate_mock_settings
```

---

## 验收检查清单

| 功能 | 状态 | 备注 |
|------|------|------|
| 创建分析任务 | ☐ | |
| 生成执行计划 | ☐ | |
| Mock 模式执行 | ☐ | |
| 进度显示 | ☐ | |
| 查看结果 | ☐ | |
| 批准结果 | ☐ | |
| 拒绝结果 | ☐ | |
| 应用已批准结果 | ☐ | |
| 任务状态持久化 | ☐ | |
| 多任务类型 | ☐ | |

---

## 下一步

验收完成后，可以继续以下开发：

1. **接入真实 LLM**：配置 OpenAI/Anthropic/Google API
2. **Prompt 导出模式**：支持导出 Prompt 在外部工具使用
3. **WebSocket 实时推送**：替代 SSE 实现更好的双向通信
4. **批量任务处理**：支持同时运行多个任务
5. **任务调度器**：实现任务队列和优先级管理
