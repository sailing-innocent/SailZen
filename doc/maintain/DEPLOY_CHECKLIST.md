# Feishu Bot 服务器部署检查清单

## 部署前准备

### 1. 飞书开放平台配置
- [ ] 创建企业自建应用
- [ ] 启用机器人能力
- [ ] 记录 **App ID** 
- [ ] 记录 **App Secret**
- [ ] 添加权限:
  - [ ] `im:message.group_at_msg:readonly`
  - [ ] `im:message.p2p_msg:readonly`
  - [ ] `im:message:send`
- [ ] 启用事件订阅
- [ ] 配置请求地址: `https://your-domain.com/api/v1/feishu/webhook`
- [ ] 订阅事件: `im.message.receive_v1`
- [ ] 记录 **Verification Token**
- [ ] 记录 **Encrypt Key**
- [ ] 创建版本并申请发布
- [ ] 管理员审批通过

### 2. 域名和SSL
- [ ] 拥有已备案的域名
- [ ] 域名指向服务器IP
- [ ] 配置SSL证书（Let's Encrypt或自签名）

### 3. 服务器准备
- [ ] Ubuntu服务器（推荐20.04+）
- [ ] 已配置SSH密钥登录
- [ ] 防火墙开放80/443端口

---

## 服务器部署步骤

### 步骤1: 登录服务器并更新代码
```bash
ssh ubuntu@your-domain.com
cd ~/repos/SailZen
git pull origin main
```
**状态**: [ ] 未完成 / [x] 完成

---

### 步骤2: 安装依赖
```bash
uv sync
pnpm install
```
**状态**: [ ] 未完成 / [x] 完成

---

### 步骤3: 配置环境变量
```bash
cp .env.template .env.prod
nano .env.prod
```

需要添加的配置项:
```bash
# Feishu Bot
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxx
FEISHU_VERIFICATION_TOKEN=xxxxxxxx
FEISHU_ENCRYPT_KEY=xxxxxxxx

# OpenCode
OPENCODE_DEFAULT_PROJECT=/home/ubuntu/repos/SailZen
OPENCODE_PORT=4096

# 功能开关
ENABLE_FEISHU_BOT=true
```
**状态**: [ ] 未完成 / [x] 完成

---

### 步骤4: 构建前端
```bash
pnpm build-site
```
**状态**: [ ] 未完成 / [x] 完成

---

### 步骤5: 配置Nginx
```bash
sudo nano /etc/nginx/sites-available/sailzen
# 编辑配置文件（参考DEPLOY.md中的配置）

sudo ln -s /etc/nginx/sites-available/sailzen /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```
**状态**: [ ] 未完成 / [x] 完成

---

### 步骤6: 配置SSL证书（Let's Encrypt）
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```
**状态**: [ ] 未完成 / [x] 完成

---

### 步骤7: 配置Systemd服务
```bash
sudo nano /etc/systemd/system/sailzen.service
# 编辑服务文件（参考DEPLOY.md中的配置）

sudo systemctl daemon-reload
sudo systemctl enable sailzen.service
sudo systemctl start sailzen.service
```
**状态**: [ ] 未完成 / [x] 完成

---

### 步骤8: 验证服务状态
```bash
sudo systemctl status sailzen.service
sudo journalctl -u sailzen.service -f
```

应该看到:
- [ ] 服务状态为 **active (running)**
- [ ] 日志中没有错误信息
- [ ] 显示 "Server running on 0.0.0.0:1974"
**状态**: [ ] 未完成 / [x] 完成

---

## 功能测试

### 测试1: 健康检查
```bash
curl https://your-domain.com/api/v1/health
```

期望响应:
```json
{"status": "ok"}
```
**状态**: [ ] 未测试 / [x] 通过 / [ ] 失败

---

### 测试2: Webhook端点
```bash
curl -X POST https://your-domain.com/api/v1/feishu/webhook \
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

期望响应:
```json
{"code": 0, "msg": "success"}
```
**状态**: [ ] 未测试 / [x] 通过 / [ ] 失败

---

### 测试3: 飞书Bot消息测试
在飞书中:
1. [ ] 将Bot添加到测试群组
2. [ ] @Bot 发送: `/status`
3. [ ] 查看服务器日志是否有请求记录

检查日志:
```bash
sudo journalctl -u sailzen.service -f
```

期望看到:
```
[Feishu Webhook] Received message from: ou_xxxxxx
[Feishu Response] Message ID: om_xxxxx
[Feishu Response] Content: {...}
```
**状态**: [ ] 未测试 / [x] 通过 / [ ] 失败

---

## 本地开发机配置（可选）

### 配置本地Agent
```bash
# 在Windows/Mac上编辑配置文件
mkdir -p ~/.config/opencode-agent
cat > ~/.config/opencode-agent/config.yaml << 'EOF'
cloud_url: wss://your-domain.com/ws
pin: "123456"
project_path: "D:/ws/repos/SailZen"
opencode_port: 4096
EOF
```

启动Agent:
```bash
python scripts/opencode_agent.py
```
**状态**: [ ] 未配置 / [x] 已配置 / [ ] 不需要

---

## 故障排查检查表

### 问题: Webhook接收不到消息
检查项:
- [ ] Nginx配置正确（location /api/）
- [ ] SSL证书有效
- [ ] 飞书事件订阅URL正确
- [ ] 服务器防火墙开放443端口
- [ ] 查看Nginx错误日志

### 问题: 服务启动失败
检查项:
- [ ] 环境变量配置完整
- [ ] .env.prod文件存在且格式正确
- [ ] uv依赖已安装（uv sync）
- [ ] 端口1974未被占用
- [ ] 查看systemd日志

### 问题: 飞书Bot无响应
检查项:
- [ ] 应用已发布并通过审批
- [ ] 机器人已添加到群组
- [ ] 权限配置完整
- [ ] 事件订阅已启用
- [ ] 检查飞书开放平台日志

---

## 部署完成确认

- [ ] 所有部署步骤已完成
- [ ] 所有测试已通过
- [ ] 飞书Bot可以正常接收消息
- [ ] 系统日志无错误
- [ ] 已配置监控（可选）

**部署日期**: _________
**部署人员**: _________
**备注**: _________

---

## 维护命令速查

```bash
# 更新代码
cd ~/repos/SailZen && git pull

# 重启服务
sudo systemctl restart sailzen.service

# 查看状态
sudo systemctl status sailzen.service

# 查看日志
sudo journalctl -u sailzen.service -f

# 查看Nginx日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```
