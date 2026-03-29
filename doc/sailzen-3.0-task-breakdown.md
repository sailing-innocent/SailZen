# SailZen 3.0 AI Task Breakdown

> **Version**: v1.0 | **Date**: 2026-03-29 | **Status**: Draft

## Purpose

This document translates the SailZen 3.0 roadmap into task packages that are easier to assign to AI-assisted development workflows.

Each package is designed to be:

- relatively self-contained
- verifiable with clear acceptance criteria
- small enough for iterative implementation
- aligned with the revised roadmap priority

---

## Epic A: Feishu Dev Loop MVP

### A1. Feishu Runtime Consolidation

**Goal**: Identify and consolidate the canonical Feishu runtime path.

**Tasks**
- [ ] Audit current Feishu-related modules and entrypoints
- [ ] Decide canonical request flow and deprecate overlap
- [ ] Standardize inbound/outbound interfaces

**Acceptance**
- One primary Feishu runtime path is documented and used
- Duplicate or dead paths are explicitly marked or removed

### A2. Workspace and Session API Hardening

**Goal**: Make control-plane session operations explicit and stable.

**Tasks**
- [ ] Add/verify APIs for list, inspect, start, suspend, resume, stop
- [ ] Ensure payloads expose state, URL, diagnostics, and errors
- [ ] Ensure action/event records are queryable

**Acceptance**
- Session lifecycle can be controlled entirely via API
- State transitions are auditable

### A3. Edge Runtime State Sync

**Goal**: Make edge runtime status trustworthy enough for remote operation.

**Tasks**
- [ ] Verify observed-state reporting
- [ ] Sync process info and diagnostics
- [ ] Handle stale or failed session cases

**Acceptance**
- Remote status matches actual local state with acceptable lag

### A4. Feishu Cockpit Cards

**Goal**: Present development state clearly in Feishu.

**Tasks**
- [ ] Workspace selection card
- [ ] Session status card
- [ ] Confirmation card
- [ ] Error/result card

**Acceptance**
- User can operate core flows through cards without cryptic raw text

### A5. Start / Monitor / Suspend / Resume E2E

**Goal**: Close the first usable loop.

**Tasks**
- [ ] Start session from Feishu
- [ ] Query status from Feishu
- [ ] Suspend/resume from Feishu
- [ ] Stop safely from Feishu

**Acceptance**
- All four core actions work end-to-end against a real workspace

---

## Epic B: Development Task Layer

### B1. Development Task Model

**Goal**: Represent AI development work as a first-class tracked object.

**Tasks**
- [ ] Define task schema and lifecycle
- [ ] Link task to workspace, session, Feishu thread, and agent execution

**Acceptance**
- A development task can be created, queried, and transitioned predictably

### B2. Feishu Request to Task Draft

**Goal**: Convert user intent into structured development tasks.

**Tasks**
- [ ] Normalize common dev intents
- [ ] Create draft tasks from Feishu messages
- [ ] Add confirmation/edit loop where needed

**Acceptance**
- A user can create a structured dev task from natural language

### B3. Task Progress Updates in Feishu

**Goal**: Make task execution visible without polling external systems.

**Tasks**
- [ ] Pipe task progress/events into Feishu card updates
- [ ] Add completion/failure summaries

**Acceptance**
- Task execution state is observable from Feishu in near real time

### B4. Task Suspend / Resume / Cancel

**Goal**: Support long-running or interruptible AI work.

**Tasks**
- [ ] Add suspend/resume/cancel controls
- [ ] Record context needed for recovery

**Acceptance**
- Long-running dev tasks can be safely interrupted and resumed

---

## Epic C: Unified Agent Tools

### C1. Agent Core Contract

**Goal**: Clarify the relationship among channels, tasks, tools, and execution.

**Tasks**
- [ ] Define core execution interfaces
- [ ] Reconcile existing agent classes with revised architecture

**Acceptance**
- Agent flow is documented and implemented through a stable contract

### C2. Tool Registration System

**Goal**: Allow the agent to call typed tools consistently.

**Tasks**
- [ ] Define tool abstraction
- [ ] Add registry/discovery
- [ ] Add schema-based inputs/outputs

**Acceptance**
- The agent can discover and call tools with structured IO

### C3. Product Domain Tools

**Goal**: Expose structured SailZen capabilities to the agent.

**Tasks**
- [ ] Finance tools
- [ ] Health tools
- [ ] Project tools
- [ ] Text/analysis tools
- [ ] Necessity/history tools

**Acceptance**
- Agent can answer and act over core structured domains

### C4. Conversation Persistence

**Goal**: Support multi-turn continuity across channels.

**Tasks**
- [ ] Session persistence
- [ ] Context window strategy
- [ ] Redis/PostgreSQL responsibility split

**Acceptance**
- Conversations retain usable continuity after restart or reconnect

---

## Epic D: Note/Data Bridge

### D1. Dendron Access Layer

**Goal**: Give the agent reliable access to the note system.

**Tasks**
- [ ] File-based note read/search support
- [ ] Engine-backed access where needed
- [ ] Guarded create/update flows

**Acceptance**
- Agent can search and read notes reliably, and draft writes safely

### D2. Cross-System Context Builder

**Goal**: Make note and data context work together.

**Tasks**
- [ ] Link structured events to note context
- [ ] Link note context back to structured domains

**Acceptance**
- At least several real cross-system question types are supported

### D3. Multi-Channel Reuse

**Goal**: Reuse the same backend across Feishu, VSCode, and SailSite.

**Tasks**
- [ ] VSCode chat integration
- [ ] SailSite widget integration

**Acceptance**
- Multiple channels share the same agent capabilities without duplicate logic

---

## Epic E: Proactive Shadow

### E1. Scheduler and Triggering

**Goal**: Add proactive routines and event-based suggestions.

### E2. Preference and Memory Learning

**Goal**: Improve relevance over time.

### E3. Intelligent Continuation

**Goal**: Detect and assist unfinished work.

### E4. Long-Term Expansion

**Goal**: Add specialized agents, external integrations, and automation proposals.

---

## Recommended Near-Term Execution Order

1. A1
2. A2
3. A3
4. A4
5. A5
6. B1
7. B2
8. B3
9. B4
10. C1
11. C2
12. C3
13. C4
14. D1
15. D2
16. D3

---

## Practical Rule for AI Task Assignment

When assigning work to an AI coding agent, prefer tasks that satisfy all of the following:

- one main subsystem
- clear input/output contract
- limited cross-cutting schema changes
- testable within one session
- visible user value or architectural unblock

If a task touches Feishu gateway, control plane, edge runtime, agent tasking, and Dendron integration all at once, it is too large and should be split.
