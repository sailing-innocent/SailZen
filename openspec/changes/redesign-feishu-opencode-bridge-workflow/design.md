## Context

The current `feishu-opencode-bridge` MVP receives Feishu messages through `sail_server/feishu_gateway/webhook.py` and routes them with a rigid parser in `sail_server/feishu_gateway/message_handler.py`. Responses are plain text, OpenCode lifecycle actions are mostly placeholders, and there is no durable session model for multiple projects, desktop agents, or remote recovery. In parallel, SailZen already has reusable primitives that fit this redesign: a unified agent registry, task execution model, WebSocket event fan-out, and a centralized LLM gateway with retry, cost, and provider abstractions.

The redesign targets a real-world workflow: the user controls a home desktop from a phone through Feishu, often with one hand, intermittent attention, and voice-assisted text input. That changes the system shape from “command bot” into “remote development control plane” with four cooperating layers: Feishu interaction, intent routing, desktop execution, and observability/governance. A key deployment constraint is that persistent control-plane state must run continuously on a server, while the Feishu/Lark bot process and the OpenCode executor run on the home machine. The design must therefore separate cloud/server persistence from home-host interaction/runtime responsibilities, preserve the existing Python service boundaries where useful, and leave room for a future mobile/web console without requiring it for MVP-2.

## Goals / Non-Goals

**Goals:**
- Provide a mobile-first Feishu interaction model that minimizes typing, accepts large voice-input-method text blocks, normalizes them into structured drafts, and returns rich, actionable cards instead of raw strings.
- Route user intent through an LLM-backed normalization layer before execution, while keeping deterministic fallbacks for simple or safety-critical flows.
- Introduce durable multi-session orchestration for multiple OpenCode workspaces, with start/stop/restart/recover, health checks, and remote operation control.
- Expose live observability for active and historical sessions, including progress, logs, failures, alerts, and action history.
- Enforce safety controls for destructive operations, ambiguous requests, and degraded external dependencies.
- Keep long-lived persistence and orchestration state independent from the existing SailZen PostgreSQL business database.

**Non-Goals:**
- Replacing Feishu with a custom chat app or building a full standalone IDE on mobile.
- Solving arbitrary desktop remote control beyond the OpenCode-centered development workflow.
- Implementing generalized multi-user enterprise RBAC in the first iteration; the design supports policy hooks but optimizes for a trusted personal-operator setup.
- Making the LLM the sole authority for execution; deterministic policies and confirmations remain the final gate for sensitive actions.
- Coupling this remote-control system to the existing monolithic SailZen database lifecycle or assuming the Feishu bot host is always online.
- Directly processing raw audio as a first-class requirement in the first release.

## Decisions

### 1. Split the system into a server control plane and a home-host edge plane

The redesign will be deployed as two cooperating runtime planes:
- `server control plane`: always-on service responsible for durable state, orchestration APIs, policy, audit, event storage, alert evaluation, and operator-visible status.
- `home-host edge plane`: Feishu/Lark bot ingress plus desktop execution agent, responsible for receiving Feishu events, executing local OpenCode actions, collecting local telemetry, and synchronizing with the server control plane.

The home-host edge plane is allowed to keep short-lived caches and delivery queues, but the source of truth for remote workflow state lives on the server control plane. The home-host plane must reconnect and resync after restarts without data loss.

Rationale: the user clarified that the bot runs at home while the durable service runs on a server. This forces an edge/cloud split and removes the assumption that webhook ingress and persistent orchestration live together.

Alternatives considered:
- Run the full control plane on the home machine. Rejected because it is less reliable for 24/7 persistence and monitoring.
- Run the Feishu bot directly on the server. Rejected because the user explicitly wants the bot and OpenCode control near the home desktop environment.

### 2. Model the bridge as a layered control plane, not a message parser

The system will be split into five bounded subsystems across the two runtime planes:
- `feishu ingress`: home-host webhook/event intake, sender validation, message normalization, response delivery, card action callbacks.
- `interaction orchestration`: conversation state, card state, quick actions, voice/text normalization, session summaries.
- `intent routing`: LLM-assisted interpretation that produces a structured action plan.
- `desktop execution`: home-host local desktop agent that owns OpenCode process control and machine-local operations.
- `observability/governance`: server-side session registry, event store, alerts, policy, audit, and operator controls.

Rationale: this avoids further overloading `MessageHandler` and maps directly to the pain points: mobile UX, flexibility, and monitoring. It also lets the existing unified-agent stack remain the execution backbone instead of baking more subprocess logic into the webhook path.

