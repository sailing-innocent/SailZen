# -*- coding: utf-8 -*-
# @file content_ingest.py
# @brief Multi-format Content Importers (EPUB, PDF via PyMuPDF, arXiv HTML/PDF)
# @author sailing-innocent
# @date 2026-11-26
# @version 1.0
# ---------------------------------

"""
Content 2.0 多格式文档摄入管线：
1. EPUB 解析（标准库 zipfile + xml.etree.ElementTree + html.parser，天然还原分卷 -> 章节树）
2. PDF 解析（基于 PyMuPDF / fitz：提取目录大纲/标题结构分节 + 原始 PDF 存入 ContentAsset 对照查看）
3. arXiv 论文导入（拉取 arXiv Atom 元数据 + 优先抓取 arxiv.org/html 结构化分节正文，回退 PDF 解析）
"""

from __future__ import annotations

import io
import logging
import posixpath
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from sail_server.application.dto.text import MultiFormatImportResponse
from sail_server.model.content_library import save_content_asset_impl
from sail_server.model.text import (
    ChapterBatchItem,
    batch_insert_chapters_impl,
    create_work_with_edition_impl,
    get_work_impl,
)
from sailzen_orm.text import DocumentNode

logger = logging.getLogger(__name__)


# ============================================================================
# HTML -> Clean Plaintext Helper
# ============================================================================


class _CleanTextHTMLParser(HTMLParser):
    """将 XHTML/HTML 清洗为结构清晰的阅读纯文本（保留段落换行与标题分隔）。"""

    _SKIP_TAGS = {"script", "style", "head", "nav", "noscript", "svg"}
    _BLOCK_TAGS = {
        "p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6",
        "blockquote", "pre", "tr", "section", "article",
    }

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs):
        t = tag.lower()
        if t in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and t in self._BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str):
        t = tag.lower()
        if t in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth == 0 and t in self._BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str):
        if self._skip_depth == 0 and data:
            self._chunks.append(data)

    def get_text(self) -> str:
        raw = "".join(self._chunks)
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in raw.splitlines()]
        cleaned: List[str] = []
        empty = 0
        for ln in lines:
            if not ln:
                empty += 1
                if empty <= 1 and cleaned:
                    cleaned.append("")
            else:
                empty = 0
                cleaned.append(ln)
        return "\n".join(cleaned).strip()


def html_to_clean_text(html_str: str) -> str:
    parser = _CleanTextHTMLParser()
    parser.feed(html_str or "")
    parser.close()
    return parser.get_text()


@dataclass
class ParsedSection:
    label: str
    title: str
    content: str
    volume_label: Optional[str] = None
    volume_title: Optional[str] = None
    meta_data: dict = field(default_factory=dict)


# ============================================================================
# 1. EPUB Parser (Zero heavy native dependencies, native volume->chapter tree)
# ============================================================================


