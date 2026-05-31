"""CubeClaw CommandBus — 统一交互层。

所有操作（Dashboard / IM / Bot 自动化）最终归结为 Command，
由 CommandBus 统一调度、权限检查、执行并产生 Event。

权限模型:
  ADMIN > OPERATOR > REVIEWER > VIEWER > BOT

  Dashboard  = ADMIN（全量管理）
  IM User  = OPERATOR / REVIEWER（按用户配置）
  Bot 自动化 = BOT（可被打断，需 auto_run 开关）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── 权限等级 ────────────────────────────────────────────────────────


class Role(IntEnum):
    """权限等级，数值越大权限越高。"""

    BOT = 0
    VIEWER = 10
    REVIEWER = 20
    OPERATOR = 30
    ADMIN = 40


# 来源标识
class Source:
    DASHBOARD = "dashboard"
    IM = "IM"
    BOT = "bot"
    SYSTEM = "system"  # 内部调度


# ── Command ─────────────────────────────────────────────────────────


@dataclass
class Command:
    """统一命令对象。"""

    name: str  # 命令名，如 "status", "retry_task", "create_batch"
    args: Dict[str, Any] = field(default_factory=dict)
    source: str = Source.SYSTEM  # 来源: dashboard / IM / bot / system
    actor: str = "system"  # 执行者标识（user_id / "dashboard" / "bot"）
    role: Role = Role.VIEWER  # 执行者权限
    reply_to: Optional[str] = None  # IM 回复目标 (chat_id / group_id)

    @property
    def required_role(self) -> Role:
        """根据命令名推断所需最低权限。"""
        return _COMMAND_ROLES.get(self.name, Role.VIEWER)

    def has_permission(self) -> bool:
        return self.role >= self.required_role


# ── 命令权限映射 ────────────────────────────────────────────────────

_COMMAND_ROLES: Dict[str, Role] = {
    # 查询类 — VIEWER
    "status": Role.VIEWER,
    "list_projects": Role.VIEWER,
    "get_project": Role.VIEWER,
    "list_workspaces": Role.VIEWER,
    "list_batches": Role.VIEWER,
    "get_batch": Role.VIEWER,
    "list_sub_batches": Role.VIEWER,
    "get_sub_batch": Role.VIEWER,
    "list_tasks": Role.VIEWER,
    "get_task": Role.VIEWER,
    "list_agents": Role.VIEWER,
    "list_events": Role.VIEWER,
    "blocked": Role.VIEWER,
    "health": Role.VIEWER,
    "pipeline_definitions": Role.VIEWER,
    "list_pipeline_runs": Role.VIEWER,
    "get_pipeline_run": Role.VIEWER,
    # 操作类 — OPERATOR
    "retry_task": Role.OPERATOR,
    "pause": Role.OPERATOR,
    "resume": Role.OPERATOR,
    "create_batch": Role.OPERATOR,
    "schedule_batch": Role.OPERATOR,
    "start_pipeline_run": Role.OPERATOR,
    "resume_pipeline_from_node": Role.OPERATOR,
    "manual_block_node": Role.OPERATOR,
    "manual_success_node": Role.OPERATOR,
    "cancel_pipeline_run": Role.OPERATOR,
    "assign_task": Role.OPERATOR,
    "heartbeat": Role.OPERATOR,
    "register_agent": Role.OPERATOR,
    # 审批类 — REVIEWER
    "resolve_task": Role.REVIEWER,
    "skip_task": Role.REVIEWER,
    "approve_batch": Role.REVIEWER,
    "complete_task": Role.REVIEWER,
    # 管理类 — ADMIN
    "create_project": Role.ADMIN,
    "create_workspace": Role.ADMIN,
    "delete_batch": Role.ADMIN,
    "config_set": Role.ADMIN,
    "maintenance_agent": Role.ADMIN,
    "IM_manage": Role.ADMIN,
    # Codemaker 会话 — OPERATOR
    "cm_start": Role.OPERATOR,
    "cm_stop": Role.OPERATOR,
    "cm_status": Role.VIEWER,
    "cm_send_task": Role.OPERATOR,
    "cm_list": Role.VIEWER,
    # 系统 — BOT 级别（自动化可调用）
    "auto_schedule": Role.BOT,
    "auto_complete_task": Role.BOT,
}


# ── CommandResult ───────────────────────────────────────────────────


@dataclass
class CommandResult:
    """命令执行结果。"""

    success: bool
    data: Any = None
    error: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)

    # 方便 IM 回复的文本摘要
    text: Optional[str] = None

    @staticmethod
    def ok(data: Any = None, text: str = "", events: list = None) -> CommandResult:
        return CommandResult(success=True, data=data, text=text, events=events or [])

    @staticmethod
    def fail(error: str, data: Any = None) -> CommandResult:
        return CommandResult(success=False, error=error, data=data, text=f"❌ {error}")

    @staticmethod
    def permission_denied(cmd: Command) -> CommandResult:
        return CommandResult(
            success=False,
            error=f"权限不足: {cmd.name} 需要 {cmd.required_role.name}, 当前 {cmd.role.name}",
            text=f"⛔ 权限不足: {cmd.name} 需要 {cmd.required_role.name} 权限",
        )


# ── Handler 类型 ────────────────────────────────────────────────────

# Handler 签名: async (Command) -> CommandResult
CommandHandler = Callable[[Command], Any]  # 实际是 async callable


# ── CommandBus ──────────────────────────────────────────────────────


class CommandBus:
    """统一命令总线。

    Usage::

        bus = CommandBus()
        bus.register("status", handle_status)
        result = await bus.dispatch(Command("status", source="dashboard", role=Role.ADMIN))
    """

    def __init__(self):
        self._handlers: Dict[str, CommandHandler] = {}
        self._middlewares: List[Callable] = []
        self._event_callback: Optional[Callable] = None
        self._auto_run_enabled: bool = False  # Bot 自动化开关

    # ── 注册 ────────────────────────────────────────────────────────

    def register(self, name: str, handler: CommandHandler) -> None:
        """注册命令处理器。"""
        self._handlers[name] = handler
        logger.debug("CommandBus: registered handler for '%s'", name)

    def register_many(self, handlers: Dict[str, CommandHandler]) -> None:
        """批量注册。"""
        for name, handler in handlers.items():
            self.register(name, handler)

    def on_events(self, callback: Callable) -> None:
        """设置事件回调（EventBus 会监听此回调）。"""
        self._event_callback = callback

    # ── 自动化开关 ──────────────────────────────────────────────────

    @property
    def auto_run_enabled(self) -> bool:
        return self._auto_run_enabled

    @auto_run_enabled.setter
    def auto_run_enabled(self, val: bool) -> None:
        self._auto_run_enabled = val
        logger.info("CommandBus: auto_run = %s", val)

    # ── 调度 ────────────────────────────────────────────────────────

    async def dispatch(self, cmd: Command) -> CommandResult:
        """调度命令：权限检查 → 查找 handler → 执行 → 分发事件。"""

        # 1. BOT 自动化检查
        if cmd.source == Source.BOT and not self._auto_run_enabled:
            # BOT 来源且自动化未开启 → 拦截（查询类放行）
            if cmd.required_role > Role.VIEWER:
                return CommandResult.fail(
                    "Bot 自动化未开启，操作被拦截。发送 /claw auto on 开启。"
                )

        # 2. 权限检查
        #    BOT 来源对查询类命令（VIEWER 级别）豁免，允许读取系统状态
        if not cmd.has_permission():
            if cmd.source == Source.BOT and cmd.required_role <= Role.VIEWER:
                pass  # BOT 查询豁免
            else:
                logger.warning(
                    "权限拒绝: %s (source=%s, role=%s, required=%s)",
                    cmd.name,
                    cmd.source,
                    cmd.role.name,
                    cmd.required_role.name,
                )
                return CommandResult.permission_denied(cmd)

        # 3. 查找 handler
        handler = self._handlers.get(cmd.name)
        if not handler:
            return CommandResult.fail(f"未知命令: {cmd.name}")

        # 4. 执行
        try:
            result = await handler(cmd)
        except Exception as exc:
            logger.exception("命令执行异常: %s", cmd.name)
            return CommandResult.fail(f"执行异常: {exc}")

        # 5. 分发事件
        if result.events and self._event_callback:
            for event in result.events:
                event.setdefault("source", cmd.source)
                event.setdefault("actor", cmd.actor)
                try:
                    await self._event_callback(event)
                except Exception:
                    logger.exception("事件分发异常")

        return result

    # ── 工具方法 ────────────────────────────────────────────────────

    def list_commands(self, role: Role = Role.VIEWER) -> List[str]:
        """列出指定权限可用的命令。"""
        return sorted(
            name
            for name, handler in self._handlers.items()
            if _COMMAND_ROLES.get(name, Role.VIEWER) <= role
        )

    @property
    def registered_commands(self) -> List[str]:
        return sorted(self._handlers.keys())
