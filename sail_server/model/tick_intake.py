# -*- coding: utf-8 -*-
# @file tick_intake.py
# @brief SailTick 通用视觉识图（DeepSeek Vision/OCR）与二段式确认落库业务实现
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""SailTick 通用视觉识图业务逻辑。

闭环流程：
1. 上传图片 → 校验/EXIF 旋转校正/等比压缩 → 留存到 <SERVER_DATA_DIR>/tick_media/YYYY-MM/
2. 调 DeepSeek Vision (deepseek-flash) 一次性完成场景识别 + 结构化条目抽取 + 轻量建议；
   对超长截图（高宽比 >= 2.4）或显式指定 use_ocr_assist=true 时，先调 /v1/tools/ocr
   辅助提取高密度文字再联合图像理解（OCR 失败优雅降级，不阻断主流程）。
3. 返回 SailTickIntakeDraft 草稿供前端弹出确认卡片让用户人工核对/微调。
4. 用户点「确认落库」→ 事务性写入对应健康主表（DietLog / Sleep / Exercise / BodyData+Weight / Mood）
   + 自动写入汇总 SailTickMessage 供 SailTick 后续 Tick 与睡前日报整合
   + 若关联 ticket_id 则自动回复并关闭对应票据。
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from sail.llm.deepseek_vision import (
    DeepSeekVisionError,
    deepseek_ocr_file,
    deepseek_vision_chat,
)
from sail_server.application.dto.body_data import BUILTIN_METRIC_MAP, BodyDataCreateRequest
from sail_server.application.dto.health import (
    DietCreateRequest,
    ExerciseCreateRequest,
    MealType,
    MoodCreateRequest,
    SleepCreateRequest,
)
from sail_server.application.dto.tick import (
    CommittedRefDto,
    ImageIntakeCommitRequest,
    ImageIntakeCommitResponse,
    ImageIntakeDraftResponse,
    IntakeEntryDto,
    TickMessageCreateRequest,
)
from sail_server.config.paths import get_tick_media_dir
from sail_server.model.body_data import create_body_data_impl
from sail_server.model.health import (
    create_diet_impl,
    create_exercise_impl,
    create_mood_impl,
    create_sleep_impl,
)
from sail_server.model.tick import (
    TicketBadRequestError,
    TicketNotFoundError,
    create_message_impl,
    reply_ticket_impl,
)
from sailzen_orm.tick import SailTickIntakeDraft, SailTickTicket

logger = logging.getLogger(__name__)

MAX_IMAGE_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MiB 原始上传上限
MAX_IMAGE_LONG_EDGE = 1280  # 常规压缩最大边长（B3 降延迟，长截图/账单放宽至 1600）
MAX_IMAGE_LONG_EDGE_HIGH = 1600
JPEG_QUALITY = 84

VALID_SCENES = {
    "diet",
    "canteen_menu",
    "sleep",
    "exercise",
    "weight",
    "selfie_status",
    "receipt",
    "bill_screenshot",
    "account_balance",
    "general",
}
VALID_ENTRY_KINDS = {
    "diet",
    "canteen_menu",
    "sleep",
    "exercise",
    "weight",
    "mood",
    "transaction",
    "account_balance_check",
    "daily_info",
}
VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}

YEAR_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

