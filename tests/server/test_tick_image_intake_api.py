# -*- coding: utf-8 -*-
# @file test_tick_image_intake_api.py
# @brief SailTick 通用视觉识图与二段式确认落库 API 集成测试
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""SailTick 图片识图与确认落库测试（内存 SQLite + Mock DeepSeek Vision/OCR）。"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from litestar import Litestar, Router
from litestar.di import Provide
from litestar.plugins.pydantic import PydanticPlugin
from litestar.testing import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from sail.llm.deepseek_vision import OcrPage, OcrResult, VisionResult
from sail_server.controller.tick import TicketController
from sailzen_orm.health import BodyData, DietLog, Exercise, Mood, Sleep, Weight
from sailzen_orm.tick import SailTickMessage, SailTickTicket

pytestmark = pytest.mark.server

BASE = "/api/v1/tick"


def _make_jpeg_bytes(width: int = 320, height: int = 240, color=(200, 120, 80)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


@pytest.fixture(scope="function")
def client(db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TICK_MEDIA_PATH", str(tmp_path / "tick_media"))
    monkeypatch.delenv("SAILZEN_API_TOKEN", raising=False)

    async def _test_db_dep():
        def _gen():
            yield db

        return _gen()

    router = Router(
        path=BASE,
        dependencies={"router_dependency": Provide(_test_db_dep)},
        route_handlers=[TicketController],
    )
    app = Litestar(route_handlers=[router], plugins=[PydanticPlugin(prefer_alias=True)])
    with TestClient(app=app) as test_client:
        yield test_client


class TestTickImageIntakeFlow:
    def test_analyze_and_commit_multi_entries_with_ticket_reply(
        self,
        client: TestClient,
        db: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # 1. 创建一张待回票据，验证“传图回复票据”闭环
        t_resp = client.post(
            f"{BASE}/tickets",
            json={
                "tick_id": "t_img_1",
                "type": "question",
                "title": "昨晚睡得怎么样，午饭打算吃什么？",
                "body": "直接传手表截图或餐盘照片即可",
                "priority": "normal",
                "channel": "mobile",
            },
        )
        assert t_resp.status_code == 201, t_resp.text
        ticket_id = t_resp.json()["id"]

        # Mock DeepSeek Vision 返回单图多条目（睡眠 + 饮食 + 体重 + 运动 + 自拍气色）
        async def _fake_vision(**kwargs):
            return VisionResult(
                content="{}",
                parsed_json={
                    "scene": "diet",
                    "summary": "识别到健康总览与午餐餐盘：睡眠7.5h、午餐鸡胸肉糙米饭约560kcal、慢跑35分钟、体重74.2kg",
                    "coach_advice": "蛋白与睡眠都很稳，晚餐清淡一点即可。",
                    "entries": [
                        {
                            "selected": True,
                            "kind": "diet",
                            "title": "午餐：鸡胸肉糙米饭",
                            "confidence": 0.94,
                            "data": {
                                "meal_type": "lunch",
                                "description": "香煎鸡胸肉+半碗糙米饭+西兰花",
                                "calories": 560,
                                "protein": 38,
                                "carbs": 58,
                                "fat": 14,
                                "sugar": 4,
                            },
                        },
                        {
                            "selected": True,
                            "kind": "sleep",
                            "title": "昨晚睡眠 7.5 小时",
                            "confidence": 0.91,
                            "data": {
                                "hours": 7.5,
                                "quality": 4,
                                "description": "23:30-07:00，深睡1.9h",
                            },
                        },
                        {
                            "selected": True,
                            "kind": "exercise",
                            "title": "户外慢跑 35 分钟",
                            "confidence": 0.90,
                            "data": {
                                "exercise_type": "running",
                                "duration_minutes": 35,
                                "calories": 320,
                                "description": "5.1km 平均心率 146",
                            },
                        },
                        {
                            "selected": True,
                            "kind": "weight",
                            "title": "体重 74.2 kg",
                            "confidence": 0.96,
                            "data": {
                                "value": 74.2,
                                "description": "晨起称重",
                            },
                        },
                        {
                            "selected": True,
                            "kind": "mood",
                            "title": "气色较好",
                            "confidence": 0.85,
                            "data": {
                                "score": 4,
                                "description": "精神饱满，略带轻度眼周疲劳",
                            },
                        },
                    ],
                },
                model="deepseek-flash",
                usage={"prompt_tokens": 520, "completion_tokens": 210, "total_tokens": 730},
                latency_ms=820.5,
            )

        monkeypatch.setattr("sail_server.model.tick_intake.deepseek_vision_chat", _fake_vision)

        # 2. 上传图片分析
        img_bytes = _make_jpeg_bytes()
        analyze_resp = client.post(
            f"{BASE}/intake/analyze",
            data={
                "note": "刚拍的餐盘和手表汇总",
                "source_channel": "android",
                "ticket_id": str(ticket_id),
                "use_ocr_assist": "false",
            },
            files={"file": ("meal.jpg", img_bytes, "image/jpeg")},
        )
        assert analyze_resp.status_code == 201, analyze_resp.text
        draft = analyze_resp.json()
        assert draft["status"] == "pending_confirm"
        assert draft["ticket_id"] == ticket_id
        assert draft["model_used"] == "deepseek-flash"
        assert len(draft["entries"]) == 5
        assert draft["media_url"].startswith("/api/v1/tick/media/")

        # 3. 媒体文件可安全访问，且拦截目录穿越
        media_resp = client.get(draft["media_url"])
        assert media_resp.status_code == 200
        assert len(media_resp.content) > 100

        bad_media = client.get(f"{BASE}/media/2026-11/..evil.jpg")
        assert bad_media.status_code in (400, 404)

        # 4. 健康聚合视图能看到待确认草稿
        summary_resp = client.get(f"{BASE}/health-summary")
        assert summary_resp.status_code == 200
        assert len(summary_resp.json()["pending_intake_drafts"]) == 1

        # 5. 人工微调第一条饮食热量（560 -> 590）并确认落库
        edited_entries = draft["entries"]
        edited_entries[0]["data"]["calories"] = 590

        commit_resp = client.post(
            f"{BASE}/intake/{draft['id']}/commit",
            json={
                "entries": edited_entries,
                "summary": "已核对的今日饮食、睡眠、运动与体重",
                "ticket_id": ticket_id,
            },
        )
        assert commit_resp.status_code == 201, commit_resp.text
        committed = commit_resp.json()
        assert committed["draft"]["status"] == "committed"
        assert committed["replied_ticket_id"] == ticket_id
        assert committed["message_id"] is not None

        # 验证 5 张健康主表 + SailTickMessage + Ticket 回复全部落库成功
        diet_row = db.query(DietLog).first()
        assert diet_row is not None
        assert diet_row.calories == 590.0
        assert diet_row.photo_path == draft["media_key"]

        sleep_row = db.query(Sleep).first()
        assert sleep_row is not None
        assert sleep_row.hours == 450  # 7.5h = 450 minutes
        assert sleep_row.quality == 4

        ex_row = db.query(Exercise).first()
        assert ex_row is not None
        assert ex_row.duration_minutes == 35
        assert ex_row.calories == 320

        bd_row = db.query(BodyData).first()
        w_row = db.query(Weight).first()
        assert bd_row is not None and bd_row.data.get("weight") == 74.2
        assert w_row is not None and float(w_row.value) == pytest.approx(74.2)

        mood_row = db.query(Mood).first()
        assert mood_row is not None and mood_row.score == 4

        msg_row = db.query(SailTickMessage).first()
        assert msg_row is not None
        assert "[识图记录]" in msg_row.content
        assert msg_row.meta.get("draft_id") == draft["id"]

        ticket_row = db.get(SailTickTicket, ticket_id)
        assert ticket_row is not None
        assert ticket_row.status == "replied"
        assert "[识图记录]" in (ticket_row.reply or "")

        # 6. 幂等校验：重复 commit 不重复写库
        commit_again = client.post(
            f"{BASE}/intake/{draft['id']}/commit",
            json={"entries": edited_entries},
        )
        assert commit_again.status_code == 201
        assert db.query(DietLog).count() == 1

    def test_tall_screenshot_auto_triggers_ocr_assist_and_discard(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        ocr_called = {"count": 0}

        async def _fake_ocr(**kwargs):
            ocr_called["count"] += 1
            return OcrResult(
                id="ocr-test-1",
                purpose="text_recognition",
                page_count=1,
                pages=[OcrPage(index=0, text="白灼鸡胸 18元\n红烧肉 26元\n清炒西兰花 10元")],
                full_text="白灼鸡胸 18元\n红烧肉 26元\n清炒西兰花 10元",
                latency_ms=320.0,
            )

        async def _fake_vision(**kwargs):
            assert "白灼鸡胸" in kwargs["prompt"]
            return VisionResult(
                content="{}",
                parsed_json={
                    "scene": "canteen_menu",
                    "summary": "食堂点餐菜单（3道菜）",
                    "coach_advice": "推荐白灼鸡胸 + 清炒西兰花，高蛋白低油。",
                    "entries": [
                        {
                            "selected": True,
                            "kind": "canteen_menu",
                            "title": "食堂午间菜单",
                            "confidence": 0.92,
                            "data": {
                                "meal_type": "lunch",
                                "description": "菜单含白灼鸡胸、红烧肉、西兰花",
                                "recommended_items": ["白灼鸡胸", "清炒西兰花"],
                                "estimated_calories": 480,
                                "log_as_diet": False,
                            },
                        }
                    ],
                },
                model="deepseek-flash",
                usage={"total_tokens": 600},
                latency_ms=650.0,
            )

        monkeypatch.setattr("sail_server.model.tick_intake.deepseek_ocr_file", _fake_ocr)
        monkeypatch.setattr("sail_server.model.tick_intake.deepseek_vision_chat", _fake_vision)

        # 生成超长竖图（高宽比 3.0 >= 2.4），use_ocr_assist=auto 应自动触发 OCR 辅助
        tall_bytes = _make_jpeg_bytes(width=400, height=1200)
        resp = client.post(
            f"{BASE}/intake/analyze",
            data={"source_channel": "android_share", "use_ocr_assist": "auto"},
            files={"file": ("menu_long.jpg", tall_bytes, "image/jpeg")},
        )
        assert resp.status_code == 201, resp.text
        draft = resp.json()
        assert ocr_called["count"] == 1
        assert draft["model_used"] == "deepseek-flash+ocr"
        assert "白灼鸡胸" in draft["ocr_text"]
        assert draft["scene"] == "canteen_menu"

        # 丢弃草稿后不可再提交
        disc = client.post(f"{BASE}/intake/{draft['id']}/discard")
        assert disc.status_code == 201
        assert disc.json()["status"] == "discarded"

        bad_commit = client.post(
            f"{BASE}/intake/{draft['id']}/commit",
            json={"entries": draft["entries"]},
        )
        assert bad_commit.status_code == 400
