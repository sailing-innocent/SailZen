# SailZen Workbench

SailZen 3.0 Work & Creation Workbench for VS Code — lightweight dot-hierarchy Markdown vault engine, Rhythm v2 + SailTick QuickChat, Content 2.0 virtual library & fenced sync, and multi-machine project workflows (Novel, Indie Game, Research, Systems Engineering).

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
