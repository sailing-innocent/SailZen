# SailZen Workbench

SailZen 3.0 Work & Creation Workbench for VS Code — lightweight dot-hierarchy Markdown vault engine, dual-sidebar layout (Local Vault on Left, Cloud Rhythm/SailTick/Content on Right), native VS Code Markdown Editor & Previewer bidirectional link integration, and cloud VSIX OTA self-update.

## Dual-Sidebar Layout

- **Left Primary Sidebar (`SailZen Vault`)**: Local core workspace — **Vault Tree** (auto-reveals & expands the focused note so its parent, siblings, and children stay visible) + **Calendar**.
- **Right Secondary Sidebar (`SailZen Cloud`)**: Cloud workspace — **Today & Rhythm**, **SailTick QuickChat**, and **Projects & Content** (toggleable via VS Code's Secondary Side Bar `Ctrl+Alt+B` or command `SailZen: Open Cloud Sidebar`).

## Native Markdown Editor & Previewer

- **Native Markdown Preview (`Ctrl+Shift+V` / `Ctrl+K V`)**: Renders `[[wikilink]]`, `[[alias|target#heading]]`, `[[#local-heading]]`, `![[note]]` / `![[note#section]]` transclusion cards, and `repo://` links directly in VS Code's built-in Markdown Preview (compatible with default Strict preview security).
- **Native Markdown Editor**: Live theme-aware highlighting for existing/missing `[[wikilinks]]`, `![[embeds]]`, and `repo://` links; `#heading` autocomplete; `F12` heading-aware Go to Definition; `Shift+F12` vault-wide Backlinks (`ReferenceProvider`) + clickable top Backlinks CodeLens.

## Core Shortcuts

| Shortcut | Context | Command |
|---|---|---|
| `Ctrl+L` / `Cmd+L` | Global | Lookup / Create Note |
| `Ctrl+Shift+I` / `Cmd+Shift+I` | Global | Open Today's Journal |
| `Ctrl+K G` or `Alt+Enter` | Markdown Editor | Follow / Create `[[wikilink]]` or `repo://` Link at Cursor |
| `Ctrl+Shift+V` / `Cmd+Shift+V` | Editor ↔ Preview | Toggle between Native Markdown Editor & Preview |
| `Ctrl+K V` / `Cmd+K V` | Markdown Editor | Open Native Markdown Preview to the Side |
| `Shift+F12` | Markdown Editor | Find / Peek All Vault Backlinks (References) |
| `Ctrl+Shift+C` / `Cmd+Shift+C` | Editor & Preview | Copy Note Wikilink (`[[title\|fname]]`) |
| `Ctrl+Shift+R` / `Cmd+Shift+R` | Editor & Preview | Copy Note Embed Ref (`![[fname]]`) |
| `Ctrl+Shift+D` / `Cmd+Shift+D` | Editor & Preview | Delete Note (Move to Trash) |
| `Ctrl+Shift+Up` / `Down` | Editor & Preview | Go Up / Go Down Dot-Hierarchy |
| `Ctrl+Shift+[` / `]` | Editor & Preview | Go to Previous / Next Sibling Note |

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

### 0.3.2 (2026-11-28)
- **VaultTree Auto-Focus & Expand**: Implemented `TreeDataProvider.getParent()` and `VaultTreeLinkageController` so focusing any Markdown note (Text Editor, native `vscode.markdown.editor`, or `vscode.markdown.preview.editor`) automatically locates, selects, and expands it in Vault Tree; added manual Reveal button (`sailzen.revealActiveNoteInTree`) and `sailzen.vaultTree.autoReveal` setting.
- **Dual-Sidebar Layout**: Separated local core views (`Vault Tree`, `Calendar`) in the Left Activity Bar (`SailZen Vault`) from cloud views (`Today & Rhythm`, `SailTick QuickChat`, `Projects & Content`) in the Right Secondary Sidebar (`SailZen Cloud`).
- **Native VS Code Markdown Editor & Previewer Compatibility**:
  - Switched note opening (`openOrCreateNote` / `openDailyJournal` / `syncWorkToVault`) to `vscode.open` (with `#heading` URI fragments) so VS Code opens notes in your preferred native `vscode.markdown.editor` instead of forcing plain Text Editor.
  - Added `TabInputCustom` awareness for VaultTree auto-reveal, status bar word count, trash tab closing, and fenced sync commands (`syncJournalRhythm`, `syncChapterToCloud`, `logToTodayJournal`, `reviewNoteItemDiff`) via `WorkspaceEdit`.
  - Extended Dendron/SailZen keybindings (`Ctrl+Shift+C/R/D/Up/Down/[/]`) with `activeCustomEditorId == 'vscode.markdown.editor' || activeCustomEditorId == 'vscode.markdown.preview.editor'` so shortcuts work seamlessly inside VS Code's native Markdown Editor & Previewer.
  - Added official `markdown.markdownItPlugins` + `markdown.previewStyles` wikilink/embed/`repo://` hook for VS Code's built-in Markdown Preview (using strict-mode compatible relative `./<fname>.md` links), plus non-conflicting editor decorations, `#heading` completion, and scoped `Shift+F12` backlinks.

### 0.3.1 (2026-11-28)
- Added Release Notes & OTA guide in Extension README page.
- Added active extension version line to `SailZen: Workbench Diagnostics`.
- Verified end-to-end cloud VSIX OTA update pipeline across machines.

### 0.3.0 (2026-11-28)
- First cloud OTA-enabled release (`sailzen.checkForUpdate` + SHA-256 verification).
- Restored Dendron keybindings (`Ctrl+L`, `Ctrl+Shift+I`, `Ctrl+Shift+C`, `Ctrl+Shift+D`, `Ctrl+Shift+Up`).
- Added Pinned Works + QuickPick Library Search (`sailzen.searchLibrary`).
- Added Novel, Indie Game, Research, and Systems Engineering workflows (`syncChapterToCloud`, Story Bible hover/diff, `repo://` semantic code links, `logToTodayJournal`, `insertPaperReference`, AI Context Pack).