def parse_epub_bytes(epub_bytes: bytes, fallback_title: str = "未命名电子书") -> dict:
    """解析 EPUB 二进制，返回 metadata 与带分卷归属的 sections 列表。"""
    with zipfile.ZipFile(io.BytesIO(epub_bytes), "r") as zf:
        names = set(zf.namelist())
        opf_path = None
        if "META-INF/container.xml" in names:
            c_root = ET.fromstring(zf.read("META-INF/container.xml"))
            for elem in c_root.iter():
                if elem.tag.endswith("rootfile") and elem.attrib.get("full-path"):
                    opf_path = elem.attrib["full-path"]
                    break
        if not opf_path:
            for n in names:
                if n.lower().endswith(".opf"):
                    opf_path = n
                    break
        if not opf_path or opf_path not in names:
            raise ValueError("无效 EPUB 文件：未找到 OPF 清单")

        opf_dir = posixpath.dirname(opf_path)
        opf_root = ET.fromstring(zf.read(opf_path))

        # 1) 元数据
        title = fallback_title
        author = None
        language = "zh"
        synopsis = None
        for elem in opf_root.iter():
            tag = elem.tag.split("}")[-1].lower()
            text = (elem.text or "").strip()
            if not text:
                continue
            if tag == "title" and title == fallback_title:
                title = text
            elif tag == "creator" and not author:
                author = text
            elif tag == "language":
                language = text[:16]
            elif tag == "description" and not synopsis:
                synopsis = html_to_clean_text(text)[:2000]

        # 2) manifest + spine
        manifest: Dict[str, Tuple[str, str]] = {}  # id -> (full_href, media_type)
        ncx_href = None
        nav_href = None
        for elem in opf_root.iter():
            tag = elem.tag.split("}")[-1].lower()
            if tag == "item":
                item_id = elem.attrib.get("id", "")
                href = urllib.parse.unquote(elem.attrib.get("href", ""))
                mtype = elem.attrib.get("media-type", "")
                props = elem.attrib.get("properties", "")
                full_href = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
                manifest[item_id] = (full_href, mtype)
                if "nav" in props.split():
                    nav_href = full_href
                if mtype == "application/x-dtbncx+xml" or href.lower().endswith(".ncx"):
                    ncx_href = full_href

        spine_hrefs: List[str] = []
        for elem in opf_root.iter():
            tag = elem.tag.split("}")[-1].lower()
            if tag == "itemref":
                idref = elem.attrib.get("idref", "")
                if idref in manifest:
                    spine_hrefs.append(manifest[idref][0])

        # 3) 解析多级目录（NCX 优先，回退 EPUB3 nav.xhtml）
        # toc_map: href_no_frag -> (chapter_title, volume_title_or_None)
        toc_map: Dict[str, Tuple[str, Optional[str]]] = {}

        def _norm_href(base_dir: str, raw_src: str) -> str:
            src_no_frag = urllib.parse.unquote(raw_src.split("#")[0])
            return posixpath.normpath(posixpath.join(base_dir, src_no_frag)) if base_dir else src_no_frag

        if ncx_href and ncx_href in names:
            ncx_dir = posixpath.dirname(ncx_href)
            try:
                ncx_root = ET.fromstring(zf.read(ncx_href))

                def _walk_navpoint(np, current_vol: Optional[str] = None, depth: int = 0):
                    lbl = ""
                    src = ""
                    child_nps = []
                    for c in np:
                        ctag = c.tag.split("}")[-1]
                        if ctag == "navLabel":
                            for t in c.iter():
                                if t.tag.split("}")[-1] == "text" and t.text:
                                    lbl = t.text.strip()
                        elif ctag == "content":
                            src = c.attrib.get("src", "")
                        elif ctag == "navPoint":
                            child_nps.append(c)

                    if child_nps and depth == 0:
                        # 顶层含子节点 → 作为卷
                        for child in child_nps:
                            _walk_navpoint(child, current_vol=lbl or current_vol, depth=depth + 1)
                        if src:
                            full = _norm_href(ncx_dir, src)
                            if full not in toc_map:
                                toc_map[full] = (lbl or "导言", lbl or current_vol)
                    else:
                        if src:
                            full = _norm_href(ncx_dir, src)
                            if full not in toc_map:
                                toc_map[full] = (lbl or "", current_vol)
                        for child in child_nps:
                            _walk_navpoint(child, current_vol=current_vol, depth=depth + 1)

                for elem in ncx_root.iter():
                    if elem.tag.split("}")[-1] == "navMap":
                        for np in elem:
                            if np.tag.split("}")[-1] == "navPoint":
                                _walk_navpoint(np, None, 0)
            except Exception as exc:
                logger.warning("EPUB NCX parse warning: %s", exc)
        elif nav_href and nav_href in names:
            nav_dir = posixpath.dirname(nav_href)
            try:
                nav_root = ET.fromstring(zf.read(nav_href))

                def _walk_li(li_elem, current_vol: Optional[str] = None, depth: int = 0):
                    a_text = ""
                    a_href = ""
                    sub_lis = []
                    for c in li_elem:
                        ctag = c.tag.split("}")[-1].lower()
                        if ctag in ("a", "span") and not a_text:
                            a_text = "".join(c.itertext()).strip()
                            a_href = c.attrib.get("href", "")
                        elif ctag in ("ol", "ul"):
                            for sub in c:
                                if sub.tag.split("}")[-1].lower() == "li":
                                    sub_lis.append(sub)
                    if sub_lis and depth == 0:
                        for sub in sub_lis:
                            _walk_li(sub, current_vol=a_text or current_vol, depth=depth + 1)
                    elif a_href:
                        full = _norm_href(nav_dir, a_href)
                        if full not in toc_map:
                            toc_map[full] = (a_text, current_vol)

                for nav_el in nav_root.iter():
                    if nav_el.tag.split("}")[-1].lower() == "nav":
                        for ol in nav_el:
                            if ol.tag.split("}")[-1].lower() in ("ol", "ul"):
                                for li in ol:
                                    if li.tag.split("}")[-1].lower() == "li":
                                        _walk_li(li, None, 0)
            except Exception as exc:
                logger.warning("EPUB nav.xhtml parse warning: %s", exc)

        # 4) 按 spine 顺序读取正文
        sections: List[ParsedSection] = []
        for idx, href in enumerate(spine_hrefs):
            if href not in names:
                continue
            raw_html = zf.read(href).decode("utf-8", errors="replace")
            text = html_to_clean_text(raw_html)
            if len(text) < 20:
                continue
            ch_title, vol_title = toc_map.get(href, ("", None))
            if not ch_title:
                first_line = text.splitlines()[0].strip()[:80] if text else f"第{len(sections) + 1}章"
                ch_title = first_line
            sections.append(
                ParsedSection(
                    label=f"第{len(sections) + 1}章",
                    title=ch_title,
                    content=text,
                    volume_label=vol_title if vol_title else None,
                    volume_title=vol_title,
                    meta_data={"epub_href": href},
                )
            )

    return {
        "title": title,
        "author": author,
        "language": language,
        "synopsis": synopsis,
        "sections": sections,
    }


