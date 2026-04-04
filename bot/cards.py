"""
SailZen Feishu Bot - Interactive Cards Module

Builds and manages Feishu interactive cards for better UX.
Documentation: https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/card-overview
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class CardColor(Enum):
    """Card accent colors."""

    BLUE = "blue"
    GREEN = "green"
    ORANGE = "orange"
    RED = "red"
    GREY = "grey"
    DEFAULT = "default"


class ButtonType(Enum):
    """Button types."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    DANGER = "danger"


@dataclass
class CardButton:
    """A card button."""

    text: str
    action: str
    params: Optional[Dict[str, Any]] = None
    button_type: ButtonType = ButtonType.PRIMARY
    confirm_text: Optional[str] = None


class CardBuilder:
    """Builder for Feishu interactive cards."""

    def __init__(self, title: str, color: CardColor = CardColor.DEFAULT):
        self.title = title
        self.color = color
        self.elements: List[Dict[str, Any]] = []
        self.header_extras: List[Dict[str, Any]] = []

    def add_text(
        self, text: str, bold: bool = False, size: str = "normal"
    ) -> "CardBuilder":
        """Add text element."""
        self.elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "plain_text" if not bold else "lark_md",
                    "content": f"**{text}**" if bold else text,
                },
            }
        )
        return self

    def add_markdown(self, content: str) -> "CardBuilder":
        """Add markdown text."""
        self.elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": content,
                },
            }
        )
        return self

    def add_divider(self) -> "CardBuilder":
        """Add divider."""
        self.elements.append({"tag": "hr"})
        return self

    def add_note(self, content: str, icon: Optional[str] = None) -> "CardBuilder":
        """Add note element."""
        element = {
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": content}],
        }
        if icon:
            element["elements"].insert(0, {"tag": "img", "img_key": icon})
        self.elements.append(element)
        return self

    def add_button_group(self, buttons: List[CardButton]) -> "CardBuilder":
        """Add button group."""
        actions = []
        for btn in buttons:
            action = {
                "tag": "button",
                "text": {"tag": "plain_text", "content": btn.text},
                "type": btn.button_type.value,
                "value": {"action": btn.action, "params": btn.params or {}},
            }
            if btn.confirm_text:
                action["confirm"] = {"title": "确认", "text": btn.confirm_text}
            actions.append(action)

        self.elements.append({"tag": "action", "actions": actions})
        return self

    def add_select(
        self,
        placeholder: str,
        options: List[tuple],
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> "CardBuilder":
        """Add select dropdown."""
        select_options = [
            {"text": {"tag": "plain_text", "content": label}, "value": value}
            for value, label in options
        ]

        self.elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "select_static",
                        "placeholder": {"tag": "plain_text", "content": placeholder},
                        "options": select_options,
                        "value": {"action": action, "params": params or {}},
                    }
                ],
            }
        )
        return self

    def add_input(
        self, placeholder: str, action: str, multiline: bool = False
    ) -> "CardBuilder":
        """Add text input."""
        self.elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "input",
                        "placeholder": {"tag": "plain_text", "content": placeholder},
                        "multiline": multiline,
                        "value": {"action": action},
                    }
                ],
            }
        )
        return self

    def add_column_layout(
        self, items: List[Dict[str, Any]], column_count: int = 2
    ) -> "CardBuilder":
        """Add multi-column layout."""
        columns = []
        for item in items:
            columns.append(
                {"tag": "div", "text": {"tag": "plain_text", "content": str(item)}}
            )

        self.elements.append(
            {
                "tag": "column_set",
                "flex_mode": "none",
                "background_style": "default",
                "columns": [
                    {"tag": "column", "elements": [col]}
                    for col in columns[:column_count]
                ],
            }
        )
        return self

    def build(self) -> Dict[str, Any]:
        """Build the card JSON."""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": self.title},
                "template": self.color.value,
            },
            "elements": self.elements,
        }

        if self.header_extras:
            card["header"]["extra"] = self.header_extras

        return card


def create_welcome_card(
    bot_name: str, projects: List[Dict[str, str]]
) -> Dict[str, Any]:
    """Create welcome card with project selection."""
    builder = CardBuilder(f"🤖 {bot_name}", CardColor.BLUE)

    builder.add_text("欢迎使用 SailZen Bot！", bold=True)
    builder.add_text("我可以帮你管理 OpenCode 开发会话。")
    builder.add_divider()

    if projects:
        builder.add_text("快速启动项目：")
        buttons = []
        for proj in projects[:6]:  # Max 6 buttons
            buttons.append(
                CardButton(
                    text=proj.get("label", proj.get("slug", "Unknown")),
                    action="start_workspace",
                    params={"path": proj.get("path")},
                )
            )
        builder.add_button_group(buttons)
        builder.add_divider()

    builder.add_text("或者发送自然语言指令：")
    builder.add_note("💡 示例：\n• 启动 sailzen\n• 帮我写个登录功能\n• 查看状态")

    return builder.build()


