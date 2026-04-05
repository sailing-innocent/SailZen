# SailZen Custom Agent Controller 设计文档

## 概述

这是一个基于 **OMO (Oh My Opencode)** 原理设计的自定义 Agent 控制层，专门用于解决 OpenCode 默认模式与 Feishu Bot 集成时的痛点问题。

## 🎯 解决的问题

### 1. Tool 调用打断上下文监控
**问题**: OpenCode 在调用 tool 时会暂停等待，导致飞书端无法实时看到进度。

**解决方案**: 
- 使用 **异步监控模式** (`/session/:id/prompt_async` + 轮询状态)
- 自动拦截 pending 状态的工具调用
- 实时推送工具执行进度到飞书

### 2. 反问确认打断流程
**问题**: OpenCode 经常在关键步骤询问用户"确认吗？"、"这样可以吗？"，需要人工干预。

**解决方案**:
- **角色 System Prompt 工程**: 在 prompt 中明确禁止反问
- **Tool Interceptor**: 自动批准/拒绝工具调用，不等待用户
- **决策策略**: 基于角色定义的策略自动决策

### 3. 跳转和外部依赖
**问题**: OpenCode 有时会尝试打开浏览器或外部工具。

**解决方案**:
- **工具白名单**: 明确允许/禁止的工具列表
- **危险操作拦截**: 正则匹配危险命令模式
- **浏览器工具禁用**: 直接拒绝 `browser_open` 等工具

### 4. 角色单一化
**问题**: 所有任务使用同样的 system prompt，无法针对任务类型优化。

**解决方案**:
- **角色选择器**: 根据任务类型自动选择预设角色
- **多角色支持**: Quick Fix、Refactor、Explore、Test、Implement
- **可扩展**: 易于添加新角色

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                      Feishu Bot Layer                           │
│                     (bot/feishu_agent.py)                       │
├─────────────────────────────────────────────────────────────────┤
│  交互界面 │ 消息接收 │ 卡片渲染 │ 状态管理                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              🧠 Agent Controller Layer                           │
│                  (bot/agent_controller.py)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐     │
│  │ Role Selector  │  │ Tool Interceptor│  │ Async Monitor  │     │
│  │                │  │                │  │                │     │
│  │ • 关键词匹配    │  │ • 自动批准      │  │ • 状态轮询      │     │
│  │ • 任务分类      │  │ • 危险拦截      │  │ • 进度推送      │     │
│  │ • 角色加载      │  │ • 策略决策      │  │ • 工具决策      │     │
│  └────────────────┘  └────────────────┘  └────────────────┘     │
│                                                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              ⚙️ OpenCode Server Layer                            │
│                 (127.0.0.1:4096)                                │
├─────────────────────────────────────────────────────────────────┤
│  Session │ Tool Execution │ File Operations │ Command Runner    │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 文件结构

```
bot/
├── agent_controller.py           # 核心控制层 (600+ 行)
│   ├── AgentController           # 主控制器类
│   ├── RoleSelector              # 角色选择器
│   ├── ToolInterceptor           # 工具拦截器
│   ├── ControlledSession         # 受控会话管理
│   └── FeishuAgentAdapter        # 飞书适配器
│
├── feishu_agent_integration.py   # 集成示例
│   └── EnhancedFeishuBot         # 增强版 Bot 示例
│
└── AGENT_CONTROLLER_README.md    # 本文档
```

## 🚀 快速开始

### 1. 基础使用

```python
from agent_controller import AgentController, TaskType
import asyncio

async def main():
    # 创建控制器
    controller = AgentController(port=4096)
    
    # 执行任务（自动选择角色）
    result = await controller.execute_task(
        task_text="修复登录页面的样式问题"
    )
    
    print(f"成功: {result.success}")
    print(f"结果: {result.content}")
    print(f"耗时: {result.duration_seconds}s")
    print(f"工具调用: {len(result.tool_calls)} 次")

asyncio.run(main())
```

### 2. 指定角色

