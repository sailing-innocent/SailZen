---
name: sailzen-dendron-kb
version: 1.0.0
description: "AI Native CLI for Dendron knowledge base. Query notes, export documents, create/update/delete notes via the Dendron Engine Server HTTP API. Supports fuzzy search, bulk export, document rendering, and backlink analysis."
metadata:
  requires:
    files:
      - .opencode/skills/sailzen-dendron-kb/scripts/dendron_kb.py
---

# SailZen Dendron Knowledge Base Skill

AI-native interface to Dendron knowledge bases via the Engine Server HTTP API.

## When to Use This Skill

- Querying notes in a Dendron/Dendron-based workspace
- Bulk exporting knowledge base content for analysis
- Creating or updating notes programmatically
- Analyzing document structure, backlinks, and hierarchies
- Rendering notes to HTML for external use
- Building automated knowledge processing pipelines

## Architecture Overview

```
AI Agent / CLI
      |
      | HTTP (REST API)
      v
Dendron Engine Server  (Express, runs on localhost)
      |
      | File I/O
      v
Markdown Notes (.md files in vaults)
```

The Dendron Engine Server provides a complete REST API for note CRUD, search, and rendering. This skill wraps those APIs in a Python CLI tool.

## Prerequisites

### 1. Engine Server Must Be Running

The Engine Server is automatically started when VSCode opens a Dendron workspace with the SailZen VSCode plugin active.

**Port Discovery (automatic):**
- The CLI reads `{wsRoot}/.dendron.port` (created by VSCode plugin)
- Fallback: `{wsRoot}/.dendron.port.cli`
- Fallback: `DENDRON_ENGINE_PORT` environment variable

**Manual port specification:**
```bash
python dendron_kb.py --ws <workspace> --port <port> <command>
```

### 2. Workspace Structure

A valid Dendron workspace contains:
- `dendron.yml` - Workspace configuration with vault definitions
- Vault directories containing `.md` files
- Notes use `.` as hierarchy separator (e.g., `daily.journal.2024.01.01`)

## CLI Reference

### Global Options

```bash
python scripts/dendron_kb.py \
  --ws <workspace_root>     # Workspace path (default: cwd) \
  --port <port>            # Engine server port (optional, auto-detected)
```

### Commands

#### `status` - Check Engine and Workspace

```bash
python scripts/dendron_kb.py --ws ~/notes status
```

Output:
```
Engine Server: OK
  Port: 54321
  Health: {'ok': 1}
  Version: 0.2.4

Workspace: /home/user/notes
  Vaults (3):
    - vault (vault)
    - vault2 (vault2)
    - vault3 (dependencies/localhost/vault3)
```

#### `query` - Fuzzy Search Notes

Uses Fuse.js index for fuzzy matching across titles, filenames, and content.

```bash
# Search for notes matching "ai agent"
python scripts/dendron_kb.py --ws ~/notes query "ai agent"

# Limit results and output JSON
python scripts/dendron_kb.py --ws ~/notes query "project" --limit 10 --json
```

Output:
```
Found 15 note(s) for query: 'ai agent'
ID       Updated      Vault           FName                                    Title
----------------------------------------------------------------------------------------------------
abc123.. 2024-03-15   vault           ai.agent.architecture                    AI Agent Architecture
 def456.. 2024-02-20   vault           projects.ai-chatbot                     AI Chatbot Project
```

#### `find` - Exact Search

More precise search by filename, vault, or other criteria.

```bash
# Find exact fname
python scripts/dendron_kb.py --ws ~/notes find --fname daily.journal.2024.01.01

# Find in specific vault
python scripts/dendron_kb.py --ws ~/notes find --fname root --vault vault2

# Include stub notes
python scripts/dendron_kb.py --ws ~/notes find --fname "*.journal.*" --include-stubs
```

#### `get` - Retrieve Note Content

```bash
# Get as markdown (default)
python scripts/dendron_kb.py --ws ~/notes get daily.journal.2024.01.01

# Get as JSON
python scripts/dendron_kb.py --ws ~/notes get daily.journal.2024.01.01 --format json

# Render to HTML
python scripts/dendron_kb.py --ws ~/notes get daily.journal.2024.01.01 --format html

# Get by note ID
python scripts/dendron_kb.py --ws ~/notes get abc123-def456-789
```

#### `export` - Bulk Export

```bash
# Export all notes
python scripts/dendron_kb.py --ws ~/notes export -o ./backup

# Export matching query
python scripts/dendron_kb.py --ws ~/notes export -q "project" -o ./projects_export

# Export as HTML
python scripts/dendron_kb.py --ws ~/notes export -q "blog" -o ./blog_html --format html

# Export as JSON (machine-readable)
python scripts/dendron_kb.py --ws ~/notes export -o ./kb_json --format json
```

#### `create` - Create New Note

