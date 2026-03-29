# -*- coding: utf-8 -*-
# @file self_update_orchestrator.py
# @brief Self-update orchestration for Feishu Bot
# @author sailing-innocent
# @date 2026-03-29
# @version 1.0
# ---------------------------------
"""Self-update orchestration for graceful bot updates.

This module handles the complete self-update flow:
1. Detect update trigger (from SailZen OpenCode session)
2. Backup current state
3. Disconnect from network (Feishu websocket)
4. Launch new Python session with uv run
5. Cleanup and close gracefully
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum, auto
import threading
import time


class UpdatePhase(Enum):
    """Phases of the self-update process."""

    IDLE = auto()
    DETECTED = auto()
    BACKING_UP = auto()
    DISCONNECTING = auto()
    SPAWNING_NEW = auto()
    HANDING_OVER = auto()
    CLEANING_UP = auto()
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
    new_process_pid: Optional[int] = None
    error_message: Optional[str] = None


@dataclass
class UpdateResult:
    """Result of self-update operation."""

    success: bool
    phase: UpdatePhase
    message: str
    new_pid: Optional[int] = None
    backup_path: Optional[Path] = None
    error: Optional[str] = None


class SelfUpdateOrchestrator:
    """Orchestrates the bot self-update process.

    This class manages the complete flow of self-updating:
    - Receiving update trigger from SailZen OpenCode session
    - Creating state backup
    - Gracefully disconnecting from Feishu
    - Spawning new process via uv run
    - Handing over state
    - Cleaning up old process
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
        self.workspace_root = workspace_root or Path("D:/ws/repos/SailZen")
        self.uv_executable = uv_executable

        self._phase = UpdatePhase.IDLE
        self._shutdown_event = threading.Event()
        self._update_callbacks: List[Callable[[UpdatePhase, str], None]] = []
        self._current_context: Optional[UpdateContext] = None

        # Graceful shutdown timeout
        self._shutdown_timeout_seconds = 30

        # Handover file for new process
        self._handover_file: Optional[Path] = None

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
    ) -> UpdateResult:
        """Initiate the self-update process.

        This is the main entry point for bot self-updates.

        Args:
            trigger_source: What triggered the update
            reason: Human-readable reason for update
            initiated_by: Who/what initiated the update
            metadata: Additional metadata about the update

        Returns:
            UpdateResult with status and details
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
            await self._execute_update_phases()

            return UpdateResult(
                success=self._phase == UpdatePhase.COMPLETED,
                phase=self._phase,
                message="Self-update completed successfully"
                if self._phase == UpdatePhase.COMPLETED
                else "Self-update failed",
                new_pid=self._current_context.new_process_pid,
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

    async def _execute_update_phases(self) -> None:
        """Execute all update phases in sequence."""
        # Phase 1: Backup current state
        await self._phase_backup()

        # Phase 2: Disconnect from Feishu
        await self._phase_disconnect()

        # Phase 3: Spawn new process
        await self._phase_spawn_new()

        # Phase 4: Hand over state
        await self._phase_handover()

        # Phase 5: Cleanup
        await self._phase_cleanup()

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

    async def _phase_spawn_new(self) -> None:
        """Phase 3: Spawn new bot process via uv run."""
        self._set_phase(UpdatePhase.SPAWNING_NEW, "Spawning new bot process...")

        try:
            # Create handover file with context
            self._handover_file = self._create_handover_file()

            # Build command to spawn new process
            cmd = self._build_spawn_command()

            # Spawn new process
            if sys.platform == "win32":
                # Windows: use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS
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
                # Unix: use nohup and disown pattern
                process = subprocess.Popen(
                    cmd,
                    cwd=str(self.workspace_root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )

            if self._current_context:
                self._current_context.new_process_pid = process.pid

            # Wait a moment to verify process started
            await asyncio.sleep(2)

            # Check if process is still running
            try:
                os.kill(process.pid, 0)  # Signal 0 checks if process exists
                self._set_phase(
                    UpdatePhase.SPAWNING_NEW,
                    f"New process spawned (PID: {process.pid})",
                )
            except ProcessLookupError:
                raise RuntimeError("New process failed to start")

        except Exception as e:
            raise RuntimeError(f"Failed to spawn new process: {e}")

    async def _phase_handover(self) -> None:
        """Phase 4: Hand over state to new process."""
        self._set_phase(UpdatePhase.HANDING_OVER, "Handing over to new process...")

        try:
            # Write handover signal file
            if self._handover_file:
                handover_complete = self._handover_file.with_suffix(".complete")
                handover_complete.write_text(
                    json.dumps(
                        {
                            "old_pid": os.getpid(),
                            "new_pid": self._current_context.new_process_pid
                            if self._current_context
                            else None,
                            "handover_at": datetime.now().isoformat(),
                        }
                    ),
                    encoding="utf-8",
                )

            # Wait for new process to signal readiness
            await self._wait_for_new_process_ready()

            self._set_phase(UpdatePhase.HANDING_OVER, "Handover complete")

        except Exception as e:
            # Handover failure is serious but we should still try cleanup
            self._set_phase(UpdatePhase.HANDING_OVER, f"Handover warning: {e}")

    async def _phase_cleanup(self) -> None:
        """Phase 5: Cleanup and graceful shutdown."""
        self._set_phase(UpdatePhase.CLEANING_UP, "Cleaning up...")

        try:
            # Mark current state as handed over
            if self._current_context and self._current_context.backup_path:
                # Create a marker file indicating handover
                marker = self._current_context.backup_path.with_suffix(".handed_over")
                marker.write_text(
                    json.dumps(
                        {
                            "old_pid": os.getpid(),
                            "new_pid": self._current_context.new_process_pid,
                            "handover_at": datetime.now().isoformat(),
                        }
                    ),
                    encoding="utf-8",
                )

            # Cleanup resources
            self.state_manager.cleanup_current_session()

            # Signal shutdown
            self._shutdown_event.set()

            self._set_phase(
                UpdatePhase.COMPLETED, "Self-update completed - ready to exit"
            )

        except Exception as e:
            self._set_phase(UpdatePhase.CLEANING_UP, f"Cleanup warning: {e}")

    def _create_handover_file(self) -> Path:
        """Create handover file for new process."""
        handover_dir = Path(tempfile.gettempdir()) / "sailzen_bot_handover"
        handover_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        handover_file = handover_dir / f"handover_{timestamp}_{os.getpid()}.json"

        handover_data = {
            "old_pid": os.getpid(),
            "workspace_root": str(self.workspace_root),
            "backup_path": str(self._current_context.backup_path)
            if self._current_context and self._current_context.backup_path
            else None,
            "trigger_source": self._current_context.trigger_source.value
            if self._current_context
            else None,
            "trigger_reason": self._current_context.trigger_reason
            if self._current_context
            else None,
            "initiated_at": self._current_context.initiated_at
            if self._current_context
            else None,
            "handover_created_at": datetime.now().isoformat(),
        }

        handover_file.write_text(
            json.dumps(handover_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return handover_file

    def _build_spawn_command(self) -> List[str]:
        """Build command to spawn new bot process."""
        # Get current Python executable info
        python_path = sys.executable

        # Build uv run command
        cmd = [
            self.uv_executable,
            "run",
            "--python",
            python_path,
            "python",
            "-m",
            "sail_server.feishu_gateway.bot_runtime",
        ]

        # Add handover file argument
        if self._handover_file:
            cmd.extend(["--handover-file", str(self._handover_file)])

        # Add restore flag
        cmd.append("--restore-state")

        return cmd

    async def _wait_for_new_process_ready(self, timeout_seconds: int = 30) -> bool:
        """Wait for new process to signal readiness."""
        if not self._handover_file:
            return False

        ready_file = self._handover_file.with_suffix(".ready")

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if ready_file.exists():
                return True
            await asyncio.sleep(0.5)

        # Timeout - but don't fail, new process might still be starting
        return False

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
        """Check if bot should exit after update."""
        return self._phase == UpdatePhase.COMPLETED

    def get_exit_code(self) -> int:
        """Get appropriate exit code."""
        if self._phase == UpdatePhase.COMPLETED:
            return 0  # Clean exit for handover
        elif self._phase == UpdatePhase.FAILED:
            return 1  # Error exit
        return 0

    @classmethod
    def check_for_handover(cls) -> Optional[Dict[str, Any]]:
        """Check if this process was spawned as part of a handover.

        This should be called at startup to detect if we need to restore state.

        Returns:
            Handover data if available, None otherwise
        """
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--handover-file", type=str)
        parser.add_argument("--restore-state", action="store_true")

        # Only parse known args to avoid conflicts
        args, _ = parser.parse_known_args()

        if args.handover_file and Path(args.handover_file).exists():
            try:
                handover_data = json.loads(
                    Path(args.handover_file).read_text(encoding="utf-8")
                )

                # Signal readiness
                ready_file = Path(args.handover_file).with_suffix(".ready")
                ready_file.write_text(
                    json.dumps(
                        {
                            "pid": os.getpid(),
                            "ready_at": datetime.now().isoformat(),
                        }
                    ),
                    encoding="utf-8",
                )

                return handover_data
            except Exception as e:
                print(f"[SelfUpdate] Failed to read handover file: {e}")

        return None
