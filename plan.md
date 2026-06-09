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
