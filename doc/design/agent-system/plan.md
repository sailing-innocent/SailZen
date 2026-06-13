# SailZen Autonomous Agent — 全面审查与长期演进规划

> **版本**: 2.0-draft  
> **日期**: 2025-06-18  
> **范围**: 基于 `doc/design/agent-system/autonomous-agent.md` 的完整链路审查  
> **方法**: 第一性原理 — 从"长期身体健康、财产健康维护"和"长期-渐进个人助手"的本质需求出发，审视当前实现的完备性。

---

## 第一部分：第一性原理分析

### 1.1 长期身体健康维护的本质需求

从第一性原理出发，维护长期身体健康需要：

1. **多维度生物指标采集** — 体重只是其中一个维度，还需要睡眠、心率、血压、血糖、体脂率、腰围等
2. **行为模式识别** — 识别饮食、运动、作息的周期性规律和异常偏离
3. **渐进式干预** — 不是一次性建议，而是根据执行反馈持续调整策略强度
4. **归因分析** — 体重变化≠健康变化，需要区分水分、肌肉、脂肪的构成变化
5. **预防性监测** — 在问题发生前识别风险信号（如连续熬夜→免疫力下降→生病概率上升）
6. **医疗上下文整合** — 体检报告、医嘱、用药记录的整合分析

### 1.2 长期财产健康维护的本质需求

1. **资产全景视图** — 不仅账户余额，还有投资、房产、保险、债务的净 worth 计算
2. **现金流预测** — 基于收入规律+支出规律+大额事件，预测未来N个月的现金状况
3. **风险暴露分析** — 收入集中度、应急储备充足率、保险覆盖缺口
4. **目标导向规划** — 退休、购房、教育等长期目标的进度追踪和缺口计算
5. **税务优化建议** — 基于收入结构和支出结构的税务规划
6. **行为经济学干预** — 识别冲动消费、锚定效应、心理账户等非理性财务行为

### 1.3 长期-渐进个人助手的本质需求

1. **持续学习用户模型** — 不是预设规则，而是从交互中提炼用户的偏好、习惯、约束
2. **主动感知与询问** — 在合适的时机（而非固定时间）主动发起交互
3. **执行闭环** — 建议→执行→反馈→调整的完整闭环
4. **上下文连续性** — 跨会话、跨pipeline的长期记忆和上下文继承
5. **可解释性** — 用户能理解为什么agent做出某个建议
6. **渐进式自治** — 从"建议"到"半自动"到"全自动"的逐步升级，有明确的approval gates
7. **多代理协作** — 不同领域的专家agent（健康、财务、学习、社交）协同工作

---

## 第二部分：当前实现审查 — Bug 清单与修复计划

### 2.1 严重 Bug（影响功能正确性或安全性）

| # | 位置 | 问题 | 影响 | 修复优先级 |
|---|------|------|------|-----------|
| B1 | `daemon.py:312` | `datetime.now()` 未导入 | 编译/运行时错误，pipeline执行失败 | **P0** |
| B2 | `scheduler.py:246,255` | 使用 `eval()` 反序列化params | 严重安全漏洞，任意代码执行 | **P0** |
| B3 | `db.py:413` | SQL字符串拼接注入风险 `f"WHERE status = '{status}'"` | SQL注入 | **P0** |
| B4 | `daemon.py:289-304` | DAG run创建后未真正触发执行 | pipeline看似运行实际未执行 | **P0** |
| B5 | `wellness_node.py:70` | fallback调用不存在的模块 `sailzen.wellness` | 双重fallback失败 | **P1** |
| B6 | `finance_anomaly_scan.yaml:67` | 引用未注册的 `shell` node type | pipeline执行失败 | **P1** |
| B7 | `smart_digest.yaml:42,71,78` | 引用未注册的 `skill`/`shell` node type | pipeline执行失败 | **P1** |
| B8 | `daily_standup.yaml:20` | 引用未注册的 `skill` node type | pipeline执行失败 | **P1** |

### 2.2 中等 Bug（影响可靠性或用户体验）

| # | 位置 | 问题 | 影响 | 修复优先级 |
|---|------|------|------|-----------|
| B9 | `notification_engine.py:98-99` | reminder状态更新TODO未实现 | 通知发送后状态仍为pending | **P1** |
| B10 | `notification_engine.py` | `_recent_alerts` 仅存内存 | 重启后去重状态丢失，可能重复通知 | **P1** |
| B11 | `condition_node.py:52` | Jinja2表达式eval方式脆弱 | 复杂condition可能解析失败 | **P1** |
| B12 | `scheduler.py` | `_restore_schedules` 重复插入 | DB中schedule记录重复 | **P1** |
| B13 | `llm_gateway.py` | system prompt处理逻辑混乱 | kimi的system prompt可能不生效 | **P2** |
| B14 | `memory.py` | `get_working_summary` 只按时间取10条 | 可能遗漏相关long-term记忆 | **P2** |
| B15 | `daemon.py:67` | `load_dag_config()` 可能加载错误配置 | DAG client配置和agent期望不匹配 | **P2** |

### 2.3 代码质量问题

| # | 位置 | 问题 | 建议 |
|---|------|------|------|
| Q1 | `daemon.py` | Windows信号处理为空pass | 添加Windows兼容的信号处理（如KeyboardInterrupt捕获） |
| Q2 | `config.py` | 路径解析逻辑复杂 | 统一使用 `pathlib.Path.resolve()` |
| Q3 | `store.py` | backup排除runs但保留notifications | 应该相反——runs可能更重要 |
| Q4 | `state_manager.py` | anomalies仅存内存 | 应持久化到DB |
| Q5 | `api/routes.py:76` | `eval(schedule.get("params","{}"))` | 同B2，替换为 `json.loads` |

---

## 第三部分：数据模型缺口分析

### 3.1 健康数据模型 — 当前 vs 所需

```
当前模型:                    所需模型:
┌─────────────┐              ┌─────────────┐
│ Weight      │              │ Weight      │
│ - value     │              │ - value     │
│ - htime     │              │ - htime     │
│ - tag       │              │ - tag       │
│ - desc      │              │ - body_fat% │  ← 新增
└─────────────┘              │ - muscle_kg │  ← 新增
                             │ - water%    │  ← 新增
┌─────────────┐              └─────────────┘
│ Exercise    │              
│ - htime     │              ┌─────────────┐
│ - desc      │              │ Sleep       │  ← 新增
└─────────────┘              │ - duration  │
                             │ - quality   │
┌─────────────┐              │ - deep%     │
│ BodySize    │              │ - rem%      │
│ - waist     │              │ - htime     │
│ - hip       │              └─────────────┘
│ - chest     │              
└─────────────┘              ┌─────────────┐
                             │ VitalSign   │  ← 新增
                             │ - heart_rate│
                             │ - bp_systolic│
                             │ - bp_diastolic│
                             │ - htime     │
                             └─────────────┘
                             
                             ┌─────────────┐
                             │ Meal        │  ← 新增
                             │ - type      │
                             │ - calories  │
                             │ - nutrients │
                             │ - htime     │
                             └─────────────┘
                             
                             ┌─────────────┐
                             │ Mood        │  ← 新增
                             │ - score     │
                             │ - stress    │
                             │ - energy    │
                             │ - htime     │
                             └─────────────┘
                             
                             ┌─────────────┐
                             │ MedicalExam │  ← 新增
                             │ - type      │
                             │ - results   │
                             │ - htime     │
                             └─────────────┘
```

### 3.2 财务数据模型 — 当前 vs 所需

```
当前模型:                    所需模型:
┌─────────────┐              ┌─────────────┐
│ Account     │              │ Account     │
│ Transaction │              │ Transaction │
│ Budget      │              │ Budget      │
│ BudgetItem  │              │ BudgetItem  │
│ FinanceTag  │              │ FinanceTag  │
└─────────────┘              └─────────────┘
                             
                             ┌─────────────┐
                             │ Investment  │  ← 新增
                             │ - symbol    │
                             │ - quantity  │
                             │ - cost_basis│
                             │ - current   │
                             └─────────────┘
                             
                             ┌─────────────┐
                             │ Debt        │  ← 新增
                             │ - principal │
                             │ - interest  │
                             │ - term      │
                             │ - remaining │
                             └─────────────┘
                             
                             ┌─────────────┐
                             │ Insurance   │  ← 新增
                             │ - type      │
                             │ - coverage  │
                             │ - premium   │
                             │ - expire    │
                             └─────────────┘
                             
                             ┌─────────────┐
                             │ FinancialGoal│ ← 新增
                             │ - name      │
                             │ - target    │
                             │ - current   │
                             │ - deadline  │
                             │ - category  │
                             └─────────────┘
                             
                             ┌─────────────┐
                             │ RecurringBill│ ← 新增
                             │ - name      │
                             │ - amount    │
                             │ - frequency │
                             │ - next_due  │
                             └─────────────┘
```

### 3.3 Agent内部数据模型 — 当前 vs 所需

```
当前:                        所需:
┌─────────────────┐          ┌─────────────────┐
│ agent_schedules │          │ agent_schedules │
│ agent_memories  │          │ agent_memories  │
│ agent_reminders │          │ agent_reminders │
│ agent_goals     │          │ agent_goals     │
│ agent_run_log   │          │ agent_run_log   │
└─────────────────┘          │ agent_feedback  │  ← 新增：用户对建议的反馈
                             │ agent_strategies│  ← 新增：策略A/B测试结果
                             │ agent_events    │  ← 新增：事件驱动的触发记录
                             │ agent_learnings │  ← 新增：从交互中学到的模式
                             │ agent_profiles  │  ← 新增：用户画像（偏好、约束）
                             └─────────────────┘
```

---

## 第四部分：功能缺口分析

### 4.1 健康维护功能缺口

| 功能域 | 当前状态 | 缺失能力 | 优先级 |
|--------|---------|---------|--------|
| **指标采集** | 体重、运动 | 睡眠、心率、血压、饮食、情绪、体检 | P1 |
| **趋势分析** | 线性回归 | 多变量回归、异常检测、季节性分解 | P1 |
| **目标管理** | WeightPlan | 综合健康目标（BMI、体脂、睡眠时长等） | P2 |
| **干预闭环** | 提醒通知 | 执行追踪、效果评估、策略调整 | P1 |
| **预防监测** | 无 | 风险预测模型（基于历史模式） | P2 |
| **医疗整合** | 无 | 体检报告OCR、医嘱追踪、用药提醒 | P2 |
| **社交支持** | 无 | 运动打卡、健康挑战、进度分享 | P3 |

