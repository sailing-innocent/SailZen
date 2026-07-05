# -*- coding: utf-8 -*-
# @file note_links.py
# @brief Markdown 双向链接解析工具
# @author sailing-innocent
# @date 2026-08-06
# @version 1.0
# ---------------------------------

"""
解析 Markdown 中的 [[wiki-link]] 双向链接，并构建链接图谱。

支持的链接格式:
- [[slug]]
- [[category/slug]]
- [[title#heading]]
- [[display text|slug]]
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# Constants
# ============================================================================

WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# 默认笔记分类到目录的映射
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


# ============================================================================
# Parsing
# ============================================================================


def parse_wiki_links(content: str) -> List[Dict[str, str]]:
    """
    从 Markdown 正文中解析所有 [[...]] 双向链接。

    Returns:
        每个链接为 dict: {"raw": "原始文本", "target": "目标", "display": "显示文本",
                          "heading": "锚点"}
    """
    results: List[Dict[str, str]] = []
    for match in WIKI_LINK_RE.finditer(content):
        raw = match.group(1).strip()
        # 支持 [[target|display]]（Obsidian/Wiki 标准）
        # 也兼容 [[display|target]]：当右侧含 / 或 # 时，右侧视为 target
        if "|" in raw:
            left, right = raw.split("|", 1)
            left, right = left.strip(), right.strip()
            # 若右侧含 / 或 #，则右侧是 target
            if "/" in right or "#" in right:
                display, target = left, right
            else:
                target, display = left, right
        else:
            target = raw
            display = raw

        heading = ""
        if "#" in target:
            target, heading = target.split("#", 1)
            target = target.strip()
            heading = heading.strip()

        results.append(
            {
                "raw": raw,
                "target": target,
                "display": display,
                "heading": heading,
            }
        )
    return results


def extract_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    简单提取 YAML frontmatter，返回 (meta, body)。

    不依赖 yaml 库，仅做基础解析以解析 related / tags 等字段。
    """
    meta: Dict[str, Any] = {}
    if not content.startswith("---"):
        return meta, content

    end = content.find("\n---", 3)
    if end == -1:
        return meta, content

    frontmatter = content[3:end].strip()
    body = content[end + 4 :].lstrip()

    current_key: Optional[str] = None
    current_list: List[str] = []
    in_list = False

    for line in frontmatter.splitlines():
        stripped = line.rstrip()
        if not stripped:
            continue

        # 列表项
        if stripped.lstrip().startswith("-"):
            value = stripped.lstrip()[1:].strip()
            if in_list and current_key:
                current_list.append(value)
            continue

        # key: value
        if ":" in stripped:
            # 保存上一个 list
            if in_list and current_key:
                meta[current_key] = current_list
                current_list = []
                in_list = False

            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            # 判断下一行是否是列表
            current_key = key
            if value == "":
                in_list = True
                current_list = []
            else:
                # 去除可能的引号
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                meta[key] = value

    if in_list and current_key:
        meta[current_key] = current_list

    return meta, body


def resolve_note_target(
    target: str, category: Optional[str] = None
) -> Tuple[Optional[str], str]:
    """
    将链接目标解析为 (category, slug)。

    例如:
      - "魔法体系" -> ("setting", "魔法体系")
      - "settings/魔法体系" -> ("setting", "魔法体系")
      - "王都" -> ("geography", "王都")
    """
    if "/" in target:
        parts = target.split("/", 1)
        dir_name = parts[0]
        slug = parts[1].strip()
        # 目录名 -> category
        cat = None
        for c, d in CATEGORY_DIRS.items():
            if d == dir_name:
                cat = c
                break
        return cat or dir_name, slug

    # 无目录前缀，使用传入 category 或保持未知
    return category, target


# ============================================================================
# Link Graph
# ============================================================================


