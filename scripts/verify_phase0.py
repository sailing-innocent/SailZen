# -*- coding: utf-8 -*-
# @file verify_phase0.py
# @brief Verification script for Phase 0 implementation
# @author sailing-innocent
# @date 2026-03-29
# @version 1.0
# ---------------------------------
"""Quick verification script for Phase 0 MVP implementation."""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing module imports...")

    try:
        from sail_server.feishu_gateway.bot_state_manager import (
            BotStateManager,
            BotSessionState,
            get_state_manager,
        )

        print("✅ bot_state_manager")
    except Exception as e:
        print(f"❌ bot_state_manager: {e}")
        return False

    try:
        from sail_server.feishu_gateway.self_update_orchestrator import (
            SelfUpdateOrchestrator,
            UpdatePhase,
            UpdateTriggerSource,
        )

        print("✅ self_update_orchestrator")
    except Exception as e:
        print(f"❌ self_update_orchestrator: {e}")
        return False

    try:
        from sail_server.feishu_gateway.bot_runtime import (
            SailZenBotRuntime,
            FeishuLongConnectionClient,
        )

        print("✅ bot_runtime")
    except Exception as e:
        print(f"❌ bot_runtime: {e}")
        return False

    try:
        from sail_server.feishu_gateway.bot_control_integration import (
            BotControlIntegration,
        )

        print("✅ bot_control_integration")
    except Exception as e:
        print(f"❌ bot_control_integration: {e}")
        return False

    try:
        from sail_server.feishu_gateway.cards import CardRenderer, CardTemplate

        print("✅ cards")
    except Exception as e:
        print(f"❌ cards: {e}")
        return False

    try:
        from sail_server.feishu_gateway.session_orchestrator import (
            SessionOrchestrator,
            SessionStatus,
            TaskStatus,
        )

        print("✅ session_orchestrator")
    except Exception as e:
        print(f"❌ session_orchestrator: {e}")
        return False

    return True


def test_state_manager():
    """Test state manager functionality."""
    print("\nTesting state manager...")

    try:
        from sail_server.feishu_gateway.bot_state_manager import get_state_manager

        # Create state manager with temp directory
        import tempfile

        temp_dir = Path(tempfile.mkdtemp())

        manager = get_state_manager(backup_dir=temp_dir)
        state = manager.initialize_session()

        print(f"✅ Session initialized: {state.session_id[:20]}...")

        # Test backup
        backup_path = manager.create_backup(reason="test", initiated_by="verify_script")
        print(f"✅ Backup created: {backup_path.name}")

        # Test restore
        restored = manager.restore_from_backup()
        if restored:
            print(f"✅ State restored: {restored.session_id[:20]}...")

        # Cleanup
        manager.cleanup_current_session()
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

        return True

    except Exception as e:
        print(f"❌ State manager test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_update_orchestrator():
    """Test update orchestrator."""
    print("\nTesting update orchestrator...")

    try:
        from sail_server.feishu_gateway.self_update_orchestrator import (
            SelfUpdateOrchestrator,
            UpdatePhase,
        )
        from sail_server.feishu_gateway.bot_state_manager import get_state_manager

        import tempfile

        temp_dir = Path(tempfile.mkdtemp())

        state_manager = get_state_manager(backup_dir=temp_dir)
        state_manager.initialize_session()

        orchestrator = SelfUpdateOrchestrator(
            state_manager=state_manager, workspace_root=Path(".")
        )

        print(f"✅ Update orchestrator created")
        print(f"   Initial phase: {orchestrator.current_phase.name}")

        # Test handover detection
        handover = SelfUpdateOrchestrator.check_for_handover()
        if handover:
            print(f"✅ Handover detected: {handover}")
        else:
            print("   No handover detected (expected)")

        # Cleanup
        state_manager.cleanup_current_session()
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

        return True

    except Exception as e:
        print(f"❌ Update orchestrator test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_cards():
    """Test card rendering."""
    print("\nTesting card rendering...")

    try:
        from sail_server.feishu_gateway.cards import CardRenderer

        # Test workspace home card
        card = CardRenderer.render_workspace_home(
            workspaces=[
                {"slug": "test", "name": "Test Workspace", "path": "/tmp/test"}
            ],
            active_sessions=[],
        )
        print(f"✅ Workspace home card rendered")
        print(f"   Elements: {len(card.get('elements', []))}")

        # Test session cockpit card
        card = CardRenderer.render_session_cockpit(
            session={
                "id": "sess_test",
                "workspace_name": "Test",
                "status": "running",
                "branch": "main",
            },
            recent_events=[],
        )
        print(f"✅ Session cockpit card rendered")
        print(f"   Template: {card.get('header', {}).get('template', 'default')}")

        return True

    except Exception as e:
        print(f"❌ Card rendering test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_control_integration():
    """Test control integration."""
    print("\nTesting control integration...")

    try:
        from sail_server.feishu_gateway.bot_control_integration import (
            BotControlIntegration,
        )
        from sail_server.feishu_gateway.bot_state_manager import get_state_manager

        import tempfile

        temp_dir = Path(tempfile.mkdtemp())

        state_manager = get_state_manager(backup_dir=temp_dir)
        state_manager.initialize_session()

        integration = BotControlIntegration(
            state_manager=state_manager, workspace_root=Path(".")
        )

        # Test list workspaces
        workspaces = integration.list_workspaces()
        print(f"✅ Listed {len(workspaces)} workspaces")

        # Test render card
        card = integration.render_workspace_home_card()
        print(f"✅ Rendered workspace home card")

        # Cleanup
        state_manager.cleanup_current_session()
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

        return True

    except Exception as e:
        print(f"❌ Control integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("SailZen Phase 0 MVP - Verification Script")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Module Imports", test_imports()))
    results.append(("State Manager", test_state_manager()))
    results.append(("Update Orchestrator", test_update_orchestrator()))
    results.append(("Card Rendering", test_cards()))
    results.append(("Control Integration", test_control_integration()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! Phase 0 MVP is ready.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
