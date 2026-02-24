# -*- coding: utf-8 -*-
# @file main.py
# @brief The Main script entry
# @author sailing-innocent
# @date 2025-04-21
# @version 1.0
# ---------------------------------

import os
import sys
import argparse
import logging

logger = logging.getLogger(__name__)


def run_task_mode(args):
    """运行任务调度模式"""
    from sail_server.utils.env import read_env

    read_env("prod")

    from sail_server.db import g_db_func
    from task.db._dispatcher import DBTaskDispatcher

    logger.info(os.environ.get("POSTGRE_URI"))

    task_name = args.task
    task_args = args.args
    if task_args is None:
        task_args = []

    dispatcher = DBTaskDispatcher(g_db_func)
    try:
        result = dispatcher.dispatch(task_name, task_args)
        logger.info(f"Task {task_name} result: {result}")
    except Exception as e:
        logger.info(f"Error: {e}")


def run_import_text_mode():
    """运行文本导入模式"""
    from sail_server.cli.text_import import run_text_import_cli

    run_text_import_cli()


def main():
    """主入口函数"""
    # 检查是否是文本导入模式
    if "--import-text" in sys.argv:
        run_import_text_mode()
        return

    # 原有的任务调度模式

    parser = argparse.ArgumentParser(
        description="SailZen 主入口脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令模式:
  任务调度模式:
    uv run main.py --task <task_name> --args <arg1> <arg2> ...

  文本导入模式:
    uv run main.py --import-text <file.txt> [options]

文本导入示例:
  # 预览章节切分（不导入）
  uv run main.py --import-text novel.txt --preview

  # 使用自定义正则匹配
  uv run main.py --import-text novel.txt --pattern "^第\\d+章.*" --preview

  # 导入到开发环境
  uv run main.py --import-text novel.txt --title "小说标题" --author "作者" --dev

  # 导入到生产环境
  uv run main.py --import-text novel.txt --title "小说标题" --prod

  # 交互式测试正则表达式
  uv run main.py --import-text novel.txt --interactive

  更多选项请运行: uv run main.py --import-text --help
        """,
    )
    parser.add_argument("--task", type=str, help="Task to run")
    parser.add_argument("--args", type=str, nargs="+", help="Task arguments")
    parser.add_argument(
        "--prod", type=bool, help="use production mode", action="store_true"
    )
    args = parser.parse_args()
    from sail_server.utils.env import read_env

    read_env("prod" if args.prod else "dev")
    if args.task:
        run_task_mode(args)


if __name__ == "__main__":
    main()
