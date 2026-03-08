## ADDED Requirements

### Requirement: 文本多级切分
系统 SHALL 支持将文本切分为三个层级：chunks（片段）、segments（段落组）、chapters（章节）。

#### Scenario: 文本自动切分
- **WHEN** 用户提交文本长度为 50000 tokens
- **THEN** 系统 SHALL 切分为约 50 个 chunks（每 chunk 1000 tokens）
- **AND** 每 5 个 chunks 组成 1 个 segment（共 10 个 segments）
- **AND** 所有 segments 属于 1 个 chapter

#### Scenario: 短文本优化切分
- **WHEN** 用户提交文本长度 < 5000 tokens
- **THEN** 系统 SHALL 只切分为 chunks（不创建 segments 层级）
- **AND** 直接合并 chunk 结果作为最终大纲

### Requirement: 层级大纲提取
系统 SHALL 在每个层级调用 LLM 提取大纲，不同层级有不同的提取目标。

#### Scenario: Chunk 层级提取
- **GIVEN** 一个 chunk 包含原文内容
- **WHEN** 执行 chunk 级大纲提取
- **THEN** LLM SHALL 提取该片段内的关键事件、角色出现、场景转换
- **AND** 输出为结构化大纲节点列表

#### Scenario: Segment 层级提取
- **GIVEN** 一个 segment 包含 5 个 chunks 的合并结果
- **WHEN** 执行 segment 级大纲提取
- **THEN** LLM SHALL 识别段落主题、子情节发展、角色关系变化
- **AND** 整合 chunks 结果，去除重复，补全缺失信息

#### Scenario: Chapter 层级提取
- **GIVEN** 所有 segments 结果已合并
- **WHEN** 执行 chapter 级大纲提取
- **THEN** LLM SHALL 生成完整的大纲树结构
- **AND** 包含章节标题、主要情节点、角色弧线、时间线

### Requirement: 结果顺序保持
系统 SHALL 保证并行处理后的大纲结果按原文顺序排列。

#### Scenario: 并行处理后的顺序保持
- **GIVEN** 10 个 chunks 并发处理，完成时间不同
- **WHEN** 合并所有 chunk 结果
- **THEN** 最终大纲 SHALL 按 chunks 的原始顺序排列
- **AND** 与串行处理的结果顺序一致

### Requirement: 上下文传递
系统 SHALL 在层级间传递上下文信息，保证大纲连贯性。

#### Scenario: Segment 处理时获取上下文
- **GIVEN** Segment S2 依赖 chunks C6-C10
- **WHEN** 处理 S2 时
- **THEN** 系统 SHALL 提供 S1（前一个 segment）的摘要作为上下文
- **AND** 帮助 LLM 理解情节连贯性

### Requirement: 边界处理
系统 SHALL 处理文本边界处的信息完整性。

#### Scenario: Chunk 边界重叠
- **GIVEN** 文本在 chunk 边界处被切断（一个句子跨两个 chunks）
- **WHEN** 切分文本时
- **THEN** 系统 SHALL 使用滑动窗口（overlap 200 tokens）
- **AND** 合并时 SHALL 识别并去除重叠内容的重复
