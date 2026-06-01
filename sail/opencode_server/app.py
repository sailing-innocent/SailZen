# -*- coding: utf-8 -*-
# @file app.py
# @brief aiohttp application implementing opencode-compatible HTTP/SSE API.
# @author sailing-innocent
# @date 2026-05-31
# @version 1.0
# ---------------------------------

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from aiohttp import web

from sail.opencode_server.llm_backend import LLMBackend, MockBackend
from sail.opencode_server.sse import SSEBroadcaster
from sail.opencode_server.store import OpencodeStore

logger = logging.getLogger(__name__)


class OpencodeServerApp:
    """Assemble routes, store, broadcaster, and LLM backend."""

    def __init__(
        self,
        store: Optional[OpencodeStore] = None,
        broadcaster: Optional[SSEBroadcaster] = None,
        backend: Optional[LLMBackend] = None,
    ) -> None:
        self.store = store or OpencodeStore()
        self.broadcaster = broadcaster or SSEBroadcaster()
        self.backend = backend or MockBackend()
        self._app = web.Application()
        self._register_routes()

    def _register_routes(self) -> None:
        self._app.router.add_get("/global/health", self._health)
        self._app.router.add_get("/session", self._list_sessions)
        self._app.router.add_post("/session", self._create_session)
        self._app.router.add_get("/session/{id}", self._get_session)
        self._app.router.add_delete("/session/{id}", self._delete_session)
        self._app.router.add_get("/session/{id}/message", self._get_messages)
        self._app.router.add_get("/session/{id}/children", self._get_children)
        self._app.router.add_get("/session/status", self._session_status)
        self._app.router.add_post(
            "/session/{id}/prompt_async", self._prompt_async
        )
        self._app.router.add_post("/session/{id}/message", self._send_message)
        self._app.router.add_post("/session/{id}/abort", self._abort_session)
        self._app.router.add_get("/agent", self._list_agents)
        self._app.router.add_get("/config", self._get_config)
        self._app.router.add_patch("/config", self._patch_config)
        self._app.router.add_post(
            "/permission/{perm_id}/reply", self._permission_reply
        )
        self._app.router.add_get("/event", self._event_stream)

    # ── Helpers ───────────────────────────────────────────────────

    def _sse(self, event: str, data: Dict[str, Any]) -> bytes:
        lines = [f"event: {event}", f"data: {json.dumps(data, ensure_ascii=False)}"]
        return ("\n".join(lines) + "\n\n").encode("utf-8")

    # ── Handlers ──────────────────────────────────────────────────

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"healthy": True})

    async def _list_sessions(self, request: web.Request) -> web.Response:
        sessions = [s.to_dict() for s in self.store.list_sessions()]
        return web.json_response(sessions)

    async def _create_session(self, request: web.Request) -> web.Response:
        body = await request.json() if request.can_read_body else {}
        sess = self.store.create_session(title=body.get("title"))
        return web.json_response(sess.to_dict())

    async def _get_session(self, request: web.Request) -> web.Response:
        sid = request.match_info["id"]
        sess = self.store.get_session(sid)
        if not sess:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response(sess.to_dict())

    async def _delete_session(self, request: web.Request) -> web.Response:
        sid = request.match_info["id"]
        ok = self.store.delete_session(sid)
        return web.json_response({"ok": ok})

    async def _get_messages(self, request: web.Request) -> web.Response:
        sid = request.match_info["id"]
        limit = int(request.query.get("limit", "10"))
        msgs = self.store.get_messages(sid, limit=limit)
        return web.json_response([m.to_dict() for m in msgs])

    async def _get_children(self, request: web.Request) -> web.Response:
        sid = request.match_info["id"]
        children = self.store.get_children(sid)
        return web.json_response(children)

    async def _session_status(self, request: web.Request) -> web.Response:
        return web.json_response(self.store.get_session_status())

    async def _prompt_async(self, request: web.Request) -> web.Response:
        sid = request.match_info["id"]
        body = await request.json() if request.can_read_body else {}
        text = ""
        for part in body.get("parts", []):
            if part.get("type") == "text":
                text = part.get("text", "")
                break
        if not text:
            return web.Response(status=400)

        self.store.add_message(sid, "user", body.get("parts", []))
        self.store.set_session_status(sid, "busy")

        # Kick off background generation
        asyncio.create_task(self._generate(sid, text, body))
        return web.Response(status=204)

    async def _send_message(self, request: web.Request) -> web.Response:
        sid = request.match_info["id"]
        body = await request.json() if request.can_read_body else {}
        text = ""
        for part in body.get("parts", []):
            if part.get("type") == "text":
                text = part.get("text", "")
                break
        if not text:
            return web.Response(status=400)

        self.store.add_message(sid, "user", body.get("parts", []))
        self.store.set_session_status(sid, "busy")

        # Collect streamed text into a single assistant message
        chunks: list[str] = []
        async for chunk in self.backend.complete_stream(sid, text):
            chunks.append(chunk)

        full = "".join(chunks)
        msg = self.store.add_message(
            sid, "assistant", [{"type": "text", "text": full}]
        )
        self.store.set_session_status(sid, "idle")
        return web.json_response(msg.to_dict())

    async def _abort_session(self, request: web.Request) -> web.Response:
        sid = request.match_info["id"]
        self.store.set_session_status(sid, "idle")
        return web.json_response({"aborted": True})

    async def _list_agents(self, request: web.Request) -> web.Response:
        return web.json_response(self.store.list_agents())

    async def _get_config(self, request: web.Request) -> web.Response:
        return web.json_response(self.store.get_config())

    async def _patch_config(self, request: web.Request) -> web.Response:
        body = await request.json() if request.can_read_body else {}
        return web.json_response(self.store.patch_config(body))

    async def _permission_reply(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def _event_stream(self, request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse()
        response.headers["Content-Type"] = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        await response.prepare(request)

        queue = await self.broadcaster.subscribe()
        try:
            while True:
                payload = await asyncio.wait_for(queue.get(), timeout=2.0)
                event_line = f"data: {payload}\n\n"
                await response.write(event_line.encode("utf-8"))
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            pass
        finally:
            await self.broadcaster.unsubscribe(queue)
        return response

    # ── Background generation ─────────────────────────────────────

    async def _generate(
        self, session_id: str, prompt: str, body: Dict[str, Any]
    ) -> None:
        """Stream LLM output as SSE events, then emit step-finish + session.idle."""
        try:
            # step-start
            await self.broadcaster.broadcast({
                "type": "message.part.updated",
                "properties": {
                    "part": {"type": "step-start"},
                    "sessionID": session_id,
                },
            })

            full_text = ""
            async for chunk in self.backend.complete_stream(session_id, prompt):
                full_text += chunk
                await self.broadcaster.broadcast({
                    "type": "message.part.delta",
                    "properties": {
                        "delta": chunk,
                        "field": "text",
                        "sessionID": session_id,
                    },
                })

            # Persist assistant message
            self.store.add_message(
                session_id,
                "assistant",
                [{"type": "text", "text": full_text}],
            )

            # step-finish
            await self.broadcaster.broadcast({
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "type": "step-finish",
                        "reason": "stop",
                        "cost": 0.0,
                        "tokens": {"input": 0, "output": 0},
                    },
                    "sessionID": session_id,
                },
            })

            # session.idle
            await self.broadcaster.broadcast({
                "type": "session.idle",
                "sessionID": session_id,
            })

            self.store.set_session_status(session_id, "idle")
        except Exception as exc:
            logger.exception("[%s] generation failed: %s", session_id, exc)
            self.store.set_session_status(session_id, "idle")
            await self.broadcaster.broadcast({
                "type": "session.idle",
                "sessionID": session_id,
            })

    # ── Application factory ───────────────────────────────────────

    def get_app(self) -> web.Application:
        return self._app


def create_app(backend: Optional[LLMBackend] = None) -> web.Application:
    return OpencodeServerApp(backend=backend).get_app()
