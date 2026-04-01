from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import init_db
from app.routers import pipelines, runs, sse, agents
from app.services.agent_manager import agent_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await agent_manager.start()
    yield
    await agent_manager.stop()


app = FastAPI(title="CubeClaw Multi-Agent System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 原有的Pipeline路由
app.include_router(pipelines.router)
app.include_router(runs.router)
app.include_router(sse.router)

# 新增的Agent路由
app.include_router(agents.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "cubeclaw"}