Alternatives considered:
- Extend `MessageHandler` with more commands and regex parsing. Rejected because mobile friction and multi-session state would remain unsolved.
- Put everything in a single orchestration agent. Rejected because lifecycle management, governance, and observability need deterministic infrastructure boundaries.

### 3. Use Feishu cards and action-driven flows as the primary mobile UI

The bridge will treat text input as the primary inbound channel, with special support for long, imperfect text produced by third-party speech-to-text input methods. Primary interactions will be card-based:
- “workspace home” card with recent projects, active sessions, health badges, and one-tap actions.
- “session cockpit” card with progress, current branch, latest agent step, errors, and quick actions.
- “task result” card with structured result sections, diffs/links, retry/continue controls, and escalation actions.
- “pending confirmation” card for sensitive actions such as push, restart, mass stop, and branch deletion.

Instead of requiring native audio processing, the first release assumes users often speak into a phone keyboard or IME and send large text blocks with filler words, punctuation drift, or transcription mistakes. The middle-layer agent therefore performs intent matching plus template-based cleanup and normalization, then returns a structured draft for user confirmation before execution. The system also supports tap-first quick actions that insert structured intents without requiring `/` commands.

Rationale: the user explicitly identified mobile typing pain and poor output presentation. Card-first interaction turns Feishu into an operator console and reduces dependency on symbol keyboard switching, while draft-confirm interaction makes voice-input-method text practical without building full speech handling first.

Alternatives considered:
- Keep text-only replies with markdown formatting. Rejected because it does not solve tap workflows, stateful actions, or visual monitoring.
- Build a dedicated mobile web dashboard first. Rejected because Feishu is already the user’s remote control entry point.
- Depend on first-party audio transcription as the default path. Rejected because the real requirement is robust handling of messy text already produced by external voice input tools.

### 4. Add an LLM intent router that emits validated action plans, not direct execution

The new intent layer will transform raw input into a structured plan with fields such as:
- `intent_type`
- `target_workspace`
- `target_session`
- `requested_action`
- `parameters`
- `risk_level`
- `confidence`
- `clarification_needed`

Before producing the executable plan, the router also produces a normalization draft that:
- removes filler and duplicate phrases;
- resolves template slots such as workspace, objective, urgency, and expected outcome;
- highlights uncertain tokens or likely transcription mistakes;
- rewrites the request into a cleaner operator-visible command brief.

Execution only proceeds after deterministic validators pass and the operator confirms the normalized draft when the request came from free-form conversational input. For high-confidence and low-risk structured card actions, the bridge can auto-dispatch. For ambiguous, messy, or risky actions, it asks a clarifying question or emits a confirmation card.

Implementation-wise, this should be a dedicated agent/service on the server control plane using `sail_server/utils/llm/gateway.py` rather than embedding ad hoc prompt calls inside `MessageHandler`. The home-host bot forwards raw operator text to the server plane, and the router returns both an operator-facing normalized draft and a machine-validated JSON plan for execution or clarification.

Rationale: this preserves flexibility while preventing the LLM from directly shelling out actions. It also lets the same routing layer interpret voice transcripts, free-form requests, and card actions consistently.

Alternatives considered:
- Pure deterministic rules. Rejected because the user explicitly wants a more flexible portal layer and natural language handling.
- Fully autonomous agent execution with no validator stage. Rejected for safety and audit reasons.
- Passing messy voice-input text straight through after light regex cleanup. Rejected because template-driven normalization plus second confirmation is the more flexible and safer interaction model.

### 5. Introduce a desktop-local execution agent as the source of truth for machine state

The always-on server control plane should not directly own all local process control assumptions. Instead, introduce a desktop-local agent on the home machine that:
- registers machine and workspace inventory;
- starts/stops/restarts OpenCode sessions;
- streams heartbeats, process metadata, and health state;
- runs approved local commands via a narrow action contract;
- returns logs, stderr, and recovery diagnostics;
- reconnects after local restarts and resumes desired session state.

This edge runtime should prefer Feishu/Lark long-connection registration on the home host, following the local agent pattern already demonstrated in `scripts/feishu_agent.py`, rather than assuming a server-hosted webhook is the only ingress model.

The server-side control plane stores desired state and observed state separately. The desktop agent continuously reconciles them. This supports operations like “keep session alive”, “restart crashed workspace”, and “drain all sessions before reboot”. The Feishu bot process may run alongside this desktop agent or share the same edge runtime, but it is not itself the persistence layer.