def import_epub_impl(
    db: Session,
    epub_bytes: bytes,
    filename: str,
    pillar: str = "fiction",
    reading_track: str = "mainline",
    work_type: str = "book",
    topic_id: Optional[int] = None,
    title_override: Optional[str] = None,
    author_override: Optional[str] = None,
) -> MultiFormatImportResponse:
    fallback_title = re.sub(r"\.epub$", "", filename or "未命名书籍", flags=re.IGNORECASE)
    parsed = parse_epub_bytes(epub_bytes, fallback_title=fallback_title)
    sections: List[ParsedSection] = parsed["sections"]
    if not sections:
        raise ValueError("EPUB 未解析出有效正文章节")

    work, edition = create_work_with_edition_impl(
        db,
        title=(title_override or parsed["title"]).strip(),
        author=author_override or parsed["author"],
        edition_name="EPUB 导入",
        language=parsed["language"] or "zh",
        work_type=work_type,
        source_format="epub",
        pillar=pillar,
        reading_status="queued",
        reading_track=reading_track,
        synopsis=parsed["synopsis"],
        topic_id=topic_id,
        meta_data={"source_filename": filename},
    )

    batch_items = [
        ChapterBatchItem(
            label=s.label,
            title=s.title,
            content=s.content,
            volume_label=s.volume_label,
            volume_title=s.volume_title,
            meta_data=s.meta_data,
        )
        for s in sections
    ]
    batch_insert_chapters_impl(db, edition.id, batch_items, start_index=0)

    asset = save_content_asset_impl(
        db,
        content_bytes=epub_bytes,
        original_name=filename or f"{work.slug}.epub",
        mime_type="application/epub+zip",
        asset_kind="epub_source",
        work_id=work.id,
        topic_id=topic_id,
    )

    vol_count = (
        db.query(DocumentNode)
        .filter(DocumentNode.edition_id == edition.id, DocumentNode.node_type == "volume")
        .count()
    )
    fresh_work = get_work_impl(db, work.id) or work
    return MultiFormatImportResponse(
        work=fresh_work,
        edition=edition,
        volume_count=vol_count,
        chapter_count=len(sections),
        asset=asset,
        parser_used="epub_stdlib",
        message=f"EPUB 导入成功：共 {vol_count} 卷 / {len(sections)} 章",
    )


# ============================================================================
# 2. PDF Parser (PyMuPDF / fitz: TOC/Section extraction + raw PDF asset)
# ============================================================================


_PAPER_HEADING_RE = re.compile(
    r"^(?:(\d+(?:\.\d+)?)\s+([A-Z][A-Za-z0-9\s\-:,/]{2,70})|(Abstract|Introduction|Related Work|Background|Method|Methodology|Implementation|Evaluation|Experiments?|Results?|Discussion|Limitations?|Conclusion|References|Appendix))$",
    re.MULTILINE,
)


