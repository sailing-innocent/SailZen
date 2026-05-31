#!/usr/bin/env python3
"""
visualize_filetree.py

功能：
1. scan   - 扫描给定目录，按指定深度生成 JSON 配置文件
2. render - 读取用户编辑后的 JSON，渲染成可嵌入 Markdown 的 HTML 片段或 SVG 图片

用法:
    python visualize_filetree.py scan  <dir>  [--depth N] [--out config.json]
    python visualize_filetree.py render <config.json> [--format html|svg] [--out tree.<ext>]

JSON 配置说明:
    - root_name: 根节点显示名称
    - root_icon: 根节点图标 (默认 📁)
    - show_depth: 扫描深度
    - items: 文件树节点列表，每个节点包含:
        - name: 文件/文件夹名称
        - path: 相对路径
        - type: "dir" | "file"
        - depth: 层级深度
        - icon: 自定义图标 (可修改)
        - repeat_placeholder: 若为 true, 该节点会被渲染为 "..." 占位符
        - collapsed: 是否折叠子节点
        - note: 备注文本，会显示在节点右侧
        - children: 子节点列表 (仅目录)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# ───────────────────────── 默认图标映射 ─────────────────────────

DEFAULT_ICONS: dict[str, str] = {
    "dir": "📁",
    "file": "📄",
    ".py": "🐍",
    ".js": "📜",
    ".ts": "📘",
    ".json": "📋",
    ".md": "📝",
    ".yml": "⚙️",
    ".yaml": "⚙️",
    ".toml": "⚙️",
    ".html": "🌐",
    ".css": "🎨",
    ".vue": "💚",
    ".sql": "🗄️",
    ".db": "🗄️",
    ".sh": "🔧",
    ".bat": "🔧",
    ".ps1": "🔧",
    ".dockerfile": "🐳",
    ".gitignore": "👁️",
    ".env": "🔐",
    ".lock": "🔒",
    ".png": "🖼️",
    ".jpg": "🖼️",
    ".svg": "🖼️",
    ".woff": "🔤",
    ".woff2": "🔤",
    ".ttf": "🔤",
}


def get_icon(name: str, is_dir: bool) -> str:
    """根据文件名和类型推断默认图标。"""
    if is_dir:
        return DEFAULT_ICONS["dir"]
    ext = Path(name).suffix.lower()
    if ext in DEFAULT_ICONS:
        return DEFAULT_ICONS[ext]
    if name.lower().startswith("dockerfile"):
        return DEFAULT_ICONS[".dockerfile"]
    if name.lower() == ".gitignore":
        return DEFAULT_ICONS[".gitignore"]
    return DEFAULT_ICONS["file"]


# ───────────────────────── 扫描逻辑 ─────────────────────────

EXCLUDE_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".cache", ".mypy_cache", ".idea", ".vscode", ".egg-info", "dist", "build"}

EXCLUDE_FILES = {".DS_Store"}


def should_skip(name: str, is_dir: bool) -> bool:
    if is_dir and name in EXCLUDE_DIRS:
        return True
    if not is_dir and name in EXCLUDE_FILES:
        return True
    return False


def scan_directory(root: Path, max_depth: int) -> dict[str, Any]:
    """扫描目录，返回嵌套的 JSON 结构。"""

    def _scan(path: Path, depth: int) -> list[dict[str, Any]] | None:
        if depth > max_depth:
            return None
        items: list[dict[str, Any]] = []
        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return items

        for entry in entries:
            is_dir = entry.is_dir()
            if should_skip(entry.name, is_dir):
                continue
            rel = str(entry.relative_to(root)).replace("\\", "/")
            node: dict[str, Any] = {
                "name": entry.name,
                "path": rel,
                "type": "dir" if is_dir else "file",
                "depth": depth,
                "icon": get_icon(entry.name, is_dir),
                "repeat_placeholder": False,
                "collapsed": False,
                "note": "",
            }
            if is_dir and depth < max_depth:
                children = _scan(entry, depth + 1)
                if children:
                    node["children"] = children
            items.append(node)
        return items

    return {
        "root_name": root.name or str(root),
        "root_icon": "📁",
        "show_depth": max_depth,
        "items": _scan(root, 0) or [],
    }


# ───────────────────────── HTML 渲染逻辑 ─────────────────────────

HTML_TEMPLATE = """\
<div class="filetree-wrapper">
<style>
.filetree-wrapper {{
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  color: #333;
  background: #fafbfc;
  border: 1px solid #e1e4e8;
  border-radius: 6px;
  padding: 16px 20px;
  max-width: 100%;
  overflow-x: auto;
}}
.filetree-wrapper ul {{
  list-style: none;
  padding-left: 0;
  margin: 0;
}}
.filetree-wrapper ul ul {{
  padding-left: 22px;
  border-left: 1px dashed #d0d7de;
  margin-left: 4px;
}}
.filetree-wrapper li {{
  margin: 2px 0;
  position: relative;
}}
.filetree-wrapper .ft-root {{
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 8px;
  color: #1a1a1a;
}}
.filetree-wrapper .ft-icon {{
  margin-right: 6px;
  display: inline-block;
  width: 1.2em;
  text-align: center;
}}
.filetree-wrapper .ft-name {{
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 13px;
}}
.filetree-wrapper .ft-dir > .ft-name {{
  color: #0969da;
  font-weight: 500;
}}
.filetree-wrapper .ft-file > .ft-name {{
  color: #333;
}}
.filetree-wrapper .ft-placeholder {{
  color: #8c959f;
  font-style: italic;
}}
.filetree-wrapper .ft-note {{
  color: #6e7781;
  font-size: 12px;
  margin-left: 8px;
  font-style: italic;
}}
.filetree-wrapper .ft-hidden {{
  display: none;
}}
</style>
<div class="ft-root"><span class="ft-icon">{root_icon}</span>{root_name}</div>
{tree_html}
</div>
"""


def render_node_html(node: dict[str, Any]) -> str:
    """递归渲染单个节点为 HTML <li>。"""
    icon = node.get("icon", "")
    name = node.get("name", "")
    node_type = node.get("type", "file")
    is_placeholder = node.get("repeat_placeholder", False)
    note = node.get("note", "")
    collapsed = node.get("collapsed", False)
    children = node.get("children")

    if is_placeholder:
        note_html = f'<span class="ft-note">{_escape_html(note)}</span>' if note else ""
        html = f'<li class="ft-placeholder"><span class="ft-icon">{_escape_html(icon)}</span><span class="ft-name">...</span>{note_html}</li>\n'
        return html

    note_html = f'<span class="ft-note">{_escape_html(note)}</span>' if note else ""
    html = f'<li class="ft-{node_type}"><span class="ft-icon">{_escape_html(icon)}</span><span class="ft-name">{_escape_html(name)}</span>{note_html}'

    if children:
        child_class = ' class="ft-hidden"' if collapsed else ""
        html += f"<ul{child_class}>\n"
        for child in children:
            html += render_node_html(child)
        html += "</ul>\n"

    html += "</li>\n"
    return html


def render_html(config: dict[str, Any]) -> str:
    """将 JSON 配置渲染为完整 HTML 片段。"""
    root_name = config.get("root_name", "root")
    root_icon = config.get("root_icon", "📁")
    items = config.get("items", [])

    tree_html = "<ul>\n"
    for item in items:
        tree_html += render_node_html(item)
    tree_html += "</ul>\n"

    return HTML_TEMPLATE.format(
        root_name=_escape_html(root_name),
        root_icon=_escape_html(root_icon),
        tree_html=tree_html,
    )


# ───────────────────────── SVG 渲染逻辑 ─────────────────────────

# 布局常量
SVG_FONT_SIZE = 14
SVG_LINE_HEIGHT = 24
SVG_INDENT = 24
SVG_PAD_LEFT = 20
SVG_PAD_TOP = 44   # 标题行占用
SVG_PAD_RIGHT = 20
SVG_PAD_BOTTOM = 16
SVG_ICON_WIDTH = 20
SVG_NAME_OFFSET = 24
SVG_NOTE_GAP = 12

# 等宽字体字符宽度估算 (px)
_CHAR_W_EN = 7.5
_CHAR_W_EMOJI = 14.0
_CHAR_W_CN = 14.0


def _text_width(text: str) -> float:
    """估算文本在等宽字体 14px 下的宽度。"""
    w = 0.0
    for ch in text:
        o = ord(ch)
        if 0x1F300 <= o <= 0x1F9FF or 0x2600 <= o <= 0x26FF or 0x2700 <= o <= 0x27BF:
            w += _CHAR_W_EMOJI
        elif o > 0x2E7F:
            w += _CHAR_W_CN
        else:
            w += _CHAR_W_EN
    return w


def _collect_visible(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按遍历顺序收集所有可见节点（扁平化）。"""
    result: list[dict[str, Any]] = []
    for node in nodes:
        result.append(node)
        if node.get("type") == "dir" and not node.get("collapsed", False):
            result.extend(_collect_visible(node.get("children", [])))
    return result


