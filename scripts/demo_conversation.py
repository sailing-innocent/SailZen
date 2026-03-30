#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Feishu Bot 对话管理系统快速示例

演示如何使用 ConversationManager 实现人类友好的对话交互
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.conversation_manager import (
    ConversationManager,
    ConversationStatus,
    get_conversation_manager,
)
from bot.message_formatter import MessageFormatter


def demo_conversation_lifecycle():
    """演示会话生命周期管理"""
    print("=" * 60)
    print("演示 1: 会话生命周期管理")
    print("=" * 60)

    # 获取对话管理器
    mgr = get_conversation_manager()

    # 1. 创建新会话
    print("\n1. 创建新会话...")
    session = mgr.create_session(
        workspace_path="~/projects/demo", chat_id="chat_12345", task="演示对话管理功能"
    )
    print(f"   会话ID: {session.session_id}")
    print(f"   状态: {session.status.value}")
    print(f"   任务: {session.current_task}")

    # 2. 开始会话
    print("\n2. 开始会话...")
    mgr.start_session(session.session_id, opencode_session_id="oc_abc123")
    print(f"   状态更新为: {session.status.value}")

    # 3. 添加消息
    print("\n3. 添加消息...")
    mgr.add_user_message(session.session_id, "你好，帮我写个函数")
    mgr.add_assistant_message(
        session.session_id,
        "好的，我来帮你写一个示例函数：\n\n"
        "```python\n"
        "def hello_world():\n"
        "    print('Hello, World!')\n"
        "```\n\n"
        "这是一个简单的函数，你可以根据需要修改。",
    )
    print(f"   当前消息数: {session.get_message_count()}")

    # 4. 暂停会话
    print("\n4. 暂停会话...")
    mgr.pause_session(session.session_id)
    print(f"   状态更新为: {session.status.value}")

    # 5. 恢复会话
    print("\n5. 恢复会话...")
    mgr.resume_session(session.session_id)
    print(f"   状态更新为: {session.status.value}")

    # 6. 添加更多消息
    print("\n6. 添加更多消息...")
    mgr.add_user_message(session.session_id, "能加个参数吗？")
    long_response = """当然可以！下面是带参数的示例：

```python
def hello_world(name="World", greeting="Hello"):
    '''
    打印问候语
    
    参数:
        name: 要问候的名字，默认 "World"
        greeting: 问候语，默认 "Hello"
    '''
    print(f'{greeting}, {name}!')
    return f'{greeting}, {name}!'

# 使用示例
hello_world()                    # 输出: Hello, World!
hello_world("Alice")             # 输出: Hello, Alice!
hello_world("Bob", "Hi")         # 输出: Hi, Bob!
```

这个函数现在更灵活了！你可以自定义名字和问候语。
"""
    mgr.add_assistant_message(session.session_id, long_response)
    print(f"   当前消息数: {session.get_message_count()}")

    # 7. 结束会话
    print("\n7. 结束会话...")
    mgr.end_session(session.session_id)
    print(f"   状态更新为: {session.status.value}")

    return session


def demo_message_formatting():
    """演示消息格式化"""
    print("\n" + "=" * 60)
    print("演示 2: 消息格式化与渐进展示")
    print("=" * 60)

    formatter = MessageFormatter()

    long_text = """我已经完成了登录接口的实现。以下是完整的功能：

## 1. 登录接口

```python
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    # 验证用户
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # 验证密码
    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return jsonify({'error': 'Invalid password'}), 401
    
    # 生成 token
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, app.config['SECRET_KEY'])
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email
        }
    })
```

## 2. 安全措施

- 使用 bcrypt 进行密码哈希
- JWT token 有效期 24 小时
- 支持 refresh token 机制
- 登录失败 5 次后锁定 15 分钟
- 完整的错误处理和日志记录

## 3. 使用示例

```bash
curl -X POST http://localhost:5000/api/login \\
  -H "Content-Type: application/json" \\
  -d '{
    "username": "admin",
    "password": "secret123"
  }'
```

希望这个实现对你有帮助！
"""

    print("\n1. 自动模式格式化:")
    formatted, has_more, pages = formatter.format_for_card(long_text, mode="auto")
    print(f"   长度: {len(formatted)} 字符")
    print(f"   是否还有更多: {has_more}")
    print(f"   总页数: {pages}")
    print(f"   预览:\n{formatted[:200]}...")

    print("\n2. 渐进展示 - Stage 1 (摘要):")
    stage1 = formatter.create_progressive_display(long_text, stage=1)
    print(f"   {stage1}")

    print("\n3. 渐进展示 - Stage 2 (要点):")
    stage2 = formatter.create_progressive_display(long_text, stage=2)
    print(f"   {stage2[:300]}...")

    print("\n4. 分页展示:")
    pages = formatter.paginate(long_text, page_size=500)
    print(f"   共 {len(pages)} 页")
    print(f"   第一页长度: {len(pages[0])} 字符")


