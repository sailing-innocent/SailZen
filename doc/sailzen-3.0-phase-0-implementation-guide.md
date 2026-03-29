# SailZen 3.0 Phase 0 Implementation Guide

> **Version**: v1.0 | **Date**: 2026-03-29 | **Status**: Draft

## Purpose

This document is the execution guide for Phase 0 of SailZen 3.0.

It is written for follow-up coding agents that may have weaker judgment or less project context. The goal is to reduce ambiguity and make implementation order, file targets, contracts, and acceptance criteria explicit.

Use this document together with:

- `doc/sailzen-3.0-roadmap.md`
- `doc/sailzen-3.0-phase-0-feishu-dev-loop.md`
- `doc/sailzen-3.0-task-breakdown.md`

---

## Phase 0 Outcome Definition

Phase 0 is successful when all of the following are true:

- A user can use Feishu to target a workspace
- A user can start a local development session from Feishu
- A user can inspect current session state from Feishu
- A user can suspend, resume, and stop that session from Feishu
- The bot returns understandable card/text status instead of opaque errors
- The system records enough action/event/state data to debug failures

This phase does **not** require:

- general personal assistant chat
- Dendron note bridge
- full tool registry
- proactive scheduler
- memory system

---

## Source of Truth for Phase 0

When in doubt, Phase 0 should favor the following runtime path:

`Feishu -> feishu_gateway -> control_plane -> edge_runtime -> local session`

The `unified_agent` path is allowed only where it helps with progress reporting or task wrapping, but it should not become the center of Phase 0 unless that is clearly necessary.

---

## Recommended Implementation Order

Follow this order strictly unless a concrete repository reality forces a change:

1. A1 Feishu runtime consolidation
2. A2 workspace/session API hardening
3. A3 edge runtime state sync
4. A4 Feishu cockpit cards
5. A5 end-to-end flows

Do not start note bridge or generalized agent tool abstractions during Phase 0.

---

## A1. Feishu Runtime Consolidation

### Objective

Make one code path the canonical Feishu integration path for Phase 0.

### Likely Relevant Files

- `sail_server/router/feishu.py`
- `sail_server/feishu_gateway/message_handler.py`
- `sail_server/feishu_gateway/intent_router.py`
- `sail_server/feishu_gateway/session_orchestrator.py`
- `sail_server/feishu_gateway/events.py`
- `sail_server/feishu_gateway/delivery.py`
- `sail_server/feishu_gateway/cards.py`
- `server.py`
- any legacy Feishu runtime files discovered during audit

### Implementation Tasks

- [ ] Identify every Feishu-related entrypoint in the repository
- [ ] Decide which module receives inbound Feishu events in Phase 0
- [ ] Decide which module owns outbound Feishu replies/cards in Phase 0
- [ ] Normalize one internal request shape for:
  - inbound text message
  - inbound card action
  - normalized sender/chat context
- [ ] Normalize one internal response shape for:
  - plain text
  - card payload
  - error response
- [ ] Ensure idempotency is based on Feishu `message_id` or equivalent stable event identifier
- [ ] Add structured logs around:
  - receive
  - normalization
  - routing
  - action creation
  - delivery

### Required Decisions

- The repository may contain overlapping experiments. Do not try to keep every path equally alive.
- If two implementations overlap, pick one as canonical and leave a clear deprecation note in comments or docs.
- Avoid large framework rewrites; prefer consolidation and simplification.

### Suggested Output Contract

For internal gateway handling, prefer a normalized shape similar to:

```python
{
    "platform": "feishu",
    "message_id": "msg_xxx",
    "chat_id": "oc_xxx",
    "chat_type": "p2p",
    "sender_open_id": "ou_xxx",
    "message_type": "text",
    "normalized_text": "启动 sailzen 工作区",
    "raw_payload": {...},
}
```

### Acceptance Criteria

- One canonical inbound path is used
- One canonical outbound path is used
- Duplicate inbound messages do not trigger duplicate actions
- Log traces are sufficient to reconstruct a failed request

### Common Failure Modes

- Hidden duplicate processing due to multiple handlers
- Card action path and text path producing different internal formats
- Logging only raw exceptions without request context

---

## A2. Workspace and Session API Hardening

### Objective

Make control-plane APIs explicit enough to support Feishu remote operations without guessing hidden state.

### Likely Relevant Files

- `sail_server/router/control_plane.py`
- `sail_server/control_plane/service.py`
- `sail_server/control_plane/models.py`
- `sail_server/application/dto/control_plane.py`
- `sail_server/application/dto/control_plane_commands.py`
- `sail_server/application/dto/control_plane_sync.py`

### Required Session Operations

Phase 0 should expose or stabilize the following operations:

- list workspaces
- inspect workspace/session
- request start session
- request suspend session
- request resume session
- request stop session
- inspect recent actions/events

### Implementation Tasks

- [ ] Review current control-plane routes and list missing operations
- [ ] Add missing DTOs rather than overloading unrelated payloads
- [ ] Ensure session responses expose at least:
  - `session_key`
  - `workspace_slug` or equivalent workspace identity
  - `status`
  - `desired_state`
  - `observed_state`
  - `local_url`
  - `local_path`
  - `process_info`
  - `diagnostics`
  - `last_error`
  - `last_heartbeat_at`
- [ ] Ensure actions are represented as first-class audit objects
- [ ] Ensure event history can be queried for debugging

### Important Constraint

Do not make Feishu logic directly manipulate database rows that should be controlled through service methods. Use `control_plane/service.py` as the state transition boundary whenever possible.

### Acceptance Criteria

