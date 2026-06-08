# SailZen Autonomous Agent System — Comprehensive Design Plan

> **Version**: 1.0  
> **Date**: 2025-06-02  
> **Status**: Design — correcting historical architectural errors  
> **Core Principle**: Complete isolation. The Agent is not a module of `sail_server`; it is a sovereign runtime that *consumes* `sail_server` via HTTP API only.

---

## 1. Problem Analysis: What Went Wrong Before

### 1.1 Historical Debt Inventory

| Debt Item | Previous (Wrong) Design | Why It Was Wrong |
|-----------|------------------------|------------------|
| **Database** | `agent_jobs` and `sail_configs` tables created in main PostgreSQL DB via `sail_server/migration/agent_job_table.sql` | Violates isolation. Agent data would be synced/backed up with main DB. Creates coupling where agent bugs can corrupt production data. |
| **Code Location** | Planned `sail_server/agent/` directory inside the main server | Violates bounded context. Agent lifecycle, scheduling, and memory concerns leak into the web service. |
| **Execution Model** | Shadow-agent daemon proposed as a sub-process or thread of sail_server | Tight coupling. Agent crashes could destabilize the API server. |
| **Data Access** | Direct ORM/DAO access to sail_server tables | Bypasses API contracts. Makes schema changes risky for both sides. |
| **LLM Integration** | Implicit dependency on server-side LLM gateway configuration | No direct control over Kimi/DeepSeek parameters for agent-specific reasoning. |

### 1.2 Why `sail_bot/` Is Not the Answer

- `sail_bot/` is a **personal Feishu remote-operation tool** (遥操作). Its purpose is human-in-the-loop chat control.
- It is tightly bound to Feishu IM semantics and personal bot identity.
- It does not have a general DAG execution engine, cron scheduling, or skill-oriented architecture.
- **Decision**: Leave `sail_bot/` untouched. Build a new, orthogonal system.

### 1.3 What Exists and Can Be Reused

`sailzen.dag_client` (v3.0) is already a **correctly isolated** execution framework:
- Own SQLite DB (`data/dag_client.db`)
- Own file workspace (`data/dag/`)
- DAG scheduler + executor with topology sorting, retries, SSE events
- Skill nodes (OpenCode protocol), Shell nodes, Python nodes
- Independent Litestar HTTP API (port 9050)
- Dynamic node registration via `NodeRegistry`

**The autonomous agent should be built as a layer ON TOP OF `sailzen.dag_client`, not inside `sail_server`.**

---

## 2. Architecture Overview

