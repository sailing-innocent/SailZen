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

## 12. Core Feishu-OpenCode web communication loop (added 2026-03-23)

The tasks above defined the architecture and scaffolding, but the actual end-to-end communication loop between Feishu and the OpenCode web HTTP API was never wired together in `bot/feishu_agent.py`. These tasks address the real functional gap.

- [x] 12.1 Add `OpenCodeWebClient` class to `bot/feishu_agent.py` that communicates with the OpenCode HTTP API (`POST /session`, `POST /session/:id/message` SSE stream, `GET /global/health`)
- [x] 12.2 Rewrite `OpenCodeSessionManager` to track both the subprocess (opencode web process) and the OpenCode API session ID per workspace path, with health checks via port polling and HTTP health endpoint
- [x] 12.3 Implement `send_task()` that ensures a session is running, creates an OpenCode API session if missing, sends the user's message via the HTTP API, collects the SSE stream response, and returns the assembled reply text
- [x] 12.4 Wire the Feishu reply path: `FeishuBotAgent._run_task()` calls `send_task()` and uses the lark SDK REST client to reply to the original Feishu message with the OpenCode output
- [x] 12.5 Support arbitrary workspace paths: `ensure_running(path)` starts `opencode web --hostname 127.0.0.1 --port <N>` at any given directory, waits for the health endpoint to respond, and records the port in the session state file (`~/.config/feishu-agent/sessions.json`)
- [ ] 12.6 Test end-to-end: start `bot/feishu_agent.py`, send a task from Feishu, verify OpenCode web starts, processes the task, and the reply appears in Feishu
- [ ] 12.7 Handle SSE stream edge cases: `session.idle` vs `session.completed` event names may vary across opencode versions; add robust event-name matching and a timeout fallback that returns whatever text was collected

## 13. LLM-driven intent understanding and conversation context (added 2026-03-23)

The keyword-based `_dispatch` was too rigid for production use. This section replaces it with an LLM-backed brain plus conversation state tracking, enabling tolerance of typos, voice-input text, and context-aware task routing.

- [x] 13.1 Implement `ConversationContext` per `chat_id`: sliding history window (6 turns), `mode` (`idle`/`coding`), `active_workspace`, and `pending` confirmation slot
- [x] 13.2 Implement `BotBrain` class with `think(text, ctx) → ActionPlan`: tries LLM first (via project `LLMGateway`), falls back to deterministic keyword matching when no API key is configured
- [x] 13.3 Design `_BRAIN_SYSTEM` prompt that provides context (mode, active_workspace, project slugs, recent history) and instructs the LLM to return structured JSON with `action`, `params`, `confirm_required`, `confirm_summary`, `reply`, `reasoning`
- [x] 13.4 Implement `ActionPlan` dataclass with `action`, `params`, `confirm_required`, `confirm_summary`, `reply` fields
- [x] 13.5 Implement `PendingConfirmation` with 5-minute TTL; `ConversationContext` checks expiry automatically on each turn
- [x] 13.6 Implement `_handle_with_context`: routes confirmation replies (`确认`/`取消`) before calling `brain.think()`; dispatches `confirm_required` plans to pending-confirmation state instead of executing immediately
- [x] 13.7 Implement `_execute_plan`: single method handling all six actions (`start_workspace`, `stop_workspace`, `send_task`, `show_status`, `show_help`, `chat`); updates `ctx.mode` and `ctx.active_workspace` on session lifecycle changes
- [x] 13.8 Remove hardcoded keyword dispatch (`_dispatch`, `_cmd_start`, `_cmd_stop`, `_cmd_task`, `_cmd_task_default`, `_run_task`, `_extract_path`) and replace with `_handle_with_context` + `_execute_plan`
- [x] 13.9 Implement `_make_gateway()` helper: reads provider API keys from environment variables and registers available providers into `LLMGateway`; gracefully returns `None` when no keys are present
- [ ] 13.10 Add LLM API key loading from config yaml: support `llm_provider`, `llm_api_key` fields in `bot/opencode.bot.yaml` as an alternative to environment variables
- [ ] 13.11 Validate BotBrain LLM path end-to-end: set `MOONSHOT_API_KEY`, send an ambiguous message to Feishu, verify intent is correctly classified and action is executed
- [ ] 13.12 Add context persistence across bot restarts: serialize `ConversationContext` (mode + active_workspace) to `~/.config/feishu-agent/contexts.json` so session context survives process restarts
