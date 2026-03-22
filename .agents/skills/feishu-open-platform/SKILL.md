---
name: feishu-open-platform
description: Feishu Open Platform guidance for Lark bot development in feishu-opencode-bridge, focused on app bots, long connections, message events, cards, replies, and implementation guardrails.
---

# Feishu Open Platform

Use this skill when implementing or reviewing `feishu-opencode-bridge` features that depend on Feishu/Lark bot capabilities.

## What This Skill Covers

- Application bot vs custom bot capability choices
- Long-connection event reception on the home host
- Message receive event structure and idempotency
- Feishu card design and update patterns
- Bot menu and conversation-entry interaction patterns
- Practical implementation guidance for `scripts/feishu_agent.py`-style local runtimes

## Project-Specific Guidance

- Prefer an **application bot** over a custom bot for `feishu-opencode-bridge`.
- Prefer a **home-host long connection** runtime for the local edge bot, consistent with `scripts/feishu_agent.py`.
- Treat Feishu as the operator interaction surface, not the persistence layer.
- Use cards for workspace home, session cockpit, confirmations, and alerts.
- Treat long free-form text from third-party speech-to-text keyboards as normal input; route it into normalization and confirmation, not raw execution.

## Key Platform Facts

### 1. Use an application bot

Application bots support:
- receiving and replying to user messages;
- interactive cards;
- sending p2p and group messages;
- richer platform APIs.

Custom bots are mainly for one-way group push and are not suitable for this workflow.

### 2. Prefer long connection on the home host

Feishu supports event handling through Webhook and long connection.

For this project, long connection is a strong fit because:
- the bot is intended to run on the home host;
- it reduces dependence on public ingress exposure for the local bot runtime;
- it matches the current implementation style in `scripts/feishu_agent.py`.

Python SDK pattern:

```python
import lark_oapi as lark

def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    print(lark.JSON.marshal(data, indent=2))

event_handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
    .build()

cli = lark.ws.Client("APP_ID", "APP_SECRET", event_handler=event_handler)
cli.start()
```

### 3. Message receive event essentials

Core event:
- `im.message.receive_v1`

Important fields:
- `message_id`: use for idempotent dedupe
- `chat_id`: conversation identity
- `chat_type`: `p2p` or `group`
- `message_type`: text or other types
- `content`: JSON string payload
- `mentions`: mention list for group mention handling
- `sender.sender_id.open_id`: sender identity

Guidance:
- dedupe by `message_id`, not by `event_id`;
- only respond in group chats when policy allows or the bot is explicitly mentioned;
- normalize inbound payloads into internal event envelopes before routing.

### 4. Cards are the default rich UI

Feishu cards are suitable for:
- structured status views;
- quick actions;
- approval/confirmation steps;
- streaming or refreshed AI task updates;
- lightweight data visualization.

For this project, prefer cards for:
- workspace home;
- session cockpit;
- normalized draft confirmation;
- alerts and recovery actions.

### 5. Streaming and updates

Feishu cards support update flows and AI-oriented streaming update patterns.

Use updates for:
- long-running task progress;
- session health refresh;
- post-action result replacement;
- alert escalation state changes.

Do not spam users with a new message for every low-value event; prefer card refresh or digesting.

### 6. Voice-friendly means text normalization first

For this project, voice-friendly does **not** mean native audio handling is mandatory.

Preferred flow:
1. user speaks through phone IME or third-party speech-to-text input;
2. bot receives a long imperfect text block;
3. server intent router matches intent and cleans text with templates;
4. system returns a normalized draft card;
5. user confirms, edits, or rejects;
6. only then does execution begin.

This is safer and more flexible than direct execution from messy text.

## Implementation Checklist

When building Feishu-facing features, verify:

- app bot capability is enabled;
- required message permissions are configured;
- long-connection runtime is stable on the home host;
- inbound events are deduplicated with `message_id`;
- card payloads are structured for mobile reading and one-tap actions;
- free-form text goes through normalization and confirmation;
- Feishu failures are retried or surfaced through edge queues;
- group-chat behavior is constrained to mention/policy rules.

## Recommended Design Defaults

- **Bot type**: application bot
- **Ingress mode**: long connection on home host
- **Primary input**: text and speech-derived text blocks
- **Primary output**: Feishu cards
- **Confirmation mode**: normalized draft confirmation before execution from free-form text
- **Status updates**: card updates first, new messages second
- **Dedupe key**: `message_id`

## Good Uses In This Repo

- Updating `scripts/feishu_agent.py`
- Implementing home-host edge runtime behavior
- Designing card JSON for remote development workflows
- Wiring message receive events and replies
- Reviewing whether a feature belongs in Feishu cards or internal control-plane APIs

## Sources Reviewed

- Feishu Open Platform home: `https://open.feishu.cn/?lang=zh-CN`
- Bot overview: `https://open.feishu.cn/document/client-docs/bot-v3/bot-overview?lang=zh-CN`
- Message receive event: `https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/events/receive?lang=zh-CN`
- Feishu cards overview: `https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/feishu-card-overview?lang=zh-CN`
