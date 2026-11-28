# -*- coding: utf-8 -*-
# @file test_domain_routing.py
# @brief 后端消息类型 × 业务域/交互角色分流单元测试（Ticket / Inbox / HealthSummary / DomainSummary / Workbench）
# @author sailing-innocent
# @date 2026-11-28
# @version 1.0
# ---------------------------------

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sail_server.application.dto.tick import (
    DailyReportUpsertRequest,
    QuickChatRequest,
    TicketCreateRequest,
)
from sail_server.model.inbox import list_inbox_impl, resolve_domain_routing
from sail_server.model.tick import (
    create_ticket_impl,
    get_domain_summary_impl,
    get_health_coach_summary_impl,
    list_tickets_impl,
    upsert_daily_report_impl,
)
from sailzen_orm import ORMBase
import sailzen_orm.health  # noqa: F401
import sailzen_orm.inbox  # noqa: F401
import sailzen_orm.reminder  # noqa: F401
import sailzen_orm.rhythm  # noqa: F401
import sailzen_orm.tick  # noqa: F401
import sailzen_orm.user  # noqa: F401


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    ORMBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_resolve_domain_routing_matrix():
    r_health = resolve_domain_routing(topic="diet_lunch", title="午饭吃什么？", ticket_id=10)
    assert r_health["target_domain"] == "health"
    assert r_health["persona"] == "health_coach"
    assert r_health["deep_link"] == "/health/coach?ticket=10"
    assert "vscode" not in r_health["target_clients"]

    r_rhythm = resolve_domain_routing(topic="rhythm_key_projects", title="项目目标日是否顺延？", ticket_id=11)
    assert r_rhythm["target_domain"] == "rhythm"
    assert r_rhythm["persona"] == "rhythm_planner"
    assert r_rhythm["deep_link"] == "/rhythm?ticket=11"
    assert "vscode" in r_rhythm["target_clients"]

    r_fin = resolve_domain_routing(domain="finance", title="微信余额差额核对", ticket_id=12)
    assert r_fin["target_domain"] == "finance"
    assert r_fin["persona"] == "finance_secretary"
    assert r_fin["deep_link"] == "/money?ticket=12"


def test_tickets_inbox_and_health_summary_isolation(db_session):
    t_health = create_ticket_impl(
        db_session,
        TicketCreateRequest(
            type="question",
            topic="diet_lunch",
            title="今天午饭吃了什么？",
            body="顺手记录一下",
            push="none",
        ),
    )
    t_rhythm = create_ticket_impl(
        db_session,
        TicketCreateRequest(
            type="question",
            domain="rhythm",
            topic="rhythm_key_projects",
            title="主线项目是否要拆小里程碑？",
            body="原定目标日临近",
            push="none",
        ),
    )
    t_finance = create_ticket_impl(
        db_session,
        TicketCreateRequest(
            type="question",
            domain="finance",
            topic="finance_reconcile",
            title="支付宝余额差额 ¥180 核对",
            body="是否漏记大额支出",
            push="none",
        ),
    )

    assert t_health.domain == "health" and t_health.persona == "health_coach"
    assert t_rhythm.domain == "rhythm" and t_rhythm.persona == "rhythm_planner"
    assert t_finance.domain == "finance" and t_finance.persona == "finance_secretary"

    # 健康页聚合视图严格只返回 health 域票据，杜绝日程/财务串味
    health_sum = get_health_coach_summary_impl(db_session)
    assert health_sum.pending_ticket_count == 1
    assert [t.id for t in health_sum.pending_tickets] == [t_health.id]

    # 写入分节综合日报，验证 domain-summary 精准抽取各域对应分节
    upsert_daily_report_impl(
        db_session,
        DailyReportUpsertRequest(
            report_date="2026-11-28",
            title="2026-11-28 今日生活总览",
            summary="三域综合摘要",
            body_markdown="完整正文",
            sections={
                "health": {"summary": "体重稳定 73.5kg", "highlights": ["午餐食堂鸡胸"]},
                "rhythm": {"summary": "完成 3/4 专注块", "highlights": ["SailTick Round2 启动"]},
                "finance": {"summary": "今日支出 ¥42", "highlights": ["零食 ¥0"]},
                "chief": {"summary": "整体稳健", "highlights": ["早睡"]},
            },
            push=False,
        ),
    )

    rhythm_sum = get_domain_summary_impl(db_session, domain="rhythm")
    assert rhythm_sum.persona == "rhythm_planner"
    assert [t.id for t in rhythm_sum.pending_tickets] == [t_rhythm.id]
    assert rhythm_sum.report_section["summary"] == "完成 3/4 专注块"

    finance_sum = get_domain_summary_impl(db_session, domain="finance")
    assert finance_sum.persona == "finance_secretary"
    assert [t.id for t in finance_sum.pending_tickets] == [t_finance.id]
    assert finance_sum.report_section["summary"] == "今日支出 ¥42"

    # 收件箱按 target_domain 分流过滤 + 精确 deep_link
    inbox_rhythm = list_inbox_impl(db_session, user_id=1, tab="active", source_domain="rhythm")
    assert len(inbox_rhythm) == 1
    assert inbox_rhythm[0].target_domain == "rhythm"
    assert inbox_rhythm[0].persona == "rhythm_planner"
    assert inbox_rhythm[0].action_schema["deep_link"] == f"/rhythm?ticket={t_rhythm.id}"

    # list_tickets 支持 domain 过滤
    assert len(list_tickets_impl(db_session, status="pending", domain="finance")) == 1


def test_quick_chat_request_accepts_message_alias():
    req1 = QuickChatRequest(text="下午加会", domain="rhythm", surface="vscode_workbench")
    req2 = QuickChatRequest.model_validate({"message": "下午加会", "channel": "vscode_workbench"})
    assert req1.text == "下午加会"
    assert req2.text == "下午加会"
