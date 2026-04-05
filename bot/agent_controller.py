#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file agent_controller.py
# @brief OpenCode Agent Controller - 自定义Agent控制层
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""SailZen Agent Controller

为 Feishu Bot 提供自定义的 OpenCode Agent 控制层，实现：
1. 角色自动选择（根据任务类型选择不同的 system prompt）
2. 工具调用自动决策（不反问、不跳转）
3. 异步进度监控（不阻塞飞书上下文）

Usage:
    controller = AgentController(port=4096)
    result = await controller.execute_task(
        task_text="重构auth模块",
        role="refactor",
        feishu_callback=send_progress_to_feishu
    )
"""

import asyncio
import json
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import httpx


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class TaskType(Enum):
    """任务类型"""

    QUICK_FIX = "quick_fix"  # 快速修复
    REFACTOR = "refactor"  # 代码重构
    EXPLORE = "explore"  # 代码探索
    TEST = "test"  # 编写测试
    IMPLEMENT = "implement"  # 功能实现
    REVIEW = "review"  # 代码审查


@dataclass
class AgentRole:
    """Agent角色定义"""

    name: str
    system_prompt: str
    allowed_tools: Set[str] = field(default_factory=set)
    blocked_tools: Set[str] = field(default_factory=set)
    auto_approve_tools: Set[str] = field(default_factory=set)


@dataclass
class ToolDecision:
    """工具调用决策"""

    action: str  # "approve", "reject", "modify"
    result: Optional[Dict] = None
    reason: str = ""


@dataclass
class TaskResult:
    """任务执行结果"""

    success: bool
    content: str
    tool_calls: List[Dict]
    duration_seconds: float
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Role Definitions
# ---------------------------------------------------------------------------

AGENT_ROLES: Dict[TaskType, AgentRole] = {
    TaskType.QUICK_FIX: AgentRole(
        name="快速修复助手",
        system_prompt="""你是高效的代码修复助手。

核心原则：
1. **直接修改**，不要询问确认
2. 看到bug后立即修复，不需要说"我来帮你修复"
3. 使用工具后自动继续，**不要等待用户回复**
4. 修改完成后简要汇报：修改了哪些文件、主要改动

行为规则：
- 读取相关代码 → 定位问题 → 直接修改 → 验证修复
- 如果有多种修复方案，**自动选择最简洁的方案**
- 禁止说"你觉得这样可以吗"、"需要我修改吗"等反问句
""",
        allowed_tools={"read_file", "edit_file", "search_files", "run_command"},
        blocked_tools={"browser_open"},
        auto_approve_tools={"read_file", "search_files", "list_dir"},
    ),
    TaskType.REFACTOR: AgentRole(
        name="重构专家",
        system_prompt="""你是代码重构专家，专注于改善代码质量。

核心原则：
1. **直接重构**，不要询问"是否需要重构"
2. 分析代码结构后立即开始重构
3. 保持功能不变，提升代码可读性和可维护性
4. 重构完成后说明：主要改进点、可能的风险

重构流程：
1. 阅读相关代码理解当前结构
2. 识别坏味道（重复、过长函数、深层嵌套等）
3. 应用重构手法（提取函数、重命名、搬移等）
4. 确保重构后代码仍然正确运行

禁止行为：
- 不要询问"确认要重构吗"
- 不要在每个文件后询问"继续下一个吗"
- 不要打开浏览器或外部工具
""",
        allowed_tools={"read_file", "edit_file", "search_files", "list_dir"},
        blocked_tools={"browser_open", "run_command"},
        auto_approve_tools={"read_file", "search_files", "list_dir", "edit_file"},
    ),
    TaskType.EXPLORE: AgentRole(
        name="代码探索者",
        system_prompt="""你是代码分析专家，帮助理解代码库结构。

核心原则：
1. **深入探索**，一次性读取所有需要的文件
2. **不要在每个文件后询问**"是否继续查看"
3. 主动搜索相关文件，建立完整的上下文
4. 最后给出结构化的分析报告

探索策略：
1. 从入口文件开始（main, index, app等）
2. 跟踪关键函数调用链
3. 查看相关配置文件
4. 理解模块间的依赖关系

