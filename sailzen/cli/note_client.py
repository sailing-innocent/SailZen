# -*- coding: utf-8 -*-
# @file note_client.py
# @brief NoteClient CLI - 通过 HTTP API 同步服务器 NoteItem 与本地 Markdown 文件
# @author sailing-innocent
# @date 2026-08-06
# @version 1.0
# ---------------------------------

"""
NoteClient CLI 工具

通过 sail_server 的 HTTP API 与远程服务器交互，管理 NoteItem 索引与本地 Markdown 文件：
1. 从服务器拉取 NoteItem 列表并在本地生成/更新 .md 文件
2. 扫描本地 Markdown 文件，同步到服务器（创建/更新 NoteItem）
3. 支持 list / pull / push / create / delete / sync / links 等子命令

API 端点：
- GET    /api/v1/text/note/                  列表
- POST   /api/v1/text/note/                  创建
- GET    /api/v1/text/note/{id}              获取索引
- PUT    /api/v1/text/note/{id}              更新索引
- DELETE /api/v1/text/note/{id}              删除索引
- GET    /api/v1/text/note/{id}/content      获取 Markdown 内容
- PUT    /api/v1/text/note/{id}/content      更新 Markdown 内容
- GET    /api/v1/text/note/links             获取双向链接图谱

环境变量：
- SAIL_SERVER_URL: 服务器地址
- NOTE_WORKSPACE_ROOT: 本地 note 工作区根目录（默认当前目录）
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
import yaml


# ============================================================================
# Environment / Server URL Resolution
# ============================================================================


def _load_env_file(env_path: str) -> dict:
    """手动解析 .env 文件"""
    env = {}
    if not os.path.isfile(env_path):
        return env
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                env[key] = value
    return env


def _resolve_default_server_url() -> str:
    """解析默认服务器地址"""
    env_url = os.environ.get("SAIL_SERVER_URL")
    if env_url:
        return env_url

    cwd = os.getcwd()
    for env_name in (".env.prod", ".env.dev", ".env"):
        env_path = os.path.join(cwd, env_name)
        if os.path.isfile(env_path):
            env = _load_env_file(env_path)
            host = env.get("SERVER_HOST", "localhost")
            port = env.get("SERVER_PORT", "8000")
            return f"http://{host}:{port}"

    return "http://localhost:8000"


DEFAULT_SERVER_URL = _resolve_default_server_url()


# ============================================================================
# Constants
# ============================================================================

API_TIMEOUT = 30
REQUEST_DELAY = 0.05
NOTE_EXT = ".md"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

CATEGORY_DIRS = {
    "character": "characters",
    "setting": "settings",
    "geography": "geography",
    "outline": "outlines",
    "plot": "plots",
    "history": "history",
    "person": "persons",
    "timeline": "timeline",
    "relationship": "relationship",
    "misc": "misc",
}

CSV_FIELDS = [
    "id",
    "category",
    "title",
    "slug",
    "setting_file",
    "work_id",
    "edition_id",
    "tags",
    "related",
]


# ============================================================================
# NoteItem Client
# ============================================================================


class NoteItemClient:
    """通过 HTTP API 与 sail_server 交互的 NoteItem 客户端"""

    def __init__(self, server_url: str, workspace_root: str):
        self.server_url = server_url.rstrip("/")
        self.base_api = f"{self.server_url}/api/v1/text/note"
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def list_notes(
        self,
        category: Optional[str] = None,
        work_id: Optional[int] = None,
        edition_id: Optional[int] = None,
    ) -> list[dict]:
        """获取 NoteItem 列表"""
        params: dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        if work_id is not None:
            params["work_id"] = work_id
        if edition_id is not None:
            params["edition_id"] = edition_id

        resp = self.session.get(self.base_api + "/", params=params, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("notes", [])

    def get_note(self, note_id: int) -> Optional[dict]:
        """获取单个 NoteItem"""
        url = f"{self.base_api}/{note_id}"
        resp = self.session.get(url, timeout=API_TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def create_note(self, data: dict) -> dict:
        """创建 NoteItem"""
        resp = self.session.post(self.base_api + "/", json=data, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def update_note(self, note_id: int, data: dict) -> dict:
        """更新 NoteItem 索引"""
        url = f"{self.base_api}/{note_id}"
        resp = self.session.put(url, json=data, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def delete_note(self, note_id: int) -> Optional[dict]:
        """删除 NoteItem"""
        url = f"{self.base_api}/{note_id}"
        resp = self.session.delete(url, timeout=API_TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def get_content(self, note_id: int) -> Optional[str]:
        """获取 Markdown 内容"""
        url = f"{self.base_api}/{note_id}/content"
        resp = self.session.get(url, timeout=API_TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("content", "")

    def update_content(self, note_id: int, content: str) -> dict:
        """更新 Markdown 内容"""
        url = f"{self.base_api}/{note_id}/content"
        resp = self.session.put(url, json={"content": content}, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def get_links(self) -> dict:
        """获取双向链接图谱"""
        url = f"{self.base_api}/links"
        resp = self.session.get(url, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    def _resolve_file_path(self, setting_file: str) -> Path:
        """将 setting_file 解析为本地绝对路径，限制在 workspace 内"""
        rel = setting_file
        if rel.startswith("/"):
            rel = rel.lstrip("/")
        target = (self.workspace_root / rel).resolve()
        try:
            target.relative_to(self.workspace_root.resolve())
        except ValueError:
            raise ValueError(f"Note file path outside workspace: {setting_file}")
        return target

    def _setting_file_for_path(self, file_path: Path) -> str:
        """从本地文件路径计算 setting_file"""
        rel = file_path.relative_to(self.workspace_root)
        return str(rel).replace("\\", "/")

    def read_local_note(self, file_path: Path) -> tuple[dict, str]:
        """读取本地 Markdown 文件，返回 (frontmatter, body)"""
        text = file_path.read_text(encoding="utf-8")
        return _split_frontmatter(text)

    def write_local_note(self, setting_file: str, content: str) -> Path:
        """写入本地 Markdown 文件"""
        file_path = self._resolve_file_path(setting_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        content = content.replace("\x00", "")
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def scan_local_notes(self, subdir: Optional[str] = None) -> list[Path]:
        """扫描本地所有 Markdown 笔记"""
        root = self.workspace_root
        if subdir:
            root = self.workspace_root / subdir
        if not root.exists():
            return []
        return sorted(root.rglob(f"*{NOTE_EXT}"))


# ============================================================================
# Helpers
# ============================================================================


def _split_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except Exception:
        meta = {}
    body = text[match.end() :]
    return meta, body


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _make_slug(title: str) -> str:
    slug = re.sub(r"\s+", "_", title.strip())
    slug = re.sub(r"[^\w\u4e00-\u9fff-_]", "", slug)
    return (slug or "note")[:80]


def _parse_tags(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _build_note_from_file(client: NoteItemClient, file_path: Path) -> dict:
    """从本地 Markdown 文件构建 NoteItem 数据"""
    meta, body = client.read_local_note(file_path)
    setting_file = client._setting_file_for_path(file_path)
    category = meta.get("category", _guess_category_from_path(setting_file)) or "misc"
    slug = meta.get("slug", Path(setting_file).stem)
    title = meta.get("title", slug)
    work_id = meta.get("work_id") or None
    edition_id = meta.get("edition_id") or None
    return {
        "category": category,
        "setting_file": setting_file,
        "title": title,
        "slug": slug,
        "work_id": int(work_id) if work_id is not None else None,
        "edition_id": int(edition_id) if edition_id is not None else None,
        "meta_data": meta,
    }


def _guess_category_from_path(setting_file: str) -> Optional[str]:
    """根据文件路径猜测 category"""
    parts = Path(setting_file).parts
    if len(parts) >= 2:
        dir_name = parts[-2]
        for cat, d in CATEGORY_DIRS.items():
            if d == dir_name:
                return cat
    return None


def _resolve_workspace(args) -> str:
    root = args.workspace or os.environ.get("NOTE_WORKSPACE_ROOT", ".")
    return root


def _make_client(args) -> NoteItemClient:
    return NoteItemClient(args.server, _resolve_workspace(args))


# ============================================================================
# CLI Commands
# ============================================================================


def cmd_list(args):
    """列出服务器上的 NoteItem"""
    client = _make_client(args)
    notes = client.list_notes(
        category=args.category,
        work_id=args.work_id,
        edition_id=args.edition_id,
    )
    if not notes:
        print("(无 NoteItem)")
        return

    print(f"{'ID':>6}  {'Category':<12}  {'Title':<30}  {'Setting File'}")
    print("-" * 100)
    for note in notes:
        title = (note.get("title") or "")[:28]
        print(
            f"{note.get('id', ''):>6}  "
            f"{note.get('category', ''):<12}  "
            f"{title:<30}  "
            f"{note.get('setting_file', '')}"
        )


def cmd_pull(args):
    """拉取 NoteItem 并在本地生成/更新 Markdown 文件"""
    client = _make_client(args)

    if args.id:
        note = client.get_note(args.id)
        if note is None:
            print(f"❌ NoteItem 不存在: {args.id}", file=sys.stderr)
            sys.exit(1)
        notes = [note]
    else:
        notes = client.list_notes(
            category=args.category,
            work_id=args.work_id,
            edition_id=args.edition_id,
        )

    for note in notes:
        note_id = note["id"]
        setting_file = note["setting_file"]
        content = client.get_content(note_id) or ""
        file_path = client.write_local_note(setting_file, content)
        print(f"✅ 拉取笔记 {note_id} -> {file_path}")
        time.sleep(REQUEST_DELAY)


def cmd_push(args):
    """扫描本地 Markdown 文件，同步到服务器"""
    client = _make_client(args)
    files = client.scan_local_notes(args.dir)

    for file_path in files:
        data = _build_note_from_file(client, file_path)
        existing = None
        # 尝试通过 setting_file 查找已有 NoteItem
        for note in client.list_notes():
            if note.get("setting_file") == data["setting_file"]:
                existing = note
                break

        content = file_path.read_text(encoding="utf-8")
        if existing:
            note_id = existing["id"]
            client.update_note(note_id, data)
            client.update_content(note_id, content)
            print(f"✅ 更新笔记 {note_id}: {data['setting_file']}")
        else:
            created = client.create_note(data)
            note_id = created["id"]
            client.update_content(note_id, content)
            print(f"✅ 创建笔记 {note_id}: {data['setting_file']}")
        time.sleep(REQUEST_DELAY)


def cmd_create(args):
    """创建新的 NoteItem + 空 Markdown 文件"""
    client = _make_client(args)
    category = args.category
    title = args.title
    slug = args.slug or _make_slug(title)
    dir_name = CATEGORY_DIRS.get(category, category)
    setting_file = f"notes/text/{dir_name}/{slug}.md"

    work_id = args.work_id
    edition_id = args.edition_id

    front = {
        "category": category,
        "title": title,
        "slug": slug,
        "created": _now_iso(),
        "updated": _now_iso(),
    }
    if args.tags:
        front["tags"] = _parse_tags(args.tags)
    if work_id:
        front["work_id"] = work_id
    if edition_id:
        front["edition_id"] = edition_id

    yaml_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False)
    content = f"---\n{yaml_text}---\n\n"

    data = {
        "category": category,
        "setting_file": setting_file,
        "title": title,
        "slug": slug,
        "work_id": work_id,
        "edition_id": edition_id,
        "meta_data": front,
    }

    created = client.create_note(data)
    note_id = created["id"]
    client.update_content(note_id, content)
    file_path = client.write_local_note(setting_file, content)
    print(f"✅ 创建笔记 {note_id}: {file_path}")


def cmd_delete(args):
    """删除 NoteItem 及对应文件"""
    client = _make_client(args)
    note = client.get_note(args.id)
    if note is None:
        print(f"❌ NoteItem 不存在: {args.id}", file=sys.stderr)
        sys.exit(1)

    if not args.yes:
        confirm = input(f"确认删除 NoteItem {args.id} [{note.get('setting_file')}]? [y/N] ").strip().lower()
        if confirm != "y":
            print("已取消")
            return

    client.delete_note(args.id)
    if not args.keep_file:
        try:
            file_path = client._resolve_file_path(note["setting_file"])
            if file_path.exists():
                file_path.unlink()
                print(f"✅ 已删除文件: {file_path}")
        except Exception as e:
            print(f"⚠️ 删除文件失败: {e}", file=sys.stderr)
    print(f"✅ 已删除 NoteItem: {args.id}")


def cmd_sync(args):
    """双向同步：pull + push"""
    print("--- pull ---")
    cmd_pull(args)
    print("--- push ---")
    cmd_push(args)


def cmd_links(args):
    """分析/重建双向链接索引"""
    client = _make_client(args)
    graph = client.get_links()
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    print(f"节点数: {len(nodes)}, 链接数: {len(edges)}")
    if args.json:
        print(json.dumps(graph, ensure_ascii=False, indent=2))
        return
    print("\n--- nodes ---")
    for node in nodes:
        print(f"  [{node.get('id')}] {node.get('slug')} ({node.get('title')})")
    print("\n--- edges ---")
    for edge in edges:
        print(f"  {edge.get('source')} -> {edge.get('target')} [{edge.get('display')}]")


def cmd_export_csv(args):
    """导出 NoteItem 到 CSV（用于批量编辑）"""
    client = _make_client(args)
    notes = client.list_notes(
        category=args.category,
        work_id=args.work_id,
        edition_id=args.edition_id,
    )
    if not notes:
        print("(无 NoteItem)")
        return

    csv_path = args.output or "notes.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for note in notes:
            meta = note.get("meta_data", {}) or {}
            row = {
                "id": note.get("id"),
                "category": note.get("category"),
                "title": note.get("title"),
                "slug": note.get("slug"),
                "setting_file": note.get("setting_file"),
                "work_id": note.get("work_id"),
                "edition_id": note.get("edition_id"),
                "tags": ",".join(meta.get("tags", [])),
                "related": ",".join(meta.get("related", [])),
            }
            writer.writerow(row)
    print(f"✅ 导出 {len(notes)} 条记录到 {csv_path}")


# ============================================================================
# Main Entry
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="NoteClient - SailZen 文本/创作笔记 CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  sailzen note list --category character
  sailzen note pull --id 42
  sailzen note push notes/text/
  sailzen note create --category character --title "Alice" --work 1
  sailzen note delete --id 42
  sailzen note sync --workspace ./workspace
  sailzen note links --json
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    def add_common_args(p):
        p.add_argument(
            "--server",
            default=os.environ.get("SAIL_SERVER_URL", DEFAULT_SERVER_URL),
            help=f"sail_server 地址 (默认: {DEFAULT_SERVER_URL})",
        )
        p.add_argument(
            "--workspace",
            default=os.environ.get("NOTE_WORKSPACE_ROOT", "."),
            help="本地 note 工作区根目录 (默认: 当前目录)",
        )

    # ---- list ----
    p_list = subparsers.add_parser("list", aliases=["ls"], help="列出 NoteItem")
    add_common_args(p_list)
    p_list.add_argument("--category", default=None, help="按分类过滤")
    p_list.add_argument("--work-id", type=int, default=None, help="按作品 ID 过滤")
    p_list.add_argument("--edition-id", type=int, default=None, help="按版本 ID 过滤")
    p_list.set_defaults(func=cmd_list)

    # ---- pull ----
    p_pull = subparsers.add_parser("pull", help="拉取 NoteItem 到本地 Markdown")
    add_common_args(p_pull)
    p_pull.add_argument("--id", type=int, default=None, help="指定 NoteItem ID")
    p_pull.add_argument("--category", default=None, help="按分类拉取全部")
    p_pull.add_argument("--work-id", type=int, default=None, help="按作品 ID 过滤")
    p_pull.add_argument("--edition-id", type=int, default=None, help="按版本 ID 过滤")
    p_pull.set_defaults(func=cmd_pull)

    # ---- push ----
    p_push = subparsers.add_parser("push", help="扫描本地 Markdown 推送到服务器")
    add_common_args(p_push)
    p_push.add_argument("dir", nargs="?", default="notes/text", help="扫描目录")
    p_push.set_defaults(func=cmd_push)

    # ---- create ----
    p_create = subparsers.add_parser("create", aliases=["new"], help="创建 NoteItem")
    add_common_args(p_create)
    p_create.add_argument("--category", required=True, help="笔记分类")
    p_create.add_argument("--title", required=True, help="标题")
    p_create.add_argument("--slug", default=None, help="slug（默认由标题生成）")
    p_create.add_argument("--work-id", type=int, default=None, help="关联作品 ID")
    p_create.add_argument("--edition-id", type=int, default=None, help="关联版本 ID")
    p_create.add_argument("--tags", default=None, help="标签，逗号分隔")
    p_create.set_defaults(func=cmd_create)

    # ---- delete ----
    p_delete = subparsers.add_parser("delete", aliases=["rm"], help="删除 NoteItem")
    add_common_args(p_delete)
    p_delete.add_argument("--id", type=int, required=True, help="NoteItem ID")
    p_delete.add_argument("--keep-file", action="store_true", help="保留本地文件")
    p_delete.add_argument("--yes", "-y", action="store_true", help="跳过确认")
    p_delete.set_defaults(func=cmd_delete)

    # ---- sync ----
    p_sync = subparsers.add_parser("sync", help="双向同步")
    add_common_args(p_sync)
    p_sync.add_argument("--category", default=None, help="按分类过滤")
    p_sync.add_argument("--work-id", type=int, default=None, help="按作品 ID 过滤")
    p_sync.add_argument("--edition-id", type=int, default=None, help="按版本 ID 过滤")
    p_sync.set_defaults(func=cmd_sync)

    # ---- links ----
    p_links = subparsers.add_parser("links", help="获取双向链接图谱")
    add_common_args(p_links)
    p_links.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_links.set_defaults(func=cmd_links)

    # ---- export-csv ----
    p_export = subparsers.add_parser("export-csv", help="导出 NoteItem 到 CSV")
    add_common_args(p_export)
    p_export.add_argument("--category", default=None, help="按分类过滤")
    p_export.add_argument("--work-id", type=int, default=None, help="按作品 ID 过滤")
    p_export.add_argument("--edition-id", type=int, default=None, help="按版本 ID 过滤")
    p_export.add_argument("--output", "-o", default=None, help="输出 CSV 路径")
    p_export.set_defaults(func=cmd_export_csv)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
