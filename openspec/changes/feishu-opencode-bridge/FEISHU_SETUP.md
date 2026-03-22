# Feishu-OpenCode Bridge 配置指南

## 快速开始

### 1. 启动本地Agent

```bash
# 在项目根目录运行
python scripts/opencode_agent.py --project D:/ws/repos/SailZen
```

Agent启动后，你可以输入以下命令：
- `start` - 启动OpenCode
- `stop` - 停止OpenCode  
- `status` - 查看状态
- `commit` - 执行git commit
- `push` - 执行git push
- `quit` - 退出

### 2. 配置环境变量

创建 `.env.feishu` 文件：

```env
# 飞书Bot配置（待配置）
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxx
FEISHU_VERIFICATION_TOKEN=xxxxxxxx
FEISHU_ENCRYPT_KEY=xxxxxxxx

# OpenCode默认项目路径
OPENCODE_DEFAULT_PROJECT=D:/ws/repos/SailZen
OPENCODE_PORT=4096
```

### 3. 启动后端服务

```bash
# 安装依赖
uv sync

# 启动服务器
uv run server.py --dev
```

## 飞书Bot配置步骤

### 1. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 启用 "机器人" 能力
4. 记录 App ID 和 App Secret

### 2. 配置权限

在 "权限管理" 中添加以下权限：
- `im:message.group_at_msg:readonly` - 接收群聊@消息
- `im:message.p2p_msg:readonly` - 接收私聊消息  
- `im:message:send` - 发送消息

### 3. 配置事件订阅

在 "事件订阅" 中：
1. 开启事件订阅
2. 设置请求地址: `https://your-server.com/api/v1/feishu/webhook`
3. 订阅事件: `im.message.receive_v1`
4. 记录 Verification Token 和 Encrypt Key

### 4. 发布应用

1. 进入 "版本管理与发布"
2. 创建版本并发布
3. 管理员审批通过后，将Bot添加到群组

## 使用示例

### 在飞书中使用

```
@机器人 /start-opencode
```

回复示例：
```
📂 项目路径: D:/ws/repos/SailZen
🚀 请在本地运行以下命令启动OpenCode:
```
cd D:/ws/repos/SailZen && opencode web --hostname 0.0.0.0
```
```

### Git操作

```
@机器人 /git-status
@机器人 /git-commit "修复登录bug"
@机器人 /git-push
```

## 架构说明

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   飞书APP    │────▶│  SailServer │────▶│  本地Agent  │
│             │     │  (Webhook)  │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                                                ▼
                                         ┌─────────────┐
                                         │   OpenCode  │
                                         │   Server    │
                                         └─────────────┘
```

## 注意事项

1. **当前为MVP版本**，仅支持单机模式
2. 飞书Webhook配置需要公网HTTPS地址
3. 本地Agent需要手动启动
4. OpenCode需要在本地机器上安装

## TODO

- [ ] 实现WebSocket连接云端
- [ ] 实现期望状态自动同步
- [ ] 实现飞书消息自动回复
- [ ] 添加交互式卡片支持
