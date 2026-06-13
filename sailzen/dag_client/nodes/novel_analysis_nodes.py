# -*- coding: utf-8 -*-
# @file novel_analysis_nodes.py
# @brief 网文拆解分析专用节点
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""网文拆解分析专用节点集合。

包含:
  - BatchSplitNode: 按 batch_size 将章节分组成批次
  - BatchMergeNode: 合并各批次的分析结果
  - ReportNode: 生成最终综合报告
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


class BatchSplitNode(NodeExecutor):
    """将章节列表按 batch_size 分组，并动态生成分支节点。

    参数::

        {
            "batch_size": 100,          # 每批章节数
            "overlap": 0,               # 批次间重叠章节数
            "strategy": "by_count",     # 分组策略: by_count / by_char_count
            "max_char_per_batch": 50000 # strategy=by_char_count 时的字符上限
        }

    上游依赖:
      - chapter_index: 章节列表数据 (from fetch_chapter_index text_fetch 节点)

    输出:
      - data.batch_count: 总批次数
      - data.batches: [{start_index, end_index, chapter_count}, ...]
      - next_nodes: 动态生成 batch_fetch_N 节点
    """

    node_type = "batch_split"

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        if params.get("batch_size", 0) <= 0 and params.get("max_char_per_batch", 0) <= 0:
            return "Missing valid batch_size or max_char_per_batch"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        batch_size = ctx.params.get("batch_size", 100)
        overlap = ctx.params.get("overlap", 0)
        strategy = ctx.params.get("strategy", "by_count")
        max_char = ctx.params.get("max_char_per_batch", 50000)

        # 从上游获取章节列表
        chapter_index = ctx.upstream_results.get("fetch_chapter_index", {})
        if not chapter_index:
            return NodeResult.fail("Missing upstream chapter_index from fetch_chapter_index")

        chapters = chapter_index.get("data", chapter_index)
        if isinstance(chapters, dict):
            chapters = chapters.get("chapters", chapters.get("data", []))

        if not chapters:
            return NodeResult.fail("Empty chapter list")

        # 分组
        batches = []
        if strategy == "by_char_count":
            current_batch = []
            current_chars = 0
            for i, ch in enumerate(chapters):
                ch_chars = ch.get("char_count", 0) or len(ch.get("raw_text", ""))
                if current_chars + ch_chars > max_char and current_batch:
                    batches.append({
                        "start_index": current_batch[0]["sort_index"],
                        "end_index": current_batch[-1]["sort_index"],
                        "chapter_count": len(current_batch),
                        "total_chars": current_chars,
                    })
                    # 重叠
                    if overlap > 0:
                        current_batch = current_batch[-overlap:]
                        current_chars = sum(
                            (c.get("char_count", 0) or len(c.get("raw_text", "")))
                            for c in current_batch
                        )
                    else:
                        current_batch = []
                        current_chars = 0
                current_batch.append(ch)
                current_chars += ch_chars
            if current_batch:
                batches.append({
                    "start_index": current_batch[0]["sort_index"],
                    "end_index": current_batch[-1]["sort_index"],
                    "chapter_count": len(current_batch),
                    "total_chars": current_chars,
                })
        else:
            # by_count
            step = max(1, batch_size - overlap)
            for i in range(0, len(chapters), step):
                batch_chs = chapters[i:i + batch_size]
                batches.append({
                    "start_index": batch_chs[0].get("sort_index", i),
                    "end_index": batch_chs[-1].get("sort_index", i + len(batch_chs) - 1),
                    "chapter_count": len(batch_chs),
                    "total_chars": sum(
                        (c.get("char_count", 0) or len(c.get("raw_text", "")))
                        for c in batch_chs
                    ),
                })

        # 动态生成分支节点
        next_nodes = []
        edition_id = ctx.global_params.get("edition_id") or ctx.params.get("edition_id")
        sail_url = ctx.global_params.get("sail_server_url", "http://localhost:8000")
        analysis_types = ctx.global_params.get("analysis_types", ["character", "plot", "setting", "emotion"])

        for i, batch in enumerate(batches):
            batch_fetch_id = f"batch_fetch_{i}"
            next_nodes.append({
                "id": batch_fetch_id,
                "type": "text_fetch",
                "name": f"批量获取批次 {i}",
                "params": {
                    "sail_server_url": sail_url,
                    "endpoint": "chapters",
                    "edition_id": edition_id,
                    "batch_info": batch,
                },
            })

            # 为每个分析维度生成对应的分析节点，并通过 join_to 阻塞对应的 merge 节点
            for dimension in analysis_types:
                analyze_id = f"analyze_{dimension}_{i}"
                next_nodes.append({
                    "id": analyze_id,
                    "type": "skill",
                    "name": f"分析 {dimension} 批次 {i}",
                    "depends_on": [batch_fetch_id],
                    "join_to": [f"merge_{dimension}"],
                    "params": {
                        "skill": f"novel_analyze_{dimension}",
                        "dimension": dimension,
                        "batch_index": i,
                        "batch_info": batch,
                        "edition_id": edition_id,
                    },
                })

        # 保存产物
        output_data = {
            "batch_count": len(batches),
            "batches": batches,
        }
        if ctx.store:
            ctx.store.save_artifact(
                ctx.run_id, f"{ctx.node_id}_result.json",
                json.dumps(output_data, ensure_ascii=False, indent=2)
            )

        return NodeResult.ok(
            data=output_data,
            output=f"Split {len(chapters)} chapters into {len(batches)} batches",
            next_nodes=next_nodes,
        )


