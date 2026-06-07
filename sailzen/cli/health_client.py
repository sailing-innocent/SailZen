# -*- coding: utf-8 -*-
# @file health_client.py
# @brief HealthClient CLI - 通过 HTTP API 导出健康数据（体重/运动/减重计划）
# @author sailing-innocent
# @date 2026-06-07
# @version 1.0
# ---------------------------------

"""
HealthClient CLI 工具

通过 sail_server 的 HTTP API 与远程服务器交互，支持：
1. 导出体重记录为 CSV
2. 导出运动记录为 CSV
3. 获取体重趋势分析和减重计划进度

API 端点：
- GET  /api/v1/health/weight              → 体重列表
- GET  /api/v1/health/weight/avg          → 平均体重
- GET  /api/v1/health/weight/analysis     → 体重趋势分析
- GET  /api/v1/health/weight/prediction   → 体重预测
- GET  /api/v1/health/weight/plan         → 活跃减重计划
- GET  /api/v1/health/weight/plan/progress → 减重计划进度
- GET  /api/v1/health/exercise            → 运动记录列表
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

import requests


# ============================================================================
# Environment / Server URL Resolution (与 finance_client 共享逻辑)
# ============================================================================

def _load_env_file(env_path: str) -> dict:
    """手动解析 .env 文件"""
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
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                env[key] = value
    return env


def _resolve_default_server_url() -> str:
    """解析默认服务器地址"""
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
API_TIMEOUT = 30
REQUEST_DELAY = 0.1


# ============================================================================
# HealthClient
# ============================================================================

class HealthClient:
    """通过 HTTP API 与 sail_server 交互的 Health 客户端"""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self.base_api = f"{self.server_url}/api/v1/health"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # Weight API
    # ------------------------------------------------------------------

    def fetch_all_weights(
        self,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: int = 10000,
    ) -> list[dict]:
        """拉取所有体重记录"""
        url = f"{self.base_api}/weight"
        params = {"skip": 0, "limit": limit}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        resp = self.session.get(url, params=params, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def get_weight_avg(self, start: Optional[int] = None, end: Optional[int] = None) -> dict:
        """获取平均体重"""
        url = f"{self.base_api}/weight/avg"
        params = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        resp = self.session.get(url, params=params, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def analyze_weight_trend(
        self,
        start: Optional[int] = None,
        end: Optional[int] = None,
        model_type: str = "linear",
    ) -> dict:
        """体重趋势分析"""
        url = f"{self.base_api}/weight/analysis"
        params = {"model_type": model_type}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        resp = self.session.get(url, params=params, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def get_weight_plan(self) -> Optional[dict]:
        """获取活跃减重计划"""
        url = f"{self.base_api}/weight/plan"
        resp = self.session.get(url, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data if data else None

    def get_weight_plan_progress(self, plan_id: Optional[int] = None) -> Optional[dict]:
        """获取减重计划进度"""
        url = f"{self.base_api}/weight/plan/progress"
        params = {}
        if plan_id is not None:
            params["plan_id"] = plan_id
        resp = self.session.get(url, params=params, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data if data else None

    def get_weights_with_plan_status(
        self,
        start: Optional[int] = None,
        end: Optional[int] = None,
        plan_id: Optional[int] = None,
    ) -> list[dict]:
        """获取带计划状态的体重记录"""
        url = f"{self.base_api}/weight/plan/weights-with-status"
        params = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        if plan_id is not None:
            params["plan_id"] = plan_id
        resp = self.session.get(url, params=params, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # Exercise API
    # ------------------------------------------------------------------

    def fetch_all_exercises(
        self,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: int = 10000,
    ) -> list[dict]:
        """拉取所有运动记录"""
        url = f"{self.base_api}/exercise"
        params = {"skip": 0, "limit": limit}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        resp = self.session.get(url, params=params, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # CSV Export
    # ------------------------------------------------------------------

    def export_weights_to_csv(self, weights: list[dict], csv_path: str) -> int:
        """导出体重记录为 CSV"""
        fields = ["id", "value", "ctime", "note"]
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for w in weights:
                row = {k: w.get(k, "") for k in fields}
                if row.get("ctime") and isinstance(row["ctime"], (int, float)):
                    row["ctime"] = datetime.fromtimestamp(row["ctime"]).isoformat()
                writer.writerow(row)
        return len(weights)

    def export_exercises_to_csv(self, exercises: list[dict], csv_path: str) -> int:
        """导出运动记录为 CSV"""
        fields = ["id", "name", "value", "unit", "ctime", "note"]
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for e in exercises:
                row = {k: e.get(k, "") for k in fields}
                if row.get("ctime") and isinstance(row["ctime"], (int, float)):
                    row["ctime"] = datetime.fromtimestamp(row["ctime"]).isoformat()
                writer.writerow(row)
        return len(exercises)


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_pull_weight(args):
    """导出体重记录为 CSV"""
    client = HealthClient(args.server)
    print(f"Fetching weight records from {args.server} ...")

    start_ts = int(datetime.strptime(args.start, "%Y-%m-%d").timestamp()) if args.start else 0
    end_ts = int(datetime.strptime(args.end, "%Y-%m-%d").timestamp()) if args.end else int(datetime(2099, 12, 31).timestamp())

    weights = client.fetch_all_weights(start=start_ts, end=end_ts)
    if not weights:
        print("No weight records found.")
        return

    csv_path = args.output or "health_weights.csv"
    count = client.export_weights_to_csv(weights, csv_path)
    print(f"Exported {count} weight records to {csv_path}")


def cmd_pull_exercise(args):
    """导出运动记录为 CSV"""
    client = HealthClient(args.server)
    print(f"Fetching exercise records from {args.server} ...")

    start_ts = int(datetime.strptime(args.start, "%Y-%m-%d").timestamp()) if args.start else 0
    end_ts = int(datetime.strptime(args.end, "%Y-%m-%d").timestamp()) if args.end else int(datetime(2099, 12, 31).timestamp())

    exercises = client.fetch_all_exercises(start=start_ts, end=end_ts)
    if not exercises:
        print("No exercise records found.")
        return

    csv_path = args.output or "health_exercises.csv"
    count = client.export_exercises_to_csv(exercises, csv_path)
    print(f"Exported {count} exercise records to {csv_path}")


def cmd_weight_analysis(args):
    """获取体重趋势分析和减重计划进度"""
    client = HealthClient(args.server)

    start_ts = int(datetime.strptime(args.start, "%Y-%m-%d").timestamp()) if args.start else 0
    end_ts = int(datetime.strptime(args.end, "%Y-%m-%d").timestamp()) if args.end else int(datetime(2099, 12, 31).timestamp())

    print("=" * 60)
    print("📊 体重趋势分析")
    print("=" * 60)

    # 趋势分析
    trend = client.analyze_weight_trend(start=start_ts, end=end_ts, model_type=args.model)
    print(f"\n趋势模型: {trend.get('model_type', 'linear')}")
    print(f"当前趋势: {trend.get('current_trend', 'unknown')}")
    print(f"斜率: {trend.get('slope', 0):.4f} kg/天")
    print(f"R² 拟合度: {trend.get('r_squared', 0):.4f}")
    if "prediction_30d" in trend:
        print(f"30天预测: {trend['prediction_30d']:.2f} kg")
    if "prediction_90d" in trend:
        print(f"90天预测: {trend['prediction_90d']:.2f} kg")

    # 平均值
    avg = client.get_weight_avg(start=start_ts, end=end_ts)
    if avg and avg.get("result"):
        print(f"\n平均体重: {avg['result']:.2f} kg")

    # 减重计划
    print("\n" + "=" * 60)
    print("📋 减重计划")
    print("=" * 60)

    plan = client.get_weight_plan()
    if plan:
        print(f"\n计划名称: {plan.get('name', 'N/A')}")
        print(f"目标体重: {plan.get('target_weight', 'N/A')} kg")
        print(f"起始体重: {plan.get('start_weight', 'N/A')} kg")
        print(f"计划周期: {plan.get('duration_days', 'N/A')} 天")

        progress = client.get_weight_plan_progress(plan_id=plan.get("id"))
        if progress:
            print(f"\n控制率: {progress.get('control_rate', 'N/A')}")
            if "current_weight" in progress:
                print(f"当前体重: {progress['current_weight']:.2f} kg")
            if "expected_weight" in progress:
                print(f"预期体重: {progress['expected_weight']:.2f} kg")
            if "remaining_days" in progress:
                print(f"剩余天数: {progress['remaining_days']} 天")
    else:
        print("\n无活跃减重计划")


def cmd_weight_plan_status(args):
    """导出带计划状态的体重记录"""
    client = HealthClient(args.server)
    print(f"Fetching weight records with plan status from {args.server} ...")

    start_ts = int(datetime.strptime(args.start, "%Y-%m-%d").timestamp()) if args.start else 0
    end_ts = int(datetime.strptime(args.end, "%Y-%m-%d").timestamp()) if args.end else int(datetime(2099, 12, 31).timestamp())

    records = client.get_weights_with_plan_status(start=start_ts, end=end_ts)
    if not records:
        print("No records found.")
        return

    fields = ["id", "value", "ctime", "expected_value", "status", "diff", "note"]
    csv_path = args.output or "health_weight_plan_status.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            row = {k: r.get(k, "") for k in fields}
            if row.get("ctime") and isinstance(row["ctime"], (int, float)):
                row["ctime"] = datetime.fromtimestamp(row["ctime"]).isoformat()
            writer.writerow(row)

    print(f"Exported {len(records)} records to {csv_path}")


# ============================================================================
# Main Entry
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="HealthClient - SailZen 健康数据 CLI 工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    def add_server_arg(p):
        p.add_argument(
            "--server",
            default=os.environ.get("SAIL_SERVER_URL", DEFAULT_SERVER_URL),
            help=f"sail_server 地址 (默认: {DEFAULT_SERVER_URL})",
        )

    def add_date_args(p):
        p.add_argument("--start", help="起始日期 (YYYY-MM-DD)")
        p.add_argument("--end", help="截止日期 (YYYY-MM-DD)")

    # ---- pull-weight ----
    p_w = subparsers.add_parser("pull-weight", aliases=["pw"], help="导出体重记录为 CSV")
    add_server_arg(p_w)
    add_date_args(p_w)
    p_w.add_argument("--output", "-o", default=None, help="输出 CSV 文件路径")
    p_w.set_defaults(func=cmd_pull_weight)

    # ---- pull-exercise ----
    p_e = subparsers.add_parser("pull-exercise", aliases=["pe"], help="导出运动记录为 CSV")
    add_server_arg(p_e)
    add_date_args(p_e)
    p_e.add_argument("--output", "-o", default=None, help="输出 CSV 文件路径")
    p_e.set_defaults(func=cmd_pull_exercise)

    # ---- weight-analysis ----
    p_a = subparsers.add_parser("weight-analysis", aliases=["wa"], help="体重趋势分析与减重计划")
    add_server_arg(p_a)
    add_date_args(p_a)
    p_a.add_argument("--model", default="linear", choices=["linear", "polynomial"], help="趋势模型")
    p_a.set_defaults(func=cmd_weight_analysis)

    # ---- weight-plan-status ----
    p_ps = subparsers.add_parser("weight-plan-status", aliases=["wps"], help="导出带计划状态的体重记录")
    add_server_arg(p_ps)
    add_date_args(p_ps)
    p_ps.add_argument("--output", "-o", default=None, help="输出 CSV 文件路径")
    p_ps.set_defaults(func=cmd_weight_plan_status)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
