## Context

SailZen项目已有成熟的前后端架构：
- **前端**: `packages/site` 基于React + Vite，使用pnpm管理
- **后端**: `sail_server/` 基于Python + Litestar + SQLAlchemy，使用uv管理

当前痛点：用户需要通过远程桌面软件操控OpenCode，移动端输入体验差，无法有效利用碎片时间进行AI开发。

**已有基础设施：**
- 稳定的云服务器，支持HTTPS和WebSocket
- 本地开发机运行OpenCode (`opencode web --hostname 0.0.0.0`)
- 飞书企业账号，可创建自定义Bot

**约束条件：**
- MVP限定单Agent单会话，避免过早复杂化
- 认证采用简单6位PIN码，而非复杂的双向TLS
- 必须复用现有SailZen架构，保持一致的技术栈

## Goals / Non-Goals

**Goals:**
- 实现飞书Bot作为OpenCode的统一入口
- 支持基础git操作（pull/commit/push）通过飞书指令触发
- 支持简单的代码生成和文件修改
- 实现本地代理与云端的可靠连接
- 提供基础配置界面管理项目路径和PIN码

**Non-Goals:**
- 多Agent并行执行（后续版本考虑）
- 复杂的多会话管理
- 代码diff预览和冲突解决UI
- 自动代码审查或测试执行
- 与其他IM平台（钉钉、企业微信）的集成

## Decisions

### Decision 1: 连接方式 - 飞书SDK长连接模式（无需域名备案）
**选择**: 本地Agent使用飞书Python SDK（`lark-oapi`）建立WebSocket长连接

**架构对比**:

传统Webhook模式（需要备案域名）:
```
飞书平台 ──► 你的服务器（HTTPS域名）──► 本地Agent
```

长连接模式（无需域名）:
```
飞书平台 ◄──WebSocket──► 本地Agent（直接使用lark-oapi SDK）
```

**优势**:
- ✅ **无需域名和备案** - Agent主动连接飞书服务器
- ✅ **无需公网IP** - 只要能访问互联网即可
- ✅ **自动认证** - SDK封装了token管理和签名验证
- ✅ **本地开发友好** - 直接在内网环境运行
- ✅ **自动重连** - SDK内置断线重连机制
- ✅ **简化架构** - 去掉云服务器中间层

**适用条件**:
- 仅支持企业自建应用
- 需要订阅的事件：im.message.receive_v1
- 开发周期从1周缩短到5分钟

### Decision 2: 协议栈 - WebSocket + HTTP Fallback
**选择**: WebSocket为主，SSE作为OpenCode通信备用

**理由**:
- WebSocket支持双向实时通信，适合状态同步
- OpenCode原生支持SSE事件流，无需额外适配
- HTTP API作为OpenCode的基础调用方式

**架构层次**:
```
飞书Bot ──► 云端Gateway (HTTP Webhook)
               │
               ▼
          WebSocket Server
               │
               ▼
         本地Agent ──► OpenCode (HTTP + SSE)
```

### Decision 3: 会话存储 - Redis + 内存缓存
**选择**: Redis存储会话状态，本地Agent内存缓存热数据

**理由**:
- 支持多设备切换（手机飞书切到电脑飞书）
- 云端崩溃后任务不丢失
- 本地缓存减少Redis查询延迟

**数据结构**:
- `feishu:user:{open_id}:profile` - 用户配置（项目路径、PIN码哈希）
- `feishu:session:{session_id}` - 会话状态（active/completed/error）
- `feishu:task:{task_id}` - 任务详情和结果
- `feishu:user:{open_id}:desired_state` - **期望状态**（opencode_running: true/false, project_path）

**期望状态模式**:
```
云端存储"期望状态" ←→ 本地Agent监控并修复偏差

示例：
1. 用户通过手机发送: "/start-opencode"
2. 云端更新 desired_state: {opencode_running: true, project_path: "/work/project"}
3. 本地Agent检测到实际状态 ≠ 期望状态
4. Agent执行: cd /work/project && opencode web --hostname 0.0.0.0
5. Agent报告状态同步完成
```

### Decision 4: 指令解析 - 前缀 + 自然语言混合
**选择**: 支持结构化指令（/git-pull）和自然语言（"拉取最新代码"）

**指令分类**:
| 类型 | 示例 | 处理方式 |
|------|------|----------|
| Git操作 | `/git-pull`, `/git-push "commit msg"` | 直接映射到git命令 |
| 代码生成 | `/code "实现登录功能"` | 转发到OpenCode session |
| 查询 | `/status`, `/projects` | 本地Agent直接响应 |
| 自然语言 | "帮我修复这个bug" | NLP意图识别后路由 |

### Decision 5: 安全模型 - PIN码 + Webhook签名验证
**选择**: 
- 本地Agent连接云端需6位PIN码
- 飞书Webhook验证signature和timestamp防重放

**理由**:
- PIN码简单易记，适合个人使用场景
- 飞书内置的signature验证足够防御常见攻击
- 代码提交等敏感操作通过飞书交互卡片二次确认

**PIN码存储**:
- 云端存储SHA256哈希（salt=用户open_id）
- 本地Agent首次连接时验证，成功后发放JWT token（24h有效）

### Decision 6: 远程进程管理 - 期望状态模式（Self-Healing）
**选择**: 采用"期望状态"（Desired State）模式，云端存储期望配置，本地Agent自动修复偏差

