# -*- coding: utf-8 -*-
# @file finance_analytics.py
# @brief SailTick 夜间个人账单与财务健康深度分析引擎（消费习惯/真实零食/固定与弹性支出/开源节流预测）
# @author sailing-innocent
# @date 2026-11-25
# @version 1.0
# ---------------------------------
"""FinanceAnalyticsEngine — 夜间确定性个人财务健康与消费习惯分析引擎。

设计定位：
- 不是企业复式审计报表，而是「懂我」的日常开销秘书后台分析大脑；
- 自动隔离 balance_adjust / micro_adjust / 房贷类排除账户，只分析真实消费与现金流；
- 优先按 Transaction.meta.items 拆分汇总真实零食与品类结构，打通财务 ↔ 健康盲区；
- 识别周期性刚性开销、月底支出预测、高频小额漏斗、沉默账户与差旅日程关联；
- 输出紧凑结论与最多 1 条高价值发问建议，编译进统一 `expert_brief["finance"]`。
"""

from __future__ import annotations

import calendar
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

_RIGID_TAGS = {"大宗收支", "医药健康"}
_RIGID_KEYWORDS = ("房租", "租金", "水费", "电费", "燃气", "宽带", "话费", "物业", "社保", "房贷")
_TRAVEL_KEYWORDS = ("高铁", "动车", "火车", "12306", "机票", "航班", "酒店", "民宿", "携程", "飞猪")
_MIXED_MERCHANTS = ("超市", "盒马", "山姆", "京东", "淘宝", "拼多多", "便利店", "全家", "罗森")


