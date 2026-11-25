# -*- coding: utf-8 -*-
# @file test_vault_bridge.py
# @brief Phase 2 Vault Journal Bridge（日记摘要同步、月报导出、SailTick 差旅联动）单元测试
# @author sailing-innocent
# @date 2026-11-25
# @version 1.0
# ---------------------------------

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sail_server.application.dto.finance import TransactionData
from sail_server.model.finance.transaction import create_transaction_impl
from sail_server.model.vault_bridge import (
    export_finance_review_markdown_impl,
    list_vault_journals_impl,
    sync_vault_journals_impl,
)
from sailtick.finance_analytics import FinanceAnalyticsEngine
from sailzen_orm import ORMBase
from sailzen_orm.finance import Account

# 确保可直接导入 packages/py/sailzen-cli
_CLI_PKG = Path(__file__).resolve().parents[2] / "packages" / "py" / "sailzen-cli"
if str(_CLI_PKG) not in sys.path:
    sys.path.insert(0, str(_CLI_PKG))

from sailzen_cli.commands.vault_client import (  # noqa: E402
    extract_journal_digest_from_file,
    scan_local_vault_journals,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    ORMBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        acc = Account(name="微信", description="常用", balance="2000.00", state=0)
        db.add(acc)
        db.commit()
        db.refresh(acc)
        yield db, acc
    finally:
        db.close()
        engine.dispose()


def test_extract_journal_digest_skips_empty_dendron_skeleton(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()

    empty_file = notes / "journal.daily.2026.11.20.md"
    empty_file.write_text(
        """---
id: abc123
title: '2026-11-20'
desc: ''
updated: 1700000000000
created: 1700000000000
traitIds:
  - journalNote
---
- [[routines.daily]]
- [[routines.weekday.friday]]

## Plan

## Record

## Summary
""",
        encoding="utf-8",
    )
    assert extract_journal_digest_from_file(empty_file) is None

    real_file = notes / "journal.daily.2026.11.21.md"
    real_file.write_text(
        """---
id: def456
title: '2026-11-21 上海出差'
tags:
  - journalNote
  - travel
---
- [[routines.daily]]

## Record
- 早上坐高铁去上海出差，晚上和同事聚餐，有点累但很顺利。
- 顺路去超市采购了日用品和一点零食。
""",
        encoding="utf-8",
    )
    digest = extract_journal_digest_from_file(real_file)
    assert digest is not None
    assert digest["note_date"] == "2026-11-21"
    assert digest["title"] == "2026-11-21 上海出差"
    assert "高铁" in digest["travel_hints"]
    assert "出差" in digest["travel_hints"]
    assert "超市" in digest["spend_context_hints"]
    assert "累" in digest["mood_hints"]
    assert "travel" in digest["tags"]
    assert "journalNote" not in digest["tags"]
    assert len(digest["content_hash"]) == 32

    # 未来日期应被 scan_local_vault_journals 忽略
    future_file = notes / "journal.daily.2026.12.31.md"
    future_file.write_text("## Record\n未来计划内容测试", encoding="utf-8")

    scanned = scan_local_vault_journals(tmp_path, days=15, today=datetime(2026, 11, 25))
    assert [d["note_date"] for d in scanned] == ["2026-11-21"]


def test_vault_sync_idempotency_and_finance_review_export(db_session):
    db, acc = db_session

    items = [
        {
            "note_date": "2026-11-21",
            "filename": "journal.daily.2026.11.21.md",
            "title": "2026-11-21 出差日",
            "summary": "高铁前往上海出差，住陆家嘴酒店",
            "excerpt": "高铁前往上海出差，住陆家嘴酒店，晚饭聚餐",
            "mood_hints": ["顺利"],
            "travel_hints": ["高铁", "出差", "酒店"],
            "spend_context_hints": ["聚餐"],
            "tags": ["travel"],
            "content_hash": "hash_v1",
        }
    ]

    r1 = sync_vault_journals_impl(db, items, source_vault="myvault")
    assert r1 == {"created": 1, "updated": 0, "skipped": 0, "total_processed": 1}

    # 同样 content_hash 幂等跳过
    r2 = sync_vault_journals_impl(db, items, source_vault="myvault")
    assert r2 == {"created": 0, "updated": 0, "skipped": 1, "total_processed": 1}

    # 内容变更后更新
    items_v2 = [{**items[0], "summary": "高铁前往上海出差（已补充发票）", "content_hash": "hash_v2"}]
    r3 = sync_vault_journals_impl(db, items_v2, source_vault="myvault")
    assert r3 == {"created": 0, "updated": 1, "skipped": 0, "total_processed": 1}

    listed = list_vault_journals_impl(db, start_date="2026-11-01", end_date="2026-11-30", keyword="发票")
    assert len(listed) == 1
    assert listed[0]["content_hash"] == "hash_v2"

    # 构造一笔差旅支出 + 一笔小票拆分支出 + 一笔不计入统计的小额平账
    ts_travel = datetime(2026, 11, 21, 9, 30).timestamp()
    create_transaction_impl(
        db,
        TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="553.00",
            description="高铁订票 北京-上海",
            tags="出行",
            htime=ts_travel,
        ),
    )
    ts_mart = datetime(2026, 11, 22, 18, 0).timestamp()
    create_transaction_impl(
        db,
        TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="100.00",
            description="盒马超市采购",
            tags="日用,零食",
            meta={
                "items": [
                    {"name": "洗衣液", "amount": "70.00", "tag": "日用", "is_snack": False},
                    {"name": "薯片", "amount": "30.00", "tag": "零食", "is_snack": True},
                ]
            },
            htime=ts_mart,
        ),
    )
    create_transaction_impl(
        db,
        TransactionData(
            from_acc_id=acc.id,
            to_acc_id=-1,
            value="12.00",
            description="小额无感平账",
            entry_kind="micro_adjust",
            exclude_from_stats=True,
            htime=ts_mart,
        ),
    )

    exported = export_finance_review_markdown_impl(db, month="2026-11")
    assert exported["month"] == "2026-11"
    assert exported["filename"] == "journal.finance.2026.11.md"
    assert exported["journals_linked"] == 1
    md = exported["markdown"]
    assert "id: sailtick-finance-2026-11" in md
    assert "¥653.00" in md  # 553 + 100，不包含 12 元平账
    assert "¥30.00" in md  # 混合小票拆出的真实零食
    assert "[[journal.daily.2026.11.21]]" in md
    assert "高铁前往上海出差" in md


