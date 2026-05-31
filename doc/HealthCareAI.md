# HealthCare AI — 永不休眠的个人健康管家

> **版本**: v1.0  
> **更新日期**: 2026-05-17  
> **状态**: 需求文档 & 技术框架  
> **定位**: SailZen 3.0 影子助手的健康子系统

---

## 1. 产品愿景

**HealthCare AI** 是运行在云服务器上的 24h 后台管家，承担专业营养医生 + 私人健康教练的角色。它不只是被动记录数据，而是：

- **主动发现**数据缺失（体重、睡眠、运动），及时提醒补录
- **综合分析** vault 日常笔记 + sail_server 结构化数据，理解用户的真实生活状况
- **动态调整**计划，根据出差、加班、生理期等实际状况给出可行建议
- **双向反馈**要求用户提供诚实反馈，建立信任闭环
- **持续进化**随着数据维度增加（睡眠 App、三维数据），评估精度不断提升

> **核心原则**: Agent 是桥梁，不是替代。它连接 Notes（主观状态）和 Database（客观数据），通过 LLM 产生人性化的健康洞察，但最终决策权始终在用户。

---

## 2. 系统架构

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          云服务器 (24h 运行)                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    HealthCare AI Daemon                               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │  │
│  │  │ Vault Sync  │  │  Note       │  │  Health     │  │  Report     │ │  │
│  │  │ Worker      │  │  Analyzer   │  │  Analyzer   │  │  Engine     │ │  │
│  │  │ (git pull)  │  │  (daily md) │  │  (DB API)   │  │  (LLM)      │ │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │  │
│  │         └─────────────────┴─────────────────┘                 │       │  │
│  │                           │                                   │       │  │
│  │                    ┌──────▼──────┐                           │       │  │
│  │                    │  Context    │◄──────────────────────────┘       │  │
│  │                    │  Builder    │  (合并笔记+数据，生成 LLM Prompt)   │  │
│  │                    └──────┬──────┘                                  │  │
│  │                           │                                         │  │
│  │                    ┌──────▼──────┐                                  │  │
│  │                    │  LLM Gateway│  (sail.llm.gateway)               │  │
│  │                    │  (分析+建议) │                                   │  │
│  │                    └──────┬──────┘                                  │  │
│  │                           │                                         │  │
│  │                    ┌──────▼──────┐                                  │  │
│  │                    │  Push       │  (飞书卡片 / 邮件)                │  │
│  │                    │  Dispatcher │                                   │  │
│  │                    └─────────────┘                                  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│         │                              │                                    │
│         ▼                              ▼                                    │
│  ┌─────────────┐              ┌─────────────────┐                          │
│  │  Git Repo   │              │  Sail Server    │                          │
│  │  (Vault)    │              │  (Litestar API) │                          │
│  └─────────────┘              └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │  用户手机/PC   │
                              │  (飞书/邮件)   │
                              └───────────────┘
