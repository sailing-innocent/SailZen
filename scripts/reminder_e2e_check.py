# -*- coding: utf-8 -*-
# @file reminder_e2e_check.py
# @brief Reminder M1 端到端联调验收脚本（针对运行中的 sail_server）
# @author sailing-innocent
# @date 2026-08-03
# @version 1.0
# ---------------------------------

"""
Reminder M1 端到端联调验收脚本

前置：服务端已启动（建议 REMINDER_SCAN_INTERVAL_SECONDS=5 加速验收）::

    uv run server.py --dev          # .env.dev 中 DB_BACKEND=sqlite

用法::

    uv run scripts/reminder_e2e_check.py --base-url http://127.0.0.1:1974
    uv run scripts/reminder_e2e_check.py --base-url http://192.168.1.10:1974 --token <SAILZEN_API_TOKEN>

流程（对应验收文档 ACCEPTANCE_M1.md）：

- health → 注册设备
- （默认）WS 长连接监听 reminder.delivered，--skip-ws 可关闭
- A：创建 3 秒后触发提醒 → 等 DELIVERED → ack → open → resolve → 核对事件序列
- B：创建 → DELIVERED → snooze 15m → 核对 SNOOZED/next_trigger_time/snoozed 事件
    （--wait-redelivery 可真实等待 15 分钟验证 scan 重投，默认跳过并由 dismiss 收尾）
- C：创建 → DELIVERED → dismiss → 核对 IGNORED
- summary/today 与 history  sanity 检查
- 打印 PASS/FAIL 汇总，任一失败 exit 1
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

RESULTS: List[Tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    line = f"[{mark}] {name}"
    if detail:
        line += f" -- {detail}"
    print(line, flush=True)


class ReminderE2E:
    def __init__(self, base_url: str, token: str = "", delivery_timeout: float = 75.0):
        self.base_url = base_url.rstrip("/")
        self.api = f"{self.base_url}/api/v1/reminder"
        self.token = token
        self.delivery_timeout = delivery_timeout
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.client = httpx.AsyncClient(timeout=30.0, headers=headers)
        self.device_id = "e2e-check-device"
        self.ws_messages: List[Dict[str, Any]] = []
        self._ws_stop = asyncio.Event()

    async def close(self):
        self._ws_stop.set()
        await self.client.aclose()

    # ------------------------------------------------------------------
    # WS listener
    # ------------------------------------------------------------------

    def ws_url(self) -> str:
        url = self.base_url
        if url.startswith("https://"):
            url = "wss://" + url[len("https://"):]
        elif url.startswith("http://"):
            url = "ws://" + url[len("http://"):]
        return f"{url}/api/v1/reminder/ws?device_id={self.device_id}&token={self.token}"

    async def ws_listener(self):
        import websockets

        try:
            async with websockets.connect(self.ws_url()) as ws:
                while not self._ws_stop.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    try:
                        self.ws_messages.append(json.loads(raw))
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            record("ws.connect", False, f"{type(e).__name__}: {e}")

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    async def step_health(self) -> bool:
        r = await self.client.get(f"{self.base_url}/api/v1/health")
        ok = r.status_code == 200 and r.json().get("status") == "ok"
        record("health", ok, f"status={r.status_code}")
        return ok

    async def step_register_device(self) -> bool:
        r = await self.client.post(
            f"{self.api}/device/register",
            json={
                "device_id": self.device_id,
                "device_name": "e2e-check",
                "app_version": "0.1.0",
            },
        )
        ok = r.status_code in (200, 201) and r.json().get("device_id") == self.device_id
        record("device.register", ok, f"status={r.status_code}")
        return ok

    async def create_reminder(self, title: str, delay_seconds: int = 3) -> Optional[int]:
        trigger = datetime.now() + timedelta(seconds=delay_seconds)
        r = await self.client.post(
            f"{self.api}/",
            json={
                "type": "test.ping",
                "title": title,
                "body": "e2e check",
                "trigger_time": trigger.isoformat(),
                "expire_after_minutes": 240,
            },
        )
        if r.status_code not in (200, 201):
            record(f"create[{title}]", False, f"status={r.status_code} body={r.text[:200]}")
            return None
        data = r.json()
        ok = data.get("state") == "PENDING"
        record(f"create[{title}]", ok, f"id={data.get('id')} state={data.get('state')}")
        return data.get("id") if ok else None

    async def wait_delivered(self, reminder_id: int, title: str) -> bool:
        """轮询 /pending 直到该提醒变为 DELIVERED"""
        deadline = datetime.now() + timedelta(seconds=self.delivery_timeout)
        while datetime.now() < deadline:
            r = await self.client.get(f"{self.api}/pending")
            if r.status_code == 200:
                for item in r.json():
                    if item.get("id") == reminder_id and item.get("state") == "DELIVERED":
                        record(f"deliver[{title}]", True, f"id={reminder_id}")
                        return True
            await asyncio.sleep(2)
        record(f"deliver[{title}]", False, f"timeout {self.delivery_timeout}s")
        return False

    def check_ws_delivered(self, reminder_id: int, title: str) -> None:
        hit = any(
            m.get("type") == "reminder.delivered"
            and (m.get("data") or {}).get("id") == reminder_id
            for m in self.ws_messages
        )
        record(f"ws.push[{title}]", hit, f"ws_messages={len(self.ws_messages)}")

    async def step_feedback(
        self, reminder_id: int, action: str, expect_state: str, option: str = ""
    ) -> bool:
        body: Dict[str, Any] = {"action": action}
        if option:
            body["option"] = option
        r = await self.client.post(f"{self.api}/{reminder_id}/feedback", json=body)
        ok = r.status_code in (200, 201) and r.json().get("state") == expect_state
        state = r.json().get("state") if r.status_code in (200, 201) else r.text[:120]
        record(f"feedback[{action}->{expect_state}]", ok, f"status={r.status_code} state={state}")
        return ok

    async def step_ack(self, reminder_id: int) -> bool:
        r = await self.client.post(
            f"{self.api}/ack",
            json={"reminder_id": reminder_id, "device_id": self.device_id},
        )
        ok = r.status_code in (200, 201) and r.json().get("ok") is True
        record("ack", ok, f"status={r.status_code}")
        return ok

    async def check_events(self, reminder_id: int, expected_subseq: List[str], title: str) -> bool:
        r = await self.client.get(f"{self.api}/{reminder_id}/events")
        if r.status_code != 200:
            record(f"events[{title}]", False, f"status={r.status_code}")
            return False
        events = [e.get("event") for e in r.json()]
        # 子序列匹配（事件按 id 升序）
        it = iter(events)
        ok = all(any(e == x for e in it) for x in expected_subseq)
        record(f"events[{title}]", ok, f"events={events}")
        return ok

    async def step_summary(self) -> bool:
        r = await self.client.get(f"{self.api}/summary/today")
        ok = r.status_code == 200 and "pending" in r.json()
        record("summary.today", ok, json.dumps(r.json() if ok else {}, ensure_ascii=False))
        return ok

    async def step_history(self, ids: List[int]) -> bool:
        date = datetime.now().strftime("%Y-%m-%d")
        r = await self.client.get(f"{self.api}/history", params={"date": date})
        if r.status_code != 200:
            record("history", False, f"status={r.status_code}")
            return False
        found = {item.get("id") for item in r.json()}
        missing = [i for i in ids if i not in found]
        record("history", not missing, f"missing={missing}" if missing else f"all {len(ids)} found")
        return not missing


async def main_async(args) -> int:
    e2e = ReminderE2E(args.base_url, args.token, args.delivery_timeout)
    ws_task: Optional[asyncio.Task] = None
    try:
        if not await e2e.step_health():
            print_summary()
            return 1
        await e2e.step_register_device()

        if not args.skip_ws:
            ws_task = asyncio.create_task(e2e.ws_listener())
            await asyncio.sleep(1.5)  # 等 connected
            connected = any(m.get("type") == "connected" for m in e2e.ws_messages)
            record("ws.connect", connected, f"ws_messages={len(e2e.ws_messages)}")

        # ---------------- A：完整闭环 ----------------
        a_id = await e2e.create_reminder("e2e-A")
        if a_id is not None:
            if await e2e.wait_delivered(a_id, "A"):
                if ws_task is not None:
                    await asyncio.sleep(0.5)
                    e2e.check_ws_delivered(a_id, "A")
                await e2e.step_ack(a_id)
                await e2e.step_feedback(a_id, "open", "OPENED")
                await e2e.step_feedback(a_id, "resolve", "RESOLVED")
                await e2e.check_events(
                    a_id, ["created", "delivered", "ack", "opened", "resolved"], "A"
                )

        # ---------------- B：snooze 路径 ----------------
        b_id = await e2e.create_reminder("e2e-B")
        if b_id is not None:
            if await e2e.wait_delivered(b_id, "B"):
                before = datetime.now()
                ok = await e2e.step_feedback(b_id, "snooze", "SNOOZED", option="15m")
                if ok:
                    r = await e2e.client.get(f"{e2e.api}/pending")
                    item = next(
                        (x for x in r.json() if x.get("id") == b_id), {}
                    )
                    ntt = item.get("next_trigger_time")
                    snooze_ok = item.get("snooze_count") == 1 and ntt is not None
                    if ntt:
                        ntt_dt = datetime.fromisoformat(ntt)
                        delta = (ntt_dt - before).total_seconds()
                        snooze_ok = snooze_ok and 14 * 60 < delta < 16 * 60
                    record("snooze.fields", snooze_ok, f"next_trigger_time={ntt}")
                    await e2e.check_events(b_id, ["created", "delivered", "snoozed"], "B")
                if args.wait_redelivery:
                    if await e2e.wait_delivered(b_id, "B-redelivery"):
                        await e2e.check_events(
                            b_id, ["created", "delivered", "snoozed", "delivered"], "B-redelivery"
                        )
                # dismiss 收尾（SNOOZED → IGNORED）
                await e2e.step_feedback(b_id, "dismiss", "IGNORED")

        # ---------------- C：dismiss 路径 ----------------
        c_id = await e2e.create_reminder("e2e-C")
        if c_id is not None:
            if await e2e.wait_delivered(c_id, "C"):
                await e2e.step_feedback(c_id, "dismiss", "IGNORED")
                await e2e.check_events(c_id, ["created", "delivered", "dismissed"], "C")

        # ---------------- 汇总查询 ----------------
        await e2e.step_summary()
        await e2e.step_history([i for i in (a_id, b_id, c_id) if i is not None])
    finally:
        if ws_task is not None:
            e2e._ws_stop.set()
            ws_task.cancel()
            try:
                await ws_task
            except (asyncio.CancelledError, Exception):
                pass
        await e2e.close()

    print_summary()
    return 0 if all(ok for _, ok, _ in RESULTS) else 1


def print_summary() -> None:
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("=" * 60)
    print(f"E2E SUMMARY: {passed}/{total} passed")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED: {name} -- {detail}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reminder M1 E2E check")
    parser.add_argument("--base-url", default="http://127.0.0.1:1974")
    parser.add_argument("--token", default="", help="SAILZEN_API_TOKEN（服务端未配置可留空）")
    parser.add_argument(
        "--delivery-timeout",
        type=float,
        default=75.0,
        help="等待 DELIVERED 的超时秒数（应大于 REMINDER_SCAN_INTERVAL_SECONDS）",
    )
    parser.add_argument("--skip-ws", action="store_true", help="跳过 WebSocket 推送验证")
    parser.add_argument(
        "--wait-redelivery",
        action="store_true",
        help="真实等待 15 分钟验证 snooze 到点重投（默认跳过）",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
