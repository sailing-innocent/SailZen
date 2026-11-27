# -*- coding: utf-8 -*-
# @file test_content_v2.py
# @brief Content 2.0 (Phase 1) Backend Regression Tests: Volumes, Cloud Progress,
#        Topics<->Rhythm Linkage, EPUB/PDF/arXiv Importers, Vault Index & Clips Export
# @author sailing-innocent
# @date 2026-11-26
# @version 1.0
# ---------------------------------

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta

import fitz  # PyMuPDF
import pytest

import sail_server.model.content_library as content_lib
import sail_server.model.text as text_model
from sail_server.application.dto.text import (
    AutoVolumeRequest,
    ContentTopicCreateRequest,
    ContentTopicWorkAttachRequest,
    NoteItemCreateRequest,
    ReadingProgressSyncItem,
    ReadingProgressSyncRequest,
    ReadingProgressUpsertRequest,
    ReadingSessionCreateRequest,
    TopicPushRhythmTaskRequest,
    VaultNoteIndexItem,
    VaultNoteIndexSyncRequest,
    VolumeAssignRequest,
    VolumeCreateRequest,
)
from sail_server.model.content_ingest import (
    extract_arxiv_id,
    import_epub_impl,
    import_pdf_impl,
    parse_arxiv_html_sections,
)
from sailzen_orm.rhythm import RhythmAffair

pytestmark = pytest.mark.server


@pytest.fixture()
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("SERVER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CONTENT_ASSETS_PATH", str(tmp_path / "content_assets"))
    monkeypatch.setattr(text_model, "SERVER_DATA_DIR", tmp_path)
    monkeypatch.setattr(content_lib, "SERVER_DATA_DIR", tmp_path)
    return tmp_path


def _build_sample_epub() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
            <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
              <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
            </container>""",
        )
        zf.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0" encoding="utf-8"?>
            <package xmlns="http://www.idpf.org/2007/opf" version="2.0">
              <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                <dc:title>明代财政史略</dc:title>
                <dc:creator>测试史家</dc:creator>
                <dc:language>zh</dc:language>
                <dc:description>梳理明代田赋与白银货币化的关键脉络。</dc:description>
              </metadata>
              <manifest>
                <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
                <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
                <item id="ch2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
                <item id="ch3" href="ch3.xhtml" media-type="application/xhtml+xml"/>
              </manifest>
              <spine toc="ncx">
                <itemref idref="ch1"/>
                <itemref idref="ch2"/>
                <itemref idref="ch3"/>
              </spine>
            </package>""",
        )
        zf.writestr(
            "OEBPS/toc.ncx",
            """<?xml version="1.0" encoding="utf-8"?>
            <ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
              <navMap>
                <navPoint id="v1" playOrder="1">
                  <navLabel><text>上编 洪武体制</text></navLabel>
                  <content src="ch1.xhtml"/>
                  <navPoint id="c1" playOrder="2">
                    <navLabel><text>第一章 黄册与鱼鳞图册</text></navLabel>
                    <content src="ch1.xhtml"/>
                  </navPoint>
                  <navPoint id="c2" playOrder="3">
                    <navLabel><text>第二章 卫所屯田</text></navLabel>
                    <content src="ch2.xhtml"/>
                  </navPoint>
                </navPoint>
                <navPoint id="v2" playOrder="4">
                  <navLabel><text>下编 一条鞭法</text></navLabel>
                  <content src="ch3.xhtml"/>
                  <navPoint id="c3" playOrder="5">
                    <navLabel><text>第三章 白银帝国的转向</text></navLabel>
                    <content src="ch3.xhtml"/>
                  </navPoint>
                </navPoint>
              </navMap>
            </ncx>""",
        )
        zf.writestr("OEBPS/ch1.xhtml", "<html><body><h1>第一章</h1><p>洪武年间编制黄册与鱼鳞图册，奠定明初实物财政基础，影响长达百年。</p></body></html>")
        zf.writestr("OEBPS/ch2.xhtml", "<html><body><h1>第二章</h1><p>卫所屯田制度试图以军屯自给，但在明中期逐渐瓦解，转为募兵与银饷。</p></body></html>")
        zf.writestr("OEBPS/ch3.xhtml", "<html><body><h1>第三章</h1><p>张居正推行一条鞭法，将赋役折银合并征收，深刻改变了乡村经济结构。</p></body></html>")
    return buf.getvalue()


