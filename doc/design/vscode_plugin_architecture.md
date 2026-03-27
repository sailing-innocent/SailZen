# VSCode Plugin Architecture Guide

> **Version**: v1.0 | **Updated**: 2026-03-27 | **Status**: Active

This document describes the architecture of the `sail-zen-vscode` extension — a fork of Dendron maintained in single-person + AI mode. It serves as a navigational reference for understanding, extending, and debugging the plugin.

---

## 1. Project Positioning

The VSCode extension is built on top of Dendron's hierarchical note system. The original Dendron codebase has been stripped of cloud sync, sharing, and telemetry features. What remains is a local-first personal knowledge base engine with additional SailZen modules (finance, health, project, text, necessity).

The extension communicates with two separate processes:

- **Engine Server** (`@saili/api-server`) — a local Express HTTP server, spawned as a child Node.js process. Port is written to `.dendron.port` in the vault root.
- **Sail Server** (`sail_server/`) — Python/Litestar backend for SailZen domain features (finance, health, text analysis, etc.).

---

## 2. Layered Architecture

```
+-----------------------------------------------------------+
|  VSCode Extension Host (sail-zen-vscode)                  |
|                                                           |
|  extension.ts  -->  _extension.ts  -->  WorkspaceActivator|
|         |                                    |            |
|  Commands (ALL_COMMANDS[])          DendronExtension       |
|  Providers (completion, hover…)     WorkspaceService      |
|  Webviews (dendron-plugin-views)    TextDocumentService   |
+----------------------------+------------------------------+
                             | HTTP (localhost:.dendron.port)
+----------------------------+------------------------------+
|  Engine Server (@saili/api-server, child Node.js process) |
|                                                           |
|  DendronEngineV3  -->  NoteParserV2  -->  NotesFSCache    |
|                                          (vault/*.md)      |
+-----------------------------------------------------------+
```

---

## 3. Activation Flow

Activation event: `onStartupFinished` (deferred, does not block VS Code startup).

### Phase 0 — Entry

| File | Line | Description |
|------|------|-------------|
| `packages/vscode_plugin/src/extension.ts` | 1 | Package entry point, re-exports `activate` / `deactivate` |
| `packages/vscode_plugin/src/_extension.ts` | 81 | `activate()` — registers context, spawns `_activate()` async |
| `packages/vscode_plugin/src/_extension.ts` | 110 | `_activate()` — main activation logic, ~400 LOC |

### Phase 1 — `WorkspaceActivator.init()`

Called at `_extension.ts:248`. Runs before the engine is loaded.

| Step | Method | File:Line |
|------|--------|-----------|
| Detect workspace type | `initCodeWorkspace` / `initNativeWorkspace` | `workspaceActivator.ts:638,648` |
| Create `WorkspaceService` | constructor | `workspaceActivator.ts:419` |
| Run migrations | `WorkspaceMigration` | inside `init()` |
| Spawn engine process | `verifyOrStartServerProcess` | `workspaceActivator.ts:543,683` |
| Connect `EngineAPIService` | HTTP client setup | `workspaceActivator.ts:544` |

### Phase 2 — `WorkspaceActivator.activate()`

Called at `_extension.ts:311`. Engine is alive; vault data is loaded.

| Step | Method | File:Line |
|------|--------|-----------|
| `reloadWorkspace()` | reads all notes via engine | `workspaceActivator.ts:573` — **slowest step** |
| Record duration | `durationReloadWorkspace` | `workspaceActivator.ts:574` |
| `postReloadWorkspace()` | sets up tree, watchers | `workspaceActivator.ts:257` |
| `trackWorkspaceInit()` | collects metrics, writes perf log | `ExtensionUtils.ts:274,477` |
| `activateWatchers()` | file system watchers | `workspaceActivator.ts` |
| `initTreeView()` | builds note tree | `workspaceActivator.ts` |

---

## 4. Engine Server: Note Loading Pipeline

The slowest part of startup is inside the engine server: `NoteParserV2` parses all vault `.md` files on `reloadWorkspace`.

```
DendronEngineV3.init()
  └─ NoteParserV2.parseFiles()
       ├─ Level 1 (domain notes, addParent=false)
       │    Promise.all([...]) -- parallel parse   <-- optimized
       │    for...of           -- serial dict write
       │
       └─ Level 2+ (child notes, addParent=true)
            while (frontier not empty):
              Promise.all([...]) -- parallel parse  <-- optimized
              for...of           -- serial dict write
```

**Key file**: `packages/engine-server/src/drivers/file/NoteParserV2.ts`

- Level 1 parallel parse: line 157
- Level 2+ parallel parse: line 213

**Before optimization**: all levels used `asyncLoopOneAtATime` — fully serial.  
**After optimization**: parse step is concurrent; dict writes remain serial to avoid race conditions.

**Expected improvement**: 8–16 seconds saved on a vault of ~8,400 notes.

---

## 5. Command System

All commands follow the `BaseCommand` pattern:

```typescript
abstract class BaseCommand<TOpts, TOut> {
  abstract gatherInputs(): Promise<TOpts | undefined>
  abstract enrichInputs(inputs: TOpts): Promise<TOpts>
  abstract execute(opts: TOpts): Promise<TOut>
  showResponse?(out: TOut): void

  async run(): Promise<TOut | undefined> {
    // gatherInputs -> enrichInputs -> execute -> showResponse
  }
}
```

