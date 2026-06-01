"""Runtime path helpers driven by bot.yaml data_dir."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping


DEFAULT_DATA_DIR = "data"


def resolve_config_path(config_path: str | os.PathLike[str] | None = None) -> Path:
    """Return absolute bot.yaml path."""
    raw = config_path or os.environ.get("CUBECLAW_CONFIG", "bot.yaml")
    return Path(raw).expanduser().resolve()


def config_root(config_path: str | os.PathLike[str] | None = None) -> Path:
    """Directory containing bot.yaml."""
    return resolve_config_path(config_path).parent


def resolve_path_from_config(
    path: str | os.PathLike[str] | None,
    *,
    config_path: str | os.PathLike[str] | None = None,
    base_dir: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve path relative to config directory or configured data_dir."""
    raw = Path(path or "").expanduser()
    if raw.is_absolute():
        return raw.resolve()

    base = Path(base_dir).expanduser() if base_dir is not None else config_root(config_path)
    if not base.is_absolute():
        base = config_root(config_path) / base
    return (base / raw).resolve()


def get_data_dir(
    config: Mapping[str, Any] | None = None,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> Path:
    """Return configured data root.

    Priority:
      1. CUBECLAW_DATA_DIR env
      2. bot.yaml top-level data_dir
      3. bot.yaml top-level data.dir
      4. data next to bot.yaml
    """
    env_value = os.environ.get("CUBECLAW_DATA_DIR")
    raw = env_value or DEFAULT_DATA_DIR
    if config:
        data_cfg = config.get("data")
        if isinstance(data_cfg, Mapping):
            raw = data_cfg.get("dir") or raw
        raw = config.get("data_dir") or raw
    return resolve_path_from_config(raw, config_path=config_path)


def path_under_data_dir(
    relative_path: str | os.PathLike[str],
    config: Mapping[str, Any] | None = None,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve relative path under configured data_dir; keep absolute path unchanged."""
    raw = Path(relative_path).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    return (get_data_dir(config, config_path=config_path) / raw).resolve()


def resolve_data_path(
    path: str | os.PathLike[str] | None,
    default_relative: str,
    config: Mapping[str, Any] | None = None,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve configured data artifact path.

    Relative values are interpreted under data_dir. If legacy value starts with
    "data/", strip that prefix so old configs move with data_dir.
    """
    raw_text = str(path or default_relative)
    raw = Path(raw_text).expanduser()
    if raw.is_absolute():
        return raw.resolve()

    parts = raw.parts
    if parts and parts[0].lower() == DEFAULT_DATA_DIR:
        raw = Path(*parts[1:]) if len(parts) > 1 else Path()
    return path_under_data_dir(raw, config, config_path=config_path)
