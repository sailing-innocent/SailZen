## MODIFIED Requirements

### Requirement: 异步并行大纲提取
系统 SHALL 支持异步并行处理模式，同时保持向后兼容。

#### Scenario: 默认使用并行模式
- **WHEN** 调用大纲提取 API 不指定模式
- **THEN** 系统 SHALL 使用新的异步并行模式
- **AND** 处理速度比串行模式提升 5 倍以上

#### Scenario: 显式指定串行模式
- **GIVEN** API 请求包含参数 mode: "sequential"
- **WHEN** 调用大纲提取
- **THEN** 系统 SHALL 使用旧的串行模式
- **AND** 结果与之前版本一致

#### Scenario: 结果一致性验证
- **GIVEN** 同一段文本
- **WHEN** 分别使用串行模式和并行模式提取大纲
- **THEN** 两种模式 SHALL 产生结构相同的大纲树
- **AND** 节点顺序和内容差异 < 5%

### Requirement: API 接口保持兼容
系统 SHALL 保持现有 API 接口不变，新增参数可选。

#### Scenario: 现有 API 调用
- **GIVEN** 旧版客户端调用 POST /api/v1/analysis/outline
- **AND** 请求体包含 text、title、author
- **WHEN** 发送请求
- **THEN** 系统 SHALL 正常处理并返回大纲
- **AND** 响应格式与之前版本相同

#### Scenario: 新增可选参数
- **GIVEN** 新版客户端调用 API
- **AND** 请求体包含可选参数：mode、max_concurrency、enable_progress
- **WHEN** 发送请求
- **THEN** 系统 SHALL 识别并使用这些参数
- **AND** 不传递时 SHALL 使用默认值

### Requirement: 错误处理增强
系统 SHALL 提供更详细的错误信息，帮助调试并行任务。

#### Scenario: 任务失败错误报告
- **GIVEN** 某个 chunk 任务执行失败
- **WHEN** 系统返回错误
- **THEN** 错误信息 SHALL 包含：
  - 失败的任务 ID 和层级
  - 失败原因（超时/网络/API 错误）
  - 重试次数
  - 建议的解决方案

#### Scenario: 部分成功处理
- **GIVEN** 100 个 chunks 中有 2 个失败
- **WHEN** 合并结果
- **THEN** 系统 SHALL 使用 best-effort 策略
- **AND** 在最终大纲中标记缺失部分
- **AND** 返回警告信息而非完全失败

### Requirement: 性能指标报告
系统 SHALL 在响应中包含性能指标，便于监控。

#### Scenario: 响应包含性能数据
- **WHEN** 大纲提取完成
- **THEN** 响应 SHALL 包含 performance 字段：
  - processing_time_ms: 总处理时间
  - tasks_count: 各级别任务数量
  - concurrency_used: 实际使用的最大并发数
  - api_calls: LLM API 调用次数
  - tokens_consumed: 消耗的 Token 数

## ADDED Requirements

### Requirement: 进度查询接口
系统 SHALL 提供独立的进度查询端点。

#### Scenario: 查询任务进度
- **WHEN** 调用 GET /api/v1/analysis/outline/status/{task_id}
- **THEN** 系统 SHALL 返回当前进度信息：
  - overall_progress: 总体完成百分比
  - level_progress: 各级别完成详情
  - estimated_time_remaining: 预估剩余时间
  - current_status: 当前状态（running/completed/failed）

### Requirement: 取消任务
系统 SHALL 支持取消正在执行的大纲提取任务。

#### Scenario: 取消正在运行的任务
- **GIVEN** 一个任务正在执行中
- **WHEN** 调用 DELETE /api/v1/analysis/outline/{task_id}
- **THEN** 系统 SHALL 取消所有正在执行的任务
- **AND** 清理相关资源
- **AND** 返回 204 No Content
