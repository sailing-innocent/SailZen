from fastapi import APIRouter
from app.services.pipeline_loader import load_pipelines, get_pipeline
from app.models.schemas import PipelineInfo

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.get("", response_model=list[PipelineInfo])
async def list_pipelines():
    return [
        PipelineInfo(
            id=p["id"],
            name=p["name"],
            description=p["description"],
            params=p.get("params", []),
        )
        for p in load_pipelines()
    ]


@router.get("/{pipeline_id}")
async def get_pipeline_detail(pipeline_id: str):
    p = get_pipeline(pipeline_id)
    if not p:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Pipeline not found")
    return p
