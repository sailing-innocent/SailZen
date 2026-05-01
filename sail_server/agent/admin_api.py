# -*- coding: utf-8 -*-
# @file admin_api.py
# @brief Agent Admin HTTP API (Litestar sub-app)
# @author sailing-innocent
# @date 2026-08-24
# @version 1.0
# ---------------------------------

import asyncio
import logging
from typing import TYPE_CHECKING

from litestar import Litestar, get, post, Controller
from litestar.config.cors import CORSConfig

if TYPE_CHECKING:
    from sail_server.agent.daemon import AgentDaemon

logger = logging.getLogger(__name__)


class AgentAdminController(Controller):
    path = "/"

    def __init__(self, daemon: "AgentDaemon"):
        self.daemon = daemon

    @get("/health")
    async def health(self) -> dict:
        return {"status": "ok", "agent": self.daemon.config.name}

    @get("/jobs")
    async def list_jobs(self) -> list[dict]:
        from sail_server.db import get_db_session
        from sail_server.infrastructure.orm.agent import AgentJob

        with get_db_session() as db:
            jobs = db.query(AgentJob).order_by(AgentJob.ctime.desc()).limit(50).all()
            return [
                {
                    "id": j.id,
                    "type": j.job_type,
                    "status": j.status,
                    "params": j.params,
                    "created_by": j.created_by,
                    "ctime": j.ctime.isoformat() if j.ctime else None,
                }
                for j in jobs
            ]

    @post("/jobs/{job_id:int}/approve")
    async def approve_job(self, job_id: int) -> dict:
        from sail_server.db import get_db_session
        from sail_server.infrastructure.orm.agent import AgentJob, JobStatus

        with get_db_session() as db:
            job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
            if not job:
                return {"error": "Job not found"}
            job.status = JobStatus.pending.value
            job.auto_approved = True
            db.commit()
            return {"id": job_id, "status": "approved"}

    @post("/trigger/{job_id:str}")
    async def trigger_job(self, job_id: str) -> dict:
        await self.daemon.scheduler.trigger_now(job_id)
        return {"triggered": job_id}


class AgentAdminAPI:
    def __init__(self, daemon: "AgentDaemon"):
        self.daemon = daemon
        self.app: Litestar = None
        self.server = None

    async def start(self, host: str, port: int):
        from uvicorn import Config, Server

        self.app = Litestar(
            route_handlers=[AgentAdminController(self.daemon)],
            cors_config=CORSConfig(allow_origins=["*"]),
            debug=True,
        )
        config = Config(self.app, host=host, port=port, log_level="warning")
        self.server = Server(config)
        logger.info(f"[AdminAPI] Starting on {host}:{port}")

        # Run in background
        self._task = asyncio.create_task(self.server.serve())

    async def stop(self):
        if self.server:
            self.server.should_exit = True
            await self._task
