import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import attributes

from app.database import AsyncSessionLocal
from app.models.db_models import PipelineRun, NodeRun
from app.models.schemas import PipelineRunOut

router = APIRouter(prefix="/sse", tags=["sse"])


async def _event_generator(run_id: int, request: Request):
    while True:
        if await request.is_disconnected():
            break
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PipelineRun).where(PipelineRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if not run:
                break
            nr = await db.execute(
                select(NodeRun).where(NodeRun.pipeline_run_id == run_id)
            )
            attributes.set_committed_value(run, "node_runs", list(nr.scalars().all()))
            data = PipelineRunOut.model_validate(run).model_dump(mode="json")
            yield f"data: {json.dumps(data)}\n\n"
            if run.status in ("success", "failed"):
                break
        await asyncio.sleep(1)


@router.get("/runs/{run_id}")
async def stream_run(run_id: int, request: Request):
    return StreamingResponse(
        _event_generator(run_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
