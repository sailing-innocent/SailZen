# Deployment Guide - SailZen with Feishu Bot (Edge Runtime)

> **架构说明**: 当前版本使用 **Edge Runtime 架构**，飞书 Bot 作为本地代理运行，通过长连接接收消息，无需服务器端 Webhook 配置。

## 架构概览

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
                           │ HTTPS/WebSocket (可选)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   HOME-HOST EDGE PLANE                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Feishu Bot   │  │   Desktop    │  │  OpenCode    │          │
│  │   (Lark WS)  │  │    Agent     │  │  Sessions    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  • 本地飞书事件接收（长连接）                                  │
│  • OpenCode 进程生命周期管理                                   │
│  • 心跳和状态同步                                              │
│  • 命令执行                                                    │
└─────────────────────────────────────────────────────────────────┘
```

## 快速部署（已配置环境）

```bash
ssh ubuntu@your-server
cd ~/repos/SailZen
git pull
pnpm build-site
sudo systemctl restart sailzen.service
```

---

## 首次部署配置清单

### 1. 服务器基础配置

#### 1.1 登录服务器
```bash
ssh ubuntu@your-server-ip
```

基础更新
- `sudo apt-get update`
- `sudo apt-get upgrade`

#### 1.2 更新代码
```bash
cd ~/repos/SailZen
git pull origin master
```

#### 1.3 安装依赖
```bash
# 安装/更新Python依赖
uv sync

# 安装/更新前端依赖
pnpm install
```

### 2. 环境变量配置

#### 2.1 创建生产环境配置
```bash
cp .env.template .env.prod
nano .env.prod
```

#### 2.2 配置数据库和其他服务
```bash
# 编辑 .env.prod，配置以下关键项：
# - POSTGRE_URI: PostgreSQL 连接字符串
# - LOG_MODE: 日志模式 (prod/dev/debug)
# - 其他服务配置...
```

**注意**: Feishu Bot 配置已移至本地配置文件，不再需要服务器端环境变量。

### 3. 飞书开放平台配置

#### 3.1 创建应用
1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 登录企业账号
3. 创建企业自建应用
4. 记录 **App ID** 和 **App Secret**

#### 3.2 启用机器人能力
1. 左侧菜单 > **应用能力** > **机器人**
2. 点击 **启用机器人**
3. 配置机器人名称和头像

#### 3.3 配置权限
1. 左侧菜单 > **权限管理**
2. 添加以下权限：
   - `im:message.group_at_msg:readonly` - 接收群聊@消息
   - `im:message.p2p_msg:readonly` - 接收私聊消息
   - `im:message:send` - 发送消息

#### 3.4 配置事件订阅（长连接模式）
1. 左侧菜单 > **事件与回调** > **事件订阅**
2. 开启 **启用事件订阅**
3. 选择 **长连接** 模式（不需要配置请求地址）
   - ⚠️ **重要**: 新版架构使用长连接模式，不需要 HTTPS 域名
4. 添加订阅事件：
   - `im.message.receive_v1` - 接收消息

#### 3.5 发布应用
1. 左侧菜单 > **版本管理与发布**
2. 点击 **创建版本**
3. 填写版本号和更新说明
4. 点击 **申请发布**
5. 联系企业管理员审批

#### 3.6 添加机器人到群组
1. 在飞书群组中，点击 **设置** > **群机器人** > **添加机器人**
2. 选择你创建的应用
3. 机器人加入群组后即可使用

### 4. 服务器网络配置

#### 4.1 开放端口（如需防火墙）
```bash
# 检查防火墙状态
sudo ufw status

# 开放HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 开放SailServer端口（根据你的配置）
sudo ufw allow 1974/tcp
```

#### 4.2 Nginx反向代理配置（HTTPS）

创建Nginx配置文件：
```bash
sudo nano /etc/nginx/sites-available/sailzen
```

添加配置：
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # 重定向到HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL证书（使用certbot或自签名）
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # 前端静态文件
    location / {
        root /home/ubuntu/repos/SailZen/site_dist;
        try_files $uri $uri/ /index.html;
    }

    # API反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:1974;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # 增加超时时间
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/sailzen /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 4.3 申请SSL证书（Let's Encrypt）
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 5. Systemd服务配置

#### 5.1 创建服务文件
```bash
sudo nano /etc/systemd/system/sailzen.service
```

添加内容：
```ini
[Unit]
Description=SailZen Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/repos/SailZen

# 加载环境变量
Environment="PATH=/home/ubuntu/.cargo/bin:/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"

# 先加载环境变量文件
ExecStartPre=/bin/bash -c 'export $(cat /home/ubuntu/repos/SailZen/.env.prod | xargs)'

# 启动命令
ExecStart=/home/ubuntu/.local/bin/uv run server.py

# 重启策略
Restart=always
RestartSec=5

# 日志
StandardOutput=append:/home/ubuntu/logs/sailzen.log
StandardError=append:/home/ubuntu/logs/sailzen.log

[Install]
WantedBy=multi-user.target
```

#### 5.2 启用并启动服务
```bash
# 重载systemd
sudo systemctl daemon-reload

# 启用开机自启
sudo systemctl enable sailzen.service