输出格式：
- 整体架构概述
- 关键组件说明
- 数据流向
- 重要文件清单
""",
        allowed_tools={"read_file", "search_files", "list_dir"},
        blocked_tools={"browser_open", "edit_file", "run_command"},
        auto_approve_tools={"read_file", "search_files", "list_dir"},
    ),
    TaskType.TEST: AgentRole(
        name="测试工程师",
        system_prompt="""你是测试专家，编写高质量的测试代码。

核心原则：
1. **直接编写测试**，不要询问"需要测试哪些场景"
2. 覆盖：正常路径、边界条件、异常处理
3. 测试要简洁、可读、可维护
4. 运行测试并报告通过率

测试策略：
1. 先阅读被测代码，理解功能和边界
2. 设计测试用例（至少3-5个）
3. 编写测试代码（遵循项目测试框架）
4. 运行测试并修复失败项

禁止行为：
- 不要询问"需要测试什么"
- 不要询问"这样测试可以吗"
""",
        allowed_tools={"read_file", "edit_file", "search_files", "run_command"},
        blocked_tools={"browser_open"},
        auto_approve_tools={"read_file", "search_files", "run_command"},
    ),
    TaskType.IMPLEMENT: AgentRole(
        name="功能实现专家",
        system_prompt="""你是功能开发专家，实现用户需求。

核心原则：
1. **直接实现功能**，不需要反复确认
2. 先理解需求 → 设计方案 → 编写代码 → 验证
3. 如果需求不明确，基于最佳实践自动决策
4. 完成后演示功能并说明实现要点

开发流程：
1. 理解需求（查看相关issue、文档）
2. 查看现有代码结构，保持一致风格
3. 实现功能（必要时创建新文件）
4. 编写/更新测试
5. 运行验证