def _build_sample_pdf() -> bytes:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text(
        (72, 72),
        "ReSTIR GI: Path Resampling for Real-Time Path Tracing\n\n"
        "Abstract\nWe present spatiotemporal reservoir resampling for real-time global illumination in complex dynamic scenes.\n\n"
        "1 Introduction\nReal-time global illumination remains challenging under tight frame budgets.",
    )
    p2 = doc.new_page()
    p2.insert_text(
        (72, 72),
        "2 Method\nWe combine temporal reuse with spatial neighbor reservoirs and visibility validation.",
    )
    p3 = doc.new_page()
    p3.insert_text(
        (72, 72),
        "3 Evaluation\nOur shader achieves 2.4ms on 1080p with significantly lower variance than naive path tracing.",
    )
    doc.set_toc(
        [
            [1, "Abstract & Introduction", 1],
            [1, "Method", 2],
            [1, "Evaluation", 3],
        ]
    )
    data = doc.tobytes()
    doc.close()
    return data


class TestVolumesAndToc:
    def test_batch_insert_with_volumes_and_toc(self, db):
        work, ed = text_model.create_work_with_edition_impl(
            db,
            title="诡秘测试卷",
            author="爱潜水的乌贼",
            pillar="fiction",
            reading_track="leisure",
        )
        items = [
            text_model.ChapterBatchItem(
                label="第一章",
                title="绯红",
                content="痛，好痛。" * 30,
                volume_label="第一卷",
                volume_title="小丑",
            ),
            text_model.ChapterBatchItem(
                label="第二章",
                title="情况",
                content="镜子里的青年。" * 30,
                volume_label="第一卷",
                volume_title="小丑",
            ),
            text_model.ChapterBatchItem(
                label="第三章",
                title="无面人开篇",
                content="贝克兰德的雾。" * 30,
                volume_label="第二卷",
                volume_title="无面人",
            ),
        ]
        cnt = text_model.batch_insert_chapters_impl(db, ed.id, items, start_index=0)
        assert cnt == 3

        toc = content_lib.get_edition_toc_impl(db, ed.id)
        assert toc is not None
        assert toc.total_chapters == 3
        assert toc.volume_count == 2
        assert len(toc.ungrouped_chapters) == 0
        assert toc.volumes[0].title == "小丑"
        assert toc.volumes[0].chapter_count == 2
        assert toc.volumes[1].title == "无面人"
        assert toc.volumes[1].chapter_count == 1

        # 扁平兼容接口仍返回完整章节列表并带 volume_title
        flat = text_model.get_chapter_list_impl(db, ed.id)
        assert len(flat) == 3
        assert flat[0].volume_title == "第一卷 小丑"

    def test_auto_volume_dry_run_and_apply_and_delete(self, db):
        _, ed = text_model.create_work_with_edition_impl(db, title="扁平旧小说")
        items = [
            text_model.ChapterBatchItem(label="第一卷 第一章", title="起风", content="正文" * 50),
            text_model.ChapterBatchItem(label="第一卷 第二章", title="落叶", content="正文" * 50),
            text_model.ChapterBatchItem(label="第二卷 第一章", title="远行", content="正文" * 50),
        ]
        text_model.batch_insert_chapters_impl(db, ed.id, items, start_index=0)

        preview = content_lib.auto_volume_edition_impl(db, ed.id, AutoVolumeRequest(dry_run=True))
        assert preview is not None
        assert preview.strategy == "volume_prefix"
        assert len(preview.volumes) == 2
        assert preview.applied_volumes == 0

        applied = content_lib.auto_volume_edition_impl(db, ed.id, AutoVolumeRequest(dry_run=False))
        assert applied is not None
        assert applied.applied_volumes == 2
        assert applied.assigned_chapters == 3

        toc = content_lib.get_edition_toc_impl(db, ed.id)
        assert toc.volume_count == 2
        first_vol_id = toc.volumes[0].id

        # 删除分卷必须保留章节正文，仅解绑
        assert content_lib.delete_volume_impl(db, ed.id, first_vol_id) is True
        toc_after = content_lib.get_edition_toc_impl(db, ed.id)
        assert toc_after.total_chapters == 3
        assert toc_after.volume_count == 1
        assert len(toc_after.ungrouped_chapters) == 2

        # 手动建卷并重新归组
        new_vol = content_lib.create_volume_impl(
            db, ed.id, VolumeCreateRequest(label="卷一", title="重构卷", start_sort_index=0, end_sort_index=0)
        )
        assert new_vol is not None and new_vol.chapter_count == 1
        assigned = content_lib.assign_chapters_to_volume_impl(
            db, ed.id, new_vol.id, VolumeAssignRequest(start_sort_index=1, end_sort_index=1)
        )
        assert assigned == 1


