# -*- coding: utf-8 -*-
# @file content_library.py
# @brief Content 2.0 Core Model Layer: Volumes/TOC, Cloud Reading Progress, Topics<->Rhythm, Assets & Vault Bridge
# @author sailing-innocent
# @date 2026-11-26
# @version 1.0
# ---------------------------------

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from sail_server.application.dto.text import (
    AutoVolumePreviewItem,
    AutoVolumeRequest,
    AutoVolumeResponse,
    ContentAssetResponse,
    ContentTopicCreateRequest,
    ContentTopicDetailResponse,
    ContentTopicResponse,
    ContentTopicUpdateRequest,
    ContentTopicWorkAttachRequest,
    ContentTopicWorkItem,
    EditionTocResponse,
    PillarStatItem,
    ReadingOverviewResponse,
    ReadingProgressResponse,
    ReadingProgressSyncRequest,
    ReadingProgressSyncResponse,
    ReadingProgressUpsertRequest,
    ReadingSessionCreateRequest,
    ReadingSessionResponse,
    TocChapterItem,
    TocVolumeItem,
    TopicPushRhythmTaskRequest,
    TopicRhythmTaskSummary,
    VaultNoteIndexItem,
    VaultNoteIndexSyncRequest,
    VaultNoteIndexSyncResponse,
    VolumeAssignRequest,
    VolumeCreateRequest,
    WorkClipsExportResponse,
)
from sail_server.config.paths import SERVER_DATA_DIR, get_content_assets_dir
from sail_server.model.text import _enrich_works_batch, _make_slug
from sailzen_orm.rhythm import RhythmAffair
from sailzen_orm.text import (
    ContentAsset,
    ContentTopic,
    ContentTopicWork,
    DocumentNode,
    Edition,
    NoteItem,
    ReadingProgress,
    ReadingSession,
    VaultNoteIndex,
    Work,
)

logger = logging.getLogger(__name__)

MAX_CONTENT_ASSET_BYTES = 100 * 1024 * 1024  # 100MB (supports SIGGRAPH PDFs / EPUBs)

_VOLUME_PREFIX_RE = re.compile(
    r"^(第[一二三四五六七八九十百千万零〇\d]+[卷部篇集]|卷[一二三四五六七八九十百千万零〇\d]+|Volume\s+\d+|Part\s+\d+|Book\s+\d+)\s*[:：\-—·\s]*([^\s第]*.*)?$",
    re.IGNORECASE,
)


# ============================================================================
# 1. Volume & Tree TOC Management
# ============================================================================


def get_edition_toc_impl(db: Session, edition_id: int) -> Optional[EditionTocResponse]:
    """获取版本的分卷树形目录（卷 + 卷内章节 + 未归卷章节）。"""
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return None

    volumes = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "volume",
        )
        .order_by(DocumentNode.sort_index, DocumentNode.id)
        .all()
    )
    chapters = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "chapter",
        )
        .order_by(DocumentNode.sort_index, DocumentNode.id)
        .all()
    )

    by_parent: Dict[int, List[TocChapterItem]] = {}
    ungrouped: List[TocChapterItem] = []
    valid_vol_ids = {v.id for v in volumes}

    for ch in chapters:
        item = TocChapterItem(
            id=ch.id,
            parent_id=ch.parent_id,
            sort_index=ch.sort_index,
            label=ch.label,
            title=ch.title,
            char_count=ch.char_count,
            path=ch.path,
            node_type=ch.node_type,
        )
        if ch.parent_id and ch.parent_id in valid_vol_ids:
            by_parent.setdefault(ch.parent_id, []).append(item)
        else:
            ungrouped.append(item)

    vol_items: List[TocVolumeItem] = []
    for v in volumes:
        chs = by_parent.get(v.id, [])
        meta = v.meta_data if isinstance(v.meta_data, dict) else {}
        vol_items.append(
            TocVolumeItem(
                id=v.id,
                sort_index=v.sort_index,
                label=v.label,
                title=v.title or v.label or f"第{v.sort_index + 1}卷",
                summary=str(meta.get("summary") or ""),
                chapter_count=len(chs),
                total_chars=sum(int(c.char_count or 0) for c in chs),
                chapters=chs,
            )
        )

    return EditionTocResponse(
        edition_id=edition_id,
        total_chapters=len(chapters),
        volume_count=len(vol_items),
        volumes=vol_items,
        ungrouped_chapters=ungrouped,
    )


def create_volume_impl(
    db: Session, edition_id: int, data: VolumeCreateRequest
) -> Optional[TocVolumeItem]:
    """创建分卷节点，并可选将 [start_sort_index, end_sort_index] 区间章节归入该卷。"""
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return None

    existing_count = (
        db.query(func.count(DocumentNode.id))
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "volume",
        )
        .scalar()
        or 0
    )
    sort_index = data.sort_index if data.sort_index is not None else int(existing_count)
    label = (data.label or f"第{sort_index + 1}卷").strip()
    title = (data.title or label).strip()

    vol = DocumentNode(
        edition_id=edition_id,
        parent_id=None,
        node_type="volume",
        sort_index=sort_index,
        depth=0,
        label=label,
        title=title,
        raw_text=None,
        word_count=0,
        char_count=0,
        path=f"V{sort_index:04d}",
        status="active",
        meta_data={"summary": data.summary or ""},
    )
    db.add(vol)
    db.flush()

    assigned: List[DocumentNode] = []
    if data.start_sort_index is not None and data.end_sort_index is not None:
        assigned = (
            db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id,
                DocumentNode.node_type == "chapter",
                DocumentNode.sort_index >= data.start_sort_index,
                DocumentNode.sort_index <= data.end_sort_index,
            )
            .order_by(DocumentNode.sort_index)
            .all()
        )
        for ch in assigned:
            ch.parent_id = vol.id
            ch.path = f"{vol.path}.{ch.sort_index:04d}"

    db.commit()
    db.refresh(vol)

    chapters_dto = [
        TocChapterItem(
            id=c.id,
            parent_id=c.parent_id,
            sort_index=c.sort_index,
            label=c.label,
            title=c.title,
            char_count=c.char_count,
            path=c.path,
            node_type=c.node_type,
        )
        for c in assigned
    ]
    return TocVolumeItem(
        id=vol.id,
        sort_index=vol.sort_index,
        label=vol.label,
        title=vol.title or label,
        summary=data.summary or "",
        chapter_count=len(chapters_dto),
        total_chars=sum(int(c.char_count or 0) for c in chapters_dto),
        chapters=chapters_dto,
    )


