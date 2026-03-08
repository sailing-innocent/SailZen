## Why

当前 SailZen 项目的文本导入功能存在前后端脱节问题：前端上传大文本文件（如百万字小说）会触发 "Too Large" 错误，而后端虽然具备 AI 驱动的智能章节解析能力，但仅作为独立脚本存在，未与前端打通。这导致用户无法便捷地导入和管理大型文本作品，限制了知识库管理的完整性和实用性。

## What Changes

- **前端改造**: 实现流式大文件上传组件，支持分片上传和实时进度显示
- **后端异步任务**: 扩展 UnifiedAgentScheduler 支持文本导入任务类型，实现后台异步处理大文本
- **AI 章节识别集成**: 将现有的 AI 文本导入工具（`.agents/skills/sailzen-ai-text-import/`）集成到后端 API，支持智能章节切分
- **WebSocket 实时通知**: 实现导入进度实时推送到前端，展示章节解析、AI 分析、数据存储各阶段进度
- **任务管理界面**: 前端新增导入任务列表和详情页面，支持查看历史导入记录和重新处理
- **文本预清理**: 自动处理编码问题、移除广告噪音、规范化章节格式
- **异常章节检测**: 识别超长/超短章节、合并错误切分、提示异常内容

## Capabilities

### New Capabilities
- `large-file-upload`: 大文件分片上传和流式处理，支持 GB 级文本文件
- `async-text-import`: 异步文本导入任务调度和执行，集成到现有任务系统
- `ai-chapter-parsing`: AI 驱动的智能章节识别和切分，支持非标准格式
- `text-preprocessing`: 文本预清理和规范化，处理编码、噪音、格式问题
- `import-progress-tracking`: 导入进度实时跟踪和 WebSocket 推送
- `import-task-management`: 导入任务管理和历史记录查询

### Modified Capabilities
- `unified-agent-scheduler`: 扩展支持新的文本导入任务类型，增强进度回调机制
- `text-api`: 新增异步导入端点，保留现有同步导入 API 兼容性
- `frontend-text-management`: 扩展文本管理页面支持导入任务展示和监控

## Impact

- **后端**: `sail_server/router/text.py`, `sail_server/controller/text.py`, `sail_server/model/text.py`, `sail_server/model/unified_scheduler.py`
- **前端**: `packages/site/src/pages/text.tsx`, `packages/site/src/components/text_import_dialog.tsx`, 新增 `packages/site/src/components/import_task_panel.tsx`
- **API**: 新增 `/api/v1/text/import-async` 端点，扩展 WebSocket 消息类型
- **数据库**: 复用现有的 `IngestJob` 表，无需 schema 变更
- **依赖**: 复用现有的 LLM 客户端和 AI 文本导入工具逻辑
