# -*- coding: utf-8 -*-
# @file sse.py
# @brief SSE 路由
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""SailZen DAG Client SSE API。

端点::

  GET /dag/sse/runs/{run_id}      订阅单个运行的实时事件
  GET /dag/sse/global             订阅全局事件
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from litestar import Router, get, Request
from litestar.response import Stream

from sailzen.dag_client.deps import get_event_bus, get_db
from sailzen.dag_client.models import RunStatus

logger = logging.getLogger(__name__)


async def _run_event_generator(run_id: str, request: Request) -> AsyncIterator[str]:
    """为指定 run 生成 SSE 事件流。"""
    eb = get_event_bus()
    db = get_db()
    queue = eb.subscribe(run_id)

    try:
        # 立即发送当前状态
        run = await db.get_run(run_id)
        if run:
            yield f"data: {json.dumps({'type': 'run.state', 'data': run}, default=str)}\n\n"

        while True:
            if not request.is_connected:
                break
            try:
                event_text = await asyncio.wait_for(queue.get(), timeout=5.0)
                yield f"data: {event_text}\n\n"
                # 检查运行是否已结束
                run = await db.get_run(run_id)
                if run and run["status"] in {
                    RunStatus.COMPLETED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value,
                }:
                    # 再发送一次最终状态后关闭
                    yield f"data: {json.dumps({'type': 'run.final', 'data': run}, default=str)}\n\n"
                    break
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
    finally:
        eb.unsubscribe(run_id, queue)


async def _global_event_generator(request: Request) -> AsyncIterator[str]:
    """生成全局 SSE 事件流。"""
    eb = get_event_bus()
    queue = eb.subscribe_global()

    try:
        while True:
            if not request.is_connected:
                break
            try:
                event_text = await asyncio.wait_for(queue.get(), timeout=5.0)
                yield f"data: {event_text}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
    finally:
        eb.unsubscribe_global(queue)


@get("/runs/{run_id:str}")
async def stream_run(run_id: str, request: Request) -> Stream:
    return Stream(
        _run_event_generator(run_id, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@get("/global")
async def stream_global(request: Request) -> Stream:
    return Stream(
        _global_event_generator(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def create_sse_router() -> Router:
    return Router(
        path="/dag/sse",
        route_handlers=[stream_run, stream_global],
    )
