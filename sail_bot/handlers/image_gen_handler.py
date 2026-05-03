# -*- coding: utf-8 -*-
# @file image_gen_handler.py
# @brief Image generation workflow handler
# @author sailing-innocent
# @date 2025-07-20
# @version 1.0
# ---------------------------------
"""Handler for the image generation workflow.

Uses OpenAICompatProvider via dogapi.cc proxy to generate/edit images.
"""

import os
import asyncio
import tempfile
import threading
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from sail.llm.providers import (
    OpenAICompatProvider,
    ProviderConfig,
    ImageGenerationConfig,
)
from sail_bot.handlers.base import BaseHandler, HandlerContext
from sail_bot.context import ConversationContext, ActionPlan
from sail.feishu_card_kit.renderer import CardRenderer

logger = logging.getLogger(__name__)

# Load DOGAPI_KEY from .env.prod
_ENV_PROD_PATH = Path(__file__).parents[2] / ".env.prod"
if _ENV_PROD_PATH.exists():
    load_dotenv(_ENV_PROD_PATH, override=True)

_DOGAPI_KEY = os.getenv("DOGAPI_KEY", "")
_DOGAPI_BASE = os.getenv("DOGAPI_BASE", "https://www.dogapi.cc/v1")
_IMAGE_MODEL = "gpt-image-2"


