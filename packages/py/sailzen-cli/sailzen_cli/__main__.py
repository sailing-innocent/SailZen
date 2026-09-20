# -*- coding: utf-8 -*-
# @file __main__.py
# @brief SailZen CLI entry point (click)
# @author sailing-innocent
# @date 2026-09-20
# @version 2.0
# ---------------------------------

"""
SailZen CLI 入口

用法:
  sailzen --version
  sailzen finance pull --account 1 --server http://host:port
  sailzen notes list --vault ./notes
"""

from sailzen_cli.cli import main

if __name__ == "__main__":
    main()
