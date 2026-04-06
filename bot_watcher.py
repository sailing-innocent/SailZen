# -*- coding: utf-8 -*-
# @file bot_watcher.py
# @brief Bot process watcher - manages bot lifecycle and self-updates
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Bot Watcher - Process supervisor for Feishu Bot with self-update support.

This module provides a watcher process that:
1. Monitors the bot process and restarts it on crashes
2. Handles self-update requests (exit code 42)
3. Performs git pull before restart when updating
4. Prevents infinite restart loops

Usage:
    # Start with watcher
    uv run bot_watcher.py -c code.bot.yaml

    # Or directly (no self-update support)
    uv run bot.py -c code.bot.yaml

Exit Codes:
    0: Normal exit, don't restart
    42: Self-update requested, git pull + restart
    1-41, 43+: Error, restart with backoff
"""

import argparse
import json
import subprocess
import sys
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict


EXIT_CODE_UPDATE = 42
EXIT_CODE_NORMAL = 0
MAX_RESTART_ATTEMPTS = 5
RESTART_BACKOFF_SECONDS = [1, 2, 5, 10, 30]  # Exponential backoff


@dataclass
class RestartState:
    """Tracks restart state to prevent infinite loops."""

    restart_count: int = 0
    last_restart_at: Optional[str] = None
    last_exit_code: int = 0
    consecutive_crashes: int = 0
    last_git_pull_at: Optional[str] = None
    git_pull_success: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RestartState":
        return cls(**data)


class BotWatcher:
    """Watches and manages the bot process lifecycle."""

    def __init__(
        self,
        config_path: str = "code.bot.yaml",
        state_file: Optional[Path] = None,
        max_restarts: int = MAX_RESTART_ATTEMPTS,
    ):
        self.config_path = config_path
        self.max_restarts = max_restarts
        self.state_file = (
            state_file or Path.home() / ".sailzen" / "bot_restart_state.json"
        )
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        self.restart_state = self._load_state()
        self._running = False

    def _load_state(self) -> RestartState:
        """Load restart state from file."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                state = RestartState.from_dict(data)
                # Reset counter if last restart was > 1 hour ago
                if state.last_restart_at:
                    last_time = datetime.fromisoformat(state.last_restart_at)
                    if datetime.now() - last_time > timedelta(hours=1):
                        state.restart_count = 0
                        state.consecutive_crashes = 0
                return state
            except Exception as e:
                print(f"[Watcher] Failed to load state: {e}")
        return RestartState()

    def _save_state(self) -> None:
        """Save restart state to file."""
        try:
            self.state_file.write_text(
                json.dumps(self.restart_state.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"[Watcher] Failed to save state: {e}")

    def _perform_git_pull(self) -> bool:
        """Perform git pull to update code."""
        print("[Watcher] Performing git pull...")

        try:
            # Find git repository root
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_root = Path(result.stdout.strip())

            # Perform git pull
            result = subprocess.run(
                ["git", "pull"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )

            self.restart_state.last_git_pull_at = datetime.now().isoformat()

            if result.returncode == 0:
                print(f"[Watcher] Git pull successful")
                if result.stdout:
                    print(f"[Watcher] Output: {result.stdout.strip()}")
                self.restart_state.git_pull_success = True
                return True
            else:
                print(f"[Watcher] Git pull failed: {result.stderr}")
                self.restart_state.git_pull_success = False
                return False

        except Exception as e:
            print(f"[Watcher] Git pull error: {e}")
            self.restart_state.git_pull_success = False
            return False

    def _start_bot(self) -> int:
        """Start the bot process and return its exit code."""
        cmd = [
            sys.executable,
            "bot.py",
            "-c",
            self.config_path,
        ]

        env = os.environ.copy()
        # Tell bot it's being watched (so it can use exit codes)
        env["BOT_WATCHER_ENABLED"] = "1"

        print(f"[Watcher] Starting bot: {' '.join(cmd)}")
        print(f"[Watcher] Restart #{self.restart_state.restart_count + 1}")

        try:
            process = subprocess.Popen(
                cmd,
                env=env,
            )

            # Wait for process to complete
            exit_code = process.wait()
            return exit_code

        except KeyboardInterrupt:
            print("\n[Watcher] Interrupted by user")
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            return EXIT_CODE_NORMAL
        except Exception as e:
            print(f"[Watcher] Failed to start bot: {e}")
            return 1

    def _should_restart(self, exit_code: int) -> bool:
        """Determine if bot should be restarted based on exit code."""
        if exit_code == EXIT_CODE_NORMAL:
            print("[Watcher] Bot exited normally, not restarting")
            return False

        if exit_code == EXIT_CODE_UPDATE:
            print("[Watcher] Bot requested update restart")
            return True

        # Error exit - check restart limits
        self.restart_state.consecutive_crashes += 1

        if self.restart_state.consecutive_crashes >= self.max_restarts:
            print(
                f"[Watcher] Too many consecutive crashes ({self.restart_state.consecutive_crashes}), giving up"
            )
            return False

        return True

    def _get_backoff_delay(self) -> int:
        """Get delay before restart (exponential backoff)."""
        idx = min(
            self.restart_state.consecutive_crashes - 1, len(RESTART_BACKOFF_SECONDS) - 1
        )
        return RESTART_BACKOFF_SECONDS[idx]

    def run(self) -> None:
        """Main watcher loop."""
        print("=" * 60)
        print("Bot Watcher Started")
        print(f"Config: {self.config_path}")
        print(f"State file: {self.state_file}")
        print("=" * 60)

        self._running = True

        while self._running:
            # Update restart state
            self.restart_state.restart_count += 1
            self.restart_state.last_restart_at = datetime.now().isoformat()
            self._save_state()

            # Start bot and wait for it to exit
            exit_code = self._start_bot()
            self.restart_state.last_exit_code = exit_code

            print(f"[Watcher] Bot exited with code: {exit_code}")

            # Determine if we should restart
            if not self._should_restart(exit_code):
                break

            # Handle update restart
            if exit_code == EXIT_CODE_UPDATE:
                # Reset crash counter for intentional restarts
                self.restart_state.consecutive_crashes = 0

                # Perform git pull
                git_success = self._perform_git_pull()
                if not git_success:
                    print(
                        "[Watcher] Warning: git pull failed, will restart with current code"
                    )

                # Brief delay to ensure clean restart
                time.sleep(1)
            else:
                # Error restart with backoff
                delay = self._get_backoff_delay()
                print(f"[Watcher] Waiting {delay}s before restart...")
                time.sleep(delay)

            self._save_state()

        print("[Watcher] Shutting down")
        self._save_state()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bot Watcher - Process supervisor for Feishu Bot"
    )
    parser.add_argument(
        "--config", "-c", default="code.bot.yaml", help="Config file path"
    )
    parser.add_argument(
        "--max-restarts",
        type=int,
        default=MAX_RESTART_ATTEMPTS,
        help=f"Maximum consecutive restarts (default: {MAX_RESTART_ATTEMPTS})",
    )

    args = parser.parse_args()

    watcher = BotWatcher(
        config_path=args.config,
        max_restarts=args.max_restarts,
    )

    try:
        watcher.run()
    except KeyboardInterrupt:
        print("\n[Watcher] Stopped by user")


if __name__ == "__main__":
    main()