def build_link_graph(
    notes: List[Tuple[int, str, str]],
    workspace_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    基于 NoteItem 列表构建链接图谱。

    Args:
        notes: [(id, title, setting_file), ...]
        workspace_root: 可选，用于读取 Markdown 内容解析链接

    Returns:
        {"nodes": [...], "edges": [...]}
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    # 多种方式索引目标：slug -> id, stem -> id, filename -> id
    target_to_id: Dict[str, int] = {}

    for note_id, title, setting_file in notes:
        slug = Path(setting_file).stem
        nodes.append(
            {
                "id": note_id,
                "slug": slug,
                "title": title,
                "setting_file": setting_file,
            }
        )
        target_to_id[slug] = note_id
        target_to_id[Path(setting_file).name] = note_id
        target_to_id[setting_file] = note_id
        if title:
            target_to_id[title] = note_id

    if workspace_root is not None:
        for note_id, title, setting_file in notes:
            file_path = workspace_root / setting_file
            if not file_path.exists():
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            links = parse_wiki_links(content)
            for link in links:
                target_id = target_to_id.get(link["target"])
                if target_id is None:
                    # 尝试用 slug/stem 匹配
                    target_id = target_to_id.get(Path(link["target"]).stem)
                if target_id is None:
                    # 尝试解析 category/slug 形式
                    target_cat, target_slug = resolve_note_target(link["target"])
                    target_id = target_to_id.get(target_slug)
                    if target_id is None and target_cat:
                        combined = f"notes/text/{CATEGORY_DIRS.get(target_cat, target_cat)}/{target_slug}.md"
                        target_id = target_to_id.get(combined)
                if target_id is not None and target_id != note_id:
                    edges.append(
                        {
                            "source": note_id,
                            "target": target_id,
                            "display": link["display"],
                            "heading": link.get("heading", ""),
                        }
                    )

    return {"nodes": nodes, "edges": edges}


# ============================================================================
# Helpers for AI-generated notes
# ============================================================================


def make_note_slug(title: str, max_length: int = 80) -> str:
    """根据标题生成 URL/文件名友好的 slug"""
    import re as _re

    slug = title.strip().replace(" ", "_")
    slug = _re.sub(r"[^\w\u4e00-\u9fff-_]", "", slug)
    return (slug or "note")[:max_length]


def make_note_setting_file(category: str, slug: str) -> str:
    """生成 setting_file 相对路径"""
    dir_name = CATEGORY_DIRS.get(category, category)
    return f"notes/text/{dir_name}/{slug}.md"


def normalize_note_content(
    content: str,
    note_id: int,
    category: str,
    title: str,
    slug: str,
    work_slug: Optional[str] = None,
    edition_slug: Optional[str] = None,
    tags: Optional[List[str]] = None,
    related: Optional[List[str]] = None,
) -> str:
    """
    规范化 AI 生成的 Markdown 笔记内容，确保 frontmatter 完整。
    """
    from datetime import datetime

    # 简单判断是否存在 frontmatter
    has_frontmatter = content.strip().startswith("---")

    now = datetime.now().isoformat(timespec="seconds")
    front = {
        "id": note_id,
        "category": category,
        "title": title,
        "slug": slug,
        "created": now,
        "updated": now,
    }
    if work_slug:
        front["work"] = work_slug
    if edition_slug:
        front["edition"] = edition_slug
    if tags:
        front["tags"] = tags
    if related:
        front["related"] = related

    # 如果已有 frontmatter，尝试合并并保留原正文；传入字段优先
    if has_frontmatter:
        meta, body = extract_frontmatter(content)
        for k, v in front.items():
            meta[k] = v
        meta["updated"] = now
        # 构建 frontmatter 文本
        lines = ["---"]
        for k, v in meta.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
        lines.append("---")
        return "\n".join(lines) + "\n\n" + body.lstrip()

    # 无 frontmatter，自动创建
    lines = ["---"]
    for k, v in front.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + content.lstrip()
