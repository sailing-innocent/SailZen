"""CubeClaw Bot Server - Litestar HTTP 应用。

重构后的 app.py 职责精简为:
  - App lifecycle (on_startup / on_shutdown)
  - create_app() 工厂
  - 向后兼容 re-export: register_handlers, set_popo_bridge

所有路由/handler/service 已按领域拆分到:
  controller/  — HTTP 路由层
  handler/     — CommandBus 命令处理层
  router/      — Router 组装层
  service/     — 业务逻辑辅助层
  deps.py      — 全局依赖注入
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from litestar import Litestar, Request, Router, get
from litestar.config.cors import CORSConfig
from litestar.response import Redirect
from litestar.static_files import create_static_files_router

from bot_server.database import Database
from bot_server.repositories import DatabaseCompat
from bot_server.scheduler import TaskScheduler
from bot_server.models import make_event_log
from sail.dag.command_bus import CommandBus
from sail.dag.event_bus import EventBus
from sail.paths import resolve_data_path

# ── deps 层 ─────────────────────────────────────────────────────────
from bot_server import deps

# ── handler 注册入口 ────────────────────────────────────────────────
from bot_server.handler.registry import register_handlers  # noqa: F401 — re-export

# ── router 层 ───────────────────────────────────────────────────────
from bot_server.router import api_v1_router

# ── controller: health_check 单独挂在 / ────────────────────────────
from bot_server.controller.health import health_check

# ── 向后兼容: set_popo_bridge ──────────────────────────────────────
set_popo_bridge = deps.set_popo_bridge  # noqa: F401

logger = logging.getLogger(__name__)

DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard" / "dist"
PAGE_ALIASES = (
    "/main",
    "/dag-pipeline",
)


# ── DB Event Logger adapter ─────────────────────────────────────────


async def _db_event_logger(event: dict) -> None:
    """将 EventBus 事件写入 event_logs 表。"""
    db = deps.get_db()
    log_entry = make_event_log(
        event_type=event.get("type", "unknown"),
        entity_type=event.get("entity_type", "system"),
        entity_id=event.get("entity_id", ""),
        new_state=event.get("data"),
        actor=event.get("actor", "system"),
    )
    await db.log_event(log_entry)


# ── App lifecycle ──────────────────────────────────────────────────

_http_client = None  # aiohttp ClientSession for POPO API


async def on_startup() -> None:
    global _http_client

    # ── 配置 ─────────────────────────────────────────────────────────
    config_path = os.environ.get("CUBECLAW_CONFIG", "bot.yaml")
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            _config = yaml.safe_load(f) or {}
    except Exception:
        _config = {}

    db_path = os.environ.get("CUBECLAW_DB") or str(resolve_data_path(
        _config.get("server", {}).get("db"),
        "cubeclaw.db",
        _config,
        config_path=config_path,
    ))
    raw_db = Database(db_path)
    await raw_db.connect()
    db = DatabaseCompat(raw_db)

    scheduler = TaskScheduler(db)
    command_bus = CommandBus()
    event_bus = EventBus()

    # 设置全局单例
    deps.set_db(db)
    deps.set_scheduler(scheduler)
    deps.set_bus(command_bus)
    deps.set_event_bus(event_bus)

    # 连接 EventBus
    event_bus.set_db_logger(_db_event_logger)
    command_bus.on_events(event_bus.emit)

    # ── POPO 通知代理 ──────────────────────────────────────────────
    popo_cfg = _config.get("popo", {})

    # 节点完成通知属于 bot_server 进程内 EventBus 事件，不能依赖独立 POPO Bridge
    # 进程。这里直接复用 samples/popo_demo.py 已验证的 POPO Open API 调用格式。
    app_key = popo_cfg.get("popo_app_key", "") or popo_cfg.get("app_key", "")
    app_secret = popo_cfg.get("popo_app_secret", "") or popo_cfg.get("app_secret", "")
    token_file = str(resolve_data_path(popo_cfg.get("token_file"), "popo_token.json", _config, config_path=config_path))
    default_group = str(popo_cfg.get("default_group_id", "") or "")

    _token_mgr = None
    if app_key and app_secret and default_group:
        from aiohttp import ClientSession, ClientTimeout
        from cube_bot.popo_token_manager import POPOTokenManager
        import asyncio

        _http_client = ClientSession(timeout=ClientTimeout(total=30))
        _token_mgr = POPOTokenManager(app_key, app_secret, token_file)

        async def _popo_sender_proxy(text: str, **kwargs) -> None:
            """直接调用 POPO Open API 发送通知。"""
            target = str(kwargs.get("to") or default_group)
            if not target:
                logger.debug("[POPO Proxy] 未指定目标群，跳过通知: %s", text[:60])
                return

            try:
                token = await asyncio.to_thread(_token_mgr.get_token)

                # 注意：samples/popo_demo.py 已验证 msgType=text + {content: text}
                # 可用。之前这里发送 rich_text，部分机器人配置下会被 POPO 接口拒绝，
                # 导致 DAG 节点完成事件已发出但通知丢失。
                payload = {
                    "receiver": target,
                    "msgType": "text",
                    "message": {"content": text},
                }
                headers = {
                    "Content-Type": "application/json",
                    "Open-Access-Token": token,
                }

                async with _http_client.post(
                    "https://open.popo.netease.com/open-apis/robots/v1/im/send-msg",
                    json=payload, headers=headers,
                ) as resp:
                    result = await resp.json(content_type=None)
                    if result.get("errcode") == 0:
                        logger.info("[POPO Proxy] 通知发送成功: %s", text[:60])
                    else:
                        logger.warning(
                            "[POPO Proxy] 通知发送失败: status=%s errcode=%s errmsg=%s result=%s",
                            resp.status, result.get("errcode"), result.get("errmsg"), result,
                        )
            except Exception as e:
                logger.warning("[POPO Proxy] 通知发送异常: %s", e)

        event_bus.set_popo_sender(_popo_sender_proxy)
        logger.info("POPO 通知代理已配置 (group: %s, token_file: %s)", default_group, token_file)
    elif popo_cfg:
        logger.warning(
            "POPO 通知代理未启用：需要 popo_app_key / popo_app_secret / default_group_id"
        )

    # 注册所有 handler
    register_handlers(command_bus, db, scheduler)

    # ── CodeMaker 进程管理器 ─────────────────────────────────────────
    cm_cfg = _config.get("codemaker", {})
    cm_base_port = cm_cfg.get("base_port", 4096)
    cm_projects = cm_cfg.get("projects") or []
    cm_state_file = resolve_data_path(cm_cfg.get("state_file"), "bot/state/sessions.json", _config, config_path=config_path)
    cm_log_dir = resolve_data_path(cm_cfg.get("log_dir"), "bot/codemaker_logs", _config, config_path=config_path)
    if "transcript_dir" in cm_cfg:
        cm_cfg["transcript_dir"] = str(resolve_data_path(cm_cfg.get("transcript_dir"), "transcripts", _config, config_path=config_path))
    from sail.opencode.process_manager import OpenCodeProcessManager
    codemaker_mgr = OpenCodeProcessManager(
        base_port=cm_base_port,
        state_file=cm_state_file,
        log_dir=cm_log_dir,
        projects=cm_projects,
    )
    deps.set_codemaker_mgr(codemaker_mgr)

    logger.info("CubeClaw Bot Server started (CommandBus: %d commands)",
                len(command_bus.registered_commands))


async def on_shutdown() -> None:
    global _http_client
    cancelled = await deps.cancel_background_tasks()
    if cancelled:
        logger.info("Cancelled %d CubeClaw background task(s)", cancelled)
    try:
        codemaker_mgr = deps.get_codemaker_mgr()
        if codemaker_mgr:
            stopped = codemaker_mgr.stop_all()
            if stopped:
                logger.info("Stopped %d managed CodeMaker process(es)", stopped)
        else:
            # fallback: 尝试用无参实例清理（可能无效，但聊胜于无）
            from sail.opencode.process_manager import OpenCodeProcessManager
            stopped = OpenCodeProcessManager().stop_all()
            if stopped:
                logger.info("Stopped %d managed CodeMaker process(es) [fallback]", stopped)
    except Exception as exc:
        logger.warning("Stop managed CodeMaker processes failed: %s", exc)
    if _http_client:
        await _http_client.close()
        _http_client = None
    db = deps.get_db()
    if db:
        await db.close()
    logger.info("CubeClaw Bot Server stopped")


# ── Create App ──────────────────────────────────────────────────────


def create_page_redirect_handler(path: str):
    """创建 Dashboard 页面别名重定向 handler。"""

    @get(path, include_in_schema=False)
    async def redirect_handler(request: Request) -> Redirect:
        return Redirect(
            path="/",
            query_params={**request.query_params, "path": path.lstrip("/")},
        )

    return redirect_handler


def create_app() -> Litestar:
    """创建 Litestar 应用实例。

    参照 SailZen 的架构: 将 API 路由和静态文件 router 分开注册，
    避免 StaticFilesConfig(html_mode=True) 的 catch-all 拦截 SSE 等动态路由。
    """
    dashboard_dir = DASHBOARD_DIR

    # ── Static / SPA Router ─────────────────────────────────────────
    base_handlers = [health_check]
    if dashboard_dir.exists():
        base_handlers.append(
            create_static_files_router(
                directories=[dashboard_dir],
                path="/",
                html_mode=True,
                include_in_schema=False,
            )
        )
        base_handlers.extend(create_page_redirect_handler(alias) for alias in PAGE_ALIASES)

    base_router = Router(
        path="/",
        route_handlers=base_handlers,
    )

    return Litestar(
        route_handlers=[base_router, api_v1_router],
        on_startup=[on_startup],
        on_shutdown=[on_shutdown],
        cors_config=CORSConfig(
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        debug=os.environ.get("DEBUG", "0") == "1",
    )


app = create_app()
