# -*- coding: utf-8 -*-
# @file workbench.py
# @brief SailZen Workbench 领域逻辑（聚合启动、项目语义绑定、AI Context Pack、原创章节同步）
# @author sailing-innocent
# @date 2026-11-27
# @version 1.0
# ---------------------------------

from __future__ import annotations

import logging
import re
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from sail_server.application.dto.text import DocumentNodeResponse
from sail_server.application.dto.workbench import (
    ChapterSyncRequest,
    ChapterSyncResponse,
    ProjectArchetype,
    WorkbenchBootstrapResponse,
    WorkbenchContextPackResponse,
    WorkbenchProjectItem,
    WorkbenchProjectMeta,
    WorkbenchProjectMetaUpdateRequest,
)
from sail_server.model.content_library import get_topic_detail_impl, list_topics_impl
from sail_server.model.rhythm import (
    RhythmBadRequestError,
    RhythmNotFoundError,
    get_dashboard_impl,
    list_timeline_range_impl,
    venture_progress_impl,
)
from sail_server.model.text import sanitize_text
from sail_server.model.tick import STATUS_PENDING, list_tickets_impl
from sailzen_orm.rhythm import RhythmAffair
from sailzen_orm.text import DocumentNode, Edition, NoteItem

logger = logging.getLogger(__name__)


def _derive_slug(title: str, venture_id: int) -> str:
    ascii_part = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if ascii_part:
        return ascii_part[:60]
    return f"venture-{venture_id}"


def extract_workbench_meta(affair: RhythmAffair) -> WorkbenchProjectMeta:
    """从 RhythmAffair.kind_meta 安全解析工作台语义配置。"""
    raw_kind_meta = affair.kind_meta if isinstance(affair.kind_meta, dict) else {}
    raw_wb = raw_kind_meta.get("workbench")
    if isinstance(raw_wb, dict):
        try:
            meta = WorkbenchProjectMeta.model_validate(raw_wb)
            if not meta.slug:
                meta.slug = _derive_slug(affair.title or "", affair.id)
            return meta
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Invalid workbench meta on venture %s: %s", affair.id, exc)
    return WorkbenchProjectMeta(slug=_derive_slug(affair.title or "", affair.id))


def get_workbench_bootstrap_impl(
    db: Session,
    target_date: Optional[date_type] = None,
) -> WorkbenchBootstrapResponse:
    """单次往返聚合工作台核心视图数据（1 RTT 点亮 4 面板）。"""
    day = target_date or datetime.now().date()
    degraded: List[str] = []

    dashboard = get_dashboard_impl(db, day)
    if dashboard.degraded:
        degraded.extend(dashboard.degraded)

    # 批量加载 Venture ORM 以读取 kind_meta.workbench
    venture_ids = [p.affair_id for p in dashboard.projects]
    venture_map: Dict[int, RhythmAffair] = {}
    if venture_ids:
        rows = db.query(RhythmAffair).filter(RhythmAffair.id.in_(venture_ids)).all()
        venture_map = {r.id: r for r in rows}

    # 如果某 Venture 未显式填 topic_id，尝试按 rhythm_venture_id 反查关联 Topic
    topics = []
    topic_by_venture: Dict[int, int] = {}
    try:
        topics = list_topics_impl(db, status=None)
        for t in topics:
            if t.rhythm_venture_id and t.rhythm_venture_id not in topic_by_venture:
                topic_by_venture[t.rhythm_venture_id] = t.id
    except Exception as exc:
        logger.warning("Workbench bootstrap failed loading topics: %s", exc)
        degraded.append("topics")

    projects: List[WorkbenchProjectItem] = []
    for prog in dashboard.projects:
        orm_row = venture_map.get(prog.affair_id)
        wb_meta = (
            extract_workbench_meta(orm_row)
            if orm_row is not None
            else WorkbenchProjectMeta(slug=_derive_slug(prog.title, prog.affair_id))
        )
        if wb_meta.topic_id is None and prog.affair_id in topic_by_venture:
            wb_meta.topic_id = topic_by_venture[prog.affair_id]
        projects.append(WorkbenchProjectItem(progress=prog, workbench=wb_meta))

    pending_tickets = []
    try:
        pending_tickets = list_tickets_impl(db, status=STATUS_PENDING, limit=20)
    except Exception as exc:
        logger.warning("Workbench bootstrap failed loading tickets: %s", exc)
        degraded.append("tickets")

    return WorkbenchBootstrapResponse(
        date=day,
        timeline=dashboard.timeline,
        projects=projects,
        focus_affairs=dashboard.focus_affairs,
        overdue_affairs=dashboard.overdue_affairs,
        topics=topics,
        pending_tickets=pending_tickets,
        degraded=degraded,
    )


