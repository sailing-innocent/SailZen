# -*- coding: utf-8 -*-
# @file text_import_manager.py
# @brief Text Import Management Tool - Undo Import & Fix Chapter Anomalies
# @author sailing-innocent
# @date 2026-02-16
# @version 1.0
# ---------------------------------
"""
文本导入管理工具

功能：
1. 撤销导入 - 删除作品及其所有相关数据
2. 分析异常 - 检测超长/超短章节
3. 拆分章节 - 重新解析超长章节
4. 安全导入 - 用户确认后再导入

使用方法：
    # 撤销导入
    python scripts/text_import_manager.py --undo --work-id 9

    # 分析文件中的异常章节
    python scripts/text_import_manager.py --analyze file.txt

    # 安全导入（带异常检测和确认）
    python scripts/text_import_manager.py --safe-import file.txt --title "求魔" --author "耳根"
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field
from statistics import mean, stdev

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sail_server.utils.env import read_env


# 延迟导入数据库相关模块
def get_db_models():
    from sail_server.db import Database
    from sail_server.data.text import Work, Edition, DocumentNode

    return Database, Work, Edition, DocumentNode


# ============================================================================
# 颜色输出
# ============================================================================


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def colorize(text: str, color: str) -> str:
    """为文本添加颜色"""
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            return text
    return f"{color}{text}{Colors.ENDC}"


def print_separator(char: str = "─", width: int = 70):
    print(char * width)


def print_header(title: str, color: str = Colors.CYAN):
    print()
    print_separator("═")
    print(f"  {colorize(title, Colors.BOLD + color)}")
    print_separator("═")


# ============================================================================
# 撤销导入功能
# ============================================================================


def undo_import(work_id: int, env_mode: str = "dev") -> bool:
    """
    撤销导入，删除作品及其所有相关数据

    Args:
        work_id: 作品ID
        env_mode: 环境模式 (dev/prod)

    Returns:
        是否成功删除
    """
    print_header("撤销导入", Colors.RED)

    # 设置环境并加载模型
    read_env(env_mode)
    Database, Work, Edition, DocumentNode = get_db_models()
    db = Database.get_instance().get_db_session()

    try:
        # 查询作品
        work = db.query(Work).filter(Work.id == work_id).first()

        if not work:
            print(colorize(f"❌ 未找到作品 ID: {work_id}", Colors.RED))
            return False

        # 显示作品信息
        print(f"作品标题: {colorize(work.title, Colors.BOLD)}")
        print(f"作者: {work.author or 'N/A'}")

        # 统计相关信息
        edition_count = db.query(Edition).filter(Edition.work_id == work_id).count()
        chapter_count = (
            db.query(DocumentNode)
            .join(Edition)
            .filter(Edition.work_id == work_id)
            .count()
        )

        print(f"关联版本数: {edition_count}")
        print(f"关联章节数: {chapter_count}")
        print()

        # 确认删除
        print(colorize("⚠️  警告: 此操作将永久删除以上所有数据！", Colors.YELLOW))
        confirm = input(colorize("确认删除? 请输入 'delete' 确认: ", Colors.RED))

        if confirm != "delete":
            print(colorize("❌ 已取消删除", Colors.YELLOW))
            return False

        # 执行删除（级联删除会自动处理 editions 和 document_nodes）
        db.delete(work)
        db.commit()

        print(colorize(f"✅ 成功删除作品 ID {work_id} 及其所有相关数据", Colors.GREEN))
        return True

    except Exception as e:
        db.rollback()
        print(colorize(f"❌ 删除失败: {e}", Colors.RED))
        return False
    finally:
        db.close()


# ============================================================================
# 章节解析和异常检测
# ============================================================================

DEFAULT_CHAPTER_PATTERNS = [
    r"^第[一二三四五六七八九十百千万零〇\d]+章[^\n]*",
    r"^第[一二三四五六七八九十百千万零〇\d]+节[^\n]*",
    r"^Chapter\s+\d+[^\n]*",
    r"^CHAPTER\s+\d+[^\n]*",
    r"^\d+\.\s+[^\n]+",
    r"^【[^\】]+】",
]


def read_file_with_encoding(file_path: str) -> Tuple[str, str]:
    """读取文件并自动检测编码"""
    encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "gb2312", "utf-16", "big5"]

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            return content, encoding
        except (UnicodeDecodeError, UnicodeError):
            continue

    raise ValueError(f"无法解析文件编码: {file_path}")


def parse_chapters(
    content: str, pattern: Optional[str] = None
) -> List[Tuple[str, str, int, int]]:
    """
    解析章节

    Returns:
        [(title, content, start_pos, end_pos), ...]
    """
    if not content:
        return []

    patterns = [pattern] if pattern else DEFAULT_CHAPTER_PATTERNS
    combined_pattern = "|".join(f"({p})" for p in patterns)

    matches = list(re.finditer(combined_pattern, content, re.MULTILINE))

    if not matches:
        return [("正文", content.strip(), 0, len(content))]

    chapters = []
    for i, match in enumerate(matches):
        title = match.group().strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        chapter_content = content[match.end() : end].strip()
        chapters.append((title, chapter_content, start, end))

    return chapters


@dataclass
class ChapterAnomaly:
    """章节异常信息"""

    index: int
    title: str
    char_count: int
    expected_chapters: int  # 预计包含的章节数
    content_preview: str
    issues: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """分析结果"""

    total_chapters: int
    total_chars: int
    avg_chars: int
    min_chars: int
    max_chars: int
    anomalies: List[ChapterAnomaly]
    normal_chapters: List[Tuple[int, str, int]]  # (index, title, char_count)


def analyze_chapters(chapters: List[Tuple[str, str, int, int]]) -> AnalysisResult:
    """
    分析章节，检测异常
    """
    if not chapters:
        return AnalysisResult(0, 0, 0, 0, 0, [], [])

    char_counts = [len(c[1]) for c in chapters]
    total_chars = sum(char_counts)
    avg_chars = total_chars // len(chapters)
    min_chars = min(char_counts)
    max_chars = max(char_counts)

    # 计算标准差
    if len(char_counts) > 1:
        try:
            std = stdev(char_counts)
        except:
            std = 0
    else:
        std = 0

    # 检测异常阈值
    # 正常网络小说章节：3000-10000字
    # 超长：超过平均值的5倍或超过10万字
    # 超短：少于平均值的一半或少于500字
    super_long_threshold = min(avg_chars * 5, 100000)
    super_long_threshold = max(super_long_threshold, 50000)  # 至少5万字才算超长

    super_short_threshold = max(avg_chars * 0.3, 500)

    anomalies = []
    normal_chapters = []

    for i, (title, content, start, end) in enumerate(chapters):
        char_count = len(content)
        issues = []

        # 检测超长
        if char_count > super_long_threshold:
            expected = max(1, char_count // avg_chars)
            issues.append(f"超长章节: {char_count:,} 字 (平均 {avg_chars:,} 字)")
            issues.append(f"预计包含 {expected} 个正常章节")

            anomalies.append(
                ChapterAnomaly(
                    index=i,
                    title=title,
                    char_count=char_count,
                    expected_chapters=expected,
                    content_preview=content[:200].replace("\n", " "),
                    issues=issues,
                )
            )
        # 检测超短
        elif char_count < super_short_threshold:
            issues.append(f"超短章节: {char_count:,} 字")

            anomalies.append(
                ChapterAnomaly(
                    index=i,
                    title=title,
                    char_count=char_count,
                    expected_chapters=1,
                    content_preview=content[:200].replace("\n", " "),
                    issues=issues,
                )
            )
        else:
            normal_chapters.append((i, title, char_count))

    return AnalysisResult(
        total_chapters=len(chapters),
        total_chars=total_chars,
        avg_chars=avg_chars,
        min_chars=min_chars,
        max_chars=max_chars,
        anomalies=anomalies,
        normal_chapters=normal_chapters,
    )


def deep_parse_long_chapter(title: str, content: str) -> List[Tuple[str, str]]:
    """
    深度解析超长章节，尝试拆分

    返回: [(sub_title, sub_content), ...]
    """
    # 尝试更严格的章节匹配
    # 有些文件使用 "第XXX章" 但可能格式不标准

    # 模式1: 标准第X章
    pattern1 = r"第[一二三四五六七八九十百千万零〇\d]+章[^\n]*"

    # 模式2: 数字章节 (1. 或 1、)
    pattern2 = r"^\d+[\.、]\s*[^\n]+"

    # 模式3: 可能缺失"第"字的章节
    pattern3 = r"^[一二三四五六七八九十百千万零〇\d]+章[^\n]*"

    sub_chapters = []

    for pattern in [pattern1, pattern2, pattern3]:
        matches = list(re.finditer(pattern, content, re.MULTILINE))
        if len(matches) > 1:
            # 找到了子章节
            for i, match in enumerate(matches):
                sub_title = match.group().strip()
                start = match.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
                sub_content = content[start:end].strip()
                sub_chapters.append((sub_title, sub_content))
            break

    # 如果没找到子章节，尝试按段落数估算
    if not sub_chapters and len(content) > 50000:
        paragraphs = [p for p in content.split("\n\n") if p.strip()]
        # 如果段落很多，可能是格式问题
        if len(paragraphs) > 100:
            sub_chapters.append((title, content))
            sub_chapters.append(
                ("(注意)", "该章节内容超长，但未检测到子章节结构，可能是格式异常")
            )

    if not sub_chapters:
        sub_chapters.append((title, content))

    return sub_chapters


# ============================================================================
# 分析和展示
# ============================================================================


def print_analysis(result: AnalysisResult):
    """打印分析结果"""
    print_header("章节分析结果")

    print_separator()
    print(f"  总章节数: {colorize(str(result.total_chapters), Colors.GREEN)}")
    print(f"  总字数: {colorize(f'{result.total_chars:,}', Colors.GREEN)}")
    print(f"  平均每章: {colorize(f'{result.avg_chars:,}', Colors.BLUE)} 字")
    print(f"  最短: {colorize(f'{result.min_chars:,}', Colors.YELLOW)} 字")
    print(f"  最长: {colorize(f'{result.max_chars:,}', Colors.YELLOW)} 字")
    print_separator()

    # 异常章节
    if result.anomalies:
        print()
        print_header(f"⚠️ 检测到 {len(result.anomalies)} 个异常章节", Colors.RED)

        for anomaly in result.anomalies:
            print()
            print(
                f"  {colorize(f'[{anomaly.index}]', Colors.YELLOW)} {colorize(anomaly.title, Colors.BOLD)}"
            )
            print(f"      字数: {colorize(f'{anomaly.char_count:,}', Colors.RED)}")
            for issue in anomaly.issues:
                print(f"      {colorize('! ' + issue, Colors.RED)}")
            print(f"      预览: {anomaly.content_preview[:100]}...")

            # 如果是超长章节，尝试深度解析
            if anomaly.char_count > 50000:
                print()
                print(f"      {colorize('>>> 尝试深度解析...', Colors.CYAN)}")
    else:
        print()
        print(colorize("✅ 未检测到异常章节", Colors.GREEN))

    # 正常章节样本
    print()
    print_header("正常章节样本")
    sample_count = min(5, len(result.normal_chapters))
    for i, title, char_count in result.normal_chapters[:sample_count]:
        print(f"  [{i}] {title[:40]} ({char_count:,} 字)")


def interactive_fix_long_chapter(title: str, content: str) -> List[Tuple[str, str]]:
    """
    交互式修复超长章节

    返回拆分后的子章节列表
    """
    print()
    print_header(f"修复超长章节: {title}", Colors.YELLOW)
    print(f"当前字数: {colorize(f'{len(content):,}', Colors.RED)} 字")
    print()

    # 先尝试自动解析
    sub_chapters = deep_parse_long_chapter(title, content)

    if len(sub_chapters) > 1:
        print(colorize(f"✓ 自动检测到 {len(sub_chapters)} 个子章节:", Colors.GREEN))
        for i, (sub_title, sub_content) in enumerate(sub_chapters[:10]):
            print(f"  [{i}] {sub_title[:50]} ({len(sub_content):,} 字)")
        if len(sub_chapters) > 10:
            print(f"  ... 还有 {len(sub_chapters) - 10} 个子章节")

        confirm = (
            input(colorize("\n是否使用此拆分方案? (y/n): ", Colors.YELLOW))
            .strip()
            .lower()
        )
        if confirm in ["y", "yes", "是"]:
            return sub_chapters

    # 手动拆分
    print()
    print("尝试在以下内容中查找章节边界...")
    print("章节开头预览 (前500字符):")
    print_separator()
    print(content[:500])
    print_separator()
    print()
    print("章节结尾预览 (后500字符):")
    print_separator()
    print(content[-500:])
    print_separator()

    # 询问处理方式
    print()
    print("选择处理方式:")
    print("  1. 保持原样 (不拆分)")
    print("  2. 按字数大致均分")
    print("  3. 输入自定义正则表达式拆分")

    choice = input(colorize("选择 (1/2/3): ", Colors.CYAN)).strip()

    if choice == "1":
        return [(title, content)]

    elif choice == "2":
        # 大致均分
        avg_len = len(content) // 3
        parts = []
        for i in range(3):
            start = i * avg_len
            end = (i + 1) * avg_len if i < 2 else len(content)
            part_content = content[start:end]
            part_title = f"{title} (部分{i + 1})"
            parts.append((part_title, part_content))
        return parts

    elif choice == "3":
        custom_pattern = input(colorize("输入正则表达式: ", Colors.CYAN)).strip()
        try:
            matches = list(re.finditer(custom_pattern, content, re.MULTILINE))
            if len(matches) > 1:
                parts = []
                for i, match in enumerate(matches):
                    part_title = match.group().strip()
                    start = match.start()
                    end = (
                        matches[i + 1].start() if i + 1 < len(matches) else len(content)
                    )
                    part_content = content[start:end].strip()
                    parts.append((part_title, part_content))
                print(colorize(f"✓ 使用正则拆分为 {len(parts)} 个部分", Colors.GREEN))
                return parts
            else:
                print(colorize("❌ 正则表达式未找到足够的匹配", Colors.RED))
                return [(title, content)]
        except re.error as e:
            print(colorize(f"❌ 正则表达式错误: {e}", Colors.RED))
            return [(title, content)]

    return [(title, content)]


# ============================================================================
# 安全导入
# ============================================================================


def safe_import(
    file_path: str,
    title: str,
    author: Optional[str],
    env_mode: str = "dev",
    auto_fix: bool = False,
):
    """
    安全导入流程：
    1. 预览分析
    2. 检测异常
    3. 用户确认
    4. 修复异常
    5. 导入
    """
    print_header("安全导入模式")

    # 读取文件
    print(f"读取文件: {file_path}")
    content, encoding = read_file_with_encoding(file_path)
    print(f"编码: {encoding}, 大小: {len(content):,} 字符")

    # 解析章节
    print("解析章节...")
    chapters = parse_chapters(content)
    print(f"初步识别: {len(chapters)} 个章节")

    # 分析异常
    analysis = analyze_chapters(chapters)
    print_analysis(analysis)

    # 如果有异常，询问处理方式
    if analysis.anomalies:
        print()
        print_header("需要处理异常章节", Colors.RED)

        if auto_fix:
            print("自动修复模式...")
        else:
            confirm = (
                input(
                    colorize(
                        "\n是否继续导入? (y=是/n=否/f=尝试自动修复): ", Colors.YELLOW
                    )
                )
                .strip()
                .lower()
            )

            if confirm == "n":
                print(colorize("❌ 已取消导入", Colors.YELLOW))
                return
            elif confirm == "f":
                auto_fix = True

        # 修复异常
        if auto_fix:
            fixed_chapters = []
            for i, (title, content, start, end) in enumerate(chapters):
                char_count = len(content)

                # 检测是否为超长章节
                if char_count > 50000:
                    sub_chapters = interactive_fix_long_chapter(title, content)
                    fixed_chapters.extend(sub_chapters)
                else:
                    fixed_chapters.append((title, content))

            print()
            print_header("修复后章节统计")
            print(f"原章节数: {len(chapters)}")
            print(f"修复后章节数: {len(fixed_chapters)}")

            # 重新构建 chapters 格式
            chapters = []
            for title, content in fixed_chapters:
                chapters.append((title, content, 0, len(content)))

            # 再次分析
            analysis = analyze_chapters(chapters)
            if analysis.anomalies:
                print(
                    colorize(
                        f"⚠️ 仍有 {len(analysis.anomalies)} 个异常章节", Colors.YELLOW
                    )
                )

    # 最终确认
    print()
    print_header("导入前最终确认")
    print(f"作品标题: {colorize(title, Colors.BOLD)}")
    print(f"作者: {author or 'N/A'}")
    print(f"章节数: {colorize(str(len(chapters)), Colors.GREEN)}")
    print(f"总字数: {colorize(f'{sum(len(c[1]) for c in chapters):,}', Colors.GREEN)}")

    final_confirm = (
        input(colorize("\n确认导入到数据库? (y/n): ", Colors.YELLOW)).strip().lower()
    )

    if final_confirm not in ["y", "yes", "是"]:
        print(colorize("❌ 已取消导入", Colors.YELLOW))
        return

    # 执行导入
    print()
    print_header("开始导入...")

    # 设置环境并加载模型
    read_env(env_mode)
    Database, Work, Edition, DocumentNode = get_db_models()
    db = Database.get_instance().get_db_session()

    try:
        from sail_server.model.text import import_text_impl
        from sail_server.data.text import TextImportRequest

        # 构建请求
        request = TextImportRequest(
            work_title=title,
            content=content,
            work_author=author,
            edition_name="安全导入",
            language="zh",
        )

        work_data, edition_data, chapter_count = import_text_impl(db, request)

        print()
        print(colorize("✅ 导入成功!", Colors.GREEN))
        print_separator()
        print(f"  作品 ID: {work_data.id}")
        print(f"  版本 ID: {edition_data.id}")
        print(f"  章节数: {chapter_count}")
        print(f"  总字数: {edition_data.char_count:,}")
        print_separator()

    except Exception as e:
        db.rollback()
        print(colorize(f"❌ 导入失败: {e}", Colors.RED))
        import traceback

        traceback.print_exc()
    finally:
        db.close()


# ============================================================================
# 主函数
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="文本导入管理工具 - 撤销导入、分析异常、安全导入",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 撤销导入（删除作品及其所有数据）
  python text_import_manager.py --undo --work-id 9
  
  # 分析文件章节
  python text_import_manager.py --analyze novel.txt
  
  # 安全导入（带异常检测和用户确认）
  python text_import_manager.py --safe-import novel.txt --title "求魔" --author "耳根"
  
  # 安全导入（自动修复异常）
  python text_import_manager.py --safe-import novel.txt --title "求魔" --author "耳根" --auto-fix
        """,
    )

    # 操作模式
    parser.add_argument("--undo", action="store_true", help="撤销导入模式")
    parser.add_argument("--work-id", type=int, help="作品ID（用于撤销导入）")

    parser.add_argument("--analyze", dest="analyze_file", type=str, help="分析文件章节")

    parser.add_argument(
        "--safe-import", dest="import_file", type=str, help="安全导入文件"
    )
    parser.add_argument("--title", type=str, help="作品标题")
    parser.add_argument("--author", type=str, help="作者名")
    parser.add_argument("--auto-fix", action="store_true", help="自动修复异常章节")

    # 环境
    parser.add_argument("--prod", action="store_true", help="使用生产环境")

    args = parser.parse_args()

    # 确定环境
    env_mode = "prod" if args.prod else "dev"

    # 执行操作
    if args.undo:
        if not args.work_id:
            print(colorize("❌ 请指定 --work-id", Colors.RED))
            sys.exit(1)
        undo_import(args.work_id, env_mode)

    elif args.analyze_file:
        print_header("章节分析模式")
        content, encoding = read_file_with_encoding(args.analyze_file)
        print(f"文件: {args.analyze_file}")
        print(f"编码: {encoding}")
        print(f"大小: {len(content):,} 字符")

        chapters = parse_chapters(content)
        analysis = analyze_chapters(chapters)
        print_analysis(analysis)

    elif args.import_file:
        if not args.title:
            args.title = Path(args.import_file).stem
        safe_import(args.import_file, args.title, args.author, env_mode, args.auto_fix)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
