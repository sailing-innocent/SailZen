# -*- coding: utf-8 -*-
# @file card_renderer.py
# @brief Feishu interactive card templates for mobile-optimized UX
# @author sailing-innocent
# @date 2026-03-24
# @version 1.0
# ---------------------------------

from __future__ import annotations

import json
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class CardColor(str, Enum):
    GREEN = "green"
    RED = "red"
    BLUE = "blue"
    YELLOW = "yellow"
    GREY = "grey"
    ORANGE = "orange"


_STATE_COLORS: Dict[str, CardColor] = {
    "idle": CardColor.GREY,
    "starting": CardColor.BLUE,
    "running": CardColor.GREEN,
    "stopping": CardColor.YELLOW,
    "error": CardColor.RED,
}

_STATE_ICONS: Dict[str, str] = {
    "idle": "⬜",
    "starting": "🔄",
    "running": "🟢",
    "stopping": "🟡",
    "error": "🔴",
}


def _header(title: str, color: CardColor = CardColor.BLUE) -> Dict[str, Any]:
    return {
        "title": {"tag": "plain_text", "content": title},
        "template": color.value,
    }


def _divider() -> Dict[str, Any]:
    return {"tag": "hr"}


def _text(content: str, bold: bool = False) -> Dict[str, Any]:
    return {
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"**{content}**" if bold else content,
        },
    }


def _note(content: str) -> Dict[str, Any]:
    return {
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": content}],
    }


def _button(
    label: str, action_type: str, value: Dict[str, Any], style: str = "default"
) -> Dict[str, Any]:
    # Feishu button uses behaviors array for interactions
    # action_type can be: open_url, callback, form_action
    if action_type == "callback":
        behaviors = [{"type": "callback", "value": value}]
    elif action_type == "link":
        behaviors = [{"type": "open_url", "default_url": value.get("url", "")}]
    else:
        # Default fallback
        behaviors = [{"type": "callback", "value": value}]

    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": label},
        "type": style,
        "behaviors": behaviors,
    }


def _action_row(buttons: List[Dict[str, Any]]) -> Dict[str, Any]:
    # mobile: never more than 2 per row for adequate touch targets
    return {"tag": "action", "actions": buttons[:2]}


def _field_row(pairs: List) -> Dict[str, Any]:
    fields = [
        {
            "is_short": True,
            "text": {
                "tag": "lark_md",
                "content": "**" + str(label) + "**\n" + str(val),
            },
        }
        for label, val in pairs
    ]
    return {"tag": "div", "fields": fields}


# ---------------------------------------------------------------------------
# Card Template Framework
# ---------------------------------------------------------------------------


