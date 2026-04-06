# -*- coding: utf-8 -*-
# @file text_import.py
# @brief CLI Tool for Bulk Text Import
# @author sailing-innocent
# @date 2025-01-30
# @version 1.0
# ---------------------------------
#
# 批量导入大文本文件（如小说）的命令行工具
# 支持:
#   - 解析数千章的 .txt 文件
#   - 自定义章节正则匹配
#   - 交互式预览切分结果
#   - --dev/--prod 环境切换
#

import os
import re
import sys
import argparse
from typing import List, Tuple, Optional
from pathlib import Path


# 颜色输出支持
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def colorize(text: str, color: str) -> str:
    """为文本添加颜色（仅在支持 ANSI 的终端生效）"""
    if sys.platform == "win32":
        # Windows 需要启用 ANSI 转义序列
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            return text
    return f"{color}{text}{Colors.ENDC}"


# 默认章节模式（与 model/text.py 保持一致）
DEFAULT_CHAPTER_PATTERNS = [
    r"^第[一二三四五六七八九十百千万零〇\d]+章[^\n]*",  # 中文章节: 第一章、第1章
    r"^第[一二三四五六七八九十百千万零〇\d]+节[^\n]*",  # 中文节: 第一节
    r"^Chapter\s+\d+[^\n]*",  # 英文章节: Chapter 1
    r"^CHAPTER\s+\d+[^\n]*",  # 大写英文章节
    r"^\d+\.\s+[^\n]+",  # 数字章节: 1. Title
    r"^【[^\】]+】",  # 【章节标题】
]


def parse_chapters_preview(
    content: str, pattern: Optional[str] = None
) -> List[Tuple[str, str, int, int]]:
    """
    解析文本内容，识别章节（预览版本，不导入数据库）

    返回: [(chapter_title, chapter_content, start_pos, end_pos), ...]
    """
    if not content:
        return []

    # 合并所有模式
    if pattern:
        patterns = [pattern]
    else:
        patterns = DEFAULT_CHAPTER_PATTERNS

    combined_pattern = "|".join(f"({p})" for p in patterns)

    # 查找所有章节标题
    matches = list(re.finditer(combined_pattern, content, re.MULTILINE))

    if not matches:
        # 如果没有找到章节，把整个内容作为一章
        return [("正文", content.strip(), 0, len(content))]

    chapters = []
    for i, match in enumerate(matches):
        title = match.group().strip()
        start = match.start()

        # 确定章节内容的结束位置
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)

        # 提取章节内容（不包括标题行）
        chapter_content = content[match.end() : end].strip()

        chapters.append((title, chapter_content, start, end))

    return chapters


def read_file_content(filepath: str) -> Tuple[str, str]:
    """
    读取文件内容，自动检测编码

    返回: (content, encoding)
    """
    encodings = ["utf-8", "gb18030", "gbk", "gb2312", "utf-16", "big5"]

    for encoding in encodings:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                content = f.read()
            return content, encoding
        except (UnicodeDecodeError, UnicodeError):
            continue

    raise ValueError(f"无法解析文件编码: {filepath}")


