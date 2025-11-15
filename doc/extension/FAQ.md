# SailZen VSCode Plugin - Frequently Asked Questions

## General Questions

### What is SailZen?

SailZen is a collaborative writing platform with LLM assistance, designed for creative writers working on novels, stories, and other long-form content. The VSCode plugin provides a local-first editing experience with automatic synchronization to the SailZen backend.

### Do I need an internet connection?

No! The plugin works offline. You can edit your work without internet, and changes will automatically sync when you reconnect. 

Meanwhile, the backend server implementation is also open-sourced. You can deploy them with your own LLM service without considering security and privicy issues.

### Where are my files stored?

Files are stored locally in your workspace under the `editions/` directory as standard Markdown files. Sync metadata is stored in `.sailzen/sync-state.db`.

## Setup and Configuration

### How do I change the backend URL?

1. Go to `File > Preferences > Settings`
2. Search for "SailZen"
3. Update "Backend URL" setting
4. Restart VSCode or run `SailZen: Initialize Workspace` again

### Can I use multiple workspaces?

Yes! Each workspace is independent. Initialize each workspace separately with `SailZen: Initialize Workspace`.

### What happens to .sailzen directory?

The `.sailzen` directory contains:
- `config.json`: Workspace settings
- `sync-state.db`: SQLite database with sync metadata
- `logs/`: Log files
- `cache/`: Temporary cache files

You should add `.sailzen/` to `.gitignore` if using version control.

## Editing and Sync

### How often does sync happen?

- **Automatic**: 5 seconds after you save a file
- **Manual**: Run `SailZen: Sync Now` anytime
- **Scheduled**: Every 30 seconds (configurable) if auto-sync is enabled

### My changes aren't syncing. Why?

Common reasons:
1. **Offline**: Check status bar for 🔴 offline indicator
2. **Sync disabled**: Check `sailzen.autoSync` setting
3. **Backend unreachable**: Verify backend URL and server status
4. **Conflict**: Check for ⚠️ conflict indicator

Run `SailZen: Show Sync Status` to see details.

### What happens if I edit the same file online and offline?

Conflicts are detected automatically. When both local and remote versions change:
1. Status bar shows ⚠️ conflict indicator
2. Run `SailZen: Resolve Conflicts`
3. Choose resolution strategy

### Can I disable automatic sync?

Yes:
1. Go to Settings
2. Search for "SailZen"
3. Uncheck "Auto Sync"

You can still sync manually with `SailZen: Sync Now`.

### How do I know if my changes are synced?

Check the status bar:
- ✓ **Synced**: All changes uploaded
- ↑ **Pending**: Changes waiting to upload
- ⟳ **Syncing**: Upload in progress
- ⚠️ **Conflict**: Needs resolution
- 🔴 **Offline**: Not connected

## LLM Features

### The LLM isn't working. Why?

Check:
1. Backend server is running and accessible
2. Edition and node are correctly detected (should auto-detect)
3. View logs with `SailZen: Show Logs` for error details

### Can I customize LLM prompts?

Currently, prompts are built automatically from:
- Current document content
- Previous paragraphs
- Entity settings (characters, locations, etc.)
- Outline/chapter structure

Custom prompts may be added in future versions.

### How do I get better LLM suggestions?

Tips for better results:
1. **Add entity details**: Define characters with descriptions
2. **Provide context**: More content = better continuations
3. **Use outline**: Clear chapter structure helps
4. **Be specific**: Select specific text for targeted improvements

### Are LLM responses cached?

Yes, LLM responses are cached for 30 minutes to avoid redundant API calls.


## Entity Management

### What are entities?

Entities are key elements in your story:
- **Characters**: People in your story
- **Locations**: Places where events occur
- **Items**: Important objects
- **Organizations**: Groups or institutions
- **Concepts**: Abstract ideas or themes


### How do I create an entity?

Two ways:
1. **Manual**: Run `SailZen: Show Entities` and click "Create"
2. **From text**: Select text, press `Ctrl+Shift+E`, choose "Create New Entity"


### Can I link mentions to existing entities?

