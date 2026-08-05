# -*- coding: utf-8 -*-
# @file rhythm_client.py
# @brief RhythmClient CLI - 生活/工作节奏综合优先级调节工具命令行（人类/AI 双模式）
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
RhythmClient CLI 工具

通过 sail_server 的 HTTP API（/api/v1/rhythm）与远程服务器交互，
覆盖：快速捕获/AI 分拣/确认、基础节奏模板、戒律/习惯打卡、长期事业、
计划与时间线、评分复盘、精力画像、守护策略。

人类友好 + AI 友好双模式：所有命令支持 --json（AI 解析用，stdout 纯 JSON）。

工作流程示例：
  sailzen rhythm capture "每周运动3次" --json
  sailzen rhythm suggest-triage --json            # AI 拉取待分拣 + 分类学规范
  sailzen rhythm hint 1 --kind habit --meta '{"freq_per_week":3}'
  sailzen rhythm confirm 1 --accept-hint
  sailzen rhythm template upsert --file weekday_template.json
  sailzen rhythm plan today
  sailzen rhythm timeline today
  sailzen rhythm checkin 1 --result done
  sailzen rhythm score --week

AI 调用契约见 doc/design/manager/rhythm.md §7。
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from typing import Any, Optional

import requests

# ============================================================================
# Environment / Server URL Resolution（与 finance_client 同款）
# ============================================================================


def _load_env_file(env_path: str) -> dict:
    """手动解析 .env 文件（不依赖 python-dotenv）"""
    env = {}
    if not os.path.isfile(env_path):
        return env
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _resolve_default_server_url() -> str:
    """
    解析默认服务器地址。
    优先级：SAIL_SERVER_URL 环境变量 > .env.prod/.env.dev 的 SERVER_HOST/PORT > localhost:8000
    """
    env_url = os.environ.get("SAIL_SERVER_URL")
    if env_url:
        return env_url
    cwd = os.getcwd()
    for env_name in (".env.prod", ".env.dev", ".env"):
        env_path = os.path.join(cwd, env_name)
        if os.path.isfile(env_path):
            env = _load_env_file(env_path)
            host = env.get("SERVER_HOST", "localhost")
            port = env.get("SERVER_PORT", "8000")
            return f"http://{host}:{port}"
    return "http://localhost:8000"


DEFAULT_SERVER_URL = _resolve_default_server_url()

API_TIMEOUT = 30  # HTTP 请求超时（秒）
REQUEST_DELAY = 0.1  # 请求间隔（秒）

# ============================================================================
# 分类学权威定义（rhythm kinds 输出；与服务端 DTO 同源校验）
# ============================================================================

#: 9 类事务权威说明（AI 分拣 prompt 与人查阅的权威参考，保持文档/CLI/prompt 三处同源）
KIND_TAXONOMY: dict[str, dict[str, Any]] = {
    "base_rhythm": {
        "zh": "基础节奏",
        "lifecycle": "长期 ACTIVE⇄PAUSED→ARCHIVED",
        "domain": "life/work",
        "schedule": "每日骨架：由 DayTemplate 实例化，plan_day 最早铺底（通勤/工作窗/微节律/餐饮）",
        "kind_meta": {"template_id": "int?"},
        "examples": ["08:20-09:00 通勤", "09:00-12:00 工作窗(90/15)"],
    },
    "precept": {
        "zh": "戒律",
        "lifecycle": "长期 ACTIVE⇄PAUSED",
        "domain": "life",
        "schedule": "按日/按周规则：轻量打卡块 + 到点核销提醒；severity=hard 参与铺底（生活地板）",
        "kind_meta": {
            "rule_text": "str", "cycle": "daily|weekly", "weekday_mask": "[7]",
            "check_time": "HH:MM", "severity": "hard|soft", "block_minutes": "int",
        },
        "examples": ["23:30前入睡(hard)", "三餐定时", "每周一天无零食日(weekly)"],
    },
    "habit": {
        "zh": "习惯养成",
        "lifecycle": "长期 ACTIVE⇄PAUSED",
        "domain": "life",
        "schedule": "频率目标制：每周 N 次、单次最小时长、偏好槽位；按周缺口压力竞争弹性区（生活地板）",
        "kind_meta": {
            "freq_per_week": "int", "min_session_minutes": "int",
            "preferred_slots": ["HH:MM-HH:MM"],
        },
        "examples": ["每周运动3次,每次>=30min,偏好19:00-21:00"],
    },
    "fixed_plan": {
        "zh": "刚性规划",
        "lifecycle": "一次性 INBOX→PLANNED(confirm 直接)→SCHEDULED→DOING→DONE",
        "domain": "life/work",
        "schedule": "刚性钉：固定起止 immovable，排程器绕开它；禁 defer；可挂子事务（行程段）",
        "kind_meta": {"immovable": "bool", "fixed_start": "datetime", "fixed_end": "datetime",
                      "legs": "[int]"},
        "examples": ["10.1-10.5 家人旅行", "周四 14:00 高铁赴沪"],
    },
    "task_oneoff": {
        "zh": "一次性工作任务",
        "lifecycle": "一次性 INBOX→PLANNED→SCHEDULED→DOING→DONE",
        "domain": "work",
        "schedule": "按 ddl 紧迫度竞争弹性工作区（工作窗内优先，超窗标记 overtime）",
        "kind_meta": {},
        "examples": ["写季度总结", "修复某个线上 bug"],
    },
    "task_maintenance": {
        "zh": "长期维护任务",
        "lifecycle": "长期 ACTIVE⇄PAUSED",
        "domain": "work",
        "schedule": "SLA 周期制：interval_days + last_done_at，越接近/超过周期紧迫度越高",
        "kind_meta": {"interval_days": "int", "last_done_at": "datetime?", "session_minutes": "int"},
        "examples": ["每周代码巡检", "服务器月度维护"],
    },
    "venture": {
        "zh": "长期事业",
        "lifecycle": "长期，达成目标日后 GRADUATE→DONE",
        "domain": "career",
        "schedule": "目标日倒排：target_date + 每周业余小时预算 + 里程碑链；仅排业余时间区",
        "kind_meta": {"target_date": "date", "weekly_budget_hours": "float",
                      "spare_time_only": "bool", "total_est_hours": "float"},
        "examples": ["2027-04 独立游戏上线:每周8h,里程碑 demo/内测/上架"],
    },
    "buffer": {
        "zh": "系统缓冲",
        "lifecycle": "系统生成",
        "domain": "-",
        "schedule": "强制留白(min_buffer_ratio)，分散插入，只读禁编辑",
        "kind_meta": {},
        "examples": [],
    },
    "generic": {
        "zh": "未分类",
        "lifecycle": "一次性（捕获默认值）",
        "domain": "待定",
        "schedule": "停留 INBOX 等待 AI 分拣 + 人确认改判为上述具体 kind",
        "kind_meta": {},
        "examples": ["给车做保养(一句话捕获)"],
    },
}

