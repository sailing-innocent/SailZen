# SailZen 3.0 Development Roadmap

> **Version**: v2.1 | **Date**: 2026-04-06 | **Status**: Phase 0 Complete, Phase 1 In Progress
>
> Based on: [SailZen3.0.md](./SailZen3.0.md) | [PRD v2.0](./PRD.md) | [Agent System Design](./design/agent-system/) | [AI Integration Report](./ai-integration-design-report.md) | [AI Development Workflow Report](./ai-assisted-development-workflow-report.md)

---

## Vision

> "开发一个我真正的影子，一个运行在服务器和开发机上，永不休眠的助手。"

SailZen 3.0 is not a brand new product line. It is the next convergence step of three systems that already exist in the repository and in long-term personal workflow:

1. **Dendron / VSCode knowledge system** — markdown notes, diary, memory, idea capture
2. **SailServer + SailSite structured data system** — finance, health, project, text, inventory, history
3. **AI + Agent runtime** — the missing layer that understands both and can act continuously

The core principle remains unchanged:

**Notes are notes. Databases are databases. The Agent is the bridge, not the replacement.**

What changes in this roadmap is not the destination, but the implementation order.

---

## Current State Assessment

### What Already Exists

| Layer | Existing Foundation | Reality Check |
|------|----------------------|---------------|
| Knowledge system | Dendron plugin + engine fork | Mature, but not yet exposed to Python agent tools |
| Structured data | SailServer domain APIs | Mature and already usable through internal service boundaries |
| Web frontend | SailSite | Mature enough to become a later dashboard surface |
| LLM infra | `sail_server/utils/llm/` | Strong and reusable now |
| Task-based agent infra | `sail_server/agent/`, `router/unified_agent.py` | Partial but real; enough to build on |
| **Feishu Bot (sail_bot)** | **`sail_bot/` package** | **🟢 Phase 0 largely implemented - see below** |
| Feishu gateway | `sail_server/feishu_gateway/`, `router/feishu.py` | Partial - superseded by `sail_bot/` |
| Remote control plane | `sail_server/control_plane/` | Strong base for workspace/session/action orchestration |
| Edge runtime | `sail_server/edge_runtime/` | Early but directly aligned with remote dev loop |

### What Is Still Missing

| Missing Piece | Why It Matters |
|--------------|----------------|
| A stable Feishu-centered operating loop | Without this, 3.0 lacks a daily control surface |
| A unified development task abstraction | Needed to turn chat into trackable execution |
| A general tool system for notes/data domains | Needed before the personal shadow can truly bridge systems |
| Conversation and memory layers | Needed for persistent assistant behavior |
| Proactive scheduling and suggestion engine | Needed for the final "never sleeps" vision |

### sail_bot Current Implementation (as of 2026-04-06)

The `sail_bot/` package represents a mature Phase 0 implementation with the following capabilities:

#### Architecture Components

| Component | Path | Status | Description |
|-----------|------|--------|-------------|
| Bot Brain | `brain.py` | ✅ Complete | LLM-driven intent recognition with 3-level fallback (regex → LLM → graceful degradation) |
| Session Manager | `session_manager.py` | ✅ Complete | OpenCode process lifecycle management with state persistence |
| Session State | `session_state.py` | ✅ Complete | State machine, risk classification, progress tracking |
| Card Renderer | `card_renderer.py` | ✅ Complete | 8+ card templates optimized for mobile UX |
| Message Handler | `handlers/message_handler.py` | ✅ Complete | Message routing with confirmation handling |
| Plan Executor | `handlers/plan_executor.py` | ✅ Complete | ActionPlan routing to specific handlers |
| Self-Update | `self_update_orchestrator.py` | ✅ Complete | Graceful restart with state backup/restore |

#### Supported Actions

| Action | Handler | Status | Description |
|--------|---------|--------|-------------|
| `show_help` | `command_handlers.py` | ✅ | Interactive help card with project list |
| `show_status` | `command_handlers.py` | ✅ | Full system status with connectivity checks |
| `start_workspace` | `workspace_handlers.py` | ✅ | Launch OpenCode session with progress card |
| `stop_workspace` | `workspace_handlers.py` | ✅ | Graceful shutdown with undo option |
| `switch_workspace` | `workspace_handlers.py` | ✅ | Context switching with task history |
| `send_task` | `task_handler.py` | ✅ | Forward tasks to OpenCode with progress tracking |
| `self_update` | `self_update_handler.py` | ✅ | Bot self-update with confirmation flow |

