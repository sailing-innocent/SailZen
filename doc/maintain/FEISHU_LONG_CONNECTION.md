# Feishu Bot 长连接模式部署指南

## 优势

✅ **无需域名** - 直接使用IPv4访问互联网即可  
✅ **无需备案** - 不需要ICP备案  
✅ **无需云服务器** - 本地运行Agent即可  
✅ **无需Nginx** - 省去反向代理配置  
✅ **自动重连** - SDK内置断线重连机制  
✅ **本地开发友好** - 直接在内网环境运行

## 架构

```
┌─────────────┐         WebSocket长连接          ┌──────────────┐
│  飞书APP    │◄───────────────────────────────►│  本地Agent   │
│  (手机/电脑)│                                   │  (你的电脑)   │
└─────────────┘                                  └──────┬───────┘
                                                        │
                              ┌───────────────────────┘
                              │
                              ▼
                       ┌─────────────┐
                       │  OpenCode   │
                       │  Server     │
                       └─────────────┘
```

## 快速开始（5分钟）

### 1. 安装依赖

```bash
# 确保已安装Python 3.8+
python --version

# 安装飞书SDK
pip install lark-oapi

# 确保已安装OpenCode
opencode --version
```

### 2. 配置飞书应用

#### 2.1 创建应用
1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 登录企业账号 → 创建企业自建应用
3. 记录 **App ID** 和 **App Secret**

#### 2.2 启用机器人
1. 应用详情 → **应用能力** → **机器人** → 启用

#### 2.3 配置权限
权限管理 → 添加权限：
- `im:message.group_at_msg:readonly` - 接收群聊@消息
- `im:message.p2p_msg:readonly` - 接收私聊消息
- `im:message:send` - 发送消息

#### 2.4 配置事件订阅（关键步骤）

**⚠️ 重要：选择"长连接模式"**

1. 事件与回调 → 事件订阅
2. **订阅方式** → 选择 **"使用长连接接收事件"**
3. 添加事件：`im.message.receive_v1`
4. 保存配置

![长连接配置示意图]
```
传统模式: 飞书 → HTTPS你的服务器 → 本地
           (需要域名备案)

长连接模式: 飞书 ←──WebSocket── 本地Agent
            (无需域名)
```

#### 2.5 发布应用
1. 版本管理与发布 → 创建版本
2. 填写版本信息 → 申请发布
3. 联系管理员审批

#### 2.6 添加机器人到群组
在目标群组中 → 设置 → 群机器人 → 添加机器人 → 选择你的应用

### 3. 配置环境变量

```bash
# Linux/Mac
export FEISHU_APP_ID=cli_xxxxxxxx
export FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
export OPENCODE_PROJECT=/path/to/your/project

# Windows PowerShell
$env:FEISHU_APP_ID="cli_xxxxxxxx"
$env:FEISHU_APP_SECRET="xxxxxxxxxxxxxxxx"
$env:OPENCODE_PROJECT="D:\ws\repos\YourProject"
```

### 4. 启动Agent

```bash
# 进入项目目录
cd D:/ws/repos/SailZen

# 启动Agent
python scripts/feishu_agent.py --project D:/ws/repos/YourProject

# 或使用环境变量中的路径
python scripts/feishu_agent.py
```

你应该看到：
```
🚀 Feishu Bot Agent Starting...
   Project: D:/ws/repos/YourProject
   Port: 4096

✅ Agent configured successfully
🔗 Connecting to Feishu...
   (Press Ctrl+C to stop)

connected to wss://ws.feishu.cn/...
```

### 5. 在飞书中测试

打开飞书，在配置了机器人的群组中：

```
@机器人 /help
```

你应该立即收到回复：
```
🤖 Available Commands
━━━━━━━━━━━━━━
/start - Start OpenCode
/stop - Stop OpenCode
/status - Show system status
...
```

## 可用指令