### 4.2 财务维护功能缺口

| 功能域 | 当前状态 | 缺失能力 | 优先级 |
|--------|---------|---------|--------|
| **资产全景** | 账户余额 | 投资、房产、债务、保险的净 worth | P1 |
| **现金流预测** | 历史统计 | 基于周期规律的预测模型 | P1 |
| **预算监控** | Budget存在 | 执行率追踪、超预算预警 | P2 |
| **目标规划** | 无 | FinancialGoal系统、缺口计算 | P1 |
| **税务优化** | 无 | 税务计算、扣除建议 | P3 |
| **行为干预** | 零食追踪 | 冲动消费识别、储蓄游戏化 | P2 |
| **账单管理** | 无 | RecurringBill追踪、到期提醒 | P2 |

### 4.3 个人助手能力缺口

| 能力域 | 当前状态 | 缺失能力 | 优先级 |
|--------|---------|---------|--------|
| **交互模式** | 定时推送 | 对话式交互、上下文感知 | P1 |
| **学习机制** | 无 | 用户偏好学习、策略优化 | P1 |
| **执行闭环** | 提醒发送 | 执行追踪、结果反馈、策略迭代 | P1 |
| **主动感知** | 定时触发 | 事件驱动（体重异常→立即询问） | P1 |
| **多代理协作** | 单一agent | 领域专家agent协作 | P2 |
| **知识整合** | 日记读取 | vault笔记深度索引、知识图谱 | P2 |
| **任务委托** | 无 | 创建sail_server任务、日历事件 | P2 |
| **生命周期** | 无 | 人生阶段模型、优先级动态调整 | P3 |

---

## 第五部分：长期设计大纲（Roadmap）

### 5.1 架构演进路线图

```
Phase 1: 修复与稳固 (0-2周)
  ├── 修复所有P0/P1 Bug
  ├── 补齐node registry（skill/shell nodes）
  ├── 完善单元测试和集成测试
  └── 建立CI/CD pipeline

Phase 2: 数据模型扩展 (2-6周)
  ├── sail_server: 新增Sleep/VitalSign/Meal/Mood ORM
  ├── sail_server: 新增Investment/Debt/Insurance/FinancialGoal ORM
  ├── sail_server: 新增RecurringBill ORM
  ├── agent: 新增feedback/strategies/events/learnings/profiles表
  └── CLI客户端: 新增数据导入导出命令

Phase 3: 核心能力增强 (6-12周)
  ├── 事件驱动架构: EventBus + 规则引擎
  ├── 对话系统: AgentChat + 上下文管理
  ├── 学习系统: PreferenceLearning + StrategyOptimizer
  ├── 预测引擎: TimeSeriesForecast + AnomalyDetection
  └── 闭环系统: ActionTracker + EffectEvaluator

Phase 4: 多智能体协作 (12-20周)
  ├── 领域Agent拆分: HealthAgent / FinanceAgent / LifeAgent
  ├── Agent协调器: AgentOrchestrator + 消息总线
  ├── 知识图谱: PersonalKnowledgeGraph
  └── 可视化仪表板: AgentDashboard

Phase 5: 高级自治 (20周+)
  ├── 渐进式自治升级: 建议→半自动→全自动的approval gates
  ├── 策略A/B测试: 多策略并行评估
  ├── 用户画像进化: 长期行为模式建模
  └── 跨平台集成: 可穿戴设备、智能家居、银行API
```

### 5.2 核心子系统设计

#### 5.2.1 事件驱动架构（EventBus）

```
┌─────────────────────────────────────────┐
│           EventBus                      │
├─────────────────────────────────────────┤
│  Sources:                               │
│  - sail_server webhooks (数据变更)       │
│  - 定时触发器 (cron/interval)            │
│  - 外部API (日历、银行、健康设备)         │
│  - 用户交互 (对话、按钮点击)              │
│                                         │
│  Rules Engine:                          │
│  - IF weight.change > 2kg/day           │
│    THEN trigger health_alert            │
│  - IF budget.execution > 100%           │
│    THEN trigger budget_warning          │
│  - IF sleep.quality < 3/3 days          │
│    THEN trigger sleep_intervention      │
│                                         │
│  Router:                                │
│  - 实时事件 → 立即处理                   │
│  - 批量事件 → 聚合后处理                 │
│  - 异常事件 → 高优先级队列               │
└─────────────────────────────────────────┘
```

#### 5.2.2 对话系统（AgentChat）

```
┌─────────────────────────────────────────┐
│           AgentChat                     │
├─────────────────────────────────────────┤
│  Input Channels:                        │
│  - Lark IM (双向)                        │
│  - WebSocket (实时)                      │
│  - API (程序化)                          │
│                                         │
│  Context Manager:                       │
│  - SessionContext (当前会话)             │
│  - UserProfile (长期画像)                │
│  - ActiveGoals (当前目标)                │
│  - RecentMemories (近期记忆)             │
│                                         │
│  Intent Router:                         │
│  - 查询类 → 数据检索                     │
│  - 分析类 → 调用wellness/analysis        │
│  - 执行类 → 调用sail_server API          │
│  - 对话类 → 闲聊/情感支持                │
│                                         │
│  Response Builder:                      │
│  - 结构化数据 → 图表/表格                │
│  - 分析结果 → 摘要+建议                  │
│  - 执行结果 → 确认+下一步                │
└─────────────────────────────────────────┘
```

#### 5.2.3 学习系统（LearningEngine）

```
┌─────────────────────────────────────────┐
│         LearningEngine                  │
├─────────────────────────────────────────┤
│  Preference Learning:                   │
│  - 通知时间偏好 (用户何时回复最快)        │
│  - 内容深度偏好 (简洁 vs 详细)           │
│  - 建议接受度 (哪些类型的建议被执行)      │
│                                         │
│  Strategy Optimization:                 │
│  - A/B测试框架                          │
│  - 多臂老虎机 (MAB) 策略选择             │
│  - 效果反馈闭环                         │
│                                         │
│  Pattern Discovery:                     │
│  - 周期性行为识别 (周末晚睡、月初大额支出) │
│  - 关联规则挖掘 (运动→睡眠质量→情绪)      │
│  - 异常基线建立 (个人化的正常范围)        │
└─────────────────────────────────────────┘
```

#### 5.2.4 闭环系统（ActionLoop）

```
┌─────────────────────────────────────────┐
│           ActionLoop                    │
├─────────────────────────────────────────┤
│  1. Suggest: 生成建议                    │
│     ↓                                   │
│  2. Deliver: 通过最佳渠道发送            │
│     ↓                                   │
│  3. Track: 追踪用户响应                  │
│     - 已读？已执行？已忽略？             │
│     ↓                                   │
│  4. Evaluate: 评估效果                   │
│     - 建议后的行为改变？                 │
│     - 目标进度变化？                     │
│     ↓                                   │
│  5. Learn: 更新策略                      │
│     - 成功策略强化                       │
│     - 失败策略弱化/淘汰                  │
│     ↓                                   │
│  6. Iterate: 下一轮建议                  │
└─────────────────────────────────────────┘
```

### 5.3 数据流重构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                        外部数据源                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │ 体重秤   │  │ 手环    │  │ 银行API │  │ 日历    │  │ 日记    │   │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘   │
│       │            │            │            │            │         │
│       └────────────┴────────────┴────────────┴────────────┘         │
│                              │                                      │
│                    ┌─────────┴─────────┐                            │
│                    │  Data Ingestion   │                            │
│                    │  (统一数据接入层)  │                            │
│                    └─────────┬─────────┘                            │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                    ┌─────────┴─────────┐                            │
│                    │   sail_server     │                            │
│                    │   (主数据存储)     │                            │
│                    └─────────┬─────────┘                            │
│                              │ HTTP API                             │
│                    ┌─────────┴─────────┐                            │
│                    │  sailzen CLI      │                            │
│                    │  (数据导出/分析)   │                            │
│                    └─────────┬─────────┘                            │
│                              │                                       │
│  ┌───────────────────────────┼───────────────────────────────────┐  │
│  │     Autonomous Agent      │                                   │  │
│  │  ┌─────────────────────┐  │  ┌─────────────────────┐         │  │
│  │  │   EventBus          │  │  │   LearningEngine    │         │  │
│  │  │   (事件路由/触发)    │◄─┼─►│   (策略学习/优化)    │         │  │
│  │  └─────────────────────┘  │  └─────────────────────┘         │  │
│  │  ┌─────────────────────┐  │  ┌─────────────────────┐         │  │
│  │  │   AgentChat         │  │  │   ActionLoop        │         │  │
│  │  │   (对话交互)         │◄─┼─►│   (建议闭环)         │         │  │
│  │  └─────────────────────┘  │  └─────────────────────┘         │  │
│  │  ┌─────────────────────┐  │  ┌─────────────────────┐         │  │
│  │  │   PredictionEngine  │  │  │   MultiAgent        │         │  │
│  │  │   (预测/异常检测)    │  │  │   Orchestrator      │         │  │
│  │  │                     │  │  │   (多Agent协作)      │         │  │
│  │  └─────────────────────┘  │  └─────────────────────┘         │  │
│  │                           │                                   │  │
│  │  ┌─────────────────────┐  │  ┌─────────────────────┐         │  │
│  │  │   AgentMemory       │  │  │   AgentStore        │         │  │
│  │  │   (记忆系统)         │  │  │   (文件存储)         │         │  │
│  │  └─────────────────────┘  │  └─────────────────────┘         │  │
│  └───────────────────────────┼───────────────────────────────────┘  │
│                              │                                       │
│                    ┌─────────┴─────────┐                            │
│                    │  Lark / IM        │                            │
│                    │  (用户交互渠道)    │                            │
│                    └───────────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第六部分：具体实施任务清单

### 6.1 Phase 1: 修复与稳固（立即开始）

