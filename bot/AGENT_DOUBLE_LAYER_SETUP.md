# OpenCode Agent 双层配置方案

## 概述

这是一个完整的解决方案，通过在 **OpenCode 侧** 和 **Controller 侧** 双层配置，实现对 Feishu Bot 的完美适配。

## 架构对比

### 之前：默认 Build Agent（冲突）

```
Feishu Bot → OpenCode (Build Agent) → 用户
                  ↓
            "确认要修改吗？" ← 阻塞等待
                  ↓
            打断飞书上下文
```

### 之后：Feishu Bridge Agent（自动）

```
Feishu Bot → Controller → @feishu-bridge → OpenCode
                              ↓
                     permissions: edit/allow
                              ↓
                     自动执行，不询问
                              ↓
                     Controller 监控进度 → 飞书
```

## 文件结构

```
SailZen/
├── .opencode/
│   ├── agents/
│   │   └── feishu-bridge.md      # 自定义 Agent 定义
│   └── opencode.json              # OpenCode 配置
│
└── bot/
    ├── agent_controller.py        # Controller（已更新）
    ├── feishu_agent_integration.py # 集成示例
    └── AGENT_CONTROLLER_README.md  # 设计文档
```

## 配置步骤

### Step 1: OpenCode 侧配置

已在项目中创建：

1. **`.opencode/agents/feishu-bridge.md`** - 自定义 Agent
   - mode: primary
   - permissions: edit/allow, bash/allow (除 git push)
   - 详细的 system prompt 指导不反问

2. **`.opencode/opencode.json`** - OpenCode 配置
   - 注册 feishu-bridge agent
   - 设置默认权限

### Step 2: 启动 OpenCode

在项目根目录启动 OpenCode：

```bash
# 确保配置生效
opencode serve --port 4096

# 或使用默认端口
opencode serve
```

### Step 3: 测试 Agent 切换

在 OpenCode TUI 中测试：

```
# 按 Tab 键切换 Agent，确认能看到 "feishu-bridge"

# 或者直接使用 @ 语法
@feishu-bridge 修复这个bug
```

### Step 4: Controller 侧使用

```python
from bot.agent_controller import AgentController, TaskType

controller = AgentController(port=4096)

# 执行任务
result = await controller.execute_task(
    task_text="修复登录bug",
    role_type=TaskType.QUICK_FIX
)
```

Controller 会自动：
1. 创建 session
2. 发送 `@feishu-bridge` 切换到自定义 Agent
3. 发送任务消息
4. 监控执行进度
5. 拦截并自动批准工具调用

## 双层控制机制

### Layer 1: OpenCode 配置（基础行为）

```yaml
# .opencode/agents/feishu-bridge.md

permission:
  edit: allow        # 基础：允许直接编辑
  bash:
    "*": allow       # 基础：允许命令
    "git push": ask  # 例外：push 需要确认
  webfetch: deny     # 基础：禁止网页
```

**作用**：定义 Agent 的默认行为模式

### Layer 2: Controller 控制（运行时微调）

```python
# agent_controller.py

class ToolInterceptor:
    DANGEROUS_PATTERNS = [
        r"rm\s+-rf\s+/",     # 运行时拦截危险命令
        r"sudo",              # 运行时拦截 sudo
    ]
    
    def intercept(self, tool, input):
        # 运行时额外检查
        if self._is_dangerous(input):
            return ToolDecision(action="reject")
```

**作用**：
- 运行时安全过滤
- 细粒度控制
- 实时进度监控
- 飞书状态同步

## 工作原理

### 1. Session 创建与 Agent 切换

```python
# 1. 创建 Session
POST /session
{"title": "feishu-task-xxx"}
→ 返回 session_id

# 2. 切换到 feishu-bridge agent
POST /session/:id/message
{"parts": [{"type": "text", "text": "@feishu-bridge"}]}

# 3. 发送任务
POST /session/:id/message
{"parts": [{"type": "text", "text": "修复登录bug"}]}
```

### 2. 权限控制流程

```
工具调用请求
    ↓
OpenCode 检查 permissions
    ↓ (edit: allow)
不询问用户，直接 pending
    ↓
Controller 拦截 pending
    ↓
ToolInterceptor 检查
    ↓ (安全检查通过)
自动批准
    ↓
OpenCode 执行工具
```

### 3. 反问消除机制

**OpenCode 层**：
```markdown
# feishu-bridge.md system prompt

核心原则：
1. 直接执行，绝不反问
2. 禁止说"确认吗"、"可以吗"
3. 有选择时自动决策
```

**Controller 层**：
```python
# 如果 OpenCode 还是问了（意外情况）
if "确认" in response or "可以吗" in response:
    # 自动回复"是"并继续
    await send_message("是的，请继续")
```

## 特性对比