class TestCloudProgressAndStats:
    def test_progress_lww_sync_sessions_and_overview(self, db):
        w, ed = text_model.create_work_with_edition_impl(
            db,
            title="Real-Time Rendering 4th",
            pillar="tech",
            work_type="book",
            reading_track="mainline",
        )
        items = [
            text_model.ChapterBatchItem(label=f"Ch {i+1}", title=f"Topic {i+1}", content="text " * 40)
            for i in range(4)
        ]
        text_model.batch_insert_chapters_impl(db, ed.id, items, start_index=0)

        t1 = datetime(2026, 11, 25, 20, 0, 0)
        t2 = datetime(2026, 11, 25, 21, 0, 0)
        t_old = datetime(2026, 11, 25, 19, 0, 0)

        p1, applied1 = content_lib.upsert_reading_progress_impl(
            db,
            w.id,
            ReadingProgressUpsertRequest(
                edition_id=ed.id, sort_index=1, char_offset=120, client_device="android", last_read_at=t1, delta_seconds=600
            ),
        )
        assert applied1 is True
        assert p1.progress_pct == 50.0
        # 自动从 queued 转入 reading
        assert text_model.get_work_impl(db, w.id).reading_status == "reading"

        # 过期时间戳不得倒退进度
        p_stale, applied_stale = content_lib.upsert_reading_progress_impl(
            db,
            w.id,
            ReadingProgressUpsertRequest(
                edition_id=ed.id, sort_index=0, client_device="web", last_read_at=t_old
            ),
        )
        assert applied_stale is False
        assert p_stale.sort_index == 1

        # 批量同步推进到第 3 章
        sync_res = content_lib.sync_reading_progress_batch_impl(
            db,
            ReadingProgressSyncRequest(
                items=[
                    ReadingProgressSyncItem(
                        work_id=w.id, edition_id=ed.id, sort_index=2, client_device="web", last_read_at=t2, delta_seconds=300
                    )
                ]
            ),
        )
        assert sync_res.updated == 1
        assert sync_res.progress_list[0].progress_pct == 75.0
        assert sync_res.progress_list[0].total_read_seconds == 900

        # 记录阅读会话并检查概览统计
        sess = content_lib.record_reading_session_impl(
            db,
            ReadingSessionCreateRequest(
                work_id=w.id, edition_id=ed.id, duration_sec=1200, chars_read=3500, source_client="android"
            ),
        )
        assert sess is not None
        overview = content_lib.get_reading_overview_impl(db)
        assert overview.total_works >= 1
        assert overview.reading_count >= 1
        assert overview.total_read_seconds_7d >= 1200
        tech_stat = next(s for s in overview.pillar_stats if s.pillar == "tech")
        assert tech_stat.read_seconds_7d >= 1200