- [ ] **B1** 在 `daemon.py` 顶部添加 `from datetime import datetime`
- [ ] **B2** 将 `scheduler.py` 中所有 `eval()` 替换为 `json.loads()`，schedule创建时存储JSON字符串
- [ ] **B3** 将 `db.py:413` SQL拼接改为参数化查询
- [ ] **B4** 修复DAG run触发逻辑：创建run后主动调用 `dag_scheduler.execute_run(dag_run_id)` 或等待机制
- [ ] **B5** 修复 `wellness_node.py` fallback路径，改为调用正确的 wellness skill 或直接HTTP
- [ ] **B6-B8** 注册缺失的 `shell` 和 `skill` node types，或修改pipeline YAML移除未实现节点
- [ ] **B9** 实现 `notification_engine.py` 中reminder状态更新逻辑
- [ ] **B10** 将 `_recent_alerts` 持久化到 `agent_memories` 表
- [ ] **B11** 改进 `condition_node.py` 表达式解析，使用safe_eval或结构化条件
- [ ] **B12** 在 `_restore_schedules` 中添加存在性检查，避免重复插入
- [ ] 编写 `tests/test_autonomous_agent/` 单元测试集
- [ ] 添加 `scripts/test-agent.sh` 一键测试脚本

### 6.2 Phase 2: 数据模型扩展

- [ ] **sail_server ORM扩展**
  - [ ] `Sleep` 表: duration, quality_score, deep_minutes, rem_minutes, awake_times
  - [ ] `VitalSign` 表: heart_rate, bp_systolic, bp_diastolic, blood_sugar, temperature
  - [ ] `Meal` 表: meal_type, calories, protein, carbs, fat, description
  - [ ] `Mood` 表: mood_score, stress_level, energy_level, notes
  - [ ] `MedicalExam` 表: exam_type, results_json, abnormal_flags
  - [ ] `Investment` 表: symbol, type, quantity, cost_basis, current_value
  - [ ] `Debt` 表: name, principal, interest_rate, term_months, remaining, monthly_payment
  - [ ] `Insurance` 表: type, provider, coverage_amount, premium, expire_date
  - [ ] `FinancialGoal` 表: name, target_amount, current_amount, deadline, category
  - [ ] `RecurringBill` 表: name, amount, frequency, next_due_date, account_id
- [ ] **Agent DB扩展**
  - [ ] `agent_feedback` 表: action_id, user_response, outcome, rating
  - [ ] `agent_strategies` 表: strategy_id, domain, params, success_rate, active
  - [ ] `agent_events` 表: event_type, source, payload, processed_at
  - [ ] `agent_learnings` 表: pattern_type, pattern_data, confidence, last_seen
  - [ ] `agent_profiles` 表: profile_key, profile_value, confidence, updated_at
- [ ] **CLI扩展**
  - [ ] `sailzen health log-sleep --duration 7.5 --quality 4`
  - [ ] `sailzen health log-vitals --heart-rate 72 --bp 120/80`
  - [ ] `sailzen health log-mood --score 7 --stress 3`
  - [ ] `sailzen finance add-goal --name "退休储蓄" --target 1000000 --deadline 2045-01-01`
  - [ ] `sailzen finance add-bill --name "房租" --amount 3500 --frequency monthly`

### 6.3 Phase 3: 核心能力增强

- [ ] **EventBus实现**
  - [ ] 事件定义schema（Pydantic模型）
  - [ ] WebSocket/Webhook接入sail_server变更事件
  - [ ] 规则引擎（简单的IF-THEN-ELSE，支持时间窗口和聚合）
  - [ ] 事件优先级队列
- [ ] **AgentChat实现**
  - [ ] Lark IM双向对话接口（接收用户消息）
  - [ ] 对话状态管理（SessionContext）
  - [ ] Intent分类器（基于LLM few-shot）
  - [ ] 响应模板系统（支持markdown、图表、表格）
- [ ] **LearningEngine实现**
  - [ ] 用户响应时间分析（找出最佳通知时间）
  - [ ] 建议执行率统计（按类型、时间、内容）
  - [ ] 简单的MAB策略选择（epsilon-greedy）
- [ ] **PredictionEngine实现**
  - [ ] 体重预测（扩展现有线性回归到ARIMA/Prophet）
  - [ ] 现金流预测（基于历史transaction的季节性模型）
  - [ ] 异常检测（Isolation Forest或基于统计的Z-score）
- [ ] **ActionLoop实现**
  - [ ] 建议生成器（基于规则+LLM）
  - [ ] 执行追踪器（用户是否执行了建议？）
  - [ ] 效果评估器（建议前后的指标变化）
  - [ ] 策略更新器（强化学习或简单加权）

### 6.4 Phase 4: 多智能体协作

- [ ] **领域Agent拆分**
  - [ ] `HealthAgent`: 专注于健康数据分析和干预
  - [ ] `FinanceAgent`: 专注于财务分析和规划
  - [ ] `LifeAgent`: 专注于日程、任务、生活管理
- [ ] **AgentOrchestrator**
  - [ ] 消息总线（Agent间通信）
  - [ ] 任务委托协议
  - [ ] 冲突解决（如Health建议休息 vs Life建议加班）
- [ ] **PersonalKnowledgeGraph**
  - [ ] 实体抽取（从日记、聊天记录中提取人、地点、事件）
  - [ ] 关系建模（时间关系、因果关系、社交关系）
  - [ ] 查询接口（支持自然语言查询个人历史）
- [ ] **AgentDashboard**
  - [ ] Web界面（Litestar + React）
  - [ ] 实时健康/财务指标展示
  - [ ] Agent决策过程可视化（为什么给出这个建议？）
  - [ ] 用户反馈界面（赞同/反对建议、调整偏好）

### 6.5 Phase 5: 高级自治

- [ ] **渐进式自治**
  - [ ] 定义自治级别：观察→建议→确认执行→自动执行
  - [ ] 每个pipeline/action可配置autonomy_level
  - [ ] 审批网关（Approval Gate）UI
- [ ] **策略A/B测试**
  - [ ] 多策略并行运行
  - [ ] 效果统计显著性检验
  - [ ] 自动策略切换
- [ ] **跨平台集成**
  - [ ] 可穿戴设备API（Apple Health, Garmin, Fitbit）
  - [ ] 银行API（支付宝、微信账单自动导入）
  - [ ] 智能家居（睡眠环境监控）

---

## 第七部分：关键设计决策记录

### 7.1 为什么不把Agent直接集成到sail_server？

**决策**: 保持完全隔离。  
**理由**:
1. **故障隔离**: Agent的LLM调用失败不应影响sail_server的API可用性
2. **部署独立**: Agent可以独立升级/重启，不依赖sail_server的发布周期
3. **资源隔离**: Agent的LLM成本、内存占用不应影响核心服务
4. **安全边界**: Agent可能需要调用外部API（银行、健康设备），隔离降低攻击面

### 7.2 为什么Agent需要自己的SQLite而不是用sail_server的DB？

**决策**: 完全独立的SQLite。  
**理由**:
1. **schema自主权**: Agent的记忆、策略、学习数据模型独立于业务数据
2. **迁移自由**: Agent DB可以删除重建而不影响业务数据
3. **备份策略不同**: Agent DB可能不需要和业务DB一样的备份频率
4. **写入性能**: Agent的高频写入（事件、记忆）不应影响业务DB

### 7.3 事件驱动vs定时驱动的选择

**决策**: 以事件驱动为主，定时驱动为辅。  
**理由**:
1. **响应性**: 体重异常应该立即提醒，而不是等到下一个定时任务
2. **效率**: 没有事件时不需要消耗资源运行pipeline
3. **自然感**: 人类助手的交互是事件触发的，不是定时播报
4. **保留定时**: 日报、周报等周期性汇总仍然需要定时触发

### 7.4 LLM使用策略

**决策**: 分层使用LLM。  
**架构**:
- **规则引擎**: 处理明确的IF-THEN场景（如预算超支100%）
- **轻量LLM**: 处理模式识别（如"本周支出比上月高20%"）
- **重量LLM**: 处理综合分析（wellness报告生成）
- **成本 guardrails**: 每次LLM调用记录成本，日/周/月预算上限

---

## 第八部分：成功标准（演进版）

### 8.1 Phase 1 成功标准
- [ ] `pytest tests/test_autonomous_agent/` 全部通过
- [ ] `grep -r "eval(" sailzen/autonomous_agent/` 返回0结果
- [ ] Agent可连续运行7天无崩溃
- [ ] 所有6个pipeline可手动触发并成功执行

### 8.2 Phase 2 成功标准
- [ ] 新增10个ORM表，API完整（CRUD + 列表 + 过滤）
- [ ] CLI支持所有新数据类型的导入导出
- [ ] 数据迁移脚本可从旧schema平滑升级

### 8.3 Phase 3 成功标准
- [ ] Agent可通过Lark IM与用户进行双向对话
- [ ] 用户反馈（执行/忽略建议）被记录并影响后续策略
- [ ] 体重预测准确率（30天）> 80%
- [ ] 现金流预测（下月支出）误差 < 15%

### 8.4 Phase 4 成功标准
- [ ] HealthAgent和FinanceAgent可独立运行并协作
- [ ] 个人知识图谱支持至少10种实体类型和5种关系类型
- [ ] Dashboard支持实时指标展示

### 8.5 Phase 5 成功标准
- [ ] 80%的日常建议无需用户确认即可自动执行
- [ ] 策略A/B测试自动识别最优策略
- [ ] 用户满意度评分（1-10）> 7.5

---

## 第九部分：风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| LLM API成本失控 | 中 | 高 | 硬编码token上限、日消费cap、分级使用策略 |
| 数据隐私泄露 | 低 | 极高 | 敏感数据不出本地、API密钥环境变量管理、定期审计 |
| 过度自动化导致用户反感 | 中 | 中 | 渐进式自治、明确approval gates、随时可降级到建议模式 |
| 数据模型频繁变更 | 高 | 中 | 使用Alembic迁移、版本化API、向后兼容设计 |
| 可穿戴设备API不稳定 | 中 | 低 | 抽象设备接口、本地缓存、优雅降级 |
| 用户反馈数据不足 | 高 | 中 | 简化反馈机制（一键反馈）、默认假设执行 |

---

## 第十部分：附录

### A. 当前Bug修复代码示例

**B2修复 (scheduler.py)**:
```python
# Before (line 246):
params=eval(s.get("params", "{}")),

# After:
import json
params=json.loads(s.get("params", "{}")),

# 同时在 add_cron/add_interval 中:
"params": json.dumps(params or {}),
```

**B3修复 (db.py)**:
```python
# Before (line 413):
query += f" WHERE status = '{status}'"

# After:
query += " WHERE status = :status"
# params 已在下面传入
```

**B1修复 (daemon.py)**:
```python
# 在文件顶部添加:
from datetime import datetime
```

### B. 推荐阅读顺序

