# -*- coding: utf-8 -*-
# @file __main__.py
# @brief SailZen CLI entry point
# @author sailing-innocent
# @date 2026-05-06
# @version 1.0
# ---------------------------------

"""
SailZen CLI 入口

用法:
  sailzen finance pull --account 1 --server http://host:port
  sailzen finance push transactions_1.csv --server http://host:port
  sailzen finance list-accounts --server http://host:port
"""

import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: sailzen <module> <command> [options]")
        print()
        print("Modules:")
        print("  finance   财务交易管理(拉取/修改/上传 transaction)")
        print("  health    健康数据管理(体重/运动/减重计划导出分析)")
        print("  notes     本地 Markdown 笔记库管理(git 托管)")
        print("  note      服务器 NoteItem / 创作笔记同步管理")
        print("  rhythm    生活/工作节奏综合优先级调节(统一事务/时间线/打卡/事业/复盘)")
        print()
        print("Examples:")
        print("  sailzen finance list-accounts --server http://localhost:8000")
        print("  sailzen finance pull --account 1 --server http://localhost:8000")
        print("  sailzen finance push transactions_1.csv --server http://localhost:8000")
        print("  sailzen health pull-weight --start 2025-01-01 --server http://localhost:8000")
        print("  sailzen health weight-analysis --start 2025-01-01 --end 2025-12-31")
        print("  sailzen notes list --vault ./notes")
        print("  sailzen notes get daily.2026-07-13 --vault ./notes")
        print("  sailzen note list --category character --server http://localhost:8000")
        print("  sailzen note pull --id 42 --workspace ./workspace")
        print("  sailzen note push notes/text/ --workspace ./workspace")
        sys.exit(1)

    module = sys.argv[1]

    if module == "finance":
        # 移除模块名，让 finance_client 的 argparse 处理剩余参数
        sys.argv.pop(1)
        from sailzen.cli.finance_client import main as finance_main

        finance_main()
    elif module == "health":
        sys.argv.pop(1)
        from sailzen.cli.health_client import main as health_main

        health_main()
    elif module == "notes":
        sys.argv.pop(1)
        from sailzen.cli.notes_client import main as notes_main

        notes_main()
    elif module == "note":
        sys.argv.pop(1)
        from sailzen.cli.note_client import main as note_main

        note_main()
    elif module == "rhythm":
        sys.argv.pop(1)
        from sailzen.cli.rhythm_client import main as rhythm_main

        rhythm_main()
    else:
        print(f"Unknown module: {module}", file=sys.stderr)
        print("Available modules: finance, health, notes, note, rhythm", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
