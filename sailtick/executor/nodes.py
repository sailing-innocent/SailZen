# -*- coding: utf-8 -*-
# @file nodes.py
# @brief SailTick 各节点实现
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 节点实现。

每个节点是 NodeExecutor 子类；params 通过 NodeContext 传入。
节点设计为「薄封装」：核心逻辑在 sailtick 各模块，节点只做参数适配，
以便 TickEngine 进程内路径与 dag_client pipeline 路径共享同一份实现。

节点依赖（datascan/llm/inbox 等）通过 params["_services"] 注入（进程内模式），
在纯 dag_client 模式下缺省时降级为无操作（节点仍合法）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


def _services(ctx: NodeContext) -> Dict[str, Any]:
    return ctx.params.get("_services") or {}


class TickScanNode(NodeExecutor):
    """SCAN 阶段：数据扫描 + 票据同步。"""

    node_type = "tick_scan"

    async def execute(self, ctx: NodeContext) -> NodeResult:
        scanner = _services(ctx).get("scanner")
        inbox = _services(ctx).get("inbox")
        if scanner is None:
            return NodeResult.ok(data={"skipped": "no scanner service"})
        package = await scanner.scan(days=int(ctx.params.get("days", 7)))
        tickets: List[dict] = []
        if inbox is not None:
            try:
                tickets = await inbox.pending_tickets()
            except Exception as exc:
                logger.warning("tick_scan pending_tickets failed: %s", exc)
        return NodeResult.ok(
            data={"data_ok": package.get("health_ok"), "pending_tickets": len(tickets)},
            output=f"data_ok={package.get('health_ok')} pending={len(tickets)}",
        )


class TickPlanNode(NodeExecutor):
    """PLAN 阶段：调用 LLM 生成计划（不可用 → 空计划）。"""

    node_type = "tick_plan"

    async def execute(self, ctx: NodeContext) -> NodeResult:
        llm = _services(ctx).get("llm")
        prompt = ctx.params.get("prompt", "")
        if llm is None or not prompt:
            return NodeResult.ok(data={"plan": {}, "source": "noop"})
        try:
            resp = await llm.chat(prompt, expect_json=True, max_tokens=3000)
            import json

            plan = json.loads(resp.content.strip().strip("`").removeprefix("json"))
            return NodeResult.ok(data={"plan": plan, "source": "llm"})
        except Exception as exc:
            logger.warning("tick_plan llm failed: %s", exc)
            return NodeResult.ok(data={"plan": {}, "source": "fallback"})


class TicketEmitNode(NodeExecutor):
    """创建一张票据。"""

    node_type = "ticket_emit"

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        if not params.get("title"):
            return "ticket_emit requires params.title"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        inbox = _services(ctx).get("inbox")
        if inbox is None:
            return NodeResult.ok(data={"skipped": "no inbox service"})
        ticket = await inbox.create_ticket(
            tick_id=ctx.params.get("tick_id", ""),
            ticket_type=ctx.params.get("ticket_type", ctx.params.get("type", "info")),
            title=ctx.params["title"],
            body=ctx.params.get("body", ""),
            priority=ctx.params.get("priority", "normal"),
            expected_reply_hours=ctx.params.get("expected_reply_hours"),
            fallback_assumption=ctx.params.get("fallback_assumption", ""),
            channel=ctx.params.get("channel", "web"),
        )
        return NodeResult.ok(data={"ticket_id": ticket.get("id")})


class WeightTrendNode(NodeExecutor):
    """体重趋势：从数据包提取最新/区间/趋势方向。"""

    node_type = "weight_trend"

    async def execute(self, ctx: NodeContext) -> NodeResult:
        scanner = _services(ctx).get("scanner")
        if scanner is None:
            return NodeResult.ok(data={"skipped": "no scanner service"})
        package = await scanner.scan(days=int(ctx.params.get("days", 14)))
        series = (package.get("weight") or []) if package.get("health_ok") else []
        vals = [
            (w.get("value") or w.get("weight"))
            for w in series
            if isinstance(w, dict) and (w.get("value") or w.get("weight")) is not None
        ]
        trend = "flat"
        if len(vals) >= 2:
            delta = float(vals[-1]) - float(vals[0])
            trend = "down" if delta < -0.5 else ("up" if delta > 0.5 else "flat")
        return NodeResult.ok(
            data={
                "latest": vals[-1] if vals else None,
                "min": min(vals) if vals else None,
                "max": max(vals) if vals else None,
                "trend": trend,
                "count": len(vals),
            }
        )