Rationale: the current TODO comments already hint at a local-agent design. Desired-vs-observed state is the correct industrial pattern for resilient remote machine control.

Alternatives considered:
- Let the webhook server spawn local processes directly. Rejected because the server may not run on the same trusted machine and cannot model reconnection cleanly.
- Poll the machine only on demand. Rejected because real-time monitoring and recovery require continuous heartbeat/state.
- Force all Feishu ingress through public server webhooks. Rejected because the user already has a viable long-connection local bot pattern and wants the bot colocated with the home machine runtime.

### 6. Use a dedicated remote-control datastore instead of the existing SailZen PostgreSQL database

The persistent control-plane data for remote development MUST NOT be stored in the existing SailZen PostgreSQL business database. Instead, the redesign introduces an isolated remote-control datastore owned by this subsystem. The exact engine can be PostgreSQL, SQLite + WAL for small deployments, or another operational store, but it must have:
- a separate schema lifecycle and migration path;
- separate credentials and failure domain;
- explicit backup/restore and retention policy;
- no coupling to existing business-domain tables;
- the ability to continue operating even if the main SailZen database is offline or under migration.

The control-plane service may still integrate with existing SailZen APIs and task abstractions, but its runtime state, audit trail, session registry, and operator actions live in the isolated datastore.

Rationale: the user explicitly requires continuous server-side operation without reusing the original PostgreSQL database. Isolating the persistence layer also reduces blast radius and simplifies independent deployment.

Alternatives considered:
- Reuse the current `UnifiedAgentTask` and related PostgreSQL tables directly. Rejected because deployment, availability, and schema coupling would become fragile.
- Keep everything in files or in-memory caches on the home host. Rejected because it cannot support industrial observability or server-side continuity.

### 7. Create a first-class OpenCode session domain model

The redesign will add explicit persistent entities in the dedicated remote-control datastore beyond generic unified tasks. At minimum:
- `RemoteWorkspace`: logical project/workspace metadata, path, labels, policy profile.
- `DesktopAgentNode`: home machine or executor identity, version, last heartbeat, capabilities.
- `OpenCodeSession`: runtime session record with workspace, process info, URL, branch, status, desired state, observed state, timestamps.
- `SessionAction`: operator or system action request with parameters, initiator, confirmation state, and result.
- `SessionEvent`: append-only event stream for lifecycle, log summary, errors, checkpoints, and alerts.
- `InteractionThread`: Feishu-side conversation context and current focus.

These should coexist with `UnifiedAgentTask` rather than replacing it. `UnifiedAgentTask` remains an optional execution/task abstraction in the SailZen application domain; `OpenCodeSession` becomes the durable runtime container in the remote-control domain that tasks attach to through references or synchronization adapters.

Rationale: trying to overload generic task tables for long-lived remote sessions will blur runtime lifecycle and operator intent. A dedicated session model unlocks monitoring, recovery, and multi-session coordination cleanly.

Alternatives considered:
- Store session metadata in `UnifiedAgentTask.config`. Rejected because it is insufficient for durable lifecycle, indexing, and event streaming.

### 8. Use server-owned events with edge delivery queues

All authoritative events are appended on the server control plane, then fanned out to edge/home delivery channels. The home-host bot maintains an outbound delivery queue for Feishu replies, card updates, and delayed retries, but event ownership stays on the server side.

The edge plane must support:
- pull or subscribe-based event sync from server to home host;
- idempotent acknowledgment of delivered actions and replies;
- local buffering when Feishu APIs or the server plane are temporarily unreachable;
- replay on reconnect without duplicating operator-visible side effects.

Rationale: with persistence on the server and Feishu ingress on the home host, event ownership and delivery must be explicitly separated.

Alternatives considered:
- Let the home host own the event log and sync upward later. Rejected because it makes the always-on server view eventually inconsistent.

### 9. Reuse WebSocket/event infrastructure, but add a fan-out layer for Feishu card refresh and alerting

Current WebSocket management already supports subscriptions and progress messages. The redesign keeps that pattern and adds a higher-level event bus abstraction that can fan out to:
- WebSocket clients for dashboards;
- Feishu card refresh/update handlers;
- audit/event persistence;
- alert rules (stale session, repeated crash, intent failure, agent offline).

Events should be normalized around session lifecycle and task execution so all surfaces consume the same source.

Rationale: one event model prevents drift between chat status, future dashboards, and stored audit history.

Alternatives considered:
- Feishu-only status updates. Rejected because a future dashboard and machine-readable alerting need a shared event stream.

### 10. Use progressive autonomy with policy gates