INTAKE_SYSTEM_PROMPT = """你是 SailTick Personal Agent 的「通用视觉识图引擎」（覆盖健康管理 + 个人账单小票/流水/余额核对）。
用户会上传健康或日常消费相关的任意图片：
- 健康类：点餐 App 截图、食堂菜单、外卖订单、实拍餐盘、健康手表/手环的睡眠或运动节律截图、体重秤/体脂秤读数、自拍气色状态、零食营养成分表；
- 财务类：商超/便利店/餐饮小票、外卖/电商订单详情（盒马/京东/淘宝/美团/拼多多）、微信/支付宝账单流水截图、银行卡/微信/支付宝余额页截图、高铁/12306/机票/酒店订单截图。

你的任务是：准确看懂图片（含图表波形、商品清单、价格明细、商户时间、账户余额），结合用户备注与当前时间，抽取成严格合法的 JSON，供用户一键确认后写入数据库。

核心原则：
1. 温和客观，绝不对用户外貌、体重或消费做评判或批评；自拍只客观观察精神状态/疲劳感/气色并给 1-5 的温和状态评分。
2. 食堂菜单 / 点餐界面：
   - 已点/已下单/实拍餐盘用 kind="diet" 记录实际饮食并估算热量与营养素（protein/carbs/fat/sugar）。
   - 待选择菜单用 kind="canteen_menu"：给出 2-3 个高蛋白低油盐推荐，设 data.log_as_diet=false。
3. 健康手表/手环截图：
   - 睡眠页：hours（浮点数）、quality（1-5）、description。
   - 运动页：exercise_type、duration_minutes、calories、description。
4. 体重秤/体脂秤：kind="weight"，data.value 填公斤数（斤需除以 2 转 kg）。
5. 财务小票 / 电商订单 / 支付账单（scene="receipt" 或 "bill_screenshot"）：
   - **单笔混合采购小票/订单（如超市一次买了洗衣液和薯片）**：输出 **1 条** `kind="transaction"`，把总支付金额填在 `data.amount`，并在 `data.items` 中按商品/品类拆分（每项含 `name`, `amount`, `tag`, `is_snack`, `health_hint`）！这样既保持和银行流水 1:1 对应，又能让健康模块看见真实零食占比。
   - **微信/支付宝多笔流水列表截图**：每笔独立消费输出 1 条 `kind="transaction"`。
   - 财务标签优先从常用体系选择：零食、交通、日用消耗、娱乐休闲、人际交往、医药健康、衣物、大宗电器、大宗收支；可逗号分隔多个标签。
   - 若小票含零食/含糖饮品/正餐外卖，将对应明细 `is_snack=true` 且设 `data.sync_to_health=true`。
   - 若为 12306/高铁/机票/酒店订单，在 `data.travel_date` 填入 `YYYY-MM-DD` 以便联动日程。
6. 账户余额页截图（scene="account_balance"）：
   - 输出 `kind="account_balance_check"`，抽取 `account_hint`（如「微信」「支付宝余额宝」「招行」）和精确 `actual_balance` 数字。
7. 所有数值宁可合理估算并标注「约」，也不要编造离谱数值；完全看不清的数值留 null。

严格只输出一个 JSON 对象，Schema 如下：
{
  "scene": "diet | canteen_menu | sleep | exercise | weight | selfie_status | receipt | bill_screenshot | account_balance | general",
  "summary": "20-60字以内的清晰中文总结",
  "coach_advice": "1-2句温和、可执行的健康或开销秘书简评",
  "entries": [
    {
      "selected": true,
      "kind": "diet | canteen_menu | sleep | exercise | weight | mood | transaction | account_balance_check | daily_info",
      "title": "简短标题，如：盒马采购 ¥128.50（日用+零食）",
      "confidence": 0.9,
      "data": { ... }
    }
  ]
}

各 kind 的 data 字段约定：
- diet: {"meal_type": "breakfast|lunch|dinner|snack", "description": "...", "calories": 550, "protein": 32, "carbs": 60, "fat": 15, "sugar": 6}
- canteen_menu: {"meal_type": "lunch", "description": "菜单概况与推荐理由", "recommended_items": ["菜品A", "菜品B"], "estimated_calories": 520, "log_as_diet": false}
- sleep: {"hours": 7.5, "quality": 4, "description": "23:30-07:00，深睡1.8h，浅睡4.3h，REM 1.4h"}
- exercise: {"exercise_type": "running", "duration_minutes": 35, "calories": 320, "description": "户外跑5.0km，平均心率145"}
- weight: {"value": 74.2, "body_fat": 21.5, "description": "体脂秤记录"}
- mood: {"score": 4, "description": "气色观察/精神状态描述"}
- transaction: {"direction": "expense|income|transfer", "amount": 128.5, "description": "盒马鲜生采购", "tags": "日用消耗,零食", "account_hint": "支付宝", "htime": "2026-11-25 18:30", "sync_to_health": true, "travel_date": null, "items": [{"name": "薯片+无糖可乐", "amount": 42.0, "tag": "零食", "is_snack": true, "health_hint": "零食"}, {"name": "洗衣液+纸巾", "amount": 86.5, "tag": "日用消耗", "is_snack": false}]}
- account_balance_check: {"account_hint": "支付宝余额宝", "actual_balance": 2950.3, "description": "支付宝余额核对"}
- daily_info: {"category": "daily_info", "description": "其他健康或日常信息摘要"}
"""


def media_url_for_key(media_key: str) -> str:
    """将 media_key (YYYY-MM/filename) 转为相对 API URL。"""
    clean = (media_key or "").lstrip("/")
    if not clean:
        return ""
    return f"/api/v1/tick/media/{clean}"


def resolve_tick_media_path(year_month: str, filename: str) -> Path:
    """安全解析媒体文件路径，防目录穿越。"""
    if not YEAR_MONTH_RE.match(year_month or "") or not FILENAME_RE.match(filename or ""):
        raise TicketBadRequestError("invalid media path")
    root = get_tick_media_dir().resolve()
    target = (root / year_month / filename).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise TicketBadRequestError("invalid media path") from exc
    if not target.is_file():
        raise TicketNotFoundError(f"media not found: {year_month}/{filename}")
    return target


def _compress_and_store_image(
    raw_bytes: bytes,
    original_filename: str = "",
) -> Tuple[str, str, bytes, int, int, int]:
    """校验、校正 EXIF 方向、按需压缩并落盘到 tick_media/YYYY-MM/。

    Returns:
        (media_key, mime_type, stored_bytes, size, width, height)
    """
    if not raw_bytes:
        raise TicketBadRequestError("上传的图片为空")
    if len(raw_bytes) > MAX_IMAGE_UPLOAD_BYTES:
        raise TicketBadRequestError(
            f"图片超过大小限制（最大 {MAX_IMAGE_UPLOAD_BYTES // (1024 * 1024)} MB）"
        )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            width, height = img.size
            if width <= 0 or height <= 0:
                raise TicketBadRequestError("无效的图片尺寸")

            # 超长竖图（如点餐 App 长截图）适当保留更高纵边以免文字模糊
            aspect = max(width, height) / max(1, min(width, height))
            max_edge = 2400 if aspect >= 2.4 else MAX_IMAGE_LONG_EDGE
            if max(width, height) > max_edge:
                img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                width, height = img.size

            out = io.BytesIO()
            # 统一转 RGB 保存为高压缩比 JPEG（极省服务器空间与视觉 API 带宽）
            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                converted = img.convert("RGBA")
                bg.paste(converted, mask=converted.split()[-1])
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            stored_bytes = out.getvalue()
            mime_type = "image/jpeg"
            ext = "jpg"
    except TicketBadRequestError:
        raise
    except Exception as exc:
        raise TicketBadRequestError(f"无法解析图片文件，请上传合法的 JPG/PNG/WebP 图片: {exc}") from exc

    now = datetime.now()
    year_month = now.strftime("%Y-%m")
    file_hash = hashlib.md5(stored_bytes).hexdigest()[:8]
    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{file_hash}_{uuid.uuid4().hex[:6]}.{ext}"
    media_key = f"{year_month}/{filename}"

    target_dir = get_tick_media_dir() / year_month
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(stored_bytes)

    return media_key, mime_type, stored_bytes, len(stored_bytes), width, height


