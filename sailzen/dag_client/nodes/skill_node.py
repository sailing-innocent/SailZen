# -*- coding: utf-8 -*-
# @file skill_node.py
# @brief Skill 调用节点
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""通过 OpenCode 协议调用 Skill 的节点执行器。

参数::

    {
        "skill": "skill-name",           # 必需
        "prompt": "...",                 # 发送给 skill 的提示
        "session_id": "...",             # 可选，复用已有 session
        "agent": "default",              # 可选，指定 agent
        "model": "kimi-k2.5",            # 可选，指定模型
        "timeout": 3600,                 # 可选，覆盖默认超时
        "auto_respond_permissions": true # 可选，自动响应权限请求
    }
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


class SkillNode(NodeExecutor):
    """调用 OpenCode Skill 的节点。"""

    node_type = "skill"

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        if not params.get("skill"):
            return "Missing required param: skill"
        return None

    def required_skills(self, params: Dict[str, Any]) -> List[str]:
        skill = params.get("skill", "")
        return [skill] if skill else []

    async def execute(self, ctx: NodeContext) -> NodeResult:
        skill_name = ctx.params.get("skill")
        prompt = ctx.params.get("prompt", f"Execute skill: {skill_name}")
        session_id = ctx.params.get("session_id")
        agent = ctx.params.get("agent")
        model = ctx.params.get("model")
        timeout = ctx.params.get("timeout", 3600)
        auto_respond = ctx.params.get("auto_respond_permissions", True)

        client = ctx.opencode_client
        if not client:
            return NodeResult.fail("OpenCode client not available")

        try:
            # 创建或复用 session
            if session_id:
                try:
                    await client.get_session(session_id)
                except Exception:
                    logger.info("Session %s not found, creating new", session_id)
                    session = await client.create_session(title=f"dag-{ctx.run_id}-{ctx.node_id}")
                    session_id = session.id
            else:
                session = await client.create_session(title=f"dag-{ctx.run_id}-{ctx.node_id}")
                session_id = session.id

            # 发送 prompt
            logger.info("SkillNode %s: sending prompt to session %s", ctx.node_id, session_id)
            await client.send_prompt_async(session_id, prompt, agent=agent, model=model)

            # 监听 SSE 事件
            output_parts: List[str] = []
            final_data: Dict[str, Any] = {}
            permission_tasks: List[asyncio.Task] = []

            async for event in client.stream_events_robust(session_id, timeout=timeout):
                if event.event == "__reconnected__":
                    continue
                data = event.json()
                if not data:
                    continue

                event_type = data.get("type", "")
                if event_type == "text":
                    text = data.get("text", "")
                    output_parts.append(text)
                elif event_type == "tool":
                    tool_state = data.get("state", {})
                    if tool_state.get("status") == "success":
                        final_data.update(tool_state.get("result", {}))
                elif event_type == "step-finish":
                    reason = data.get("reason", "")
                    if reason == "completed":
                        break
                    elif reason in ("error", "aborted"):
                        return NodeResult.fail(f"Session ended with reason: {reason}")
                elif event_type == "permission" and auto_respond:
                    perm_id = data.get("permission_id", "")
                    if perm_id:
                        task = asyncio.create_task(
                            client.respond_permission(session_id, perm_id, response="always")
                        )
                        permission_tasks.append(task)

            # 等待所有权限响应任务
            if permission_tasks:
                await asyncio.gather(*permission_tasks, return_exceptions=True)

            output_text = "".join(output_parts)

            # 保存产物
            artifact_path = None
            if ctx.store:
                artifact_path = ctx.store.save_artifact(
                    ctx.run_id, f"{ctx.node_id}_output.txt", output_text
                )

            return NodeResult.ok(
                data={"session_id": session_id, "skill": skill_name, "result": final_data},
                output=output_text,
                artifacts=[str(artifact_path)] if artifact_path else [],
            )

        except asyncio.TimeoutError:
            return NodeResult.fail(f"Skill execution timeout after {timeout}s")
        except Exception as exc:
            logger.exception("SkillNode execute error")
            return NodeResult.fail(str(exc))
