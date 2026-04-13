# -*- coding: utf-8 -*-
# @file dag_pipeline_loader.py
# @brief DAG Pipeline Definition Loader
# @author sailing-innocent
# @date 2026-04-13
# @version 1.0
# ---------------------------------

import json
import os
from typing import Any

from sail_server.config.paths import PIPELINES_DIR

_cache: list[dict] | None = None


def load_pipelines() -> list[dict]:
    global _cache
    if _cache is None:
        _cache = []
        pipelines_dir = str(PIPELINES_DIR)
        if os.path.isdir(pipelines_dir):
            for filename in sorted(os.listdir(pipelines_dir)):
                if filename.endswith(".json"):
                    filepath = os.path.join(pipelines_dir, filename)
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            _cache.extend(data)
                        else:
                            _cache.append(data)
    return _cache


def reload_pipelines() -> list[dict]:
    global _cache
    _cache = None
    return load_pipelines()


def get_pipeline(pipeline_id: str) -> dict | None:
    return next((p for p in load_pipelines() if p["id"] == pipeline_id), None)


def resolve_template(text: str, params: dict[str, Any]) -> str:
    for k, v in params.items():
        text = text.replace(f"{{{k}}}", str(v))
    return text
