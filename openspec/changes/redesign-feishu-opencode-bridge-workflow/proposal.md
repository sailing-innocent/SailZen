## Why

`feishu-opencode-bridge` has proven the MVP path, but its current command-first interaction model is too brittle for real mobile use: phone typing is awkward, voice input is wasted, and plain-text responses do not take advantage of Feishu cards or interactive flows. At the same time, direct portal-agent command parsing and weak multi-session monitoring make the bridge hard to scale into a reliable remote development cockpit.

## What Changes

- Replace slash-command-centric interaction with a mobile-first conversational control plane that supports voice-to-text friendly prompts, tap-first quick actions, and rich Feishu card responses.
- Introduce an LLM-based intent routing layer between Feishu ingress and OpenCode execution so user requests can be normalized, clarified, and dispatched more flexibly than rigid command parsing.
- Add an industrial-grade desktop control plane for OpenCode lifecycle management, project selection, multi-session orchestration, health checks, and resilient error recovery.
- Build an observability layer for remote development that exposes session states, step-level progress, logs, alerts, and safe remote actions across multiple concurrent OpenCode sessions.
- Define safety guardrails for destructive actions, authorization boundaries, audit trails, and degraded-mode behavior when Feishu, LLM, or local agents are partially unavailable.

## Capabilities

### New Capabilities
- `feishu-mobile-control-plane`: Mobile-first Feishu interaction model for remote development, including cards, quick actions, voice-friendly flows, and contextual replies.
- `llm-intent-routing`: LLM-mediated command understanding and routing layer that translates natural language requests into validated remote development actions.
- `opencode-session-orchestration`: Multi-project and multi-session orchestration for starting, stopping, monitoring, recovering, and coordinating OpenCode work on the home desktop.
- `remote-dev-observability`: Real-time monitoring, event streaming, audit history, failure handling, and operator controls for remote AI-driven development sessions.
- `remote-dev-safety-governance`: Authorization, confirmation, policy, and fallback mechanisms for sensitive or failure-prone remote actions.

### Modified Capabilities
- None.

## Impact

- Affects `sail_server/feishu_gateway/` webhook ingestion, message handling, response rendering, and Feishu outbound integration.
- Extends the unified agent/task stack in `sail_server/agent/`, `sail_server/router/unified_agent.py`, `sail_server/model/`, `sail_server/infrastructure/orm/`, and `sail_server/utils/websocket_manager.py`.
- Adds new APIs, background workers, persistence models, and event streams for session registry, lifecycle control, monitoring, and audit.
- Integrates with the existing `sail_server/utils/llm/gateway.py` as the intent understanding and orchestration entry layer.
- Likely introduces Feishu card schemas, desktop-local agent components, and optional mobile/web dashboard surfaces for monitoring multiple sessions.
