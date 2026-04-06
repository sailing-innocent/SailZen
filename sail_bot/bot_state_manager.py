# -*- coding: utf-8 -*-
# @file bot_state_manager.py
# @brief Bot state backup and restore management for self-updates
# @author sailing-innocent
# @date 2026-03-29
# @version 1.0
# ---------------------------------
"""Bot state management for graceful self-updates.

This module handles:
- Session state serialization and persistence
- Backup creation before updates
- State restoration after restart
- Cleanup of old backups
"""

import json
import pickle
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager
import os

# Platform-specific locking
if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


@dataclass
class BotSessionState:
    """Complete bot session state for backup/restore."""

    # Session identification
    session_id: str
    created_at: str
    backup_at: str
    version: str = "1.0"

    # Feishu connection state
    chat_contexts: Dict[str, Any] = field(default_factory=dict)
    active_threads: Dict[str, Any] = field(default_factory=dict)
    pending_confirmations: Dict[str, Any] = field(default_factory=dict)

    # Workspace/Session state
    active_sessions: Dict[str, Any] = field(default_factory=dict)
    workspace_states: Dict[str, Any] = field(default_factory=dict)

    # Runtime state
    last_heartbeat: Optional[str] = None
    sequence_number: int = 0

    # Update tracking
    update_reason: Optional[str] = None
    update_initiated_by: Optional[str] = None
    update_initiated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotSessionState":
        """Create from dictionary."""
        return cls(**data)


