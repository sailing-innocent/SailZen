# -*- coding: utf-8 -*-
# @file migrate_history_to_notes.py
# @brief 将 HistoryEvent / Person 结构化数据迁移为 NoteItem + Markdown 笔记
# @author sailing-innocent
# @date 2026-08-06
# @version 1.0
# ---------------------------------

"""
一次性迁移脚本：将旧 history_events / persons 表数据迁移到 note_items + .md 文件。

用法:
    cd SailZen
    $env:DB_BACKEND="postgres"  # 或 sqlite
    uv run scripts/migrate_history_to_notes.py --workspace ./data

说明:
- 每条 HistoryEvent 生成 notes/text/history/<id>_<slug>.md
- 每条 Person 生成 notes/text/persons/<id>_<slug>.md
- 创建对应 note_items 记录
- 旧表数据保留，便于回滚验证
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

# 设置编码
import os
os.environ["PGCLIENTENCODING"] = "UTF8"

from sail_server.db import get_db_session
from sail_server.infrastructure.orm.history import HistoryEvent, Person
from sail_server.infrastructure.orm.text import NoteItem
from sail_server.utils.note_links import make_note_slug


# ============================================================================
# Helpers
# ============================================================================


def _make_slug(title: str) -> str:
    slug = make_note_slug(title, max_length=60)
    if not slug:
        slug = "note"
    return slug


def _write_markdown(
    workspace: Path,
    category: str,
    slug: str,
    title: str,
    content: str,
    note_id: int,
    created: Optional[datetime] = None,
    updated: Optional[datetime] = None,
    tags: Optional[list[str]] = None,
) -> str:
    """写入 Markdown 文件并返回相对路径"""
    dir_name = "history" if category == "history" else "persons"
    setting_file = f"notes/text/{dir_name}/{slug}.md"
    file_path = workspace / setting_file
    file_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().isoformat(timespec="seconds")
    front = {
        "id": note_id,
        "category": category,
        "title": title,
        "slug": slug,
        "created": (created or datetime.now()).isoformat(timespec="seconds") if created else now,
        "updated": (updated or datetime.now()).isoformat(timespec="seconds") if updated else now,
    }
    if tags:
        front["tags"] = tags

    lines = ["---"]
    for k, v in front.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    md = "\n".join(lines) + "\n\n" + content.lstrip()
    file_path.write_text(md, encoding="utf-8")
    return setting_file


# ============================================================================
# Migration functions
# ============================================================================


def migrate_history_events(db: Session, workspace: Path, dry_run: bool = False) -> int:
    """迁移 HistoryEvent 表"""
    events = db.query(HistoryEvent).all()
    count = 0
    for event in events:
        slug = f"{event.id}_{_make_slug(event.title)}"
        title = event.title

        # 构造 Markdown 正文
        lines = [f"# {title}", ""]
        lines.append("## 描述")
        lines.append("")
        lines.append(event.description or "")
        lines.append("")
        if event.start_time:
            lines.append(f"- 开始时间: {event.start_time.isoformat()}")
        if event.end_time:
            lines.append(f"- 结束时间: {event.end_time.isoformat()}")
        if event.rar_tags:
            lines.append(f"- 手动标签: {', '.join(event.rar_tags)}")
        if event.tags:
            lines.append(f"- 机器标签: {', '.join(event.tags)}")
        if event.related_events:
            lines.append(f"- 相关事件: {event.related_events}")
        if event.parent_event:
            lines.append(f"- 父事件 ID: {event.parent_event}")
        if event.details:
            lines.append("")
            lines.append("## 详情")
            lines.append("")
            lines.append(str(event.details))
        content = "\n".join(lines)

        if dry_run:
            print(f"[DRY RUN] Would migrate HistoryEvent {event.id} -> {slug}.md")
            count += 1
            continue

        note = NoteItem(
            category="history",
            setting_file="",  # 临时，稍后更新
            title=title,
            slug=slug,
            meta_data={
                "old_id": event.id,
                "old_table": "history_events",
                "tags": list(event.tags or []),
            },
        )
        db.add(note)
        db.flush()

        setting_file = _write_markdown(
            workspace,
            "history",
            slug,
            title,
            content,
            note.id,
            created=event.receive_time,
            tags=list(event.rar_tags or []),
        )
        note.setting_file = setting_file
        db.commit()
        db.refresh(note)
        count += 1
        print(f"✅ Migrated HistoryEvent {event.id} -> NoteItem {note.id}: {setting_file}")

    return count


def migrate_persons(db: Session, workspace: Path, dry_run: bool = False) -> int:
    """迁移 Person 表"""
    persons = db.query(Person).all()
    count = 0
    for person in persons:
        slug = f"{person.id}_{_make_slug(person.name)}"
        title = person.name

        content = f"# {title}\n\n## 档案\n\n{person.data or ''}"

        if dry_run:
            print(f"[DRY RUN] Would migrate Person {person.id} -> {slug}.md")
            count += 1
            continue

        note = NoteItem(
            category="person",
            setting_file="",
            title=title,
            slug=slug,
            meta_data={
                "old_id": person.id,
                "old_table": "persons",
            },
        )
        db.add(note)
        db.flush()

        setting_file = _write_markdown(
            workspace,
            "person",
            slug,
            title,
            content,
            note.id,
            created=person.created_at,
            updated=person.updated_at,
        )
        note.setting_file = setting_file
        db.commit()
        db.refresh(note)
        count += 1
        print(f"✅ Migrated Person {person.id} -> NoteItem {note.id}: {setting_file}")

    return count


# ============================================================================
# Main
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Migrate HistoryEvent / Person to NoteItem + Markdown"
    )
    parser.add_argument(
        "--workspace",
        default=os.environ.get("SERVER_DATA_DIR", "data"),
        help="Note Markdown 文件输出根目录 (默认: data)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不实际写入",
    )
    parser.add_argument(
        "--only",
        choices=["history", "person", "all"],
        default="all",
        help="迁移范围",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    with get_db_session() as db:
        total = 0
        if args.only in ("history", "all"):
            total += migrate_history_events(db, workspace, dry_run=args.dry_run)
        if args.only in ("person", "all"):
            total += migrate_persons(db, workspace, dry_run=args.dry_run)

    action = "Would migrate" if args.dry_run else "Migrated"
    print(f"\n{action} {total} records to NoteItem + Markdown notes.")


if __name__ == "__main__":
    main()
