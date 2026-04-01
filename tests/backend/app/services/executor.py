import asyncio
import random
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.db_models import NodeRun, PipelineRun, RunStatus
from app.services.pipeline_loader import get_pipeline, resolve_template


_active_tasks: dict[int, asyncio.Task] = {}


async def _db_update_node(run_id: int, node_id: str, **kwargs):
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(NodeRun).where(
                NodeRun.pipeline_run_id == run_id,
                NodeRun.node_id == node_id,
            )
        )
        node = result.scalar_one_or_none()
        if node:
            for k, v in kwargs.items():
                setattr(node, k, v)
            await db.commit()


async def _db_update_pipeline(run_id: int, **kwargs):
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            for k, v in kwargs.items():
                setattr(run, k, v)
            await db.commit()


async def _db_add_nodes(run_id: int, nodes: list[dict], params: dict):
    async with AsyncSessionLocal() as db:
        for nd in nodes:
            name = resolve_template(nd["name"], params)
            existing = await db.execute(
                __import__("sqlalchemy", fromlist=["select"])
                .select(NodeRun)
                .where(
                    NodeRun.pipeline_run_id == run_id,
                    NodeRun.node_id == nd["id"],
                )
            )
            if existing.scalar_one_or_none():
                continue
            node_run = NodeRun(
                pipeline_run_id=run_id,
                node_id=nd["id"],
                node_name=name,
                node_type=nd["type"],
                description=nd.get("description", ""),
                depends_on=nd.get("depends_on", []),
                status=RunStatus.pending,
                logs=[],
                is_dynamic=True,
                can_spawn=bool(nd.get("dynamic_spawn")),
            )
            db.add(node_run)
        await db.commit()


async def _db_get_node_status(run_id: int, node_id: str) -> RunStatus | None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(NodeRun).where(
                NodeRun.pipeline_run_id == run_id,
                NodeRun.node_id == node_id,
            )
        )
        node = result.scalar_one_or_none()
        return node.status if node else None


async def _db_all_nodes(run_id: int) -> list[NodeRun]:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(NodeRun).where(NodeRun.pipeline_run_id == run_id)
        )
        return list(result.scalars().all())


async def _execute_node(run_id: int, node_def: dict, params: dict):
    node_id = node_def["id"]
    duration = node_def.get("mock_duration", 3)
    fail_rate = node_def.get("mock_fail_rate", 0.0)

    await _db_update_node(
        run_id, node_id, status=RunStatus.running, started_at=datetime.utcnow()
    )

    await asyncio.sleep(duration)

    failed = random.random() < fail_rate
    now = datetime.utcnow()

    raw_logs = node_def.get("logs", [])
    resolved_logs = [resolve_template(lg, params) for lg in raw_logs]

    if failed:
        await _db_update_node(
            run_id,
            node_id,
            status=RunStatus.failed,
            finished_at=now,
            duration=float(duration),
            logs=resolved_logs + ["[ERROR] Step failed unexpectedly"],
        )
        return False

    await _db_update_node(
        run_id,
        node_id,
        status=RunStatus.success,
        finished_at=now,
        duration=float(duration),
        logs=resolved_logs,
    )
    return True


async def _run_pipeline(run_id: int, pipeline_def: dict, params: dict):
    await _db_update_pipeline(
        run_id, status=RunStatus.running, started_at=datetime.utcnow()
    )

    all_node_defs: dict[str, dict] = {nd["id"]: nd for nd in pipeline_def["nodes"]}
    completed: set[str] = set()
    failed: set[str] = set()
    in_flight: dict[str, asyncio.Task] = {}

    def _pending_node_ids() -> list[str]:
        nodes = []
        for nid, nd in all_node_defs.items():
            if nid in completed or nid in failed or nid in in_flight:
                continue
            deps = nd.get("depends_on", [])
            if any(d in failed for d in deps):
                continue
            if all(d in completed for d in deps):
                nodes.append(nid)
        return nodes

    while True:
        ready = _pending_node_ids()
        for nid in ready:
            nd = all_node_defs[nid]
            task = asyncio.create_task(_execute_node(run_id, nd, params))
            in_flight[nid] = task

        if not in_flight:
            break

        done, _ = await asyncio.wait(
            in_flight.values(), return_when=asyncio.FIRST_COMPLETED
        )

        for task in done:
            nid = next(k for k, v in in_flight.items() if v is task)
            in_flight.pop(nid)
            success = task.result()
            if success:
                completed.add(nid)
                nd = all_node_defs[nid]
                spawn_cfg = nd.get("dynamic_spawn")
                if spawn_cfg and spawn_cfg.get("trigger_on") == "success":
                    spawn_nodes = spawn_cfg.get("spawn_nodes", [])
                    await _db_add_nodes(run_id, spawn_nodes, params)
                    for snd in spawn_nodes:
                        all_node_defs[snd["id"]] = snd
            else:
                failed.add(nid)
                for other_nid, other_nd in list(all_node_defs.items()):
                    if other_nid in completed or other_nid in failed:
                        continue
                    if _transitively_depends(other_nid, nid, all_node_defs):
                        failed.add(other_nid)
                        await _db_update_node(
                            run_id, other_nid, status=RunStatus.skipped
                        )

    overall = RunStatus.success if not failed else RunStatus.failed
    await _db_update_pipeline(run_id, status=overall, finished_at=datetime.utcnow())
    _active_tasks.pop(run_id, None)


def _transitively_depends(node_id: str, target_id: str, all_defs: dict) -> bool:
    visited = set()
    queue = list(all_defs.get(node_id, {}).get("depends_on", []))
    while queue:
        dep = queue.pop()
        if dep == target_id:
            return True
        if dep not in visited:
            visited.add(dep)
            queue.extend(all_defs.get(dep, {}).get("depends_on", []))
    return False


async def start_pipeline_run(
    db: AsyncSession, pipeline_id: str, params: dict
) -> PipelineRun:
    pipeline_def = get_pipeline(pipeline_id)
    if not pipeline_def:
        raise ValueError(f"Pipeline '{pipeline_id}' not found")

    resolved_name = resolve_template(pipeline_def["name"], params)

    run = PipelineRun(
        pipeline_id=pipeline_id,
        pipeline_name=resolved_name,
        params=params,
        status=RunStatus.pending,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    for nd in pipeline_def["nodes"]:
        name = resolve_template(nd["name"], params)
        node_run = NodeRun(
            pipeline_run_id=run.id,
            node_id=nd["id"],
            node_name=name,
            node_type=nd["type"],
            description=nd.get("description", ""),
            depends_on=nd.get("depends_on", []),
            status=RunStatus.pending,
            logs=[],
            is_dynamic=False,
            can_spawn=bool(nd.get("dynamic_spawn")),
        )
        db.add(node_run)
    await db.commit()
    await db.refresh(run)

    task = asyncio.create_task(_run_pipeline(run.id, pipeline_def, params))
    _active_tasks[run.id] = task

    return run


def cancel_pipeline_run(run_id: int):
    task = _active_tasks.get(run_id)
    if task:
        task.cancel()
        _active_tasks.pop(run_id, None)