#: 分拣判定规则（precept vs habit 边界）
TRIAGE_RULES = [
    "惩罚性/禁止性规则（不吃零食、23:30 前睡）→ precept",
    "建设性/累计性目标（每周 3 次运动）→ habit",
    "固定起止不可移动（旅行/车票）→ fixed_plan",
    "业余长期推进且有目标日（独立游戏上线）→ venture(career)",
    "工作一次性交付 → task_oneoff(work)；周期性维护 → task_maintenance(work)",
]

# 尝试与服务端 DTO 同源校验 kind_meta（同仓库运行时可导入）
try:
    from sail_server.application.dto.rhythm import (
        AffairKind as _AffairKind,
        validate_kind_meta as _validate_kind_meta,
    )

    def validate_meta_locally(kind: str, meta: dict) -> dict:
        """同源校验：非法即 ValueError（CLI 拒绝）"""
        return _validate_kind_meta(_AffairKind(kind), meta)

    _HAS_SERVER_DTO = True
except Exception:  # pragma: no cover - 独立运行时的降级
    _HAS_SERVER_DTO = False

    def validate_meta_locally(kind: str, meta: dict) -> dict:
        if kind not in KIND_TAXONOMY:
            raise ValueError(f"未知 kind: {kind!r}（合法: {sorted(KIND_TAXONOMY)}）")
        return meta


# ============================================================================
# RhythmClient
# ============================================================================


class RhythmClient:
    """通过 HTTP API 与 sail_server 交互的 Rhythm 客户端"""

    def __init__(self, server_url: str, token: Optional[str] = None):
        self.server_url = server_url.rstrip("/")
        self.base_api = f"{self.server_url}/api/v1/rhythm"
        self.life_api = f"{self.server_url}/api/v1/life"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        token = token or os.environ.get("SAILZEN_API_TOKEN", "")
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    # ---------------- 内部 ----------------

    def _req(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_api}{path}"
        resp = self.session.request(method, url, timeout=API_TIMEOUT, **kwargs)
        if resp.status_code >= 400:
            raise RhythmAPIError(resp.status_code, resp.text[:300])
        if resp.content:
            return resp.json()
        return None

    # ---------------- Affair ----------------

    def capture(self, payload: dict) -> dict:
        return self._req("POST", "/affair/", json=payload)

    def list_affairs(self, params: Optional[dict] = None) -> list[dict]:
        data = self._req("GET", "/affair/", params=params or {})
        return (data or {}).get("affairs", [])

    def get_affair(self, affair_id: int) -> dict:
        return self._req("GET", f"/affair/{affair_id}")

    def update_affair(self, affair_id: int, payload: dict) -> dict:
        return self._req("PUT", f"/affair/{affair_id}", json=payload)

    def transit(self, affair_id: int, action: str, **kwargs) -> dict:
        payload = {"action": action, **kwargs}
        return self._req("POST", f"/affair/{affair_id}/state", json=payload)

    def confirm_hint(self, affair_id: int, accept: bool, overrides: Optional[dict] = None) -> dict:
        payload: dict[str, Any] = {"accept": accept}
        if overrides:
            payload["overrides"] = overrides
        return self._req("POST", f"/affair/{affair_id}/confirm-hint", json=payload)

    def split(self, affair_id: int, children: list[dict]) -> list[dict]:
        data = self._req("POST", f"/affair/{affair_id}/split", json={"children": children})
        return (data or {}).get("affairs", [])

    # ---------------- Template ----------------

    def list_templates(self) -> list[dict]:
        data = self._req("GET", "/template/")
        return (data or {}).get("templates", [])

    def get_template(self, template_id: int) -> dict:
        return self._req("GET", f"/template/{template_id}")

    def upsert_template(self, payload: dict) -> dict:
        return self._req("POST", "/template/", json=payload)

    def active_template(self, d: date) -> Optional[dict]:
        try:
            return self._req("GET", "/template/active", params={"date": d.isoformat()})
        except RhythmAPIError as e:
            if e.status == 404:
                return None
            raise

    # ---------------- Checkin ----------------

    def checkin(self, affair_id: int, result: str, log_date: Optional[str] = None,
                note: str = "") -> dict:
        payload: dict[str, Any] = {"affair_id": affair_id, "result": result, "note": note}
        if log_date:
            payload["log_date"] = log_date
        return self._req("POST", "/checkin/", json=payload)

    def checkin_today(self, d: Optional[date] = None) -> dict:
        params = {"date": d.isoformat()} if d else {}
        return self._req("GET", "/checkin/today", params=params)

    def list_checkins(self, params: Optional[dict] = None) -> list[dict]:
        data = self._req("GET", "/checkin/", params=params or {})
        return (data or {}).get("logs", [])

    # ---------------- Venture ----------------

    def venture_progress(self, venture_id: int) -> dict:
        return self._req("GET", f"/venture/{venture_id}/progress")

    def add_milestone(self, venture_id: int, payload: dict) -> dict:
        return self._req("POST", f"/venture/{venture_id}/milestone", json=payload)

    def milestone_done(self, milestone_id: int) -> dict:
        return self._req("POST", f"/venture/milestone/{milestone_id}/done")

    # ---------------- Timeline / Plan ----------------

    def timeline_day(self, d: date) -> dict:
        return self._req("GET", "/timeline/day", params={"date": d.isoformat()})

    def block_status(self, block_id: int, status: str) -> dict:
        return self._req("POST", f"/timeline/block/{block_id}/status", json={"status": status})

    def block_move(self, block_id: int, start: str, end: str) -> dict:
        return self._req(
            "POST", f"/timeline/block/{block_id}/move",
            json={"start_time": start, "end_time": end},
        )

    def plan_day(self, d: date, force: bool = False) -> dict:
        return self._req("POST", "/plan/day", json={"date": d.isoformat(), "force": force})

    def rebalance(self, d: date, trigger: str = "manual") -> dict:
        return self._req("POST", "/plan/rebalance",
                         json={"date": d.isoformat(), "trigger": trigger})

    def conflicts(self, d: date) -> dict:
        return self._req("GET", "/plan/conflicts", params={"date": d.isoformat()})

    # ---------------- Energy / Policy ----------------

    def get_profile(self) -> dict:
        return self._req("GET", "/energy/profile")

    def upsert_profile(self, payload: dict) -> dict:
        return self._req("PUT", "/energy/profile", json=payload)

    def list_policies(self) -> list[dict]:
        data = self._req("GET", "/policy/")
        return (data or {}).get("policies", [])

    def create_policy(self, payload: dict) -> dict:
        return self._req("POST", "/policy/", json=payload)

    def update_policy(self, policy_id: int, payload: dict) -> dict:
        return self._req("PUT", f"/policy/{policy_id}", json=payload)

    # ---------------- Review ----------------

    def review_day(self, d: date) -> dict:
        return self._req("GET", "/review/day", params={"date": d.isoformat()})

    def review_week(self, span: Optional[str] = None) -> dict:
        params = {"span": span} if span else {}
        return self._req("GET", "/review/week", params=params)

    def update_review_summary(self, scope: str, period_key: str, ai_summary: str) -> dict:
        return self._req(
            "PUT", f"/review/{scope}/{period_key}/summary", json={"ai_summary": ai_summary}
        )

    def encroachments(self, start: Optional[str] = None, end: Optional[str] = None) -> list[dict]:
        params = {}
        if start:
            params["start_date"] = start
        if end:
            params["end_date"] = end
        return self._req("GET", "/review/encroachments", params=params) or []

    # ---------------- Life（timespan 解析） ----------------

    def resolve_timespan(self, name: str, span_class: str) -> Optional[dict]:
        url = f"{self.life_api}/timespan/by-name"
        resp = self.session.get(
            url, params={"name": name, "class": span_class}, timeout=API_TIMEOUT
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


class RhythmAPIError(Exception):
    """API 错误（保留 HTTP 状态码）"""

    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


# ============================================================================
# 输出助手
# ============================================================================


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _out(args, data: Any, human_fn=None) -> None:
    """双模式输出：--json 纯 JSON；否则人类可读"""
    if getattr(args, "json", False):
        _print_json(data)
    elif human_fn is not None:
        human_fn(data)
    else:
        _print_json(data)


def _parse_date_arg(s: Optional[str]) -> date:
    """today/tomorrow/昨天/ISO 日期"""
    if not s or s == "today":
        return date.today()
    if s == "tomorrow":
        return date.today() + timedelta(days=1)
    if s == "yesterday":
        return date.today() - timedelta(days=1)
    return date.fromisoformat(s[:10])


def _parse_json_arg(raw: Optional[str], name: str) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: --{name} 非法 JSON: {e}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict):
        print(f"Error: --{name} 应为 JSON 对象", file=sys.stderr)
        sys.exit(2)
    return data