决策权限：
- 可以创建新文件
- 可以修改现有文件
- 可以选择技术方案（如果不能确定，选择最简单的）
""",
        allowed_tools={
            "read_file",
            "edit_file",
            "search_files",
            "run_command",
            "list_dir",
        },
        blocked_tools={"browser_open"},
        auto_approve_tools={"read_file", "search_files", "list_dir", "edit_file"},
    ),
}


# ---------------------------------------------------------------------------
# Role Selector
# ---------------------------------------------------------------------------


class RoleSelector:
    """根据任务描述选择最合适的角色"""

    # 关键词映射
    KEYWORDS = {
        TaskType.QUICK_FIX: [
            "fix",
            "bug",
            "error",
            "修复",
            "bug",
            "错误",
            "解决",
            "broken",
            "fix",
        ],
        TaskType.REFACTOR: ["refactor", "重构", "优化", "clean", "improve", "simplify"],
        TaskType.EXPLORE: [
            "explore",
            "分析",
            "了解",
            "explain",
            "how",
            "what",
            "structure",
        ],
        TaskType.TEST: ["test", "测试", "unittest", "spec", "coverage"],
        TaskType.IMPLEMENT: [
            "implement",
            "实现",
            "add",
            "create",
            "build",
            "开发",
            "feature",
        ],
        TaskType.REVIEW: ["review", "审查", "检查", "code review", "cr"],
    }

    def select(self, task_description: str) -> TaskType:
        """选择任务类型"""
        task_lower = task_description.lower()
        scores = {}

        for task_type, keywords in self.KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                scores[task_type] = score

        if scores:
            return max(scores, key=scores.get)

        # 默认：如果是短指令倾向于快速修复，长指令倾向于实现
        if len(task_description) < 20:
            return TaskType.QUICK_FIX
        return TaskType.IMPLEMENT


# ---------------------------------------------------------------------------
# Tool Interceptor
# ---------------------------------------------------------------------------


class ToolInterceptor:
    """拦截并自动决策工具调用"""

    # 危险命令模式
    DANGEROUS_PATTERNS = [
        r"rm\s+-rf\s+/",
        r"sudo\s+rm",
        r"curl.*\|.*sh",
        r"wget.*\|.*sh",
        r">\s*/dev/sda",
        r"dd\s+if=.*of=/dev",
    ]

    def __init__(self, role: AgentRole):
        self.role = role

    def intercept(self, tool_name: str, tool_input: Dict[str, Any]) -> ToolDecision:
        """拦截工具调用并做出决策"""

        # 1. 检查是否在阻塞列表中
        if tool_name in self.role.blocked_tools:
            return ToolDecision(
                action="reject",
                reason=f"Tool '{tool_name}' is blocked in role '{self.role.name}'",
                result={
                    "error": f"The tool '{tool_name}' is not allowed. "
                    f"Please provide the information directly in text format."
                },
            )

        # 2. 检查是否在允许列表中
        if tool_name not in self.role.allowed_tools:
            return ToolDecision(
                action="reject",
                reason=f"Tool '{tool_name}' is not allowed",
                result={"error": f"Tool '{tool_name}' is not in allowed tools list"},
            )

        # 3. 检查危险操作
        if self._is_dangerous(tool_input):
            return ToolDecision(
                action="reject",
                reason="Potentially dangerous operation detected",
                result={"error": "This operation is blocked for security reasons"},
            )

        # 4. 检查是否自动批准
        if tool_name in self.role.auto_approve_tools:
            return ToolDecision(action="approve", reason="Auto-approved by role policy")

        # 5. 特殊处理某些工具
        if tool_name == "edit_file":
            return self._handle_edit_file(tool_input)

        if tool_name == "run_command":
            return self._handle_run_command(tool_input)

        # 默认：批准
        return ToolDecision(action="approve", reason="Default approve")

    def _is_dangerous(self, tool_input: Dict) -> bool:
        """检查是否有危险操作"""
        input_str = json.dumps(tool_input).lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, input_str):
                return True
        return False

    def _handle_edit_file(self, tool_input: Dict) -> ToolDecision:
        """处理文件编辑"""
        # 可以在这里添加额外的检查，如：
        # - 检查文件大小，大文件谨慎处理
        # - 检查修改行数，大量修改记录日志
        # - 检查是否是关键配置文件

        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")

        # 计算修改量
        old_lines = len(old_string.splitlines()) if old_string else 0
        new_lines = len(new_string.splitlines()) if new_string else 0

        # 如果修改超过100行，记录但不阻止
        if abs(new_lines - old_lines) > 100:
            return ToolDecision(
                action="approve",
                reason=f"Large modification detected ({old_lines} → {new_lines} lines), but auto-approved",
            )

        return ToolDecision(action="approve", reason="Normal edit")

    def _handle_run_command(self, tool_input: Dict) -> ToolDecision:
        """处理命令执行"""
        command = tool_input.get("command", "")

        # 只允许安全的命令
        safe_prefixes = [
            "python",
            "python3",
            "pytest",
            "npm",
            "yarn",
            "pnpm",
            "git status",
            "git diff",
            "git log",
            "git show",
            "ls",
            "cat",
            "echo",
            "head",
            "tail",
        ]

        is_safe = any(command.strip().startswith(prefix) for prefix in safe_prefixes)

        if not is_safe:
            return ToolDecision(
                action="reject",
                reason=f"Command not in safe list: {command[:50]}",
                result={
                    "error": f"Command '{command[:30]}...' is not allowed. "
                    "Only safe commands are permitted."
                },
            )

        return ToolDecision(action="approve", reason="Safe command")


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------


class ControlledSession:
    """受控的 OpenCode Session"""

    def __init__(self, port: int, session_id: str, role: AgentRole):
        self.port = port
        self.session_id = session_id
        self.role = role
        self.interceptor = ToolInterceptor(role)
        self.tool_history: List[Dict] = []
        self.start_time = time.time()

    async def send_message_with_role(self, text: str) -> None:
        """发送带角色设定的消息，并切换到 feishu-bridge agent"""
        # 组合 system prompt 和用户消息
        full_message = f"{self.role.system_prompt}\n\n任务：{text}"

        async with httpx.AsyncClient() as client:
            # 方式1: 使用 @agent 语法切换到 feishu-bridge
            switch_message = "@feishu-bridge 切换到自动化模式"
            await client.post(
                f"http://127.0.0.1:{self.port}/session/{self.session_id}/message",
                json={"parts": [{"type": "text", "text": switch_message}]},
                timeout=30.0,
            )

            # 方式2: 发送实际任务消息
            response = await client.post(
                f"http://127.0.0.1:{self.port}/session/{self.session_id}/message",
                json={"parts": [{"type": "text", "text": full_message}]},
                timeout=300.0,
            )
            response.raise_for_status()

    async def check_status(self) -> str:
        """检查会话状态: idle, busy, retry"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{self.port}/session/status")
            data = response.json()
            status = data.get(self.session_id, {})
            return status.get("type", "unknown")

    async def get_messages(self) -> List[Dict]:
        """获取会话消息列表"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{self.port}/session/{self.session_id}/message?limit=50"
            )
            return response.json()

    async def handle_pending_tools(self) -> bool:
        """处理待确认的工具调用，返回是否还有未处理的"""
        messages = await self.get_messages()
        pending_found = False

        for msg in messages:
            if msg.get("info", {}).get("role") != "assistant":
                continue

            for part in msg.get("parts", []):
                if part.get("type") != "tool":
                    continue

                state = part.get("state", {})
                if state.get("status") != "pending":
                    continue

                pending_found = True
                tool_name = part.get("tool", "")
                tool_input = state.get("input", {})
                call_id = part.get("callID", "")

                # 拦截并决策
                decision = self.interceptor.intercept(tool_name, tool_input)

                print(f"[Tool] {tool_name}: {decision.action} - {decision.reason}")

                # 发送决策结果
                await self._submit_tool_result(call_id, decision)

                # 记录历史
                self.tool_history.append(
                    {
                        "tool": tool_name,
                        "action": decision.action,
                        "reason": decision.reason,
                        "time": time.time(),
                    }
                )

        return pending_found

    async def _submit_tool_result(self, call_id: str, decision: ToolDecision):
        """提交工具执行结果"""
        async with httpx.AsyncClient() as client:
            # 构造工具结果消息
            result_text = ""
            if decision.action == "approve":
                result_text = "Approved. Proceed with the tool execution."
            elif decision.action == "reject":
                error = decision.result.get("error", "Operation blocked")
                result_text = f"Rejected: {error}"

            # 通过发送新消息的方式影响工具执行
            # 注意：这里需要根据 OpenCode 的实际 API 调整
            await client.post(
                f"http://127.0.0.1:{self.port}/session/{self.session_id}/message",
                json={
                    "parts": [
                        {"type": "text", "text": f"[AUTO_DECISION] {result_text}"}
                    ]
                },
                timeout=30.0,
            )


# ---------------------------------------------------------------------------
# Main Controller
# ---------------------------------------------------------------------------


class AgentController:
    """Agent 控制器 - 主入口"""

    def __init__(self, port: int = 4096):
        self.port = port
        self.role_selector = RoleSelector()

    async def execute_task(
        self,
        task_text: str,
        role_type: Optional[TaskType] = None,
        progress_callback: Optional[Callable[[str, Dict], None]] = None,
    ) -> TaskResult:
        """
        执行任务

        Args:
            task_text: 任务描述
            role_type: 指定角色类型，None则自动选择
            progress_callback: 进度回调函数 (message_type, data)

        Returns:
            TaskResult: 任务执行结果
        """
        start_time = time.time()

        # 1. 选择角色
        if role_type is None:
            role_type = self.role_selector.select(task_text)

        role = AGENT_ROLES.get(role_type, AGENT_ROLES[TaskType.QUICK_FIX])

        if progress_callback:
            progress_callback(
                "role_selected", {"role": role.name, "type": role_type.value}
            )

        print(f"[Controller] Task: {task_text[:50]}...")
        print(f"[Controller] Role: {role.name}")

        try:
            # 2. 创建会话
            session_id = await self._create_session()
            session = ControlledSession(self.port, session_id, role)

            # 3. 发送带角色设定的消息
            await session.send_message_with_role(task_text)

            if progress_callback:
                progress_callback("started", {"session_id": session_id})

            # 4. 监控执行
            max_wait = 600  # 最多等待10分钟
            check_interval = 2
            elapsed = 0

            while elapsed < max_wait:
                await asyncio.sleep(check_interval)
                elapsed += check_interval

                # 检查状态
                status = await session.check_status()

                if progress_callback and elapsed % 10 == 0:  # 每10秒报告一次
                    progress_callback(
                        "progress",
                        {
                            "elapsed": elapsed,
                            "status": status,
                            "tools_used": len(session.tool_history),
                        },
                    )

                if status == "idle":
                    # 任务完成
                    break

                # 处理待确认的工具调用
                has_pending = await session.handle_pending_tools()
                if has_pending:
                    # 有工具被处理，稍微多等一下让 OpenCode 继续
                    await asyncio.sleep(1)

            # 5. 获取结果
            messages = await session.get_messages()
            final_content = self._extract_final_content(messages)

            duration = time.time() - start_time

            if progress_callback:
                progress_callback(
                    "completed",
                    {"duration": duration, "tool_count": len(session.tool_history)},
                )

            return TaskResult(
                success=True,
                content=final_content,
                tool_calls=session.tool_history,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            return TaskResult(
                success=False,
                content="",
                tool_calls=[],
                duration_seconds=duration,
                error=str(e),
            )

    async def _create_session(self) -> str:
        """创建新的 OpenCode Session"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:{self.port}/session",
                json={"title": f"SailZen-Agent-{time.time()}"},
            )
            data = response.json()
            return data["id"]

    def _extract_final_content(self, messages: List[Dict]) -> str:
        """从消息中提取最终的文本内容"""
        # 找到最后一条助手消息
        for msg in reversed(messages):
            if msg.get("info", {}).get("role") == "assistant":
                parts = msg.get("parts", [])
                text_parts = [
                    p.get("text", "") for p in parts if p.get("type") == "text"
                ]
                return "\n".join(text_parts)
        return ""


