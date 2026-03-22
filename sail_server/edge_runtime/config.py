from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import os
from urllib.parse import urlparse

import yaml


@dataclass
class EdgeRuntimeProject:
    slug: str
    path: str
    label: str = ""


@dataclass
class EdgeRuntimeConfig:
    app_id: str = ""
    app_secret: str = ""
    control_plane_url: str = "http://127.0.0.1:8000/api/v1/remote-dev/control-plane"
    edge_node_key: str = "home-dev-host"
    edge_secret: str = ""
    host_name: str = os.environ.get("COMPUTERNAME", "unknown-host")
    runtime_version: str = "0.1.0"
    heartbeat_interval_seconds: int = 15
    request_timeout_seconds: int = 15
    offline_mode: bool = False
    queue_path: str = "data/control_plane/edge_queue.json"
    projects: list[EdgeRuntimeProject] = field(default_factory=list)


def get_default_edge_config_path() -> str:
    if os.name == "nt":
        return str(Path.home() / "AppData" / "Roaming" / "feishu-agent" / "config.yaml")
    return str(Path.home() / ".config" / "feishu-agent" / "config.yaml")


def load_edge_runtime_config(config_path: str | None = None) -> EdgeRuntimeConfig:
    path = Path(config_path or get_default_edge_config_path())
    config = EdgeRuntimeConfig()

    if not path.exists():
        return config

    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    config.app_id = data.get("app_id", config.app_id)
    config.app_secret = data.get("app_secret", config.app_secret)
    config.control_plane_url = data.get("control_plane_url", config.control_plane_url)
    config.edge_node_key = data.get("edge_node_key", config.edge_node_key)
    config.edge_secret = data.get("edge_secret", config.edge_secret)
    config.host_name = data.get("host_name", config.host_name)
    config.runtime_version = data.get("runtime_version", config.runtime_version)
    config.heartbeat_interval_seconds = data.get(
        "heartbeat_interval_seconds", config.heartbeat_interval_seconds
    )
    config.request_timeout_seconds = data.get(
        "request_timeout_seconds", config.request_timeout_seconds
    )
    config.offline_mode = data.get("offline_mode", config.offline_mode)
    config.queue_path = data.get("queue_path", config.queue_path)
    config.projects = [_load_project(item) for item in data.get("projects", [])]
    _validate_runtime_config(config)
    return config


def _load_project(item: dict[str, Any]) -> EdgeRuntimeProject:
    return EdgeRuntimeProject(
        slug=item.get("slug", "default"),
        path=item.get("path", ""),
        label=item.get("label", item.get("slug", "default")),
    )


def _validate_runtime_config(config: EdgeRuntimeConfig) -> None:
    parsed = urlparse(config.control_plane_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("control_plane_url must be a valid http(s) URL")
    if not config.edge_node_key.strip():
        raise ValueError("edge_node_key is required")