| 指令 | 功能 | 示例 |
|------|------|------|
| `/start` | 启动OpenCode | `/start` |
| `/stop` | 停止OpenCode | `/stop` |
| `/status` | 查看状态 | `/status` |
| `/code <描述>` | 代码生成请求 | `/code 实现登录页面` |
| `/git-status` | Git状态 | `/git-status` |
| `/git-pull` | 拉取代码 | `/git-pull` |
| `/git-commit <msg>` | 提交代码 | `/git-commit "修复bug"` |
| `/git-push` | 推送代码 | `/git-push` |
| `/help` | 帮助 | `/help` |

## 高级配置

### 开机自启（Windows）

创建`start_feishu_agent.bat`：
```batch
@echo off
set FEISHU_APP_ID=cli_xxxxxxxx
set FEISHU_APP_SECRET=xxxxxxxx
set OPENCODE_PROJECT=D:\ws\repos\YourProject

python D:\ws\repos\SailZen\scripts\feishu_agent.py
```

添加到启动文件夹：
- Win+R → `shell:startup`
- 将bat文件复制进去

### 开机自启（Linux/Mac）

创建systemd服务：`~/.config/systemd/user/feishu-agent.service`
```ini
[Unit]
Description=Feishu Bot Agent
After=network.target

[Service]
Type=simple
Environment="FEISHU_APP_ID=cli_xxxxxxxx"
Environment="FEISHU_APP_SECRET=xxxxxxxx"
Environment="OPENCODE_PROJECT=/path/to/project"
ExecStart=/usr/bin/python3 /path/to/sailzen/scripts/feishu_agent.py
Restart=always

[Install]
WantedBy=default.target
```

启用：
```bash
systemctl --user daemon-reload
systemctl --user enable feishu-agent.service
systemctl --user start feishu-agent.service
```

### 多项目配置

创建多个启动脚本：
```bash
# project1.sh
export OPENCODE_PROJECT=/path/to/project1
export OPENCODE_PORT=4096
python scripts/feishu_agent.py

# project2.sh  
export OPENCODE_PROJECT=/path/to/project2
export OPENCODE_PORT=4097
python scripts/feishu_agent.py
```

## 故障排查

### Agent无法连接
```bash
# 检查网络
curl https://open.feishu.cn

# 检查凭证
echo $FEISHU_APP_ID
echo $FEISHU_APP_SECRET

# 检查应用状态（飞书开放平台）
# 确保应用已发布并通过审批
```

### 消息收不到
- 确认机器人已添加到群组
- 确认事件订阅选择了"长连接模式"
- 确认订阅了`im.message.receive_v1`事件
- 检查Agent日志是否有连接信息

### OpenCode无法启动
```bash
# 检查OpenCode是否安装
opencode --version

# 检查项目路径
ls $OPENCODE_PROJECT

# 手动测试启动
cd $OPENCODE_PROJECT
opencode web --hostname 127.0.0.1 --port 4096
```

## 与传统模式对比

| 特性 | 长连接模式（推荐） | 传统Webhook模式 |
|------|------------------|----------------|
| 域名 | ❌ 不需要 | ✅ 需要 |
| 备案 | ❌ 不需要 | ✅ 需要 |
| 云服务器 | ❌ 不需要 | ✅ 需要 |
| Nginx | ❌ 不需要 | ✅ 需要 |
| 配置复杂度 | ⭐ 简单 | ⭐⭐⭐⭐ 复杂 |
| 延迟 | ⭐⭐⭐ 低 | ⭐⭐⭐ 低 |
| 稳定性 | ⭐⭐⭐ 高 | ⭐⭐⭐ 高 |

## 限制说明

- 仅支持**企业自建应用**（不支持商店应用）
- 每个应用最多**50个长连接**
- 需要在**3秒内**响应消息（SDK已封装）
- 多客户端部署时，消息随机推送到其中一个

## 下一步

1. ✅ 当前已可用：OpenCode控制、Git操作
2. 🚧 开发中：OpenCode Session自动创建
3. 🚧 开发中：代码diff自动展示
4. 🚧 开发中：多Agent并行执行

---

**相关文档**:
- [飞书Python SDK文档](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/server-side-sdk/python--sdk/preparations-before-development)
- [长连接模式说明](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/server-side-sdk/python--sdk/handle-events)
- [SDK GitHub](https://github.com/larksuite/oapi-sdk-python)