def assign_chapters_to_volume_impl(
    db: Session, edition_id: int, volume_id: int, data: VolumeAssignRequest
) -> Optional[int]:
    """将指定节点 ID 列表或 sort_index 区间的章节归入指定分卷。"""
    vol = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.id == volume_id,
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "volume",
        )
        .first()
    )
    if not vol:
        return None

    q = db.query(DocumentNode).filter(
        DocumentNode.edition_id == edition_id,
        DocumentNode.node_type == "chapter",
    )
    if data.node_ids:
        q = q.filter(DocumentNode.id.in_(data.node_ids))
    elif data.start_sort_index is not None and data.end_sort_index is not None:
        q = q.filter(
            DocumentNode.sort_index >= data.start_sort_index,
            DocumentNode.sort_index <= data.end_sort_index,
        )
    else:
        return 0

    nodes = q.all()
    for ch in nodes:
        ch.parent_id = vol.id
        ch.path = f"{vol.path}.{ch.sort_index:04d}"
    db.commit()
    return len(nodes)


def delete_volume_impl(db: Session, edition_id: int, volume_id: int) -> bool:
    """删除分卷节点，同时将卷下章节安全解绑回顶层（不删章节正文）。"""
    vol = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.id == volume_id,
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "volume",
        )
        .first()
    )
    if not vol:
        return False

    children = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.parent_id == vol.id,
        )
        .all()
    )
    for ch in children:
        ch.parent_id = None
        ch.path = f"{ch.sort_index:04d}"
    db.flush()
    db.delete(vol)
    db.commit()
    return True


def auto_volume_edition_impl(
    db: Session, edition_id: int, req: AutoVolumeRequest
) -> Optional[AutoVolumeResponse]:
    """自动识别扁平小说的分卷结构（支持先预览 dry_run=True 再落库）。"""
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        return None

    chapters = (
        db.query(DocumentNode)
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "chapter",
        )
        .order_by(DocumentNode.sort_index)
        .all()
    )
    if not chapters:
        return AutoVolumeResponse(
            edition_id=edition_id, dry_run=req.dry_run, strategy="empty"
        )

    # 策略 1：优先检测章节 label/title 中自带的卷前缀（如 "第一卷 绯红 第一章..."）
    detected_groups: List[Tuple[str, str, List[DocumentNode]]] = []
    current_label = ""
    current_title = ""
    current_bucket: List[DocumentNode] = []

    for ch in chapters:
        combined = f"{ch.label or ''} {ch.title or ''}".strip()
        m = _VOLUME_PREFIX_RE.match(combined)
        if m:
            vol_label = m.group(1).strip()
            rest = (m.group(2) or "").strip()
            # 去掉 rest 尾部如果紧跟 "第X章"
            rest = re.split(r"\s+第[一二三四五六七八九十百千万零〇\d]+章", rest)[0].strip()
            vol_title = rest or vol_label
            if vol_label != current_label:
                if current_bucket:
                    detected_groups.append(
                        (current_label or "序卷", current_title or "未分卷", current_bucket)
                    )
                current_label = vol_label
                current_title = vol_title
                current_bucket = [ch]
            else:
                current_bucket.append(ch)
        else:
            current_bucket.append(ch)

    if current_bucket and current_label:
        detected_groups.append((current_label, current_title, current_bucket))

    strategy = "volume_prefix"
    if len(detected_groups) <= 1:
        # 策略 2：检测按固定章数分卷（仅在用户指定 chunk_size 或章节数 >= 100 时启用）
        chunk = req.chapter_chunk_size or (100 if len(chapters) >= 120 else 50)
        strategy = f"fixed_chunk_{chunk}"
        detected_groups = []
        for idx in range(0, len(chapters), chunk):
            sub = chapters[idx : idx + chunk]
            vol_no = idx // chunk + 1
            first_lbl = sub[0].label or f"#{sub[0].sort_index + 1}"
            last_lbl = sub[-1].label or f"#{sub[-1].sort_index + 1}"
            detected_groups.append(
                (f"第{vol_no}卷", f"{first_lbl} ~ {last_lbl}", sub)
            )

    previews = [
        AutoVolumePreviewItem(
            label=lbl,
            title=ttl,
            start_sort_index=chs[0].sort_index,
            end_sort_index=chs[-1].sort_index,
            chapter_count=len(chs),
        )
        for lbl, ttl, chs in detected_groups
    ]

    if req.dry_run:
        return AutoVolumeResponse(
            edition_id=edition_id,
            dry_run=True,
            strategy=strategy,
            volumes=previews,
            applied_volumes=0,
            assigned_chapters=0,
        )

    # 先解绑并清理旧分卷，再按新规划重建
    for ch in chapters:
        ch.parent_id = None
    db.flush()
    db.query(DocumentNode).filter(
        DocumentNode.edition_id == edition_id,
        DocumentNode.node_type == "volume",
    ).delete(synchronize_session=False)
    db.flush()

    assigned_total = 0
    for idx, (lbl, ttl, chs) in enumerate(detected_groups):
        vol = DocumentNode(
            edition_id=edition_id,
            parent_id=None,
            node_type="volume",
            sort_index=idx,
            depth=0,
            label=lbl,
            title=ttl,
            raw_text=None,
            word_count=0,
            char_count=0,
            path=f"V{idx:04d}",
            status="active",
            meta_data={"auto_volume_strategy": strategy},
        )
        db.add(vol)
        db.flush()
        for ch in chs:
            ch.parent_id = vol.id
            ch.path = f"{vol.path}.{ch.sort_index:04d}"
            assigned_total += 1

    db.commit()
    return AutoVolumeResponse(
        edition_id=edition_id,
        dry_run=False,
        strategy=strategy,
        volumes=previews,
        applied_volumes=len(detected_groups),
        assigned_chapters=assigned_total,
    )