def _parse_window(raw: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """--window 2026-10-27T19:00/2026-10-28T21:00"""
    if not raw:
        return None, None
    if "/" not in raw:
        print("Error: --window 应为 start/end 格式", file=sys.stderr)
        sys.exit(2)
    start, end = raw.split("/", 1)
    return start.strip(), end.strip()


def _fmt_block(b: dict) -> str:
    start = str(b.get("start_time", ""))[11:16]
    end = str(b.get("end_time", ""))[11:16]
    title = b.get("affair_title") or (b.get("ref") or {}).get("label") or ""
    pin = "📌" if b.get("pinned") else "  "
    status = b.get("status", "")
    return f"  {pin} {start}-{end} [{b.get('block_type')}] {title} ({status}) #{b.get('id')}"


# ============================================================================
# CLI Commands: 捕获与分拣
# ============================================================================


def cmd_capture(args):
    client = RhythmClient(args.server)
    kind = args.kind or "generic"
    meta = _parse_json_arg(args.meta, "meta")
    # CLI 侧同源校验（非法即拒绝）
    try:
        meta = validate_meta_locally(kind, meta)
    except ValueError as e:
        print(f"Error: kind_meta 校验失败: {e}", file=sys.stderr)
        sys.exit(2)
    payload: dict[str, Any] = {"title": args.title, "kind": kind}
    if meta:
        payload["kind_meta"] = meta
    if args.domain:
        payload["domain"] = args.domain
    if args.desc:
        payload["description"] = args.desc
    affair = client.capture(payload)
    _out(args, affair, lambda a: print(f"[OK] 捕获 #{a['id']} ({a['kind']}) → INBOX: {a['title']}"))


def cmd_kinds(args):
    """输出分类学说明（AI 分拣与人查阅的权威参考）"""
    payload = {"kinds": KIND_TAXONOMY, "triage_rules": TRIAGE_RULES}

    def _human(data):
        print("=" * 72)
        print("Rhythm 事务分类学（9 类 kind × 3 域 domain）")
        print("=" * 72)
        for kind, info in data["kinds"].items():
            print(f"\n■ {kind}（{info['zh']}）  域: {info['domain']}")
            print(f"  生命周期: {info['lifecycle']}")
            print(f"  排程行为: {info['schedule']}")
            if info["kind_meta"]:
                print(f"  kind_meta: {json.dumps(info['kind_meta'], ensure_ascii=False)}")
            for ex in info["examples"]:
                print(f"  例: {ex}")
        print("\n分拣判定规则:")
        for rule in data["triage_rules"]:
            print(f"  - {rule}")

    _out(args, payload, _human)


def cmd_inbox(args):
    client = RhythmClient(args.server)
    affairs = client.list_affairs({"state": "INBOX", "limit": args.limit})

    def _human(items):
        if not items:
            print("INBOX 为空。")
            return
        print(f"{'ID':>6}  {'kind':<18}  {'importance':>4}  标题")
        print("-" * 70)
        for a in items:
            hint = "💡" if a.get("ai_hint") else "  "
            print(f"{a['id']:>6}  {a['kind']:<18}  {a.get('importance', ''):>4}  {hint} {a['title']}")

    _out(args, affairs, _human)


def cmd_suggest_triage(args):
    """【AI 用】拉 INBOX，输出待分拣事务 + 分类学规范（含 kind_meta 草案 schema）"""
    client = RhythmClient(args.server)
    affairs = client.list_affairs({"state": "INBOX", "limit": args.limit})
    payload = {
        "instruction": (
            "对 affairs 中每个事务给出分拣建议：kind(九选一)/domain/kind_meta 草案/"
            "importance(1-5)/energy_cost/est_minutes/window/fallback_plan/split_children。"
            "然后对每个事务调用: sailzen rhythm hint <id> --kind <kind> --meta '<json>' ..."
        ),
        "kinds": KIND_TAXONOMY,
        "triage_rules": TRIAGE_RULES,
        "affairs": affairs,
        "hint_schema": {
            "kind": "九选一",
            "domain": "life|work|career",
            "kind_meta": "按 kinds[kind].kind_meta",
            "importance": "1-5",
            "energy_cost": "轻量5/常规10/深度25/重决策40",
            "est_minutes": "int",
            "window": "ISO start/end 或 null",
            "fallback_plan": "Plan B 文字",
        },
    }
    _out(args, payload)


def cmd_hint(args):
    """【AI 写回建议】写 ai_hint（不落状态，待人 confirm）"""
    client = RhythmClient(args.server)
    kind = args.kind
    meta = _parse_json_arg(args.meta, "meta")
    if kind:
        try:
            meta = validate_meta_locally(kind, meta)
        except ValueError as e:
            print(f"Error: kind_meta 校验失败: {e}", file=sys.stderr)
            sys.exit(2)
    hint: dict[str, Any] = {}
    if kind:
        hint["kind"] = kind
    if args.domain:
        hint["domain"] = args.domain
    if meta:
        hint["kind_meta"] = meta
    if args.importance:
        hint["importance"] = args.importance
    if args.energy is not None:
        hint["energy_cost"] = args.energy
    if args.est is not None:
        hint["est_minutes"] = args.est
    if args.money is not None:
        hint["money_cost"] = args.money
    ws, we = _parse_window(args.window)
    if ws:
        hint["window_start"] = ws
    if we:
        hint["window_end"] = we
    if args.fallback:
        hint["fallback_plan"] = args.fallback
    if args.reason:
        hint["reason"] = args.reason
    if not hint:
        print("Error: hint 内容为空", file=sys.stderr)
        sys.exit(2)
    affair = client.update_affair(args.id, {"ai_hint": hint})
    _out(args, affair, lambda a: print(f"[OK] 建议已写回 #{a['id']}（待确认）: {json.dumps(hint, ensure_ascii=False)}"))


def cmd_suggest_split(args):
    """【AI 用】拆分建议草案（不落库）"""
    client = RhythmClient(args.server)
    affair = client.get_affair(args.id)
    payload = {
        "instruction": (
            "给出拆分建议（不落库）：子事务数组 children[]，每项含 title/kind/domain/"
            "kind_meta/est_minutes/urgency_ddl/timespan_id。"
            "venture → 里程碑链；确认后调用: sailzen rhythm split <id> --file split.json"
        ),
        "affair": affair,
        "split_schema": {
            "children": [
                {"title": "str", "kind": "九选一?", "domain": "life|work|career?",
                 "kind_meta": "{}", "est_minutes": "int?", "urgency_ddl": "datetime?",
                 "timespan_id": "int?"}
            ]
        },
    }
    _out(args, payload)


def cmd_split(args):
    """确认后落库拆分"""
    if not os.path.exists(args.file):
        print(f"Error: 文件不存在: {args.file}", file=sys.stderr)
        sys.exit(1)
    with open(args.file, "r", encoding="utf-8") as f:
        payload = json.load(f)
    children = payload.get("children", payload if isinstance(payload, list) else [])
    if not children:
        print("Error: split 文件中 children 为空", file=sys.stderr)
        sys.exit(2)
    # CLI 侧校验每个子事务的 kind/kind_meta
    for child in children:
        if child.get("kind"):
            try:
                child["kind_meta"] = validate_meta_locally(
                    child["kind"], child.get("kind_meta") or {}
                )
            except ValueError as e:
                print(f"Error: 子事务「{child.get('title')}」kind_meta 校验失败: {e}",
                      file=sys.stderr)
                sys.exit(2)
    client = RhythmClient(args.server)
    created = client.split(args.id, children)
    _out(args, created, lambda items: print(f"[OK] 拆出 {len(items)} 个子事务: "
                                            + ", ".join(f"#{c['id']} {c['title']}" for c in items)))


def cmd_confirm(args):
    """确认：一次性流→PLANNED；长期流→ACTIVE；fixed_plan→SCHEDULED(钉入)"""
    client = RhythmClient(args.server)
    hint_result = None
    if args.accept_hint:
        hint_result = client.confirm_hint(args.id, accept=True)
        time.sleep(REQUEST_DELAY)
    affair = client.transit(args.id, "confirm")
    if args.json:
        _print_json({"hint_applied": hint_result, "affair": affair})
    else:
        if hint_result:
            print(f"[OK] 已采纳建议: #{hint_result['id']} kind={hint_result['kind']}")
        print(f"[OK] #{affair['id']} → {affair['state']}: {affair['title']}")


def cmd_defer(args):
    """显式弹性推迟（fixed_plan 拒绝 409）"""
    client = RhythmClient(args.server)
    defer_to = date.fromisoformat(args.to).isoformat()
    if len(args.to) <= 10:
        defer_to = f"{args.to}T09:00:00"
    try:
        affair = client.transit(args.id, "defer", defer_to=defer_to)
    except RhythmAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    _out(args, affair, lambda a: print(f"[OK] #{a['id']} → DEFERRED (新窗口 {a.get('window_start')})"))


# ============================================================================
# CLI Commands: 模板
# ============================================================================


def cmd_template_list(args):
    client = RhythmClient(args.server)
    templates = client.list_templates()

    def _human(items):
        if not items:
            print("无模板。")
            return
        for t in items:
            flag = "✅" if t.get("enabled") else "⏸️"
            print(f"{flag} #{t['id']} {t['name']} (priority={t.get('priority', 0)}) "
                  f"mask={t.get('weekday_mask')} slots={len(t.get('slots') or [])}")

    _out(args, templates, _human)


def cmd_template_show(args):
    client = RhythmClient(args.server)
    _out(args, client.get_template(args.id))


def cmd_template_upsert(args):
    if not os.path.exists(args.file):
        print(f"Error: 文件不存在: {args.file}", file=sys.stderr)
        sys.exit(1)
    with open(args.file, "r", encoding="utf-8") as f:
        payload = json.load(f)
    client = RhythmClient(args.server)
    tpl = client.upsert_template(payload)
    _out(args, tpl, lambda t: print(f"[OK] 模板 upsert: #{t['id']} {t['name']}"))


def cmd_template_active(args):
    client = RhythmClient(args.server)
    tpl = client.active_template(_parse_date_arg(args.date))
    if tpl is None:
        print("当日无命中模板。")
        return
    _out(args, tpl)


# ============================================================================
# CLI Commands: 打卡
# ============================================================================


def cmd_checkin(args):
    client = RhythmClient(args.server)
    if args.target == "today":
        resp = client.checkin_today(_parse_date_arg(args.date))
        _out(args, resp, _human_checkin_today)
        return
    try:
        affair_id = int(args.target)
    except ValueError:
        print("Error: checkin 目标应为 affair_id 或 today", file=sys.stderr)
        sys.exit(2)
    if not args.result:
        print("Error: 打卡需 --result kept|violated|done|missed|exempt", file=sys.stderr)
        sys.exit(2)
    try:
        log = client.checkin(affair_id, args.result, args.log_date, args.note or "")
    except RhythmAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    _out(args, log, lambda x: print(f"[OK] 打卡 #{x['affair_id']} → {x['result']} ({x['log_date']})"))


def _human_checkin_today(data: dict) -> None:
    print(f"今日待打卡（{data.get('date')}）:")
    print("  戒律:")
    for item in data.get("precepts", []):
        a = item["affair"]
        flag = "✅" if item.get("done_today") else "⬜"
        meta = a.get("kind_meta") or {}
        print(f"    {flag} #{a['id']} {meta.get('rule_text') or a['title']} "
              f"({item.get('last_result') or '未打卡'})")
    print("  习惯:")
    for item in data.get("habits", []):
        a = item["affair"]
        flag = "✅" if item.get("done_today") else "⬜"
        print(f"    {flag} #{a['id']} {a['title']} "
              f"本周 {item.get('week_done_count')}/{item.get('week_target')}")


def cmd_habit_board(args):
    """习惯看板：streak/本周缺口/最佳连续"""
    client = RhythmClient(args.server)
    habits = client.list_affairs({"kind": ["habit"], "state": "ACTIVE"})
    today = client.checkin_today()
    done_map = {h["affair"]["id"]: h for h in today.get("habits", [])}
    board = []
    for h in habits:
        meta = h.get("kind_meta") or {}
        today_item = done_map.get(h["id"], {})
        board.append({
            "id": h["id"],
            "title": h["title"],
            "streak": meta.get("streak", 0),
            "best_streak": meta.get("best_streak", 0),
            "week_done": today_item.get("week_done_count", 0),
            "week_target": meta.get("freq_per_week", 3),
            "last_done_date": meta.get("last_done_date"),
        })

    def _human(items):
        if not items:
            print("无 ACTIVE 习惯。")
            return
        print(f"{'ID':>4}  {'streak':>6}  {'best':>4}  {'本周':>7}  标题")
        print("-" * 60)
        for b in items:
            flame = "🔥" if b["streak"] >= 3 else "  "
            print(f"{b['id']:>4}  {flame}{b['streak']:>4}  {b['best_streak']:>4}  "
                  f"{b['week_done']}/{b['week_target']:>2}   {b['title']}")

    _out(args, board, _human)


# ============================================================================
# CLI Commands: 长期事业
# ============================================================================


def _resolve_span_arg(client: RhythmClient, span: Optional[str]) -> Optional[int]:
    """解析 --span（Y2027Q2/B0049/Y2027M04/W0049）→ timespan_id"""
    if not span:
        return None
    s = span.strip()
    span_class = None
    if s.startswith("Y") and "Q" in s:
        span_class = "quarter"
    elif s.startswith("Y") and "BM" in s:
        span_class = "bimonth"
    elif s.startswith("Y") and "M" in s:
        span_class = "month"
    elif s.startswith("B"):
        span_class = "biweek"
    elif s.startswith("W"):
        span_class = "week"
    if span_class is None:
        print(f"Error: 无法识别 span 格式: {span!r}（例 Y2027Q2 / B0049）", file=sys.stderr)
        sys.exit(2)
    ts = client.resolve_timespan(s, span_class)
    if ts is None:
        print(f"Error: TimeSpan 不存在: {span_class}/{s}", file=sys.stderr)
        sys.exit(1)
    return ts["id"]


def cmd_venture_status(args):
    client = RhythmClient(args.server)
    if args.id is not None:
        progress = client.venture_progress(args.id)
        _out(args, progress, _human_venture_progress)
        return
    ventures = client.list_affairs({"kind": ["venture"]})
    progresses = []
    for v in ventures:
        if v["state"] in ("ACTIVE", "PAUSED"):
            progresses.append(client.venture_progress(v["id"]))
            time.sleep(REQUEST_DELAY)

    def _human(items):
        if not items:
            print("无 venture。")
            return
        for p in items:
            _human_venture_progress(p)
            print("-" * 60)

    _out(args, progresses, _human)


def _human_venture_progress(p: dict) -> None:
    pressure = p.get("countdown_pressure")
    lamp = "🟢"
    if pressure is not None and pressure > 1.0:
        lamp = "🔴"
    elif pressure is not None and pressure > 0.8:
        lamp = "🟡"
    print(f"{lamp} #{p['affair_id']} {p['title']}")
    print(f"   目标日: {p.get('target_date')}  剩余: {p.get('weeks_left')} 周")
    print(f"   本周预算: {p.get('week_consumed_hours')}h / {p.get('weekly_budget_hours')}h"
          f"  累计: {p.get('total_done_hours')}h / 预估 {p.get('total_est_hours')}h")
    print(f"   倒排压力: {pressure}  里程碑完成: {p.get('completion_ratio', 0) * 100:.0f}%")
    for m in p.get("milestones", []):
        flag = "✅" if m["state"] == "DONE" else "⬜"
        print(f"     {flag} #{m['id']} {m['title']} ({m['state']})")


def cmd_venture_milestone(args):
    client = RhythmClient(args.server)
    timespan_id = _resolve_span_arg(client, args.span)
    payload: dict[str, Any] = {"title": args.title}
    if timespan_id:
        payload["timespan_id"] = timespan_id
    if args.ddl:
        payload["urgency_ddl"] = args.ddl
    milestone = client.add_milestone(args.id, payload)
    _out(args, milestone, lambda m: print(f"[OK] 里程碑 #{m['id']}: {m['title']}"))


# ============================================================================
# CLI Commands: 计划与时间线
# ============================================================================


def cmd_plan(args):
    client = RhythmClient(args.server)
    d = _parse_date_arg(args.date)
    resp = client.plan_day(d, force=args.force)

    def _human(data):
        print(f"日计划 {data['date']} (plan_version={data['plan_version']}, "
              f"{len(data['blocks'])} 块):")
        for b in sorted(data["blocks"], key=lambda x: x.get("start_time", "")):
            print(_fmt_block(b))
        for w in data.get("warnings", []):
            print(f"  ⚠️ [{w['code']}] {w['message']}")
        for u in data.get("unplaced", []):
            print(f"  ❌ 未排入: #{u['affair_id']} {u['title']}（{u['reason']}）")

    _out(args, resp, _human)


def cmd_timeline(args):
    client = RhythmClient(args.server)
    d = _parse_date_arg(args.date)
    resp = client.timeline_day(d)

    def _human(data):
        print(f"时间线 {data['date']} (plan_version={data['plan_version']}):")
        for b in sorted(data["blocks"], key=lambda x: x.get("start_time", "")):
            print(_fmt_block(b))
        dm = data.get("domain_minutes", {})
        print(f"\n三域投入: 生活 {dm.get('life', 0)}min / 工作 {dm.get('work', 0)}min / "
              f"事业 {dm.get('career', 0)}min")
        print(f"精力: {data.get('energy_consumed')}/{data.get('energy_budget')}  "
              f"缓冲: {data.get('buffer_free_minutes')}/{data.get('buffer_total_minutes')}min 剩余")
        checkins = data.get("checkins") or {}
        pending_p = [x for x in checkins.get("precepts", []) if not x.get("done_today")]
        pending_h = [x for x in checkins.get("habits", []) if not x.get("done_today")]
        if pending_p or pending_h:
            print(f"待打卡: 戒律 {len(pending_p)} 项 / 习惯 {len(pending_h)} 项")

    _out(args, resp, _human)


def cmd_block_done(args):
    client = RhythmClient(args.server)
    block = client.block_status(args.block_id, "DONE")
    _out(args, block, lambda b: print(f"[OK] 块 #{b['id']} → DONE"))


def cmd_block_skip(args):
    client = RhythmClient(args.server)
    block = client.block_status(args.block_id, "SKIPPED")
    _out(args, block, lambda b: print(f"[OK] 块 #{b['id']} → SKIPPED"))


def cmd_rebalance(args):
    client = RhythmClient(args.server)
    resp = client.rebalance(_parse_date_arg(args.date), trigger=args.trigger)

    def _human(data):
        print(f"再平衡 {data['date']} → plan_version={data['plan_version']}, "
              f"{len(data['blocks'])} 块, {len(data.get('warnings', []))} 警告, "
              f"{len(data.get('unplaced', []))} 未排入")

    _out(args, resp, _human)


# ============================================================================
# CLI Commands: 评分与复盘
# ============================================================================


def cmd_conflicts(args):
    """冲突/侵占报告"""
    client = RhythmClient(args.server)
    resp = client.conflicts(_parse_date_arg(args.date))

    def _human(data):
        items = data.get("encroachments", [])
        if not items:
            print(f"{data['date']} 无侵占事件 ✅")
            return
        print(f"{data['date']} 侵占事件 {len(items)} 起:")
        for e in items:
            print(f"  ⚠️ [{e['type']}] {e['message']}")

    _out(args, resp, _human)


def cmd_score(args):
    client = RhythmClient(args.server)
    if args.week:
        resp = client.review_week(args.span)
    else:
        resp = client.review_day(_parse_date_arg(args.date))

    def _human(r):
        scope = "周" if args.week else "日"
        print(f"节奏{scope}评 {r['period_key']}: {r['rhythm_score']:.1f} / 100")
        print(f"  戒律合规率:   {r['precept_compliance_rate'] * 100:.0f}%")
        print(f"  习惯达标率:   {r['habit_consistency'] * 100:.0f}%")
        print(f"  睡眠窗守约:   {r['sleep_window_keeping'] * 100:.0f}%")
        print(f"  事业预算达成: {r['venture_budget_fulfillment'] * 100:.0f}%")
        print(f"  缓冲消耗:     {r['buffer_consumed'] * 100:.0f}%")
        dm = r.get("domain_minutes", {})
        print(f"  三域投入: 生活 {dm.get('life', 0)} / 工作 {dm.get('work', 0)} / "
              f"事业 {dm.get('career', 0)} (min)")
        if r.get("encroachments"):
            print(f"  侵占事件: {len(r['encroachments'])} 起")

    _out(args, resp, _human)


def cmd_review(args):
    """复盘报告（--md 输出 Markdown，供 notes 模块归档）"""
    client = RhythmClient(args.server)
    resp = client.review_week(args.span) if args.week else client.review_day(
        _parse_date_arg(args.date)
    )
    if args.md:
        dm = resp.get("domain_minutes", {})
        lines = [
            f"# 节奏复盘 {resp['period_key']}（{'周' if args.week else '日'}）",
            "",
            f"- 节奏分: **{resp['rhythm_score']:.1f}** / 100",
            f"- 戒律合规率: {resp['precept_compliance_rate'] * 100:.0f}%",
            f"- 习惯达标率: {resp['habit_consistency'] * 100:.0f}%",
            f"- 睡眠窗守约: {resp['sleep_window_keeping'] * 100:.0f}%",
            f"- 事业预算达成: {resp['venture_budget_fulfillment'] * 100:.0f}%",
            f"- 缓冲消耗: {resp['buffer_consumed'] * 100:.0f}%",
            f"- 三域投入(min): 生活 {dm.get('life', 0)} / 工作 {dm.get('work', 0)} / "
            f"事业 {dm.get('career', 0)}",
            f"- 侵占事件: {len(resp.get('encroachments') or [])} 起",
        ]
        if resp.get("ai_summary"):
            lines += ["", "## AI 周评", "", resp["ai_summary"]]
        print("\n".join(lines))
        return
    _out(args, resp)


def cmd_summary(args):
    """【AI】写回复盘评语（rhythm_reviews.ai_summary）"""
    client = RhythmClient(args.server)
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: 文件不存在: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    elif args.text:
        text = args.text
    else:
        # stdin 管道输入
        text = sys.stdin.read()
    if not text.strip():
        print("Error: 评语内容为空（--file/--text/stdin 三选一）", file=sys.stderr)
        sys.exit(2)
    # period_key 缺省自动解析：week → 当前 ISO 周；day → 今日
    key = args.key
    if not key:
        today = date.today()
        if args.scope == "week":
            iso = today.isocalendar()
            key = f"W{iso[0]}-{iso[1]:02d}"
        else:
            key = today.isoformat()
    resp = client.update_review_summary(args.scope, key, text.strip())
    _out(args, resp, lambda r: print(f"[OK] 评语已写回 {r['scope']}/{r['period_key']}"))


def cmd_profile_show(args):
    client = RhythmClient(args.server)
    _out(args, client.get_profile())


def cmd_profile_set(args):
    client = RhythmClient(args.server)
    payload: dict[str, Any] = {"name": "default"}
    if args.work_cap is not None:
        payload["work_hours_cap"] = args.work_cap
    if args.energy_budget is not None:
        payload["daily_energy_budget"] = args.energy_budget
    if args.career_weight is not None:
        payload["career_weight"] = args.career_weight
    if args.life_weight is not None:
        payload["life_weight"] = args.life_weight
    if args.work_weight is not None:
        payload["work_weight"] = args.work_weight
    if args.buffer is not None:
        payload["min_buffer_ratio"] = args.buffer
    if args.sleep_start:
        payload["sleep_start"] = args.sleep_start
    if args.sleep_end:
        payload["sleep_end"] = args.sleep_end
    if args.spare_windows:
        payload["spare_time_windows"] = _parse_json_arg(args.spare_windows, "spare-windows")
    profile = client.upsert_profile(payload)
    _out(args, profile, lambda p: print(f"[OK] 精力画像已更新: budget={p['daily_energy_budget']}, "
                                        f"work_cap={p['work_hours_cap']}h, "
                                        f"buffer={p['min_buffer_ratio']}"))


def cmd_policy_list(args):
    client = RhythmClient(args.server)
    policies = client.list_policies()

    def _human(items):
        if not items:
            print("无策略。")
            return
        for p in items:
            flag = "✅" if p.get("enabled") else "⏸️"
            print(f"{flag} #{p['id']} {p['name']} [{p['rule_type']}] "
                  f"scope={p.get('scope')} params={json.dumps(p.get('params') or {}, ensure_ascii=False)}")

    _out(args, policies, _human)


def cmd_policy_add(args):
    client = RhythmClient(args.server)
    payload = {
        "name": args.name,
        "rule_type": args.rule_type,
        "params": _parse_json_arg(args.params, "params"),
        "scope": args.scope,
    }
    policy = client.create_policy(payload)
    _out(args, policy, lambda p: print(f"[OK] 策略 #{p['id']}: {p['name']}"))


def cmd_policy_toggle(args):
    client = RhythmClient(args.server)
    policies = client.list_policies()
    target = next((p for p in policies if p["id"] == args.id), None)
    if target is None:
        print(f"Error: 策略不存在: {args.id}", file=sys.stderr)
        sys.exit(1)
    policy = client.update_policy(args.id, {"enabled": not target["enabled"]})
    _out(args, policy, lambda p: print(f"[OK] 策略 #{p['id']} enabled={p['enabled']}"))


# ============================================================================
# Main Entry
# ============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="RhythmClient - SailZen 生活/工作节奏综合优先级调节 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    def add_common(p, with_json=True):
        p.add_argument(
            "--server",
            default=os.environ.get("SAIL_SERVER_URL", DEFAULT_SERVER_URL),
            help=f"sail_server 地址 (默认: {DEFAULT_SERVER_URL})",
        )
        if with_json:
            p.add_argument("--json", action="store_true", help="纯 JSON 输出（AI 解析用）")

    # ---- capture ----
    p = subparsers.add_parser("capture", help="快速捕获（kind=generic 进 INBOX）")
    add_common(p)
    p.add_argument("title", help="标题（捕获时唯一必填）")
    p.add_argument("--kind", default=None, help="事务种类（默认 generic）")
    p.add_argument("--domain", default=None, help="life/work/career")
    p.add_argument("--meta", default=None, help="kind_meta JSON")
    p.add_argument("--desc", default=None, help="详情")
    p.set_defaults(func=cmd_capture)

    # ---- kinds ----
    p = subparsers.add_parser("kinds", help="输出分类学说明（AI 分拣权威参考）")
    add_common(p)
    p.set_defaults(func=cmd_kinds)

    # ---- inbox ----
    p = subparsers.add_parser("inbox", help="待分拣列表")
    add_common(p)
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_inbox)

    # ---- suggest-triage ----
    p = subparsers.add_parser("suggest-triage", help="【AI】拉 INBOX + 分类学规范")
    add_common(p)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_suggest_triage)

    # ---- hint ----
    p = subparsers.add_parser("hint", help="【AI】写回分拣建议（ai_hint）")
    add_common(p)
    p.add_argument("id", type=int)
    p.add_argument("--kind", default=None)
    p.add_argument("--domain", default=None)
    p.add_argument("--meta", default=None, help="kind_meta JSON（按 kind 校验）")
    p.add_argument("--importance", type=int, default=None)
    p.add_argument("--energy", type=int, default=None, help="精力点数（轻5/常10/深25/重40）")
    p.add_argument("--est", type=int, default=None, help="预估时长（分钟）")
    p.add_argument("--money", type=float, default=None, help="预估花费")
    p.add_argument("--window", default=None, help="弹性窗口 start/end")
    p.add_argument("--fallback", default=None, help="Plan B 备用方案")
    p.add_argument("--reason", default=None, help="分拣理由")
    p.set_defaults(func=cmd_hint)

    # ---- suggest-split ----
    p = subparsers.add_parser("suggest-split", help="【AI】拆分建议草案（不落库）")
    add_common(p)
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_suggest_split)

    # ---- split ----
    p = subparsers.add_parser("split", help="确认后落库拆分")
    add_common(p)
    p.add_argument("id", type=int)
    p.add_argument("--file", required=True, help="split.json（含 children 数组）")
    p.set_defaults(func=cmd_split)

    # ---- confirm ----
    p = subparsers.add_parser("confirm", help="确认（一次性→PLANNED；长期→ACTIVE）")
    add_common(p)
    p.add_argument("id", type=int)
    p.add_argument("--accept-hint", action="store_true", help="先采纳 AI 建议")
    p.set_defaults(func=cmd_confirm)

    # ---- defer ----
    p = subparsers.add_parser("defer", help="显式弹性推迟（fixed_plan 拒绝）")
    add_common(p)
    p.add_argument("id", type=int)
    p.add_argument("--to", required=True, help="新窗口起点日期 YYYY-MM-DD")
    p.set_defaults(func=cmd_defer)

    # ---- template ----
    p = subparsers.add_parser("template", help="基础节奏模板")
    add_common(p)
    tsub = p.add_subparsers(dest="template_cmd")
    tp = tsub.add_parser("list", help="模板列表")
    add_common(tp)
    tp.set_defaults(func=cmd_template_list)
    tp = tsub.add_parser("show", help="模板详情")
    add_common(tp)
    tp.add_argument("id", type=int)
    tp.set_defaults(func=cmd_template_show)
    tp = tsub.add_parser("upsert", help="模板 upsert")
    add_common(tp)
    tp.add_argument("--file", required=True)
    tp.set_defaults(func=cmd_template_upsert)
    tp = tsub.add_parser("active", help="某日命中模板")
    add_common(tp)
    tp.add_argument("--date", default="today")
    tp.set_defaults(func=cmd_template_active)
    p.set_defaults(func=lambda a: (p.print_help(), sys.exit(1)))

    # ---- checkin ----
    p = subparsers.add_parser("checkin", help="戒律/习惯打卡")
    add_common(p)
    p.add_argument("target", help="affair_id 或 today")
    p.add_argument("--result", default=None, help="kept|violated|done|missed|exempt")
    p.add_argument("--note", default=None, help="备注（破戒原因等）")
    p.add_argument("--log-date", default=None)
    p.add_argument("--date", default=None, help="today 模式的日期")
    p.set_defaults(func=cmd_checkin)

    # ---- habit board ----
    p = subparsers.add_parser("habit", help="习惯")
    add_common(p)
    hsub = p.add_subparsers(dest="habit_cmd")
    hp = hsub.add_parser("board", help="习惯看板：streak/本周缺口/最佳连续")
    add_common(hp)
    hp.set_defaults(func=cmd_habit_board)
    p.set_defaults(func=lambda a: (p.print_help(), sys.exit(1)))

    # ---- venture ----
    p = subparsers.add_parser("venture", help="长期事业")
    add_common(p)
    vsub = p.add_subparsers(dest="venture_cmd")
    vp = vsub.add_parser("status", help="倒排周数/周预算/里程碑进度")
    add_common(vp)
    vp.add_argument("id", type=int, nargs="?", default=None)
    vp.set_defaults(func=cmd_venture_status)
    vp = vsub.add_parser("milestone", help="添加里程碑（--span 锚定 TimeSpan）")
    add_common(vp)
    vp.add_argument("id", type=int)
    vp.add_argument("--title", required=True)
    vp.add_argument("--span", default=None, help="如 Y2027Q2 / B0049")
    vp.add_argument("--ddl", default=None)
    vp.set_defaults(func=cmd_venture_milestone)
    p.set_defaults(func=lambda a: (p.print_help(), sys.exit(1)))

    # ---- plan ----
    p = subparsers.add_parser("plan", help="生成日计划并展示时间线")
    add_common(p)
    p.add_argument("date", help="today|tomorrow|YYYY-MM-DD")
    p.add_argument("--force", action="store_true", help="预算不足等软警告强制排入")
    p.set_defaults(func=cmd_plan)

    # ---- timeline ----
    p = subparsers.add_parser("timeline", help="查看时间线")
    add_common(p)
    p.add_argument("date", nargs="?", default="today")
    p.set_defaults(func=cmd_timeline)

    # ---- done / skip ----
    p = subparsers.add_parser("done", help="块反馈完成")
    add_common(p)
    p.add_argument("block_id", type=int)
    p.set_defaults(func=cmd_block_done)

    p = subparsers.add_parser("skip", help="块反馈跳过")
    add_common(p)
    p.add_argument("block_id", type=int)
    p.set_defaults(func=cmd_block_skip)

    # ---- rebalance ----
    p = subparsers.add_parser("rebalance", help="再平衡")
    add_common(p)
    p.add_argument("date", nargs="?", default="today")
    p.add_argument("--trigger", default="manual",
                   help="defer|new_affair|manual|checkin_missed")
    p.set_defaults(func=cmd_rebalance)

    # ---- conflicts ----
    p = subparsers.add_parser("conflicts", help="冲突/侵占报告")
    add_common(p)
    p.add_argument("date", nargs="?", default="today")
    p.set_defaults(func=cmd_conflicts)

    # ---- score ----
    p = subparsers.add_parser("score", help="节奏评分")
    add_common(p)
    p.add_argument("--week", action="store_true")
    p.add_argument("--span", default=None, help="周键 W2026-44")
    p.add_argument("--date", default="today")
    p.set_defaults(func=cmd_score)

    # ---- review ----
    p = subparsers.add_parser("review", help="复盘报告（--md 输出 Markdown）")
    add_common(p)
    p.add_argument("--week", action="store_true")
    p.add_argument("--span", default=None)
    p.add_argument("--date", default="today")
    p.add_argument("--md", action="store_true", help="Markdown 周报（供 notes 归档）")
    p.set_defaults(func=cmd_review)

    # ---- summary（Agent 写回复盘评语） ----
    p = subparsers.add_parser("summary", help="【AI】写回复盘评语 ai_summary")
    add_common(p)
    p.add_argument("--scope", default="week", choices=["day", "week"])
    p.add_argument("--key", default=None,
                   help="period_key，如 W2026-44 / 2026-10-26（缺省取当前周/今日）")
    p.add_argument("--file", default=None, help="评语 Markdown 文件")
    p.add_argument("--text", default=None, help="评语文字（与 --file 二选一，缺省读 stdin）")
    p.set_defaults(func=cmd_summary)

    # ---- profile ----
    p = subparsers.add_parser("profile", help="精力画像")
    add_common(p)
    psub = p.add_subparsers(dest="profile_cmd")
    pp = psub.add_parser("show", help="查看画像")
    add_common(pp)
    pp.set_defaults(func=cmd_profile_show)
    pp = psub.add_parser("set", help="更新画像")
    add_common(pp)
    pp.add_argument("--work-cap", type=float, default=None)
    pp.add_argument("--energy-budget", type=int, default=None)
    pp.add_argument("--career-weight", type=float, default=None)
    pp.add_argument("--life-weight", type=float, default=None)
    pp.add_argument("--work-weight", type=float, default=None)
    pp.add_argument("--buffer", type=float, default=None, help="min_buffer_ratio")
    pp.add_argument("--sleep-start", default=None)
    pp.add_argument("--sleep-end", default=None)
    pp.add_argument("--spare-windows", default=None, help="业余时间区 JSON")
    pp.set_defaults(func=cmd_profile_set)
    p.set_defaults(func=lambda a: (p.print_help(), sys.exit(1)))

    # ---- policy ----
    p = subparsers.add_parser("policy", help="守护策略")
    add_common(p)
    posub = p.add_subparsers(dest="policy_cmd")
    pop = posub.add_parser("list", help="策略列表")
    add_common(pop)
    pop.set_defaults(func=cmd_policy_list)
    pop = posub.add_parser("add", help="新增策略")
    add_common(pop)
    pop.add_argument("--name", required=True)
    pop.add_argument("--rule-type", required=True,
                     choices=["protect_window", "domain_cap", "kind_min_freq",
                              "max_consecutive_focus", "spare_time_guard"])
    pop.add_argument("--params", default=None)
    pop.add_argument("--scope", default="day", choices=["day", "week"])
    pop.set_defaults(func=cmd_policy_add)
    pop = posub.add_parser("toggle", help="启停策略")
    add_common(pop)
    pop.add_argument("id", type=int)
    pop.set_defaults(func=cmd_policy_toggle)
    p.set_defaults(func=lambda a: (p.print_help(), sys.exit(1)))

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except RhythmAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.ConnectionError as e:
        print(f"Error: 无法连接服务器 {args.server}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