def _infer_meal_type_by_hour(now: datetime) -> str:
    h = now.hour
    if 5 <= h < 10:
        return "breakfast"
    if 10 <= h < 15:
        return "lunch"
    if 17 <= h < 21:
        return "dinner"
    return "snack"


def _safe_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _safe_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(round(float(v)))
    except (ValueError, TypeError):
        return None


def _normalize_entries(
    raw_entries: Any,
    scene: str,
    summary: str,
    now: datetime,
) -> List[Dict[str, Any]]:
    """清洗并规范化 AI 返回的 entries 数组，确保前端可安全编辑、后端可可靠落库。"""
    normalized: List[Dict[str, Any]] = []
    if not isinstance(raw_entries, list):
        raw_entries = []

    default_meal = _infer_meal_type_by_hour(now)

    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        if kind == "selfie_status":
            kind = "mood"
        if kind not in VALID_ENTRY_KINDS:
            kind = "daily_info"

        raw_data = item.get("data") if isinstance(item.get("data"), dict) else {}
        data: Dict[str, Any] = {}

        if kind == "diet":
            mt = str(raw_data.get("meal_type") or default_meal).strip().lower()
            if mt not in VALID_MEAL_TYPES:
                mt = default_meal
            data = {
                "meal_type": mt,
                "description": str(raw_data.get("description") or item.get("title") or summary).strip(),
                "calories": _safe_float(raw_data.get("calories")),
                "protein": _safe_float(raw_data.get("protein")),
                "carbs": _safe_float(raw_data.get("carbs")),
                "fat": _safe_float(raw_data.get("fat")),
                "sugar": _safe_float(raw_data.get("sugar")),
            }
        elif kind == "canteen_menu":
            mt = str(raw_data.get("meal_type") or default_meal).strip().lower()
            if mt not in VALID_MEAL_TYPES:
                mt = default_meal
            rec = raw_data.get("recommended_items")
            rec_list = [str(x).strip() for x in rec if str(x).strip()] if isinstance(rec, list) else []
            data = {
                "meal_type": mt,
                "description": str(raw_data.get("description") or summary).strip(),
                "recommended_items": rec_list,
                "estimated_calories": _safe_float(raw_data.get("estimated_calories")),
                "log_as_diet": bool(raw_data.get("log_as_diet", False)),
            }
        elif kind == "sleep":
            hours = _safe_float(raw_data.get("hours"))
            quality = _safe_int(raw_data.get("quality"))
            if quality is None:
                quality = 3
            quality = max(1, min(5, quality))
            data = {
                "hours": round(hours, 2) if hours is not None else 7.0,
                "quality": quality,
                "description": str(raw_data.get("description") or summary).strip(),
            }
        elif kind == "exercise":
            ex_type = str(raw_data.get("exercise_type") or "other").strip().lower()
            dur = _safe_int(raw_data.get("duration_minutes"))
            cal = _safe_int(raw_data.get("calories"))
            data = {
                "exercise_type": ex_type or "other",
                "duration_minutes": max(0, dur or 0),
                "calories": max(0, cal or 0),
                "description": str(raw_data.get("description") or item.get("title") or summary).strip(),
            }
        elif kind == "weight":
            val = _safe_float(raw_data.get("value"))
            bf = _safe_float(raw_data.get("body_fat") or raw_data.get("body_fat_pct"))
            data = {
                "value": round(val, 2) if val is not None else None,
                "body_fat": round(bf, 2) if bf is not None else None,
                "description": str(raw_data.get("description") or summary).strip(),
            }
        elif kind == "mood":
            score = _safe_int(raw_data.get("score"))
            if score is None:
                score = 3
            score = max(1, min(5, score))
            data = {
                "score": score,
                "description": str(raw_data.get("description") or summary).strip(),
            }
        elif kind == "transaction":
            direction = str(raw_data.get("direction") or "expense").strip().lower()
            if direction not in ("expense", "income", "transfer"):
                direction = "expense"
            amt = _safe_float(raw_data.get("amount") or raw_data.get("value"))
            raw_items = raw_data.get("items")
            norm_items: List[Dict[str, Any]] = []
            inferred_tags: List[str] = []
            has_snack_item = False
            if isinstance(raw_items, list):
                for sub in raw_items:
                    if not isinstance(sub, dict):
                        continue
                    sub_amt = _safe_float(sub.get("amount"))
                    sub_tag = str(sub.get("tag") or "").strip()
                    is_snack = bool(sub.get("is_snack", False)) or sub_tag == "零食"
                    if is_snack:
                        has_snack_item = True
                    if sub_tag and sub_tag not in inferred_tags:
                        inferred_tags.append(sub_tag)
                    norm_items.append(
                        {
                            "name": str(sub.get("name") or "商品").strip()[:60],
                            "amount": f"{abs(sub_amt):.2f}" if sub_amt is not None else "0.00",
                            "tag": sub_tag,
                            "is_snack": is_snack,
                            "health_hint": str(sub.get("health_hint") or "").strip()[:60],
                        }
                    )
            tags_str = str(raw_data.get("tags") or "").strip()
            if not tags_str and inferred_tags:
                tags_str = ",".join(inferred_tags)
            data = {
                "direction": direction,
                "amount": round(abs(amt), 2) if amt is not None else None,
                "description": str(raw_data.get("description") or item.get("title") or summary).strip()[:120],
                "tags": tags_str,
                "account_hint": str(raw_data.get("account_hint") or "").strip()[:40],
                "account_id": _safe_int(raw_data.get("account_id")),
                "htime": str(raw_data.get("htime") or now.strftime("%Y-%m-%d %H:%M")).strip(),
                "sync_to_health": bool(raw_data.get("sync_to_health", has_snack_item)),
                "travel_date": str(raw_data.get("travel_date") or "").strip()[:10] or None,
                "items": norm_items,
            }
        elif kind == "account_balance_check":
            bal = _safe_float(raw_data.get("actual_balance") or raw_data.get("balance"))
            data = {
                "account_hint": str(raw_data.get("account_hint") or "").strip()[:40],
                "account_id": _safe_int(raw_data.get("account_id")),
                "actual_balance": round(bal, 2) if bal is not None else None,
                "description": str(raw_data.get("description") or item.get("title") or summary).strip()[:120],
                "force_adjust": bool(raw_data.get("force_adjust", False)),
            }
        else:
            data = {
                "category": str(raw_data.get("category") or "daily_info").strip(),
                "description": str(raw_data.get("description") or item.get("title") or summary).strip(),
            }

        conf = _safe_float(item.get("confidence"))
        if conf is None:
            conf = 0.85
        conf = max(0.0, min(1.0, conf))

        title = str(item.get("title") or "").strip()
        if not title:
            title = {
                "diet": "饮食记录",
                "canteen_menu": "食堂菜单与点餐建议",
                "sleep": "睡眠节律记录",
                "exercise": "运动记录",
                "weight": "体重记录",
                "mood": "状态/气色记录",
                "transaction": "账单消费记录",
                "account_balance_check": "账户余额核对",
                "daily_info": "日常健康记录",
            }.get(kind, "健康记录")

        normalized.append(
            {
                "selected": bool(item.get("selected", True)),
                "kind": kind,
                "title": title,
                "confidence": conf,
                "data": data,
            }
        )

    if not normalized:
        normalized.append(
            {
                "selected": True,
                "kind": "daily_info",
                "title": "图片健康记录",
                "confidence": 0.6,
                "data": {
                    "category": "daily_info",
                    "description": summary or "已上传图片记录",
                },
            }
        )
    return normalized