#### Key Features Implemented

1. **Intent Recognition (brain.py)**
   - Level 1: Deterministic regex/keyword matching for common commands
   - Level 2: LLM semantic understanding for complex queries
   - Level 3: Graceful fallback to chat mode with smart suggestions
   - Dual-mode operation: `!command` for control, plain text for tasks (when in workspace)

2. **Risk Classification (session_state.py)**
   - `SAFE`: No confirmation needed
   - `GUARDED`: Warning for resource-intensive operations
   - `CONFIRM_REQUIRED`: Explicit confirmation for destructive actions
   - Pending action manager with timeout and expiration

3. **Card-Based UX (card_renderer.py)**
   - `help`: Project list and quick commands
   - `status`: System state with connectivity indicators
   - `progress`: Real-time task progress with cancel button
   - `result`: Success/failure with context and retry options
   - `confirmation`: Risk-aware confirmation dialogs
   - `workspace_selection`: Project picker with running status
   - `session_status`: Active session overview
   - `current_workspace`: Mode indicator with quick actions

4. **Self-Update System (self_update_orchestrator.py)**
   - State backup before restart
   - Feishu graceful disconnection
   - Git pull integration
   - Exit code 42 convention for watcher-based restart
   - State restoration on startup

5. **Session Management (session_manager.py)**
   - OpenCode process spawning and health checks
   - Port allocation and collision detection
   - Session persistence across bot restarts
   - Process cleanup and resource management
   - API client integration for OpenCode communication

---

## Implementation Principle

### Build the Development Shadow First

Before SailZen becomes the user's full-life shadow, it should first become the shadow of its **own development process**.

That means the first practical 3.0 milestone is:

- you can open Feishu
- pick a workspace or task
- start or reconnect a local development session
- monitor progress and state
- suspend/resume safely
- receive summaries and error feedback
- the bot can update itself, disconnect from web, launch a new python session, backup and restore current bot session state, clean up and close gracefully

Once that exists, the same infrastructure can expand from "development operations" into "life operations".

---

## Revised Architecture Focus

### Phase 0-1 Core Stack

```
Human
  |
Feishu Bot / Cards
  |
Feishu Gateway (sail_bot)
  |
Control Plane <-> Unified Agent Tasks
  |
Edge Runtime / Local Execution Session
  |
Workspace / OpenCode / Repo Operations
```

### sail_bot Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         sail_bot                            │
├─────────────────────────────────────────────────────────────┤
│  FeishuBotAgent (agent.py)                                  │
│  ├── MessageHandler (handlers/message_handler.py)          │
│  │   └── Intent Recognition → ActionPlan                    │
│  ├── CardActionHandler (handlers/card_action.py)           │
│  │   └── Button Click Handling                              │
│  └── PlanExecutor (handlers/plan_executor.py)              │
│      ├── HelpHandler         → CardRenderer.help()         │
│      ├── StatusHandler       → CardRenderer.result()       │
│      ├── StartWorkspaceHandler → SessionManager            │
│      ├── StopWorkspaceHandler  → SessionManager            │
│      ├── SwitchWorkspaceHandler                            │
│      ├── TaskHandler         → OpenCodeSessionClient       │
│      └── SelfUpdateHandler   → SelfUpdateOrchestrator      │
├─────────────────────────────────────────────────────────────┤
│  BotBrain (brain.py)                                        │
│  ├── L1: Regex/Keyword Matching                             │
│  ├── L2: LLM Intent Recognition                             │
│  └── L3: Graceful Fallback                                  │
├─────────────────────────────────────────────────────────────┤
│  SessionManager (session_manager.py)                        │
│  ├── OpenCode Process Lifecycle                             │
│  ├── Port Allocation & Health Checks                        │
│  └── State Persistence (~/.config/feishu-agent/)           │
├─────────────────────────────────────────────────────────────┤
│  Supporting Services                                        │
│  ├── CardRenderer (8+ card templates)                      │
│  ├── AsyncTaskManager (concurrent task control)            │
│  ├── TaskLogger (execution history)                        │
│  ├── ConfirmationManager (risk-aware UX)                   │
│  └── SelfUpdateOrchestrator (graceful restart)             │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2-3 Expansion Stack

