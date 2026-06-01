# -*- coding: utf-8 -*-
# @file app.py
# @brief Litestar HTTP 应用
# @author sailing-innocent
# @date 2025-06-02
# @version 3.0
# ---------------------------------
"""SailZen DAG Client 独立 Litestar HTTP 应用。

职责:
  - App lifecycle (on_startup / on_shutdown)
  - create_app() 工厂
  - 独立运行，不依赖 sail_server
"""

from __future__ import annotations

import logging
import os

from litestar import Litestar, Router, get
from litestar.config.cors import CORSConfig
from litestar.response import Response

from sailzen.dag_client.config import load_config, DAGClientConfig
from sailzen.dag_client.database import Database
from sailzen.dag_client.repositories import DatabaseCompat
from sailzen.dag_client.scheduler import DAGScheduler
from sailzen.dag_client.executor import DAGExecutor
from sailzen.dag_client.events import EventBus
from sailzen.dag_client.store import DAGStore
from sailzen.dag_client.opencode_bridge import OpenCodeBridge
from sailzen.dag_client.nodes.registry import NodeRegistry
from sailzen.dag_client.api import create_api_router, create_sse_router

from sailzen.dag_client import deps
from sailzen.dag_client.models import make_event_log

logger = logging.getLogger(__name__)


# ── DB Event Logger ─────────────────────────────────────────────────

async def _db_event_logger(event: dict) -> None:
    db = deps.get_db()
    log_entry = make_event_log(
        event_type=event.get("type", "unknown"),
        entity_type=event.get("entity_type", "system"),
        entity_id=event.get("entity_id", ""),
        new_state=event.get("data"),
        actor=event.get("actor", "system"),
    )
    await db.log_event(log_entry)


# ── App lifecycle ───────────────────────────────────────────────────

async def on_startup() -> None:
    # 加载配置
    cfg = load_config()
    logger.info("DAG Client config loaded: name=%s db=%s", cfg.name, cfg.db_path)

    # 初始化 Store
    store = DAGStore(cfg.data_dir)
    deps.set_store(store)

    # 初始化 Database
    raw_db = Database(cfg.db_path)
    await raw_db.connect()
    db = DatabaseCompat(raw_db)
    deps.set_db(db)

    # 初始化 EventBus
    event_bus = EventBus()
    event_bus.set_db_logger(_db_event_logger)
    deps.set_event_bus(event_bus)

    # 初始化 Scheduler
    scheduler = DAGScheduler(db)
    deps.set_scheduler(scheduler)

    # 初始化 OpenCode Bridge
    bridge = OpenCodeBridge(
        host=cfg.opencode.host,
        port=cfg.opencode.port,
        timeout=cfg.opencode.timeout,
    )
    deps.set_bridge(bridge)

    # 初始化 NodeRegistry
    node_registry = NodeRegistry()
    node_registry.load_from_config(cfg.node_types)

    # 初始化 Executor
    opencode_client = bridge.client if bridge else None
    executor = DAGExecutor(
        db_compat=db,
        scheduler=scheduler,
        event_bus=event_bus,
        node_registry=node_registry,
        store=store,
        opencode_client=opencode_client,
    )
    deps.set_executor(executor)

    # 注册必需 skills
    for skill_name in cfg.required_skills:
        await db.upsert_required_skill({
            "skill_name": skill_name,
            "node_type": "*",
            "status": "pending",
        })

    # 预注册 pipelines 为 definitions
    for pipeline in cfg.pipelines:
        template = {
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type,
                    "name": n.name,
                    "depends_on": n.depends_on,
                    "params": n.params,
                    "priority": 100,
                    "timeout": n.timeout or 3600,
                    "retries": n.retries,
                }
                for n in pipeline.nodes
            ],
            "edges": [],
        }
        from sailzen.dag_client.models import make_dag_definition
        d = make_dag_definition(
            name=pipeline.name or pipeline.id,
            template=template,
            description=pipeline.description,
        )
        d["id"] = pipeline.id  # 使用配置中的 ID
        await db.upsert_definition(d)

    # 启动执行器
    if cfg.auto_start:
        await executor.start()

    logger.info(
        "SailZen DAG Client started (node_types=%d, pipelines=%d)",
        len(node_registry.list_types()),
        len(cfg.pipelines),
    )


async def on_shutdown() -> None:
    cancelled = await deps.cancel_background_tasks()
    if cancelled:
        logger.info("Cancelled %d background task(s)", cancelled)

    executor = deps.get_executor()
    if executor:
        await executor.stop()

    bridge = deps.get_bridge()
    if bridge:
        await bridge.close()

    db = deps.get_db()
    if db:
        await db.close()

    logger.info("SailZen DAG Client stopped")


# ── Create App ──────────────────────────────────────────────────────

@get("/", include_in_schema=False)
async def index() -> Response:
    return Response({
        "service": "SailZen DAG Client",
        "version": "3.0",
        "endpoints": {
            "api": "/api/v1/dag",
            "sse": "/dag/sse",
            "health": "/api/v1/dag/health",
        },
    })


def create_app() -> Litestar:
    api_router = create_api_router()
    sse_router = create_sse_router()

    base_router = Router(
        path="/",
        route_handlers=[index],
    )

    return Litestar(
        route_handlers=[base_router, api_router, sse_router],
        on_startup=[on_startup],
        on_shutdown=[on_shutdown],
        cors_config=CORSConfig(
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        debug=os.environ.get("DAG_DEBUG", "0") == "1",
    )


app = create_app()
