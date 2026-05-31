"""Codemaker 进程管理、Agent 发现、权限自动响应。

负责：
- 为每个 task 启动独立的 codemaker serve 进程（避免不同 task 的 session/event 互相干扰）
- 在 Codemaker 中查找目标 Agent
- 对权限请求自动批准
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from cube.codemaker import CodemakerProcessManager
from cube.codemaker.client import CodemakerAsyncClient

from .base import DEFAULT_AGENT_NAME, DEFAULT_CODEMAKER_HOST, DEFAULT_CODEMAKER_PORT

logger = logging.getLogger(__name__)


AUTOMATION_CONTINUE_PROMPT = (
    "请按照流程设计继续推进任务，检查session result json是否完备，所有授权全部同意"
)
_PERMISSION_TEXT_RESPONDED: set[tuple[str, str]] = set()

async def ensure_codemaker_for_workdir(
    *,
    working_dir: str,
    codemaker_config: Dict[str, Any],
) -> Dict[str, Any]:
    """为本次 task 启动独立的 codemaker serve，并返回连接配置。

    生产 DAG task 不复用按 workdir 常驻的 codemaker 进程。复用端口会让不同 task 的
    session/event 互相干扰，尤其是上一个 session 未完全 idle/delete 时会造成重复 prompt
    或错误恢复。这里为每个 task 构造唯一的 process key，并在 task 结束后停止该进程。
    """
    if not working_dir:
        return codemaker_config

    base_port = int(codemaker_config.get("base_port") or codemaker_config.get("port") or DEFAULT_CODEMAKER_PORT)
    state_file = codemaker_config.get("state_file")
    log_dir = codemaker_config.get("log_dir")
    startup_timeout = int(codemaker_config.get("startup_timeout", 20))
    projects = codemaker_config.get("projects") or []
    task_id = str(codemaker_config.get("task_id") or "")
    task_key = str(codemaker_config.get("task_id_short") or task_id[:8] or "")
    process_key = f"{working_dir}#task-{task_key}" if task_key else working_dir

    mgr = CodemakerProcessManager(
        base_port=base_port,
        state_file=Path(state_file) if state_file else None,
        log_dir=Path(log_dir) if log_dir else None,
        startup_timeout=startup_timeout,
        projects=projects,
    )
    logger.info(
        "[CodemkrSkill] 启动 Codemaker 进程: workdir=%s process_key=%s base_port=%d startup_timeout=%ds",
        working_dir, process_key, base_port, startup_timeout,
    )
    import time as _time
    _t0 = _time.time()
    if task_key and hasattr(mgr, "ensure_running_unique_async"):
        ok, proc, msg = await mgr.ensure_running_unique_async(working_dir, process_key)
    else:
        ok, proc, msg = await mgr.ensure_running_async(working_dir)
    _elapsed = _time.time() - _t0
    if not ok:
        raise RuntimeError(f"启动 Codemaker 失败: {msg}")

    logger.info(
        "[CodemkrSkill] Codemaker ready: workdir=%s process_key=%s port=%s pid=%s elapsed=%.1fs msg=%s",
        working_dir, process_key, proc.port, proc.pid, _elapsed, msg,
    )
    return {
        **codemaker_config,
        "host": codemaker_config.get("host", DEFAULT_CODEMAKER_HOST),
        "port": proc.port,
        "working_dir": working_dir,
        "codemaker_pid": proc.pid,
        "codemaker_process_key": process_key,
        "_codemaker_process_manager": mgr,
    }


async def discover_agent(
    client: CodemakerAsyncClient,
    preferred_name: str = DEFAULT_AGENT_NAME,
) -> Optional[str]:
    """在 Codemaker 中查找目标 Agent。

    按以下优先级匹配:
      1. 精确匹配 agent name == preferred_name
      2. 包含匹配 preferred_name in agent name (忽略大小写)
      3. 返回 None (使用默认 agent)

    Returns:
        Agent 名称/ID, 或 None
    """
    try:
        agents = await client.list_agents()
        if not agents:
            logger.info("[CodemkrPick] 无可用 agent, 使用默认")
            return None

        agent_names = []
        for ag in agents:
            name = ag.get("name", "") or ag.get("id", "")
            agent_names.append(name)
            # 精确匹配
            if name == preferred_name:
                logger.info("[CodemkrPick] ✅ 找到目标 Agent: %s", name)
                return name

        # 包含匹配 (忽略大小写)
        for name in agent_names:
            if preferred_name.lower() in name.lower():
                logger.info(
                    "[CodemkrPick] ✅ 找到相似 Agent: %s (匹配 %s)",
                    name, preferred_name,
                )
                return name

        logger.warning(
            "[CodemkrPick] 未找到 Agent '%s', 可用: %s. 使用默认 Agent",
            preferred_name, agent_names,
        )
        return None
    except Exception as exc:
        logger.warning("[CodemkrPick] 列出 Agent 失败: %s, 使用默认", exc)
        return None


async def auto_respond_permission(
    client: CodemakerAsyncClient,
    session_id: str,
    permission_id: str,
    task_label: str,
) -> None:
    """自动批准权限请求。

    对于自动化任务，所有权限请求均自动批准。
    """
    if permission_id:
        # 原生 opencode permission API
        try:
            ok = await client.respond_permission(
                session_id, permission_id,
                response="always",
            )
            logger.info(
                "[CodemkrPick] %s: 🔓 自动批准权限 %s → %s",
                task_label, permission_id[:16], "ok" if ok else "failed",
            )
            if ok:
                return
        except Exception as exc:
            logger.warning(
                "[CodemkrPick] %s: 权限响应失败 (permission API): %s",
                task_label, exc,
            )

    # permission_id 为空时通常是 question/ask 这类 tool-based prompt，原生
    # permission API 没有可响应对象，只能用文本继续推进。对于同一 session 中同一类
    # pending/running 事件去重，避免同一工具状态反复触发 prompt_async 后形成新的 LLM turn，
    # 导致 DAG 既无法 BLOCK 也无法继续。
    dedupe_key = (session_id, permission_id or "tool-based-permission")
    if dedupe_key in _PERMISSION_TEXT_RESPONDED:
        logger.debug("[CodemkrPick] %s: 已发送过权限兜底文本，跳过重复确认", task_label)
        return
    _PERMISSION_TEXT_RESPONDED.add(dedupe_key)

    # 发送文本回复 (兼容 tool-based permission ask)
    try:
        await client.send_prompt_async(
            session_id, AUTOMATION_CONTINUE_PROMPT,
        )
        logger.info("[CodemkrPick] %s: 🔓 发送自动推进兜底确认", task_label)
    except Exception as exc:
        logger.warning(
            "[CodemkrPick] %s: 文本授权确认失败: %s", task_label, exc,
        )
