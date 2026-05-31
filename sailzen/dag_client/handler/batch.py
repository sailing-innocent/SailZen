"""Batch & SubBatch handlers."""

from __future__ import annotations

from bot_server.models import BatchStatus, make_batch
from cube.command_bus import Command, CommandResult


def register(bus, db, scheduler) -> dict:
    """返回 {command_name: handler_fn} 映射。"""

    # ── Batches ────────────────────────────────────────────────────

    async def handle_list_batches(cmd: Command) -> CommandResult:
        batches = await db.get_batches(
            workspace_id=cmd.args.get("workspace_id") or None,
            status=cmd.args.get("status") or None,
            lifecycle=cmd.args.get("lifecycle") or None,
        )
        return CommandResult.ok(data=batches)

    async def handle_get_batch(cmd: Command) -> CommandResult:
        b = await db.get_batch(cmd.args["batch_id"])
        if not b:
            return CommandResult.fail("Batch 不存在")
        b["sub_batches"] = await db.get_sub_batches(b["id"])
        return CommandResult.ok(data=b)

    async def handle_create_batch(cmd: Command) -> CommandResult:
        batch = make_batch(
            workspace_id=cmd.args["workspace_id"],
            batch_type=cmd.args.get("batch_type", "global"),
            commits=cmd.args.get("commits", []),
            predecessor_branch=cmd.args.get("predecessor_branch", "main"),
            predecessor_id=cmd.args.get("predecessor_id"),
            config=cmd.args.get("config"),
            batch_id=cmd.args.get("id"),
        )
        await db.upsert_batch(batch)
        return CommandResult.ok(data=batch, text=f"✅ Batch 已创建: {batch['id'][:16]}")

    async def handle_schedule_batch(cmd: Command) -> CommandResult:
        batch = await db.get_batch(cmd.args["batch_id"])
        if not batch:
            return CommandResult.fail("Batch 不存在")
        if batch["status"] != BatchStatus.PENDING.value:
            return CommandResult.fail(f"Batch 状态为 {batch['status']}, 需要 pending")
        tasks = await scheduler.schedule_batch(batch)
        return CommandResult.ok(data={
            "batch_id": batch["id"],
            "tasks_created": len(tasks),
            "status": "running",
        })

    # ── SubBatches ─────────────────────────────────────────────────

    async def handle_list_sub_batches(cmd: Command) -> CommandResult:
        bid = cmd.args.get("batch_id", "")
        if bid:
            sbs = await db.get_sub_batches(bid)
        else:
            sbs = []
        return CommandResult.ok(data=sbs)

    async def handle_get_sub_batch(cmd: Command) -> CommandResult:
        sb = await db.get_sub_batch(cmd.args["sb_id"])
        if not sb:
            return CommandResult.fail("SubBatch 不存在")
        sb["tasks"] = await db.get_tasks(sub_batch_id=sb["id"])
        return CommandResult.ok(data=sb)

    return {
        "list_batches": handle_list_batches,
        "get_batch": handle_get_batch,
        "create_batch": handle_create_batch,
        "schedule_batch": handle_schedule_batch,
        "list_sub_batches": handle_list_sub_batches,
        "get_sub_batch": handle_get_sub_batch,
    }
