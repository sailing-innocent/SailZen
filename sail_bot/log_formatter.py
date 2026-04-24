# -*- coding: utf-8 -*-
# @file log_formatter.py
# @brief Unified log formatter for Feishu Bot
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------

"""统一的日志格式化器

提供一致的日志格式：
[TIME] [LEVEL] [COMPONENT] Message

示例：
[16:30:45] [INFO] [MessageHandler] From: chat_abc123
[16:30:46] [INFO] [BotBrain] Level 1 matched: send_task
[16:30:46] [INFO] [TaskHandler] Async task submitted: task_1775464865053
"""

import sys
from datetime import datetime
from typing import Optional

# 组件名称映射（用于缩短显示）
COMPONENT_SHORT = {
    "MessageHandler": "MsgHandler",
    "BotBrain": "Brain",
    "TaskHandler": "Task",
    "AsyncTaskManager": "Async",
    "OpenCode": "OpenCode",
    "SessionManager": "Session",
    "CardActionHandler": "Card",
    "PlanExecutor": "Executor",
    "SelfUpdate": "Update",
    "HealthMonitor": "Health",
}

# 日志级别颜色 (仅用于支持颜色的终端)
LEVEL_COLORS = {
    "DEBUG": "\033[36m",    # Cyan
    "INFO": "\033[32m",     # Green
    "WARN": "\033[33m",     # Yellow
    "ERROR": "\033[31m",    # Red
    "FATAL": "\033[35m",    # Magenta
    "RESET": "\033[0m",
}


def _get_timestamp() -> str:
    """获取当前时间戳"""
    return datetime.now().strftime("%H:%M:%S")


def _format_component(component: str) -> str:
    """格式化组件名称"""
    # 移除方括号如果存在
    component = component.strip("[]")
    # 尝试缩短
    return COMPONENT_SHORT.get(component, component)


def log(level: str, component: str, message: str, 
        use_color: bool = False, file: Optional[object] = None) -> None:
    """
    输出统一格式的日志
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARN, ERROR, FATAL)
        component: 组件名称
        message: 日志消息
        use_color: 是否使用颜色
        file: 输出目标（默认 sys.stdout）
    """
    timestamp = _get_timestamp()
    comp = _format_component(component)
    level = level.upper()
    
    if use_color and level in LEVEL_COLORS:
        color = LEVEL_COLORS[level]
        reset = LEVEL_COLORS["RESET"]
        output = f"{color}[{timestamp}] [{level}] [{comp}] {message}{reset}"
    else:
        output = f"[{timestamp}] [{level}] [{comp}] {message}"
    
    target = file if file else sys.stdout
    print(output, file=target)


def info(component: str, message: str) -> None:
    """输出 INFO 级别日志"""
    log("INFO", component, message)


def warn(component: str, message: str) -> None:
    """输出 WARN 级别日志"""
    log("WARN", component, message)


def error(component: str, message: str) -> None:
    """输出 ERROR 级别日志"""
    log("ERROR", component, message)


def debug(component: str, message: str) -> None:
    """输出 DEBUG 级别日志"""
    log("DEBUG", component, message)


# ===== 快捷方法 - 用于各组件 =====

def msg_handler(message: str, chat_id: str = "", level: str = "INFO") -> None:
    """MessageHandler 日志"""
    prefix = f"From: {chat_id[:16]}... " if chat_id else ""
    log(level, "MsgHandler", f"{prefix}{message}")


def brain(message: str, level: str = "INFO") -> None:
    """BotBrain 日志"""
    log(level, "Brain", message)


def task(message: str, task_id: str = "", level: str = "INFO") -> None:
    """TaskHandler 日志"""
    prefix = f"{task_id[:20]}... " if task_id else ""
    log(level, "Task", f"{prefix}{message}")


def async_mgr(message: str, task_id: str = "", level: str = "INFO") -> None:
    """AsyncTaskManager 日志"""
    prefix = f"{task_id[:16]}... " if task_id else ""
    log(level, "Async", f"{prefix}{message}")


def opencode(message: str, level: str = "INFO") -> None:
    """OpenCode 相关日志"""
    log(level, "OpenCode", message)


def session(message: str, level: str = "INFO") -> None:
    """SessionManager 日志"""
    log(level, "Session", message)


# ===== 任务进度专用日志 =====

def task_progress(task_id: str, action: str, detail: str = "") -> None:
    """
    任务进度日志
    
    Args:
        task_id: 任务ID
        action: 动作 (started, running, completed, failed, cancelled)
        detail: 详细信息
    """
    action_icons = {
        "started": "[+]",
        "running": "[~]",
        "completed": "[DONE]",
        "failed": "[FAIL]",
        "cancelled": "[-]",
        "tool": "[T]",
        "message": "[M]",
    }
    icon = action_icons.get(action, "[*]")
    suffix = f" | {detail}" if detail else ""
    log("INFO", "Async", f"{icon} {task_id[:16]}...{suffix}")


def task_status(task_id: str, status: str, elapsed: int, 
                last_activity: str = "", extra: str = "") -> None:
    """
    任务状态报告（用于长时间运行的任务）
    
    Args:
        task_id: 任务ID
        status: 当前状态
        elapsed: 已运行秒数
        last_activity: 最后活动描述
        extra: 额外信息
    """
    elapsed_str = f"{elapsed//60}m{elapsed%60}s" if elapsed >= 60 else f"{elapsed}s"
    activity = f" | last: {last_activity}" if last_activity else ""
    extra_str = f" | {extra}" if extra else ""
    
    log("INFO", "Async", 
        f"[~] {task_id[:16]}... status={status} elapsed={elapsed_str}{activity}{extra_str}")


# ===== 消息内容专用日志 =====

def user_message(text: str, chat_id: str = "") -> None:
    """
    打印用户消息（带边框）
    """
    print()  # 空行
    print("=" * 70)
    if chat_id:
        print(f"[USER] Chat: {chat_id}")
    print(f"{text}")
    print("=" * 70)


def ai_response(content: str, task_id: str = "", msg_id: str = "") -> None:
    """
    打印 AI 响应（简洁格式）
    """
    prefix = f"[{task_id[:16]}...] " if task_id else ""
    lines = content.strip().split('\n')
    
    print(f"{prefix}[AI] Response ({len(content)} chars):")
    print("-" * 60)
    
    # 显示前10行或前500字符
    preview = []
    length = 0
    for line in lines[:15]:
        if length + len(line) > 500:
            break
        preview.append(line)
        length += len(line) + 1
    
    print('\n'.join(preview))
    
    if len(lines) > 15 or length < len(content):
        remaining_lines = len(lines) - 15
        remaining_chars = len(content) - length
        if remaining_lines > 0:
            print(f"... ({remaining_lines} more lines, {remaining_chars} chars)")
        else:
            print(f"... ({remaining_chars} more chars)")
    
    print("-" * 60)
