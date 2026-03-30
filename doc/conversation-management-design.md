# Feishu Bot 对话管理系统设计文档

## 问题背景

当前 Feishu Bot 与 OpenCode session 交互时存在以下问题：
1. **对话截断**：OpenCode 返回的长回复会被截断，丢失重要信息
2. **无状态管理**：无法暂停、恢复或查看历史对话
3. **信息过载**：一次性展示所有内容，用户体验差
4. **无法回顾**：对话结束后无法查看完整记录

## 解决方案

设计了一个完整的对话管理系统，提供以下能力：

### 1. 会话生命周期管理 (`conversation_manager.py`)

```python
ConversationStatus:
  - IDLE: 未开始
  - ACTIVE: 活跃中
  - PAUSED: 已暂停
  - COMPLETED: 已完成
  - ERROR: 出错

ConversationSession:
  - session_id: 唯一标识
  - workspace_path: 工作区路径
  - chat_id: 飞书聊天ID
  - messages: 完整消息历史
  - summary: 对话摘要
  - current_task: 当前任务

ConversationManager:
  - create_session(): 创建会话
  - start/pause/resume/end: 生命周期控制
  - add_message(): 添加消息（不截断）
  - get_session_history(): 分页查看历史
  - save/load: 持久化存储
```

### 2. 消息格式化 (`message_formatter.py`)

提供多种展示模式：

```python
# 自动模式：根据长度智能截断，带"查看详情"提示
MessageFormatter.format_for_card(text, mode="auto")

# 分页模式：将长文本分页，支持"下一页"
MessageFormatter.paginate(text, page_size=2000)

# 渐进模式：分阶段展示
# Stage 1: 一句话摘要
# Stage 2: 关键要点（5个bullet）
# Stage 3: 详细摘要
# Stage 4: 完整内容
MessageFormatter.create_progressive_display(text, stage=1)

# 历史格式化：带分页的对话历史
MessageFormatter.format_conversation_history(messages, page=1)
```

### 3. Bot 集成 (`conversation_bot_integration.py`)

将对话管理集成到 Feishu Bot：

```python
ConversationBotIntegration:
  - start_conversation(): 开始新对话
  - send_message(): 发送消息（支持渐进展示）
  - pause/resume/end: 会话控制
  - get_more_content(): 获取更多内容
  - get_conversation_history(): 查看历史
  - process_command(): 处理管理命令
```

## 使用示例

### 1. 开始对话

**用户**: 开始 ~/projects/myapp 实现用户登录功能

**Bot**:
```
✅ 对话已创建
会话ID: `conv_12345678...`
工作区: ~/projects/myapp
任务: 实现用户登录功能

现在开始你的任务描述，我会帮你处理。
```

### 2. 发送消息（长回复处理）

**用户**: 帮我写一个完整的登录接口

**Bot** (如果回复很长):
```
我已经完成了登录接口的实现。以下是主要功能：

1. POST /api/login - 处理登录请求
2. JWT token 生成和验证
3. 密码加密存储
4. 登录失败限制

[查看详情了解完整代码实现]
```

**用户**: 详情

**Bot** (展示关键要点):
```
要点:
• 使用 bcrypt 进行密码哈希
• JWT token 有效期 24 小时
• 支持 refresh token 机制
• 登录失败 5 次后锁定 15 分钟
• 完整的错误处理和日志记录

[查看完整内容]
```

**用户**: 完整

**Bot** (分页展示完整代码):
```
[第 1/3 页]

```python
from flask import Flask, request, jsonify
import bcrypt
import jwt
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if not user or not bcrypt.checkpw(
        password.encode(), user.password_hash.encode()
    ):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Generate JWT token
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, app.config['SECRET_KEY'])
    
    return jsonify({'token': token})
```

[回复「下一页」继续]
```

### 3. 会话控制

**用户**: 暂停

**Bot**:
```
⏸️ 对话已暂停
回复「继续」恢复对话
```

**用户**: 继续

