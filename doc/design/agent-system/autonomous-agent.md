# SailZen Autonomous Agent System

> **Version**: 1.0
> **Date**: 2025-06-02
> **Status**: Implemented
> **Core Principle**: Complete isolation. The Agent is not a module of `sail_server`; it is a sovereign runtime that *consumes* `sail_server` via HTTP API only.

---

## 1. Architecture Overview

### 1.1 Isolation Boundaries

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

### 1.2 Core Design Principles

1. **Zero Main-DB Touch**: The agent never opens a SQLAlchemy session to `sail_server.db`. All reads are via HTTP API (`sailzen` CLI or direct `httpx` calls).
2. **Sovereign SQLite**: `agent.db` lives in `data/agent/db/` (or configured path). It is excluded from `scripts/db_sync.py` and any backup logic targeting the main DB.
3. **Skill-First Execution**: Complex workflows (wellness, Lark, finance analysis) are executed by invoking OpenCode Skills through the DAG Client's `SkillNode`. The agent orchestrates; skills execute.
4. **Direct LLM for Reasoning**: When the agent needs to make decisions (prioritize reminders, interpret anomalies), it calls Kimi/DeepSeek directly via the Agent's own `LLMGateway`, not through the server's analysis controllers.
5. **Cron-Native**: Scheduling is a first-class citizen, not an afterthought. Recurring pipelines are stored persistently in the agent's SQLite DB.

---

## 2. Module Structure

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
├── store.py                 # AgentStore: isolated file workspace
├── pipelines/               # Pre-defined autonomous pipeline YAMLs
│   ├── daily_standup.yaml
│   ├── weekly_wellness.yaml
│   ├── finance_anomaly_scan.yaml
│   ├── health_monitor.yaml
│   ├── patch_reminder.yaml
│   └── smart_digest.yaml
├── nodes/                   # Agent-specific DAG node types
│   ├── __init__.py
│   ├── sailzen_cli_node.py
│   ├── lark_notify_node.py
│   ├── wellness_node.py
│   ├── state_check_node.py
│   ├── llm_reasoning_node.py
│   ├── reminder_emit_node.py
│   └── condition_node.py
├── api/                     # Management HTTP API (optional, port 9060)
│   ├── __init__.py
│   └── routes.py
└── templates/               # Jinja2 templates for notifications/reports
    ├── daily_standup.md.j2
    ├── wellness_alert.md.j2
    └── finance_digest.md.j2
```

---

## 3. Database Design (Isolated SQLite)

**File**: `data/agent/db/agent.db` (configurable via `AGENT_DB_PATH` env var)

**Tables**:

- `agent_schedules` — Cron and interval schedules
- `agent_memories` — Short-term and long-term memory
- `agent_reminders` — Notification queue
- `agent_goals` — High-level objectives
- `agent_run_log` — Pipeline execution history (agent's view)
- `apscheduler_jobs` — APScheduler's internal job store

**Key constraint**: `db_sync.py` must NEVER see this file. It lives outside the main DB URI entirely.

---

## 4. Workspace Design (Isolated File System)

**Root**: `data/agent/` (configurable via `AGENT_DATA_DIR`)

```
data/agent/
├── db/
│   └── agent.db
├── runs/
│   └── {pipeline_run_id}/
│       ├── artifacts/
│       ├── logs/
│       └── report.md
├── memory/
│   └── context_snapshots/
├── notifications/
│   ├── queued/
│   └── sent/
├── backups/
│   └── agent_backup_YYYYMMDD.tar.gz
└── config/
    └── agent.yaml
