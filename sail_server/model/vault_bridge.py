# -*- coding: utf-8 -*-
# @file vault_bridge.py
# @brief SailTick <-> 本地 Dendron/Vault 双向轻量桥接业务逻辑
# @author sailing-innocent
# @date 2026-11-25
# @version 1.0
# ---------------------------------
"""Vault Journal Bridge — 笔记与结构化数据库的轻量双向桥接。

1. Notes -> Cloud Digest:
   接收本地 CLI 增量提取的 journal.daily.YYYY.MM.DD.md 摘要（按 content_hash 幂等去重），
   供 SailTick 在分析财务异常/差旅账单/情绪消费时获得日记上下文。
2. Cloud DB -> Vault Markdown:
   生成 Dendron 兼容 frontmatter 的月度财务与生活复盘 Markdown，
   供 CLI 写回 D:\\vault\\notes\\journal.finance.YYYY.MM.md。
"""

from __future__ import annotations

import calendar
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from sail_server.model.finance.hygiene import get_finance_overview_impl
from sail_server.model.finance.transaction import (
    _not_deprecated,
    _not_excluded_from_stats,
    _parse_money_decimal,
)
from sail_server.utils.finance_helpers import _acc_inv, _htime
from sailzen_orm.finance import Account, Transaction
from sailzen_orm.tick import VaultJournalDigest


def _digest_to_dict(d: VaultJournalDigest) -> Dict[str, Any]:
    return {
        "id": d.id,
        "note_date": d.note_date,
        "filename": d.filename or "",
        "title": d.title or d.note_date,
        "summary": d.summary or "",
        "excerpt": d.excerpt or "",
        "mood_hints": list(d.mood_hints) if isinstance(d.mood_hints, list) else [],
        "travel_hints": list(d.travel_hints) if isinstance(d.travel_hints, list) else [],
        "spend_context_hints": list(d.spend_context_hints) if isinstance(d.spend_context_hints, list) else [],
        "tags": list(d.tags) if isinstance(d.tags, list) else [],
        "content_hash": d.content_hash or "",
        "source_vault": d.source_vault or "local",
        "synced_at": d.synced_at.isoformat() if d.synced_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


def sync_vault_journals_impl(
    db: Session,
    items: List[Dict[str, Any]],
    source_vault: str = "local",
) -> Dict[str, Any]:
    """幂等批量 upsert 本地 Vault 日记摘要（按 content_hash 跳过未变更记录）。"""
    now = datetime.now()
    created = 0
    updated = 0
    skipped = 0

    for raw in items:
        if not isinstance(raw, dict):
            continue
        note_date = str(raw.get("note_date") or "").strip()[:10]
        if len(note_date) != 10:
            continue
        content_hash = str(raw.get("content_hash") or "").strip()[:64]
        existing = (
            db.query(VaultJournalDigest)
            .filter(VaultJournalDigest.note_date == note_date)
            .first()
        )
        if existing is not None:
            if content_hash and existing.content_hash == content_hash:
                skipped += 1
                continue
            existing.filename = str(raw.get("filename") or existing.filename or "")[:160]
            existing.title = str(raw.get("title") or note_date)[:160]
            existing.summary = str(raw.get("summary") or "")[:600]
            existing.excerpt = str(raw.get("excerpt") or "")[:1800]
            existing.mood_hints = list(raw.get("mood_hints") or [])[:12]
            existing.travel_hints = list(raw.get("travel_hints") or [])[:12]
            existing.spend_context_hints = list(raw.get("spend_context_hints") or [])[:12]
            existing.tags = list(raw.get("tags") or [])[:20]
            existing.content_hash = content_hash
            existing.source_vault = str(raw.get("source_vault") or source_vault)[:64]
            existing.synced_at = now
            existing.updated_at = now
            updated += 1
        else:
            row = VaultJournalDigest(
                note_date=note_date,
                filename=str(raw.get("filename") or "")[:160],
                title=str(raw.get("title") or note_date)[:160],
                summary=str(raw.get("summary") or "")[:600],
                excerpt=str(raw.get("excerpt") or "")[:1800],
                mood_hints=list(raw.get("mood_hints") or [])[:12],
                travel_hints=list(raw.get("travel_hints") or [])[:12],
                spend_context_hints=list(raw.get("spend_context_hints") or [])[:12],
                tags=list(raw.get("tags") or [])[:20],
                content_hash=content_hash,
                source_vault=str(raw.get("source_vault") or source_vault)[:64],
                synced_at=now,
                updated_at=now,
            )
            db.add(row)
            created += 1

    db.commit()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total_processed": created + updated + skipped,
    }


