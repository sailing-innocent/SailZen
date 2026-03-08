## ADDED Requirements

### Requirement: 并发数限制
系统 SHALL 限制同时进行的 LLM API 调用数量不超过配置的最大并发数。

#### Scenario: 并发数达到上限
- **GIVEN** 最大并发数配置为 100
- **AND** 当前有 100 个任务正在执行
- **WHEN** 有新任务变为 READY 状态
- **THEN** 系统 SHALL 将该任务保持在 READY 队列
- **AND** 等待有任务完成后再执行

#### Scenario: 并发数释放
- **GIVEN** 当前有 100 个任务正在执行
- **WHEN** 其中一个任务完成（COMPLETED 或 FAILED）
- **THEN** 系统 SHALL 从 READY 队列取出一个任务开始执行
- **AND** 保持并发数不超过 100

### Requirement: RPM（每分钟请求数）限制
系统 SHALL 控制每分钟发送的 LLM API 请求数不超过配置值。

#### Scenario: RPM 接近上限
- **GIVEN** RPM 限制配置为 500
- **AND** 过去 60 秒内已发送 480 个请求
- **WHEN** 有 5 个新任务需要执行
- **THEN** 系统 SHALL 只执行 2 个任务（预留 20 缓冲）
- **AND** 其余 3 个任务 SHALL 延迟到下一分钟窗口

#### Scenario: RPM 重置
- **GIVEN** 上一分钟已用完 500 RPM 配额
- **WHEN** 进入新的一分钟
- **THEN** 系统 SHALL 重置计数器
- **AND** 允许执行新任务

### Requirement: TPM（每分钟 Token 数）限制
系统 SHALL 跟踪每分钟消耗的 Token 数，确保不超过限制。

#### Scenario: TPM 限制检查
- **GIVEN** TPM 限制配置为 3,000,000
- **AND** 当前分钟已消耗 2,800,000 tokens
- **WHEN** 新任务需要消耗 250,000 tokens
- **THEN** 系统 SHALL 延迟该任务到下一分钟窗口
- **AND** 确保总消耗不超过 3,000,000

#### Scenario: Token 数估算
- **GIVEN** 任务输入文本长度为 1000 字符
- **WHEN** 计算 Token 消耗
- **THEN** 系统 SHALL 按 1 token ≈ 4 字符估算
- **AND** 预估该任务消耗约 250 tokens

### Requirement: 令牌桶算法实现
系统 SHALL 使用令牌桶算法平滑流量，避免突发请求。

#### Scenario: 令牌桶消费
- **GIVEN** 令牌桶容量为 100，当前有 80 个令牌
- **WHEN** 有 30 个新任务需要执行
- **THEN** 系统 SHALL 执行 20 个任务（消耗 20 令牌）
- **AND** 剩余 10 个任务 SHALL 等待令牌补充

#### Scenario: 令牌补充
- **GIVEN** 令牌桶每秒补充 8.33 个令牌（500 RPM / 60）
- **WHEN** 1 秒后
- **THEN** 系统 SHALL 向桶中添加 8.33 个令牌（向上取整为 8）
- **AND** 桶中令牌数不超过 100

### Requirement: 优先级调度
系统 SHALL 支持任务优先级，高层级任务优先于低层级任务。

#### Scenario: 优先级队列
- **GIVEN** READY 队列中有 10 个 chunk 任务和 5 个 segment 任务
- **WHEN** 有空闲执行槽位
- **THEN** 系统 SHALL 优先执行 segment 任务（优先级高）
- **AND** 即使 chunk 任务先进入队列

#### Scenario: 同优先级 FIFO
- **GIVEN** READY 队列中有多个相同优先级的任务
- **WHEN** 选择下一个执行任务
- **THEN** 系统 SHALL 选择最早进入队列的任务（FIFO）

### Requirement: 动态限流调整
系统 SHALL 根据 API 响应动态调整限流参数。

#### Scenario: 收到 429 Too Many Requests
- **GIVEN** 系统按 80 RPM 发送请求
- **WHEN** 收到 API 返回 429 状态码
- **THEN** 系统 SHALL 将 RPM 临时降低到 60
- **AND** 等待 10 秒后逐步恢复

#### Scenario: 成功率监控
- **GIVEN** 最近 50 个请求的成功率 < 95%
- **WHEN** 计算限流参数
- **THEN** 系统 SHALL 降低并发数 20%
- **AND** 记录警告日志
