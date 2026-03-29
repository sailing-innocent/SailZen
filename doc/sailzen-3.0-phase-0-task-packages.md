# SailZen 3.0 Phase 0 Task Packages

> **Version**: v1.0 | **Date**: 2026-03-29 | **Status**: Draft

## Purpose

This document breaks Phase 0 into small implementation packages that another coding model can pick up one by one.

Each package should ideally fit within one focused development session.

---

## Package P0-1: Feishu Entry Audit

**Goal**: Identify the real inbound/outbound Feishu path.

**Do**
- inspect all Feishu-related modules
- document inbound entrypoint
- document outbound delivery path
- document duplicated or dead paths

**Deliverable**
- short audit note committed into docs or PR description

**Done When**
- one canonical path is chosen for Phase 0

---

## Package P0-2: Request/Response Normalization

**Goal**: Make text and card actions use one internal request shape.

**Do**
- define normalized inbound request model
- define normalized outbound response model
- update handlers to use them consistently

**Done When**
- both text input and card actions can reach the same downstream routing layer cleanly

---

## Package P0-3: Idempotency and Logging

**Goal**: Prevent duplicate action execution and improve debuggability.

**Do**
- dedupe on stable message/event id
- add structured logs for request lifecycle

**Done When**
- repeated delivery does not create duplicate side effects
- logs show the full path of a failed request

---

## Package P0-4: Session API Gap Fill

**Goal**: Ensure control plane exposes all required session operations.

**Do**
- audit list/inspect/start/suspend/resume/stop
- add missing DTOs/routes/service methods

**Done When**
- Feishu layer does not need to guess or patch around missing control-plane behavior

---

## Package P0-5: Session State Contract Cleanup

**Goal**: Make desired state, observed state, and user-facing status explicit.

**Do**
- inspect current session model fields
- clarify semantics in code and DTOs
- avoid ambiguous overloaded status meaning

**Done When**
- state fields are understandable enough to render a card correctly

---

## Package P0-6: Edge Runtime Status Sync

**Goal**: Ensure local runtime can sync true observed state back to control plane.

**Do**
- verify ensure/start behavior
- verify process and diagnostics syncing
- preserve last error and heartbeat

**Done When**
- status shown in remote APIs matches actual local runtime state

---

## Package P0-7: Workspace Selection Card

**Goal**: Let user choose a workspace cleanly in Feishu.

**Do**
- render workspace list card
- support empty state
- support selecting/starting a workspace

**Done When**
- user can pick a workspace from Feishu without typing raw internal ids

---

## Package P0-8: Session Cockpit Card

**Goal**: Show session state and main actions.

**Do**
- show key runtime state
- add actions for refresh, suspend/resume, stop

**Done When**
- user can manage an active session from one main card

---

## Package P0-9: Confirmation and Safety Flow

**Goal**: Guard risky operations.

**Do**
- classify actions by risk
- require confirmation when needed
- handle stale confirmations

**Done When**
- risky actions cannot execute accidentally from loose text or repeated clicks

---

## Package P0-10: Error and Recovery UX

**Goal**: Fail visibly and recover sanely.

**Do**
- add readable error/result cards
- include suggested next actions
- expose diagnostics snippets when useful

**Done When**
- a broken session flow is still understandable to the user

---

## Package P0-11: Start Flow E2E Validation

**Goal**: Prove that a real workspace can be started from Feishu.

**Done When**
- a real message starts a real session and returns a running-state result

---

## Package P0-12: Suspend/Resume Flow E2E Validation

**Goal**: Prove that a running session can be paused and resumed.

**Done When**
- both operations work end-to-end with visible state changes

---

## Package P0-13: Stop Flow and Failure Validation

**Goal**: Prove that stop and failure reporting are usable.

**Done When**
- stop works safely and failures show readable diagnostics

---

## Recommended Execution Order

1. P0-1
2. P0-2
3. P0-3
4. P0-4
5. P0-5
6. P0-6
7. P0-7
8. P0-8
9. P0-9
10. P0-10
11. P0-11
12. P0-12
13. P0-13

---

## Rule for Further Splitting

If any package requires touching all of these at once, split it again:

- Feishu gateway
- control plane
- edge runtime
- UI cards
- task/agent model

That usually means the package is still too large for a weaker follow-up model.
