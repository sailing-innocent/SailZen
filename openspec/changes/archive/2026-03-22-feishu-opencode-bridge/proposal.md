# Proposal: Feishu-OpenCode Bridge

## Why

当前移动端操控OpenCode进行AI开发存在严重体验问题：远程控制软件输入兼容性差，无法有效转译AI的复杂需求。通过飞书Bot作为统一入口，用户可以随时随地通过手机/电脑端飞书发送指令，由云端服务桥接到本地OpenCode执行，实现"口袋里的AI开发助手"。

## What Changes

**新增系统组件：**
- **Feishu Bot本地Agent** (`scripts/feishu_agent.py`): 使用飞书SDK长连接模式，直接接收消息并管理OpenCode
- **OpenCode管理器**: 封装OpenCode进程生命周期管理（启动/停止/健康检查）
- **Git自动化模块**: 封装常见git操作（pull/commit/push）为可执行指令

**架构简化（长连接模式）：**
- ❌ **移除云服务器依赖**: 无需HTTPS域名和备案
- ❌ **移除Webhook接收**: 使用SDK长连接替代HTTP回调
- ❌ **移除Redis存储**: 配置存储在本地环境变量
- ✅ **简化部署**: 仅需本地运行一个Python脚本

**MVP范围限定：**
- 仅支持单Agent单会话模式
- 使用飞书SDK长连接（无需域名备案）
- 支持基础git操作（拉取、提交、推送）
- 支持OpenCode启动/停止控制

## Capabilities

### New Capabilities
- `feishu-long-connection-agent`: 使用飞书SDK长连接模式接收消息，无需域名备案
- `opencode-process-manager`: OpenCode进程生命周期管理（启动、停止、健康检查）
- `git-automation`: 封装git操作流程，提供安全的代码提交能力
- `message-command-parser`: 飞书消息指令解析器，支持结构化指令和自然语言

### Modified Capabilities
- *无现有spec需要修改*

## Impact

**新增文件:**
- `scripts/feishu_agent.py` - 飞书Bot本地Agent（长连接模式）
- `doc/maintain/FEISHU_LONG_CONNECTION.md` - 长连接模式部署指南
- `doc/maintain/DEPLOY_CHECKLIST.md` - 部署检查清单

**依赖:**
- `lark-oapi` - 飞书Python SDK（长连接模式必需）

**部署（极大简化）:**
- ✅ **无需云服务器** - 本地直接运行Agent
- ✅ **无需域名备案** - 使用SDK长连接
- ✅ **无需Nginx** - 无HTTP服务
- ✅ **无需Redis** - 配置存储在环境变量
- 仅需: 本地运行 `python scripts/feishu_agent.py`

**架构变更:**
```
原架构: 飞书 → 云服务器(Webhook) → 本地Agent → OpenCode
          （需要域名备案、云服务器）

新架构: 飞书 ←──SDK长连接── 本地Agent → OpenCode
          （仅需能访问互联网）
```

**安全考虑:**
- SDK自动处理认证和签名验证
- 消息内容在SDK层自动解密
- 项目路径本地验证（防路径遍历）
- 代码提交需用户显式确认
