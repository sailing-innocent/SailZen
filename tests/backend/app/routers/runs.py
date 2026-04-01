from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import attributes

from app.database import get_db
from app.models.db_models import PipelineRun, NodeRun
from app.models.schemas import PipelineRunOut, RunRequest
from app.services.executor import start_pipeline_run, cancel_pipeline_run

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=PipelineRunOut)
async def create_run(body: RunRequest, db: AsyncSession = Depends(get_db)):
    try:
        run = await start_pipeline_run(db, body.pipeline_id, body.params)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run.id))
    run = result.scalar_one()
    node_result = await db.execute(
        select(NodeRun).where(NodeRun.pipeline_run_id == run.id)
    )
    node_runs = list(node_result.scalars().all())
    attributes.set_committed_value(run, "node_runs", node_runs)
    return PipelineRunOut.model_validate(run)


@router.get("", response_model=list[PipelineRunOut])
async def list_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PipelineRun).order_by(PipelineRun.created_at.desc())
    )
    runs = result.scalars().all()
    out = []
    for run in runs:
        nr = await db.execute(select(NodeRun).where(NodeRun.pipeline_run_id == run.id))
        attributes.set_committed_value(run, "node_runs", list(nr.scalars().all()))
        out.append(PipelineRunOut.model_validate(run))
    return out


@router.get("/{run_id}", response_model=PipelineRunOut)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    nr = await db.execute(select(NodeRun).where(NodeRun.pipeline_run_id == run_id))
    attributes.set_committed_value(run, "node_runs", list(nr.scalars().all()))
    return PipelineRunOut.model_validate(run)


@router.delete("/{run_id}")
async def cancel_run(run_id: int):
    cancel_pipeline_run(run_id)
    return {"detail": "cancellation requested"}
