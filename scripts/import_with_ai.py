# -*- coding: utf-8 -*-
# @file import_with_ai.py
# @brief AI-Powered Text Import with Human Confirmation
# @author sailing-innocent
# @date 2026-02-16
# @version 1.0
# ---------------------------------
"""
AI 文本导入主程序

功能：
1. 读取并清理文本文件
2. 使用 AI 分析章节结构
3. 展示详细的预览界面
4. 人机确认后导入数据库

使用方法：
    uv run import_with_ai.py <file.txt> --title "作品标题" --author "作者"
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional

from sailzen.text import TextCleaner, detect_encoding
from sailzen.chapter import AIChapterParser, ChapterType
from sailzen.cmd import Colors, colorize, print_separator, print_header


def format_number(n: int) -> str:
    """格式化数字，添加千位分隔符"""
    return f"{n:,}"


def print_chapter_preview(chapter, show_content: bool = True, content_limit: int = 300):
    """打印单个章节预览"""
    type_colors = {
        ChapterType.STANDARD: Colors.GREEN,
        ChapterType.PROLOGUE: Colors.BLUE,
        ChapterType.EPILOGUE: Colors.BLUE,
        ChapterType.EXTRA: Colors.YELLOW,
        ChapterType.INTERLUDE: Colors.CYAN,
        ChapterType.AUTHOR: Colors.YELLOW,
        ChapterType.NOISE: Colors.RED,
    }

    type_color = type_colors.get(chapter.chapter_type, Colors.ENDC)
    type_label = chapter.chapter_type.value.upper()

    # 标题行
    title_display = chapter.title
    if chapter.chapter_title:
        title_display = f"{chapter.label} {chapter.chapter_title}"

    print(
        f"\n  {colorize(f'[{chapter.index}]', Colors.YELLOW)} "
        f"{colorize(title_display, Colors.BOLD)} "
        f"{colorize(f'[{type_label}]', type_color)}"
    )

    # 统计信息
    print(
        f"      字数: {colorize(format_number(chapter.char_count), Colors.CYAN)} | "
        f"位置: {format_number(chapter.start_pos)}-{format_number(chapter.end_pos)}"
    )

    # 警告
    if chapter.warnings:
        for warning in chapter.warnings:
            print(f"      {colorize('[!] ' + warning, Colors.YELLOW)}")

    # 内容预览
    if show_content and chapter.content:
        content_preview = chapter.content[:content_limit].replace("\n", " ").strip()
        if len(chapter.content) > content_limit:
            content_preview += "..."
        print(f"      开头: {content_preview[:100]}")

        if len(chapter.content) > 200:
            ending_preview = chapter.content[-200:].replace("\n", " ").strip()
            print(f"      结尾: ...{ending_preview[-100:]}")


def print_analysis_result(result):
    """打印分析结果摘要"""
    print_header("ANALYSIS RESULT")

    print_separator()
    print(
        f"  总章节数: {colorize(format_number(result.chapter_count), Colors.GREEN + Colors.BOLD)}"
    )
    print(f"  总字数:   {colorize(format_number(result.total_chars), Colors.GREEN)}")
    print(
        f"  平均每章: {colorize(format_number(result.avg_char_count), Colors.CYAN)} 字"
    )
    print(
        f"  最短章节: {colorize(format_number(result.min_char_count), Colors.YELLOW)} 字"
    )
    print(
        f"  最长章节: {colorize(format_number(result.max_char_count), Colors.YELLOW)} 字"
    )
    print_separator()

    # 拆分规则
    print(f"\n  {colorize('拆分规则:', Colors.BOLD)}")
    for rule in result.split_rules:
        print(f"    - {rule}")

    # 异常章节
    if result.anomalies:
        print(f"\n  {colorize('异常章节:', Colors.BOLD + Colors.YELLOW)}")
        for anomaly in result.anomalies[:5]:  # 只显示前5个
            print(
                f"    [{anomaly['index']}] {anomaly['title'][:30]} "
                f"({format_number(anomaly['char_count'])} 字)"
            )
        if len(result.anomalies) > 5:
            print(f"    ... 还有 {len(result.anomalies) - 5} 个异常章节")

    # 警告
    if result.warnings:
        print(f"\n  {colorize('⚠️ 警告:', Colors.BOLD + Colors.YELLOW)}")
        for warning in result.warnings:
            print(f"    • {warning}")


def print_preview_chapters(result, num_preview: int = 3):
    """打印章节预览"""
    chapters = result.chapters
    total = len(chapters)

    if total == 0:
        print(colorize("\n  未识别到任何章节", Colors.RED))
        return

    # 前 N 章
    print_header(f"PREVIEW: First {min(num_preview, total)} chapters")
    for chapter in result.get_first_chapters(num_preview):
        print_chapter_preview(chapter)

    # 中间章节（如果足够多）
    if total > num_preview * 2 + 2:
        mid_idx = total // 2
        print_header(f"PREVIEW: Middle chapter ({mid_idx + 1})")
        print_chapter_preview(chapters[mid_idx])

    # 后 N 章
    if total > num_preview:
        print_header(f"PREVIEW: Last {min(num_preview, total - num_preview)} chapters")
        for chapter in result.get_last_chapters(num_preview):
            print_chapter_preview(chapter)


def confirm_import_interactive() -> bool:
    """交互式确认导入"""
    print()
    print_separator("─")

    while True:
        response = (
            input(
                colorize("\n是否确认导入? (y/n/e=编辑): ", Colors.BOLD + Colors.YELLOW)
            )
            .strip()
            .lower()
        )

        if response in ["y", "yes", "是", "确认"]:
            return True
        elif response in ["n", "no", "否", "取消"]:
            return False
        elif response in ["e", "edit", "编辑"]:
            return None  # 返回 None 表示需要编辑
        else:
            print("  请输入: y (确认) / n (取消) / e (编辑)")


def edit_chapters(result):
    """简单的章节编辑界面"""
    print_header("EDIT MODE")
    print("可用命令:")
    print("  d <index>  - 删除指定章节")
    print("  m <index> <new_index>  - 移动章节")
    print("  t <index> <type>  - 修改章节类型")
    print("  l  - 列出所有章节")
    print("  q  - 完成编辑")
    print()

    while True:
        command = input(colorize("编辑 > ", Colors.CYAN)).strip().split()

        if not command:
            continue

        cmd = command[0].lower()

        if cmd == "q":
            break
        elif cmd == "l":
            print(f"\n共 {len(result.chapters)} 章:")
            for c in result.chapters:
                print(f"  [{c.index}] {c.title[:40]} ({c.chapter_type.value})")
        elif cmd == "d" and len(command) >= 2:
            try:
                idx = int(command[1])
                chapter = next((c for c in result.chapters if c.index == idx), None)
                if chapter:
                    result.chapters.remove(chapter)
                    print(f"  已删除章节 [{idx}]")
                else:
                    print(f"  未找到章节 [{idx}]")
            except ValueError:
                print("  无效的索引")
        elif cmd == "t" and len(command) >= 3:
            try:
                idx = int(command[1])
                new_type = command[2]
                chapter = next((c for c in result.chapters if c.index == idx), None)
                if chapter:
                    try:
                        chapter.chapter_type = ChapterType(new_type)
                        print(f"  已修改章节 [{idx}] 类型为 {new_type}")
                    except ValueError:
                        print(f"  无效的类型: {new_type}")
                else:
                    print(f"  未找到章节 [{idx}]")
            except ValueError:
                print("  无效的索引")
        else:
            print("  未知命令")

    # 重新计算索引
    for i, chapter in enumerate(result.chapters):
        chapter.index = i

    return result


def export_to_database(
    result, title: str, author: Optional[str], edition_name: Optional[str]
):
    """导出到数据库"""
    print_header("IMPORTING TO DATABASE")

    try:
        # 添加项目根目录到路径以导入 sail_server
        # 脚本路径: .agents/skills/sailzen-ai-text-import/scripts/
        # 项目根目录在脚本的上四级目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, "..", "..", "..", ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        print(f"Project root: {project_root}")

        # 读取环境变量
        from sail.utils import read_env

        read_env("dev")  # 使用开发环境

        from sail_server.db import Database
        from sail_server.data.text import TextImportRequest
        from sail_server.model.text import import_text_impl

        # 构建导入请求
        # 将解析好的章节组装成 content
        content_parts = []
        for c in result.chapters:
            content_parts.append(f"{c.title}\n{c.content}")
        content = "\n\n".join(content_parts)

        request = TextImportRequest(
            work_title=title,
            content=content,
            work_author=author,
            edition_name=edition_name or "AI导入",
            language="zh",
        )

        print(f"Title: {title}")
        print(f"Author: {author or 'Unknown'}")
        print(f"Edition: {edition_name or 'AI Import'}")
        print(f"Chapters: {len(result.chapters)}")
        print(f"Content size: {len(content):,} chars")
        print()
        print("Connecting to database...")

        db = Database.get_instance().get_db_session()
        work_data, edition_data, chapter_count = import_text_impl(db, request)

        print()
        print(colorize("[SUCCESS] Import completed!", Colors.GREEN))
        print(f"  Work ID: {work_data.id}")
        print(f"  Edition ID: {edition_data.id}")
        print(f"  Chapter count: {chapter_count}")
        print(f"  Total chars: {edition_data.char_count:,}")

    except ImportError as e:
        print(colorize(f"[Error] Cannot import sail_server modules: {e}", Colors.RED))
        print("Make sure you are running from the project root or skill directory")
        raise
    except Exception as e:
        print(colorize(f"[Error] Import failed: {e}", Colors.RED))
        raise


def run_import(
    file_path: str,
    title: Optional[str],
    author: Optional[str],
    edition_name: Optional[str],
    use_ai: bool = True,
    skip_confirm: bool = False,
    preview_only: bool = False,
):
    """
    执行导入流程

    Args:
        file_path: 文件路径
        title: 作品标题
        author: 作者
        edition_name: 版本名称
        use_ai: 是否使用 AI 分析
        skip_confirm: 跳过确认直接导入
        preview_only: 仅预览不导入
    """
    # 检查文件
    if not os.path.exists(file_path):
        print(colorize(f"❌ 文件不存在: {file_path}", Colors.RED))
        return

    file_name = Path(file_path).name
    work_title = title or Path(file_path).stem

    print()
    print_separator("═")
    print(f"  {colorize('SailZen AI Text Import Tool', Colors.BOLD + Colors.CYAN)}")
    print_separator("═")

    # 1. 读取文件
    print(f"\n[File] Reading: {colorize(file_name, Colors.BOLD)}")
    try:
        content, encoding = detect_encoding(file_path)
        print(f"  编码: {colorize(encoding, Colors.CYAN)}")
        print(f"  原始大小: {colorize(format_number(len(content)), Colors.CYAN)} 字符")
    except Exception as e:
        print(colorize(f"❌ 读取失败: {e}", Colors.RED))
        return

    # 2. 清理文本
    print(f"\n[Clean] Cleaning text...")
    cleaner = TextCleaner()
    clean_result = cleaner.clean(content, encoding)

    print(
        f"  清理后大小: {colorize(format_number(len(clean_result.cleaned_text)), Colors.CYAN)} 字符"
    )
    print(f"  Removed: {len(clean_result.removed_content)} items")

    if clean_result.warnings:
        for warning in clean_result.warnings:
            print(f"  {colorize('[Warning] ' + warning, Colors.YELLOW)}")

    # 3. 解析章节
    print(f"\n[Parse] Parsing chapters{' (AI mode)' if use_ai else ' (Rule mode)'}...")
    parser = AIChapterParser(sample_size=3000)
    parse_result = parser.parse(clean_result.cleaned_text, use_ai=use_ai)

    # 4. 展示分析结果
    print_analysis_result(parse_result)

    # 5. 展示章节预览
    print_preview_chapters(parse_result, num_preview=3)

    # 6. 预览模式
    if preview_only:
        print_header("PREVIEW MODE COMPLETE")
        print("  使用 --confirm 参数执行实际导入")
        return

    # 7. 确认导入
    if not skip_confirm:
        confirm_result = confirm_import_interactive()

        if confirm_result is None:  # 编辑模式
            parse_result = edit_chapters(parse_result)
            # 重新展示结果
            print_analysis_result(parse_result)
            confirm_result = confirm_import_interactive()
            if confirm_result is None:
                confirm_result = True  # 编辑后直接确认

        if not confirm_result:
            print(colorize("\n[Cancelled] Import cancelled", Colors.YELLOW))
            return

    # 8. 导入数据库
    export_to_database(parse_result, work_title, author, edition_name)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="AI 驱动的文本导入工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用 AI 分析并预览
  python import_with_ai.py novel.txt --title "我的小说" --preview
  
  # 使用规则解析（无 AI）
  python import_with_ai.py novel.txt --title "我的小说" --no-ai
  
  # 直接导入（跳过确认）
  python import_with_ai.py novel.txt --title "我的小说" --author "作者" --yes
  
  # 指定版本名称
  python import_with_ai.py novel.txt --title "我的小说" --edition "精校版"
        """,
    )

    parser.add_argument("file", help="要导入的 .txt 文件路径")
    parser.add_argument("--title", "-t", help="作品标题（默认使用文件名）")
    parser.add_argument("--author", "-a", help="作者名")
    parser.add_argument("--edition", "-e", help="版本名称")

    parser.add_argument(
        "--no-ai", action="store_true", help="不使用 AI，仅使用规则解析"
    )
    parser.add_argument(
        "--preview", "-p", action="store_true", help="仅预览分析结果，不导入"
    )
    parser.add_argument("--yes", "-y", action="store_true", help="跳过确认直接导入")

    parser.add_argument(
        "--sample-size", type=int, default=3000, help="AI 采样大小（默认: 3000）"
    )
    parser.add_argument(
        "--preview-count", type=int, default=3, help="预览时显示的章节数量（默认: 3）"
    )

    args = parser.parse_args()

    run_import(
        file_path=args.file,
        title=args.title,
        author=args.author,
        edition_name=args.edition,
        use_ai=not args.no_ai,
        skip_confirm=args.yes,
        preview_only=args.preview,
    )


if __name__ == "__main__":
    main()
