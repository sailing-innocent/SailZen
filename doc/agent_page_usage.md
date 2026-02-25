# Agent 页面使用指南

## 概述

Agent 页面是 SailZen 的 AI Agent 系统交互入口，提供：
- 任务提交和管理
- 实时执行状态跟踪
- 历史任务查看
- 调度器状态监控

## 页面结构

```
/agent
├── 顶部状态栏
│   └── Scheduler 状态（运行/停止、活跃任务数、统计）
├── 左侧区域
│   ├── 任务输入区（Prompt 输入、类型选择、优先级）
│   └── 快速模板（代码审查、数据分析、文档生成等）
└── 右侧区域
    ├── 任务历史列表
    └── 任务详情面板
```

## 功能说明

### 1. 提交任务

1. 选择任务类型（通用/代码/分析/写作/数据）
2. 输入任务描述
3. 设置优先级（1-10，数字越小优先级越高）
4. 点击"提交任务"或使用 Ctrl+Enter 快捷键

### 2. 快速模板

点击快速模板卡片，自动填充预设的 Prompt 格式：
- 💻 代码审查：审查代码质量和潜在问题
- 📊 数据分析：分析数据并生成报告
- ✍️ 文档生成：生成技术文档或说明
- 🤔 问题解答：解答技术或概念问题

### 3. 任务历史

- 显示所有历史任务列表
- 按点击时间倒序排列
- 显示任务状态、进度、类型
- 点击任务查看详情

### 4. 任务详情

- 实时显示执行进度
- 展示执行步骤（thought/action/observation/error/completion）
- 显示输出结果
- 错误信息展示

### 5. 调度器控制

- 显示调度器运行状态
- 启动/停止调度器
- 显示统计信息（已处理数、失败数）

## 技术实现

### 前端

- **页面组件**: `packages/site/src/pages/agent.tsx`
- **状态管理**: `packages/site/src/lib/store/agentStore.ts`
- **API 客户端**: `packages/site/src/lib/api/agent.ts`

### 后端

- **API 路由**: `/api/v1/agent/*`
- **WebSocket**: `/api/v1/agent/ws/events`

## 后续扩展计划

### Phase 1: 基础功能完善
- [ ] 模板系统增强（支持自定义模板）
- [ ] 任务搜索和筛选
- [ ] 批量操作（批量取消、删除）
- [ ] 任务导出功能

### Phase 2: 交互增强
- [ ] 对话式交互（多轮对话支持）
- [ ] 文件上传/下载
- [ ] 代码编辑器集成
- [ ] 富文本输出展示

### Phase 3: 智能化
- [ ] Prompt 优化建议
- [ ] 任务结果自动总结
- [ ] 相似任务推荐
- [ ] 个人知识库集成

### Phase 4: 协作功能
- [ ] 任务分享
- [ ] 团队协作空间
- [ ] 评论和反馈
- [ ] 版本历史

## 开发调试

### 启动开发服务器

```bash
# 后端
uv run server.py --dev

# 前端
cd packages/site
pnpm dev
```

### 访问页面

打开浏览器访问: `http://localhost:5173/agent`

### 调试技巧

1. **查看 WebSocket 消息**: 浏览器 DevTools → Network → WS
2. **查看 Redux 状态**: 使用 Redux DevTools
3. **后端日志**: 查看调度器和任务执行日志

## Mock 配置

当前实现使用 Mock 数据，可在 `sail_server/model/agent/runner.py` 中调整：

```python
class AgentRunner:
    MOCK_MIN_DELAY = 0.5      # 最小步骤延时（秒）
    MOCK_MAX_DELAY = 2.0      # 最大步骤延时（秒）
    MOCK_FAILURE_RATE = 0.2   # 失败率（20%）
    MOCK_MIN_STEPS = 3        # 最小步骤数
    MOCK_MAX_STEPS = 6        # 最大步骤数
```