```

- `data/agent/` is excluded from main project backup scripts.
- The agent implements its own `AgentStore` (similar to `DAGStore`) for file operations.

---

## 5. Core Components

### 5.1 AgentDaemon (`daemon.py`)

Main lifecycle orchestrator:
- Initialize isolated DB and workspace
- Start CronScheduler
- Start DAG Executor (reused from `sailzen.dag_client`)
- Register agent-specific nodes into `NodeRegistry`
- Run the main event loop
- Graceful shutdown handling

### 5.2 CronScheduler (`scheduler.py`)

Uses **APScheduler** with SQLAlchemyJobStore pointing to `agent.db`.

Capabilities:
- `add_cron(pipeline_id, cron_expr, params)`
- `add_interval(pipeline_id, seconds, params)`
- `trigger_now(pipeline_id, params)` — manual/ad-hoc execution
- Persistent: schedules survive daemon restarts
- Timezone-aware (default `Asia/Shanghai`)

### 5.3 LLMGateway (`llm_gateway.py`)

Direct clients for Kimi and DeepSeek, independent of `sail_server.utils.llm`.

```python
gateway = LLMGateway(config.llm)
response = await gateway.reason(prompt, provider="kimi")
response = await gateway.generate(prompt, provider="deepseek")
```

### 5.4 AgentMemory (`memory.py`)

Tiered memory system:
- **Short-term**: Last 24h of execution logs, recent reminders. TTL = 7 days.
- **Long-term**: User preferences, learned patterns. Permanent.
- **Context**: Current session state, active goals. In-memory + periodic checkpoint to DB.

### 5.5 StateManager (`state_manager.py`)

Maintains the agent's internal state machine:
- Active goals and their progress
- Current "focus"
- Health of external dependencies (sail_server, OpenCode server, Lark)
- Recent anomalies detected

### 5.6 NotificationEngine (`notification_engine.py`)

Abstracts push channels:
- `lark_im`: Personal chat message
- `lark_group`: Group chat message
- `log`: Write to agent log (fallback)

Features:
- Quiet hours: No non-urgent messages between 23:00-08:00
- Deduplication: Same alert within 4h is suppressed
- Priority filtering

---

## 6. Agent-Specific DAG Nodes

| Node | Type | Purpose |
|------|------|---------|
| `sailzen_cli` | SailZenCliNode | Invoke `sailzen finance/health ...` |
| `lark_notify` | LarkNotifyNode | Send Lark IM / group messages |
| `wellness` | WellnessNode | Trigger sailzen-wellness skill |
| `state_check` | StateCheckNode | HTTP health checks against sail_server |
| `llm_reasoning` | LLMReasoningNode | Direct LLM call for agent reasoning |
| `reminder_emit` | ReminderEmitNode | Emit a reminder to configured channels |
| `condition` | ConditionNode | Branching logic based on state/memory |

---

## 7. Pre-Defined Pipelines

### 7.1 `daily_standup`
- **Schedule**: `0 8 * * 1-5` (8:00 AM, Mon-Fri)
- **Nodes**: health_check → standup_skill → summarize → condition → lark_notify

### 7.2 `weekly_wellness`
- **Schedule**: `0 21 * * 0` (Sunday 9:00 PM)
- **Nodes**: pull_health + pull_finance → wellness_analysis → analyze_trends → condition → reminder + notify

### 7.3 `finance_anomaly_scan`
- **Schedule**: `0 22 * * *` (10:00 PM daily)
- **Nodes**: pull_daily → analyze_anomalies → condition → alert + notify

### 7.4 `health_monitor`
- **Schedule**: `interval: 3600` (hourly)
- **Nodes**: check_data → pull_weight → analyze_change → condition → health_alert

### 7.5 `patch_reminder`
- **Schedule**: `0 23 * * *` (11:00 PM daily)
- **Nodes**: check_commits → condition → infer_topic → emit_reminder + send_reminder

### 7.6 `smart_digest`
- **Schedule**: `interval: 1800` (every 30 minutes)
- **Nodes**: quick_health → check_actionable → condition → check_free → condition → notify

---

## 8. Configuration (`agent.yaml`)

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
    job_store: "sqlalchemy"

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

  opencode:
    host: "127.0.0.1"
    port: 4096

  notifications:
    default_channel: "lark_im"
    lark:
      user_open_id: "${LARK_USER_OPEN_ID}"

  pipelines_dir: "sailzen/autonomous_agent/pipelines"

  autonomy:
    default_level: "fully_autonomous"
    approval_required_for: []
```

Environment variable overrides (prefix `AGENT_`):
- `AGENT_DB_PATH`
- `AGENT_DATA_DIR`
- `AGENT_API_PORT`
- `KIMI_API_KEY`
- `DEEPSEEK_API_KEY`

---

## 9. Deployment

### 9.1 Startup

```bash
# Development (foreground)
uv run python -m sailzen.autonomous_agent --fg

# Production (daemon mode, via systemd)
uv run python -m sailzen.autonomous_agent
```

### 9.2 Systemd Service

See: `scripts/agent-daemon.service`

```bash
sudo cp scripts/agent-daemon.service /etc/systemd/system/sailzen-agent@$USER.service
sudo systemctl enable --now sailzen-agent@$USER
```

---

## 10. Security & Constraints

1. **No DB Access to sail_server**: Agent only uses HTTP API. Violating this is a critical bug.
2. **API Rate Limiting**: Respect sail_server rate limits.
3. **LLM Cost Guardrails**: Max tokens per pipeline run, daily spend cap.
4. **Notification Quiet Hours**: Do not send Lark messages between 23:00-08:00 unless `priority: urgent`.
5. **Approval Gates**: For pipelines that could modify data, require human approval.
6. **Secrets**: API keys stored in environment variables only, never in `agent.yaml` or DB.

---

## 11. Success Criteria

1. **Isolation Proof**: `grep -r "sail_server.db\|Database.get_instance" sailzen/autonomous_agent/` returns zero matches.
2. **DB Independence**: Deleting `data/agent/` does not affect `sail_server` operation in any way.
3. **Autonomy Proof**: Agent can run for 7 days without manual intervention, delivering daily digests and anomaly alerts.
4. **Skill Integration**: Agent successfully invokes `sailzen-wellness`, `lark-calendar`, and `lark-task` skills via DAG pipelines.
5. **Schedule Persistence**: Restarting the agent daemon does not lose configured schedules.
6. **Zero Main-DB Writes**: No INSERT/UPDATE/DELETE against main PostgreSQL/SQLite from agent code.

---

## 12. Migration from Previous (Wrong) Design

| Legacy Item | Action | Details |
|-------------|--------|---------|
| `sail_server/migration/agent_job_table.sql` | **Moved to `archive/migrations/`** | These tables must not be created in main DB. |
| `doc/design/agent-system/shadow-agent.md` | **Renamed to `shadow-agent-v1-deprecated.md`** | Superseded by this document. |
| `sail_server/agent/` (planned) | **Never create** | All agent code goes in `sailzen/autonomous_agent/` |
| Any `agent_jobs` queries in server code | **Remove** | If any experimental code exists, delete it. |
| `sail_configs` table concept | **Migrate to agent.db** | Config lives in agent's isolated SQLite. |

---

*End of Document*