1. `doc/design/agent-system/autonomous-agent.md` — 当前设计文档
2. `sailzen/autonomous_agent/daemon.py` — Agent主生命周期
3. `sailzen/autonomous_agent/db.py` — 数据库设计
4. `sailzen/autonomous_agent/scheduler.py` — 调度器实现
5. `sailzen/autonomous_agent/memory.py` — 记忆系统
6. `sailzen/autonomous_agent/notification_engine.py` — 通知引擎
7. `.opencode/skills/sailzen-wellness/SKILL.md` — Wellness分析skill

---

*End of Plan*  
*本计划应作为未来6-12个月Agent系统演进的指导性文档，每2周review一次进度并根据实际情况调整优先级。*
# Plan: 清理 VSCode Plugin 版本兼容残留 API 并更新审查文档

## 背景与目标

对 `packages/vscode_plugin/` 进行全面清理，移除历史上为版本兼容而保留的各类带版本号后缀的 API（V2/V2a/V3/Legacy 等）。作为个人版仅保留最新可用实现，消除技术债务，并同步更新 `doc/design/vscode_plugin/vscode_plugin_review.md`。

---

## 一、现状分析：待清理的版本化 API 清单

### 1.1 Workspace 双版本（P0）
| 文件/类 | 版本后缀 | 说明 |
|---------|---------|------|
| `src/workspacev2.ts` | v2 | 旧版 `DWorkspace` 类，仅存一处被 `extension.ts` import |
| `src/workspace.ts` | V2 | 新版 `DWorkspaceV2` + `SailExtension`，但含大量 `@deprecated` 静态方法 |

**结论**: `workspacev2.ts` 是真正的旧版本，可直接删除并将 `extension.ts` 的引用迁移到 `workspace.ts` 的导出。`workspace.ts` 本身是当前主实现，保留但清理其 `@deprecated` 静态方法。

### 1.2 WSUtils V2（P1）
| 文件 | 版本后缀 | 引用次数 |
|------|---------|---------|
| `src/WSUtilsV2.ts` | V2 | ~30 处直接实例化/调用 |
| `src/WSUtilsV2Interface.ts` | V2 | 被 `sailExtensionInterface.ts`、`ExtensionProvider.ts`、`GotoNote.ts` 等 import |

**结论**: 不存在非 V2 版本，`WSUtilsV2` 就是当前唯一实现。应重命名为 `WSUtils` / `IWSUtils`，删除 V2 后缀。

### 1.3 Lookup 系统 V3（P1）
| 文件 | 版本后缀 | 说明 |
|------|---------|------|
| `src/components/lookup/LookupControllerV3.ts` | V3 | 控制器实现 |
| `src/components/lookup/LookupControllerV3Factory.ts` | V3 | 工厂 |
| `src/components/lookup/LookupControllerV3Interface.ts` | V3 | 接口定义 |
| `src/components/lookup/LookupProviderV3Factory.ts` | V3 | Provider 工厂 |
| `src/components/lookup/LookupProviderV3Interface.ts` | V3 | Provider 接口 |
| `src/components/lookup/LookupControllerV3CreateOpts` | V3 | 类型别名 |
| `src/components/views/LookupV3QuickPickView.ts` | V3 | 视图包装 |

**结论**: 不存在 V1/V2 版本，V3 就是当前唯一实现。全部去版本号重命名。

### 1.4 Rename / Refactor V2/V2a（P1）
| 文件 | 版本后缀 | 说明 |
|------|---------|------|
| `src/commands/RenameNoteV2a.ts` | V2a | 内部重命名命令，未在 `ALL_COMMANDS` 注册，被 `RenameProvider.ts` 和 `RefactorHierarchyV2.ts` 使用 |
| `src/commands/RefactorHierarchyV2.ts` | V2 | 层级重构命令，在 `ALL_COMMANDS` 中注册 |
| `src/constants.ts` | V2A / V2 | `RENAME_NOTE_V2A`、`REFACTOR_HIERARCHY` 命令常量 |

**结论**: `RenameNoteV2a` 是内部实现，不应暴露 V2a 后缀；`RefactorHierarchyV2` 是当前唯一重构实现。考虑将 V2a 逻辑合并到 `RenameNoteCommand.ts` 或重命名为内部 `RenameNoteInternalCommand`。`RefactorHierarchyCommandV2` 重命名为 `RefactorHierarchyCommand`。

### 1.5 PickerUtils V2（P1）
| 文件 | 版本后缀 | 引用次数 |
|------|---------|---------|
| `src/components/lookup/utils.ts` 中的 `PickerUtilsV2` | V2 | ~40 处 |

**结论**: 唯一实现，重命名为 `PickerUtils`。

### 1.6 ClientUtils V2（P1）
| 文件 | 版本后缀 | 引用次数 |
|------|---------|---------|
| `src/clientUtils.ts` 中的 `SailClientUtilsV2` | V2 | ~10 处 |

**结论**: 唯一实现，重命名为 `ClientUtils` 或 `SailClientUtils`。

### 1.7 common-all 中的版本化类型（P1，跨包）
| 符号 | 位置 | 影响范围 |
|------|------|---------|
| `VaultUtilsV2` | `packages/common-all/src/VaultUtilsV2.ts` | 被 `vault.ts` 和 vscode_plugin 引用 |
| `DNodePropsQuickInputV2` | `packages/common-all/src/types/typesv2.ts` | 被 lookup/utils.ts、RefactorHierarchyV2.ts 等大量引用 |
| `NoteQuickInputV2` | `packages/common-all/src/types/typesv2.ts` | 被 lookup/utils.ts 引用 |
| `SailQuickPickItemV2` / `SailQuickPickerV2` | `packages/vscode_plugin/src/components/lookup/types.ts` | 本地类型 |
| `RespV2` / `RespV3` | `packages/common-all/src/types/typesv2.ts` | 引擎响应类型，改动影响面大 |

**结论**: `VaultUtilsV2` 应合并到 `VaultUtils` 或重命名。`DNodePropsQuickInputV2` 和 `NoteQuickInputV2` 是当前唯一输入类型，应去版本号。`RespV2` 已标记 `TODO: remove`，可安全删除；`RespV3` 是当前主力响应类型，但由于涉及整个引擎 API，本次计划先保留 `RespV3` 名称（否则改动面过大），或至少不在本次范围内重命名。

### 1.8 其他已废弃/可移除模块（P2）
| 文件/目录 | 说明 |
|-----------|------|
| `src/services/stateService.ts` | 整个类 `@deprecated`，建议合并到 MetadataService |
| `src/versionProvider.ts` | `@deprecated` |
| `src/commands/Refactor.ts` | `LegacyRefactorCommand`，含危险 `process.exit(0)` |
| `src/commands/ShowLegacyPreview.ts` | Legacy 预览 |
| `src/commands/SignIn.ts`, `SignUp.ts` | Sail 云端账户 |
| `src/commands/PublishDevCommand.ts` | Sail 发布 |
| `src/commands/SeedAddCommand.ts` 等 | Seed 注册表 |
| `src/commands/ShowWelcomePageCommand.ts` 等 | 新用户引导 |
| `src/commands/CopyCodespaceURL.ts` | Codespaces 专用 |
| `src/commands/MigrateSelfContainedVault.ts`, `RunMigrationCommand.ts` | 数据迁移 |
| `src/commands/InstrumentedWrapperCommand.ts` | 遥测包装 |
| `src/web/` | 完整 Web 版平行实现（~32 文件）|
| `src/telemetry/` | 遥测系统 |
| `src/showcase/` | 功能展示提示 |

**结论**: 这些不是“版本兼容”API，而是“个人版不需要的功能”。虽然用户主要要求是清理版本兼容 API，但作为个人版整理，应在计划中明确这些也在清理范围内，或至少分阶段处理。本次计划将它们纳入第二轮（模块移除轮）。

---

## 二、执行阶段

### Phase 0: 前置准备
- [ ] **P0-1** 创建独立分支（如 `cleanup/versioned-apis`）
- [ ] **P0-2** 确保当前构建通过：`pnpm run build-plugin`
- [ ] **P0-3** 确保测试通过：`pnpm test`（至少 vscode_plugin 相关测试）
- [ ] **P0-4** 备份当前 `doc/design/vscode_plugin/vscode_plugin_review.md`

### Phase 1: Workspace 旧版移除（最小改动，建立信心）
- [ ] **P1-1** 检查 `src/extension.ts` 对 `workspacev2.ts` 的 import：`import { DWorkspace } from "./workspacev2";`
- [ ] **P1-2** 将 `workspace.ts` 中 `DWorkspaceV2` 类型同时以 `DWorkspace` 别名 export（或在 `extension.ts` 直接改为 import `DWorkspaceV2` 并 rename）
- [ ] **P1-3** 删除 `src/workspacev2.ts`
- [ ] **P1-4** 验证构建：`pnpm run build-plugin`
- [ ] **P1-5** 提交该阶段改动

### Phase 2: WSUtils / Lookup / PickerUtils / ClientUtils 去版本号（核心重命名）

此阶段采用“文件重命名 + 类/接口重命名 + 批量替换引用”的三步法。

#### 2.1 WSUtils 去 V2
- [ ] **P2.1-1** 重命名文件：`WSUtilsV2Interface.ts` → `WSUtilsInterface.ts`
- [ ] **P2.1-2** 重命名文件：`WSUtilsV2.ts` → `WSUtils.ts`
- [ ] **P2.1-3** 在 `WSUtilsInterface.ts` 中：`IWSUtilsV2` → `IWSUtils`
- [ ] **P2.1-4** 在 `WSUtils.ts` 中：`WSUtilsV2` → `WSUtils`，更新内部 `IWSUtilsV2` import
- [ ] **P2.1-5** 全局替换所有 import 和引用（`IWSUtilsV2` → `IWSUtils`, `WSUtilsV2` → `WSUtils`）
- [ ] **P2.1-6** 更新 `sailExtensionInterface.ts` 中的 `wsUtils: IWSUtilsV2` → `wsUtils: IWSUtils`
- [ ] **P2.1-7** 更新 `workspace.ts` 中的 `new WSUtilsV2(this)` → `new WSUtils(this)`

#### 2.2 Lookup 系统去 V3
- [ ] **P2.2-1** 重命名文件（6 个文件）：
  - `LookupControllerV3.ts` → `LookupController.ts`
  - `LookupControllerV3Factory.ts` → `LookupControllerFactory.ts`
  - `LookupControllerV3Interface.ts` → `LookupControllerInterface.ts`
  - `LookupProviderV3Factory.ts` → `LookupProviderFactory.ts`
  - `LookupProviderV3Interface.ts` → `LookupProviderInterface.ts`
  - `views/LookupV3QuickPickView.ts` → `views/LookupQuickPickView.ts`
