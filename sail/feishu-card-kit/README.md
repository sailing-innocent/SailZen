# Feishu Card Kit

A **zero-dependency** Python toolkit for building Feishu (Lark) interactive cards.

Extracted from the [SailZen](https://github.com/sailing-innocent/SailZen) project as a standalone, reusable module.

## Features

- **Zero external dependencies** — Only Python standard library (≥3.9)
- **Mobile-optimized** — Cards designed for phone-first interaction
- **Rich templates** — Progress, result, error, confirmation, workspace, welcome, help
- **Long content handling** — Automatic pagination and file fallback for large outputs
- **Card tracking** — Track sent cards for later updates
- **Text fallback** — Graceful degradation when card API fails

## Installation

```bash
# From source
pip install packages/feishu-card-kit

# Or copy the single package folder into your project
```

## Quick Start

```python
from sail.feishu_card_kit import CardRenderer, card_to_feishu_content

# Create a progress card
card = CardRenderer.progress(
    title="正在处理",
    description="分析代码结构中...",
    elapsed_seconds=15,
    show_cancel_button=True,
    cancel_action_data={"action": "cancel_task", "task_id": "123"},
)

# Serialize for Feishu API
content = card_to_feishu_content(card)
# Pass `content` to Feishu message.create API
```

## Card Templates

### Progress
```python
CardRenderer.progress(
    title="任务执行中",
    description="正在优化数据库查询...",
    progress_pct=45,          # Optional: 0-100
    elapsed_seconds=30,       # Optional
    spinner_tick=3,           # Animation frame
    show_cancel_button=True,
    cancel_action_data={"action": "cancel", "id": "abc"},
)
```

### Result
```python
CardRenderer.result(
    title="任务完成",
    content="已重构完成，修改了 3 个文件。",
    success=True,
    can_retry=False,
    context_path="~/projects/myapp",
)
```

### Error
```python
CardRenderer.error(
    title="执行失败",
    error_message="数据库连接超时，请检查网络。",
    can_retry=True,
    retry_action={"action": "retry"},
)
```

### Confirmation
```python
CardRenderer.confirmation(
    action_summary="停止工作区 sailzen？",
    action_detail="这将终止所有正在运行的任务。",
    risk_level="confirm_required",  # safe | guarded | confirm_required
    pending_id="confirm_001",
    timeout_minutes=5,
)
```

### Workspace Selection
```python
projects = [
    {"slug": "sailzen", "path": "~/repos/SailZen", "label": "SailZen"},
    {"slug": "blog", "path": "~/projects/blog", "label": "Blog"},
]
session_states = {"~/repos/SailZen": "running"}

CardRenderer.workspace_selection(projects, session_states)
```

### Session Status
```python
CardRenderer.session_status(
    path="~/repos/SailZen",
    state="running",
    port=4096,
    pid=12345,
    activities=["启动完成", "任务执行中..."],
)
```

### Welcome / Help
```python
CardRenderer.welcome(
    title="欢迎使用 MyBot",
    description="我是你的智能助手",
    quick_commands=["• **帮助** - 查看说明", "• **状态** - 查看状态"],
    projects=projects,
    features=[("智能识别", "✅ LLM"), ("自更新", "✅ 支持")],
)

CardRenderer.help(
    commands=[
        ("启动 <项目>", "启动工作区", "启动 sailzen"),
        ("停止", "停止工作区", "停止 sailzen"),
    ],
    projects=projects,
)
```

## Low-Level Building Blocks

For custom cards, use the atomic builders:

```python
from sail.feishu_card_kit import (
    card, header, text, note, divider,
    button, action_row, field_row,
    CardColor, ButtonStyle,
)

my_card = card(
    elements=[
        text("Hello, **Feishu**!"),
        divider(),
        field_row([("状态", "✅ 正常"), ("版本", "v1.0.0")]),
        action_row([
            button("确认", "callback", {"action": "ok"}, ButtonStyle.PRIMARY),
            button("取消", "callback", {"action": "cancel"}),
        ]),
    ],
    title="自定义卡片",
    color=CardColor.GREEN,
)
```

## Long Content Handling

```python
from sail.feishu_card_kit import LongOutputHandler

handler = LongOutputHandler(output_dir="/tmp/bot_output")
strategy, result = handler.process(
    title="分析结果",
    content=very_long_text,  # > 8K chars → paginate, > 30K → file
)

# strategy: "direct" | "paginate" | "file"
# result: card dict | list[card dict] | Path
```

## Card Tracking

```python
from sail.feishu_card_kit import CardMessageTracker

tracker = CardMessageTracker()
tracker.register("om_xxx", "progress", {"task_id": "123"})

# Later: find message ID by context
mid = tracker.find_by_context("progress", "task_id", "123")
```

## Text Fallback

When card API fails, extract plain text:

```python
from sail.feishu_card_kit import text_fallback

text_msg = text_fallback(card_dict)
# Send text_msg as fallback
```

## Architecture

```
feishu_card_kit/
├── core.py      — Atomic builders (header, text, button, etc.)
├── renderer.py  — Pre-built templates (CardRenderer)
├── tracker.py   — Message tracking + serialization
└── handler.py   — Long content strategies
```

## License

MIT