| 特性 | 默认 Build Agent | Feishu Bridge Agent | 改进 |
|------|------------------|---------------------|------|
| **编辑文件** | ask | allow | ✅ 自动执行 |
| **运行命令** | ask | allow (除push) | ✅ 自动执行 |
| **反问确认** | 经常 | 绝不 | ✅ 无阻塞 |
| **浏览器跳转** | 允许 | deny | ✅ 更安全 |
| **进度反馈** | 完成后 | 实时推送 | ✅ 更及时 |
| **角色切换** | 手动 Tab | 自动 @ | ✅ 更智能 |

## 使用示例

### 示例 1：快速修复

**用户指令**：`修复登录bug`

**执行流程**：
1. Controller 识别为 QUICK_FIX 角色
2. 创建 session，切换 @feishu-bridge
3. 发送任务：修复登录bug
4. OpenCode 直接读取代码 → 定位问题 → 修改 → 不询问
5. Controller 实时推送进度到飞书
6. 完成后发送结果卡片

**输出**：
```
✅ 修复完成

📁 修改文件：
- login.py: 添加空指针检查（第45行）

📊 统计：
- 修改行数：+3/-1
- 工具调用：5次
- 耗时：12s
```

### 示例 2：代码重构

**用户指令**：`重构 auth 模块`

**执行流程**：
1. Controller 识别为 REFACTOR 角色
2. 发送重构专用 system prompt
3. OpenCode 一次性分析多个文件
4. 批量修改，不在每个文件后询问
5. 完成后总结改进点

**输出**：
```
✅ 重构完成

📁 修改文件：
- auth.py: 提取验证函数
- user.py: 简化登录流程  
- token.py: 优化过期检查

📊 改进：
- 消除重复代码 3 处
- 函数平均行数：45 → 28
- 圈复杂度降低 35%
```

## 故障排除

### Q: OpenCode 没有加载自定义 Agent

**检查**：
```bash
# 1. 确认文件位置
ls .opencode/agents/feishu-bridge.md

# 2. 确认配置文件
ls .opencode/opencode.json

# 3. 重启 OpenCode
opencode serve --port 4096

# 4. 在 TUI 中按 Tab 查看是否有 feishu-bridge
```

### Q: 工具调用还是需要确认

**检查**：
```python
# 1. 确认发送了 @feishu-bridge
# 在 agent_controller.py 中查看日志
print(f"[Agent Switch] {switch_message}")

# 2. 确认 permissions 配置正确
# 检查 .opencode/opencode.json
```

### Q: Controller 收不到进度更新

**检查**：
```python
# 1. 确认 session 状态查询正常
status = await session.check_status()
print(f"Status: {status}")  # 应该是 busy → idle

# 2. 确认消息轮询正常
messages = await session.get_messages()
print(f"Messages count: {len(messages)}")
```

## 进阶配置

### 自定义角色

添加新角色到 `AGENT_ROLES`：

```python
AGENT_ROLES[TaskType.DEPLOY] = AgentRole(
    name="部署专家",
    system_prompt="""部署专家，负责发布上线。

规则：
1. 检查 CI/CD 配置
2. 运行测试确保通过
3. 执行部署命令
4. 验证部署结果

禁止：
- 不要询问"确认部署吗"
- 直接执行，失败后回滚
""",
    allowed_tools={"read_file", "run_command", "search_files"},
    blocked_tools={"browser_open", "edit_file"},
    auto_approve_tools={"read_file", "run_command"}
)
```

### 添加安全规则

在 `ToolInterceptor` 中添加：

```python
DANGEROUS_PATTERNS = [
    # 现有规则...
    r"docker.*rm.*-f",    # 禁止强制删除容器
    r"kubectl.*delete",   # 禁止删除 k8s 资源
]
```

### 集成到 Feishu Bot

修改 `feishu_agent.py`：

```python
class FeishuBotAgent:
    def __init__(self, config):
        self.config = config
        # 添加 Agent Controller
        self.agent_controller = AgentController(
            port=self.config.base_port
        )
    
    async def _execute_plan_with_card(self, plan, chat_id, message_id, ctx):
        if plan.action == "send_task":
            adapter = FeishuAgentAdapter(
                self.agent_controller, 
                self
            )
            
            result = await adapter.execute_with_feishu_updates(
                task_text=plan.params.get("task", ""),
                chat_id=chat_id,
                message_id=message_id,
                role_type=self._determine_role(plan.params.get("task", ""))
            )
            
            # 处理结果...
```

## 总结

这个双层配置方案的优势：

1. **无需修改 OpenCode 源码** - 纯配置实现
2. **渐进式采用** - 可以同时保留默认 Build Agent
3. **灵活可控** - OpenCode 层定基调，Controller 层做微调
4. **安全隔离** - 危险操作在两层都有防护
5. **易于维护** - 配置即代码，版本可控

通过这种方式，我们完全解决了：
- ✅ 工具调用不打断上下文
- ✅ 不反问确认
- ✅ 不浏览器跳转
- ✅ 根据任务自动选择角色

现在你可以开始使用这个方案了！
