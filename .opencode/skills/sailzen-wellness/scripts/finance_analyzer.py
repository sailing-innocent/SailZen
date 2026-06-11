# -*- coding: utf-8 -*-
# @file finance_analyzer.py
# @brief 财务数据引擎 —— 只输出原始指标与证据，不做业务判断
# @author sailing-innocent
# @date 2026-06-07
# @version 2.0
# ---------------------------------
"""
财务数据引擎（纯工具层）

职责：
1. 读取财务交易 CSV，按时间范围过滤
2. 计算各项财务指标（储蓄率、收支比、波动率等）
3. 统计标签分布、月度聚合
4. 标记零食消费明细
5. 识别统计异常点（只标记，不判断重要性）
6. 输出结构化 JSON 供 LLM 解读

不做的：
- 不做 "healthy/warning/danger" 状态判定
- 不写结论性文字
- 不生成报告

使用方式：
    python finance_analyzer.py --finance-csv data.csv \
        --start 2025-01-01 --end 2025-12-31 \
        --output finance_evidence.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from common import AnalysisConfig, read_csv, write_json, parse_htime, Transaction


# ============================================================================
# 输出数据结构（纯数据，无判断）
# ============================================================================

@dataclass
class MonthlyMetrics:
    month: str
    income: float = 0.0
    expense: float = 0.0
    transfer: float = 0.0
    net: float = 0.0
    expense_count: int = 0
    income_count: int = 0
    snack_expense: float = 0.0
    snack_count: int = 0
    large_expense_count: int = 0  # >= 1000
    transaction_ids: list[int] = field(default_factory=list)


@dataclass
class TagMetrics:
    tag: str
    total: float = 0.0
    count: int = 0
    avg: float = 0.0
    max_single: float = 0.0
    min_single: float = 0.0
    median: float = 0.0
    std: float = 0.0
    monthly_breakdown: dict[str, float] = field(default_factory=dict)
    transaction_ids: list[int] = field(default_factory=list)


@dataclass
class CashflowMetrics:
    savings_rate: float = 0.0           # (收入-支出)/收入
    income_expense_ratio: float = 0.0   # 收入/支出
    avg_monthly_net: float = 0.0
    cashflow_volatility: float = 0.0    # 月度净流标准差
    positive_months: int = 0
    negative_months: int = 0
    total_months: int = 0
    net_cashflow: float = 0.0
    total_income: float = 0.0
    total_expense: float = 0.0


@dataclass
class RiskMetrics:
    emergency_months: float = 0.0       # 净正累积 / 月均支出
    income_stability_ratio: float = 0.0 # 工资收入 / 总收入
    expense_concentration: float = 0.0  # 最大标签 / 总支出
    top_tag_name: str = ""
    top_tag_ratio: float = 0.0
    large_expense_frequency: float = 0.0 # >=1000 笔数 / 月
    salary_ratio: float = 0.0
    non_salary_income: float = 0.0
    income_volatility: float = 0.0           # 收入波动率 CV
    expense_volatility: float = 0.0          # 支出波动率 CV
    essential_expense_ratio: float = 0.0     # 刚性支出占比
    discretionary_expense_ratio: float = 0.0 # 弹性支出占比
    consecutive_negative_months: int = 0     # 最大连续赤字月数
    survival_months: float = 0.0             # 基于净现金流的生存月数
    top3_expense_ratio: float = 0.0          # TOP3标签支出占总支出比例
    # --- 增强：基于真实 Account 余额的抗风险指标 ---
    account_based_emergency_months: float = 0.0  # 总资产 / 月均支出
    liquid_emergency_months: float = 0.0         # 流动资产 / 月均刚性支出
    net_worth: float = 0.0                       # 净资产快照


@dataclass
class ResilienceMetrics:
    """抗风险韧性指标 —— 支撑决策的核心数据"""
    financial_stress_index: float = 0.0      # 财务压力指数 0-100（越高越危险）
    buffer_capacity: float = 0.0             # 缓冲能力：弹性支出占比（可削减空间%）
    essential_expense_ratio: float = 0.0     # 刚性支出占总支出比例
    discretionary_expense_ratio: float = 0.0 # 弹性支出占比
    income_volatility: float = 0.0           # 收入波动率（CV，标准差/均值）
    expense_volatility: float = 0.0          # 支出波动率（CV）
    consecutive_negative_months: int = 0     # 最大连续赤字月数
    consecutive_positive_months: int = 0     # 最大连续盈余月数
    survival_months_at_current_burn: float = 0.0  # 按当前支出速度，净现金流可支撑月数
    scenario_3mo_no_income: dict = field(default_factory=dict)  # 3个月无收入情景
    scenario_50pct_income_drop: dict = field(default_factory=dict)  # 收入减半情景
    burn_rate_trend: str = ""                # 支出趋势："rising"/"stable"/"falling"
    liquidity_score: float = 0.0             # 流动性评分 0-100
    # --- 增强：基于真实 Account 余额的决策级指标 ---
    net_worth: float = 0.0                   # 净资产（所有账户余额总和）
    liquid_assets: float = 0.0               # 流动资产（活期/现金类账户）
    illiquid_assets: float = 0.0             # 非流动资产（定期/投资/房产等）
    real_emergency_months: float = 0.0       # 基于流动资产的真实应急月数（流动资产 / 月均刚性支出）
    account_breakdown: list[dict] = field(default_factory=list)  # 账户明细 [{name, balance, liquidity}]
    debt_service_ratio: float = 0.0          # 债务偿还支出占总支出比例
    essential_monthly_burn: float = 0.0      # 月均刚性支出


@dataclass
class SnackMetrics:
    total_expense: float = 0.0
    total_count: int = 0
    avg_per_day: float = 0.0
    pct_of_expense: float = 0.0
    daily_records: list[tuple[str, float]] = field(default_factory=list)  # (date, amount)
    monthly_breakdown: dict[str, float] = field(default_factory=dict)
    item_breakdown: list[tuple[str, float, int]] = field(default_factory=list)  # (desc, amount, count)


@dataclass
class StatisticalOutlier:
    """统计异常点 —— 只标记偏离度，不判断是否应该担心"""
    transaction_id: int
    date: str
    description: str
    amount: float
    tags: str
    tag_mean: float
    tag_std: float
    z_score: float            # (value - mean) / std
    outlier_type: str         # "tag_level" / "monthly_level" / "income_gap"


@dataclass
class FinanceEvidence:
    """财务证据包 —— 供 LLM 解读"""
    period: str = ""
    total_income: float = 0.0
    total_expense: float = 0.0
    total_transfer: float = 0.0
    net_cashflow: float = 0.0
    tx_count: int = 0
    expense_count: int = 0
    income_count: int = 0
    transfer_count: int = 0
    monthly: list[MonthlyMetrics] = field(default_factory=list)
    tags: list[TagMetrics] = field(default_factory=list)
    cashflow: CashflowMetrics = field(default_factory=CashflowMetrics)
    risk: RiskMetrics = field(default_factory=RiskMetrics)
    snack: SnackMetrics = field(default_factory=SnackMetrics)
    outliers: list[StatisticalOutlier] = field(default_factory=list)
    top_expenses: list[tuple[int, str, str, float]] = field(default_factory=list)  # (id, date, desc, amount)
    top_incomes: list[tuple[int, str, str, float]] = field(default_factory=list)
    resilience: ResilienceMetrics = field(default_factory=ResilienceMetrics)
    accounts_snapshot: list[dict] = field(default_factory=list)  # 账户余额快照


# ============================================================================
# 财务数据引擎
# ============================================================================

class FinanceEngine:
    def __init__(self, config: Optional[AnalysisConfig] = None):
        self.config = config or AnalysisConfig()
        self.transactions: list[Transaction] = []
        self.accounts: list[dict] = []

    def load_csv(self, csv_path: str) -> "FinanceEngine":
        rows = read_csv(csv_path)
        self.transactions = [Transaction.from_row(r) for r in rows]
        return self

    def load_accounts(self, accounts: list[dict]) -> "FinanceEngine":
        self.accounts = accounts
        return self

    def filter_period(self, start: datetime, end: datetime, exclude_mortgage: Optional[bool] = None) -> list[Transaction]:
        if exclude_mortgage is None:
            exclude_mortgage = self.config.exclude_mortgage
        result = []
        for tx in self.transactions:
            if start <= tx.htime <= end:
                if exclude_mortgage and (tx.from_acc_id == self.config.mortgage_acc_id or tx.to_acc_id == self.config.mortgage_acc_id):
                    continue
                result.append(tx)
        return result

    def analyze(self, start: datetime, end: datetime, label: str = "") -> FinanceEvidence:
        txs = self.filter_period(start, end)
        ev = FinanceEvidence(period=label or f"{start.date()} ~ {end.date()}")

        if not txs:
            return ev

        expenses = [t for t in txs if t.tx_type == "expense"]
        incomes = [t for t in txs if t.tx_type == "income"]
        transfers = [t for t in txs if t.tx_type == "transfer"]

        ev.total_expense = sum(t.value for t in expenses)
        ev.total_income = sum(t.value for t in incomes)
        ev.total_transfer = sum(t.value for t in transfers)
        ev.net_cashflow = ev.total_income - ev.total_expense
        ev.expense_count = len(expenses)
        ev.income_count = len(incomes)
        ev.transfer_count = len(transfers)
        ev.tx_count = len(txs)

        # TOP 单笔
        ev.top_expenses = sorted(
            [(t.id, t.htime.strftime("%Y-%m-%d"), t.description, t.value) for t in expenses],
            key=lambda x: x[3], reverse=True
        )[:20]
        ev.top_incomes = sorted(
            [(t.id, t.htime.strftime("%Y-%m-%d"), t.description, t.value) for t in incomes],
            key=lambda x: x[3], reverse=True
        )[:10]

        # 月度聚合
        ev.monthly = self._calc_monthly(expenses, incomes, transfers)

        # 标签统计
        ev.tags = self._calc_tags(expenses)

        # 现金流指标
        ev.cashflow = self._calc_cashflow(ev.monthly, ev.total_income, ev.total_expense, ev.net_cashflow)

        # 抗风险指标
        ev.risk = self._calc_risk(ev, expenses, incomes)

        # 韧性指标
        ev.resilience = self._calc_resilience(ev, expenses, incomes)
        ev.accounts_snapshot = self.accounts

        # 零食追踪
        ev.snack = self._calc_snack(expenses, start, end)

        # 统计异常点
        ev.outliers = self._find_outliers(expenses, incomes, ev.monthly)

        return ev

    def _calc_monthly(self, expenses, incomes, transfers) -> list[MonthlyMetrics]:
        mmap: dict[str, MonthlyMetrics] = {}
        for tx in expenses + incomes + transfers:
            key = tx.htime.strftime("%Y-%m")
            if key not in mmap:
                mmap[key] = MonthlyMetrics(month=key)
            m = mmap[key]
            m.transaction_ids.append(tx.id)
            if tx.tx_type == "expense":
                m.expense += tx.value
                m.expense_count += 1
                if any(tag in tx.tags for tag in self.config.snack_tags):
                    m.snack_expense += tx.value
                    m.snack_count += 1
                if tx.value >= 1000:
                    m.large_expense_count += 1
            elif tx.tx_type == "income":
                m.income += tx.value
                m.income_count += 1
            elif tx.tx_type == "transfer":
                m.transfer += tx.value

        result = []
        for key in sorted(mmap.keys()):
            m = mmap[key]
            m.net = m.income - m.expense
            result.append(m)
        return result

    def _calc_tags(self, expenses: list[Transaction]) -> list[TagMetrics]:
        tag_data: dict[str, list[tuple[int, float, str]]] = defaultdict(list)  # (tx_id, value, month)
        for tx in expenses:
            month = tx.htime.strftime("%Y-%m")
            for tag in tx.tags.split(","):
                tag = tag.strip()
                if tag:
                    tag_data[tag].append((tx.id, tx.value, month))

        result = []
        for tag, records in tag_data.items():
            values = [v for _, v, _ in records]
            tm = TagMetrics(tag=tag)
            tm.total = sum(values)
            tm.count = len(values)
            tm.avg = tm.total / tm.count if tm.count > 0 else 0
            tm.max_single = max(values)
            tm.min_single = min(values)
            values_sorted = sorted(values)
            tm.median = values_sorted[len(values_sorted)//2] if values_sorted else 0
            if len(values) > 1:
                mean = tm.avg
                tm.std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))

            monthly: dict[str, float] = defaultdict(float)
            for _, v, m in records:
                monthly[m] += v
            tm.monthly_breakdown = dict(sorted(monthly.items()))
            tm.transaction_ids = [tid for tid, _, _ in records]
            result.append(tm)

        return sorted(result, key=lambda x: x.total, reverse=True)

    def _calc_cashflow(self, monthly: list[MonthlyMetrics], total_income: float, total_expense: float, net: float) -> CashflowMetrics:
        cf = CashflowMetrics()
        cf.total_income = total_income
        cf.total_expense = total_expense
        cf.net_cashflow = net
        cf.total_months = len(monthly)

        nets = [m.net for m in monthly]
        if nets:
            cf.avg_monthly_net = sum(nets) / len(nets)
            if len(nets) > 1:
                mean = cf.avg_monthly_net
                cf.cashflow_volatility = math.sqrt(sum((n - mean) ** 2 for n in nets) / len(nets))
            cf.positive_months = sum(1 for n in nets if n > 0)
            cf.negative_months = sum(1 for n in nets if n < 0)

        if total_income > 0:
            cf.savings_rate = (total_income - total_expense) / total_income * 100
        if total_expense > 0:
            cf.income_expense_ratio = total_income / total_expense

        return cf

    def _calc_risk(self, ev: FinanceEvidence, expenses: list[Transaction], incomes: list[Transaction]) -> RiskMetrics:
        rm = RiskMetrics()

        # 工资收入占比
        salary_income = sum(t.value for t in incomes if "工资" in t.description)
        if ev.total_income > 0:
            rm.salary_ratio = salary_income / ev.total_income * 100
            rm.income_stability_ratio = rm.salary_ratio
            rm.non_salary_income = ev.total_income - salary_income

        # 支出集中度
        if ev.tags:
            top_tag = ev.tags[0]
            rm.top_tag_name = top_tag.tag
            rm.top_tag_ratio = top_tag.total / ev.total_expense * 100 if ev.total_expense > 0 else 0
            rm.expense_concentration = rm.top_tag_ratio

        # 大额支出频率
        if ev.monthly:
            total_large = sum(m.large_expense_count for m in ev.monthly)
            rm.large_expense_frequency = total_large / len(ev.monthly)

        # 应急资金月数（简化）
        avg_monthly_expense = sum(m.expense for m in ev.monthly) / len(ev.monthly) if ev.monthly else 1
        if avg_monthly_expense > 0:
            rm.emergency_months = max(0, ev.net_cashflow) / avg_monthly_expense

        # --- 新增：决策支撑指标 ---
        monthly = ev.monthly

        # 收入波动率
        monthly_incomes = [m.income for m in monthly]
        if len(monthly_incomes) > 1:
            mean_income = sum(monthly_incomes) / len(monthly_incomes)
            if mean_income > 0:
                std_income = math.sqrt(sum((v - mean_income) ** 2 for v in monthly_incomes) / len(monthly_incomes))
                rm.income_volatility = std_income / mean_income

        # 支出波动率
        monthly_expenses = [m.expense for m in monthly]
        if len(monthly_expenses) > 1:
            mean_expense = sum(monthly_expenses) / len(monthly_expenses)
            if mean_expense > 0:
                std_expense = math.sqrt(sum((v - mean_expense) ** 2 for v in monthly_expenses) / len(monthly_expenses))
                rm.expense_volatility = std_expense / mean_expense

        # 刚性/弹性支出比例
        essential = sum(
            t.value for t in expenses
            if any(tag.strip() in self.config.essential_tags for tag in t.tags.split(","))
        )
        discretionary = ev.total_expense - essential
        if ev.total_expense > 0:
            rm.essential_expense_ratio = essential / ev.total_expense * 100
            rm.discretionary_expense_ratio = discretionary / ev.total_expense * 100

        # 最大连续赤字月数
        max_neg = 0
        cur_neg = 0
        for m in monthly:
            if m.net < 0:
                cur_neg += 1
                max_neg = max(max_neg, cur_neg)
            else:
                cur_neg = 0
        rm.consecutive_negative_months = max_neg

        # 基于净现金流的生存月数
        if avg_monthly_expense > 0 and ev.net_cashflow > 0:
            rm.survival_months = ev.net_cashflow / avg_monthly_expense

        # TOP3标签支出占总支出比例
        top3_total = sum(tag.total for tag in ev.tags[:3])
        if ev.total_expense > 0:
            rm.top3_expense_ratio = top3_total / ev.total_expense * 100

        # --- 增强：基于真实 Account 余额的抗风险指标 ---
        has_accounts = bool(self.accounts)
        if has_accounts:
            total_balance = sum(float(acc.get("balance", 0) or 0) for acc in self.accounts)
            rm.net_worth = total_balance

            # 账户流动性分类（与 resilience 保持一致）
            liquid_keywords = {"活期", "现金", "支付宝", "微信", "零钱", "备用金", "日常", "生活"}
            liquid_balance = 0.0
            for acc in self.accounts:
                balance = float(acc.get("balance", 0) or 0)
                name = str(acc.get("name", "")).lower()
                if any(kw in name for kw in liquid_keywords):
                    liquid_balance += balance
                else:
                    # 默认流动
                    liquid_balance += balance

            if avg_monthly_expense > 0:
                rm.account_based_emergency_months = total_balance / avg_monthly_expense

            essential = sum(
                t.value for t in expenses
                if any(tag.strip() in self.config.essential_tags for tag in t.tags.split(","))
            )
            avg_essential_monthly = essential / len(ev.monthly) if ev.monthly else 0.0
            if avg_essential_monthly > 0:
                rm.liquid_emergency_months = liquid_balance / avg_essential_monthly

        return rm

    def _calc_resilience(self, ev: FinanceEvidence, expenses: list[Transaction], incomes: list[Transaction]) -> ResilienceMetrics:
        rm = ResilienceMetrics()
        monthly = ev.monthly

        avg_monthly_income = sum(m.income for m in monthly) / len(monthly) if monthly else 0.0
        avg_monthly_expense = sum(m.expense for m in monthly) / len(monthly) if monthly else 0.0

        # 收入波动率
        monthly_incomes = [m.income for m in monthly]
        if len(monthly_incomes) > 1 and avg_monthly_income > 0:
            std_income = math.sqrt(sum((v - avg_monthly_income) ** 2 for v in monthly_incomes) / len(monthly_incomes))
            rm.income_volatility = std_income / avg_monthly_income

        # 支出波动率
        monthly_expenses = [m.expense for m in monthly]
        if len(monthly_expenses) > 1 and avg_monthly_expense > 0:
            std_expense = math.sqrt(sum((v - avg_monthly_expense) ** 2 for v in monthly_expenses) / len(monthly_expenses))
            rm.expense_volatility = std_expense / avg_monthly_expense

        # 刚性/弹性支出
        essential = sum(
            t.value for t in expenses
            if any(tag.strip() in self.config.essential_tags for tag in t.tags.split(","))
        )
        discretionary = ev.total_expense - essential
        if ev.total_expense > 0:
            rm.essential_expense_ratio = essential / ev.total_expense * 100
            rm.discretionary_expense_ratio = discretionary / ev.total_expense * 100
        rm.buffer_capacity = rm.discretionary_expense_ratio
        rm.essential_monthly_burn = essential / len(monthly) if monthly else 0.0

        # 连续赤字/盈余
        max_neg = 0
        max_pos = 0
        cur_neg = 0
        cur_pos = 0
        for m in monthly:
            if m.net < 0:
                cur_neg += 1
                cur_pos = 0
                max_neg = max(max_neg, cur_neg)
            elif m.net > 0:
                cur_pos += 1
                cur_neg = 0
                max_pos = max(max_pos, cur_pos)
            else:
                cur_neg = 0
                cur_pos = 0
        rm.consecutive_negative_months = max_neg
        rm.consecutive_positive_months = max_pos

        # 生存月数
        if avg_monthly_expense > 0 and ev.net_cashflow > 0:
            rm.survival_months_at_current_burn = ev.net_cashflow / avg_monthly_expense

        # 债务偿还支出占比
        debt_expense = sum(
            t.value for t in expenses
            if any(tag.strip() in {"房贷", "信用卡还款", "贷款", "借款", "分期", "花呗", "白条"} for tag in t.tags.split(","))
        )
        if ev.total_expense > 0:
            rm.debt_service_ratio = debt_expense / ev.total_expense * 100

        # --- 增强：基于真实 Account 余额的决策级指标 ---
        has_accounts = bool(self.accounts)
        if has_accounts:
            liquid_keywords = {"活期", "现金", "支付宝", "微信", "零钱", "备用金", "日常", "生活"}
            illiquid_keywords = {"定期", "理财", "基金", "股票", "债券", "房产", "公积金", "投资", "养老"}

            total_balance = 0.0
            liquid_balance = 0.0
            illiquid_balance = 0.0
            account_breakdown = []

            for acc in self.accounts:
                balance = float(acc.get("balance", 0) or 0)
                name = str(acc.get("name", "")).lower()
                total_balance += balance

                if any(kw in name for kw in liquid_keywords):
                    liquidity = "liquid"
                    liquid_balance += balance
                elif any(kw in name for kw in illiquid_keywords):
                    liquidity = "illiquid"
                    illiquid_balance += balance
                else:
                    # 默认归类为流动资产（保守策略）
                    liquidity = "liquid"
                    liquid_balance += balance

                account_breakdown.append({
                    "name": acc.get("name", ""),
                    "balance": balance,
                    "liquidity": liquidity,
                })

            rm.net_worth = total_balance
            rm.liquid_assets = liquid_balance
            rm.illiquid_assets = illiquid_balance
            rm.account_breakdown = account_breakdown

            # 真实应急月数 = 流动资产 / 月均刚性支出
            if rm.essential_monthly_burn > 0:
                rm.real_emergency_months = liquid_balance / rm.essential_monthly_burn

            # 更新流动性评分：基于流动资产而非总资产
            if avg_monthly_expense > 0:
                liquidity_months = liquid_balance / avg_monthly_expense
                rm.liquidity_score = min(100.0, liquidity_months * 8.33)
        else:
            total_balance = 0.0
            liquid_balance = 0.0

        # 财务压力指数 (0-100，越高越危险)
        savings_rate = ev.cashflow.savings_rate

        # 储蓄率压力 (30%)
        if savings_rate < 0:
            stress_savings = min(100.0, abs(savings_rate) * 2.0)
        else:
            stress_savings = max(0.0, 50.0 - savings_rate)

        # 收入波动压力 (20%)
        stress_income_vol = min(100.0, rm.income_volatility * 100.0 * 2.0)

        # 支出波动压力 (15%)
        stress_expense_vol = min(100.0, rm.expense_volatility * 100.0 * 2.0)

        # 连续赤字压力 (20%)
        stress_deficit = min(100.0, max_neg * 20.0)

        # 应急月数压力 (15%)：优先使用真实应急月数，回退到现金流应急月数
        emergency_months = rm.real_emergency_months if rm.real_emergency_months > 0 else ev.risk.emergency_months
        if emergency_months < 1:
            stress_emergency = 100.0
        elif emergency_months < 3:
            stress_emergency = 80.0
        elif emergency_months < 6:
            stress_emergency = 50.0
        elif emergency_months < 12:
            stress_emergency = 20.0
        else:
            stress_emergency = 0.0

        rm.financial_stress_index = (
            stress_savings * 0.30
            + stress_income_vol * 0.20
            + stress_expense_vol * 0.15
            + stress_deficit * 0.20
            + stress_emergency * 0.15
        )

        # 情景分析：3个月无收入
        avg_essential_monthly = essential / len(monthly) if monthly else 0.0
        required_reserve = 3.0 * avg_essential_monthly
        months_can_survive = rm.survival_months_at_current_burn

        if has_accounts:
            gap = required_reserve - liquid_balance
            if gap <= 0:
                status = "adequate"
            elif gap <= required_reserve * 0.5:
                status = "insufficient"
            else:
                status = "critical"
        else:
            gap = 0.0
            status = "unavailable (no accounts data)"

        rm.scenario_3mo_no_income = {
            "required_reserve": required_reserve,
            "current_reserve_status": status,
            "gap_amount": gap if has_accounts else 0.0,
            "months_can_survive": months_can_survive,
            "liquid_assets": liquid_balance if has_accounts else 0.0,
            "total_assets": total_balance if has_accounts else 0.0,
        }

        # 情景分析：收入减半
        new_monthly_income = avg_monthly_income * 0.5
        monthly_deficit = avg_monthly_expense - new_monthly_income
        annual_deficit = monthly_deficit * 12.0 if monthly_deficit > 0 else 0.0
        can_survive = new_monthly_income >= avg_monthly_expense

        rm.scenario_50pct_income_drop = {
            "new_monthly_income": new_monthly_income,
            "monthly_deficit": monthly_deficit if monthly_deficit > 0 else 0.0,
            "annual_deficit": annual_deficit,
            "can_survive": can_survive,
            "months_can_survive_with_liquid": rm.real_emergency_months if has_accounts else 0.0,
        }

        # 支出趋势
        if len(monthly) >= 6:
            recent = sum(m.expense for m in monthly[-3:]) / 3.0
            previous = sum(m.expense for m in monthly[-6:-3]) / 3.0
            if previous > 0:
                if recent > previous * 1.05:
                    rm.burn_rate_trend = "rising"
                elif recent < previous * 0.95:
                    rm.burn_rate_trend = "falling"
                else:
                    rm.burn_rate_trend = "stable"
            else:
                rm.burn_rate_trend = "stable"
        elif len(monthly) >= 2:
            mid = len(monthly) // 2
            recent = sum(m.expense for m in monthly[mid:]) / max(1, len(monthly) - mid)
            previous = sum(m.expense for m in monthly[:mid]) / max(1, mid)
            if previous > 0:
                if recent > previous * 1.05:
                    rm.burn_rate_trend = "rising"
                elif recent < previous * 0.95:
                    rm.burn_rate_trend = "falling"
                else:
                    rm.burn_rate_trend = "stable"
            else:
                rm.burn_rate_trend = "stable"
        else:
            rm.burn_rate_trend = "insufficient_data"

        # 流动性评分（若上面未计算）
        if rm.liquidity_score == 0.0 and has_accounts and avg_monthly_expense > 0:
            liquidity_months = liquid_balance / avg_monthly_expense
            rm.liquidity_score = min(100.0, liquidity_months * 8.33)

        return rm

    def _calc_snack(self, expenses: list[Transaction], start: datetime, end: datetime) -> SnackMetrics:
        sm = SnackMetrics()
        snack_txs = [t for t in expenses if any(tag in t.tags for tag in self.config.snack_tags)]

        sm.total_expense = sum(t.value for t in snack_txs)
        sm.total_count = len(snack_txs)
        days = max(1, (end - start).days + 1)
        sm.avg_per_day = sm.total_expense / days

        if expenses:
            total_exp = sum(t.value for t in expenses)
            sm.pct_of_expense = sm.total_expense / total_exp * 100

        # 日记录
        daily: dict[str, float] = defaultdict(float)
        for t in snack_txs:
            key = t.htime.strftime("%Y-%m-%d")
            daily[key] += t.value
        sm.daily_records = sorted(daily.items())

        # 月度
        monthly: dict[str, float] = defaultdict(float)
        for t in snack_txs:
            key = t.htime.strftime("%Y-%m")
            monthly[key] += t.value
        sm.monthly_breakdown = dict(sorted(monthly.items()))

        # 项目明细
        item_map: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
        for t in snack_txs:
            item_map[t.description] = (item_map[t.description][0] + t.value, item_map[t.description][1] + 1)
        sm.item_breakdown = sorted([(desc, amt, cnt) for desc, (amt, cnt) in item_map.items()], key=lambda x: x[1], reverse=True)

        return sm

    def _find_outliers(self, expenses: list[Transaction], incomes: list[Transaction], monthly: list[MonthlyMetrics]) -> list[StatisticalOutlier]:
        outliers = []

        # 1. 标签级异常（Z-score > 3）
        tag_values: dict[str, list[tuple[int, float, str, str]]] = defaultdict(list)  # (id, value, desc, date)
        for tx in expenses:
            for tag in tx.tags.split(","):
                tag = tag.strip()
                if tag:
                    tag_values[tag].append((tx.id, tx.value, tx.description, tx.htime.strftime("%Y-%m-%d")))

        for tag, records in tag_values.items():
            if len(records) < 10:
                continue  # 样本不足，跳过
            values = [v for _, v, _, _ in records]
            mean = sum(values) / len(values)
            std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
            if std == 0:
                continue
            for tid, val, desc, date in records:
                z = (val - mean) / std
                if z > 3 and val >= 500:  # 金额过小不标记
                    outliers.append(StatisticalOutlier(
                        transaction_id=tid,
                        date=date,
                        description=desc,
                        amount=val,
                        tags=tag,
                        tag_mean=mean,
                        tag_std=std,
                        z_score=z,
                        outlier_type="tag_level",
                    ))

        # 2. 月度支出突增（Z-score > 2）
        if len(monthly) >= 3:
            expense_values = [m.expense for m in monthly]
            mean_m = sum(expense_values) / len(expense_values)
            std_m = math.sqrt(sum((v - mean_m) ** 2 for v in expense_values) / len(expense_values))
            if std_m > 0:
                for m in monthly:
                    z = (m.expense - mean_m) / std_m
                    if z > 2:
                        outliers.append(StatisticalOutlier(
                            transaction_id=-1,
                            date=m.month,
                            description=f"{m.month}月总支出",
                            amount=m.expense,
                            tags="",
                            tag_mean=mean_m,
                            tag_std=std_m,
                            z_score=z,
                            outlier_type="monthly_level",
                        ))

        # 3. 收入中断
        for i, m in enumerate(monthly):
            if m.income == 0 and i > 0 and monthly[i-1].income > 0:
                outliers.append(StatisticalOutlier(
                    transaction_id=-1,
                    date=m.month,
                    description=f"{m.month}月收入中断",
                    amount=0,
                    tags="",
                    tag_mean=0,
                    tag_std=0,
                    z_score=0,
                    outlier_type="income_gap",
                ))

        return sorted(outliers, key=lambda o: o.date)


def main():
    parser = argparse.ArgumentParser(description="财务数据引擎 —— 输出证据供 LLM 解读")
    parser.add_argument("--finance-csv", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", "-o", default="finance_evidence.json")
    parser.add_argument("--include-mortgage", action="store_true")
    parser.add_argument("--accounts-json", default=None, help="账户余额 JSON 文件路径，格式 [{\"id\": 1, \"name\": \"日常\", \"balance\": \"12345.67\"}, ...]")
    args = parser.parse_args()

    config = AnalysisConfig(exclude_mortgage=not args.include_mortgage)
    engine = FinanceEngine(config)
    engine.load_csv(args.finance_csv)

    if args.accounts_json:
        with open(args.accounts_json, "r", encoding="utf-8") as f:
            engine.load_accounts(json.load(f))

    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")

    evidence = engine.analyze(start_dt, end_dt)

    def serialize(obj):
        if isinstance(obj, list):
            return [serialize(i) for i in obj]
        if hasattr(obj, "__dataclass_fields__"):
            return {k: serialize(v) for k, v in asdict(obj).items()}
        return obj

    write_json(args.output, serialize(evidence))
    print(f"证据包已输出: {args.output}")
    print(f"  交易数: {evidence.tx_count}")
    print(f"  月度: {len(evidence.monthly)}")
    print(f"  标签: {len(evidence.tags)}")
    print(f"  异常点: {len(evidence.outliers)}")


if __name__ == "__main__":
    main()
