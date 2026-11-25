---
name: sailzen-trace-triage
description: |
  SailZen 线上 AI Trace 排查、消息链路取证与脏数据安全修复技能。
  覆盖：双存储拓扑速查（云端 sail_server REST/PG vs sailtick.db 独立 SQLite）、
  只读全链路取证（QuickChat / TickEngine / Reminder / UserInbox / Rhythm / Device）、
  Windows PowerShell + SSH Base64 无转义查询技巧、典型 AI 链路脏数据模式识别，
  以及严格遵守双库隔离红线的安全清理与回归固化 SOP。
---

# SailZen 线上 AI Trace 排查与脏数据安全修复手册

本技能沉淀 SailZen 3.0 生产环境下排查 AI 智能体异常行为（如重复提醒、重复事务、终端重复绑定、消息未消解、排程不生效等）的标准取证与安全修复闭环。

关联技能与文档：
- 运维与发布规范：`.agents/skills/sailzen-ops/SKILL.md`、`AGENTS.md`
- 性能遥测闭环：`.agents/skills/sailzen-perf-loop/SKILL.md`
- 核心源码：`sailtick/quick_agent.py`、`sailtick/tick_engine.py`、`sailtick/tracer.py`、`sailtick/db.py`、`sail_server/model/reminder.py`、`sail_server/model/inbox.py`、`sail_server/model/user.py`

---

## 0. 不可逾越的安全红线

1. **严禁直接连云端 PostgreSQL 写数据**：
   - `sail_server` 业务数据（Reminder / Inbox / Affair / Device / Health 等）的**所有排查优先走只读 REST API**，**所有清理必须走合法业务 REST API**（如 `DELETE /api/v1/reminder/{id}`、`POST /api/v1/inbox/{id}/dismiss`、`DELETE /api/v1/rhythm/affair/{id}`、`POST /api/v1/user/devices/cleanup`）。
   - 走业务 API 的核心价值：自动触发级联逻辑（例如撤销 Reminder 时联动关闭 `user_inbox_items` 并经 WebSocket 撤回手机通知），绝不产生跨表孤儿脏状态。
2. **双库边界清晰**：
   - 云端主库（PostgreSQL）：由 `sail_server` 唯一拥有，对外仅通过 `/api/v1/*` HTTP API 操作。
   - SailTick 隔离库（`/home/ubuntu/repos/SailZen/data/sailtick/db/sailtick.db`）：独立 SQLite，存 `st_*` 表族（不参与 `db_sync.py`）。仅可在只读排查确认精确主键后，对异常 `pending` 态记录做最小化状态修正（如 `status='canceled'`），**严禁直接 `DELETE` 历史 Trace/对话证据**。
3. **凭据零泄露**：读 `.env.prod` 提取 `SAILZEN_API_TOKEN` 仅在进程内存中使用，严禁 `print()` 到日志或终端。

---

## 1. 全链路数据拓扑速查（排查前先对齐表名与入口）

| 链路环节 | 存储位置 | 真实表名 / REST 接口 | 常见踩坑 |
|---|---|---|---|
| **快脑对话原文与执行回执** | `sailtick.db` | `st_quick_chats`（⚠️ 复数！） | 容易误写成 `st_quick_chat` 查空 |
| **快脑 / 慢脑全链路 Trace** | `sailtick.db` + `sail_server` | `st_ai_traces`、`st_ai_trace_spans` / `GET /api/v1/telemetry/ai-traces` | 排查慢脑看 `slot in (morning_checkin, midday_checkin, ...)`，排查快脑看 `slot='quick_chat'` |
| **本地定时推送队列** | `sailtick.db` | `st_scheduled_nudges` | 与 `sail_server` Reminder 通过 `server_reminder_id` 关联，双写必须联动取消 |
| **Agent 长期画像** | `sailtick.db` | `st_profile`（含 `offwork_time` 等） | 检查 Prompt 注入的默认值是否与用户原话冲突 |
| **云端提醒** | `sail_server` (PG) | `GET /api/v1/reminder/pending`、`GET /api/v1/reminder/history?date=YYYY-MM-DD`、`DELETE /api/v1/reminder/{id}` | 路由挂在 `/api/v1/reminder/`，不是 `/api/v1/reminder/reminders` |
| **统一多端收件箱** | `sail_server` (PG) | `GET /api/v1/inbox/sync?since_seq=0&limit=200`、`POST /api/v1/inbox/{id}/dismiss` | `active_ids` 为当前全端未消解的权威集合 |
| **Rhythm 事务 / 日程** | `sail_server` (PG) | `GET /api/v1/rhythm/dashboard?date=...`、`GET /api/v1/rhythm/affair/`、`DELETE /api/v1/rhythm/affair/{id}` | `rhythm_upsert_affair` 排查重点看是否出现同名多条 `id` |
| **多端终端绑定** | `sail_server` (PG) | `GET /api/v1/user/devices`、`POST /api/v1/user/devices/cleanup`、`DELETE /api/v1/user/devices/{device_id}` | 重点检查 `is_emulator`、相同 `device_name` 多 UUID 残留 |
| **云端运行日志** | systemd journald | `sudo journalctl -u my-server.service` / `sudo journalctl -u sailtick.service` | 结合精确时间戳串联 HTTP 请求与 LLM 调用 |