### 2.1 Isolation Boundaries

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Host / Server                                    │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────┐ │
│  │   sail_server (Litestar)    │    │   sailzen.autonomous_agent      │ │
│  │   ┌─────────────────────┐   │    │   ┌─────────────────────────┐   │ │
│  │   │  PostgreSQL/SQLite  │   │    │   │  agent.db (SQLite)      │   │ │
│  │   │  (MAIN DB)          │   │    │   │  ─ COMPLETELY ISOLATED  │   │ │
│  │   │  ─ DO NOT TOUCH     │   │    │   │  ─ NOT synced/backed up │   │ │
│  │   └─────────────────────┘   │    │   │    with main DB         │   │ │
│  │           ▲                 │    │   └─────────────────────────┘   │ │
│  │           │ HTTP API only   │    │   ┌─────────────────────────┐   │ │
│  │           │ (same as CLI)   │    │   │  data/agent/ workspace  │   │ │
│  │           ▼                 │    │   │  ─ runs/artifacts/logs  │   │ │
│  │   ┌─────────────────────┐   │    │   └─────────────────────────┘   │ │
│  │   │  Router/Controller  │   │    │   ┌─────────────────────────┐   │ │
│  │   │  /api/v1/*          │   │    │   │  Cron Scheduler         │   │ │
│  │   └─────────────────────┘   │    │   │  (APScheduler + SQLite) │   │ │
│  └─────────────────────────────┘    │   └─────────────────────────┘   │ │
│                                     │   ┌─────────────────────────┐   │ │
│  ┌─────────────────────────────┐    │   │  Agent Daemon           │   │ │
│  │   sailzen CLI               │◄───┼───┤  ─ orchestrates goals   │   │ │
│  │   (HTTP client to server)   │    │   │  ─ manages memory       │   │ │
│  └─────────────────────────────┘    │   └─────────────────────────┘   │ │
│                                     │   ┌─────────────────────────┐   │ │
│  ┌─────────────────────────────┐    │   │  DAG Executor (reused   │   │ │
│  │   OpenCode Server           │◄───┼───┤  from dag_client)       │   │ │
│  │   (Skills: wellness, lark)  │    │   └─────────────────────────┘   │ │
│  └─────────────────────────────┘    │   ┌─────────────────────────┐   │ │
│                                     │   │  LLM Gateway            │   │ │
│                                     │   │  ─ Kimi (moonshot)      │   │ │
│                                     │   │  ─ DeepSeek             │   │ │
│                                     │   └─────────────────────────┘   │ │
│                                     └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Design Principles

1. **Zero Main-DB Touch**: The agent never opens a SQLAlchemy session to `sail_server.db`. All reads are via HTTP API (`sailzen` CLI or direct `httpx` calls).
2. **Sovereign SQLite**: `agent.db` lives in `data/agent.db` (or configured path). It is excluded from `scripts/db_sync.py` and any backup logic targeting the main DB.
3. **Skill-First Execution**: Complex workflows (wellness, Lark, finance analysis) are executed by invoking OpenCode Skills through the DAG Client's `SkillNode`. The agent orchestrates; skills execute.
4. **Direct LLM for Reasoning**: When the agent needs to make decisions (prioritize reminders, interpret anomalies), it calls Kimi/DeepSeek directly via the Agent's own `LLMGateway`, not through the server's analysis controllers.
5. **Cron-Native**: Scheduling is a first-class citizen, not an afterthought. Recurring pipelines are stored persistently in the agent's SQLite DB.

---

## 3. Module Structure

### 3.1 New Package: `sailzen/autonomous_agent/`

```
sailzen/autonomous_agent/
├── __init__.py              # Package exports
├── __main__.py              # CLI entry: python -m sailzen.autonomous_agent
├── daemon.py                # AgentDaemon: main lifecycle orchestrator
├── config.py                # AgentConfig loader (agent.yaml + env vars)
├── db.py                    # Agent SQLite ORM + connection (ISOLATED)
├── scheduler.py             # CronScheduler: APScheduler wrapper
├── memory.py                # AgentMemory: short-term + long-term memory manager
├── llm_gateway.py           # Direct LLM clients (Kimi, DeepSeek)
├── state_manager.py         # Agent state machine, goals, reminders
├── notification_engine.py   # Push notification abstraction (Lark, IM)
├── pipelines/               # Pre-defined autonomous pipeline YAMLs
│   ├── daily_standup.yaml
│   ├── weekly_wellness.yaml
│   ├── finance_anomaly_scan.yaml
│   ├── health_monitor.yaml
│   ├── patch_reminder.yaml
│   └── smart_digest.yaml
├── nodes/                   # Agent-specific DAG node types
│   ├── __init__.py
│   ├── sailzen_cli_node.py      # Invoke `sailzen finance/health ...`
│   ├── lark_notify_node.py      # Send Lark IM / post messages
│   ├── wellness_node.py         # Trigger sailzen-wellness skill
│   ├── state_check_node.py      # HTTP health/state checks against sail_server
│   ├── llm_reasoning_node.py    # Direct LLM call for agent reasoning
│   ├── reminder_emit_node.py    # Emit a reminder to configured channels
│   └── condition_node.py        # Branching logic based on state/memory
├── api/                     # Management HTTP API (optional, port 9060)
│   ├── __init__.py
│   └── routes.py
└── templates/               # Jinja2 templates for notifications/reports
    ├── daily_standup.md.j2
    ├── wellness_alert.md.j2
    └── finance_digest.md.j2
```

### 3.2 Modifications to Existing Code

| File | Change | Reason |
|------|--------|--------|
| `sailzen/dag_client/nodes/registry.py` | Allow external packages to register nodes | Agent nodes need to be registered at runtime |
| `sailzen/dag_client/config.py` | Add `agent_pipelines_dir` optional field | Agent can load its pipeline definitions into dag_client |
| `sailzen/dag_client/models.py` | Add `DBCronSchedule` and `DBAgentMemory` ORM models (in agent DB, NOT dag_client DB) | Wait — no. Agent DB is separate. These go in `sailzen/autonomous_agent/db.py` |
| `scripts/db_sync.py` | Explicitly ignore `data/agent.db` and `data/agent/` | Prevent accidental sync of agent data |
| `sail_server/migration/agent_job_table.sql` | **DELETE** or move to `archive/` | This was the wrong design. Agent tables do not belong in main DB. |
| `doc/design/agent-system/shadow-agent.md` | **ARCHIVE** and replace with reference to this plan | Historical document; concepts are superseded. |

---

## 4. Database Design (Isolated SQLite)

**File**: `data/agent.db` (configurable via `AGENT_DB_PATH` env var)

**Schema**:

```sql
-- Agent schedules (cron + interval)
CREATE TABLE agent_schedules (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    pipeline_id     TEXT NOT NULL,        -- references dag_definitions.id
    schedule_type   TEXT NOT NULL,        -- 'cron' | 'interval' | 'date'
    schedule_expr   TEXT NOT NULL,        -- cron expr or "3600" seconds
    timezone        TEXT DEFAULT 'Asia/Shanghai',
    enabled         INTEGER DEFAULT 1,
    params          TEXT DEFAULT '{}',    -- JSON: runtime params for the pipeline
    next_run_time   TEXT,
    last_run_time   TEXT,
    last_run_status TEXT,                 -- 'success' | 'failed' | 'skipped'
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- Agent memory (ephemeral + persistent context)
CREATE TABLE agent_memories (
    id              TEXT PRIMARY KEY,
    memory_type     TEXT NOT NULL,        -- 'short_term' | 'long_term' | 'context'
    key             TEXT NOT NULL,
    value           TEXT NOT NULL,        -- JSON
    ttl_seconds     INTEGER,              -- NULL = permanent
    created_at      TEXT DEFAULT (datetime('now')),
    expires_at      TEXT
);
CREATE INDEX idx_memories_type_key ON agent_memories(memory_type, key);
CREATE INDEX idx_memories_expires ON agent_memories(expires_at);

-- Reminders and alerts emitted by the agent
CREATE TABLE agent_reminders (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    content         TEXT,
    channel         TEXT NOT NULL,        -- 'lark_im' | 'lark_group' | 'log'
    priority        TEXT DEFAULT 'normal', -- 'low' | 'normal' | 'high' | 'urgent'
    status          TEXT DEFAULT 'pending', -- 'pending' | 'sent' | 'dismissed' | 'snoozed'
    scheduled_at    TEXT,                 -- when to send
    sent_at         TEXT,
    pipeline_run_id TEXT,                 -- which run created this
    context         TEXT DEFAULT '{}',    -- JSON: related data
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_reminders_status_scheduled ON agent_reminders(status, scheduled_at);

-- Agent goals (higher-level objectives)
CREATE TABLE agent_goals (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT,
    status          TEXT DEFAULT 'active', -- 'active' | 'paused' | 'completed' | 'abandoned'
    priority        INTEGER DEFAULT 100,
    target_date     TEXT,
    completion_criteria TEXT,             -- JSON
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- Pipeline execution log (agent's view, not dag_client's internal log)
CREATE TABLE agent_run_log (
    id              TEXT PRIMARY KEY,
    schedule_id     TEXT REFERENCES agent_schedules(id),
    pipeline_id     TEXT NOT NULL,
    dag_run_id      TEXT,                 -- references dag_client.dag_runs.id
    status          TEXT NOT NULL,        -- 'started' | 'completed' | 'failed'
    summary         TEXT,                 -- human-readable summary
    started_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT,
    error           TEXT
);
CREATE INDEX idx_run_log_schedule ON agent_run_log(schedule_id, started_at);
```

**Key constraint**: `db_sync.py` must NEVER see this file. It lives outside the main DB URI entirely.

---

## 5. Workspace Design (Isolated File System)

**Root**: `data/agent/` (configurable via `AGENT_DATA_DIR`)

```
data/agent/
├── db/
│   └── agent.db                 # The isolated SQLite database
├── runs/
│   └── {pipeline_run_id}/
│       ├── artifacts/
│       ├── logs/
│       └── report.md
├── memory/
│   └── context_snapshots/       # Periodic dumps of working memory
├── notifications/
│   └── queued/                  # Notifications queued for delivery
│   └── sent/                    # Archive of sent notifications
├── backups/
│   └── agent_backup_YYYYMMDD.tar.gz
└── config/
    └── agent.yaml               # Runtime configuration
```

- `data/agent/` is excluded from main project backup scripts.
- The agent implements its own `AgentStore` (similar to `DAGStore`) for file operations.

---

## 6. Core Components

### 6.1 AgentDaemon (`daemon.py`)

Responsibilities:
- Initialize isolated DB and workspace
- Start CronScheduler
- Start DAG Executor (reused from `sailzen.dag_client`) 
- Register agent-specific nodes into `NodeRegistry`
- Run the main event loop: process reminders, check goals, schedule pipelines
- Expose management API (optional)
- Graceful shutdown handling

```python
class AgentDaemon:
    def __init__(self, config: AgentConfig):
        self.db = AgentDatabase(config.db_path)
        self.store = AgentStore(config.data_dir)
        self.scheduler = CronScheduler(self.db)
        self.memory = AgentMemory(self.db)
        self.llm = LLMGateway(config.llm)
        self.state = StateManager(self.db, self.memory)
        self.notifier = NotificationEngine(config.notifications)
        
        # Reuse dag_client executor but with our nodes
        self.dag_db = DatabaseCompat(self.db)  # adapter pattern
        self.node_registry = NodeRegistry()
        self._register_agent_nodes()
        self.executor = DAGExecutor(...)
        
    async def start(self):
        await self.db.connect()
        await self.scheduler.start()
        await self.executor.start()
        await self._main_loop()
```

### 6.2 CronScheduler (`scheduler.py`)

Uses **APScheduler** with SQLAlchemyJobStore pointing to `agent.db`.

Capabilities:
- `add_cron(pipeline_id, cron_expr, params)`
- `add_interval(pipeline_id, seconds, params)`
- `trigger_now(pipeline_id, params)` — manual/ad-hoc execution
- Persistent: schedules survive daemon restarts
- Timezone-aware (default `Asia/Shanghai`)

On trigger: creates a DAG run via `dag_client` scheduler, then monitors completion.

### 6.3 LLMGateway (`llm_gateway.py`)

Direct clients for Kimi and DeepSeek, independent of `sail_server.utils.llm`.

```python
class LLMGateway:
    async def reason(self, prompt: str, provider: str = "kimi", **kwargs) -> str:
        """Agent reasoning — low temperature, deterministic."""
        
    async def generate(self, prompt: str, provider: str = "deepseek", **kwargs) -> str:
        """Creative generation — higher temperature."""
```

Configuration:
```yaml
llm:
  providers:
    kimi:
      api_key: "${KIMI_API_KEY}"
      model: "kimi-k2.5"
      base_url: "https://api.moonshot.cn/v1"
    deepseek:
      api_key: "${DEEPSEEK_API_KEY}"
      model: "deepseek-chat"
      base_url: "https://api.deepseek.com/v1"
  default_reasoning: "kimi"
  default_generation: "deepseek"
```

### 6.4 AgentMemory (`memory.py`)

Tiered memory system:
- **Short-term**: Last 24h of execution logs, recent reminders. TTL = 7 days.
- **Long-term**: User preferences, learned patterns, recurring anomaly baselines. Permanent.
- **Context**: Current session state, active goals. In-memory + periodic checkpoint to DB.

### 6.5 StateManager (`state_manager.py`)

Maintains the agent's internal state machine:
- Active goals and their progress
- Current "focus" (what the agent is working on)
- Health of external dependencies (sail_server, OpenCode server, Lark)
- Recent anomalies detected

### 6.6 NotificationEngine (`notification_engine.py`)

Abstracts push channels:
- `lark_im`: Personal chat message via `lark-cli im send-message`
- `lark_group`: Group chat message
- `log`: Write to agent log (fallback)

Queues messages in `agent_reminders` table; a background task flushes the queue.

---

## 7. Agent-Specific DAG Nodes

These nodes extend `NodeExecutor` and are registered with `NodeRegistry` at daemon startup.

### 7.1 `sailzen_cli_node` — Invoke SailZen CLI

Parameters:
```yaml
params:
  module: "finance"           # finance | health
  command: "pull"
  args: ["--account", "1", "--output", "finance.csv"]
  timeout: 300
```

Implementation: wraps `asyncio.create_subprocess_exec("sailzen", module, command, ...)`.

### 7.2 `lark_notify_node` — Send Lark Notification

Parameters:
```yaml
params:
  channel: "im"               # im | group
  target: "user_open_id"      # or group chat_id
  content: "{{ upstream.report_summary }}"   # supports Jinja2 templating
  content_type: "text"        # text | markdown | post
```

Implementation: invokes `lark-cli` subprocess or uses OpenCode `lark-im` skill.

### 7.3 `wellness_node` — Run Wellness Analysis

Parameters:
```yaml
params:
  start_date: "2025-01-01"
  end_date: "2025-12-31"
  label: "annual_2025"
  output_format: "markdown"
```

Implementation: invokes `sailzen-wellness` skill via OpenCode, or runs the underlying `run_analysis.py` script.

### 7.4 `state_check_node` — Check Server State

Parameters:
```yaml
params:
  endpoint: "http://localhost:1974/health"
  expected_status: 200
  extract_fields: ["status"]
```

Use case: Health check before running dependent pipelines.

### 7.5 `llm_reasoning_node` — Direct LLM Reasoning

Parameters:
```yaml
params:
  prompt_template: |
    Based on the following finance data, identify any anomalies:
    {{ upstream.finance_csv }}
  provider: "kimi"
  temperature: 0.3
  max_tokens: 2000
```

Use case: Agent makes decisions without routing through OpenCode skill layer (faster, cheaper for simple reasoning).

### 7.6 `reminder_emit_node` — Emit Reminder

Parameters:
```yaml
params:
  title: "Finance Anomaly Detected"
  content: "{{ upstream.llm_result }}"
  priority: "high"
  channel: "lark_im"
```

Inserts into `agent_reminders` table; NotificationEngine delivers asynchronously.

### 7.7 `condition_node` — Branching Logic

Parameters:
```yaml
params:
  condition: "{{ upstream.state_check.status == 'ok' }}"
  true_next: ["continue_pipeline"]
  false_next: ["send_alert", "abort"]
```

Supports Jinja2 expressions evaluated against upstream results and agent memory.

---

## 8. Pre-Defined Autonomous Pipelines

### 8.1 `daily_standup` — Daily Standup & Agenda Digest

Schedule: `cron: 0 8 * * 1-5` (8:00 AM, Mon-Fri)

Nodes:
1. `state_check`: Verify sail_server health
2. `skill`: `lark-workflow-standup-report` (fetch calendar + tasks)
3. `llm_reasoning`: Summarize and prioritize today's focus
4. `condition`: If high-priority items exist
5. `lark_notify`: Send digest to user IM

### 8.2 `weekly_wellness` — Weekly Financial & Health Check

Schedule: `cron: 0 21 * * 0` (Sunday 9:00 PM)

Nodes:
1. `sailzen_cli`: `health pull-weight` + `finance pull`
2. `wellness`: Run `sailzen-wellness` analysis for past 7 days
3. `llm_reasoning`: Identify trends and anomalies
4. `condition`: If anomalies detected or health thresholds breached
5. `reminder_emit`: Queue wellness alert
6. `lark_notify`: Send summary report

### 8.3 `finance_anomaly_scan` — Daily Finance Anomaly Detection

Schedule: `cron: 0 22 * * *` (10:00 PM daily)

Nodes:
1. `sailzen_cli`: `finance pull --output daily.csv`
2. `llm_reasoning`: Analyze yesterday's transactions for anomalies
3. `condition`: If anomaly score > threshold
4. `reminder_emit`: High-priority alert
5. `lark_notify`: Send alert with details

### 8.4 `health_monitor` — Health Metric Tracking

Schedule: `interval: 3600` (hourly)

Nodes:
1. `state_check`: Check if new weight/exercise data available
2. `sailzen_cli`: `health pull-weight --start today --end today`
3. `condition`: If weight changes significantly (>1kg day-over-day)
4. `reminder_emit`: Health alert

### 8.5 `patch_reminder` — Patch Generation Nudge

Schedule: `cron: 0 23 * * *` (11:00 PM daily)

Nodes:
1. `shell`: `git log origin/$(git branch --show-current)..HEAD --oneline`
2. `condition`: If commits exist ahead of origin
3. `llm_reasoning`: Infer patch topic from commit messages
4. `reminder_emit`: "You have un-patched commits: {topic}"
5. `lark_notify`: Send reminder

### 8.6 `smart_digest` — Adaptive Smart Digest

Schedule: `interval: 1800` (every 30 minutes, lightweight)

Nodes:
1. `state_check`: Quick health check of all services
2. `memory`: Load recent anomalies and pending reminders
3. `condition`: If any actionable items pending and user is "active" (based on calendar free-busy via Lark)
4. `lark_notify`: Send only if user is free — avoid interrupting meetings

---

## 9. Scheduled Task & Autonomy Design

### 9.1 Trigger Types

| Type | Mechanism | Example |
|------|-----------|---------|
| **Cron** | APScheduler cron trigger | Daily at 8 AM |
| **Interval** | APScheduler interval trigger | Every 30 minutes |
| **Event-driven** | Webhook from sail_server (future) | New transaction added |
| **State-driven** | Memory condition check | Remind when weight > threshold |
| **Manual** | API endpoint or CLI | `sailzen-agent trigger daily_standup` |

### 9.2 Autonomy Levels

1. **Fully Autonomous**: Pipeline runs, reasons, and notifies without human gate (e.g., daily digest)
2. **Suggestion Only**: Pipeline runs, generates recommendation, queues for approval (e.g., automatic tagging suggestions)
3. **Alert & Wait**: Pipeline detects anomaly, sends alert, pauses further action until acknowledged

Configured per pipeline:
```yaml
autonomy_level: "fully_autonomous"  # | suggestion | alert_and_wait
approval_required_for:
  - "finance_bulk_update"
  - "lark_doc_write"
```

### 9.3 Retry & Backoff

- DAG node retries: handled by `dag_client` (default 3 retries)
- Pipeline-level retries: if a scheduled run fails, retry after `backoff_seconds` (exponential: 60, 120, 240)
- Dead letter: after max retries, record in `agent_run_log` with status `failed` and notify admin channel

---

## 10. Management API

Optional Litestar sub-app on port `AGENT_API_PORT` (default 9060).

Endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Agent health, DB stats, next scheduled runs |
| GET | `/schedules` | List all schedules |
| POST | `/schedules` | Create new schedule |
| POST | `/schedules/{id}/trigger` | Manual trigger |
| DELETE | `/schedules/{id}` | Delete schedule |
| GET | `/reminders` | List reminders |
| POST | `/reminders/{id}/dismiss` | Dismiss reminder |
| GET | `/memory` | Query memory by key/type |
| POST | `/memory` | Write to memory |
| GET | `/runs` | Execution history |
| GET | `/goals` | List active goals |
| POST | `/goals` | Create goal |
| POST | `/goals/{id}/complete` | Mark goal complete |

---

## 11. Configuration (`agent.yaml`)

```yaml
agent:
  name: "sailzen-autonomous-agent"
  data_dir: "data/agent"
  db_path: "data/agent/db/agent.db"
  log_dir: "logs/agent"
  
  daemon:
    heartbeat_interval: 30
    max_concurrent_pipelines: 3
    
  scheduler:
    timezone: "Asia/Shanghai"
    job_store: "sqlalchemy"   # stores in agent.db
    
  llm:
    providers:
      kimi:
        api_key: "${KIMI_API_KEY}"
        model: "kimi-k2.5"
        base_url: "https://api.moonshot.cn/v1"
      deepseek:
        api_key: "${DEEPSEEK_API_KEY}"
        model: "deepseek-chat"
        base_url: "https://api.deepseek.com/v1"
    default_reasoning: "kimi"
    default_generation: "deepseek"
    
  sail_server:
    api_base: "http://localhost:1974/api/v1"
    # Auth token if needed in future
    
  opencode:
    host: "127.0.0.1"
    port: 4096
    
  notifications:
    default_channel: "lark_im"
    lark:
      user_open_id: "${LARK_USER_OPEN_ID}"
      # lark-cli handles actual auth
      
  pipelines_dir: "sailzen/autonomous_agent/pipelines"
  
  autonomy:
    default_level: "fully_autonomous"
    approval_required_for: []  # list of pipeline IDs
```

Environment variable overrides (prefix `AGENT_`):
- `AGENT_DB_PATH`
- `AGENT_DATA_DIR`
- `AGENT_API_PORT`
- `KIMI_API_KEY`
- `DEEPSEEK_API_KEY`

---

## 12. Deployment & Operations

### 12.1 Startup

```bash
# Development (foreground)
uv run python -m sailzen.autonomous_agent --fg

# Production (daemon mode, via systemd)
uv run python -m sailzen.autonomous_agent
```

### 12.2 Integration with sail_server Lifecycle

The agent is **not** started by `server.py`. It is a separate systemd service or background process.

However, a convenience wrapper can be provided:
```bash
# scripts/start-all.sh
uv run server.py &          # Main API server
sleep 2
uv run python -m sailzen.autonomous_agent &  # Agent daemon
```

### 12.3 Logging

- Uses `sail_server.utils.logging_config` patterns but writes to `logs/agent/`
- Structured JSON logs for machine parsing
- Separate log files:
  - `agent.log` — general operations
  - `agent_scheduler.log` — schedule triggers and completions
  - `agent_llm.log` — LLM calls and responses
  - `agent_notify.log` — notification delivery attempts

### 12.4 Backup

The agent implements its own backup:
```bash
# Triggered via API or scheduled pipeline
POST /backup
# → creates data/agent/backups/agent_backup_YYYYMMDD.tar.gz
```

Contents: `agent.db` + `memory/` + `config/agent.yaml`

**Critical**: This backup is independent of any main-DB backup procedures.

---

## 13. Security & Constraints

1. **No DB Access to sail_server**: Agent only uses HTTP API. Violating this is a critical bug.
2. **API Rate Limiting**: Respect sail_server rate limits. Add delays between bulk CLI calls.
3. **LLM Cost Guardrails**:
   - Max tokens per pipeline run
   - Daily spend cap
   - Alert if approaching cap
4. **Notification Quiet Hours**: Do not send Lark messages between 23:00-08:00 unless `priority: urgent`.
5. **Approval Gates**: For pipelines that could modify data (future expansion), require human approval via Lark interactive cards.
6. **Secrets**: API keys stored in environment variables only, never in `agent.yaml` or DB.

---

## 14. Migration from Previous (Wrong) Design

| Legacy Item | Action | Details |
|-------------|--------|---------|
| `sail_server/migration/agent_job_table.sql` | **Move to `archive/migrations/`** | These tables must not be created in main DB. If they already exist in some environment, document them as deprecated and do not use. |
| `doc/design/agent-system/shadow-agent.md` | **Archive** | Rename to `shadow-agent-v1-deprecated.md`. Add header: "Superseded by autonomous-agent redesign. Do not implement." |
| `sail_server/agent/` (planned) | **Never create** | All agent code goes in `sailzen/autonomous_agent/` |
| Any `agent_jobs` queries in server code | **Remove** | If any experimental code exists, delete it. |
| `sail_configs` table concept | **Migrate to agent.db** | Config lives in agent's isolated SQLite, not main DB. |

---

## 15. Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create `sailzen/autonomous_agent/` package skeleton
- [ ] Implement `AgentDatabase` with isolated SQLite schema
- [ ] Implement `AgentStore` for file workspace
- [ ] Implement `AgentConfig` loader
- [ ] Implement `AgentDaemon` lifecycle (start/stop/signals)
- [ ] Archive/delete legacy migration files
- [ ] Write tests for DB and config layers

### Phase 2: Scheduling & Execution (Week 1-2)
- [ ] Integrate APScheduler with `agent.db` SQLAlchemy store
- [ ] Implement `CronScheduler` wrapper
- [ ] Wire `dag_client` executor into daemon
- [ ] Implement `sailzen_cli_node` and `shell_node`
- [ ] Create first pipeline YAML: `daily_standup`
- [ ] Add manual trigger CLI: `python -m sailzen.autonomous_agent trigger <pipeline>`

### Phase 3: LLM & Reasoning (Week 2)
- [ ] Implement `LLMGateway` for Kimi and DeepSeek
- [ ] Implement `llm_reasoning_node`
- [ ] Implement `condition_node` with Jinja2 expressions
- [ ] Implement `memory.py` (short-term + long-term)
- [ ] Implement `state_manager.py`
- [ ] Create pipeline: `finance_anomaly_scan`

### Phase 4: Notifications & Skills (Week 2-3)
- [ ] Implement `lark_notify_node`
- [ ] Implement `reminder_emit_node`
- [ ] Implement `NotificationEngine`
- [ ] Implement `wellness_node`
- [ ] Create pipelines: `weekly_wellness`, `health_monitor`
- [ ] Add quiet hours and priority filtering

### Phase 5: Management API & Polish (Week 3)
- [ ] Implement management API routes
- [ ] Add health/telemetry endpoints
- [ ] Write systemd service file
- [ ] Write comprehensive tests
- [ ] Update documentation (`doc/design/agent-system/autonomous-agent.md`)
- [ ] Add backup/restore commands

### Phase 6: Autonomy Hardening (Week 4)
- [ ] Add retry/backoff policies
- [ ] Add LLM cost guardrails
- [ ] Add dead-letter queue for failed pipelines
- [ ] Add smart digest pipeline with calendar free-busy check
- [ ] Performance tuning and long-running stability tests

---

## 16. Complete File Inventory

### New Files to Create

```
sailzen/autonomous_agent/__init__.py
sailzen/autonomous_agent/__main__.py
sailzen/autonomous_agent/daemon.py
sailzen/autonomous_agent/config.py
sailzen/autonomous_agent/db.py
sailzen/autonomous_agent/scheduler.py
sailzen/autonomous_agent/memory.py
sailzen/autonomous_agent/llm_gateway.py
sailzen/autonomous_agent/state_manager.py
sailzen/autonomous_agent/notification_engine.py
sailzen/autonomous_agent/store.py

sailzen/autonomous_agent/nodes/__init__.py
sailzen/autonomous_agent/nodes/sailzen_cli_node.py
sailzen/autonomous_agent/nodes/lark_notify_node.py
sailzen/autonomous_agent/nodes/wellness_node.py
sailzen/autonomous_agent/nodes/state_check_node.py
sailzen/autonomous_agent/nodes/llm_reasoning_node.py
sailzen/autonomous_agent/nodes/reminder_emit_node.py
sailzen/autonomous_agent/nodes/condition_node.py

sailzen/autonomous_agent/pipelines/daily_standup.yaml
sailzen/autonomous_agent/pipelines/weekly_wellness.yaml
sailzen/autonomous_agent/pipelines/finance_anomaly_scan.yaml
sailzen/autonomous_agent/pipelines/health_monitor.yaml
sailzen/autonomous_agent/pipelines/patch_reminder.yaml
sailzen/autonomous_agent/pipelines/smart_digest.yaml

sailzen/autonomous_agent/api/__init__.py
sailzen/autonomous_agent/api/routes.py

sailzen/autonomous_agent/templates/daily_standup.md.j2
sailzen/autonomous_agent/templates/wellness_alert.md.j2
sailzen/autonomous_agent/templates/finance_digest.md.j2

doc/design/agent-system/autonomous-agent.md
scripts/agent-daemon.service   # systemd unit file
```

### Files to Modify

```
sailzen/dag_client/nodes/registry.py          # Allow external node registration
sailzen/dag_client/config.py                  # Add agent_pipelines_dir option
scripts/db_sync.py                            # Exclude data/agent/ from sync
pyproject.toml / uv.lock                      # Add apscheduler dependency
```

### Files to Archive/Delete

```
sail_server/migration/agent_job_table.sql     # MOVE → archive/migrations/
doc/design/agent-system/shadow-agent.md       # RENAME → shadow-agent-v1-deprecated.md
```

### Files to Leave Untouched

```
sail_bot/                                     # Explicitly out of scope
sail_server/agent/                            # Do not create
sail_server/db.py                             # No agent tables added
```

---

## 17. Success Criteria

1. **Isolation Proof**: `grep -r "sail_server.db\|Database.get_instance" sailzen/autonomous_agent/` returns zero matches.
2. **DB Independence**: Deleting `data/agent/` does not affect `sail_server` operation in any way.
3. **Autonomy Proof**: Agent can run for 7 days without manual intervention, delivering daily digests and anomaly alerts.
4. **Skill Integration**: Agent successfully invokes `sailzen-wellness`, `lark-calendar`, and `lark-task` skills via DAG pipelines.
5. **Schedule Persistence**: Restarting the agent daemon does not lose configured schedules.
6. **Zero Main-DB Writes**: No INSERT/UPDATE/DELETE against main PostgreSQL/SQLite from agent code.

---

## 18. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Agent DB corruption | WAL mode + periodic `PRAGMA integrity_check` + automated backup |
| LLM API rate limits / costs | Token cap, caching of identical prompts, exponential backoff |
| sail_server downtime | `state_check_node` gates pipelines; agent queues tasks and retries |
| Notification spam | Quiet hours, deduplication (same alert within 4h is suppressed), priority filtering |
| Dag_client version drift | Agent pins to `sailzen.dag_client` public API; integration tests catch breaking changes |
| Circular dependencies | Agent imports dag_client; dag_client NEVER imports agent |

---

**End of Plan**