class BatchMergeNode(NodeExecutor):
    """合并各批次的分析结果。

    参数::

        {
            "dimension": "character",   # 分析维度: character/plot/setting/emotion
            "merge_strategy": "concat"  # 合并策略: concat / dedup / summarize
        }

    上游依赖:
      - 所有 analyze_{dimension}_N 节点的结果

    输出:
      - 合并后的分析结果 JSON
    """

    node_type = "batch_merge"

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        if not params.get("dimension"):
            return "Missing required param: dimension"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        dimension = ctx.params["dimension"]
        strategy = ctx.params.get("merge_strategy", "concat")

        # 收集上游分析结果
        upstream = ctx.upstream_results
        batch_results = []
        for key, value in upstream.items():
            if key.startswith(f"analyze_{dimension}_"):
                batch_results.append(value)

        if not batch_results:
            return NodeResult.fail(f"No upstream results found for dimension '{dimension}'")

        # 合并
        merged = self._merge(batch_results, strategy, dimension)

        # 保存产物
        if ctx.store:
            ctx.store.save_artifact(
                ctx.run_id, f"merge_{dimension}.json",
                json.dumps(merged, ensure_ascii=False, indent=2)
            )

        return NodeResult.ok(
            data=merged,
            output=f"Merged {len(batch_results)} batches for {dimension}",
        )

    def _merge(self, results: List[Any], strategy: str, dimension: str) -> dict:
        if strategy == "concat":
            return {
                "dimension": dimension,
                "batch_count": len(results),
                "batches": results,
                "summary": f"Concatenated {len(results)} batch analyses",
            }
        if strategy == "dedup":
            # 简单去重：假设结果是列表，合并后去重
            all_items = []
            for r in results:
                items = r if isinstance(r, list) else r.get("items", r.get("data", []))
                if isinstance(items, list):
                    all_items.extend(items)
            # 按 name/id 去重
            seen = set()
            deduped = []
            for item in all_items:
                key = item.get("name") or item.get("id") or str(item)
                if key not in seen:
                    seen.add(key)
                    deduped.append(item)
            return {
                "dimension": dimension,
                "batch_count": len(results),
                "total_items": len(all_items),
                "unique_items": len(deduped),
                "items": deduped,
            }
        # summarize: 交给 LLM skill 处理，这里先做简单拼接
        return {
            "dimension": dimension,
            "batch_count": len(results),
            "batches": results,
            "note": "Use 'skill' node with 'summarize' prompt for LLM-based merging",
        }


