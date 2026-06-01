"""Codemaker session transcript collection and archive helpers."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from sail.opencode.client import OpencodeAsyncClient

logger = logging.getLogger(__name__)


async def collect_session_transcript_tree(
    client: OpencodeAsyncClient,
    session_id: str,
    task_label: str,
    *,
    max_depth: int = 8,
) -> Dict[str, Any]:
    """递归拉取一个 CodeMaker session 及其 subagent 子 session 的完整消息。

    CodeMaker 的主 session 在处理复杂任务时会通过 task/subagent 打开子
    session。主 session 的 `/message` 只包含父会话消息，不会内联子会话
    transcript；因此归档时需要先查询 `/session/{id}/children`，再对每个
    子 session 递归拉取 `/message` 和下一层 children。
    """
    visited: set[str] = set()

    async def _collect(
        current_id: str,
        depth: int,
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        node: Dict[str, Any] = {
            "session_id": current_id,
            "parent_id": parent_id,
            "depth": depth,
            "messages": [],
            "children": [],
            "errors": [],
        }
        if current_id in visited:
            node["errors"].append("cycle detected; session already collected")
            return node
        visited.add(current_id)

        try:
            node["messages"] = await client.get_session_transcript(
                current_id,
                limit=0,
            )
        except Exception as exc:
            logger.warning(
                "[CodemkrSkill] %s: 获取 transcript 失败 session=%s: %s",
                task_label,
                current_id,
                exc,
            )
            node["errors"].append(f"get_session_transcript failed: {exc}")

        if depth >= max_depth:
            node["errors"].append(
                f"max_depth={max_depth} reached; children not collected"
            )
            return node

        try:
            children_meta = await client.get_session_children(current_id)
        except Exception as exc:
            logger.warning(
                "[CodemkrSkill] %s: 获取子 session 失败 session=%s: %s",
                task_label,
                current_id,
                exc,
            )
            node["errors"].append(f"get_session_children failed: {exc}")
            children_meta = []

        for child_meta in children_meta:
            child_id = str(child_meta.get("id") or "")
            if not child_id:
                continue
            child_node = await _collect(child_id, depth + 1, current_id)
            child_node["session"] = child_meta
            node["children"].append(child_node)

        return node

    return await _collect(session_id, 0)


def summarize_transcript_tree(root: Dict[str, Any]) -> Dict[str, Any]:
    """汇总 session tree 的消息、费用、tokens、工具和子 session 数量。"""
    total_sessions = 0
    total_messages = 0
    total_cost = 0.0
    total_tokens_in = 0
    total_tokens_out = 0
    tool_names: list[str] = []
    errors: list[Dict[str, Any]] = []

    def _walk(node: Dict[str, Any]) -> None:
        nonlocal total_sessions, total_messages, total_cost
        nonlocal total_tokens_in, total_tokens_out
        total_sessions += 1
        messages = node.get("messages") or []
        total_messages += len(messages)
        for msg in messages:
            info = msg.get("info", msg) if isinstance(msg, dict) else {}
            if info.get("role") == "assistant":
                total_cost += float(info.get("cost", 0) or 0)
                tokens = info.get("tokens", {}) or {}
                total_tokens_in += int(tokens.get("input", 0) or 0)
                total_tokens_out += int(tokens.get("output", 0) or 0)
            for part in msg.get("parts", []) if isinstance(msg, dict) else []:
                if part.get("type") != "tool":
                    continue
                state = part.get("state", {}) or {}
                title = state.get("title", "") or part.get("tool", "")
                if title and state.get("status") == "completed":
                    tool_names.append(title)
        if node.get("errors"):
            errors.append({
                "session_id": node.get("session_id"),
                "errors": node.get("errors"),
            })
        for child in node.get("children") or []:
            _walk(child)

    _walk(root)
    return {
        "session_count": total_sessions,
        "subagent_session_count": max(0, total_sessions - 1),
        "message_count": total_messages,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens_input": total_tokens_in,
        "total_tokens_output": total_tokens_out,
        "completed_tools": tool_names,
        "errors": errors,
    }


async def archive_session_transcript(
    client: OpencodeAsyncClient,
    session_id: str,
    task_label: str,
    task_id: str = "",
    task_type: str = "",
    transcript_dir: str = "transcripts",
) -> Optional[str]:
    """会话结束后拉取完整 transcript 并保存到文件留档。

    文件保存在 transcript_dir 下，命名格式：
        {task_type}_{task_id_short}_{session_id_short}.json

    对应 CodeMaker GET /session/{id}/message 和
    GET /session/{id}/children 接口。归档对象包含根 session 的
    messages 字段，以及递归 children 树，确保 subagent 子会话也被留档。

    Returns:
        保存的文件路径，失败时返回 None。
    """
    root = await collect_session_transcript_tree(client, session_id, task_label)
    if not root.get("messages") and not root.get("children"):
        logger.info("[CodemkrSkill] %s: transcript: (empty session tree)", task_label)
        return None

    summary = summarize_transcript_tree(root)
    archive = {
        "task_label": task_label,
        "task_id": task_id,
        "task_type": task_type,
        "session_id": session_id,
        "archived_at": datetime.utcnow().isoformat() + "Z",
        "summary": summary,
        "messages": root.get("messages", []),
        "children": root.get("children", []),
        "session_tree": root,
    }

    os.makedirs(transcript_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_type = (task_type or "task").replace("/", "-")
    task_short = (task_id or "")[:8]
    session_short = (session_id or "")[:12]
    filename = f"{timestamp}_{safe_type}_{task_short}_{session_short}.json"
    filepath = os.path.join(transcript_dir, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(archive, file, ensure_ascii=False, indent=2)
        logger.info(
            "[CodemkrSkill] %s: transcript saved -> %s "
            "(sessions=%d subagents=%d msgs=%d cost=$%.4f "
            "tokens=[in=%d out=%d] tools=%d errors=%d)",
            task_label,
            filepath,
            summary["session_count"],
            summary["subagent_session_count"],
            summary["message_count"],
            summary["total_cost_usd"],
            summary["total_tokens_input"],
            summary["total_tokens_output"],
            len(summary["completed_tools"]),
            len(summary["errors"]),
        )
        return filepath
    except Exception as exc:
        logger.warning("[CodemkrSkill] %s: transcript 写入失败: %s", task_label, exc)
        return None
