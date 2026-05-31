"""Pipeline run handlers (兼容 Dashboard DAG 前端)。

包含:
  - pipeline_definitions: 返回可用的 Pipeline 定义列表
  - start_pipeline_run: 两阶段初始化 (Phase 0 立即创建 Batch → Phase 1/2/3 异步执行)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import yaml

from bot_server.deps import get_event_bus, track_background_task
from bot_server.models import (
    BatchStatus, TaskStatus, now_iso,
)
from bot_server.service.converter import batch_to_pipeline_run
from bot_server.service.task_runner import (
    TaskRunnerConfig,
    TaskRunnerDependencies,
    normalize_mock_task_types,
    productive_task_runner,
)
from bot_server.service.gb_init import create_init_batch, execute_init
from cube.command_bus import Command, CommandResult
from cube.codemaker import CodemakerProcessManager
from cube.paths import resolve_data_path

logger = logging.getLogger(__name__)


def _load_globalbatch_config() -> dict:
    """从 bot.yaml 加载 globalbatch 配置节。"""
    config_path = os.environ.get("CUBECLAW_CONFIG", "bot.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("globalbatch", {})
    except Exception as e:
        logger.warning("加载 bot.yaml globalbatch 配置失败: %s", e)
        return {}


def _load_codemaker_config() -> dict:
    """从 bot.yaml 加载 codemaker 配置节。

    Returns:
        {"host": str, "port": int, ...} 或空 dict

    注意: 此函数只负责读取配置, 不负责启动 codemaker 进程。
    codemaker serve 进程需要预先通过以下方式之一启动:
      1. POPO Bot 的「启动 <项目>」命令 (CodemakerSessionManager)
      2. 手动执行: codemaker serve --hostname 127.0.0.1 --port 4096
      3. 调试脚本: python scripts/debug_pick.py --ensure-running
    """
    config_path = os.environ.get("CUBECLAW_CONFIG", "bot.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        cm_cfg = cfg.get("codemaker", {})
        if cm_cfg:
            result = {
                "host": "127.0.0.1",
                "port": cm_cfg.get("base_port", 4096),
                "agent": cm_cfg.get("agent", "Sisyphus"),
                "projects": cm_cfg.get("projects", []),
            }
            for key in ("sse_timeout", "http_timeout", "startup_timeout"):
                if key in cm_cfg:
                    result[key] = cm_cfg[key]
            for key, default in {
                "state_file": "bot/state/sessions.json",
                "log_dir": "bot/codemaker_logs",
                "transcript_dir": "transcripts",
            }.items():
                result[key] = str(resolve_data_path(cm_cfg.get(key), default, cfg, config_path=config_path))
            return result
        return {}
    except Exception as e:
        logger.warning("加载 bot.yaml codemaker 配置失败: %s", e)
        return {}


async def _ensure_codemaker_running(codemaker_cfg: dict) -> dict | None:
    """确保 codemaker serve 进程已启动。

    通过 CodemakerSessionManager.ensure_running() 自动启动进程。
    该方法是同步阻塞的 (等待 health check)，所以用 run_in_executor 包装。

    Args:
        codemaker_cfg: 从 _load_codemaker_config() 返回的配置 dict

    Returns:
        更新了实际 port 的 codemaker_cfg, 或 None (启动失败)
    """
    projects = codemaker_cfg.get("projects", [])
    if not projects:
        logger.warning("[Pipeline] codemaker.projects 未配置, 无法自动启动")
        return None

    # 取第一个项目的 path 作为 codemaker serve 的 cwd
    workspace_path = projects[0].get("path", "")
    if not workspace_path:
        logger.warning("[Pipeline] codemaker.projects[0].path 为空")
        return None

    base_port = codemaker_cfg.get("port", 4096)

    def _do_ensure():
        mgr = CodemakerProcessManager(
            base_port=base_port,
            state_file=codemaker_cfg.get("state_file"),
            log_dir=codemaker_cfg.get("log_dir"),
        )
        ok, session, msg = mgr.ensure_running(workspace_path)
        return ok, session, msg

    loop = asyncio.get_event_loop()
    try:
        ok, session, msg = await loop.run_in_executor(None, _do_ensure)
    except Exception as exc:
        logger.error("[Pipeline] 启动 codemaker serve 异常: %s", exc)
        return None

    if ok:
        # 用实际分配到的端口更新配置
        actual_port = session.port
        logger.info(
            "[Pipeline] Codemaker serve 已就绪: port=%d, pid=%s, msg=%s",
            actual_port, session.pid, msg,
        )
        return {
            **codemaker_cfg,
            "port": actual_port,
        }
    else:
        logger.error("[Pipeline] 启动 codemaker serve 失败: %s", msg)
        return None


def register(bus, db, scheduler) -> dict:
    """返回 {command_name: handler_fn} 映射。"""

    async def handle_pipeline_definitions(cmd: Command) -> CommandResult:
        globalbatch_nodes = [
            {"type": "init_workspace", "label": "Init Workspace", "default_mock": False},
            {"type": "pick", "label": "Pick / Branch Dance", "default_mock": False},
            {"type": "summary", "label": "Summary", "default_mock": False},
            {"type": "ensure_worktree", "label": "Ensure Worktree", "default_mock": False},
            {"type": "rebase", "label": "Rebase", "default_mock": False},
            {"type": "build_win", "label": "Windows BuildFix", "default_mock": False},
            {"type": "build_ios", "label": "iOS BuildFix", "default_mock": True},
            {"type": "review", "label": "SubBatch Review", "default_mock": False},
            {"type": "final_review", "label": "Final Review", "default_mock": False},
            {"type": "report", "label": "Report", "default_mock": False},
            {"type": "finalization", "label": "Finalization", "default_mock": False},
        ]
        return CommandResult.ok(data=[
            {
                "id": "globalbatch_init",
                "name": "GlobalBatch Init",
                "description": "标准 GlobalBatch 流程：创建 Init Workspace 入口节点，再进入 pick_a；可通过 mock Init Workspace 表达跳过初始化。",
                "params": [
                    {"key": "workspace_id", "label": "Workspace", "type": "string", "default": ""},
                    {"key": "predecessor_branch", "label": "Predecessor Branch", "type": "string", "default": ""},
                    {"key": "subbatch_size", "label": "SubBatch Size", "type": "string", "default": "10"},
                    {"key": "subbatch_count", "label": "SubBatch Count (_a,_b,_c,_d)", "type": "string", "default": "4"},
                ],
                "nodes": globalbatch_nodes,
                "options": {
                    "node_mock": True,
                },
            },
        ])

    async def handle_list_pipeline_runs(cmd: Command) -> CommandResult:
        batches = await db.get_batches()
        runs = []
        for b in batches[:20]:
            run = await batch_to_pipeline_run(b)
            runs.append(run)
        return CommandResult.ok(data=runs)

    async def handle_get_pipeline_run(cmd: Command) -> CommandResult:
        batch = await db.get_batch(cmd.args["run_id"])
        if not batch:
            return CommandResult.fail("Pipeline run 不存在")
        run = await batch_to_pipeline_run(batch)
        return CommandResult.ok(data=run)

    async def handle_start_pipeline_run(cmd: Command) -> CommandResult:
        pipeline_id = cmd.args.get("pipeline_id", "globalbatch")
        params = cmd.args.get("params", {})

        workspace_id = params.get("workspace_id", "")
        if not workspace_id:
            projects = await db.get_projects()
            if projects:
                workspaces = await db.get_workspaces(projects[0]["id"])
                if workspaces:
                    workspace_id = workspaces[0]["id"]

        if not workspace_id:
            return CommandResult.fail("无可用 workspace")

        # ── GlobalBatch 初始化 / 续跑流程 ────────────────────────────
        if pipeline_id == "globalbatch_init":
            try:
                gb_cfg = _load_globalbatch_config()

                mock_task_types = normalize_mock_task_types(
                    params.get("mock_task_types") or params.get("node_mocks")
                )
                init_workspace_mocked = "init_workspace" in mock_task_types

                raw_predecessor = (
                    params.get("predecessor_branch")
                    or gb_cfg.get("predecessor_branch")
                    or ""
                ).strip()
                if not raw_predecessor:
                    raise ValueError(
                        "GlobalBatch Init 需要显式配置 predecessor_branch "
                        "(Dashboard 参数或 bot.yaml → globalbatch → predecessor_branch)"
                    )
                unsupported_branch_keys = [
                    key for key in ("base_branch",)
                    if key in params
                ]
                if unsupported_branch_keys:
                    raise ValueError(
                        "GlobalBatch Init 只接受 predecessor_branch 作为 Batch 前序分支；"
                        f"不接受参数: {', '.join(unsupported_branch_keys)}"
                    )

                init_config = {
                    "predecessor_branch": raw_predecessor,
                    "subbatch_size": int(params.get("subbatch_size") or gb_cfg.get("subbatch_size", 10)),
                    "subbatch_count": int(params.get("subbatch_count") or gb_cfg.get("subbatch_count", 4)),
                    "mock": False,
                    "mock_init_workspace": init_workspace_mocked,
                    "mock_task_types": sorted(mock_task_types),
                }
                init_config.setdefault("workspace_root", gb_cfg.get("workspace_root", ""))
                init_config.setdefault("github_repo", gb_cfg.get("github_repo", "https://github.com/Mojang/Minecraftpe/"))
                init_config.setdefault("github_branch", gb_cfg.get("github_branch", "main"))

                logger.info(
                    "[Pipeline] Real 模式配置: workspace_root=%s, repo=%s, branch=%s, node_mocks=%s",
                    init_config["workspace_root"],
                    init_config["github_repo"],
                    init_config["github_branch"],
                    ",".join(sorted(mock_task_types)) or "none",
                )

                # ── Phase 0: 立即创建 Batch + init_workspace 节点 ──
                # 前端可以立刻看到 Pipeline DAG；init_workspace 的真实工作
                # 将在 task runner 异步执行。
                batch, init_task = await create_init_batch(
                    db=db, scheduler=scheduler,
                    workspace_id=workspace_id, config=init_config,
                )

                batch_id = batch["id"]
                run = await batch_to_pipeline_run(batch)

                # ── 启动 Productive Task Runner ──
                codemaker_cfg = None
                cm_cfg_raw = _load_codemaker_config()
                if cm_cfg_raw:
                    codemaker_cfg = cm_cfg_raw
                    logger.info(
                        "[Pipeline] Codemaker 集成已启用: base_port=%s",
                        codemaker_cfg.get("port"),
                    )
                else:
                    logger.warning(
                        "[Pipeline] 未配置 codemaker；未被 node mock 的 CodeMaker 节点会 BLOCKED"
                    )

                event_bus = get_event_bus()
                runner_deps = TaskRunnerDependencies(db=db, scheduler=scheduler, event_bus=event_bus)
                runner_config = TaskRunnerConfig(
                    codemaker_config=codemaker_cfg,
                    mock_task_types=mock_task_types,
                )
                track_background_task(asyncio.create_task(productive_task_runner(batch_id, runner_deps, runner_config)))
                runner_name = "productive_task_runner"

                logger.info(
                    "[Pipeline] Task Runner 已启动: %s (runner=%s, node_mocks=%s, codemaker=%s)",
                    batch_id, runner_name, ",".join(sorted(mock_task_types)) or "none", "yes" if codemaker_cfg else "no",
                )

                init_action = "初始化已跳过（Init Workspace mocked）" if init_workspace_mocked else "init_workspace 节点将在后台运行"
                return CommandResult.ok(
                    data=run,
                    text=(
                        f"⚡ GlobalBatch {init_action}: {batch_id}\n"
                        f"  Batch 前序分支: {raw_predecessor}\n"
                        f"  Pipeline 已创建，init_workspace 节点正在执行（可从前端实时查看进度）\n"
                        f"  Runner: {runner_name}"
                    ),
                    events=[{
                        "type": "pipeline_run.started",
                        "entity_type": "batch",
                        "entity_id": batch_id,
                        "run_id": batch_id,
                        "data": {
                            "pipeline_name": run["pipeline_name"],
                            "runner": runner_name,
                            "mock_task_types": sorted(mock_task_types),
                            "mock_init_workspace": init_workspace_mocked,
                        },
                    }],
                )
            except Exception as e:
                return CommandResult.fail(f"GlobalBatch 初始化失败: {e}")

        return CommandResult.fail(f"未知 Pipeline 模板: {pipeline_id}")

    async def handle_resume_pipeline_from_node(cmd: Command) -> CommandResult:
        run_id = cmd.args["run_id"]
        node_id = cmd.args["node_id"]

        batch = await db.get_batch(run_id)
        if not batch:
            return CommandResult.fail("Pipeline run 不存在")

        tasks = await db.get_tasks_by_batch(run_id)
        task_by_id = {t["id"]: t for t in tasks}
        if node_id not in task_by_id:
            return CommandResult.fail("节点不存在")

        target_task = task_by_id[node_id]
        target_already_success = (
            target_task.get("status") == TaskStatus.SUCCESS.value
        )

        # 严格意义上的“后续节点”——传递依赖于 node_id 的所有节点，但 **不含**
        # node_id 自身。重置时这些节点必须先全部进入 PENDING，由 runner / 调度器
        # 在 node_id 完成后再逐层解锁，避免出现“自己还没跑完但下游已经被 QUEUED”的
        # 错乱状态。
        strict_descendants: set[str] = set()
        changed = True
        while changed:
            changed = False
            for t in tasks:
                tid = t["id"]
                if tid == node_id or tid in strict_descendants:
                    continue
                deps = t.get("dependencies", []) or []
                if node_id in deps or any(dep in strict_descendants for dep in deps):
                    strict_descendants.add(tid)
                    changed = True

        # 1) 后续节点全部锁回 PENDING（清掉已有的执行/完成痕迹），等待 node_id
        #    完成后由 scheduler._unlock_dependents 逐层解锁。
        pending_count = 0
        downstream_expected = [
            TaskStatus.QUEUED.value,
            TaskStatus.ASSIGNED.value,
            TaskStatus.RUNNING.value,
            TaskStatus.PENDING.value,
            TaskStatus.BLOCKED.value,
            TaskStatus.SUCCESS.value,
            TaskStatus.CANCELLED.value,
            TaskStatus.FAILED.value,
            TaskStatus.SUPERSEDED.value,
        ]
        for t in tasks:
            if t["id"] not in strict_descendants:
                continue
            updated = await db.update_task_status(
                t["id"],
                TaskStatus.PENDING.value,
                expected_statuses=downstream_expected,
                force=True,
                queued_at=None,
                started_at=None,
                completed_at=None,
                result=None,
                error=None,
            )
            if updated:
                pending_count += 1

        # 2) 处理目标节点本身
        #    - 若目标已经 SUCCESS：保持 SUCCESS，调用 scheduler._unlock_dependents
        #      让其直接后继从 PENDING 解锁为 QUEUED，runner 接力推进。
        #    - 否则：重置为 QUEUED，由 runner 推进至 RUNNING。
        if target_already_success:
            # 重新读取最新版本，确保 _unlock_dependents 使用的状态是最新的（前面
            # 的 PENDING 重置可能已经修改了周边任务）。
            refreshed_target = await db.get_task(node_id) or target_task
            await scheduler._unlock_dependents(refreshed_target)
            target_action = "保持 SUCCESS，已解锁后续节点"
        else:
            queued_self = await db.update_task_status(
                node_id,
                TaskStatus.QUEUED.value,
                expected_statuses=[
                    TaskStatus.QUEUED.value,
                    TaskStatus.ASSIGNED.value,
                    TaskStatus.RUNNING.value,
                    TaskStatus.PENDING.value,
                    TaskStatus.BLOCKED.value,
                    TaskStatus.CANCELLED.value,
                    TaskStatus.FAILED.value,
                    TaskStatus.SUPERSEDED.value,
                ],
                force=True,
                queued_at=now_iso(),
                started_at=None,
                completed_at=None,
                result=None,
                error=None,
            )
            target_action = "已重置为 QUEUED，等待 runner 拉起" if queued_self else "状态保持不变"

        await db.update_batch_status(run_id, BatchStatus.RUNNING.value, completed_at=None)

        event_bus = get_event_bus()
        codemaker_cfg = None
        cm_cfg_raw = _load_codemaker_config()
        if cm_cfg_raw:
            codemaker_cfg = cm_cfg_raw
        mock_task_types = set((batch.get("config") or {}).get("mock_task_types") or [])
        runner_deps = TaskRunnerDependencies(db=db, scheduler=scheduler, event_bus=event_bus)
        runner_config = TaskRunnerConfig(
            codemaker_config=codemaker_cfg,
            mock_task_types=mock_task_types,
        )
        track_background_task(asyncio.create_task(productive_task_runner(run_id, runner_deps, runner_config)))

        run = await batch_to_pipeline_run(await db.get_batch(run_id))
        return CommandResult.ok(
            data=run,
            text=(
                f"▶️ 已从节点 {node_id[:8]} 断点续跑："
                f"自身 {target_action}，后续 {pending_count} 个节点回到 PENDING"
            ),
            events=[{
                "type": "pipeline_run.progress",
                "entity_type": "batch",
                "entity_id": run_id,
                "run_id": run_id,
                "data": run,
            }],
        )

    async def handle_cancel_pipeline_run(cmd: Command) -> CommandResult:
        run_id = cmd.args["run_id"]
        batch = await db.get_batch(run_id)
        if not batch:
            return CommandResult.fail("Pipeline run 不存在")

        await db.update_batch_status(run_id, BatchStatus.FAILED.value, completed_at=now_iso())
        tasks = await db.get_tasks_by_batch(run_id)
        for t in tasks:
            if t["status"] in (TaskStatus.QUEUED.value, TaskStatus.ASSIGNED.value,
                               TaskStatus.RUNNING.value, TaskStatus.PENDING.value):
                await db.update_task_status(
                    t["id"],
                    TaskStatus.CANCELLED.value,
                    expected_statuses=[TaskStatus.QUEUED.value, TaskStatus.ASSIGNED.value,
                                       TaskStatus.RUNNING.value, TaskStatus.PENDING.value],
                )

        return CommandResult.ok(
            text=f"❌ Pipeline {run_id[:16]} 已取消",
            events=[{
                "type": "pipeline_run.failed",
                "entity_type": "batch",
                "entity_id": run_id,
                "run_id": run_id,
                "data": {"pipeline_name": batch.get("batch_type", ""), "reason": "cancelled"},
            }],
        )

    async def handle_manual_block_node(cmd: Command) -> CommandResult:
        run_id = cmd.args["run_id"]
        node_id = cmd.args["node_id"]
        reason = (cmd.args.get("reason") or "手动 block：人工接管并清理 LLM 错误行为").strip()

        batch = await db.get_batch(run_id)
        if not batch:
            return CommandResult.fail("Pipeline run 不存在")

        task = await db.get_task(node_id)
        if not task or task.get("batch_id") != run_id:
            return CommandResult.fail("节点不存在")

        now = now_iso()
        error = {
            "runner": "dashboard_manual_block",
            "error": reason,
            "manual_block": True,
            "blocked_by": cmd.actor or "dashboard",
            "blocked_at": now,
        }

        # 先把节点强制置为 BLOCKED，runner 的 claim/update 均带 expected status，
        # 后续完成回写会失败或被 batch 终态拦住，从而让人接管。
        await db.update_task_status(
            node_id,
            TaskStatus.BLOCKED.value,
            expected_statuses=[
                TaskStatus.QUEUED.value,
                TaskStatus.ASSIGNED.value,
                TaskStatus.RUNNING.value,
                TaskStatus.PENDING.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
            ],
            force=True,
            completed_at=now,
            error=error,
        )
        await db.update_batch_status(run_id, BatchStatus.BLOCKED.value, completed_at=now)

        pids: list[int] = []
        ports: list[int] = []
        updated_runs = 0
        try:
            runs = await db.get_task_runs(node_id)
            for task_run in runs:
                if str(task_run.get("status") or "").lower() not in ("running", "pending"):
                    continue
                context = task_run.get("context") or {}
                if isinstance(context, dict):
                    pid = context.get("codemaker_pid")
                    port = context.get("port")
                    if pid:
                        pids.append(int(pid))
                    if port:
                        ports.append(int(port))
                await db.complete_task_run(
                    task_run["id"],
                    success=False,
                    error={**error, "previous_status": task_run.get("status")},
                )
                updated_runs += 1
        except Exception:
            logger.exception("[Pipeline] 手动 block 更新 task_runs 失败: node=%s", node_id[:16])

        kill_result: dict[str, Any] = {}
        try:
            from bot_watcher import kill_codemaker_runner_for_task, load_config

            config_path = os.environ.get("CUBECLAW_CONFIG", "bot.yaml")
            cfg = load_config(config_path)
            kill_result = await asyncio.to_thread(
                kill_codemaker_runner_for_task,
                node_id,
                pids=pids,
                ports=ports,
                config=cfg,
                config_path=config_path,
            )
        except Exception as exc:
            logger.warning("[Pipeline] 手动 block 清理 CodeMaker runner 失败: node=%s err=%s", node_id[:16], exc)
            kill_result = {"error": str(exc), "requested_pids": pids, "requested_ports": ports, "killed_pids": []}

        event_bus = get_event_bus()
        await event_bus.emit({
            "type": "task.blocked",
            "entity_type": "task",
            "entity_id": node_id,
            "run_id": run_id,
            "actor": cmd.actor or "dashboard",
            "data": {
                "task_type": task.get("type", ""),
                "task_label": task.get("id", "")[:16],
                "runner": "dashboard_manual_block",
                "manual_block": True,
                "reason": reason,
                "kill_result": kill_result,
            },
        })

        run = await batch_to_pipeline_run(await db.get_batch(run_id))
        return CommandResult.ok(
            data=run,
            text=(
                f"⛔ 已手动 block 节点 {node_id[:8]}，"
                f"已结束 {updated_runs} 条 task_run，"
                f"已强杀 {len(kill_result.get('killed_pids') or [])} 个 CodeMaker runner"
            ),
            events=[{
                "type": "pipeline_run.progress",
                "entity_type": "batch",
                "entity_id": run_id,
                "run_id": run_id,
                "data": run,
            }],
        )

    async def handle_manual_success_node(cmd: Command) -> CommandResult:
        """手动将任意状态的节点强制设为 SUCCESS —— 人类专家接管完成。

        与 resume-from-node 不同：success 不会重置下游，而是把当前节点当作已完成，
        然后调用 _unlock_dependents 让 scheduler 正常推进后续。
        """
        run_id = cmd.args["run_id"]
        node_id = cmd.args["node_id"]
        reason = (cmd.args.get("reason") or "手动标记 success：人类专家接管完成").strip()

        logger.info("[manual_success_node] run_id=%s node_id=%s reason=%s", run_id, node_id, reason[:60])

        batch = await db.get_batch(run_id)
        logger.info("[manual_success_node] batch=%s", batch["id"] if batch else None)
        if not batch:
            return CommandResult.fail("Pipeline run 不存在")

        task = await db.get_task(node_id)
        logger.info("[manual_success_node] task=%s task.batch_id=%s",
                     task["id"][:16] if task else None,
                     task.get("batch_id") if task else None)
        if not task:
            return CommandResult.fail("节点不存在")
        # 检查 task 是否属于该 batch：直接字段 batch_id 或通过 sub_batch 关联
        task_batch_id = task.get("batch_id")
        if not task_batch_id:
            sub_batch = await db.get_sub_batch(task.get("sub_batch_id"))
            task_batch_id = sub_batch.get("batch_id") if sub_batch else None
            logger.info("[manual_success_node] sub_batch_id=%s batch_id=%s",
                         task.get("sub_batch_id"), task_batch_id)
        if task_batch_id != run_id:
            logger.warning("[manual_success_node] batch_id mismatch: task_batch=%s run=%s",
                           task_batch_id, run_id)
            return CommandResult.fail(f"节点不存在 (task batch={task_batch_id}, run={run_id})")

        now = now_iso()
        result_payload = {
            "runner": "dashboard_manual_success",
            "reason": reason,
            "manual_success": True,
            "completed_by": cmd.actor or "dashboard",
            "completed_at": now,
            "previous_status": task.get("status"),
        }

        # 将当前节点强制置为 SUCCESS
        updated = await db.update_task_status(
            node_id,
            TaskStatus.SUCCESS.value,
            expected_statuses=[
                TaskStatus.PENDING.value,
                TaskStatus.QUEUED.value,
                TaskStatus.ASSIGNED.value,
                TaskStatus.RUNNING.value,
                TaskStatus.FAILED.value,
                TaskStatus.BLOCKED.value,
                TaskStatus.CANCELLED.value,
                TaskStatus.SUPERSEDED.value,
            ],
            force=True,
            completed_at=now,
            error=None,
            result=result_payload,
        )
        if not updated:
            latest = await db.get_task(node_id)
            latest_status = (latest or {}).get("status")
            if latest_status == TaskStatus.SUCCESS.value:
                logger.info("手动 success: 节点 %s 已经是 SUCCESS，继续推进解锁", node_id[:8])
            else:
                return CommandResult.fail(
                    f"无法设置节点状态: 当前状态 {latest_status}，不允许转为 SUCCESS"
                )

        # 结束该节点关联的所有正在运行的 task_run
        updated_runs = 0
        all_runs: list[dict] = []
        try:
            all_runs = await db.get_task_runs(node_id)
            for task_run in all_runs:
                if str(task_run.get("status") or "").lower() not in ("running", "pending", "starting"):
                    continue
                await db.complete_task_run(
                    task_run["id"],
                    success=True,
                    error=None,
                )
                updated_runs += 1
        except Exception:
            logger.exception("[Pipeline] 手动 success 更新 task_runs 失败: node=%s", node_id[:16])

        # 强杀可能还在运行的 CodeMaker runner
        pids: list[int] = []
        ports: list[int] = []
        try:
            for task_run in all_runs:
                context = task_run.get("context") or {}
                if isinstance(context, dict):
                    pid = context.get("codemaker_pid")
                    port = context.get("port")
                    if pid:
                        pids.append(int(pid))
                    if port:
                        ports.append(int(port))
        except Exception:
            pass

        kill_result: dict[str, Any] = {}
        if pids or ports:
            try:
                from bot_watcher import kill_codemaker_runner_for_task, load_config

                config_path = os.environ.get("CUBECLAW_CONFIG", "bot.yaml")
                cfg = load_config(config_path)
                kill_result = await asyncio.to_thread(
                    kill_codemaker_runner_for_task,
                    node_id,
                    pids=pids,
                    ports=ports,
                    config=cfg,
                    config_path=config_path,
                )
            except Exception as exc:
                logger.warning("[Pipeline] 手动 success 清理 CodeMaker runner 失败: node=%s err=%s", node_id[:16], exc)
                kill_result = {"error": str(exc), "requested_pids": pids, "requested_ports": ports, "killed_pids": []}

        # 重新读取最新版本
        refreshed_task = await db.get_task(node_id) or task
        refreshed_task["status"] = TaskStatus.SUCCESS.value
        refreshed_task["result"] = refreshed_task.get("result") or result_payload

        # 解锁后继节点
        await scheduler._unlock_dependents(refreshed_task)

        # 确保 batch 状态不是 BLOCKED（如果原来是 BLOCKED，改为 RUNNING，让 scheduler 继续推进）
        if batch.get("status") == BatchStatus.BLOCKED.value:
            await db.update_batch_status(run_id, BatchStatus.RUNNING.value, completed_at=None)

        event_bus = get_event_bus()
        await event_bus.emit({
            "type": "task.success",
            "entity_type": "task",
            "entity_id": node_id,
            "run_id": run_id,
            "actor": cmd.actor or "dashboard",
            "data": {
                "task_type": task.get("type", ""),
                "task_label": task.get("id", "")[:16],
                "runner": "dashboard_manual_success",
                "manual_success": True,
                "reason": reason,
                "previous_status": task.get("status"),
                "updated_runs": updated_runs,
                "kill_result": kill_result,
            },
        })

        # 异步推进 task_runner 以确保后续节点不会因调度器停滞而卡住
        from bot_server.service.task_runner import productive_task_runner
        codemaker_cfg = _load_codemaker_config()
        mock_task_types = set((batch.get("config") or {}).get("mock_task_types") or [])
        runner_deps = TaskRunnerDependencies(db=db, scheduler=scheduler, event_bus=event_bus)
        runner_config = TaskRunnerConfig(
            codemaker_config=codemaker_cfg,
            mock_task_types=mock_task_types,
        )
        track_background_task(asyncio.create_task(productive_task_runner(run_id, runner_deps, runner_config)))

        run = await batch_to_pipeline_run(await db.get_batch(run_id))
        return CommandResult.ok(
            data=run,
            text=(
                f"✅ 人类专家已接管节点 {node_id[:8]}，标记为 SUCCESS"
                f"{f'，已结束 {updated_runs} 条 task_run' if updated_runs else ''}"
                f"{f'，已强杀 {len(kill_result.get('killed_pids') or [])} 个 CodeMaker runner' if kill_result.get('killed_pids') else ''}"
            ),
            events=[{
                "type": "pipeline_run.progress",
                "entity_type": "batch",
                "entity_id": run_id,
                "run_id": run_id,
                "data": run,
            }],
        )

    # ── Scheduler control ──────────────────────────────────────────

    async def handle_pause(cmd: Command) -> CommandResult:
        scheduler.pause()
        return CommandResult.ok(text="⏸️ 调度器已暂停")

    async def handle_resume(cmd: Command) -> CommandResult:
        scheduler.resume()
        return CommandResult.ok(text="▶️ 调度器已恢复")

    return {
        "pipeline_definitions": handle_pipeline_definitions,
        "list_pipeline_runs": handle_list_pipeline_runs,
        "get_pipeline_run": handle_get_pipeline_run,
        "start_pipeline_run": handle_start_pipeline_run,
        "resume_pipeline_from_node": handle_resume_pipeline_from_node,
        "manual_block_node": handle_manual_block_node,
        "manual_success_node": handle_manual_success_node,
        "cancel_pipeline_run": handle_cancel_pipeline_run,
        "pause": handle_pause,
        "resume": handle_resume,
    }
