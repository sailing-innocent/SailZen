# -*- coding: utf-8 -*-
# @file budget_analyzer.py
# @brief 预算分析引擎 —— 拉取 Budget 数据，计算执行率与预警
# @author sailing-innocent
# @date 2026-06-18
# @version 1.0
# ---------------------------------
"""
预算分析引擎（纯工具层）

职责：
1. 通过 HTTP API 从 sail_server 拉取 Budget 数据
2. 计算预算执行率、超预算预警
3. 分析预算与 transaction 标签的匹配度
4. 输出结构化 JSON 供 LLM 解读

不做的：
- 不做 "healthy/warning/danger" 状态判定（只输出执行率数据）
- 不写结论性文字
- 不生成报告

使用方式：
    python budget_analyzer.py --start 2025-01-01 --end 2025-12-31 --label 2025
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    AnalysisConfig,
    FINANCE_API_BASE,
    resolve_server_url,
    write_json,
    SailZenClient,
)


# ============================================================================
# 输出数据结构（纯数据，无判断）
# ============================================================================

@dataclass
class BudgetItemExecution:
    item_id: int = 0
    name: str = ""
    amount: float = 0.0
    total_amount: float = 0.0
    remaining_periods: int = 0
    status: str = ""  # 从 API 返回的 status 转换


@dataclass
class BudgetExecutionMetrics:
    budget_id: int = 0
    budget_name: str = ""
    tags: str = ""
    total_amount: float = 0.0
    used_amount: float = 0.0
    remaining_amount: float = 0.0
    usage_percentage: float = 0.0
    transaction_count: int = 0
    direction: int = 0  # 0=支出 1=收入
    items: list[BudgetItemExecution] = field(default_factory=list)
    by_tag: dict[str, dict] = field(default_factory=dict)  # {tag: {"amount": float, "count": int}}
    top_transactions: list[dict] = field(default_factory=list)  # 大额交易 TOP5


@dataclass
class BudgetEvidence:
    period: str = ""
    total_budget_count: int = 0
    total_budget_amount: float = 0.0
    total_used_amount: float = 0.0
    total_remaining_amount: float = 0.0
    overall_usage_percentage: float = 0.0
    budgets: list[BudgetExecutionMetrics] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)  # 预警列表
    untagged_budget_spending: list[dict] = field(default_factory=list)  # 未关联 budget 的大额支出


# ============================================================================
# 预算分析引擎
# ============================================================================

class BudgetAnalyzer:
    def __init__(self, config: Optional[AnalysisConfig] = None):
        self.config = config or AnalysisConfig()
        self.client = SailZenClient(self.config.server_url)

    def analyze(self, start_ts: int, end_ts: int, label: str = "") -> BudgetEvidence:
        ev = BudgetEvidence(period=label)

        # 1. 拉取预算列表
        budgets = self._fetch_budgets(start_ts, end_ts)

        # 2. 拉取预算统计（overview）
        stats = self._fetch_budget_stats(start_ts, end_ts)
        ev.total_budget_count = stats.get("total_budget_count", 0)
        ev.total_budget_amount = self._safe_float(stats.get("total_budget_amount"))
        ev.total_used_amount = self._safe_float(stats.get("total_used_amount"))
        ev.total_remaining_amount = self._safe_float(stats.get("total_remaining_amount"))
        if ev.total_budget_amount > 0:
            ev.overall_usage_percentage = ev.total_used_amount / ev.total_budget_amount * 100

        # 3. 逐个预算拉取详细分析
        for b in budgets:
            detail = self._fetch_budget_analysis(self._safe_int(b.get("id")))
            if detail:
                bem = self._build_budget_execution(b, detail)
                ev.budgets.append(bem)

                # 生成预警
                w = self._check_warnings(bem)
                if w:
                    ev.warnings.extend(w)

        # 4. 拉取未关联 budget 的大额支出（通过 transaction paginated API）
        ev.untagged_budget_spending = self._fetch_untagged_spending(start_ts, end_ts)

        return ev

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_float(val) -> float:
        if val is None:
            return 0.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _safe_int(val) -> int:
        if val is None:
            return 0
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0

    # ------------------------------------------------------------------
    # 数据拉取
    # ------------------------------------------------------------------

    def _fetch_budgets(self, from_time: int, to_time: int) -> list[dict]:
        url = f"{FINANCE_API_BASE}/budget"
        params = {"from_time": from_time, "to_time": to_time, "limit": -1}
        try:
            data = self.client.get(url, params)
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[BudgetAnalyzer] 拉取预算列表失败: {e}")
            return []

    def _fetch_budget_stats(self, from_time: int, to_time: int) -> dict:
        url = f"{FINANCE_API_BASE}/budget/stats/"
        params = {"from_time": from_time, "to_time": to_time, "return_list": "true"}
        try:
            return self.client.get(url, params)
        except Exception as e:
            print(f"[BudgetAnalyzer] 拉取预算统计失败: {e}")
            return {}

    def _fetch_budget_analysis(self, budget_id: int) -> Optional[dict]:
        if budget_id <= 0:
            return None
        url = f"{FINANCE_API_BASE}/budget/{budget_id}/analysis"
        try:
            return self.client.get(url)
        except Exception as e:
            print(f"[BudgetAnalyzer] 拉取预算 {budget_id} 分析失败: {e}")
            return None

    def _fetch_untagged_spending(self, from_time: int, to_time: int) -> list[dict]:
        """拉取未关联 budget 的大额支出（金额 >= 500），返回前 10 条"""
        url = f"{FINANCE_API_BASE}/transaction/paginated/"
        params = {"from_time": from_time, "to_time": to_time, "page_size": 100}
        try:
            resp = self.client.get(url, params)
            txs = resp.get("data", []) if isinstance(resp, dict) else resp if isinstance(resp, list) else []
        except Exception as e:
            print(f"[BudgetAnalyzer] 拉取交易列表失败: {e}")
            return []

        untagged = []
        for tx in txs:
            budget_id = tx.get("budget_id")
            if budget_id is not None and budget_id != 0:
                continue

            # 判断是否为支出
            tx_type = tx.get("type", "")
            if tx_type == "expense":
                is_expense = True
            else:
                f = self._safe_int(tx.get("from_acc_id"))
                t = self._safe_int(tx.get("to_acc_id"))
                is_expense = f > 0 and t == -1

            if not is_expense:
                continue

            val = self._safe_float(tx.get("value"))
            if val >= 500:
                untagged.append({
                    "id": tx.get("id"),
                    "date": tx.get("htime", ""),
                    "description": tx.get("description", ""),
                    "value": val,
                    "tags": tx.get("tags", ""),
                })

        return sorted(untagged, key=lambda x: x["value"], reverse=True)[:10]

    # ------------------------------------------------------------------
    # 指标构建
    # ------------------------------------------------------------------

    def _build_budget_execution(self, budget: dict, detail: dict) -> BudgetExecutionMetrics:
        bem = BudgetExecutionMetrics()
        bem.budget_id = self._safe_int(budget.get("id"))
        bem.budget_name = budget.get("name", "") or ""
        bem.tags = budget.get("tags", "") or ""
        bem.total_amount = self._safe_float(budget.get("total_amount"))
        bem.direction = self._safe_int(budget.get("direction", 0))

        # 从 analysis detail 中读取执行数据
        bem.used_amount = self._safe_float(detail.get("used_amount"))
        if bem.used_amount == 0.0:
            # 兼容字段名差异
            bem.used_amount = self._safe_float(detail.get("spent_amount", detail.get("amount", 0)))

        bem.remaining_amount = self._safe_float(detail.get("remaining_amount"))
        if bem.remaining_amount == 0.0 and bem.total_amount > 0:
            bem.remaining_amount = bem.total_amount - bem.used_amount

        bem.usage_percentage = self._safe_float(detail.get("usage_percentage"))
        if bem.usage_percentage == 0.0 and bem.total_amount > 0:
            bem.usage_percentage = bem.used_amount / bem.total_amount * 100

        bem.transaction_count = self._safe_int(detail.get("transaction_count"))

        # by_tag
        by_tag_raw = detail.get("by_tag", {})
        if isinstance(by_tag_raw, dict):
            for tag, info in by_tag_raw.items():
                if isinstance(info, dict):
                    bem.by_tag[tag] = {
                        "amount": self._safe_float(info.get("amount")),
                        "count": self._safe_int(info.get("count")),
                    }
                else:
                    bem.by_tag[tag] = {"amount": self._safe_float(info), "count": 0}

        # items（预算条目拆分）
        items_raw = budget.get("items", []) or detail.get("items", [])
        for item in items_raw:
            bem.items.append(BudgetItemExecution(
                item_id=self._safe_int(item.get("id")),
                name=item.get("name", "") or "",
                amount=self._safe_float(item.get("amount")),
                total_amount=self._safe_float(item.get("total_amount")),
                remaining_periods=self._safe_int(item.get("remaining_periods")),
                status=item.get("status", "") or "",
            ))

        # top_transactions（大额交易 TOP5）
        txs = detail.get("transactions", [])
        if isinstance(txs, list):
            sorted_txs = sorted(
                txs,
                key=lambda x: self._safe_float(x.get("value", 0)),
                reverse=True,
            )[:5]
            bem.top_transactions = [
                {
                    "id": tx.get("id"),
                    "date": tx.get("htime", ""),
                    "description": tx.get("description", ""),
                    "value": self._safe_float(tx.get("value")),
                    "tags": tx.get("tags", ""),
                }
                for tx in sorted_txs
            ]

        return bem

    # ------------------------------------------------------------------
    # 预警规则
    # ------------------------------------------------------------------

    def _check_warnings(self, bem: BudgetExecutionMetrics) -> list[dict]:
        warnings = []

        # 超预算预警
        if bem.usage_percentage > 100:
            warnings.append({
                "level": "critical",
                "type": "overrun",
                "budget_id": bem.budget_id,
                "budget_name": bem.budget_name,
                "message": f"预算 '{bem.budget_name}' 已超支 {bem.usage_percentage - 100:.1f}%",
                "used": bem.used_amount,
                "total": bem.total_amount,
            })
        elif bem.usage_percentage > 90:
            warnings.append({
                "level": "warning",
                "type": "near_overrun",
                "budget_id": bem.budget_id,
                "budget_name": bem.budget_name,
                "message": f"预算 '{bem.budget_name}' 已使用 {bem.usage_percentage:.1f}%，接近上限",
                "used": bem.used_amount,
                "total": bem.total_amount,
            })
        elif bem.usage_percentage > 80:
            warnings.append({
                "level": "info",
                "type": "high_usage",
                "budget_id": bem.budget_id,
                "budget_name": bem.budget_name,
                "message": f"预算 '{bem.budget_name}' 已使用 {bem.usage_percentage:.1f}%",
                "used": bem.used_amount,
                "total": bem.total_amount,
            })

        # 低利用率预警（收入预算）
        if bem.direction == 1 and bem.usage_percentage < 50 and bem.total_amount > 1000:
            warnings.append({
                "level": "info",
                "type": "low_usage",
                "budget_id": bem.budget_id,
                "budget_name": bem.budget_name,
                "message": f"收入预算 '{bem.budget_name}' 仅实现 {bem.usage_percentage:.1f}%",
            })

        return warnings


# ============================================================================
# 序列化辅助
# ============================================================================

def _serialize(obj):
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    return obj


# ============================================================================
# 入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="预算分析引擎")
    parser.add_argument("--start", required=True, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--label", required=True, help="证据包标签")
    parser.add_argument(
        "--output", "-o", default=None,
        help="输出 JSON 路径（默认 data/temp/wellness/budget_evidence_{label}.json）",
    )
    args = parser.parse_args()

    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    analyzer = BudgetAnalyzer()
    evidence = analyzer.analyze(start_ts, end_ts, f"{args.start} ~ {args.end}")

    output = args.output or f"data/temp/wellness/budget_evidence_{args.label}.json"

    write_json(output, _serialize(evidence))
    print(f"预算证据包已输出: {output}")
    print(f"  预算数: {evidence.total_budget_count}")
    print(f"  总预算: {evidence.total_budget_amount:.2f}")
    print(f"  已使用: {evidence.total_used_amount:.2f}")
    print(f"  剩余: {evidence.total_remaining_amount:.2f}")
    print(f"  预警: {len(evidence.warnings)} 条")


if __name__ == "__main__":
    main()
