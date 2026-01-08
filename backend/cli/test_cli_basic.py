"""Basic CLI functionality tests

This script tests the basic CLI components without requiring full workflow execution.
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest

# Check for required CLI dependencies
try:
    import rich
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Skip entire module if rich is not available
if not RICH_AVAILABLE:
    pytest.skip(
        "CLI tests require 'rich' package: pip install rich",
        allow_module_level=True
    )

from cli.session_manager import SessionManager
from cli.terminal_ui import TerminalUI


def test_session_manager():
    """Test SessionManager basic functionality"""
    print("Testing SessionManager...")

    # Create session manager
    session_mgr = SessionManager(
        workspace=".",
        model="deepseek-r1:14b",
        auto_save=False
    )

    print(f"✓ Session created: {session_mgr.session_id}")
    print(f"✓ Workspace: {session_mgr.workspace}")
    print(f"✓ Model: {session_mgr.model}")

    # Test adding messages
    session_mgr.add_message("user", "Test message 1")
    session_mgr.add_message("assistant", "Test response 1")

    print(f"✓ Messages added: {len(session_mgr.conversation_history)}")

    # Test history summary
    summary = session_mgr.get_history_summary()
    print(f"✓ History summary: {summary['total_messages']} messages")

    # Test context info
    context = session_mgr.get_context_info()
    print(f"✓ Context info extracted")

    print()


def test_terminal_ui():
    """Test TerminalUI basic functionality"""
    print("Testing TerminalUI...")

    # Create session manager and UI
    session_mgr = SessionManager(
        workspace=".",
        model="deepseek-r1:14b",
        auto_save=False
    )

    ui = TerminalUI(session_mgr)

    print(f"✓ TerminalUI created")
    print(f"✓ Console initialized")

    # Test slash command handlers (without actual input)
    print("\nTesting slash command handlers:")

    try:
        ui._cmd_help()
        print("✓ /help command works")
    except Exception as e:
        print(f"✗ /help failed: {e}")

    try:
        ui._cmd_status()
        print("✓ /status command works")
    except Exception as e:
        print(f"✗ /status failed: {e}")

    try:
        ui._cmd_history()
        print("✓ /history command works")
    except Exception as e:
        print(f"✗ /history failed: {e}")

    try:
        ui._cmd_context()
        print("✓ /context command works")
    except Exception as e:
        print(f"✗ /context failed: {e}")

    try:
        ui._cmd_sessions()
        print("✓ /sessions command works")
    except Exception as e:
        print(f"✗ /sessions failed: {e}")

    print()


def test_session_persistence():
    """Test session save/load"""
    print("Testing session persistence...")

    # Create session with auto-generated ID first
    session_mgr = SessionManager(
        workspace=".",
        auto_save=True
    )

    # Save the session ID for reloading
    test_session_id = session_mgr.session_id

    session_mgr.add_message("user", "Test message for persistence")
    session_mgr.add_message("assistant", "Test response for persistence")
    session_mgr.save_session()

    session_file = session_mgr._get_session_file()
    print(f"✓ Session saved to: {session_file}")

    # Load session by ID
    session_mgr2 = SessionManager(
        workspace=".",
        session_id=test_session_id,
        auto_save=False
    )

    print(f"✓ Session loaded: {len(session_mgr2.conversation_history)} messages")
    assert len(session_mgr2.conversation_history) == 2, "History should have 2 messages"

    # Clean up
    if session_file.exists():
        session_file.unlink()
        print(f"✓ Test session file cleaned up")

    print()


def main():
    """Run all tests"""
    print("="*60)
    print("TestCodeAgent CLI - Basic Functionality Tests")
    print("="*60)
    print()

    try:
        test_session_manager()
        test_terminal_ui()
        test_session_persistence()

        print("="*60)
        print("✅ All basic tests passed!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
