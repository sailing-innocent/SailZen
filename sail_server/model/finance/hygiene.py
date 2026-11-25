# -*- coding: utf-8 -*-
# @file hygiene.py
# @brief Finance 2.0 账单健康体检、分级自治清理队列、一键撤销与秘书总览
# @author sailing-innocent
# @date 2026-11-25
# @version 1.0
# ---------------------------------
"""Finance 2.0 Hygiene & Secretary Overview Engine.

实现「分级自治（Graded Autonomy）」账单治理闭环：
1. 自动扫描并分类历史 `balance fix` 伪时间戳平账项（标记 exclude_from_stats=True，不污染消费统计）；
2. 从历史已打标交易中学习精确商户/描述模式，高置信度（>= 0.90）自动打标并留存可一键撤销审计日志；
3. 识别混合采购（超市/盒马/京东/淘宝等）、疑似重复交易、差旅未关联日程项，放入待人工确认队列；
4. 支持批准（approve）、忽略（dismiss）与一键回滚（revert）；
5. 聚合输出财务秘书总览（overview）供 Web/Android/SailTick 使用。
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from sail_server.application.dto.finance import (
    AccountReconcileRequest,
    HygieneProposalResponse,
    TransactionData,
)
from sail_server.model.finance.account import (
    reconcile_account_balance_impl,
    update_account_balance_impl,
)
from sail_server.model.finance.transaction import (
    _not_deprecated,
    _parse_money_decimal,
    create_transaction_impl,
    delete_transaction_impl,
    get_breakdown_stats_impl,
    read_from_trans,
)
from sail_server.utils.finance_helpers import _acc_inv, _htime, _htime_inv
from sailzen_orm.finance import (
    Account,
    FinanceBalanceCheckpoint,
    FinanceHygieneProposal,
    FinanceTag,
    Transaction,
)

logger = logging.getLogger(__name__)

# 混合采购商户：一笔订单常同时包含日用品 + 零食，禁止盲目单标签自动覆盖，优先建议小票 OCR 拆分
MIXED_MERCHANT_KEYWORDS = (
    "超市", "盒马", "山姆", "叮咚", "永辉", "大润发", "奥乐齐", "全家",
    "罗森", "7-11", "711", "便利店", "沃尔玛", "京东", "淘宝", "天猫",
    "拼多多", "唯品会", "美团优选", "小象超市",
)

# 高精度无歧义关键词（兜底历史模式未覆盖的常见个人日常描述）
HIGH_PRECISION_KEYWORD_RULES: List[Tuple[Tuple[str, ...], str, float]] = [
    (("零食", "咖啡", "奶茶", "汉堡王", "肯德基", "麦当劳", "瑞幸", "星巴克", "霸王茶姬", "喜茶", "蜜雪", "甜品", "蛋糕", "冰淇淋", "炸鸡"), "零食", 0.92),
    (("地铁", "公交", "打车", "滴滴", "高德打车", "高铁", "动车", "火车", "12306", "车票", "机票", "航班", "停车", "共享单车", "哈啰"), "交通", 0.93),
    (("起点", "电影", "游戏", "steam", "ktv", "演出", "门票", "会员", "bilibili", "b站"), "娱乐休闲", 0.91),
    (("红包", "份子", "礼物", "请客", "聚餐"), "人际交往", 0.91),
    (("药房", "药店", "购药", "医院", "体检", "挂号", "看病", "诊所", "牙科"), "医药健康", 0.93),
    (("日用品", "燃气费", "电费", "水费", "话费", "宽带", "理发", "洗衣", "纸巾", "物业"), "日用消耗", 0.91),
    (("衣服", "外套", "裤子", "运动鞋", "球鞋", "羽绒服", "衬衫"), "衣物", 0.90),
    (("房租", "租金", "房贷", "月供"), "大宗收支", 0.92),
]

TRAVEL_KEYWORDS = (
    "高铁", "动车", "火车", "12306", "机票", "航班", "酒店", "宾馆", "民宿", "携程", "飞猪", "去哪儿",
)


def _norm_desc(desc: Optional[str]) -> str:
    return " ".join((desc or "").strip().lower().split())


def _is_legacy_fix_tx(t: Transaction) -> bool:
    desc = (t.description or "").strip().lower()
    if desc == "balance fix" or "balance fix" in desc:
        return True
    if t.htime is not None and t.htime.year <= 1971:
        return True
    return False


def _proposal_to_response(p: FinanceHygieneProposal) -> HygieneProposalResponse:
    return HygieneProposalResponse(
        id=p.id,
        proposal_type=p.proposal_type,
        autonomy_level=p.autonomy_level or "needs_review",
        status=p.status or "pending",
        target_tx_ids=[int(x) for x in (p.target_tx_ids or []) if str(x).isdigit()],
        confidence=float(p.confidence or 0.0),
        title=p.title or "",
        reason=p.reason or "",
        before_snapshot=dict(p.before_snapshot) if isinstance(p.before_snapshot, dict) else {},
        after_payload=dict(p.after_payload) if isinstance(p.after_payload, dict) else {},
        created_by=p.created_by or "sailtick",
        created_at=p.created_at,
        resolved_at=p.resolved_at,
    )


def _existing_pending_key_set(db: Session) -> set[tuple[str, tuple[int, ...]]]:
    rows = (
        db.query(FinanceHygieneProposal.proposal_type, FinanceHygieneProposal.target_tx_ids)
        .filter(FinanceHygieneProposal.status == "pending")
        .all()
    )
    out: set[tuple[str, tuple[int, ...]]] = set()
    for ptype, tids in rows:
        norm_ids = tuple(sorted(int(x) for x in (tids or []) if str(x).isdigit()))
        out.add((str(ptype), norm_ids))
    return out


def _build_historical_tag_consensus(db: Session) -> Dict[str, Tuple[str, float, int]]:
    """从全量已打标有效交易中学习 normalized_desc -> (best_tags, consistency_ratio, total_count)。"""
    rows = (
        db.query(Transaction.description, Transaction.tags)
        .filter(
            Transaction.state != 0,
            _not_deprecated(),
            Transaction.tags.isnot(None),
            Transaction.tags != "",
            Transaction.tags != ",",
        )
        .all()
    )
    counters: Dict[str, Counter] = defaultdict(Counter)
    for desc, tags in rows:
        nd = _norm_desc(desc)
        clean_tags = ",".join(x.strip() for x in (tags or "").split(",") if x.strip())
        if not nd or not clean_tags:
            continue
        counters[nd][clean_tags] += 1

    consensus: Dict[str, Tuple[str, float, int]] = {}
    for nd, cnt in counters.items():
        total = sum(cnt.values())
        top_tags, top_cnt = cnt.most_common(1)[0]
        ratio = top_cnt / total if total > 0 else 0.0
        consensus[nd] = (top_tags, ratio, total)
    return consensus


def _infer_tag_for_tx(
    desc: str,
    consensus: Dict[str, Tuple[str, float, int]],
    valid_vocab: set[str],
) -> Tuple[Optional[str], float, str, bool]:
    """返回 (suggested_tags, confidence, reason, is_mixed_merchant)。"""
    nd = _norm_desc(desc)
    if not nd:
        return None, 0.0, "描述为空", False

    is_mixed = any(kw in nd for kw in MIXED_MERCHANT_KEYWORDS)

    # 1. 历史精确一致模式（优先级最高，非混合商户可直接高置信度自动落库）
    if nd in consensus:
        top_tags, ratio, total = consensus[nd]
        if total >= 2 and ratio >= 0.85 and not is_mixed:
            conf = min(0.98, 0.90 + 0.01 * min(total, 8))
            return top_tags, round(conf, 3), f"命中历史精确模式（{total}次，一致率{int(ratio*100)}%）", False
        if total >= 1 and ratio >= 0.80:
            conf = 0.72 if is_mixed else (0.86 if total == 1 else 0.88)
            return (
                top_tags,
                conf,
                f"参考历史记录（{total}次）" + ("，属商超/电商混合采购建议拆分" if is_mixed else ""),
                is_mixed,
            )

    # 2. 混合采购商户：提示 OCR 小票拆分，不做盲目单标覆盖
    if is_mixed:
        return "日用消耗", 0.62, "疑似商超/电商混合采购（可能含日用品+零食），建议上传小票 OCR 拆分明细", True

    # 3. 高精度关键词兜底
    for kws, tag_name, conf in HIGH_PRECISION_KEYWORD_RULES:
        if valid_vocab and tag_name not in valid_vocab:
            continue
        for kw in kws:
            if kw in nd:
                return tag_name, conf, f"命中高精度关键词「{kw}」→ {tag_name}", False

    return None, 0.0, "未命中明确规则，待人工补充", False


def run_hygiene_scan_impl(
    db: Session,
    days: Optional[int] = 90,
    from_time: Optional[float] = None,
    to_time: Optional[float] = None,
    auto_apply_safe: bool = True,
    min_auto_confidence: float = 0.90,
    max_review_proposals: int = 10,
    include_legacy_fix: bool = True,
    created_by: str = "sailtick",
    commit: bool = True,
) -> Dict[str, Any]:
    """执行确定性账单健康体检与分级自治清理扫描（支持按精确时间区间与待审上限限流）。"""
    now = datetime.now()
    existing_pending = _existing_pending_key_set(db)
    review_budget = max(0, int(max_review_proposals))

    # 1. 拉取目标范围交易（优先 from_time/to_time 精确月份窗口；否则按 days，days=None/0 为全历史）
    q = db.query(Transaction).filter(Transaction.state != 0, _not_deprecated())
    if from_time is not None or to_time is not None:
        from sqlalchemy import and_, or_

        conds = []
        if from_time is not None:
            conds.append(Transaction.htime >= _htime(from_time))
        if to_time is not None:
            conds.append(Transaction.htime <= _htime(to_time))
        window_cond = and_(*conds) if len(conds) > 1 else conds[0]
        if include_legacy_fix:
            q = q.filter(or_(window_cond, Transaction.htime <= datetime(1972, 1, 1)))
        else:
            q = q.filter(window_cond)
    elif days and int(days) > 0:
        cutoff = now - timedelta(days=int(days))
        from sqlalchemy import or_

        if include_legacy_fix:
            q = q.filter(or_(Transaction.htime >= cutoff, Transaction.htime <= datetime(1972, 1, 1)))
        else:
            q = q.filter(Transaction.htime >= cutoff)
    txs = q.order_by(Transaction.htime.desc(), Transaction.id.desc()).all()

    consensus = _build_historical_tag_consensus(db)
    registered_tags = {
        t.name for t in db.query(FinanceTag).filter(FinanceTag.is_active == 1).all()
    }

    stats: Dict[str, Any] = {
        "scanned_transactions": len(txs),
        "legacy_fix_found": 0,
        "legacy_fix_auto_classified": 0,
        "auto_tagged_count": 0,
        "review_proposals_created": 0,
        "duplicates_detected": 0,
        "mixed_split_hints": 0,
        "travel_links_detected": 0,
        "created_proposal_ids": [],
    }

    # ── A. 历史 balance fix / 1970 平账项归类隔离 ────────────────────────
    legacy_fix_txs: List[Transaction] = []
    for t in txs:
        if _is_legacy_fix_tx(t) and (
            not bool(getattr(t, "exclude_from_stats", False))
            or getattr(t, "entry_kind", "normal") != "balance_adjust"
        ):
            legacy_fix_txs.append(t)

    stats["legacy_fix_found"] = len(legacy_fix_txs)
    if legacy_fix_txs:
        tx_ids = [t.id for t in legacy_fix_txs]
        before_map = {
            str(t.id): {
                "entry_kind": getattr(t, "entry_kind", "normal") or "normal",
                "exclude_from_stats": bool(getattr(t, "exclude_from_stats", False)),
            }
            for t in legacy_fix_txs
        }
        if auto_apply_safe:
            for t in legacy_fix_txs:
                t.entry_kind = "balance_adjust"
                t.exclude_from_stats = True
                t.mtime = now
            prop = FinanceHygieneProposal(
                proposal_type="legacy_fix_classify",
                autonomy_level="auto_applied",
                status="applied",
                target_tx_ids=tx_ids,
                confidence=1.0,
                title=f"自动隔离 {len(tx_ids)} 笔历史平账（balance fix）",
                reason="将历史遗留的余额强制重置记录标记为 balance_adjust 且不计入消费统计（余额不受影响），支持一键撤销。",
                before_snapshot={"items": before_map},
                after_payload={"entry_kind": "balance_adjust", "exclude_from_stats": True},
                created_by=created_by,
                created_at=now,
                resolved_at=now,
            )
            db.add(prop)
            db.flush()
            stats["legacy_fix_auto_classified"] = len(tx_ids)
            stats["created_proposal_ids"].append(prop.id)
        else:
            key = ("legacy_fix_classify", tuple(sorted(tx_ids)))
            if key not in existing_pending:
                prop = FinanceHygieneProposal(
                    proposal_type="legacy_fix_classify",
                    autonomy_level="needs_review",
                    status="pending",
                    target_tx_ids=tx_ids,
                    confidence=1.0,
                    title=f"建议隔离 {len(tx_ids)} 笔历史平账（balance fix）",
                    reason="这些记录为历史 balance fix 重置，排除出消费趋势统计可让月度图表更准确。",
                    before_snapshot={"items": before_map},
                    after_payload={"entry_kind": "balance_adjust", "exclude_from_stats": True},
                    created_by=created_by,
                    created_at=now,
                )
                db.add(prop)
                db.flush()
                existing_pending.add(key)
                stats["review_proposals_created"] += 1
                stats["created_proposal_ids"].append(prop.id)

    # ── B. 未打标支出智能归类（高置信度静默自动打标 + 低置信度/混合采购待审） ──
    auto_tag_changes: List[Tuple[Transaction, str, float, str]] = []
    review_tag_candidates: List[Tuple[Transaction, Optional[str], float, str, bool]] = []

    for t in txs:
        if bool(getattr(t, "exclude_from_stats", False)) or _is_legacy_fix_tx(t):
            continue
        from_id = _acc_inv(t.from_acc_id)
        to_id = _acc_inv(t.to_acc_id)
        if not (from_id > 0 and to_id == -1):
            continue  # 仅对支出自动打标（转账/工资跳过）
        existing_tags = ",".join(x.strip() for x in (t.tags or "").split(",") if x.strip())
        if existing_tags:
            continue

        suggested, conf, reason, is_mixed = _infer_tag_for_tx(
            t.description or "", consensus, registered_tags
        )
        if suggested and conf >= min_auto_confidence and not is_mixed:
            auto_tag_changes.append((t, suggested, conf, reason))
        elif is_mixed:
            review_tag_candidates.append((t, suggested, conf, reason, True))
        elif suggested:
            review_tag_candidates.append((t, suggested, conf, reason, False))

    if auto_tag_changes:
        if auto_apply_safe:
            # 按推断标签分组写入简洁的可撤销审计记录（避免一次产生几百条碎片记录）
            grouped: Dict[str, List[Tuple[Transaction, float, str]]] = defaultdict(list)
            for t, tag_s, conf, reason in auto_tag_changes:
                grouped[tag_s].append((t, conf, reason))

            for tag_s, items in grouped.items():
                before_map: Dict[str, str] = {}
                target_ids: List[int] = []
                avg_conf = sum(c for _, c, _ in items) / len(items)
                sample_descs = list(dict.fromkeys((t.description or "").strip() for t, _, _ in items))[:4]
                for t, conf, reason in items:
                    before_map[str(t.id)] = t.tags or ""
                    t.tags = tag_s
                    meta = dict(t.meta) if isinstance(t.meta, dict) else {}
                    meta["ai_audit"] = {
                        "source": created_by,
                        "action": "auto_tag",
                        "confidence": conf,
                        "reason": reason,
                        "at": now.isoformat(),
                    }
                    t.meta = meta
                    t.mtime = now
                    target_ids.append(t.id)

                prop = FinanceHygieneProposal(
                    proposal_type="auto_tag",
                    autonomy_level="auto_applied",
                    status="applied",
                    target_tx_ids=target_ids,
                    confidence=round(avg_conf, 3),
                    title=f"自动补全标签「{tag_s}」× {len(target_ids)} 笔",
                    reason=f"高置信度匹配样本：{'、'.join(sample_descs)}（支持一键全部撤销）",
                    before_snapshot={"tags_by_id": before_map},
                    after_payload={"tags": tag_s},
                    created_by=created_by,
                    created_at=now,
                    resolved_at=now,
                )
                db.add(prop)
                db.flush()
                stats["auto_tagged_count"] += len(target_ids)
                stats["created_proposal_ids"].append(prop.id)
        else:
            for t, tag_s, conf, reason in auto_tag_changes[:20]:
                key = ("auto_tag", (t.id,))
                if key in existing_pending:
                    continue
                prop = FinanceHygieneProposal(
                    proposal_type="auto_tag",
                    autonomy_level="needs_review",
                    status="pending",
                    target_tx_ids=[t.id],
                    confidence=conf,
                    title=f"建议打标 #{t.id}「{(t.description or '')[:20]}」→ {tag_s}",
                    reason=f"金额 ¥{t.value}；{reason}",
                    before_snapshot={"tags_by_id": {str(t.id): t.tags or ""}},
                    after_payload={"tags": tag_s},
                    created_by=created_by,
                    created_at=now,
                )
                db.add(prop)
                db.flush()
                existing_pending.add(key)
                stats["review_proposals_created"] += 1
                stats["created_proposal_ids"].append(prop.id)

    # 待审的混合采购 & 中置信度标签建议（严格受本次 review_budget 限流，防队列爆炸）
    review_added = 0
    for t, suggested, conf, reason, is_mixed in review_tag_candidates:
        if stats["review_proposals_created"] >= review_budget:
            break
        ptype = "mixed_split_hint" if is_mixed else "auto_tag"
        key = (ptype, (t.id,))
        if key in existing_pending:
            continue
        val_str = f"{abs(_parse_money_decimal(t.value)):.2f}"
        title = (
            f"混合采购建议拆分 #{t.id}「{(t.description or '')[:18]}」¥{val_str}"
            if is_mixed
            else f"待确认标签 #{t.id}「{(t.description or '')[:18]}」→ {suggested}"
        )
        prop = FinanceHygieneProposal(
            proposal_type=ptype,
            autonomy_level="needs_review",
            status="pending",
            target_tx_ids=[t.id],
            confidence=conf,
            title=title,
            reason=reason,
            before_snapshot={"tags_by_id": {str(t.id): t.tags or ""}},
            after_payload={"tags": suggested or "", "suggest_ocr": is_mixed},
            created_by=created_by,
            created_at=now,
        )
        db.add(prop)
        db.flush()
        existing_pending.add(key)
        review_added += 1
        stats["review_proposals_created"] += 1
        if is_mixed:
            stats["mixed_split_hints"] += 1
        stats["created_proposal_ids"].append(prop.id)

    # ── C. 疑似重复交易检测（同向同金额、同描述同日或 10 分钟内） ────────
    normal_expenses = [
        t
        for t in txs
        if not bool(getattr(t, "exclude_from_stats", False))
        and not _is_legacy_fix_tx(t)
        and _acc_inv(t.from_acc_id) > 0
        and _acc_inv(t.to_acc_id) == -1
        and t.htime is not None
    ]
    normal_expenses.sort(key=lambda x: (x.htime, x.id))
    dup_added = 0
    for i in range(1, len(normal_expenses)):
        if dup_added >= 8 or stats["review_proposals_created"] >= review_budget:
            break
        prev = normal_expenses[i - 1]
        cur = normal_expenses[i]
        v_prev = abs(_parse_money_decimal(prev.value))
        v_cur = abs(_parse_money_decimal(cur.value))
        if v_prev <= Decimal("0") or v_prev != v_cur:
            continue
        delta_sec = abs((cur.htime - prev.htime).total_seconds())
        same_desc = _norm_desc(prev.description) == _norm_desc(cur.description) and bool(_norm_desc(cur.description))
        same_day = prev.htime.date() == cur.htime.date()
        is_suspected_dup = (delta_sec <= 600 and prev.from_acc_id == cur.from_acc_id) or (
            same_day and same_desc and prev.from_acc_id == cur.from_acc_id and v_cur >= Decimal("10.00")
        )
        if not is_suspected_dup:
            continue
        pair = tuple(sorted([prev.id, cur.id]))
        key = ("duplicate_merge", pair)
        if key in existing_pending:
            continue
        stats["duplicates_detected"] += 1
        prop = FinanceHygieneProposal(
            proposal_type="duplicate_merge",
            autonomy_level="needs_review",
            status="pending",
            target_tx_ids=list(pair),
            confidence=0.82 if delta_sec <= 600 else 0.72,
            title=f"疑似重复记账：{(cur.description or '未备注')[:16]} ¥{v_cur:.2f} (#{prev.id} / #{cur.id})",
            reason=(
                f"{prev.htime.strftime('%Y-%m-%d %H:%M')} 与 {cur.htime.strftime('%Y-%m-%d %H:%M')} "
                f"在同一账户记录了两笔相同金额 ¥{v_cur:.2f}。批准后将安全删除后者 #{cur.id} 并自动回退余额（支持撤销恢复）。"
            ),
            before_snapshot={"delete_tx": read_from_trans(cur).model_dump(mode="json")},
            after_payload={"keep_tx_id": prev.id, "delete_tx_id": cur.id},
            created_by=created_by,
            created_at=now,
        )
        db.add(prop)
        db.flush()
        existing_pending.add(key)
        dup_added += 1
        stats["review_proposals_created"] += 1
        stats["created_proposal_ids"].append(prop.id)

    # ── D. 近 30 天差旅账单（高铁/机票/酒店）关联日程提示 ────────────────
    travel_cutoff = now - timedelta(days=30)
    travel_added = 0
    for t in normal_expenses:
        if travel_added >= 5 or stats["review_proposals_created"] >= review_budget:
            break
        if t.htime is None or t.htime < travel_cutoff:
            continue
        nd = _norm_desc(t.description)
        if not any(kw in nd for kw in TRAVEL_KEYWORDS):
            continue
        meta = t.meta if isinstance(t.meta, dict) else {}
        links = meta.get("links") if isinstance(meta.get("links"), dict) else {}
        if links.get("rhythm_occupancy_id") or links.get("rhythm_checked"):
            continue
        key = ("travel_rhythm_link", (t.id,))
        if key in existing_pending:
            continue
        val_str = f"{abs(_parse_money_decimal(t.value)):.2f}"
        d_str = t.htime.strftime("%Y-%m-%d")
        prop = FinanceHygieneProposal(
            proposal_type="travel_rhythm_link",
            autonomy_level="needs_review",
            status="pending",
            target_tx_ids=[t.id],
            confidence=0.80,
            title=f"差旅账单可关联日程：{d_str}「{(t.description or '')[:16]}」¥{val_str}",
            reason="检测到高铁/机票/酒店消费，批准后将标记行程关联并在 Rhythm 时间线记录差旅占位。",
            before_snapshot={"tx_id": t.id},
            after_payload={
                "tx_id": t.id,
                "travel_date": d_str,
                "label": f"出行：{(t.description or '差旅')[:24]}",
            },
            created_by=created_by,
            created_at=now,
        )
        db.add(prop)
        db.flush()
        existing_pending.add(key)
        travel_added += 1
        stats["travel_links_detected"] += 1
        stats["review_proposals_created"] += 1
        stats["created_proposal_ids"].append(prop.id)

    if commit:
        db.commit()
    else:
        db.flush()
    return stats


def list_hygiene_months_impl(db: Session) -> Dict[str, Any]:
    """按自然月统计历史账单覆盖率与待整理量（最新月→最早月），供 SailTick 夜间按月倒推慢迭代使用。"""
    rows = (
        db.query(
            Transaction.htime,
            Transaction.from_acc_id,
            Transaction.to_acc_id,
            Transaction.tags,
            Transaction.description,
            Transaction.exclude_from_stats,
            Transaction.entry_kind,
        )
        .filter(Transaction.state != 0, _not_deprecated())
        .all()
    )

    monthly: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "expenses": 0, "untagged_expenses": 0}
    )
    legacy_fix_unclassified = 0

    for htime_val, raw_from, raw_to, tags, desc, excl, entry_kind in rows:
        is_legacy = (
            (desc or "").strip().lower() == "balance fix"
            or "balance fix" in (desc or "").strip().lower()
            or (htime_val is not None and htime_val.year <= 1971)
        )
        if is_legacy:
            if not bool(excl) or (entry_kind or "normal") != "balance_adjust":
                legacy_fix_unclassified += 1
            continue
        if bool(excl) or htime_val is None or htime_val.year <= 1971:
            continue

        ym = htime_val.strftime("%Y-%m")
        monthly[ym]["total"] += 1
        from_id = _acc_inv(raw_from)
        to_id = _acc_inv(raw_to)
        if from_id > 0 and to_id == -1:
            monthly[ym]["expenses"] += 1
            if not (tags or "").strip().strip(","):
                monthly[ym]["untagged_expenses"] += 1

    months_list = [
        {
            "month": ym,
            "total": info["total"],
            "expenses": info["expenses"],
            "untagged_expenses": info["untagged_expenses"],
            "needs_work": info["untagged_expenses"] > 0,
        }
        for ym, info in sorted(monthly.items(), key=lambda x: x[0], reverse=True)
    ]

    return {
        "months": months_list,
        "total_months": len(months_list),
        "months_need_work": sum(1 for m in months_list if m["needs_work"]),
        "earliest_month": months_list[-1]["month"] if months_list else None,
        "latest_month": months_list[0]["month"] if months_list else None,
        "legacy_fix_unclassified": legacy_fix_unclassified,
    }


def create_hygiene_proposal_impl(
    db: Session,
    proposal_type: str,
    target_tx_ids: List[int],
    title: str,
    reason: str = "",
    confidence: float = 0.75,
    after_payload: Optional[Dict[str, Any]] = None,
    created_by: str = "sailtick_nightly_llm",
) -> Tuple[Optional[HygieneProposalResponse], bool]:
    """创建单条待审清理建议（严格去重 + 仅允许 needs_review，用于慢脑 LLM 温和补充长尾历史归类）。

    Returns:
        (proposal_response, created_new)
    """
    norm_ids = sorted(int(x) for x in (target_tx_ids or []) if str(x).isdigit())
    existing_pending = _existing_pending_key_set(db)
    key = (str(proposal_type), tuple(norm_ids))
    if norm_ids and key in existing_pending:
        return None, False

    before_map: Dict[str, str] = {}
    for tid in norm_ids:
        t = db.query(Transaction).filter(Transaction.id == tid).first()
        if t is not None:
            before_map[str(tid)] = t.tags or ""

    prop = FinanceHygieneProposal(
        proposal_type=str(proposal_type),
        autonomy_level="needs_review",
        status="pending",
        target_tx_ids=norm_ids,
        confidence=max(0.0, min(1.0, float(confidence))),
        title=str(title).strip()[:160],
        reason=str(reason or "").strip()[:500],
        before_snapshot={"tags_by_id": before_map} if before_map else {},
        after_payload=dict(after_payload or {}),
        created_by=created_by or "sailtick_nightly_llm",
        created_at=datetime.now(),
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return _proposal_to_response(prop), True


def list_hygiene_proposals_impl(
    db: Session,
    status: Optional[str] = None,
    autonomy_level: Optional[str] = None,
    proposal_type: Optional[str] = None,
    limit: int = 50,
) -> List[HygieneProposalResponse]:
    q = db.query(FinanceHygieneProposal)
    if status:
        q = q.filter(FinanceHygieneProposal.status == status)
    if autonomy_level:
        q = q.filter(FinanceHygieneProposal.autonomy_level == autonomy_level)
    if proposal_type:
        q = q.filter(FinanceHygieneProposal.proposal_type == proposal_type)
    rows = (
        q.order_by(FinanceHygieneProposal.created_at.desc(), FinanceHygieneProposal.id.desc())
        .limit(max(1, min(200, int(limit))))
        .all()
    )
    return [_proposal_to_response(p) for p in rows]


def approve_hygiene_proposal_impl(db: Session, proposal_id: int) -> Optional[HygieneProposalResponse]:
    """人工批准待审建议并执行落库（保留 before_snapshot 以支持撤销）。"""
    prop = db.query(FinanceHygieneProposal).filter(FinanceHygieneProposal.id == proposal_id).first()
    if prop is None:
        return None
    if prop.status != "pending":
        return _proposal_to_response(prop)

    now = datetime.now()
    ptype = prop.proposal_type
    payload = dict(prop.after_payload) if isinstance(prop.after_payload, dict) else {}
    tx_ids = [int(x) for x in (prop.target_tx_ids or []) if str(x).isdigit()]

    if ptype in ("auto_tag", "mixed_split_hint"):
        new_tags = str(payload.get("tags") or "").strip()
        if new_tags and tx_ids:
            before_map: Dict[str, str] = {}
            for tid in tx_ids:
                t = db.query(Transaction).filter(Transaction.id == tid).first()
                if t is not None:
                    before_map[str(tid)] = t.tags or ""
                    t.tags = new_tags
                    t.mtime = now
            prop.before_snapshot = {"tags_by_id": before_map}

    elif ptype == "legacy_fix_classify":
        before_map = {}
        for tid in tx_ids:
            t = db.query(Transaction).filter(Transaction.id == tid).first()
            if t is not None:
                before_map[str(tid)] = {
                    "entry_kind": getattr(t, "entry_kind", "normal") or "normal",
                    "exclude_from_stats": bool(getattr(t, "exclude_from_stats", False)),
                }
                t.entry_kind = "balance_adjust"
                t.exclude_from_stats = True
                t.mtime = now
        prop.before_snapshot = {"items": before_map}

    elif ptype == "duplicate_merge":
        del_id = payload.get("delete_tx_id")
        if del_id is not None:
            t = db.query(Transaction).filter(Transaction.id == int(del_id)).first()
            if t is not None:
                prop.before_snapshot = {"delete_tx": read_from_trans(t).model_dump(mode="json")}
                delete_transaction_impl(db, int(del_id))

    elif ptype == "large_drift":
        acc_id = payload.get("account_id")
        actual_bal = payload.get("actual_balance")
        if acc_id is not None and actual_bal is not None:
            rec = reconcile_account_balance_impl(
                db,
                AccountReconcileRequest(
                    account_id=int(acc_id),
                    actual_balance=str(actual_bal),
                    force_adjust=True,
                    note=f"批准平账提案 #{prop.id}",
                    source="hygiene_approve",
                ),
            )
            if rec and rec.get("checkpoint") and rec["checkpoint"].adjustment_tx_id:
                payload["adjustment_tx_id"] = rec["checkpoint"].adjustment_tx_id
                prop.after_payload = payload

    elif ptype == "travel_rhythm_link":
        tx_id = payload.get("tx_id") or (tx_ids[0] if tx_ids else None)
        if tx_id is not None:
            t = db.query(Transaction).filter(Transaction.id == int(tx_id)).first()
            if t is not None:
                meta = dict(t.meta) if isinstance(t.meta, dict) else {}
                links = dict(meta.get("links") or {})
                # 尝试在 Rhythm 中建立 travel 刚性占位（容错，不阻塞主事务）
                occ_id = None
                try:
                    from sail_server.model.rhythm import create_occupancy_impl
                    from sail_server.application.dto.rhythm import OccupancyCreateRequest

                    occ = create_occupancy_impl(
                        db,
                        OccupancyCreateRequest(
                            date=str(payload.get("travel_date") or now.strftime("%Y-%m-%d")),
                            occupancy_type="travel",
                            whole_day=True,
                            label=str(payload.get("label") or f"出行：{(t.description or '')[:20]}"),
                            note=f"来自财务账单 #{t.id} (¥{t.value})",
                        ),
                    )
                    occ_id = occ.get("id") if isinstance(occ, dict) else getattr(occ, "id", None)
                except Exception as exc:
                    logger.warning("travel_rhythm_link create_occupancy skipped: %s", exc)
                links["rhythm_checked"] = True
                if occ_id is not None:
                    links["rhythm_occupancy_id"] = occ_id
                meta["links"] = links
                t.meta = meta
                t.mtime = now

    prop.status = "applied"
    prop.resolved_at = now
    db.commit()
    db.refresh(prop)
    return _proposal_to_response(prop)


def dismiss_hygiene_proposal_impl(db: Session, proposal_id: int) -> Optional[HygieneProposalResponse]:
    prop = db.query(FinanceHygieneProposal).filter(FinanceHygieneProposal.id == proposal_id).first()
    if prop is None:
        return None
    if prop.status == "pending":
        prop.status = "dismissed"
        prop.resolved_at = datetime.now()
        db.commit()
        db.refresh(prop)
    return _proposal_to_response(prop)


def revert_hygiene_proposal_impl(db: Session, proposal_id: int) -> Optional[HygieneProposalResponse]:
    """一键撤销已执行的（含 AI 自动托管）账单治理动作。"""
    prop = db.query(FinanceHygieneProposal).filter(FinanceHygieneProposal.id == proposal_id).first()
    if prop is None:
        return None
    if prop.status != "applied":
        return _proposal_to_response(prop)

    now = datetime.now()
    ptype = prop.proposal_type
    snap = dict(prop.before_snapshot) if isinstance(prop.before_snapshot, dict) else {}

    if ptype in ("auto_tag", "mixed_split_hint"):
        tags_by_id = snap.get("tags_by_id") if isinstance(snap.get("tags_by_id"), dict) else {}
        for tid_str, old_tags in tags_by_id.items():
            t = db.query(Transaction).filter(Transaction.id == int(tid_str)).first()
            if t is not None:
                t.tags = str(old_tags or "")
                t.mtime = now

    elif ptype == "legacy_fix_classify":
        items = snap.get("items") if isinstance(snap.get("items"), dict) else {}
        for tid_str, old_vals in items.items():
            t = db.query(Transaction).filter(Transaction.id == int(tid_str)).first()
            if t is not None and isinstance(old_vals, dict):
                t.entry_kind = str(old_vals.get("entry_kind") or "normal")
                t.exclude_from_stats = bool(old_vals.get("exclude_from_stats", False))
                t.mtime = now

    elif ptype == "micro_adjust_audit":
        created_tx_id = snap.get("created_tx_id")
        if created_tx_id is not None:
            delete_transaction_impl(db, int(created_tx_id))

    elif ptype == "large_drift":
        adj_tx_id = (prop.after_payload or {}).get("adjustment_tx_id")
        if adj_tx_id is not None:
            delete_transaction_impl(db, int(adj_tx_id))

    elif ptype == "duplicate_merge":
        del_snap = snap.get("delete_tx")
        if isinstance(del_snap, dict):
            restored = create_transaction_impl(
                db,
                TransactionData(
                    from_acc_id=int(del_snap.get("from_acc_id", -1)),
                    to_acc_id=int(del_snap.get("to_acc_id", -1)),
                    value=str(del_snap.get("value", "0.0")),
                    description=str(del_snap.get("description", "")),
                    tags=str(del_snap.get("tags", "")),
                    budget_id=del_snap.get("budget_id"),
                    entry_kind=str(del_snap.get("entry_kind", "normal")),
                    exclude_from_stats=bool(del_snap.get("exclude_from_stats", False)),
                    meta=del_snap.get("meta") if isinstance(del_snap.get("meta"), dict) else {},
                    htime=del_snap.get("htime"),
                ),
            )
            for acc_id in (restored.from_acc_id, restored.to_acc_id):
                if acc_id and acc_id > 0:
                    update_account_balance_impl(db, acc_id)

    prop.status = "reverted"
    prop.resolved_at = now
    db.commit()
    db.refresh(prop)
    return _proposal_to_response(prop)


def get_finance_overview_impl(db: Session, month: Optional[str] = None) -> Dict[str, Any]:
    """聚合财务秘书核心总览（真实收支、真实零食拆分、标签覆盖率、清理队列、沉默账户）。"""
    now = datetime.now()
    if month and len(month) == 7:
        try:
            year, mon = int(month[:4]), int(month[5:7])
            m_start = datetime(year, mon, 1)
            m_end = (
                datetime(year + 1, 1, 1) - timedelta(seconds=1)
                if mon == 12
                else datetime(year, mon + 1, 1) - timedelta(seconds=1)
            )
        except ValueError:
            m_start = datetime(now.year, now.month, 1)
            m_end = now
    else:
        m_start = datetime(now.year, now.month, 1)
        m_end = now
    month_label = m_start.strftime("%Y-%m")

    # 识别配置为排除消费统计的账户（如房贷账户）
    accounts = db.query(Account).order_by(Account.id.asc()).all()
    excluded_acc_ids = [
        a.id
        for a in accounts
        if isinstance(a.meta, dict) and a.meta.get("exclude_from_consumption")
    ]

    mtd_breakdown = get_breakdown_stats_impl(
        db,
        from_time=m_start.timestamp(),
        to_time=m_end.timestamp(),
        include_excluded=False,
        exclude_account_ids=excluded_acc_ids,
    )

    # 今日支出快速统计
    today_start = datetime(now.year, now.month, now.day)
    today_breakdown = get_breakdown_stats_impl(
        db,
        from_time=today_start.timestamp(),
        to_time=now.timestamp(),
        include_excluded=False,
        exclude_account_ids=excluded_acc_ids,
    )

    # 全库标签覆盖率 & 隔离统计数
    valid_q = db.query(Transaction).filter(Transaction.state != 0, _not_deprecated())
    all_txs = valid_q.all()
    real_expense_total = 0
    real_expense_tagged = 0
    excluded_count = 0
    last_tx_by_acc: Dict[int, datetime] = {}

    for t in all_txs:
        is_excl = bool(getattr(t, "exclude_from_stats", False)) or _is_legacy_fix_tx(t)
        if is_excl:
            excluded_count += 1
            continue
        from_id = _acc_inv(t.from_acc_id)
        to_id = _acc_inv(t.to_acc_id)
        if t.htime is not None:
            for aid in (from_id, to_id):
                if aid > 0 and (aid not in last_tx_by_acc or t.htime > last_tx_by_acc[aid]):
                    last_tx_by_acc[aid] = t.htime
        if from_id > 0 and to_id == -1:
            real_expense_total += 1
            if (t.tags or "").strip().strip(","):
                real_expense_tagged += 1

    tag_coverage_pct = (
        round(real_expense_tagged / real_expense_total * 100.0, 1)
        if real_expense_total > 0
        else 100.0
    )

    # 待审与自动托管计数
    pending_proposals = (
        db.query(FinanceHygieneProposal)
        .filter(FinanceHygieneProposal.status == "pending")
        .count()
    )
    auto_applied_proposals = (
        db.query(FinanceHygieneProposal)
        .filter(
            FinanceHygieneProposal.autonomy_level == "auto_applied",
            FinanceHygieneProposal.status == "applied",
        )
        .count()
    )

    # 账户健康与沉默提醒（活跃账户且常用余额不为 0，超过 5 天未记账）
    account_health = []
    silent_accounts = []
    for a in accounts:
        if a.state != 0:
            continue
        meta = dict(a.meta) if isinstance(a.meta, dict) else {}
        last_dt = last_tx_by_acc.get(a.id)
        days_silent = (now - last_dt).days if last_dt else None
        bal_dec = _parse_money_decimal(a.balance)
        is_daily = any(k in (a.name or "") for k in ("微信", "支付宝", "余额宝", "招行", "中行"))
        if is_daily and days_silent is not None and days_silent >= 5:
            silent_accounts.append(
                {
                    "account_id": a.id,
                    "name": a.name,
                    "days_silent": days_silent,
                    "last_tx_date": last_dt.strftime("%Y-%m-%d") if last_dt else None,
                }
            )
        account_health.append(
            {
                "id": a.id,
                "name": a.name,
                "balance": f"{bal_dec:.2f}",
                "days_since_last_tx": days_silent,
                "last_reconciled_at": meta.get("last_reconciled_at"),
                "last_drift": meta.get("last_drift"),
                "exclude_from_consumption": bool(meta.get("exclude_from_consumption", False)),
            }
        )

    return {
        "month": month_label,
        "today_expense": today_breakdown["total_expense"],
        "today_count": today_breakdown["expense_count"],
        "mtd_expense": mtd_breakdown["total_expense"],
        "mtd_income": mtd_breakdown["total_income"],
        "mtd_net": mtd_breakdown["net_cashflow"],
        "mtd_expense_count": mtd_breakdown["expense_count"],
        "mtd_snack_total": mtd_breakdown["snack_total"],
        "mtd_snack_from_split": mtd_breakdown["snack_from_split"],
        "mtd_snack_pct": mtd_breakdown["snack_pct_of_expense"],
        "mtd_split_tx_count": mtd_breakdown["split_tx_count"],
        "mtd_untagged_count": mtd_breakdown["untagged_count"],
        "mtd_by_tag": mtd_breakdown["by_tag"][:8],
        "overall_tag_coverage_pct": tag_coverage_pct,
        "overall_expense_count": real_expense_total,
        "overall_untagged_expense_count": real_expense_total - real_expense_tagged,
        "excluded_adjustments_count": excluded_count,
        "pending_hygiene_count": pending_proposals,
        "auto_applied_hygiene_count": auto_applied_proposals,
        "silent_accounts": silent_accounts,
        "account_health": account_health,
    }