---

## 2. 四步只读取证工作流（Windows PowerShell 实操模板）

### Step 1 — 经业务 REST API 拉取关联快照（零副作用）

```powershell
uv run python -c @'
import json, urllib.request

base = "http://101.43.22.254:4399"
token = ""
for line in open(".env.prod", encoding="utf-8"):
    s = line.strip()
    if s.startswith("SAILZEN_API_TOKEN="):
        token = s.split("=", 1)[1].strip().strip("\"'")
headers = {"Authorization": f"Bearer {token}"} if token else {}

def fetch(path):
    with urllib.request.urlopen(urllib.request.Request(f"{base}{path}", headers=headers), timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))

kw = ("关键词1", "关键词2")  # 替换为具体排查关键词
print("=== PENDING REMINDERS ===")
for r in fetch("/api/v1/reminder/pending"):
    if any(k in str(r) for k in kw):
        print(json.dumps(r, ensure_ascii=False))

print("=== ACTIVE INBOX ===")
sync = fetch("/api/v1/inbox/sync?since_seq=0&limit=200")
for it in sync.get("changes", []):
    if any(k in str(it) for k in kw):
        print(json.dumps(it, ensure_ascii=False))
'@
```

### Step 2 — Base64 封装 SSH 查询 `sailtick.db`（彻底避开 PowerShell/SSH 引号吞噬）

> **⚠️ 关键技巧**：在 Windows `pwsh` 里经 `run_ssh_command` 传内联 `python3 -c '...'` 极易被嵌套双/单引号破坏导致空输出。**一律将只读 Python 脚本 Base64 编码后通过 `exec(base64.b64decode(...))` 在云端执行**，100% 稳定。

```powershell
uv run python -c @'
import base64
from scripts.ops.common import load_ops_config, run_ssh_command

cfg = load_ops_config()
script = """
import sqlite3, json
conn = sqlite3.connect("/home/ubuntu/repos/SailZen/data/sailtick/db/sailtick.db")
conn.row_factory = sqlite3.Row
print("=== RECENT QUICK CHATS ===")
for r in conn.execute("SELECT * FROM st_quick_chats ORDER BY rowid DESC LIMIT 12").fetchall():
    print(json.dumps(dict(r), ensure_ascii=False, default=str))
print("\\n=== PENDING NUDGES ===")
for r in conn.execute("SELECT * FROM st_scheduled_nudges WHERE status='pending' ORDER BY trigger_at ASC").fetchall():
    print(json.dumps(dict(r), ensure_ascii=False, default=str))
print("\\n=== RECENT AI TRACES ===")
for r in conn.execute("SELECT trace_id, slot, trigger_source, status, plan_source, actions_executed, actions_failed, summary, started_at FROM st_ai_traces ORDER BY rowid DESC LIMIT 10").fetchall():
    print(json.dumps(dict(r), ensure_ascii=False, default=str))
"""
b64 = base64.b64encode(script.encode()).decode()
print(run_ssh_command(cfg, f"python3 -c \"import base64; exec(base64.b64decode('{b64}').decode())\"", check=False, timeout=20).stdout)
'@
```

### Step 3 — 下钻单条 Trace 的 Span 树（定位 LLM 原始输出与每个 Action 结果）

拿到 `trace_id` 后，读取 `st_ai_trace_spans`：
- 看 `stage='context'`：上下文里是否漏注入了已有状态（如待触发提醒、画像字段、历史动作回执）？
- 看 `stage='llm'`：模型拿到的 Prompt 是什么、原始 JSON `actions` 输出了什么、是否触发了 `max_tokens` 截断或默认值覆盖？
- 看 `stage='work'`：执行器是否命中了幂等去重（`deduplicated`）、原地改期（`rescheduled`），还是无条件新建了重复记录？