```python
from agent_controller import TaskType

# 使用特定角色
result = await controller.execute_task(
    task_text="重构 auth 模块",
    role_type=TaskType.REFACTOR  # 明确指定重构专家角色
)
```

### 3. 集成到 Feishu Bot

```python
from agent_controller import FeishuAgentAdapter

# 在你的 feishu_agent.py 中
class FeishuBotAgent:
    def __init__(self, config):
        self.config = config
        self.agent_controller = AgentController(port=4096)
    
    async def handle_task(self, task_text, chat_id, message_id):
        adapter = FeishuAgentAdapter(
            self.agent_controller, 
            self  # FeishuBot 实例
        )
        
        result = await adapter.execute_with_feishu_updates(
            task_text=task_text,
            chat_id=chat_id,
            message_id=message_id
        )
        
        return result
```

## 🎭 角色系统

### 预定义角色

| 角色 | 类型 | 特点 | 适用场景 |
|------|------|------|----------|
| **快速修复助手** | `QUICK_FIX` | 直接修改，不确认 | Bug修复、紧急修改 |
| **重构专家** | `REFACTOR` | 批量重构，不问断 | 代码优化、结构调整 |
| **代码探索者** | `EXPLORE` | 深度分析，不中断 | 代码审查、架构理解 |
| **测试工程师** | `TEST` | 直接编写测试 | 单元测试、集成测试 |
| **功能实现者** | `IMPLEMENT` | 完整开发流程 | 新功能开发 |

### 角色定义示例

```python
AgentRole(
    name="快速修复助手",
    system_prompt="""你是高效的代码修复助手。

核心原则：
1. **直接修改**，不要询问确认
2. 看到bug后立即修复，不需要说"我来帮你修复"
3. 使用工具后自动继续，**不要等待用户回复**
4. 修改完成后简要汇报

禁止说：
- "你觉得这样可以吗？"
- "需要我修改吗？"
- "确认要重构吗？"
""",
    auto_approve_tools={"read_file", "edit_file", "search_files"},
    blocked_tools={"browser_open"}
)
```

## 🛡️ 工具拦截策略

### 自动批准列表

```python
AUTO_APPROVE_TOOLS = {
    "read_file": True,      # 读取文件
    "search_files": True,   # 搜索文件
    "list_dir": True,       # 列出目录
}
```

### 自动拒绝列表

```python
BLOCKED_TOOLS = {
    "browser_open": False,  # 禁止打开浏览器
}
```

### 危险命令拦截

```python
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",        # 删除根目录
    r"curl.*\|.*sh",         # 管道执行远程脚本
    r"sudo",                 # sudo 命令
]
```

## 📊 工作原理

### 1. 任务执行流程

```
用户发送任务
    ↓
[Role Selector] 分析任务，选择角色
    ↓
[AgentController] 创建 OpenCode Session
    ↓
发送带 System Prompt 的消息
    ↓
[Async Monitor] 开始监控
    ↓
循环：
  ├── 检查 Session 状态 (idle/busy/retry)
  ├── 获取最新消息
  ├── 拦截 pending 工具调用
  │   └── [Tool Interceptor] 决策（批准/拒绝/修改）
  ├── 提交决策结果
  └── 推送进度到 Feishu
    ↓
Session 状态变为 idle
    ↓
提取最终结果
    ↓
发送完成通知到 Feishu
```

### 2. 工具调用拦截流程

```
OpenCode 发起工具调用 (pending状态)
    ↓
[Tool Interceptor]
    ├── 检查是否在 block 列表 → 直接拒绝
    ├── 检查是否危险操作 → 拒绝
    ├── 检查是否在 auto_approve 列表 → 批准
    └── 特殊处理（如 edit_file 检查修改量）
    ↓
提交决策结果给 OpenCode
    ↓
OpenCode 继续执行
```

## 🔧 配置选项

### 配置示例