- [ ] **P2.2-2** 在每个文件中重命名类/接口/类型：
  - `LookupControllerV3` → `LookupController`
  - `ILookupControllerV3` → `ILookupController`
  - `ILookupControllerV3Factory` → `ILookupControllerFactory`
  - `LookupControllerV3CreateOpts` → `LookupControllerCreateOpts`
  - `ILookupProviderV3` → `ILookupProvider`
  - `ILookupProviderOptsV3` → `ILookupProviderOpts`
  - `LookupProviderV3Factory` → `LookupProviderFactory`
  - `LookupV3QuickPickView` → `LookupQuickPickView`
- [ ] **P2.2-3** 全局替换所有 import 和引用（可使用 IDE 重构或批量文本替换）
- [ ] **P2.2-4** 更新 `sailExtensionInterface.ts`、`workspace.ts`、所有 commands 和 components 中的 import

#### 2.3 PickerUtils 去 V2
- [ ] **P2.3-1** 在 `src/components/lookup/utils.ts` 中：`PickerUtilsV2` → `PickerUtils`
- [ ] **P2.3-2** 全局替换所有 `PickerUtilsV2` 引用

#### 2.4 SailClientUtils 去 V2
- [ ] **P2.4-1** 在 `src/clientUtils.ts` 中：`SailClientUtilsV2` → `SailClientUtils`
- [ ] **P2.4-2** 全局替换所有 `SailClientUtilsV2` 引用

#### 2.5 common-all 类型去 V2（跨包协调）
- [ ] **P2.5-1** `packages/common-all/src/types/typesv2.ts`：
  - `DNodePropsQuickInputV2<T>` → `DNodePropsQuickInput<T>`
  - `NoteQuickInputV2` → `NoteQuickInput`（注意已存在 `NoteQuickInput`，需确认是否冲突）
- [ ] **P2.5-2** `packages/common-all/src/dnode.ts`：更新导出函数返回类型
- [ ] **P2.5-3** `packages/common-all/src/index.ts`：更新 re-export
- [ ] **P2.5-4** `packages/common-all/src/VaultUtilsV2.ts`：
  - 将 `VaultUtilsV2` 的静态方法合并到 `VaultUtils`（如果 `VaultUtils` 无同名方法）
  - 或重命名 `VaultUtilsV2` → `VaultUtilsURI`（因为其设计目标是 URI 兼容）
  - 更新所有引用
- [ ] **P2.5-5** `packages/vscode_plugin/src/components/lookup/types.ts`：
  - `SailQuickPickItemV2` → `SailQuickPickItem`
  - `SailQuickPickerV2` → `SailQuickPicker`

#### 2.6 Rename / Refactor 去版本号
- [ ] **P2.6-1** `src/commands/RenameNoteV2a.ts`：
  - 重命名为 `src/commands/RenameNoteInternal.ts`
  - `RenameNoteV2aCommand` → `RenameNoteInternalCommand`
  - `RenameNoteOutputV2a` → `RenameNoteOutput`
  - 更新 `constants.ts` 中的 `RENAME_NOTE_V2A` → `RENAME_NOTE_INTERNAL`（或直接从常量中移除，因为它不在 ALL_COMMANDS 中）
- [ ] **P2.6-2** `src/commands/RefactorHierarchyV2.ts`：
  - 重命名为 `src/commands/RefactorHierarchy.ts`
  - `RefactorHierarchyCommandV2` → `RefactorHierarchyCommand`
  - 更新 `constants.ts` 中的 key（如果 key 含 V2 字样则更新）
  - 更新 `commands/index.ts` 中的 import 和 `ALL_COMMANDS`
  - 更新 `commands/ArchiveHierarchy.ts` 中对 `RefactorHierarchyV2CommandOutput` 的引用
- [ ] **P2.6-3** `src/features/RenameProvider.ts`：更新对 `RenameNoteV2aCommand` 的引用

#### 2.7 构建与验证
- [ ] **P2.7-1** 构建 common-all：`pnpm run build:common-all`
- [ ] **P2.7-2** 构建 engine-server：`pnpm run build-with-deps @saili/engine-server`
- [ ] **P2.7-3** 构建 vscode_plugin：`pnpm run build-plugin`
- [ ] **P2.7-4** 运行测试：`pnpm test`
- [ ] **P2.7-5** 提交该阶段改动

### Phase 3: 废弃模块与冗余命令移除（个人版裁剪）

#### 3.1 移除已废弃服务
- [ ] **P3.1-1** 分析 `services/stateService.ts` 的所有引用，将逻辑迁移到 `MetadataService` 或直接内联
- [ ] **P3.1-2** 删除 `services/stateService.ts`
- [ ] **P3.1-3** 删除 `versionProvider.ts`，将其引用改为 `vscode.ExtensionContext.extension.packageJSON.version`

#### 3.2 移除 Sail 专属 / 个人版不需要的命令
以下命令从 `src/commands/`、`commands/index.ts` 的 `ALL_COMMANDS`、`constants.ts` 的 `SAIL_COMMANDS`、`package.json` 的 `contributes.commands` 和 `contributes.menus` 中一并移除：

| 命令文件 | 命令常量 key |
|---------|-------------|
| `Refactor.ts` | `LEGACY_REFACTOR` |
| `ShowLegacyPreview.ts` | `SHOW_LEGACY_PREVIEW` |
| `SignIn.ts` | `SIGN_IN` |
| `SignUp.ts` | `SIGN_UP` |
| `PublishDevCommand.ts` | `PUBLISH_DEV` |
| `SeedAddCommand.ts` | `SEED_ADD` |
| `SeedBrowseCommand.ts` | `SEED_BROWSE` |
| `SeedRemoveCommand.ts` | `SEED_REMOVE` |
| `ShowWelcomePageCommand.ts` | `SHOW_WELCOME_PAGE` |
| `LaunchTutorialWorkspaceCommand.ts` | `LAUNCH_TUTORIAL_WORKSPACE` |
| `CopyCodespaceURL.ts` | `COPY_CODESPACE_URL` |
| `MigrateSelfContainedVault.ts` | `MIGRATE_SELF_CONTAINED_VAULT` |
| `RunMigrationCommand.ts` | `RUN_MIGRATION` |
| `InstrumentedWrapperCommand.ts` | 遥测包装 |

- [ ] **P3.2-1** 逐个删除上述命令文件
- [ ] **P3.2-2** 从 `commands/index.ts` 的 `ALL_COMMANDS` 中移除对应 import 和数组项
- [ ] **P3.2-3** 从 `constants.ts` 中删除对应命令常量定义
- [ ] **P3.2-4** 从 `package.json` 中删除对应 `contributes.commands` 和 `contributes.menus` 项
- [ ] **P3.2-5** 清理这些命令在 `_extension.ts` 或其他文件中的残留引用

#### 3.3 Web 版平行实现决策与移除
- [ ] **P3.3-1** 确认个人版确实不需要 Web 版 VSCode 支持
- [ ] **P3.3-2** 删除 `src/web/` 整个目录（~32 文件）
- [ ] **P3.3-3** 删除 `src/services/web/TextDocumentService.ts`（如果存在）
- [ ] **P3.3-4** 从 `package.json` 中移除 `browser` 入口字段
- [ ] **P3.3-5** 移除 `tsyringe` 依赖（如果仅 Web 版使用）

#### 3.4 遥测与 Showcase 系统移除
- [ ] **P3.4-1** 删除 `src/telemetry/` 目录
- [ ] **P3.4-2** 删除 `src/utils/ProxyMetricUtils.ts`、`src/utils/MeetingTelemHelper.ts`
- [ ] **P3.4-3** 删除 `src/showcase/` 目录
- [ ] **P3.4-4** 清理 `_extension.ts` 中遥测和 showcase 的初始化逻辑

#### 3.5 构建与验证
- [ ] **P3.5-1** `pnpm run build-plugin`
- [ ] **P3.5-2** `pnpm test`
- [ ] **P3.5-3** 提交该阶段改动

### Phase 4: 细节清理与危险代码修复
- [ ] **P4-1** 清理 `src/workspace.ts` 中的 `@deprecated` 静态方法（`getDWorkspace()`、`getExtension()`、`getEngine()` 等），确认所有引用已迁移到 `ExtensionProvider`
- [ ] **P4-2** 修复 `src/commands/Refactor.ts` 中的 `process.exit(0)`（虽然文件会被删除，但如果决定保留则需修复；按 3.2 计划应已删除）
- [ ] **P4-3** 修复 `src/utils/ExtensionUtils.ts` 第 145 行 `sail.sail-sail` 错误
- [ ] **P4-4** 重命名 `web/injection-providers/getEnablePrettlyLinks.ts` → `getEnablePrettyLinks.ts`（如 Web 目录未删除）；如果 Web 已删除则跳过
- [ ] **P4-5** 清理 `views/utils.ts` 中的 `@deprecated` 方法
- [ ] **P4-6** 更新日志文件名：`sail.log` → `sailzen.log`，`sail.server.log` → `sailzen.server.log`
- [ ] **P4-7** 构建验证并提交

### Phase 5: 更新审查文档
- [ ] **P5-1** 在 `doc/design/vscode_plugin/vscode_plugin_review.md` 中：
  - 更新“生成日期”为当前日期
  - 在 **2. 债务清单** 中，将已清理的债务项标记为 ✅ 已清理，并注明清理日期/PR
  - 新增一节“5. 版本兼容 API 清理记录”，记录：
    - 已删除的文件清单（workspacev2.ts、ShowLegacyPreview.ts 等）
    - 已重命名的类/接口清单（WSUtilsV2→WSUtils、LookupControllerV3→LookupController 等）
    - 已移除的命令清单（SignIn、SeedAdd 等）
    - common-all 中的改动（DNodePropsQuickInputV2→DNodePropsQuickInput 等）
  - 更新 **3. 后续重构计划**，将已完成项标记为完成，调整剩余项优先级
  - 更新 **附录：关键文件速查表**，删除已不存在的文件路径，更新重命名后的路径
- [ ] **P5-2** 检查文档中是否还有对 `sail.` 前缀命令/视图的引用，同步更新为 `sailzen.`（如 3.1 轮计划中的命名统一已部分完成，需在文档中反映）
- [ ] **P5-3** 将文档末尾的“建议将此报告与 `doc/refact_todo.md` 和 `doc/sailzen-3.0-roadmap.md` 交叉参考”更新为包含本轮清理的对应条目