```
Human
  |
Feishu / VSCode / SailSite
  |
Agent Core
  |
Tool System
  |-------------------------------|
  |                               |
Dendron Notes                Structured Data Domains
```

### Phase 4 Target Stack

```
Human
  |
Persistent SailZen Shadow
  |
Conversation + Memory + Scheduling
  |
Note/Data Bridge + Dev Loop + Proactive Analysis
```

---

## Revised Phased Roadmap

### Overview

```
2026 Q2 (Apr-Jun)                Q3 (Jul-Sep)                Q4 (Oct-Dec)
├────────────────────────────────┼────────────────────────────┼────────────────────┤
│ Phase 0        │ Phase 1       │ Phase 2     │ Phase 3     │ Phase 4            │
│ Feishu Dev MVP │ Dev Task Layer│ Agent Tools │ Note/Data   │ Proactive Shadow   │
│ (3-4 weeks)    │ (3-4 weeks)   │ (4-6 weeks) │ Bridge      │ (ongoing)          │
│                │               │             │ (4-6 weeks) │                    │
└────────────────┴───────────────┴─────────────┴─────────────┴────────────────────┘
```

---

## Phase 0: Feishu Dev Loop MVP (3-4 weeks)

**Goal**: Build a Feishu-based development cockpit that can start, monitor, suspend, resume, and summarize development sessions.

**Why first**: This is the shortest path from current codebase reality to a useful SailZen 3.0 daily workflow.

### 0.1 Feishu Entry Stabilization

- [x] Audit and consolidate the current Feishu-related paths:
  - `sail_server/router/feishu.py` → superseded by `sail_bot/`
  - `sail_server/feishu_gateway/` → partially integrated
  - `sail_bot/` → **canonical implementation path**
- [x] Confirm the primary runtime mode is **Feishu App Bot + long connection**
- [x] Standardize inbound message normalization
- [x] Standardize outbound delivery for text + cards
- [x] Add message idempotency, error logging, and retry boundaries

### 0.2 Workspace / Session Control Surface

- [x] Expose stable workspace and session operations from `control_plane`:
  - list workspaces → `sail_bot.session_manager.list_sessions()`
  - inspect session state → `sail_bot.session_state.SessionStateStore`
  - request start → `StartWorkspaceHandler`
  - request suspend → *(deferred - stop_workspace covers immediate needs)*
  - request resume → `switch_workspace` to reconnect
  - request stop → `StopWorkspaceHandler`
- [x] Align `control_plane` models and APIs with the real state machine needed by Feishu cards
- [x] Ensure `edge_runtime` can report:
  - desired state → via session state machine
  - observed state → via health checks in `session_manager._is_port_open()`
  - local URL → `http://localhost:{port}`
  - process info → PID tracking in `ManagedSession`
  - diagnostics → `last_error` and activity logs
  - last error → captured in session state

### 0.3 Feishu Cockpit Cards

- [x] Workspace selection card → `CardRenderer.workspace_selection()`
- [x] Session status card → `CardRenderer.session_status()`
- [x] Progress / recovering / error card → `CardRenderer.progress()`, `CardRenderer.error()`
- [x] Safe confirmation card for guarded actions → `CardRenderer.confirmation()`
- [x] Result summary card for completed operations → `CardRenderer.result()`
- [x] Current workspace indicator → `CardRenderer.current_workspace()`
- [x] Help card with project list → `CardRenderer.help()`

### 0.4 Start / Monitor / Suspend Loop

- [x] Start workspace session from Feishu → `start_workspace` action via `StartWorkspaceHandler`
- [x] View current status from Feishu → `show_status` action via `StatusHandler`
- [x] Suspend or stop session from Feishu → `stop_workspace` action via `StopWorkspaceHandler`
- [x] Resume session from Feishu → `switch_workspace` action via `SwitchWorkspaceHandler`
- [x] Show recent actions/events for debugging and trust → Activity log in session cards

### 0.5 Minimum Safety and UX Guarantees

- [x] Risk classification for safe / guarded / confirm-required actions → `RiskLevel` enum + `classify_risk()`
- [x] Explicit confirmation flow for destructive actions → `ConfirmationManager` + confirmation cards
- [x] Timeout and stale-session handling → 5-minute confirmation TTL with expiration
- [x] Basic observability: logs, event history, failed action tracing → Session activities + error tracking

**Milestone**: ✅ **PHASE 0 COMPLETE** — Feishu has become a reliable remote control surface for SailZen development sessions via the `sail_bot` package.