Actions are classified into policy tiers:
- `safe-auto`: read-only status queries, log fetches, card refresh, non-destructive workspace navigation.
- `guarded-auto`: starting sessions, resuming idle work, retrying failed subtasks.
- `confirm-required`: git push, stop-all, session reset, branch mutation, destructive cleanup.
- `blocked`: actions outside the configured workspace or violating policy.

Policy checks combine sender identity, workspace policy, action class, and current session state. The LLM can recommend, but policy decides.

Rationale: this makes the system trustworthy enough for unattended use while still feeling fluid on mobile.

Alternatives considered:
- Require confirmation for everything. Rejected because it would make mobile operation too slow.
- Allow fully autonomous git/network operations. Rejected because it raises unacceptable risk.

### 11. Build for degraded operation and replay

The system must tolerate partial outages:
- If Feishu delivery fails, actions still persist and can be surfaced later.
- If the LLM router is unavailable, deterministic commands and quick actions still work.
- If the desktop agent disconnects, desired state stays queued and stale-session alerts fire.
- If the home-host bot goes offline, the server control plane preserves desired state and marks the edge channel unavailable.
- If the server control plane is temporarily unreachable, the home-host bot and desktop agent buffer a bounded set of inbound/outbound events for replay.
- If a messy voice-input-method text block cannot be normalized confidently, the system returns a draft for correction rather than guessing execution intent.
- If a card action callback is missed, the user can reopen the session cockpit from conversation history without losing state.

To support this, all operator actions and session events must be durably recorded and idempotently replayable.

Rationale: remote phone-driven workflows are sensitive to flaky networks and intermittent attention; replayable state is essential.

Alternatives considered:
- In-memory conversation state only. Rejected because it breaks after restarts and cannot support industrial monitoring.

## Risks / Trade-offs

- [Card-driven UX increases integration complexity] -> Mitigation: define card schemas centrally and keep card rendering as a dedicated adapter layer.
- [LLM intent routing can misclassify high-stakes actions] -> Mitigation: require structured JSON output, confidence thresholds, policy validation, and confirmation cards.
- [Voice-input-method text may contain dangerous transcription errors] -> Mitigation: normalize with templates, highlight uncertainty, and require second confirmation before execution from free-form text.
- [Desktop-local agent adds another deployable component] -> Mitigation: keep the local agent narrow, auto-reconnecting, and independently observable with heartbeat/version status.
- [New session tables may overlap conceptually with unified tasks] -> Mitigation: make sessions long-lived runtime containers in the isolated datastore and tasks short-lived work units linked through explicit adapters.
- [Server/edge split introduces sync complexity] -> Mitigation: use idempotent action IDs, delivery acknowledgments, replay-safe events, and desired/observed state reconciliation.
- [Separate datastore increases operational burden] -> Mitigation: keep schema small, isolate credentials, and provide dedicated backup and migration runbooks.
- [Feishu callback/refresh limits may constrain live monitoring] -> Mitigation: combine push updates with explicit refresh buttons and summarized event windows.
- [More observability can generate noise on mobile] -> Mitigation: collapse low-priority events into digest cards and only escalate actionable alerts.

## Migration Plan

- Stand up the isolated server-side datastore, migrations, and service boundaries for remote-control state.
- Introduce the home-host edge runtime in shadow mode, using the local long-connection Feishu bot pattern to publish heartbeats, inbound Feishu events, and observed state without taking control.
- Move `MessageHandler` behind a new edge-to-server interaction facade while keeping existing slash commands as compatibility fallbacks.
- Enable the server-side LLM intent router first for draft normalization and recommendations/logging, then for guarded dispatch once validation quality is acceptable.
- Roll out card-based responses for status and session cockpit views before converting destructive workflows to confirmation cards.
- Cut over OpenCode lifecycle management from placeholder/manual guidance to desired-state reconciliation with the desktop agent.
- Keep rollback simple: disable server-routed orchestration by feature flag and fall back to deterministic text command handling on the home-host bot.

## Open Questions

- Should the home-host edge runtime maintain a persistent outbound connection to the server control plane, or should it rely on polling plus webhook callbacks?
- Should draft normalization use a single universal template, or a small set of intent-family templates such as session control, coding request, recovery, and monitoring?
- How much of session log content should be sent into Feishu cards versus linked to a richer dashboard or downloadable artifact?
- Does the first release need project-scoped auth beyond sender allowlists and confirmation gates?
- Should “continuous development workflow” include autonomous scheduling/plan continuation while the user is offline, or stay user-triggered in the first release?