def _safe_float(raw: Any) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw or "0").strip()
    if " " in s:
        s = s.split()[0]
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_tx_dt(tx: Dict[str, Any]) -> Optional[datetime]:
    ht = tx.get("htime")
    if isinstance(ht, (int, float)) and ht > 100000:
        try:
            return datetime.fromtimestamp(float(ht))
        except (ValueError, OSError):
            return None
    if isinstance(ht, str) and ht.strip():
        try:
            dt = datetime.fromisoformat(ht.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            pass
    return None


class FinanceAnalyticsEngine:
    """夜间个人财务健康、消费习惯与开源节流分析引擎。"""

    def __init__(self, clock: Callable[[], datetime] = datetime.now):
        self._clock = clock

    def analyze(self, deep_pkg: Dict[str, Any]) -> Dict[str, Any]:
        now = self._clock()
        month_prefix = now.strftime("%Y-%m")
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        day_of_month = max(1, now.day)

        tx_all = deep_pkg.get("finance_transactions") or []
        tx_all = tx_all if isinstance(tx_all, list) else []
        overview = deep_pkg.get("finance_overview") or {}
        overview = overview if isinstance(overview, dict) else {}
        accounts = deep_pkg.get("finance_accounts") or []
        accounts = accounts if isinstance(accounts, list) else []
        hygiene_res = deep_pkg.get("finance_hygiene_scan") or {}

        # 识别需排除在日常消费趋势外的账户（如房贷账户）
        excluded_acc_ids = {
            int(a["id"])
            for a in accounts
            if isinstance(a, dict)
            and a.get("id") is not None
            and isinstance(a.get("meta"), dict)
            and a["meta"].get("exclude_from_consumption")
        }

        monthly_expense: Dict[str, float] = defaultdict(float)
        monthly_income: Dict[str, float] = defaultdict(float)
        tag_totals_90d: Dict[str, float] = defaultdict(float)
        mtd_tag_totals: Dict[str, float] = defaultdict(float)
        merchant_counter: Counter = Counter()
        merchant_spend: Dict[str, float] = defaultdict(float)

        mtd_expense = 0.0
        mtd_income = 0.0
        mtd_rigid = 0.0
        mtd_flexible = 0.0
        mtd_snack = 0.0
        mtd_snack_from_split = 0.0
        snack_90d = 0.0
        total_expense_90d = 0.0
        total_income_90d = 0.0
        late_night_spend_count = 0
        weekend_spend = 0.0
        weekday_spend = 0.0
        weekend_days: set[str] = set()
        weekday_days: set[str] = set()
        travel_txs: List[Dict[str, Any]] = []
        unsplit_mixed_count = 0

        for tx in tx_all:
            if not isinstance(tx, dict):
                continue
            if tx.get("exclude_from_stats"):
                continue
            desc = str(tx.get("description") or "").strip()
            if desc.lower() == "balance fix":
                continue
            dt = _parse_tx_dt(tx)
            if dt is None or dt.year <= 1971:
                continue

            from_id = int(tx.get("from_acc_id") or -1)
            to_id = int(tx.get("to_acc_id") or -1)
            if from_id in excluded_acc_ids or to_id in excluded_acc_ids:
                continue

            val = abs(_safe_float(tx.get("value")))
            if val <= 0:
                continue
            ym = dt.strftime("%Y-%m")
            d_str = dt.strftime("%Y-%m-%d")

            if from_id == -1 and to_id > 0:
                monthly_income[ym] += val
                total_income_90d += val
                if ym == month_prefix:
                    mtd_income += val
                continue

            if not (from_id > 0 and to_id == -1):
                continue  # transfer

            monthly_expense[ym] += val
            total_expense_90d += val
            if ym == month_prefix:
                mtd_expense += val

            if dt.weekday() >= 5:
                weekend_spend += val
                weekend_days.add(d_str)
            else:
                weekday_spend += val
                weekday_days.add(d_str)

            if dt.hour >= 22 or dt.hour < 4:
                late_night_spend_count += 1

            # 商户频率（归一化前 12 字）
            mkey = desc[:12] if desc else "未备注"
            merchant_counter[mkey] += 1
            merchant_spend[mkey] += val

            tags_raw = str(tx.get("tags") or "")
            tags_list = [x.strip() for x in tags_raw.split(",") if x.strip()]
            primary_tag = tags_list[0] if tags_list else "未分类"
            meta = tx.get("meta") if isinstance(tx.get("meta"), dict) else {}
            items = meta.get("items") if isinstance(meta.get("items"), list) else []

            is_rigid = primary_tag in _RIGID_TAGS or any(k in desc for k in _RIGID_KEYWORDS)
            if ym == month_prefix:
                if is_rigid:
                    mtd_rigid += val
                else:
                    mtd_flexible += val

            # 优先按 meta.items 统计真实标签与真实零食占比
            if items:
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    sub_amt = abs(_safe_float(it.get("amount")))
                    if sub_amt <= 0:
                        continue
                    sub_tag = str(it.get("tag") or "").strip() or primary_tag
                    tag_totals_90d[sub_tag] += sub_amt
                    if ym == month_prefix:
                        mtd_tag_totals[sub_tag] += sub_amt
                    if bool(it.get("is_snack")) or sub_tag == "零食":
                        snack_90d += sub_amt
                        if ym == month_prefix:
                            mtd_snack += sub_amt
                            mtd_snack_from_split += sub_amt
            else:
                tag_totals_90d[primary_tag] += val
                if ym == month_prefix:
                    mtd_tag_totals[primary_tag] += val
                if "零食" in tags_list:
                    snack_90d += val
                    if ym == month_prefix:
                        mtd_snack += val
                if any(kw in desc for kw in _MIXED_MERCHANTS) and val >= 50.0:
                    unsplit_mixed_count += 1

            if any(kw in desc for kw in _TRAVEL_KEYWORDS) and (now - dt).days <= 30:
                travel_txs.append({"id": tx.get("id"), "date": d_str, "desc": desc[:24], "value": round(val, 2)})

        # 若 overview 提供了更全的本月汇总（避免分页截断），优先采用
        if overview.get("mtd_expense") is not None and mtd_expense == 0:
            mtd_expense = _safe_float(overview.get("mtd_expense"))
            mtd_income = _safe_float(overview.get("mtd_income"))
            mtd_snack = _safe_float(overview.get("mtd_snack_total"))

        # 本月弹性支出日均与月底预测（刚性支出按已发生计，弹性支出按日均外推）
        daily_flex_pace = mtd_flexible / day_of_month if mtd_flexible > 0 else (mtd_expense / day_of_month)
        projected_eom_expense = round(mtd_rigid + daily_flex_pace * days_in_month, 2) if mtd_expense > 0 else 0.0
        savings_rate_90d = (
            round((total_income_90d - total_expense_90d) / total_income_90d * 100.0, 1)
            if total_income_90d > 0
            else None
        )
        snack_pct_mtd = round(mtd_snack / mtd_expense * 100.0, 1) if mtd_expense > 0 else 0.0
        snack_pct_90d = round(snack_90d / total_expense_90d * 100.0, 1) if total_expense_90d > 0 else 0.0

        # 周期性消费识别（近 90 天出现 >= 2 个不同月份的同名账单）
        recurring_candidates = [
            {"name": name, "count": cnt, "total": round(merchant_spend[name], 2), "avg": round(merchant_spend[name] / cnt, 2)}
            for name, cnt in merchant_counter.most_common(12)
            if cnt >= 3 and name != "未备注"
        ][:6]

        top_tags_mtd = [
            {"tag": k, "amount": round(v, 2)}
            for k, v in sorted(mtd_tag_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        silent_accounts = overview.get("silent_accounts") or []
        pending_hygiene = int(overview.get("pending_hygiene_count") or 0)
        tag_coverage_pct = float(overview.get("overall_tag_coverage_pct") or 100.0)
        auto_tagged_tonight = int(hygiene_res.get("auto_tagged_count") or 0)
        backfill_progress = deep_pkg.get("finance_backfill_progress") or {}
        backfill_active = isinstance(backfill_progress, dict) and backfill_progress.get("status") in (
            "in_progress",
            "paused_backpressure",
        )

        # 生成面向「开源节流与日常省心」的个性化洞察
        insights: List[str] = []
        if mtd_expense > 0:
            insights.append(
                f"本月({month_prefix})真实支出 ¥{mtd_expense:.0f}（弹性日均 ¥{daily_flex_pace:.0f}），按当前节奏预计月底总支出约 ¥{projected_eom_expense:.0f}"
            )
        if mtd_snack > 0:
            split_part = f"（含混合小票拆出 ¥{mtd_snack_from_split:.0f}）" if mtd_snack_from_split > 0 else ""
            insights.append(
                f"本月真实零食/饮品支出 ¥{mtd_snack:.0f}，占本月开销 {snack_pct_mtd}%{split_part}"
                + ("，偏高且直接影响减脂进度，建议改用无糖茶/轻负担替代" if snack_pct_mtd >= 15.0 else "")
            )
        if weekend_days and weekday_days:
            wkend_avg = weekend_spend / len(weekend_days)
            wkday_avg = weekday_spend / len(weekday_days)
            if wkend_avg > wkday_avg * 1.45 and wkend_avg >= 60:
                insights.append(
                    f"周末消费显著高于工作日（周末日均 ¥{wkend_avg:.0f} vs 工作日 ¥{wkday_avg:.0f}），是节流主要弹性空间"
                )
        if late_night_spend_count >= 5:
            insights.append(f"近 90 天有 {late_night_spend_count} 笔 22:00 后夜间消费，多与熬夜/嘴馋相关，早睡可同时省钱与减脂")
        if isinstance(backfill_progress, dict) and backfill_progress.get("last_month_processed"):
            done_m = len(backfill_progress.get("completed_months") or [])
            tot_m = backfill_progress.get("total_months_detected") or done_m
            insights.append(
                f"夜间历史慢迭代：已悄悄整理 {backfill_progress['last_month_processed']}（累计自动补标 {backfill_progress.get('cumulative_auto_tagged', 0)} 笔，进度 {done_m}/{tot_m} 月）"
            )
        elif auto_tagged_tonight > 0:
            insights.append(f"夜间已静默自动补标 {auto_tagged_tonight} 笔高频账单（支持在财务页一键撤销）")
        if silent_accounts:
            names = "、".join(f"{a['name']}({a['days_silent']}天)" for a in silent_accounts[:2])
            insights.append(f"常用账户较久未记账：{names}，方便时可核对一次余额")
        if travel_txs:
            insights.append(f"近 30 天检测到 {len(travel_txs)} 笔高铁/机票/酒店账单，可在财务页一键关联至 Rhythm 行程")

        # 提炼最多 1 条高价值发问建议（严控不轰炸：历史慢迭代静默推进，绝不催促用户补旧账）
        suggested_questions: List[Dict[str, str]] = []
        if silent_accounts:
            top_s = silent_accounts[0]
            suggested_questions.append(
                {
                    "topic": f"finance_reconcile_{top_s['account_id']}",
                    "question": f"「{top_s['name']}」已经 {top_s['days_silent']} 天没记账了，方便看一眼现在余额大概是多少吗？我帮你顺手核对对齐。",
                    "why": "定期轻量对账可避免遗漏积累成大额漂移",
                }
            )
        elif unsplit_mixed_count >= 2:
            suggested_questions.append(
                {
                    "topic": "finance_mixed_receipt_ocr",
                    "question": f"近期有 {unsplit_mixed_count} 笔超市/电商采购暂未拆分明细，下次买完直接发张小票或订单截图给我，我自动把日用品和零食拆开入账？",
                    "why": "拆分商超订单能让健康模块看见真实的零食占比",
                }
            )
        elif pending_hygiene >= 5 and not backfill_active:
            suggested_questions.append(
                {
                    "topic": "finance_hygiene_review",
                    "question": f"账单秘书整理出 {pending_hygiene} 条待确认的清理建议，不着急，哪天打开财务页顺手点几下即可。",
                    "why": "随手消化几条后，夜间慢迭代会自动继续往更早的历史月份推进",
                }
            )

        return {
            "snapshot_date": now.strftime("%Y-%m-%d"),
            "month": month_prefix,
            "transactions_analyzed": len(tx_all),
            "mtd_expense": round(mtd_expense, 2),
            "mtd_income": round(mtd_income, 2),
            "mtd_net": round(mtd_income - mtd_expense, 2),
            "mtd_rigid_expense": round(mtd_rigid, 2),
            "mtd_flexible_expense": round(mtd_flexible, 2),
            "daily_flexible_pace": round(daily_flex_pace, 2),
            "projected_eom_expense": projected_eom_expense,
            "mtd_snack_total": round(mtd_snack, 2),
            "mtd_snack_from_split": round(mtd_snack_from_split, 2),
            "mtd_snack_pct": snack_pct_mtd,
            "snack_90d_total": round(snack_90d, 2),
            "snack_90d_pct": snack_pct_90d,
            "savings_rate_90d": savings_rate_90d,
            "tag_coverage_pct": tag_coverage_pct,
            "pending_hygiene_count": pending_hygiene,
            "auto_tagged_tonight": auto_tagged_tonight,
            "top_tags_mtd": top_tags_mtd,
            "top_merchants": recurring_candidates,
            "silent_accounts": silent_accounts,
            "travel_txs_recent": travel_txs[:5],
            "unsplit_mixed_count": unsplit_mixed_count,
            "insights": insights,
            "suggested_questions": suggested_questions,
        }