```bash
# Simple creation
python scripts/dendron_kb.py --ws ~/notes create \
  --fname ideas.ai-agents \
  --title "AI Agent Ideas" \
  --desc "Collection of ideas for AI agent implementation"

# With body from file
python scripts/dendron_kb.py --ws ~/notes create \
  --fname meeting.2024-03-15 \
  --title "Team Sync March 15" \
  --body "@meeting_notes.md"

# With inline body
python scripts/dendron_kb.py --ws ~/notes create \
  --fname scratch.temp-idea \
  --title "Temporary Idea" \
  --body "# Core Idea\n\nThis is the main concept..."
```

#### `update` - Update Existing Note

```bash
# Update body from file
python scripts/dendron_kb.py --ws ~/notes update scratch.temp-idea --body "@updated.md"

# Update title
python scripts/dendron_kb.py --ws ~/notes update scratch.temp-idea --title "Refined Idea"

# Update multiple fields
python scripts/dendron_kb.py --ws ~/notes update scratch.temp-idea \
  --title "Final Version" \
  --body "New content here" \
  --desc "Updated description"
```

#### `delete` - Remove Note

```bash
# Delete note (moves to trash in dendron)
python scripts/dendron_kb.py --ws ~/notes delete scratch.temp-idea

# Delete by ID
python scripts/dendron_kb.py --ws ~/notes delete abc123-def456
```

#### `rename` - Rename Note

```bash
# Simple rename
python scripts/dendron_kb.py --ws ~/notes rename \
  --from scratch.temp-idea \
  --to ideas.permanent-idea

# Cross-vault rename
python scripts/dendron_kb.py --ws ~/notes rename \
  --from vault.old-note \
  --to vault2.new-note \
  --to-vault vault2
```

#### `stats` - Knowledge Base Statistics

```bash
python scripts/dendron_kb.py --ws ~/notes stats
```

Output:
```
Knowledge Base Statistics
========================================
Workspace: /home/user/notes
Vaults: 3
Total notes: 1247
  Stubs: 45
  With links: 892
  With schema: 234

Notes by vault:
  vault: 523
  vault2: 412
  vault3: 312

Recently updated:
  2024-03-20 ai.llm.research                          LLM Research Notes
  2024-03-19 projects.web-app                         Web Application Project
```

#### `blocks` - Get Note Structure

```bash
# Get all headers and anchors
python scripts/dendron_kb.py --ws ~/notes blocks ai.llm.research

# Filter headers only
python scripts/dendron_kb.py --ws ~/notes blocks ai.llm.research --filter header
```

#### `backlinks` - Analyze Backlinks

```bash
python scripts/dendron_kb.py --ws ~/notes backlinks ai.llm.research
```

Output:
```
Backlinks for ai.llm.research (12):
  projects.ai-chatbot
  reading-list.2024
  notes.technical-debt (alias: TD Notes)
```

## AI Agent Workflows

### Workflow 1: Knowledge Retrieval

```bash
# Step 1: Check connectivity
python scripts/dendron_kb.py --ws ~/notes status

# Step 2: Search for relevant notes
python scripts/dendron_kb.py --ws ~/notes query "microservice architecture" --json > /tmp/results.json

# Step 3: Get full content of top results
for id in $(jq -r '.[:3] | .[].id' /tmp/results.json); do
  python scripts/dendron_kb.py --ws ~/notes get "$id" --format markdown > "/tmp/note_${id}.md"
done

# Step 4: Process with AI...
```

### Workflow 2: Document Export Pipeline

```bash
# Export all project notes as HTML for sharing
python scripts/dendron_kb.py --ws ~/notes export \
  --query "project" \
  --output ./project_docs \
  --format html

# Or export as structured JSON for downstream processing
python scripts/dendron_kb.py --ws ~/notes export \
  --output ./kb_snapshot \
  --format json
```

### Workflow 3: Batch Content Update

```bash
# 1. Find notes matching pattern
python scripts/dendron_kb.py --ws ~/notes find --fname "*.legacy.*" --json > legacy_notes.json

# 2. For each note, update content (scripted)
python << 'EOF'
import json, subprocess
with open('legacy_notes.json') as f:
    notes = json.load(f)
for note in notes:
    # Add deprecation notice
    new_body = f"> **DEPRECATED**: This content is legacy.\n\n{note['body']}"
    subprocess.run([
        'python', 'scripts/dendron_kb.py', '--ws', '~/notes',
        'update', note['fname'], '--body', new_body
    ])
EOF
```

### Workflow 4: Knowledge Base Audit

```bash
# Get comprehensive stats
python scripts/dendron_kb.py --ws ~/notes stats

# Find orphaned notes (no backlinks)
python << 'EOF'
import json, subprocess
result = subprocess.run(
    ['python', 'scripts/dendron_kb.py', '--ws', '~/notes', 'find', '--json'],
    capture_output=True, text=True
)
notes = json.loads(result.stdout)
for note in notes:
    backlinks = [l for l in note.get('links', []) if l.get('type') == 'backlink']
    if not backlinks and not note.get('stub'):
        print(f"Orphaned: {note['fname']}")
EOF
```