def create_session_status_card(session_info: Dict[str, Any]) -> Dict[str, Any]:
    """Create session status card."""
    status = session_info.get("process_status", "unknown")
    color = (
        CardColor.GREEN
        if status == "running"
        else CardColor.ORANGE
        if status == "starting"
        else CardColor.RED
    )

    builder = CardBuilder(f"📦 {session_info.get('name', 'Session')}", color)

    # Status indicator
    status_emoji = (
        "🟢" if status == "running" else "🟡" if status == "starting" else "🔴"
    )
    builder.add_markdown(f"**状态:** {status_emoji} {status.upper()}")

    # Details
    builder.add_divider()
    details = []
    if session_info.get("path"):
        details.append(f"📁 路径: `{session_info['path']}`")
    if session_info.get("port"):
        details.append(f"🔌 端口: {session_info['port']}")
    if session_info.get("pid"):
        details.append(f"⚙️ PID: {session_info['pid']}")

    builder.add_markdown("\n".join(details))

    # Action buttons
    builder.add_divider()
    buttons = []
    if status == "running":
        buttons.append(
            CardButton("发送任务", "send_task", {"path": session_info.get("path")})
        )
        buttons.append(
            CardButton(
                "停止",
                "stop_workspace",
                {"path": session_info.get("path")},
                ButtonType.DANGER,
                "确认停止此会话？",
            )
        )
    else:
        buttons.append(
            CardButton("启动", "start_workspace", {"path": session_info.get("path")})
        )

    buttons.append(
        CardButton(
            "查看日志",
            "view_logs",
            {"path": session_info.get("path")},
            ButtonType.SECONDARY,
        )
    )
    builder.add_button_group(buttons)

    return builder.build()


def create_task_result_card(task: str, result: str, path: str) -> Dict[str, Any]:
    """Create task result card."""
    builder = CardBuilder("✅ 任务完成", CardColor.GREEN)

    # Task info
    builder.add_markdown(f"**任务:** {task[:100]}{'...' if len(task) > 100 else ''}")
    builder.add_markdown(f"**工作区:** `{path}`")
    builder.add_divider()

    # Result (truncated if too long)
    display_result = result[:2000] + "..." if len(result) > 2000 else result
    builder.add_markdown(f"**结果:**\n```\n{display_result}\n```")

    # Actions
    builder.add_divider()
    builder.add_button_group(
        [
            CardButton("继续任务", "continue_task", {"path": path}),
            CardButton(
                "停止会话",
                "stop_workspace",
                {"path": path},
                ButtonType.DANGER,
                "确认停止？",
            ),
        ]
    )

    return builder.build()


def create_confirmation_card(
    title: str, message: str, action: str, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Create confirmation card."""
    builder = CardBuilder(f"⚠️ {title}", CardColor.ORANGE)

    builder.add_text(message)
    builder.add_divider()

    builder.add_button_group(
        [
            CardButton("确认", action, params, ButtonType.PRIMARY),
            CardButton("取消", "cancel", {}, ButtonType.SECONDARY),
        ]
    )

    return builder.build()


def create_error_card(
    error_message: str, suggestion: Optional[str] = None
) -> Dict[str, Any]:
    """Create error display card."""
    builder = CardBuilder("❌ 发生错误", CardColor.RED)

    builder.add_text(error_message)

    if suggestion:
        builder.add_divider()
        builder.add_note(f"💡 {suggestion}")

    return builder.build()


def create_help_card(bot_name: str, projects: List[Dict[str, str]]) -> Dict[str, Any]:
    """Create help card."""
    builder = CardBuilder(f"📖 {bot_name} 帮助", CardColor.BLUE)

    # Quick actions
    builder.add_text("快速操作", bold=True)
    builder.add_button_group(
        [
            CardButton("查看状态", "show_status", {}),
            CardButton("更新 Bot", "self_update", {}, ButtonType.SECONDARY),
        ]
    )

    builder.add_divider()

    # Available projects
    if projects:
        builder.add_text("可用项目", bold=True)
        for proj in projects:
            builder.add_markdown(
                f"• **{proj.get('label', proj.get('slug'))}** - {proj.get('description', 'No description')}"
            )

    builder.add_divider()

    # Command examples
    builder.add_text("指令示例", bold=True)
    examples = [
        "• `启动 sailzen` - 启动工作区",
        "• `使用 sailzen` - 切换工作区",
        "• `帮我写个登录功能` - 发送任务",
        "• `停止` - 停止会话",
        "• `状态` - 查看状态",
    ]
    builder.add_markdown("\n".join(examples))

    return builder.build()
