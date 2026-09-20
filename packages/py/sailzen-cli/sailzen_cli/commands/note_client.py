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

import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import click
import requests
import yaml

from sailzen_cli.common import (
    _resolve_default_server_url,
    API_TIMEOUT,
    REQUEST_DELAY,
    server_option,
)


# ============================================================================
# Constants
# ============================================================================

DEFAULT_SERVER_URL = _resolve_default_server_url()
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


# ============================================================================
# Click Commands
# ============================================================================


def _note_client_ctx(server: str, workspace: str) -> NoteItemClient:
    return NoteItemClient(server, workspace or os.environ.get("NOTE_WORKSPACE_ROOT", "."))


@click.group()
def note():
    """服务器 NoteItem / 创作笔记同步管理。"""


@note.command("list")
@server_option
@click.option("--workspace", default=None, help="本地 note 工作区根目录 (默认: NOTE_WORKSPACE_ROOT 或当前目录)")
@click.option("--category", default=None, help="按分类过滤")
@click.option("--work-id", type=int, default=None, help="按作品 ID 过滤")
@click.option("--edition-id", type=int, default=None, help="按版本 ID 过滤")
def cmd_list(server, workspace, category, work_id, edition_id):
    """列出服务器上的 NoteItem"""
    client = _note_client_ctx(server, workspace)
    notes = client.list_notes(
        category=category,
        work_id=work_id,
        edition_id=edition_id,
    )
    if not notes:
        click.echo("(无 NoteItem)")
        return

    click.echo(f"{'ID':>6}  {'Category':<12}  {'Title':<30}  {'Setting File'}")
    click.echo("-" * 100)
    for n in notes:
        title = (n.get("title") or "")[:28]
        click.echo(
            f"{n.get('id', ''):>6}  "
            f"{n.get('category', ''):<12}  "
            f"{title:<30}  "
            f"{n.get('setting_file', '')}"
        )


@note.command("pull")
@server_option
@click.option("--workspace", default=None, help="本地 note 工作区根目录")
@click.option("--id", "note_id", type=int, default=None, help="指定 NoteItem ID")
@click.option("--category", default=None, help="按分类拉取全部")
@click.option("--work-id", type=int, default=None, help="按作品 ID 过滤")
@click.option("--edition-id", type=int, default=None, help="按版本 ID 过滤")
def cmd_pull(server, workspace, note_id, category, work_id, edition_id):
    """拉取 NoteItem 并在本地生成/更新 Markdown 文件"""
    client = _note_client_ctx(server, workspace)

    if note_id:
        n = client.get_note(note_id)
        if n is None:
            raise click.ClickException(f"NoteItem 不存在: {note_id}")
        notes = [n]
    else:
        notes = client.list_notes(
            category=category,
            work_id=work_id,
            edition_id=edition_id,
        )

    for n in notes:
        nid = n["id"]
        setting_file = n["setting_file"]
        content = client.get_content(nid) or ""
        file_path = client.write_local_note(setting_file, content)
        click.echo(f"✅ 拉取笔记 {nid} -> {file_path}")
        time.sleep(REQUEST_DELAY)


@note.command("push")
@server_option
@click.option("--workspace", default=None, help="本地 note 工作区根目录")
@click.argument("dir", default="notes/text")
def cmd_push(server, workspace, dir):
    """扫描本地 Markdown 文件，同步到服务器"""
    client = _note_client_ctx(server, workspace)
    files = client.scan_local_notes(dir)

    for file_path in files:
        data = _build_note_from_file(client, file_path)
        existing = None
        # 尝试通过 setting_file 查找已有 NoteItem
        for n in client.list_notes():
            if n.get("setting_file") == data["setting_file"]:
                existing = n
                break

        content = file_path.read_text(encoding="utf-8")
        if existing:
            nid = existing["id"]
            client.update_note(nid, data)
            client.update_content(nid, content)
            click.echo(f"✅ 更新笔记 {nid}: {data['setting_file']}")
        else:
            created = client.create_note(data)
            nid = created["id"]
            client.update_content(nid, content)
            click.echo(f"✅ 创建笔记 {nid}: {data['setting_file']}")
        time.sleep(REQUEST_DELAY)


@note.command("create")
@server_option
@click.option("--workspace", default=None, help="本地 note 工作区根目录")
@click.option("--category", required=True, help="笔记分类")
@click.option("--title", required=True, help="标题")
@click.option("--slug", default=None, help="slug（默认由标题生成）")
@click.option("--work-id", type=int, default=None, help="关联作品 ID")
@click.option("--edition-id", type=int, default=None, help="关联版本 ID")
@click.option("--tags", default=None, help="标签，逗号分隔")
def cmd_create(server, workspace, category, title, slug, work_id, edition_id, tags):
    """创建新的 NoteItem + 空 Markdown 文件"""
    client = _note_client_ctx(server, workspace)
    slug = slug or _make_slug(title)
    dir_name = CATEGORY_DIRS.get(category, category)
    setting_file = f"notes/text/{dir_name}/{slug}.md"

    front = {
        "category": category,
        "title": title,
        "slug": slug,
        "created": _now_iso(),
        "updated": _now_iso(),
    }
    if tags:
        front["tags"] = _parse_tags(tags)
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
    nid = created["id"]
    client.update_content(nid, content)
    file_path = client.write_local_note(setting_file, content)
    click.echo(f"✅ 创建笔记 {nid}: {file_path}")


