# -*- coding: utf-8 -*-
# @file finance_audit.py
# @brief 历史个人账单诊断与安全分级自治清理工具（默认只读 dry-run，绝不直连生产写库）
# @author sailing-innocent
# @date 2026-11-25
# @version 1.0
# ---------------------------------
"""历史账单诊断与分级自治清理脚本。

用法：
  # 仅在本地 dev 调试库只读体检（推荐先跑）：
  uv run python scripts/finance_audit.py --env dev --dry-run

  # 在本地 dev 调试库执行安全分级自治清理（自动隔离 balance fix + 高置信度补标，全部可一键撤销）：
  uv run python scripts/finance_audit.py --env dev --apply-safe --days 0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="SailZen Finance 2.0 历史账单体检与安全清理工具")
    parser.add_argument("--env", choices=["dev", "debug"], default="dev", help="目标本地环境（禁止直接写 prod）")
    parser.add_argument("--days", type=int, default=0, help="扫描最近 N 天（0 表示全历史）")
    parser.add_argument("--dry-run", action="store_true", help="只读诊断，不写入任何修改（默认行为）")
    parser.add_argument("--apply-safe", action="store_true", help="执行安全分级自治清理（全部记录可撤销审计日志）")
    parser.add_argument("--min-confidence", type=float, default=0.90, help="自动打标最低置信度（默认 0.90）")
    args = parser.parse_args()

    from sail.utils import read_env

    read_env(args.env)

    from sail_server.db import Database
    from sail_server.migration import run_migrations
    from sail_server.model.finance.hygiene import (
        get_finance_overview_impl,
        run_hygiene_scan_impl,
    )

    db_inst = Database.get_instance()
    run_migrations()
    session = db_inst.get_db_session()

    try:
        before = get_finance_overview_impl(session)
        print("=" * 64)
        print(f"SailZen Finance 2.0 账单健康体检 (env={args.env}, days={args.days or 'ALL'})")
        print("=" * 64)
        print(f"当前月份: {before['month']}")
        print(f"本月真实支出: ¥{before['mtd_expense']} | 真实零食: ¥{before['mtd_snack_total']} ({before['mtd_snack_pct']}%)")
        print(
            f"全历史有效支出: {before['overall_expense_count']} 笔 | "
            f"未打标: {before['overall_untagged_expense_count']} 笔 | "
            f"标签覆盖率: {before['overall_tag_coverage_pct']}%"
        )
        print(f"已隔离平账项: {before['excluded_adjustments_count']} 笔 | 待审清理: {before['pending_hygiene_count']} 条")
        if before["silent_accounts"]:
            print("沉默账户:", ", ".join(f"{a['name']}({a['days_silent']}天)" for a in before["silent_accounts"]))

        if not args.apply_safe:
            # dry-run 模式：commit=False 试跑并强制回滚，零副作用展示精确预估结果
            preview = run_hygiene_scan_impl(
                session,
                days=args.days or None,
                auto_apply_safe=True,
                min_auto_confidence=args.min_confidence,
                created_by="finance_audit_dry_run",
                commit=False,
            )
            after_preview = get_finance_overview_impl(session)
            session.rollback()
            print("\n[DRY-RUN 预演结果（已自动回滚，未改动数据库）]")
            print(json.dumps(preview, ensure_ascii=False, indent=2))
            print(
                f"\n预估清理后覆盖率: {before['overall_tag_coverage_pct']}% → {after_preview['overall_tag_coverage_pct']}% "
                f"| 剩余未打标: {after_preview['overall_untagged_expense_count']} 笔"
            )
            print("提示：确认无误后可运行 `--apply-safe` 正式执行安全分级清理（所有操作均支持一键撤销）。")
            return 0

        res = run_hygiene_scan_impl(
            session,
            days=args.days or None,
            auto_apply_safe=True,
            min_auto_confidence=args.min_confidence,
            created_by="finance_audit_cli",
        )
        after = get_finance_overview_impl(session)
        print("\n[APPLY-SAFE 执行结果]")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        print(
            f"\n覆盖率变化: {before['overall_tag_coverage_pct']}% → {after['overall_tag_coverage_pct']}% "
            f"| 剩余未打标: {after['overall_untagged_expense_count']} 笔 "
            f"| 待人工审阅: {after['pending_hygiene_count']} 条"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