class ReportNode(NodeExecutor):
    """生成最终综合报告。

    参数::

        {
            "template": "default",      # 报告模板
            "include_raw": false        # 是否包含原始分析数据
        }

    上游依赖:
      - merge_character, merge_plot, merge_setting, merge_emotion
      - work_meta
      - batch_split (批次信息)

    输出:
      - report.json 综合报告
    """

    node_type = "report"

    async def execute(self, ctx: NodeContext) -> NodeResult:
        template = ctx.params.get("template", "default")
        include_raw = ctx.params.get("include_raw", False)

        # 收集所有上游数据
        work_meta = ctx.upstream_results.get("fetch_work_meta", {})
        batch_info = ctx.upstream_results.get("batch_split", {})

        dimensions = ["character", "plot", "setting", "emotion"]
        analyses = {}
        for dim in dimensions:
            data = ctx.upstream_results.get(f"merge_{dim}")
            if data:
                analyses[dim] = data

        report = {
            "work": work_meta.get("data", work_meta) if isinstance(work_meta, dict) else work_meta,
            "batch_info": batch_info.get("data", batch_info) if isinstance(batch_info, dict) else batch_info,
            "analyses": analyses,
            "dimensions": list(analyses.keys()),
            "generated_at": datetime.now().isoformat(),
        }

        if not include_raw:
            # 精简报告：移除 batches 原始数据
            for dim, data in analyses.items():
                if isinstance(data, dict) and "batches" in data:
                    data["batches"] = f"[{len(data.get('batches', []))} batches omitted]"

        # 保存产物
        if ctx.store:
            ctx.store.save_artifact(
                ctx.run_id, "report.json",
                json.dumps(report, ensure_ascii=False, indent=2)
            )

        return NodeResult.ok(
            data=report,
            output=f"Report generated with {len(analyses)} dimensions",
        )


class BatchTextCollectorNode(NodeExecutor):
    """批量收集章节文本的辅助节点。

    由于 text_fetch 只能获取章节列表（不含 raw_text），
    此节点负责遍历章节索引，批量获取每章内容。

    参数::

        {
            "sail_server_url": "http://localhost:8000",
            "edition_id": 1,
            "start_index": 0,
            "end_index": 99,
            "concurrency": 5
        }

    上游依赖:
      - chapter_index (可选，如果没有则通过 chapter_count 获取)

    输出:
      - chapters: [{id, sort_index, label, title, raw_text, char_count}, ...]
    """

    node_type = "batch_text_collector"

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        if not params.get("sail_server_url"):
            return "Missing sail_server_url"
        if not params.get("edition_id"):
            return "Missing edition_id"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        url = ctx.params["sail_server_url"].rstrip("/")
        edition_id = ctx.params["edition_id"]
        start_index = ctx.params.get("start_index", 0)
        end_index = ctx.params.get("end_index")
        concurrency = ctx.params.get("concurrency", 5)

        # 如果没有指定 end_index，先获取章节总数
        if end_index is None:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(f"{url}/api/v1/text/edition/{edition_id}/chapters/count")
                resp.raise_for_status()
                count_data = resp.json()
                end_index = count_data.get("count", 0) - 1

        if end_index < start_index:
            return NodeResult.fail(f"Invalid range: {start_index} > {end_index}")

        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_one(idx: int) -> dict:
            async with semaphore:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(
                        f"{url}/api/v1/text/edition/{edition_id}/chapter/{idx}"
                    )
                    if resp.status_code == 200:
                        return resp.json()
                    return {"sort_index": idx, "error": resp.status_code}

        tasks = [fetch_one(i) for i in range(start_index, end_index + 1)]
        chapters = await asyncio.gather(*tasks)

        # 过滤失败的
        success_chapters = [c for c in chapters if "error" not in c]
        failed = len(chapters) - len(success_chapters)

        output_data = {
            "edition_id": edition_id,
            "start_index": start_index,
            "end_index": end_index,
            "fetched": len(success_chapters),
            "failed": failed,
            "chapters": success_chapters,
        }

        if ctx.store:
            ctx.store.save_artifact(
                ctx.run_id, f"{ctx.node_id}_chapters.json",
                json.dumps(output_data, ensure_ascii=False, indent=2)
            )

        return NodeResult.ok(
            data=output_data,
            output=f"Collected {len(success_chapters)}/{len(chapters)} chapters ({failed} failed)",
        )
