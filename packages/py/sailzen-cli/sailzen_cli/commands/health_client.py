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

import click
import requests

from sailzen_cli.common import (
    _resolve_default_server_url,
    API_TIMEOUT,
    REQUEST_DELAY,
    server_option,
)


# ============================================================================
# Constants
# ============================================================================

DEFAULT_SERVER_URL = _resolve_default_server_url()


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
# Click Commands
# ============================================================================


@click.group()
def health():
    """健康数据管理（体重/运动/减重计划导出分析）。"""


def _resolve_range(start: Optional[str], end: Optional[str]) -> tuple[int, int]:
    start_ts = int(datetime.strptime(start, "%Y-%m-%d").timestamp()) if start else 0
    end_ts = int(datetime.strptime(end, "%Y-%m-%d").timestamp()) if end else int(datetime(2099, 12, 31).timestamp())
    return start_ts, end_ts


@health.command("pull-weight")
@server_option
@click.option("--start", default=None, help="起始日期 (YYYY-MM-DD)")
@click.option("--end", default=None, help="截止日期 (YYYY-MM-DD)")
@click.option("--output", "-o", default=None, help="输出 CSV 文件路径")
def cmd_pull_weight(server, start, end, output):
    """导出体重记录为 CSV"""
    client = HealthClient(server)
    click.echo(f"Fetching weight records from {server} ...")

    start_ts, end_ts = _resolve_range(start, end)

    weights = client.fetch_all_weights(start=start_ts, end=end_ts)
    if not weights:
        click.echo("No weight records found.")
        return

    csv_path = output or "health_weights.csv"
    count = client.export_weights_to_csv(weights, csv_path)
    click.echo(f"Exported {count} weight records to {csv_path}")


@health.command("pull-exercise")
@server_option
@click.option("--start", default=None, help="起始日期 (YYYY-MM-DD)")
@click.option("--end", default=None, help="截止日期 (YYYY-MM-DD)")
@click.option("--output", "-o", default=None, help="输出 CSV 文件路径")
def cmd_pull_exercise(server, start, end, output):
    """导出运动记录为 CSV"""
    client = HealthClient(server)
    click.echo(f"Fetching exercise records from {server} ...")

    start_ts, end_ts = _resolve_range(start, end)

    exercises = client.fetch_all_exercises(start=start_ts, end=end_ts)
    if not exercises:
        click.echo("No exercise records found.")
        return

    csv_path = output or "health_exercises.csv"
    count = client.export_exercises_to_csv(exercises, csv_path)
    click.echo(f"Exported {count} exercise records to {csv_path}")


@health.command("weight-analysis")
@server_option
@click.option("--start", default=None, help="起始日期 (YYYY-MM-DD)")
@click.option("--end", default=None, help="截止日期 (YYYY-MM-DD)")
@click.option("--model", default="linear", show_default=True, type=click.Choice(["linear", "polynomial"]), help="趋势模型")
def cmd_weight_analysis(server, start, end, model):
    """获取体重趋势分析和减重计划进度"""
    client = HealthClient(server)

    start_ts, end_ts = _resolve_range(start, end)

    click.echo("=" * 60)
    click.echo("📊 体重趋势分析")
    click.echo("=" * 60)

    trend = client.analyze_weight_trend(start=start_ts, end=end_ts, model_type=model)
    click.echo(f"\n趋势模型: {trend.get('model_type', 'linear')}")
    click.echo(f"当前趋势: {trend.get('current_trend', 'unknown')}")
    click.echo(f"斜率: {trend.get('slope', 0):.4f} kg/天")
    click.echo(f"R² 拟合度: {trend.get('r_squared', 0):.4f}")
    if "prediction_30d" in trend:
        click.echo(f"30天预测: {trend['prediction_30d']:.2f} kg")
    if "prediction_90d" in trend:
        click.echo(f"90天预测: {trend['prediction_90d']:.2f} kg")

    avg = client.get_weight_avg(start=start_ts, end=end_ts)
    if avg and avg.get("result"):
        click.echo(f"\n平均体重: {avg['result']:.2f} kg")

    click.echo("\n" + "=" * 60)
    click.echo("📋 减重计划")
    click.echo("=" * 60)

    plan = client.get_weight_plan()
    if plan:
        click.echo(f"\n计划名称: {plan.get('name', 'N/A')}")
        click.echo(f"目标体重: {plan.get('target_weight', 'N/A')} kg")
        click.echo(f"起始体重: {plan.get('start_weight', 'N/A')} kg")
        click.echo(f"计划周期: {plan.get('duration_days', 'N/A')} 天")

        progress = client.get_weight_plan_progress(plan_id=plan.get("id"))
        if progress:
            click.echo(f"\n控制率: {progress.get('control_rate', 'N/A')}")
            if "current_weight" in progress:
                click.echo(f"当前体重: {progress['current_weight']:.2f} kg")
            if "expected_weight" in progress:
                click.echo(f"预期体重: {progress['expected_weight']:.2f} kg")
            if "remaining_days" in progress:
                click.echo(f"剩余天数: {progress['remaining_days']} 天")
    else:
        click.echo("\n无活跃减重计划")


@health.command("weight-plan-status")
@server_option
@click.option("--start", default=None, help="起始日期 (YYYY-MM-DD)")
@click.option("--end", default=None, help="截止日期 (YYYY-MM-DD)")
@click.option("--output", "-o", default=None, help="输出 CSV 文件路径")
def cmd_weight_plan_status(server, start, end, output):
    """导出带计划状态的体重记录"""
    client = HealthClient(server)
    click.echo(f"Fetching weight records with plan status from {server} ...")

    start_ts, end_ts = _resolve_range(start, end)

    records = client.get_weights_with_plan_status(start=start_ts, end=end_ts)
    if not records:
        click.echo("No records found.")
        return

    fields = ["id", "value", "ctime", "expected_value", "status", "diff", "note"]
    csv_path = output or "health_weight_plan_status.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            row = {k: r.get(k, "") for k in fields}
            if row.get("ctime") and isinstance(row["ctime"], (int, float)):
                row["ctime"] = datetime.fromtimestamp(row["ctime"]).isoformat()
            writer.writerow(row)

    click.echo(f"Exported {len(records)} records to {csv_path}")


if __name__ == "__main__":
    health()