def _calc_node_width(node: dict[str, Any]) -> float:
    """计算单个节点的内容宽度。"""
    w = _text_width(node.get("icon", "")) + SVG_NAME_OFFSET
    w += _text_width(node.get("name", ""))
    note = node.get("note", "")
    if note:
        w += SVG_NOTE_GAP + _text_width(note)
    return w


def render_svg(config: dict[str, Any]) -> str:
    """将 JSON 配置渲染为自包含 SVG。"""
    root_name = config.get("root_name", "root")
    root_icon = config.get("root_icon", "📁")
    items = config.get("items", [])

    visible = _collect_visible(items)

    # 计算尺寸
    max_content_w = 0.0
    for node in visible:
        depth = node.get("depth", 0)
        x = SVG_PAD_LEFT + depth * SVG_INDENT
        node_w = _calc_node_width(node)
        max_content_w = max(max_content_w, x + node_w)

    # 根标题宽度
    title_w = _text_width(root_icon) + 6 + _text_width(root_name)
    max_content_w = max(max_content_w, title_w)

    width = int(max_content_w + SVG_PAD_LEFT + SVG_PAD_RIGHT)
    height = SVG_PAD_TOP + len(visible) * SVG_LINE_HEIGHT + SVG_PAD_BOTTOM

    # 构建 SVG 内容
    svg_parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs>',
        '  <style>',
        f'    .ft-root {{ font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 15px; font-weight: 600; fill: #1a1a1a; }}',
        f'    .ft-icon {{ font-family: "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif; font-size: {SVG_FONT_SIZE}px; }}',
        f'    .ft-name {{ font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: {SVG_FONT_SIZE}px; }}',
        f'    .ft-dir {{ fill: #0969da; font-weight: 500; }}',
        f'    .ft-file {{ fill: #333; }}',
        f'    .ft-placeholder {{ fill: #8c959f; font-style: italic; }}',
        f'    .ft-note {{ font-family: "SFMono-Regular", Consolas, monospace; font-size: 12px; fill: #6e7781; font-style: italic; }}',
        '    .ft-bg { fill: #fafbfc; }',
        '    .ft-border { fill: none; stroke: #e1e4e8; stroke-width: 1; }',
        '    .ft-guide { stroke: #d0d7de; stroke-width: 1; stroke-dasharray: 3,3; }',
        '  </style>',
        '</defs>',
        # 背景 + 边框
        f'<rect class="ft-bg" x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="6" ry="6"/>',
        f'<rect class="ft-border" x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="6" ry="6"/>',
    ]

    # 根标题
    tx = SVG_PAD_LEFT
    ty = 26
    svg_parts.append(
        f'<text x="{tx}" y="{ty}" class="ft-root">'
        f'<tspan class="ft-icon">{_escape_svg_text(root_icon)}</tspan>'
        f' {_escape_svg_text(root_name)}</text>'
    )

    # 节点行和连接线
    row = 0
    node_index_map: dict[int, dict[str, Any]] = {}  # row -> node
    for node in visible:
        node_index_map[row] = node
        row += 1

    def _render_nodes(nodes: list[dict[str, Any]], parent_depth: int = -1, parent_row: int = -1):
        nonlocal row
        for node in nodes:
            depth = node.get("depth", 0)
            y = SVG_PAD_TOP + row * SVG_LINE_HEIGHT
            x = SVG_PAD_LEFT + depth * SVG_INDENT

            node_type = node.get("type", "file")
            is_placeholder = node.get("repeat_placeholder", False)
            icon = node.get("icon", "")
            name = node.get("name", "")
            note = node.get("note", "")

            # 类名
            cls = "ft-placeholder" if is_placeholder else f"ft-{node_type}"

            # 图标
            svg_parts.append(
                f'<text x="{x}" y="{y}" class="ft-icon">{_escape_svg_text(icon)}</text>'
            )

            # 名称
            nx = x + SVG_NAME_OFFSET
            display_name = "..." if is_placeholder else name
            svg_parts.append(
                f'<text x="{nx}" y="{y}" class="ft-name {cls}">{_escape_svg_text(display_name)}</text>'
            )

            # note
            if note:
                nw = _text_width(name)
                nx2 = nx + int(nw) + SVG_NOTE_GAP
                svg_parts.append(
                    f'<text x="{nx2}" y="{y}" class="ft-note">{_escape_svg_text(note)}</text>'
                )

            current_row = row
            row += 1

            # 递归子节点
            children = node.get("children", [])
            if node_type == "dir" and children and not node.get("collapsed", False):
                _render_nodes(children, depth, current_row)

    # 重置 row 并渲染
    row = 0
    _render_nodes(items)

    # 绘制连接线 (guides)
    # 对于每个展开的目录，从其行开始到最后一子行画竖线
    row = 0
    for node in visible:
        children = node.get("children", [])
        if node.get("type") == "dir" and children and not node.get("collapsed", False):
            depth = node.get("depth", 0)
            # 找到该目录下所有可见子节点的最后行
            child_rows: list[int] = []
            child_depth = depth + 1
            r = row + 1
            while r < len(visible) and visible[r].get("depth", 0) >= child_depth:
                if visible[r].get("depth", 0) == child_depth:
                    child_rows.append(r)
                r += 1

            if child_rows:
                guide_x = SVG_PAD_LEFT + depth * SVG_INDENT + 12
                y1 = SVG_PAD_TOP + row * SVG_LINE_HEIGHT + 4
                y2 = SVG_PAD_TOP + child_rows[-1] * SVG_LINE_HEIGHT + 4
                svg_parts.append(
                    f'<line class="ft-guide" x1="{guide_x}" y1="{y1}" x2="{guide_x}" y2="{y2}"/>'
                )
                for cr in child_rows:
                    cy = SVG_PAD_TOP + cr * SVG_LINE_HEIGHT + 4
                    child_x = SVG_PAD_LEFT + child_depth * SVG_INDENT + 4
                    svg_parts.append(
                        f'<line class="ft-guide" x1="{guide_x}" y1="{cy}" x2="{child_x}" y2="{cy}"/>'
                    )
        row += 1

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _escape_svg_text(text: str) -> str:
    """Escape text for SVG text element."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ───────────────────────── 公共工具 ─────────────────────────

def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ───────────────────────── 命令行入口 ─────────────────────────

def cmd_scan(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    if not root.exists():
        print(f"错误: 目录不存在: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"错误: 不是目录: {root}", file=sys.stderr)
        return 1

    data = scan_directory(root, args.depth)
    out_path = Path(args.out) if args.out else Path(f"{root.name}_filetree.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"配置已保存: {out_path}")
    print(f"提示: 你可以手动编辑该 JSON，修改 icon、添加 repeat_placeholder、note 等字段，")
    print(f"      然后运行: python visualize_filetree.py render {out_path}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"错误: 配置文件不存在: {config_path}", file=sys.stderr)
        return 1

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    fmt = args.format.lower()
    if fmt == "html":
        output = render_html(config)
        default_ext = ".html"
        tip = "将文件内容复制到 Markdown 中即可嵌入显示。"
    elif fmt == "svg":
        output = render_svg(config)
        default_ext = ".svg"
        tip = "SVG 图片可直接嵌入 Markdown 或作为独立图片使用。"
    else:
        print(f"错误: 不支持的格式: {fmt}。仅支持 html、svg。", file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else config_path.with_suffix(default_ext)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"{fmt.upper()} 已保存: {out_path}")
    print(f"提示: {tip}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="目录文件树可视化工具：扫描 → 编辑 JSON → 渲染 HTML/SVG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 1. 扫描当前目录，深度 3，生成 config.json
  python visualize_filetree.py scan . --depth 3 -o config.json

  # 2. 渲染为 HTML（默认）
  python visualize_filetree.py render config.json -o tree.html

  # 3. 渲染为 SVG
  python visualize_filetree.py render config.json --format svg -o tree.svg
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="扫描目录并生成 JSON 配置")
    p_scan.add_argument("dir", help="要扫描的目录路径")
    p_scan.add_argument("--depth", "-d", type=int, default=3, help="扫描深度 (默认 3)")
    p_scan.add_argument("--out", "-o", default=None, help="输出 JSON 文件路径")
    p_scan.set_defaults(func=cmd_scan)

    p_render = sub.add_parser("render", help="将 JSON 配置渲染为 HTML 或 SVG")
    p_render.add_argument("config", help="JSON 配置文件路径")
    p_render.add_argument(
        "--format", "-f", choices=["html", "svg"], default="html", help="输出格式 (默认 html)"
    )
    p_render.add_argument("--out", "-o", default=None, help="输出文件路径")
    p_render.set_defaults(func=cmd_render)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