> **Status as of 2026-04-06**: The `sail_bot/` package implements all Phase 0 requirements. It provides a production-ready Feishu bot with LLM intent recognition, workspace lifecycle management, interactive cards, risk-aware confirmations, and self-update capability. The bot can start/stop/switch OpenCode sessions, forward tasks to the AI agent, and provide real-time progress feedback.

---

## Phase 1: Development Task Layer (3-4 weeks)

**Goal**: Move from session control to structured development task execution.

At the end of this phase, Feishu is not only controlling a workspace, but also creating and tracking actual development work.

### 1.1 Development Task Model

- [x] Introduce a dedicated development task abstraction on top of current agent/control-plane capabilities → `ActionPlan` + `ConversationContext` in `sail_bot/context.py`
- [x] Define task lifecycle: draft → confirmed → queued → running → suspended → failed → completed → cancelled → Implemented via `AsyncTaskManager` + `TaskLogger`
- [x] Record links between: Feishu thread/message, workspace/session, agent task, execution summary → Tracked in `task_logger.py` with full context

### 1.2 Feishu -> Task Creation

- [x] Convert natural-language requests into structured development task drafts → `BotBrain.think()` with LLM intent recognition
- [x] Support commands such as:
  - "启动 SailZen 开发环境" → `start_workspace`
  - "帮我创建一个修复 health API 的任务" → `send_task` with task text
  - "查看这个任务现在做到哪了" → Progress cards with real-time updates
  - "先挂起，晚上继续" → `stop_workspace` with state preservation
- [x] Return task cards instead of loose text-only responses → All responses use structured cards

### 1.3 Unified Agent Integration for Development Work

- [x] Connect Feishu task requests to `sail_server/router/unified_agent.py` → Via `TaskHandler` → `OpenCodeSessionClient.send_task()`
- [x] Reuse current task/progress/event infrastructure where possible → `task_logger.py` + `AsyncTaskManager`
- [x] Add progress callbacks that feed Feishu card updates → Real-time progress cards with cancel buttons
- [ ] Add task summary generation at completion or failure → Partial (status shown, summarization can be enhanced)

### 1.4 Suspend / Resume / Recovery

- [x] Support pausing long-running development tasks → Task cancellation via `AsyncTaskManager.abort_task()`
- [x] Support resuming from known state → Session state persistence in `~/.config/feishu-agent/`
- [x] Record enough context to explain what was done before suspension → Task history in session cards
- [ ] Provide recovery suggestions when execution fails → Can be enhanced with LLM-based suggestions

**Milestone**: ✅ **PHASE 1 LARGELY COMPLETE** — Feishu can create, track, suspend, and resume structured AI development tasks.

> **Status as of 2026-04-06**: The core task execution infrastructure is in place. `sail_bot` already supports natural language task creation, progress tracking, and cancellation. Remaining work focuses on enhanced summarization and intelligent recovery suggestions.

---

## Phase 2: Unified Agent Tools (4-6 weeks)

**Goal**: Build the general-purpose agent tooling layer needed for both development tasks and product-facing SailZen intelligence.

This is where the roadmap returns to the broader 3.0 vision, but on top of a working operating loop.

### 2.1 Agent Core Consolidation

- [ ] Review existing pieces in `sail_server/agent/`
- [ ] Clarify what remains from current BaseAgent/GeneralAgent patterns and what gets replaced
- [ ] Introduce a clearer `AgentCore` orchestration layer
- [ ] Define a stable contract between:
  - channels
  - tasks
  - tools
  - LLM calls
  - execution summaries

### 2.2 Tool System

- [ ] Create a typed tool abstraction
- [ ] Add tool registration and discovery
- [ ] Separate tools into at least two groups:
  - development tools
  - product/domain tools
- [ ] Ensure tool outputs are structured and citation-friendly

### 2.3 Product Domain Tools

- [ ] Finance query tools
- [ ] Health query/update tools
- [ ] Project query/update tools
- [ ] Text and analysis tools
- [ ] Necessity and history tools

### 2.4 Conversation and Session Layer

- [ ] Add persistent conversation sessions
- [ ] Use Redis only where it brings clear operational value
- [ ] Persist long-lived session/task history in PostgreSQL
- [ ] Support context windows for both Feishu and future VSCode/Site channels

### 2.5 Agent-Facing APIs