# 启动服务
sudo systemctl start sailzen.service

# 查看状态
sudo systemctl status sailzen.service
```

#### 5.3 查看日志
```bash
# 实时日志
sudo journalctl -u sailzen.service -f

# 或查看文件日志
tail -f ~/logs/sailzen.log
```

### 6. 本地 Feishu Agent 配置（开发机）

#### 6.1 复制配置文件模板
```bash
cd ~/repos/SailZen
cp bot/opencode.bot.yaml bot/myconfig.bot.yaml
```

#### 6.2 编辑配置文件
```bash
nano bot/myconfig.bot.yaml
```

填写以下配置：
```yaml
# REQUIRED: Feishu App Credentials
app_id: "cli_xxxxxxxxxxxxxxxx"
app_secret: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# OPTIONAL: Control Plane Settings (如需服务器集成)
# control_plane_url: "https://your-server.com/api/v1/remote-dev/control-plane"
# edge_node_key: "home-macbook-pro"
# heartbeat_interval_seconds: 15

# OPTIONAL: Session Settings
base_port: 4096
max_sessions: 10
callback_timeout: 300
auto_restart: false

# OPTIONAL: Project Inventory
projects:
  - slug: "sailzen"
    path: "/home/ubuntu/repos/SailZen"  # Linux/Mac 路径
    label: "SailZen"
  # - slug: "myproject"
  #   path: "D:/projects/myproject"     # Windows 路径示例
  #   label: "My Project"
```

#### 6.3 启动本地 Agent
```bash
# 使用 uv 运行（推荐）
uv run bot/feishu_agent.py -c bot/myconfig.bot.yaml

# 或使用 Python 直接运行
python bot/feishu_agent.py -c bot/myconfig.bot.yaml
```

#### 6.4 后台运行（Linux/Mac）
```bash
# 使用 nohup
nohup uv run bot/feishu_agent.py -c bot/myconfig.bot.yaml > logs/feishu_agent.log 2>&1 &

# 或使用 systemd（推荐用于长期运行）
```

### 7. 测试验证

#### 7.1 测试后端服务
```bash
# 测试健康检查
curl https://your-domain.com/api/v1/health
```

#### 7.2 在飞书中测试
1. 打开飞书，找到配置了机器人的群组
2. @机器人并发送自然语言指令：
   ```
   @机器人 查看状态
   @机器人 启动 ~/projects/myapp
   @机器人 帮我写代码 ~/projects/myapp 实现用户登录
   ```
   
   **注意**：系统使用 **自然语言** 而非 slash 命令（如 `/status`），因为手机上输入 `/` 需要切换键盘，体验不佳。
3. 查看本地 Agent 日志确认收到消息

### 8. 故障排查

#### 8.1 Agent 无法连接飞书
- 检查 `app_id` 和 `app_secret` 是否正确
- 确认应用已发布并通过审批
- 检查网络连接：`curl https://open.feishu.cn`
- 查看 Agent 日志：`tail -f logs/feishu_agent.log`

#### 8.2 服务启动失败
- 检查环境变量: `cat /home/ubuntu/repos/SailZen/.env.prod`
- 手动测试启动: `cd ~/repos/SailZen && uv run server.py`
- 检查端口占用: `sudo lsof -i :1974`

#### 8.3 飞书Bot无响应
- 检查应用是否已发布并审批通过
- 检查机器人是否已添加到群组
- 检查权限配置是否完整
- 确认事件订阅模式为 **长连接** 而非 **请求地址模式**

#### 8.4 FeishuWebhookHandler 启动错误
**错误信息**: `TypeError: FeishuWebhookHandler.__init__() got an unexpected keyword argument 'owner'`

**原因**: Litestar 框架在注册 Controller 时会自动传递 `owner` 参数，但自定义的 `__init__` 方法未正确处理。

**解决方案**: 确保 `FeishuWebhookHandler.__init__()` 方法接受 `owner` 参数并调用父类的 `__init__`：

```python
def __init__(self, owner: Router | None = None) -> None:
    super().__init__(owner=owner)
    # 你的初始化代码...
```

**注意**: 从 2026-03-22 版本开始，此问题已修复。如果遇到此问题，请更新代码：
```bash
cd ~/repos/SailZen && git pull
sudo systemctl restart sailzen.service
```

---

## 维护命令

```bash
# 更新代码
cd ~/repos/SailZen && git pull

# 重新构建前端
pnpm build-site

# 重启服务
sudo systemctl restart sailzen.service

# 查看状态
sudo systemctl status sailzen.service

# 查看日志
sudo journalctl -u sailzen.service -f -n 100
```

---

## 相关文档

- [Feishu Bot 详细使用指南](../../FEISHU_BOT_README.md)
- [飞书开放平台文档](https://open.feishu.cn/document/)

---

## 版本历史

### 2026-03-22 - Edge Runtime 架构
- 迁移到 Edge Runtime 架构
- 飞书 Bot 改为本地长连接模式
- 移除服务器端 Webhook 依赖
- 新增 Control Plane 集成（可选）

### 2026-03-21 - MVP 版本
- 初始版本
- 服务器端 Webhook 接收飞书消息
- 需要 HTTPS 域名和备案
