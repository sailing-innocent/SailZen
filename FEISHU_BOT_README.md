# Feishu OpenCode Agent

Universal OpenCode controller via Feishu Bot. Works with **any directory** on your computer.

## Features

- ✅ **Mobile-first design** - Natural language and card buttons, no slash commands
- ✅ **No project binding** - Works with any path
- ✅ **Dynamic sessions** - Start OpenCode at any location
- ✅ **Configuration-based** - All settings in config file
- ✅ **Multiple sessions** - Run multiple OpenCode instances
- ✅ **Long connection** - No domain or server needed
- ✅ **Server Control Plane** - Durable state and orchestration (optional)
- ✅ **Edge Runtime** - Home-host execution with optional server sync

## Architecture

The system split into two cooperating runtime planes:

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
                           │ HTTPS/WebSocket (optional)
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

### Prerequisites

Before starting, ensure you have:

1. **Python 3.8+** installed
2. **uv** or **pip** for package management
3. **opencode** installed and in PATH
4. A **Feishu app** created on [https://open.feishu.cn/app](https://open.feishu.cn/app)

### Step 1: Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install lark-oapi pyyaml
```

### Step 2: Configure

Copy the example configuration:
```bash
cp bot/opencode.bot.yaml bot/myconfig.bot.yaml
```

Edit `bot/myconfig.bot.yaml` with your Feishu credentials:
```yaml
# REQUIRED: Feishu App Credentials
# Get these from: https://open.feishu.cn/app
app_id: "cli_xxxxxxxx"
app_secret: "xxxxxxxxxxxxxxxx"

# Project inventory (optional but recommended)
projects:
  - slug: "sailzen"
    path: "D:/ws/repos/SailZen"
    label: "SailZen"
```

### Step 3: Run

```bash
# Recommended: use explicit config file
uv run bot/feishu_agent.py -c bot/myconfig.bot.yaml

# Or use the example config directly
uv run bot/feishu_agent.py -c bot/opencode.bot.yaml
```

---

## Detailed Environment Setup

### 1. Feishu App Configuration

#### 1.1 Create a Feishu App

1. Visit [Feishu Open Platform](https://open.feishu.cn/app)
2. Login with your enterprise account
3. Click **Create App** > **Enterprise Self-built App**
4. Fill in app name and description
5. Record the **App ID** and **App Secret**

#### 1.2 Enable Bot Capability

1. In your app page, go to **App Capability** > **Bot**
2. Click **Enable Bot**
3. Configure bot name and avatar
4. Save changes

#### 1.3 Configure Permissions

1. Go to **Permission Management**
2. Add the following permissions:
   - `im:message.group_at_msg:readonly` - Receive group @ messages
   - `im:message.p2p_msg:readonly` - Receive private messages
   - `im:message:send` - Send messages

#### 1.4 Configure Event Subscription (Long Connection Mode)

1. Go to **Events & Callbacks** > **Event Subscription**
2. Enable **Event Subscription**
3. Select **Long Connection** mode
   - ⚠️ **Important**: Use "Long Connection" mode, NOT "Request URL" mode
   - This eliminates the need for HTTPS domain and server configuration
4. Add subscription event:
   - `im.message.receive_v1` - Receive messages

#### 1.5 Publish the App

1. Go to **Version Management & Release**
2. Click **Create Version**
3. Fill in version number and changelog
4. Click **Apply for Release**
5. Contact your enterprise admin for approval

#### 1.6 Add Bot to Group

1. In a Feishu group, click **Settings** > **Group Bots** > **Add Bot**
2. Select your created app
3. The bot is now ready to use

### 2. Local Environment Setup

#### 2.1 Python Environment

```bash
# Check Python version (requires 3.8+)
python --version

# Install dependencies
pip install lark-oapi pyyaml

# Or using uv
uv sync
```

#### 2.2 OpenCode Installation

Ensure `opencode` is installed and available in PATH:

```bash
# Check if opencode is installed
opencode --version

# If not installed, follow the official installation guide
# https://github.com/your-org/opencode#installation
```

#### 2.3 Project Directory Setup

```bash
# Clone or navigate to SailZen repository
cd ~/repos/SailZen  # or your preferred location

# Create data directories if not exist
mkdir -p data/control_plane
mkdir -p logs
```

### 3. Configuration File Reference

#### 3.1 Minimal Configuration

Create `bot/myconfig.bot.yaml`:

```yaml
# REQUIRED: Feishu App Credentials
app_id: "cli_xxxxxxxxxxxxxxxx"
app_secret: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# OPTIONAL: Project shortcuts
projects:
  - slug: "myproject"
    path: "/home/user/projects/myproject"
    label: "My Project"
```

#### 3.2 Full Configuration

```yaml
# =============================================================================
# REQUIRED: Feishu App Credentials
# =============================================================================
app_id: "cli_xxxxxxxxxxxxxxxx"
app_secret: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# =============================================================================
# OPTIONAL: Control Plane Settings (for server integration)
# =============================================================================

# Server control plane URL
control_plane_url: "https://your-server.com/api/v1/remote-dev/control-plane"

# Edge node identifier (unique for this machine)
edge_node_key: "home-macbook-pro"

# Edge node secret for authentication
edge_secret: ""

# Host name for this machine (auto-detected if empty)
host_name: ""

# Runtime version identifier
runtime_version: "0.1.0"

# Heartbeat interval in seconds
heartbeat_interval_seconds: 15

# Request timeout in seconds
request_timeout_seconds: 15

# Offline mode - don't connect to control plane
offline_mode: false

# Queue file path for offline message buffering
queue_path: "data/control_plane/edge_queue.json"

# =============================================================================
# OPTIONAL: Session Settings
# =============================================================================

# Starting port for OpenCode sessions (default: 4096)
# Each session uses a different port: 4096, 4097, 4098, ...
base_port: 4096

# Maximum concurrent OpenCode sessions (default: 10)
max_sessions: 10

# Session callback timeout in seconds (default: 300)
callback_timeout: 300

# Auto-restart crashed sessions (default: false)
auto_restart: false

# =============================================================================
# OPTIONAL: Project Inventory
# =============================================================================

projects:
  - slug: "sailzen"
    path: "D:/ws/repos/SailZen"
    label: "SailZen"
  - slug: "frontend"
    path: "/home/user/projects/frontend"
    label: "Frontend Project"
```

### 4. Running the Agent

#### 4.1 Interactive Mode (Development)

```bash
# Run with explicit config
uv run bot/feishu_agent.py -c bot/myconfig.bot.yaml

# Run with verbose logging
uv run bot/feishu_agent.py -c bot/myconfig.bot.yaml --verbose
```

#### 4.2 Background Mode (Production)

**Linux/Mac:**
```bash
# Using nohup
nohup uv run bot/feishu_agent.py -c bot/myconfig.bot.yaml > logs/feishu_agent.log 2>&1 &

# Check if running
ps aux | grep feishu_agent

# Stop the agent
pkill -f feishu_agent
```

**Windows:**
```powershell
# Using PowerShell job
Start-Process -FilePath "uv" -ArgumentList "run", "bot/feishu_agent.py", "-c", "bot/myconfig.bot.yaml" -WindowStyle Hidden

# Or use Windows Task Scheduler for auto-start
```

#### 4.3 Systemd Service (Linux)

Create `/etc/systemd/system/feishu-agent.service`:

```ini
[Unit]
Description=Feishu OpenCode Agent
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/repos/SailZen
ExecStart=/usr/local/bin/uv run bot/feishu_agent.py -c bot/myconfig.bot.yaml
Restart=always
RestartSec=10
StandardOutput=append:/home/your-username/repos/SailZen/logs/feishu_agent.log
StandardError=append:/home/your-username/repos/SailZen/logs/feishu_agent.log

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable feishu-agent.service
sudo systemctl start feishu-agent.service
sudo systemctl status feishu-agent.service
```

---

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
├── bot.example.yaml      # Another example configuration
├── test_feishu_bridge.py # Bridge integration tests
├── test_feishu_events.py # Event reception tests
└── debug_feishu.py       # Debug tool
```

## Debug Tools

### Test Event Reception
```bash
uv run bot/test_feishu_events.py -c bot/myconfig.bot.yaml
```

### Debug Connection
```bash
uv run bot/debug_feishu.py -c bot/myconfig.bot.yaml
```

### Test Bridge Integration
```bash
uv run bot/test_feishu_bridge.py
```

## Troubleshooting

### Agent Won't Start

**Problem**: `ModuleNotFoundError: No module named 'lark_oapi'`

**Solution**:
```bash
pip install lark-oapi pyyaml
# or
uv sync
```

### Cannot Connect to Feishu

**Problem**: Connection errors or authentication failures

**Solutions**:
1. Check `app_id` and `app_secret` in config file
2. Verify the app is published and approved
3. Check network connectivity: `curl https://open.feishu.cn`
4. Review agent logs: `tail -f logs/feishu_agent.log`

### Bot Not Responding in Feishu

**Problem**: Bot is silent when mentioned

**Solutions**:
1. Check if agent is running: `ps aux | grep feishu_agent`
2. Verify bot is added to the group
3. Check event subscription is enabled with correct event type
4. Review agent logs for errors

### OpenCode Not Found

**Problem**: `opencode: command not found`

**Solution**:
1. Install opencode following official guide
2. Ensure it's in PATH: `which opencode`
3. Or specify full path in configuration

## Requirements

- Python 3.8+
- lark-oapi (`pip install lark-oapi`)
- pyyaml (`pip install pyyaml`)
- opencode (installed and in PATH)

## Design Documentation

For detailed design decisions and architecture:
- [openspec/changes/redesign-feishu-opencode-bridge-workflow/design.md](openspec/changes/redesign-feishu-opencode-bridge-workflow/design.md)

**Important Design Decision**: This system intentionally does NOT support slash commands (e.g., `/start`, `/status`) because they require symbol keyboard switching on mobile devices, creating poor user experience. We use natural language and card buttons instead.

## Deployment

For server deployment instructions, see:
- [doc/maintain/DEPLOY.md](doc/maintain/DEPLOY.md)

## License

MIT