### Phase 6: 最终验证与收尾
- [ ] **P6-1** 全量构建：`pnpm run build-plugin`
- [ ] **P6-2** 运行所有相关测试
- [ ] **P6-3** 手动验证核心功能：Lookup、笔记创建、重命名、编译文档等
- [ ] **P6-4** 检查 `git diff --stat`，确认改动范围符合预期
- [ ] **P6-5** 生成 patch 文件（根据项目约束，使用 `git format-patch`）
- [ ] **P6-6** 提交最终 commit，message 示例：`cleanup(vscode-plugin): remove versioned APIs and legacy commands for personal edition`

---

## 三、风险与回滚策略

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 全局重命名引入编译错误 | 高 | 每完成一组重命名立即构建；使用 IDE 重构而非纯文本替换 |
| 删除命令后 `package.json` 残留 | 中 | 清理脚本：搜索 `package.json` 中已删除命令的 key |
| common-all 改动导致其他包中断 | 高 | 按依赖顺序构建：`common-all` → `common-server`/`unified` → `engine-server` → `vscode_plugin` |
| 测试失败难以定位 | 中 | 分阶段提交，每阶段独立验证，方便 `git bisect` |
| Web 版删除后发现仍有引用 | 中 | 删除前全局搜索 `from "../web/` 或 `from "./web/`，确保无 Node 代码引用 Web 模块 |

**回滚策略**: 所有改动在独立分支进行，每 Phase 结束为一个 commit。若某 Phase 失败，可单独 revert 该 commit。

---

## 四、预计工作量

| 阶段 | 预计耗时 | 说明 |
|------|---------|------|
| Phase 0 | 15 min | 分支、构建、备份 |
| Phase 1 | 30 min | workspacev2 删除 |
| Phase 2 | 3-4 h | 核心重命名，最耗时 |
| Phase 3 | 2-3 h | 模块移除 |
| Phase 4 | 1 h | 细节清理 |
| Phase 5 | 1-2 h | 文档更新 |
| Phase 6 | 30 min | 验证、提交 |
| **总计** | **~8-10 h** | 可分 2-3 天完成 |

---

## 五、关键文件变更索引

### 将被删除的文件
```
packages/vscode_plugin/src/workspacev2.ts
packages/vscode_plugin/src/services/stateService.ts
packages/vscode_plugin/src/versionProvider.ts
packages/vscode_plugin/src/commands/Refactor.ts
packages/vscode_plugin/src/commands/ShowLegacyPreview.ts
packages/vscode_plugin/src/commands/SignIn.ts
packages/vscode_plugin/src/commands/SignUp.ts
packages/vscode_plugin/src/commands/PublishDevCommand.ts
packages/vscode_plugin/src/commands/SeedAddCommand.ts
packages/vscode_plugin/src/commands/SeedBrowseCommand.ts
packages/vscode_plugin/src/commands/SeedRemoveCommand.ts
packages/vscode_plugin/src/commands/ShowWelcomePageCommand.ts
packages/vscode_plugin/src/commands/LaunchTutorialWorkspaceCommand.ts
packages/vscode_plugin/src/commands/CopyCodespaceURL.ts
packages/vscode_plugin/src/commands/MigrateSelfContainedVault.ts
packages/vscode_plugin/src/commands/RunMigrationCommand.ts
packages/vscode_plugin/src/commands/InstrumentedWrapperCommand.ts
packages/vscode_plugin/src/web/                  (整个目录)
packages/vscode_plugin/src/telemetry/            (整个目录)
packages/vscode_plugin/src/showcase/             (整个目录)
packages/vscode_plugin/src/utils/ProxyMetricUtils.ts
packages/vscode_plugin/src/utils/MeetingTelemHelper.ts
```

### 将被重命名的文件
```
WSUtilsV2.ts                  → WSUtils.ts
WSUtilsV2Interface.ts         → WSUtilsInterface.ts
LookupControllerV3.ts         → LookupController.ts
LookupControllerV3Factory.ts  → LookupControllerFactory.ts
LookupControllerV3Interface.ts→ LookupControllerInterface.ts
LookupProviderV3Factory.ts    → LookupProviderFactory.ts
LookupProviderV3Interface.ts  → LookupProviderInterface.ts
views/LookupV3QuickPickView.ts→ views/LookupQuickPickView.ts
commands/RenameNoteV2a.ts     → commands/RenameNoteInternal.ts
commands/RefactorHierarchyV2.ts→ commands/RefactorHierarchy.ts
```

### 将被修改的核心文件
```
packages/vscode_plugin/src/extension.ts
packages/vscode_plugin/src/_extension.ts
packages/vscode_plugin/src/workspace.ts
packages/vscode_plugin/src/sailExtensionInterface.ts
packages/vscode_plugin/src/ExtensionProvider.ts
packages/vscode_plugin/src/constants.ts
packages/vscode_plugin/src/commands/index.ts
packages/vscode_plugin/src/package.json
packages/common-all/src/types/typesv2.ts
packages/common-all/src/dnode.ts
packages/common-all/src/VaultUtilsV2.ts
packages/common-all/src/index.ts
packages/vscode_plugin/src/components/lookup/types.ts
packages/vscode_plugin/src/clientUtils.ts
packages/vscode_plugin/src/components/lookup/utils.ts
```

---

*Plan generated based on analysis of packages/vscode_plugin/src/ and common-all/ as of current HEAD.*
<<<<<<< HEAD
# Plan: 清理 VSCode Plugin 版本兼容残留 API 并更新审查文档

## 背景与目标

对 `packages/vscode_plugin/` 进行全面清理，移除历史上为版本兼容而保留的各类带版本号后缀的 API（V2/V2a/V3/Legacy 等）。作为个人版仅保留最新可用实现，消除技术债务，并同步更新 `doc/design/vscode_plugin/vscode_plugin_review.md`。

---

## 一、现状分析：待清理的版本化 API 清单

### 1.1 Workspace 双版本（P0）
| 文件/类 | 版本后缀 | 说明 |
|---------|---------|------|
| `src/workspacev2.ts` | v2 | 旧版 `DWorkspace` 类，仅存一处被 `extension.ts` import |
| `src/workspace.ts` | V2 | 新版 `DWorkspaceV2` + `SailExtension`，但含大量 `@deprecated` 静态方法 |

**结论**: `workspacev2.ts` 是真正的旧版本，可直接删除并将 `extension.ts` 的引用迁移到 `workspace.ts` 的导出。`workspace.ts` 本身是当前主实现，保留但清理其 `@deprecated` 静态方法。

### 1.2 WSUtils V2（P1）
| 文件 | 版本后缀 | 引用次数 |
|------|---------|---------|
| `src/WSUtilsV2.ts` | V2 | ~30 处直接实例化/调用 |
| `src/WSUtilsV2Interface.ts` | V2 | 被 `sailExtensionInterface.ts`、`ExtensionProvider.ts`、`GotoNote.ts` 等 import |

**结论**: 不存在非 V2 版本，`WSUtilsV2` 就是当前唯一实现。应重命名为 `WSUtils` / `IWSUtils`，删除 V2 后缀。

### 1.3 Lookup 系统 V3（P1）
| 文件 | 版本后缀 | 说明 |
|------|---------|------|
| `src/components/lookup/LookupControllerV3.ts` | V3 | 控制器实现 |
| `src/components/lookup/LookupControllerV3Factory.ts` | V3 | 工厂 |
| `src/components/lookup/LookupControllerV3Interface.ts` | V3 | 接口定义 |
| `src/components/lookup/LookupProviderV3Factory.ts` | V3 | Provider 工厂 |
| `src/components/lookup/LookupProviderV3Interface.ts` | V3 | Provider 接口 |
| `src/components/lookup/LookupControllerV3CreateOpts` | V3 | 类型别名 |
| `src/components/views/LookupV3QuickPickView.ts` | V3 | 视图包装 |

**结论**: 不存在 V1/V2 版本，V3 就是当前唯一实现。全部去版本号重命名。

### 1.4 Rename / Refactor V2/V2a（P1）
| 文件 | 版本后缀 | 说明 |
|------|---------|------|
| `src/commands/RenameNoteV2a.ts` | V2a | 内部重命名命令，未在 `ALL_COMMANDS` 注册，被 `RenameProvider.ts` 和 `RefactorHierarchyV2.ts` 使用 |
| `src/commands/RefactorHierarchyV2.ts` | V2 | 层级重构命令，在 `ALL_COMMANDS` 中注册 |
| `src/constants.ts` | V2A / V2 | `RENAME_NOTE_V2A`、`REFACTOR_HIERARCHY` 命令常量 |

**结论**: `RenameNoteV2a` 是内部实现，不应暴露 V2a 后缀；`RefactorHierarchyV2` 是当前唯一重构实现。考虑将 V2a 逻辑合并到 `RenameNoteCommand.ts` 或重命名为内部 `RenameNoteInternalCommand`。`RefactorHierarchyCommandV2` 重命名为 `RefactorHierarchyCommand`。

### 1.5 PickerUtils V2（P1）
| 文件 | 版本后缀 | 引用次数 |
|------|---------|---------|
| `src/components/lookup/utils.ts` 中的 `PickerUtilsV2` | V2 | ~40 处 |

**结论**: 唯一实现，重命名为 `PickerUtils`。

### 1.6 ClientUtils V2（P1）
| 文件 | 版本后缀 | 引用次数 |
|------|---------|---------|
| `src/clientUtils.ts` 中的 `SailClientUtilsV2` | V2 | ~10 处 |

**结论**: 唯一实现，重命名为 `ClientUtils` 或 `SailClientUtils`。

### 1.7 common-all 中的版本化类型（P1，跨包）
| 符号 | 位置 | 影响范围 |
|------|------|---------|
| `VaultUtilsV2` | `packages/common-all/src/VaultUtilsV2.ts` | 被 `vault.ts` 和 vscode_plugin 引用 |
| `DNodePropsQuickInputV2` | `packages/common-all/src/types/typesv2.ts` | 被 lookup/utils.ts、RefactorHierarchyV2.ts 等大量引用 |
| `NoteQuickInputV2` | `packages/common-all/src/types/typesv2.ts` | 被 lookup/utils.ts 引用 |
| `SailQuickPickItemV2` / `SailQuickPickerV2` | `packages/vscode_plugin/src/components/lookup/types.ts` | 本地类型 |
| `RespV2` / `RespV3` | `packages/common-all/src/types/typesv2.ts` | 引擎响应类型，改动影响面大 |

