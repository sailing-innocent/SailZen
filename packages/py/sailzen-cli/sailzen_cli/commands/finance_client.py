# -*- coding: utf-8 -*-
# @file finance_client.py
# @brief FinanceClient CLI - 通过 HTTP API 分批加载/修改/上传 account 的 transaction 记录
# @author sailing-innocent
# @date 2026-05-06
# @version 2.0
# ---------------------------------

"""
FinanceClient CLI 工具

通过 sail_server 的 HTTP API 与远程服务器交互，支持：
1. 按 account_id 分批拉取 transaction 记录，导出为 CSV
2. 用户在 CSV 中修改后，逐条 PUT 回服务器
3. 支持查看 account 列表

命令示例:
  sailzen finance pull --account 1 --server http://host:port
  sailzen finance push transactions_1.csv --server http://host:port
  sailzen finance list-accounts --server http://host:port
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
    DEFAULT_PAGE_SIZE,
    API_TIMEOUT,
    REQUEST_DELAY,
    server_option,
)

DEFAULT_SERVER_URL = _resolve_default_server_url()
CSV_FIELDS = [
    "id",
    "from_acc_id",
    "to_acc_id",
    "value",
    "prev_value",
    "description",
    "tags",
    "state",
    "budget_id",
    "htime",
    "ctime",
    "mtime",
]

# 可编辑字段（push 时只发送这些字段给 PUT API）
EDITABLE_FIELDS = [
    "from_acc_id",
    "to_acc_id",
    "value",
    "description",
    "tags",
    "budget_id",
    "htime",
]


# ============================================================================
# FinanceClient
# ============================================================================


class FinanceClient:
    """通过 HTTP API 与 sail_server 交互的 Finance 客户端"""

    def __init__(self, server_url: str):
        """
        Args:
            server_url: sail_server 地址，如 http://192.168.1.100:8000
        """
        self.server_url = server_url.rstrip("/")
        self.base_api = f"{self.server_url}/api/v1/finance"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # Account API
    # ------------------------------------------------------------------

    def list_accounts(self) -> list[dict]:
        """获取所有账户列表"""
        url = f"{self.base_api}/account"
        resp = self.session.get(url, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data is None:
            return []
        return data if isinstance(data, list) else [data]

    def get_account(self, account_id: int) -> Optional[dict]:
        """获取单个账户信息"""
        url = f"{self.base_api}/account/{account_id}"
        resp = self.session.get(url, timeout=API_TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Transaction API
    # ------------------------------------------------------------------

    def fetch_all_transactions(
        self,
        account_id: Optional[int] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict]:
        """
        分页拉取所有 transaction 记录。

        由于 API 不支持直接按 account_id 过滤，先拉取全部数据，
        然后在本地按 from_acc_id / to_acc_id 过滤。

        Args:
            account_id: 可选，只返回与该账户相关的交易
            page_size: 每页数量

        Returns:
            transaction 列表
        """
        all_transactions: list[dict] = []
        page = 1

        while True:
            url = f"{self.base_api}/transaction/paginated/"
            params = {
                "page": page,
                "page_size": page_size,
                "sort_by": "htime",
                "sort_order": "desc",
            }
            resp = self.session.get(url, params=params, timeout=API_TIMEOUT)
            resp.raise_for_status()
            result = resp.json()

            transactions = result.get("data", [])
            if not transactions:
                break

            all_transactions.extend(transactions)

            # 检查是否还有下一页
            if not result.get("has_next", False):
                break

            page += 1
            time.sleep(REQUEST_DELAY)

        # 按 account_id 过滤
        if account_id is not None:
            all_transactions = [
                t
                for t in all_transactions
                if t.get("from_acc_id") == account_id
                or t.get("to_acc_id") == account_id
            ]

        return all_transactions

    def update_transaction(self, transaction_id: int, data: dict) -> dict:
        """
        更新单条 transaction。

        Args:
            transaction_id: 交易 ID
            data: 更新数据（只包含可编辑字段）

        Returns:
            更新后的 transaction 数据
        """
        url = f"{self.base_api}/transaction/{transaction_id}"
        resp = self.session.put(url, json=data, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def create_transaction(self, data: dict) -> dict:
        """
        创建新 transaction。

        Args:
            data: 创建数据（from_acc_id, to_acc_id, value 必填）

        Returns:
            创建后的 transaction 数据
        """
        url = f"{self.base_api}/transaction"
        resp = self.session.post(url, json=data, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # CSV 导出 / 导入
    # ------------------------------------------------------------------

    def export_to_csv(
        self,
        transactions: list[dict],
        csv_path: str,
    ) -> int:
        """
        将 transaction 列表导出为 CSV 文件。

        Args:
            transactions: transaction 字典列表
            csv_path: 输出 CSV 文件路径

        Returns:
            导出的记录数
        """
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for t in transactions:
                # 将 datetime 字符串原样保留，htime 转为可读格式方便编辑
                row = {k: t.get(k, "") for k in CSV_FIELDS}
                # htime 如果是时间戳，转为可读的 ISO 格式字符串
                if row.get("htime") and isinstance(row["htime"], (int, float)):
                    try:
                        row["htime"] = datetime.fromtimestamp(row["htime"]).isoformat()
                    except (ValueError, OSError):
                        pass
                writer.writerow(row)

        return len(transactions)

    def import_from_csv(self, csv_path: str) -> list[dict]:
        """
        从 CSV 文件读取 transaction 数据。

        Args:
            csv_path: CSV 文件路径

        Returns:
            transaction 字典列表（包含所有字段）
        """
        transactions: list[dict] = []
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 清理空字符串
                cleaned = {}
                for k, v in row.items():
                    if v is None or v.strip() == "":
                        cleaned[k] = None
                    else:
                        cleaned[k] = v.strip()

                # 类型转换
                if cleaned.get("id"):
                    cleaned["id"] = int(cleaned["id"])
                if cleaned.get("from_acc_id") is not None:
                    cleaned["from_acc_id"] = int(cleaned["from_acc_id"])
                if cleaned.get("to_acc_id") is not None:
                    cleaned["to_acc_id"] = int(cleaned["to_acc_id"])
                if cleaned.get("state") is not None:
                    cleaned["state"] = int(cleaned["state"])
                if cleaned.get("budget_id") is not None:
                    cleaned["budget_id"] = int(cleaned["budget_id"])
                # htime: 尝试解析 ISO 格式 → 时间戳
                if cleaned.get("htime"):
                    try:
                        dt = datetime.fromisoformat(cleaned["htime"])
                        cleaned["htime"] = dt.timestamp()
                    except (ValueError, TypeError):
                        try:
                            cleaned["htime"] = float(cleaned["htime"])
                        except (ValueError, TypeError):
                            cleaned["htime"] = None

                transactions.append(cleaned)

        return transactions

    def push_from_csv(
        self,
        csv_path: str,
        dry_run: bool = False,
    ) -> dict:
        """
        从 CSV 读取并逐条 PUT 更新到服务器。

        Args:
            csv_path: CSV 文件路径
            dry_run: 如果为 True，只打印将要执行的操作，不实际发送请求

        Returns:
            {"success": int, "failed": int, "errors": list}
        """
        transactions = self.import_from_csv(csv_path)
        success = 0
        failed = 0
        errors: list[dict] = []

        for t in transactions:
            tid = t.get("id")
            if not tid:
                errors.append({"id": None, "error": "Missing transaction id"})
                failed += 1
                continue

            # 只提取可编辑字段
            update_data = {}
            for field in EDITABLE_FIELDS:
                if field in t and t[field] is not None:
                    update_data[field] = t[field]

            if dry_run:
                print(f"[DRY RUN] Would update transaction {tid}: {json.dumps(update_data, ensure_ascii=False)}")
                success += 1
                continue

            try:
                result = self.update_transaction(tid, update_data)
                print(f"[OK] Updated transaction {tid}: {result.get('description', '')[:50]}")
                success += 1
                time.sleep(REQUEST_DELAY)
            except requests.HTTPError as e:
                msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                print(f"[FAIL] Transaction {tid}: {msg}", file=sys.stderr)
                errors.append({"id": tid, "error": msg})
                failed += 1
            except Exception as e:
                print(f"[FAIL] Transaction {tid}: {e}", file=sys.stderr)
                errors.append({"id": tid, "error": str(e)})
                failed += 1

        return {"success": success, "failed": failed, "errors": errors}

    def create_from_csv(
        self,
        csv_path: str,
        dry_run: bool = False,
    ) -> dict:
        """
        从 CSV 读取并创建新 transaction（id 为空或缺失的行会被视为新建）。

        Args:
            csv_path: CSV 文件路径
            dry_run: 如果为 True，只打印将要执行的操作，不实际发送请求

        Returns:
            {"success": int, "failed": int, "errors": list}
        """
        transactions = self.import_from_csv(csv_path)
        success = 0
        failed = 0
        errors: list[dict] = []

        # 新建交易所需字段（与 TransactionCreateRequest 对应）
        CREATE_FIELDS = [
            "from_acc_id",
            "to_acc_id",
            "value",
            "description",
            "tags",
            "budget_id",
            "htime",
        ]

        for t in transactions:
            tid = t.get("id")
            if tid:
                # 有 id 的行跳过，仅处理无 id 的新记录
                continue

            # 必填校验
            if t.get("from_acc_id") is None or t.get("to_acc_id") is None or not t.get("value"):
                errors.append({"row": t.get("description", ""), "error": "Missing required fields: from_acc_id, to_acc_id, value"})
                failed += 1
                continue

            create_data = {}
            for field in CREATE_FIELDS:
                if field in t and t[field] is not None:
                    create_data[field] = t[field]

            if dry_run:
                print(f"[DRY RUN] Would create transaction: {json.dumps(create_data, ensure_ascii=False)}")
                success += 1
                continue

            try:
                result = self.create_transaction(create_data)
                print(f"[OK] Created transaction: {result.get('description', '')[:50]} (ID: {result.get('id')})")
                success += 1
                time.sleep(REQUEST_DELAY)
            except requests.HTTPError as e:
                msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                print(f"[FAIL] Create transaction: {msg}", file=sys.stderr)
                errors.append({"row": t.get("description", ""), "error": msg})
                failed += 1
            except Exception as e:
                print(f"[FAIL] Create transaction: {e}", file=sys.stderr)
                errors.append({"row": t.get("description", ""), "error": str(e)})
                failed += 1

        return {"success": success, "failed": failed, "errors": errors}


# ============================================================================
# Click Commands
# ============================================================================


@click.group()
def finance():
    """财务交易管理（拉取/修改/上传 transaction）。"""


@finance.command("list-accounts")
@server_option
def cmd_list_accounts(server):
    """列出所有账户"""
    client = FinanceClient(server)
    accounts = client.list_accounts()
    if not accounts:
        click.echo("No accounts found.")
        return

    click.echo(f"{'ID':>6}  {'Name':<30}  {'Balance':>12}  {'State':>6}")
    click.echo("-" * 65)
    for acc in accounts:
        click.echo(
            f"{acc.get('id', ''):>6}  "
            f"{acc.get('name', ''):<30}  "
            f"{acc.get('balance', '0'):>12}  "
            f"{acc.get('state', ''):>6}"
        )


@finance.command("pull")
@server_option
@click.option("--account", "-a", type=int, default=None, help="按 account_id 过滤（可选，不指定则拉取全部）")
@click.option("--output", "-o", default=None, help="输出 CSV 文件路径（默认: transactions_{account_id}.csv）")
@click.option("--page-size", type=int, default=DEFAULT_PAGE_SIZE, show_default=True, help="每页拉取数量（最大: 100）")
def cmd_pull(server, account, output, page_size):
    """拉取 transaction 并导出为 CSV"""
    client = FinanceClient(server)

    if account is not None:
        acc = client.get_account(account)
        if acc is None:
            raise click.ClickException(f"Account {account} not found.")
        click.echo(f"Account: {acc['name']} (ID: {acc['id']})")

    click.echo(f"Fetching transactions from {server} ...")
    transactions = client.fetch_all_transactions(
        account_id=account,
        page_size=page_size,
    )

    if not transactions:
        click.echo("No transactions found.")
        return

    if output:
        csv_path = output
    else:
        suffix = f"_{account}" if account is not None else "_all"
        csv_path = f"transactions{suffix}.csv"

    count = client.export_to_csv(transactions, csv_path)
    click.echo(f"Exported {count} transactions to {csv_path}")


@finance.command("push")
@server_option
@click.argument("csv", type=click.Path(exists=True))
@click.option("--dry-run", "-n", is_flag=True, help="仅预览，不实际发送请求")
def cmd_push(server, csv, dry_run):
    """从 CSV 读取并推送更新到服务器"""
    client = FinanceClient(server)
    click.echo(f"Pushing updates from {csv} to {server} ...")

    if dry_run:
        click.echo("[DRY RUN MODE] No actual requests will be sent.\n")

    result = client.push_from_csv(csv, dry_run=dry_run)

    click.echo(f"\nDone. Success: {result['success']}, Failed: {result['failed']}")
    if result["errors"]:
        click.echo("\nErrors:")
        for err in result["errors"]:
            click.echo(f"  - ID {err['id']}: {err['error']}")


@finance.command("create-from-csv")
@server_option
@click.argument("csv", type=click.Path(exists=True))
@click.option("--dry-run", "-n", is_flag=True, help="仅预览，不实际发送请求")
def cmd_create_from_csv(server, csv, dry_run):
    """从 CSV 创建新 transaction（id 为空或缺失的行）"""
    client = FinanceClient(server)
    click.echo(f"Creating new transactions from {csv} to {server} ...")

    if dry_run:
        click.echo("[DRY RUN MODE] No actual requests will be sent.\n")

    result = client.create_from_csv(csv, dry_run=dry_run)

    click.echo(f"\nDone. Created: {result['success']}, Failed: {result['failed']}")
    if result["errors"]:
        click.echo("\nErrors:")
        for err in result["errors"]:
            click.echo(f"  - Row '{err['row']}': {err['error']}")


if __name__ == "__main__":
    finance()

