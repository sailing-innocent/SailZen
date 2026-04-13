# -*- coding: utf-8 -*-
# @file dag_pipeline.py
# @brief DAG Pipeline Litestar Controller
# @author sailing-innocent
# @date 2026-04-13
# @version 1.0
# ---------------------------------

from __future__ import annotations

import asyncio
import json
import logging

from litestar import Controller, delete, get, post, Request
from litestar.response import Stream
from litestar.exceptions import NotFoundException
from sqlalchemy.orm import Session
from typing import Generator

from sail_server.application.dto.dag_pipeline import (
    PipelineInfo,
    PipelineRunOut,
    NodeRunOut,
    RunRequest,
)
from sail_server.infrastructure.orm.dag_pipeline import PipelineRun, NodeRun
from sail_server.service.dag_pipeline_loader import load_pipelines, get_pipeline
from sail_server.service.dag_executor import start_pipeline_run, cancel_pipeline_run

logger = logging.getLogger(__name__)


def _build_run_out(run: PipelineRun) -> PipelineRunOut:
    node_outs = [NodeRunOut.model_validate(nr) for nr in run.node_runs]
    run_dict = {
        "id": run.id,
        "pipeline_id": run.pipeline_id,
        "pipeline_name": run.pipeline_name,
        "params": run.params or {},
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "node_runs": node_outs,
    }
    return PipelineRunOut(**run_dict)


class PipelineDefController(Controller):
    path = "/definition"

    @get("")
    async def list_pipelines(self) -> list[PipelineInfo]:
        pipelines = load_pipelines()
        return [
            PipelineInfo(
                id=p["id"],
                name=p["name"],
                description=p["description"],
                params=p.get("params", []),
            )
            for p in pipelines
        ]

    @get("/{pipeline_id:str}")
    async def get_pipeline_detail(self, pipeline_id: str) -> dict:
        p = get_pipeline(pipeline_id)
        if not p:
            raise NotFoundException(detail=f"Pipeline '{pipeline_id}' not found")
        return p


class PipelineRunController(Controller):
    path = "/run"

    @post("")
    async def create_run(
        self,
        data: RunRequest,
        router_dependency: Generator[Session, None, None],
    ) -> PipelineRunOut:
        db = next(router_dependency)
        try:
            run = start_pipeline_run(db, data.pipeline_id, data.params)
        except ValueError as e:
            raise NotFoundException(detail=str(e))
        return _build_run_out(run)

    @get("")
    async def list_runs(
        self,
        router_dependency: Generator[Session, None, None],
    ) -> list[PipelineRunOut]:
        db = next(router_dependency)
        runs = db.query(PipelineRun).order_by(PipelineRun.created_at.desc()).all()
        return [_build_run_out(r) for r in runs]

    @get("/{run_id:int}")
    async def get_run(
        self,
        run_id: int,
        router_dependency: Generator[Session, None, None],
    ) -> PipelineRunOut:
        db = next(router_dependency)
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            raise NotFoundException(detail=f"Run {run_id} not found")
        return _build_run_out(run)

    @delete("/{run_id:int}", status_code=200)
    async def cancel_run(self, run_id: int) -> dict:
        cancel_pipeline_run(run_id)
        return {"detail": "cancellation requested"}


class PipelineSSEController(Controller):
    path = "/sse"

    @get("/run/{run_id:int}")
    async def stream_run(self, run_id: int, request: Request) -> Stream:
        async def event_generator():
            from sail_server.db import get_db_session

            while True:
                if not request.is_connected:
                    break
                with get_db_session() as db:
                    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
                    if not run:
                        break
                    data = _build_run_out(run)
                    payload = data.model_dump(mode="json")
                    yield f"data: {json.dumps(payload)}\n\n"
                    status_str = (
                        run.status.value
                        if hasattr(run.status, "value")
                        else str(run.status)
                    )
                    if status_str in ("success", "failed"):
                        break
                await asyncio.sleep(1)

        return Stream(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