**结论**: `VaultUtilsV2` 应合并到 `VaultUtils` 或重命名。`DNodePropsQuickInputV2` 和 `NoteQuickInputV2` 是当前唯一输入类型，应去版本号。`RespV2` 已标记 `TODO: remove`，可安全删除；`RespV3` 是当前主力响应类型，但由于涉及整个引擎 API，本次计划先保留 `RespV3` 名称（否则改动面过大），或至少不在本次范围内重命名。

### 1.8 其他已废弃/可移除模块（P2）
| 文件/目录 | 说明 |
|-----------|------|
| `src/services/stateService.ts` | 整个类 `@deprecated`，建议合并到 MetadataService |
| `src/versionProvider.ts` | `@deprecated` |
| `src/commands/Refactor.ts` | `LegacyRefactorCommand`，含危险 `process.exit(0)` |
| `src/commands/ShowLegacyPreview.ts` | Legacy 预览 |
| `src/commands/SignIn.ts`, `SignUp.ts` | Sail 云端账户 |
| `src/commands/PublishDevCommand.ts` | Sail 发布 |
| `src/commands/SeedAddCommand.ts` 等 | Seed 注册表 |
| `src/commands/ShowWelcomePageCommand.ts` 等 | 新用户引导 |
| `src/commands/CopyCodespaceURL.ts` | Codespaces 专用 |
| `src/commands/MigrateSelfContainedVault.ts`, `RunMigrationCommand.ts` | 数据迁移 |
| `src/commands/InstrumentedWrapperCommand.ts` | 遥测包装 |
| `src/web/` | 完整 Web 版平行实现（~32 文件）|
| `src/telemetry/` | 遥测系统 |
| `src/showcase/` | 功能展示提示 |

**结论**: 这些不是“版本兼容”API，而是“个人版不需要的功能”。虽然用户主要要求是清理版本兼容 API，但作为个人版整理，应在计划中明确这些也在清理范围内，或至少分阶段处理。本次计划将它们纳入第二轮（模块移除轮）。

---

## 二、执行阶段

### Phase 0: 前置准备
- [ ] **P0-1** 创建独立分支（如 `cleanup/versioned-apis`）
- [ ] **P0-2** 确保当前构建通过：`pnpm run build-plugin`
- [ ] **P0-3** 确保测试通过：`pnpm test`（至少 vscode_plugin 相关测试）
- [ ] **P0-4** 备份当前 `doc/design/vscode_plugin/vscode_plugin_review.md`

### Phase 1: Workspace 旧版移除（最小改动，建立信心）
- [ ] **P1-1** 检查 `src/extension.ts` 对 `workspacev2.ts` 的 import：`import { DWorkspace } from "./workspacev2";`
- [ ] **P1-2** 将 `workspace.ts` 中 `DWorkspaceV2` 类型同时以 `DWorkspace` 别名 export（或在 `extension.ts` 直接改为 import `DWorkspaceV2` 并 rename）
- [ ] **P1-3** 删除 `src/workspacev2.ts`
- [ ] **P1-4** 验证构建：`pnpm run build-plugin`
- [ ] **P1-5** 提交该阶段改动

### Phase 2: WSUtils / Lookup / PickerUtils / ClientUtils 去版本号（核心重命名）

此阶段采用“文件重命名 + 类/接口重命名 + 批量替换引用”的三步法。

#### 2.1 WSUtils 去 V2
- [ ] **P2.1-1** 重命名文件：`WSUtilsV2Interface.ts` → `WSUtilsInterface.ts`
- [ ] **P2.1-2** 重命名文件：`WSUtilsV2.ts` → `WSUtils.ts`
- [ ] **P2.1-3** 在 `WSUtilsInterface.ts` 中：`IWSUtilsV2` → `IWSUtils`
- [ ] **P2.1-4** 在 `WSUtils.ts` 中：`WSUtilsV2` → `WSUtils`，更新内部 `IWSUtilsV2` import
- [ ] **P2.1-5** 全局替换所有 import 和引用（`IWSUtilsV2` → `IWSUtils`, `WSUtilsV2` → `WSUtils`）
- [ ] **P2.1-6** 更新 `sailExtensionInterface.ts` 中的 `wsUtils: IWSUtilsV2` → `wsUtils: IWSUtils`
- [ ] **P2.1-7** 更新 `workspace.ts` 中的 `new WSUtilsV2(this)` → `new WSUtils(this)`

#### 2.2 Lookup 系统去 V3
- [ ] **P2.2-1** 重命名文件（6 个文件）：
  - `LookupControllerV3.ts` → `LookupController.ts`
  - `LookupControllerV3Factory.ts` → `LookupControllerFactory.ts`
  - `LookupControllerV3Interface.ts` → `LookupControllerInterface.ts`
  - `LookupProviderV3Factory.ts` → `LookupProviderFactory.ts`
  - `LookupProviderV3Interface.ts` → `LookupProviderInterface.ts`
  - `views/LookupV3QuickPickView.ts` → `views/LookupQuickPickView.ts`
- [ ] **P2.2-2** 在每个文件中重命名类/接口/类型：
  - `LookupControllerV3` → `LookupController`
  - `ILookupControllerV3` → `ILookupController`
  - `ILookupControllerV3Factory` → `ILookupControllerFactory`
  - `LookupControllerV3CreateOpts` → `LookupControllerCreateOpts`
  - `ILookupProviderV3` → `ILookupProvider`
  - `ILookupProviderOptsV3` → `ILookupProviderOpts`
  - `LookupProviderV3Factory` → `LookupProviderFactory`
  - `LookupV3QuickPickView` → `LookupQuickPickView`
- [ ] **P2.2-3** 全局替换所有 import 和引用（可使用 IDE 重构或批量文本替换）
- [ ] **P2.2-4** 更新 `sailExtensionInterface.ts`、`workspace.ts`、所有 commands 和 components 中的 import

#### 2.3 PickerUtils 去 V2
- [ ] **P2.3-1** 在 `src/components/lookup/utils.ts` 中：`PickerUtilsV2` → `PickerUtils`
- [ ] **P2.3-2** 全局替换所有 `PickerUtilsV2` 引用

#### 2.4 SailClientUtils 去 V2
- [ ] **P2.4-1** 在 `src/clientUtils.ts` 中：`SailClientUtilsV2` → `SailClientUtils`
- [ ] **P2.4-2** 全局替换所有 `SailClientUtilsV2` 引用

#### 2.5 common-all 类型去 V2（跨包协调）
- [ ] **P2.5-1** `packages/common-all/src/types/typesv2.ts`：
  - `DNodePropsQuickInputV2<T>` → `DNodePropsQuickInput<T>`
  - `NoteQuickInputV2` → `NoteQuickInput`（注意已存在 `NoteQuickInput`，需确认是否冲突）
- [ ] **P2.5-2** `packages/common-all/src/dnode.ts`：更新导出函数返回类型
- [ ] **P2.5-3** `packages/common-all/src/index.ts`：更新 re-export
- [ ] **P2.5-4** `packages/common-all/src/VaultUtilsV2.ts`：
  - 将 `VaultUtilsV2` 的静态方法合并到 `VaultUtils`（如果 `VaultUtils` 无同名方法）
  - 或重命名 `VaultUtilsV2` → `VaultUtilsURI`（因为其设计目标是 URI 兼容）
  - 更新所有引用
- [ ] **P2.5-5** `packages/vscode_plugin/src/components/lookup/types.ts`：
  - `SailQuickPickItemV2` → `SailQuickPickItem`
  - `SailQuickPickerV2` → `SailQuickPicker`

#### 2.6 Rename / Refactor 去版本号
- [ ] **P2.6-1** `src/commands/RenameNoteV2a.ts`：
  - 重命名为 `src/commands/RenameNoteInternal.ts`
  - `RenameNoteV2aCommand` → `RenameNoteInternalCommand`
  - `RenameNoteOutputV2a` → `RenameNoteOutput`
  - 更新 `constants.ts` 中的 `RENAME_NOTE_V2A` → `RENAME_NOTE_INTERNAL`（或直接从常量中移除，因为它不在 ALL_COMMANDS 中）
- [ ] **P2.6-2** `src/commands/RefactorHierarchyV2.ts`：
  - 重命名为 `src/commands/RefactorHierarchy.ts`
  - `RefactorHierarchyCommandV2` → `RefactorHierarchyCommand`
  - 更新 `constants.ts` 中的 key（如果 key 含 V2 字样则更新）
  - 更新 `commands/index.ts` 中的 import 和 `ALL_COMMANDS`
  - 更新 `commands/ArchiveHierarchy.ts` 中对 `RefactorHierarchyV2CommandOutput` 的引用
- [ ] **P2.6-3** `src/features/RenameProvider.ts`：更新对 `RenameNoteV2aCommand` 的引用

#### 2.7 构建与验证
- [ ] **P2.7-1** 构建 common-all：`pnpm run build:common-all`
- [ ] **P2.7-2** 构建 engine-server：`pnpm run build-with-deps @saili/engine-server`
- [ ] **P2.7-3** 构建 vscode_plugin：`pnpm run build-plugin`
- [ ] **P2.7-4** 运行测试：`pnpm test`
- [ ] **P2.7-5** 提交该阶段改动

### Phase 3: 废弃模块与冗余命令移除（个人版裁剪）

#### 3.1 移除已废弃服务
- [ ] **P3.1-1** 分析 `services/stateService.ts` 的所有引用，将逻辑迁移到 `MetadataService` 或直接内联
- [ ] **P3.1-2** 删除 `services/stateService.ts`
- [ ] **P3.1-3** 删除 `versionProvider.ts`，将其引用改为 `vscode.ExtensionContext.extension.packageJSON.version`

#### 3.2 移除 Sail 专属 / 个人版不需要的命令
以下命令从 `src/commands/`、`commands/index.ts` 的 `ALL_COMMANDS`、`constants.ts` 的 `SAIL_COMMANDS`、`package.json` 的 `contributes.commands` 和 `contributes.menus` 中一并移除：