def list_vault_journals_impl(
    db: Session,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    """查询已同步的本地 Vault 日记轻量摘要（按日期倒序）。"""
    q = db.query(VaultJournalDigest)
    if start_date:
        q = q.filter(VaultJournalDigest.note_date >= str(start_date)[:10])
    if end_date:
        q = q.filter(VaultJournalDigest.note_date <= str(end_date)[:10])
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        q = q.filter(
            VaultJournalDigest.summary.like(kw) | VaultJournalDigest.excerpt.like(kw)
        )
    rows = (
        q.order_by(VaultJournalDigest.note_date.desc())
        .limit(max(1, min(120, int(limit))))
        .all()
    )
    return [_digest_to_dict(r) for r in rows]


def export_finance_review_markdown_impl(
    db: Session,
    month: Optional[str] = None,
) -> Dict[str, Any]:
    """生成 Dendron 兼容的月度财务复盘 Markdown（结合同月日记上下文），供写回 D:\\vault。"""
    now = datetime.now()
    if month and len(month) == 7:
        try:
            year, mon = int(month[:4]), int(month[5:7])
        except ValueError:
            year, mon = now.year, now.month
    else:
        year, mon = now.year, now.month

    month_str = f"{year:04d}-{mon:02d}"
    month_dot = f"{year:04d}.{mon:02d}"
    last_day = calendar.monthrange(year, mon)[1]
    start_dt = datetime(year, mon, 1, 0, 0, 0)
    end_dt = datetime(year, mon, last_day, 23, 59, 59)

    overview = get_finance_overview_impl(db, month=month_str)

    # 拉取该月已同步的日记上下文（按日期映射）
    journals = list_vault_journals_impl(
        db,
        start_date=start_dt.strftime("%Y-%m-%d"),
        end_date=end_dt.strftime("%Y-%m-%d"),
        limit=35,
    )
    journal_by_date = {j["note_date"]: j for j in journals}

    # 拉取该月 Top 10 真实支出（排除平账与房贷账户）
    excluded_acc_ids = {
        a.id
        for a in db.query(Account).all()
        if isinstance(a.meta, dict) and a.meta.get("exclude_from_consumption")
    }
    tx_rows = (
        db.query(Transaction)
        .filter(
            Transaction.state != 0,
            _not_deprecated(),
            _not_excluded_from_stats(),
            Transaction.htime >= _htime(start_dt.timestamp()),
            Transaction.htime <= _htime(end_dt.timestamp()),
        )
        .all()
    )
    expenses = []
    for t in tx_rows:
        from_id = _acc_inv(t.from_acc_id)
        to_id = _acc_inv(t.to_acc_id)
        if not (from_id > 0 and to_id == -1) or from_id in excluded_acc_ids:
            continue
        val = abs(_parse_money_decimal(t.value))
        d_str = t.htime.strftime("%Y-%m-%d") if t.htime else ""
        expenses.append(
            {
                "id": t.id,
                "date": d_str,
                "value": float(val),
                "description": (t.description or "未备注").strip(),
                "tags": (t.tags or "未分类").strip() or "未分类",
                "journal": journal_by_date.get(d_str),
            }
        )
    expenses.sort(key=lambda x: x["value"], reverse=True)
    top_expenses = expenses[:10]

    ts_ms = int(time.time() * 1000)
    filename = f"journal.finance.{month_dot}.md"
    lines: List[str] = [
        "---",
        f"id: sailtick-finance-{month_str}",
        f"title: '{month_str} 财务与生活开销复盘'",
        f"desc: '由 SailTick 日常开销秘书自动生成的 {month_str} 月度复盘（可自由批注）'",
        f"updated: {ts_ms}",
        f"created: {ts_ms}",
        "tags:",
        "  - finance",
        "  - sailtick",
        "---",
        "",
        f"# {month_str} 月度财务与生活开销复盘",
        "",
        f"> 生成时间：{now.strftime('%Y-%m-%d %H:%M')} · 数据源：SailZen 云端账单 + 本地 Vault 日记桥接（共关联 {len(journals)} 篇日记）",
        "",
        "## 1. 月度真实收支总览",
        "",
        f"- **本月真实支出**：¥{overview['mtd_expense']}（共 {overview['mtd_expense_count']} 笔，已自动隔离平账噪音）",
        f"- **本月真实收入**：¥{overview['mtd_income']}",
        f"- **月度净结余**：¥{overview['mtd_net']}",
        f"- **真实零食开销**：¥{overview['mtd_snack_total']}（占支出 {overview['mtd_snack_pct']}%，其中混合小票拆出 ¥{overview['mtd_snack_from_split']}）",
        f"- **账单标签健康度**：全历史覆盖率 {overview['overall_tag_coverage_pct']}% · 待审清理 {overview['pending_hygiene_count']} 条",
        "",
        "## 2. 品类消费结构（含混合小票穿透拆分）",
        "",
    ]

    by_tag = overview.get("mtd_by_tag") or []
    if by_tag:
        lines.append("| 标签 | 金额 | 占比 | 笔数 |")
        lines.append("|---|---:|---:|---:|")
        for row in by_tag:
            lines.append(f"| {row['tag']} | ¥{row['amount']} | {row['pct']}% | {row['count']} |")
    else:
        lines.append("- 本月暂无有效支出记录。")

    lines.extend(["", "## 3. Top 大额支出与日记背景关联", ""])
    if top_expenses:
        for e in top_expenses:
            j = e["journal"]
            j_link = f" · 日记 [[journal.daily.{e['date'].replace('-', '.')}]]" if e["date"] else ""
            j_note = f" — {j['summary'][:60]}" if j and j.get("summary") else ""
            lines.append(
                f"- `{e['date']}` **¥{e['value']:.2f}** [{e['tags']}] {e['description']}{j_link}{j_note}"
            )
    else:
        lines.append("- 本月暂无大额支出。")

    travel_days = [j for j in journals if j.get("travel_hints")]
    if travel_days:
        lines.extend(["", "## 4. 日记识别到的差旅/出行线索", ""])
        for j in travel_days[:10]:
            d_dot = j["note_date"].replace("-", ".")
            lines.append(
                f"- [[journal.daily.{d_dot}]] ({', '.join(j['travel_hints'][:4])})：{j['summary'][:80]}"
            )

    lines.extend(
        [
            "",
            "## 5. 个人批注与下月微调",
            "",
            "- （可在此随手写下本月感受或下月节流小目标）",
            "",
        ]
    )

    return {
        "month": month_str,
        "filename": filename,
        "journals_linked": len(journals),
        "overview": overview,
        "markdown": "\n".join(lines),
    }