class ConditionNode(NodeExecutor):
    """条件分支：评估 condition 表达式，走 true_next/false_next。"""

    node_type = "condition"

    async def execute(self, ctx: NodeContext) -> NodeResult:
        expr = ctx.params.get("condition", "False")
        try:
            # 简易求值：upstream.<node>.result 路径解析
            value = self._eval(expr, ctx.upstream_results)
        except Exception as exc:
            logger.warning("condition eval failed (%s): %s", expr, exc)
            value = False
        nxt = ctx.params.get("true_next", []) if value else ctx.params.get("false_next", [])
        return NodeResult(success=True, data={"value": bool(value)}, next_nodes=list(nxt))

    def _eval(self, expr: str, upstream: Dict[str, Any]) -> Any:
        # 支持 "<path> | default(x) > y" 的简易子集
        import re

        m = re.match(r"^\s*(.+?)\s*(>=|<=|==|!=|>|<)\s*(.+?)\s*$", expr)
        if not m:
            return bool(self._resolve(expr, upstream))
        left, op, right = m.groups()
        left_val = self._resolve(left, upstream)
        right_val: Any = right.strip().strip('"\'')
        try:
            right_val = float(right_val)  # type: ignore[arg-type]
            left_val = float(left_val)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            pass
        return {
            ">": left_val > right_val,
            "<": left_val < right_val,
            ">=": left_val >= right_val,
            "<=": left_val <= right_val,
            "==": left_val == right_val,
            "!=": left_val != right_val,
        }[op]

    @staticmethod
    def _resolve(path: str, upstream: Dict[str, Any]) -> Any:
        path = path.strip()
        default = None
        if "|" in path:
            path, dflt = path.split("|", 1)
            dflt = dflt.strip()
            if dflt.startswith("default(") and dflt.endswith(")"):
                default = dflt[8:-1].strip().strip('"\'')
                try:
                    default = float(default)  # type: ignore[assignment]
                except (ValueError, TypeError):
                    pass
        cur: Any = upstream
        for part in path.split("."):
            part = part.strip()
            if not part or part == "upstream":
                continue
            if isinstance(cur, dict):
                if part not in cur:
                    return default
                cur = cur[part]
            else:
                return default
        return cur if cur is not None else default


class HandoffWriteNode(NodeExecutor):
    """HANDOFF 阶段：写交接文档。"""

    node_type = "handoff_write"

    async def execute(self, ctx: NodeContext) -> NodeResult:
        manager = _services(ctx).get("handoffs")
        if manager is None:
            return NodeResult.ok(data={"skipped": "no handoffs service"})
        from sailtick.handoff import HandoffDoc

        doc = HandoffDoc(
            tick_id=ctx.params.get("tick_id", ""),
            slot=ctx.params.get("slot", "manual"),
            tick_date=ctx.params.get("tick_date", ""),
            prev_summary=ctx.params.get("summary", ""),
            unfinished=ctx.params.get("unfinished", []),
            plan_version=ctx.params.get("plan_version", ""),
            plan_change=ctx.params.get("plan_change", ""),
            pending_tickets=ctx.params.get("pending_tickets", []),
            user_status=ctx.params.get("user_status", ""),
            next_tick_suggestions=ctx.params.get("next_tick_suggestions", []),
        )
        path = await manager.write(doc)
        return NodeResult.ok(data={"path": path})


def register_all(registry: Any) -> None:
    """把 SailTick 节点族注册进 dag_client NodeRegistry。"""
    registry.register("tick_scan", TickScanNode)
    registry.register("tick_plan", TickPlanNode)
    registry.register("ticket_emit", TicketEmitNode)
    registry.register("weight_trend", WeightTrendNode)
    registry.register("condition", ConditionNode)
    registry.register("handoff_write", HandoffWriteNode)
