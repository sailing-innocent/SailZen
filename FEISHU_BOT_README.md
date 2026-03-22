# Feishu OpenCode Agent

Universal OpenCode controller via Feishu Bot. Works with **any directory** on your computer.

## Features

- ✅ **No project binding** - Works with any path
- ✅ **Dynamic sessions** - Start OpenCode at any location
- ✅ **Configuration-based** - All settings in config file
- ✅ **Multiple sessions** - Run multiple OpenCode instances
- ✅ **Long connection** - No domain or server needed

## Quick Start (3 Steps)

### 1. Install
```bash
pip install lark-oapi pyyaml
```

### 2. Create Config
```bash
python scripts/feishu_agent.py --init
```

Edit the config file:
- Windows: `%USERPROFILE%\AppData\Roaming\feishu-agent\config.yaml`
- Linux/Mac: `~/.config/feishu-agent/config.yaml`

```yaml
app_id: "cli_xxxxxxxx"
app_secret: "xxxxxxxxxxxxxxxx"
```

### 3. Run
```bash
python scripts/feishu_agent.py
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

## Configuration

### Config File Location
- **Windows**: `%USERPROFILE%\AppData\Roaming\feishu-agent\config.yaml`
- **Linux/Mac**: `~/.config/feishu-agent/config.yaml`

### Full Configuration Options
```yaml
# Required
app_id: "cli_xxxxxxxx"
app_secret: "xxxxxxxxxxxxxxxx"

# Optional
base_port: 4096        # Starting port for sessions
max_sessions: 10       # Maximum concurrent sessions
callback_timeout: 300  # Callback timeout in seconds
auto_restart: false    # Auto-restart crashed sessions
```

### Custom Config Path
```bash
python scripts/feishu_agent.py --config /path/to/config.yaml
```

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start <path>` | Start OpenCode at path | `/start ~/projects/myapp` |
| `/stop [path]` | Stop session(s) | `/stop` or `/stop ~/projects/myapp` |
| `/status [path]` | Show status | `/status` or `/status ~/projects/myapp` |
| `/list` | List all sessions | `/list` |
| `/code <path> <task>` | Start and request code | `/code ~/projects/myapp implement login` |
| `/git <path> <cmd>` | Git operations | `/git ~/projects/myapp status` |
| `/help` | Show help | `/help` |

## Architecture

```
Feishu ←──WebSocket── Agent ──► OpenCode Sessions
                           ├── Session 1: ~/project1 (Port 4096)
                           ├── Session 2: ~/project2 (Port 4097)
                           └── Session N: ~/projectN (Port 4096+N)
```

## Files

```
scripts/
├── feishu_agent.py       # Main agent (universal, config-based)
├── echo_bot.py           # Simple echo bot example
└── config.example.yaml   # Config file example

doc/maintain/
├── FEISHU_AGENT_TUTORIAL.md  # Detailed tutorial
└── ...
```

## Tutorial

📚 **Full Tutorial**: [doc/maintain/FEISHU_AGENT_TUTORIAL.md](doc/maintain/FEISHU_AGENT_TUTORIAL.md)

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

## Requirements

- Python 3.8+
- lark-oapi (`pip install lark-oapi`)
- pyyaml (`pip install pyyaml`)
- opencode (installed and in PATH)

## License

MIT
