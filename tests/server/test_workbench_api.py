# -*- coding: utf-8 -*-
# @file test_workbench_api.py
# @brief SailZen Workbench API 完整单元测试（Bootstrap / 项目语义绑定 / Context Pack / 章节同步）
# @author sailing-innocent
# @date 2026-11-27
# @version 1.0
# ---------------------------------

from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sail_server.application.dto.rhythm import (
    AffairCreateRequest,
    AffairDomain,
    AffairKind,
    VentureMilestoneRequest,
)
from sail_server.application.dto.text import EditionCreateRequest, WorkCreateRequest
from sail_server.application.dto.workbench import (
    ChapterSyncRequest,
    ProjectArchetype,
    WorkbenchProjectMeta,
    WorkbenchProjectMetaUpdateRequest,
)
from sail_server.model.rhythm import (
    RhythmBadRequestError,
    add_milestone_impl,
    create_affair_impl,
)
from sail_server.model.text import create_edition_impl, create_work_impl
from sail_server.model.workbench import (
    build_workbench_context_pack_impl,
    get_workbench_bootstrap_impl,
    sync_edition_chapter_impl,
    update_workbench_project_meta_impl,
)
from sailzen_orm.orm_base import ORMBase


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    ORMBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_workbench_meta_rejects_local_paths():
    with pytest.raises(ValidationError):
        WorkbenchProjectMeta(slug="demo", repo_hints=["F:/repos/myrepo/SailZen"])

    with pytest.raises(ValidationError):
        WorkbenchProjectMeta(slug="demo", repo_hints=["/home/user/repo"])

    with pytest.raises(ValidationError):
        WorkbenchProjectMeta(slug="demo", repo_hints=[r"repos\demo"])

    ok = WorkbenchProjectMeta(
        slug="Hat Factory",
        archetype=ProjectArchetype.GAME,
        vault_namespace="project.hat-factory",
        repo_hints=["hat-factory", "github.com/user/hat-factory"],
    )
    assert ok.slug == "hat-factory"
    assert ok.repo_hints == ["hat-factory", "github.com/user/hat-factory"]


def test_workbench_bootstrap_project_meta_and_context_pack(db):
    venture = create_affair_impl(
        db,
        AffairCreateRequest(
            title="Hat Factory Indie Game",
            description="Godot prototype for Hat Factory",
            domain=AffairDomain.CAREER,
            kind=AffairKind.VENTURE,
            kind_meta={"target_date": (date.today() + timedelta(days=30)).isoformat()},
        ),
    )
    add_milestone_impl(db, venture.id, VentureMilestoneRequest(title="完成核心玩法原型"))

    updated = update_workbench_project_meta_impl(
        db,
        venture.id,
        WorkbenchProjectMetaUpdateRequest(
            slug="hat-factory",
            archetype=ProjectArchetype.GAME,
            vault_namespace="project.hat-factory",
            repo_hints=["hat-factory"],
        ),
    )
    assert updated.workbench.slug == "hat-factory"
    assert updated.workbench.archetype == ProjectArchetype.GAME
    assert updated.workbench.vault_namespace == "project.hat-factory"

    boot = get_workbench_bootstrap_impl(db, date.today())
    assert len(boot.projects) == 1
    assert boot.projects[0].workbench.slug == "hat-factory"
    assert len(boot.projects[0].progress.milestones) == 1

    pack = build_workbench_context_pack_impl(db, venture.id)
    assert pack.slug == "hat-factory"
    assert pack.archetype == ProjectArchetype.GAME
    assert "完成核心玩法原型" in pack.markdown
    assert "project.hat-factory" in pack.markdown

    # 非 venture 事务禁止设置项目语义元数据
    task = create_affair_impl(db, AffairCreateRequest(title="普通任务"))
    with pytest.raises(RhythmBadRequestError):
        update_workbench_project_meta_impl(
            db,
            task.id,
            WorkbenchProjectMetaUpdateRequest(slug="not-a-venture"),
        )


def test_edition_chapter_sync_idempotent_upsert(db):
    work = create_work_impl(
        db,
        WorkCreateRequest(
            slug="novel-starlight",
            title="星海长歌",
            author="sailing-innocent",
            work_type="novel",
            pillar="fiction",
            is_original=True,
        ),
    )
    edition = create_edition_impl(
        db,
        EditionCreateRequest(
            work_id=work.id,
            edition_name="主稿",
            language="zh",
            source_format="markdown",
        ),
    )

    # 首次同步 → created
    r1 = sync_edition_chapter_impl(
        db,
        edition.id,
        ChapterSyncRequest(
            source_slug="ch001",
            label="第一章",
            title="启程",
            content="星光照亮了港口，Hello World。",
        ),
    )
    assert r1 is not None
    assert r1.action == "created"
    assert r1.node.title == "启程"
    assert r1.edition_word_count > 0

    # 二次同 source_slug 同步 → updated（幂等，不重复建章）
    r2 = sync_edition_chapter_impl(
        db,
        edition.id,
        ChapterSyncRequest(
            source_slug="ch001",
            label="第一章",
            title="启程（修订版）",
            content="星光照亮了整个港口，远方的引擎已经点火。",
        ),
    )
    assert r2 is not None
    assert r2.action == "updated"
    assert r2.node.id == r1.node.id
    assert r2.node.title == "启程（修订版）"
    assert r2.edition_char_count == len("星光照亮了整个港口，远方的引擎已经点火。")
