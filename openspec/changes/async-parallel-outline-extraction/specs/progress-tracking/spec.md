## ADDED Requirements

### Requirement: 任务级别进度报告
系统 SHALL 报告不同层级任务的完成进度。

#### Scenario: 查询整体进度
- **WHEN** 用户查询大纲提取任务进度
- **THEN** 系统 SHALL 返回各级别完成数量
- **AND** 格式为：{"chunks": {"completed": 45, "total": 50}, "segments": {"completed": 8, "total": 10}, "chapters": {"completed": 0, "total": 1}}

#### Scenario: 计算总体完成百分比
- **GIVEN** chunks 完成 45/50 (90%)
- **AND** segments 完成 8/10 (80%)
- **AND** chapters 完成 0/1 (0%)
- **WHEN** 计算总体进度
- **THEN** 系统 SHALL 按权重计算：chunks 40% + segments 30% + chapters 30%
- **AND** 返回总体进度 72%

### Requirement: 实时状态更新
系统 SHALL 支持实时或近实时的进度更新机制。

#### Scenario: WebSocket 实时推送
- **GIVEN** 客户端建立了 WebSocket 连接
- **WHEN** 任务状态发生变化（如 RUNNING → COMPLETED）
- **THEN** 系统 SHALL 通过 WebSocket 推送更新
- **AND** 消息包含 task_id、status、progress_percentage

#### Scenario: 轮询接口
- **GIVEN** 客户端通过 HTTP 轮询
- **WHEN** 调用 GET /api/v1/analysis/outline/status/{task_id}
- **THEN** 系统 SHALL 返回当前进度和状态
- **AND** 响应时间 < 100ms

### Requirement: 预估剩余时间
系统 SHALL 根据历史执行速度预估剩余处理时间。

#### Scenario: 计算 ETA
- **GIVEN** 任务已运行 30 秒
- **AND** 已完成 30 个 chunks，总共 100 个
- **AND** 每个 chunk 平均耗时 1 秒
- **WHEN** 计算预估剩余时间
- **THEN** 系统 SHALL 返回 "约 70 秒"
- **AND** 格式化为 "1分10秒"

#### Scenario: 动态调整 ETA
- **GIVEN** 初始 ETA 为 120 秒
- **WHEN** 系统检测到当前并发数受限（RPM 上限）
- **THEN** 系统 SHALL 更新 ETA 为 150 秒
- **AND** 通知客户端时间调整

### Requirement: 详细状态信息
系统 SHALL 提供每个任务的详细状态信息。

#### Scenario: 获取任务详情
- **WHEN** 查询特定 task_id 的状态
- **THEN** 系统 SHALL 返回：
  - status: 当前状态
  - level: 任务层级（chunk/segment/chapter）
  - dependencies: 依赖任务列表及状态
  - start_time: 开始时间（如果有）
  - end_time: 结束时间（如果有）
  - error: 错误信息（如果失败）
  - retry_count: 重试次数

### Requirement: 进度历史记录
系统 SHALL 记录进度变化历史，支持事后分析。

#### Scenario: 记录状态变更
- **WHEN** 任务从 PENDING → READY → RUNNING → COMPLETED
- **THEN** 系统 SHALL 记录每个状态变更的时间戳
- **AND** 存储到内存或日志中

#### Scenario: 生成执行报告
- **GIVEN** 大纲提取任务完成
- **WHEN** 生成执行报告
- **THEN** 系统 SHALL 包含：
  - 总耗时
  - 各级别任务数量
  - 平均任务执行时间
  - 重试次数统计
  - API 调用次数和 Token 消耗