- A client can list and inspect workspaces/sessions through explicit APIs
- Start/suspend/resume/stop requests are represented as auditable actions or state transitions
- The data returned is sufficient to render a Feishu session status card without extra hidden queries

### Common Failure Modes

- Mixing desired state and observed state into one ambiguous field
- Returning incomplete diagnostics so the bot can only show "failed"
- Updating status optimistically before edge runtime confirmation

---

## A3. Edge Runtime State Sync

### Objective

Make remote state trustworthy enough that Feishu can be used as an operational surface.

### Likely Relevant Files

- `sail_server/edge_runtime/runtime.py`
- `sail_server/edge_runtime/client.py`
- `sail_server/edge_runtime/executor.py`
- `sail_server/edge_runtime/config.py`
- `sail_server/edge_runtime/queue.py`
- `sail_server/control_plane/service.py`

### Implementation Tasks

- [ ] Verify how a local session is created or ensured
- [ ] Verify how observed state is detected after local operations
- [ ] Ensure `ensure_workspace_session()` returns enough state for UI/reporting
- [ ] Ensure `run_local_command()` or equivalent operation reports both success/failure and updated observed state
- [ ] Preserve last known error information
- [ ] Preserve heartbeat timestamps for stale-session detection
- [ ] Handle offline or disconnected edge conditions without corrupting state

### Required State Model

At minimum, the system should keep these concepts separate:

- desired state: what the control plane wants
- observed state: what is actually happening locally
- session status: user-facing summary derived from real data

### Acceptance Criteria

- After a start/suspend/resume/stop request, observed state eventually reflects reality
- Feishu-visible state is based on synced observed data, not assumption
- Broken or stale sessions can be detected and surfaced

### Common Failure Modes

- Treating request success as runtime success
- Forgetting to sync diagnostics after command execution
- Losing state when edge runtime briefly disconnects

---

## A4. Feishu Cockpit Cards

### Objective

Make the Feishu UX readable and operational on mobile and desktop.

### Likely Relevant Files

- `sail_server/feishu_gateway/cards.py`
- `sail_server/feishu_gateway/message_handler.py`
- `tests/unit/test_feishu_bot_ux.py`
- any card helper or renderer modules already present in repository

### Required Cards

#### 1. Workspace Selection Card

Must show:

- workspace name
- workspace slug
- short path or path hint
- action to start/select

#### 2. Session Status Card

Must show:

- workspace/session identity
- current state
- local URL if available
- heartbeat freshness
- last error if present
- actions: refresh, suspend/resume, stop

#### 3. Confirmation Card

Must show:

- action being confirmed
- why confirmation is required
- confirm/cancel path

#### 4. Error / Result Card

Must show:

- short title
- key detail
- suggested next action where applicable

### UX Guidance

- Prefer concise Chinese copy for user-facing text
- Do not overload one card with every detail
- Put key state first, details second
- Mobile readability matters more than dense information

### Acceptance Criteria

- Core session operations can be completed from cards or very short follow-up text
- Errors are understandable without reading server logs
- Card content reflects real backend state

---

## A5. End-to-End Flow Validation

### Objective

Verify that the full Phase 0 loop works with a real workspace, not just unit tests.

### Required End-to-End Flows

#### Flow 1: Start Session

- User sends start request in Feishu
- Gateway normalizes request
- Control plane creates action or desired-state update
- Edge runtime ensures session
- Observed state syncs back
- Bot shows running state and local URL if available

#### Flow 2: Inspect Status

- User asks for status
- Bot returns current observed state and useful diagnostics

#### Flow 3: Suspend and Resume

- User suspends from Feishu
- Confirmation is required if policy says so
- Edge runtime syncs updated observed state
- User resumes and sees state recovery

#### Flow 4: Stop and Failure Reporting

- User stops the session safely
- If any step fails, the bot exposes a useful error and next step

### Test Guidance

- Prefer at least one real-workspace validation path in addition to unit tests
- If full integration tests are too hard initially, add a manual verification checklist to the doc
- Record known limitations instead of pretending a flow is complete

### Acceptance Criteria

- All four flows work against at least one real workspace
- Known failures are visible and diagnosable
- Duplicate or retried messages do not create broken duplicate state

---

## Suggested Manual Verification Checklist

- [ ] Feishu bot receives a text message
- [ ] Message is logged with message id
- [ ] Workspace list can be returned
- [ ] A session can be started for one workspace
- [ ] Returned status shows desired state and observed state correctly
- [ ] Suspend action changes state correctly
- [ ] Resume action changes state correctly
- [ ] Stop action changes state correctly
- [ ] A forced failure produces readable diagnostics
- [ ] Duplicate resend does not create duplicate action side effects

---

## Coding Rules for Follow-Up Agents

- Prefer extending existing modules over inventing a parallel subsystem
- Keep Phase 0 changes local to Feishu gateway, control plane, and edge runtime where possible
- Do not start broad generalized architecture work during Phase 0
- Do not silently change public state semantics; update DTOs and docs together
- Add logs where remote debugging would otherwise be painful
- If a state transition is ambiguous, prefer explicit fields over overloaded strings

---

## Handoff Notes for the Next Agent

If you are the next coding agent working on Phase 0, start by answering these questions from the codebase before editing anything:

1. What is the real canonical Feishu entrypoint today?
2. Which module sends Feishu replies/cards today?
3. Which control-plane operations already exist and which are missing?
4. How does edge runtime currently create, track, and report a session?
5. What exact state fields are already available to render a cockpit card?

If you cannot answer those five questions from code inspection, you are not ready to implement Phase 0 safely.