### Step 4 — 结合 `journalctl` 交叉验证时间线

```powershell
uv run python -c @'
from scripts.ops.common import load_ops_config, run_ssh_command
cfg = load_ops_config()
cmd = "sudo journalctl -u my-server.service -u sailtick.service --since '2026-11-25 11:45:00' --until '2026-11-25 12:15:00' --no-pager | grep -iE 'quick|reminder|inbox|affair|error|warn' | tail -n 80 || true"
print(run_ssh_command(cfg, cmd, check=False, timeout=20).stdout)
'@
```

---

## 3. 典型 AI 链路脏数据模式库（对照速查）

| 症状 | 根因模式 | 排查重点 | 根治手段 |
|---|---|---|---|
| **多轮对话产生 2–3 条同主题提醒或同名事务** | **历史重放（Action Replay）** | `st_quick_chats` 中后续轮次用户没提旧事，但 assistant 口头总结后又输出了旧 `actions` | 历史消息注入 `[系统回执-该轮已执行]` + Prompt 硬禁复读 + 执行层语义归一化幂等防重 |
| **改时间后新旧两个时段同时提醒** | **只增不改（Append-Only Tooling）** | 工具集只有 `create_*` 没有 `update_*`/`cancel_*`，Prompt 无现有列表 | 注入待触发列表 + 补全 `update_reminder`/`cancel_reminder` + 执行层同日同主题自动改期替换 |
| **用户纠正作息后仍按旧默认值算时间** | **画像断写 + 默认值越权** | `st_profile` 缺失对应 key，Prompt 默认值描述强于用户原话 | 新增 `update_profile` 动作即时落库 + Prompt 明确用户原话时间绝对优先 |
| **取消了云端提醒但到点仍推 QQ / 通知** | **双写孤儿记录** | `sail_server` Reminder 已 `CANCELED`，但 `st_scheduled_nudges` 仍为 `pending` | 任何改期/取消必须按 `server_reminder_id` 双向同步 `st_scheduled_nudges` |
| **同一手机/浏览器出现十几个重复终端** | **无指纹随机 UUID** | `GET /api/v1/user/devices` 同 `device_name` 多个 `device_id` | 端侧稳定硬件/环境指纹 + 服务端指纹接管 + `POST /api/v1/user/devices/cleanup` |
| **Trace 面板查不到白天对话记录** | **快脑未接入 Tracer** | `st_ai_traces` 仅有慢脑 slot，缺少 `slot='quick_chat'` | 统一接入 `TickTraceRecorder` 并落盘 + 上报 `/api/v1/telemetry/ai-traces` |

---

## 4. 线上脏数据安全清理与回归固化 SOP

1. **先盘点并确认保留项（Keep List）与清理项（Drop List）**：
   - 明确列出每条待清理记录的 `id`、创建时间和冗余原因，绝不盲目批量删表。
2. **先清 `sail_server` 业务侧（一律走 REST API）**：
   - 重复提醒：`DELETE /api/v1/reminder/{id}`，随后检查 `GET /api/v1/inbox/sync` 确认关联收件箱条目已级联退出 `active_ids`（若未级联则补 `POST /api/v1/inbox/{id}/dismiss`）。
   - 重复事务：`DELETE /api/v1/rhythm/affair/{id}`（或 `POST /api/v1/rhythm/affair/{id}/state` `{"action":"cancel"}`）。
   - 重复终端：`POST /api/v1/user/devices/cleanup` 或 `DELETE /api/v1/user/devices/{device_id}`。
3. **再同步清理 `sailtick.db` 隔离侧（精确主键状态更新，不物理删证据）**：
   - 将对应的冗余 `st_scheduled_nudges` 按 `server_reminder_id` 或 `id` 标记为 `status='canceled'`。
   - 若用户已在对话中明确纠正基础画像（如 `offwork_time`），同步 `UPSERT` 到 `st_profile` 并标记 `source='user_explicit_correction'`。
4. **二次只读复核**：
   - 再次查询 `/api/v1/reminder/pending`、`st_scheduled_nudges (status='pending')` 与 `/api/v1/rhythm/affair/`，确认只剩下预期的干净记录。
5. **代码根治 + 回归单测**：
   - 将本次线上真实多轮输入固化为 `tests/sailtick/` 或 `tests/server/` 的回归测试用例，确保同类脏数据永不复发。