def _to_draft_response(d: SailTickIntakeDraft) -> ImageIntakeDraftResponse:
    raw_entries = d.entries if isinstance(d.entries, list) else []
    entries = [IntakeEntryDto.model_validate(e) for e in raw_entries if isinstance(e, dict)]
    raw_refs = d.committed_refs if isinstance(d.committed_refs, list) else []
    refs = [CommittedRefDto.model_validate(r) for r in raw_refs if isinstance(r, dict)]
    return ImageIntakeDraftResponse(
        id=d.id,
        status=d.status or "pending_confirm",
        source_channel=d.source_channel or "android",
        ticket_id=d.ticket_id,
        media_key=d.media_key,
        media_url=media_url_for_key(d.media_key),
        media_mime=d.media_mime or "image/jpeg",
        media_size=int(d.media_size or 0),
        original_filename=d.original_filename or "",
        user_note=d.user_note or "",
        scene=d.scene or "general",
        summary=d.summary or "",
        coach_advice=d.coach_advice or "",
        ocr_text=d.ocr_text or "",
        entries=entries,
        committed_refs=refs,
        model_used=d.model_used or "deepseek-flash",
        usage=d.usage if isinstance(d.usage, dict) else {},
        created_at=d.created_at,
        updated_at=d.updated_at,
        committed_at=d.committed_at,
    )