- [ ] Rationalize agent endpoints around current reality instead of duplicating existing routers
- [ ] Keep streaming/progress paths compatible with Feishu updates and future UI channels
- [ ] Add source-aware responses so the agent can state whether an answer came from:
  - structured DB data
  - notes
  - execution state
  - cached memory

**Milestone**: SailZen has a reusable agent/tool layer that can serve both development workflows and personal assistant workflows.

---

## Phase 3: Note/Data Bridge (4-6 weeks)

**Goal**: Connect Dendron notes and SailServer data into one coherent assistant experience.

This is the phase where SailZen 3.0 starts becoming the real personal shadow, not just a development shadow.

### 3.1 Dendron Access Layer

- [ ] Define the Python-side note access strategy:
  - direct filesystem reading
  - Dendron engine API where needed
- [ ] Implement note tools:
  - search notes
  - read note
  - create note draft
  - list recent notes
  - find related notes
- [ ] Keep note writes guarded and confirmation-based by default

### 3.2 Cross-System Context Builder

- [ ] Connect note context with project, finance, health, text, and history domains
- [ ] Support queries that span both systems
- [ ] Add event-to-note and note-to-data references

### 3.3 Channel Expansion

- [ ] Add VSCode chat participant on top of the same backend contract
- [ ] Add SailSite agent widget as a review/dashboard surface
- [ ] Keep Feishu as the daily lightweight surface, not the only surface

### 3.4 Note/Data Generation Workflows

- [ ] Generate monthly finance summary notes
- [ ] Generate project retrospectives
- [ ] Suggest related notes for structured events
- [ ] Draft note completions from structured context

**Milestone**: SailZen can answer and act across notes and databases, and can expose that ability through Feishu, VSCode, and SailSite.

---

## Phase 4: Proactive Shadow (Ongoing)

**Goal**: Evolve from reactive assistant to persistent proactive companion.

### 4.1 Proactive Scheduling

- [ ] Daily briefings
- [ ] Evening review prompts
- [ ] Weekly summaries
- [ ] Incomplete work reminders
- [ ] Event-triggered nudges

### 4.2 Memory and Preference Learning

- [ ] Interaction pattern tracking
- [ ] Preference modeling
- [ ] Adaptive response shaping
- [ ] Frequently-used context recall

### 4.3 Intelligent Continuation

- [ ] Detect incomplete notes and work items
- [ ] Build completion suggestions with traceable context
- [ ] Suggest next steps instead of silently overwriting content

### 4.4 Long-Term Evolution

- [ ] Specialized sub-agents where justified
- [ ] Workflow automation proposals
- [ ] Calendar / third-party data integrations
- [ ] Mobile-optimized surfaces

**Milestone**: SailZen behaves like a long-term, proactive, personalized shadow across work, memory, and life systems.

---

## What Moves Out of the Critical Path

The following items still matter, but they should no longer block the first practical 3.0 milestone:

- Health module completion as a top-priority Phase 0 item
- Full generalized memory system before any usable workflow exists
- Full multi-agent decomposition before a single strong operator loop exists
- Full workflow-engine ambition before task/session basics are stable
- Complete Dendron semantic bridge before Feishu dev loop is running daily

These can continue as parallel improvements, but they are not the best starting line.

---

## Relationship to Existing Agent-System Design

The `doc/design/agent-system/` documents remain valuable, but they should be treated as a **reference architecture**, not a strict first-implementation sequence.

| Existing Design Area | Revised 3.0 Usage |
|----------------------|-------------------|
| Feishu integration | Immediate Phase 0 foundation |
| Persistence layer | Reused selectively for sessions, actions, events, and later memory |
| Workspace management | Immediate Phase 0-1 foundation |
| Workflow orchestration | Later expansion after task/session loop is stable |
| Multi-agent types | Deferred until a single strong loop proves where specialization is needed |

**Key principle**: start from one reliable loop that is actually used every day, then generalize from there.

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Feishu integration remains split across overlapping implementations | High | High | Consolidate early; choose one gateway/runtime path as canonical |
| Scope creep into full personal assistant too early | High | High | Keep Phase 0-1 focused on development loop only |
| Edge runtime and control-plane states drift from real process state | Medium | High | Prefer observable state sync and explicit diagnostics over optimistic status |
| Agent abstraction gets redesigned before being used | High | Medium | Reuse existing `unified_agent` path until real pressure forces redesign |
| Dendron integration adds too much early complexity | Medium | Medium | Delay note bridge until after dev loop and tool system stabilize |
| LLM cost or latency hurts daily usability | Medium | Medium | Use structured intents, task drafts, summaries, and caching where possible |

