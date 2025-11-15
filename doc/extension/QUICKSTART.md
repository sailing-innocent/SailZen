# SailZen VSCode Plugin - Quick Start Guide

## Installation

1. Install the SailZen VSCode extension from the marketplace
2. Open VSCode in your preferred workspace folder

## First Time Setup

### Step 1: Initialize Workspace

1. Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`)
2. Run command: `SailZen: Initialize Workspace`
3. Enter your SailZen backend URL (default: `http://localhost:8000/api/v1`)
4. The workspace will be initialized with a `.sailzen` directory

### Step 2: Pull an Edition

1. Open the Command Palette
2. Run command: `SailZen: Pull Edition`
   - Or click "Pull Edition from Server" button in the SailZen Chapters view
3. Select an edition from the list
4. Wait for the download to complete
5. The edition will appear in the SailZen Chapters tree view

## Daily Writing Workflow

### Opening and Editing Chapters

1. In the **SailZen Chapters** view (Explorer sidebar), expand your edition
2. Click on any chapter to open it as a markdown file
3. Edit the content as you would any markdown file
4. Save with `Ctrl+S` / `Cmd+S`
5. Changes will automatically sync to the server after 5 seconds

### Using LLM Assistance

#### Continue Writing

1. Place your cursor where you want to continue writing
2. Press `Ctrl+Shift+C` / `Cmd+Shift+C`
3. The system will automatically:
   - Detect current edition and chapter
   - Collect context (previous content, character settings)
   - Request LLM suggestions
4. Select a suggestion and choose action:
   - **Insert at Cursor**: Add directly to document
   - **Preview in Diff**: See changes before applying
   - **Copy to Clipboard**: Copy for manual insertion

#### Get Writing Suggestions

1. Select text you want to improve or continue
2. Press `Ctrl+Shift+L` / `Cmd+Shift+L`
3. Review suggestions in the diff panel
4. Accept or modify suggestions

### Managing Entities

#### View Entities

1. Run command: `SailZen: Show Entities`
2. The system auto-detects current edition
3. Browse entities by type (Characters, Locations, etc.)
4. Use search box to filter entities
5. Click entity to jump to mentions in text

#### Mark Text as Entity

1. Select text in your document
2. Press `Ctrl+Shift+E` / `Cmd+Shift+E`
   - Or right-click and select "SailZen: Mark as Entity"
3. Choose:
   - **Create New Entity**: Define a new character/location/etc.
   - **Link to Existing Entity**: Connect to existing entity
4. Fill in entity details
5. The text is now marked as an entity mention

### Using the Outline View

1. Open any markdown file
2. The **SailZen Outline** view shows document structure
3. Click headings to jump to that section
4. Right-click to rename headings

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+S` / `Cmd+Shift+S` | Sync Now |
| `Ctrl+Shift+L` / `Cmd+Shift+L` | Request LLM Suggestions |
| `Ctrl+Shift+C` / `Cmd+Shift+C` | Continue Chapter |
| `Ctrl+Shift+E` / `Cmd+Shift+E` | Mark as Entity |

## Sync and Conflict Resolution

### Automatic Sync

- Changes are automatically synced 5 seconds after saving
- Sync status is shown in the status bar
- Icons indicate sync state:
  - ✓ Synced
  - ↑ Pending upload
  - ⚠️ Conflict detected
  - 🔴 Offline

### Manual Sync

- **Sync Now**: Run `SailZen: Sync Now` command
- **Pull Changes**: Run `SailZen: Pull Changes` to get remote updates
- **Push Changes**: Run `SailZen: Push Changes` to upload local changes

### Resolving Conflicts

1. When conflicts are detected, status bar shows ⚠️
2. Run command: `SailZen: Resolve Conflicts`
3. For each conflict, choose:
   - **Use Local**: Keep your changes
   - **Use Remote**: Accept server version
   - **Manual Merge**: Edit to resolve manually
4. Save after resolving

## Offline Mode

- Continue editing when offline
- All changes are queued locally
- When back online, changes automatically sync
- Status bar indicates offline state

## Configuration

Access settings via `File > Preferences > Settings` and search for "SailZen":

- **Backend URL**: Server address
- **Auto Sync**: Enable/disable automatic sync
- **Sync Interval**: Seconds between auto-syncs (default: 30)
- **Sync Debounce Delay**: Milliseconds to wait after save before syncing (default: 5000)
- **Conflict Strategy**: How to handle conflicts (prompt/useLocal/useRemote)

## Troubleshooting

### Cannot Connect to Server

1. Check backend URL in settings
2. Verify server is running
3. Check network connection
4. View logs: Run `SailZen: Show Logs`

### Sync Not Working

1. Check status bar for errors
2. Run `SailZen: Show Sync Status` for details
3. Try manual sync with `SailZen: Sync Now`
4. Check logs for errors

### Lost Local Changes

- Local changes are stored in `.sailzen/sync-state.db`
- Check sync queue: Run `SailZen: Show Sync Status`
- Manual sync should recover pending changes

## Tips and Tricks

1. **Use Outline View**: Quick navigation in long documents
2. **Entity Jump**: Click entities in Entity Panel to find mentions
3. **Context-Aware Commands**: Most commands auto-detect current edition/chapter
4. **Search Entities**: Use search box in Entity Panel for quick lookup
5. **Preview Before Insert**: Use diff preview for LLM suggestions
6. **Work Offline**: Don't worry about connectivity, changes will sync later

## Next Steps

- Read the [User Guide](USER_GUIDE.md) for detailed feature explanations
- Check [FAQ](FAQ.md) for common questions
- Review [CHANGELOG](../CHANGELOG.md) for latest updates

## Getting Help

- View logs: `SailZen: Show Logs`
- Report issues on GitHub
- Check documentation at [project repository]

---

Happy Writing! 🎉