# ============================================================================
# 2. Cloud Reading Progress, Sessions & Stats
# ============================================================================


def _compute_progress_pct(db: Session, edition_id: int, sort_index: int) -> float:
    """按版本章节总数与当前序号计算平滑阅读百分比（0~100）。"""
    total = (
        db.query(func.count(DocumentNode.id))
        .filter(
            DocumentNode.edition_id == edition_id,
            DocumentNode.node_type == "chapter",
        )
        .scalar()
        or 0
    )
    if total <= 0:
        return 0.0
    pos = max(0, min(int(sort_index) + 1, int(total)))
    return round(min(100.0, pos * 100.0 / float(total)), 1)


def get_reading_progress_impl(
    db: Session, work_id: int, user_id: int = 1
) -> Optional[ReadingProgressResponse]:
    row = (
        db.query(ReadingProgress)
        .filter(ReadingProgress.user_id == user_id, ReadingProgress.work_id == work_id)
        .first()
    )
    if not row:
        return None
    return ReadingProgressResponse.model_validate(row)


def upsert_reading_progress_impl(
    db: Session,
    work_id: int,
    data: ReadingProgressUpsertRequest,
    user_id: int = 1,
) -> Tuple[Optional[ReadingProgressResponse], bool]:
    """幂等更新阅读进度（按 last_read_at LWW 解决多端冲突）。返回 (response, applied)。"""
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        return None, False

    now = datetime.now()
    incoming_ts = data.last_read_at or now
    # 规范为 naive datetime，避免与数据库 naive TIMESTAMP 比较报错
    if incoming_ts.tzinfo is not None:
        incoming_ts = incoming_ts.replace(tzinfo=None)

    row = (
        db.query(ReadingProgress)
        .filter(ReadingProgress.user_id == user_id, ReadingProgress.work_id == work_id)
        .first()
    )

    if row is not None and row.last_read_at is not None and incoming_ts < row.last_read_at:
        # 远端已有更新的进度，跳过过期上报（但仍累加 delta_seconds 若有）
        if data.delta_seconds > 0:
            row.total_read_seconds = (row.total_read_seconds or 0) + int(data.delta_seconds)
            db.commit()
            db.refresh(row)
        return ReadingProgressResponse.model_validate(row), False

    pct = _compute_progress_pct(db, data.edition_id, data.sort_index)
    node_id = data.node_id
    if node_id is None:
        node = (
            db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == data.edition_id,
                DocumentNode.node_type == "chapter",
                DocumentNode.sort_index == data.sort_index,
            )
            .first()
        )
        if node:
            node_id = node.id

    if row is None:
        row = ReadingProgress(
            user_id=user_id,
            work_id=work_id,
            edition_id=data.edition_id,
            node_id=node_id,
            sort_index=data.sort_index,
            char_offset=data.char_offset,
            scroll_offset=data.scroll_offset,
            page_index=data.page_index,
            mode=data.mode,
            progress_pct=pct,
            total_read_seconds=max(0, int(data.delta_seconds)),
            client_device=data.client_device[:64],
            last_read_at=incoming_ts,
            updated_at=now,
        )
        db.add(row)
    else:
        row.edition_id = data.edition_id
        row.node_id = node_id
        row.sort_index = data.sort_index
        row.char_offset = data.char_offset
        row.scroll_offset = data.scroll_offset
        row.page_index = data.page_index
        row.mode = data.mode
        row.progress_pct = pct
        if data.delta_seconds > 0:
            row.total_read_seconds = (row.total_read_seconds or 0) + int(data.delta_seconds)
        row.client_device = data.client_device[:64]
        row.last_read_at = incoming_ts
        row.updated_at = now

    # 自动推进作品阅读态：queued/inbox 有实质阅读进度时转入 reading
    if (work.reading_status in (None, "queued", "inbox")) and (
        data.sort_index > 0 or data.char_offset > 0 or data.scroll_offset > 0 or pct > 0
    ):
        work.reading_status = "reading"

    db.commit()
    db.refresh(row)
    return ReadingProgressResponse.model_validate(row), True


def sync_reading_progress_batch_impl(
    db: Session, req: ReadingProgressSyncRequest, user_id: int = 1
) -> ReadingProgressSyncResponse:
    """多端批量进度同步（Android 离线重连批量对账，返回全量最新云端进度列表）。"""
    updated = 0
    skipped = 0
    for item in req.items:
        resp, applied = upsert_reading_progress_impl(
            db,
            work_id=item.work_id,
            data=ReadingProgressUpsertRequest(
                edition_id=item.edition_id,
                node_id=item.node_id,
                sort_index=item.sort_index,
                char_offset=item.char_offset,
                scroll_offset=item.scroll_offset,
                page_index=item.page_index,
                mode=item.mode,
                client_device=item.client_device,
                last_read_at=item.last_read_at,
                delta_seconds=item.delta_seconds,
            ),
            user_id=user_id,
        )
        if resp is None:
            skipped += 1
        elif applied:
            updated += 1
        else:
            skipped += 1

    all_rows = (
        db.query(ReadingProgress)
        .filter(ReadingProgress.user_id == user_id)
        .order_by(ReadingProgress.last_read_at.desc())
        .all()
    )
    return ReadingProgressSyncResponse(
        updated=updated,
        skipped_stale=skipped,
        progress_list=[ReadingProgressResponse.model_validate(r) for r in all_rows],
    )