**架构**:
```
┌─────────────────────────────────────────────────────────────┐
│                        手机端飞书                            │
│  用户发送: "/start-opencode /work/myproject"                  │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      云服务器                                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  期望状态存储 (Redis)                                     ││
│  │  feishu:user:{id}:desired_state                         ││
│  │  {                                                      ││
│  │    "opencode_running": true,                           ││
│  │    "project_path": "/work/myproject",                  ││
│  │    "port": 4096,                                       ││
│  │    "updated_at": "2026-03-21T10:30:00Z"               ││
│  │  }                                                      ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────┬───────────────────────────────────┘
                          │ WebSocket 广播 "desired_state_changed"
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     本地开发机                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Agent状态协调器 (每5秒检查)                              ││
│  │  1. 读取云端期望状态                                      ││
│  │  2. 检查本地OpenCode实际状态                              ││
│  │  3. 如果偏差 → 执行修复操作                               ││
│  │                                                         ││
│  │  实际状态: stopped                                      ││
│  │  期望状态: running                                      ││
│  │  → 执行: opencode web --hostname 0.0.0.0               ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**远程控制指令**:
| 指令 | 功能 | 示例 |
|------|------|------|
| `/start-opencode [path]` | 在指定路径启动OpenCode | `/start-opencode /work/myproject` |
| `/restart-opencode` | 重启当前OpenCode进程 | `/restart-opencode` |
| `/stop-opencode` | 停止OpenCode进程 | `/stop-opencode` |
| `/status` | 查看OpenCode和Agent状态 | `/status` |
| `/switch-project <path>` | 切换到新项目路径 | `/switch-project /work/newproject` |

**自愈机制**:
- Agent每5秒检查一次"期望状态" vs "实际状态"
- 发现偏差时自动执行修复（无需人工干预）
- 修复失败3次后标记为"error"并通过飞书通知用户
- 支持用户通过手机覆盖期望状态（手动控制）

**理由**:
- ✅ 用户可在手机端随时拉起/停止OpenCode
- ✅ 进程崩溃后自动恢复（Agent持续运行）
- ✅ 云端作为"单一真相源"，多设备状态一致
- ✅ 符合k8s的声明式配置理念，易于理解和扩展

**安全考虑**:
- 项目路径必须经过Agent本地验证（防止路径遍历攻击）
- 启动OpenCode前检查目录存在性和git仓库有效性
- 敏感操作（stop/restart）需通过飞书卡片二次确认

## Risks / Trade-offs

| Risk | 影响 | Mitigation |
|------|------|------------|
| 本地Agent断线 | 高 | 心跳检测5s间隔，3次失败标记离线；任务队列云端持久化，重连后恢复 |
| 飞书Webhook超时 | 中 | 立即返回200，异步处理；长任务通过消息卡片持续更新进度 |
| OpenCode执行失败 | 中 | 错误信息捕获并通过飞书反馈；支持`/revert`指令回滚 |
| PIN码泄露 | 低 | 6位PIN仅用于初始连接，实际通信使用JWT；支持PIN码重置 |
| 多设备冲突 | 中 | 单会话设计天然避免冲突；状态变更通过Redis原子操作 |

### Trade-off: 简单PIN码 vs 复杂认证
**选择**: 6位PIN码
- ✅ 用户体验好，无需管理证书
- ✅ 个人使用场景风险可控
- ❌ 不适合团队协作或多用户场景

**未来可升级**: OAuth2 + 短期token

## Migration Plan

**阶段1: 后端Gateway（Week 1）**
1. 添加 `lark-oapi` 依赖
2. 实现 `/feishu/webhook` 端点
3. 部署到云服务器，配置飞书Webhook URL
4. 验证消息接收和响应

**阶段2: 本地Agent（Week 2）**
1. 创建 `scripts/opencode_agent.py`
2. 实现WebSocket客户端和OpenCode HTTP封装
3. 本地测试：飞书 → 云端 → 本地Agent → OpenCode

**阶段3: 前端配置（Week 3）**
1. 新增飞书Bot配置页面
2. 项目路径管理和PIN码设置
3. 状态监控页面（连接状态、活跃会话）

**阶段4: Git自动化（Week 4）**
1. 封装git操作流程
2. 集成到指令路由
3. 端到端测试完整工作流

**Rollback策略**:
- 云端：保留旧版本Docker镜像，5分钟内可回滚
- 本地Agent：进程级重启，无状态
- 数据库：Redis数据可清空重新生成

## Open Questions

1. **OpenCode Server认证**: OpenCode的HTTP Basic Auth如何处理？是否需要用户在SailZen中配置密码？
   - *决策*: 本地Agent和OpenCode在同一台机器，使用127.0.0.1无需认证；如需公网访问则配置密码
   
2. **消息长度限制**: 飞书消息有长度限制，长代码diff如何分页展示？
   - *决策*: 超过限制时使用飞书文档/云文档链接，或分页卡片
   
3. **文件上传**: 用户能否通过飞书发送文件给OpenCode（如上传图片、配置文件）？
   - *决策*: MVP不支持，后续版本考虑飞书文件下载到项目目录
   
4. **成本**: 飞书Bot有API调用频率限制，是否需要本地队列做速率控制？
   - *决策*: 本地Agent缓存消息，云端限制并发任务数（默认3个）
   
5. **移动端体验**: 飞书小程序是否需要？还是纯文本交互足够？
   - *决策*: MVP纯文本+卡片交互足够，小程序作为后续优化

6. **✅ 已解决**: 远程拉起OpenCode - 通过"期望状态"模式实现，Agent每5秒检查并自动修复偏差
