# Feishu OpenCode Agent

Universal OpenCode controller via Feishu Bot. Works with **any directory** on your computer.

## Features

- ✅ **Mobile-first design** - Natural language and card buttons, no slash commands
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

**Important**: This system uses a **mobile-first design** that intentionally does NOT support slash commands (e.g., `/start`, `/status`). 

**Why no slash commands?** On mobile, typing `/` requires switching to the symbol keyboard, which is slow and creates poor user experience. Instead, we use:
- **Natural language** - Just type what you want
- **Card buttons** - Tap interactive buttons in Feishu cards
- **Voice input** - Use your phone's voice-to-text feature

### Start OpenCode at Any Path

Simply send a natural language message:
```
@机器人 启动 ~/projects/myapp
@机器人 start D:\work\project
@机器人 打开项目 ./relative/path
```

Or use the **Workspace Home** card buttons:
1. Send any message to the bot to get the home card
2. Tap "🚀 启动会话" button
3. Select the workspace from the list

### Code Generation
```
@机器人 帮我写代码 ~/projects/myapp implement login page
@机器人 code request ~/projects/myapp 实现用户认证
```

### Git Operations
```
@机器人 git状态 ~/projects/myapp
@机器人 git提交 ~/projects/myapp "Add feature"
@机器人 git推送 ~/projects/myapp
```

### Session Management
```
@机器人 查看状态              # Show all sessions
@机器人 status ~/projects/myapp  # Show specific session
@机器人 停止会话               # Stop all sessions
@机器人 stop ~/projects/myapp    # Stop specific session
@机器人 列出工作区              # List all workspaces
```

### Natural Language Examples
```
@机器人 查看状态
@机器人 启动 ~/projects/myapp
@机器人 停止
@机器人 帮助
@机器人 列出所有项目
```

## What Happens If I Type Slash Commands?

If you accidentally type a slash command like `/status`, the bot will reply:
```
❌ 不支持 / 开头的命令

在手机上输入 / 需要切换键盘，体验不佳。
请直接输入自然语言，例如：
• "查看状态"
• "启动工作区"
• "停止会话"

或使用下方的快捷按钮 👇
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

## Interaction Patterns

### Mobile-First Design Principles

1. **Natural Language First**: Just type what you want in Chinese or English
   - ✅ "启动工作区"
   - ✅ "查看状态"
   - ✅ "停止会话"
   - ❌ `/start` (not supported)

2. **Card-Based Actions**: Use buttons in Feishu cards for quick actions
   - Tap buttons instead of typing commands
   - Visual feedback with rich cards

3. **Voice Input Friendly**: Use your phone's voice-to-text
   - Speak naturally: "启动我的前端项目"
   - The system handles messy transcription with normalization

4. **No Symbol Switching**: All interactions use regular characters
   - No need to switch to symbol keyboard for `/`
   - Faster input on mobile devices

## Available Actions

| Action | Natural Language Examples | Card Button |
|--------|---------------------------|-------------|
| Start Session | "启动 ~/projects/myapp", "start myapp" | 🚀 启动会话 |
| Stop Session | "停止", "stop session" | ⏹️ 停止 |
| View Status | "查看状态", "status" | 📊 查看状态 |
| List Workspaces | "列出工作区", "list workspaces" | 📁 工作区列表 |
| Code Request | "帮我写代码", "code request" | 📝 代码请求 |
| Git Status | "git状态", "git status" | Git 状态 |
| Git Commit | "git提交", "git commit" | Git 提交 |
| Git Push | "git推送", "git push" | Git 推送 |

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
@机器人 帮我写代码 ~/projects/myapp 实现用户认证

📝 Code Generation
━━━━━━━━━━━━━━
Path: /home/user/projects/myapp
Port: 4096
Task: 实现用户认证

OpenCode running at http://localhost:4096
Open this URL and input your task.
```

### Example 2: Git Workflow
```
@机器人 git状态 ~/projects/myapp
@机器人 git提交 ~/projects/myapp "Add auth feature"  
@机器人 git推送 ~/projects/myapp
```

### Example 3: Multi-Project
```
@机器人 启动 ~/projects/frontend
@机器人 启动 ~/projects/backend
@机器人 查看状态
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

**Important Design Decision**: This system intentionally does NOT support slash commands (e.g., `/start`, `/status`) because they require symbol keyboard switching on mobile devices, creating poor user experience. We use natural language and card buttons instead.

## License

MIT
