# SailZen 3.0 Development Roadmap

> **Version**: v2.0 | **Date**: 2026-03-29 | **Status**: Draft
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

## Strategic Shift

### Old Priority

1. Foundation cleanup
2. General Agent core
3. Feishu / VSCode / Site interfaces
4. Note-data bridge
5. Proactive intelligence

### New Priority

1. **Feishu Dev Loop MVP**
2. **Development Task Layer**
3. **Unified Agent + Tooling for real work**
4. **Note/Data Bridge**
5. **Proactive Shadow**

This order is better because it uses the strongest existing code path first, creates an immediate human-facing operating surface, and makes later AI-assisted development much faster.

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
| Feishu gateway | `sail_server/feishu_gateway/`, `router/feishu.py` | Partial but strategically important |
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

Once that exists, the same infrastructure can expand from "development operations" into "life operations".

---

## Revised Architecture Focus

### Phase 0-1 Core Stack

```
Human
  |
Feishu Bot / Cards
  |
Feishu Gateway
  |
Control Plane <-> Unified Agent Tasks
  |
Edge Runtime / Local Execution Session
  |
Workspace / OpenCode / Repo Operations
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

- [ ] Audit and consolidate the current Feishu-related paths:
  - `sail_server/router/feishu.py`
  - `sail_server/feishu_gateway/`
  - any duplicated/legacy Feishu runtime logic
- [ ] Confirm the primary runtime mode is **Feishu App Bot + long connection**
- [ ] Standardize inbound message normalization
- [ ] Standardize outbound delivery for text + cards
- [ ] Add message idempotency, error logging, and retry boundaries

### 0.2 Workspace / Session Control Surface

- [ ] Expose stable workspace and session operations from `control_plane`:
  - list workspaces
  - inspect session state
  - request start
  - request suspend
  - request resume
  - request stop
- [ ] Align `control_plane` models and APIs with the real state machine needed by Feishu cards
- [ ] Ensure `edge_runtime` can report:
  - desired state
  - observed state
  - local URL
  - process info
  - diagnostics
  - last error

### 0.3 Feishu Cockpit Cards

- [ ] Workspace selection card
- [ ] Session status card
- [ ] Progress / recovering / error card
- [ ] Safe confirmation card for guarded actions
- [ ] Result summary card for completed operations

### 0.4 Start / Monitor / Suspend Loop

- [ ] Start workspace session from Feishu
- [ ] View current status from Feishu
- [ ] Suspend or stop session from Feishu
- [ ] Resume session from Feishu
- [ ] Show recent actions/events for debugging and trust

### 0.5 Minimum Safety and UX Guarantees

- [ ] Risk classification for safe / guarded / confirm-required actions
- [ ] Explicit confirmation flow for destructive actions
- [ ] Timeout and stale-session handling
- [ ] Basic observability: logs, event history, failed action tracing

**Milestone**: Feishu becomes a reliable remote control surface for SailZen development sessions.

---

## Phase 1: Development Task Layer (3-4 weeks)

**Goal**: Move from session control to structured development task execution.

At the end of this phase, Feishu is not only controlling a workspace, but also creating and tracking actual development work.

### 1.1 Development Task Model

- [ ] Introduce a dedicated development task abstraction on top of current agent/control-plane capabilities
- [ ] Define task lifecycle:
  - draft
  - confirmed
  - queued
  - running
  - suspended
  - failed
  - completed
  - cancelled
- [ ] Record links between:
  - Feishu thread/message
  - workspace/session
  - agent task
  - execution summary

### 1.2 Feishu -> Task Creation

- [ ] Convert natural-language requests into structured development task drafts
- [ ] Support commands such as:
  - "启动 SailZen 开发环境"
  - "帮我创建一个修复 health API 的任务"
  - "查看这个任务现在做到哪了"
  - "先挂起，晚上继续"
- [ ] Return task cards instead of loose text-only responses

### 1.3 Unified Agent Integration for Development Work

- [ ] Connect Feishu task requests to `sail_server/router/unified_agent.py`
- [ ] Reuse current task/progress/event infrastructure where possible
- [ ] Add progress callbacks that feed Feishu card updates
- [ ] Add task summary generation at completion or failure

### 1.4 Suspend / Resume / Recovery

- [ ] Support pausing long-running development tasks
- [ ] Support resuming from known state
- [ ] Record enough context to explain what was done before suspension
- [ ] Provide recovery suggestions when execution fails

**Milestone**: Feishu can create, track, suspend, and resume structured AI development tasks.

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

Starting from today (2026-03-29), the recommended first actions are:

1. **Consolidate the Feishu path** — decide the canonical implementation path around `sail_server/feishu_gateway/` and `router/feishu.py`
2. **Harden control plane session operations** — make start/status/suspend/resume/stop explicit and traceable
3. **Validate edge runtime loop** — ensure observed state can be trusted and surfaced in Feishu
4. **Build Feishu cockpit cards** — workspace picker, session status, progress, confirmation, result
5. **Only after the loop works daily**, connect Feishu requests into unified development task execution

---

## Supporting Documents

This roadmap is intentionally shorter at the top level. Execution detail is split into companion planning documents:

- [SailZen 3.0 AI Task Breakdown](./sailzen-3.0-task-breakdown.md)
- [SailZen 3.0 Phase 0 Feishu Dev Loop](./sailzen-3.0-phase-0-feishu-dev-loop.md)

---

*This roadmap is a living document. Update it as implementation reality changes.*
*Author: AI Agent | Date: 2026-03-29*
