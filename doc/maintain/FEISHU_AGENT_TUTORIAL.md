# Feishu Bot Agent 完整教程

## 目录
1. [快速开始（5分钟）](#快速开始)
2. [详细配置指南](#详细配置指南)
3. [使用场景示例](#使用场景示例)
4. [高级功能](#高级功能)
5. [故障排查](#故障排查)

---

## 快速开始

### 第一步：安装依赖（1分钟）

```bash
# 安装必需的Python包
pip install lark-oapi pyyaml

# 验证安装
python -c "import lark_oapi; print('✅ lark-oapi installed')"
```

### 第二步：配置飞书应用（3分钟）

#### 2.1 创建飞书应用

1. 打开 https://open.feishu.cn/
2. 点击「创建企业自建应用」
3. 填写应用名称："OpenCode Controller"
4. 点击「确定创建」

#### 2.2 记录凭证

进入应用详情页，记录以下信息：
- **App ID**: `cli_xxxxxxxx`
- **App Secret**: 点击显示并复制

#### 2.3 启用机器人能力

1. 左侧菜单 → 「应用能力」→ 「机器人」
2. 点击「启用机器人」
3. 配置机器人头像和名称

#### 2.4 添加权限

1. 左侧菜单 → 「权限管理」
2. 搜索并添加以下权限：
   - ✅ `im:message.group_at_msg:readonly`
   - ✅ `im:message.p2p_msg:readonly`
   - ✅ `im:message:send`

#### 2.5 配置事件订阅（关键！）

1. 左侧菜单 → 「事件与回调」→ 「事件订阅」
2. **订阅方式** 选择 **「使用长连接接收事件」**
3. 点击「添加事件」→ 选择 `im.message.receive_v1`
4. 点击「保存」

⚠️ **注意**: 一定要选择"长连接模式"，不要选"发送事件到开发者服务器"

#### 2.6 发布应用

1. 左侧菜单 → 「版本管理与发布」
2. 点击「创建版本」
3. 填写版本信息，点击「保存」
4. 点击「申请发布」
5. 联系企业管理员审批

#### 2.7 添加到群组

1. 在目标飞书群组中，点击右上角「设置」
2. 选择「群机器人」→ 「添加机器人」
3. 选择「OpenCode Controller」
4. 点击「确定」

### 第三步：启动Agent（1分钟）

#### 3.1 设置环境变量

**Windows (PowerShell)**:
```powershell
$env:FEISHU_APP_ID="cli_xxxxxxxx"
$env:FEISHU_APP_SECRET="xxxxxxxxxxxxxxxx"
```

**Windows (CMD)**:
```cmd
set FEISHU_APP_ID=cli_xxxxxxxx
set FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
```

**Linux/Mac**:
```bash
export FEISHU_APP_ID=cli_xxxxxxxx
export FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
```

#### 3.2 启动Agent

```bash
# 进入项目目录
cd /path/to/SailZen

# 启动Agent
python scripts/feishu_agent.py
```

你会看到：
```
🚀 Feishu Bot Agent Starting...
   Config: C:\Users\xxx\.config\opencode-agent\config.yaml
   Projects: 0

✅ Agent configured successfully
   Managing 0 projects
🔗 Connecting to Feishu...
   (Press Ctrl+C to stop)

connected to wss://ws.feishu.cn/...
```

### 第四步：测试使用

在飞书群组中发送：
```
@OpenCode Controller /help
```

你应该立即收到回复：
```
🤖 Feishu Bot Agent - Commands
━━━━━━━━━━━━━━
Project Management:
  /list - List configured projects
  /add <name> <path> [port] - Add project
  /status [project] - Show project status
...
```

---

## 详细配置指南

### 配置文件详解

Agent支持两种配置方式：
1. **环境变量** - 适合快速测试
2. **配置文件** - 适合长期使用，支持多项目管理

#### 配置文件位置

- **Windows**: `%USERPROFILE%\AppData\Roaming\opencode-agent\config.yaml`
- **Linux/Mac**: `~/.config/opencode-agent/config.yaml`

#### 配置文件示例

创建配置文件：

```bash
# Windows
mkdir "%USERPROFILE%\AppData\Roaming\opencode-agent"
notepad "%USERPROFILE%\AppData\Roaming\opencode-agent\config.yaml"

# Linux/Mac
mkdir -p ~/.config/opencode-agent
nano ~/.config/opencode-agent/config.yaml
```

写入以下内容：

```yaml
# 默认项目（可选）
default_project: sailzen

# 项目列表
projects:
  - name: sailzen
    path: D:/ws/repos/SailZen
    port: 4096
    description: "SailZen main project"
    auto_start: false
  
  - name: myapp
    path: ~/projects/myapp
    port: 4097
    description: "My side project"
    auto_start: false
  
  - name: work-project
    path: /home/user/work/project
    port: 4098
    description: "Work project"
```

#### 配置字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `default_project` | string | 否 | 默认项目名，用于简化命令 |
| `projects` | list | 否 | 项目列表 |
| `projects[].name` | string | 是 | 项目标识名（短名，无空格） |
| `projects[].path` | string | 是 | 项目绝对路径 |
| `projects[].port` | int | 否 | OpenCode端口，默认4096+index |
| `projects[].description` | string | 否 | 项目描述 |
| `projects[].auto_start` | bool | 否 | 启动Agent时自动启动，默认false |

### 环境变量详解

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `FEISHU_APP_ID` | ✅ | 飞书App ID |
| `FEISHU_APP_SECRET` | ✅ | 飞书App Secret |
| `AGENT_CONFIG_PATH` | 否 | 配置文件路径，默认使用标准位置 |

---

## 使用场景示例

### 场景1：添加并启动项目

**步骤1**：添加项目
```
@机器人 /add sailzen D:/ws/repos/SailZen 4096 "SailZen main project"
```

回复：
```
✅ Added project 'sailzen'
   Path: D:\ws\repos\SailZen
   Port: 4096
```

**步骤2**：启动OpenCode
```
@机器人 /start sailzen
```

回复：
```
🚀 Starting OpenCode for project 'sailzen'...
   Path: D:\ws\repos\SailZen
   Port: 4096
✅ OpenCode started for 'sailzen' (PID: 12345, Port: 4096)
```

**步骤3**：查看状态
```
@机器人 /status
```

回复：
```
📊 Project Status
━━━━━━━━━━━━━━
sailzen: 🟢 Running (since 14:32:15) | Port: 4096 | Path: D:\ws\repos\SailZen
━━━━━━━━━━━━━━
Total: 1 | Running: 1
```

### 场景2：代码生成请求

```
@机器人 /code sailzen implement user login with JWT authentication
```

回复：
```
📝 Code Generation Request
━━━━━━━━━━━━━━
Project: sailzen
Task: implement user login with JWT authentication

OpenCode is running at http://localhost:4096
Please input the task in OpenCode.

💡 Tip: You can also use natural language:
"Start sailzen and implement login page"
```

此时你可以：
1. 在浏览器打开 http://localhost:4096
2. 输入提示词让OpenCode生成代码
3. 完成后用Git命令提交

### 场景3：Git操作工作流

**查看状态**：
```
@机器人 /git sailzen status
```

**拉取最新代码**：
```
@机器人 /git sailzen pull
```

**提交修改**：
```
@机器人 /git sailzen commit "Add user authentication feature"
```

**推送到远程**：
```
@机器人 /git sailzen push
```

### 场景4：自然语言交互

支持自然语言识别：

```
@机器人 Start sailzen
```
等价于：
```
@机器人 /start sailzen
```

```
@机器人 Status of myapp
```
等价于：
```
@机器人 /status myapp
```

```
@机器人 List all projects
```
等价于：
```
@机器人 /list
```

### 场景5：管理多个项目

**列出所有项目**：
```
@机器人 /list
```

回复：
```
📁 Configured Projects
━━━━━━━━━━━━━━
🟢 sailzen
   Path: D:\ws\repos\SailZen
   Port: 4096
   Desc: SailZen main project

⚪ myapp
   Path: C:\Users\xxx\projects\myapp
   Port: 4097
   Desc: My side project

⚪ work-project
   Path: /home/user/work/project
   Port: 4098
```

**停止所有项目**：
```
@机器人 /stop
```

**停止特定项目**：
```
@机器人 /stop myapp
```

---

## 高级功能

### 1. 开机自启配置

#### Windows

创建启动脚本 `start_opencode_agent.bat`：

```batch
@echo off
cd /d D:\ws\repos\SailZen
set FEISHU_APP_ID=cli_xxxxxxxx
set FEISHU_APP_SECRET=xxxxxxxx
python scripts\feishu_agent.py
```

添加到启动文件夹：
1. Win+R → 输入 `shell:startup`
2. 复制 `start_opencode_agent.bat` 到该文件夹

#### Linux (systemd)

创建服务文件 `~/.config/systemd/user/opencode-agent.service`：

```ini
[Unit]
Description=OpenCode Feishu Agent
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/user/repos/SailZen
Environment="FEISHU_APP_ID=cli_xxxxxxxx"
Environment="FEISHU_APP_SECRET=xxxxxxxx"
ExecStart=/usr/bin/python3 /home/user/repos/SailZen/scripts/feishu_agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

启用服务：
```bash
systemctl --user daemon-reload
systemctl --user enable opencode-agent.service
systemctl --user start opencode-agent.service

# 查看状态
systemctl --user status opencode-agent.service
```

#### Mac (launchd)

创建 plist 文件 `~/Library/LaunchAgents/com.opencode.agent.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.opencode.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/xxx/repos/SailZen/scripts/feishu_agent.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>FEISHU_APP_ID</key>
        <string>cli_xxxxxxxx</string>
        <key>FEISHU_APP_SECRET</key>
        <string>xxxxxxxx</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

加载并启动：
```bash
launchctl load ~/Library/LaunchAgents/com.opencode.agent.plist
launchctl start com.opencode.agent
```

### 2. 多设备同步

由于Agent本地运行，如果你想在多台电脑上使用：

1. 在每台电脑上安装Agent
2. 使用相同的 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`
3. 每台电脑配置不同的项目（或相同项目的不同端口）

注意：飞书Bot消息会随机推送到其中一个在线Agent

### 3. 日志记录

Agent默认输出到控制台，你可以重定向到文件：

```bash
# Windows
python scripts/feishu_agent.py > agent.log 2>&1

# Linux/Mac
python3 scripts/feishu_agent.py >> ~/.local/share/opencode-agent/agent.log 2>&1
```

或使用 `tee` 同时显示和保存：
```bash
python3 scripts/feishu_agent.py | tee -a agent.log
```

---

## 故障排查

### 问题1: Agent启动失败

**症状**: 显示 "❌ Error: lark-oapi not installed"

**解决**:
```bash
pip install lark-oapi pyyaml
```

### 问题2: 无法连接到Feishu

**症状**: 长时间显示 "🔗 Connecting to Feishu..." 没有 "connected" 消息

**检查清单**:
1. ✅ 确认 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 正确设置
2. ✅ 确认网络可以访问 https://open.feishu.cn
3. ✅ 确认飞书应用已发布并通过审批

**测试网络**:
```bash
curl https://open.feishu.cn
curl https://ws.feishu.cn
```

### 问题3: 收不到消息

**症状**: Agent已连接，但在飞书中@机器人没有响应

**检查清单**:
1. ✅ 确认机器人已添加到目标群组
2. ✅ 确认飞书应用「事件订阅」选择了「使用长连接接收事件」
3. ✅ 确认订阅了 `im.message.receive_v1` 事件
4. ✅ 检查Agent日志是否有收到消息的记录

### 问题4: OpenCode启动失败

**症状**: `/start` 命令返回错误

**检查**:
1. ✅ 确认OpenCode已安装: `opencode --version`
2. ✅ 确认项目路径存在: `ls /path/to/project`
3. ✅ 确认端口未被占用: 
   ```bash
   # Windows
   netstat -ano | findstr :4096
   
   # Linux/Mac
   lsof -i :4096
   ```

**手动测试**:
```bash
cd /path/to/project
opencode web --hostname 127.0.0.1 --port 4096
```

### 问题5: Git操作失败

**症状**: `/git` 命令返回错误

**检查**:
1. ✅ 确认是Git仓库: `ls -la /path/to/project/.git`
2. ✅ 确认Git已安装: `git --version`
3. ✅ 检查远程配置: `cd /path/to/project && git remote -v`

### 问题6: 配置文件不生效

**症状**: 配置了项目但 `/list` 显示为空

**检查**:
1. ✅ 确认配置文件路径正确
2. ✅ 确认YAML格式正确（使用空格缩进，不要用Tab）
3. ✅ 手动测试YAML:
   ```bash
   python3 -c "import yaml; print(yaml.safe_load(open('config.yaml')))"
   ```

### 获取帮助

如果以上都无法解决问题：

1. 查看详细日志，添加 `-v` 参数（如果有）
2. 检查飞书开放平台的事件日志
3. 提交Issue到项目仓库

---

## 最佳实践

### 1. 项目命名规范

使用简短、有意义的项目名：
- ✅ `sailzen`, `myapp`, `backend-api`
- ❌ `My Project 2024`, `project-with-long-name-and-spaces`

### 2. 端口规划

为每个项目分配不同端口：
- 项目1: 4096
- 项目2: 4097
- 项目3: 4098

### 3. 安全建议

1. **保护凭证**: 不要将 `.env` 文件提交到Git
   ```bash
   echo ".env" >> .gitignore
   ```

2. **权限最小化**: 飞书应用只申请必要的权限

3. **访问控制**: 只在可信群组中添加机器人

### 4. 定期备份配置

```bash
# 备份配置文件
cp ~/.config/opencode-agent/config.yaml ~/.config/opencode-agent/config.yaml.backup
```

---

## 下一步

- [ ] 尝试添加你的第一个项目
- [ ] 测试OpenCode启动和停止
- [ ] 尝试代码生成工作流
- [ ] 探索自然语言交互
- [ ] 配置开机自启

遇到问题？查看 [故障排查](#故障排查) 或提交Issue！
