import json
import os
from typing import Any

_PIPELINES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "pipelines.json"
)
_cache: list[dict] | None = None


def load_pipelines() -> list[dict]:
    global _cache
    if _cache is None:
        with open(_PIPELINES_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def get_pipeline(pipeline_id: str) -> dict | None:
    return next((p for p in load_pipelines() if p["id"] == pipeline_id), None)


def resolve_template(text: str, params: dict[str, Any]) -> str:
    for k, v in params.items():
        text = text.replace(f"{{{k}}}", str(v))
    return text
