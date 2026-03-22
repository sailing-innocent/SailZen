# Feishu OpenCode Agent

Universal OpenCode controller via Feishu Bot. Works with **any directory** on your computer.

## Features

- ✅ **No project binding** - Works with any path
- ✅ **Dynamic sessions** - Start OpenCode at any location
- ✅ **Configuration-based** - All settings in config file
- ✅ **Multiple sessions** - Run multiple OpenCode instances
- ✅ **Long connection** - No domain or server needed
- ✅ **Server Control Plane** - Durable state and orchestration
- ✅ **Edge Runtime** - Home-host execution with server sync

## Architecture

The system is split into two cooperating runtime planes:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SERVER CONTROL PLANE                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Session    │  │    LLM       │  │   Event      │          │
│  │   Registry   │  │   Router     │  │   Store      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  • Durable state and orchestration                             │
│  • Policy enforcement and audit                                │
│  • Intent routing and action planning                          │
│  • Event streaming and alerting                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS/WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   HOME-HOST EDGE PLANE                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Feishu Bot   │  │   Desktop    │  │  OpenCode    │          │
│  │   (Lark WS)  │  │    Agent     │  │  Sessions    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  • Local Feishu event reception                                │
│  • OpenCode process lifecycle                                  │
│  • Heartbeat and state sync                                    │
│  • Command execution                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start (3 Steps)

Register robot on https://open.feishu.cn/app

### 1. Install Dependencies
```bash
pip install lark-oapi pyyaml
```

### 2. Configure
Copy the example configuration:
```bash
cp bot/opencode.bot.yaml bot/myconfig.bot.yaml
```

Edit `bot/myconfig.bot.yaml`:
```yaml
# REQUIRED: Feishu App Credentials
app_id: "cli_xxxxxxxx"
app_secret: "xxxxxxxxxxxxxxxx"

# Project inventory (optional)
projects:
  - slug: "sailzen"
    path: "D:/ws/repos/SailZen"
    label: "SailZen"
```

### 3. Run
```bash
# Recommended: use explicit config file
uv run bot/feishu_agent.py -c bot/myconfig.bot.yaml

# Or use the example config directly
uv run bot/feishu_agent.py -c bot/opencode.bot.yaml
```

## Usage

### Start OpenCode at Any Path
```
@机器人 /start ~/projects/myapp
@机器人 /start D:\work\project
@机器人 /start ./relative/path
```

### Code Generation
```
@机器人 /code ~/projects/myapp implement login page
```

### Git Operations
```
@机器人 /git ~/projects/myapp status
@机器人 /git ~/projects/myapp commit "Add feature"
@机器人 /git ~/projects/myapp push
```

### Session Management
```
@机器人 /status              # Show all sessions
@机器人 /status ~/projects/myapp  # Show specific session
@机器人 /stop               # Stop all sessions
@机器人 /stop ~/projects/myapp    # Stop specific session
@机器人 /list              # List all sessions
```

### Natural Language Commands
```
@机器人 start ~/projects/myapp
@机器人 status
@机器人 stop
@机器人 help
```

## Configuration

### Config File
The recommended approach is to use a project-local config file:
```yaml
# bot/opencode.bot.yaml
app_id: "cli_xxxxxxxx"
app_secret: "xxxxxxxxxxxxxxxx"

base_port: 4096
max_sessions: 10
callback_timeout: 300
auto_restart: false

projects:
  - slug: "sailzen"
    path: "D:/ws/repos/SailZen"
    label: "SailZen"
```

