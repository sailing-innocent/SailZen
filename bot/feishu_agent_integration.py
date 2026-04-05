#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file feishu_agent_integration.py
# @brief Feishu Agent 集成示例 - 展示如何使用 AgentController
# @author sailing-innocent
# @date 2026-04-06
# ---------------------------------
"""Feishu Agent 集成示例

展示如何将 AgentController 集成到现有的 feishu_agent.py 中。

使用方式：
1. 将 agent_controller.py 放在 bot/ 目录下
2. 在 feishu_agent.py 中导入并使用
"""

import asyncio
from typing import Optional

# 导入 AgentController
from agent_controller import AgentController, TaskType, FeishuAgentAdapter


class EnhancedFeishuBot:
    """增强版 Feishu Bot，使用自定义 Agent Controller"""

    def __init__(self, config):
        self.config = config
        self.agent_controller: Optional[AgentController] = None

    def initialize(self):
        """初始化 Agent Controller"""
        # 为每个工作区创建一个控制器实例
        # 或者共享一个控制器，通过 port 区分不同工作区
        self.agent_controller = AgentController(port=4096)

    async def handle_task_with_controller(
        self, task_text: str, chat_id: str, message_id: str, workspace_path: str
    ):
        """
        使用 Agent Controller 处理任务

        这是原 feishu_agent.py 中 _execute_plan_with_card 的增强版本
        """
        # 创建适配器
        adapter = FeishuAgentAdapter(self.agent_controller, self)

        # 根据任务内容自动选择角色
        role_type = self._determine_role(task_text)

        # 发送初始进度卡片
        await self._send_progress_card(
            chat_id,
            message_id,
            title="🚀 任务开始",
            content=f"识别角色: {role_type.value}\n正在初始化...",
            show_cancel=True,
        )

        # 执行任务
        result = await adapter.execute_with_feishu_updates(
            task_text=task_text,
            chat_id=chat_id,
            message_id=message_id,
            role_type=role_type,
        )

        # 处理结果
        if result.success:
            await self._send_result_card(
                chat_id,
                title="✅ 任务完成",
                content=result.content[:2000],  # 限制长度
                tool_count=len(result.tool_calls),
                duration=result.duration_seconds,
            )
        else:
            await self._send_error_card(
                chat_id, title="❌ 任务失败", error=result.error or "Unknown error"
            )

        return result

    def _determine_role(self, task_text: str) -> TaskType:
        """根据任务文本确定角色类型"""
        # 可以使用简单的关键词匹配
        # 或者使用 LLM 进行意图识别

        text_lower = task_text.lower()

        if any(kw in text_lower for kw in ["fix", "bug", "error", "修复"]):
            return TaskType.QUICK_FIX
        elif any(kw in text_lower for kw in ["refactor", "重构", "优化"]):
            return TaskType.REFACTOR
        elif any(kw in text_lower for kw in ["test", "测试"]):
            return TaskType.TEST
        elif any(kw in text_lower for kw in ["explore", "分析", "了解"]):
            return TaskType.EXPLORE
        else:
            return TaskType.IMPLEMENT

    async def _send_progress_card(
        self,
        chat_id: str,
        message_id: str,
        title: str,
        content: str,
        show_cancel: bool = False,
    ):
        """发送进度卡片（需要与你的 CardRenderer 集成）"""
        # 这里调用你现有的卡片发送逻辑
        print(f"[Progress] {title}: {content}")

    async def _send_result_card(
        self, chat_id: str, title: str, content: str, tool_count: int, duration: float
    ):
        """发送结果卡片"""
        summary = (
            f"{content}\n\n---\n📊 统计: {tool_count} 个工具调用 | ⏱️ {duration:.1f}s"
        )
        print(f"[Result] {title}: {summary}")

    async def _send_error_card(self, chat_id: str, title: str, error: str):
        """发送错误卡片"""
        print(f"[Error] {title}: {error}")


# ---------------------------------------------------------------------------
# 与原 feishu_agent.py 的集成点
# ---------------------------------------------------------------------------

"""
在 feishu_agent.py 中的修改建议：

1. 导入 AgentController:
   
   from agent_controller import AgentController, TaskType, FeishuAgentAdapter
   
2. 在 FeishuBotAgent.__init__ 中初始化:
   
   self.agent_controller = AgentController(port=4096)
   
3. 修改 _execute_plan_with_card 方法:
   
   原代码（简化）:
   ```python
   def _execute_plan_with_card(self, plan, chat_id, message_id, ctx):
       if action == "send_task":
           # ... 原来的 OpenCode 调用逻辑
   ```
   
   新代码:
   ```python
   async def _execute_plan_with_card(self, plan, chat_id, message_id, ctx):
       if action == "send_task":
           task_text = plan.params.get("task", "")
           
           # 使用 Agent Controller
           adapter = FeishuAgentAdapter(self.agent_controller, self)
           role_type = self._determine_role(task_text)
           
           result = await adapter.execute_with_feishu_updates(
               task_text=task_text,
               chat_id=chat_id,
               message_id=message_id,
               role_type=role_type
           )
           
           # 处理结果...
   ```

4. 可选：保留原来的模式作为 fallback:
   
   可以添加一个配置项，让用户选择使用哪种模式:
   
   ```yaml
   # opencode.bot.yaml
   agent_mode: "controlled"  # 或 "standard" 使用原模式
   ```
"""


# ---------------------------------------------------------------------------
# 快速测试
# ---------------------------------------------------------------------------


async def test_integration():
    """测试集成"""
    print("=" * 60)
    print("Feishu Agent Controller 集成测试")
    print("=" * 60)

    # 模拟配置
    class MockConfig:
        app_id = "test"
        app_secret = "test"

    config = MockConfig()

    # 创建增强版 Bot
    bot = EnhancedFeishuBot(config)
    bot.initialize()

    # 测试任务
    test_tasks = [
        "修复登录页面的 404 错误",
        "重构 auth.py 的错误处理逻辑",
        "分析用户模块的代码结构",
        "为用户服务编写单元测试",
    ]

    for task in test_tasks:
        print(f"\n{'=' * 60}")
        print(f"测试任务: {task}")
        print("=" * 60)

        # 注意：这里不会真正执行，因为没有运行 OpenCode
        # 只是展示调用方式
        print("\n[Info] 实际执行需要 OpenCode Server 运行在 127.0.0.1:4096")
        print("[Info] 这里是集成示例代码，展示了如何调用\n")

        # 显示角色选择
        role = bot._determine_role(task)
        print(f"🎭 自动识别角色: {role.value}")


if __name__ == "__main__":
    asyncio.run(test_integration())