class TestTopicAndRhythmLinkage:
    def test_topic_venture_and_push_rhythm_task(self, db):
        venture = RhythmAffair(
            title="SIGGRAPH 2026 实时渲染复现",
            kind="venture",
            domain="career",
            state="ACTIVE",
        )
        db.add(venture)
        db.commit()
        db.refresh(venture)

        topic = content_lib.create_topic_impl(
            db,
            ContentTopicCreateRequest(
                title="ReSTIR 光追复现专题",
                pillar="tech",
                rhythm_venture_id=venture.id,
                keywords=["ReSTIR", "SIGGRAPH", "Path Tracing"],
            ),
        )
        assert topic.venture_title == "SIGGRAPH 2026 实时渲染复现"

        work, ed = text_model.create_work_with_edition_impl(
            db, title="ReSTIR GI Paper", work_type="paper", pillar="tech", reading_track="project"
        )
        link = content_lib.attach_work_to_topic_impl(
            db, topic.id, ContentTopicWorkAttachRequest(work_id=work.id, role="core", note="核心算法论文")
        )
        assert link is not None and link.work.id == work.id

        pushed = content_lib.push_topic_rhythm_task_impl(
            db,
            topic.id,
            TopicPushRhythmTaskRequest(
                title="复现 ReSTIR GI Temporal Reuse Shader",
                work_id=work.id,
                edition_id=ed.id,
                est_minutes=90,
            ),
        )
        assert pushed is not None
        assert pushed.ref["content_topic_id"] == topic.id
        assert pushed.ref["work_id"] == work.id

        detail = content_lib.get_topic_detail_impl(db, topic.id)
        assert detail is not None
        assert detail.venture is not None and detail.venture.id == venture.id
        assert len(detail.works) == 1
        assert any(t.id == pushed.id for t in detail.rhythm_tasks)