| 命令文件 | 命令常量 key |
|---------|-------------|
| `Refactor.ts` | `LEGACY_REFACTOR` |
| `ShowLegacyPreview.ts` | `SHOW_LEGACY_PREVIEW` |
| `SignIn.ts` | `SIGN_IN` |
| `SignUp.ts` | `SIGN_UP` |
| `PublishDevCommand.ts` | `PUBLISH_DEV` |
| `SeedAddCommand.ts` | `SEED_ADD` |
| `SeedBrowseCommand.ts` | `SEED_BROWSE` |
| `SeedRemoveCommand.ts` | `SEED_REMOVE` |
| `ShowWelcomePageCommand.ts` | `SHOW_WELCOME_PAGE` |
| `LaunchTutorialWorkspaceCommand.ts` | `LAUNCH_TUTORIAL_WORKSPACE` |
| `CopyCodespaceURL.ts` | `COPY_CODESPACE_URL` |
| `MigrateSelfContainedVault.ts` | `MIGRATE_SELF_CONTAINED_VAULT` |
| `RunMigrationCommand.ts` | `RUN_MIGRATION` |
| `InstrumentedWrapperCommand.ts` | 遥测包装 |

- [ ] **P3.2-1** 逐个删除上述命令文件
- [ ] **P3.2-2** 从 `commands/index.ts` 的 `ALL_COMMANDS` 中移除对应 import 和数组项
- [ ] **P3.2-3** 从 `constants.ts` 中删除对应命令常量定义
- [ ] **P3.2-4** 从 `package.json` 中删除对应 `contributes.commands` 和 `contributes.menus` 项
- [ ] **P3.2-5** 清理这些命令在 `_extension.ts` 或其他文件中的残留引用

#### 3.3 Web 版平行实现决策与移除
- [ ] **P3.3-1** 确认个人版确实不需要 Web 版 VSCode 支持
- [ ] **P3.3-2** 删除 `src/web/` 整个目录（~32 文件）
- [ ] **P3.3-3** 删除 `src/services/web/TextDocumentService.ts`（如果存在）
- [ ] **P3.3-4** 从 `package.json` 中移除 `browser` 入口字段
- [ ] **P3.3-5** 移除 `tsyringe` 依赖（如果仅 Web 版使用）

#### 3.4 遥测与 Showcase 系统移除
- [ ] **P3.4-1** 删除 `src/telemetry/` 目录
- [ ] **P3.4-2** 删除 `src/utils/ProxyMetricUtils.ts`、`src/utils/MeetingTelemHelper.ts`
- [ ] **P3.4-3** 删除 `src/showcase/` 目录
- [ ] **P3.4-4** 清理 `_extension.ts` 中遥测和 showcase 的初始化逻辑

#### 3.5 构建与验证
- [ ] **P3.5-1** `pnpm run build-plugin`
- [ ] **P3.5-2** `pnpm test`
- [ ] **P3.5-3** 提交该阶段改动

### Phase 4: 细节清理与危险代码修复
- [ ] **P4-1** 清理 `src/workspace.ts` 中的 `@deprecated` 静态方法（`getDWorkspace()`、`getExtension()`、`getEngine()` 等），确认所有引用已迁移到 `ExtensionProvider`
- [ ] **P4-2** 修复 `src/commands/Refactor.ts` 中的 `process.exit(0)`（虽然文件会被删除，但如果决定保留则需修复；按 3.2 计划应已删除）
- [ ] **P4-3** 修复 `src/utils/ExtensionUtils.ts` 第 145 行 `sail.sail-sail` 错误
- [ ] **P4-4** 重命名 `web/injection-providers/getEnablePrettlyLinks.ts` → `getEnablePrettyLinks.ts`（如 Web 目录未删除）；如果 Web 已删除则跳过
- [ ] **P4-5** 清理 `views/utils.ts` 中的 `@deprecated` 方法
- [ ] **P4-6** 更新日志文件名：`sail.log` → `sailzen.log`，`sail.server.log` → `sailzen.server.log`
- [ ] **P4-7** 构建验证并提交

### Phase 5: 更新审查文档
- [ ] **P5-1** 在 `doc/design/vscode_plugin/vscode_plugin_review.md` 中：
  - 更新“生成日期”为当前日期
  - 在 **2. 债务清单** 中，将已清理的债务项标记为 ✅ 已清理，并注明清理日期/PR
  - 新增一节“5. 版本兼容 API 清理记录”，记录：
    - 已删除的文件清单（workspacev2.ts、ShowLegacyPreview.ts 等）
    - 已重命名的类/接口清单（WSUtilsV2→WSUtils、LookupControllerV3→LookupController 等）
    - 已移除的命令清单（SignIn、SeedAdd 等）
    - common-all 中的改动（DNodePropsQuickInputV2→DNodePropsQuickInput 等）
  - 更新 **3. 后续重构计划**，将已完成项标记为完成，调整剩余项优先级
  - 更新 **附录：关键文件速查表**，删除已不存在的文件路径，更新重命名后的路径
- [ ] **P5-2** 检查文档中是否还有对 `sail.` 前缀命令/视图的引用，同步更新为 `sailzen.`（如 3.1 轮计划中的命名统一已部分完成，需在文档中反映）
- [ ] **P5-3** 将文档末尾的“建议将此报告与 `doc/refact_todo.md` 和 `doc/sailzen-3.0-roadmap.md` 交叉参考”更新为包含本轮清理的对应条目

### Phase 6: 最终验证与收尾
- [ ] **P6-1** 全量构建：`pnpm run build-plugin`
- [ ] **P6-2** 运行所有相关测试
- [ ] **P6-3** 手动验证核心功能：Lookup、笔记创建、重命名、编译文档等
- [ ] **P6-4** 检查 `git diff --stat`，确认改动范围符合预期
- [ ] **P6-5** 生成 patch 文件（根据项目约束，使用 `git format-patch`）
- [ ] **P6-6** 提交最终 commit，message 示例：`cleanup(vscode-plugin): remove versioned APIs and legacy commands for personal edition`

---

## 三、风险与回滚策略

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 全局重命名引入编译错误 | 高 | 每完成一组重命名立即构建；使用 IDE 重构而非纯文本替换 |
| 删除命令后 `package.json` 残留 | 中 | 清理脚本：搜索 `package.json` 中已删除命令的 key |
| common-all 改动导致其他包中断 | 高 | 按依赖顺序构建：`common-all` → `common-server`/`unified` → `engine-server` → `vscode_plugin` |
| 测试失败难以定位 | 中 | 分阶段提交，每阶段独立验证，方便 `git bisect` |
| Web 版删除后发现仍有引用 | 中 | 删除前全局搜索 `from "../web/` 或 `from "./web/`，确保无 Node 代码引用 Web 模块 |

**回滚策略**: 所有改动在独立分支进行，每 Phase 结束为一个 commit。若某 Phase 失败，可单独 revert 该 commit。

---

## 四、预计工作量

| 阶段 | 预计耗时 | 说明 |
|------|---------|------|
| Phase 0 | 15 min | 分支、构建、备份 |
| Phase 1 | 30 min | workspacev2 删除 |
| Phase 2 | 3-4 h | 核心重命名，最耗时 |
| Phase 3 | 2-3 h | 模块移除 |
| Phase 4 | 1 h | 细节清理 |
| Phase 5 | 1-2 h | 文档更新 |
| Phase 6 | 30 min | 验证、提交 |
| **总计** | **~8-10 h** | 可分 2-3 天完成 |

---

## 五、关键文件变更索引

### 将被删除的文件
```
packages/vscode_plugin/src/workspacev2.ts
packages/vscode_plugin/src/services/stateService.ts
packages/vscode_plugin/src/versionProvider.ts
packages/vscode_plugin/src/commands/Refactor.ts
packages/vscode_plugin/src/commands/ShowLegacyPreview.ts
packages/vscode_plugin/src/commands/SignIn.ts
packages/vscode_plugin/src/commands/SignUp.ts
packages/vscode_plugin/src/commands/PublishDevCommand.ts
packages/vscode_plugin/src/commands/SeedAddCommand.ts
packages/vscode_plugin/src/commands/SeedBrowseCommand.ts
packages/vscode_plugin/src/commands/SeedRemoveCommand.ts
packages/vscode_plugin/src/commands/ShowWelcomePageCommand.ts
packages/vscode_plugin/src/commands/LaunchTutorialWorkspaceCommand.ts
packages/vscode_plugin/src/commands/CopyCodespaceURL.ts
packages/vscode_plugin/src/commands/MigrateSelfContainedVault.ts
packages/vscode_plugin/src/commands/RunMigrationCommand.ts
packages/vscode_plugin/src/commands/InstrumentedWrapperCommand.ts
packages/vscode_plugin/src/web/                  (整个目录)
packages/vscode_plugin/src/telemetry/            (整个目录)
packages/vscode_plugin/src/showcase/             (整个目录)
packages/vscode_plugin/src/utils/ProxyMetricUtils.ts
packages/vscode_plugin/src/utils/MeetingTelemHelper.ts
```

### 将被重命名的文件
```
WSUtilsV2.ts                  → WSUtils.ts
WSUtilsV2Interface.ts         → WSUtilsInterface.ts
LookupControllerV3.ts         → LookupController.ts
LookupControllerV3Factory.ts  → LookupControllerFactory.ts
LookupControllerV3Interface.ts→ LookupControllerInterface.ts
LookupProviderV3Factory.ts    → LookupProviderFactory.ts
LookupProviderV3Interface.ts  → LookupProviderInterface.ts
views/LookupV3QuickPickView.ts→ views/LookupQuickPickView.ts
commands/RenameNoteV2a.ts     → commands/RenameNoteInternal.ts
commands/RefactorHierarchyV2.ts→ commands/RefactorHierarchy.ts
```

### 将被修改的核心文件
```
packages/vscode_plugin/src/extension.ts
packages/vscode_plugin/src/_extension.ts
packages/vscode_plugin/src/workspace.ts
packages/vscode_plugin/src/sailExtensionInterface.ts
packages/vscode_plugin/src/ExtensionProvider.ts
packages/vscode_plugin/src/constants.ts
packages/vscode_plugin/src/commands/index.ts
packages/vscode_plugin/src/package.json
packages/common-all/src/types/typesv2.ts
packages/common-all/src/dnode.ts
packages/common-all/src/VaultUtilsV2.ts
packages/common-all/src/index.ts
packages/vscode_plugin/src/components/lookup/types.ts
packages/vscode_plugin/src/clientUtils.ts
packages/vscode_plugin/src/components/lookup/utils.ts
```

---

*Plan generated based on analysis of packages/vscode_plugin/src/ and common-all/ as of current HEAD.*
=======
>>>>>>> c08cb4d (cleanup(vscode-plugin): remove versioned APIs and legacy commands for personal edition)