All commands are registered in `ALL_COMMANDS` array:

| File | Description |
|------|-------------|
| `packages/vscode_plugin/src/commands/` | Individual command implementations |
| `packages/vscode_plugin/src/_extension.ts` | `ALL_COMMANDS` registration loop |

Commands are bound to `vscode.commands.registerCommand` during activation. The string IDs follow `dendron.<CommandName>` convention (preserved from upstream).

---

## 6. Webviews

Rich UI panels (finance dashboard, project board, etc.) are built as React apps in `packages/dendron_plugin_views/`. They communicate with the extension host via `vscode.postMessage` / `webview.onDidReceiveMessage`.

Build pipeline: `pnpm run views:build` compiles the React apps, `pnpm run views:copy` copies the bundles into `packages/vscode_plugin/`.

---

## 7. Deprecated / Stub Components

These files exist but are effectively no-ops. Do not waste time investigating them for real behavior.

| File | What it looks like | Reality |
|------|--------------------|---------|
| `packages/vscode_plugin/src/telemetry/common/ITelemetryClient.ts` | Telemetry interface | Implemented only by `DummyTelemetryClient` — all methods are empty stubs |
| `packages/vscode_plugin/src/utils/ProxyMetricUtils.ts` | `trackRefactoringProxyMetric()` | Constructs payload but never sends it; no-op |
| `ExtensionUtils.trackWorkspaceInit()` (old) | Collected workspace init metrics | Was a no-op; now wired to `StartupProfiler` |

---

## 8. Performance Monitoring Framework

Replaces the defunct telemetry system. Zero external dependencies; output is a local JSON Lines file.

### Output File

```
{wsRoot}/logs/startup-perf.jsonl
```

Rolling window of 50 records. Each line is a JSON object:

```json
{
  "timestamp": "2026-03-27T10:00:00.000Z",
  "version": "0.2.4",
  "activationSucceeded": true,
  "noteCount": 8425,
  "vaultCount": 1,
  "cacheMisses": 12,
  "durationMs": {
    "reloadWorkspace": 4200
  }
}
```

### Implementation

| File | Role |
|------|------|
| `packages/vscode_plugin/src/perf/StartupProfiler.ts` | `StartupProfiler.write(wsRoot, record)` static method |
| `packages/vscode_plugin/src/utils/ExtensionUtils.ts:477` | Calls `StartupProfiler.write()` after `reloadWorkspace` completes |

### Reading the Log

```bash
# Show last 10 startup records (PowerShell)
Get-Content vault/logs/startup-perf.jsonl | Select-Object -Last 10 | ForEach-Object { $_ | ConvertFrom-Json }

# Show only reloadWorkspace durations over time
Get-Content vault/logs/startup-perf.jsonl | ForEach-Object { ($_ | ConvertFrom-Json).durationMs.reloadWorkspace }
```

### Extending the Schema

To add new timing measurements, extend `StartupPerfRecord` in `StartupProfiler.ts` and populate the new fields in `ExtensionUtils.ts:trackWorkspaceInit()`.

---

## 9. Known Performance Hotspots

| Hotspot | Location | Status |
|---------|----------|--------|
| Serial note parsing (8,400+ files) | `NoteParserV2.ts:157,213` | **Fixed** — `Promise.all` concurrency |
| Engine process startup latency | `workspaceActivator.ts:543` | Not optimized — inherent IPC cost |
| Large individual notes (>200KB) | `NoteParserV2` parse step | Not optimized — single-file concern |
| Cache cold start (7.8MB JSON parse) | `notesFileSystemCache.ts` | Not optimized |

---

## 10. Key File Index

| Path | Description |
|------|-------------|
| `packages/vscode_plugin/src/extension.ts` | Extension entry point |
| `packages/vscode_plugin/src/_extension.ts` | Main `_activate()` logic (~744 lines) |
| `packages/vscode_plugin/src/workspace/workspaceActivator.ts` | Two-phase activator (~715 lines) |
| `packages/vscode_plugin/src/workspace.ts` | `DendronExtension` singleton |
| `packages/vscode_plugin/src/utils/ExtensionUtils.ts` | `trackWorkspaceInit`, server spawn helpers |
| `packages/vscode_plugin/src/perf/StartupProfiler.ts` | Local perf log writer |
| `packages/engine-server/src/drivers/file/NoteParserV2.ts` | Note file parser (concurrency-optimized) |
| `packages/engine-server/src/DendronEngineV3.ts` | Engine core, `init()` / `writeNote()` |
| `packages/engine-server/src/cache/notesFileSystemCache.ts` | Notes cache (`.dendron.cache.json`) |
| `packages/common-all/src/util/performanceTimer.ts` | `PerformanceTimer` utility |
| `packages/vscode_plugin/src/telemetry/common/ITelemetryClient.ts` | Telemetry stub (do not use) |
| `packages/vscode_plugin/src/versionProvider.ts` | Extension version helper |
| `packages/vscode_plugin/src/commands/` | All command implementations |
