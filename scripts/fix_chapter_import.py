# -*- coding: utf-8 -*-
# @file fix_chapter_import.py
# @brief Smart Chapter Import with Auto-Fix for Merged Chapters
# @author sailing-innocent
# @date 2026-02-16
# @version 1.0
# ---------------------------------
"""
智能章节导入修复工具

功能：
1. 解析原始文件章节
2. 检测被合并的超长章节
3. 使用更严格的正则重新解析超长章节
4. 用户确认后导入
5. 生产环境安全导入（双重确认）

使用方法：
    # 开发环境导入
    uv run scripts/fix_chapter_import.py "novel.txt" --title "求魔" --author "耳根"

    # 开发环境自动导入（跳过确认）
    uv run scripts/fix_chapter_import.py "novel.txt" --title "求魔" --author "耳根" --yes

    # 生产环境导入（需要双重确认）
    uv run scripts/fix_chapter_import.py "novel.txt" --title "求魔" --author "耳根" --prod

生产环境安全机制：
    - 显示详细的预览信息
    - 需要输入 'DEPLOY' 确认
    - 需要输入作品标题二次确认
    - --yes 参数在生产环境下无效

警告：
    生产环境导入会直接修改远程数据库，请谨慎操作！
    建议先在开发环境测试后再导入到生产环境。
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
from sailzen.cmd import Colors, colorize, print_separator, print_header, read_file


def extract_chapter_number(title: str) -> Optional[int]:
    """从章节标题中提取数字"""
    match = re.search(r"第([一二三四五六七八九十百千万零〇\d]+)章", title)
    if match:
        num_str = match.group(1)
        # 尝试直接转换阿拉伯数字
        try:
            return int(num_str)
        except:
            # 中文数字转换（简化版）
            cn_nums = {
                "一": 1,
                "二": 2,
                "三": 3,
                "四": 4,
                "五": 5,
                "六": 6,
                "七": 7,
                "八": 8,
                "九": 9,
                "十": 10,
                "百": 100,
                "千": 1000,
                "万": 10000,
                "〇": 0,
                "零": 0,
            }
            result = 0
            temp = 0
            for char in num_str:
                if char in cn_nums:
                    num = cn_nums[char]
                    if num >= 10:
                        if temp == 0:
                            temp = 1
                        result += temp * num
                        temp = 0
                    else:
                        temp = temp * 10 + num
            result += temp
            return result if result > 0 else None
    return None


@dataclass
class Chapter:
    index: int
    title: str
    content: str
    char_count: int
    chapter_num: Optional[int] = None  # 章节编号（如 192）


def parse_chapters_strict(content: str) -> List[Chapter]:
    """
    使用严格模式解析章节
    尝试多种模式以确保捕获所有章节
    """
    # 多种章节模式（按优先级排序）
    patterns = [
        # 标准格式：第XXX章
        (r"第[一二三四五六七八九十百千万零〇\d]+章[^\n]*", "标准章节"),
        # 数字格式：第XXX节
        (r"第[一二三四五六七八九十百千万零〇\d]+节[^\n]*", "数字节"),
        # 英文格式
        (r"Chapter\s+\d+[^\n]*", "英文章节"),
        # 方括号格式
        (r"【[^\】]+】[^\n]*", "方括号章节"),
    ]

    all_matches = []

    for pattern, desc in patterns:
        matches = list(re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE))
        if len(matches) > len(all_matches):
            all_matches = matches
            best_pattern = (pattern, desc)

    if not all_matches:
        return [Chapter(0, "正文", content.strip(), len(content), None)]

    print(f"使用模式: {best_pattern[1]} ({best_pattern[0]})")
    print(f"初步匹配: {len(all_matches)} 个章节")

    chapters = []
    for i, match in enumerate(all_matches):
        title = match.group().strip()
        start = match.start()
        end = all_matches[i + 1].start() if i + 1 < len(all_matches) else len(content)
        chapter_content = content[match.end() : end].strip()
        char_count = len(chapter_content)
        chapter_num = extract_chapter_number(title)

        chapters.append(Chapter(i, title, chapter_content, char_count, chapter_num))

    return chapters


def find_merged_chapters(chapters: List[Chapter]) -> List[Tuple[int, Chapter]]:
    """找出可能被合并的章节（超长且章节号跳跃）"""
    merged = []

    for i, ch in enumerate(chapters):
        # 超长检测（超过5万字）
        if ch.char_count > 50000:
            # 检查章节号是否跳跃
            prev_num = chapters[i - 1].chapter_num if i > 0 else None
            next_num = chapters[i + 1].chapter_num if i < len(chapters) - 1 else None

            gap_before = (
                (ch.chapter_num - prev_num) if (ch.chapter_num and prev_num) else 0
            )
            gap_after = (
                (next_num - ch.chapter_num) if (ch.chapter_num and next_num) else 0
            )

            # 如果章节号跳跃超过5，可能是合并了
            if gap_before > 5 or gap_after > 5 or ch.char_count > 100000:
                merged.append((i, ch))

    return merged


def deep_split_chapter(chapter: Chapter) -> List[Chapter]:
    """
    深度拆分被合并的章节

    策略：
    1. 在内容中查找所有可能的子章节标题
    2. 按顺序拆分
    """
    content = chapter.content

    # 在内容内部查找子章节（更严格的匹配）
    # 匹配 "第XXX章" 格式，但要求前面有换行
    sub_pattern = r"\n第[一二三四五六七八九十百千万零〇\d]+章[^\n]*"
    sub_matches = list(re.finditer(sub_pattern, content, re.MULTILINE))

    if len(sub_matches) <= 1:
        # 尝试其他模式
        sub_pattern = r"\n[一二三四五六七八九十百千万零〇\d]+章[^\n]*"
        sub_matches = list(re.finditer(sub_pattern, content, re.MULTILINE))

    if len(sub_matches) <= 1:
        # 没发现子章节，返回原章节
        return [chapter]

    print(f"  发现 {len(sub_matches)} 个子章节标记")

    sub_chapters = []
    base_index = chapter.index

    for i, match in enumerate(sub_matches):
        # 提取子章节标题（去掉开头的换行）
        sub_title = match.group().strip()
        start = match.start()
        end = sub_matches[i + 1].start() if i + 1 < len(sub_matches) else len(content)
        sub_content = content[start:end].strip()
        sub_chapter_num = extract_chapter_number(sub_title)

        sub_chapters.append(
            Chapter(
                index=base_index + i,
                title=sub_title,
                content=sub_content,
                char_count=len(sub_content),
                chapter_num=sub_chapter_num,
            )
        )

    return sub_chapters


def fix_merged_chapters(
    chapters: List[Chapter], merged_indices: List[int]
) -> List[Chapter]:
    """修复被合并的章节"""
    fixed = []

    for i, ch in enumerate(chapters):
        if i in merged_indices:
            print(f"\n修复章节 [{i}]: {ch.title} ({ch.char_count:,} 字)")
            sub_chapters = deep_split_chapter(ch)

            if len(sub_chapters) > 1:
                print(f"  拆分为 {len(sub_chapters)} 个子章节")
                for j, sub in enumerate(sub_chapters[:5]):
                    print(f"    [{j}] {sub.title[:40]} ({sub.char_count:,} 字)")
                if len(sub_chapters) > 5:
                    print(f"    ... 还有 {len(sub_chapters) - 5} 个子章节")
                fixed.extend(sub_chapters)
            else:
                print(f"  无法自动拆分，保持原样")
                fixed.append(ch)
        else:
            fixed.append(ch)

    # 重新编号
    for i, ch in enumerate(fixed):
        ch.index = i

    return fixed


def import_to_database(chapters: List[Chapter], title: str, author: str, env_mode: str):
    """导入到数据库"""
    from sail.utils import read_env

    print_header("开始导入到数据库")

    # 组装内容
    content_parts = []
    for ch in chapters:
        content_parts.append(f"{ch.title}\n{ch.content}")
    full_content = "\n\n".join(content_parts)

    # 先设置环境变量
    read_env(env_mode)

    # 延迟导入（避免在模块加载时初始化）
    import importlib

    db_module = importlib.import_module("sail_server.db")
    Database = db_module.Database

    data_module = importlib.import_module("sail_server.data.text")
    TextImportRequest = data_module.TextImportRequest

    model_module = importlib.import_module("sail_server.model.text")
    import_text_impl = model_module.import_text_impl

    db = Database.get_instance().get_db_session()

    try:
        request = TextImportRequest(
            work_title=title,
            content=full_content,
            work_author=author,
            edition_name="智能修复导入",
            language="zh",
        )

        work_data, edition_data, chapter_count = import_text_impl(db, request)

        print()
        print(colorize("✅ 导入成功!", Colors.GREEN))
        print_separator()
        print(f"  作品 ID: {work_data.id}")
        print(f"  标题: {work_data.title}")
        print(f"  版本 ID: {edition_data.id}")
        print(f"  章节数: {chapter_count}")
        print(f"  总字数: {edition_data.char_count:,}")
        print_separator()

        return work_data.id

    except Exception as e:
        db.rollback()
        print(colorize(f"❌ 导入失败: {e}", Colors.RED))
        import traceback

        traceback.print_exc()
        return None
    finally:
        db.close()


def prod_safety_confirmation(
    chapters: List[Chapter], title: str, author: str, file_path: str
) -> bool:
    """
    生产环境导入的安全确认流程

    返回: 是否确认导入
    """
    print_header("⚠️  生产环境导入确认 ⚠️", Colors.RED)

    print()
    print(colorize("警告: 您正在准备将数据导入到生产环境！", Colors.RED))
    print(colorize("这是一个危险操作，请仔细确认以下信息：", Colors.YELLOW))
    print_separator()

    # 1. 显示文件信息
    print(f"  文件路径: {file_path}")
    print(f"  作品标题: {colorize(title, Colors.BOLD)}")
    print(f"  作者: {author or 'N/A'}")

    # 2. 显示章节统计
    total_chars = sum(ch.char_count for ch in chapters)
    avg_chars = total_chars // len(chapters) if chapters else 0
    max_chars = max(ch.char_count for ch in chapters) if chapters else 0
    min_chars = min(ch.char_count for ch in chapters) if chapters else 0

    print()
    print(colorize("【章节统计】", Colors.BOLD))
    print(f"  总章节数: {colorize(str(len(chapters)), Colors.GREEN)}")
    print(f"  总字数: {colorize(f'{total_chars:,}', Colors.GREEN)}")
    print(f"  平均每章: {colorize(f'{avg_chars:,}', Colors.BLUE)} 字")
    print(f"  最长章节: {colorize(f'{max_chars:,}', Colors.YELLOW)} 字")
    print(f"  最短章节: {colorize(f'{min_chars:,}', Colors.YELLOW)} 字")

    # 3. 检测异常
    long_chapters = [ch for ch in chapters if ch.char_count > 50000]
    short_chapters = [ch for ch in chapters if ch.char_count < 1000]

    if long_chapters:
        print()
        print(colorize(f"【警告】检测到 {len(long_chapters)} 个超长章节:", Colors.RED))
        for ch in long_chapters[:3]:
            print(f"  - {ch.title}: {ch.char_count:,} 字")
        if len(long_chapters) > 3:
            print(f"  ... 还有 {len(long_chapters) - 3} 个")

    if short_chapters:
        print()
        print(
            colorize(f"【警告】检测到 {len(short_chapters)} 个超短章节", Colors.YELLOW)
        )

    # 4. 显示首尾章节预览
    print()
    print(colorize("【首尾章节预览】", Colors.BOLD))
    print("前3章:")
    for ch in chapters[:3]:
        print(f"  [{ch.index}] {ch.title[:50]} ({ch.char_count:,} 字)")
    print("...")
    print("后3章:")
    for ch in chapters[-3:]:
        print(f"  [{ch.index}] {ch.title[:50]} ({ch.char_count:,} 字)")

    # 5. 二次确认
    print_separator()
    print()
    print(colorize("请确认您要导入到生产环境:", Colors.RED))
    print()
    print("输入 'preview' - 仅预览，不导入")
    print("输入 'dev' - 切换到开发环境导入")
    print("输入 'DEPLOY' - 确认导入到生产环境（大写）")
    print("输入其他 - 取消导入")
    print()

    confirm = input(colorize("您的选择: ", Colors.CYAN)).strip()

    if confirm == "DEPLOY":
        print()
        print(colorize("✅ 已确认，开始导入到生产环境...", Colors.GREEN))
        return True
    elif confirm.lower() == "preview":
        print()
        print(colorize("📋 预览模式：显示信息但不导入", Colors.YELLOW))
        return False
    elif confirm.lower() == "dev":
        print()
        print(colorize("🔄 切换到开发环境导入", Colors.YELLOW))
        return False
    else:
        print()
        print(colorize("❌ 已取消导入", Colors.YELLOW))
        return False


def safe_import_with_prod_check(
    chapters: List[Chapter],
    title: str,
    author: str,
    env_mode: str,
    file_path: str,
    yes: bool,
) -> Optional[int]:
    """
    安全的导入流程，包含生产环境特殊处理

    返回: 作品ID（成功）或 None（失败/取消）
    """
    # 生产环境需要额外的安全确认
    if env_mode == "prod":
        if yes:
            print()
            print(
                colorize(
                    "⚠️ 警告: --yes 参数在生产环境下被忽略，必须进行手动确认",
                    Colors.YELLOW,
                )
            )

        confirmed = prod_safety_confirmation(chapters, title, author, file_path)

        if not confirmed:
            return None

        # 最终确认
        print()
        final = input(
            colorize("最后确认：输入作品标题以继续导入: ", Colors.RED)
        ).strip()
        if final != title:
            print(colorize("❌ 标题不匹配，导入取消", Colors.RED))
            return None
    else:
        # 开发环境的确认
        if not yes:
            print()
            confirm = (
                input(
                    colorize(f"确认导入 '{title}' 到开发环境? (y/n): ", Colors.YELLOW)
                )
                .strip()
                .lower()
            )
            if confirm not in ["y", "yes", "是"]:
                print(colorize("已取消导入", Colors.YELLOW))
                return None

    # 执行导入
    return import_to_database(chapters, title, author, env_mode)


def main():
    parser = argparse.ArgumentParser(description="智能章节导入修复工具")
    parser.add_argument("file", help="要导入的 .txt 文件路径")
    parser.add_argument("--title", "-t", required=True, help="作品标题")
    parser.add_argument("--author", "-a", help="作者名")
    parser.add_argument("--prod", action="store_true", help="使用生产环境")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过所有确认直接导入")

    args = parser.parse_args()

    env_mode = "prod" if args.prod else "dev"

    # 1. 读取文件
    print_header("智能章节导入修复工具")
    print(f"文件: {args.file}")
    print("读取文件...")

    content = read_file(args.file)
    print(f"文件大小: {len(content):,} 字符")

    # 2. 解析章节
    print()
    print("解析章节...")
    chapters = parse_chapters_strict(content)
    print(f"初步解析: {len(chapters)} 个章节")

    # 3. 检测被合并的章节
    print()
    print("检测章节合并...")
    merged = find_merged_chapters(chapters)

    if merged:
        print_header(f"⚠️ 发现 {len(merged)} 个被合并的章节", Colors.RED)

        for idx, ch in merged[:5]:
            prev_num = chapters[idx - 1].chapter_num if idx > 0 else None
            next_num = (
                chapters[idx + 1].chapter_num if idx < len(chapters) - 1 else None
            )
            print()
            print(f"  [{idx}] {ch.title}")
            print(f"      字数: {colorize(f'{ch.char_count:,}', Colors.RED)} 字")
            print(f"      章节号: {prev_num} -> {ch.chapter_num} -> {next_num}")
            if prev_num and ch.chapter_num:
                print(f"      跳跃: {ch.chapter_num - prev_num} 章")

        if len(merged) > 5:
            print(f"\n  ... 还有 {len(merged) - 5} 个")

        # 4. 询问是否修复
        print()
        if args.yes:
            confirm = "y"
            print(colorize("自动修复模式", Colors.GREEN))
        else:
            confirm = (
                input(colorize("是否自动修复这些章节? (y/n): ", Colors.YELLOW))
                .strip()
                .lower()
            )

        if confirm in ["y", "yes", "是"]:
            merged_indices = [idx for idx, _ in merged]
            chapters = fix_merged_chapters(chapters, merged_indices)
            print(f"\n修复后总章节数: {len(chapters)}")
        else:
            print(colorize("保持原样，不修复", Colors.YELLOW))
    else:
        print(colorize("✅ 未发现被合并的章节", Colors.GREEN))

    # 5. 显示统计
    total_chars = sum(ch.char_count for ch in chapters)
    avg_chars = total_chars // len(chapters) if chapters else 0

    print()
    print_header("最终统计")
    print(f"  章节数: {colorize(str(len(chapters)), Colors.GREEN)}")
    print(f"  总字数: {colorize(f'{total_chars:,}', Colors.GREEN)}")
    print(f"  平均每章: {colorize(f'{avg_chars:,}', Colors.BLUE)} 字")

    # 显示首尾章节
    print()
    print("前3章:")
    for ch in chapters[:3]:
        print(f"  [{ch.index}] {ch.title[:40]} ({ch.char_count:,} 字)")

    print()
    print("后3章:")
    for ch in chapters[-3:]:
        print(f"  [{ch.index}] {ch.title[:40]} ({ch.char_count:,} 字)")

    # 6. 安全导入（包含生产环境特殊处理）
    result = safe_import_with_prod_check(
        chapters, args.title, args.author, env_mode, args.file, args.yes
    )

    if result:
        print()
        print(colorize(f"✅ 作品已成功导入，ID: {result}", Colors.GREEN))
    else:
        print()
        print(colorize("导入未执行", Colors.YELLOW))


if __name__ == "__main__":
    main()