Yes! Select text, press `Ctrl+Shift+E`, choose "Link to Existing Entity", and select from the list.


### How do I find all mentions of an entity?

1. Run `SailZen: Show Entities`
2. Click on the entity
3. Select a mention from the list
4. Editor jumps to that location with highlighting


## Outline and Navigation

### The outline isn't showing. Why?

The outline only appears for:
- Markdown files (`.md`)
- Files in your workspace
- Files with headings (`#`, `##`, etc.)

### Can I reorganize chapters in the outline?

Currently, the outline shows the document structure. To reorganize:
1. Manually cut and paste in the editor
2. Use file system to rename/move files
3. Sync changes

Future versions may support drag-and-drop reordering.

## Troubleshooting

### "Workspace not initialized" error

Run `SailZen: Initialize Workspace` first before using other commands.

### Cannot find node/edition ID

This usually means:
1. File is not in the `editions/` directory
2. `.nodes.json` mapping file is missing
3. Database is out of sync

Solution: Re-pull the edition with `SailZen: Pull Edition`.

### Sync status is stuck on "Pending"

Try:
1. Check backend connectivity
2. Run `SailZen: Sync Now` manually
3. View logs for errors
4. Restart VSCode

### Lost my local changes

Check:
1. Sync queue: `SailZen: Show Sync Status`
2. Database: `.sailzen/sync-state.db` contains all pending changes
3. Manual recovery: Export database or manually push changes

### Plugin is slow

Possible solutions:
1. Clear cache: Settings → SailZen → Clear Cache (if available)
2. Check log file size (may need rotation)
3. Reduce sync interval if too frequent
4. Check for large number of pending sync operations

## File Format and Structure

### Can I edit files outside VSCode?

Yes! Files are standard Markdown. Edit with any editor. Changes will be detected when VSCode is active.

### What markdown features are supported?

Standard markdown:
- Headings (`#` to `######`)
- Bold, italic, code
- Lists
- Links and images
- Code blocks

### Can I use custom markdown extensions?

Yes, VSCode markdown extensions work normally. However, entity mentions and special SailZen features work best in VSCode with the plugin.

## Advanced

### Can I customize keyboard shortcuts?

Yes:
1. `File > Preferences > Keyboard Shortcuts`
2. Search for "SailZen"
3. Edit bindings as needed

### Where are logs stored?

Logs are in `.sailzen/logs/sailzen.log`. View with `SailZen: Show Logs`.

### How do I reset everything?

To completely reset:
1. Delete `.sailzen/` directory
2. Run `SailZen: Initialize Workspace`
3. Pull editions again

**Warning**: This deletes all local sync state and cached data.

### Can I use this with Git?

Yes! Add to `.gitignore`:
```
.sailzen/
editions/
```

Only commit source files, not synced content.

## Performance

### How much disk space does it use?

- Editions: Size of your markdown files
- Database: Usually < 10MB
- Logs: Max 15MB (3 files × 5MB with rotation)
- Cache: Minimal, auto-cleaned

### Is there a file size limit?

No hard limit, but very large files (> 1MB) may be slower to sync and edit.

### How many editions can I have?

No limit. However, pulling many large editions at once may take time.

## Data and Privacy

### Is my data encrypted?

- Local storage: Files are plain text (not encrypted by plugin)
- Network: Depends on backend configuration (use HTTPS)
- Consider using OS-level encryption if needed

### What data is sent to the backend?

Only:
- File content when syncing
- Edition/node metadata
- LLM requests (when using AI features)

Local file operations don't communicate with backend.

### Can I export my work?

Yes! Your files are standard Markdown in `editions/` directory. Copy them anywhere.

## Future Features

### Will there be mobile support?

Mobile editing is planned for future versions through web interface or mobile app.

### Will there be real-time collaboration?

Real-time collaborative editing is on the roadmap for version 2.0.

### Can I suggest a feature?

Yes! Open an issue on GitHub or contact the development team.

---

## Still Need Help?

- Check logs: `SailZen: Show Logs`
- Review [Quick Start Guide](QUICKSTART.md)
- Read [User Guide](USER_GUIDE.md)
- Report bugs on GitHub
- Contact support