class TestMultiFormatIngestAndVaultBridge:
    def test_epub_import_preserves_volumes_and_asset(self, db, isolated_storage):
        res = import_epub_impl(
            db,
            epub_bytes=_build_sample_epub(),
            filename="ming_finance.epub",
            pillar="history",
            reading_track="mainline",
        )
        assert res.work.title == "明代财政史略"
        assert res.work.pillar == "history"
        assert res.volume_count == 2
        assert res.chapter_count == 3
        assert res.asset is not None
        assert res.asset.asset_kind == "epub_source"
        assert content_lib.resolve_asset_file_path(res.asset.storage_key).exists()

    def test_pdf_import_extracts_sections_and_keeps_raw_pdf(self, db, isolated_storage):
        res = import_pdf_impl(
            db,
            pdf_bytes=_build_sample_pdf(),
            filename="restir_gi.pdf",
            pillar="tech",
            reading_track="project",
        )
        assert res.work.work_type == "paper"
        assert res.chapter_count == 3
        assert res.parser_used == "pymupdf_toc"
        assert res.asset is not None
        assert res.asset.asset_kind == "pdf_source"
        assert content_lib.resolve_asset_file_path(res.asset.storage_key).exists()

    def test_arxiv_parsers(self):
        assert extract_arxiv_id("https://arxiv.org/abs/2405.12345v2") == "2405.12345v2"
        assert extract_arxiv_id("2308.04079") == "2308.04079"
        sample_html = """
        <section class="ltx_section"><h2>1 Introduction</h2><p>Gaussian Splatting enables real-time radiance field rendering with explicit primitives.</p></section>
        <section class="ltx_section"><h2>2 Method</h2><p>We optimize anisotropic 3D Gaussians using differentiable tile-based rasterization.</p></section>
        """
        secs = parse_arxiv_html_sections(sample_html)
        assert len(secs) == 2
        assert "Introduction" in secs[0].title
        assert "Gaussians" in secs[1].content

    def test_vault_index_sync_and_clips_export(self, db, isolated_storage):
        w, ed = text_model.create_work_with_edition_impl(
            db, title="渲染架构笔记书", pillar="tech", work_type="book"
        )
        text_model.batch_insert_chapters_impl(
            db,
            ed.id,
            [text_model.ChapterBatchItem(label="第一章", title="管线概览", content="现代渲染管线依赖 GPU 驱动绘制。")],
        )
        ch = text_model.get_chapter_list_impl(db, ed.id)[0]
        text_model.create_note_item_impl(
            db,
            NoteItemCreateRequest(
                category="annotation",
                work_id=w.id,
                edition_id=ed.id,
                title="GPU 驱动绘制",
                content="非常适合独立游戏大场景批处理",
                node_id=ch.id,
                start_offset=0,
                end_offset=10,
                selected_text="现代渲染管线依赖 GPU 驱动绘制",
                color="yellow",
            ),
        )

        export = content_lib.export_work_clips_markdown_impl(db, w.id)
        assert export is not None
        assert export.annotation_count == 1
        assert "GPU 驱动绘制" in export.clips_markdown
        assert "sailzen:managed:meta:start" in export.card_markdown

        sync1 = content_lib.sync_vault_note_index_impl(
            db,
            VaultNoteIndexSyncRequest(
                items=[
                    VaultNoteIndexItem(
                        fname="study.history.ming-silver",
                        namespace="study",
                        title="明代白银货币化",
                        summary="从宝钞崩溃到一条鞭法",
                        pillar="history",
                        era="明代",
                        year_start=1436,
                        year_end=1581,
                        tags=["history", "economy"],
                        content_hash="abc123",
                    )
                ]
            ),
        )
        assert sync1.created == 1
        sync2 = content_lib.sync_vault_note_index_impl(
            db,
            VaultNoteIndexSyncRequest(
                items=[
                    VaultNoteIndexItem(
                        fname="study.history.ming-silver",
                        namespace="study",
                        title="明代白银货币化",
                        content_hash="abc123",
                    )
                ]
            ),
        )
        assert sync2.skipped == 1
        notes = content_lib.list_vault_note_index_impl(db, pillar="history")
        assert len(notes) == 1 and notes[0].year_start == 1436

    def test_cli_vault_content_scanner_and_managed_fence_merge(self, tmp_path):
        import sys
        from pathlib import Path

        cli_root = Path(__file__).resolve().parents[2] / "packages" / "py" / "sailzen-cli"
        if str(cli_root) not in sys.path:
            sys.path.insert(0, str(cli_root))
        from sailzen_cli.commands.vault_client import (
            merge_managed_card_markdown,
            scan_local_vault_content_notes,
        )

        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "study.history.ming-tax.md").write_text(
            "---\ntitle: '明代一条鞭法'\nera: '明代'\nyear_start: 1581\ntags:\n  - history\n---\n\n参见 [[topic.indie-game-ming]] 经济系统参考。",
            encoding="utf-8",
        )
        (notes_dir / "read.demo.clips.md").write_text("# clips should be skipped", encoding="utf-8")

        scanned = scan_local_vault_content_notes(tmp_path)
        assert len(scanned) == 1
        assert scanned[0]["fname"] == "study.history.ming-tax"
        assert scanned[0]["pillar"] == "history"
        assert scanned[0]["year_start"] == 1581
        assert "topic.indie-game-ming" in scanned[0]["links"]

        existing_card = (
            "# Demo\n\n"
            "<!-- sailzen:managed:meta:start -->\n> old 10%\n<!-- sailzen:managed:meta:end -->\n\n"
            "## 个人思考\n\n这是我亲手写的重要笔记，不能被覆盖。\n"
        )
        fresh_card = (
            "# Demo\n\n"
            "<!-- sailzen:managed:meta:start -->\n> new 85%\n<!-- sailzen:managed:meta:end -->\n\n"
            "## 个人思考\n\n默认占位\n"
        )
        merged = merge_managed_card_markdown(existing_card, fresh_card)
        assert "> new 85%" in merged
        assert "这是我亲手写的重要笔记，不能被覆盖。" in merged

    def test_sailtick_datascan_simplify_reading(self):
        from sailtick.datascan import DataScanner

        simplified = DataScanner._simplify_reading(
            {
                "total_works": 12,
                "reading_count": 3,
                "active_topic_count": 2,
                "total_read_seconds_7d": 3600,
                "pillar_stats": [{"pillar": "tech", "work_count": 4, "reading_count": 2, "read_seconds_7d": 2400}],
                "mainline_reading": [{"id": 1, "title": "ReSTIR GI", "pillar": "tech", "progress": {"progress_pct": 50.0}}],
                "stalled_mainline": [{"title": "旧书"}],
            }
        )
        assert simplified is not None
        assert simplified["min_7d"] == 60.0
        assert simplified["pillars"]["tech"]["min_7d"] == 40.0
        assert simplified["stalled_mainline"] == ["旧书"]