def update_workbench_project_meta_impl(
    db: Session,
    venture_id: int,
    req: WorkbenchProjectMetaUpdateRequest,
) -> WorkbenchProjectItem:
    """更新 Venture 项目的跨机器语义元数据。"""
    affair = db.get(RhythmAffair, venture_id)
    if not affair:
        raise RhythmNotFoundError(f"venture {venture_id} not found")
    if affair.kind != "venture":
        raise RhythmBadRequestError(f"affair {venture_id} is kind={affair.kind}, expected venture")

    current = extract_workbench_meta(affair)
    merged: Dict[str, Any] = current.model_dump()
    patch = req.model_dump(exclude_unset=True)
    for k, v in patch.items():
        if v is not None or k in ("topic_id", "original_work_id"):
            merged[k] = v

    validated = WorkbenchProjectMeta.model_validate(merged)
    if not validated.slug:
        validated.slug = _derive_slug(affair.title or "", affair.id)

    kind_meta = dict(affair.kind_meta) if isinstance(affair.kind_meta, dict) else {}
    kind_meta["workbench"] = validated.model_dump(mode="json")
    affair.kind_meta = kind_meta
    db.commit()
    db.refresh(affair)

    progress = venture_progress_impl(db, venture_id)
    return WorkbenchProjectItem(progress=progress, workbench=validated)


def build_workbench_context_pack_impl(
    db: Session,
    venture_id: int,
) -> WorkbenchContextPackResponse:
    """聚合项目进度、里程碑、近 7 天时间块与关联内容，输出精简 Markdown 供本地 Agent 使用。"""
    affair = db.get(RhythmAffair, venture_id)
    if not affair:
        raise RhythmNotFoundError(f"venture {venture_id} not found")
    if affair.kind != "venture":
        raise RhythmBadRequestError(f"affair {venture_id} is kind={affair.kind}, expected venture")

    meta = extract_workbench_meta(affair)
    progress = venture_progress_impl(db, venture_id)

    lines: List[str] = [
        f"# SailZen Project Context: {affair.title}",
        "",
        f"- **Slug**: `{meta.slug}`",
        f"- **Archetype**: `{meta.archetype.value}`",
        f"- **State**: `{affair.state}`",
    ]
    if progress.target_date:
        lines.append(f"- **Target Date**: {progress.target_date} (days left: {progress.days_left})")
    if meta.vault_namespace:
        lines.append(f"- **Vault Namespace**: `{meta.vault_namespace}.*`")
    if meta.repo_hints:
        lines.append(f"- **Repo Hints**: {', '.join(f'`{h}`' for h in meta.repo_hints)}")
    milestones_total = len(progress.milestones)
    milestones_done = sum(
        1 for m in progress.milestones if m.state.value in ("DONE", "COMPLETED")
    )
    lines.append(
        f"- **Progress**: {milestones_done}/{milestones_total} milestones "
        f"({round(progress.completion_ratio * 100)}%), recent 14d focus: {progress.recent_14d_hours:.1f}h"
    )
    if affair.description:
        lines.extend(["", "## Description", "", affair.description.strip()])

    # 里程碑清单
    lines.extend(["", "## Milestones", ""])
    if progress.milestones:
        for ms in progress.milestones:
            mark = "x" if ms.state.value in ("DONE", "COMPLETED") else " "
            ddl = f" (ddl: {ms.urgency_ddl.date()})" if ms.urgency_ddl else ""
            lines.append(f"- [{mark}] #{ms.id} {ms.title}{ddl}")
    else:
        lines.append("- (No milestones yet)")

    # 近 7 天该项目相关时间块
    today = datetime.now().date()
    start_day = today - timedelta(days=6)
    try:
        tl_range = list_timeline_range_impl(db, start_day, today)
        milestone_ids = {m.id for m in progress.milestones} | {venture_id}
        recent_blocks: List[str] = []
        for day_item in tl_range.days:
            for blk in day_item.blocks:
                if blk.affair_id in milestone_ids:
                    title = blk.affair_title or (blk.ref or {}).get("label") or blk.block_type.value
                    recent_blocks.append(
                        f"- {day_item.date} {blk.start_time.strftime('%H:%M')}-{blk.end_time.strftime('%H:%M')} "
                        f"[{blk.status.value}] {title}"
                    )
        if recent_blocks:
            lines.extend(["", "## Recent 7d Rhythm Blocks", "", *recent_blocks[-12:]])
    except Exception as exc:
        logger.warning("Context pack skipped timeline range: %s", exc)

    # 关联 Content Topic 书单/资料
    if meta.topic_id:
        detail = get_topic_detail_impl(db, meta.topic_id)
        if detail:
            lines.extend(["", f"## Linked Content Topic: {detail.topic.title}", ""])
            if detail.topic.description:
                lines.append(detail.topic.description.strip())
                lines.append("")
            for item in detail.works[:15]:
                pct = f"{round(item.progress_pct)}%" if item.progress_pct is not None else "-"
                lines.append(
                    f"- [{item.work.reading_status}] **{item.work.title}** "
                    f"(pillar: {item.work.pillar}, progress: {pct}, vault: `{item.work.vault_slug or '-'}`)"
                )

    # 关联原创作品 NoteItems（人物/设定/大纲）
    if meta.original_work_id:
        note_items = (
            db.query(NoteItem)
            .filter(NoteItem.work_id == meta.original_work_id)
            .order_by(NoteItem.category, NoteItem.id)
            .limit(30)
            .all()
        )
        if note_items:
            lines.extend(["", "## Story Bible / NoteItems", ""])
            for ni in note_items:
                lines.append(f"- [{ni.category}] {ni.title or ni.slug} (`{ni.setting_file}`)")

    return WorkbenchContextPackResponse(
        venture_id=venture_id,
        slug=meta.slug,
        title=affair.title,
        archetype=meta.archetype,
        markdown="\n".join(lines).strip() + "\n",
        generated_at=datetime.now(),
    )


