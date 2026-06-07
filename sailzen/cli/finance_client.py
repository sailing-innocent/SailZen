# -*- coding: utf-8 -*-
# @file finance_client.py
# @brief FinanceClient CLI - 通过 HTTP API 分批加载/修改/上传 account 的 transaction 记录
# @author sailing-innocent
# @date 2026-05-06
# @version 1.0
# ---------------------------------

"""
FinanceClient CLI 工具

通过 sail_server 的 HTTP API 与远程服务器交互，支持：
1. 按 account_id 分批拉取 transaction 记录，导出为 CSV
2. 用户在 CSV 中修改后，逐条 PUT 回服务器
3. 支持查看 account 列表

API 端点（基于 sail_server 路由结构）：
- GET  /api/v1/finance/account              → 获取所有账户
- GET  /api/v1/finance/transaction/paginated/ → 分页获取交易（page, page_size, sort_by, sort_order）
- PUT  /api/v1/finance/transaction/{id}     → 更新单条交易

工作流程：
  sailzen finance pull --account 1 --server http://host:port
    → 拉取 account 1 的所有 transaction，导出为 transactions_1.csv
  （用户编辑 CSV）
  sailzen finance push --csv transactions_1.csv --server http://host:port
    → 读取 CSV，逐条 PUT 更新到服务器
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
# Environment / Server URL Resolution
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
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                env[key] = value
    return env


def _resolve_default_server_url() -> str:
    """
    解析默认服务器地址。
    优先级：
      1. SAIL_SERVER_URL 环境变量
      2. .env.prod / .env.dev 中的 SERVER_HOST + SERVER_PORT
      3. http://localhost:8000
    """
    # 1. 环境变量
    env_url = os.environ.get("SAIL_SERVER_URL")
    if env_url:
        return env_url

    # 2. 尝试读取 .env 文件
    cwd = os.getcwd()
    for env_name in (".env.prod", ".env.dev", ".env"):
        env_path = os.path.join(cwd, env_name)
        if os.path.isfile(env_path):
            env = _load_env_file(env_path)
            host = env.get("SERVER_HOST", "localhost")
            port = env.get("SERVER_PORT", "8000")
            return f"http://{host}:{port}"

    # 3. 回退默认值
    return "http://localhost:8000"


DEFAULT_SERVER_URL = _resolve_default_server_url()


# ============================================================================
# Constants
# ============================================================================

DEFAULT_PAGE_SIZE = 100  # 每页拉取数量（API 最大 100）
API_TIMEOUT = 30  # HTTP 请求超时（秒）
REQUEST_DELAY = 0.1  # 请求间隔（秒），避免打爆服务器

# CSV 列定义（与 TransactionResponse 字段对应）
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
# CLI Commands
# ============================================================================


def cmd_list_accounts(args):
    """列出所有账户"""
    client = FinanceClient(args.server)
    accounts = client.list_accounts()
    if not accounts:
        print("No accounts found.")
        return

    print(f"{'ID':>6}  {'Name':<30}  {'Balance':>12}  {'State':>6}")
    print("-" * 65)
    for acc in accounts:
        print(
            f"{acc.get('id', ''):>6}  "
            f"{acc.get('name', ''):<30}  "
            f"{acc.get('balance', '0'):>12}  "
            f"{acc.get('state', ''):>6}"
        )


def cmd_pull(args):
    """拉取 transaction 并导出为 CSV"""
    client = FinanceClient(args.server)

    account_id = args.account
    if account_id is not None:
        account = client.get_account(account_id)
        if account is None:
            print(f"Error: Account {account_id} not found.", file=sys.stderr)
            sys.exit(1)
        print(f"Account: {account['name']} (ID: {account['id']})")

    print(f"Fetching transactions from {args.server} ...")
    transactions = client.fetch_all_transactions(
        account_id=account_id,
        page_size=args.page_size,
    )

    if not transactions:
        print("No transactions found.")
        return

    # 生成默认 CSV 文件名
    if args.output:
        csv_path = args.output
    else:
        suffix = f"_{account_id}" if account_id is not None else "_all"
        csv_path = f"transactions{suffix}.csv"

    count = client.export_to_csv(transactions, csv_path)
    print(f"Exported {count} transactions to {csv_path}")


def cmd_push(args):
    """从 CSV 读取并推送更新到服务器"""
    csv_path = args.csv
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    client = FinanceClient(args.server)
    print(f"Pushing updates from {csv_path} to {args.server} ...")

    if args.dry_run:
        print("[DRY RUN MODE] No actual requests will be sent.\n")

    result = client.push_from_csv(csv_path, dry_run=args.dry_run)

    print(f"\nDone. Success: {result['success']}, Failed: {result['failed']}")
    if result["errors"]:
        print(f"\nErrors:")
        for err in result["errors"]:
            print(f"  - ID {err['id']}: {err['error']}")


def cmd_create_from_csv(args):
    """从 CSV 读取并创建新 transaction（id 为空或缺失的行）"""
    csv_path = args.csv
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    client = FinanceClient(args.server)
    print(f"Creating new transactions from {csv_path} to {args.server} ...")

    if args.dry_run:
        print("[DRY RUN MODE] No actual requests will be sent.\n")

    result = client.create_from_csv(csv_path, dry_run=args.dry_run)

    print(f"\nDone. Created: {result['success']}, Failed: {result['failed']}")
    if result["errors"]:
        print(f"\nErrors:")
        for err in result["errors"]:
            print(f"  - Row '{err['row']}': {err['error']}")


# ============================================================================
# Main Entry
# ============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="FinanceClient - SailZen 财务交易 CLI 工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ---- 公共参数 ----
    def add_server_arg(p):
        p.add_argument(
            "--server",
            default=os.environ.get("SAIL_SERVER_URL", DEFAULT_SERVER_URL),
            help=f"sail_server 地址 (默认: {DEFAULT_SERVER_URL}, 环境变量: SAIL_SERVER_URL)",
        )

    # ---- list-accounts ----
    p_list = subparsers.add_parser("list-accounts", aliases=["la"], help="列出所有账户")
    add_server_arg(p_list)
    p_list.set_defaults(func=cmd_list_accounts)

    # ---- pull ----
    p_pull = subparsers.add_parser("pull", help="拉取 transaction 并导出为 CSV")
    add_server_arg(p_pull)
    p_pull.add_argument(
        "--account", "-a",
        type=int,
        default=None,
        help="按 account_id 过滤（可选，不指定则拉取全部）",
    )
    p_pull.add_argument(
        "--output", "-o",
        default=None,
        help="输出 CSV 文件路径（默认: transactions_{account_id}.csv）",
    )
    p_pull.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"每页拉取数量（默认: {DEFAULT_PAGE_SIZE}, 最大: 100）",
    )
    p_pull.set_defaults(func=cmd_pull)

    # ---- push ----
    p_push = subparsers.add_parser("push", help="从 CSV 读取并推送更新到服务器")
    add_server_arg(p_push)
    p_push.add_argument(
        "csv",
        help="CSV 文件路径",
    )
    p_push.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="仅预览，不实际发送请求",
    )
    p_push.set_defaults(func=cmd_push)

    # ---- create-from-csv ----
    p_create = subparsers.add_parser("create-from-csv", aliases=["create"], help="从 CSV 创建新 transaction（id 为空或缺失的行）")
    add_server_arg(p_create)
    p_create.add_argument(
        "csv",
        help="CSV 文件路径",
    )
    p_create.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="仅预览，不实际发送请求",
    )
    p_create.set_defaults(func=cmd_create_from_csv)

    # ----
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