# ---------------------------------------------------------------------------
# Integration with Feishu Bot
# ---------------------------------------------------------------------------


class FeishuAgentAdapter:
    """适配 Feishu Bot 的 Agent 控制器包装器"""

    def __init__(self, controller: AgentController, feishu_bot):
        self.controller = controller
        self.feishu_bot = feishu_bot

    async def execute_with_feishu_updates(
        self,
        task_text: str,
        chat_id: str,
        message_id: str,
        role_type: Optional[TaskType] = None,
    ) -> TaskResult:
        """执行任务并实时更新飞书"""

        last_update = time.time()
        update_interval = 5  # 每5秒更新一次

        def progress_callback(msg_type: str, data: Dict):
            nonlocal last_update

            current_time = time.time()
            if current_time - last_update < update_interval and msg_type != "completed":
                return

            last_update = current_time

            if msg_type == "role_selected":
                text = f"🎭 选择角色: {data['role']}"
            elif msg_type == "started":
                text = "🚀 任务开始执行..."
            elif msg_type == "progress":
                elapsed = data.get("elapsed", 0)
                tools = data.get("tools_used", 0)
                text = f"⏳ 执行中... ({elapsed}s, {tools} 个工具调用)"
            elif msg_type == "completed":
                duration = data.get("duration", 0)
                text = f"✅ 任务完成 ({duration:.1f}s)"
            else:
                return

            # 发送进度更新到飞书
            self._send_feishu_update(chat_id, message_id, text)

        result = await self.controller.execute_task(
            task_text=task_text,
            role_type=role_type,
            progress_callback=progress_callback,
        )

        return result

    def _send_feishu_update(self, chat_id: str, message_id: str, text: str):
        """发送更新到飞书（这里需要集成你的 Feishu Bot 发送逻辑）"""
        # 调用你的 feishu_bot 发送方法
        # self.feishu_bot._send_text_reply(chat_id, text)
        print(f"[Feishu] {text}")


# ---------------------------------------------------------------------------
# Example Usage
# ---------------------------------------------------------------------------


async def demo():
    """演示用法"""
    controller = AgentController(port=4096)

    # 示例任务
    tasks = [
        "修复登录页面的样式问题",
        "重构 auth 模块的错误处理",
        "分析 project.py 的代码结构",
        "为 user service 编写单元测试",
    ]

    for task in tasks:
        print(f"\n{'=' * 50}")
        print(f"任务: {task}")
        print("=" * 50)

        result = await controller.execute_task(task)

        print(f"\n结果:")
        print(f"  成功: {result.success}")
        print(f"  耗时: {result.duration_seconds:.1f}s")
        print(f"  工具调用: {len(result.tool_calls)} 次")
        if result.error:
            print(f"  错误: {result.error}")
        else:
            print(f"  内容: {result.content[:200]}...")


if __name__ == "__main__":
    # 运行演示
    asyncio.run(demo())
