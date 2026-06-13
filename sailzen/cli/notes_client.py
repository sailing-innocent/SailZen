# -*- coding: utf-8 -*-
# @file notes_client.py
# @brief NotesClient CLI - 直接管理本地 git 托管的 Markdown 笔记库
# @author sailing-innocent
# @date 2026-07-13
# @version 1.0
# ---------------------------------

"""
NotesClient CLI 工具

核心理念: Notes are notes. Databases are databases.
- 笔记就是本地的 Markdown 文件，用 git 管理。
- 本模块直接读写 vault 目录下的 .md 文件，不经过关系型数据库。
- 可选与 Vault API Server 交互，但默认操作本地文件系统。

笔记格式 (Sail 风格):
  - 文件名即 note id / fname，如 daily.2026-07-13.md
  - 文件头部可选 YAML frontmatter: id, title, tags, created, updated
  - 正文为 Markdown

环境变量:
  - NOTES_VAULT_ROOT: 笔记库根目录

用法示例:
  sailzen notes list --vault ./notes
  sailzen notes get daily.2026-07-13 --vault ./notes
  sailzen notes new daily.2026-07-13 --title "今日记录" --body "..."
  sailzen notes search python --vault ./notes
  sailzen notes status --vault ./notes
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml


# ============================================================================
# Constants
# ============================================================================

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
NOTE_EXT = ".md"


# ============================================================================
# Note Model
# ============================================================================


@dataclass
class Note:
    """本地 Markdown 笔记"""

    fname: str  # 文件标识，如 "daily.2026-07-13"
    title: str = ""
    body: str = ""
    id: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    created: Optional[str] = None
    updated: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def filename(self) -> str:
        return f"{self.fname}{NOTE_EXT}"

    def to_markdown(self) -> str:
        """序列化为带 YAML frontmatter 的 Markdown"""
        front = {
            "id": self.id or self.fname,
            "title": self.title or self.fname,
            "tags": self.tags,
            "created": self.created or _now_iso(),
            "updated": _now_iso(),
        }
        # 合并额外元数据
        for k, v in self.meta.items():
            if k not in front:
                front[k] = v
        yaml_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False)
        return f"---\n{yaml_text}---\n\n{self.body.lstrip()}"


# ============================================================================
# NotesClient
# ============================================================================


class NotesClient:
    """本地 Markdown 笔记库客户端"""

    def __init__(self, vault_root: str):
        self.vault_root = Path(vault_root).expanduser().resolve()
        if not self.vault_root.exists():
            raise FileNotFoundError(f"Vault root does not exist: {self.vault_root}")
        if not self.vault_root.is_dir():
            raise NotADirectoryError(f"Vault root is not a directory: {self.vault_root}")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _note_path(self, fname: str) -> Path:
        """根据 fname 定位文件（支持子目录，如 seeds.python）"""
        rel = fname.replace(".", os.sep) + NOTE_EXT
        return self.vault_root / rel

    @staticmethod
    def _fname_from_path(vault_root: Path, path: Path) -> str:
        """从文件路径还原 fname"""
        rel = path.relative_to(vault_root).with_suffix("")
        return str(rel).replace(os.sep, ".")

    # ------------------------------------------------------------------
    # Read / Write
    # ------------------------------------------------------------------

    def list_notes(self, prefix: Optional[str] = None) -> list[Note]:
        """列出所有笔记（只读元数据，不加载正文）"""
        notes: list[Note] = []
        for path in sorted(self.vault_root.rglob(f"*{NOTE_EXT}")):
            fname = self._fname_from_path(self.vault_root, path)
            if prefix and not fname.startswith(prefix):
                continue
            note = self._parse_meta_only(path, fname)
            if note:
                notes.append(note)
        return notes

    def get(self, fname: str) -> Optional[Note]:
        """获取单条完整笔记"""
        path = self._note_path(fname)
        if not path.exists():
            return None
        return self._parse_full(path, fname)

    def write(self, note: Note, create_dirs: bool = True) -> Path:
        """写入笔记"""
        path = self._note_path(note.fname)
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(note.to_markdown(), encoding="utf-8")
        return path

    def delete(self, fname: str) -> bool:
        """删除笔记"""
        path = self._note_path(fname)
        if not path.exists():
            return False
        path.unlink()
        # 清理空目录
        self._cleanup_empty_dirs(path.parent)
        return True

    def search(self, keyword: str) -> list[tuple[str, str]]:
        """在笔记文件名和正文中搜索关键字"""
        results: list[tuple[str, str]] = []
        lower_kw = keyword.lower()
        for path in sorted(self.vault_root.rglob(f"*{NOTE_EXT}")):
            fname = self._fname_from_path(self.vault_root, path)
            if lower_kw in fname.lower():
                results.append((fname, "fname"))
                continue
            try:
                text = path.read_text(encoding="utf-8").lower()
                if lower_kw in text:
                    results.append((fname, "body"))
            except Exception:
                continue
        return results

    def git_status(self) -> dict[str, Any]:
        """返回 vault 的 git 状态摘要"""
        result: dict[str, Any] = {"is_git_repo": False, "branch": None, "dirty": False, "summary": ""}
        git_dir = self.vault_root / ".git"
        if not git_dir.exists():
            return result
        result["is_git_repo"] = True
        try:
            result["branch"] = _git_capture(self.vault_root, ["branch", "--show-current"])
            status_text = _git_capture(self.vault_root, ["status", "--short"])
            result["summary"] = status_text
            result["dirty"] = bool(status_text.strip())
        except Exception as exc:
            result["error"] = str(exc)
        return result

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_full(self, path: Path, fname: str) -> Note:
        text = path.read_text(encoding="utf-8")
        meta, body = self._split_frontmatter(text)
        return Note(
            fname=fname,
            title=meta.get("title", fname),
            body=body,
            id=meta.get("id"),
            tags=meta.get("tags", []),
            created=meta.get("created"),
            updated=meta.get("updated"),
            meta={k: v for k, v in meta.items() if k not in {"id", "title", "tags", "created", "updated"}},
        )

    def _parse_meta_only(self, path: Path, fname: str) -> Optional[Note]:
        try:
            text = path.read_text(encoding="utf-8")
            meta, body = self._split_frontmatter(text)
            return Note(
                fname=fname,
                title=meta.get("title", fname),
                body="",
                id=meta.get("id"),
                tags=meta.get("tags", []),
                created=meta.get("created"),
                updated=meta.get("updated"),
            )
        except Exception:
            return None

    @staticmethod
    def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
        match = FRONTMATTER_RE.match(text)
        if not match:
            return {}, text
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except Exception:
            meta = {}
        body = text[match.end():]
        return meta, body

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup_empty_dirs(self, directory: Path) -> None:
        """删除空目录（直到 vault_root 为止）"""
        try:
            for parent in [directory, *directory.parents]:
                if parent == self.vault_root:
                    break
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
        except Exception:
            pass


# ============================================================================
# Helpers
# ============================================================================


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _resolve_vault_root(args) -> str:
    """解析 vault 根目录"""
    root = args.vault or os.environ.get("NOTES_VAULT_ROOT", "")
    if not root:
        print("❌ 必须指定 --vault 或设置环境变量 NOTES_VAULT_ROOT", file=sys.stderr)
        sys.exit(1)
    return root


def _make_client(args) -> NotesClient:
    root = _resolve_vault_root(args)
    try:
        return NotesClient(root)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)


def _git_capture(cwd: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


# ============================================================================
# CLI Commands
# ============================================================================


def cmd_list(args):
    """列出笔记"""
    client = _make_client(args)
    notes = client.list_notes(prefix=args.prefix)
    if not notes:
        print("(vault 为空)")
        return
    print(f"{'fname':<40} {'title':<30} {'updated':<20}")
    print("-" * 90)
    for note in notes:
        title = (note.title or "")[:28]
        updated = note.updated or ""
        print(f"{note.fname:<40} {title:<30} {updated:<20}")


def cmd_get(args):
    """获取单条笔记"""
    client = _make_client(args)
    note = client.get(args.fname)
    if note is None:
        print(f"❌ 笔记不存在: {args.fname}", file=sys.stderr)
        sys.exit(1)
    if args.body_only:
        print(note.body)
        return
    if args.json:
        print(json.dumps(_note_to_dict(note), ensure_ascii=False, indent=2))
        return
    print(f"fname  : {note.fname}")
    print(f"id     : {note.id or note.fname}")
    print(f"title  : {note.title}")
    print(f"tags   : {', '.join(note.tags)}")
    print(f"created: {note.created or ''}")
    print(f"updated: {note.updated or ''}")
    print()
    print("--- body ---")
    print(note.body)


def cmd_new(args):
    """新建笔记"""
    client = _make_client(args)
    if client.get(args.fname):
        print(f"❌ 笔记已存在: {args.fname}", file=sys.stderr)
        print("   如需覆盖请使用 write 子命令。", file=sys.stderr)
        sys.exit(1)
    note = Note(
        fname=args.fname,
        title=args.title or args.fname,
        body=args.body or "",
        tags=_parse_tags(args.tags),
    )
    path = client.write(note)
    print(f"✅ 创建笔记: {path}")


def cmd_write(args):
    """写入/更新笔记"""
    client = _make_client(args)
    body = args.body
    if args.file:
        if not os.path.exists(args.file):
            print(f"❌ 文件不存在: {args.file}", file=sys.stderr)
            sys.exit(1)
        body = Path(args.file).read_text(encoding="utf-8")
    elif body is None:
        body = ""

    existing = client.get(args.fname)
    if existing:
        note = Note(
            fname=args.fname,
            title=args.title or existing.title,
            body=body if args.body is not None or args.file else existing.body,
            id=existing.id or args.fname,
            tags=_parse_tags(args.tags) if args.tags is not None else existing.tags,
            created=existing.created,
        )
    else:
        note = Note(
            fname=args.fname,
            title=args.title or args.fname,
            body=body,
            id=args.fname,
            tags=_parse_tags(args.tags),
        )
    path = client.write(note)
    action = "更新" if existing else "创建"
    print(f"✅ {action}笔记: {path}")


def cmd_delete(args):
    """删除笔记"""
    client = _make_client(args)
    if not args.yes:
        confirm = input(f"确认删除笔记 {args.fname}? [y/N] ").strip().lower()
        if confirm != "y":
            print("已取消")
            return
    if client.delete(args.fname):
        print(f"✅ 已删除: {args.fname}")
    else:
        print(f"❌ 笔记不存在: {args.fname}", file=sys.stderr)
        sys.exit(1)


def cmd_search(args):
    """搜索笔记"""
    client = _make_client(args)
    results = client.search(args.keyword)
    if not results:
        print("(无结果)")
        return
    print(f"找到 {len(results)} 条结果:\n")
    for fname, source in results:
        print(f"  [{source}] {fname}")


def cmd_status(args):
    """显示 vault 的 git 状态"""
    client = _make_client(args)
    status = client.git_status()
    if not status["is_git_repo"]:
        print("⚠️  该目录不是 git 仓库")
        return
    print(f"branch: {status['branch']}")
    print(f"dirty : {status['dirty']}")
    if status["summary"]:
        print("\n--- git status ---")
        print(status["summary"])
    else:
        print("工作区干净")


# ============================================================================
# CLI Helpers
# ============================================================================


def _parse_tags(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _note_to_dict(note: Note) -> dict[str, Any]:
    return {
        "fname": note.fname,
        "id": note.id or note.fname,
        "title": note.title,
        "tags": note.tags,
        "created": note.created,
        "updated": note.updated,
        "body": note.body,
    }


# ============================================================================
# Main Entry
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="NotesClient - 本地 Markdown 笔记库 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  sailzen notes list --vault ./notes
  sailzen notes list --prefix daily --vault ./notes
  sailzen notes get daily.2026-07-13 --vault ./notes
  sailzen notes new daily.2026-07-13 --title "今日记录" --body "学习了 DAG 调度"
  sailzen notes write daily.2026-07-13 --file entry.md
  sailzen notes search python --vault ./notes
  sailzen notes status --vault ./notes
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    def add_vault_arg(p):
        p.add_argument(
            "--vault",
            default=os.environ.get("NOTES_VAULT_ROOT", ""),
            help="笔记库根目录 (默认: NOTES_VAULT_ROOT 环境变量)",
        )

    # ---- list ----
    p_list = subparsers.add_parser("list", aliases=["ls"], help="列出笔记")
    add_vault_arg(p_list)
    p_list.add_argument("--prefix", default=None, help="按 fname 前缀过滤")
    p_list.set_defaults(func=cmd_list)

    # ---- get ----
    p_get = subparsers.add_parser("get", aliases=["g"], help="获取单条笔记")
    add_vault_arg(p_get)
    p_get.add_argument("fname", help="笔记 fname")
    p_get.add_argument("--body-only", action="store_true", help="只输出正文")
    p_get.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_get.set_defaults(func=cmd_get)

    # ---- new ----
    p_new = subparsers.add_parser("new", aliases=["n"], help="新建笔记")
    add_vault_arg(p_new)
    p_new.add_argument("fname", help="笔记 fname")
    p_new.add_argument("--title", default=None, help="标题")
    p_new.add_argument("--body", default=None, help="正文")
    p_new.add_argument("--tags", default=None, help="标签，逗号分隔")
    p_new.set_defaults(func=cmd_new)

    # ---- write ----
    p_write = subparsers.add_parser("write", aliases=["w"], help="写入/更新笔记")
    add_vault_arg(p_write)
    p_write.add_argument("fname", help="笔记 fname")
    p_write.add_argument("--title", default=None, help="标题")
    p_write.add_argument("--body", default=None, help="正文")
    p_write.add_argument("--file", "-f", default=None, help="从文件读取正文")
    p_write.add_argument("--tags", default=None, help="标签，逗号分隔")
    p_write.set_defaults(func=cmd_write)

    # ---- delete ----
    p_delete = subparsers.add_parser("delete", aliases=["d", "rm"], help="删除笔记")
    add_vault_arg(p_delete)
    p_delete.add_argument("fname", help="笔记 fname")
    p_delete.add_argument("--yes", "-y", action="store_true", help="跳过确认")
    p_delete.set_defaults(func=cmd_delete)

    # ---- search ----
    p_search = subparsers.add_parser("search", aliases=["s", "find"], help="搜索笔记")
    add_vault_arg(p_search)
    p_search.add_argument("keyword", help="关键字")
    p_search.set_defaults(func=cmd_search)

    # ---- status ----
    p_status = subparsers.add_parser("status", aliases=["st"], help="git 状态")
    add_vault_arg(p_status)
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
