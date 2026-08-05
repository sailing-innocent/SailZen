# -*- coding: utf-8 -*-
# @file rhythm_smoke.py
# @brief Rhythm CLI 端到端冒烟脚本（sqlite 本地环境）
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
Rhythm CLI 冒烟脚本（M2 验收）

流程:
1. 以 DB_BACKEND=sqlite 启动临时 sail_server（独立 SERVER_DATA_DIR 与端口）
2. 通过 `python -m sailzen rhythm ...` 走完端到端:
   建模板 → capture → hint 改判 habit → confirm → plan → timeline →
   checkin → 块 done → venture(创建/里程碑/进度) → score → review --md
3. 每步断言关键输出，全部通过打印 SMOKE OK

用法:
  uv run python scripts/rhythm_smoke.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_PORT = int(os.environ.get("SMOKE_SERVER_PORT", "18974"))
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"
TODAY = date.today().isoformat()


def _run_cli(args: list[str], env: dict, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "sailzen", "rhythm", *args]
    proc = subprocess.run(
        cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=120,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"CLI 失败: sailzen rhythm {' '.join(args)}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    return proc


def _wait_server(timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{SERVER_URL}/api/v1/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(1.0)
    raise RuntimeError("服务器启动超时")


def main() -> int:
    tmp_dir = tempfile.mkdtemp(prefix="rhythm_smoke_")
    server_env = dict(os.environ)
    server_env["DB_BACKEND"] = "sqlite"
    server_env["SERVER_DATA_DIR"] = tmp_dir
    server_env["SERVER_PORT"] = str(SERVER_PORT)
    server_env["SERVER_HOST"] = "127.0.0.1"
    server_env["WEATHER_ENABLED"] = "false"
    server_env["REMINDER_ENABLED"] = "false"

    cli_env = dict(os.environ)
    cli_env["SAIL_SERVER_URL"] = SERVER_URL

    # 模板文件（工作日骨架）
    template_path = Path(tmp_dir) / "weekday_template.json"
    template_path.write_text(
        json.dumps({
            "name": "weekday",
            "description": "工作日骨架",
            "weekday_mask": [1, 1, 1, 1, 1, 1, 1],
            "priority": 0,
            "slots": [
                {"label": "通勤", "start": "08:20", "end": "09:00", "block_type": "commute"},
                {"label": "上午工作窗", "start": "09:00", "end": "12:00",
                 "block_type": "work_window",
                 "micro_cycle": {"work_min": 90, "rest_min": 15}},
                {"label": "午餐", "start": "12:00", "end": "13:00", "block_type": "meal"},
                {"label": "下午工作窗", "start": "13:00", "end": "18:00",
                 "block_type": "work_window"},
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    server_proc = subprocess.Popen(
        [sys.executable, "server.py", "--dev"],
        cwd=PROJECT_ROOT, env=server_env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        print(f"[smoke] 启动临时服务器 {SERVER_URL} (data={tmp_dir}) ...")
        _wait_server()

        # 1. kinds（分类学权威输出）
        proc = _run_cli(["kinds", "--json"], cli_env)
        kinds = json.loads(proc.stdout)
        assert len(kinds["kinds"]) == 9, "应为 9 类 kind"
        print("[smoke] 1. kinds OK (9 类)")

        # 2. 建模板
        _run_cli(["template", "upsert", "--file", str(template_path)], cli_env)
        proc = _run_cli(["template", "active", "--date", TODAY, "--json"], cli_env)
        assert json.loads(proc.stdout)["name"] == "weekday"
        print("[smoke] 2. template upsert/active OK")

        # 3. capture（generic → INBOX）
        proc = _run_cli(["capture", "每周运动3次", "--json"], cli_env)
        affair = json.loads(proc.stdout)
        assert affair["kind"] == "generic" and affair["state"] == "INBOX"
        habit_id = affair["id"]
        print(f"[smoke] 3. capture OK (#{habit_id})")

        # 4. suggest-triage 能看到它
        proc = _run_cli(["suggest-triage", "--json"], cli_env)
        triage = json.loads(proc.stdout)
        assert any(a["id"] == habit_id for a in triage["affairs"])
        print("[smoke] 4. suggest-triage OK")

        # 5. hint 改判 habit（CLI 同源校验 kind_meta）
        proc = _run_cli([
            "hint", str(habit_id), "--kind", "habit", "--domain", "life",
            "--meta", '{"freq_per_week": 3, "min_session_minutes": 30, "preferred_slots": ["19:00-21:00"]}',
            "--importance", "4", "--energy", "20", "--json",
        ], cli_env)
        assert json.loads(proc.stdout)["ai_hint"]["kind"] == "habit"
        print("[smoke] 5. hint OK")

        # 5b. 非法 kind_meta 被 CLI 拒绝
        bad = _run_cli(
            ["hint", str(habit_id), "--kind", "habit", "--meta", '{"freq_per_week": "abc"}'],
            cli_env, check=False,
        )
        assert bad.returncode == 2, "非法 kind_meta 应被 CLI 拒绝"
        print("[smoke] 5b. hint 非法 meta 拒绝 OK")

        # 6. confirm --accept-hint → ACTIVE
        proc = _run_cli(["confirm", str(habit_id), "--accept-hint", "--json"], cli_env)
        assert json.loads(proc.stdout)["affair"]["state"] == "ACTIVE"
        print("[smoke] 6. confirm(accept-hint) OK → ACTIVE")

        # 7. 戒律（hard 睡眠）
        proc = _run_cli([
            "capture", "23:30前入睡", "--kind", "precept", "--domain", "life",
            "--meta", '{"rule_text": "23:30前入睡", "severity": "hard", "check_time": "23:00"}',
            "--json",
        ], cli_env)
        precept_id = json.loads(proc.stdout)["id"]
        _run_cli(["confirm", str(precept_id)], cli_env)
        print(f"[smoke] 7. precept OK (#{precept_id})")

        # 8. venture + 里程碑
        target = (date.today() + timedelta(days=180)).isoformat()
        proc = _run_cli([
            "capture", "独立游戏上线", "--kind", "venture", "--domain", "career",
            "--meta", f'{{"target_date": "{target}", "weekly_budget_hours": 8, "total_est_hours": 300}}',
            "--json",
        ], cli_env)
        venture_id = json.loads(proc.stdout)["id"]
        _run_cli(["confirm", str(venture_id)], cli_env)
        _run_cli(["venture", "milestone", str(venture_id), "--title", "demo 完成"], cli_env)
        proc = _run_cli(["venture", "status", str(venture_id), "--json"], cli_env)
        progress = json.loads(proc.stdout)
        assert progress["weekly_budget_hours"] == 8.0
        assert len(progress["milestones"]) == 1
        print(f"[smoke] 8. venture OK (#{venture_id}, weeks_left={progress['weeks_left']})")

        # 9. plan today → 骨架 + buffer + habit + career
        proc = _run_cli(["plan", "today", "--json"], cli_env)
        plan = json.loads(proc.stdout)
        types = {b["block_type"] for b in plan["blocks"]}
        assert {"sleep", "work_window", "buffer", "habit", "career"} <= types, (
            f"计划应含骨架+buffer+habit+career，实际: {types}"
        )
        habit_block = next(b for b in plan["blocks"] if b["block_type"] == "habit")
        print(f"[smoke] 9. plan today OK (v{plan['plan_version']}, {len(plan['blocks'])} 块)")

        # 10. timeline
        proc = _run_cli(["timeline", "today", "--json"], cli_env)
        timeline = json.loads(proc.stdout)
        assert timeline["plan_version"] >= 1
        print("[smoke] 10. timeline OK")

        # 11. checkin（habit done + precept kept）
        _run_cli(["checkin", str(habit_id), "--result", "done"], cli_env)
        _run_cli(["checkin", str(precept_id), "--result", "kept"], cli_env)
        proc = _run_cli(["checkin", "today", "--json"], cli_env)
        today = json.loads(proc.stdout)
        assert today["habits"][0]["week_done_count"] == 1
        print("[smoke] 11. checkin OK")

        # 12. 块 done（habit 块联动打卡 source=auto）
        proc = _run_cli(["done", str(habit_block["id"]), "--json"], cli_env)
        assert json.loads(proc.stdout)["status"] == "DONE"
        print("[smoke] 12. block done OK")

        # 13. habit board
        proc = _run_cli(["habit", "board", "--json"], cli_env)
        board = json.loads(proc.stdout)
        assert board and board[0]["week_done"] >= 1
        print("[smoke] 13. habit board OK")

        # 14. score 日评 + 周评
        proc = _run_cli(["score", "--json"], cli_env)
        day_review = json.loads(proc.stdout)
        assert 0 <= day_review["rhythm_score"] <= 100
        proc = _run_cli(["score", "--week", "--json"], cli_env)
        week_review = json.loads(proc.stdout)
        assert week_review["precept_compliance_rate"] == 1.0
        print(f"[smoke] 14. score OK (日 {day_review['rhythm_score']} / 周 {week_review['rhythm_score']})")

        # 15. review --week --md（Markdown 周报）
        proc = _run_cli(["review", "--week", "--md"], cli_env)
        assert "# 节奏复盘" in proc.stdout
        print("[smoke] 15. review --md OK")

        # 16. profile set + policy
        _run_cli(["profile", "set", "--work-cap", "7", "--career-weight", "0.6",
                  "--buffer", "0.2"], cli_env)
        proc = _run_cli(["profile", "show", "--json"], cli_env)
        profile = json.loads(proc.stdout)
        assert profile["work_hours_cap"] == 7.0
        _run_cli(["policy", "add", "--name", "事业仅占业余时间区",
                  "--rule-type", "spare_time_guard"], cli_env)
        proc = _run_cli(["policy", "list", "--json"], cli_env)
        assert len(json.loads(proc.stdout)) >= 1
        print("[smoke] 16. profile/policy OK")

        # 17. conflicts 侵占报告
        proc = _run_cli(["conflicts", "today", "--json"], cli_env)
        assert "encroachments" in json.loads(proc.stdout)
        print("[smoke] 17. conflicts OK")

        # 18. summary 写回（Agent 复盘闭环）
        summary_path = Path(tmp_dir) / "weekly_summary.md"
        summary_path.write_text("本周节奏良好，下周继续保持。", encoding="utf-8")
        proc = _run_cli(["summary", "--scope", "week", "--file", str(summary_path),
                         "--json"], cli_env)
        assert "节奏良好" in json.loads(proc.stdout)["ai_summary"]
        print("[smoke] 18. summary 写回 OK")

        # 19. defer + replan（一次性工作任务）
        proc = _run_cli([
            "capture", "写季度总结", "--kind", "task_oneoff", "--domain", "work",
            "--json",
        ], cli_env)
        task_id = json.loads(proc.stdout)["id"]
        _run_cli(["confirm", str(task_id)], cli_env)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        proc = _run_cli(["defer", str(task_id), "--to", tomorrow, "--json"], cli_env)
        assert json.loads(proc.stdout)["state"] == "DEFERRED"
        print("[smoke] 19. defer OK")

        # 20. rebalance
        proc = _run_cli(["rebalance", "today", "--json"], cli_env)
        assert json.loads(proc.stdout)["plan_version"] >= 2
        print("[smoke] 20. rebalance OK")

        print("\n" + "=" * 60)
        print("SMOKE OK: Rhythm CLI 端到端全部通过 ✅ (20 步)")
        print("=" * 60)
        return 0
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()


if __name__ == "__main__":
    sys.exit(main())
