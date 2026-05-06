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
        print()
        print("Examples:")
        print("  sailzen finance list-accounts --server http://localhost:8000")
        print("  sailzen finance pull --account 1 --server http://localhost:8000")
        print("  sailzen finance push transactions_1.csv --server http://localhost:8000")
        sys.exit(1)

    module = sys.argv[1]

    if module == "finance":
        # 移除模块名，让 finance_client 的 argparse 处理剩余参数
        sys.argv.pop(1)
        from sailzen.cli.finance_client import main as finance_main

        finance_main()
    else:
        print(f"Unknown module: {module}", file=sys.stderr)
        print("Available modules: finance", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