class ImageGenHandler(BaseHandler):
    """图片生成工作流 Handler"""

    def __init__(self, ctx: HandlerContext):
        super().__init__(ctx)
        self._provider: Optional[OpenAICompatProvider] = None

    def _ensure_provider(self) -> OpenAICompatProvider:
        if self._provider is None:
            if not _DOGAPI_KEY:
                raise RuntimeError("DOGAPI_KEY not configured in .env.prod")
            cfg = ProviderConfig(
                provider_name="openai_compat",
                model=_IMAGE_MODEL,
                api_key=_DOGAPI_KEY,
                api_base=_DOGAPI_BASE,
            )
            self._provider = OpenAICompatProvider(cfg)
            self._provider._init_client()
        return self._provider

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def handle_enter(self, chat_id: str, message_id: str, ctx: ConversationContext) -> None:
        ctx.mode = "image_gen"
        if ctx.image_gen is None:
            from sail_bot.context import ImageGenState
            ctx.image_gen = ImageGenState()
        self.ctx.save_contexts()

        card = CardRenderer.result(
            "🎨 图片生成模式",
            "已进入图片生成工作流。\n\n"
            "• 直接输入描述来生成图片\n"
            "• 生成后可以继续输入描述来编辑图片\n"
            "• 「保存 xxx.png」保存当前图片\n"
            "• 「退出」退出图片生成模式",
            success=True,
        )
        self.ctx.messaging.reply_card(message_id, card)

    def handle_generate(self, plan: ActionPlan, chat_id: str, message_id: str, ctx: ConversationContext) -> None:
        prompt = plan.params.get("prompt", "")
        if not prompt:
            self.ctx.messaging.reply_text(message_id, "请输入图片描述")
            return
        self._run_async(self._do_generate(prompt, chat_id, message_id, ctx))

    def handle_edit(self, plan: ActionPlan, chat_id: str, message_id: str, ctx: ConversationContext) -> None:
        prompt = plan.params.get("prompt", "")
        if not prompt:
            self.ctx.messaging.reply_text(message_id, "请输入编辑描述")
            return
        if not ctx.image_gen or not ctx.image_gen.last_image_path:
            self.ctx.messaging.reply_text(message_id, "没有可编辑的图片，先生成一张")
            return
        self._run_async(self._do_edit(prompt, chat_id, message_id, ctx))

    def handle_save(self, plan: ActionPlan, chat_id: str, message_id: str, ctx: ConversationContext) -> None:
        filename = plan.params.get("filename", "image.png")
        if not ctx.image_gen or not ctx.image_gen.last_image_path:
            self.ctx.messaging.reply_text(message_id, "没有可保存的图片")
            return
        src = Path(ctx.image_gen.last_image_path)
        dest = Path(filename)
        try:
            dest.write_bytes(src.read_bytes())
            self.ctx.messaging.reply_text(message_id, f"✅ 已保存为 {dest.absolute()}")
        except Exception as exc:
            logger.error("Save image failed: %s", exc)
            self.ctx.messaging.reply_text(message_id, f"❌ 保存失败: {exc}")

    def handle_exit(self, chat_id: str, message_id: str, ctx: ConversationContext) -> None:
        ctx.mode = "idle"
        ctx.image_gen = None
        self.ctx.save_contexts()
        card = CardRenderer.result("已退出", "已退出图片生成模式", success=True)
        self.ctx.messaging.reply_card(message_id, card)

    # ------------------------------------------------------------------
    # Async internals
    # ------------------------------------------------------------------

    def _run_async(self, coro):
        def runner():
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(coro)
            finally:
                loop.close()
        threading.Thread(target=runner, daemon=True).start()

    async def _do_generate(self, prompt: str, chat_id: str, message_id: str, ctx: ConversationContext) -> None:
        progress_mid = None
        try:
            progress_card = CardRenderer.progress("正在生成图片", f"Prompt: {prompt}")
            progress_mid = self.ctx.messaging.reply_card(message_id, progress_card)

            provider = self._ensure_provider()
            resp = provider.generate_image(
                prompt,
                config=ImageGenerationConfig(width=1024, height=1024, num_images=1),
            )

            suffix = "png" if resp.mime_type == "image/png" else "jpg"
            tmp_path = Path(tempfile.gettempdir()) / f"sz_img_{chat_id}_{os.urandom(4).hex()}.{suffix}"
            tmp_path.write_bytes(resp.image_bytes)

            if ctx.image_gen is None:
                from sail_bot.context import ImageGenState
                ctx.image_gen = ImageGenState()
            ctx.image_gen.last_image_path = str(tmp_path)
            ctx.image_gen.last_prompt = prompt
            self.ctx.save_contexts()

            self.ctx.messaging.reply_image(message_id, resp.image_bytes)

            success_card = CardRenderer.result(
                "生成完成",
                f"Prompt: {prompt}\n\n输入新描述可继续编辑，「保存 xxx.png」保存，「退出」退出。",
                success=True,
            )
            if progress_mid:
                self.ctx.messaging.update_card(progress_mid, success_card)
            else:
                self.ctx.messaging.reply_card(message_id, success_card)
        except Exception as exc:
            logger.error("Image generation failed: %s", exc, exc_info=True)
            error_card = CardRenderer.result("生成失败", str(exc), success=False)
            if progress_mid:
                self.ctx.messaging.update_card(progress_mid, error_card)
            else:
                self.ctx.messaging.reply_card(message_id, error_card)

    async def _do_edit(self, prompt: str, chat_id: str, message_id: str, ctx: ConversationContext) -> None:
        progress_mid = None
        try:
            progress_card = CardRenderer.progress("正在编辑图片", f"Edit: {prompt}")
            progress_mid = self.ctx.messaging.reply_card(message_id, progress_card)

            provider = self._ensure_provider()
            resp = provider.edit_image(
                ctx.image_gen.last_image_path,
                prompt,
                config=ImageGenerationConfig(width=1024, height=1024, num_images=1),
            )

            suffix = "png" if resp.mime_type == "image/png" else "jpg"
            tmp_path = Path(tempfile.gettempdir()) / f"sz_img_{chat_id}_{os.urandom(4).hex()}.{suffix}"
            tmp_path.write_bytes(resp.image_bytes)

            ctx.image_gen.last_image_path = str(tmp_path)
            ctx.image_gen.last_prompt = prompt
            self.ctx.save_contexts()

            self.ctx.messaging.reply_image(message_id, resp.image_bytes)

            success_card = CardRenderer.result(
                "编辑完成",
                f"Edit: {prompt}\n\n可继续编辑、保存或退出。",
                success=True,
            )
            if progress_mid:
                self.ctx.messaging.update_card(progress_mid, success_card)
            else:
                self.ctx.messaging.reply_card(message_id, success_card)
        except Exception as exc:
            logger.error("Image edit failed: %s", exc, exc_info=True)
            error_card = CardRenderer.result("编辑失败", str(exc), success=False)
            if progress_mid:
                self.ctx.messaging.update_card(progress_mid, error_card)
            else:
                self.ctx.messaging.reply_card(message_id, error_card)
