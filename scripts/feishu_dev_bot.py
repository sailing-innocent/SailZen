# -*- coding: utf-8 -*-
# @file feishu_dev_bot.py
# @brief Standalone Feishu Dev Bot launcher for Phase 0 MVP
# @author sailing-innocent
# @date 2026-03-29
# @version 1.0
# ---------------------------------
"""Standalone launcher for SailZen Feishu Dev Bot (Phase 0 MVP).

This script provides:
- Easy startup for the Feishu bot
- Environment configuration
- Integration with control plane
- Self-update trigger from OpenCode session

Usage:
    # Start normally
    uv run python scripts/feishu_dev_bot.py

    # Start and trigger self-update from OpenCode
    uv run python scripts/feishu_dev_bot.py --from-opencode --update-trigger

    # Mock mode (without real Feishu credentials)
    uv run python scripts/feishu_dev_bot.py --mock
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add sail_server to path
sys.path.insert(0, str(Path(__file__).parent.parent / "sail_server"))

from sail_server.feishu_gateway.bot_runtime import SailZenBotRuntime
from sail_server.feishu_gateway.self_update_orchestrator import UpdateTriggerSource


def load_env_file(env_file: Path) -> dict:
    """Load environment variables from .env file."""
    env_vars = {}
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip("\"'")
    return env_vars


def setup_environment():
    """Setup environment from .env files."""
    # Load from .env files in order of precedence
    env_files = [
        Path(".env"),
        Path(".env.local"),
        Path(".env.feishu"),
    ]

    for env_file in env_files:
        if env_file.exists():
            print(f"[Setup] Loading environment from {env_file}")
            env_vars = load_env_file(env_file)
            for key, value in env_vars.items():
                if key not in os.environ:
                    os.environ[key] = value


def create_default_config():
    """Create default configuration file if not exists."""
    config_file = Path(".env.feishu")
    if not config_file.exists():
        print(f"[Setup] Creating default config: {config_file}")
        config_content = """# Feishu Bot Configuration
# Get these from your Feishu app console: https://open.feishu.cn/app

FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Override workspace root
# SAILZEN_WORKSPACE_ROOT=D:/ws/repos/SailZen
"""
        config_file.write_text(config_content, encoding="utf-8")
        print(f"[Setup] Please edit {config_file} with your Feishu credentials")
        return False
    return True


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SailZen Feishu Dev Bot - Phase 0 MVP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start bot normally
  uv run python scripts/feishu_dev_bot.py
  
  # Start from OpenCode session and trigger update
  uv run python scripts/feishu_dev_bot.py --from-opencode --update-trigger
  
  # Mock mode (no real Feishu connection)
  uv run python scripts/feishu_dev_bot.py --mock
  
  # Start with specific config
  uv run python scripts/feishu_dev_bot.py --config ./my-config.env
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Path to environment config file",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode without real Feishu connection",
    )
    parser.add_argument(
        "--from-opencode",
        action="store_true",
        help="Indicate this was started from OpenCode session",
    )
    parser.add_argument(
        "--update-trigger",
        action="store_true",
        help="Trigger self-update immediately (for testing)",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore from previous backup",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show bot status and exit",
    )

    args = parser.parse_args()

    # Show status and exit
    if args.status:
        show_status()
        return

    # Load configuration
    if args.config:
        env_vars = load_env_file(Path(args.config))
        for key, value in env_vars.items():
            os.environ[key] = value
    else:
        create_default_config()
        setup_environment()

    # Check credentials
    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")

    if args.mock:
        print("[Main] Running in MOCK mode")
        app_id = "mock_app_id"
        app_secret = "mock_app_secret"
    elif not app_id or not app_secret or "xxxx" in app_id:
        print("❌ Feishu credentials not configured!")
        print("   Please edit .env.feishu with your app credentials")
        print("   Get them from: https://open.feishu.cn/app")
        sys.exit(1)

    # Create runtime
    workspace_root = Path(os.getenv("SAILZEN_WORKSPACE_ROOT", "D:/ws/repos/SailZen"))

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║         SailZen Feishu Dev Bot - Phase 0 MVP                 ║
╠══════════════════════════════════════════════════════════════╣
║  Workspace: {str(workspace_root)[:48]:<48} ║
║  Mock Mode: {str(args.mock):<48} ║
║  From OpenCode: {str(args.from_opencode):<44} ║
╚══════════════════════════════════════════════════════════════╝
""")

    runtime = SailZenBotRuntime(
        app_id=app_id,
        app_secret=app_secret,
        workspace_root=workspace_root,
    )

    # Initialize
    initialized = await runtime.initialize(restore_state=args.restore)
    if not initialized:
        print("❌ Failed to initialize bot runtime")
        sys.exit(1)

    # Trigger self-update if requested (from OpenCode)
    if args.update_trigger and args.from_opencode:
        print("[Main] Triggering self-update from OpenCode session...")
        success = await runtime.request_self_update(
            reason="Triggered from OpenCode session for self-modification",
            source=UpdateTriggerSource.OPENCODE_SESSION,
            initiated_by="opencode_session",
        )
        if success:
            print("✅ Self-update initiated successfully")
            print("   New process should take over shortly")
            print("   This process will exit gracefully")
        else:
            print("❌ Self-update failed")
        return

    # Run normally
    try:
        await runtime.start()
    except KeyboardInterrupt:
        print("\n[Main] Interrupted by user")
    finally:
        print("[Main] Bot stopped")


def show_status():
    """Show bot status from backup files."""
    from sail_server.feishu_gateway.bot_state_manager import get_state_manager

    state_manager = get_state_manager()
    backups = state_manager.list_backups()

    print("\n🤖 SailZen Bot Status")
    print("=" * 50)

    if backups:
        print(f"\n📦 Available Backups ({len(backups)}):")
        for i, backup in enumerate(backups[:5], 1):
            stat = backup.stat()
            print(f"  {i}. {backup.name}")
            print(f"     Size: {stat.st_size} bytes")
            print(f"     Time: {time.ctime(stat.st_mtime)}")
    else:
        print("\n📦 No backups found")

    # Check for handover files
    import tempfile

    handover_dir = Path(tempfile.gettempdir()) / "sailzen_bot_handover"
    if handover_dir.exists():
        handover_files = list(handover_dir.glob("handover_*.json"))
        if handover_files:
            print(f"\n🔄 Recent Handover Files ({len(handover_files)}):")
            for hf in sorted(handover_files)[-3:]:
                try:
                    data = json.loads(hf.read_text())
                    print(f"  - Old PID: {data.get('old_pid')}")
                    print(f"    Reason: {data.get('trigger_reason', 'N/A')[:40]}")
                except Exception:
                    print(f"  - {hf.name} (unreadable)")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