def parse_pdf_bytes(pdf_bytes: bytes, fallback_title: str = "未命名 PDF") -> dict:
    """用 PyMuPDF 提取 PDF 元数据、目录大纲/章节正文。"""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        meta = doc.metadata or {}
        title = (meta.get("title") or "").strip() or fallback_title
        author = (meta.get("author") or "").strip() or None
        page_count = len(doc)

        page_texts = [doc[i].get_text("text") for i in range(page_count)]
        # 若 metadata 无标题，从第一页首行猜测
        if title == fallback_title and page_texts:
            first_lines = [ln.strip() for ln in page_texts[0].splitlines() if len(ln.strip()) > 6]
            if first_lines and len(first_lines[0]) <= 140:
                title = first_lines[0]

        toc = doc.get_toc(simple=True) or []  # [[level, title, page_1based], ...]
        sections: List[ParsedSection] = []
        parser_used = "pymupdf_toc"

        if len(toc) >= 2:
            # 用 PDF 内置书签目录分节（level=1 可作卷或顶层节）
            top_entries = [item for item in toc if item[0] <= 2 and 1 <= item[2] <= page_count]
            current_vol: Optional[str] = None
            has_multi_level = any(item[0] == 2 for item in top_entries) and any(
                item[0] == 1 for item in top_entries
            )
            for idx, (lvl, sec_title, p_start) in enumerate(top_entries):
                p_end = (
                    top_entries[idx + 1][2]
                    if idx + 1 < len(top_entries)
                    else page_count + 1
                )
                # 同一页多节或跨页区间
                start_i = max(0, p_start - 1)
                end_i = max(start_i + 1, min(page_count, p_end - 1 if p_end > p_start else p_start))
                chunk_text = "\n\n".join(
                    f"[Page {p + 1}]\n{page_texts[p].strip()}"
                    for p in range(start_i, end_i)
                    if page_texts[p].strip()
                ).strip()
                if has_multi_level and lvl == 1:
                    current_vol = sec_title.strip()
                if chunk_text:
                    sections.append(
                        ParsedSection(
                            label=f"Section {len(sections) + 1}",
                            title=sec_title.strip()[:160],
                            content=chunk_text,
                            volume_label=current_vol if has_multi_level and lvl == 2 else None,
                            volume_title=current_vol if has_multi_level and lvl == 2 else None,
                            meta_data={"page_start": p_start, "page_end": end_i, "toc_level": lvl},
                        )
                    )

        if not sections:
            # 回退：按学术论文标题正则切分，或按每 4 页分组
            full_text = "\n\n".join(
                f"[Page {i + 1}]\n{t.strip()}" for i, t in enumerate(page_texts) if t.strip()
            )
            matches = list(_PAPER_HEADING_RE.finditer(full_text))
            if len(matches) >= 3:
                parser_used = "pymupdf_heading_regex"
                if matches[0].start() > 40:
                    sections.append(
                        ParsedSection(
                            label="Front",
                            title="Title & Abstract",
                            content=full_text[: matches[0].start()].strip(),
                            meta_data={"page_start": 1},
                        )
                    )
                for idx, m in enumerate(matches):
                    end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
                    heading = m.group(0).strip()
                    body = full_text[m.end() : end_pos].strip()
                    if len(body) >= 20:
                        sections.append(
                            ParsedSection(
                                label=f"Sec {len(sections) + 1}",
                                title=heading[:160],
                                content=body,
                            )
                        )
            else:
                parser_used = "pymupdf_pages"
                chunk_pages = 3 if page_count > 12 else 1
                for i in range(0, page_count, chunk_pages):
                    end_p = min(page_count, i + chunk_pages)
                    body = "\n\n".join(
                        page_texts[p].strip() for p in range(i, end_p) if page_texts[p].strip()
                    ).strip()
                    if body:
                        lbl = f"P{i + 1}" if end_p == i + 1 else f"P{i + 1}-P{end_p}"
                        sections.append(
                            ParsedSection(
                                label=lbl,
                                title=f"第 {i + 1}–{end_p} 页" if end_p > i + 1 else f"第 {i + 1} 页",
                                content=body,
                                meta_data={"page_start": i + 1, "page_end": end_p},
                            )
                        )

        synopsis = None
        if page_texts:
            abs_m = re.search(r"Abstract\s*[:\n]+(.{80,1200}?)(?:\n\s*\n|1[\.\s]+Introduction)", page_texts[0], re.IGNORECASE | re.DOTALL)
            if abs_m:
                synopsis = re.sub(r"\s+", " ", abs_m.group(1)).strip()

        return {
            "title": title,
            "author": author,
            "page_count": page_count,
            "synopsis": synopsis,
            "sections": sections,
            "parser_used": parser_used,
        }
    finally:
        doc.close()


