# -*- coding: utf-8 -*-
# @file self_update_orchestrator.py
# @brief Self-update orchestration for Feishu Bot
# @author sailing-innocent
# @date 2026-04-06
# @version 2.0
# ---------------------------------
"""Self-update orchestration for graceful bot updates.

This module handles the self-update flow when running under bot_watcher:
1. Receive update trigger from user command
2. Create state backup
3. Disconnect from Feishu websocket
4. Perform git pull (optional, watcher will also do this)
5. Signal exit code 42 for watcher to restart
6. Watcher performs restart with updated code

Usage:
    Bot runs normally -> User requests update ->
    Bot creates backup -> git pull -> Bot exits(42) ->
    Watcher detects exit 42 -> performs git pull -> restarts bot ->
    New bot restores state from backup

Exit Code Convention:
    0: Normal exit, don't restart
    42: Self-update requested, restart with git pull
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import threading
import time


EXIT_CODE_SELF_UPDATE = 42

class UpdatePhase(Enum):
    """Phases of the self-update process."""

    IDLE = auto()
    DETECTED = auto()
    BACKING_UP = auto()
    DISCONNECTING = auto()
    GIT_PULL = auto()
    READY_TO_RESTART = auto()
    COMPLETED = auto()
    FAILED = auto()


class UpdateTriggerSource(Enum):
    """Sources that can trigger a self-update."""

    OPENCODE_SESSION = "opencode_session"
    MANUAL_COMMAND = "manual_command"
    SCHEDULED = "scheduled"
    CONFIG_CHANGE = "config_change"


@dataclass
class UpdateContext:
    """Context for self-update operation."""

    trigger_source: UpdateTriggerSource
    trigger_reason: str
    initiated_at: str
    initiated_by: Optional[str] = None
    update_metadata: Dict[str, Any] = field(default_factory=dict)
    backup_path: Optional[Path] = None
    git_pull_success: bool = False
    git_pull_output: str = ""
    error_message: Optional[str] = None


@dataclass
class UpdateResult:
    """Result of self-update preparation (not execution)."""

    success: bool
    phase: UpdatePhase
    message: str
    should_exit: bool = False
    exit_code: int = 0
    backup_path: Optional[Path] = None
    git_pull_success: bool = False
    error: Optional[str] = None


class SelfUpdateOrchestrator:
    """Orchestrates the bot self-update process.

    When running under bot_watcher, this orchestrator:
    - Prepares the bot for restart (backup state, disconnect)
    - Optionally performs git pull
    - Signals completion so bot can exit with code 42
    - Watcher then restarts the bot

    When running standalone (no watcher), falls back to legacy mode
    with process spawning.
    """

    def __init__(
        self,
        state_manager: Any,
        feishu_client: Optional[Any] = None,
        workspace_root: Optional[Path] = None,
        uv_executable: str = "uv",
    ):
        """Initialize the update orchestrator.

        Args:
            state_manager: Bot state manager instance
            feishu_client: Feishu websocket client (for disconnection)
            workspace_root: SailZen workspace root directory
            uv_executable: Path to uv executable
        """
        self.state_manager = state_manager
        self.feishu_client = feishu_client
        self.workspace_root = workspace_root or self._find_workspace_root()
        self.uv_executable = uv_executable

        self._phase = UpdatePhase.IDLE
        self._shutdown_event = threading.Event()
        self._update_callbacks: List[Callable[[UpdatePhase, str], None]] = []
        self._current_context: Optional[UpdateContext] = None

        # Check if running under watcher
        self._watcher_enabled = os.environ.get("BOT_WATCHER_ENABLED") == "1"

    def _find_workspace_root(self) -> Path:
        """Find workspace root from current file location."""
        try:
            # Try to find git repo root
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            return Path(result.stdout.strip())
        except Exception:
            # Fallback to script directory
            return Path(__file__).parent.parent.parent.parent

    @property
    def current_phase(self) -> UpdatePhase:
        """Get current update phase."""
        return self._phase

    def register_update_callback(
        self, callback: Callable[[UpdatePhase, str], None]
    ) -> None:
        """Register callback for update phase changes."""
        self._update_callbacks.append(callback)

    async def initiate_self_update(
        self,
        trigger_source: UpdateTriggerSource,
        reason: str,
        initiated_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        perform_git_pull: bool = True,
    ) -> UpdateResult:
        """Initiate the self-update process.

        This prepares the bot for restart by:
        1. Creating state backup
        2. Disconnecting from Feishu
        3. Optionally performing git pull
        4. Returning result with exit code for watcher

        Args:
            trigger_source: What triggered the update
            reason: Human-readable reason for update
            initiated_by: Who/what initiated the update
            metadata: Additional metadata about the update
            perform_git_pull: Whether to perform git pull (watcher will also do this)

        Returns:
            UpdateResult with status and exit code for watcher
        """
        # Check if already updating
        if self._phase != UpdatePhase.IDLE:
            return UpdateResult(
                success=False,
                phase=self._phase,
                message="Update already in progress",
                error="Concurrent update attempted",
            )

        # Create update context
        self._current_context = UpdateContext(
            trigger_source=trigger_source,
            trigger_reason=reason,
            initiated_at=datetime.now().isoformat(),
            initiated_by=initiated_by,
            update_metadata=metadata or {},
        )

        try:
            # Execute update phases
            await self._execute_update_phases(perform_git_pull)

            # Determine exit behavior
            if self._watcher_enabled:
                # Watcher mode: exit with code 42, watcher will restart
                return UpdateResult(
                    success=self._phase == UpdatePhase.READY_TO_RESTART,
                    phase=self._phase,
                    message="Self-update prepared - ready to restart via watcher",
                    should_exit=True,
                    exit_code=EXIT_CODE_SELF_UPDATE,
                    backup_path=self._current_context.backup_path,
                    git_pull_success=self._current_context.git_pull_success,
                )
            else:
                # Standalone mode: spawn new process (legacy behavior)
                await self._phase_spawn_new()
                return UpdateResult(
                    success=self._phase == UpdatePhase.COMPLETED,
                    phase=self._phase,
                    message="Self-update completed (standalone mode)",
                    should_exit=False,
                    exit_code=0,
                    backup_path=self._current_context.backup_path,
                )

        except Exception as e:
            self._set_phase(UpdatePhase.FAILED, str(e))
            return UpdateResult(
                success=False,
                phase=UpdatePhase.FAILED,
                message="Self-update failed with exception",
                error=str(e),
            )

    async def _execute_update_phases(self, perform_git_pull: bool = True) -> None:
        """Execute all update phases in sequence."""
        # Phase 1: Backup current state
        await self._phase_backup()

        # Phase 2: Disconnect from Feishu
        await self._phase_disconnect()

        if self._watcher_enabled:
            # Watcher mode: optionally do git pull, then signal ready
            if perform_git_pull:
                await self._phase_git_pull()
            self._set_phase(UpdatePhase.READY_TO_RESTART, "Ready for watcher restart")
        else:
            # Standalone mode: spawn new process
            await self._phase_spawn_new()

    async def _phase_backup(self) -> None:
        """Phase 1: Backup current bot state."""
        self._set_phase(UpdatePhase.BACKING_UP, "Creating state backup...")

        try:
            backup_path = self.state_manager.create_backup(
                reason="pre_update",
                initiated_by=self._current_context.initiated_by
                if self._current_context
                else None,
            )

            if self._current_context:
                self._current_context.backup_path = backup_path

            self._set_phase(UpdatePhase.BACKING_UP, f"Backup created: {backup_path}")

        except Exception as e:
            raise RuntimeError(f"Failed to create backup: {e}")

    async def _phase_disconnect(self) -> None:
        """Phase 2: Disconnect from Feishu network."""
        self._set_phase(UpdatePhase.DISCONNECTING, "Disconnecting from Feishu...")

        try:
            if self.feishu_client:
                # Gracefully close websocket connection
                if hasattr(self.feishu_client, "close"):
                    await self.feishu_client.close()
                elif hasattr(self.feishu_client, "stop"):
                    self.feishu_client.stop()

                # Wait a moment for disconnection
                await asyncio.sleep(1)

            self._set_phase(UpdatePhase.DISCONNECTING, "Disconnected from Feishu")

        except Exception as e:
            # Log but continue - disconnection failures shouldn't stop update
            self._set_phase(UpdatePhase.DISCONNECTING, f"Disconnection warning: {e}")

    async def _phase_git_pull(self) -> None:
        """Phase: Perform git pull to update code."""
        self._set_phase(UpdatePhase.GIT_PULL, "Pulling latest code...")

        try:
            # Run git pull
            result = subprocess.run(
                ["git", "pull"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
            )

            if self._current_context:
                self._current_context.git_pull_success = result.returncode == 0
                self._current_context.git_pull_output = result.stdout + result.stderr

            if result.returncode == 0:
                self._set_phase(UpdatePhase.GIT_PULL, "Git pull successful")
            else:
                # Git pull failed but we can still try to restart
                self._set_phase(
                    UpdatePhase.GIT_PULL, f"Git pull warning: {result.stderr}"
                )

        except Exception as e:
            # Git pull error but don't fail the update
            if self._current_context:
                self._current_context.git_pull_success = False
                self._current_context.git_pull_output = str(e)
            self._set_phase(UpdatePhase.GIT_PULL, f"Git pull error: {e}")

    async def _phase_spawn_new(self) -> None:
        """Phase (legacy): Spawn new bot process via uv run.

        This is only used when running without watcher (legacy mode).
        """
        self._set_phase(UpdatePhase.READY_TO_RESTART, "Spawning new bot process...")

        try:
            # Build command to spawn new process
            cmd = self._build_spawn_command()

            # Spawn new process
            if sys.platform == "win32":
                creationflags = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                )
                process = subprocess.Popen(
                    cmd,
                    cwd=str(self.workspace_root),
                    creationflags=creationflags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            else:
                process = subprocess.Popen(
                    cmd,
                    cwd=str(self.workspace_root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )

            # Wait a moment to verify process started
            await asyncio.sleep(2)

            # Check if process is still running
            try:
                os.kill(process.pid, 0)
                self._set_phase(
                    UpdatePhase.COMPLETED,
                    f"New process spawned (PID: {process.pid})",
                )
            except ProcessLookupError:
                raise RuntimeError("New process failed to start")

        except Exception as e:
            raise RuntimeError(f"Failed to spawn new process: {e}")

    def _build_spawn_command(self) -> List[str]:
        """Build command to spawn new bot process (legacy mode)."""
        cmd = [
            self.uv_executable,
            "run",
            "python",
            "-m",
            "bot",
        ]

        # Add restore flag for state restoration
        cmd.append("--restore-state")

        return cmd

    def _set_phase(self, phase: UpdatePhase, message: str) -> None:
        """Set current phase and notify callbacks."""
        self._phase = phase

        print(f"[SelfUpdate] {phase.name}: {message}")

        for callback in self._update_callbacks:
            try:
                callback(phase, message)
            except Exception:
                pass

    def should_exit(self) -> bool:
        """Check if bot should exit after update (watcher mode)."""
        return self._phase == UpdatePhase.READY_TO_RESTART and self._watcher_enabled

    def get_exit_code(self) -> int:
        """Get appropriate exit code for watcher."""
        if self._phase == UpdatePhase.READY_TO_RESTART and self._watcher_enabled:
            return EXIT_CODE_SELF_UPDATE
        elif self._phase == UpdatePhase.FAILED:
            return 1
        return 0

    @classmethod
    def check_for_handover(cls) -> Optional[Dict[str, Any]]:
        """Check if this process should restore state from backup.

        Called at startup to detect if we need to restore state.

        Returns:
            Handover data if available, None otherwise
        """
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--restore-state", action="store_true")

        # Only parse known args to avoid conflicts
        args, _ = parser.parse_known_args()

        if args.restore_state:
            # Look for recent backup to restore
            return {"restore_state": True}

        return None


def get_exit_code_for_restart() -> int:
    """Get the exit code that signals watcher to restart with update."""
    return EXIT_CODE_SELF_UPDATE
