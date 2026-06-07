# -*- coding: utf-8 -*-
# @file journal_fetcher.py
# @brief 日记检索器 —— 只收集原文，不做任何筛选或分析
# @author sailing-innocent
# @date 2026-06-07
# @version 2.0
# ---------------------------------
"""
日记检索器（纯工具层）

职责：
1. 按时间范围查找日记文件
2. 提取日记的原始内容（保留完整文本，不做关键词提取）
3. 输出按日期排列的原始日记段落

不做：
- 不做关键词提取
- 不做情绪统计
- 不做事件分类
- 不生成任何结论

输出格式：
{
  "period": "2025-01-01 ~ 2025-01-31",
  "journal_dir": "D:/ws/vault/notes",
  "total_days_in_period": 31,
  "days_with_journal": 15,
  "coverage_rate": 48.4,
  "entries": [
    {
      "date": "2025-01-07",
      "file": "journal.daily.2025.01.07.md",
      "title": "2025-01-07",
      "content": "...完整原文..."
    }
  ],
  "missing_dates": ["2025-01-02", "2025-01-03", ...]
}

使用方式：
    python journal_fetcher.py --journal-dir D:/ws/vault/notes \
        --start 2025-01-01 --end 2025-01-31 \
        --output journal_raw.json
"""

from __future__ import annotations

import argparse
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from common import find_journal_files, write_json


@dataclass
class JournalEntry:
    date: str
    file: str
    title: str
    content: str = ""  # 完整原文（去除 YAML front matter）


@dataclass
class JournalCollection:
    period: str = ""
    journal_dir: str = ""
    total_days_in_period: int = 0
    days_with_journal: int = 0
    coverage_rate: float = 0.0
    entries: list[JournalEntry] = field(default_factory=list)
    missing_dates: list[str] = field(default_factory=list)
    note: str = ""  # 数据完整性说明


# YAML front matter 正则
YAML_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def strip_front_matter(content: str) -> str:
    """去除 YAML front matter，保留正文"""
    match = YAML_FRONT_MATTER.match(content)
    if match:
        return content[match.end():].strip()
    return content.strip()


def extract_title_from_yaml(content: str) -> str:
    """从 YAML front matter 提取 title"""
    match = YAML_FRONT_MATTER.match(content)
    if match:
        yaml_text = match.group(1)
        title_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', yaml_text, re.MULTILINE)
        if title_match:
            return title_match.group(1).strip("'\"")
    return ""


class JournalFetcher:
    def __init__(self, journal_dir: str | Path):
        self.journal_dir = Path(journal_dir)

    def fetch(self, start: datetime, end: datetime, label: str = "") -> JournalCollection:
        files = find_journal_files(self.journal_dir, start, end)
        collection = JournalCollection(
            period=label or f"{start.date()} ~ {end.date()}",
            journal_dir=str(self.journal_dir),
            total_days_in_period=(end - start).days + 1,
            days_with_journal=len(files),
        )

        if collection.total_days_in_period > 0:
            collection.coverage_rate = collection.days_with_journal / collection.total_days_in_period * 100

        # 收集有日记的日期
        found_dates = set()
        for file_path in sorted(files):
            content = file_path.read_text(encoding="utf-8")
            title = extract_title_from_yaml(content)
            body = strip_front_matter(content)

            # 从文件名解析日期
            date_str = self._extract_date_from_filename(file_path)
            found_dates.add(date_str)

            collection.entries.append(JournalEntry(
                date=date_str,
                file=file_path.name,
                title=title or date_str,
                content=body,
            ))

        # 计算缺失日期
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            if date_str not in found_dates:
                collection.missing_dates.append(date_str)
            current += timedelta(days=1)

        # 数据完整性说明
        if collection.coverage_rate >= 80:
            collection.note = f"日记覆盖良好 ({collection.coverage_rate:.1f}%)"
        elif collection.coverage_rate >= 50:
            collection.note = f"日记覆盖一般 ({collection.coverage_rate:.1f}%)，部分日期缺失"
        else:
            collection.note = f"日记覆盖不足 ({collection.coverage_rate:.1f}%)，大量日期缺失，分析深度受限"

        return collection

    def _extract_date_from_filename(self, file_path: Path) -> str:
        name = file_path.stem
        parts = name.split(".")
        try:
            year = int(parts[2])
            month = int(parts[3]) if len(parts) > 3 else 1
            day = int(parts[4]) if len(parts) > 4 else 1
            return f"{year:04d}-{month:02d}-{day:02d}"
        except (ValueError, IndexError):
            return "unknown"


def main():
    parser = argparse.ArgumentParser(description="日记检索器 —— 只收集原文")
    parser.add_argument("--journal-dir", default="D:/ws/vault/notes")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", "-o", default="journal_raw.json")
    parser.add_argument("--max-length", type=int, default=50000, help="单条日记最大保留字符数")
    args = parser.parse_args()

    fetcher = JournalFetcher(args.journal_dir)
    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")

    collection = fetcher.fetch(start_dt, end_dt)

    # 截超长内容
    for entry in collection.entries:
        if len(entry.content) > args.max_length:
            entry.content = entry.content[:args.max_length] + f"\n\n... [截断，原文 {len(entry.content)} 字符]"

    def serialize(obj):
        if isinstance(obj, list):
            return [serialize(i) for i in obj]
        if hasattr(obj, "__dataclass_fields__"):
            return {k: serialize(v) for k, v in asdict(obj).items()}
        return obj

    write_json(args.output, serialize(collection))
    print(f"日记原始数据已输出: {args.output}")
    print(f"  时间范围: {collection.period}")
    print(f"  有记录: {collection.days_with_journal} / {collection.total_days_in_period} 天")
    print(f"  覆盖率: {collection.coverage_rate:.1f}%")
    print(f"  缺失: {len(collection.missing_dates)} 天")
    print(f"  备注: {collection.note}")


if __name__ == "__main__":
    main()
