# -*- coding: utf-8 -*-
# @file config.py
# @brief SailTick 配置加载（sailtick.yaml + SAILTICK_* 环境变量）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 配置系统。

配置源优先级（从高到低）:
  1. 环境变量（SAILTICK_*）
  2. sailtick.yaml 文件
  3. 内置默认值

修复自旧 autonomous_agent/config.py 的问题:
  - 路径解析统一基于配置文件所在目录（repo root），不可配时回退 cwd
  - LLM key 支持 ${VAR} 引用环境变量
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_NAME = "sailtick.yaml"


# ═══════════════════════════════════════════════════════════════════════
#  数据类
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class LLMProviderConfig:
    """单个 LLM provider 配置。"""

    api_key: str = ""
    model: str = ""
    base_url: str = ""


@dataclass
class LLMConfig:
    """LLM 网关配置 + 成本护栏。"""

    providers: Dict[str, LLMProviderConfig] = field(default_factory=dict)
    default: str = "deepseek"
    per_tick_token_cap: int = 200_000
    daily_token_cap: int = 1_000_000


@dataclass
class SailServerConfig:
    """sail_server HTTP API 配置（票据/健康数据/推送联动）。"""

    api_base: str = "http://127.0.0.1:1974/api/v1"
    auth_token: str = ""


@dataclass
class QuietHoursConfig:
    """安静时段（非 urgent 不推送）。"""

    start: int = 23
    end: int = 8


@dataclass
class TickConfig:
    """Tick 排程配置。"""

    hours: List[int] = field(default_factory=lambda: [0, 6, 12, 18])
    work_budget_minutes: int = 180
    scan_budget_minutes: int = 15
    plan_budget_minutes: int = 20
    handoff_budget_minutes: int = 10


@dataclass
class SelfDevConfig:
    """自我开发安全协议配置（D5）。"""

    repo_dir: str = ""
    branch: str = "agent/sailtick-dev"
    whitelist_dirs: List[str] = field(
        default_factory=lambda: ["sailtick", "tests/sailtick", "doc/design/agent-system"]
    )
    protected_paths: List[str] = field(
        default_factory=lambda: ["data", ".env", ".env.dev", ".env.prod", ".env.debug", ".git"]
    )


@dataclass
class NotifyConfig:
    """通知配置。"""

    quiet_hours: QuietHoursConfig = field(default_factory=QuietHoursConfig)
    push_enabled: bool = True  # 经 sail_server reminder WS 推送手机
    dedup_window_seconds: int = 3600


@dataclass
class CanaryConfig:
    """灰度开关与熔断配置（off / shadow / canary / live）。"""

    mode: str = "live"
    allow_push: bool = True
    allow_self_dev: bool = True
    max_tickets_per_tick: int = 2
    allowed_slots: List[str] = field(default_factory=list)
    ticket_title_prefix: str = ""
    auto_downgrade_failures: int = 3
    auto_downgrade_target: str = "shadow"