### Full Configuration Options
```yaml
# Required - Feishu App Credentials
app_id: "cli_xxxxxxxx"
app_secret: "xxxxxxxxxxxxxxxx"

# Remote Control Plane (Optional)
control_plane_url: "http://127.0.0.1:8000/api/v1/remote-dev/control-plane"
edge_node_key: "home-dev-host"
edge_secret: ""
host_name: ""
runtime_version: "0.1.0"
heartbeat_interval_seconds: 15
request_timeout_seconds: 15
offline_mode: false
queue_path: "data/control_plane/edge_queue.json"

# Project Inventory (Optional)
projects:
  - slug: "myproject"
    path: "/home/user/projects/myproject"
    label: "My Project"

# Session Settings
base_port: 4096        # Starting port for sessions
max_sessions: 10       # Maximum concurrent sessions
callback_timeout: 300  # Callback timeout in seconds
auto_restart: false    # Auto-restart crashed sessions
```

### Using Custom Config Path
```bash
# Recommended approach with uv
uv run bot/feishu_agent.py -c bot/myconfig.bot.yaml

# Using --config long form
uv run bot/feishu_agent.py --config bot/myconfig.bot.yaml

# Traditional python (requires pip install lark-oapi pyyaml)
python bot/feishu_agent.py -c bot/myconfig.bot.yaml
```

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/session <path>` | Create/get session for path | `/session ~/projects/myapp` |
| `/start <path>` | Start OpenCode at path | `/start ~/projects/myapp` |
| `/stop [path]` | Stop session(s) | `/stop` or `/stop ~/projects/myapp` |
| `/status [path]` | Show status | `/status` or `/status ~/projects/myapp` |
| `/list` | List all sessions | `/list` |
| `/code <path> <task>` | Start and request code | `/code ~/projects/myapp implement login` |
| `/git <path> <cmd>` | Git operations | `/git ~/projects/myapp status` |
| `/help` | Show help | `/help` |

## Files

```
bot/
├── feishu_agent.py       # Main agent (universal, config-based)
├── opencode.bot.yaml     # Example configuration file
├── test_feishu_bridge.py # Bridge integration tests
├── test_feishu_events.py # Event reception tests
└── debug_feishu.py       # Debug tool
```

## Tutorial

Includes:
- Feishu app setup
- Configuration guide
- Usage examples
- Troubleshooting

## Examples

### Example 1: Quick Code Generation
```
@机器人 /code ~/projects/myapp implement user authentication with JWT

📝 Code Generation
━━━━━━━━━━━━━━
Path: /home/user/projects/myapp
Port: 4096
Task: implement user authentication with JWT

OpenCode running at http://localhost:4096
Open this URL and input your task.
```

### Example 2: Git Workflow
```
@机器人 /git ~/projects/myapp status
@机器人 /git ~/projects/myapp commit "Add auth feature"  
@机器人 /git ~/projects/myapp push
```

### Example 3: Multi-Project
```
@机器人 /start ~/projects/frontend
@机器人 /start ~/projects/backend
@机器人 /status
```

### Example 4: Server Control Plane Integration
```yaml
# bot/opencode.bot.yaml
app_id: "cli_xxxxxxxx"
app_secret: "xxxxxxxxxxxxxxxx"

# Enable server integration
control_plane_url: "http://your-server:8000/api/v1/remote-dev/control-plane"
edge_node_key: "home-macbook-pro"
heartbeat_interval_seconds: 15

projects:
  - slug: "sailzen"
    path: "D:/ws/repos/SailZen"
    label: "SailZen"
```

Then run:
```bash
uv run bot/feishu_agent.py -c bot/opencode.bot.yaml
```

## Debug Tools

### Test Event Reception
```bash
uv run bot/test_feishu_events.py -c bot/opencode.bot.yaml
```

### Debug Connection
```bash
uv run bot/debug_feishu.py -c bot/opencode.bot.yaml
```

### Test Bridge Integration
```bash
uv run bot/test_feishu_bridge.py
```

## Requirements

- Python 3.8+
- lark-oapi (`pip install lark-oapi`)
- pyyaml (`pip install pyyaml`)
- opencode (installed and in PATH)

## Design Documentation

For detailed design decisions and architecture:
- [openspec/changes/redesign-feishu-opencode-bridge-workflow/design.md](openspec/changes/redesign-feishu-opencode-bridge-workflow/design.md)

## License

MIT
