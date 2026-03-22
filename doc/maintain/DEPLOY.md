# Deployment Guide - SailZen with Feishu Bot

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

#### 2.2 添加Feishu Bot配置（在.env.prod末尾追加）
```bash
cat >> .env.prod << 'EOF'

# =============================================================================
# Feishu Bot 配置 (MVP版本)
# =============================================================================

# 飞书应用凭证（从飞书开放平台获取）
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_VERIFICATION_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_ENCRYPT_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# OpenCode默认项目路径（用于MVP版本）
OPENCODE_DEFAULT_PROJECT=D:/ws/repos/SailZen
OPENCODE_PORT=4096

# Feishu功能开关
ENABLE_FEISHU_BOT=true
EOF
```

#### 2.3 关键配置说明

| 变量 | 获取位置 | 说明 |
|------|---------|------|
| `FEISHU_APP_ID` | 飞书开放平台 > 应用详情 | 应用唯一标识 |
| `FEISHU_APP_SECRET` | 飞书开放平台 > 应用详情 > 凭证 | 应用密钥 |
| `FEISHU_VERIFICATION_TOKEN` | 飞书开放平台 > 事件订阅 | 验证Token |
| `FEISHU_ENCRYPT_KEY` | 飞书开放平台 > 事件订阅 > 加密策略 | 消息加密密钥 |

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

#### 3.4 配置事件订阅
1. 左侧菜单 > **事件与回调** > **事件订阅**
2. 开启 **启用事件订阅**
3. 配置 **请求地址**：
   ```
   https://your-domain.com/api/v1/feishu/webhook
   ```
   ⚠️ **重要**: 必须是HTTPS，且域名需备案
4. 添加订阅事件：
   - `im.message.receive_v1` - 接收消息
5. 记录 **Verification Token** 和 **Encrypt Key**

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

# 如需WebSocket（后续版本）
sudo ufw allow 8080/tcp
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
        
        # 增加超时时间（飞书Webhook可能需要）
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

### 6. 本地Agent配置（开发机）

#### 6.1 在本地开发机配置
```bash
# 在本地开发机（Windows/Mac）上
# 创建配置文件
mkdir -p ~/.config/opencode-agent
cat > ~/.config/opencode-agent/config.yaml << 'EOF'
cloud_url: wss://your-domain.com/ws
pin: "123456"  # 与服务端配置的PIN一致
project_path: "D:/ws/repos/SailZen"  # Windows路径示例
opencode_port: 4096
heartbeat_interval: 5
EOF
```

#### 6.2 启动本地Agent
```bash
# Windows
python D:/ws/repos/SailZen/scripts/opencode_agent.py

# 或Mac/Linux
python3 ~/repos/SailZen/scripts/opencode_agent.py
```

⚠️ **注意**: MVP版本需要手动启动Agent，后续版本将实现自动启动

### 7. 测试验证

#### 7.1 测试后端服务
```bash
# 测试健康检查
curl https://your-domain.com/api/v1/health

# 测试Feishu Webhook（本地测试）
curl -X POST http://localhost:1974/api/v1/feishu/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "schema": "2.0",
    "header": {
      "event_id": "test-001",
      "event_type": "im.message.receive_v1",
      "app_id": "cli_test"
    },
    "event": {
      "sender": {"sender_id": {"open_id": "ou_test"}, "sender_type": "user"},
      "message": {
        "message_id": "om_test",
        "chat_type": "p2p",
        "message_type": "text",
        "content": "{\"text\": \"/status\"}"
      }
    }
  }'
```

#### 7.2 在飞书中测试
1. 打开飞书，找到配置了机器人的群组
2. @机器人并发送指令：
   ```
   @机器人 /status
   ```
3. 查看服务器日志确认收到消息

### 8. 故障排查

#### 8.1 Webhook接收不到
- 检查Nginx日志: `sudo tail -f /var/log/nginx/error.log`
- 检查服务日志: `sudo journalctl -u sailzen -f`
- 确认URL可公网访问: `curl -I https://your-domain.com/api/v1/feishu/webhook`
- 检查飞书开放平台的事件订阅配置

#### 8.2 服务启动失败
- 检查环境变量: `cat /home/ubuntu/repos/SailZen/.env.prod`
- 手动测试启动: `cd ~/repos/SailZen && uv run server.py`
- 检查端口占用: `sudo lsof -i :1974`

#### 8.3 飞书Bot无响应
- 检查应用是否已发布并审批通过
- 检查机器人是否已添加到群组
- 检查权限配置是否完整

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

- [Feishu Bot配置详细指南](../changes/feishu-opencode-bridge/FEISHU_SETUP.md)
- [MVP版本使用说明](../changes/feishu-opencode-bridge/MVP_README.md)
- [飞书开放平台文档](https://open.feishu.cn/document/)