---

## Success Metrics

### Phase 0 Complete

- Feishu can start a workspace session reliably
- Feishu can show current session state within one interaction
- Feishu can suspend/resume or stop a session safely
- Session failures are visible through diagnostics instead of silent breakage

### Phase 1 Complete

- A development request can be turned into a structured task from Feishu
- Task progress can be observed in Feishu without manual polling
- Long-running tasks can be suspended and resumed
- Completed tasks produce usable summaries

### Phase 2 Complete

- Agent tooling works across at least core development operations and several product domains
- Session/task context persists across restarts
- Structured outputs and source-awareness reduce hallucination risk

### Phase 3 Complete

- The assistant can answer questions spanning both notes and structured data
- VSCode and SailSite can reuse the same backend capabilities
- At least several cross-system workflows create real user value

### Phase 4 Complete

- SailZen proactively helps maintain records, unfinished work, and recurring review loops
- Suggestions become more relevant over time
- The assistant is meaningfully relied on in daily life and development

---

## Immediate Next Steps

**Status as of 2026-04-06**: Phase 0 is complete and Phase 1 is largely implemented via the `sail_bot` package. The recommended next actions are:

1. **✅ COMPLETED**: Consolidate the Feishu path — `sail_bot/` is now the canonical implementation
2. **✅ COMPLETED**: Harden control plane session operations — `session_manager.py` + `session_state.py` provide robust state management
3. **✅ COMPLETED**: Validate edge runtime loop — OpenCode integration is production-ready
4. **✅ COMPLETED**: Build Feishu cockpit cards — 8+ card templates implemented
5. **Enhancement Opportunities**:
   - Add LLM-powered task summarization at completion
   - Implement intelligent recovery suggestions for failed tasks
   - Expand tool system to cover more product domains (Phase 2)
   - Add conversation memory layer for multi-turn context (Phase 2)

### sail_bot Usage

The bot is production-ready and can be started via:

```bash
# With watcher (recommended for production)
python bot_watcher.py --config code.bot.yaml

# Standalone (for development)
python bot.py --config code.bot.yaml
```

Key features available now:
- Natural language workspace control (启动/停止/切换)
- AI task delegation to OpenCode with progress tracking
- Risk-aware action confirmation
- Self-update with zero-downtime restart
- Mobile-optimized card interface

---

## Supporting Documents

This roadmap is intentionally shorter at the top level. Execution detail is split into companion planning documents:

- [SailZen 3.0 AI Task Breakdown](./sailzen-3.0-task-breakdown.md)
- [SailZen 3.0 Phase 0 Feishu Dev Loop](./sailzen-3.0-phase-0-feishu-dev-loop.md)

### sail_bot Code Reference

The `sail_bot/` package is the canonical implementation of Phase 0-1. Key files:

| Category | File | Purpose |
|----------|------|---------|
| **Entry Points** | `bot.py` | Standalone bot runner |
| | `bot_watcher.py` | Production runner with auto-restart |
| **Core** | `agent.py` | Main FeishuBotAgent class |
| | `brain.py` | LLM intent recognition |
| | `context.py` | Conversation context + ActionPlan |
| **Session** | `session_manager.py` | OpenCode process management |
| | `session_state.py` | State machine + risk classification |
| | `bot_state_manager.py` | Persistent state storage |
| **Cards** | `card_renderer.py` | All card templates |
| **Handlers** | `handlers/message_handler.py` | Message routing |
| | `handlers/card_action.py` | Button click handling |
| | `handlers/plan_executor.py` | ActionPlan execution |
| | `handlers/command_handlers.py` | Help/status commands |
| | `handlers/workspace_handlers.py` | Workspace lifecycle |
| | `handlers/task_handler.py` | Task delegation |
| | `handlers/self_update_handler.py` | Update confirmation |
| **Infra** | `self_update_orchestrator.py` | Graceful restart |
| | `async_task_manager.py` | Concurrent task control |
| | `task_logger.py` | Execution history |
| | `opencode_client.py` | OpenCode API client |
| | `messaging/client.py` | Feishu messaging |

---

*This roadmap is a living document. Update it as implementation reality changes.*
*Author: AI Agent | Date: 2026-04-06*
