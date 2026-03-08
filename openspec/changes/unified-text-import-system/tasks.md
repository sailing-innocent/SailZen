## 1. 后端基础设施 - 文本导入工具迁移

- [x] 1.1 创建 `sail_server/utils/text_import/` 模块结构
- [x] 1.2 将 AI 文本导入工具核心逻辑从 `.agents/skills/sailzen-ai-text-import/` 迁移到 `sail_server/utils/text_import/`
- [x] 1.3 重构 `text_cleaner.py` 为可调用模块（保持脚本独立运行能力）
- [x] 1.4 重构 `ai_chapter_parser.py` 为可调用模块
- [x] 1.5 创建 `chapter_types.py` 定义章节类型常量
- [x] 1.6 创建 `noise_patterns.py` 定义噪音模式
- [x] 1.7 添加文本编码检测功能（使用 chardet 库）
- [x] 1.8 创建 `__init__.py` 暴露主要 API

## 2. 后端 - 异步导入任务实现

- [x] 2.1 扩展 UnifiedAgentScheduler 支持 `text_import` 任务类型
- [x] 2.2 创建 `TextImportTaskHandler` 类处理导入任务
- [x] 2.3 实现四阶段处理流程：Upload→Preprocess→Parse→Store
- [x] 2.4 集成 AI 章节解析到任务处理流程
- [x] 2.5 实现任务进度更新和持久化
- [x] 2.6 实现任务取消机制
- [ ] 2.7 实现任务恢复和重试机制
- [ ] 2.8 添加任务执行超时控制

## 3. 后端 - API 端点实现

- [x] 3.1 创建 `POST /api/v1/text/import-async/upload` 端点接收文件上传
- [x] 3.2 创建 `POST /api/v1/text/import-async/` 端点创建异步导入任务
- [x] 3.3 创建 `GET /api/v1/text/import-async/tasks` 端点获取任务列表
- [x] 3.4 创建 `GET /api/v1/text/import-async/tasks/{task_id}` 端点获取任务详情
- [x] 3.5 创建 `POST /api/v1/text/import-async/tasks/{task_id}/cancel` 端点取消任务
- [ ] 3.6 创建 `POST /api/v1/text/import-async/tasks/{task_id}/retry` 端点重试任务
- [x] 3.7 创建 `DELETE /api/v1/text/import-async/tasks/{task_id}` 端点删除任务
- [x] 3.8 更新 `sail_server/router/text.py` 注册新端点

## 4. 后端 - WebSocket 进度通知

- [x] 4.1 扩展 WebSocket 消息类型定义（import_task_created, import_progress_update 等）
- [x] 4.2 在 TextImportTaskHandler 中集成 WebSocket 通知
- [x] 4.3 实现四阶段进度计算和推送
- [x] 4.4 实现任务完成/失败通知
- [ ] 4.5 添加心跳机制防止长连接断开
- [ ] 4.6 实现服务器重启后的 WebSocket 重连和状态恢复

## 5. 后端 - 临时文件管理

- [x] 5.1 实现上传文件临时存储（/tmp/sailzen_uploads/）
- [x] 5.2 添加文件大小限制（500MB）
- [x] 5.3 实现文件类型验证（.txt, .md, .text）
- [x] 5.4 实现临时文件自动清理（成功24小时后，失败7天后）
- [x] 5.5 添加临时文件存储目录监控

## 6. 前端 - 文件上传组件

- [x] 6.1 创建 `AsyncImportDialog` 组件支持大文件上传
- [x] 6.2 实现文件选择和验证（大小、类型）
- [x] 6.3 实现流式上传和进度显示
- [ ] 6.4 添加上传取消功能
- [ ] 6.5 实现编码选择和自动检测
- [x] 6.6 添加 AI 解析模式开关
- [ ] 6.7 更新 `text_import_dialog.tsx` 使用新的上传组件

## 7. 前端 - 导入任务管理界面

- [x] 7.1 创建 `ImportTaskList` 组件显示任务列表
- [x] 7.2 实现任务状态筛选和搜索
- [ ] 7.3 创建 `ImportTaskDetail` 组件显示任务详情
- [x] 7.4 实现任务操作按钮（取消、重试、删除）
- [ ] 7.5 添加批量操作功能
- [ ] 7.6 实现实时 WebSocket 更新
- [ ] 7.7 添加任务历史自动清理提示

## 8. 前端 - 进度显示组件

- [ ] 8.1 创建 `ImportProgressBar` 组件
- [ ] 8.2 实现四阶段进度指示器
- [ ] 8.3 添加当前阶段描述和 ETA 显示
- [ ] 8.4 实现可展开的详细信息视图
- [ ] 8.5 添加完成成功/失败动画
- [ ] 8.6 集成到文本管理页面

## 9. 前端 - API 和类型定义

- [x] 9.1 更新 `packages/site/src/lib/api/text.ts` 添加异步导入 API
- [x] 9.2 更新 `packages/site/src/lib/data/text.ts` 添加任务相关类型
- [x] 9.3 创建 `packages/site/src/lib/api/asyncImport.ts` 任务管理 API
- [ ] 9.4 更新 WebSocket 消息类型定义
- [ ] 9.5 添加导入任务相关的 Store（Zustand）

## 10. 前端 - 页面集成

- [ ] 10.1 更新 `text.tsx` 页面添加导入任务列表标签页
- [ ] 10.2 实现导入完成后自动刷新作品列表
- [ ] 10.3 添加从作品详情查看关联导入任务功能
- [ ] 10.4 优化移动端导入体验

## 11. 测试和验证

- [ ] 11.1 编写后端单元测试（文本清理、章节解析）
- [ ] 11.2 编写后端集成测试（API 端点、任务调度）
- [ ] 11.3 编写前端组件测试
- [ ] 11.4 进行大文件测试（10MB, 100MB, 500MB）
- [ ] 11.5 测试各种编码格式（UTF-8, GBK, GB2312）
- [ ] 11.6 测试 AI 章节解析准确性
- [ ] 11.7 测试 WebSocket 实时通知
- [ ] 11.8 进行并发导入测试

## 12. 文档和优化

- [ ] 12.1 更新 API 文档
- [ ] 12.2 编写用户操作指南
- [ ] 12.3 添加代码注释和文档字符串
- [ ] 12.4 性能优化（数据库批量插入、内存使用）
- [ ] 12.5 错误处理和日志完善
- [ ] 12.6 添加监控和告警（可选）