def record_reading_session_impl(
    db: Session, data: ReadingSessionCreateRequest, user_id: int = 1
) -> Optional[ReadingSessionResponse]:
    work = db.query(Work).filter(Work.id == data.work_id).first()
    if not work:
        return None
    now = datetime.now()
    ended_at = (data.ended_at or now).replace(tzinfo=None)
    started_at = (
        data.started_at.replace(tzinfo=None)
        if data.started_at
        else ended_at - timedelta(seconds=data.duration_sec)
    )
    session = ReadingSession(
        user_id=user_id,
        work_id=data.work_id,
        edition_id=data.edition_id,
        start_node_id=data.start_node_id,
        end_node_id=data.end_node_id,
        duration_sec=data.duration_sec,
        chars_read=data.chars_read,
        source_client=data.source_client[:32],
        started_at=started_at,
        ended_at=ended_at,
    )
    db.add(session)

    prog = (
        db.query(ReadingProgress)
        .filter(
            ReadingProgress.user_id == user_id, ReadingProgress.work_id == data.work_id
        )
        .first()
    )
    if prog:
        prog.total_read_seconds = (prog.total_read_seconds or 0) + data.duration_sec
        prog.last_read_at = max(prog.last_read_at or ended_at, ended_at)

    db.commit()
    db.refresh(session)
    return ReadingSessionResponse.model_validate(session)


def get_reading_overview_impl(db: Session, user_id: int = 1) -> ReadingOverviewResponse:
    """阅读库与三大素养概览（供 Web 顶栏看板与 SailTick DataScanner 使用）。"""
    works = db.query(Work).order_by(Work.updated_at.desc()).all()
    enriched = _enrich_works_batch(db, works, user_id=user_id)

    now = datetime.now()
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)
    stalled_cutoff = now - timedelta(days=5)

    sessions_30d = (
        db.query(ReadingSession)
        .filter(
            ReadingSession.user_id == user_id,
            ReadingSession.started_at >= cutoff_30d,
        )
        .all()
    )
    work_pillar_map = {w.id: (w.pillar or "fiction") for w in enriched}

    sec_7d_by_pillar: Dict[str, int] = {}
    sec_30d_by_pillar: Dict[str, int] = {}
    for s in sessions_30d:
        p = work_pillar_map.get(s.work_id, "fiction")
        sec_30d_by_pillar[p] = sec_30d_by_pillar.get(p, 0) + int(s.duration_sec or 0)
        if s.started_at and s.started_at >= cutoff_7d:
            sec_7d_by_pillar[p] = sec_7d_by_pillar.get(p, 0) + int(s.duration_sec or 0)

    pillars_order = ["tech", "history", "aesthetics", "fiction", "general"]
    pillar_stats: List[PillarStatItem] = []
    for p in pillars_order:
        p_works = [w for w in enriched if (w.pillar or "fiction") == p]
        if not p_works and sec_30d_by_pillar.get(p, 0) == 0 and p == "general":
            continue
        pillar_stats.append(
            PillarStatItem(
                pillar=p,
                work_count=len(p_works),
                reading_count=sum(1 for w in p_works if w.reading_status == "reading"),
                finished_count=sum(1 for w in p_works if w.reading_status == "finished"),
                read_seconds_7d=sec_7d_by_pillar.get(p, 0),
                read_seconds_30d=sec_30d_by_pillar.get(p, 0),
            )
        )

    reading_works = [w for w in enriched if w.reading_status == "reading"]
    mainline_reading = [
        w
        for w in enriched
        if w.reading_track in ("mainline", "project")
        and w.reading_status in ("reading", "queued")
    ]
    mainline_reading.sort(key=lambda w: (w.reading_status != "reading", w.priority, -w.id))

    stalled_mainline = []
    for w in mainline_reading:
        if w.reading_status != "reading":
            continue
        last_ts = w.progress.last_read_at if w.progress else w.updated_at
        if last_ts and last_ts < stalled_cutoff:
            stalled_mainline.append(w)

    active_topics = (
        db.query(func.count(ContentTopic.id))
        .filter(ContentTopic.status == "active")
        .scalar()
        or 0
    )

    return ReadingOverviewResponse(
        total_works=len(enriched),
        reading_count=len(reading_works),
        mainline_reading=mainline_reading[:8],
        stalled_mainline=stalled_mainline[:5],
        pillar_stats=pillar_stats,
        total_read_seconds_7d=sum(sec_7d_by_pillar.values()),
        total_read_seconds_30d=sum(sec_30d_by_pillar.values()),
        active_topic_count=int(active_topics),
    )


# ============================================================================
# 3. Content Topics & Rhythm Venture Linkage
# ============================================================================


def _enrich_topics_batch(
    db: Session, topics: List[ContentTopic]
) -> List[ContentTopicResponse]:
    if not topics:
        return []
    tids = [t.id for t in topics]
    links = (
        db.query(ContentTopicWork)
        .filter(ContentTopicWork.topic_id.in_(tids))
        .all()
    )
    work_ids = list({lk.work_id for lk in links})
    prog_map: Dict[int, float] = {}
    if work_ids:
        for wid, pct in (
            db.query(ReadingProgress.work_id, ReadingProgress.progress_pct)
            .filter(ReadingProgress.work_id.in_(work_ids))
            .all()
        ):
            prog_map[wid] = float(pct or 0.0)

    by_topic: Dict[int, List[int]] = {}
    for lk in links:
        by_topic.setdefault(lk.topic_id, []).append(lk.work_id)

    venture_ids = [t.rhythm_venture_id for t in topics if t.rhythm_venture_id]
    venture_map: Dict[int, str] = {}
    if venture_ids:
        for vid, vtitle in (
            db.query(RhythmAffair.id, RhythmAffair.title)
            .filter(RhythmAffair.id.in_(venture_ids))
            .all()
        ):
            venture_map[vid] = vtitle

    result: List[ContentTopicResponse] = []
    for t in topics:
        wids = by_topic.get(t.id, [])
        avg_pct = (
            round(sum(prog_map.get(wid, 0.0) for wid in wids) / len(wids), 1)
            if wids
            else 0.0
        )
        result.append(
            ContentTopicResponse(
                id=t.id,
                slug=t.slug,
                title=t.title,
                description=t.description or "",
                pillar=t.pillar or "tech",
                status=t.status or "active",
                rhythm_venture_id=t.rhythm_venture_id,
                vault_prefix=t.vault_prefix or f"topic.{t.slug}",
                keywords=list(t.keywords) if isinstance(t.keywords, list) else [],
                meta_data=t.meta_data if isinstance(t.meta_data, dict) else {},
                created_at=t.created_at,
                updated_at=t.updated_at,
                work_count=len(wids),
                avg_progress_pct=avg_pct,
                venture_title=venture_map.get(t.rhythm_venture_id)
                if t.rhythm_venture_id
                else None,
            )
        )
    return result


