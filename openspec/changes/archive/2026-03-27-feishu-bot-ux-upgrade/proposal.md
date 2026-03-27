## Why

当前 Feishu 机器人与 OpenCode 的交互体验存在明显不足：会话生命周期管理混乱导致状态错误；纯文本交互缺乏视觉引导和信息层次；缺少等待状态和确认流程让用户无法感知操作进度。这些问题严重影响了远程开发控制的可用性和用户体验，需要一次全面的 UX 升级来打造真正可用的移动开发助手。

## What Changes

- **会话生命周期绑定**: 实现 Feishu 机器人与 OpenCode 会话的完整生命周期绑定 - 机器人启动时自动恢复或创建会话，关闭时优雅关闭相关会话
- **交互卡片系统**: 使用飞书消息卡片替代纯文本，提供工作区选择卡片、会话状态卡片、任务执行进度卡片、确认对话框等丰富的视觉交互
- **等待与进度反馈**: 添加操作等待状态（"正在启动..."、"正在处理..."），配合进度指示器和实时状态更新
- **二次确认流程**: 为高风险操作（停止会话、切换工作区）添加确认步骤，支持显式确认/取消交互
- **状态同步机制**: 实现机器人与 OpenCode 进程状态的实时同步，在状态异常时自动恢复或提示用户

**BREAKING**: 原有的纯文本交互模式将被卡片交互取代，但核心命令语义保持不变

## Capabilities

### New Capabilities

- `feishu-card-rendering`: 飞书消息卡片的渲染与更新，支持多种卡片模板（工作区选择、会话状态、确认对话框等）
- `session-lifecycle-binding`: 机器人与 OpenCode 会话的生命周期绑定与同步管理
- `ux-progress-feedback`: 操作进度反馈与等待状态展示系统
- `interaction-confirmation-flow`: 用户操作的二次确认流程与风险评估

### Modified Capabilities

- `feishu-mobile-control-plane`: 增强移动端交互体验，从纯文本升级到卡片驱动交互（基于 redesign-feishu-opencode-bridge-workflow 中的基础实现）
- `opencode-session-orchestration`: 添加会话状态与机器人状态的绑定逻辑

## Impact

- **主要影响**: `bot/feishu_agent.py` - 核心交互逻辑重构
- **依赖**: 需要飞书开放平台的消息卡片 API 权限
- **用户体验**: 从命令行式交互升级为 GUI 式卡片交互
- **向后兼容**: 保留原有命令解析能力，但交互形式改变
