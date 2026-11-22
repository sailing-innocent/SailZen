# -*- coding: utf-8 -*-
# @file common.py
# @brief Shared configuration loader, PG binary discovery, safety guardrails, and SSH helpers
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""SailZen 运维脚本共享基础设施。

核心原则：
1. 凭据收敛：生产与本地数据库连接串、API Token 直接从 .env.prod / .env.dev 读取，
   运维脚本仅从 .env.ops（或 .env.prod 兜底）读取 OPS_* 运维参数，不重复存放密码。
2. 零明文泄露：所有日志/报错输出均对 URI 密码、Token 执行打码；子进程通过环境变量
   PGPASSWORD 传递数据库密码，严禁拼接到命令行参数中。
3. 本地护栏：任何破坏性还原/重建库操作强制校验目标 Host 属于 localhost / 127.0.0.1 / ::1。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlparse

from dotenv import dotenv_values

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
LOCAL_PG_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


def configure_console_utf8() -> None:
    """尽量避免 Windows 控制台中文输出乱码。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def mask_uri(uri: str) -> str:
    """将数据库 URI 中的密码替换为 ***，用于日志与诊断输出。"""
    if not uri or "://" not in uri or "@" not in uri:
        return uri
    try:
        head, tail = uri.rsplit("@", 1)
        scheme, rest = head.split("://", 1)
        if ":" in rest:
            user, _pwd = rest.split(":", 1)
            return f"{scheme}://{user}:***@{tail}"
    except ValueError:
        pass
    return uri


def mask_secret(value: str, visible: int = 4) -> str:
    """对 Token/密码做脱敏展示。"""
    if not value:
        return "<unset>"
    if len(value) <= visible * 2:
        return "***"
    return f"{value[:visible]}***{value[-visible:]}"


@dataclass(frozen=True)
class PgConnInfo:
    """解析后的 PostgreSQL 连接信息。"""

    host: str
    port: int
    user: str
    password: str
    database: str
    raw_uri: str

    @property
    def masked_uri(self) -> str:
        return mask_uri(self.raw_uri)

    @property
    def is_local(self) -> bool:
        return self.host.lower() in LOCAL_PG_HOSTS

    def to_pg_env(self, base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """构建 pg_dump / pg_restore / psql 安全环境变量（密码只走 PGPASSWORD）。"""
        env = dict(base_env if base_env is not None else os.environ)
        env["PGCLIENTENCODING"] = "UTF8"
        if self.password:
            env["PGPASSWORD"] = self.password
        else:
            env.pop("PGPASSWORD", None)
        return env

    def base_cli_args(self, database: Optional[str] = None) -> List[str]:
        """返回不含密码的标准 PG CLI 连接参数。"""
        args: List[str] = []
        if self.host:
            args.extend(["-h", self.host])
        if self.port:
            args.extend(["-p", str(self.port)])
        if self.user:
            args.extend(["-U", self.user])
        db_name = database if database is not None else self.database
        if db_name:
            args.extend(["-d", db_name])
        return args


def parse_postgres_uri(uri: str) -> PgConnInfo:
    """解析 postgresql:// 或 postgresql+psycopg:// URI。"""
    if not uri or not uri.strip():
        raise ValueError("POSTGRE_URI 为空，请先在对应的 .env 文件中配置")

    normalized = uri.strip()
    if normalized.startswith("postgresql+psycopg://"):
        normalized = "postgresql://" + normalized[len("postgresql+psycopg://") :]
    elif normalized.startswith("postgres://"):
        normalized = "postgresql://" + normalized[len("postgres://") :]

    parsed = urlparse(normalized)
    if parsed.scheme != "postgresql":
        raise ValueError(f"不支持的 PostgreSQL URI scheme: {parsed.scheme!r}")

    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = unquote(parsed.username) if parsed.username else "postgres"
    password = unquote(parsed.password) if parsed.password else ""
    database = unquote(parsed.path.lstrip("/")) if parsed.path else ""
    if not database:
        raise ValueError(f"POSTGRE_URI 缺少数据库名: {mask_uri(uri)}")

    return PgConnInfo(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        raw_uri=uri.strip(),
    )