## API Endpoints (Reference)

The CLI wraps these Engine Server endpoints:

| Endpoint | Method | CLI Command |
|----------|--------|-------------|
| `/health` | GET | `status` |
| `/api/workspace/initialize` | POST | `init` |
| `/api/workspace/sync` | POST | (implicit) |
| `/api/note/query` | GET | `query` |
| `/api/note/find` | POST | `find` |
| `/api/note/findMeta` | POST | (used by `stats`) |
| `/api/note/get` | GET | `get` |
| `/api/note/getMeta` | GET | (used internally) |
| `/api/note/bulkGet` | GET | (used by `export`) |
| `/api/note/write` | POST | `create`, `update` |
| `/api/note/delete` | POST | `delete` |
| `/api/note/rename` | POST | `rename` |
| `/api/note/render` | POST | `get --format html` |
| `/api/note/blocks` | GET | `blocks` |
| `/api/schema/query` | POST | (future) |

## Note Data Model

```json
{
  "id": "uuid-v4-string",
  "title": "Human Readable Title",
  "desc": "Short description",
  "fname": "hierarchy.note.name",
  "body": "# Markdown Content\n\n...",
  "vault": {"fsPath": "vault", "name": "vault"},
  "created": 1710000000000,
  "updated": 1710500000000,
  "links": [
    {"type": "wiki", "from": {...}, "to": {"fname": "other.note"}},
    {"type": "backlink", "from": {"fname": "referencing.note"}}
  ],
  "anchors": {
    "header-id": {"type": "header", "value": "Header ID", "depth": 2}
  },
  "children": ["child-note-id-1", "child-note-id-2"],
  "parent": "parent-note-id",
  "tags": ["tag1", "tag2"],
  "schema": {"moduleId": "schema-module", "schemaId": "schema-id"}
}
```

## Important Notes

1. **Port Auto-Discovery**: The CLI automatically finds the Engine Server by reading `.dendron.port` in the workspace root. This file is created by the VSCode plugin when it starts the engine.

2. **Workspace Initialization**: The first API call automatically initializes the workspace via `/api/workspace/initialize`. You rarely need to call `init` manually.

3. **Body Content**: The `body` field contains raw Markdown. Frontmatter is stored in structured fields (`title`, `desc`, `tags`, etc.), not in the body.

4. **ID vs FName**: Notes can be referenced by `id` (UUID) or `fname` (hierarchical filename). The `resolve_note()` method tries both.

5. **Vaults**: A workspace can have multiple vaults (directories). Notes within different vaults can have the same `fname`.

6. **Timestamps**: `created` and `updated` are Unix timestamps in **milliseconds**.

7. **Standard Library Only**: The CLI uses only Python standard library (`urllib.request`, `json`, `argparse`). No `requests` or external HTTP dependencies required.

8. **Optional YAML**: If `pyyaml` is installed, `dendron.yml` is parsed properly. Otherwise, a minimal parser handles basic vault configurations.

## Error Handling

Common errors and solutions:

| Error | Cause | Solution |
|-------|-------|----------|
| `No engine server found` | VSCode not running or plugin inactive | Open workspace in VSCode, wait for plugin activation |
| `Connection failed` | Engine server crashed or wrong port | Check `.dendron.port` content; restart VSCode |
| `Workspace init failed` | Invalid dendron.yml | Validate YAML syntax |
| `HTTP 500` | Engine internal error | Check engine logs; may need workspace reload |
| `Note not found` | Wrong fname or ID | Use `query` or `find` to discover correct identifier |

## Integration with SailZen 3.0

This skill is designed for the SailZen 3.0 architecture where AI Agents act as "shadow assistants":

```
Human (Feishu)
  |
  v
Feishu Gateway
  |
  v
Control Plane / Unified Agent
  |
  v
Edge Runtime (this CLI tool)
  |
  v
Dendron Engine Server <-> Markdown Knowledge Base
```

The CLI can be invoked by the Unified Agent to:
- Answer questions by querying the knowledge base
- Generate reports by exporting and analyzing notes
- Maintain documentation by creating/updating notes
- Build context for LLM prompts by retrieving relevant notes

## Extending the CLI

To add new commands, extend the `DendronEngineClient` class with new API wrappers and add corresponding `cmd_*` functions and argparse subparsers.

Key extension points:
- `DendronEngineClient._http()` - Raw HTTP wrapper
- `DendronEngineClient.write_note()` - Note creation/update
- `DendronEngineClient.render_note()` - HTML rendering
- Schema operations (`/api/schema/*`) - Not yet exposed in CLI
