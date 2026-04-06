# -*- coding: utf-8 -*-
# @file opencode_message_logger.py
# @brief OpenCode Message Logger - 专门处理 OpenCode 消息日志
# @author sailing-innocent
# @date 2026-04-06
# @version 2.0
# ---------------------------------
"""OpenCode Message Logger

根据 OpenCode 源码 message-v2.ts 的消息格式，提供结构化的消息日志输出。

消息结构:
- info: { id, role, sessionID, time, ... }
- parts: Part[]

关键发现:
1. OpenCode 会发送大量空 parts 的 assistant 消息作为占位符/心跳
2. 实际内容通过后续的 parts 填充或更新
3. 需要追踪消息序列才能看到完整对话流程
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime


class MessageSequenceTracker:
    """消息序列追踪器 - 跟踪消息间的关联关系"""
    
    def __init__(self):
        self._messages: Dict[str, Dict[str, Any]] = {}  # msg_id -> message
        self._sequences: Dict[str, List[str]] = {}  # parent_id -> [child_ids]
        self._assistant_chains: Dict[str, List[str]] = {}  # user_msg_id -> [assistant_msg_ids]
        self._content_accumulator: Dict[str, str] = {}  # msg_id -> accumulated text
        
    def add_message(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """添加消息到追踪器，返回分析结果"""
        info = msg.get("info", {})
        msg_id = info.get("id", "")
        parent_id = info.get("parentID", "")
        role = info.get("role", "unknown")
        parts = msg.get("parts", [])
        
        if not msg_id:
            return {"is_new": False, "has_content": False}
        
        # 存储消息
        is_new = msg_id not in self._messages
        self._messages[msg_id] = msg
        
        # 建立父子关系
        if parent_id:
            if parent_id not in self._sequences:
                self._sequences[parent_id] = []
            if msg_id not in self._sequences[parent_id]:
                self._sequences[parent_id].append(msg_id)
        
        # 如果是 assistant 消息，尝试关联到用户消息链
        if role == "assistant" and parent_id:
            if parent_id not in self._assistant_chains:
                self._assistant_chains[parent_id] = []
            if msg_id not in self._assistant_chains[parent_id]:
                self._assistant_chains[parent_id].append(msg_id)
        
        # 提取并累积内容
        has_content = False
        current_text = ""
        for part in parts:
            if part.get("type") == "text":
                text = part.get("text", "")
                if text:
                    current_text += text
                    has_content = True
        
        # 累积到父链
        if parent_id and parent_id in self._assistant_chains:
            if parent_id not in self._content_accumulator:
                self._content_accumulator[parent_id] = ""
            self._content_accumulator[parent_id] += current_text
        
        return {
            "is_new": is_new,
            "has_content": has_content,
            "text_length": len(current_text),
            "accumulated_length": len(self._content_accumulator.get(parent_id, "")),
            "chain_position": self._get_chain_position(parent_id, msg_id) if parent_id else None,
        }
    
    def _get_chain_position(self, parent_id: str, msg_id: str) -> Optional[int]:
        """获取消息在链中的位置"""
        if parent_id in self._assistant_chains:
            try:
                return self._assistant_chains[parent_id].index(msg_id) + 1
            except ValueError:
                return None
        return None
    
    def get_chain_info(self, parent_id: str) -> Dict[str, Any]:
        """获取消息链的信息"""
        if parent_id not in self._assistant_chains:
            return {"count": 0, "content": ""}
        
        chain = self._assistant_chains[parent_id]
        total_parts = 0
        total_text = ""
        
        for msg_id in chain:
            msg = self._messages.get(msg_id, {})
            parts = msg.get("parts", [])
            for part in parts:
                if part.get("type") == "text":
                    total_text += part.get("text", "")
                total_parts += 1
        
        return {
            "count": len(chain),
            "parts": total_parts,
            "content_length": len(total_text),
            "content_preview": total_text[:200] + "..." if len(total_text) > 200 else total_text,
        }
    
    def get_message_tree(self, root_id: str, max_depth: int = 3) -> str:
        """获取消息树的字符串表示"""
        lines = []
        self._build_tree_recursive(root_id, 0, max_depth, lines, set())
        return "\n".join(lines)
    
    def _build_tree_recursive(self, msg_id: str, depth: int, max_depth: int, lines: List[str], visited: set):
        """递归构建消息树"""
        if depth > max_depth or msg_id in visited:
            return
        visited.add(msg_id)
        
        msg = self._messages.get(msg_id, {})
        info = msg.get("info", {})
        role = info.get("role", "?")
        parts_count = len(msg.get("parts", []))
        
        indent = "  " * depth
        icon = "[U]" if role == "user" else "[A]"
        parts_info = f"[{parts_count}p]" if parts_count > 0 else "[empty]"
        lines.append(f"{indent}{icon} {msg_id[:16]}... {parts_info}")
        
        # 递归子消息
        if msg_id in self._sequences:
            for child_id in self._sequences[msg_id]:
                self._build_tree_recursive(child_id, depth + 1, max_depth, lines, visited)


# 全局追踪器实例
_sequence_tracker = MessageSequenceTracker()


class OpenCodeMessageLogger:
    """OpenCode 消息日志记录器 - 增强版，提供 TUI 级别的信息量"""

    @staticmethod
    def log_message(task_id: str, msg: Dict[str, Any], show_empty: bool = False) -> None:
        """
        打印消息内容 - 智能过滤空消息，展示消息序列关系
        
        Args:
            task_id: 任务ID
            msg: OpenCode 消息字典
            show_empty: 是否显示空消息（默认只显示有内容的消息）
        """
        info = msg.get("info", {})
        parts = msg.get("parts", [])
        role = info.get("role", "unknown")
        msg_id = info.get("id", "unknown")
        parent_id = info.get("parentID", "")
        
        # 添加到追踪器
        analysis = _sequence_tracker.add_message(msg)
        
        # 决定如何显示这条消息
        has_parts = len(parts) > 0
        has_text_content = any(
            p.get("type") == "text" and p.get("text") 
            for p in parts
        )
        
        # 提取工具调用信息
        tool_info = OpenCodeMessageLogger._extract_tool_info(parts)
        has_tool = tool_info is not None
        
        # 提取步骤信息
        step_info = OpenCodeMessageLogger._extract_step_info(parts)
        
        # === 智能显示逻辑 ===
        
        # 1. 有文本内容 - 完整显示
        if has_text_content:
            OpenCodeMessageLogger._log_full_message(task_id, msg, analysis)
            return
        
        # 2. 有工具调用 - 显示工具信息
        if has_tool:
            OpenCodeMessageLogger._log_tool_compact(task_id, msg, tool_info)
            return
        
        # 3. 有步骤标记 (step-start/finish) - 显示步骤信息
        if step_info:
            OpenCodeMessageLogger._log_step_compact(task_id, msg, step_info)
            return
        
        # 4. 空消息 - 简洁显示或跳过
        if not show_empty:
            # 只在特定情况下显示空消息（如链中的第一条或重要状态变更）
            if analysis.get("chain_position") == 1:
                print(f"[{task_id[:20]}] [AI] Assistant responding... (parent: {parent_id[:16]}...)")
            return
        
        # 显示空消息详情
        OpenCodeMessageLogger._log_empty_message(task_id, msg, analysis)

    @staticmethod
    def _extract_tool_info(parts: List[Dict]) -> Optional[Dict[str, Any]]:
        """提取工具调用信息"""
        for part in parts:
            if part.get("type") == "tool":
                state = part.get("state", {})
                return {
                    "tool": part.get("tool", "unknown"),
                    "status": state.get("status", "unknown"),
                    "title": state.get("title", ""),
                    "call_id": part.get("callID", ""),
                }
        return None

    @staticmethod
    def _extract_step_info(parts: List[Dict]) -> Optional[Dict[str, Any]]:
        """提取步骤信息"""
        for part in parts:
            ptype = part.get("type", "")
            if ptype == "step-start":
                return {"type": "start", "snapshot": part.get("snapshot", "")}
            elif ptype == "step-finish":
                return {
                    "type": "finish",
                    "reason": part.get("reason", ""),
                    "cost": part.get("cost", 0),
                    "tokens": part.get("tokens", {}),
                }
        return None

    @staticmethod
    def _log_full_message(task_id: str, msg: Dict[str, Any], analysis: Dict[str, Any]) -> None:
        """显示完整消息（有文本内容）"""
        info = msg.get("info", {})
        parts = msg.get("parts", [])
        msg_id = info.get("id", "")[:16]
        parent_id = info.get("parentID", "")[:16]
        
        # 收集所有文本
        texts = []
        for part in parts:
            if part.get("type") == "text":
                text = part.get("text", "")
                if text:
                    texts.append(text)
        
        content = "".join(texts)
        chain_pos = analysis.get("chain_position", "?")
        
        print(f"\n{'='*70}")
        print(f"[{task_id[:20]}] [AI] Response #{chain_pos} | {msg_id}...")
        if parent_id:
            print(f"  Parent: {parent_id}...")
        print(f"  Content ({len(content)} chars):")
        print(f"  {'-'*60}")
        # 智能截断长内容
        if len(content) > 500:
            print(content[:500])
            print(f"  ... ({len(content) - 500} more chars)")
        else:
            print(content)
        print(f"  {'-'*60}")
        
        # 如果有其他 part 类型，显示统计
        other_types = [p.get("type") for p in parts if p.get("type") != "text"]
        if other_types:
            print(f"  Other parts: {', '.join(set(other_types))}")

    @staticmethod
    def _log_tool_compact(task_id: str, msg: Dict[str, Any], tool_info: Dict[str, Any]) -> None:
        """紧凑显示工具调用"""
        status_icons = {
            "pending": "[PEND]",
            "running": "[RUN]",
            "completed": "[DONE]",
            "error": "[ERR]",
        }
        icon = status_icons.get(tool_info["status"], "❓")
        title = tool_info["title"] or tool_info["tool"]
        print(f"[{task_id[:20]}] {icon} {title} ({tool_info['status']})")

    @staticmethod
    def _log_step_compact(task_id: str, msg: Dict[str, Any], step_info: Dict[str, Any]) -> None:
        """紧凑显示步骤信息"""
        if step_info["type"] == "start":
            snapshot = step_info["snapshot"][:20] + "..." if step_info["snapshot"] else "N/A"
            print(f"[{task_id[:20]}] [START] Step (snapshot: {snapshot})")
        elif step_info["type"] == "finish":
            reason = step_info["reason"]
            cost = step_info["cost"]
            tokens = step_info["tokens"]
            total_tokens = tokens.get("input", 0) + tokens.get("output", 0) + tokens.get("reasoning", 0)
            print(f"[{task_id[:20]}] [FINISH] Step | reason={reason} | cost=${cost:.4f} | tokens={total_tokens}")

    @staticmethod
    def _log_empty_message(task_id: str, msg: Dict[str, Any], analysis: Dict[str, Any]) -> None:
        """显示空消息详情（调试模式）"""
        info = msg.get("info", {})
        msg_id = info.get("id", "")[:16]
        parent_id = info.get("parentID", "")[:16]
        agent = info.get("agent", "unknown")
        model = info.get("modelID", "unknown")
        
        print(f"\n[{task_id[:20]}] [EMPTY] msg | {msg_id}... | parent: {parent_id}...")
        print(f"  Agent: {agent} | Model: {model}")
        
        # 显示链信息
        if parent_id:
            chain_info = _sequence_tracker.get_chain_info(parent_id)
            if chain_info["count"] > 0:
                print(f"  Chain: {chain_info['count']} msgs, {chain_info['parts']} parts, {chain_info['content_length']} chars")

    @staticmethod
    def log_message_tree(task_id: str, root_msg_id: str) -> None:
        """打印消息树结构"""
        print(f"\n{'='*70}")
        print(f"[Message Tree] Task: {task_id}")
        print(f"{'='*70}")
        tree = _sequence_tracker.get_message_tree(root_msg_id)
        print(tree)
        print(f"{'='*70}")

    @staticmethod
    def log_session_summary(task_id: str) -> None:
        """打印会话摘要"""
        print(f"\n{'='*70}")
        print(f"[Session Summary] Task: {task_id}")
        print(f"{'='*70}")
        
        total_msgs = len(_sequence_tracker._messages)
        total_chains = len(_sequence_tracker._assistant_chains)
        
        print(f"Total messages: {total_msgs}")
        print(f"Total chains: {total_chains}")
        
        # 统计各角色消息
        role_counts = {}
        empty_count = 0
        content_count = 0
        
        for msg_id, msg in _sequence_tracker._messages.items():
            info = msg.get("info", {})
            role = info.get("role", "unknown")
            role_counts[role] = role_counts.get(role, 0) + 1
            
            parts = msg.get("parts", [])
            if not parts:
                empty_count += 1
            else:
                has_content = any(
                    p.get("type") == "text" and p.get("text")
                    for p in parts
                )
                if has_content:
                    content_count += 1
        
        print(f"\nBy role: {role_counts}")
        print(f"Empty messages: {empty_count}")
        print(f"Messages with content: {content_count}")
        print(f"{'='*70}")

    # === 兼容旧接口 ===
    
    @staticmethod
    def _log_part(part: Dict[str, Any]) -> None:
        """打印单个 part 的详细内容（兼容旧接口）"""
        ptype = part.get("type", "unknown")
        
        if ptype == "text":
            OpenCodeMessageLogger._log_text_part(part)
        elif ptype == "reasoning":
            OpenCodeMessageLogger._log_reasoning_part(part)
        elif ptype == "tool":
            OpenCodeMessageLogger._log_tool_part(part)
        elif ptype == "step-start":
            snapshot = part.get("snapshot", "")
            print(f"  Type: step-start")
            print(f"  Snapshot: {snapshot[:50] if snapshot else 'N/A'}")
        elif ptype == "step-finish":
            OpenCodeMessageLogger._log_step_finish_part(part)
        elif ptype == "file":
            OpenCodeMessageLogger._log_file_part(part)
        else:
            print(f"  Type: {ptype}")
            print(f"  Data: {json.dumps(part, ensure_ascii=False, indent=2)[:300]}")

    @staticmethod
    def _log_text_part(part: Dict[str, Any]) -> None:
        """打印 text part"""
        text = part.get("text", "")
        print(f"  Type: text ({len(text)} chars)")
        if part.get("synthetic"):
            print(f"  [synthetic]")
        if text:
            print(f"  {'-'*40}")
            print(text[:500])
            if len(text) > 500:
                print(f"  ... ({len(text) - 500} more)")
            print(f"  {'-'*40}")

    @staticmethod
    def _log_reasoning_part(part: Dict[str, Any]) -> None:
        """打印 reasoning part"""
        text = part.get("text", "")
        print(f"  Type: reasoning ({len(text)} chars)")
        if text:
            print(f"  {'-'*40}")
            print(text[:300])
            if len(text) > 300:
                print(f"  ...")
            print(f"  {'-'*40}")

    @staticmethod
    def _log_tool_part(part: Dict[str, Any]) -> None:
        """打印 tool part"""
        tool_name = part.get("tool", "unknown")
        call_id = part.get("callID", "unknown")[:8]
        state = part.get("state", {})
        status = state.get("status", "unknown")
        
        print(f"  Type: tool | {tool_name} | {status}")
        
        if status == "running":
            title = state.get("title", "")
            if title:
                print(f"  Title: {title}")
        elif status == "completed":
            title = state.get("title", "")
            output = state.get("output", "")
            print(f"  Title: {title}")
            if output:
                print(f"  Output ({len(output)} chars):")
                print(f"  {'-'*40}")
                print(output[:300])
                if len(output) > 300:
                    print(f"  ...")
                print(f"  {'-'*40}")
        elif status == "error":
            error = state.get("error", "Unknown error")
            print(f"  Error: {error}")

    @staticmethod
    def _log_step_finish_part(part: Dict[str, Any]) -> None:
        """打印 step-finish part"""
        reason = part.get("reason", "")
        cost = part.get("cost", 0)
        tokens = part.get("tokens", {})
        
        print(f"  Type: step-finish")
        print(f"  Reason: {reason}")
        print(f"  Cost: ${cost:.4f}")
        print(f"  Tokens: in={tokens.get('input', 0)}, out={tokens.get('output', 0)}, reasoning={tokens.get('reasoning', 0)}")

    @staticmethod
    def _log_file_part(part: Dict[str, Any]) -> None:
        """打印 file part"""
        print(f"  Type: file")
        print(f"  Mime: {part.get('mime', 'unknown')}")
        print(f"  Filename: {part.get('filename', 'unnamed')}")

    @staticmethod
    def log_summary(task_id: str, messages: List[Dict[str, Any]]) -> None:
        """打印消息列表摘要（兼容旧接口）"""
        if not messages:
            return
            
        print(f"\n[SUMMARY] Task: {task_id}")
        print(f"  Total messages: {len(messages)}")
        
        # 统计各类型 part
        part_counts = {}
        tool_counts = {}
        total_cost = 0
        
        for msg in messages:
            for part in msg.get("parts", []):
                ptype = part.get("type", "unknown")
                part_counts[ptype] = part_counts.get(ptype, 0) + 1
                
                if ptype == "tool":
                    tool_name = part.get("tool", "unknown")
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                elif ptype == "step-finish":
                    total_cost += part.get("cost", 0)
        
        print(f"  Part types:")
        for ptype, count in sorted(part_counts.items()):
            print(f"    {ptype}: {count}")
        
        if tool_counts:
            print(f"  Tool calls:")
            for tool, count in sorted(tool_counts.items()):
                print(f"    {tool}: {count}")
        
        if total_cost > 0:
            print(f"  Total cost: ${total_cost:.4f}")
