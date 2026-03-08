## ADDED Requirements

### Requirement: 任务依赖图构建
系统 SHALL 能够根据文本结构和处理层级构建有向无环图（DAG），表示任务间的依赖关系。

#### Scenario: 构建三级任务图
- **WHEN** 用户提交长文本进行大纲提取
- **THEN** 系统 SHALL 将文本切分为 chunks、segments 和 chapters
- **AND** 建立依赖关系：segments 依赖于其包含的 chunks 全部完成
- **AND** chapters 依赖于其包含的 segments 全部完成

### Requirement: 任务状态管理
系统 SHALL 维护每个任务的执行状态，支持状态流转和查询。

#### Scenario: 任务状态流转
- **WHEN** 任务被创建时
- **THEN** 状态为 PENDING
- **WHEN** 依赖任务全部完成且有可用资源时
- **THEN** 状态变为 READY
- **WHEN** 任务开始执行时
- **THEN** 状态变为 RUNNING
- **WHEN** 任务成功完成时
- **THEN** 状态变为 COMPLETED
- **WHEN** 任务执行失败但可重试时
- **THEN** 状态变为 FAILED 并触发重试逻辑

### Requirement: 依赖触发机制
系统 SHALL 在任务完成后自动检查并触发下游依赖任务。

#### Scenario: 下游任务自动触发
- **GIVEN** 任务 A 有下游依赖任务 B 和 C
- **WHEN** 任务 A 标记为 COMPLETED
- **THEN** 系统 SHALL 检查 B 和 C 的所有上游依赖是否完成
- **AND** 如果所有上游依赖完成，将 B 和 C 标记为 READY

### Requirement: 结果传递与合并
系统 SHALL 支持任务结果的向上传递和合并，形成层级结构。

#### Scenario: Chunk 结果合并到 Segment
- **GIVEN** Segment S 包含 Chunk C1、C2、C3
- **WHEN** C1、C2、C3 全部完成并返回大纲节点
- **THEN** 系统 SHALL 将三个 chunk 的结果按原始顺序合并
- **AND** 传递给 Segment S 的输入

#### Scenario: Segment 结果合并到 Chapter
- **GIVEN** Chapter Ch 包含 Segment S1、S2
- **WHEN** S1、S2 全部完成
- **THEN** 系统 SHALL 合并 segments 结果并生成最终大纲树

### Requirement: 任务超时处理
系统 SHALL 支持任务超时检测和自动重试。

#### Scenario: 任务执行超时
- **GIVEN** 任务配置了 30 秒超时
- **WHEN** 任务执行超过 30 秒未完成
- **THEN** 系统 SHALL 取消该任务执行
- **AND** 标记为 FAILED
- **AND** 触发重试逻辑（最多 3 次）

### Requirement: 循环依赖检测
系统 SHALL 在构建任务图时检测循环依赖并报错。

#### Scenario: 检测到循环依赖
- **GIVEN** 任务 A 依赖 B，B 依赖 C，C 依赖 A
- **WHEN** 系统构建任务图
- **THEN** 系统 SHALL 检测到循环依赖
- **AND** 抛出 ValueError 并说明循环路径
