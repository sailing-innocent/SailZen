# SailZen 3.0 Phase 0: Feishu Dev Loop

> **Version**: v1.0 | **Date**: 2026-03-29 | **Status**: Draft

## Goal

Make Feishu the first practical SailZen 3.0 operating surface for development work.

The phase is complete when the user can use Feishu to:

- choose a workspace
- start or reconnect a development session
- inspect current runtime state
- suspend/resume or stop safely
- receive clear progress/error/result feedback

---

## Scope

### In Scope

- Feishu App Bot long-connection runtime
- Feishu message/card interaction for development control
- Workspace/session operations through control plane
- Edge runtime state sync
- Safe action confirmation for risky operations
- Progress and status card updates

### Out of Scope

- Full note/data bridge
- Personal memory model
- Proactive daily briefings
- General personal assistant chat
- Full workflow engine

---

## Main User Flows

### Flow A: Start Session

1. User opens Feishu and asks to start SailZen workspace
2. Bot shows workspace selection or directly targets known workspace
3. Control plane creates or reuses session request
4. Edge runtime ensures local session exists
5. Bot updates card from starting -> running
6. User sees URL, state, diagnostics summary

### Flow B: Inspect Status

1. User asks for current status
2. Bot returns current observed state, desired state, local URL, process info, last error
3. If state is degraded, bot offers guarded recovery actions

### Flow C: Suspend / Resume

1. User clicks suspend or sends natural-language request
2. Bot classifies risk and asks for confirmation if needed
3. Control plane writes desired action
4. Edge runtime syncs observed state back
5. Bot updates card and records summary

### Flow D: Failure / Recovery

1. Session startup or sync fails
2. Bot shows diagnostic card instead of generic failure text
3. User can retry, inspect, or stop cleanup

---

## Workstreams

### Workstream 1: Feishu Gateway Consolidation

- [ ] Audit current entrypoints and remove overlap
- [ ] Normalize inbound text/card actions into one internal request format
- [ ] Normalize outbound text/card sending through one delivery path
- [ ] Ensure message deduplication by message id
- [ ] Add structured logs for receive -> route -> send

### Workstream 2: Control Plane Session Contract

- [ ] Define canonical session operations:
  - list
  - inspect
  - start
  - suspend
  - resume
  - stop
- [ ] Make action/event records complete enough for debugging
- [ ] Ensure API payloads match Feishu card needs

### Workstream 3: Edge Runtime Trustworthiness

- [ ] Report real observed state, not assumed state
- [ ] Sync process info and diagnostics
- [ ] Preserve last known error and last heartbeat
- [ ] Handle reconnect and stale-session cases

### Workstream 4: Card UX

- [ ] Workspace home card
- [ ] Session cockpit card
- [ ] Progress card
- [ ] Confirmation card
- [ ] Error/result card

### Workstream 5: Safety Model

- [ ] Safe vs guarded vs confirm-required action classification
- [ ] Confirmation timeout behavior
- [ ] Stale action rejection
- [ ] Clear user-visible explanation for blocked actions

---

## Suggested Task Order

1. Consolidate Feishu gateway path
2. Harden control plane session APIs
3. Verify edge runtime state sync
4. Implement session cockpit cards
5. Implement start/status/stop flows
6. Implement suspend/resume flows
7. Add diagnostics and recovery actions
8. Add end-to-end validation with a real workspace

---

## Acceptance Criteria

- A real Feishu message can start a real local dev session
- User can see whether the session is starting, running, suspended, stopped, or failed
- User can suspend and resume from Feishu without manual local intervention
- Errors are inspectable from card output or follow-up details
- Repeated duplicate messages do not create duplicate actions
- Logs and event history are sufficient to debug failures

---

## Exit Condition

Once this phase is stable enough to be used daily, SailZen 3.0 has a real operational surface and can move to the development task layer.
