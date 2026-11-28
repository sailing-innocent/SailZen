# SailZen Workbench

SailZen 3.0 Work & Creation Workbench for VS Code — lightweight dot-hierarchy Markdown vault engine, Rhythm v2 + SailTick QuickChat, Content 2.0 virtual library & fenced sync, multi-machine project workflows (Novel, Indie Game, Research, Systems Engineering), and cloud VSIX OTA self-update.

## Core Shortcuts

| Shortcut | Command |
|---|---|
| `Ctrl+L` / `Cmd+L` | Lookup / Create Note |
| `Ctrl+Shift+I` / `Cmd+Shift+I` | Open Today's Journal |
| `Ctrl+Shift+C` / `Cmd+Shift+C` | Copy Note Wikilink (`[[title\|fname]]`) |
| `Ctrl+Shift+D` / `Cmd+Shift+D` | Delete Note (Move to Trash) |
| `Ctrl+Shift+Up` / `Cmd+Shift+Up` | Go Up Hierarchy |

## Multi-Machine Configuration

Run `SailZen: Open Machine Config (~/.sailzen/machine.json)` to configure:
- `serverUrl` / `apiToken`: SailZen cloud backend endpoint
- `vaults.private` / `vaults.work`: dual-vault paths (Work vault enforces strict offline isolation)
- `projectPaths`: semantic project slug → local directory mapping on this machine
- `pinnedWorkIds`: works pinned to the top of `Projects & Content`

## Cloud OTA Self-Update

- Automatically checks `GET /api/v1/workbench/release/latest` on startup (skipped in Work Offline mode).
- Run `SailZen: Check for Workbench Update (OTA)` at any time to verify SHA-256, download, and install the latest `.vsix` directly inside VS Code — zero Node.js or build toolchain required on client laptops.

## Release Notes

### 0.3.1 (2026-11-28)
- Added Release Notes & OTA guide in Extension README page.
- Added active extension version line to `SailZen: Workbench Diagnostics`.
- Verified end-to-end cloud VSIX OTA update pipeline across machines.

### 0.3.0 (2026-11-28)
- First cloud OTA-enabled release (`sailzen.checkForUpdate` + SHA-256 verification).
- Restored Dendron keybindings (`Ctrl+L`, `Ctrl+Shift+I`, `Ctrl+Shift+C`, `Ctrl+Shift+D`, `Ctrl+Shift+Up`).
- Added Pinned Works + QuickPick Library Search (`sailzen.searchLibrary`).
- Added Novel, Indie Game, Research, and Systems Engineering workflows (`syncChapterToCloud`, Story Bible hover/diff, `repo://` semantic code links, `logToTodayJournal`, `insertPaperReference`, AI Context Pack).
