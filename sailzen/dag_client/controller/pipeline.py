"""Pipeline Controller — /pipeline 端点 + SSE。"""

from __future__ import annotations

import asyncio
import json
from typing import List

from litestar import Controller, get, post, delete, Request
from litestar.response import Response, Stream

from bot_server.deps import get_bus, get_db, get_event_bus
from bot_server.service.converter import batch_to_pipeline_run
from sail.dag.command_bus import Command, Source, Role


def _dash_cmd(name: str, **args) -> Command:
    return Command(name=name, args=args, source=Source.DASHBOARD,
                   actor="dashboard", role=Role.ADMIN)


@get("/pipeline/definition")
async def get_pipeline_definitions() -> List[dict]:
    result = await get_bus().dispatch(_dash_cmd("pipeline_definitions"))
    return result.data or []


@get("/pipeline/run")
async def list_pipeline_runs() -> List[dict]:
    result = await get_bus().dispatch(_dash_cmd("list_pipeline_runs"))
    return result.data or []


@get("/pipeline/run/{run_id:str}")
async def get_pipeline_run(run_id: str) -> Response:
    result = await get_bus().dispatch(_dash_cmd("get_pipeline_run", run_id=run_id))
    if result.success:
        return Response(result.data)
    return Response({"error": result.error}, status_code=404)


@post("/pipeline/run")
async def start_pipeline_run(data: dict) -> Response:
    result = await get_bus().dispatch(_dash_cmd("start_pipeline_run", **data))
    if result.success:
        return Response(result.data, status_code=201)
    return Response({"error": result.error, "text": result.text}, status_code=400)


@post("/pipeline/run/{run_id:str}/resume-from/{node_id:str}")
async def resume_pipeline_from_node(run_id: str, node_id: str) -> Response:
    result = await get_bus().dispatch(
        _dash_cmd("resume_pipeline_from_node", run_id=run_id, node_id=node_id))
    if result.success:
        return Response(result.data, status_code=200)
    return Response({"error": result.error, "text": result.text}, status_code=400)


@post("/pipeline/run/{run_id:str}/block-node/{node_id:str}")
async def manual_block_node(run_id: str, node_id: str, data: dict | None = None) -> Response:
    result = await get_bus().dispatch(
        _dash_cmd("manual_block_node", run_id=run_id, node_id=node_id, **(data or {})))
    if result.success:
        return Response(result.data, status_code=200)
    return Response({"error": result.error, "text": result.text}, status_code=400)


@post("/pipeline/run/{run_id:str}/success-node/{node_id:str}")
async def manual_success_node(run_id: str, node_id: str, data: dict | None = None) -> Response:
    result = await get_bus().dispatch(
        _dash_cmd("manual_success_node", run_id=run_id, node_id=node_id, **(data or {})))
    if result.success:
        return Response(result.data, status_code=200)
    return Response({"error": result.error, "text": result.text}, status_code=400)


@delete("/pipeline/run/{run_id:str}", status_code=200)
async def cancel_pipeline_run(run_id: str) -> Response:
    result = await get_bus().dispatch(
        _dash_cmd("cancel_pipeline_run", run_id=run_id))
    return Response({"ok": result.success})


class PipelineSSEController(Controller):
    """Pipeline SSE 事件流 Controller。"""
    path = "/pipeline/sse"

    @get("/run/{run_id:str}")
    async def stream_run(self, run_id: str, request: Request) -> Stream:
        """SSE 事件流，通过 EventBus 订阅实时推送 PipelineRun 状态。"""

        async def event_generator():
            eb = get_event_bus()
            queue = eb.subscribe(run_id)

            try:
                # 立即发送当前状态
                batch = await get_db().get_batch(run_id)
                if batch:
                    run_data = await batch_to_pipeline_run(batch)
                    yield f"data: {json.dumps(run_data, default=str)}\n\n"

                while True:
                    if not request.is_connected:
                        break
                    try:
                        _event = await asyncio.wait_for(queue.get(), timeout=5.0)
                        # 收到事件后，发送最新的完整 PipelineRun 状态
                        batch = await get_db().get_batch(run_id)
                        if batch:
                            run_data = await batch_to_pipeline_run(batch)
                            yield f"data: {json.dumps(run_data, default=str)}\n\n"
                            if batch["status"] in ("completed", "failed", "blocked"):
                                break
                    except asyncio.TimeoutError:
                        yield ": heartbeat\n\n"
            finally:
                eb.unsubscribe(run_id, queue)

        return Stream(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