def import_pdf_impl(
    db: Session,
    pdf_bytes: bytes,
    filename: str,
    pillar: str = "tech",
    reading_track: str = "project",
    work_type: str = "paper",
    topic_id: Optional[int] = None,
    title_override: Optional[str] = None,
    author_override: Optional[str] = None,
    source_url: Optional[str] = None,
    extra_meta: Optional[dict] = None,
) -> MultiFormatImportResponse:
    fallback_title = re.sub(r"\.pdf$", "", filename or "未命名论文", flags=re.IGNORECASE)
    parsed = parse_pdf_bytes(pdf_bytes, fallback_title=fallback_title)
    sections: List[ParsedSection] = parsed["sections"]
    if not sections:
        sections = [
            ParsedSection(
                label="Full",
                title="PDF 全文（扫描版或无文本层，请点击原 PDF 预览）",
                content="本 PDF 未检测到可提取文本层，已保留原始 PDF 附件供对照阅读。",
            )
        ]

    meta_data = {
        "source_filename": filename,
        "page_count": parsed["page_count"],
        **(extra_meta or {}),
    }
    work, edition = create_work_with_edition_impl(
        db,
        title=(title_override or parsed["title"]).strip()[:200],
        author=author_override or parsed["author"],
        edition_name="PDF 导入",
        language="en" if work_type == "paper" else "zh",
        work_type=work_type,
        source_format="pdf",
        pillar=pillar,
        reading_status="queued",
        reading_track=reading_track,
        synopsis=parsed["synopsis"],
        source_url=source_url,
        topic_id=topic_id,
        meta_data=meta_data,
    )

    batch_items = [
        ChapterBatchItem(
            label=s.label,
            title=s.title,
            content=s.content,
            volume_label=s.volume_label,
            volume_title=s.volume_title,
            meta_data=s.meta_data,
        )
        for s in sections
    ]
    batch_insert_chapters_impl(db, edition.id, batch_items, start_index=0)

    asset = save_content_asset_impl(
        db,
        content_bytes=pdf_bytes,
        original_name=filename or f"{work.slug}.pdf",
        mime_type="application/pdf",
        asset_kind="pdf_source",
        work_id=work.id,
        topic_id=topic_id,
        meta_data={"page_count": parsed["page_count"]},
    )

    vol_count = (
        db.query(DocumentNode)
        .filter(DocumentNode.edition_id == edition.id, DocumentNode.node_type == "volume")
        .count()
    )
    fresh_work = get_work_impl(db, work.id) or work
    return MultiFormatImportResponse(
        work=fresh_work,
        edition=edition,
        volume_count=vol_count,
        chapter_count=len(sections),
        asset=asset,
        parser_used=parsed["parser_used"],
        message=f"PDF 导入成功：{parsed['page_count']} 页 / {len(sections)} 节（已保留原始 PDF）",
    )


# ============================================================================
# 3. arXiv Paper Importer (Atom Metadata + arxiv.org/html + optional PDF Asset)
# ============================================================================


_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)")


def extract_arxiv_id(raw: str) -> str:
    m = _ARXIV_ID_RE.search((raw or "").strip())
    if not m:
        raise ValueError(f"无法识别 arXiv ID：{raw}")
    return m.group(1)


def parse_arxiv_html_sections(html_str: str) -> List[ParsedSection]:
    """解析 arxiv.org/html 页面中的 <section class='ltx_section'> 为干净分节正文。"""
    sections: List[ParsedSection] = []
    # 匹配 ltx_section 块（轻量正则切片，避免引入 lxml/bs4 重依赖）
    sec_pattern = re.compile(
        r"<section[^>]*class=[\"'][^\"']*ltx_section[^\"']*[\"'][^>]*>(.*?)</section>",
        re.DOTALL | re.IGNORECASE,
    )
    h_pattern = re.compile(r"<h[1-4][^>]*>(.*?)</h[1-4]>", re.DOTALL | re.IGNORECASE)

    for m in sec_pattern.finditer(html_str or ""):
        block = m.group(1)
        hm = h_pattern.search(block)
        heading = html_to_clean_text(hm.group(1)) if hm else f"Section {len(sections) + 1}"
        body = html_to_clean_text(block[hm.end() :] if hm else block)
        if len(body) >= 30:
            sections.append(
                ParsedSection(
                    label=f"Sec {len(sections) + 1}",
                    title=heading[:160],
                    content=body,
                )
            )
    return sections