def test_finance_analytics_correlates_travel_tx_with_vault_journal():
    engine = FinanceAnalyticsEngine()
    now_ts = datetime.now().timestamp()
    today_str = datetime.now().strftime("%Y-%m-%d")
    report = engine.analyze(
        {
            "finance_overview": {
                "mtd_expense": "800.00",
                "mtd_snack_total": "40.00",
                "overall_tag_coverage_pct": 95.0,
            },
            "finance_transactions": [
                {
                    "id": 101,
                    "from_acc_id": 1,
                    "to_acc_id": -1,
                    "value": "420.00",
                    "description": "高铁车票 杭州东",
                    "tags": "出行",
                    "htime": now_ts,
                    "exclude_from_stats": False,
                    "meta": {},
                }
            ],
            "finance_accounts": [{"id": 1, "name": "微信", "balance": "1000.00", "state": 0}],
            "vault_journals": [
                {
                    "note_date": today_str,
                    "summary": "坐高铁去杭州拜访朋友",
                    "travel_hints": ["高铁"],
                }
            ],
        }
    )
    assert len(report["travel_txs_recent"]) == 1
    travel_item = report["travel_txs_recent"][0]
    assert travel_item["journal_summary"] == "坐高铁去杭州拜访朋友"
    assert any("日记提及：坐高铁去杭州拜访朋友" in ins for ins in report["insights"])