class CardRenderer:
    @staticmethod
    def workspace_selection(
        projects: List[Dict[str, str]],
        session_states: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        session_states = session_states or {}
        elements: List[Dict[str, Any]] = [
            _text("📱 手机端快捷指令", bold=True),
            _note("直接发送「启动 sailzen」即可快速启动，无需输入完整路径"),
            _divider(),
        ]

        for proj in projects:
            slug = proj.get("slug", "")
            label = proj.get("label", slug)
            path = proj.get("path", "")
            resolved = str(Path(path).expanduser()) if path else path
            state = session_states.get(resolved, "idle")
            icon = _STATE_ICONS.get(state, "⬜")
            state_label = {
                "idle": "未启动",
                "starting": "启动中...",
                "running": "运行中",
                "stopping": "停止中...",
                "error": "出错",
            }.get(state, state)

            elements.append(
                _text(icon + " **" + label + "** (" + slug + ")  |  " + state_label)
            )

            # 添加文字指令提示（本地运行不支持卡片按钮回调）
            if state in ("idle", "error"):
                cmd_text = f"发送「启动 {slug}」启动此工作区"
            elif state == "running":
                cmd_text = f"发送「使用 {slug}」切换到该工作区"
            else:
                cmd_text = f"当前状态: {state_label}"

            elements.append(_note(cmd_text))
            elements.append(_divider())

        if not projects:
            elements.append(_text("暂无配置的工作区，请在配置文件中添加 projects。"))
        else:
            # 添加底部提示
            elements.append(_text("💡 提示", bold=True))
            elements.append(_note("点击上方按钮，或直接发送「启动 <名称>」"))
            # 显示所有可用的快捷名称
            slugs = [p.get("slug", "") for p in projects if p.get("slug")]
            if slugs:
                elements.append(_note(f"可用名称: {', '.join(slugs)}"))

        return {
            "config": {"wide_screen_mode": True},
            "header": _header("🖥  选择工作区", CardColor.BLUE),
            "elements": elements,
        }

    @staticmethod
    def session_status(
        path: str,
        state: str,
        port: Optional[int] = None,
        pid: Optional[int] = None,
        last_error: Optional[str] = None,
        activities: Optional[List[str]] = None,
        show_stop_button: bool = True,
    ) -> Dict[str, Any]:
        color = _STATE_COLORS.get(state, CardColor.GREY)
        icon = _STATE_ICONS.get(state, "⬜")
        state_label = {
            "idle": "空闲",
            "starting": "启动中",
            "running": "运行中",
            "stopping": "停止中",
            "error": "出错",
        }.get(state, state)
        name = Path(path).name if path else "未知"

        elements: List[Dict[str, Any]] = [
            _text(icon + " **" + state_label + "**  |  " + name)
        ]

        info_pairs: List = []
        if port:
            info_pairs.append(("端口", str(port)))
        if pid:
            info_pairs.append(("PID", str(pid)))
        if info_pairs:
            elements.append(_field_row(info_pairs))

        if last_error:
            elements.append(_divider())
            elements.append(_text("错误：" + last_error[:200]))

        if activities:
            elements.append(_divider())
            elements.append(_text("最近活动：", bold=True))
            for act in activities[-5:]:
                elements.append(_note(act))

        # 添加快捷指令提示
        if path:
            elements.append(_divider())
            # 获取slug用于快捷指令
            slug_hint = Path(path).name
            elements.append(
                _note(f"快捷操作：发送「使用 {slug_hint}」可直接进入此工作区发送指令")
            )

        # 添加文字指令提示（本地运行不支持卡片按钮回调）
        if state == "running" and show_stop_button:
            elements.append(_divider())
            elements.append(_note("💡 发送「停止" + name + "」可停止此工作区"))
        elif state == "error":
            elements.append(_divider())
            elements.append(_note("💡 发送「启动" + name + "」可重新启动"))
        elif state == "idle":
            elements.append(_divider())
            elements.append(_note("💡 发送「启动" + name + "」可启动此工作区"))

        return {
            "config": {"wide_screen_mode": True},
            "header": _header("会话状态：" + name, color),
            "elements": elements,
        }

    @staticmethod
    def progress(
        title: str,
        description: str = "",
        progress_pct: Optional[int] = None,
        elapsed_seconds: Optional[float] = None,
        spinner_tick: int = 0,
    ) -> Dict[str, Any]:
        spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        spinner = spinner_chars[spinner_tick % len(spinner_chars)]

        elements: List[Dict[str, Any]] = []
        if description:
            elements.append(_text(description))

        if progress_pct is not None:
            filled = progress_pct // 10
            bar = "█" * filled + "░" * (10 - filled)
            elements.append(_text(bar + "  " + str(progress_pct) + "%"))
        else:
            elements.append(_text(spinner + " 处理中，请稍候..."))

        if elapsed_seconds is not None:
            elements.append(_note("已用时 " + str(int(elapsed_seconds)) + "s"))

        return {
            "config": {"wide_screen_mode": True},
            "header": _header("⏳ " + title, CardColor.BLUE),
            "elements": elements,
        }

    @staticmethod
    def confirmation(
        action_summary: str,
        action_detail: str = "",
        risk_level: str = "confirm_required",
        can_undo: bool = False,
        pending_id: str = "",
        timeout_minutes: int = 5,
    ) -> Dict[str, Any]:
        risk_icons = {"safe": "🟢", "guarded": "🟡", "confirm_required": "🔴"}
        risk_labels = {
            "safe": "低风险",
            "guarded": "中等风险",
            "confirm_required": "高风险",
        }

        elements: List[Dict[str, Any]] = [_text(action_summary, bold=True)]
        if action_detail:
            elements.append(_text(action_detail))

        elements.append(_divider())
        elements.append(
            _field_row(
                [
                    (
                        "风险等级",
                        risk_icons.get(risk_level, "🔴")
                        + " "
                        + risk_labels.get(risk_level, "需确认"),
                    ),
                    ("有效期", str(timeout_minutes) + " 分钟"),
                ]
            )
        )

        if can_undo:
            # 30s window is realistic for mobile push notification latency (vs original 10s)
            elements.append(_note("此操作可在 30 秒内撤销"))

        elements.append(_divider())
        # 文字指令提示（本地运行不支持卡片按钮回调）
        elements.append(_note("💡 请回复："))
        elements.append(_note("   「确认」- 执行此操作"))
        elements.append(_note("   「取消」- 放弃此操作"))

        return {
            "config": {"wide_screen_mode": True},
            "header": _header("⚠️  请确认操作", CardColor.YELLOW),
            "elements": elements,
        }

    @staticmethod
    def result(
        title: str,
        content: str,
        success: bool = True,
        can_retry: bool = False,
        retry_action: Optional[Dict[str, Any]] = None,
        can_undo: bool = False,
        undo_deadline: Optional[float] = None,
        context_path: str = "",
    ) -> Dict[str, Any]:
        color = CardColor.GREEN if success else CardColor.RED
        icon = "✅" if success else "❌"

        elements: List[Dict[str, Any]] = []
        if content:
            display = content[:500]
            if len(content) > 500:
                display += "\n\n…（已截断，请在 OpenCode 查看完整输出）"
            elements.append(_text(display))

        # 文字指令提示（本地运行不支持卡片按钮回调）
        notes: List[str] = []
        if can_retry and retry_action:
            notes.append("💡 发送「重试」重新执行")
        if can_undo and undo_deadline:
            remaining = undo_deadline - time.time()
            if remaining > 0:
                notes.append(f"💡 发送「撤销」撤销此操作（{int(remaining)}秒内有效）")
        if context_path:
            notes.append(f"💡 发送「状态 {Path(context_path).name}」查看详情")

        if notes:
            elements.append(_divider())
            for note in notes:
                elements.append(_note(note))

        return {
            "config": {"wide_screen_mode": True},
            "header": _header(icon + " " + title, color),
            "elements": elements,
        }

    @staticmethod
    def error(
        title: str,
        error_message: str,
        context_path: str = "",
        can_retry: bool = True,
        retry_action: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        elements: List[Dict[str, Any]] = [_text(error_message[:300])]

        # 文字指令提示（本地运行不支持卡片按钮回调）
        notes: List[str] = []
        if can_retry and retry_action:
            notes.append("💡 发送「重试」重新执行")
        if context_path:
            notes.append(f"💡 发送「状态 {Path(context_path).name}」查看详情")

        if notes:
            elements.append(_divider())
            for note in notes:
                elements.append(_note(note))

        return {
            "config": {"wide_screen_mode": True},
            "header": _header("❌ " + title, CardColor.RED),
            "elements": elements,
        }

    @staticmethod
    def all_sessions(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        elements: List[Dict[str, Any]] = []
        if not sessions:
            elements.append(_text("暂无会话。\n发送「启动 <工作区>」开始工作。"))
        else:
            for s in sessions:
                path = s.get("path", "")
                state = s.get("state", "idle")
                port = s.get("port")
                icon = _STATE_ICONS.get(state, "⬜")
                name = str(Path(path).name if path else "?")
                state_label_map = {
                    "idle": "空闲",
                    "starting": "启动中",
                    "running": "运行中",
                    "stopping": "停止中",
                    "error": "出错",
                }
                state_label = state_label_map.get(state, state or "未知")
                port_info = ":" + str(port) if port else ""
                elements.append(
                    _text(icon + " **" + name + "**" + port_info + "  " + state_label)
                )
            elements.append(_divider())
            elements.append(_note("发送「状态 <工作区名>」查看详情"))

        return {
            "config": {"wide_screen_mode": True},
            "header": _header("📊 所有会话", CardColor.BLUE),
            "elements": elements,
        }

    @staticmethod
    def timeout_warning(
        operation: str,
        elapsed_seconds: float,
        context_path: str = "",
    ) -> Dict[str, Any]:
        elements = [
            _text("操作「" + operation + "」比预期用时更长。"),
            _text("已用时 " + str(int(elapsed_seconds)) + "s，系统仍在工作中。"),
        ]
        buttons = [_button("继续等待", "callback", {"action": "noop"}, "default")]
        if context_path:
            buttons.append(
                _button(
                    "取消操作",
                    "callback",
                    {
                        "action": "cancel_operation",
                        "path": context_path,
                    },
                    "danger",
                )
            )
        elements.append(_divider())
        elements.append(_action_row(buttons))
        return {
            "config": {"wide_screen_mode": True},
            "header": _header("⏰ 操作超时警告", CardColor.YELLOW),
            "elements": elements,
        }


# ---------------------------------------------------------------------------
# Card Update Mechanism + Fallback
# ---------------------------------------------------------------------------


class CardMessageTracker:
    def __init__(self) -> None:
        self._map: Dict[str, Dict[str, Any]] = {}

    def register(
        self, message_id: str, card_type: str, context: Dict[str, Any]
    ) -> None:
        self._map[message_id] = {"card_type": card_type, "context": context}

    def get(self, message_id: str) -> Optional[Dict[str, Any]]:
        return self._map.get(message_id)

    def remove(self, message_id: str) -> None:
        self._map.pop(message_id, None)

    def find_by_context(self, card_type: str, key: str, value: str) -> Optional[str]:
        for mid, info in self._map.items():
            if (
                info.get("card_type") == card_type
                and info.get("context", {}).get(key) == value
            ):
                return mid
        return None


def card_to_feishu_content(card: Dict[str, Any]) -> str:
    return json.dumps(card, ensure_ascii=False)


def text_fallback(card: Dict[str, Any]) -> str:
    """Extract plain-text fallback from a card dict when the interactive card API fails."""
    lines: List[str] = []
    header = card.get("header", {})
    title_obj = header.get("title", {})
    title = title_obj.get("content", "") if isinstance(title_obj, dict) else ""
    if title:
        lines.append(title)
        lines.append("=" * min(len(title), 40))

    for el in card.get("elements", []):
        tag = el.get("tag", "")
        if tag == "div":
            text_obj = el.get("text", {})
            if isinstance(text_obj, dict):
                content = text_obj.get("content", "").replace("**", "")
                if content:
                    lines.append(content)
            for f in el.get("fields", []):
                field_text = f.get("text", {})
                if isinstance(field_text, dict):
                    c = field_text.get("content", "").replace("**", "")
                    if c:
                        lines.append(c)
        elif tag == "note":
            for ne in el.get("elements", []):
                c = ne.get("content", "")
                if c:
                    lines.append("[" + c + "]")
        elif tag == "hr":
            lines.append("-" * 20)

    return "\n".join(lines)