def demo_history_browsing():
    """演示历史浏览"""
    print("\n" + "=" * 60)
    print("演示 3: 历史记录浏览")
    print("=" * 60)

    mgr = get_conversation_manager()

    # 创建示例会话
    session = mgr.create_session(
        workspace_path="~/projects/example", chat_id="chat_demo", task="示例任务"
    )

    # 添加多条消息
    for i in range(10):
        mgr.add_user_message(session.session_id, f"用户消息 {i + 1}")
        mgr.add_assistant_message(
            session.session_id, f"助手回复 {i + 1}\n这是详细内容..."
        )

    print(f"\n1. 消息总数: {session.get_message_count()}")

    print("\n2. 分页查看 (每页5条):")
    messages, total_pages = mgr.get_session_history(
        session.session_id, page=1, page_size=5
    )
    print(f"   总页数: {total_pages}")
    print(f"   当前页消息数: {len(messages)}")

    print("\n3. 统计信息:")
    stats = session.get_summary_stats()
    print(f"   总消息数: {stats['total_messages']}")
    print(f"   用户消息: {stats['user_messages']}")
    print(f"   助手消息: {stats['assistant_messages']}")
    print(f"   对话时长: {stats['duration_minutes']:.1f} 分钟")

    print("\n4. 最近对话摘要:")
    summary = mgr.get_recent_summary("chat_demo", max_sessions=3)
    print(f"   {summary}")


def demo_commands():
    """演示命令处理"""
    print("\n" + "=" * 60)
    print("演示 4: 命令处理")
    print("=" * 60)

    from bot.opencode_client import OpenCodeWebClient
    from bot.conversation_bot_integration import ConversationBotIntegration

    # 创建集成实例（使用 mock）
    client = OpenCodeWebClient(port=4096)
    integration = ConversationBotIntegration(client)

    chat_id = "chat_test"

    print("\n1. 测试命令识别:")
    commands = [
        "开始 ~/project 实现登录",
        "暂停",
        "继续",
        "结束",
        "列表",
        "历史",
        "详情",
        "这是一个普通消息",
    ]

    for cmd in commands:
        handled, response, action = integration.process_command(cmd, chat_id)
        status = "✓ 已处理" if handled else "○ 未处理"
        print(f"   '{cmd[:20]}...' -> {status} ({action or 'none'})")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Feishu Bot 对话管理系统演示")
    print("=" * 60)

    try:
        # 运行演示
        demo_conversation_lifecycle()
        demo_message_formatting()
        demo_history_browsing()
        demo_commands()

        print("\n" + "=" * 60)
        print("演示完成!")
        print("=" * 60)
        print("\n主要功能:")
        print("✓ 会话生命周期管理 (创建/开始/暂停/恢复/结束)")
        print("✓ 完整消息历史保存 (不截断)")
        print("✓ 渐进式消息展示 (摘要 → 要点 → 详情)")
        print("✓ 分页查看历史")
        print("✓ 对话状态持久化")
        print("\n查看详细文档: doc/conversation-management-design.md")

    except Exception as e:
        print(f"\n❌ 演示出错: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