async def analyze_image_intake_impl(
    db: Session,
    file_bytes: bytes,
    filename: str = "upload.jpg",
    note: str = "",
    source_channel: str = "android",
    ticket_id: Optional[int] = None,
    use_ocr_assist: str = "auto",
    domain_hint: str = "auto",
) -> ImageIntakeDraftResponse:
    """上传图片 → 压缩留存 → DeepSeek Vision（按需分级清晰度与 OCR）→ 生成待确认草稿。"""
    now = datetime.now()
    dom_hint = (domain_hint or "auto").strip().lower()

    # 若指定关联票据，校验存在并提取上下文供识图提示参考
    ticket_ctx = ""
    if ticket_id is not None:
        ticket = db.get(SailTickTicket, ticket_id)
        if not ticket:
            raise TicketNotFoundError(f"ticket {ticket_id} not found")
        ticket_ctx = f"\n【关联提问】标题：{ticket.title}\n正文：{(ticket.body or '')[:300]}"

    media_key, media_mime, stored_bytes, media_size, width, height = _compress_and_store_image(
        file_bytes, original_filename=filename
    )

    # 判断是否启用 DeepSeek 专用 OCR 工具辅助（显式开启、财务长截图或超长密字竖图）
    ocr_mode = (use_ocr_assist or "auto").strip().lower()
    aspect = max(width, height) / max(1, min(width, height))
    should_run_ocr = ocr_mode in ("true", "1", "yes", "force") or (
        ocr_mode == "auto" and aspect >= 2.4
    )
    # B3 分级清晰度：常规食物/体重拍照用 detail="auto" 提速，仅账单/小票/长截图/显式 OCR 用 "high"
    vision_detail = (
        "high"
        if (should_run_ocr or dom_hint == "finance" or aspect >= 2.0)
        else "auto"
    )

    ocr_text = ""
    ocr_usage: Dict[str, Any] = {}
    if should_run_ocr:
        try:
            ocr_res = await deepseek_ocr_file(
                file_bytes=stored_bytes,
                filename=Path(media_key).name,
                mime_type=media_mime,
                purpose="text_recognition",
            )
            ocr_text = ocr_res.full_text[:6000]
            ocr_usage = {"ocr_latency_ms": ocr_res.latency_ms, "ocr_pages": ocr_res.page_count}
        except DeepSeekVisionError as exc:
            logger.warning("[tick_intake] OCR assist skipped (fallback to pure vision): %s", exc)

    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    prompt_lines = [
        f"当前时间：{now.strftime('%Y-%m-%d %H:%M')}（{weekdays[now.weekday()]}）",
        f"默认餐次参考：{_infer_meal_type_by_hour(now)}",
    ]
    if dom_hint in ("health", "finance"):
        prompt_lines.append(
            "【入口场景提示】用户从"
            + ("财务/记账页" if dom_hint == "finance" else "健康页")
            + "上传此图，请优先按对应业务域精准识别。"
        )
    if note and note.strip():
        prompt_lines.append(f"【用户备注】{note.strip()}")
    if ticket_ctx:
        prompt_lines.append(ticket_ctx)
    if ocr_text:
        prompt_lines.append(
            "【DeepSeek OCR 辅助提取文本（供精准核对文字/价格/数字）】\n" + ocr_text
        )
    prompt_lines.append("请识别图片并严格按要求的 JSON Schema 输出。")

    try:
        vision_res = await deepseek_vision_chat(
            image_bytes=stored_bytes,
            mime_type=media_mime,
            prompt="\n\n".join(prompt_lines),
            system=INTAKE_SYSTEM_PROMPT,
            detail=vision_detail,
            expect_json=True,
        )
    except DeepSeekVisionError as exc:
        raise TicketBadRequestError(f"AI 识图服务暂不可用：{exc}") from exc

    parsed = vision_res.parsed_json or {}
    scene = str(parsed.get("scene") or "general").strip().lower()
    if scene not in VALID_SCENES:
        scene = "general"
    summary = str(parsed.get("summary") or "").strip() or "已识别图片内容，请确认以下条目"
    coach_advice = str(parsed.get("coach_advice") or "").strip()
    entries = _normalize_entries(parsed.get("entries"), scene=scene, summary=summary, now=now)

    model_used = vision_res.model + ("+ocr" if ocr_text else "")
    usage: Dict[str, Any] = {
        **(vision_res.usage or {}),
        "vision_latency_ms": vision_res.latency_ms,
        "image_size": [width, height],
        **ocr_usage,
    }

    draft = SailTickIntakeDraft(
        status="pending_confirm",
        source_channel=(source_channel or "android").strip(),
        ticket_id=ticket_id,
        media_key=media_key,
        media_mime=media_mime,
        media_size=media_size,
        original_filename=(filename or "")[:200],
        user_note=(note or "").strip(),
        scene=scene,
        summary=summary,
        coach_advice=coach_advice,
        ocr_text=ocr_text,
        entries=entries,
        committed_refs=[],
        model_used=model_used,
        usage=usage,
        created_at=now,
        updated_at=now,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    logger.info(
        "[tick_intake] draft %s created: scene=%s entries=%d model=%s",
        draft.id,
        draft.scene,
        len(entries),
        model_used,
    )
    return _to_draft_response(draft)


def get_image_intake_draft_impl(db: Session, draft_id: int) -> ImageIntakeDraftResponse:
    d = db.get(SailTickIntakeDraft, draft_id)
    if not d:
        raise TicketNotFoundError(f"intake draft {draft_id} not found")
    return _to_draft_response(d)


def list_image_intake_drafts_impl(
    db: Session,
    status: Optional[str] = None,
    limit: int = 20,
) -> List[ImageIntakeDraftResponse]:
    q = db.query(SailTickIntakeDraft)
    if status:
        q = q.filter(SailTickIntakeDraft.status == status)
    rows = (
        q.order_by(SailTickIntakeDraft.created_at.desc(), SailTickIntakeDraft.id.desc())
        .limit(limit)
        .all()
    )
    return [_to_draft_response(r) for r in rows]


def discard_image_intake_impl(db: Session, draft_id: int) -> ImageIntakeDraftResponse:
    d = db.get(SailTickIntakeDraft, draft_id)
    if not d:
        raise TicketNotFoundError(f"intake draft {draft_id} not found")
    if d.status == "committed":
        return _to_draft_response(d)
    d.status = "discarded"
    d.updated_at = datetime.now()
    db.commit()
    db.refresh(d)
    return _to_draft_response(d)


def _resolve_finance_account_id(
    db: Session,
    explicit_id: Optional[int],
    account_hint: str = "",
) -> Optional[int]:
    """根据显式 ID 或中文账户提示（如「微信」「支付宝」「招行」）解析目标物理账户。"""
    from sailzen_orm.finance import Account

    if explicit_id is not None and int(explicit_id) > 0:
        acc = db.query(Account).filter(Account.id == int(explicit_id)).first()
        if acc is not None:
            return acc.id

    accounts = db.query(Account).order_by(Account.id.asc()).all()
    if not accounts:
        return None
    active = [a for a in accounts if (a.state or 0) == 0]
    pool = active or accounts

    hint = (account_hint or "").strip().lower()
    if hint:
        for a in pool:
            name_low = (a.name or "").lower()
            if hint in name_low or name_low in hint:
                return a.id
        # 常见简称映射
        aliases = {
            "wechat": "微信",
            "wx": "微信",
            "alipay": "支付宝",
            "余额宝": "支付宝",
            "cmb": "招行",
            "boc": "中行",
            "icbc": "工商",
        }
        mapped = aliases.get(hint)
        if mapped:
            for a in pool:
                if mapped in (a.name or ""):
                    return a.id

    # 默认优先常用日常消费账户（微信 / 支付宝）
    for pref in ("微信", "支付宝"):
        for a in pool:
            if pref in (a.name or ""):
                return a.id
    return pool[0].id


def _parse_tx_htime(raw_htime: Any, fallback: datetime) -> float:
    if isinstance(raw_htime, (int, float)) and raw_htime > 1_000_000_000:
        return float(raw_htime)
    if isinstance(raw_htime, str) and raw_htime.strip():
        s = raw_htime.strip().replace("/", "-")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(s[:19], fmt).timestamp()
            except ValueError:
                continue
    return fallback.timestamp()


def _scene_to_message_category(scene: str, entries: List[IntakeEntryDto]) -> str:
    selected_kinds = [e.kind for e in entries if e.selected]
    for k in selected_kinds:
        if k in ("diet", "weight", "exercise", "mood"):
            return k
        if k in ("transaction", "account_balance_check"):
            return "daily_info"
    return {
        "diet": "diet",
        "weight": "weight",
        "exercise": "exercise",
        "selfie_status": "mood",
        "sleep": "daily_info",
        "canteen_menu": "daily_info",
        "receipt": "daily_info",
        "bill_screenshot": "daily_info",
        "account_balance": "daily_info",
    }.get(scene, "daily_info")


def commit_image_intake_impl(
    db: Session,
    draft_id: int,
    req: ImageIntakeCommitRequest,
) -> ImageIntakeCommitResponse:
    """人工确认/微调草稿后正式落库到健康主表 + SailTickMessage +（可选）回复票据。"""
    draft = db.get(SailTickIntakeDraft, draft_id)
    if not draft:
        raise TicketNotFoundError(f"intake draft {draft_id} not found")

    # 幂等：已确认草稿直接返回当前状态
    if draft.status == "committed":
        resp_draft = _to_draft_response(draft)
        msg_id = next((r.id for r in resp_draft.committed_refs if r.kind == "message"), None)
        return ImageIntakeCommitResponse(
            draft=resp_draft,
            committed_refs=resp_draft.committed_refs,
            message_id=msg_id,
            replied_ticket_id=draft.ticket_id,
        )
    if draft.status == "discarded":
        raise TicketBadRequestError("该识图草稿已丢弃，请重新上传图片")

    now = datetime.now()
    entries = req.entries if req.entries else [
        IntakeEntryDto.model_validate(e)
        for e in (draft.entries if isinstance(draft.entries, list) else [])
        if isinstance(e, dict)
    ]
    selected_entries = [e for e in entries if e.selected]
    if not selected_entries:
        raise TicketBadRequestError("请至少勾选一条需要落库的记录")

    summary = (req.summary if req.summary is not None else draft.summary) or "图片识图记录"
    user_note = (req.user_note if req.user_note is not None else draft.user_note) or ""
    committed_refs: List[CommittedRefDto] = []
    summary_parts: List[str] = []

    for entry in selected_entries:
        kind = entry.kind
        data = entry.data or {}

        if kind == "diet":
            mt_raw = str(data.get("meal_type") or _infer_meal_type_by_hour(now)).lower()
            try:
                meal_type = MealType(mt_raw)
            except ValueError:
                meal_type = MealType(_infer_meal_type_by_hour(now))
            desc = str(data.get("description") or entry.title or summary).strip()
            diet_req = DietCreateRequest(
                meal_type=meal_type,
                description=desc,
                photo_path=draft.media_key,
                calories=_safe_float(data.get("calories")),
                carbs=_safe_float(data.get("carbs")),
                sugar=_safe_float(data.get("sugar")),
                protein=_safe_float(data.get("protein")),
                fat=_safe_float(data.get("fat")),
            )
            created = create_diet_impl(db, diet_req)
            cal_str = f"（约 {int(round(created.calories))} kcal）" if created.calories else ""
            committed_refs.append(CommittedRefDto(kind="diet", id=created.id, label=f"饮食: {desc[:30]}{cal_str}"))
            summary_parts.append(f"饮食[{meal_type.value}] {desc}{cal_str}")

        elif kind == "canteen_menu":
            desc = str(data.get("description") or entry.title or summary).strip()
            rec_items = data.get("recommended_items") or []
            rec_str = "、".join(str(x) for x in rec_items if str(x).strip())
            if data.get("log_as_diet"):
                mt_raw = str(data.get("meal_type") or _infer_meal_type_by_hour(now)).lower()
                try:
                    meal_type = MealType(mt_raw)
                except ValueError:
                    meal_type = MealType(_infer_meal_type_by_hour(now))
                diet_desc = f"{rec_str}（{desc}）" if rec_str else desc
                created = create_diet_impl(
                    db,
                    DietCreateRequest(
                        meal_type=meal_type,
                        description=diet_desc,
                        photo_path=draft.media_key,
                        calories=_safe_float(data.get("estimated_calories")),
                    ),
                )
                committed_refs.append(CommittedRefDto(kind="diet", id=created.id, label=f"菜单选餐: {diet_desc[:30]}"))
            summary_parts.append(f"食堂菜单: {desc}" + (f"（建议: {rec_str}）" if rec_str else ""))

        elif kind == "sleep":
            hours = _safe_float(data.get("hours"))
            if hours is None or hours <= 0:
                hours = 7.0
            quality = _safe_int(data.get("quality")) or 3
            quality = max(1, min(5, quality))
            desc = str(data.get("description") or entry.title or "").strip()
            created = create_sleep_impl(
                db,
                SleepCreateRequest(hours=hours, quality=quality, description=desc),
            )
            committed_refs.append(CommittedRefDto(kind="sleep", id=created.id, label=f"睡眠 {hours:.1f}h (质量{quality}/5)"))
            summary_parts.append(f"睡眠 {hours:.1f}h（质量{quality}/5）{desc}")

        elif kind == "exercise":
            ex_type = str(data.get("exercise_type") or "other").strip()
            dur = max(0, _safe_int(data.get("duration_minutes")) or 0)
            cal = max(0, _safe_int(data.get("calories")) or 0)
            desc = str(data.get("description") or entry.title or "").strip()
            created = create_exercise_impl(
                db,
                ExerciseCreateRequest(
                    exercise_type=ex_type,
                    duration_minutes=dur,
                    calories=cal,
                    description=desc,
                    completed=True,
                    source="health",
                ),
            )
            committed_refs.append(
                CommittedRefDto(kind="exercise", id=created.id, label=f"运动 {ex_type} {dur}分钟/{cal}kcal")
            )
            summary_parts.append(f"运动[{ex_type}] {dur}分钟 {cal}kcal {desc}")

        elif kind == "weight":
            val = _safe_float(data.get("value"))
            if val is not None and val > 0:
                metrics: Dict[str, float] = {"weight": val}
                bf = _safe_float(data.get("body_fat") or data.get("body_fat_pct"))
                if bf is not None and bf > 0:
                    for k in ("body_fat_pct", "body_fat", "fat_rate"):
                        if k in BUILTIN_METRIC_MAP:
                            metrics[k] = bf
                            break
                desc = str(data.get("description") or entry.title or "识图记录体重").strip()
                created = create_body_data_impl(
                    db,
                    BodyDataCreateRequest(data=metrics, tag="raw", description=desc),
                )
                committed_refs.append(CommittedRefDto(kind="weight", id=created.id, label=f"体重 {val:.1f}kg"))
                summary_parts.append(f"体重 {val:.1f}kg")

        elif kind == "mood":
            score = _safe_int(data.get("score")) or 3
            score = max(1, min(5, score))
            desc = str(data.get("description") or entry.title or summary).strip()
            created = create_mood_impl(
                db,
                MoodCreateRequest(score=score, description=desc),
            )
            committed_refs.append(CommittedRefDto(kind="mood", id=created.id, label=f"状态/气色 {score}/5"))
            summary_parts.append(f"气色/状态 {score}/5：{desc}")

        elif kind == "transaction":
            from sail_server.application.dto.finance import TransactionData
            from sail_server.model.finance.account import update_account_balance_impl
            from sail_server.model.finance.transaction import create_transaction_impl

            amt = _safe_float(data.get("amount") or data.get("value"))
            if amt is not None and amt > 0:
                direction = str(data.get("direction") or "expense").lower()
                acc_id = _resolve_finance_account_id(
                    db,
                    _safe_int(data.get("account_id")),
                    str(data.get("account_hint") or ""),
                )
                if acc_id is None:
                    raise TicketBadRequestError("未找到可用的财务账户，请先创建账户")

                from_acc_id, to_acc_id = (acc_id, -1) if direction != "income" else (-1, acc_id)
                desc = str(data.get("description") or entry.title or summary).strip()
                tags_str = str(data.get("tags") or "").strip()
                items = data.get("items") if isinstance(data.get("items"), list) else []
                htime_ts = _parse_tx_htime(data.get("htime"), now)

                # 跨领域健康联动：若明细中含零食/饮品且开启 sync_to_health，顺手写入轻量 DietLog
                linked_diet_ids: List[int] = []
                snack_items = [
                    it for it in items if isinstance(it, dict) and (it.get("is_snack") or it.get("tag") == "零食")
                ]
                should_sync_health = bool(data.get("sync_to_health", bool(snack_items)))
                if should_sync_health and (snack_items or "零食" in tags_str):
                    snack_names = "、".join(
                        f"{it.get('name', '零食')}(¥{it.get('amount', '')})" for it in snack_items[:6]
                    ) or desc
                    diet_rec = create_diet_impl(
                        db,
                        DietCreateRequest(
                            meal_type=MealType.SNACK,
                            description=f"[小票联动] {snack_names}",
                            photo_path=draft.media_key,
                        ),
                    )
                    linked_diet_ids.append(diet_rec.id)
                    committed_refs.append(
                        CommittedRefDto(kind="diet", id=diet_rec.id, label=f"联动零食记录: {snack_names[:26]}")
                    )

                tx_meta: Dict[str, Any] = {
                    "items": items,
                    "links": {
                        "intake_draft_id": draft.id,
                        **({"diet_ids": linked_diet_ids} if linked_diet_ids else {}),
                        **({"travel_date": data["travel_date"]} if data.get("travel_date") else {}),
                    },
                    "ai_audit": {"source": "ocr_intake", "draft_id": draft.id},
                }
                created_tx = create_transaction_impl(
                    db,
                    TransactionData(
                        from_acc_id=from_acc_id,
                        to_acc_id=to_acc_id,
                        value=f"{abs(amt):.2f}",
                        description=desc,
                        tags=tags_str,
                        entry_kind="normal",
                        exclude_from_stats=False,
                        meta=tx_meta,
                        htime=htime_ts,
                    ),
                )
                update_account_balance_impl(db, acc_id)
                split_note = f"（已拆 {len(items)} 项明细）" if items else ""
                committed_refs.append(
                    CommittedRefDto(
                        kind="transaction",
                        id=created_tx.id,
                        label=f"记账 ¥{abs(amt):.2f} {desc[:20]}{split_note}",
                    )
                )
                summary_parts.append(f"账单[{tags_str or '未分类'}] {desc} ¥{abs(amt):.2f}{split_note}")

        elif kind == "account_balance_check":
            from sail_server.application.dto.finance import AccountReconcileRequest
            from sail_server.model.finance.account import reconcile_account_balance_impl

            bal = _safe_float(data.get("actual_balance") or data.get("balance"))
            acc_id = _resolve_finance_account_id(
                db,
                _safe_int(data.get("account_id")),
                str(data.get("account_hint") or ""),
            )
            if bal is not None and acc_id is not None:
                rec = reconcile_account_balance_impl(
                    db,
                    AccountReconcileRequest(
                        account_id=acc_id,
                        actual_balance=f"{bal:.2f}",
                        force_adjust=bool(data.get("force_adjust", False)),
                        note=str(data.get("description") or "截图余额核对"),
                        source="ocr",
                    ),
                )
                if rec:
                    committed_refs.append(
                        CommittedRefDto(
                            kind="account_reconcile",
                            id=rec["checkpoint"].id,
                            label=rec["message"][:40],
                        )
                    )
                    summary_parts.append(rec["message"])

        else:
            desc = str(data.get("description") or entry.title or summary).strip()
            summary_parts.append(desc)

    # 汇总写入一条 SailTickMessage，让 SailTick 下个 Tick / 睡前日报无缝吸收
    msg_content = f"[识图记录] {summary}"
    if summary_parts:
        msg_content = f"[识图记录] {'；'.join(summary_parts)}"
    if user_note:
        msg_content += f"（备注：{user_note}）"

    msg_category = _scene_to_message_category(draft.scene, selected_entries)
    msg_resp = create_message_impl(
        db,
        TickMessageCreateRequest(
            direction="user_to_agent",
            category=msg_category,
            content=msg_content[:1000],
            meta={
                "draft_id": draft.id,
                "scene": draft.scene,
                "media_key": draft.media_key,
                "media_url": media_url_for_key(draft.media_key),
                "coach_advice": draft.coach_advice,
                "committed_refs": [r.model_dump() for r in committed_refs],
            },
            source_channel=draft.source_channel or "android",
            auto_log_diet=False,  # 饮食已由上方结构化写入，不重复建轻量 DietLog
        ),
    )
    committed_refs.append(CommittedRefDto(kind="message", id=msg_resp.id, label="教练消息已同步"))

    # 若关联票据，自动回复该票据（兼容同事务中饮食/体重落库已自动消解该票据的场景）
    target_ticket_id = req.ticket_id if req.ticket_id is not None else draft.ticket_id
    replied_ticket_id: Optional[int] = None
    if target_ticket_id is not None:
        reply_text = (req.reply_text or "").strip() or msg_content
        try:
            existing_ticket = db.get(SailTickTicket, target_ticket_id)
            if existing_ticket is not None and existing_ticket.status == "replied":
                # 若同次提交已由域事件自动消解，用更完整的识图汇总回复覆盖并同步回写收件箱
                existing_ticket.reply = reply_text
                db.commit()
                replied_ticket_id = target_ticket_id
            else:
                reply_ticket_impl(db, target_ticket_id, reply_text)
                replied_ticket_id = target_ticket_id
            committed_refs.append(
                CommittedRefDto(kind="ticket", id=target_ticket_id, label=f"已回复票据 #{target_ticket_id}")
            )
        except Exception as exc:
            logger.warning("[tick_intake] auto reply ticket %s failed (non-fatal): %s", target_ticket_id, exc)

    draft.entries = [e.model_dump() for e in entries]
    draft.summary = summary
    draft.user_note = user_note
    if target_ticket_id is not None:
        draft.ticket_id = target_ticket_id
    draft.committed_refs = [r.model_dump() for r in committed_refs]
    draft.status = "committed"
    draft.committed_at = now
    draft.updated_at = now
    db.commit()
    db.refresh(draft)

    logger.info(
        "[tick_intake] draft %s committed: refs=%d ticket=%s",
        draft.id,
        len(committed_refs),
        replied_ticket_id,
    )
    return ImageIntakeCommitResponse(
        draft=_to_draft_response(draft),
        committed_refs=committed_refs,
        message_id=msg_resp.id,
        replied_ticket_id=replied_ticket_id,
    )