def assert_local_pg_target(pg_info: PgConnInfo) -> None:
    """硬安全护栏：破坏性本地还原操作绝不允许指向非本机数据库。"""
    if not pg_info.is_local:
        raise RuntimeError(
            "安全拦截：目标数据库不是本机地址，拒绝执行覆盖/重建操作！"
            f" (target={pg_info.masked_uri}, host={pg_info.host!r})。"
            "请检查 .env.dev 中的 POSTGRE_URI 是否误填为云端生产库地址。"
        )


def read_dotenv_file(path: Path) -> Dict[str, str]:
    """以 UTF-8 读取单个 .env 文件（不污染当前进程 os.environ）。"""
    if not path.exists():
        return {}
    raw = dotenv_values(path, encoding="utf-8")
    return {k: v.strip() for k, v in raw.items() if k and v is not None}


def resolve_repo_path(value: str) -> Path:
    """将相对路径解析为基于仓库根的绝对路径。"""
    p = Path(value)
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


@dataclass(frozen=True)
class OpsConfig:
    """收敛后的统一运维配置（.env.ops + .env.prod + .env.dev + 进程环境变量）。"""

    ops_env_path: Path
    prod_env_path: Path
    dev_env_path: Path
    ops_vars: Dict[str, str]
    prod_vars: Dict[str, str]
    dev_vars: Dict[str, str]

    def get_ops(self, key: str, default: str = "") -> str:
        """优先级：进程环境变量 > .env.ops > .env.prod > 默认值。"""
        for source in (os.environ, self.ops_vars, self.prod_vars):
            val = source.get(key)
            if val is not None and str(val).strip() != "":
                return str(val).strip()
        return default

    def get_ops_bool(self, key: str, default: bool = False) -> bool:
        raw = self.get_ops(key, "true" if default else "false").lower()
        return raw in {"1", "true", "yes", "on"}

    def get_ops_int(self, key: str, default: int) -> int:
        raw = self.get_ops(key, str(default))
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"配置项 {key}={raw!r} 不是合法整数") from exc

    @property
    def backup_mode(self) -> str:
        mode = self.get_ops("OPS_BACKUP_MODE", "direct").lower()
        if mode not in {"direct", "ssh"}:
            raise ValueError(f"OPS_BACKUP_MODE 仅支持 direct 或 ssh，当前值: {mode!r}")
        return mode

    @property
    def backup_dir(self) -> Path:
        return resolve_repo_path(self.get_ops("OPS_BACKUP_DIR", "data/backups"))

    @property
    def backup_keep_days(self) -> int:
        return self.get_ops_int("OPS_BACKUP_KEEP_DAYS", 14)

    @property
    def pg_bin_dir(self) -> Optional[Path]:
        raw = self.get_ops("OPS_PG_BIN_DIR", "")
        return Path(raw).expanduser() if raw else None

    @property
    def ssh_host(self) -> str:
        configured = self.get_ops("OPS_SSH_HOST", "")
        if configured:
            return configured
        # 若未配置 OPS_SSH_HOST，尝试从 .env.prod 的 POSTGRE_URI 提取主机
        uri = self.prod_vars.get("POSTGRE_URI", "")
        if uri:
            try:
                pg = parse_postgres_uri(uri)
                if not pg.is_local:
                    return pg.host
            except ValueError:
                pass
        return ""

    @property
    def ssh_user(self) -> str:
        return self.get_ops("OPS_SSH_USER", "")

    @property
    def ssh_port(self) -> int:
        return self.get_ops_int("OPS_SSH_PORT", 22)

    @property
    def ssh_key(self) -> Optional[Path]:
        raw = self.get_ops("OPS_SSH_KEY", "")
        return Path(raw).expanduser() if raw else None

    @property
    def remote_repo(self) -> str:
        return self.get_ops("OPS_REMOTE_REPO", "/home/ubuntu/repos/SailZen")

    @property
    def remote_site_dist(self) -> str:
        return self.get_ops("OPS_REMOTE_SITE_DIST", f"{self.remote_repo}/site_dist")

    @property
    def remote_data_dir(self) -> str:
        explicit = self.get_ops("OPS_REMOTE_DATA_DIR", "")
        if explicit:
            return explicit.rstrip("/")
        raw = self.prod_vars.get("SERVER_DATA_DIR", "").strip()
        if raw:
            if raw.startswith("/"):
                return raw.rstrip("/")
            return f"{self.remote_repo.rstrip('/')}/{raw.lstrip('./').rstrip('/')}"
        return f"{self.remote_repo.rstrip('/')}/data"

    @property
    def remote_app_releases_dir(self) -> str:
        explicit = self.get_ops("OPS_REMOTE_APP_RELEASES_DIR", "")
        if explicit:
            return explicit.rstrip("/")
        raw = self.prod_vars.get("APP_RELEASES_PATH", "").strip()
        if raw:
            if raw.startswith("/"):
                return raw.rstrip("/")
            return f"{self.remote_repo.rstrip('/')}/{raw.lstrip('./').rstrip('/')}"
        return f"{self.remote_data_dir}/app_releases"

    @property
    def remote_server_service(self) -> str:
        return self.get_ops("OPS_REMOTE_SERVER_SERVICE", "sailzen-server.service")

    @property
    def remote_sailtick_service(self) -> str:
        return self.get_ops("OPS_REMOTE_SAILTICK_SERVICE", "sailtick.service")

    @property
    def remote_uv_bin(self) -> str:
        return self.get_ops("OPS_REMOTE_UV_BIN", "uv")

    @property
    def remote_pnpm_bin(self) -> str:
        return self.get_ops("OPS_REMOTE_PNPM_BIN", "pnpm")

    @property
    def site_build_mode(self) -> str:
        mode = self.get_ops("OPS_SITE_BUILD_MODE", "remote").lower()
        if mode not in {"remote", "local"}:
            raise ValueError(f"OPS_SITE_BUILD_MODE 仅支持 remote 或 local，当前值: {mode!r}")
        return mode

    @property
    def remote_use_sudo(self) -> bool:
        return self.get_ops_bool("OPS_REMOTE_USE_SUDO", True)

    @property
    def remote_pg_db(self) -> str:
        return self.get_ops("OPS_REMOTE_PG_DB", "main")

    @property
    def remote_pg_user(self) -> str:
        return self.get_ops("OPS_REMOTE_PG_USER", "postgres")

    @property
    def remote_sailtick_url(self) -> str:
        return self.get_ops("OPS_REMOTE_SAILTICK_URL", "http://127.0.0.1:9070").rstrip("/")

    def get_prod_pg(self) -> PgConnInfo:
        uri = self.prod_vars.get("POSTGRE_URI", "")
        if not uri:
            raise RuntimeError(
                f"未在 {self.prod_env_path.name} 中找到 POSTGRE_URI，无法获取生产库连接配置"
            )
        return parse_postgres_uri(uri)

    def get_dev_pg(self) -> PgConnInfo:
        backend = self.dev_vars.get("DB_BACKEND", "postgres").lower()
        if backend != "postgres":
            raise RuntimeError(
                f"{self.dev_env_path.name} 当前 DB_BACKEND={backend!r}，不是 postgres。"
                "若需还原 PG 调试库，请先将 .env.dev 切换为 DB_BACKEND=postgres 并配置本机 POSTGRE_URI。"
            )
        uri = self.dev_vars.get("POSTGRE_URI", "")
        if not uri:
            raise RuntimeError(
                f"未在 {self.dev_env_path.name} 中找到 POSTGRE_URI，无法获取本地调试库配置"
            )
        return parse_postgres_uri(uri)

    def get_server_url(self, env_name: str) -> str:
        """推导 dev 或 prod 的 sail_server HTTP 基础地址。"""
        if env_name == "dev":
            port = self.dev_vars.get("SERVER_PORT", "1974")
            return f"http://127.0.0.1:{port}"
        if env_name == "prod":
            explicit = self.get_ops("OPS_REMOTE_PUBLIC_URL", "")
            if explicit:
                return explicit.rstrip("/")
            port = self.prod_vars.get("SERVER_PORT", "1974")
            uri = self.prod_vars.get("POSTGRE_URI", "")
            if uri:
                try:
                    pg = parse_postgres_uri(uri)
                    if not pg.is_local:
                        return f"http://{pg.host}:{port}"
                except ValueError:
                    pass
            raise RuntimeError(
                "无法自动推导云端服务 URL，请在 .env.ops 中设置 OPS_REMOTE_PUBLIC_URL"
            )
        raise ValueError(f"未知环境名: {env_name!r}")

    def get_api_token(self, env_name: str) -> str:
        source = self.prod_vars if env_name == "prod" else self.dev_vars
        return source.get("SAILZEN_API_TOKEN", "")

    def get_api_endpoint(self, env_name: str) -> str:
        source = self.prod_vars if env_name == "prod" else self.dev_vars
        return source.get("API_ENDPOINT", "/api/v1").rstrip("/")


