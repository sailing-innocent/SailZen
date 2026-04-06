# -*- coding: utf-8 -*-
# @file opencode_message_logger.py
# @brief OpenCode Message Logger - 专门处理 OpenCode 消息日志
# @author sailing-innocent
# @date 2026-04-06
# @version 3.0
# ---------------------------------
"""OpenCode Message Logger - 精简版

关键设计：
1. 只显示有意义的消息（有文本内容、工具调用、步骤标记）
2. 空消息和心跳消息被静默处理
3. 累积统计信息，定期输出摘要

消息结构:
- info: { id, role, sessionID, time, ... }
- parts: Part[]
"""

import json
from typing import Any, Dict, List, Optional


class MessageAccumulator:
    """消息累积器 - 累积统计信息，减少日志噪音"""
    
    def __init__(self):
        self.msg_count = 0
        self.empty_count = 0
        self.text_chars = 0
        self.tool_calls = []
        self.last_summary_time = 0
        self.last_progress_line = ""
        
    def add_message(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """添加消息，返回摘要信息"""
        self.msg_count += 1
        parts = msg.get("parts", [])
        info = msg.get("info", {})
        
        result = {
            "is_empty": True,
            "text": "",
            "text_len": 0,
            "has_tool": False,
            "tool_info": None,
            "has_step": False,
            "step_info": None,
        }
        
        if not parts:
            self.empty_count += 1
            return result
        
        for part in parts:
            ptype = part.get("type", "")
            
            if ptype == "text":
                text = part.get("text", "")
                if text:
                    result["text"] += text
                    result["text_len"] += len(text)
                    result["is_empty"] = False
                    
            elif ptype == "reasoning":
                text = part.get("text", "")
                if text:
                    result["is_empty"] = False
                    
            elif ptype == "tool":
                result["is_empty"] = False
                result["has_tool"] = True
                state = part.get("state", {})
                result["tool_info"] = {
                    "name": part.get("tool", "unknown"),
                    "status": state.get("status", "unknown"),
                    "title": state.get("title", ""),
                }
                if result["tool_info"]["status"] in ("running", "completed"):
                    self.tool_calls.append(result["tool_info"]["name"])
                    
            elif ptype in ("step-start", "step-finish"):
                result["is_empty"] = False
                result["has_step"] = True
                result["step_info"] = {
                    "type": ptype,
                    "reason": part.get("reason", ""),
                    "cost": part.get("cost", 0),
                }
        
        self.text_chars += result["text_len"]
        return result
    
    def should_show_summary(self, elapsed_seconds: int) -> bool:
        """是否应该显示摘要（每5分钟一次）"""
        return elapsed_seconds > 0 and elapsed_seconds % 300 == 0 and elapsed_seconds != self.last_summary_time
    
    def get_summary(self) -> str:
        """获取累积摘要"""
        return f"msgs={self.msg_count} empty={self.empty_count} text={self.text_chars}ch tools={len(self.tool_calls)}"
    
    def update_progress(self, line: str):
        """更新进度行（用于覆盖显示）"""
        self.last_progress_line = line


class OpenCodeMessageLogger:
    """OpenCode 消息日志记录器 - 精简版"""
    
    # 每个任务一个累积器
    _accumulators: Dict[str, MessageAccumulator] = {}

    @staticmethod
    def _get_accumulator(task_id: str) -> MessageAccumulator:
        """获取或创建累积器"""
        if task_id not in OpenCodeMessageLogger._accumulators:
            OpenCodeMessageLogger._accumulators[task_id] = MessageAccumulator()
        return OpenCodeMessageLogger._accumulators[task_id]

    @staticmethod
    def log_message(task_id: str, msg: Dict[str, Any], elapsed: int = 0) -> bool:
        """
        打印消息 - 只显示有意义的内容
        
        Returns:
            True if message was displayed, False if filtered
        """
        acc = OpenCodeMessageLogger._get_accumulator(task_id)
        analysis = acc.add_message(msg)
        
        # 完全空的消息 - 静默处理
        if analysis["is_empty"]:
            return False
        
        info = msg.get("info", {})
        msg_id = info.get("id", "")[:12]
        
        # 1. 有文本内容 - 显示摘要
        if analysis["text_len"] > 0:
            text = analysis["text"]
            # 提取第一行作为摘要
            first_line = text.split('\n')[0][:80]
            if len(first_line) < len(text):
                first_line += "..."
            print(f"[{task_id[:16]}...] [TEXT] {analysis['text_len']}ch | {first_line}")
            return True
        
        # 2. 有工具调用 - 显示紧凑格式
        if analysis["has_tool"] and analysis["tool_info"]:
            tool = analysis["tool_info"]
            status_icon = {
                "pending": "?",
                "running": ">",
                "completed": "!",
                "error": "X",
            }.get(tool["status"], "?")
            title = tool["title"] or tool["name"]
            print(f"[{task_id[:16]}...] [TOOL] {status_icon} {title}")
            return True
        
        # 3. 有步骤标记 - 显示
        if analysis["has_step"] and analysis["step_info"]:
            step = analysis["step_info"]
            if step["type"] == "step-finish":
                reason = step["reason"]
                cost = step["cost"]
                print(f"[{task_id[:16]}...] [STEP] finish reason={reason} cost=${cost:.4f}")
                return True
        
        return False

    @staticmethod
    def log_progress(task_id: str, elapsed: int, status: str, 
                     tools_count: int, last_activity: str = "") -> None:
        """
        打印任务进度 - 精简单行格式
        只在特定间隔显示，减少日志污染
        """
        acc = OpenCodeMessageLogger._get_accumulator(task_id)
        
        # 转换 elapsed 为可读格式
        if elapsed < 60:
            time_str = f"{elapsed}s"
        elif elapsed < 3600:
            time_str = f"{elapsed//60}m{elapsed%60}s"
        else:
            time_str = f"{elapsed//3600}h{(elapsed%3600)//60}m"
        
        # 每5分钟或状态变化时显示
        if acc.should_show_summary(elapsed):
            summary = acc.get_summary()
            activity = f" | {last_activity}" if last_activity else ""
            print(f"[{task_id[:16]}...] [PROG] {time_str} status={status} | {summary}{activity}")
            acc.last_summary_time = elapsed

    @staticmethod
    def log_task_complete(task_id: str, final_result: str = "") -> None:
        """任务完成时打印最终摘要"""
        acc = OpenCodeMessageLogger._get_accumulator(task_id)
        summary = acc.get_summary()
        
        print(f"[{task_id[:16]}...] [DONE] {summary}")
        
        # 显示最终结果预览
        if final_result:
            preview = final_result[:200].replace('\n', ' ')
            if len(final_result) > 200:
                preview += "..."
            print(f"[{task_id[:16]}...] [RESULT] {preview}")
        
        # 清理累积器
        if task_id in OpenCodeMessageLogger._accumulators:
            del OpenCodeMessageLogger._accumulators[task_id]

    @staticmethod
    def get_accumulator(task_id: str) -> Optional[MessageAccumulator]:
        """获取累积器（供外部使用）"""
        return OpenCodeMessageLogger._accumulators.get(task_id)


# 兼容旧接口的包装函数
def log_message(task_id: str, msg: Dict[str, Any], **kwargs) -> None:
    """兼容旧接口"""
    OpenCodeMessageLogger.log_message(task_id, msg)