@note.command("delete")
@server_option
@click.option("--workspace", default=None, help="本地 note 工作区根目录")
@click.option("--id", "note_id", type=int, required=True, help="NoteItem ID")
@click.option("--keep-file", is_flag=True, help="保留本地文件")
@click.option("--yes", "-y", is_flag=True, help="跳过确认")
def cmd_delete(server, workspace, note_id, keep_file, yes):
    """删除 NoteItem 及对应文件"""
    client = _note_client_ctx(server, workspace)
    n = client.get_note(note_id)
    if n is None:
        raise click.ClickException(f"NoteItem 不存在: {note_id}")

    if not yes:
        confirm = input(f"确认删除 NoteItem {note_id} [{n.get('setting_file')}]? [y/N] ").strip().lower()
        if confirm != "y":
            click.echo("已取消")
            return

    client.delete_note(note_id)
    if not keep_file:
        try:
            file_path = client._resolve_file_path(n["setting_file"])
            if file_path.exists():
                file_path.unlink()
                click.echo(f"✅ 已删除文件: {file_path}")
        except Exception as e:
            click.echo(f"⚠️ 删除文件失败: {e}", err=True)
    click.echo(f"✅ 已删除 NoteItem: {note_id}")


@note.command("sync")
@server_option
@click.option("--workspace", default=None, help="本地 note 工作区根目录")
@click.option("--category", default=None, help="按分类过滤")
@click.option("--work-id", type=int, default=None, help="按作品 ID 过滤")
@click.option("--edition-id", type=int, default=None, help="按版本 ID 过滤")
def cmd_sync(server, workspace, category, work_id, edition_id):
    """双向同步：pull + push"""
    click.echo("--- pull ---")
    cmd_pull.callback(server=server, workspace=workspace, note_id=None, category=category, work_id=work_id, edition_id=edition_id)
    click.echo("--- push ---")
    cmd_push.callback(server=server, workspace=workspace, dir="notes/text")


@note.command("links")
@server_option
@click.option("--workspace", default=None, help="本地 note 工作区根目录")
@click.option("--json", "as_json", is_flag=True, help="以 JSON 输出")
def cmd_links(server, workspace, as_json):
    """分析/重建双向链接索引"""
    client = _note_client_ctx(server, workspace)
    graph = client.get_links()
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    click.echo(f"节点数: {len(nodes)}, 链接数: {len(edges)}")
    if as_json:
        click.echo(json.dumps(graph, ensure_ascii=False, indent=2))
        return
    click.echo("\n--- nodes ---")
    for node in nodes:
        click.echo(f"  [{node.get('id')}] {node.get('slug')} ({node.get('title')})")
    click.echo("\n--- edges ---")
    for edge in edges:
        click.echo(f"  {edge.get('source')} -> {edge.get('target')} [{edge.get('display')}]")


@note.command("export-csv")
@server_option
@click.option("--workspace", default=None, help="本地 note 工作区根目录")
@click.option("--category", default=None, help="按分类过滤")
@click.option("--work-id", type=int, default=None, help="按作品 ID 过滤")
@click.option("--edition-id", type=int, default=None, help="按版本 ID 过滤")
@click.option("--output", "-o", default=None, help="输出 CSV 路径")
def cmd_export_csv(server, workspace, category, work_id, edition_id, output):
    """导出 NoteItem 到 CSV（用于批量编辑）"""
    client = _note_client_ctx(server, workspace)
    notes = client.list_notes(
        category=category,
        work_id=work_id,
        edition_id=edition_id,
    )
    if not notes:
        click.echo("(无 NoteItem)")
        return

    csv_path = output or "notes.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for n in notes:
            meta = n.get("meta_data", {}) or {}
            row = {
                "id": n.get("id"),
                "category": n.get("category"),
                "title": n.get("title"),
                "slug": n.get("slug"),
                "setting_file": n.get("setting_file"),
                "work_id": n.get("work_id"),
                "edition_id": n.get("edition_id"),
                "tags": ",".join(meta.get("tags", [])),
                "related": ",".join(meta.get("related", [])),
            }
            writer.writerow(row)
    click.echo(f"✅ 导出 {len(notes)} 条记录到 {csv_path}")


if __name__ == "__main__":
    note()