def load_ops_config(ops_env_file: Optional[str] = None) -> OpsConfig:
    """加载 .env.ops、.env.prod、.env.dev（文件不存在时优雅降级为空 dict）。"""
    ops_path = resolve_repo_path(ops_env_file or os.environ.get("OPS_ENV_FILE", ".env.ops"))
    ops_vars = read_dotenv_file(ops_path)

    prod_rel = os.environ.get("OPS_PROD_ENV_FILE") or ops_vars.get("OPS_PROD_ENV_FILE") or ".env.prod"
    dev_rel = os.environ.get("OPS_DEV_ENV_FILE") or ops_vars.get("OPS_DEV_ENV_FILE") or ".env.dev"

    prod_path = resolve_repo_path(prod_rel)
    dev_path = resolve_repo_path(dev_rel)

    return OpsConfig(
        ops_env_path=ops_path,
        prod_env_path=prod_path,
        dev_env_path=dev_path,
        ops_vars=ops_vars,
        prod_vars=read_dotenv_file(prod_path),
        dev_vars=read_dotenv_file(dev_path),
    )


def _pg_version_sort_key(path: Path) -> Tuple[int, str]:
    """从类似 PostgreSQL/19/bin 提取主版本号用于降序优先选择。"""
    match = re.search(r"PostgreSQL[\\/](\d+)", str(path), re.IGNORECASE)
    return (int(match.group(1)) if match else 0, str(path))