class BotStateManager:
    """Manages bot state persistence for self-updates."""

    def __init__(
        self,
        backup_dir: Optional[Path] = None,
        max_backups: int = 10,
        backup_ttl_hours: int = 168,  # 7 days
    ):
        """Initialize state manager.

        Args:
            backup_dir: Directory for backup storage (default: ~/.sailzen/bot_backups)
            max_backups: Maximum number of backups to keep
            backup_ttl_hours: Hours before backups expire
        """
        self.backup_dir = backup_dir or Path.home() / ".sailzen" / "bot_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.max_backups = max_backups
        self.backup_ttl_hours = backup_ttl_hours

        # Current session state (in-memory)
        self._current_state: Optional[BotSessionState] = None
        self._session_id: Optional[str] = None

        # Lock file for exclusive access
        self._lock_file: Optional[Path] = None
        self._lock_fd: Optional[Any] = None  # int on Unix, file object on Windows

    def initialize_session(self, session_id: Optional[str] = None) -> BotSessionState:
        """Initialize a new bot session.

        Args:
            session_id: Optional session ID (generated if not provided)

        Returns:
            Initialized session state
        """
        self._session_id = session_id or self._generate_session_id()

        # Check for previous state to restore
        restored = self._try_restore_previous_state()
        if restored:
            self._current_state = restored
            self._current_state.session_id = self._session_id
            self._current_state.backup_at = datetime.now().isoformat()
            return self._current_state

        # Create fresh state
        self._current_state = BotSessionState(
            session_id=self._session_id,
            created_at=datetime.now().isoformat(),
            backup_at=datetime.now().isoformat(),
        )

        return self._current_state

    def get_current_state(self) -> Optional[BotSessionState]:
        """Get current session state."""
        return self._current_state

    def update_chat_context(self, chat_id: str, context: Dict[str, Any]) -> None:
        """Update chat context."""
        if self._current_state:
            self._current_state.chat_contexts[chat_id] = context

    def update_active_session(
        self, session_key: str, session_data: Dict[str, Any]
    ) -> None:
        """Update active session data."""
        if self._current_state:
            self._current_state.active_sessions[session_key] = session_data

    def update_workspace_state(
        self, workspace_slug: str, state: Dict[str, Any]
    ) -> None:
        """Update workspace state."""
        if self._current_state:
            self._current_state.workspace_states[workspace_slug] = state

    def add_pending_confirmation(
        self, confirmation_id: str, data: Dict[str, Any]
    ) -> None:
        """Add pending confirmation."""
        if self._current_state:
            self._current_state.pending_confirmations[confirmation_id] = {
                **data,
                "created_at": datetime.now().isoformat(),
            }

    def remove_pending_confirmation(self, confirmation_id: str) -> None:
        """Remove pending confirmation."""
        if self._current_state:
            self._current_state.pending_confirmations.pop(confirmation_id, None)

    def increment_sequence(self) -> int:
        """Increment and return sequence number."""
        if self._current_state:
            self._current_state.sequence_number += 1
            return self._current_state.sequence_number
        return 0

    def update_heartbeat(self) -> None:
        """Update last heartbeat timestamp."""
        if self._current_state:
            self._current_state.last_heartbeat = datetime.now().isoformat()

    def create_backup(
        self,
        reason: str,
        initiated_by: Optional[str] = None,
    ) -> Path:
        """Create a backup of current state.

        Args:
            reason: Reason for backup (e.g., "pre_update", "periodic")
            initiated_by: Who/what initiated the backup

        Returns:
            Path to backup file

        Raises:
            RuntimeError: If no current state exists
        """
        if not self._current_state:
            raise RuntimeError("No current state to backup")

        # Update backup metadata
        self._current_state.backup_at = datetime.now().isoformat()
        self._current_state.update_reason = reason
        self._current_state.update_initiated_by = initiated_by
        self._current_state.update_initiated_at = datetime.now().isoformat()

        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"bot_state_{timestamp}_{reason}.pkl"

        # Serialize and save with atomic write
        temp_file = backup_file.with_suffix(".tmp")
        try:
            with open(temp_file, "wb") as f:
                pickle.dump(self._current_state, f, protocol=pickle.HIGHEST_PROTOCOL)
            temp_file.rename(backup_file)
        except Exception:
            temp_file.unlink(missing_ok=True)
            raise

        # Also save JSON version for inspection
        json_file = backup_file.with_suffix(".json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self._current_state.to_dict(), f, ensure_ascii=False, indent=2)

        # Cleanup old backups
        self._cleanup_old_backups()

        return backup_file

    def list_backups(self) -> List[Path]:
        """List all available backups."""
        return sorted(
            self.backup_dir.glob("bot_state_*.pkl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def restore_from_backup(
        self, backup_file: Optional[Path] = None
    ) -> Optional[BotSessionState]:
        """Restore state from backup.

        Args:
            backup_file: Specific backup to restore (latest if None)

        Returns:
            Restored state or None if no backup found
        """
        if backup_file is None:
            backups = self.list_backups()
            if not backups:
                return None
            backup_file = backups[0]

        if not backup_file.exists():
            return None

        try:
            with open(backup_file, "rb") as f:
                state = pickle.load(f)

            if isinstance(state, BotSessionState):
                self._current_state = state
                self._session_id = state.session_id
                return state
            elif isinstance(state, dict):
                # Handle legacy format
                self._current_state = BotSessionState.from_dict(state)
                self._session_id = self._current_state.session_id
                return self._current_state
        except Exception as e:
            print(f"Failed to restore from backup {backup_file}: {e}")
            return None

    def cleanup_current_session(self) -> None:
        """Cleanup current session resources."""
        self._current_state = None
        self._session_id = None
        self._release_lock()

    @contextmanager
    def exclusive_access(self):
        """Context manager for exclusive access to state.

        Prevents concurrent state modifications.
        """
        self._acquire_lock()
        try:
            yield self
        finally:
            self._release_lock()

    def _acquire_lock(self) -> None:
        """Acquire exclusive lock for state access (platform-specific)."""
        if self._session_id:
            self._lock_file = self.backup_dir / f"{self._session_id}.lock"

            if sys.platform == "win32":
                # Windows: use file locking via msvcrt
                try:
                    self._lock_fd = open(str(self._lock_file), "w")
                    msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
                    # If we get here, lock was acquired
                    self._lock_fd.write(str(os.getpid()))
                    self._lock_fd.flush()
                except (IOError, OSError):
                    if self._lock_fd:
                        self._lock_fd.close()
                        self._lock_fd = None
                    raise RuntimeError("Another bot instance is already running")
            else:
                # Unix: use fcntl
                self._lock_fd = os.open(str(self._lock_file), os.O_CREAT | os.O_RDWR)
                try:
                    fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (IOError, OSError):
                    os.close(self._lock_fd)
                    self._lock_fd = None
                    raise RuntimeError("Another bot instance is already running")

    def _release_lock(self) -> None:
        """Release exclusive lock (platform-specific)."""
        if sys.platform == "win32":
            if self._lock_fd is not None:
                try:
                    self._lock_fd.close()
                except (IOError, OSError):
                    pass
                finally:
                    self._lock_fd = None
        else:
            if self._lock_fd is not None:
                try:
                    fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                    os.close(self._lock_fd)
                except (IOError, OSError):
                    pass
                finally:
                    self._lock_fd = None

        if self._lock_file:
            try:
                self._lock_file.unlink(missing_ok=True)
            except Exception:
                pass
            self._lock_file = None

    def _try_restore_previous_state(self) -> Optional[BotSessionState]:
        """Try to restore state from previous backup."""
        # Look for state with update_reason indicating a restart
        backups = self.list_backups()

        for backup in backups:
            try:
                with open(backup, "rb") as f:
                    state = pickle.load(f)

                if isinstance(state, BotSessionState):
                    # Check if this was a pre-update backup that wasn't restored
                    if state.update_reason in ("pre_update", "pre_restart"):
                        # Validate backup age
                        backup_time = datetime.fromisoformat(state.backup_at)
                        if datetime.now() - backup_time < timedelta(hours=1):
                            # Mark as restored to prevent double restoration
                            state.update_reason = "restored"
                            return state
                elif isinstance(state, dict):
                    # Legacy format
                    if state.get("update_reason") in ("pre_update", "pre_restart"):
                        backup_time = datetime.fromisoformat(
                            state.get("backup_at", "2000-01-01")
                        )
                        if datetime.now() - backup_time < timedelta(hours=1):
                            state["update_reason"] = "restored"
                            return BotSessionState.from_dict(state)
            except Exception:
                continue

        return None

    def _cleanup_old_backups(self) -> None:
        """Remove old backups based on retention policy."""
        backups = self.list_backups()

        # Remove expired backups
        cutoff = datetime.now() - timedelta(hours=self.backup_ttl_hours)
        for backup in backups:
            try:
                mtime = datetime.fromtimestamp(backup.stat().st_mtime)
                if mtime < cutoff:
                    backup.unlink(missing_ok=True)
                    json_file = backup.with_suffix(".json")
                    json_file.unlink(missing_ok=True)
            except Exception:
                pass

        # Keep only max_backups
        backups = self.list_backups()
        if len(backups) > self.max_backups:
            for backup in backups[self.max_backups :]:
                try:
                    backup.unlink(missing_ok=True)
                    json_file = backup.with_suffix(".json")
                    json_file.unlink(missing_ok=True)
                except Exception:
                    pass

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        import uuid

        return f"bot_{timestamp}_{uuid.uuid4().hex[:8]}"


# Global state manager instance
_state_manager: Optional[BotStateManager] = None


def get_state_manager(
    backup_dir: Optional[Path] = None,
    **kwargs,
) -> BotStateManager:
    """Get or create global state manager."""
    global _state_manager
    if _state_manager is None:
        _state_manager = BotStateManager(backup_dir=backup_dir, **kwargs)
    return _state_manager


def reset_state_manager() -> None:
    """Reset global state manager (for testing)."""
    global _state_manager
    _state_manager = None