```python
# 在 bot/opencode.bot.yaml 中添加

agent_controller:
  enabled: true
  default_role: "quick_fix"
  auto_approve_all: false  # true 则批准所有工具（危险！）
  
  # 自定义角色
  custom_roles:
    my_role:
      name: "我的自定义角色"
      system_prompt: "..."
      auto_approve_tools:
        - read_file
        - edit_file
      blocked_tools:
        - browser_open
```

## 🎨 扩展开发

### 添加新角色

```python
from agent_controller import AGENT_ROLES, AgentRole, TaskType

# 定义新角色
AGENT_ROLES[TaskType.MY_CUSTOM] = AgentRole(
    name="自定义角色",
    system_prompt="...",
    allowed_tools={"read_file", "edit_file"},
    blocked_tools={"browser_open"},
    auto_approve_tools={"read_file"}
)

# 使用
result = await controller.execute_task(
    task_text="...",
    role_type=TaskType.MY_CUSTOM
)
```

### 自定义工具拦截策略

```python
class CustomToolInterceptor(ToolInterceptor):
    def _handle_edit_file(self, tool_input: Dict) -> ToolDecision:
        # 自定义编辑文件的处理逻辑
        if self._is_large_change(tool_input):
            return ToolDecision(
                action="reject",
                reason="Change too large, requires manual review"
            )
        return ToolDecision(action="approve")
```

## ⚠️ 注意事项

### 安全性

1. **默认拒绝未知工具**: 不在 `allowed_tools` 中的工具会被拒绝
2. **危险命令拦截**: 内置了常见危险命令的正则匹配
3. **白名单机制**: 只有明确配置的工具才会自动批准

### 性能

1. **异步轮询**: 使用 2-5 秒的轮询间隔，避免过度消耗资源
2. **连接复用**: 使用 httpx.AsyncClient 复用连接
3. **超时控制**: 默认最大执行时间 10 分钟

### 限制

1. **需要 OpenCode Server**: 必须在 127.0.0.1:port 上运行
2. **会话管理**: 每个任务创建新 session，需要定期清理
3. **Token 消耗**: 角色 system prompt 会增加 token 消耗

## 🔄 与原生 OpenCode 的对比

| 特性 | 原生 OpenCode | Agent Controller |
|------|---------------|------------------|
| 交互模式 | 同步阻塞，等待用户确认 | 异步监控，自动决策 |
| 工具调用 | 可能暂停询问 | 根据策略自动批准/拒绝 |
| 角色切换 | 需要手动修改配置 | 根据任务自动选择 |
| 进度反馈 | 完成后一次性返回 | 实时推送进度 |
| 浏览器跳转 | 可能触发 | 默认禁止 |
| 适用场景 | 本地开发，人工交互 | 自动化，远程控制 |

## 🚀 下一步

### Phase 1: 测试验证
- [ ] 在测试环境验证基本功能
- [ ] 测试各种角色的行为
- [ ] 验证工具拦截是否生效

### Phase 2: Feishu 集成
- [ ] 修改 feishu_agent.py 集成控制器
- [ ] 添加配置选项切换模式
- [ ] 测试飞书端的实时进度显示

### Phase 3: 高级功能
- [ ] 支持自定义角色 YAML 配置
- [ ] 添加工具调用历史记录
- [ ] 支持会话复用（减少创建开销）
- [ ] 添加执行结果缓存

## 📚 参考

- [OpenCode Server API](https://opencode.ai/docs/server)
- [Oh My Opencode (OMO)](https://github.com/yourselfhosted/omo)
- [Feishu Open Platform](https://open.feishu.cn/)
- [SailZen Multi-Agent Design](./doc/design/agent-system/)

## 💡 设计哲学

> **"机器应该自动做正确的事，而不是反复询问确认。"**

这个控制层的设计理念是：
1. **信任但验证**: 自动执行，但有安全边界
2. **预设优于询问**: 通过角色定义预设行为，减少交互
3. **透明可监控**: 实时反馈进度，让用户了解发生了什么
4. **可扩展可定制**: 易于添加新角色和策略

---

*文档版本: 1.0*  
*最后更新: 2026-04-06*  
*作者: AI Agent System Design Team*