def _iter_windows_pg_dirs() -> Iterable[Path]:
    """枚举 Windows 上常见的 PostgreSQL 与 pgAdmin 4 客户端工具目录。"""
    program_files = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]
    local_app_data = os.environ.get("LOCALAPPDATA", "")

    # 1. 本地 PostgreSQL 安装目录（按版本号降序，保证 pg_dump 主版本 >= 云端 PG）
    pg_bins: List[Path] = []
    for base in program_files:
        pg_root = Path(base) / "PostgreSQL"
        if pg_root.is_dir():
            for child in pg_root.iterdir():
                bin_dir = child / "bin"
                if bin_dir.is_dir():
                    pg_bins.append(bin_dir)
    for d in sorted(pg_bins, key=_pg_version_sort_key, reverse=True):
        yield d

    # 2. pgAdmin 4 runtime（随 pgAdmin 4 自带 pg_dump / pg_restore / psql）
    pgadmin_candidates: List[Path] = []
    for base in program_files:
        pgadmin_candidates.append(Path(base) / "pgAdmin 4" / "runtime")
        root = Path(base) / "pgAdmin 4"
        if root.is_dir():
            for child in root.iterdir():
                if (child / "runtime").is_dir():
                    pgadmin_candidates.append(child / "runtime")
    if local_app_data:
        la_root = Path(local_app_data) / "Programs" / "pgAdmin 4"
        pgadmin_candidates.append(la_root / "runtime")
        if la_root.is_dir():
            for child in la_root.iterdir():
                if (child / "runtime").is_dir():
                    pgadmin_candidates.append(child / "runtime")

    for d in pgadmin_candidates:
        if d.is_dir():
            yield d


def find_pg_binary(tool_name: str, preferred_dir: Optional[Path] = None) -> Optional[Path]:
    """查找 pg_dump / pg_restore / psql 可执行文件。

    查找优先级：
    1. 显式配置的 OPS_PG_BIN_DIR
    2. 系统 PATH
    3. Windows 下自动探测 PostgreSQL/<ver>/bin（高版本优先）与 pgAdmin 4/runtime
    """
    exe_names = [f"{tool_name}.exe", tool_name] if os.name == "nt" else [tool_name]

    if preferred_dir:
        for name in exe_names:
            cand = preferred_dir / name
            if cand.is_file():
                return cand

    which_hit = shutil.which(tool_name)
    if which_hit:
        return Path(which_hit)

    if os.name == "nt":
        for directory in _iter_windows_pg_dirs():
            for name in exe_names:
                cand = directory / name
                if cand.is_file():
                    return cand

    return None


