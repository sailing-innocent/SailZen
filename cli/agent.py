#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file agent.py
# @brief sailzen-agent CLI entrypoint
# @author sailing-innocent
# @date 2026-08-24
# @version 1.0
# ---------------------------------

"""
sailzen-agent — CLI toolchain for Shadow Agent

Usage:
    sailzen-agent start [--fg] [-c agent.yaml]
    sailzen-agent stop
    sailzen-agent status
    sailzen-agent restart
    sailzen-agent vault list
    sailzen-agent vault sync [name]
    sailzen-agent task list
    sailzen-agent task run <id>
    sailzen-agent task approve <id>
    sailzen-agent analyze [now|orphans|dailies|todos]
    sailzen-agent patch gen
    sailzen-agent patch list
"""

import argparse
import sys
import json
import subprocess
import os
from pathlib import Path

# Ensure sail_server is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sail.utils import read_env

read_env("dev")

PID_FILE = Path.home() / ".sailzen" / "agent.pid"
PID_FILE.parent.mkdir(parents=True, exist_ok=True)
API_BASE = "http://127.0.0.1:1975"


def _api_get(path: str) -> dict:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{API_BASE}{path}", timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"API error: {e}")
        return {}


def _api_post(path: str) -> dict:
    import urllib.request
    req = urllib.request.Request(f"{API_BASE}{path}", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"API error: {e}")
        return {}


def cmd_start(args):
    if PID_FILE.exists():
        pid = PID_FILE.read_text().strip()
        if _is_running(pid):
            print(f"Agent already running (PID {pid})")
            return
    daemon_script = PROJECT_ROOT / "sail_server" / "agent" / "daemon.py"
    cmd = [sys.executable, str(daemon_script), "-c", args.config]
    if args.fg:
        print("Starting agent in foreground...")
        os.execv(sys.executable, cmd)
    else:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        PID_FILE.write_text(str(proc.pid))
        print(f"Agent started (PID {proc.pid})")


def cmd_stop(args):
    if not PID_FILE.exists():
        print("Agent not running")
        return
    pid = PID_FILE.read_text().strip()
    try:
        os.kill(int(pid), 15)  # SIGTERM
        PID_FILE.unlink(missing_ok=True)
        print(f"Agent stopped (PID {pid})")
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        print("Agent not running")


def cmd_status(args):
    health = _api_get("/health")
    if health:
        print(f"Agent: {health.get('agent', 'unknown')}")
        print(f"Status: {health.get('status', 'unknown')}")
    else:
        print("Agent API not reachable")
    if PID_FILE.exists():
        pid = PID_FILE.read_text().strip()
        print(f"PID: {pid} ({'running' if _is_running(pid) else 'dead'})")


def cmd_restart(args):
    cmd_stop(args)
    import time
    time.sleep(1)
    cmd_start(args)


def cmd_vault_list(args):
    print("Configured vaults:")
    # Read from config
    from sail_server.agent.config import AgentConfig
    config = AgentConfig.from_yaml(args.config)
    for v in config.vaults:
        print(f"  - {v.name}: {v.url} -> {v.local_path}")


def cmd_vault_sync(args):
    print(f"Triggering vault sync: {args.name or 'all'}")
    result = _api_post(f"/trigger/vault_sync_{args.name}" if args.name else "/trigger/vault_sync")
    print(result)


def cmd_task_list(args):
    jobs = _api_get("/jobs")
    if not jobs:
        return
    print(f"{'ID':<6} {'Type':<20} {'Status':<16} {'Created':<20} Params")
    print("-" * 80)
    for j in jobs:
        ctime = j.get("ctime", "")[:19] if j.get("ctime") else ""
        params = json.dumps(j.get("params", {}))[:40]
        print(f"{j['id']:<6} {j['type']:<20} {j['status']:<16} {ctime:<20} {params}")


def cmd_task_run(args):
    print(f"Running job {args.id}...")
    # TODO: implement task execution via API
    print("Not yet implemented — use admin API or manual run")


def cmd_task_approve(args):
    result = _api_post(f"/jobs/{args.id}/approve")
    print(result)


def cmd_analyze(args):
    sub = args.subcommand or "now"
    print(f"Triggering analysis: {sub}")
    result = _api_post("/trigger/note_analyzer")
    print(result)


def cmd_patch_gen(args):
    print("Triggering patch generation...")
    result = _api_post("/trigger/patch_generator")
    print(result)


def cmd_patch_list(args):
    patches_dir = Path("patches")
    if not patches_dir.exists():
        print("No patches directory")
        return
    patches = sorted(patches_dir.glob("*.patch"), key=lambda p: p.stat().st_mtime, reverse=True)
    print(f"{'Patch File':<50} {'Size':>10} {'Modified':<20}")
    print("-" * 85)
    for p in patches:
        size = p.stat().st_size
        mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{p.name:<50} {size:>10} {mtime:<20}")


def _is_running(pid: str) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def main():
    from datetime import datetime
    parser = argparse.ArgumentParser(prog="sailzen-agent", description="Shadow Agent CLI")
    parser.add_argument("-c", "--config", default="agent.yaml", help="Agent config file")
    subparsers = parser.add_subparsers(dest="command")

    # start
    p_start = subparsers.add_parser("start", help="Start agent daemon")
    p_start.add_argument("--fg", action="store_true", help="Run in foreground")

    # stop
    subparsers.add_parser("stop", help="Stop agent daemon")

    # status
    subparsers.add_parser("status", help="Show agent status")

    # restart
    subparsers.add_parser("restart", help="Restart agent daemon")

    # vault
    p_vault = subparsers.add_parser("vault", help="Vault management")
    v_sub = p_vault.add_subparsers(dest="vault_cmd")
    v_sub.add_parser("list", help="List vaults")
    p_vsync = v_sub.add_parser("sync", help="Sync vault")
    p_vsync.add_argument("name", nargs="?", help="Vault name")

    # task
    p_task = subparsers.add_parser("task", help="Task management")
    t_sub = p_task.add_subparsers(dest="task_cmd")
    t_sub.add_parser("list", help="List pending tasks")
    p_trun = t_sub.add_parser("run", help="Run a task")
    p_trun.add_argument("id", type=int, help="Job ID")
    p_tapp = t_sub.add_parser("approve", help="Approve a pending-review task")
    p_tapp.add_argument("id", type=int, help="Job ID")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Run note analysis")
    p_analyze.add_argument("subcommand", nargs="?", choices=["now", "orphans", "dailies", "todos"])

    # patch
    p_patch = subparsers.add_parser("patch", help="Patch management")
    pt_sub = p_patch.add_subparsers(dest="patch_cmd")
    pt_sub.add_parser("gen", help="Generate patch now")
    pt_sub.add_parser("list", help="List generated patches")

    args = parser.parse_args()

    handlers = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "restart": cmd_restart,
        "vault": {
            "list": cmd_vault_list,
            "sync": cmd_vault_sync,
        },
        "task": {
            "list": cmd_task_list,
            "run": cmd_task_run,
            "approve": cmd_task_approve,
        },
        "analyze": cmd_analyze,
        "patch": {
            "gen": cmd_patch_gen,
            "list": cmd_patch_list,
        },
    }

    if not args.command:
        parser.print_help()
        return

    handler = handlers.get(args.command)
    if isinstance(handler, dict):
        sub = getattr(args, f"{args.command}_cmd", None)
        handler = handler.get(sub)

    if handler:
        handler(args)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()


if __name__ == "__main__":
    main()