@dataclass
class SailTickConfig:
    """SailTick 根配置。"""

    name: str = "sailtick"
    data_dir: str = "data/sailtick"
    db_path: str = "data/sailtick/db/sailtick.db"
    log_dir: str = "logs/sailtick"
    api_port: int = 9070
    api_host: str = "127.0.0.1"
    timezone: str = "Asia/Shanghai"
    heartbeat_interval: int = 30
    inbox_poll_seconds: int = 600

    tick: TickConfig = field(default_factory=TickConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    sail_server: SailServerConfig = field(default_factory=SailServerConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    self_dev: SelfDevConfig = field(default_factory=SelfDevConfig)
    canary: CanaryConfig = field(default_factory=CanaryConfig)

    # 配置文件所在目录（用于解析相对资源，如 prompts/ pipelines/）
    config_dir: str = ""

    @property
    def handoffs_dir(self) -> str:
        return str(Path(self.data_dir) / "handoffs")

    @property
    def pipelines_dir(self) -> str:
        return str(Path(self.config_dir) / "sailtick" / "pipelines") if self.config_dir else ""

    @property
    def prompts_dir(self) -> str:
        return str(Path(self.config_dir) / "sailtick" / "prompts") if self.config_dir else ""


# ═══════════════════════════════════════════════════════════════════════
#  加载逻辑
# ═══════════════════════════════════════════════════════════════════════


def _resolve_env_vars(value: Any) -> Any:
    """解析字符串中的 ${VAR} 或 $VAR 为环境变量值。"""
    if not isinstance(value, str):
        return value

    def replacer(match: re.Match) -> str:
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, "")

    return re.sub(r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)", replacer, value)


def _find_config(path: Optional[str]) -> Path:
    """定位配置文件：显式路径 > SAILTICK_CONFIG > cwd 向上查找。"""
    config_path = Path(path or os.environ.get("SAILTICK_CONFIG", DEFAULT_CONFIG_NAME))
    if not config_path.is_absolute():
        cwd = Path.cwd()
        candidates = [cwd / config_path]
        for parent in cwd.parents:
            candidates.append(parent / config_path)
        for c in candidates:
            if c.exists():
                config_path = c
                break
    return config_path


def _env_override(cfg: SailTickConfig) -> None:
    """SAILTICK_* 环境变量覆盖。"""
    if v := os.environ.get("SAILTICK_DB_PATH"):
        cfg.db_path = v
    if v := os.environ.get("SAILTICK_DATA_DIR"):
        cfg.data_dir = v
    if v := os.environ.get("SAILTICK_LOG_DIR"):
        cfg.log_dir = v
    if v := os.environ.get("SAILTICK_API_PORT"):
        cfg.api_port = int(v)
    if v := os.environ.get("SAILTICK_API_HOST"):
        cfg.api_host = v
    if v := os.environ.get("SAILTICK_TIMEZONE"):
        cfg.timezone = v
    if v := os.environ.get("SAIL_SERVER_URL"):
        cfg.sail_server.api_base = v.rstrip("/") + "/api/v1"
    if v := os.environ.get("SAILZEN_API_TOKEN"):
        cfg.sail_server.auth_token = v
    if v := os.environ.get("SAILTICK_SELF_DEV_REPO"):
        cfg.self_dev.repo_dir = v
    if v := os.environ.get("SAILTICK_MODE"):
        cfg.canary.mode = v.strip().lower()
    if v := os.environ.get("SAILTICK_CANARY_PREFIX"):
        cfg.canary.ticket_title_prefix = v
    if v := os.environ.get("SAILTICK_CANARY_SLOTS"):
        cfg.canary.allowed_slots = [s.strip() for s in v.split(",") if s.strip()]
    if v := os.environ.get("SAILTICK_LLM_DEFAULT"):
        cfg.llm.default = v.strip().lower()
    # LLM key 直挂 provider（同时兼容 KIMI_API_KEY / MOONSHOT_API_KEY / DEEPSEEK_API_KEY）
    kimi_key = os.environ.get("KIMI_API_KEY") or os.environ.get("MOONSHOT_API_KEY")
    if kimi_key:
        kimi_cfg = cfg.llm.providers.setdefault("kimi", LLMProviderConfig())
        if not kimi_cfg.api_key:
            kimi_cfg.api_key = kimi_key
        if not kimi_cfg.model:
            kimi_cfg.model = os.environ.get("KIMI_MODEL") or os.environ.get("MOONSHOT_MODEL") or ""
        if not kimi_cfg.base_url:
            kimi_cfg.base_url = (
                os.environ.get("KIMI_API_BASE") or os.environ.get("MOONSHOT_API_BASE") or ""
            )
    if deepseek_key := os.environ.get("DEEPSEEK_API_KEY"):
        ds_cfg = cfg.llm.providers.setdefault("deepseek", LLMProviderConfig())
        if not ds_cfg.api_key:
            ds_cfg.api_key = deepseek_key
        if not ds_cfg.model and os.environ.get("DEEPSEEK_MODEL"):
            ds_cfg.model = os.environ["DEEPSEEK_MODEL"]


def load_config(path: Optional[str] = None) -> SailTickConfig:
    """从 sailtick.yaml 加载配置。"""
    config_path = _find_config(path)
    config_dir = str(config_path.parent) if config_path.exists() else str(Path.cwd())

    raw: Dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        logger.info("Loaded sailtick config from %s", config_path)
    else:
        logger.warning("sailtick.yaml not found: %s, using defaults", config_path)

    root = raw.get("sailtick", {})

    llm_raw = root.get("llm", {})
    providers = {
        name: LLMProviderConfig(
            api_key=_resolve_env_vars(p.get("api_key", "")),
            model=p.get("model", ""),
            base_url=p.get("base_url", ""),
        )
        for name, p in llm_raw.get("providers", {}).items()
    }

    server_raw = root.get("sail_server", {})
    notify_raw = root.get("notify", {})
    quiet_raw = notify_raw.get("quiet_hours", {})
    tick_raw = root.get("tick", {})
    dev_raw = root.get("self_dev", {})
    canary_raw = root.get("canary", {})

    cfg = SailTickConfig(
        name=root.get("name", "sailtick"),
        data_dir=root.get("data_dir", "data/sailtick"),
        db_path=root.get("db_path", "data/sailtick/db/sailtick.db"),
        log_dir=root.get("log_dir", "logs/sailtick"),
        api_port=root.get("api_port", 9070),
        api_host=root.get("api_host", "127.0.0.1"),
        timezone=root.get("timezone", "Asia/Shanghai"),
        heartbeat_interval=root.get("heartbeat_interval", 30),
        inbox_poll_seconds=root.get("inbox_poll_seconds", 600),
        tick=TickConfig(
            hours=tick_raw.get("hours", [0, 6, 12, 18]),
            work_budget_minutes=tick_raw.get("work_budget_minutes", 180),
            scan_budget_minutes=tick_raw.get("scan_budget_minutes", 15),
            plan_budget_minutes=tick_raw.get("plan_budget_minutes", 20),
            handoff_budget_minutes=tick_raw.get("handoff_budget_minutes", 10),
        ),
        llm=LLMConfig(
            providers=providers,
            default=llm_raw.get("default", "deepseek"),
            per_tick_token_cap=llm_raw.get("per_tick_token_cap", 200_000),
            daily_token_cap=llm_raw.get("daily_token_cap", 1_000_000),
        ),
        sail_server=SailServerConfig(
            api_base=server_raw.get("api_base", "http://127.0.0.1:1974/api/v1"),
            auth_token=_resolve_env_vars(server_raw.get("auth_token", "")),
        ),
        notify=NotifyConfig(
            quiet_hours=QuietHoursConfig(
                start=quiet_raw.get("start", 23),
                end=quiet_raw.get("end", 8),
            ),
            push_enabled=notify_raw.get("push_enabled", True),
            dedup_window_seconds=notify_raw.get("dedup_window_seconds", 3600),
        ),
        self_dev=SelfDevConfig(
            repo_dir=dev_raw.get("repo_dir", ""),
            branch=dev_raw.get("branch", "agent/sailtick-dev"),
            whitelist_dirs=dev_raw.get(
                "whitelist_dirs", ["sailtick", "tests/sailtick", "doc/design/agent-system"]
            ),
            protected_paths=dev_raw.get(
                "protected_paths",
                ["data", ".env", ".env.dev", ".env.prod", ".env.debug", ".git"],
            ),
        ),
        canary=CanaryConfig(
            mode=canary_raw.get("mode", "live"),
            allow_push=canary_raw.get("allow_push", True),
            allow_self_dev=canary_raw.get("allow_self_dev", True),
            max_tickets_per_tick=canary_raw.get("max_tickets_per_tick", 2),
            allowed_slots=list(canary_raw.get("allowed_slots", [])),
            ticket_title_prefix=canary_raw.get("ticket_title_prefix", ""),
            auto_downgrade_failures=canary_raw.get("auto_downgrade_failures", 3),
            auto_downgrade_target=canary_raw.get("auto_downgrade_target", "shadow"),
        ),
        config_dir=config_dir,
    )

    _env_override(cfg)

    # 相对路径统一以配置文件目录为根解析为绝对路径
    for attr in ("data_dir", "db_path", "log_dir"):
        p = Path(getattr(cfg, attr))
        if not p.is_absolute():
            setattr(cfg, attr, str((Path(config_dir) / p).resolve()))
    if cfg.self_dev.repo_dir and not Path(cfg.self_dev.repo_dir).is_absolute():
        cfg.self_dev.repo_dir = str((Path(config_dir) / cfg.self_dev.repo_dir).resolve())

    return cfg