def format_size(size: int) -> str:
    """格式化文件大小"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def print_separator(char: str = "─", width: int = 60):
    """打印分隔线"""
    print(char * width)


def preview_chapters(
    chapters: List[Tuple[str, str, int, int]],
    show_count: int = 5,
    content_preview_len: int = 100,
) -> None:
    """
    交互式预览章节切分结果
    """
    total = len(chapters)

    print(f"\n{colorize('📚 章节切分预览', Colors.HEADER)}")
    print_separator()
    print(f"共识别到 {colorize(str(total), Colors.GREEN)} 个章节")
    print_separator()

    # 显示前 N 章
    print(f"\n{colorize('【前 {0} 章】'.format(min(show_count, total)), Colors.CYAN)}")
    for i, (title, content, start, end) in enumerate(chapters[:show_count]):
        char_count = len(content)
        preview = content[:content_preview_len].replace("\n", " ").strip()
        if len(content) > content_preview_len:
            preview += "..."

        print(
            f"\n  {colorize(f'[{i + 1}]', Colors.YELLOW)} {colorize(title, Colors.BOLD)}"
        )
        print(f"      字数: {char_count:,} | 位置: {start:,}-{end:,}")
        print(f"      预览: {preview[:80]}...")

    # 如果章节数大于显示数量，显示中间章节
    if total > show_count * 2:
        mid = total // 2
        print(f"\n{colorize('【中间章节 (第 {0} 章)】'.format(mid + 1), Colors.CYAN)}")
        title, content, start, end = chapters[mid]
        char_count = len(content)
        preview = content[:content_preview_len].replace("\n", " ").strip()
        if len(content) > content_preview_len:
            preview += "..."

        print(
            f"\n  {colorize(f'[{mid + 1}]', Colors.YELLOW)} {colorize(title, Colors.BOLD)}"
        )
        print(f"      字数: {char_count:,} | 位置: {start:,}-{end:,}")
        print(f"      预览: {preview[:80]}...")

    # 显示后 N 章
    if total > show_count:
        print(
            f"\n{colorize('【后 {0} 章】'.format(min(show_count, total - show_count)), Colors.CYAN)}"
        )
        for i, (title, content, start, end) in enumerate(chapters[-show_count:]):
            idx = total - show_count + i
            char_count = len(content)
            preview = content[:content_preview_len].replace("\n", " ").strip()
            if len(content) > content_preview_len:
                preview += "..."

            print(
                f"\n  {colorize(f'[{idx + 1}]', Colors.YELLOW)} {colorize(title, Colors.BOLD)}"
            )
            print(f"      字数: {char_count:,} | 位置: {start:,}-{end:,}")
            print(f"      预览: {preview[:80]}...")

    # 统计信息
    print_separator()
    total_chars = sum(len(c[1]) for c in chapters)
    avg_chars = total_chars // total if total > 0 else 0
    min_chars = min(len(c[1]) for c in chapters) if chapters else 0
    max_chars = max(len(c[1]) for c in chapters) if chapters else 0

    print(f"\n{colorize('📊 统计信息', Colors.HEADER)}")
    print(f"  总章节数: {colorize(str(total), Colors.GREEN)}")
    print(f"  总字符数: {colorize(f'{total_chars:,}', Colors.GREEN)}")
    print(f"  平均每章: {colorize(f'{avg_chars:,}', Colors.BLUE)} 字")
    print(f"  最短章节: {colorize(f'{min_chars:,}', Colors.YELLOW)} 字")
    print(f"  最长章节: {colorize(f'{max_chars:,}', Colors.YELLOW)} 字")
    print_separator()


def analyze_file(
    filepath: str, pattern: Optional[str] = None
) -> Tuple[str, List[Tuple[str, str, int, int]], str]:
    """
    分析文件，返回内容和章节列表
    """
    # 检查文件是否存在
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    # 获取文件信息
    file_size = os.path.getsize(filepath)
    filename = os.path.basename(filepath)

    print(f"\n{colorize('📄 文件信息', Colors.HEADER)}")
    print_separator()
    print(f"  文件名: {colorize(filename, Colors.BOLD)}")
    print(f"  路径: {filepath}")
    print(f"  大小: {colorize(format_size(file_size), Colors.BLUE)}")

    # 读取文件
    print(f"  正在读取文件...")
    content, encoding = read_file_content(filepath)
    print(f"  编码: {colorize(encoding, Colors.CYAN)}")
    print(f"  字符数: {colorize(f'{len(content):,}', Colors.GREEN)}")

    # 解析章节
    print(f"  正在解析章节...")
    if pattern:
        print(f"  使用正则: {colorize(pattern, Colors.YELLOW)}")
    else:
        print(f"  使用默认章节模式")

    chapters = parse_chapters_preview(content, pattern)
    print(f"  识别章节: {colorize(str(len(chapters)), Colors.GREEN)} 章")
    print_separator()

    return content, chapters, encoding


def confirm_import() -> bool:
    """确认是否导入"""
    while True:
        response = (
            input(f"\n{colorize('是否确认导入？', Colors.YELLOW)} (y/n): ")
            .strip()
            .lower()
        )
        if response in ["y", "yes", "是"]:
            return True
        elif response in ["n", "no", "否"]:
            return False
        print("请输入 y 或 n")


def do_import(
    content: str,
    chapters: List[Tuple[str, str, int, int]],
    title: str,
    author: Optional[str],
    pattern: Optional[str],
    edition_name: Optional[str],
) -> Tuple[int, int, int]:
    """
    执行导入操作

    返回: (work_id, edition_id, chapter_count)
    """
    from sail_server.db import Database
    from sail_server.model.text import TextImportRequest
    from sail_server.model.text import import_text_impl

    # 创建导入请求
    request = TextImportRequest(
        work_title=title,
        content=content,
        work_author=author,
        chapter_pattern=pattern,
    )

    # 获取数据库会话
    db = Database.get_instance().get_db_session()

    try:
        print(f"\n{colorize('🚀 正在导入...', Colors.HEADER)}")
        work_data, edition_data, chapter_count = import_text_impl(db, request)

        print(f"\n{colorize('✅ 导入成功！', Colors.GREEN)}")
        print_separator()
        print(f"  作品 ID: {colorize(str(work_data.id), Colors.CYAN)}")
        print(f"  作品标题: {colorize(work_data.title, Colors.BOLD)}")
        print(f"  版本 ID: {colorize(str(edition_data.id), Colors.CYAN)}")
        print(f"  章节数: {colorize(str(chapter_count), Colors.GREEN)}")
        print(f"  总字数: {colorize(f'{edition_data.char_count:,}', Colors.GREEN)}")
        print_separator()

        return work_data.id, edition_data.id, chapter_count
    except Exception as e:
        db.rollback()
        print(f"\n{colorize('❌ 导入失败: ' + str(e), Colors.RED)}")
        raise
    finally:
        db.close()


def test_pattern(content: str, pattern: str, show_matches: int = 10) -> None:
    """
    测试正则表达式匹配
    """
    print(f"\n{colorize('🔍 正则表达式测试', Colors.HEADER)}")
    print_separator()
    print(f"  模式: {colorize(pattern, Colors.YELLOW)}")

    try:
        matches = list(re.finditer(pattern, content, re.MULTILINE))
        print(f"  匹配数: {colorize(str(len(matches)), Colors.GREEN)}")

        if matches:
            print(f"\n  前 {min(show_matches, len(matches))} 个匹配:")
            for i, match in enumerate(matches[:show_matches]):
                text = match.group().strip()[:60]
                if len(match.group().strip()) > 60:
                    text += "..."
                print(f"    {colorize(f'[{i + 1}]', Colors.CYAN)} {text}")
        else:
            print(f"  {colorize('未找到匹配', Colors.RED)}")
    except re.error as e:
        print(f"  {colorize(f'正则表达式错误: {e}', Colors.RED)}")
    print_separator()


def interactive_mode(filepath: str, pattern: Optional[str] = None) -> None:
    """
    交互式模式：测试不同的正则表达式
    """
    content, encoding = read_file_content(filepath)

    print(f"\n{colorize('🎯 交互式正则测试模式', Colors.HEADER)}")
    print("输入正则表达式来测试章节匹配，输入 'q' 退出，输入 'default' 使用默认模式")
    print_separator()

    while True:
        user_pattern = input(f"\n{colorize('正则表达式', Colors.CYAN)} > ").strip()

        if user_pattern.lower() == "q":
            break
        elif user_pattern.lower() == "default":
            test_pattern(content, "|".join(f"({p})" for p in DEFAULT_CHAPTER_PATTERNS))
            chapters = parse_chapters_preview(content, None)
            preview_chapters(chapters)
        elif user_pattern:
            test_pattern(content, user_pattern)
            chapters = parse_chapters_preview(content, user_pattern)
            if chapters:
                preview_chapters(chapters, show_count=3)


def run_text_import_cli():
    """
    运行文本导入 CLI
    """
    parser = argparse.ArgumentParser(
        description="批量导入大文本文件（如小说）到数据库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 预览模式（不实际导入）
  python main.py --import-text novel.txt --preview
  
  # 使用自定义正则匹配章节
  python main.py --import-text novel.txt --pattern "^第\\d+章.*" --preview
  
  # 导入到开发环境
  python main.py --import-text novel.txt --title "我的小说" --author "作者名" --dev
  
  # 导入到生产环境
  python main.py --import-text novel.txt --title "我的小说" --prod
  
  # 交互式测试正则表达式
  python main.py --import-text novel.txt --interactive

常用正则模式:
  中文章节: ^第[一二三四五六七八九十百千万零〇\\d]+章.*
  英文章节: ^Chapter\\s+\\d+.*
  数字章节: ^\\d+\\.\\s+.*
  方括号章节: ^【[^】]+】
        """,
    )

    parser.add_argument(
        "--import-text",
        dest="filepath",
        type=str,
        required=True,
        help="要导入的 .txt 文件路径",
    )
    parser.add_argument("--title", type=str, help="作品标题（默认使用文件名）")
    parser.add_argument("--author", type=str, help="作者名")
    parser.add_argument("--pattern", type=str, help="章节识别正则表达式")
    parser.add_argument("--edition", type=str, help="版本名称")

    # 操作模式
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--preview", action="store_true", help="仅预览章节切分结果，不导入"
    )
    mode_group.add_argument(
        "--interactive", action="store_true", help="交互式测试正则表达式"
    )
    mode_group.add_argument(
        "--confirm",
        action="store_true",
        default=True,
        help="显示预览后确认导入（默认）",
    )

    # 环境选择
    env_group = parser.add_mutually_exclusive_group()
    env_group.add_argument("--dev", action="store_true", help="使用开发环境数据库")
    env_group.add_argument("--prod", action="store_true", help="使用生产环境数据库")

    # 显示选项
    parser.add_argument(
        "--show-count", type=int, default=5, help="预览时显示的章节数量（默认: 5）"
    )
    parser.add_argument("--force", "-f", action="store_true", help="跳过确认直接导入")

    args = parser.parse_args()

    # 确定环境
    if args.prod:
        env_mode = "prod"
    else:
        env_mode = "dev"  # 默认使用开发环境

    print(f"\n{colorize('=' * 60, Colors.HEADER)}")
    print(f"{colorize('  📖 SailZen 文本批量导入工具', Colors.BOLD)}")
    print(f"{colorize('=' * 60, Colors.HEADER)}")
    print(
        f"  环境: {colorize(env_mode.upper(), Colors.YELLOW if env_mode == 'dev' else Colors.RED)}"
    )

    # 设置环境变量（在导入数据库模块之前）
    from sail.utils import read_env

    read_env(env_mode)

    filepath = args.filepath
    pattern = args.pattern
    title = args.title or Path(filepath).stem

    try:
        if args.interactive:
            # 交互式模式
            interactive_mode(filepath, pattern)
            return

        # 分析文件
        content, chapters, encoding = analyze_file(filepath, pattern)

        # 预览章节
        preview_chapters(chapters, show_count=args.show_count)

        if args.preview:
            # 仅预览模式
            print(f"\n{colorize('📋 预览模式：未执行导入', Colors.YELLOW)}")
            return

        # 检查是否可导入
        if len(chapters) == 0:
            print(
                f"\n{colorize('⚠️ 未识别到任何章节，请检查正则表达式', Colors.YELLOW)}"
            )
            return

        if len(chapters) == 1 and chapters[0][0] == "正文":
            print(
                f"\n{colorize('⚠️ 未能识别章节结构，整个内容将作为单一章节导入', Colors.YELLOW)}"
            )
            print(f"  建议使用 --pattern 参数指定章节正则表达式")
            print(f"  或使用 --interactive 模式测试不同的正则表达式")

        # 确认导入
        if not args.force:
            if not confirm_import():
                print(f"\n{colorize('🚫 已取消导入', Colors.YELLOW)}")
                return

        # 执行导入
        work_id, edition_id, chapter_count = do_import(
            content, chapters, title, args.author, pattern, args.edition
        )

    except FileNotFoundError as e:
        print(f"\n{colorize(f'❌ 错误: {e}', Colors.RED)}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n{colorize(f'❌ 错误: {e}', Colors.RED)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{colorize(f'❌ 未知错误: {e}', Colors.RED)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_text_import_cli()