```

### 2.2 与现有系统的集成关系

| 现有系统 | 集成方式 | 说明 |
|---------|---------|------|
| **Vault API Server** (`packages/api_server`) | HTTP Client (`sailzen/cli/vault_client.py`) | Standalone 模式启动，无需 VSCode，用于解析 daily journal |
| **Sail Server** (`sail_server/`) | HTTP Client (`requests`) | 调用 `/api/v1/health/*` 获取体重、运动、计划数据 |
| **Shadow Agent** (`doc/design/agent-system/shadow-agent.md`) | 复用 JobScheduler + agent_jobs 表 | 作为 Shadow Agent 的专用 Worker 子集运行 |
| **Feishu Bot** (`sail_bot/`) | 复用 `FeishuMessagingClient` | 通过已有飞书 client 发送卡片消息 |
| **LLM Gateway** (`sail.llm.gateway`) | 直接导入 | 复用统一 LLM 调用层，支持多 provider 自动降级 |

---

## 3. 核心组件设计

### 3.1 HealthCare Agent Daemon (`sail_server/agent/healthcare_daemon.py`)

主控进程，继承 Shadow Agent 的调度框架，负责：

```python
class HealthCareDaemon:
    def __init__(self, config: HealthCareConfig):
        self.scheduler = JobScheduler()
        self.vault_sync = VaultSyncWorker(config.vault)
        self.note_analyzer = HealthNoteAnalyzer(config.vault)
        self.data_fetcher = HealthDataFetcher(config.sail_server_url)
        self.report_engine = HealthReportEngine(config.llm)
        self.push_dispatcher = PushDispatcher(config.push)

    async def start(self):
        # 1. 恢复未完成任务
        await self._recover_jobs()
        # 2. 注册定时任务
        self.scheduler.add_cron(self.daily_analysis, hour=9, minute=0)   # 早9点日报
        self.scheduler.add_cron(self.daily_analysis, hour=21, minute=0)  # 晚9点督促
        self.scheduler.add_interval(self.vault_sync.sync, minutes=30)    # 每30分钟同步vault
        # 3. 主循环
        await self._main_loop()

    async def daily_analysis(self):
        """每日分析主流程"""
        # 1. 确保 vault 最新
        await self.vault_sync.sync()
        # 2. 获取最近7天笔记
        notes = await self.note_analyzer.get_recent_dailies(days=7)
        # 3. 获取健康数据
        health_data = await self.data_fetcher.fetch_recent(days=14)
        # 4. 构建上下文
        context = HealthContextBuilder.build(notes, health_data)
        # 5. LLM 分析生成报告
        report = await self.report_engine.generate(context)
        # 6. 推送
        await self.push_dispatcher.send(report)
        # 7. 记录到 agent_jobs
        await self._record_job("daily_health_report", report)
```

### 3.2 Vault Sync Worker (`sail_server/agent/vault_sync.py` 扩展)

复用 Shadow Agent 的 VaultSyncWorker，针对健康场景增加：

- **笔记指纹缓存**：记录已分析的笔记 hash，避免重复解析
- **增量检测**：只拉取有变更的 `journal.daily.YYYY.MM.DD.md`
- **降级模式**：若 Vault API Server 未启动，直接读取 Markdown 文件系统（正则提取 frontmatter + body）

```python
class HealthVaultSync(VaultSyncWorker):
    async def get_recent_dailies(self, days: int = 7) -> list[DailyNote]:
        """获取最近 N 天的 daily journal 笔记"""
        # 通过 vault_client 查询 fname 前缀匹配
        notes = self.vault_client.find_meta(fname=f"journal.daily.{self._date_prefix()}")
        # 过滤最近 N 天，获取完整 body
        return [self._parse_daily_note(n) for n in notes]
```

### 3.3 Health Data Fetcher (`sail_server/agent/health_data_fetcher.py`)

封装 Sail Server API 调用，获取结构化健康数据：

```python
class HealthDataFetcher:
    def __init__(self, base_url: str = "http://localhost:1974"):
        self.base_url = base_url

    async def fetch_recent(self, days: int = 14) -> HealthDataBundle:
        """获取最近 N 天的所有健康相关数据"""
        end = datetime.now()
        start = end - timedelta(days=days)
        
        return HealthDataBundle(
            weights=await self._fetch_weights(start, end),
            exercises=await self._fetch_exercises(start, end),
            plan=await self._fetch_active_plan(),
            plan_progress=await self._fetch_plan_progress(),
        )

    async def _fetch_weights(self, start: datetime, end: datetime) -> list[dict]:
        """GET /api/v1/health/weight?start=<ts>&end=<ts>"""
        ...

    async def _fetch_exercises(self, start: datetime, end: datetime) -> list[dict]:
        """GET /api/v1/health/exercise?start=<ts>&end=<ts>"""
        ...
```

### 3.4 Health Context Builder (`sail_server/agent/health_context.py`)

将非结构化的笔记内容与结构化的数据库数据合并为 LLM 可理解的上下文：

```python
class HealthContextBuilder:
    @staticmethod
    def build(notes: list[DailyNote], data: HealthDataBundle) -> AnalysisContext:
        """
        构建 LLM 分析上下文，包含：
        - 时间线：每天一条记录，融合笔记摘要 + 体重 + 运动
        - 缺失标记：哪些天没有体重、没有笔记、没有运动
        - 计划偏差：实际体重 vs 计划体重的偏离度
        - 特殊事件：出差、加班、应酬等（从笔记中提取）
        """
        timeline = []
        for day in self._date_range(data.start, data.end):
            note = notes.get(day)
            weight = data.weights.get(day)
            exercise = data.exercises.get(day)
            
            timeline.append({
                "date": day.isoformat(),
                "note_summary": note.summary if note else None,
                "note_tags": note.tags if note else [],
                "weight": weight.value if weight else None,
                "weight_status": weight.status if weight else "missing",
                "exercise": exercise.description if exercise else None,
                "mood": note.mood if note else None,  # 从笔记 frontmatter 提取
                "sleep_quality": note.sleep if note else None,
                "special_events": note.special_events if note else [],
            })
        
        return AnalysisContext(
            timeline=timeline,
            active_plan=data.plan,
            plan_control_rate=data.plan_progress.control_rate if data.plan_progress else 0,
            recent_trend=data.weights.trend(),
            missing_data=self._detect_missing(timeline),
        )
```

### 3.5 Health Report Engine (`sail_server/agent/health_report_engine.py`)

基于 LLM 生成个性化健康报告：

```python
class HealthReportEngine:
    def __init__(self, llm_config: LLMConfig):
        self.gateway = LLMGateway()
        self.provider = llm_config.provider
        self.model = llm_config.model

    async def generate(self, ctx: AnalysisContext) -> HealthReport:
        # 第一阶段：数据分析（低 temperature，确定性）
        analysis = await self._analyze_data(ctx)
        
        # 第二阶段：建议生成（中等 temperature，人性化）
        recommendations = await self._generate_recommendations(ctx, analysis)
        
        # 第三阶段：消息格式化（生成飞书卡片 JSON）
        card = self._format_card(recommendations)
        
        return HealthReport(
            analysis=analysis,
            recommendations=recommendations,
            card=card,
            raw_context=ctx,
        )

    async def _analyze_data(self, ctx: AnalysisContext) -> DataAnalysis:
        prompt = _ANALYSIS_PROMPT.format(
            timeline=json.dumps(ctx.timeline, ensure_ascii=False, indent=2),
            plan=json.dumps(ctx.active_plan, ensure_ascii=False),
            control_rate=ctx.plan_control_rate,
        )
        # 使用低 temperature 确保分析稳定
        result = await self.gateway.execute(prompt, LLMExecutionConfig(
            provider=self.provider,
            model=self.model,
            temperature=0.3,
            max_tokens=2000,
        ))
        return self._parse_analysis(result.content)
```

**Prompt 设计原则**:

```
系统角色：你是一位专业的营养医生兼私人健康教练，熟悉运动生理学和行为心理学。

任务：根据用户最近的生活记录和健康数据，生成今日健康简报。

输入格式：
- timeline: 每天一条记录，包含笔记摘要、体重、运动、睡眠、特殊事件
- active_plan: 当前体重管理计划（目标体重、截止日期）
- control_rate: 计划执行控制率（0-100%）

输出要求（JSON）：
{
  "missing_data": ["2026-05-15 体重", "2026-05-16 运动"],
  "trend_assessment": "体重连续3天高于计划线，但笔记显示有应酬，属于可控偏差",
  "risk_flags": ["睡眠不足（连续2天<6h）", "周末无运动记录"],
  "recommendations": [
    {"type": "urgent", "content": "今晚务必在23:30前入睡", "reason": "连续睡眠不足会影响代谢"},
    {"type": "suggestion", "content": "明早称重后更新记录", "reason": "已缺失2天数据"},
    {"type": "encouragement", "content": "本周应酬控制得不错，下周可以尝试增加一次有氧", "reason": "根据笔记反馈，用户本周社交压力较大但仍保持了饮食控制"}
  ],
  "follow_up_questions": ["昨晚睡眠质量如何？", "今天有安排运动吗？"],
  "plan_adjustment": "建议将本周目标放宽0.5kg，以匹配出差期间的实际条件"
}

约束：
1. 必须基于实际数据，不能编造
2. 发现缺失数据必须明确列出
3. 考虑用户实际状况（出差、加班），给出可行建议
4. 语气亲切但有专业边界，像一位关心的医生朋友
5. 如果用户明显懈怠，适度督促但不要指责
```

### 3.6 Push Dispatcher (`sail_server/agent/push_dispatcher.py`)

多渠道消息推送：

```python
class PushDispatcher:
    def __init__(self, config: PushConfig):
        self.feishu = FeishuMessagingClient() if config.feishu_enabled else None
        self.email = EmailClient() if config.email_enabled else None
        self.default_chat_id = config.feishu_chat_id

    async def send(self, report: HealthReport):
        # 飞书卡片推送（主要渠道）
        if self.feishu:
            await self._send_feishu_card(report)
        
        # 邮件备份（长内容、历史归档）
        if self.email and report.has_critical_alert():
            await self._send_email(report)

    async def _send_feishu_card(self, report: HealthReport):
        """发送飞书交互卡片，包含：
        - 今日数据摘要（体重、睡眠、运动）
        - 缺失数据提醒（红色标记）
        - 今日建议列表（分级：urgent/suggestion/encouragement）
        - 快捷反馈按钮（"已称重"/"已运动"/"昨晚睡得好"）
        - 查看详情按钮（链接到 sail_site 健康页面）
        """
        card = build_health_card(report)
        self.feishu.send_card_to_default(card, card_type="health_daily")
```

**飞书卡片结构示例**:

```json
{
  "header": {
    "title": {"content": "🏥 今日健康简报 | 5月17日", "tag": "plain_text"},
    "template": "blue"
  },
  "elements": [
    {"tag": "div", "text": {"content": "**体重**: 84.2kg (↑0.3 计划线以下)", "tag": "lark_md"}},
    {"tag": "div", "text": {"content": "**睡眠**: 6.5h ⚠️ 连续2天不足7h", "tag": "lark_md"}},
    {"tag": "div", "text": {"content": "**运动**: 昨日未记录 🏃", "tag": "lark_md"}},
    {"tag": "hr"},
    {"tag": "div", "text": {"content": "**📋 今日提醒**", "tag": "lark_md"}},
    {"tag": "div", "text": {"content": "🔴  urgent: 今晚23:30前入睡（连续睡眠不足影响代谢）", "tag": "lark_md"}},
    {"tag": "div", "text": {"content": "🟡  suggestion: 明早称重后更新记录（已缺失2天）", "tag": "lark_md"}},
    {"tag": "div", "text": {"content": "🟢  encouragement: 本周应酬控制不错，下周可增加一次有氧", "tag": "lark_md"}},
    {"tag": "hr"},
    {"tag": "div", "text": {"content": "**💬 反馈**", "tag": "lark_md"}},
    {"tag": "action", "actions": [
      {"tag": "button", "text": {"content": "已称重", "tag": "plain_text"}, "type": "primary", "value": {"action": "log_weight"}},
      {"tag": "button", "text": {"content": "已运动", "tag": "plain_text"}, "type": "primary", "value": {"action": "log_exercise"}},
      {"tag": "button", "text": {"content": "昨晚睡得好", "tag": "plain_text"}, "type": "default", "value": {"action": "log_sleep_good"}}
    ]}
  ]
}
```

---

## 4. 数据模型扩展

### 4.1 新增表：`health_daily_reports`

```sql
CREATE TABLE IF NOT EXISTS health_daily_reports (
    id              SERIAL PRIMARY KEY,
    report_date     DATE NOT NULL,
    report_type     VARCHAR(32) DEFAULT 'morning',  -- morning / evening / weekly
    
    -- 输入摘要
    notes_analyzed  INT DEFAULT 0,                  -- 分析了多少天笔记
    weights_count   INT DEFAULT 0,                  -- 获取了多少条体重记录
    exercises_count INT DEFAULT 0,                  -- 获取了多少条运动记录
    
    -- 分析结果（JSONB，存储 LLM 输出）
    analysis_result JSONB DEFAULT '{}',
    missing_data    JSONB DEFAULT '[]',             -- 缺失数据列表
    risk_flags      JSONB DEFAULT '[]',             -- 风险标记
    recommendations JSONB DEFAULT '[]',             -- 建议列表
    
    -- 推送状态
    push_channel    VARCHAR(32) DEFAULT 'feishu',   -- feishu / email / both
    push_status     VARCHAR(32) DEFAULT 'pending',  -- pending / sent / failed
    push_time       TIMESTAMP,
    message_id      VARCHAR(128),                   -- 飞书 message_id（用于更新卡片）
    
    -- 用户反馈
    user_feedback   JSONB DEFAULT NULL,             -- 用户对报告的反馈
    feedback_time   TIMESTAMP,
    
    -- 元数据
    model_used      VARCHAR(64),                    -- 使用的 LLM 模型
    token_usage     INT,                            -- token 消耗
    generation_time_ms INT,                         -- 生成耗时
    
    ctime           TIMESTAMP DEFAULT NOW(),
    mtime           TIMESTAMP DEFAULT NOW(),
    UNIQUE(report_date, report_type)
);

CREATE INDEX idx_health_reports_date ON health_daily_reports(report_date DESC);
CREATE INDEX idx_health_reports_type ON health_daily_reports(report_type);
CREATE INDEX idx_health_reports_status ON health_daily_reports(push_status);
```

### 4.2 新增表：`health_feedback_log`

记录用户通过飞书卡片按钮提供的反馈，用于 LLM 学习用户习惯：

```sql
CREATE TABLE IF NOT EXISTS health_feedback_log (
    id              SERIAL PRIMARY KEY,
    report_id       INT REFERENCES health_daily_reports(id),
    feedback_type   VARCHAR(32) NOT NULL,           -- weight_logged / exercise_logged / sleep_feedback / text_reply
    feedback_value  JSONB DEFAULT '{}',             -- 反馈内容
    feedback_time   TIMESTAMP DEFAULT NOW(),
    user_context    JSONB DEFAULT '{}'              -- 当时的上下文（方便回溯）
);
```

### 4.3 扩展现有 `agent_jobs` 表

复用 Shadow Agent 的 `agent_jobs` 表，新增 job_type：

| job_type | 说明 |
|----------|------|
| `health_vault_sync` | 同步 vault 日常笔记 |
| `health_daily_report` | 生成每日健康报告 |
| `health_weekly_report` | 生成周度健康总结 |
| `health_follow_up` | 跟进用户反馈 |
| `health_data_reminder` | 数据缺失提醒（独立任务） |

---

## 5. CLI 接口

```bash
# ── 生命周期 ──
uv run sail_server/agent/healthcare_daemon.py start      # 启动健康管家
uv run sail_server/agent/healthcare_daemon.py stop       # 停止
uv run sail_server/agent/healthcare_daemon.py status     # 查看状态

# ── 手动触发 ──
uv run sail_server/agent/healthcare_daemon.py report     # 立即生成今日报告
uv run sail_server/agent/healthcare_daemon.py report --type weekly
uv run sail_server/agent/healthcare_daemon.py sync       # 立即同步 vault

# ── 调试与测试 ──
uv run sail_server/agent/healthcare_daemon.py test-llm   # 测试 LLM 连接与 Prompt
uv run sail_server/agent/healthcare_daemon.py dry-run    # 生成报告但不推送
```

---

## 6. 配置示例 (`healthcare.yaml`)

```yaml
healthcare:
  name: "personal-health-coach"
  timezone: "Asia/Shanghai"

  # Vault 配置
  vault:
    url: "git@github.com:username/my-vault.git"
    local_path: "./vaults/health-notes"
    branch: "main"
    sync_interval_minutes: 30
    daily_note_pattern: "journal.daily.{YYYY}.{MM}.{DD}"
    # Vault API Server 配置（用于解析笔记）
    api_server_url: "http://localhost:3005"
    ws_root: "./vaults/health-notes"

  # Sail Server 配置
  sail_server:
    base_url: "http://localhost:1974"
    api_version: "v1"

  # LLM 配置（复用项目默认配置，可覆盖）
  llm:
    provider: "moonshot"
    model: "kimi-k2.6"
    temperature: 0.5  # 健康建议需要一定灵活性
    max_tokens: 4000

  # 调度配置
  scheduler:
    morning_report: "0 9 * * *"    # 每天 9:00 早报
    evening_reminder: "0 21 * * *" # 每天 21:00 晚督促
    weekly_report: "0 10 * * 0"    # 每周日 10:00 周报
    data_check: "0 22 * * *"       # 每天 22:00 检查当日数据完整性

  # 推送配置
  push:
    primary: "feishu"              # 主要推送渠道
    fallback: "email"              # 降级渠道
    
    feishu:
      enabled: true
      chat_id: "${FEISHU_HEALTH_CHAT_ID}"
      app_id: "${FEISHU_APP_ID}"
      app_secret: "${FEISHU_APP_SECRET}"
    
    email:
      enabled: false
      smtp_host: "smtp.example.com"
      smtp_port: 587
      username: "${EMAIL_USER}"
      password: "${EMAIL_PASS}"
      to: "user@example.com"

  # 提醒规则
  rules:
    weight:
      remind_if_missing_days: 2     # 连续2天未记录体重则提醒
      warn_deviation_kg: 2.0        # 偏离计划线2kg以上发出警告
    
    sleep:
      remind_if_avg_below_hours: 6.5  # 周平均睡眠低于6.5h提醒
    
    exercise:
      remind_if_missing_days: 3     # 连续3天未运动提醒
      weekly_target_minutes: 150    # 周运动目标（分钟）
    
    feedback:
      collect_after_report_hours: 2  # 报告推送后2小时收集反馈
      ask_honest_feedback: true      # 主动要求诚实反馈
```

---

## 7. 工作流详细设计

### 7.1 每日早报流程 (09:00)

```
1. JobScheduler 触发 daily_analysis
2. VaultSyncWorker.pull() → git pull 笔记库
3. HealthNoteAnalyzer.get_recent_dailies(7) → 获取最近7天笔记
   - 调用 Vault API Server /api/note/find?fname="journal.daily.2026"
   - 解析 frontmatter（mood, sleep, tags）和 body（提取特殊事件）
4. HealthDataFetcher.fetch_recent(14) → 获取最近14天健康数据
   - GET /api/v1/health/weight?start=<ts>&end=<ts>
   - GET /api/v1/health/exercise?start=<ts>&end=<ts>
   - GET /api/v1/health/weight/plan/progress
5. HealthContextBuilder.build() → 合并为时间线
6. HealthReportEngine.generate() → LLM 分析
   - Step 1: 数据分析（temperature=0.3）
   - Step 2: 建议生成（temperature=0.5）
   - Step 3: 格式化为飞书卡片
7. PushDispatcher.send() → 推送飞书卡片
8. 记录 health_daily_reports 表，状态 sent
9. 如果需要用户反馈，创建 follow_up 任务（2小时后）
```

### 7.2 晚间督促流程 (21:00)

```
1. 检查今日是否已记录体重、运动、睡眠
2. 如果存在缺失，生成简短提醒（不是完整报告）
3. 推送轻量级消息：
   "今天还没有记录体重哦，睡前称一下吧 💪"
   或
   "昨晚睡眠6小时，今晚试试23:30前放下手机？"
```

### 7.3 数据缺失检测与提醒

```
每天 22:00 执行：
1. 检查当日 journal.daily.2026.05.17.md 是否存在
2. 检查当日体重记录是否存在
3. 检查昨日睡眠记录（从笔记 frontmatter）
4. 检查近3天运动记录
5. 生成缺失清单
6. 若缺失严重（>2项），发送即时提醒（不等到21点）
```

### 7.4 用户反馈收集

飞书卡片按钮触发：
- **"已称重"** → 调用 Sail Server POST /api/v1/health/weight 快速录入（预填当前时间）
- **"已运动"** → 打开对话框让用户填写运动类型和时长
- **"昨晚睡得好" / "睡得不好"** → 记录反馈到 health_feedback_log
- **文字回复** → Bot 将该回复与最新 report 关联，作为下次分析的上下文

### 7.5 出差/特殊状况自适应

```
从笔记中检测关键词：
- "出差" / "travel" / "在外地" → 降低运动要求，关注饮食控制
- "加班" / "赶 deadline" → 提醒不要熬夜，允许体重小幅波动
- "应酬" / "聚餐" / "喝酒" → 提前给出饮食策略（多吃蔬菜、控制主食）
- "生理期" / "身体不适" → 暂停高强度运动建议，关注休息

LLM Prompt 中明确指示：
"用户本周出差，请给出在酒店可执行的运动建议（如俯卧撑、深蹲、快走），
 并提醒机场/高铁站的饮食选择策略。不要建议需要器械或固定场所的运动。"
```

---

## 8. 后续扩展规划

### Phase 1: MVP（已有数据）
- [x] 体重记录分析与提醒
- [x] 日常笔记解析
- [x] 飞书卡片推送
- [x] 基础反馈收集

### Phase 2: 多维度数据接入
- [ ] **睡眠数据导入**：每周从运动 App（如 Apple Health、小米运动）导出 CSV/JSON，自动解析睡眠时长、深睡比例、入睡时间
- [ ] **运动数据导入**：步数、跑步距离、消耗热量、运动类型
- [ ] **饮食记录**：在 daily note 中增加结构化饮食模板，AI 自动估算热量

### Phase 3: 生理数据
- [ ] **三维数据**：胸围、腰围、臀围、体脂率定期测量记录
- [ ] **体成分分析**：如有智能体脂秤，接入 API 或导入数据
- [ ] **血压/血糖**：如有慢病管理需求，定期记录

### Phase 4: 智能进化
- [ ] **长期趋势学习**：基于 3-6 个月数据，LLM 学习用户的行为模式（周末易暴食、出差易失眠等）
- [ ] **预测性提醒**：在用户通常会懈怠的时间点前主动介入（如周五下午提醒周末计划）
- [ ] **A/B 建议测试**：同一问题给出两种策略，根据用户反馈学习哪种更有效
- [ ] **多模态输入**：支持上传运动 App 截图，AI OCR 提取数据

---

## 9. 安全与隐私

1. **数据不出境**：所有健康数据存储在用户的私有数据库，LLM 分析时仅传输脱敏后的时间线摘要
2. **Vault 安全**：git 仓库使用 SSH key 拉取，key 存储在服务器环境变量
3. **飞书消息加密**：使用飞书官方 SDK，通信走 HTTPS
4. **敏感数据过滤**：LLM Prompt 中隐去具体地点、人员姓名等隐私信息
5. **日志脱敏**：`LLM_DEBUG=true` 模式下，日志中的体重、健康数据自动打码

---

## 10. 与 SailZen 3.0 路线图的关系

本文档定义的 HealthCare AI 是 [SailZen 3.0 路线图](./sailzen-3.0-roadmap.md) 中 **"永不休眠的影子助手"** 的第一个落地子系统：

| 3.0 愿景 | HealthCare AI 实现 |
|---------|-------------------|
| 自动同步知识库 | Vault Sync Worker 定时拉取 journal |
| 发现补全任务 | 缺失数据检测 + 自动提醒 |
| AI 交互 | LLM 驱动的个性化健康建议 |
| 推送通知 | 飞书卡片 + 邮件 |
| 永不休眠 | 服务器常驻 Daemon + APScheduler |

后续 Shadow Agent 的其他 Worker（TODO 提取、Patch 生成、DAG Pipeline）可独立运行，HealthCare AI 作为其中专注于健康领域的垂直 Agent 共存。

---

## 11. 附录

### 11.1 关键代码位置

| 文件 | 用途 |
|------|------|
| `sail_server/agent/healthcare_daemon.py` | HealthCare AI 主控（待创建） |
| `sail_server/agent/health_data_fetcher.py` | 健康数据获取（待创建） |
| `sail_server/agent/health_context.py` | 上下文构建（待创建） |
| `sail_server/agent/health_report_engine.py` | 报告引擎（待创建） |
| `sail_server/agent/push_dispatcher.py` | 推送分发（待创建） |
| `sail_server/migration/health_ai_tables.sql` | 数据库迁移（待创建） |
| `sailzen/cli/vault_client.py` | Vault API 客户端（已有） |
| `sail_bot/messaging/client.py` | 飞书消息客户端（已有） |
| `sail/llm/gateway.py` | LLM 网关（已有） |

### 11.2 相关文档

- [Shadow Agent 设计](./design/agent-system/shadow-agent.md)
- [Vault API Server](./design/vault-server.md)
- [健康管理模块 API](./api/health.md)
- [健康管理数据设计](./design/manager/health.md)
- [飞书 Bot 自更新](./design/sail_bot/bot-self-update.md)