def import_arxiv_impl(
    db: Session,
    arxiv_id_or_url: str,
    pillar: str = "tech",
    reading_track: str = "project",
    topic_id: Optional[int] = None,
    download_pdf: bool = True,
) -> MultiFormatImportResponse:
    arxiv_id = extract_arxiv_id(arxiv_id_or_url)
    api_url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    abs_url = f"https://arxiv.org/abs/{arxiv_id}"
    html_url = f"https://arxiv.org/html/{arxiv_id}"
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(api_url)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", ns)
        if entry is None:
            raise ValueError(f"arXiv 未找到论文：{arxiv_id}")

        title = re.sub(r"\s+", " ", (entry.findtext("atom:title", default="", namespaces=ns) or "")).strip()
        summary = re.sub(r"\s+", " ", (entry.findtext("atom:summary", default="", namespaces=ns) or "")).strip()
        published = (entry.findtext("atom:published", default="", namespaces=ns) or "")[:10]
        authors = [
            (a.findtext("atom:name", default="", namespaces=ns) or "").strip()
            for a in entry.findall("atom:author", ns)
        ]
        author_str = ", ".join(a for a in authors if a)[:200] or None
        categories = [c.attrib.get("term", "") for c in entry.findall("atom:category", ns) if c.attrib.get("term")]

        # 尝试抓取官方 HTML 版本（分节质量最高）
        sections: List[ParsedSection] = []
        parser_used = "arxiv_html"
        try:
            h_resp = client.get(html_url)
            if h_resp.status_code == 200 and "ltx_section" in h_resp.text:
                sections = parse_arxiv_html_sections(h_resp.text)
        except Exception as exc:
            logger.info("arxiv html fetch skipped for %s: %s", arxiv_id, exc)

        # 下载原 PDF（供对照看公式插图，或作为 HTML 不可用时的正文回退）
        pdf_bytes: Optional[bytes] = None
        if download_pdf or not sections:
            try:
                p_resp = client.get(pdf_url, timeout=60.0)
                if p_resp.status_code == 200 and p_resp.content[:4] == b"%PDF":
                    pdf_bytes = p_resp.content
            except Exception as exc:
                logger.warning("arxiv pdf download failed for %s: %s", arxiv_id, exc)

    extra_meta = {
        "arxiv_id": arxiv_id,
        "published": published,
        "categories": categories,
        "abs_url": abs_url,
    }

    if not sections and pdf_bytes:
        return import_pdf_impl(
            db,
            pdf_bytes=pdf_bytes,
            filename=f"{arxiv_id}.pdf",
            pillar=pillar,
            reading_track=reading_track,
            work_type="paper",
            topic_id=topic_id,
            title_override=title or arxiv_id,
            author_override=author_str,
            source_url=abs_url,
            extra_meta=extra_meta,
        )

    # 始终把 Abstract 放在首节，便于快速浏览
    final_sections: List[ParsedSection] = []
    if summary:
        final_sections.append(
            ParsedSection(label="Abstract", title="Abstract", content=summary)
        )
    final_sections.extend(sections)
    if not final_sections:
        parser_used = "arxiv_metadata_only"
        final_sections.append(
            ParsedSection(label="Info", title="论文摘要", content=summary or title)
        )

    work, edition = create_work_with_edition_impl(
        db,
        title=title or arxiv_id,
        author=author_str,
        edition_name=f"arXiv {arxiv_id}",
        language="en",
        work_type="paper",
        source_format="arxiv_html" if sections else "arxiv_meta",
        pillar=pillar,
        reading_status="queued",
        reading_track=reading_track,
        synopsis=summary,
        source_url=abs_url,
        topic_id=topic_id,
        meta_data=extra_meta,
    )
    batch_insert_chapters_impl(
        db,
        edition.id,
        [ChapterBatchItem(label=s.label, title=s.title, content=s.content) for s in final_sections],
        start_index=0,
    )

    asset = None
    if pdf_bytes:
        asset = save_content_asset_impl(
            db,
            content_bytes=pdf_bytes,
            original_name=f"{arxiv_id}.pdf",
            mime_type="application/pdf",
            asset_kind="pdf_source",
            work_id=work.id,
            topic_id=topic_id,
            meta_data={"arxiv_id": arxiv_id},
        )

    fresh_work = get_work_impl(db, work.id) or work
    return MultiFormatImportResponse(
        work=fresh_work,
        edition=edition,
        volume_count=0,
        chapter_count=len(final_sections),
        asset=asset,
        parser_used=parser_used,
        message=f"arXiv 论文 {arxiv_id} 导入成功：{len(final_sections)} 节"
        + ("（已附带原 PDF）" if asset else ""),
    )
