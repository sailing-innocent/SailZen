## 1. Server control-plane foundation

- [x] 1.1 Create a dedicated remote-control service configuration that is explicitly isolated from the existing SailZen PostgreSQL database
- [x] 1.2 Choose and wire the isolated control-plane datastore, connection settings, and migration path for server-side persistence
- [x] 1.3 Define core control-plane models for remote workspaces, edge nodes, OpenCode sessions, session actions, session events, and interaction threads
- [x] 1.4 Implement DAOs or repository adapters for the new control-plane models in the isolated datastore
- [x] 1.5 Add server-side API DTOs and endpoints for workspace listing, session listing/detail, action dispatch, confirmation handling, and observability queries

## 2. Edge-to-server synchronization contract

- [x] 2.1 Define message envelopes and idempotency keys for edge-to-server sync of inbound messages, action acknowledgments, heartbeats, and observed state
- [x] 2.2 Define the desired-state versus observed-state reconciliation contract for OpenCode sessions and desktop agent health
- [x] 2.3 Define replay, retry, and acknowledgment behavior for temporary server disconnects or Feishu delivery failures
- [x] 2.4 Add bounded local queueing rules for the home-host edge runtime so buffered events can safely replay after reconnect

## 3. Home-host edge runtime skeleton

- [x] 3.1 Split the current Feishu gateway into an edge runtime that can forward normalized events to the server control plane
- [x] 3.2 Adapt the edge runtime to use the local Lark long-connection bot pattern from `scripts/feishu_agent.py` for home-host registration and message receipt
- [x] 3.3 Implement edge authentication and secure registration between the home-host runtime and the server control plane
- [x] 3.4 Add edge heartbeat and capability reporting for the host machine, bot runtime, and desktop execution capabilities
- [x] 3.5 Add local configuration for project inventory, host identity, retry policies, and fallback behavior on the home machine

## 4. Desktop execution control plane

- [x] 4.1 Implement the desktop-local execution agent for workspace inventory sync and observed-state reporting
- [x] 4.2 Implement OpenCode lifecycle actions in the desktop agent for start, stop, restart, recover, and process inspection
- [x] 4.3 Implement local log, stderr, and diagnostic collection for failed or unhealthy sessions
- [x] 4.4 Implement server-side reconciliation workers for desired session state changes and agent disconnect recovery
- [x] 4.5 Implement safe local command adapters limited to approved OpenCode and workspace operations

## 5. Feishu interaction pipeline

- [x] 5.1 Refactor inbound Feishu handling into normalized event types covering text, voice, mentions, and card action callbacks
- [x] 5.2 Implement outbound Feishu delivery adapters for text replies, card creation, card update, and confirmation flows
- [x] 5.3 Implement a card rendering layer for workspace home, session cockpit, task result, alert, and confirmation cards
- [x] 5.4 Implement edge-side outbound retry and deduplication for Feishu API failures (implemented in delivery adapter)
- [x] 5.5 Implement normalization-draft display and clarification UX for long speech-derived text requests
- [x] 5.6 Remove any first-release assumption that raw audio transcription is required before the core workflow is usable

## 6. Intent routing and action planning

- [x] 6.1 Implement a server-side LLM-backed intent router that emits structured action plans with confidence, risk level, and clarification state
- [x] 6.2 Add deterministic fallback handlers for safe/common actions when LLM routing is unavailable or unnecessary
- [x] 6.3 Implement template-based cleanup and normalization for large free-form text blocks produced by speech-to-text input methods
- [x] 6.4 Implement plan validation for workspace resolution, session resolution, parameter completeness, normalization quality, and unsupported intents
- [x] 6.5 Implement second-confirmation flows so normalized free-form requests are confirmed or edited by the operator before execution
- [x] 6.6 Implement confirmation-plan generation for high-risk actions before execution can proceed

## 7. Policy, authorization, and governance

- [x] 7.1 Implement sender allowlists and workspace-scoped authorization checks for all requested actions
- [x] 7.2 Implement action classification into safe-auto, guarded-auto, confirm-required, and blocked tiers
- [x] 7.3 Implement confirmation expiry, cancellation, and audit recording for sensitive actions
- [x] 7.4 Implement degraded-mode safety rules that block unsafe execution when server, edge, or LLM dependencies are unhealthy

## 8. Session-aware task orchestration

- [x] 8.1 Define how remote-control sessions reference or attach to existing SailZen unified tasks without reusing the original task database as the source of truth
- [x] 8.2 Implement orchestration for creating or selecting a session before dispatching session-bound work requests
- [x] 8.3 Implement session-scoped progress publication so work execution appears inside the session cockpit and timeline
- [x] 8.4 Implement result, failure, and resume flows that keep session history and operator-facing Feishu views consistent

## 9. Observability, audit, and alerting

- [x] 9.1 Implement normalized server-owned session event streaming for persistence, subscribers, and edge delivery
- [x] 9.2 Implement health evaluation for stale sessions, offline edge runtimes, repeated recovery failures, and routing degradation
- [x] 9.3 Implement operator-facing audit queries for recent actions, failure causes, and session transitions
- [x] 9.4 Implement actionable alert payloads that map server-side issues into Feishu cards with recovery controls
- [x] 9.5 Implement dashboards or API summaries for multi-session overview across all configured workspaces

## 10. Compatibility and rollout controls

- [x] 10.1 ~~Keep existing slash-command flows as home-host compatibility fallbacks~~ (REMOVED: slash commands intentionally not supported due to poor mobile UX - requires switching to symbol keyboard)
- [x] 10.2 Add a shadow-mode path where the edge runtime forwards events to the server without executing remote lifecycle actions
- [x] 10.3 Add staged rollout flags for card rendering, intent routing, desktop reconciliation, and confirmation gating
- [x] 10.4 Define rollback behavior that returns the edge runtime to deterministic text-based natural language handling when server-routed orchestration is disabled

## 11. Validation and execution readiness

- [x] 11.1 Add automated tests for control-plane persistence isolation, sync idempotency, and reconnect replay behavior
- [x] 11.2 Add automated tests for template-based normalization, uncertainty marking, and second-confirmation flows on speech-derived text input
- [x] 11.3 Add automated tests for intent validation, policy gates, confirmation flows, and degraded-mode blocking
- [x] 11.4 Add automated tests for card payload generation, Feishu delivery retry, and session observability summaries
- [x] 11.5 Write deployment runbooks for the server control plane, the home-host edge runtime, and the desktop execution agent
- [x] 11.6 Write migration and ops documentation covering credentials, backups, feature flags, and rollback to MVP behavior
