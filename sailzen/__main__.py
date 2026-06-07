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
        print("  finance   财务交易管理（拉取/修改/上传 transaction）")
        print("  health    健康数据管理（体重/运动/减重计划导出分析）")
        print()
        print("Examples:")
        print("  sailzen finance list-accounts --server http://localhost:8000")
        print("  sailzen finance pull --account 1 --server http://localhost:8000")
        print("  sailzen finance push transactions_1.csv --server http://localhost:8000")
        print("  sailzen health pull-weight --start 2025-01-01 --server http://localhost:8000")
        print("  sailzen health weight-analysis --start 2025-01-01 --end 2025-12-31")
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
    else:
        print(f"Unknown module: {module}", file=sys.stderr)
        print("Available modules: finance, health", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