**Bot**:
```
▶️ 对话已恢复
会话: ~/projects/myapp
任务: 实现用户登录功能

上次对话:
我已经完成了登录接口的实现...

请继续...
```

### 4. 查看历史

**用户**: 历史

**Bot**:
```
📜 对话记录
工作区: ~/projects/myapp
任务: 实现用户登录功能
状态: active
第 1/3 页
========================================

👤 [10:30:15]:
帮我写一个完整的登录接口

🤖 [10:30:45]:
我已经完成了登录接口的实现...

👤 [10:32:20]:
详情

🤖 [10:32:21]:
要点: ...

========================================
回复「历史 2」查看下一页
回复「详情」查看完整内容
```

### 5. 结束对话

**用户**: 结束

**Bot**:
```
✅ 对话已结束
会话: ~/projects/myapp
任务: 实现用户登录功能
时长: 45.2 分钟
消息: 8 用户 / 8 助手

回复「历史」查看对话记录
```

### 6. 查看对话列表

**用户**: 列表

**Bot**:
```
📋 对话列表

1. 🟢 `conv_12345678...`
   工作区: ~/projects/myapp
   任务: 实现用户登录功能
   消息: 16 条 | 时长: 45.2 分钟

2. ✅ `conv_87654321...`
   工作区: ~/projects/webapp
   任务: 优化数据库查询
   消息: 8 条 | 时长: 23.5 分钟

3. ⏸️ `conv_abcdef12...`
   工作区: ~/projects/api
   任务: 添加缓存层
   消息: 4 条 | 时长: 12.0 分钟

========================================
操作:
• 「切换 编号」切换对话
• 「历史 编号」查看记录
• 「结束 编号」结束对话
```

## 支持的命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `开始 [路径] [任务]` | 开始新对话 | `开始 ~/project 实现登录` |
| `暂停` | 暂停当前对话 | `暂停` |
| `继续` | 恢复暂停的对话 | `继续` |
| `结束` | 结束当前对话 | `结束` |
| `列表` | 列出所有对话 | `列表` |
| `历史 [ID]` | 查看对话历史 | `历史` / `历史 conv_123` |
| `更多/详情` | 查看更多内容 | `详情` |
| `完整` | 查看完整内容 | `完整` |
| `下一页` | 查看下一页 | `下一页` |

## 技术架构

```
用户消息
   ↓
ConversationBotIntegration.process_command()
   ├── 如果是管理命令 → 处理命令
   └── 如果是普通消息 → send_message()
            ↓
   ConversationManager.add_user_message()
            ↓
   OpenCodeWebClient.send_message() 
            ↓
   接收完整回复（不截断）
            ↓
   ConversationManager.add_assistant_message()
            ↓
   MessageFormatter.format_for_card()
            ↓
   返回给用户（摘要 + 查看详情选项）
```

## 数据持久化

对话历史保存到:
```
~/.config/feishu-agent/conversations.json
```

格式:
```json
{
  "sessions": {
    "conv_xxx": {
      "session_id": "conv_xxx",
      "workspace_path": "~/project",
      "status": "active",
      "messages": [
        {"role": "user", "content": "...", "timestamp": 1234567890},
        {"role": "assistant", "content": "...", "timestamp": 1234567891}
      ]
    }
  },
  "chat_sessions": {
    "chat_id_xxx": "conv_xxx"
  }
}
```

## 优势

1. **无截断**：完整保存所有对话内容
2. **渐进展示**：根据用户需要提供不同详细程度
3. **会话控制**：显式管理对话生命周期
4. **历史回看**：随时查看完整对话记录
5. **上下文保持**：暂停/恢复不丢失上下文
6. **多会话**：支持同时管理多个对话

## 下一步工作

1. 集成到 `feishu_agent.py` 的 BotBrain
2. 添加飞书卡片交互（按钮、分页控件）
3. 支持更多展示模式（代码高亮、文件下载）
4. 添加对话搜索功能
5. 支持导出对话为 Markdown