def list_topics_impl(
    db: Session, pillar: Optional[str] = None, status: Optional[str] = None
) -> List[ContentTopicResponse]:
    q = db.query(ContentTopic)
    if pillar:
        q = q.filter(ContentTopic.pillar == pillar)
    if status:
        q = q.filter(ContentTopic.status == status)
    topics = q.order_by(ContentTopic.updated_at.desc()).all()
    return _enrich_topics_batch(db, topics)


def create_topic_impl(
    db: Session, data: ContentTopicCreateRequest
) -> ContentTopicResponse:
    slug = (data.slug or _make_slug(data.title)).strip().lower()
    if db.query(ContentTopic).filter(ContentTopic.slug == slug).first():
        slug = f"{slug}-{int(datetime.now().timestamp())}"

    topic = ContentTopic(
        slug=slug,
        title=data.title.strip(),
        description=data.description or "",
        pillar=data.pillar or "tech",
        status=data.status or "active",
        rhythm_venture_id=data.rhythm_venture_id,
        vault_prefix=(data.vault_prefix or f"topic.{slug}").strip(),
        keywords=list(data.keywords or []),
        meta_data=dict(data.meta_data or {}),
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _enrich_topics_batch(db, [topic])[0]


def update_topic_impl(
    db: Session, topic_id: int, data: ContentTopicUpdateRequest
) -> Optional[ContentTopicResponse]:
    topic = db.query(ContentTopic).filter(ContentTopic.id == topic_id).first()
    if not topic:
        return None
    for field_name in (
        "title",
        "description",
        "pillar",
        "status",
        "rhythm_venture_id",
        "vault_prefix",
        "keywords",
        "meta_data",
    ):
        val = getattr(data, field_name, None)
        if val is not None:
            setattr(topic, field_name, val)
    db.commit()
    db.refresh(topic)
    return _enrich_topics_batch(db, [topic])[0]


def delete_topic_impl(db: Session, topic_id: int) -> bool:
    topic = db.query(ContentTopic).filter(ContentTopic.id == topic_id).first()
    if not topic:
        return False
    db.delete(topic)
    db.commit()
    return True


def attach_work_to_topic_impl(
    db: Session, topic_id: int, data: ContentTopicWorkAttachRequest
) -> Optional[ContentTopicWorkItem]:
    topic = db.query(ContentTopic).filter(ContentTopic.id == topic_id).first()
    work = db.query(Work).filter(Work.id == data.work_id).first()
    if not topic or not work:
        return None

    existing = (
        db.query(ContentTopicWork)
        .filter(
            ContentTopicWork.topic_id == topic_id,
            ContentTopicWork.work_id == data.work_id,
        )
        .first()
    )
    if existing:
        existing.role = data.role
        existing.sort_index = data.sort_index
        existing.note = data.note
        link = existing
    else:
        link = ContentTopicWork(
            topic_id=topic_id,
            work_id=data.work_id,
            role=data.role,
            sort_index=data.sort_index,
            note=data.note,
        )
        db.add(link)
    db.commit()
    db.refresh(link)
    work_dto = _enrich_works_batch(db, [work])[0]
    return ContentTopicWorkItem(
        id=link.id,
        topic_id=link.topic_id,
        work_id=link.work_id,
        role=link.role or "core",
        sort_index=link.sort_index or 0,
        note=link.note or "",
        work=work_dto,
    )


def detach_work_from_topic_impl(db: Session, topic_id: int, work_id: int) -> bool:
    link = (
        db.query(ContentTopicWork)
        .filter(
            ContentTopicWork.topic_id == topic_id,
            ContentTopicWork.work_id == work_id,
        )
        .first()
    )
    if not link:
        return False
    db.delete(link)
    db.commit()
    return True


def _affair_to_task_summary(a: RhythmAffair) -> TopicRhythmTaskSummary:
    return TopicRhythmTaskSummary(
        id=a.id,
        title=a.title,
        kind=a.kind,
        state=a.state,
        est_minutes=int(a.est_minutes or 30),
        urgency_ddl=a.urgency_ddl,
        ref=a.ref if isinstance(a.ref, dict) else {},
    )


def get_topic_detail_impl(
    db: Session, topic_id: int
) -> Optional[ContentTopicDetailResponse]:
    topic = db.query(ContentTopic).filter(ContentTopic.id == topic_id).first()
    if not topic:
        return None
    topic_dto = _enrich_topics_batch(db, [topic])[0]

    links = (
        db.query(ContentTopicWork)
        .filter(ContentTopicWork.topic_id == topic_id)
        .order_by(ContentTopicWork.sort_index, ContentTopicWork.id)
        .all()
    )
    work_ids = [lk.work_id for lk in links]
    works_by_id: Dict[int, Any] = {}
    if work_ids:
        works = db.query(Work).filter(Work.id.in_(work_ids)).all()
        for w_dto in _enrich_works_batch(db, works):
            works_by_id[w_dto.id] = w_dto

    topic_works = [
        ContentTopicWorkItem(
            id=lk.id,
            topic_id=lk.topic_id,
            work_id=lk.work_id,
            role=lk.role or "core",
            sort_index=lk.sort_index or 0,
            note=lk.note or "",
            work=works_by_id[lk.work_id],
        )
        for lk in links
        if lk.work_id in works_by_id
    ]

    # 资产：直接挂在 topic 或挂在 topic 关联作品下的附件
    asset_q = db.query(ContentAsset)
    if work_ids:
        asset_q = asset_q.filter(
            (ContentAsset.topic_id == topic_id) | (ContentAsset.work_id.in_(work_ids))
        )
    else:
        asset_q = asset_q.filter(ContentAsset.topic_id == topic_id)
    assets = [_asset_to_response(a) for a in asset_q.order_by(ContentAsset.created_at.desc()).all()]

    # Vault 笔记索引：按 topic_id 或 vault_prefix 匹配
    note_q = db.query(VaultNoteIndex)
    prefix = (topic.vault_prefix or f"topic.{topic.slug}").strip()
    if prefix:
        note_q = note_q.filter(
            (VaultNoteIndex.topic_id == topic_id)
            | (VaultNoteIndex.fname == prefix)
            | (VaultNoteIndex.fname.like(f"{prefix}.%"))
        )
    else:
        note_q = note_q.filter(VaultNoteIndex.topic_id == topic_id)
    vault_notes = [
        VaultNoteIndexItem.model_validate(n)
        for n in note_q.order_by(VaultNoteIndex.updated_at.desc()).limit(50).all()
    ]

    # Rhythm Venture 与子任务联动
    venture_summary: Optional[TopicRhythmTaskSummary] = None
    rhythm_tasks: List[TopicRhythmTaskSummary] = []
    if topic.rhythm_venture_id:
        venture = (
            db.query(RhythmAffair)
            .filter(RhythmAffair.id == topic.rhythm_venture_id)
            .first()
        )
        if venture:
            venture_summary = _affair_to_task_summary(venture)
            children = (
                db.query(RhythmAffair)
                .filter(RhythmAffair.parent_id == venture.id)
                .order_by(RhythmAffair.id.desc())
                .limit(50)
                .all()
            )
            rhythm_tasks = [_affair_to_task_summary(c) for c in children]

    # 也检索 ref 中带 content_topic_id == topic_id 的独立任务（即便未绑 venture）
    seen_ids = {t.id for t in rhythm_tasks}
    all_recent_affairs = (
        db.query(RhythmAffair)
        .filter(RhythmAffair.kind.in_(["task_oneoff", "task_maintenance", "habit"]))
        .order_by(RhythmAffair.id.desc())
        .limit(200)
        .all()
    )
    for a in all_recent_affairs:
        if a.id in seen_ids:
            continue
        ref = a.ref if isinstance(a.ref, dict) else {}
        if ref.get("content_topic_id") == topic_id:
            rhythm_tasks.append(_affair_to_task_summary(a))
            seen_ids.add(a.id)

    return ContentTopicDetailResponse(
        topic=topic_dto,
        works=topic_works,
        assets=assets,
        vault_notes=vault_notes,
        venture=venture_summary,
        rhythm_tasks=rhythm_tasks,
    )


def push_topic_rhythm_task_impl(
    db: Session, topic_id: int, req: TopicPushRhythmTaskRequest
) -> Optional[TopicRhythmTaskSummary]:
    """从专题或阅读资料一键推送任务到 Rhythm（自动挂载到绑定 Venture 下，并写入反向引用）。"""
    topic = db.query(ContentTopic).filter(ContentTopic.id == topic_id).first()
    if not topic:
        return None

    parent_id = topic.rhythm_venture_id
    if parent_id is not None:
        exists_v = db.query(RhythmAffair.id).filter(RhythmAffair.id == parent_id).first()
        if not exists_v:
            parent_id = None

    domain = "career" if topic.pillar in ("tech", "interdisciplinary") else "life"
    ref_payload: Dict[str, Any] = {
        "source": "content_topic",
        "content_topic_id": topic.id,
        "content_topic_slug": topic.slug,
        "content_topic_title": topic.title,
    }
    if req.work_id is not None:
        ref_payload["work_id"] = req.work_id
    if req.edition_id is not None:
        ref_payload["edition_id"] = req.edition_id
    if req.node_id is not None:
        ref_payload["node_id"] = req.node_id

    affair = RhythmAffair(
        title=req.title.strip()[:200],
        description=req.description or "",
        domain=domain,
        kind="task_oneoff",
        state="PLANNED",
        importance=max(1, min(5, int(req.importance or 3))),
        est_minutes=max(5, int(req.est_minutes or 45)),
        urgency_ddl=req.urgency_ddl.replace(tzinfo=None) if req.urgency_ddl else None,
        parent_id=parent_id,
        ref=ref_payload,
    )
    db.add(affair)
    db.commit()
    db.refresh(affair)
    return _affair_to_task_summary(affair)


# ============================================================================
# 4. Content Assets (PDF Sources, EPUBs, Figures, Moodboards)
# ============================================================================


def _asset_to_response(a: ContentAsset) -> ContentAssetResponse:
    return ContentAssetResponse(
        id=a.id,
        work_id=a.work_id,
        topic_id=a.topic_id,
        asset_kind=a.asset_kind or "attachment",
        storage_key=a.storage_key,
        original_name=a.original_name,
        mime_type=a.mime_type or "application/octet-stream",
        size_bytes=int(a.size_bytes or 0),
        sha256=a.sha256 or "",
        meta_data=a.meta_data if isinstance(a.meta_data, dict) else {},
        created_at=a.created_at,
        file_url=f"/api/v1/text/asset/{a.id}/file",
    )


def save_content_asset_impl(
    db: Session,
    content_bytes: bytes,
    original_name: str,
    mime_type: str = "application/octet-stream",
    asset_kind: str = "attachment",
    work_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    meta_data: Optional[dict] = None,
) -> ContentAssetResponse:
    """将附件字节写入 content_assets 目录并登记元数据。"""
    assets_dir = get_content_assets_dir()
    month_dir = datetime.now().strftime("%Y-%m")
    target_dir = assets_dir / month_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    sha = hashlib.sha256(content_bytes).hexdigest()
    ext = Path(original_name or "").suffix.lower()
    if not ext or len(ext) > 12 or not re.match(r"^\.[a-z0-9]+$", ext):
        ext = ".bin"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{ts}_{sha[:10]}_{uuid.uuid4().hex[:6]}{ext}"
    storage_key = f"{month_dir}/{fname}"
    (target_dir / fname).write_bytes(content_bytes)

    asset = ContentAsset(
        work_id=work_id,
        topic_id=topic_id,
        asset_kind=asset_kind,
        storage_key=storage_key,
        original_name=(original_name or fname)[:255],
        mime_type=mime_type[:128],
        size_bytes=len(content_bytes),
        sha256=sha,
        meta_data=meta_data or {},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _asset_to_response(asset)


def list_content_assets_impl(
    db: Session,
    work_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    asset_kind: Optional[str] = None,
) -> List[ContentAssetResponse]:
    q = db.query(ContentAsset)
    if work_id is not None:
        q = q.filter(ContentAsset.work_id == work_id)
    if topic_id is not None:
        q = q.filter(ContentAsset.topic_id == topic_id)
    if asset_kind:
        q = q.filter(ContentAsset.asset_kind == asset_kind)
    rows = q.order_by(ContentAsset.created_at.desc()).limit(200).all()
    return [_asset_to_response(r) for r in rows]


def get_content_asset_impl(db: Session, asset_id: int) -> Optional[ContentAsset]:
    return db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()


def resolve_asset_file_path(storage_key: str) -> Path:
    base = get_content_assets_dir().resolve()
    target = (base / storage_key.lstrip("/")).resolve()
    target.relative_to(base)  # ValueError if path traversal
    return target


def delete_content_asset_impl(db: Session, asset_id: int) -> bool:
    asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
    if not asset:
        return False
    try:
        fp = resolve_asset_file_path(asset.storage_key)
        if fp.exists():
            fp.unlink()
    except Exception:
        logger.warning("Failed to unlink content asset file: %s", asset.storage_key)
    db.delete(asset)
    db.commit()
    return True


# ============================================================================
# 5. Vault Note Index Sync & Work Clips Export
# ============================================================================


def sync_vault_note_index_impl(
    db: Session, req: VaultNoteIndexSyncRequest
) -> VaultNoteIndexSyncResponse:
    """按 content_hash 幂等同步本地 D:\\vault 内容笔记元数据索引。"""
    now = datetime.now()
    created = 0
    updated = 0
    skipped = 0

    for item in req.items:
        fname = item.fname.strip()
        if not fname:
            continue
        existing = (
            db.query(VaultNoteIndex).filter(VaultNoteIndex.fname == fname).first()
        )
        if existing is not None:
            if item.content_hash and existing.content_hash == item.content_hash:
                skipped += 1
                continue
            existing.namespace = item.namespace
            existing.title = item.title[:255]
            existing.summary = item.summary[:1200]
            existing.tags = list(item.tags or [])[:30]
            existing.links = list(item.links or [])[:50]
            existing.work_id = item.work_id
            existing.topic_id = item.topic_id
            existing.pillar = item.pillar
            existing.era = item.era
            existing.year_start = item.year_start
            existing.year_end = item.year_end
            existing.content_hash = item.content_hash[:64]
            existing.source_vault = (item.source_vault or req.source_vault)[:64]
            existing.synced_at = now
            existing.updated_at = now
            updated += 1
        else:
            row = VaultNoteIndex(
                fname=fname[:200],
                namespace=item.namespace[:32],
                title=item.title[:255],
                summary=item.summary[:1200],
                tags=list(item.tags or [])[:30],
                links=list(item.links or [])[:50],
                work_id=item.work_id,
                topic_id=item.topic_id,
                pillar=item.pillar,
                era=item.era,
                year_start=item.year_start,
                year_end=item.year_end,
                content_hash=item.content_hash[:64],
                source_vault=(item.source_vault or req.source_vault)[:64],
                synced_at=now,
                updated_at=now,
            )
            db.add(row)
            created += 1

    db.commit()
    return VaultNoteIndexSyncResponse(
        created=created,
        updated=updated,
        skipped=skipped,
        total_processed=created + updated + skipped,
    )


def list_vault_note_index_impl(
    db: Session,
    namespace: Optional[str] = None,
    pillar: Optional[str] = None,
    work_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    keyword: Optional[str] = None,
    limit: int = 100,
) -> List[VaultNoteIndexItem]:
    q = db.query(VaultNoteIndex)
    if namespace:
        q = q.filter(VaultNoteIndex.namespace == namespace)
    if pillar:
        q = q.filter(VaultNoteIndex.pillar == pillar)
    if work_id is not None:
        q = q.filter(VaultNoteIndex.work_id == work_id)
    if topic_id is not None:
        q = q.filter(VaultNoteIndex.topic_id == topic_id)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        q = q.filter(
            VaultNoteIndex.title.ilike(kw)
            | VaultNoteIndex.summary.ilike(kw)
            | VaultNoteIndex.fname.ilike(kw)
        )
    rows = (
        q.order_by(VaultNoteIndex.updated_at.desc())
        .limit(max(1, min(300, int(limit))))
        .all()
    )
    return [VaultNoteIndexItem.model_validate(r) for r in rows]


def _read_note_file_safe(setting_file: str) -> str:
    try:
        rel = (setting_file or "").lstrip("/")
        base = SERVER_DATA_DIR.resolve()
        target = (base / rel).resolve()
        target.relative_to(base)
        if target.exists():
            return target.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


def export_work_clips_markdown_impl(
    db: Session, work_id: int
) -> Optional[WorkClipsExportResponse]:
    """将某作品的全部划线批注与阅读进度导出为 Dendron 规范 Markdown（托管围栏 + 独立 .clips 文件）。"""
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        return None

    vault_slug = (work.vault_slug or f"read.{work.slug}").strip()
    if not vault_slug.startswith("read."):
        vault_slug = f"read.{vault_slug}"

    notes = (
        db.query(NoteItem)
        .filter(NoteItem.work_id == work_id, NoteItem.category == "annotation")
        .order_by(NoteItem.created_at.asc())
        .all()
    )

    node_ids = [
        int(n.meta_data.get("node_id"))
        for n in notes
        if isinstance(n.meta_data, dict) and n.meta_data.get("node_id")
    ]
    node_map: Dict[int, DocumentNode] = {}
    if node_ids:
        for dn in db.query(DocumentNode).filter(DocumentNode.id.in_(node_ids)).all():
            node_map[dn.id] = dn

    # 按章节 sort_index → offset 排序
    def _sort_key(n: NoteItem):
        meta = n.meta_data if isinstance(n.meta_data, dict) else {}
        nid = meta.get("node_id")
        dn = node_map.get(int(nid)) if nid else None
        return (dn.sort_index if dn else 999999, int(meta.get("start_offset") or 0), n.id)

    notes_sorted = sorted(notes, key=_sort_key)

    prog = (
        db.query(ReadingProgress)
        .filter(ReadingProgress.work_id == work_id)
        .first()
    )
    topic_links = (
        db.query(ContentTopic)
        .join(ContentTopicWork, ContentTopicWork.topic_id == ContentTopic.id)
        .filter(ContentTopicWork.work_id == work_id)
        .all()
    )

    ts_ms = int(time.time() * 1000)
    clips_fname = f"{vault_slug}.clips.md"
    card_fname = f"{vault_slug}.md"

    # 1) 生成纯托管 clips 文件
    clips_lines: List[str] = [
        "---",
        f"id: sailzen-clips-{work.id}",
        f"title: '{work.title} — 划线与批注'",
        f"work_id: {work.id}",
        f"pillar: {work.pillar or 'fiction'}",
        f"updated: {ts_ms}",
        f"created: {ts_ms}",
        "tags:",
        "  - read",
        "  - clips",
        f"  - {work.pillar or 'fiction'}",
        "---",
        "",
        f"# {work.title} — 划线与批注",
        "",
        f"> 本文件由 SailZen 自动托管生成（共 {len(notes_sorted)} 条批注）。个人长篇思考请写在 [[{vault_slug}]]。",
        "",
    ]

    last_ch_header = None
    for n in notes_sorted:
        meta = n.meta_data if isinstance(n.meta_data, dict) else {}
        nid = meta.get("node_id")
        dn = node_map.get(int(nid)) if nid else None
        ch_header = (
            f"{dn.label or ''} {dn.title or ''}".strip() if dn else "未锚定章节"
        )
        if ch_header != last_ch_header:
            clips_lines.extend([f"## {ch_header}", ""])
            last_ch_header = ch_header

        selected = str(meta.get("selected_text") or n.title or "").strip()
        note_body = _read_note_file_safe(n.setting_file).strip()
        color = str(meta.get("color") or "yellow")
        if selected:
            clips_lines.append(f"> {selected}")
            clips_lines.append("")
        if note_body:
            clips_lines.append(f"- **批注** (`{color}` · `node:{nid or 0}`): {note_body}")
            clips_lines.append("")
        else:
            clips_lines.append(f"- *高亮标记* (`{color}` · `node:{nid or 0}`)")
            clips_lines.append("")

    # 2) 生成带受控围栏的总览读书卡
    pct_str = f"{prog.progress_pct:.1f}%" if prog else "0.0%"
    hours_str = f"{(prog.total_read_seconds or 0) / 3600:.1f}h" if prog else "0.0h"
    topic_links_str = (
        " · ".join(f"[[{t.vault_prefix or ('topic.' + t.slug)}]]" for t in topic_links)
        if topic_links
        else "暂无关联专题"
    )
    card_lines: List[str] = [
        "---",
        f"id: sailzen-read-{work.id}",
        f"title: '{work.title}'",
        f"work_id: {work.id}",
        f"work_type: {work.work_type or 'web_novel'}",
        f"pillar: {work.pillar or 'fiction'}",
        f"reading_status: {work.reading_status or 'queued'}",
        f"reading_track: {work.reading_track or 'leisure'}",
        f"updated: {ts_ms}",
        f"created: {ts_ms}",
        "tags:",
        "  - read",
        f"  - {work.work_type or 'web_novel'}",
        f"  - {work.pillar or 'fiction'}",
        "---",
        "",
        f"# {work.title}",
        "",
        "<!-- sailzen:managed:meta:start -->",
        f"> **作者**：{work.author or '未知'} · **素养**：`{work.pillar or 'fiction'}` · **轨道**：`{work.reading_track or 'leisure'}` · **状态**：`{work.reading_status or 'queued'}`",
        f"> **阅读进度**：{pct_str} · **累计阅读**：{hours_str} · **划线批注**：{len(notes_sorted)} 条 · **关联专题**：{topic_links_str}",
        f"> 完整划线见 [[{vault_slug}.clips]]"
        + (f" · 原文链接：{work.source_url}" if work.source_url else ""),
        "<!-- sailzen:managed:meta:end -->",
        "",
        "## 核心摘要与结构",
        "",
        (work.synopsis.strip() if work.synopsis else "- （待补充核心观点与章节结构）"),
        "",
        "## 个人思考与复现记录",
        "",
        "- （此处归个人自由写作，SailZen CLI 同步永不覆盖）",
        "",
    ]

    return WorkClipsExportResponse(
        work_id=work.id,
        work_title=work.title,
        vault_slug=vault_slug,
        clips_filename=clips_fname,
        card_filename=card_fname,
        annotation_count=len(notes_sorted),
        clips_markdown="\n".join(clips_lines),
        card_markdown="\n".join(card_lines),
    )
