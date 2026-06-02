# -*- coding: utf-8 -*-
# @file text_fetch_node.py
# @brief SailServer Text 数据获取节点
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""从 sail_server 的 /api/v1/text 端点获取网文数据的节点。

数据隔离原则:
  - 只读 sail_server，绝不写入
  - 所有获取的数据存入 DAGStore，与 sail_server 完全隔离

参数::

    {
        "sail_server_url": "http://localhost:8000",   # sail_server 地址
        "endpoint": "chapters",                        # 端点类型
        "edition_id": 1,                              # 版本 ID
        "work_id": 1,                                 # 作品 ID（可选）
        "chapter_index": 0,                           # 章节索引（可选）
        "keyword": "",                                # 搜索关键词（可选）
    }

endpoint 类型:
  - "work_meta"     -> GET /api/v1/text/work/{work_id}
  - "edition"       -> GET /api/v1/text/edition/{edition_id}
  - "chapters"      -> GET /api/v1/text/edition/{edition_id}/chapters
  - "chapter"       -> GET /api/v1/text/edition/{edition_id}/chapter/{chapter_index}
  - "chapter_count" -> GET /api/v1/text/edition/{edition_id}/chapters/count
  - "search"        -> GET /api/v1/text/edition/{edition_id}/search?keyword={keyword}
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


class TextFetchNode(NodeExecutor):
    """从 sail_server 获取 text 数据的节点。"""

    node_type = "text_fetch"

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        if not params.get("sail_server_url"):
            return "Missing required param: sail_server_url"
        if not params.get("endpoint"):
            return "Missing required param: endpoint"
        endpoint = params["endpoint"]
        if endpoint in ("chapters", "chapter", "chapter_count", "search"):
            if not params.get("edition_id"):
                return f"Missing required param: edition_id for endpoint '{endpoint}'"
        if endpoint in ("work_meta",):
            if not params.get("work_id"):
                return f"Missing required param: work_id for endpoint '{endpoint}'"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        url = ctx.params.get("sail_server_url", "http://localhost:8000").rstrip("/")
        endpoint = ctx.params["endpoint"]
        edition_id = ctx.params.get("edition_id")
        work_id = ctx.params.get("work_id")
        chapter_index = ctx.params.get("chapter_index", 0)
        keyword = ctx.params.get("keyword", "")

        target_url = self._build_url(url, endpoint, work_id, edition_id, chapter_index, keyword)
        logger.info("TextFetchNode %s: GET %s", ctx.node_id, target_url)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(target_url)
                resp.raise_for_status()
                data = resp.json()

            # 保存产物
            artifact_name = f"{ctx.node_id}_result.json"
            artifact_path = None
            if ctx.store:
                artifact_path = ctx.store.save_artifact(
                    ctx.run_id, artifact_name, json.dumps(data, ensure_ascii=False, indent=2)
                )

            return NodeResult.ok(
                data=data,
                output=f"Fetched {endpoint}: {len(json.dumps(data))} bytes",
                artifacts=[str(artifact_path)] if artifact_path else [],
            )

        except httpx.HTTPStatusError as exc:
            return NodeResult.fail(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            logger.exception("TextFetchNode execute error")
            return NodeResult.fail(str(exc))

    def _build_url(
        self,
        base_url: str,
        endpoint: str,
        work_id: Optional[int],
        edition_id: Optional[int],
        chapter_index: int,
        keyword: str,
    ) -> str:
        if endpoint == "work_meta":
            return f"{base_url}/api/v1/text/work/{work_id}"
        if endpoint == "edition":
            return f"{base_url}/api/v1/text/edition/{edition_id}"
        if endpoint == "chapters":
            return f"{base_url}/api/v1/text/edition/{edition_id}/chapters"
        if endpoint == "chapter":
            return f"{base_url}/api/v1/text/edition/{edition_id}/chapter/{chapter_index}"
        if endpoint == "chapter_count":
            return f"{base_url}/api/v1/text/edition/{edition_id}/chapters/count"
        if endpoint == "search":
            return f"{base_url}/api/v1/text/edition/{edition_id}/search?keyword={keyword}&limit=200"
        raise ValueError(f"Unknown endpoint: {endpoint}")
