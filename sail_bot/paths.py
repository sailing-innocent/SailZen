# -*- coding: utf-8 -*-
# @file paths.py
# @brief Centralized path management for sail_bot data files
# @author sailing-innocent
# @date 2026-04-07
# @version 1.0
# ---------------------------------
"""Centralized path management.

All persistent data files (state, logs, backups) are stored under a single
``data_dir`` directory, defaulting to ``./data/bot/`` relative to the project
root.  This avoids polluting global user directories like ``~/.config/``.

Other modules should import paths from here instead of hardcoding them::

    from sail_bot.paths import (
        DATA_DIR,
        STATE_DIR,
        LOG_DIR,
        BACKUP_DIR,
        SESSIONS_FILE,
        SESSION_STATES_FILE,
        CONTEXTS_FILE,
    )
"""

from pathlib import Path
import os

# ---------------------------------------------------------------------------
# Root resolution
# ---------------------------------------------------------------------------

def _find_project_root() -> Path:
    """Find the SailZen project root (where pyproject.toml lives)."""
    # Start from this file's directory and walk up
    current = Path(__file__).resolve().parent  # sail_bot/
    for _ in range(5):
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # Fallback: use cwd
    return Path.cwd()


PROJECT_ROOT = _find_project_root()

# ---------------------------------------------------------------------------
# Data directory hierarchy
# ---------------------------------------------------------------------------

# Allow override via environment variable
_data_dir_env = os.environ.get("SAIL_BOT_DATA_DIR")
DATA_DIR: Path = Path(_data_dir_env) if _data_dir_env else PROJECT_ROOT / "data" / "bot"

# Sub-directories
STATE_DIR: Path = DATA_DIR / "state"
LOG_DIR: Path = DATA_DIR / "logs"
TASK_LOG_DIR: Path = DATA_DIR / "task_logs"
BACKUP_DIR: Path = DATA_DIR / "backups"
OPENCODE_LOG_DIR: Path = DATA_DIR / "opencode_logs"
OUTPUT_DIR: Path = DATA_DIR / "outputs"  # For long text output files

# State files
SESSIONS_FILE: Path = STATE_DIR / "sessions.json"
SESSION_STATES_FILE: Path = STATE_DIR / "session_states.json"
CONTEXTS_FILE: Path = STATE_DIR / "contexts.json"

# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    """Create all data directories if they don't exist."""
    for d in (STATE_DIR, LOG_DIR, TASK_LOG_DIR, BACKUP_DIR, OPENCODE_LOG_DIR, OUTPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)


# Auto-create on import so files can be written immediately
ensure_dirs()