def _count_words_and_chars(text: str) -> tuple[int, int]:
    """中英文混合字数/字符数统计（去掉纯空白）。"""
    char_count = len(text)
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_words = len(re.findall(r"[A-Za-z0-9_]+", text))
    return cjk_chars + latin_words, char_count


def sync_edition_chapter_impl(
    db: Session,
    edition_id: int,
    req: ChapterSyncRequest,
) -> Optional[ChapterSyncResponse]:
    """幂等创建或更新原创作品单章，并同步刷新 Edition 总字数统计。"""
    edition = db.get(Edition, edition_id)
    if not edition:
        return None

    node: Optional[DocumentNode] = None
    if req.node_id is not None:
        candidate = db.get(DocumentNode, req.node_id)
        if candidate and candidate.edition_id == edition_id:
            node = candidate

    if node is None and req.source_slug:
        existing_nodes = (
            db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id,
                DocumentNode.node_type == "chapter",
            )
            .all()
        )
        for cand in existing_nodes:
            md = cand.meta_data if isinstance(cand.meta_data, dict) else {}
            if md.get("source_slug") == req.source_slug:
                node = cand
                break

    cleaned_content = sanitize_text(req.content or "")
    word_count, char_count = _count_words_and_chars(cleaned_content)

    merged_meta: Dict[str, Any] = dict(req.meta_data or {})
    if req.source_slug:
        merged_meta["source_slug"] = req.source_slug

    if node is not None:
        action = "updated"
        if req.label:
            node.label = req.label
        node.title = req.title
        node.raw_text = cleaned_content
        node.word_count = word_count
        node.char_count = char_count
        if req.parent_id is not None:
            node.parent_id = req.parent_id or None
        if req.sort_index is not None:
            node.sort_index = req.sort_index
        existing_meta = dict(node.meta_data) if isinstance(node.meta_data, dict) else {}
        existing_meta.update(merged_meta)
        node.meta_data = existing_meta
    else:
        action = "created"
        if req.sort_index is not None:
            sort_index = req.sort_index
        else:
            max_idx = (
                db.query(func.max(DocumentNode.sort_index))
                .filter(
                    DocumentNode.edition_id == edition_id,
                    DocumentNode.node_type == "chapter",
                )
                .scalar()
            )
            sort_index = (max_idx + 1) if max_idx is not None else 0

        depth = 1 if req.parent_id else 0
        path = f"C{sort_index + 1:04d}"
        node = DocumentNode(
            edition_id=edition_id,
            parent_id=req.parent_id,
            node_type="chapter",
            sort_index=sort_index,
            depth=depth,
            label=req.label or f"第{sort_index + 1}章",
            title=req.title,
            raw_text=cleaned_content,
            word_count=word_count,
            char_count=char_count,
            path=path,
            status="active",
            meta_data=merged_meta,
        )
        db.add(node)

    db.flush()

    totals = (
        db.query(
            func.coalesce(func.sum(DocumentNode.char_count), 0),
            func.coalesce(func.sum(DocumentNode.word_count), 0),
        )
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "chapter",
            DocumentNode.status == "active",
        )
        .one()
    )
    edition.char_count = int(totals[0] or 0)
    edition.word_count = int(totals[1] or 0)

    db.commit()
    db.refresh(node)
    db.refresh(edition)

    return ChapterSyncResponse(
        action=action,
        edition_id=edition_id,
        node=DocumentNodeResponse.model_validate(node),
        edition_char_count=edition.char_count or 0,
        edition_word_count=edition.word_count or 0,
    )