def require_pg_binary(tool_name: str, preferred_dir: Optional[Path] = None) -> Path:
    """获取 PG 客户端工具路径，找不到时给出可操作提示。"""
    found = find_pg_binary(tool_name, preferred_dir=preferred_dir)
    if not found:
        raise FileNotFoundError(
            f"未找到 {tool_name} 可执行文件。"
            "请确认已安装 PostgreSQL 或 pgAdmin 4，或在 .env.ops 中设置 OPS_PG_BIN_DIR。"
        )
    return found


def get_pg_binary_version(binary: Path) -> str:
    """获取 PG 工具版本字符串（如 pg_dump (PostgreSQL) 19.0）。"""
    try:
        proc = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if proc.returncode == 0:
            return proc.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return "unknown"


def _ssh_target(cfg: OpsConfig) -> str:
    host = cfg.ssh_host
    if not host:
        raise RuntimeError("未配置 OPS_SSH_HOST，请在 .env.ops 中填写云端 SSH 别名或地址")
    if "@" in host or not cfg.ssh_user:
        return host
    # 若 host 在 ~/.ssh/config 中定义了别名，直接用别名避免覆盖其中的 User 配置
    ssh_config_path = Path.home() / ".ssh" / "config"
    if ssh_config_path.is_file():
        try:
            content = ssh_config_path.read_text(encoding="utf-8", errors="ignore")
            if re.search(rf"^\s*Host\s+.*\b{re.escape(host)}\b", content, re.MULTILINE):
                return host
        except OSError:
            pass
    return f"{cfg.ssh_user}@{host}"


def build_ssh_base_cmd(cfg: OpsConfig, batch_mode: bool = True) -> List[str]:
    """构建 ssh 命令前缀。"""
    cmd = ["ssh"]
    if batch_mode:
        cmd.extend(["-o", "BatchMode=yes", "-o", "ConnectTimeout=10"])
    if cfg.ssh_port and cfg.ssh_port != 22:
        cmd.extend(["-p", str(cfg.ssh_port)])
    if cfg.ssh_key:
        cmd.extend(["-i", str(cfg.ssh_key)])
    cmd.append(_ssh_target(cfg))
    return cmd


def build_scp_base_cmd(cfg: OpsConfig, batch_mode: bool = True) -> Tuple[List[str], str]:
    """构建 scp 命令前缀及远端 target（user@host 或 alias）。"""
    cmd = ["scp"]
    if batch_mode:
        cmd.extend(["-o", "BatchMode=yes", "-o", "ConnectTimeout=10"])
    if cfg.ssh_port and cfg.ssh_port != 22:
        cmd.extend(["-P", str(cfg.ssh_port)])
    if cfg.ssh_key:
        cmd.extend(["-i", str(cfg.ssh_key)])
    return cmd, _ssh_target(cfg)


def run_ssh_command(
    cfg: OpsConfig,
    remote_cmd: str,
    *,
    timeout: int = 120,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    """在云端服务器执行单条 SSH 命令。"""
    cmd = [*build_ssh_base_cmd(cfg), remote_cmd]
    proc = subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(
            f"SSH 命令执行失败 (exit={proc.returncode}): {remote_cmd}\n{detail}"
        )
    return proc


def scp_download(
    cfg: OpsConfig, remote_path: str, local_path: Path, *, timeout: int = 300
) -> None:
    """从云端下载文件到本地。"""
    local_path.parent.mkdir(parents=True, exist_ok=True)
    base, target = build_scp_base_cmd(cfg)
    cmd = [*base, f"{target}:{remote_path}", str(local_path)]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"SCP 下载失败: {(proc.stderr or proc.stdout).strip()}")


def scp_upload(
    cfg: OpsConfig, local_path: Path, remote_path: str, *, timeout: int = 300
) -> None:
    """将本地文件上传到云端。"""
    base, target = build_scp_base_cmd(cfg)
    cmd = [*base, str(local_path), f"{target}:{remote_path}"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"SCP 上传失败: {(proc.stderr or proc.stdout).strip()}")


def format_bytes(size: int) -> str:
    """将字节数格式化为可读字符串。"""
    unit = "B"
    val = float(size)
    for next_unit in ("KB", "MB", "GB"):
        if val >= 1024.0:
            val /= 1024.0
            unit = next_unit
        else:
            break
    return f"{val:.2f} {unit}" if unit != "B" else f"{int(val)} B"
